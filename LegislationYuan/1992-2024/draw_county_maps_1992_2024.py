#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1992-2024 十屆立法委員選舉 —「各縣市」得票領先政黨得票率地圖
================================================================
參考 draw_legislator_maps_1992_2004.py（鄉鎮市區版）改寫，著色層級提高為「縣市」。

底圖（皆為縣市單色圖，由 County/ 的鄉鎮唯一色圖轉製，鄉鎮界線已抹去）：
    1992-2008（25 縣市時期）：County/Colorful25.png
        對照表 County/Name_Color_Correspondence_25.xlsx（縣市彙總 → 顏色 HEX）
        縣市：台北市、台北縣、基隆市、桃園縣、新竹縣、新竹市、苗栗縣、
              台中市、台中縣、彰化縣、南投縣、雲林縣、嘉義市、嘉義縣、
              台南市、台南縣、高雄市、高雄縣、屏東縣、宜蘭縣、花蓮縣、
              台東縣、澎湖縣、金門縣、連江縣
    2012-2024（22 縣市時期）：County/Colorful5.png
        對照表 County/Name_Color_Correspondence_22.xlsx
        縣市：台北市、新北市、基隆市、桃園市、新竹縣、新竹市、苗栗縣、
              台中市、彰化縣、南投縣、雲林縣、嘉義市、嘉義縣、台南市、
              高雄市、屏東縣、宜蘭縣、花蓮縣、台東縣、澎湖縣、金門縣、連江縣
    （2012 年資料仍稱「桃園縣」，比對前先正規化為底圖用名「桃園市」）

得票資料：data/{year}立法委員_政黨鄉鎮得票.xlsx（工作表「鄉鎮市區級別」）
    欄位：縣市、鄉鎮市區、<政黨>得票數／<政黨>得票率、總得票數
    本腳本**由鄉鎮得票數加總回縣市**再算得票率（比直接讀「縣市級別」更穩，
    且可驗證各黨得票率合計＝100%）；政黨欄位由表頭動態偵測（以「得票數」結尾）。

繪圖規則：
    - 每個縣市取「領先政黨」，以其政黨色階按該縣市得票率深淺填色
    - 色階**十年固定**（35% 起、5% 一階、末階 85% 以上），跨屆可直接比較，
      不像鄉鎮版需依分布自適應位移（縣市僅 22-25 個，分布集中於 35-65%）
    - 縣市界線（底圖 #000000）與海岸線（#0066CC）保留；無資料縣市填畫布底色
      #323232（1992 年金門縣、連江縣未納入資料，比照鄉鎮版以全縣得票率補繪）
    - **不標縣市名**（SHOW_COUNTY_LABELS = False）；圖面純以顏色表達，
      避免地名壓在色塊上干擾閱讀

版面（沿用鄉鎮版）：地圖滿幅；標題兩行＋橫式圖例同置于左上角方框 LEG_BOX。

輸出：map_county/{year}年立法委員選舉_縣市得票率地圖.png

執行：
    py draw_county_maps_1992_2024.py
