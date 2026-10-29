#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_boards.py —— 2022 九合一縣市長看板場次產生器（22 場）。

讀 data/nine2022.json（build_2022_dataset.py 產生）→ 逐縣市寫出：

    src/boards/2022-<slug>/meta.json          場次宣告（render_boards.mjs 靠它列場次）
    dist/boards/2022-<slug>/board.js          window.BOARD = {meta, candidates, districts, geojson}
    dist/boards/2022-<slug>/board.files.js    邏輯素材名 → 實際檔案（dist/assets/ 下的透明化成品）
    dist/boards/2022-<slug>/index.html        引擎殼（複製 src/templates/index.html）

★ 這條線跟 Video/ 那兩條（市長、總統）的差別：
  · 一個縣市一場，場次 id 是 2022-<縣市代號>（英數，因為渲染器的輸出檔名
    只留 A-Za-z0-9._-，中文會被消毒成 _ 而撞名）。
  · 沒有 source/data.xlsx、不跑 build_board.py（那條要 SHP 幾何）：
    地圖是現成的 PNG（村里級＋鄉鎮級），資料直接用官方得票數，
    所以 board.js 由本檔直接寫，跟總統桃竹苗線同一個做法。
  · 沒有副手（vice 欄位不寫），第 3 名以後的卡片自動吃「只有姓名/政黨」。

用法：
    python src/tools/gen_boards.py              # 全部 22 場
    python src/tools/gen_boards.py 臺北市 高雄市  # 指定縣市
