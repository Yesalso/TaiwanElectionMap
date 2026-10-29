#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_assets.py —— 素材透明化（去背）管線。

★ 唯一落點：``dist/assets/``

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
              ★ 桃竹苗地圖（map_tzmm.png / map2_tzmm.png）另有一條配方
                how="whiteblack"：白底轉透明 **且** 純黑界線轉白線 ——
                看板底色是深色的，黑界線看不見，轉白才浮得出來。
                （兩個遮罩在同一次掃描裡從原圖算出來，否則白線會被吃掉。）
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
    python tool/build_assets.py --only map_tzmm.png # 只做某些「原始檔名」
    python tool/build_assets.py --force             # 已存在的成品也重做
    python tool/build_assets.py --dry-run           # 只列出會做什麼
    python tool/build_assets.py --check             # 只檢查成品是否齊備（CI 用）
    python tool/build_assets.py --check-drift       # 只查「成品與現配方是否一致」（不寫檔）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]        # .../src/mapgen
VIDEO_ROOT = Path(__file__).resolve().parents[3]       # .../Video（本檔在 src/mapgen/tool/）
ASSETS_ROOT = VIDEO_ROOT / "assets"                    # 素材源（原圖）
PNG_DIR = ASSETS_ROOT                                  # 向後相容別名（內部沿用）
OUT_ROOT = VIDEO_ROOT / "dist" / "assets"              # 透明化成品（唯一落點）
MAP_FILE = Path(__file__).resolve().parent / "assets.map.json"

# 透明化的實作分兩處，這裡直接重用、不另抄一份：
#   地圖 / 圖例         本目錄的 make_transparent.py（白底 -> 透明）
#   黨徽 / 市徽 / 國徽    Video/src/tools/boardlib/assets.py（配方表 STATIC_RECIPES）
sys.path.insert(0, str(VIDEO_ROOT / "src" / "tools"))
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


def build_white_black(src: Path, dst: Path, threshold: int = MAP_WHITE_THRESHOLD) -> str:
    """白底 -> 透明 **且** 純黑界線 -> 白線（桃竹苗地圖專用）。

    兩個遮罩都在同一次掃描裡從**原圖**算出來，否則「黑轉白」做出來的白線
    會被白底遮罩一起吃掉、界線直接消失（詳見 make_transparent.py 裡
    white_to_transparent_black_to_white 的說明）。

    純黑判准**不帶容差**：桃竹苗地圖的界線是 OpenCV 畫的（不抗鋸齒），
    實測整張圖沒有半灰的過渡像素，加容差反而會誤傷深色的填色檔。
    """
    MT.white_to_transparent_black_to_white(str(src), str(dst), threshold=threshold)
    return "白底轉透明（threshold %d）＋ 純黑界線轉白線" % threshold


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
def tasks_for(cfg: dict, kinds, years, only=None):
    """把 assets.map.json 攤平成 [(kind, src, dst, how)]。

    only = 只做這些「原始檔名」（不含副檔名），例如 ("map_tzmm.png",)。
    這是為了改桃竹苗地圖時**不碰市長線 / 北北基宜線的成品**：
    那兩條線共用 map.png / map2.png，`--force` 會把它們一起重寫。
    """
    out = []
    only = set(only or [])

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

    if only:
        out = [t for t in out if t[1].name in only]

    return out


def run_one(task, force: bool, dry: bool):
    kind, src, dst, how = task
    if not src.is_file():
        return ("missing", "%s 不存在（原圖請放進 assets/%s/）"
                % (src.relative_to(VIDEO_ROOT), kind))
    if dst.is_file() and not force:
        return ("skip", "%s（已存在，--force 可重做）"
                % dst.relative_to(VIDEO_ROOT))
    if dry:
        return ("would", "%s -> %s" % (src.relative_to(VIDEO_ROOT),
                                       dst.relative_to(VIDEO_ROOT)))
    os.makedirs(dst.parent, exist_ok=True)
    if how == "copy":
        note = build_copy(src, dst)
    elif how == "white":
        note = build_white(src, dst)
    elif how == "whiteblack":
        note = build_white_black(src, dst)
    else:
        note = build_static(src, dst, dst.name)
    return ("built", "%s -> %s\n        %s"
            % (src.relative_to(VIDEO_ROOT), dst.relative_to(VIDEO_ROOT), note))