"""
import os
import warnings
from collections import OrderedDict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTY_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "County")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "map_county")

# ===================== 兩套底圖 =====================
PACKS = {
    "25": {"png": "Colorful25.png", "corr": "Name_Color_Correspondence_25.xlsx"},
    "22": {"png": "Colorful5.png",  "corr": "Name_Color_Correspondence_22.xlsx"},
}

# ===================== 十屆選舉定義 =====================
ELECTIONS = [
    # (年份, 屆別, 選舉日期, 底圖套別)
    ("1992", "第二屆", "1992年12月19日", "25"),
    ("1995", "第三屆", "1995年12月2日",  "25"),
    ("1998", "第四屆", "1998年12月5日",  "25"),
    ("2001", "第五屆", "2001年12月1日",  "25"),
    ("2004", "第六屆", "2004年12月11日", "25"),
    ("2008", "第七屆", "2008年1月12日",  "25"),
    ("2012", "第八屆", "2012年1月14日",  "22"),
    ("2016", "第九屆", "2016年1月16日",  "22"),
    ("2020", "第十屆", "2020年1月11日",  "22"),
    ("2024", "第十一屆", "2024年1月13日", "22"),
]

CANVAS_COLOR = "#323232"     # 畫布背景；同時作為無資料縣市的填色

# ===================== 色階（十年固定：35% 起、5% 一階） =====================
# 顏色直接沿用 draw_legislator_maps_1992_2004.py 的 35% 基準色階（shift=0）：
#   35、40、45、50、55、60、65、70、75、80、85、100（末階顏色＝85% 以上）
# 圖例刻度：35% 以下 → 45% → 55% → 65% → 75% → 85% 以上（每 10 個百分點標一次）
LEVELS = [35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 100]

# 各政黨色階：淺 → 深，共 12 色，對應 LEVELS
RAMPS = {
    # 中國國民黨（藍色系）
    "中國國民黨": [
        "#A6E9FF", "#73D9FF", "#40C8FF", "#00C0F4", "#00A2E8", "#0080B8",
        "#006591", "#004B6B", "#003247", "#00283A", "#001F2E", "#010D29",
    ],
    # 民主進步黨（綠色系）
    "民主進步黨": [
        "#E8FFE0", "#CEFFC2", "#C0FFB1", "#A4FF90", "#78FF4F", "#68DE45",
        "#54B337", "#3C8027", "#2B5C1C", "#1D3D13", "#0F210A", "#071A09",
    ],
    # 親民黨（橘色系）
    "親民黨": [
        "#FFC2AA", "#FFA380", "#FF8456", "#FF662B", "#FF4701", "#D93A00",
        "#B33000", "#8D2500", "#6B1D00", "#4D1400", "#3A1000", "#170500",
    ],
    # 新黨（金黃色系）
    "新黨": [
        "#FFE89A", "#FFDD66", "#FFD133", "#FFC700", "#F2B800", "#E0A800",
        "#C79200", "#AD7A00", "#946400", "#4D4900", "#2E2A00", "#161400",
    ],
    # 無黨籍及未經政黨推薦（灰色系）
    "無黨籍及未經政黨推薦": [
        "#D9D9D9", "#C9C9C9", "#B6B6B6", "#A0A0A0", "#898989", "#727272",
        "#5B5B5B", "#464646", "#333333", "#232323", "#151515", "#0B0B0B",
    ],
    # 無黨團結聯盟（粉色系）
    "無黨團結聯盟": [
        "#FAC6D8", "#F8A8C5", "#F68AB2", "#F46C9F", "#F24E8C", "#F03772",
        "#D01058", "#B30D4B", "#950B3F", "#770932", "#590726", "#3D0419",
    ],
    # 民主聯盟（桃紅色系，較無盟更深）
    "民主聯盟": [
        "#FFE0EC", "#FFBDD2", "#FF98B8", "#FF6E9B", "#FF4079", "#F41E5E",
        "#C8164C", "#9E113C", "#750C2D", "#520720", "#380517", "#20030B",
    ],
    # 台灣團結聯盟（咖啡色系）
    "台灣團結聯盟": [
        "#F5E9DB", "#EDDAC0", "#E8CFAF", "#E0C199", "#D8AE7B", "#CB9450",
        "#A37135", "#8A5C2A", "#744A20", "#5F3C19", "#4E3214", "#2E1D0B",
    ],
    # 建國黨（青色系）
    "建國黨": [
        "#D9FFF6", "#A6FFEF", "#73F9E2", "#40E8D2", "#00D4C0", "#00B8A6",
        "#009385", "#007468", "#00564E", "#003832", "#002420", "#011511",
    ],
    # 中華社會民主黨（紫色系）
    "中華社會民主黨": [
        "#F0D9FF", "#DFBFFF", "#CFA0FF", "#BE80FF", "#AB5FF9", "#9A43E8",
        "#7C34B8", "#612A91", "#481F6B", "#301547", "#1E0D2E", "#100729",
    ],
    # 工黨（棕褐色系）
    "工黨": [
        "#F5E8D9", "#E8D2B4", "#D9B98D", "#C99F66", "#B98545", "#A66F2B",
        "#87571F", "#6B4418", "#513411", "#38230B", "#261707", "#170E04",
    ],
    # 台灣民眾黨（青綠色系）
    "台灣民眾黨": [
        "#CFFCF8", "#A2F7EF", "#7FF0E6", "#4DE6D9", "#00D9CA", "#00BFB2",
        "#00A89C", "#008080", "#006666", "#004C4C", "#003838", "#001919",
    ],
    # 其餘小黨／未知名政黨（黃綠系備援）
    "其他政黨": [
        "#EFFFD9", "#DDF5B4", "#C8E88D", "#B0D966", "#96C845", "#7BB22E",
        "#628F22", "#4C6E19", "#395112", "#28380C", "#1B2508", "#111805",
    ],
}

# 政黨 → 色階組別（同名別稱一併指向同一色階）
PARTY_SCHEME = {
    "中國國民黨": "中國國民黨",
    "民主進步黨": "民主進步黨",
    "親民黨": "親民黨",
    "新黨": "新黨",
    "無黨籍及未經政黨推薦": "無黨籍及未經政黨推薦",
    "無黨籍": "無黨籍及未經政黨推薦",
    "無黨團結聯盟": "無黨團結聯盟",
    "民主聯盟": "民主聯盟",
    "台灣團結聯盟": "台灣團結聯盟",
    "建國黨": "建國黨",
    "中華社會民主黨": "中華社會民主黨",
    "工黨": "工黨",
    "勞動黨": "工黨",
    "台灣民眾黨": "台灣民眾黨",
    "台灣民衆黨": "台灣民眾黨",
}
# 未知名政黨依序取用未被佔用的備援色階
SCHEME_FALLBACK = ["其他政黨", "建國黨", "中華社會民主黨", "民主聯盟", "工黨",
                   "台灣團結聯盟", "無黨團結聯盟", "新黨", "親民黨"]

# 圖例欄位排列順序（有領先縣市的政黨才會畫出，其餘依資料欄位順序接在後面）
LEGEND_ORDER = [
    "親民黨", "新黨", "民主進步黨", "中國國民黨",
    "無黨籍及未經政黨推薦", "無黨籍", "無黨團結聯盟", "民主聯盟",
    "台灣團結聯盟", "建國黨", "中華社會民主黨", "工黨", "台灣民眾黨",
]

# ===================== 縣市名正規化 =====================
# 異體字／用字差異（資料側「臺」→ 底圖側「台」）
VARIANT_CHAR_MAP = str.maketrans({"臺": "台"})

# 22 縣市底圖：資料中的舊名 → 底圖用名
NAME_TO_22 = {"桃園縣": "桃園市"}

# ===================== 手動指定填色（無選舉資料區） =====================
# 1992 年資料未含金門縣、連江縣，比照鄉鎮市版以全縣得票率補繪：
#   金門縣 → 無黨籍 53%（陳清寶）；連江縣 → 中國國民黨 58%（曹爾忠）
COUNTY_OVERRIDES = {
    "1992": {
        "金門縣": ("無黨籍及未經政黨推薦", 53.0),
        "連江縣": ("中國國民黨", 58.0),
    },
}

# ===================== 版面參數 =====================
LEG_BOX = (151, 825, 1220, 1950)   # 圖例外框錨點(左上 x,y)與大小上限(右下 x,y)
LEG_PAD = 10                       # 圖例內容與外框左／右／上邊界線的留白（px）
LEG_BOTTOM_PAD = 44                # 色塊底部與外框下邊界線的留白（px）

TITLE_FONT_SIZE = 50               # 標題基準字號（超過上限寬度時自動收縮）
TITLE_FONT_MIN = 18
TITLE_FONT_MAX = 60
TEXT_COLOR = (255, 255, 255)

# ---- 橫式圖例 ----
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]
LEG_BORDER = (252, 252, 252, 255)
LEG_BG = (50, 50, 50, 255)
LEG_EDGE = (252, 252, 252, 255)
LEG_INK = (252, 252, 252)
TICK_LABEL_STEP = 10               # 中間刻度每 10 個百分點標一次
CELL_RATIO = 110 / 88              # 色塊長寬比（寬:高）
CELL_H_MAX = 72                    # 色塊高度上限（px）
NAME_BLOCK_GAP = 12
NAME_FONT_MAX = 40
TITLE_GRID_GAP = 10
COL_GAP_FRAC = 0.30
LEG_NAME_LINES = {
    "中國國民黨": ("中國", "國民黨"),
    "民主進步黨": ("民主", "進步黨"),
    "台灣團結聯盟": ("台灣", "團結", "聯盟"),
    "無黨籍及未經政黨推薦": ("無黨籍", "及未經", "政黨推薦"),
    "無黨團結聯盟": ("無黨", "團結", "聯盟"),
    "民主聯盟": ("民主", "聯盟"),
    "台灣民眾黨": ("民眾", "黨"),
}
LEG_DISPLAY_NAME = {"無黨籍及未經政黨推薦": "無黨籍"}

# ---- 縣市名標註（預設關閉：圖面不壓地名，僅以顏色表達） ----
SHOW_COUNTY_LABELS = False         # 改為 True 即在各縣市上標名稱
# 字級依「標註點所在的水平淨寬／垂直淨高」決定（比內切圓半徑更貼合狹長形狀），
# 使文字盡量不越界；面積極小的離島（連江）改標在群島外接框中心（浮於海面）。
# 標註用「正文（非粗黑）」字型，避免小字級在色塊上過於搶眼。
LABEL_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msjh.ttc",          # 微軟正黑體（正文）
    r"C:\Windows\Fonts\msyh.ttc",
]
LABEL_MIN = 13                     # 字級下限（px）
LABEL_MAX = 44                     # 字級上限（px）
LABEL_W_FRAC = 0.60                # 文字總寬上限 ＝ 淨寬 × 此比例
LABEL_H_FRAC = 0.50                # 文字高度上限 ＝ 淨高 × 此比例
LABEL_TINY_RADIUS = 12             # 內切圓半徑小於此值 → 視為極小離島
# 標註名例外：底圖用名 → 當屆實際縣市名（桃園 2014 年底才改制直轄市）
LABEL_ALIAS = {("2012", "桃園市"): "桃園縣"}

_FONT_PATH = None
_LABEL_FONT_PATH = None


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


def _label_font(size):
    """縣市名標註字型（正文，非粗黑）；找不到則沿用標題字型。"""
    global _LABEL_FONT_PATH
    if _LABEL_FONT_PATH is None:
        for p in LABEL_FONT_CANDIDATES:
            if os.path.isfile(p):
                _LABEL_FONT_PATH = p
                break
    if _LABEL_FONT_PATH is None:
        return _font(size)
    return ImageFont.truetype(_LABEL_FONT_PATH, size)


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_lum(rgb):
    """相對亮度（0-1），用於決定標註文字用深色或淺色。"""
    r, g, b = rgb
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


# ===================== 圖例（標題＋色階欄） =====================
def _party_name_color(party, scheme_map, stops):
    """政黨名顏色：取該黨色階 55% 階（深底上清晰）；未知則用淺灰。
    近灰階（無黨籍）色階本身太暗，改用固定淺灰以免深底上糊掉。"""
    hx = "#CCCCCC"
    for upper, c in stops[scheme_map.get(party, "其他政黨")]:
        if upper == 55:
            hx = c
            break
    r, g, b = hex2rgb(hx)
    if max(r, g, b) - min(r, g, b) <= 24:      # 近無彩色 → 淺灰
        return "#A8A8A8"
    return hx


def _split_party_name(nm):
    if nm in LEG_NAME_LINES:
        return LEG_NAME_LINES[nm]
    n = len(nm)
    if n <= 3:
        return (nm,)
    k = -(-n // 3)
    base, extra = divmod(n, k)
    lines, i = [], 0
    for j in range(k):
        ln = base + (1 if j < extra else 0)
        lines.append(nm[i:i + ln])
        i += ln
    return tuple(lines)


def _draw_name_justified(d, cx, y_top, lines, font, fill, lh):
    """政黨名多行分散對齊：各行拉伸到同一寬度後水平置中。"""
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


def build_legend_img(legend_parties, scheme_map, title_lines, stops):
    """繪製標題＋圖例外框（回傳動態大小的 RGBA Image）。"""
    bx0, by0, bx1, by1 = LEG_BOX
    max_w, max_h = bx1 - bx0, by1 - by0
    n = len(legend_parties)
    pad = LEG_PAD
    avail_w = max_w - 2 * pad

    n_lv = len(stops[scheme_map[legend_parties[0]]])

    disp_names = {p: LEG_DISPLAY_NAME.get(p, p) for p in legend_parties}
    name_lines = {p: _split_party_name(disp_names[p]) for p in legend_parties}
    max_lines = max(len(v) for v in name_lines.values())

    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)

    # ---- 標題字號 ----
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

    # ---- 色塊尺寸 ----
    v_pad = pad + LEG_BOTTOM_PAD
    cell_h = min(CELL_H_MAX,
                 max(8.0, (max_h - v_pad - title_h - TITLE_GRID_GAP - 4)
                     / max(1, n_lv) / max(1, max_lines)))
    max_chars = max(len(ln) for lns in name_lines.values() for ln in lns)
    for _ in range(3):
        cell_w = cell_h * CELL_RATIO
        col_gap0 = cell_w * COL_GAP_FRAC
        f_name_size = int(min(NAME_FONT_MAX,
                              (cell_w + col_gap0) / 3 * 0.92,
                              (cell_w + 2 * col_gap0) / max(3, max_chars)))
        lh_name = int(f_name_size * 1.35)
        name_h = max_lines * lh_name + 4
        cell_h_hi = (max_h - v_pad - title_h - TITLE_GRID_GAP
                     - name_h - NAME_BLOCK_GAP) / n_lv
        cell_h = min(CELL_H_MAX, max(8.0, cell_h_hi))
    cell_w = cell_h * CELL_RATIO

    def _axis_w(ch):
        f_t = _font(max(14, int(ch * 0.42)))
        tw = d.textlength("100%以上", font=f_t)
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

    f_name_size = int(min(NAME_FONT_MAX,
                          (cell_w + col_gap) / 3 * 0.92,
                          (cell_w + 2 * col_gap) / max(3, max_chars)))
    f_name = _font(max(12, f_name_size))
    lh_name = int(f_name_size * 1.35)
    name_h = max_lines * lh_name + 4

    box_w = int(min(max_w, max(title_w, content_w))) + 2 * pad
    cols_top = pad + title_h + TITLE_GRID_GAP
    blocks_top = cols_top + name_h + NAME_BLOCK_GAP
    # 外框高度貼齊內容（色塊底緣再留 LEG_BOTTOM_PAD），不超過上限
    box_h = int(min(max_h, blocks_top + n_lv * cell_h + LEG_BOTTOM_PAD))

    img = Image.new("RGBA", (box_w, box_h), LEG_BG)
    d = ImageDraw.Draw(img)

    x0 = (box_w - content_w) / 2
    x_tick_r = x0 + int(tick_text_w) + 6
    grid_x0 = x0 + axis_w

    # ---- 刻度尺：每格＝區間 (上一階, 本階]；首格「35%以下」、末格「85%以上」 ----
    first_v = LEVELS[0]
    last_v = LEVELS[-2]
    for k in range(1, n_lv + 1):
        v = LEVELS[k - 1]
        is_first, is_last = (k == 1), (k == n_lv)
        if is_first:
            y = blocks_top + k * cell_h
            txt = "%d%%以下" % first_v
        elif is_last:
            y = blocks_top + (n_lv - 1) * cell_h
            txt = "%d%%以上" % last_v
        elif (v - first_v) % TICK_LABEL_STEP == 0 and v < last_v:
            y = blocks_top + k * cell_h
            txt = "%d%%" % v
        else:
            continue
        d.line([x_tick_r + 4, y, x_tick_r + 4 + tick_len, y],
               fill=LEG_INK + (170,), width=2)
        d.text((x_tick_r, y), txt, font=f_tick,
               fill=LEG_INK + (230,), anchor="rm")

    # ---- 各政黨欄：欄頂政黨名（黨色）＋ 連續無間隙色階 ----
    for i, p in enumerate(legend_parties):
        x = grid_x0 + i * (cell_w + col_gap)
        cx = x + cell_w / 2
        fill = hex2rgb(_party_name_color(p, scheme_map, stops)) + (255,)
        y_name_top = blocks_top - NAME_BLOCK_GAP \
            - len(name_lines[p]) * lh_name \
            - (lh_name / 2 if len(name_lines[p]) == 1 else 0)
        _draw_name_justified(d, cx, y_name_top, name_lines[p],
                             f_name, fill, lh_name)
        y_top = blocks_top
        for k, (pct, hx) in enumerate(stops[scheme_map[p]]):
            d.rectangle([x, y_top + k * cell_h,
                         x + cell_w, y_top + (k + 1) * cell_h],
                        fill=hex2rgb(hx) + (255,))
        d.rectangle([x, y_top, x + cell_w, y_top + n_lv * cell_h],
                    outline=LEG_BORDER, width=2)

    # ---- 外框與標題 ----
    d.rectangle([0, 0, box_w - 1, box_h - 1], outline=LEG_EDGE, width=2)
    d.text((box_w / 2, pad + lh_t * 0.55), title_lines[0],
           font=f_title, fill=TEXT_COLOR, anchor="mm")
    d.text((box_w / 2, pad + lh_t * 1.55), title_lines[1],
           font=f_title, fill=TEXT_COLOR, anchor="mm")
    return img


# ===================== 讀取對照表 / 底圖幾何 =====================
def load_counties(corr_xlsx):
    """讀「縣市彙總」工作表 → list of {index, name, color, rgb, mask, center, radius}"""
    df = pd.read_excel(corr_xlsx, sheet_name="縣市彙總")
    counties = []
    for _, r in df.iterrows():
        hx = str(r["顏色 (HEX)"]).strip().upper()
        counties.append({
            "index": int(r["序號"]),
            "name": str(r["縣市"]).strip(),
            "color": hx,
            "rgb": hex2rgb(hx),
        })
    return counties


def rgb_key(arr):
    """RGB 陣列 → 單一整數色鍵（顏色互比用）。"""
    return ((arr[..., 0].astype(np.int32) << 16)
            | (arr[..., 1].astype(np.int32) << 8) | arr[..., 2].astype(np.int32))


def build_geometry(key, counties):
    """以顏色為鍵，找出每個縣市的最大連通區塊、內切圓半徑與「最內側」標註點，
    並記錄外接框（供標註時量測淨寬／淨高）。"""
    for c in counties:
        r, g, b = c["rgb"]
        c["key"] = (r << 16) | (g << 8) | b
        m = (key == c["key"])
        c["pixels"] = int(m.sum())
        if not c["pixels"]:
            c["center"], c["radius"], c["bbox"], c["full_bbox"] = None, 0, None, None
            continue
        lab, nl = ndi.label(m)
        c["ncomp"] = int(nl)
        sizes = ndi.sum(m, lab, range(1, nl + 1))
        big = (lab == (int(np.argmax(sizes)) + 1))
        dist = ndi.distance_transform_edt(big)
        cy, cx = np.unravel_index(int(np.argmax(dist)), dist.shape)
        ys, xs = np.nonzero(big)
        ys2, xs2 = np.nonzero(m)
        c["center"] = (int(cx), int(cy))
        c["radius"] = float(dist.max())
        c["bbox"] = (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))
        c["full_bbox"] = (int(ys2.min()), int(ys2.max()),
                          int(xs2.min()), int(xs2.max()))
        # 全縣重心與擴散範圍（破碎離島標註用）
        scx, scy = float(xs2.mean()), float(ys2.mean())
        d = np.hypot(xs2 - scx, ys2 - scy)
        c["scatter_center"] = (int(scx), int(scy))
        c["spread"] = float(np.clip(np.percentile(d, 88), 40, 260))
    return counties


def label_metrics(c, key):
    """量測標註點所在的水平淨寬與垂直淨高（像素）。"""
    if c["bbox"] is None:
        return 0, 0
    y0, y1, x0, x1 = c["bbox"]
    sub = (key[y0:y1 + 1, x0:x1 + 1] == c["key"])
    cy, cx = c["center"][1] - y0, c["center"][0] - x0
    if not (0 <= cy < sub.shape[0] and 0 <= cx < sub.shape[1]) or not sub[cy, cx]:
        return 0, 0
    row, col = sub[cy], sub[:, cx]
    l = cx
    while l > 0 and row[l - 1]:
        l -= 1
    r = cx
    while r < len(row) - 1 and row[r + 1]:
        r += 1
    t = cy
    while t > 0 and col[t - 1]:
        t -= 1
    b = cy
    while b < len(col) - 1 and col[b + 1]:
        b += 1
    return r - l + 1, b - t + 1


CANVAS_KEY = (0x32 << 16) | (0x32 << 8) | 0x32


def sea_anchor(text_w, text_h, cx, cy, spread, key):
    """破碎離島（澎湖／金門／連江）：在群島附近找一塊「純海面」放標註。
    由群島重心向外、以「下方優先」的順序試放，距離限制在群島擴散範圍內，
    避免文字跑到小圖框外或壓到零散島嶼。"""
    import math
    cands = [(0, 0)]
    for frac in (0.28, 0.45, 0.62, 0.80):
        r = spread * frac
        for ang in (90, 65, 115, 40, 140, 0, 180, 270, 310, 230):
            cands.append((r * math.cos(math.radians(ang)),
                          r * math.sin(math.radians(ang))))

    hw, hh = int(text_w / 2) + 4, int(text_h / 2) + 4
    for (dx, dy) in cands:
        px, py = int(cx + dx), int(cy + dy)
        if (px - hw < 0 or py - hh < 0
                or px + hw >= key.shape[1] or py + hh >= key.shape[0]):
            continue
        sub = key[py - hh:py + hh, px - hw:px + hw]
        if (sub == CANVAS_KEY).mean() >= 0.985:     # 幾乎全為海面
            return (px, py)
    return (cx, cy)


# ===================== 得票資料 =====================
def county_results(xlsx_path):
    """鄉鎮得票數加總回縣市 → {縣市: {政黨: 得票率%}}"""
    df = pd.read_excel(xlsx_path, sheet_name="鄉鎮市區級別")
    df.columns = [str(c) for c in df.columns]
    vote_cols = OrderedDict()
    for col in df.columns:
        if col.endswith("得票數") and col != "總得票數":
            vote_cols[col[:-3]] = col
    if not vote_cols:
        raise ValueError(f"{xlsx_path} 未偵測到任何「得票數」欄位")

    g = df.groupby("縣市")[list(vote_cols.values())].sum()
    out = {}
    for county, row in g.iterrows():
        tot = float(row.sum())
        if tot <= 0:
            continue
        out[str(county).strip()] = {p: float(row[col]) / tot * 100.0
                                    for p, col in vote_cols.items()}
    return out, list(vote_cols.keys())


def map_county_name(src, pack):
    """資料縣市名 → 底圖縣市名。"""
    nm = str(src).strip().translate(VARIANT_CHAR_MAP)
    if pack == "22":
        nm = NAME_TO_22.get(nm, nm)
    return nm


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


# ===================== 單屆繪圖 =====================
def draw_year(year, session_label, date_line, pack, base_cache):
    print("=" * 62)
    print(f"  {year} {session_label}立法委員選舉（底圖：{PACKS[pack]['png']}）")
    print("=" * 62)

    xlsx_path = os.path.join(DATA_DIR, f"{year}立法委員_政黨鄉鎮得票.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"  ※ 找不到 {xlsx_path}，略過本屆")
        return False

    data_raw, party_cols = county_results(xlsx_path)
    # 縣市名正規化
    data = {}
    for k, rec in data_raw.items():
        data[map_county_name(k, pack)] = rec

    counties = base_cache[pack]["counties"]
    arr = base_cache[pack]["arr"]

    # 手動指定填色（無資料縣市）
    overrides = COUNTY_OVERRIDES.get(year, {})
    for cname, (party, rate) in overrides.items():
        data[cname] = {party: rate}
        print(f"  手動指定填色 : {cname} → {LEG_DISPLAY_NAME.get(party, party)} {rate:g}%")

    known = {c["name"] for c in counties}
    extra = set(data) - known
    if extra:
        print(f"  ※ 資料縣市在底圖上找不到（將忽略）：{sorted(extra)}")

    # ------------- 政黨 → 色階指派 -------------
    used = set()
    party_scheme = {}
    for p in LEGEND_ORDER:
        if p in party_cols:
            party_scheme[p] = PARTY_SCHEME.get(p, "其他政黨")
            used.add(party_scheme[p])
    # 別名（無黨籍 = 無黨籍及未經政黨推薦）不重複佔用
    for p in party_cols:
        if p in party_scheme:
            continue
        if p in PARTY_SCHEME:
            party_scheme[p] = PARTY_SCHEME[p]
            used.add(party_scheme[p])
    for p in party_cols:
        if p in party_scheme:
            continue
        idx = next((s for s in SCHEME_FALLBACK if s not in used), "其他政黨")
        party_scheme[p] = idx
        used.add(idx)

    stops_all = {k: [(lv, c) for lv, c in zip(LEVELS, colors)]
                 for k, colors in RAMPS.items()}

    # ------------- 各縣市領先政黨 -------------
    win_cnt = {p: 0 for p in party_cols}
    win_rates = []
    for c in counties:
        rec = data.get(c["name"])
        if not rec:
            c["winner"], c["rate"], c["fill"] = None, None, CANVAS_COLOR
            continue
        vals = {p: rec.get(p, float("nan")) for p in party_cols}
        w = max(vals, key=lambda p: (vals[p] if not np.isnan(vals[p]) else -1.0))
        c["winner"], c["rate"] = w, vals[w]
        c["fill"] = get_color_by_value(vals[w], stops_all[party_scheme[w]])
        if w in win_cnt:
            win_cnt[w] += 1
        win_rates.append(vals[w])

    print(f"  縣市數             : {len(counties)}（有資料 {len(win_rates)}）")
    print("  各政黨領先縣市數:")
    for p in party_cols:
        if win_cnt.get(p):
            print(f"      {p}: {win_cnt[p]}")
    if win_rates:
        print(f"  領先得票率範圍     : {min(win_rates):.1f}% ~ {max(win_rates):.1f}%"
              f"（色階固定 {LEVELS[0]}% 起，末階 {LEVELS[-2]}% 以上）")
    missing = [c["name"] for c in counties if c["winner"] is None]
    if missing:
        print(f"  無資料（填底色）   : {missing}")

    # ------------- 重著色 -------------
    lut = {}
    for c in counties:
        if c["fill"]:
            lut[tuple(c["rgb"])] = hex2rgb(c["fill"])
    key = rgb_key(arr)
    uniq, inv = np.unique(key.ravel(), return_inverse=True)
    new_uniq = uniq.copy()
    for i, u in enumerate(uniq):
        s = int(u)
        f = lut.get(((s >> 16) & 255, (s >> 8) & 255, s & 255))
        if f is not None:
            new_uniq[i] = (f[0] << 16) | (f[1] << 8) | f[2]
    out_key = new_uniq[inv].reshape(key.shape)
    out_arr = np.empty(arr.shape, dtype=np.uint8)
    out_arr[..., 0] = (out_key >> 16) & 255
    out_arr[..., 1] = (out_key >> 8) & 255
    out_arr[..., 2] = out_key & 255

    base = Image.fromarray(out_arr).convert("RGB")
    W, H = base.size
    draw = ImageDraw.Draw(base)

    # ------------- 縣市名標註（預設不做，見 SHOW_COUNTY_LABELS） -------------
    key_img = base_cache[pack]["key"]
    n_label = 0
    for c in (counties if SHOW_COUNTY_LABELS else []):
        if c["center"] is None:
            continue
        nm = LABEL_ALIAS.get((year, c["name"]), c["name"])
        scattered = (c.get("ncomp", 0) >= 20 and c["radius"] < 60)
        if scattered:
            # 破碎離島（澎湖／金門／連江）：字級固定、標在群島旁的海面
            size = 19
            f = _label_font(size)
            tw = draw.textlength(nm, font=f)
            scx, scy = c["scatter_center"]
            anchor = sea_anchor(tw, size * 1.45, scx, scy, c["spread"], key_img)
        else:
            h_run, v_run = label_metrics(c, key_img)
            if h_run <= 0:
                h_run, v_run = 2 * c["radius"], 2 * c["radius"]
            size = int(min(LABEL_MAX,
                           max(LABEL_MIN,
                               min(LABEL_W_FRAC * h_run / len(nm),
                                   LABEL_H_FRAC * v_run))))
            f = _label_font(size)
            anchor = c["center"]
        sw = max(1, int(round(size / 16)))
        if c["winner"] is None:                       # 無資料：暗灰字
            ink, stroke = (108, 108, 108), (50, 50, 50)
        else:
            lum = rgb_lum(hex2rgb(c["fill"]))
            if lum > 0.55:                            # 淺底 → 深字＋白描邊
                ink, stroke = (26, 26, 26), (255, 255, 255)
            else:                                     # 深底 → 白字＋暗描邊
                ink, stroke = (250, 250, 250), (18, 18, 18)
        draw.text(anchor, nm, font=f, fill=ink, anchor="mm",
                  stroke_width=sw, stroke_fill=stroke)
        n_label += 1

    # ------------- 標題＋圖例 -------------
    legend_parties = [p for p in party_cols if win_cnt.get(p, 0) > 0]
    if not legend_parties:
        raise SystemExit(f"{year} 無任何領先政黨，請檢查資料。")
    legend_parties.sort(key=lambda p: (LEGEND_ORDER.index(p)
                                       if p in LEGEND_ORDER else 99))
    title_lines = [f"{session_label}立法院立法委員選舉",
                   "在各縣市得票領先之政黨得票比例圖"]
    legend_img = build_legend_img(legend_parties, party_scheme, title_lines, stops_all)

    final_img = Image.new("RGB", (W, H), hex2rgb(CANVAS_COLOR))
    final_img.paste(base, (0, 0))
    final_img.paste(legend_img, (LEG_BOX[0], LEG_BOX[1]))

    os.makedirs(OUT_DIR, exist_ok=True)
    out_png = os.path.join(OUT_DIR, f"{year}年立法委員選舉_縣市得票率地圖.png")
    tmp_png = os.path.join(OUT_DIR, f"_tmp_{year}.png")
    for attempt in range(5):
        try:
            final_img.save(tmp_png)
            os.replace(tmp_png, out_png)
            break
        except OSError:
            if attempt == 4:
                raise
            import time
            time.sleep(0.8)
    if SHOW_COUNTY_LABELS:
        print(f"  縣市名標註         : {n_label} 個")
    print(f"  輸出: {out_png}  ({W}×{H}px)")
    print(f"     標題＋圖例: 錨點 {LEG_BOX[0]},{LEG_BOX[1]}，"
          f"{legend_img.width}×{legend_img.height}px")
    print()
    return True


def main():
    print("=" * 62)
    print("  1992-2024 十屆立法委員選舉「縣市」得票率地圖")
    print("=" * 62)

    base_cache = {}
    for pack_id, meta in PACKS.items():
        png = os.path.join(COUNTY_DIR, meta["png"])
        corr = os.path.join(COUNTY_DIR, meta["corr"])
        arr = np.array(Image.open(png).convert("RGB"))
        key = rgb_key(arr)
        counties = load_counties(corr)
        build_geometry(key, counties)
        base_cache[pack_id] = {"arr": arr, "counties": counties, "key": key}
        print(f"  底圖 {meta['png']:<14s}: {arr.shape[1]}×{arr.shape[0]}，"
              f"{len(counties)} 個縣市")
    print()

    done = []
    for year, session_label, date_line, pack in ELECTIONS:
        if draw_year(year, session_label, date_line, pack, base_cache):
            done.append(year)

    print("#" * 62)
    print(f"完成 {len(done)}/{len(ELECTIONS)} 屆：{done}")
    print(f"輸出目錄：{OUT_DIR}")


if __name__ == "__main__":
    main()
