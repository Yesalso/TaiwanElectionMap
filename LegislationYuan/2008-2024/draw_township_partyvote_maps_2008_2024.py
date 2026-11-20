#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2008-2024 五屆立法委員選舉（全國不分區）— 各鄉鎮市區政黨票領先政黨得票率地圖
================================================================
粒度＝鄉（鎮、市、區）：全臺 368 個鄉鎮市區，每塊一色，不畫村里界。
以 County/Colorful*.png（368 鄉鎮市區唯一色底圖）直接重著色，無需 SHP：
    2008        用 Colorful3.png（25 縣市時期畫法，臺中／臺南／高雄 市縣之間有縣市界）
    2012 起     用 Colorful2.png（五都改制後 22 縣市畫法）
（兩張底圖的 368 鄉鎮色完全相同，只差縣市界黑線；本腳本是這個目錄唯一的製圖腳本，
  73 選舉區版本已併入並移除，只輸出不分區政黨票的鄉鎮市區地圖。）

資料來源（皆為「政黨票／不分區」原始資料，非區域候選人票）：
    2008（第 7 屆）：
        LegislationYuan/2008Legislator-at-Large/Data/2008{縣市}_得票率.xlsx
        工作表「各鄉鎮(市、區)彙總」＝鄉鎮市區級政黨得票數／得票率
    2012（第 8 屆）：
        LegislationYuan/2012-2024/data/2012不分区/立委-A05-6-({縣市}).xls
        中選會原始投開票所表，本腳本自行把「鄉鎮市區彙總列」加總
    2016（第 9 屆）：LegislationYuan/2012-2024/data/不分区2016/{縣市}.xls
    2020（第 10 屆）：LegislationYuan/2012-2024/data/不分区2020/{縣市}.xls
    2024（第 11 屆）：
        LegislationYuan/2012-2024/data/2024/2024{縣市}_得票率.xlsx
        工作表「各鄉鎮(市、區)彙總」

指標：
    每鄉鎮市區取「得票率最高的政黨」為該區領先者，
    以其政黨色階＋該黨在該區的得票率上色。
    得票率＝該黨鄉鎮票數 ÷ 該鄉鎮有效票數（先加總再算率，不用各里比率平均）。

名稱比對：
    資料端 2008 為 25 縣市（臺北縣、桃園縣、臺中縣／臺中市、臺南縣／臺南市、
    高雄縣／高雄市），2012 起為 22 縣市；底圖為現行 22 縣市 368 鄉鎮市區。
    故縣市先套用 COUNTY_ALIAS 併入現行縣市，鄉鎮市區再去掉結尾 市／鎮／鄉／區
    取「地名本體」比對（板橋市＝板橋區、桃園市＝桃園區、後壁鄉＝後壁區…）；
    異體字臺→台、裡→里一併正規化（底圖表有「後裡區」「大裡區」「佳裡區」等轉檔錯字）。

色階：固定基準 35%，每 5 個百分點一檔（35/40/…/85），末檔「85%以上」；
      顏色沿用本專案 color.txt 體系；低於 35% 落入首格。
      未在色階表內的政黨依 SCHEME_FALLBACK 順序配一組備用色階。

無圖例：本版不畫圖例、不畫標題，輸出純地圖（年份見檔名）。
      若需要把標題燒進圖裡，把 DRAW_TITLE 改成 True。

輸出：map/legislative_township_{year}_party_lead_map.png（3203×4404px）

執行：
    python draw_township_partyvote_maps_2008_2024.py          # 全部五屆
    python draw_township_partyvote_maps_2008_2024.py 2020     # 只畫某屆
