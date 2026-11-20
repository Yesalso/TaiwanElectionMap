#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2008-2024 五屆立法委員選舉 — 各鄉鎮市區得票領先政黨得票率地圖（無圖例版）
================================================================
做法沿用 draw_legislator_maps_1992_2004.py：以全台「唯一色」底圖直接重著色，無需 SHP。

與原版（draw_legislator_maps_2008_2024.py）的差異：
    1. 不繪製圖例（連同外框內的標題），輸出純地圖；
    2. 左上角大陸地區 (0,0)-(1065,1065) 矩形區域填為背景色 #323232；
    3. 輸出檔名改用英文：legislative_election_{year}_party_lead_map.png。

底圖（依屆別選用）：
    - 2008（第七屆）：County/Colorful3.png（2008 年代 25 縣市時期行政區畫法）
    - 2012~2024（第八~十一屆）：County/Colorful2.png（現行 22 縣市畫法）
    - 兩張底圖的鄉鎮色板完全相同（380 色一一對應），
      共用同一份 County/Name_Color_Correspondence.xlsx 對照表

得票資料：本目錄 data/{year}立法委員_政黨鄉鎮得票.xlsx（鄉鎮市區級別）
政黨欄位從表頭動態偵測（欄名以「得票率」結尾）。

色階檔位（本屆五屆固定）：
    基準固定 35%，每 5 個百分點一檔（35/40/…/85），末檔為「85%以上」；
    不做 1992-2004 版的自適應位移。（本版不畫圖例，檔位僅用於取色。）

各屆實際「領先政黨」（由資料統計）：
    2008  國民黨/民進黨/無盟/無黨籍/親民黨
    2012  國民黨/民進黨/無黨籍/無盟/親民黨/新黨
    2016  民進黨/國民黨/無黨籍/時代力量/親民黨/新黨
    2020  民進黨/國民黨/無黨籍/台灣基進
    2024  民進黨/國民黨/無黨籍/台灣民眾黨
時代力量、台灣民眾黨 色階取自 LegislationYuan/color.txt（第 7、3 組）；
台灣基進 color.txt 無定義，另配深紅色階。

每屆輸出一張 PNG 至 map/ 子目錄（英文檔名）。

執行：
    python "draw_legislator_maps_2008_2024 - 副本.py"            # 全部五屆
    python "draw_legislator_maps_2008_2024 - 副本.py" 2008       # 只畫某屆
