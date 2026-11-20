#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1992-2004 五屆立法委員選舉 — 各鄉鎮市區得票領先政黨得票率地圖
================================================================
以全台「唯一色」底圖（County/Colorful2.png）直接重著色，無需 SHP：
    - Colorful2.png 中每個鄉鎮市區填以單一辨識色，另有 #7F7F7F 淺灰鄉鎮界線
    - Name_Color_Correspondence.xlsx：顏色(HEX) ↔ 鄉鎮市區 對照表（County/ 目錄）
    - 得票資料：本目錄 data/{year}立法委員_政黨鄉鎮得票.xlsx（鄉鎮市區級別）
      欄位：縣市、鄉鎮市區（當時名稱）＋ 各政黨得票數／得票率（同政黨候選人得票加總）
    - 政黨欄位從表頭動態偵測（欄名以「得票率」結尾），不同屆政黨組成不同也能處理

版面：
    - 圖例：**橫式**，固定置於左上角方框 LEG_BOX（最終圖片像素座標 151,825～1220,1970）。
      方框僅界定上下限，內部版面依政黨數動態調整：內容與邊界線留 10px、
      標題字號依寬度自動收縮、政黨欄寬填滿可用寬度（政黨少時自動加寬貼近方框）、
      刻度數字只標到 80%。
      每政黨一行：左側政黨名（單行、黨色）＋ 右側色階色塊由左（低）到右（高）加深；
      下方刻度尺每 2 階標一次文字（如「35%以上」），文字與刻度線**水平居中對齊**；
      色塊描邊 #FCFCFC、底色＝畫布同色 #323232（融入背景）
    - 標題兩行，位於圖例方框正上方，兩行文字左右兩端與圖例方框左右兩端對齊（分散對齊）：
      第一行「第X屆立法院立法委員選舉」、第二行「在各鄉鎮市區得票領先之政黨得票比例圖」
      （字號由 TITLE_FONT_SIZE 基準按方框高度／寬度自動收縮，可調）
    - 無選舉地區（如 1992 年金門縣＋連江縣）：視為無選舉，填 #323232 並清除周邊
      描邊／界線／抗鋸齒光暈，完全融入背景

繪圖規則（同 2001Legislator.py）：
    - 每個鄉鎮市區取「領先政黨」，以其政黨色階按得票率深淺填色
    - 縣市名為當時名稱（臺北縣／臺中縣…），由 OLD_COUNTY_MAP 對應至現行縣市
    - 臺中市＋臺中縣、臺南市＋臺南縣、高雄市＋高雄縣 對應至現行台中市、台南市、高雄市
    - 臺南市 2003 年以前分「中區」「西區」，對照表為「中西區」→ 兩區得票率平均
    - 高雄縣三民鄉（現那瑪夏區）以來源縣市區分，與高雄市三民區不衝突

每屆輸出一張 PNG 至 map/ 子目錄。

執行：
    python draw_legislator_maps_1992_2004.py
"""
import os
import re
import time
import warnings
from collections import OrderedDict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTY_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "County")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "map")

COLORFUL_PNG = os.path.join(COUNTY_DIR, "Colorful3.png")
CORR_XLSX = os.path.join(COUNTY_DIR, "Name_Color_Correspondence.xlsx")

# ===================== 五屆選舉定義 =====================
ELECTIONS = [
    # (年份, 屆別, 選舉日期)
    ("1992", "第二屆", "1992年12月19日"),
    ("1995", "第三屆", "1995年12月2日"),
    ("1998", "第四屆", "1998年12月5日"),
    ("2001", "第五屆", "2001年12月1日"),
    ("2004", "第六屆", "2004年12月11日"),
]

CANVAS_COLOR = "#323232"   # 畫布背景；同時作為無資料區域的填色（與 Colorful2 底色一致）

# ===================== 色階（檔位 35 起，5% 間距；末檔 100） =====================
# 顏色取自 LegislationYuan/color.txt（此處直接寫死、不讀檔）。
# 檔位基準為 35；每年依「領先得票率分布」自適應位移（見 pick_shift / scale_for_shift）：
#   領先率 <35% 的鄉鎮數 <15 → 不位移（如 1992）
#   否則 <30% 的鄉鎮數 <15 → 位移 -5
#   否則（<25% 一帶也足夠多）→ 位移 -10
# 檔末 100 的顏色固定保留、獨立成格，圖例末端標註「XX%以上」。

def _expand_stops(raw, grid):
    """把（位移後的）色階展開到統一邊界 grid：各邊界取「第一個 ≥ 該邊界」
    的顏色（與 get_color_by_value 的取色規則一致，取色結果不變），
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