"""

import os
import re
import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
import xlrd
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUAN_DIR = os.path.dirname(BASE_DIR)                       # LegislationYuan/
ROOT_DIR = os.path.dirname(YUAN_DIR)                       # 專案根目錄

COUNTY_DIR = os.path.join(ROOT_DIR, "County")
# 368 鄉鎮市區唯一色底圖（兩張只差「縣市界黑線」，鄉鎮色完全相同）：
#   Colorful3.png = 25 縣市時期畫法（臺中市/縣、臺南市/縣、高雄市/縣 有縣市界）→ 2008 用
#   Colorful2.png = 22 縣市（五都改制後）畫法                              → 2012 起用
BASE_PNG_25 = os.path.join(COUNTY_DIR, "Colorful3.png")
BASE_PNG_22 = os.path.join(COUNTY_DIR, "Colorful2.png")
CORR_XLSX = os.path.join(COUNTY_DIR, "Name_Color_Correspondence.xlsx")

SRC_2008 = os.path.join(YUAN_DIR, "2008Legislator-at-Large", "Data")
SRC_2012_2024 = os.path.join(YUAN_DIR, "2012-2024", "data")
OUT_DIR = os.path.join(BASE_DIR, "map")

CANVAS_COLOR = "#323232"     # 底色（與底圖 #323232 一致），亦用於無資料鄉鎮

# 左上角留白框 (x0, y0, x1, y1)：框內只有大陸沿海（灰陸塊＋藍海岸線），
# 以底色整塊蓋掉，避免與台灣本島的政黨配色混淆；台灣本島與金馬附圖都不在框內。
# 設為 None 即保留原樣。
BLANK_RECT = (0, 0, 1065, 1065)

# ===================== 各屆資料來源 =====================
# (年份, 屆別, 選舉日期, 類型, 資料目錄, 檔名規則, 底圖)
#   類型 "rates"：鄉鎮市區級 xlsx（工作表「各鄉鎮(市、區)彙總」）
#   類型 "raw"  ：中選會原始投開票所 xls（自行彙總鄉鎮市區列）
ELECTIONS = [
    (2008, "第七屆", "2008年1月12日", "rates", SRC_2008,
     r"^2008.+_得票率\.xlsx$", BASE_PNG_25),
    (2012, "第八屆", "2012年1月14日", "raw",
     os.path.join(SRC_2012_2024, "2012不分区"), r"\.xls$", BASE_PNG_22),
    (2016, "第九屆", "2016年1月16日", "raw",
     os.path.join(SRC_2012_2024, "不分区2016"), r"\.xls$", BASE_PNG_22),
    (2020, "第十屆", "2020年1月11日", "raw",
     os.path.join(SRC_2012_2024, "不分区2020"), r"\.xls$", BASE_PNG_22),
    (2024, "第十一屆", "2024年1月13日", "rates",
     os.path.join(SRC_2012_2024, "2024"), r"^2024.+_得票率\.xlsx$", BASE_PNG_22),
]

DRAW_TITLE = False           # True = 在地圖左上角燒錄兩行標題（預設純地圖）

# ===================== 色階（固定基準 35%，5% 間距；末檔 100） =====================
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
    # 時代力量（芥黃色系）
    "時代力量": [
        (40, "#FFE300"), (45, "#E8B70D"), (50, "#CFA30C"), (55, "#997909"),
        (60, "#695207"), (85, "#403104"), (100, "#2A2003"),
    ],
    # 台灣民眾黨（青綠色系）
    "台灣民眾黨": [
        (35, "#00D9CA"), (40, "#00BFB2"), (45, "#00A89C"), (50, "#008080"),
        (55, "#006666"), (60, "#004C4C"), (65, "#003838"), (70, "#003030"),
        (75, "#002626"), (80, "#021F1F"), (85, "#001919"), (100, "#000808"),
    ],
    # 台灣基進（深紅色系）
    "台灣基進": [
        (35, "#FFB3B3"), (40, "#FF8A8A"), (45, "#FF5C5C"), (50, "#F03535"),
        (55, "#D42020"), (60, "#A81414"), (65, "#800D0D"), (70, "#5C0808"),
        (75, "#400505"), (80, "#2A0303"), (85, "#1A0202"), (100, "#0F0101"),
    ],
    # 台灣團結聯盟（咖啡色系）
    "台灣團結聯盟": [
        (35, "#E8CFAF"), (40, "#E0C199"), (45, "#D8AE7B"), (50, "#CB9450"),
        (55, "#A37135"), (85, "#59401E"), (100, "#59401E"),
    ],
    # 台灣綠黨（草綠色系）
    "綠黨": [
        (35, "#C9F5A8"), (40, "#AEEA85"), (45, "#93DC63"), (50, "#76C845"),
        (55, "#5BAC30"), (60, "#438B22"), (65, "#2F6B17"), (70, "#1F4C0F"),
        (75, "#143309"), (80, "#0E2406"), (85, "#091904"), (100, "#091904"),
    ],
    "台灣綠黨": [
        (35, "#C9F5A8"), (40, "#AEEA85"), (45, "#93DC63"), (50, "#76C845"),
        (55, "#5BAC30"), (60, "#438B22"), (65, "#2F6B17"), (70, "#1F4C0F"),
        (75, "#143309"), (80, "#0E2406"), (85, "#091904"), (100, "#091904"),
    ],
    # 以下為備用色階（未出現於領先者時僅作 fallback 配色）
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

_SCHEME_ORDER = ["中國國民黨", "親民黨", "民主進步黨", "台灣團結聯盟", "新黨",
                 "無黨籍及未經政黨推薦", "建國黨", "中華社會民主黨", "民主聯盟",
                 "工黨", "無黨團結聯盟", "其他政黨",
                 "時代力量", "台灣民眾黨", "台灣基進", "綠黨"]

LEGEND_GRID = list(range(35, 86, 5)) + [100]     # 35,40,…,85,100


def _expand_stops(raw, grid):
    """把色階展開到統一邊界 grid：各邊界取「第一個 ≥ 該邊界」的顏色。"""
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


def scale_fixed():
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
    "綠黨": 15,                   # 草綠
    "台灣綠黨": 15,               # 草綠
}
SCHEME_FALLBACK = [11, 6, 7, 8, 9, 10, 12, 13, 14, 15]

# 政黨票會出現、但屬小黨者 → 一律併入「其他政黨」色階（避免吃掉 fallback 的顏色）
SMALL_PARTIES = {
    "公民黨", "制憲聯盟", "第三社會黨", "台灣農民黨", "紅黨", "客家黨",
    "台灣國民會議", "人民最大黨", "健保免費連線", "中華民國台灣基本法連線",
    "台灣主義黨", "自由台灣黨", "和平鴿聯盟黨", "軍公教聯盟黨", "民國黨",
    "信心希望聯盟", "中華統一促進黨", "大愛憲改聯盟", "綠黨社會民主黨聯盟",
    "社會民主黨", "台灣獨立黨", "樹黨", "合一行動聯盟", "安定力量", "喜樂島聯盟",
    "一邊一國行動黨", "勞動黨", "宗教聯盟", "台灣維新", "台澎黨", "國會政黨聯盟",
    "小民參政歐巴桑聯盟", "台灣雙語無法黨", "制度救世島", "司法改革黨",
    "台灣麻將最大黨", "經濟黨", "台灣人民共產黨", "正神名黨", "公民組合",
    "歡樂無法黨", "中國民主進步黨", "圓桌",
}

# ===================== 縣市／鄉鎮市區名正規化 =====================
VARIANT_CHAR_MAP = str.maketrans({"臺": "台", "裡": "里", "衆": "眾"})
# 2008（25 縣市）→ 現行（22 縣市）：整併後同名，可直接併入
COUNTY_ALIAS = {
    "台北縣": "新北市",
    "桃園縣": "桃園市",
    "台中縣": "台中市",
    "台南縣": "台南市",
    "高雄縣": "高雄市",
}
# 鄉鎮市區名結尾（改制後 鄉／鎮／市 → 區，比對時一律去掉取地名本體）
_TOWN_SUFFIX = ("區", "市", "鎮", "鄉")

# 轉檔錯字修正（底圖表與部分年份的 xlsx 資料端皆有同批錯字，兩側一併套用）
TOWN_FIX = {
    "後里": "后里",     # 後裡區 → 后里區
    "南莊": "南庄",     # 南莊鄉 → 南庄鄉
    "褔興": "福興",     # 褔興鄉 → 福興鄉
    "鹿穀": "鹿谷",     # 鹿穀鄉 → 鹿谷鄉
    "二侖": "二崙",     # 二侖鄉 → 二崙鄉
    "鬥六": "斗六",     # 鬥六市 → 斗六市
    "鬥南": "斗南",     # 鬥南鎮 → 斗南鎮
    "樸子": "朴子",     # 樸子市 → 朴子市
    "滿洲": "滿州",     # 滿洲鄉 → 滿州鄉
    "恒春": "恆春",     # 恒春鎮 → 恆春鎮
}

# 舊鄉名 → 現行名（只影響該縣市；三民鄉 2008 年改名那瑪夏鄉，
# 不可直接對 三民 做全域對照，否則會撞 高雄市三民區）
DATA_TOWN_FIX = {
    ("高雄市", "三民", "鄉"): "那瑪夏",
}


def norm_county(name):
    s = re.sub(r"\s+", "", str(name)).translate(VARIANT_CHAR_MAP)
    return COUNTY_ALIAS.get(s, s)


def split_town(name):
    """鄉鎮市區名 → (地名本體, 結尾字)。"""
    s = re.sub(r"[\s\u3000]+", "", str(name)).translate(VARIANT_CHAR_MAP)
    if len(s) > 1 and s.endswith(_TOWN_SUFFIX):
        return s[:-1], s[-1]
    return s, ""


def norm_town(name):
    """鄉鎮市區名 → 地名本體（去掉結尾 區／市／鎮／鄉）。"""
    return split_town(name)[0]


def town_key(county, town, from_base=False):
    c = norm_county(county)
    base, suffix = split_town(town)
    base = TOWN_FIX.get(base, base)
    if not from_base:
        base = DATA_TOWN_FIX.get((c, base, suffix), base)
    return (c, base)


def norm_party(name):
    """政黨名正規化：去空白、統一 臺→台／衆→眾（2024 資料寫「台灣民衆黨」）。"""
    return re.sub(r"[\s\u3000]+", "", str(name)).translate(VARIANT_CHAR_MAP)


def to_int(v):
    """xls／xlsx 數值（float、字串、含千分位）→ int。"""
    if v is None or v == "":
        return 0
    try:
        return int(round(float(str(v).strip().replace(",", ""))))
    except (ValueError, TypeError):
        return 0


def blank(v):
    """空白判定：None、空字串、全空白（含全形空白 \u3000）。"""
    return v is None or (isinstance(v, str) and v.strip() == "")


def hex2rgb(hx):
    h = str(hx).strip().lstrip("#").upper()
    if len(h) < 6:
        return None
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and np.isnan(val)) or val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


# ===================== 底圖（368 鄉鎮市區唯一色） =====================
def load_township_base():
    """回傳 {(縣市, 地名本體): {"name", "county", "color_hex"}}。"""
    df = pd.read_excel(CORR_XLSX)
    recs = OrderedDict()
    for _, row in df.iterrows():
        county = str(row["縣市"]).strip()
        town = str(row["地名"]).strip()
        recs[town_key(county, town, from_base=True)] = {
            "name": town,
            "county": county,
            "color_hex": str(row["填充顏色 (HEX)"]).strip().upper(),
        }
    if len(recs) != len(df):
        print(f"  ※ 底圖對照表正規化後有重複，{len(df)} 列 → {len(recs)} 個 key")
    return recs


# ===================== 讀取得票資料 =====================
def _party_cols_xlsx(df):
    """xlsx：{政黨}得票數 欄位 → [(政黨, 票數欄, 得票率欄 or None)]。"""
    cols = [str(c) for c in df.columns]
    out = OrderedDict()
    for c in cols:
        if c.endswith("得票數"):
            party = norm_party(c[:-3])
            rate_col = f"{c[:-3]}得票率"
            out[party] = (c, rate_col if rate_col in cols else None)
    return out


def _valid_col_xlsx(df):
    cols = [str(c) for c in df.columns]
    for name in ("有效票數", "有效票數A", "總有效票數"):
        if name in cols:
            return name
    for c in cols:
        if "有效票數" in c:
            return c
    return None


def load_rates_xlsx(path):
    """鄉鎮市區級 xlsx（工作表「各鄉鎮(市、區)彙總」）→ [(county, town, {政黨: 票}, 有效票)]。"""
    xl = pd.ExcelFile(path)
    sheet = next((s for s in xl.sheet_names if "鄉鎮" in s), None)
    if sheet is None:
        raise ValueError(f"{path} 找不到「各鄉鎮(市、區)彙總」工作表：{xl.sheet_names}")
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c) for c in df.columns]

    town_col = next(c for c in df.columns if "鄉" in c and "別" in c)
    county_col = next((c for c in df.columns if "選舉區" in c), None)
    parties = _party_cols_xlsx(df)
    valid_col = _valid_col_xlsx(df)

    rows = []
    for _, row in df.iterrows():
        town = str(row[town_col]).strip()
        if blank(town) or "計" in town:
            continue
        county = str(row[county_col]).strip() if county_col else ""
        votes = {p: to_int(row[vc]) for p, (vc, _rc) in parties.items()}
        valid = to_int(row[valid_col]) if valid_col else 0
        if not valid:
            valid = sum(votes.values())
        rows.append((county, town, votes, valid))
    return rows, list(parties.keys())


def _party_name_from_cell(text):
    """中選會表頭（「1\\n \\n民主進步黨」「(1)\\n\\n合一行動聯盟」）→ 政黨名。"""
    parts = [p.strip() for p in str(text).split("\n")]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    name = parts[-1]
    name = re.sub(r"^[（(]?\d+[）)]?[.、]?\s*", "", name)
    return norm_party(name)


def load_raw_xls(path):
    """中選會原始投開票所 xls → [(county, town, {政黨: 票}, 有效票)]（只取鄉鎮市區彙總列）。"""
    wb = xlrd.open_workbook(path)
    rows = []
    parties_all = OrderedDict()

    for sh in wb.sheets():
        if sh.nrows < 6:
            continue
        # 縣市名：優先用工作表名（中選會一律以縣市為表名）
        county = norm_county(sh.name)
        if not county:
            continue

        # 有效票數欄（表頭第 2 列含「有效票數」）
        valid_c = None
        for c in range(3, sh.ncols):
            if "有效票數" in str(sh.cell_value(1, c)):
                valid_c = c
                break
        end_c = valid_c if valid_c is not None else sh.ncols

        # 政黨欄：第 3 列（索引 2）有值者
        party_cols = OrderedDict()
        for c in range(3, end_c):
            raw = sh.cell_value(2, c)
            if blank(raw):
                continue
            name = _party_name_from_cell(raw)
            if name:
                party_cols[c] = name
                parties_all.setdefault(name, None)
        if not party_cols:
            continue

        # 總計列之後：col0 有值、col1 空白 → 鄉鎮市區彙總列
        start = None
        for r in range(3, sh.nrows):
            v = sh.cell_value(r, 0)
            if not blank(v) and "總" in str(v):
                start = r + 1
                break
        if start is None:
            continue

        for r in range(start, sh.nrows):
            c0 = "" if blank(sh.cell_value(r, 0)) else str(sh.cell_value(r, 0)).strip()
            c1 = "" if blank(sh.cell_value(r, 1)) else str(sh.cell_value(r, 1)).strip()
            if not c0 or c1 or "計" in c0:
                continue
            votes = {p: to_int(sh.cell_value(r, c)) for c, p in party_cols.items()}
            valid = to_int(sh.cell_value(r, valid_c)) if valid_c is not None else 0
            if not valid:
                valid = sum(votes.values())
            rows.append((county, c0, votes, valid))

    return rows, list(parties_all.keys())


def load_year_files(kind, folder, pattern):
    """依年份資料類型掃描資料夾 → [(county, town, {政黨: 票}, 有效票)], 政黨清單。"""
    if not os.path.isdir(folder):
        print(f"  ※ 資料夾不存在：{folder}")
        return [], []
    rx = re.compile(pattern, re.I)
    files = sorted(f for f in os.listdir(folder)
                   if rx.search(f) and os.path.isfile(os.path.join(folder, f)))
    if not files:
        print(f"  ※ 資料夾內無符合檔案：{folder}  （{pattern}）")
        return [], []

    loader = load_rates_xlsx if kind == "rates" else load_raw_xls
    rows, parties = [], OrderedDict()
    seen_county = {}
    for fn in files:
        # xlsx 檔名「2024新北_得票率.xlsx」為重複檔（正式檔為「2024新北市_」），先濾掉
        stem = rx.sub("", fn)
        stem = re.sub(r"^20\d\d", "", stem).strip("_- ")
        if kind == "rates" and stem and not stem.endswith(("市", "縣")):
            continue
        try:
            frows, fparties = loader(os.path.join(folder, fn))
        except Exception as e:
            print(f"  ※ 讀取失敗，略過：{fn}（{e}）")
            continue
        if not frows:
            print(f"  ※ 無資料列，略過：{fn}")
            continue
        county = frows[0][0]
        if county in seen_county:      # 同一縣市重複檔（如 新北 vs 新北市）
            continue
        seen_county[county] = fn
        rows.extend(frows)
        for p in fparties:
            parties.setdefault(p, None)
    return rows, list(parties)


# ===================== 繪圖 =====================
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return None


def draw_title(img, lines):
    """把標題燒進左上角（DRAW_TITLE=True 時才呼叫）。"""
    f = _font(96)
    if f is None:
        return img
    d = ImageDraw.Draw(img)
    y = 70
    for t in lines:
        d.text((90, y), t, font=f, fill=(255, 255, 255))
        y += int(96 * 1.35)
    return img


def draw_year(year, session_label, date_line, kind, folder, pattern,
              base_png, base, stops):
    print("=" * 62)
    print(f"  {year} {session_label}立法委員選舉（不分區政黨票）— 各鄉鎮市區領先政黨")
    print("=" * 62)
    if not os.path.exists(base_png):
        print(f"  ※ 缺少底圖，略過本屆：{base_png}\n")
        return False

    rows, labels = load_year_files(kind, folder, pattern)
    if not rows:
        print("  ※ 無可用資料，略過本屆。\n")
        return False
    print(f"  資料來源           : {os.path.relpath(folder, ROOT_DIR)}"
          f"（{kind}，{len(rows)} 個鄉鎮市區列）")
    print(f"  政黨欄位           : {len(labels)} 個")

    # ------------- 政黨 → 色階指派 -------------
    used_schemes = set()
    party_scheme = {}
    ordered = ["民主進步黨", "中國國民黨", "親民黨", "新黨", "時代力量",
               "台灣民眾黨", "台灣基進", "無黨團結聯盟", "台灣團結聯盟"]
    for p in ordered:
        if p in labels and p in PARTY_SCHEME:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
    for p in labels:
        if p in party_scheme:
            continue
        if p in PARTY_SCHEME:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
        elif p in SMALL_PARTIES:              # 小黨 → 其他政黨色階
            party_scheme[p] = PARTY_SCHEME["其他政黨"] if "其他政黨" in PARTY_SCHEME else 11
        else:
            idx = next((s for s in SCHEME_FALLBACK if s not in used_schemes), 11)
            party_scheme[p] = idx
            used_schemes.add(idx)

    # ------------- 逐鄉鎮取領先者並上色 -------------
    data_map = {}
    dup = []
    for county, town, votes, valid in rows:
        k = town_key(county, town)
        if k in data_map:
            dup.append(f"{county}{town}")
        data_map[k] = {"votes": votes, "valid": valid, "name": f"{county}{town}"}
    if dup:
        print(f"  ※ 正規化後重複的鄉鎮市區（取後者）：{dup}")

    win_cnt = {}
    win_rates = []
    color2fill = {}
    no_data = []
    for key, rec in base.items():
        row = data_map.get(key)
        fill_hex = None
        if row is not None:
            votes, valid = row["votes"], row["valid"]
            total = valid or sum(votes.values())
            if total > 0:
                win = max(votes, key=lambda n: votes[n])
                val = votes[win] / total * 100.0
                if votes[win] > 0:
                    win_cnt[win] = win_cnt.get(win, 0) + 1
                    win_rates.append(val)
                    fill_hex = get_color_by_value(val, stops[party_scheme[win]])
        if fill_hex is None:
            no_data.append(rec["name"])
            fill_hex = CANVAS_COLOR
        color2fill[hex2rgb(rec["color_hex"])] = hex2rgb(fill_hex)

    miss_in_data = [base[k]["county"] + base[k]["name"] for k in base if k not in data_map]
    miss_in_base = [data_map[k]["name"] for k in data_map if k not in base]

    print("  各政黨領先鄉鎮市區數：")
    for n, c in sorted(win_cnt.items(), key=lambda kv: -kv[1]):
        print(f"      {n}: {c} 個")
    if win_rates:
        print(f"  領先得票率範圍     : {min(win_rates):.2f}% ~ {max(win_rates):.2f}%"
              f"（<35% 共 {sum(1 for r in win_rates if r < 35)} 個，落入首格）")
    print(f"  無資料(填底色)     : {len(no_data)}" + (f" {no_data}" if no_data else ""))
    if miss_in_base:
        print(f"  ※ 資料有、底圖無（未畫入）：{miss_in_base}")

    # ------------- 以唯一色重著色底圖 -------------
    img = Image.open(base_png).convert("RGB")
    arr = np.array(img)
    uniq, inv = np.unique(arr.reshape(-1, 3), axis=0, return_inverse=True)
    new_uniq = uniq.copy()
    hit = 0
    for i, u in enumerate(uniq):
        f = color2fill.get(tuple(int(x) for x in u))
        if f is not None:
            new_uniq[i] = f
            hit += 1
    out_arr = new_uniq[inv].reshape(arr.shape)
    out_img = Image.fromarray(out_arr.astype(np.uint8)).convert("RGB")

    if BLANK_RECT:                        # 蓋掉左上角的大陸沿海
        ImageDraw.Draw(out_img).rectangle(BLANK_RECT, fill=hex2rgb(CANVAS_COLOR))

    print(f"  底圖               : {os.path.basename(base_png)} {img.width}×{img.height}px"
          f"（命中 {hit} / {len(color2fill)} 色）")

    if DRAW_TITLE:
        out_img = draw_title(out_img, [f"{session_label}立法委員選舉（{date_line}）",
                                       "各鄉鎮市區政黨票領先政黨得票率"])

    os.makedirs(OUT_DIR, exist_ok=True)
    out_png = os.path.join(OUT_DIR, f"legislative_township_{year}_party_lead_map.png")
    tmp_png = os.path.join(OUT_DIR, f"_tmp_township_{year}.png")
    for attempt in range(5):
        try:
            out_img.save(tmp_png)
            os.replace(tmp_png, out_png)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.8)
    print(f"  輸出               : {os.path.relpath(out_png, ROOT_DIR)}"
          f"  ({out_img.width}×{out_img.height}px)\n")
    return True


def main():
    only = [int(a) for a in sys.argv[1:] if a.isdigit()] or [e[0] for e in ELECTIONS]
    print("=" * 62)
    print("  2008-2024 五屆立法委員不分區選舉 — 各鄉鎮市區政黨票領先政黨地圖")
    print("  底圖：2008 = Colorful3.png（25 縣市界）；2012+ = Colorful2.png（22 縣市界）")
    print("=" * 62)

    base = load_township_base()
    stops = scale_fixed()
    print(f"  底圖鄉鎮市區       : {len(base)} 個\n")

    done = []
    for year, session_label, date_line, kind, folder, pattern, base_png in ELECTIONS:
        if year not in only:
            continue
        if draw_year(year, session_label, date_line, kind, folder, pattern,
                     base_png, base, stops):
            done.append(year)

    print("#" * 62)
    print(f"完成 {len(done)}/{len(only)} 屆：{done}")


if __name__ == "__main__":
    main()