"""
import os
import re
import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTY_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "County")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "map")

CORR_XLSX = os.path.join(COUNTY_DIR, "Name_Color_Correspondence.xlsx")
# 底圖依屆別選用：2008 用 25 縣市時期版（Colorful3），其餘用現行版（Colorful2）
BASE_MAP_DEFAULT = "Colorful2.png"
BASE_MAP_BY_YEAR = {2008: "Colorful3.png"}

# ===================== 五屆選舉定義 =====================
ELECTIONS = [
    # (年份, 屆別, 選舉日期)
    (2008, "第七屆", "2008年1月12日"),
    (2012, "第八屆", "2012年1月14日"),
    (2016, "第九屆", "2016年1月16日"),
    (2020, "第十屆", "2020年1月11日"),
    (2024, "第十一屆", "2024年1月13日"),
]

CANVAS_COLOR = "#323232"   # 畫布背景；同時作為無資料區域的填色（與底圖底色一致）

# ===================== 色階（檔位固定 35 起，5% 間距；末檔 100） =====================
# 顏色來源：LegislationYuan/color.txt（無黨籍/國民黨/民進黨/新黨/親民黨/民眾黨/時代力量等）；
# 时代力量、台灣民眾黨 取 color.txt 第 7、3 組；台灣基進 為自配深紅色階。
# 檔位直接記錄實際邊界值（35/40/…/85/100），末檔 100 為「以上」獨立格。

def _expand_stops(raw, grid):
    """把色階展開到統一邊界 grid：各邊界取「第一個 ≥ 該邊界」的顏色
    （與 get_color_by_value 的取色規則一致，取色結果不變），
    使各政黨格數一致、圖例刻度對齊。"""
    out = []
    for g in grid:
        c = raw[-1][1]
        for u, hx in raw:
            if u >= g:
                c = hx
                break
        out.append((g, c))
    if raw[0][0] == 0:                     # 保留 (0,…) 前導檔位（如新黨）
        out.insert(0, raw[0])
    return out

_RAW_STOPS = {
    # 無黨籍（灰色系）
    "無黨籍及未經政黨推薦": [
        (35, "#D9D9D9"), (40, "#C9C9C9"), (45, "#B6B6B6"), (50, "#A0A0A0"),
        (55, "#898989"), (60, "#727272"), (65, "#5B5B5B"), (70, "#464646"),
        (75, "#333333"), (80, "#232323"), (85, "#151515"), (100, "#151515"),
    ],
    # 中國國民黨（藍色系）
    "中國國民黨": [
        (35, "#A6E9FF"), (40, "#73D9FF"), (45, "#40C8FF"), (50, "#00C0F4"),
        (55, "#00A2E8"), (60, "#0080B8"), (65, "#006591"), (70, "#004B6B"),
        (75, "#003247"), (80, "#00283A"), (85, "#001F2E"), (100, "#010D29"),
    ],
    # 民主進步黨（綠色系）
    "民主進步黨": [
        (35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
        (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
        (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09"),
    ],
    # 新黨（金黃色系）
    "新黨": [
        (0, "#FFF3C4"), (35, "#FFE89A"), (40, "#FFDD66"), (45, "#FFD133"),
        (50, "#FFC700"), (55, "#F2B800"), (60, "#E0A800"), (65, "#C79200"),
        (70, "#AD7A00"), (75, "#946400"), (80, "#4D4900"), (85, "#2E2A00"),
        (100, "#161400"),
    ],
    # 親民黨（橘色系）
    "親民黨": [
        (35, "#FFC2AA"), (40, "#FFA380"), (45, "#FF8456"), (50, "#FF662B"),
        (55, "#FF4701"), (60, "#D93A00"), (65, "#B33000"), (70, "#8D2500"),
        (75, "#6B1D00"), (80, "#4D1400"), (85, "#3A1000"), (100, "#170500"),
    ],
    # 無黨團結聯盟（粉色系）
    "無黨團結聯盟": [
        (35, "#FAC6D8"), (40, "#F8A8C5"), (45, "#F68AB2"), (50, "#F46C9F"),
        (55, "#F24E8C"), (60, "#F03772"), (65, "#D01058"), (70, "#B30D4B"),
        (75, "#950B3F"), (80, "#770932"), (85, "#590726"), (100, "#590726"),
    ],
    # 時代力量（芥黃色系，取自 color.txt 第 7 組；85/100 為延伸暗階）
    "時代力量": [
        (40, "#FFE300"), (45, "#E8B70D"), (50, "#CFA30C"), (55, "#997909"),
        (60, "#695207"), (85, "#403104"), (100, "#2A2003"),
    ],
    # 台灣民眾黨（青綠色系，取自 color.txt 第 3 組）
    "台灣民眾黨": [
        (35, "#00D9CA"), (40, "#00BFB2"), (45, "#00A89C"), (50, "#008080"),
        (55, "#006666"), (60, "#004C4C"), (65, "#003838"), (70, "#003030"),
        (75, "#002626"), (80, "#021F1F"), (85, "#001919"), (100, "#000808"),
    ],
    # 台灣基進（深紅色系，自配；color.txt 無定義）
    "台灣基進": [
        (35, "#FFB3B3"), (40, "#FF8A8A"), (45, "#FF5C5C"), (50, "#F03535"),
        (55, "#D42020"), (60, "#A81414"), (65, "#800D0D"), (70, "#5C0808"),
        (75, "#400505"), (80, "#2A0303"), (85, "#1A0202"), (100, "#0F0101"),
    ],
    # 台灣團結聯盟（咖啡色系；本五屆無領先鄉鎮，保留備用）
    "台灣團結聯盟": [
        (35, "#E8CFAF"), (40, "#E0C199"), (45, "#D8AE7B"), (50, "#CB9450"),
        (55, "#A37135"), (85, "#59401E"), (100, "#59401E"),
    ],
    # 以下色階沿用 1992-2004 版，備用（本五屆未出現於圖例）
    "建國黨": [
        (35, "#73F9E2"), (40, "#40E8D2"), (45, "#00D4C0"), (50, "#00B8A6"),
        (55, "#009385"), (60, "#007468"), (65, "#00564E"), (70, "#003832"),
        (75, "#002420"), (80, "#011C1B"), (85, "#011511"), (100, "#011511"),
    ],
    "中華社會民主黨": [
        (35, "#CFA0FF"), (40, "#BE80FF"), (45, "#AB5FF9"), (50, "#9A43E8"),
        (55, "#7C34B8"), (60, "#612A91"), (65, "#481F6B"), (70, "#301547"),
        (75, "#1E0D2E"), (80, "#170E2A"), (85, "#100729"), (100, "#100729"),
    ],
    "民主聯盟": [
        (35, "#FF98B8"), (40, "#FF6E9B"), (45, "#FF4079"), (50, "#F41E5E"),
        (55, "#C8164C"), (60, "#9E113C"), (65, "#750C2D"), (70, "#520720"),
        (75, "#380517"), (80, "#2B040F"), (85, "#20030B"), (100, "#20030B"),
    ],
    "工黨": [
        (35, "#D9B98D"), (40, "#C99F66"), (45, "#B98545"), (50, "#A66F2B"),
        (55, "#87571F"), (60, "#6B4418"), (65, "#513411"), (70, "#38230B"),
        (75, "#261707"), (80, "#1D1206"), (85, "#170E04"), (100, "#170E04"),
    ],
    "其他政黨": [
        (35, "#C8E88D"), (40, "#B0D966"), (45, "#96C845"), (50, "#7BB22E"),
        (55, "#628F22"), (60, "#4C6E19"), (65, "#395112"), (70, "#28380C"),
        (75, "#1B2508"), (80, "#161D06"), (85, "#111805"), (100, "#111805"),
    ],
}
BLANK_RECT = (0, 0, 1065, 1065)

# 依組別順序，展開成統一邊界（35/40/…/85/100）的色階表
_SCHEME_ORDER = ["中國國民黨", "親民黨", "民主進步黨", "台灣團結聯盟", "新黨",
                 "無黨籍及未經政黨推薦", "建國黨", "中華社會民主黨", "民主聯盟",
                 "工黨", "無黨團結聯盟", "其他政黨",
                 "時代力量", "台灣民眾黨", "台灣基進"]

LEGEND_GRID = list(range(35, 86, 5)) + [100]     # 35,40,…,85,100（固定基準 35）


def scale_fixed():
    """固定基準 35% 的色階表（list，索引同 PARTY_SCHEME 組別）。"""
    return [_expand_stops(_RAW_STOPS[p], LEGEND_GRID) for p in _SCHEME_ORDER]


# ===================== 政黨 → 色階組別 =====================
PARTY_SCHEME = {
    "中國國民黨": 0,              # 藍
    "親民黨": 1,                  # 橘
    "民主進步黨": 2,              # 綠
    "台灣團結聯盟": 3,            # 咖啡
    "新黨": 4,                    # 黃
    "無黨籍及未經政黨推薦": 5,    # 灰
    "無黨籍": 5,                  # 灰
    "建國黨": 6,                  # 青
    "中華社會民主黨": 7,          # 紫
    "民主聯盟": 8,                # 粉
    "工黨": 9,                    # 棕
    "無黨團結聯盟": 10,           # 粉
    "時代力量": 12,               # 芥黃
    "台灣民眾黨": 13,             # 青
    "台灣基進": 14,               # 紅
}
SCHEME_FALLBACK = [11, 6, 7, 8, 9, 10, 12, 13, 14, 0, 1, 2, 3, 4, 5]   # 未知名政黨依序取用

# 圖例欄位排列順序（有領先鄉鎮的政黨才會畫出，其餘依 xlsx 出現順序接在後面）
LEGEND_ORDER = [
    "民主進步黨", "中國國民黨", "親民黨", "新黨", "時代力量",
    "台灣民眾黨", "台灣基進", "無黨籍及未經政黨推薦", "無黨籍",
    "台灣團結聯盟", "建國黨", "中華社會民主黨", "民主聯盟", "工黨",
    "無黨團結聯盟",
]

# ===================== 縣市名映射（當時縣市 → 對照表現行縣市） =====================
OLD_COUNTY_MAP = {
    "臺北縣": "新北市", "桃園縣": "桃園市", "桃園市": "桃園市",
    "臺東縣": "台東縣", "新北市": "新北市",
    "臺中縣": "台中市", "臺中市": "台中市",
    "臺南縣": "台南市", "臺南市": "台南市",
    "高雄縣": "高雄市", "高雄市": "高雄市",
    "宜蘭縣": "宜蘭縣", "花蓮縣": "花蓮縣", "澎湖縣": "澎湖縣",
    "屏東縣": "屏東縣", "彰化縣": "彰化縣", "南投縣": "南投縣",
    "雲林縣": "雲林縣", "嘉義縣": "嘉義縣", "苗栗縣": "苗栗縣",
    "新竹縣": "新竹縣", "基隆市": "基隆市", "新竹市": "新竹市",
    "嘉義市": "嘉義市", "金門縣": "金門縣", "連江縣": "連江縣",
    "臺北市": "臺北市",
}

# 異體字／用字差異正規化（對照表 vs 各屆資料）
VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",   # 苗栗南莊/南庄、雲林鬥六鬥南/斗六斗南
    "褔": "福",               # 彰化縣褔興鄉 ↔ 對照表福興鄉
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中縣后里鄉 ↔ 對照表后里區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}

# 跨縣市同名、需按來源縣市區分的特殊對應（來源 → 對照表）
TOWN_MERGE = {   # 2010 年以前 臺南市 中區＋西區 → 對照表中西區（兩列得票率平均）
    ("臺南市", "中"): "中西",
    ("臺南市", "西"): "中西",
}
SPECIAL_TOWN = {   # 高雄縣三民鄉 → 現那瑪夏區（與高雄市三民區區別）
    ("高雄縣", "三民"): "那瑪夏",
}

# ===================== 繪圖參數 =====================
# 本版不繪製圖例（連同標題），只輸出地圖本體。

# 左上角大陸地區留白矩形：左上角 (x0,y0) 至右下角 (x1,y1)（含端點），
# 以畫布背景色 CANVAS_COLOR 覆蓋，使大陸陸塊與其藍色海岸線一併移除。
# 範圍僅涵蓋大陸沿海（福建／浙江一帶），不含台灣本島、金門、馬祖等圖元。
BLANK_RECT = (0, 0, 1065, 1065)

# ===================== 通用工具 =====================
def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_color_by_value(val, stops):
    if isinstance(val, (float, np.floating)) and np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


# ===================== 讀取對照表 + 得票資料 =====================
def load_correspondence():
    """回傳 (towns, county_code2name)。
    towns: list of dict {code, county, name, core, color_hex, fill_hex}
    """
    df = pd.read_excel(CORR_XLSX, header=None)
    towns = []
    for i in range(1, len(df)):
        col5 = df.iloc[i, 5]                     # 縣市編碼（本表欄位）
        if pd.isna(df.iloc[i, 0]) or pd.isna(col5):
            continue
        towns.append({
            "code": int(col5),
            "county": "",
            "name": str(df.iloc[i, 8]).strip(),
            "core": "",
            "color_hex": str(df.iloc[i, 1]).strip().upper(),
            "fill_hex": None,
        })

    county_code2name = {}
    for i in range(1, min(len(df), 30)):
        c = df.iloc[i, 12]
        nm = df.iloc[i, 13]
        if pd.isna(c) or pd.isna(nm):
            continue
        try:
            code = int(float(c))
        except (TypeError, ValueError):
            continue
        county_code2name[code] = str(nm).strip()

    for t in towns:
        n = county_code2name.get(int(t["code"]), "")
        t["county"] = n.translate(VARIANT_CHAR_MAP)   # 統一 臺→台

    return towns, county_code2name


def norm_town_core(name):
    """鄉鎮市區名 → 正規化核心字（表側用）。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