# 檔內原始色階（記錄值＝檔內值 -10：檔標 35 → 記 25；執行時再加回 (10 - 位移)）
_RAW_STOPS = {
    # 無黨籍（灰色系）
    "無黨籍及未經政黨推薦": [
        (25, "#D9D9D9"), (30, "#C9C9C9"), (35, "#B6B6B6"), (40, "#A0A0A0"),
        (45, "#898989"), (50, "#727272"), (55, "#5B5B5B"), (60, "#464646"),
        (65, "#333333"), (70, "#232323"), (75, "#151515"), (100, "#151515"),
    ],
    # 中國國民黨（藍色系）
    "中國國民黨": [
        (25, "#A6E9FF"), (30, "#73D9FF"), (35, "#40C8FF"), (40, "#00C0F4"),
        (45, "#00A2E8"), (50, "#0080B8"), (55, "#006591"), (60, "#004B6B"),
        (65, "#003247"), (70, "#00283A"), (75, "#001F2E"), (100, "#010D29"),
    ],
    # 民主進步黨（綠色系）
    "民主進步黨": [
        (25, "#E8FFE0"), (30, "#CEFFC2"), (35, "#C0FFB1"), (40, "#A4FF90"),
        (45, "#78FF4F"), (50, "#68DE45"), (55, "#54B337"), (60, "#3C8027"),
        (65, "#2B5C1C"), (70, "#1D3D13"), (75, "#0F210A"), (100, "#071A09"),
    ],
    # 新黨（金黃色系）
    "新黨": [
        (0, "#FFF3C4"), (25, "#FFE89A"), (30, "#FFDD66"), (35, "#FFD133"),
        (40, "#FFC700"), (45, "#F2B800"), (50, "#E0A800"), (55, "#C79200"),
        (60, "#AD7A00"), (65, "#946400"), (70, "#4D4900"), (75, "#2E2A00"),
        (100, "#161400"),
    ],
    # 親民黨（橘色系，檔內「宋楚瑜（無黨籍）」組）
    "親民黨": [
        (25, "#FFC2AA"), (30, "#FFA380"), (35, "#FF8456"), (40, "#FF662B"),
        (45, "#FF4701"), (50, "#D93A00"), (55, "#B33000"), (60, "#8D2500"),
        (65, "#6B1D00"), (70, "#4D1400"), (75, "#3A1000"), (100, "#170500"),
    ],
    # 無黨團結聯盟（粉色系）
    "無黨團結聯盟": [
        (25, "#FAC6D8"), (30, "#F8A8C5"), (35, "#F68AB2"), (40, "#F46C9F"),
        (45, "#F24E8C"), (50, "#F03772"), (55, "#D01058"), (60, "#B30D4B"),
        (65, "#950B3F"), (70, "#770932"), (75, "#590726"), (100, "#590726"),
    ],
    # 台灣團結聯盟（咖啡色系，檔內已為 25% 基準，不位移）
    "台灣團結聯盟": [
        (25, "#F5E9DB"), (30, "#EDDAC0"), (35, "#E8CFAF"), (40, "#E0C199"),
        (45, "#D8AE7B"), (50, "#CB9450"), (55, "#A37135"), (100, "#59401E"),
    ],
    # 以下政黨未見於 color.txt，沿用原色階並同樣 -10 對齊 25% 基準
    "建國黨": [
        (25, "#D9FFF6"), (30, "#A6FFEF"), (35, "#73F9E2"), (40, "#40E8D2"),
        (45, "#00D4C0"), (50, "#00B8A6"), (55, "#009385"), (60, "#007468"),
        (65, "#00564E"), (70, "#003832"), (75, "#002420"), (100, "#011511"),
    ],
    "中華社會民主黨": [
        (25, "#F0D9FF"), (30, "#DFBFFF"), (35, "#CFA0FF"), (40, "#BE80FF"),
        (45, "#AB5FF9"), (50, "#9A43E8"), (55, "#7C34B8"), (60, "#612A91"),
        (65, "#481F6B"), (70, "#301547"), (75, "#1E0D2E"), (100, "#100729"),
    ],
    "民主聯盟": [
        (25, "#FFE0EC"), (30, "#FFBDD2"), (35, "#FF98B8"), (40, "#FF6E9B"),
        (45, "#FF4079"), (50, "#F41E5E"), (55, "#C8164C"), (60, "#9E113C"),
        (65, "#750C2D"), (70, "#520720"), (75, "#380517"), (100, "#20030B"),
    ],
    "工黨": [
        (25, "#F5E8D9"), (30, "#E8D2B4"), (35, "#D9B98D"), (40, "#C99F66"),
        (45, "#B98545"), (50, "#A66F2B"), (55, "#87571F"), (60, "#6B4418"),
        (65, "#513411"), (70, "#38230B"), (75, "#261707"), (100, "#170E04"),
    ],
    "其他政黨": [
        (25, "#EFFFD9"), (30, "#DDF5B4"), (35, "#C8E88D"), (40, "#B0D966"),
        (45, "#96C845"), (50, "#7BB22E"), (55, "#628F22"), (60, "#4C6E19"),
        (65, "#395112"), (70, "#28380C"), (75, "#1B2508"), (100, "#111805"),
    ],
}

