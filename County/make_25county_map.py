# -*- coding: utf-8 -*-
"""
把鄉鎮市區「唯一色」底圖 Colorful4.png 改造成「25 縣市版」單色底圖。

Colorful4.png 是 25 縣市時期（台北市／高雄市為直轄市，台中、台南、高雄
皆為「市＋縣」並存）的鄉鎮市區圖，每個鄉鎮市區一個唯一辨識色；
白色 #FFFFFF 為鄉鎮市區界線（本腳本予以抹去），黑色 #000000 為縣市界線（保留）。

做法：
    1. 讀 Name_Color_Correspondence.xlsx（368 鄉鎮市區 → 顏色 / 現行縣市）
    2. 依 SPLIT_RULES 把「台中市／台南市／高雄市」拆成「市區」與「縣」，
       其餘現行縣市直接換成 25 縣市時期的名稱
    3. 以顏色為鍵把每個像素對應到 25 縣市之一 → 縣市標籤圖
    4. 白線像素（鄉鎮界線）以「最近的鄉鎮色像素」所屬縣市填補 → 界線消失
    5. 每個縣市填一種顏色（自動挑選：以相鄰縣市色差最大化為目標）
    6. 輸出底圖 Colorful25.png + 對照表 Name_Color_Correspondence_25.xlsx

共用引擎見 county_map_base.py；22 縣市版見 make_22county_map.py。

執行：
    py make_25county_map.py
"""
import os

import numpy as np
from PIL import Image

import county_map_base as base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PNG = os.path.join(BASE_DIR, "Colorful4.png")
CORR_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence.xlsx")
OUT_PNG = os.path.join(BASE_DIR, "Colorful25.png")
OUT_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence_25.xlsx")

# ===================== 25 縣市拆分規則 =====================
# 現行「市」→（留在市區的區, 市名, 縣名）
SPLIT_RULES = {
    "台中市": ({"西區", "北區", "中區", "東區", "南區", "南屯區", "西屯區", "北屯區"},
               "台中市", "台中縣"),
    "台南市": ({"安南區", "北區", "安平區", "中西區", "南區", "東區"},
               "台南市", "台南縣"),
    "高雄市": ({"楠梓區", "左營區", "鼓山區", "三民區", "鹽埕區", "前金區",
                "新興區", "苓雅區", "前鎮區", "旗津區", "小港區"},
               "高雄市", "高雄縣"),
}

# 其餘縣市：現行名稱 → 25 縣市時期名稱（統一用「台」不用「臺」）
RENAME = {
    "臺北市": "台北市", "新北市": "台北縣", "桃園市": "桃園縣",
    "臺中市": "台中市", "臺南市": "台南市", "臺東縣": "台東縣",
    "高雄市": "高雄市", "基隆市": "基隆市", "新竹市": "新竹市", "嘉義市": "嘉義市",
    "新竹縣": "新竹縣", "苗栗縣": "苗栗縣", "彰化縣": "彰化縣", "南投縣": "南投縣",
    "雲林縣": "雲林縣", "嘉義縣": "嘉義縣", "屏東縣": "屏東縣", "宜蘭縣": "宜蘭縣",
    "花蓮縣": "花蓮縣", "澎湖縣": "澎湖縣", "金門縣": "金門縣", "連江縣": "連江縣",
}

# 對照表／圖例的固定順序（北→南、本島→外島）
COUNTY_ORDER = [
    "台北市", "台北縣", "基隆市", "桃園縣", "新竹縣", "新竹市", "苗栗縣",
    "台中市", "台中縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "台南市", "台南縣", "高雄市", "高雄縣", "屏東縣", "宜蘭縣", "花蓮縣",
    "台東縣", "澎湖縣", "金門縣", "連江縣",
]


def target_county(county22, town):
    """現行縣市 + 鄉鎮市區 → 25 縣市名稱。"""
    rule = SPLIT_RULES.get(county22)
    if rule:
        in_city, city_name, county_name = rule
        return city_name if town in in_city else county_name
    return RENAME.get(county22, county22)


def build_county_table(rows):
    """回傳 (counties, townships)，並把每個鄉鎮市區標上 label。"""
    for r in rows:
        r["county_final"] = target_county(r["county22"], r["town"])

    group = {}
    for r in rows:
        group.setdefault(r["county_final"], []).append(r)

    missing = set(COUNTY_ORDER) - set(group)
    extra = set(group) - set(COUNTY_ORDER)
    if missing or extra:
        raise ValueError(f"縣市集合不符：缺少 {sorted(missing)}，多出 {sorted(extra)}")

    counties = []
    for name in COUNTY_ORDER:
        towns = group[name]
        counties.append({
            "name": name,
            "towns": [t["town"] for t in towns],
            "n": len(towns),
            "index": len(counties) + 1,   # 標籤值 1..25
        })
    for c in counties:
        for t in group[c["name"]]:
            t["label"] = c["index"]
    return counties, rows


def main():
    print("=" * 64)
    print("  Colorful4.png → 25 縣市單色底圖")
    print("=" * 64)

    rows = base.load_correspondence(CORR_XLSX)
    counties, townships = build_county_table(rows)
    print(f"  鄉鎮市區        : {len(townships)} 個")
    print(f"  縣市            : {len(counties)} 個"
          f"（{sum(c['n'] for c in counties)} 個鄉鎮市區全部歸屬）")

    arr = np.array(Image.open(SRC_PNG).convert("RGB"))
    H, W = arr.shape[:2]
    label = base.build_label_map(arr, townships)
    print(f"  底圖            : {W}×{H}，已上標籤像素 {int((label > 0).sum())}，"
          f"其餘（海／線／外框）{int((label == 0).sum())}")

    lacks = [c["name"] for c in counties
             if c["index"] not in set(np.unique(label).tolist())]
    if lacks:
        raise ValueError(f"以下縣市在底圖上找不到任何像素：{lacks}")

    filled, n_line, n_keep = base.erase_township_lines(arr, label)
    print(f"  抹去鄉鎮界線    : {n_line} px（另保留框線／比例尺白像素 {n_keep} px）")

    pairs = base.county_adjacency(label)
    print(f"  縣市相鄰關係    : {len(pairs)} 組")

    colors, min_de = base.assign_colors(len(counties), pairs)
    for c, col in zip(counties, colors):
        c["color"] = col
    print(f"  配色            : 相鄰縣市最小色差 ΔE={min_de:.1f}（Lab）")

    _, out = base.render(SRC_PNG, filled, counties)
    Image.fromarray(out).save(OUT_PNG)
    print(f"  輸出底圖        : {OUT_PNG}")

    base.save_correspondence(OUT_XLSX, counties, townships)
    print(f"  輸出對照表      : {OUT_XLSX}")

    print("-" * 64)
    print("  驗證：")
    base.verify_and_report(out, filled, counties)
    print("=" * 64)


if __name__ == "__main__":
    main()
