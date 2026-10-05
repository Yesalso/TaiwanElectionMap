#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_assets.py —— 素材透明化（去背）管線。

★ 唯一落點：``NewSolution/png/processed/``

    原始素材                          成品
    ---------------------------------  ----------------------------------------
    png/map/<year>/map.png             png/processed/map/<year>/map.png
    png/map/<year>/legend.png          png/processed/map/<year>/legend.png
    png/party/<政黨名>.png             png/processed/party/party_<key>.png
    png/share/<素材名>.png             png/processed/share/<成品名>.png

本檔之外不要再寫出透明化成品（不回寫 png/ 的原圖、也不寫進 boards/<id>/assets/）。
看板端（boards/<id>/board.files.js）直接引用 processed/ 底下的檔案。

★ 沒有候選人照片這一類。看板不畫候選人照片（卡面只填政黨純色，見
   _engine/js/render/layers.js 的 CandidateLayer），所以這條管線也不需要
   處理候選人圖檔；png/candidate/ 底下的原圖留著當素材，不再產生任何成品。

兩種處理方式（配方集中在這條管線，看板端不需要知道）：

  地圖        純白底轉透明（threshold 12，實作在 make_transparent.py）。
  圖例        原樣沿用（copy）—— 它由 Converge_to_map_taipei.py 直接畫成
              「透明底 + 白字 + 色塊」的 RGBA，白字本身就是 RGB(255,255,255)，
              再過一次白底轉透明會被整片吃掉，所以這裡只搬檔、不轉換。
  黨徽 / 市徽 / 國徽 / 當選標誌
              tools/boardlib/assets.py 的 STATIC_RECIPES —— 白底轉透明是唯一
              規則，圓形主體（國徽、兩張黨徽）額外走內切圓；配方以「成品檔名」查表。

用法：
    python tool/build_assets.py                     # 全部（依 assets.map.json）
    python tool/build_assets.py --year 2018         # 只做 2018
    python tool/build_assets.py --kind map          # 只做某一類
    python tool/build_assets.py --force             # 已存在的成品也重做
    python tool/build_assets.py --dry-run           # 只列出會做什麼
    python tool/build_assets.py --check             # 只檢查成品是否齊備（CI 用）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]        # .../NewSolution
PNG_DIR = BASE_DIR / "png"
OUT_ROOT = PNG_DIR / "processed"
VIDEO_ROOT = BASE_DIR.parent
MAP_FILE = Path(__file__).resolve().parent / "assets.map.json"