# 依 PARTY_SCHEME 對應的組別順序，展開成統一邊界的色階表
_SCHEME_ORDER = ["中國國民黨", "親民黨", "民主進步黨", "台灣團結聯盟", "新黨",
                 "無黨籍及未經政黨推薦", "建國黨", "中華社會民主黨", "民主聯盟",
                 "工黨", "無黨團結聯盟", "其他政黨"]
def scale_for_shift(shift):
    """依位移量（0/5/10）產生當年色階表（list，索引同 PARTY_SCHEME）。
    _RAW_STOPS 記錄的是「檔內值 -10」，實際檔位＝記錄值 +（10 - shift）；
    末檔 100 固定不位移。"""
    delta = 10 - shift
    grid = list(range(35 - shift, 86 - shift, 5)) + [100]
    table = []
    for p in _SCHEME_ORDER:
        raw = [(u if u in (0, 100) else u + delta, c)
               for u, c in _RAW_STOPS[p]]
        table.append(_expand_stops(raw, grid))
    return table


def pick_shift(win_rates):
    """自適應位移：依領先得票率分布選擇色階基準。
    領先率 <35% 的鄉鎮 <15 → 位移 0；否則 <30% <15 → 5；否則 → 10。"""
    def cnt_below(t):
        return sum(1 for r in win_rates if r < t)
    if cnt_below(35) < 15:
        return 0
    if cnt_below(30) < 15:
        return 5
    return 10

# ===================== 政黨 → 色階組別 =====================
PARTY_SCHEME = {
    "中國國民黨": 0,              # 藍
    "親民黨": 1,                  # 橘
    "民主進步黨": 2,              # 綠
    "台灣團結聯盟": 3,            # 紅
    "新黨": 4,                    # 黃
    "無黨籍及未經政黨推薦": 5,    # 灰
    "無黨籍": 5,                  # 灰
    "建國黨": 6,                  # 青
    "中華社會民主黨": 7,          # 紫
    "民主聯盟": 8,                # 粉
    "工黨": 9,                    # 棕
    "無黨團結聯盟": 10,           # 鋼藍
}
SCHEME_FALLBACK = [11, 6, 7, 8, 9, 10, 0, 1, 2, 3, 4, 5]   # 未知名政黨依序取用

# 圖例欄位排列順序（有領先鄉鎮的政黨才會畫出，其餘依 xlsx 出現順序接在後面）
LEGEND_ORDER = [
    "親民黨", "新黨", "民主進步黨", "中國國民黨",
    "無黨籍及未經政黨推薦", "無黨籍", "台灣團結聯盟",
    "建國黨", "中華社會民主黨", "民主聯盟", "工黨", "無黨團結聯盟",
]

# ===================== 縣市名映射（當時縣市 → 對照表現行縣市） =====================
OLD_COUNTY_MAP = {
    "臺北縣": "新北市", "桃園縣": "桃園市", "臺東縣": "台東縣",
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
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中縣后里鄉 ↔ 對照表後裡區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}

# 跨縣市同名、需按來源縣市區分的特殊對應（來源 → 對照表）
TOWN_MERGE = {   # 2003 年以前 臺南市 中區＋西區 → 對照表中西區
    ("臺南市", "中"): "中西",
    ("臺南市", "西"): "中西",
}
SPECIAL_TOWN = {   # 高雄縣三民鄉 → 現那瑪夏區（與高雄市三民區區別）
    ("高雄縣", "三民"): "那瑪夏",
}

# ===================== 手動指定填色（特例／無選舉資料區） =====================
# 整縣覆蓋：{年份: {縣市: (政黨, 得票率)}}
COUNTY_OVERRIDES = {
    "1992": {
        "金門縣": ("無黨籍及未經政黨推薦", 53.0),   # 金門全縣按無黨籍 53%
        "連江縣": ("中國國民黨", 58.0),             # 連江全縣按國民黨 58%
    },
}
# 指定鄉鎮市區：{年份: {(縣市, 鄉鎮核心名): (政黨, 得票率)}}
TOWN_OVERRIDES = {
    "1992": {
        ("屏東縣", "恆春"): ("中國國民黨", 78.0),   # 恆春鎮按國民黨 78%
        ("台東縣", "蘭嶼"): ("中國國民黨", 78.0),   # 蘭嶼鄉按國民黨 78%
    },
}