"""
from __future__ import annotations

import json
import os
import shutil
import sys

import openpyxl  # noqa: F401  （留著：確認環境有裝，資料是 xlsx 來源）

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(ROOT, "data", "nine2022.json")
SRC_BOARDS = os.path.join(ROOT, "src", "boards")
DIST_BOARDS = os.path.join(ROOT, "dist", "boards")
DIST_ASSETS = os.path.join(ROOT, "dist", "assets")
INDEX_TPL = os.path.join(ROOT, "src", "templates", "index.html")


def files_for(c):
    """邏輯素材名 → 相對路徑（相對 dist/boards/<id>/index.html）。

    鍵名去掉 "assets/" 前綴（引擎的 U.resolveAsset 就是這樣對表的）。
    """
    slug = c["slug"]
    f = {
        "city_seal.png": "../../assets/share/seal/%s.png" % slug,
        "emblem.png": "../../assets/share/emblem.png",
        "mark_elected.png": "../../assets/share/mark_elected.png",
        "roc_flag.png": "../../assets/share/roc_flag.png",
        "street_bg.png": "../../assets/share/street_bg.png",
        "map.png": "../../assets/map/%s/village.png" % slug,
        "map2.png": "../../assets/map/%s/town.png" % slug,
    }
    for key in sorted({x["partyShort"].lower() for x in c["candidates"]} | {"ind"}):
        p = os.path.join(DIST_ASSETS, "party", "party_%s.png" % key)
        if os.path.isfile(p):
            f["party_%s.png" % key] = "../../assets/party/party_%s.png" % key
    return f


def layout_for(c):
    """逐場版面覆寫（引擎 layout.js 的 LAYOUT_OVERRIDABLE：legend / map / map2）。

    ★ 橫長型縣市（金門、臺中、嘉義縣、雲林，地圖寬高比 ≥ 1.4）另外處理：
      主圖用滿 1000px 寬（預設框只有 820，橫長圖會被縮得很小），
      並把右欄的鄉鎮級圖關掉 —— 那種縣市的鄉鎮圖本身就是一條細長條，
      塞進右欄只會變成看不懂的小色塊。
      其餘縣市維持「主圖 820 + 右欄鄉鎮圖」。
    """
    lay = {"legend": {"disabled": True}}
    src = os.path.join(ROOT, "assets", "map", "village", c["mapVillage"])
    if os.path.isfile(src):
        from PIL import Image
        with Image.open(src) as im:
            ar = im.width / float(im.height)
        if ar >= 1.4:
            lay["map"] = {"x": 576, "y": 214, "w": 1000, "h": 880}
            lay["map2"] = {"enabled": False}
    return lay


def build_one(c):
    bid = c["id"]
    src_dir = os.path.join(SRC_BOARDS, bid)
    out_dir = os.path.join(DIST_BOARDS, bid)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    layout = layout_for(c)

    meta = {
        "election": c["election"],
        "electionEn": c["electionEn"],
        "year": 2022,
        "date": c["date"],
        "dateEn": c["dateEn"],
        "country": "中華民國（台灣）",
        "countryEn": "Republic of China (Taiwan)",
        "office": c["office"],
        "officeEn": c["officeEn"],
        "subtitle": c["subtitle"],
        # 頁眉數據列：一項一行（Layout.header.stats / layers.js HeaderLayer ③）
        "statsRows": c["statsRows"],
        # 頁眉右側「當選人」（layers.js HeaderLayer ④ 吃這一格）
        "header": {
            "role": "當選人",
            "name": c["winner"]["name"],
            "party": c["winner"]["party"],
            "partyShort": c["winner"]["partyShort"],
        },
        # 舊欄位一併寫，供驗證 / 除錯與日後想恢復「投票率·有效票」單行時使用
        "electorate": c["stats"]["electorate"],
        "castVotes": c["stats"]["cast"],
        "validVotes": c["stats"]["valid"],
        "invalidVotes": c["stats"]["invalid"],
        "turnout": c["stats"]["turnout"],
        # 逐場版面覆寫（圖例一律關；橫長型縣市另有 map / map2 覆寫，見 layout_for）
        "layout": layout,
    }

    board_meta = dict(meta, id=bid, layout=layout)
    board = {
        "meta": board_meta,
        "candidates": c["candidates"],
        "districts": c["districts"],
        "geojson": {"type": "FeatureCollection", "features": []},
    }

    with open(os.path.join(src_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"id": bid, "meta": meta,
                   "candidates": c["candidates"]}, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "board.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。\n"
                "   來源：data/nine2022.json（22 縣市 xlsx ＋ 2022 縣市長選舉簡報）\n"
                "   建置：Video2022/src/tools/gen_boards.py  %s（2022 九合一）\n*/\n"
                % c["name"])
        f.write("window.BOARD = " + json.dumps(board, ensure_ascii=False) + ";\n")

    with open(os.path.join(out_dir, "board.files.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。\n"
                "   邏輯素材名 -> 實際檔案（透明化成品在 dist/assets/）\n"
                "   建置：Video2022/src/tools/gen_boards.py  %s（2022 九合一）\n*/\n"
                % c["name"])
        f.write("window.BOARD_FILES = " +
                json.dumps({"files": files_for(c)}, ensure_ascii=False, indent=2) + ";\n")

    shutil.copyfile(INDEX_TPL, os.path.join(out_dir, "index.html"))
    return board


def main():
    with open(DATASET, encoding="utf-8") as f:
        counties = json.load(f)["counties"]
    if not os.path.isfile(INDEX_TPL):
        raise SystemExit("找不到引擎殼 src/templates/index.html")

    want = set(sys.argv[1:])
    if want:
        counties = [c for c in counties if c["name"] in want or c["slug"] in want]
        if not counties:
            raise SystemExit("沒有符合的縣市：%s" % " ".join(sorted(want)))

    for c in counties:
        b = build_one(c)
        print("  ✓ %-18s %2d 位候選人  當選 %s（%s）"
              % (c["id"], len(b["candidates"]),
                 c["winner"]["name"], c["winner"]["partyShort"]))
    print("\n完成 %d 場。下一步：\n"
          "  python src/tools/prep_assets.py\n"
          "  node src/tools/render_boards.mjs --all --scale 1\n"
          "  python src/tools/verify_layout.py" % len(counties))


if __name__ == "__main__":
    main()