# ----------------------------------------------------------------- 漂移检查
def drift_one(task, tmpdir: Path):
    """重算一次成品（寫到臨時目錄）並與既有成品比對，**不碰 dist/assets/**。

    為什麼需要這個：`--force` 一律重做，但如果源圖或配方在上次建置之後變過，
    重做就會**改掉畫面** —— 而看板是拿 dist/assets/ 的成品渲染的，等於三張
    看板會跟著變。2026-10-28 就踩過：2022 的 map/legend/map2 成品比源頭舊，
    按配方重做後 DPP 的綠色明顯變深（map 71 萬像素不同）。

    這支只「報告」，不動任何檔案，讓「成品到底有沒有過期」變成可查的事實。
    """
    kind, src, dst, how = task
    if not src.is_file():
        return ("missing", "%s 不存在" % src.relative_to(VIDEO_ROOT), None)
    if not dst.is_file():
        return ("nodst", "%s 尚無成品" % dst.relative_to(VIDEO_ROOT), None)

    tmp = tmpdir / ("%s__%s.png" % (kind, dst.stem))
    if how == "copy":
        shutil.copyfile(src, tmp)
    elif how == "white":
        build_white(src, tmp)
    elif how == "whiteblack":
        build_white_black(src, tmp)
    else:
        build_static(src, tmp, dst.name)

    if how == "copy":
        same = tmp.read_bytes() == dst.read_bytes()
        return ("same" if same else "drift",
                "%s -> %s" % (src.relative_to(VIDEO_ROOT),
                              dst.relative_to(VIDEO_ROOT)),
                None if same else "字节不同（copy 配方应该是逐字节相同）")

    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(tmp).convert("RGBA")).astype(np.int16)
    b = np.asarray(Image.open(dst).convert("RGBA")).astype(np.int16)
    if a.shape != b.shape:
        return ("drift", "%s -> %s" % (src.relative_to(VIDEO_ROOT),
                                       dst.relative_to(VIDEO_ROOT)),
                "尺寸不同 %s vs %s" % (a.shape, b.shape))
    d = np.abs(a - b)
    n = int((d.sum(axis=2) > 0).sum())
    if n == 0:
        return ("same", "%s -> %s" % (src.relative_to(VIDEO_ROOT),
                                      dst.relative_to(VIDEO_ROOT)), None)
    detail = "像素不同 %s 个（%.2f%%），最大差 %d（%s 通道）" % (
        format(n, ","), n * 100.0 / (a.shape[0] * a.shape[1]),
        int(d.max()), "RGBA"[int(d.max(axis=(0, 1)).argmax())])
    return ("drift", "%s -> %s" % (src.relative_to(VIDEO_ROOT),
                                   dst.relative_to(VIDEO_ROOT)), detail)


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="素材透明化管線（成品只寫 png/processed/）")
    ap.add_argument("--year", action="append", default=[],
                    help="只做這個年份（可重複；不給 = 全部）")
    ap.add_argument("--kind", action="append", default=[],
                    choices=KINDS, help="只做這一類（可重複）")
    ap.add_argument("--only", action="append", default=[],
                    help="只做這些『原始檔名』（可重複；不給 = 全部）。"
                         "例：--only map_tzmm.png --only map2_tzmm.png "
                         "（只重做桃竹苗地圖，市長線 / 北北基宜線的成品完全不動）")
    ap.add_argument("--force", action="store_true", help="已存在的成品也重做")
    ap.add_argument("--dry-run", action="store_true", help="只列出會做什麼")
    ap.add_argument("--check", action="store_true",
                    help="只檢查成品齊備（不做任何寫檔）；缺件退出碼 1")
    ap.add_argument("--check-drift", action="store_true",
                    help="只檢查「既有成品是否仍等於現配方算出來的結果」（不寫檔）。"
                         "有漂移表示源圖或配方在上次建置後改過，"
                         "此時跑 --force 會改動看板畫面。有漂移退出碼 1")
    args = ap.parse_args()

    cfg = load_map()
    years = set(args.year)
    kinds = set(args.kind)
    tasks = tasks_for(cfg, kinds, years, only=args.only)

    print("成品根：%s" % OUT_ROOT.relative_to(VIDEO_ROOT))
    print("原始素材：%s" % PNG_DIR.relative_to(VIDEO_ROOT))
    print("共 %d 個項目\n" % len(tasks))

    if args.check_drift:
        stats = {"same": 0, "drift": 0, "missing": 0, "nodst": 0}
        drifted = []
        with tempfile.TemporaryDirectory() as td:
            for task in tasks:
                state, note, detail = drift_one(task, Path(td))
                stats[state] += 1
                mark = {"same": "·", "drift": "≠", "missing": "!", "nodst": "?"}[state]
                print("  %s %s" % (mark, note))
                if detail:
                    print("      " + detail)
                if state == "drift":
                    drifted.append(task[1])
        print("\n一致 %d / 漂移 %d / 缺原圖 %d / 無成品 %d"
              % (stats["same"], stats["drift"], stats["missing"], stats["nodst"]))
        if drifted:
            print("\n[漂移] 这些成品与现配方不符（跑 --force 会改变看板画面）：")
            for p in drifted:
                print("  - %s" % p.relative_to(VIDEO_ROOT))
            print("建议：先确认源图是不是最新意图，再决定 --force 重做 + 重渲受影响看板。")
        sys.exit(1 if drifted else 0)

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