# ===================== 繪圖參數 =====================
# ---- 版面：地圖滿幅輸出；標題＋圖例外框錨定於左上角 LEG_BOX[0:2]，
#      外框大小由內容動態決定（僅以 LEG_BOX 右下角作為不可超出的上限） ----
LEG_BOX = (151, 825, 1220, 1950)   # 圖例外框錨點(左上 x,y)與大小上限(右下 x,y)
LEG_PAD = 10                       # 圖例內容與外框左／右／上邊界線的留白（px）
LEG_BOTTOM_PAD = 70                # 色塊底部與外框下邊界線的留白（px）

# ---- 標題（兩行，位於外框內上部，正常居中、不拉伸；字號可調） ----
#   第一行：第X屆立法院立法委員選舉
#   第二行：在各鄉鎮市區得票領先之政黨得票比例圖
TITLE_FONT_SIZE = 50         # 標題基準字號（實際字號受上限寬度限制自動收縮）
TITLE_FONT_MIN = 18          # 字號下限
TITLE_FONT_MAX = 60          # 字號上限
TEXT_COLOR = (255, 255, 255)   # 標題白字

# ===================== 直式圖例參數 =====================
#   每政黨一欄：欄頂政黨名（分行分散對齊、黨色）＋ 色階由上往下加深，
#   同一政黨的色階色塊上下相連**無間隙**；欄左側刻度尺每 TICK_LABEL_STEP 個百分點標一次
#   百分比文字（如「35%」，不加「以上」），文字與刻度線**垂直居中對齊**。
#   色塊長寬比固定 CELL_RATIO（110:88），只整體等比縮放、不改變形狀；
#   政黨名與色塊之間僅保留窄間隔（NAME_BLOCK_GAP）。
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]
LEG_BORDER = (252, 252, 252, 255)          # 色階欄外框描邊 #FCFCFC
LEG_BG = (50, 50, 50, 255)                 # 圖例底色＝畫布背景 #323232（融入背景）
LEG_EDGE = (252, 252, 252, 255)            # 外框 #FCFCFC
LEG_INK = (252, 252, 252)                  # 圖例文字／刻度（淺色，深底可讀）
TICK_LABEL_STEP = 10                       # 中間刻度每 10 個百分點標一次
CELL_RATIO = 110 / 88                      # 色塊長寬比（寬:高，固定不變）
CELL_H_MAX = 60                            # 色塊高度上限（px；整體等比縮放用）
NAME_BLOCK_GAP = 12                        # 政黨名末行與色塊方框的間隔（px）
NAME_FONT_MAX = 40                         # 政黨名字號上限
TITLE_GRID_GAP = 10                        # 標題區與政黨名區的間隔（px）
COL_GAP_FRAC = 0.30                        # 欄與欄間距 ＝ 色塊寬 × 0.30
# 政黨名換行（欄寬內分行分散對齊；未列出的政黨自動按 ≤3 字/行折行）
LEG_NAME_LINES = {
    "中國國民黨": ("中國", "國民黨"),
    "民主進步黨": ("民主", "進步黨"),
    "台灣團結聯盟": ("台灣", "團結", "聯盟"),
    "無黨籍及未經政黨推薦": ("無黨籍", "及未經", "政黨推薦"),
    "無黨團結聯盟": ("無黨", "團結", "聯盟"),
    "民主聯盟": ("民主", "聯盟"),
}
# 圖例顯示名（不改資料欄位名，僅影響圖例文字）
LEG_DISPLAY_NAME = {
    "無黨籍及未經政黨推薦": "無黨籍",
}

_FONT_PATH = None


def _font(size):
    global _FONT_PATH
    if _FONT_PATH is None:
        for p in FONT_CANDIDATES:
            if os.path.isfile(p):
                _FONT_PATH = p
                break
        else:
            raise RuntimeError("找不到可用的中文字型：%s" % FONT_CANDIDATES)
    return ImageFont.truetype(_FONT_PATH, size)


def _rgb255(hx):
    return tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))


def _party_name_color(party, scheme_map, col_stops):
    """政黨名顏色：取該黨色階 55% 亮階（#323232 深底上清晰）；未知則用淺灰。"""
    for upper, hx in col_stops[scheme_map.get(party, 5)]:
        if upper == 55:
            return hx
    return "#CCCCCC"