def parse_votes_year(xlsx_path):
    """各屆 xlsx（鄉鎮市區級別）：縣市、鄉鎮市區 分列，各政黨得票率並排。
    回傳 (data, cand_names, unmatched)
      data: {(target_county, town_core): {party: [rate...]}}（同 key 多列 → 平均）
    """
    df = pd.read_excel(xlsx_path, sheet_name="鄉鎮市區級別")
    df.columns = [str(c) for c in df.columns]
    rate_cols = OrderedDict()
    for col in df.columns:
        if col.endswith("得票率"):
            rate_cols[col[:-3]] = col
    if not rate_cols:
        raise ValueError(f"{xlsx_path} 未偵測到任何「得票率」欄位")
    cand_names = list(rate_cols.keys())
    data = {}
    unmatched = []

    for _, row in df.iterrows():
        src_county = str(row["縣市"]).strip()
        town = str(row["鄉鎮市區"]).strip()
        target = OLD_COUNTY_MAP.get(src_county)
        if target is None:
            unmatched.append((src_county, town))
            continue
        target = target.translate(VARIANT_CHAR_MAP)
        core = norm_town_core(town)
        merge = TOWN_MERGE.get((src_county, core))
        if merge:
            core = merge
        core = SPECIAL_TOWN.get((src_county, core), core)
        key = (target, core)
        rates = {}
        for name in cand_names:
            v = row[rate_cols[name]]
            try:
                v = float(str(v).strip().replace("%", ""))
            except (TypeError, ValueError):
                v = float("nan")
            rates[name] = v
        rec = data.setdefault(key, {})
        for name, v in rates.items():
            rec.setdefault(name, []).append(float(v))
        if all(pd.isna(row[rate_cols[n]]) for n in cand_names):
            unmatched.append((src_county, town))

    avg_data = {}
    for key, rec in data.items():
        avg_data[key] = {n: float(np.mean(v)) for n, v in rec.items()}
    return avg_data, cand_names, unmatched