# 透明化的實作分兩處，這裡直接重用、不另抄一份：
#   地圖 / 圖例         本目錄的 make_transparent.py（白底 -> 透明）
#   黨徽 / 市徽 / 國徽    Video/tools/boardlib/assets.py（配方表 STATIC_RECIPES）
sys.path.insert(0, str(VIDEO_ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from boardlib import assets as A                       # noqa: E402
import make_transparent as MT                          # noqa: E402

# 地圖 / 圖例的白底容差：與既有看板在用的產物一致，換到這條管線不會讓版面
# 產生任何像素差異。（threshold 12 -> 每條通道 >= 243。）
MAP_WHITE_THRESHOLD = 12

KINDS = ("map", "party", "share")


# ----------------------------------------------------------------- 設定
def load_map(path: Path = MAP_FILE) -> dict:
    if not path.is_file():
        raise SystemExit("找不到對應表：%s" % path)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for k in cfg:
        if k.startswith("_"):
            continue
        if k not in KINDS:
            raise SystemExit("assets.map.json 有未知的類別 %r（可用：%s）"
                             % (k, "、".join(KINDS)))
    return cfg


# ----------------------------------------------------------------- 兩種處理方式
def build_white(src: Path, dst: Path, threshold: int = MAP_WHITE_THRESHOLD) -> str:
    """純白底 -> 透明（地圖）。

    直接呼叫 make_transparent.white_to_transparent，不在這裡另抄一套 ——
    兩邊只要有一邊改了公式，地圖邊緣就會多出白邊或灰邊，而且不容易在縮圖上
    看出來。
    """
    MT.white_to_transparent(str(src), str(dst), threshold=threshold)
    return "白底轉透明（threshold %d）" % threshold


def build_copy(src: Path, dst: Path) -> str:
    """原圖本身就是最終成品（透明底 RGBA）——原樣搬成成品，不做任何轉換。

    只有圖例走這條：Converge_to_map_taipei.py 直接畫成「透明底 + 白字 + 色塊」，
    白字就是 RGB(255,255,255)，再過一次白底轉透明會被整片吃掉。
    """
    shutil.copyfile(src, dst)
    return "已是透明底 RGBA，原樣沿用（不做白底轉透明）"


def build_static(src: Path, dst: Path, filename: str) -> str:
    """黨徽 / 市徽 / 國徽 / 當選標誌 —— 走 boardlib 的配方表。"""
    note = A.build_static(str(src), str(dst), filename)
    if note is None:
        raise RuntimeError(
            "%s 在 boardlib.assets.STATIC_RECIPES 裡沒有配方；"
            "請補配方，或把這張圖改成走 build_white()" % filename)
    return note


# ----------------------------------------------------------------- 掃描
def tasks_for(cfg: dict, kinds, years):
    """把 assets.map.json 攤平成 [(kind, src, dst, how)]。"""
    out = []

    def want(kind, year=None):
        if kinds and kind not in kinds:
            return False
        if years and year is not None and str(year) not in years:
            return False
        return True

    for year, entries in (cfg.get("map") or {}).items():
        if not want("map", year):
            continue
        for name, spec in entries.items():
            # 值可以是成品檔名（預設白底轉透明），或 {"to": 檔名, "how": "copy"}
            if isinstance(spec, dict):
                dstname = spec.get("to", name)
                how = spec.get("how", "white")
            else:
                dstname, how = spec, "white"
            out.append(("map",
                        PNG_DIR / "map" / year / name,
                        OUT_ROOT / "map" / year / dstname,
                        how))

    for kind in ("party", "share"):
        for name, dstname in (cfg.get(kind) or {}).items():
            if not want(kind):
                continue
            out.append((kind,
                        PNG_DIR / kind / name,
                        OUT_ROOT / kind / dstname,
                        "static"))

    return out


def run_one(task, force: bool, dry: bool):
    kind, src, dst, how = task
    if not src.is_file():
        return ("missing", "%s 不存在（原圖請放進 png/%s/）"
                % (src.relative_to(BASE_DIR), kind))
    if dst.is_file() and not force:
        return ("skip", "%s（已存在，--force 可重做）"
                % dst.relative_to(BASE_DIR))
    if dry:
        return ("would", "%s -> %s" % (src.relative_to(BASE_DIR),
                                       dst.relative_to(BASE_DIR)))
    os.makedirs(dst.parent, exist_ok=True)
    if how == "copy":
        note = build_copy(src, dst)
    elif how == "white":
        note = build_white(src, dst)
    else:
        note = build_static(src, dst, dst.name)
    return ("built", "%s -> %s\n        %s"
            % (src.relative_to(BASE_DIR), dst.relative_to(BASE_DIR), note))


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="素材透明化管線（成品只寫 png/processed/）")
    ap.add_argument("--year", action="append", default=[],
                    help="只做這個年份（可重複；不給 = 全部）")
    ap.add_argument("--kind", action="append", default=[],
                    choices=KINDS, help="只做這一類（可重複）")
    ap.add_argument("--force", action="store_true", help="已存在的成品也重做")
    ap.add_argument("--dry-run", action="store_true", help="只列出會做什麼")
    ap.add_argument("--check", action="store_true",
                    help="只檢查成品齊備（不做任何寫檔）；缺件退出碼 1")
    args = ap.parse_args()

    cfg = load_map()
    years = set(args.year)
    kinds = set(args.kind)
    tasks = tasks_for(cfg, kinds, years)

    print("成品根：%s" % OUT_ROOT.relative_to(VIDEO_ROOT))
    print("原始素材：%s" % PNG_DIR.relative_to(VIDEO_ROOT))
    print("共 %d 個項目\n" % len(tasks))

    stats = {"built": 0, "skip": 0, "missing": 0, "would": 0}
    for task in tasks:
        state, note = run_one(task, args.force, args.dry_run or args.check)
        stats[state] = stats.get(state, 0) + 1
        mark = {"built": "✓", "skip": "·", "missing": "!", "would": "?"}[state]
        print("  %s %s" % (mark, note))

    print("\n完成 %d / 沿用 %d / 缺原圖 %d%s"
          % (stats["built"], stats["skip"], stats["missing"],
             " / 待做 %d" % stats["would"] if stats["would"] else ""))

    ok = not (args.check and (stats["missing"] or stats["would"]))
    if args.check and not ok:
        print("\n[檢查失敗] 成品不齊備；跑 python tool/build_assets.py 產生。")
    if args.check:
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