def _split_party_name(nm):
    """政黨名 → 換行方案：優先用 LEG_NAME_LINES，否則按 ≤3 字/行均勻折行。"""
    if nm in LEG_NAME_LINES:
        return LEG_NAME_LINES[nm]
    n = len(nm)
    if n <= 3:
        return (nm,)
    k = -(-n // 3)                            # ceil(n/3) 行
    base, extra = divmod(n, k)
    lines, i = [], 0
    for j in range(k):
        ln_len = base + (1 if j < extra else 0)
        lines.append(nm[i:i + ln_len])
        i += ln_len
    return tuple(lines)


def _draw_name_justified(d, cx, y_top, lines, font, fill, lh):
    """政黨名多行分散對齊（兩端對齊）：各行拉伸到同一寬度後水平置中。
    y_top 為行框頂部，每行以行框中心定位（anchor="mm"），
    避免基線定位造成行框視覺底部偏下。"""
    widths = [d.textlength(ln, font=font) for ln in lines]
    target = max(widths)
    for k, ln in enumerate(lines):
        y = y_top + k * lh + lh / 2
        w = widths[k]
        if len(ln) > 1 and w < target:
            extra = (target - w) / (len(ln) - 1)
            x = cx - target / 2 + d.textlength(ln[0], font=font) / 2
            for ch in ln:
                d.text((x, y), ch, font=font, fill=fill, anchor="mm")
                x += d.textlength(ch, font=font) + extra
        else:
            d.text((cx, y), ln, font=font, fill=fill, anchor="mm")


def build_legend_img(legend_parties, scheme_map, start_tier, title_lines, stops):
    """繪製標題＋圖例外框（回傳動態大小的 RGBA Image，由呼叫端貼於
    LEG_BOX 左上角錨點）。stops 為本屆色階表（scale_for_shift 產生）。

    LEG_BOX 僅界定不可超出的上下限（右下角），外框大小由內容動態決定：
      - 色塊長寬比固定 CELL_RATIO（110:88），只整體等比縮放、不改變形狀；
      - 政黨名末行對齊：各黨名最後一行與色塊的間隔統一為 NAME_BLOCK_GAP，
        且名字行以行框中心定位（不會視覺偏下），與標題之間保有間隔；
      - 內容與外框邊界線一律保留 LEG_PAD（10px）留白；
      - 標題字號超過上限寬度時動態收縮（最小 TITLE_FONT_MIN）；
      - 刻度：每格色塊＝區間 (上一檔, 本檔]；首格標「XX%以下」、末格（100
        顏色）標「XX%以上」，中間每隔 10 個百分點在該格上限邊界標數字。"""
    bx0, by0, bx1, by1 = LEG_BOX
    max_w, max_h = bx1 - bx0, by1 - by0    # 外框大小的上限
    n = len(legend_parties)
    pad = LEG_PAD
    avail_w = max_w - 2 * pad

    grid0 = [(u, c) for u, c in stops[scheme_map[legend_parties[0]]]
             if u > start_tier]
    n_lv = len(grid0)

    # 圖例顯示名（如「無黨籍及未經政黨推薦」→「無黨籍」）
    disp_names = {p: LEG_DISPLAY_NAME.get(p, p) for p in legend_parties}
    name_lines = {p: _split_party_name(disp_names[p]) for p in legend_parties}
    max_lines = max(len(v) for v in name_lines.values())

    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)

    # ---- 標題字號：超過上限寬度時動態收縮 ----
    fs = min(TITLE_FONT_MAX, TITLE_FONT_SIZE)
    while fs > TITLE_FONT_MIN:
        f = _font(fs)
        if max(d.textlength(t, font=f) for t in title_lines) <= avail_w:
            break
        fs -= 1
    fs = max(TITLE_FONT_MIN, fs)
    f_title = _font(fs)
    title_w = max(d.textlength(t, font=f_title) for t in title_lines)
    lh_t = int(fs * 1.4)
    title_h = 2 * lh_t + 6

    # ---- 色塊尺寸：比例固定 CELL_RATIO，只整體等比縮放 ----
    # 迭代求「上限內最大」的色塊：高度受色階階數與政黨名高度約束
    v_pad = pad + LEG_BOTTOM_PAD        # 上留白＋下留白
    cell_h = min(CELL_H_MAX,
                 max(8.0, (max_h - v_pad - title_h - TITLE_GRID_GAP - 4)
                     / max(1, n_lv) / max(1, max_lines)))
    max_chars = max(len(ln) for lns in name_lines.values() for ln in lns)
    for _ in range(3):
        cell_w = cell_h * CELL_RATIO
        col_gap0 = cell_w * COL_GAP_FRAC
        # 政黨名字級：3 字行可拉伸到「欄寬＋欄距」，最長行不得與相鄰欄重疊
        f_name_size = int(min(NAME_FONT_MAX,
                              (cell_w + col_gap0) / 3 * 0.92,
                              (cell_w + 2 * col_gap0) / max(3, max_chars)))
        lh_name = int(f_name_size * 1.35)
        name_h = max_lines * lh_name + 4
        cell_h_hi = (max_h - v_pad - title_h - TITLE_GRID_GAP
                     - name_h - NAME_BLOCK_GAP) / n_lv
        cell_h = min(CELL_H_MAX, max(8.0, cell_h_hi))
    cell_w = cell_h * CELL_RATIO

    # ---- 刻度尺尺寸；寬度若超上限則整體等比縮小色塊 ----
    def _axis_w(ch):
        f_t = _font(max(14, int(ch * 0.42)))
        tw = d.textlength("100%以上", font=f_t)     # 預留最長標籤寬度
        return f_t, tw, max(10, int(ch * 0.22)), int(tw) + max(10, int(ch * 0.22)) + 20

    f_tick, tick_text_w, tick_len, axis_w = _axis_w(cell_h)
    col_gap = cell_w * COL_GAP_FRAC
    content_w = axis_w + n * cell_w + (n - 1) * col_gap
    if content_w > avail_w:                # 政黨多時以寬度為約束等比縮小
        cell_w = (avail_w - axis_w) / (n + COL_GAP_FRAC * (n - 1))
        cell_h = cell_w / CELL_RATIO
        f_tick, tick_text_w, tick_len, axis_w = _axis_w(cell_h)
        col_gap = cell_w * COL_GAP_FRAC
        content_w = axis_w + n * cell_w + (n - 1) * col_gap

    # ---- 政黨名字級定稿（與迭代公式一致） ----
    f_name_size = int(min(NAME_FONT_MAX,
                          (cell_w + col_gap) / 3 * 0.92,
                          (cell_w + 2 * col_gap) / max(3, max_chars)))
    f_name = _font(max(12, f_name_size))
    lh_name = int(f_name_size * 1.35)
    name_h = max_lines * lh_name + 4

    # ---- 外框大小：由內容動態決定（不超過 LEG_BOX 上限） ----
    box_w = int(min(max_w, max(title_w, content_w))) + 2 * pad
    box_h = int(min(max_h, title_h + TITLE_GRID_GAP + name_h
                    + NAME_BLOCK_GAP + n_lv * cell_h
                    + pad + LEG_BOTTOM_PAD))

    img = Image.new("RGBA", (box_w, box_h), LEG_BG)
    d = ImageDraw.Draw(img)

    # ---- 版面位置：內容距外框邊界線一律 LEG_PAD 留白 ----
    x0 = (box_w - content_w) / 2                       # 刻度尺＋色階整體水平置中
    x_tick_r = x0 + int(tick_text_w) + 6               # 刻度文字右緣
    grid_x0 = x0 + axis_w                              # 色階欄左緣
    cols_top = pad + title_h + TITLE_GRID_GAP          # 政黨名頂部
    blocks_top = cols_top + name_h + NAME_BLOCK_GAP    # 色階頂部（緊貼政黨名）

    # ---- 刻度尺：每格色塊代表一個區間 (上一檔, 本檔]。
    #      第一格＝XX%以下（XX＝本屆圖例起始檔）、最後一格（100 顏色）＝XX%以上；
    #      中間自起始檔起每增加 10 個百分點標一次數字
    #      （如起始 30 → 40%、50%、60%…；起始 35 → 45%、55%…） ----
    first_v = grid0[0][0]                 # 首檔上限（＝位移後基準 35/30/25 或更高）
    prev_v = grid0[-2][0] if n_lv > 1 else first_v   # 末格下限（以上）
    for k in range(1, n_lv + 1):
        v = grid0[k - 1][0]               # 本格上限
        is_first, is_last = (k == 1), (k == n_lv)
        if is_first:
            y = blocks_top + k * cell_h        # 首格：標在起始檔邊界（該段結束處）
            txt = "%d%%以下" % first_v
        elif is_last:
            y = blocks_top + (n_lv - 1) * cell_h   # 末格：標在 85 邊界（該段開始處）
            txt = "%d%%以上" % prev_v
        elif (v - first_v) % TICK_LABEL_STEP == 0 and v < prev_v:
            y = blocks_top + k * cell_h
            txt = "%d%%" % v
        else:
            continue
        d.line([x_tick_r + 4, y, x_tick_r + 4 + tick_len, y],
               fill=LEG_INK + (170,), width=2)
        d.text((x_tick_r, y), txt, font=f_tick,
               fill=LEG_INK + (230,), anchor="rm")

    # ---- 各政黨欄：欄頂政黨名（黨色、末行對齊）＋ 連續無間隙色階 ----
    for i, p in enumerate(legend_parties):
        x = grid_x0 + i * (cell_w + col_gap)
        cx = x + cell_w / 2
        fill = _rgb255(_party_name_color(p, scheme_map, stops)) + (255,)
        # 多行名末行對齊：最後一行統一貼在色塊上方 NAME_BLOCK_GAP 處；
        # 單行名上移半行，落在兩行位置的中間（垂直居中）
        y_name_top = blocks_top - NAME_BLOCK_GAP \
            - len(name_lines[p]) * lh_name \
            - (lh_name / 2 if len(name_lines[p]) == 1 else 0)
        _draw_name_justified(d, cx, y_name_top, name_lines[p],
                             f_name, fill, lh_name)
        stops_p = [(u, c) for u, c in stops[scheme_map[p]]
                   if u > start_tier]                     # 該黨自己的色階
        y_top = blocks_top
        for k, (pct, hx) in enumerate(stops_p):
            col = _rgb255(hx) + (255,)
            # 上下相連、無間隙：直接相鄰鋪滿
            d.rectangle([x, y_top + k * cell_h,
                         x + cell_w, y_top + (k + 1) * cell_h],
                        fill=col)
        # 欄外框（整欄一個框，內部無分隔線）
        d.rectangle([x, y_top, x + cell_w, y_top + n_lv * cell_h],
                    outline=LEG_BORDER, width=2)

    # ---- 外框與標題 ----
    d.rectangle([0, 0, box_w - 1, box_h - 1], outline=LEG_EDGE, width=2)
    d.text((box_w / 2, pad + lh_t * 0.55), title_lines[0],
           font=f_title, fill=TEXT_COLOR, anchor="mm")
    d.text((box_w / 2, pad + lh_t * 1.55), title_lines[1],
           font=f_title, fill=TEXT_COLOR, anchor="mm")
    return img


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

    # 縣市碼表：右側欄（col12=縣市編碼, col13=縣市名）
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
        t["county"] = n.translate(VARIANT_CHAR_MAP)   # 統一 臺→台（臺北市→台北市）

    return towns, county_code2name