# ===================== 單屆繪圖 =====================
def draw_year(year, session_label, date_line, towns):
    """繪製單屆地圖。towns 為共享的對照表（fill_hex 會被覆寫）。"""
    print("=" * 62)
    print(f"  {year} {session_label}立法委員選舉")
    print("=" * 62)

    xlsx_path = os.path.join(DATA_DIR, f"{year}立法委員_政黨鄉鎮得票.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"  ※ 找不到 {xlsx_path}，略過本屆（請先執行抓取程式）")
        return False

    data, cand_names, unmatched = parse_votes_year(xlsx_path)
    print(f"  選舉資料           : {len(data)} 個鄉鎮市區（政黨 {len(cand_names)} 個）")
    if unmatched:
        print(f"  ※ 縣市未對應列 {len(unmatched)} 筆：{unmatched[:10]}")

    # ------------- 政黨 → 色階指派 -------------
    used_schemes = set()
    party_scheme = {}
    for p in LEGEND_ORDER:
        if p in cand_names:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
    for p in cand_names:
        if p not in party_scheme:
            idx = next((s for s in SCHEME_FALLBACK if s not in used_schemes), 5)
            party_scheme[p] = idx
            used_schemes.add(idx)

    # ------------- 建立對照表索引 -------------
    for t in towns:
        t["core"] = norm_town_core(t["name"])

    # ------------- 統計：領先政黨 -------------
    win_cnt = {n: 0 for n in cand_names}
    win_rates = []
    for t in towns:
        if (t["county"], t["core"]) not in data:
            continue
        rec = data[(t["county"], t["core"])]
        vals = {n: rec.get(n, float("nan")) for n in cand_names}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        win_cnt[win_name] += 1
        win_rates.append(vals[win_name])
    print("  各政黨領先鄉鎮數:")
    for n in cand_names:
        if win_cnt.get(n, 0):
            print(f"      {n}: {win_cnt[n]}")

    # 色階固定基準 35%（首檔 35、末檔 85%以上）
    stops = scale_fixed()
    if win_rates:
        print(f"  領先得票率範圍     : {min(win_rates):.1f}% ~ {max(win_rates):.1f}%"
              f"（<35% 共 {sum(1 for r in win_rates if r < 35)} 個，落入首格）")

    matched_data_keys = []
    no_data_names = []
    for t in towns:
        rec = data.get((t["county"], t["core"]))
        if not rec:
            t["fill_hex"] = CANVAS_COLOR   # 無資料區域填背景色（#323232）
            no_data_names.append(t["name"])
            continue
        key = (t["county"], t["core"])
        matched_data_keys.append(key)
        vals = {n: rec.get(n, float("nan")) for n in cand_names}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        scheme = stops[party_scheme[win_name]]
        t["fill_hex"] = get_color_by_value(vals[win_name], scheme)

    orphan_keys = set(data.keys()) - set(matched_data_keys)

    print(f"  有資料(填色)       : {len(matched_data_keys)}")
    print(f"  無資料(不著色)     : {len(no_data_names)}")
    if orphan_keys:
        print("  ※ 資料表有但未配對到對照表的 key（該區將不著色）：")
        for k in sorted(orphan_keys):
            print(f"      {k}")

    # ------------- 重著色底圖（2008 用 Colorful3，其餘用 Colorful2） -------------
    base_png = os.path.join(
        COUNTY_DIR, BASE_MAP_BY_YEAR.get(year, BASE_MAP_DEFAULT))
    print(f"  底圖               : {os.path.basename(base_png)}")
    img = Image.open(base_png).convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3]
    rgb_flat = rgb.reshape(-1, 3)
    uniq, inv = np.unique(rgb_flat, axis=0, return_inverse=True)

    color2fill = {}
    for t in towns:
        if t["fill_hex"]:
            color2fill[hex2rgb(t["color_hex"])] = hex2rgb(t["fill_hex"])

    new_uniq = uniq.copy()
    for i, u in enumerate(uniq):
        f = color2fill.get(tuple(int(x) for x in u))
        if f is not None:
            new_uniq[i] = f
    recolored_flat = new_uniq[inv].reshape(rgb.shape)

    out_arr = arr.copy()
    out_arr[..., :3] = recolored_flat

    base = Image.fromarray(out_arr).convert("RGB")

    # 資料健檢：至少要有一個鄉鎮市區有領先政黨，否則輸出會是整張底色
    if not any(win_cnt.values()):
        raise SystemExit(f"{year} 無任何領先政黨，請檢查資料。")

    # ------------- 左上角大陸地區留白 -------------
    # 把 BLANK_RECT 矩形區域（含端點）整片蓋成畫布背景色，
    # 使大陸陸塊（灰）與其藍色海岸線一併消失，海面保持連續。
    ImageDraw.Draw(base).rectangle(BLANK_RECT, fill=hex2rgb(CANVAS_COLOR))
    W, H = base.size

    # ------------- 輸出（無圖例版，英文檔名） -------------
    out_png = os.path.join(OUT_DIR, f"legislative_election_{year}_party_lead_map.png")
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp_png = os.path.join(OUT_DIR, f"_tmp_{year}.png")
    for attempt in range(5):
        try:
            base.save(tmp_png)
            os.replace(tmp_png, out_png)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.8)
    print(f"  輸出: {out_png}  ({W}×{H}px，無圖例)")
    print(f"     大陸留白矩形: {BLANK_RECT}（填 {CANVAS_COLOR}）\n")
    return True


def main():
    only = [int(a) for a in sys.argv[1:] if a.isdigit()] or \
           [y for y, _, _ in ELECTIONS]
    print("=" * 62)
    print("  2008-2024 五屆立法委員選舉 政黨得票率地圖 批次繪製（無圖例版）")
    print(f"  底圖：2008=Colorful3.png、2012+=Colorful2.png；"
          f"色階固定基準 35%，末檔 85%以上")
    print(f"  大陸留白矩形：{BLANK_RECT} → {CANVAS_COLOR}")
    print("=" * 62)

    towns, county_code2name = load_correspondence()
    print(f"  對照表鄉鎮市區    : {len(towns)} 個（全縣市 {len(county_code2name)} 個）\n")

    done = []
    for year, session_label, date_line in ELECTIONS:
        if year not in only:
            continue
        if draw_year(year, session_label, date_line, towns):
            done.append(year)

    print("#" * 62)
    print(f"完成 {len(done)}/{len(only)} 屆：{done}")


if __name__ == "__main__":
    main()
