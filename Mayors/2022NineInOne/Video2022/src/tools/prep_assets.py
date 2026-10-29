#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prep_assets.py —— 2022 九合一縣市長看板的素材前處理。

把「原圖」轉成看板引擎吃得下的「透明化成品」，唯一落點 dist/assets/：

    assets/map/village/<縣市>_村里級.png  →  dist/assets/map/<slug>/village.png   （主圖）
    assets/map/town/<縣市>_鄉鎮級.png     →  dist/assets/map/<slug>/town.png      （右欄圖）
    assets/share/徽章/<縣市徽>.png        →  dist/assets/share/seal/<slug>.png    （頁眉徽章卡）

地圖走 how="whiteblack"：白底轉透明 **且** 純黑界線轉白線。
（看板底色是深色街景，黑界線會整個消失；5px 縣市界轉白才浮得出來。
  兩個遮罩必須在同一次掃描裡從原圖算出來，先轉白再轉透明會把白線吃掉。）

徽章只做白底轉透明（卡片本身是白底圓角卡，硬邊鋸齒的白色殘邊正好融進卡片）。

用法：
    python src/tools/prep_assets.py            # 全部（已存在的成品不重做）
    python src/tools/prep_assets.py --force    # 全部重做
    python src/tools/prep_assets.py --only 臺北市 新北市
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_transparent as MT   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_ASSETS = os.path.join(ROOT, "dist", "assets")
DATASET = os.path.join(ROOT, "data", "nine2022.json")


def load_counties():
    with open(DATASET, encoding="utf-8") as f:
        return json.load(f)["counties"]


def conv(src, dst, how, force):
    if not os.path.isfile(src):
        return "MISSING %s" % os.path.relpath(src, ROOT)
    if os.path.isfile(dst) and not force:
        return "skip（已存在）"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if how == "whiteblack":
        MT.white_to_transparent_black_to_white(src, dst, threshold=12)
    else:
        MT.white_to_transparent(src, dst, threshold=12)
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    counties = load_counties()
    if args.only:
        want = set(args.only)
        counties = [c for c in counties if c["name"] in want]
        if not counties:
            raise SystemExit("--only 沒有符合的縣市")

    stat = {"ok": 0, "skip": 0, "miss": 0}
    for c in counties:
        slug = c["slug"]
        jobs = [
            (os.path.join(ROOT, "assets", "map", "village", c["mapVillage"]),
             os.path.join(DIST_ASSETS, "map", slug, "village.png"), "whiteblack"),
            (os.path.join(ROOT, "assets", "map", "town", c["mapTown"]),
             os.path.join(DIST_ASSETS, "map", slug, "town.png"), "whiteblack"),
            (os.path.join(ROOT, "assets", "share", "徽章", c["sealSrc"]),
             os.path.join(DIST_ASSETS, "share", "seal", slug + ".png"), "white"),
        ]
        for src, dst, how in jobs:
            r = conv(src, dst, how, args.force)
            if r.startswith("MISSING"):
                stat["miss"] += 1
                print("  [缺件]", r)
            elif r.startswith("skip"):
                stat["skip"] += 1
            else:
                stat["ok"] += 1
        print("  ✓", c["name"])
    print("\n完成：處理 %d、略過 %d、缺件 %d" % (stat["ok"], stat["skip"], stat["miss"]))


if __name__ == "__main__":
    main()