def norm_town_core(name):
    """鄉鎮市區名 → 正規化核心字（表側用）。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


def parse_votes_year(xlsx_path):
    """各屆 xlsx（鄉鎮市區級別）：縣市、鄉鎮市區 分列，各政黨得票率並排。
    政黨欄位由表頭動態偵測（欄名以「得票率」結尾）。
    回傳 (data, cand_names, unmatched)
      data: {(target_county, town_core): {party: [rate...]}}（同 key 多列 → 平均）
    """
    df = pd.read_excel(xlsx_path, sheet_name="鄉鎮市區級別")
    df.columns = [str(c) for c in df.columns]
    rate_cols = OrderedDict()
    for col in df.columns:
        if col.endswith("得票率"):
            rate_cols[col[:-3]] = col          # 政黨名 → 得票率欄名
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
        # 統一 臺→台（臺北市 → 台北市），與 load_correspondence 一致
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

    # 平均（中西區等合併後多列）
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
    for p in LEGEND_ORDER:                    # 已知政黨優先
        if p in cand_names:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
    for p in cand_names:                      # 未知名政黨依序取用備用色階
        if p not in party_scheme:
            idx = next((s for s in SCHEME_FALLBACK if s not in used_schemes), 5)
            party_scheme[p] = idx
            used_schemes.add(idx)

    # ------------- 建立對照表索引 -------------
    for t in towns:
        t["core"] = norm_town_core(t["name"])

    # ------------- 手動指定填色（特例／無選舉資料區） -------------
    ov = {}
    for county, (party, rate) in COUNTY_OVERRIDES.get(year, {}).items():
        for t in towns:
            if t["county"] == county:
                ov[(t["county"], t["core"])] = {party: rate}
    for key, (party, rate) in TOWN_OVERRIDES.get(year, {}).items():
        ov[key] = {party: rate}
    if ov:
        data.update(ov)
        print(f"  手動指定填色       : {len(ov)} 個鄉鎮市區")
        for (cty, core), rec in sorted(ov.items()):
            (party, rate), = rec.items()
            print(f"      {cty}{core} → {LEG_DISPLAY_NAME.get(party, party)} {rate:g}%")

    # 資料預先按「縣市 → 鄉鎮市區」分層，對照時先比縣市、再比鄉鎮
    data_by_county = {}
    for (county, core), rec in data.items():
        data_by_county.setdefault(county, {})[core] = rec

    # ------------- 統計：領先政黨（先算，用於自適應色階位移） -------------
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

    min_win = min(win_rates) if win_rates else 0
    legend_start_tier = int(min_win // 5) * 5
    # 自適應色階位移：<35% 鄉鎮數 <15 → 不動；<30% <15 → -5；否則 -10
    shift = pick_shift(win_rates)
    stops = scale_for_shift(shift)
    nb = {t: sum(1 for r in win_rates if r < t) for t in (35, 30, 25)}
    print(f"  領先得票率範圍     : {min_win:.1f}% ~ {max(win_rates):.1f}%"
          f"（圖例自 {legend_start_tier}% 起）")
    print(f"  色階位移           : -{shift}（<35%:{nb[35]} 個、<30%:{nb[30]} 個、"
          f"<25%:{nb[25]} 個鄉鎮 → 基準 {35 - shift}% 起；"
          f"末檔 100 顏色獨立成格並標「XX%以上」）")

    matched_data_keys = []
    no_data_names = []
    for t in towns:
        rec = data_by_county.get(t["county"], {}).get(t["core"])
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

    # 未配對到的資料 key（理論上應為空）
    orphan_keys = set(data.keys()) - set(matched_data_keys)

    print(f"  有資料(填色)       : {len(matched_data_keys)}")
    print(f"  無資料(不著色)     : {len(no_data_names)}")
    if orphan_keys:
        print("  ※ 資料表有但未配對到對照表的 key（該區將不著色）：")
        for k in sorted(orphan_keys):
            print(f"      {k}")

    # ------------- 重著色底圖 -------------
    img = Image.open(COLORFUL_PNG).convert("RGBA")
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

    # 合成（Colorful2 為全不透明：鄉鎮色重著色，界線灰與底色保留）
    # 無資料鄉鎮（如 1992 年金門縣＋連江縣，未納入選舉）依正常流程填 #323232
    out_arr = arr.copy()
    out_arr[..., :3] = recolored_flat

    base = Image.fromarray(out_arr).convert("RGB")
    W, H = base.size

    # ------------- 圖例（僅繪製有領先鄉鎮的政黨；橫式，置於左上角方框） -------------
    legend_parties = [n for n in cand_names if win_cnt.get(n, 0) > 0]
    if not legend_parties:
        raise SystemExit(f"{year} 無任何領先政黨，請檢查資料。")
    # ------------- 畫布布局：地圖滿幅 ＋ 標題＋圖例（左上角方框，同一外框） -------------
    title_lines = [f"{session_label}立法院立法委員選舉",
                   "在各鄉鎮市區得票領先之政黨得票比例圖"]
    legend_img = build_legend_img(legend_parties, party_scheme,
                                  legend_start_tier, title_lines, stops)

    final_img = Image.new("RGB", (W, H), hex2rgb(CANVAS_COLOR))
    final_img.paste(base, (0, 0))
    # 標題＋圖例（同一外框）貼入左上角方框
    final_img.paste(legend_img, (LEG_BOX[0], LEG_BOX[1]))

    out_png = os.path.join(OUT_DIR, f"{year}年立法委員選舉_得票率地圖.png")
    os.makedirs(OUT_DIR, exist_ok=True)
    # 先存 ASCII 暫存名再替換，避開偶發的目標檔佔用／開檔失敗
    tmp_png = os.path.join(OUT_DIR, f"_tmp_{year}.png")
    for attempt in range(5):
        try:
            final_img.save(tmp_png)
            os.replace(tmp_png, out_png)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.8)
    print(f"  輸出: {out_png}  ({final_img.width}×{final_img.height}px)")
    print(f"     標題＋圖例外框: 錨點左上角 {LEG_BOX[0]},{LEG_BOX[1]}，"
          f"動態大小 {legend_img.width}×{legend_img.height}px"
          f"（上限 {LEG_BOX[2]}×{LEG_BOX[3]}）")
    print(f"     主圖基於 {len(matched_data_keys)} 個有資料鄉鎮市區填色；色階自 {legend_start_tier}% 起\n")
    return True


def main():
    print("=" * 62)
    print("  1992-2004 五屆立法委員選舉 政黨得票率地圖 批次繪製")
    print(f"  底圖：{os.path.basename(COLORFUL_PNG)}；圖例：橫式（左上角方框 {LEG_BOX}）")
    print("=" * 62)

    towns, county_code2name = load_correspondence()
    print(f"  對照表鄉鎮市區    : {len(towns)} 個（全縣市 {len(county_code2name)} 個）\n")

    done = []
    for year, session_label, date_line in ELECTIONS:
        if draw_year(year, session_label, date_line, towns):
            done.append(year)

    print("#" * 62)
    print(f"完成 {len(done)}/{len(ELECTIONS)} 屆：{done}")


if __name__ == "__main__":
    main()
