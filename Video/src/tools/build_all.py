# -*- coding: utf-8 -*-
"""build_all.py —— 批次建置編排器（單進程，不再逐場起 Python）。

為什麼要有這支
--------------
本專案有三條建置路線，產物落點相同（dist/boards/<id>/），但入口不同：

  build_board.py                台北市長（8 場）—— 讀 xlsx + SHP 建 geojson
  _gen_president_boards.py      總統北北基宜（8 年 × 2 版=16 場）
  _gen_president_boards_tzmm.py 總統桃竹苗（8 場）

以前批次建置靠 shell 迴圈逐場起進程，每場都要付一次
`import geopandas`（≈1.0s）+ 讀全台村里界 SHP（0.2–0.5s）的代價。
本檔在同一個進程裡依「場次 → 建置器」分派，台北那條再用 memo 共用 geojson，
全量建置的時間主要就只剩真正的 I/O 與序列化。

用法
----
  python src/tools/build_all.py --list                # 只列出要建什麼（預設，不寫檔）
  python src/tools/build_all.py --group taipei        # 只建台北市長 8 場
  python src/tools/build_all.py --only 2022-taipei-mayor 2018-taipei-mayor
  python src/tools/build_all.py --all                 # 三條線全建（會呼叫總統生成器）
  python src/tools/build_all.py --group taipei --refresh-geo

★ 預設是 --list（乾跑）。批次建置會覆寫 dist/boards/ 的產物，不該「一個手滑
  就全量重跑」—— 本專案對北北基宜／台北市長兩條既有線有明確的「不重跑」約定，
  要真跑請明確指定 --all / --group / --only。

安全網
------
每一場建置前後都對 board.js 取 SHA256，內容有變就在摘要裡標「內容變動」。
正常情況下（只換建置路徑、不動資料）應該全部「未變」；有沒有動到資料，
一次建置就看得到，不必另外比對。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_board  # noqa: E402  （先 import，讓 boardlib 的 sys.path 設定生效）
from boardlib import naming  # noqa: E402

BOARDS_SRC = os.path.join(naming.VIDEO_ROOT, "src", "boards")

# 場次 id → 建置器。新增一條選舉線就在這裡補一列，
# 沒對上的走 fallback（build_board），並在 --list 時標「未知路線」提醒。
BUILDERS = (
    ("pres-north", re.compile(r"^\d{4}-president-north(-map2)?$"), "_gen_president_boards"),
    ("pres-tzmm", re.compile(r"^\d{4}-president-tzmm(-map2)?$"), "_gen_president_boards_tzmm"),
    ("taipei", re.compile(r"^\d{4}-(taipei|newtpei)-mayor(-map2)?$"), "build_board"),
)


def sha256_of(path):
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_boards():
    """列出 src/boards/ 下的場次（尊重 .skip，跳過 _ 與 . 開頭）。

    回傳 [{id, dir, group, builder, year, skipped}]
    """
    out = []
    for name in sorted(os.listdir(BOARDS_SRC)):
        d = os.path.join(BOARDS_SRC, name)
        if not os.path.isdir(d) or name.startswith("_") or name.startswith("."):
            continue
        meta_path = os.path.join(d, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, encoding="utf-8") as f:
                bid = json.load(f).get("id") or name
        except Exception:
            bid = name

        group, builder = "unknown", "build_board"
        for gname, pat, bname in BUILDERS:
            if pat.match(bid):
                group, builder = gname, bname
                break
        m = re.match(r"^(\d{4})-", bid)
        out.append({
            "id": bid,
            "dir": d,
            "group": group,
            "builder": builder,
            "year": int(m.group(1)) if m else None,
            "skipped": os.path.isfile(os.path.join(d, ".skip")),
        })
    return out


def select(boards, args):
    """依 --group / --only / --all 篩選場次（.skip 一律排除）。"""
    live = [b for b in boards if not b["skipped"]]
    if args.only:
        want = set(args.only)
        picked = [b for b in live if b["id"] in want]
        miss = want - {b["id"] for b in picked}
        if miss:
            raise SystemExit("找不到場次：%s" % "、".join(sorted(miss)))
        return picked
    if args.group:
        return [b for b in live if b["group"] in set(args.group)]
    if args.all:
        return live
    return []          # 都沒指定 = 乾跑


def print_plan(boards, picked):
    groups = {}
    for b in picked:
        groups.setdefault((b["group"], b["builder"]), []).append(b)
    print("場次總覽（src/boards）：%d 場，其中 .skip %d 場"
          % (len(boards), sum(1 for b in boards if b["skipped"])))
    for (gname, builder), items in sorted(groups.items()):
        print("  %-10s %-32s %2d 場" % (gname, builder, len(items)))
        print("             " + "、".join(b["id"] for b in items))
    unknown = [b for b in boards if b["group"] == "unknown" and not b["skipped"]]
    if unknown:
        print("  [注意] 沒有對應建置器的場次（將走 build_board）：%s"
              % "、".join(b["id"] for b in unknown))


def run_build_board(items, args):
    """台北市長線：同進程逐場呼叫 build_board.build_one，共用 geojson memo。"""
    memo = {}
    results = []
    ns = build_board.default_args(skip_geo=args.skip_geo, embed=args.embed,
                                  shp=args.shp, refresh_geo=args.refresh_geo)
    for b in items:
        js = os.path.join(naming.VIDEO_ROOT, "dist", "boards", b["id"], "board.js")
        before = sha256_of(js)
        t0 = time.time()
        print("\n" + "=" * 72)
        print("[%s] %s" % (b["group"], b["id"]))
        try:
            info = build_board.build_one(b["dir"], ns, memo=memo)
            after = sha256_of(js)
            results.append({
                "id": b["id"], "ok": True, "secs": time.time() - t0,
                "changed": before != after, "info": info,
            })
            print("  · %.2fs%s" % (time.time() - t0,
                                   "  內容有變動" if before != after else "  board.js 未變"))
        except SystemExit as e:
            results.append({"id": b["id"], "ok": False, "error": str(e)})
            print("  ✗ 中止：%s" % e)
        except Exception as e:  # noqa: BLE001 —— 批次要跑完，單場失敗只記錄
            results.append({"id": b["id"], "ok": False, "error": repr(e)})
            print("  ✗ 失敗：%r" % e)
    return results


def run_president(items, args):
    """總統線：一條線一個生成器，生成器自己按年份出（含變體），所以按年份去重。"""
    years = sorted({b["year"] for b in items if b["year"]})
    builder = items[0]["builder"]
    mod = __import__(builder)
    results = []
    for y in years:
        t0 = time.time()
        print("\n" + "=" * 72)
        print("[%s] %s  %d 年" % (items[0]["group"], builder, y))
        try:
            mod.build(y)
            results.append({"id": str(y), "ok": True, "secs": time.time() - t0})
            print("  · %.2fs" % (time.time() - t0))
        except Exception as e:  # noqa: BLE001
            results.append({"id": str(y), "ok": False, "error": repr(e)})
            print("  ✗ 失敗：%r" % e)
    return results


def main():
    ap = argparse.ArgumentParser(
        description="批次建置編排器（預設乾跑，要寫檔請明確指定 --all/--group/--only）")
    ap.add_argument("--all", action="store_true", help="全部三條線")
    ap.add_argument("--group", nargs="+", metavar="NAME",
                    choices=[g for g, _p, _b in BUILDERS] + ["unknown"],
                    help="只跑這幾條線：taipei / pres-north / pres-tzmm")
    ap.add_argument("--only", nargs="+", metavar="ID", help="只跑這幾場（場次 id）")
    ap.add_argument("--list", action="store_true", help="只列出計畫（預設行為）")
    ap.add_argument("--refresh-geo", action="store_true", help="忽略 geojson 快取")
    ap.add_argument("--skip-geo", action="store_true", help="不建 geojson（沿用空）")
    ap.add_argument("--shp", metavar="FILE", help="強制指定村里界 SHP")
    ap.add_argument("--embed", action="store_true",
                    help="額外產 board.assets.js（預設不產）")
    args = ap.parse_args()

    boards = scan_boards()
    picked = select(boards, args)
    # 乾跑時把全部在跑的場次列出來，讓人看清「如果 --all 會建哪些」
    print_plan(boards, picked or [b for b in boards if not b["skipped"]])

    if args.list or not picked:
        print("\n[乾跑] 沒有寫入任何檔案。要真的建置請加 --all / --group / --only。")
        return 0

    t0 = time.time()
    results = []
    by_builder = {}
    for b in picked:
        by_builder.setdefault(b["builder"], []).append(b)

    for builder, items in sorted(by_builder.items()):
        if builder == "build_board":
            results += run_build_board(items, args)
        else:
            results += run_president(items, args)

    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]
    changed = [r for r in ok if r.get("changed")]
    print("\n" + "=" * 72)
    print("建置完成：成功 %d / 失敗 %d，總耗時 %.1fs"
          % (len(ok), len(bad), time.time() - t0))
    if changed:
        print("  [注意] board.js 內容有變動的場次：%s"
              % "、".join(r["id"] for r in changed))
    for r in bad:
        print("  ✗ %s：%s" % (r["id"], r.get("error")))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
