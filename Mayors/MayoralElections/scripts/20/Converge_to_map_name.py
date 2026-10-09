# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與「高雄格式」得票 Excel 結合，
繪製各村里候選人得票率地圖。

資料格式（各里彙總 工作表）：
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票數 ... | 有效票數A
得票率(%) = 候選人得票數 ÷ 有效票數A × 100

色階從 0% 起（10% 間距）。
候選人數量由 Excel 自動偵測，圖例欄數隨之調整。

執行：
    py Converge_to_map.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import numpy as np
import re
import cv2
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from difflib import SequenceMatcher
import unicodedata
import warnings
from shapely.geometry import Point
from shapely.ops import nearest_points

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# ===================== 字体设置 =====================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "data")
MAPS_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "maps")

# ===================== 配置区 =====================
SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

# 要生成的地圖（兩張新北市長選舉）
DATASETS = [
    {
        # 改用 compute_town_rates_2010.py 的輸出（含得票數／有效票數A），
        # 區級標註才能走「Σ得票數 ÷ Σ有效票數」的人口加權，而非村里得票率平均
        "excel": os.path.join(EXCEL_DIR, "2010新北_各區得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2010年市長選舉_得票率地圖_名稱.png"),
        "tag": "2010 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：蔡英文）",
        "title_lines": ["第一屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "蔡英文"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2014新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2014年市長選舉_得票率地圖_名稱.png"),
        "tag": "2014 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：游錫堃）",
        "title_lines": ["第二屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "游錫堃"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2018新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2018年市長選舉_得票率地圖_名稱.png"),
        "tag": "2018 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第三屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "蘇貞昌"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "新北县市首长_2022.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2022年市長選舉_得票率地圖_名稱.png"),
        "tag": "2022 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：林佳龍）",
        "title_lines": ["第四屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "林佳龍"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2005台北县.xlsx"),
        "sheet": "Sheet1",
        "header": 1,
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2005年縣長選舉_得票率地圖_名稱.png"),
        "tag": "2005 臺北縣長選舉（中國國民黨：周錫瑋 / 民主進步黨：羅文嘉）",
        "title_lines": ["第十五屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["周錫瑋", "羅文嘉"],
        "cand_columns": ["周錫偉", "羅文佳"],
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "區里",
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2001年縣長選舉_得票率地圖_名稱.png"),
        "tag": "2001 臺北縣長選舉（新黨：王建煊 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["王建煊", "蘇貞昌"],
        "color_schemes": [
            [(0,   "#FFFFEB"), (35,  "#FFFFEB"), (40, "#FFF8CC"),
             (45, "#FFF0A8"), (50, "#FFE780"), (55, "#FFDD55"),
             (60, "#FFF200"), (65, "#E6DA00"), (70, "#BFB500"),
             (75, "#999100"), (80, "#736D00"), (85, "#4D4900"),
             (100, "#383502")],
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2001年縣長選舉_王建煊得票率地圖_名稱.png"),
        "tag": "2001 王建煊單獨",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）王建煊得票比例圖"],
        "legend_names": ["王建煊"],
        "cand_columns": ["新黨得票率"],
        "color_schemes": [
            [(0,   "#FFFFEB"), (35,  "#FFFFEB"), (40, "#FFF8CC"),
             (45, "#FFF0A8"), (50, "#FFE780"), (55, "#FFDD55"),
             (60, "#FFF200"), (65, "#E6DA00"), (70, "#BFB500"),
             (75, "#999100"), (80, "#736D00"), (85, "#4D4900"),
             (100, "#383502")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2001年縣長選舉_蘇貞昌得票率地圖_名稱.png"),
        "tag": "2001 蘇貞昌單獨",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）蘇貞昌得票比例圖"],
        "legend_names": ["蘇貞昌"],
        "cand_columns": ["民主進步黨得票率"],
        "color_schemes": [
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "1993台北縣_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣1993年縣長選舉_得票率地圖_名稱.png"),
        "tag": "1993 臺北縣長選舉（民主進步黨：尤清 / 中國國民黨：蔡勝邦）",
        "title_lines": ["第十二屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["尤清", "蔡勝邦"],
        "color_schemes": [
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
            [(35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"),
             (50, "#40C8FF"), (55, "#00C0F4"), (60, "#00A2E8"),
             (65, "#0080B8"), (70, "#006591"), (75, "#004B6B"),
             (80, "#003247"), (85, "#001F2E"), (100, "#010D29")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "1997台北縣_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣1997年縣長選舉_得票率地圖_名稱.png"),
        "tag": "1997 臺北縣長選舉（民主進步黨：蘇貞昌 / 中國國民黨：謝深山）",
        "title_lines": ["第十三屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["蘇貞昌", "謝深山"],
        "color_schemes": [
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
            [(35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"),
             (50, "#40C8FF"), (55, "#00C0F4"), (60, "#00A2E8"),
             (65, "#0080B8"), (70, "#006591"), (75, "#004B6B"),
             (80, "#003247"), (85, "#001F2E"), (100, "#010D29")],
        ],
    },
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 10, 32000   # 1px = 10m（比例尺 1:10）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ---------------------------------------------------------------------------
# 繪圖尺寸 —— 底圖沿用 Converge_to_map1.py（標準版）體系，另按需求加粗界線
# ---------------------------------------------------------------------------
# 固定值：留白 3%、村里線 1px、標題字級 100px、圖例色塊 170×105。
# 與標準版的差異（依使用者要求）：區界黑帶 4→6px、外輪廓 6→8px、
# 標題置頂、圖例包圓角黑框嵌進地圖右下角（放不下才退到右側緊貼）。
# 區名標註為本檔新增，字級比照參考圖等比放大並使用粗體。
VILL_LINE_PX  = 1      # 村里界線寬
TOWN_LINE_PX  = 6      # 鄉鎮市區界線寬（黑帶；由 4 加粗到 6，強化區塊感）
OUTER_LINE_PX = 8      # 市外輪廓線寬（黑帶；由 6 加粗到 8）

# ---- 標題 ----
TITLE_FONT_SIZE    = 80   # 標題字級
TITLE_GAP          = 70    # 標題與圖例之間的間距
TITLE_RIGHT_MARGIN = 225   # 畫布右界 = 標題最右端 + 此值

# ---- 圖例 ----
BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING      = 38, 150
LEGEND_PADDING            = 60
MAP_LEGEND_GAP            = 100   # 圖例第一欄與地圖右緣的間距
COLUMN_TITLE_GAP          = 100   # 圖例欄標題（候選人）與第一個色塊的間距
SWATCH_TEXT_GAP           = 8     # 色塊與數值標籤的間距
CAND_NAME_FONT_SIZE       = 72    # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE    = 56    # 圖例數值標籤字級

# ---- 鄉鎮市區標註（新增；上行區名黑字、下行得票率色塊）----
# 字級參照參考圖（consult_map.png）等比放大：參考圖區名 23px／城區寬 1590px，
# 本圖城區寬約 7300px（×4.6）→ 區名約 100px、得票率約 112px，並改用粗體字。
# 依使用者指定：字級統一 30px，字型改用 GenSekiGothic TW H（源石黑體 TW Heavy）。
# 內距／描邊／引線一律跟著縮小，否則小字配大內距會顯得鬆散。
LABEL_NAME_FONT      = 26   # 區名字級
LABEL_RATE_FONT      = 30   # 得票率字級
LABEL_RATE_PAD_X     = 8    # 得票率色塊左右留白
LABEL_RATE_PAD_Y     = 2    # 得票率色塊上下留白
LABEL_NAME_GAP       = 4    # 區名與得票率色塊的垂直間距
LABEL_BORDER         = 2    # 色塊黑描邊寬
LABEL_NAME_HALO      = 3    # 區名白色描邊
LABEL_LEADER_LINE    = 2    # 引線寬
LABEL_LEADER_CASING  = 2    # 引線白色襯線（單邊加粗量）
LABEL_LEADER_MIN_GAP = 12   # 標註框邊到行政區邊距離小於此值 → 不畫引線
LABEL_MAX_LEADER     = 900  # 引線長度上限（px）
# 標註框與「界線」的最小淨空：界線＝純黑像素（村里線／區界／外輪廓）。
# 候選落點的矩形外擴此值後，若仍碰到任何界線像素，就視為不合格落點。
LABEL_LINE_CLEAR_PX  = 4

# ---- 圖例面板（圓角黑框）----
LEGEND_PANEL_PAD    = 34    # 黑框內留白
LEGEND_PANEL_BORDER = 3     # 圓角黑框線寬
LEGEND_PANEL_RADIUS = 24    # 圓角半徑
LEGEND_INMAP_MARGIN = 46    # 圖例嵌進地圖右下角時，距地圖畫布右／下緣的距離
LEGEND_FALLBACK_GAP = 60    # 右下角放不下時，圖例與地圖右緣的間距

# ---- 佈局搜尋參數（無關外觀，只影響尋找落點的努力程度）----
LABEL_RING_RADII   = 36    # 每個區往外搜尋的環數（30→36，密集區給更多機會）
LABEL_RING_ANGLES  = 72    # 每環的角度取樣數
LABEL_KEEP_CAND    = 300   # 每個區先篩出最佳候選數（80→300，讓密集區有更多白區可選）

# 手工微調標註落點：鍵為 town_core（去「鄉/鎮/市/區」後的核心名），
# 值為 (x, y)，座標系 EPSG:3826（TWD97 公尺），代表「標註框中心」。
# 執行一次後，把不滿意的區從 console 印出的【標註落點診斷】複製進來即可。
# 密集區流放策略：把三重/板橋/中和/永和等小區直接指定到西側海域或北側空白，
# 且優先搶佔台北市空缺。下方座標先留空，跑完看結果再手填。
MANUAL_LABEL_POS = {
    # "板橋": (295746, 2766513),
}


def build_scale(city_w_px, city_h_px):
    """回傳繪圖尺寸表（單位 px）。

    底圖／標題／圖例一律回傳 Converge_to_map1.py 的固定值（不隨圖幅縮放），
    只有區名標註是本檔新增的。回傳 dict 讓既有的 st["..."] 取用方式維持不變。
    """
    return dict(
        S=1.0,
        vill_line=VILL_LINE_PX,
        town_line=TOWN_LINE_PX,
        outer_line=OUTER_LINE_PX,
        title_font=TITLE_FONT_SIZE,
        block_w=BLOCK_WIDTH,
        block_h=BLOCK_HEIGHT,
        v_spacing=V_SPACING,
        h_spacing=H_SPACING,
        column_title_gap=COLUMN_TITLE_GAP,
        cand_name_font=CAND_NAME_FONT_SIZE,
        legend_label_font=LEGEND_LABEL_FONT_SIZE,
        # ---- 區名標註 ----
        name_font=LABEL_NAME_FONT,
        rate_font=LABEL_RATE_FONT,
        rate_pad_x=LABEL_RATE_PAD_X,
        rate_pad_y=LABEL_RATE_PAD_Y,
        name_gap=LABEL_NAME_GAP,
        label_border=LABEL_BORDER,
        name_halo=LABEL_NAME_HALO,
        leader_w=LABEL_LEADER_LINE,
        leader_casing=LABEL_LEADER_CASING,
        leader_min_gap=LABEL_LEADER_MIN_GAP,
        max_leader=LABEL_MAX_LEADER,
    )

# ===================== 色階（35% 起，5% 間距）=====================
RATE_COLOR_STOPS = [
    [  # 第 1 组：中国国民党候选人
        (35, "#D9F6FF"),
        (40, "#A6E9FF"),
        (45, "#73D9FF"),
        (50, "#40C8FF"),
        (55, "#00C0F4"),
        (60, "#00A2E8"),
        (65, "#0080B8"),
        (70, "#006591"),
        (75, "#004B6B"),
        (80, "#003247"),
        (85, "#001F2E"),
        (100, "#010D29"),
    ],
    [  # 第 2 组：民主进步党候选人
        (35, "#E8FFE0"),
        (40, "#CEFFC2"),
        (45, "#C0FFB1"),
        (50, "#A4FF90"),
        (55, "#78FF4F"),
        (60, "#68DE45"),
        (65, "#54B337"),
        (70, "#3C8027"),
        (75, "#2B5C1C"),
        (80, "#1D3D13"),
        (85, "#0F210A"),
        (100, "#071A09"),
    ],
    [  # 第 3 组：台湾民众党候选人（图中未出现）
        (35, "#B3FFF0"),
        (40, "#00EBD1"),
        (45, "#00D9CA"),
        (50, "#00BFB2"),
        (55, "#00A89C"),
        (60, "#008080"),
        (65, "#006666"),
        (70, "#004C4C"),
        (75, "#003838"),
        (80, "#003030"),
        (85, "#002626"),
        (100, "#021F1F"),
    ],
    [  # 第 4 组：黄新党王建煊
        (0, "#FFFFEB"),
        (35, "#FFFFEB"),
        (40, "#FFF8CC"),
        (45, "#FFF0A8"),
        (50, "#FFE780"),
        (55, "#FFDD55"),
        (60, "#FFF200"),
        (65, "#E6DA00"),
        (70, "#BFB500"),
        (75, "#999100"),
        (80, "#736D00"),
        (85, "#4D4900"),
        (100, "#383502"),
    ],
]

# ---- 鄉鎮市區標註（區名 + 領先者得票率）----
# 比照參考圖：第一行「區名」黑字直接寫在白底上（不加底色框），
# 第二行「得票率」黑字 + 候選人代表色底框 + 黑色描邊。
TOWN_LABEL_FONT_PATH = r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf"   # GenSekiGothic TW H（源石黑體 TW Heavy）
TOWN_LABEL_FONT_FALLBACK = r"C:\Windows\Fonts\msyhbd.ttc"
TOWN_RATE_MODE = "auto"          # 區級得票率：auto / weighted / mean
MAP_PAD_FRAC_LABELS = 0.03       # 地圖留白比例 —— 與 Converge_to_map1.py 一致
LABEL_MARGIN_PX = 4              # 標註框距畫布邊緣的最小距離（px）

# ===================== 工具函数 =====================
# 異體字/音同字異 正規化對照（表格資料 vs 圖資用字不同，需先統一）
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',     # 坪林區石[曹] / 石槽
    '\U00025562': '槽',   # 坪林區石𕢥里（2024 源資料） / 石槽
    '磘': '窯',     # 中和區瓦[磘]・灰[磘]
    '獇': '羌',     # 樹林區[獇]寮 / 羌寮
    '舘': '館',     # 板橋區公舘 / 三峽區永舘
    '廍': '部',     # 永和區新廍 / 新部
    '峯': '峰',     # 土城區峯廷 / 新店區五峯 / 瑞芳區爪峯
    '脚': '腳',     # 萬里區崁脚 / 崁腳
})

def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    # 圖資以方括號標註疑難字（如 瓦[磘]里），括號本身非地名一部分，去除
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s

def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))

def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))

def get_color_by_value(val, stops):
    if val is None or np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]

def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)

def text_width(font, txt):
    try:
        bbox = font.getbbox(txt)
    except AttributeError:
        bbox = font.getmask(txt).getbbox()
    return (bbox[2] - bbox[0]) if bbox else 0

def resolve_shp():
    for p in SHP_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("找不到村里界 SHP：" + "、".join(SHP_CANDIDATE_PATHS))

# ===================== 文字圖片生成（仿 Print_word.py） =====================
DEFAULT_FONT_CHAIN = ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]
_FONT_FAMILY_CACHE = {}

def resolve_font_family(font=None):
    """回傳 matplotlib fontfamily 清單：取第一個可用的中文字型，再串 DejaVu Sans 補符號。

    font  None  → 走 DEFAULT_FONT_CHAIN（標題、圖例用）
          str   → 指定字型名（如 "GenSekiGothic TW H"）；找不到就報錯，不靜默換字型
          list  → 自訂回退順序
    """
    from matplotlib import font_manager
    if font is None:
        chain = tuple(DEFAULT_FONT_CHAIN)
    elif isinstance(font, (list, tuple)):
        chain = tuple(font)
    else:
        chain = (font,)
    if chain not in _FONT_FAMILY_CACHE:
        names = {f.name for f in font_manager.fontManager.ttflist}
        hit = next((n for n in chain if n in names), None)
        if hit is None and font is not None:
            raise ValueError(f"找不到字型 {font}；已安裝字型可用 font_manager 查詢")
        _FONT_FAMILY_CACHE[chain] = [hit, "DejaVu Sans"] if hit else ["DejaVu Sans"]
    return _FONT_FAMILY_CACHE[chain]

def _mcolor(color):
    """0–255 的 RGB tuple → matplotlib 要的 0–1 float tuple；色名字串原樣傳回。"""
    if isinstance(color, str):
        return color
    return tuple(c / 255.0 for c in color)

def _draw_text_rgb(text_lines, font_size, dpi, font_family,
                   bg, ink, halo=None, halo_w=0.0, line_ratio=1.5, pad=20):
    """在純色底上以 matplotlib 繪製多行文字（逐行量測後置中），回傳 PIL RGB 影像。

    bg / ink / halo 皆為 0–255 的 RGB tuple（或色名字串）。
    line_ratio  行距／字級；pad 畫布四周留白(px)。
    """
    bg, ink = _mcolor(bg), _mcolor(ink)
    effects = None
    if halo and halo_w > 0:
        from matplotlib import patheffects
        effects = [patheffects.withStroke(linewidth=halo_w, foreground=_mcolor(halo))]

    # 測量文字尺寸
    fig_temp = plt.figure(figsize=(1, 1), dpi=dpi)
    ax_temp = fig_temp.add_subplot(111)
    ax_temp.axis("off")
    fig_temp.canvas.draw()
    renderer = fig_temp.canvas.get_renderer()
    line_widths = []
    line_heights = []
    for line in text_lines:
        t = ax_temp.text(0, 0, line, fontsize=font_size, fontfamily=font_family)
        bbox = t.get_window_extent(renderer=renderer)
        line_widths.append(bbox.width)
        line_heights.append(bbox.height)
    plt.close(fig_temp)

    line_spacing = font_size * line_ratio
    total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing
    max_width = max(line_widths)
    fig_w_pt = max_width + 2 * pad
    fig_h_pt = total_height + 2 * pad

    fig = plt.figure(figsize=(fig_w_pt / dpi, fig_h_pt / dpi), dpi=dpi, facecolor=bg)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w_pt)
    ax.set_ylim(0, fig_h_pt)
    ax.set_facecolor(bg)
    ax.axis("off")

    y = pad + total_height
    for i, line in enumerate(text_lines):
        x = (fig_w_pt - line_widths[i]) / 2
        y -= line_heights[i]
        ax.text(x, y, line, fontsize=font_size, ha="left", va="bottom",
                fontfamily=font_family, color=ink, path_effects=effects)
        y -= line_spacing

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, facecolor=bg, pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    arr_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    return Image.fromarray(cv2.cvtColor(arr_bgr, cv2.COLOR_BGR2RGB))

def render_text_image(text_lines, font_size=64, dpi=100, font=None,
                      text_color="black", halo_color=None, halo_width=0.0,
                      line_ratio=1.5, pad=20):
    """以 Print_word.py 方式：Matplotlib 繪字 → OpenCV 二值化 → 透明背景。

    回傳 PIL RGBA（文字不透明、背景透明），可直接 paste 到地圖。
    font         指定字型名；None 走預設中文字型鏈
    text_color   文字顏色
    halo_color   描邊顏色；配合 halo_width > 0 產生「深色字 + 淺色描邊」，
                 疊在深色填色上仍可讀（描邊以兩趟渲染合成：黑底白墨取 alpha 遮罩）
    line_ratio   行距／字級（預設 1.5）；pad 畫布四周留白(px)
    """
    font_family = resolve_font_family(font)

    if halo_color and halo_width > 0:
        mask = _draw_text_rgb(text_lines, font_size, dpi, font_family,
                              (0, 0, 0), (255, 255, 255), (255, 255, 255), halo_width,
                              line_ratio, pad)
        fill = _draw_text_rgb(text_lines, font_size, dpi, font_family,
                              halo_color, text_color, halo_color, halo_width,
                              line_ratio, pad)
        rgb = np.array(fill)
        alpha = np.array(mask)[:, :, 0]          # 黑底白墨 → 灰階即 alpha
        return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")

    img = _draw_text_rgb(text_lines, font_size, dpi, font_family, (255, 255, 255), (0, 0, 0),
                         line_ratio=line_ratio, pad=pad)
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    _, bin_img = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    h, w = bin_img.shape
    result = np.zeros((h, w, 4), dtype=np.uint8)   # B,G,R = 0（黑字）
    tc = str(text_color).lower()
    if tc not in ("black", "#000000", "k"):        # 支援白字／其他顏色（晶片標註用）
        if tc in ("white", "#ffffff", "w"):
            bgr = (255, 255, 255)
        elif tc.startswith("#") and len(tc) >= 7:
            bgr = (int(tc[5:7], 16), int(tc[3:5], 16), int(tc[1:3], 16))
        else:
            bgr = (0, 0, 0)
        result[:, :, 0], result[:, :, 1], result[:, :, 2] = bgr
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))

_TEXT_IMG_CACHE = {}

def render_text_image_cached(text_lines, font_size, font=None,
                             text_color="black", halo_color=None, halo_width=0.0,
                             line_ratio=1.5, pad=20):
    """快取版 render_text_image：相同文字／字級／字型／配色只渲染一次。"""
    key = (tuple(text_lines), font_size, font, text_color, halo_color, halo_width,
           line_ratio, pad)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(
            text_lines, font_size=font_size, font=font, text_color=text_color,
            halo_color=halo_color, halo_width=halo_width, line_ratio=line_ratio, pad=pad)
    return _TEXT_IMG_CACHE[key]

def blit_rgba(base_img, rgba_img, xy):
    """將透明底 RGBA 文字圖以 alpha 為遮罩貼到 base_img 的 (x, y)。"""
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))

_TOWN_LABEL_CACHE = {}
_TOWN_FONT_CACHE = {}

def _town_font(size):
    """載入標註字型（GenSekiGothic TW H），依字級快取。"""
    if size not in _TOWN_FONT_CACHE:
        try:
            _TOWN_FONT_CACHE[size] = ImageFont.truetype(TOWN_LABEL_FONT_PATH, size)
        except OSError:
            _TOWN_FONT_CACHE[size] = ImageFont.truetype(TOWN_LABEL_FONT_FALLBACK, size)
    return _TOWN_FONT_CACHE[size]

def render_town_label(name, rate_txt, box_hex, st):
    """區名 ＋ 領先者得票率 的兩行式標註（比照參考圖樣式）。

    第一行：區名，黑色文字，**不加底色框**，僅加極細白色描邊
            （白底上看不出來，壓到深色填色區仍可讀）。
    第二行：得票率，黑色文字 ＋ 候選人代表色底框 ＋ 黑色描邊。

    回傳 (RGBA 影像, 色塊在本影像內的 rect)。
    呼叫端以「整張影像的 rect」作為避讓範圍、以「色塊 rect」作為視覺重心參考。
    """
    key = (name, rate_txt, box_hex, st["S"])
    if key in _TOWN_LABEL_CACHE:
        return _TOWN_LABEL_CACHE[key]

    name_font = _town_font(st["name_font"])
    rate_font = _town_font(st["rate_font"])
    draw_tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    nw = draw_tmp.textlength(name, font=name_font)
    rw = draw_tmp.textlength(rate_txt, font=rate_font)

    def _text_h(font):
        asc, desc = font.getmetrics()
        return asc + desc

    nh, rh = _text_h(name_font), _text_h(rate_font)
    pad = int(np.ceil(st["name_halo"])) + 1          # 讓描邊不被裁掉

    block_w = int(round(max(rw + 2 * st["rate_pad_x"], nw))) + 2 * pad
    box_w = int(round(rw + 2 * st["rate_pad_x"]))
    box_h = int(round(rh + 2 * st["rate_pad_y"]))
    W_ = block_w
    H_ = nh + st["name_gap"] + box_h + 2 * pad

    img = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- 第一行：區名（黑字 + 白描邊，無底色）----
    d.text(((W_ - nw) / 2, pad), name, font=name_font, fill=(0, 0, 0),
           stroke_width=int(round(st["name_halo"])), stroke_fill=(255, 255, 255))

    # ---- 第二行：得票率色塊 ----
    bx0 = (W_ - box_w) / 2
    by0 = pad + nh + st["name_gap"]
    d.rectangle([bx0, by0, bx0 + box_w - 1, by0 + box_h - 1],
                fill=box_hex, outline=(0, 0, 0), width=st["label_border"])
    d.text((bx0 + (box_w - rw) / 2, by0 + st["rate_pad_y"]),
           rate_txt, font=rate_font, fill=(0, 0, 0))

    rect = (bx0, by0, bx0 + box_w, by0 + box_h)
    _TOWN_LABEL_CACHE[key] = (img, rect)
    return img, rect

# ===================== 读 SHP =====================
SHP_PATH = resolve_shp()
gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
if gdf_all.crs.is_geographic:
    gdf_all = gdf_all.to_crs(epsg=3826)

for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]:
    if c not in gdf_all.columns:
        raise ValueError(f"SHP缺失必要字段：{c}")

# ===================== 读取高雄格式得票 Excel，计算得票率 =====================
def _norm_text(v):
    """正規化：NaN / 'nan'(不區分大小寫) 一律視為空字串（缺失）。"""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s

def load_rates(cfg):
    excel_path = cfg["excel"]
    df = pd.read_excel(excel_path, sheet_name=cfg["sheet"], header=cfg.get("header", 0))
    df.columns = [str(c) for c in df.columns]

    # 模式 ④：地名在單列完整路徑（如「臺北縣板橋市留侯里」），得票率為小數
    if cfg.get("loc_col") is not None and (cfg.get("rate_col") is not None or cfg.get("rate_cols")):
        loc_idx = str(cfg["loc_col"])
        rate_mult = cfg.get("rate_multiplier", 100)
        cand_names = cfg.get("legend_names", [""])
        rc_list = cfg.get("rate_cols") or [cfg["rate_col"]]
        rnames = []
        for i, rc in enumerate(rc_list):
            rname = f"rate_{cand_names[i]}" if i < len(cand_names) else f"rate{i + 1}"
            rnames.append(rname)
            df[rname] = pd.to_numeric(df[str(rc)], errors="coerce") * rate_mult

        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.+)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""

        parsed = df[loc_idx].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_names, rnames

    # 支援三種來源（原有邏輯）：
    #  ① 得票率專用檔：欄位直接是「<政黨>得票率」
    #  ② 高雄格式全量檔：<候選人>得票數 ＋ 有效票數A，再除以 A×100 得得票率
    #  ③ 指定候選人欄位（cfg["cand_columns"]）：欄名即候選人、值為得票率(%)
    #  ⑤ 鄉鎮市區層級檔（cfg["full_loc_col"]）：單一欄含完整路徑（如「臺北縣板橋市」），無村里資料
    pct_cols = [c for c in df.columns if c.endswith("得票率")]
    vote_cols = [c for c in df.columns if c.endswith("得票數")]
    given_cands = cfg.get("cand_columns")

    # 字串百分比（如 "51.54%"）→ 數值
    def _to_pct_numeric(v):
        if v is None:
            return np.nan
        s = str(v).strip()
        if s.endswith("%"):
            s = s[:-1]
        return pd.to_numeric(s, errors="coerce")

    if cfg.get("full_loc_col"):
        cand_cols = list(cfg.get("cand_columns") or pct_cols or vote_cols)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = df[c].apply(_to_pct_numeric)
        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.*)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""
        parsed = df[cfg["full_loc_col"]].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_cols, rate_cols

    if given_cands:
        cand_cols = list(given_cands)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    elif pct_cols:
        cand_cols = pct_cols
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    elif vote_cols:
        if "有效票數A" not in df.columns:
            raise ValueError(f"{excel_path} 缺少『有效票數A』欄位")
        cand_cols = vote_cols
        A = pd.to_numeric(df["有效票數A"], errors="coerce")
        rate_cols = []
        for i, c0 in enumerate(cand_cols):
            rname = f"rate{i + 1}"
            rate_cols.append(rname)
            df[rname] = pd.to_numeric(df[c0], errors="coerce") / A * 100.0
    else:
        raise ValueError(f"{excel_path} 找不到『得票率』或『得票數』欄位")

    df["縣市"] = df[cfg.get("col_city", "選舉區別")].apply(_norm_text)
    df["鄉鎮市區"] = df[cfg.get("col_town", "鄉(鎮、市、區)別")].apply(_norm_text)
    df["區里"] = df[cfg.get("col_vill", "村里別")].apply(_norm_text)

    df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
    df["vill_core"] = df["區里"].apply(strip_village_suffix)
    return df, cand_cols, rate_cols

# ===================== 精确 + 同乡镇最相似模糊匹配 =====================
MIN_SIMILARITY = 0.5

def _char_pairs(a, b):
    """回傳逐字對應 (a字, b字)；長度不同時補上長度差異標記。"""
    pairs = []
    la, lb = len(a), len(b)
    if la != lb:
        return None  # 長度不同：不視為異體字匹配
    for ca, cb in zip(a, b):
        pairs.append((ca, cb))
    return pairs

# 異體字模糊匹配表（模糊候選彼此間「單字異體」的許可字對）
# 格式：同一組內的字互為異體；用於 fuzzy（相似度≥50% 且逐字僅一案異體）
VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"},   # 瑞芳區爪峯/爪峰
    {"舘", "館"},   # 板橋區公舘/公館、三峽區永舘/永館
    {"磘", "窯"},   # 中和區瓦磘/瓦窯
    {"獇", "羌"},   # 樹林區獇寮/羌寮
    {"曹", "槽"},   # 坪林區石曹/石槽
    {"脚", "腳"},
]


def is_variant_fuzzy(a, b):
    """判斷兩個（core）里名是否屬『異體字模糊匹配』：
    相似度 ≥ MIN_SIMILARITY，且逐字比較中『最多一個字不相等，且該字對落在異體字組』。
    """
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False  # 長度不同（字數差）不視為異體字模糊
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    for group in VARIANT_FUZZY_GROUPS:
        if ca in group and cb in group:
            return True
    return False

def fuzzy_lookup(town, vill, by_key, by_town):
    if not town or not vill:
        return None, None, "none"
    key = (town, vill)
    if key in by_key:
        return vill, by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get(town, []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, None, "none"
    # 只有逐字差異恰好一個字且該字對屬異體字組，才接受模糊匹配；
    # 其餘「雖然相似度達 50% 但並非異體字」的情形，視為無資料（白底）。
    if not is_variant_fuzzy(vill, best_v):
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"

# ===================== 逐張地圖繪製 =====================
def draw_legend_on(final_img, g, x0, y0, cand_names, stops_list, start_tier=0):
    """圖例：色塊用 ImageDraw 繪製；所有文字以 Print_word.py 方式（render_text_image）貼上。

    尺寸全部取自 g（build_scale 的輸出）；版面與 Converge_to_map1.py 完全一致。
    """
    draw_obj = ImageDraw.Draw(final_img)
    block_w, block_h = g["block_w"], g["block_h"]
    pad_txt = SWATCH_TEXT_GAP                        # 色塊與右側數值文字的間距
    n = len(cand_names)
    col_width = block_w + pad_txt + g["max_label_w"]
    col_positions = [x0 + i * (col_width + g["h_spacing"]) for i in range(n)]
    name_h = max(
        (render_text_image_cached([nm], g["cand_name_font"]).height for nm in cand_names),
        default=0,
    )
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_text_image_cached([cand_names[col_idx]], g["cand_name_font"])
            blit_rgba(final_img, nm_img, (x_start + (block_w - nm_img.width) / 2, y0))
        for i, (upper, color_hex) in enumerate(stops):
            y = y0 + name_h + g["column_title_gap"] + i * (block_h + g["v_spacing"])
            draw_obj.rectangle(
                [x_start, y, x_start + block_w, y + block_h],
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                g["legend_label_font"])
            blit_rgba(final_img, limg, (x_start + block_w + pad_txt,
                                        y + (block_h - limg.height) / 2))

def get_label_text(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"

# ===================== 鄉鎮市區標註（區名 + 領先者得票率）=====================
def compute_town_rates(df_vote, rate_cols, town_level_dict, town_level_only):
    """彙總各鄉鎮市區的候選人得票率。

    得票率必須「得票數加總 ÷ 有效票數加總」重算（人口加權）——直接平均村里得票率
    會讓幾百人的小里與上萬人的大里等權而扭曲區級結果。但多數原始檔只給得票率、
    沒有得票數，此時退為村里得票率平均（近似值，僅供標註用）。
    回傳 (rates_by_town, mode)；mode = town / weighted / mean。
    """
    valid_col = next((c for c in df_vote.columns if str(c).startswith("有效票數")), None)
    vote_cols = [c for c in df_vote.columns if str(c).endswith("得票數")]

    mode = TOWN_RATE_MODE
    if mode == "auto":
        if town_level_only:
            mode = "town"
        elif valid_col and len(vote_cols) == len(rate_cols):
            mode = "weighted"
        else:
            mode = "mean"

    if mode == "town":
        rates = {t: list(v) for t, v in town_level_dict.items()}
    elif mode == "weighted":
        num = df_vote[vote_cols].apply(pd.to_numeric, errors="coerce")
        den = pd.to_numeric(df_vote[valid_col], errors="coerce").rename("__den__")
        g = pd.concat([num, den], axis=1).groupby(df_vote["town_core"], sort=False).sum(min_count=1)
        rates = {}
        for t, row in g.iterrows():
            d = row["__den__"]
            ok = pd.notna(d) and d > 0
            rates[t] = [row[v] / d * 100.0 if ok else np.nan for v in vote_cols]
    else:
        g = df_vote.groupby("town_core", sort=False)[rate_cols].mean()
        rates = {t: [row[c] for c in rate_cols] for t, row in g.iterrows()}
    return rates, mode

def _box(cx, cy, w, h):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

def _xy_maps(xlim, ylim, w_px, h_px, y_off, mpp):
    """回傳 (投影座標→像素, 像素→投影座標) 兩個互為反函式的轉換。

    像素 y 軸向下、投影 y 軸向北（TWD97 y 越大越北）。matplotlib 以
    set_ylim(ylim[0], ylim[1]) 繪製幾何時北在上，故像素 y 必須由 ylim[1]
    （北界）起算向下遞增；先前誤由 ylim[0]（南界）起算，等於把所有標註
    南北鏡像——烏來標到北海岸、金山標到南端，引線也全部指錯位置。
    兩者共用同一組參數寫在同一處，避免正反轉換各自推導而翻軸。
    """
    def to_px(x, y):
        return (x - xlim[0]) / mpp, y_off + (ylim[1] - y) / mpp

    def to_map(px, py):
        return (xlim[0] + px * mpp, ylim[1] - (py - y_off) * mpp)

    return to_px, to_map

def _box_edge_point(cx, cy, tx, ty, w, h):
    """由標註中心朝 (tx,ty) 射出，取撞到標註外框的點作為引線起點。"""
    hw, hh = w / 2, h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = hw / abs(dx) if dx else np.inf
    sy = hh / abs(dy) if dy else np.inf
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s

def _seg_cross(p1, q1, p2, q2):
    """兩線段是否相交（嚴格交叉；共線重疊視為相交，端點相觸不算）。"""
    def ori(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2 = ori(p1, q1, p2), ori(p1, q1, q2)
    o3, o4 = ori(p2, q2, p1), ori(p2, q2, q1)
    if o1 != o2 and o3 != o4:
        return True
    # 共線時若投影區間重疊也算交叉
    if o1 == o2 == o3 == o4 == 0:
        def on(a, b, c):
            return (min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
                    and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9)
        return on(p1, q1, p2) or on(p1, q1, q2) or on(p2, q2, p1) or on(p2, q2, q1)
    return False

def _seg_hits_box(p, q, box, slack=2.0, step=4.0):
    """線段 p→q 是否壓到 box（沿線取樣即可，夠用且便宜）。"""
    length = ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5
    n = max(int(length / step), 1)
    for i in range(n + 1):
        t = i / n
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        if box[0] - slack <= x <= box[2] + slack and box[1] - slack <= y <= box[3] + slack:
            return True
    return False

def _rect_overlap_frac(a, b):
    """矩形 a 被 b 覆蓋的面積比例。"""
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    return (ix * iy) / max((a[2] - a[0]) * (a[3] - a[1]), 1e-9)

def _integral_img(mask):
    """二值遮罩的積分圖：可 O(1) 查詢任意矩形內的佔用像素數。"""
    ii = np.cumsum(np.cumsum(mask.astype(np.int32), axis=0), axis=1)
    return np.pad(ii, ((1, 0), (1, 0)), mode="constant")


# ===================== 標註佈局：見縫插針 =====================
def plan_town_labels(gdf_plot, town_rates, xlim, ylim, w_px, h_px, st,
                     free_mask, box_colors, line_mask=None):
    """為每個鄉鎮市區決定標註落點（座標一律為「地圖畫布內部」像素，y 向下）。

    策略完全比照參考圖 —— 不再「全畫布網格掃描 + 一律推左」：
      1. 先把底圖渲染出來，取「白色像素」＝可用空白（含無資料白色村里、
         台北市空缺、海岸外留白）。標註要放在白的地方。
      2. 硬性淨空：候選落點矩形外擴 LABEL_LINE_CLEAR_PX 後，
         不得碰到任何界線像素（界線遮罩＝純黑像素）→ 標註絕不壓在界線上。
      3. 對每個區，以區中心（多邊形最大內接圓心）為圓心往外做「環狀取樣」，
         得到數千個候選落點。
      4. 候選成本 = 壓到非白色填色的比例 × 一個形體寬 + 引線長度。
         因此天然會「見縫插針」：三重、板橋、中和的標註會自動落進台北市
         空缺，林口、八里、泰山會落在西側海岸留白，烏來、坪溪會落在山區
         白點——與參考圖一致。
      5. 落位順序：面積小者優先（密集區先搶白區），逐區挑「總成本最低」者。
      6. MANUAL_LABEL_POS 內指定的區一律優先落位（演算法不會動它）。
    """
    from shapely.ops import transform as shp_transform, polylabel
    import shapely

    display_of = (gdf_plot.drop_duplicates("town_core")
                            .set_index("town_core")["TOWNNAME"].to_dict())
    src = gdf_plot[gdf_plot["town_core"].str.strip() != ""]
    gdf_town = src.dissolve(by="town_core").reset_index()
    gdf_town["area_km2"] = gdf_town.geometry.area / 1e6

    mpp = METERS_PER_PIXEL
    W, H = int(w_px), int(h_px)
    margin = LABEL_MARGIN_PX * st["S"]
    x0m, y1m = xlim[0], ylim[1]

    def _tf(x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        return (x - x0m) / mpp, (y1m - y) / mpp

    # 非白＝被地圖填色／界線佔用 → 標註應盡量避開
    occupied = ~free_mask
    ii = _integral_img(occupied)

    # 界線專用積分圖：候選落點外擴淨空值後不得碰到任何界線像素（硬性條件）
    ii_line = _integral_img(line_mask) if line_mask is not None else None

    # 成本權重：嚴格禁止「壓色 + 重疊 + 引線交叉」三種失敗。
    # 先前 W_OCC=0.4/W_OVER=2.5/W_CROSS=0.35 → 演算法寧可壓色也不願找白區，
    # 板橋標籤直接糊在深綠填色上。值大幅提高後，壓色/重疊/交叉都變成不可接受的代價，
    # 演算法會把密集區標籤「流放」到台北市空缺或海域的白區。
    W_OCC   = 2.0  * W   # 壓在塗色區上的成本（原 0.4 → 2.0）
    W_OVER  = 20.0 * W   # 與其它標註重疊的成本（原 2.5 → 20.0，重疊變成致命傷）
    W_CROSS = 5.0  * W   # 引線交叉／穿框的成本（原 0.35 → 5.0）
    # 碰到界線（村里線／區界／外輪廓）的成本：高到「除非該區真的找不到
    # 任何不碰界線的落點，否則絕不選它」，藉此達成「標註不碰到邊界線」。
    W_LINE  = 10.0 * W

    jobs = []
    for _, r in gdf_town.iterrows():
        core = r["town_core"]
        vals = town_rates.get(core)
        if not vals:
            continue
        vals = [np.nan if v is None or pd.isna(v) else float(v) for v in vals]
        if all(np.isnan(v) for v in vals):
            continue
        lead = int(np.nanargmax(vals))
        geom = r.geometry
        name = str(display_of.get(core, core))
        box_hex = box_colors.get(lead, "#004B6B")
        img, box_rect = render_town_label(name, f"{vals[lead]:.1f}%", box_hex, st)
        poly_px = shp_transform(_tf, geom)
        jobs.append(dict(core=core, name=name, geom=geom, poly=poly_px,
                         img=img, box_rect=box_rect,
                         km2=float(r["area_km2"]), lead=lead,
                         how="manual" if core in MANUAL_LABEL_POS else "auto",
                         crowded=False, cx=0.0, cy=0.0, leader=None,
                         cands=[], base=0.0))

    if not jobs:
        return jobs

    # ---------- 產生候選落點 ----------
    for j in jobs:
        img = j["img"]
        bw, bh = img.width, img.height
        bxr = j["box_rect"]                 # 得票率色塊在標註影像中的位置
        name_band = float(bxr[1])           # 區名帶（影像上緣到色塊上緣）
        poly = j["poly"]
        bpts = shapely.get_coordinates(poly.boundary)
        if len(bpts) > 400:                  # 邊界點抽稀，維持向量化成本
            bpts = bpts[:: max(1, len(bpts) // 400)]

        # 「區域中間」＝多邊形最大內接圓心（polylabel）。引線一律指向這裡。
        ctr = polylabel(poly, tolerance=max(1.0, 0.006 * W))
        cc = np.array([ctr.x, ctr.y], dtype=float)
        anchor = (float(ctr.x), float(ctr.y))
        j["anchor"] = anchor

        d2c = (np.hypot(bpts[:, 0] - cc[0], bpts[:, 1] - cc[1])
               if len(bpts) else np.array([50.0]))
        rext = float(d2c.max())

        r0 = max(rext * 0.30, 0.42 * float(np.hypot(bw, bh)))
        # 小面積密集區（三重/板橋/中和/永和/新莊/土城）本地沒有足夠白區，
        # 把搜尋上半徑放到 1.1×min(W,H) → 涵蓋整個畫布（海域/台北市空缺）。
        big = 1.10 * min(W, H)
        rmax = float(min(max(3.4 * rext, 0.56 * big), big))
        radii = np.geomspace(r0, max(rmax, r0 * 1.05), LABEL_RING_RADII)
        angs = np.deg2rad(np.arange(LABEL_RING_ANGLES) * (360.0 / LABEL_RING_ANGLES))
        cx = np.concatenate([[cc[0]], (cc[0] + np.outer(radii, np.cos(angs))).ravel()])
        cy = np.concatenate([[cc[1]], (cc[1] + np.outer(radii, np.sin(angs))).ravel()])

        bx0, bx1 = cx - bw / 2.0, cx + bw / 2.0
        by0, by1 = cy - bh / 2.0, cy + bh / 2.0
        inside = ((bx0 >= margin) & (bx1 <= W - margin)
                  & (by0 >= margin) & (by1 <= H - margin))

        def _occ(x0, y0, x1, y1):
            xi0 = np.clip(np.floor(x0), 0, W).astype(np.int64)
            xi1 = np.clip(np.ceil(x1), 0, W).astype(np.int64)
            yi0 = np.clip(np.floor(y0), 0, H).astype(np.int64)
            yi1 = np.clip(np.ceil(y1), 0, H).astype(np.int64)
            ar = np.maximum((xi1 - xi0) * (yi1 - yi0), 1).astype(float)
            ss = ii[yi1, xi1] - ii[yi0, xi1] - ii[yi1, xi0] + ii[yi0, xi0]
            return ss / ar

        def _line_hits(x0, y0, x1, y1):
            """矩形（外擴淨空值）內的界線像素數；0 表示與界線完全無接觸。"""
            if ii_line is None:
                return np.zeros_like(np.asarray(x0, dtype=float))
            c = LABEL_LINE_CLEAR_PX
            xi0 = np.clip(np.floor(x0 - c), 0, W).astype(np.int64)
            xi1 = np.clip(np.ceil(x1 + c), 0, W).astype(np.int64)
            yi0 = np.clip(np.floor(y0 - c), 0, H).astype(np.int64)
            yi1 = np.clip(np.ceil(y1 + c), 0, H).astype(np.int64)
            return (ii_line[yi1, xi1] - ii_line[yi0, xi1]
                    - ii_line[yi1, xi0] + ii_line[yi0, xi0])

        # 得票率色塊是不透明底 → 壓到填色就整塊遮住地圖，權重 1.0；
        # 區名行只有文字本身（底透明、且已加白色描邊）→ 壓到填色幾乎無害，權重 0.12。
        occ = (_occ(bx0 + bxr[0], by0 + bxr[1], bx0 + bxr[2], by0 + bxr[3])
               + 0.12 * _occ(bx0, by0, bx1, by0 + name_band))
        occ = np.where(inside, occ, 3.0)

        dmat = np.hypot(cx[:, None] - bpts[None, :, 0], cy[:, None] - bpts[None, :, 1])
        dmin = dmat.min(axis=1)
        d_eff = np.where(shapely.contains_xy(poly, cx, cy), 0.0, dmin)
        # 距離項：形體寬 6% 內為線性，超過後「加重」懲罰 → 讓標註盡量貼著自己的區，
        # 引線短、不橫貫全圖（與參考圖「標註貼在海岸/空隙邊緣」的做法一致）。
        cost = (W_OCC * occ + d_eff
                + 3.0 * np.maximum(d_eff - 0.06 * W, 0.0))

        half = max(bw, bh) / 2.0
        lhit = _line_hits(bx0, by0, bx1, by1)      # 每個候選碰到的界線像素數
        cands = []
        for k in range(len(cx)):
            if not inside[k] or cost[k] >= W_OVER:
                continue
            seg = None
            if (d_eff[k] - half) > st["leader_min_gap"]:
                sx, sy = _box_edge_point(cx[k], cy[k], anchor[0], anchor[1], bw, bh)
                seg = ((float(sx), float(sy)), anchor)
            cands.append(dict(cx=float(cx[k]), cy=float(cy[k]),
                              rect=(float(bx0[k]), float(by0[k]),
                                    float(bx1[k]), float(by1[k])),
                              leader=seg, base=float(cost[k]),
                              lhit=int(lhit[k])))

        # 不碰界線的候選排前面；同一組內再比成本
        cands.sort(key=lambda t: (t["lhit"] > 0, t["base"]))
        keep = []
        min_sep = 0.30 * min(bw, bh)
        for cd in cands:
            if all(np.hypot(cd["cx"] - o["cx"], cd["cy"] - o["cy"]) >= min_sep for o in keep):
                keep.append(cd)
            if len(keep) >= LABEL_KEEP_CAND:
                break

        if not keep:      # 保底：至少要有「區域中間」這個落點，否則貪心無法落位
            fx = float(np.clip(cc[0], margin + bw / 2, max(margin + bw / 2, W - margin - bw / 2)))
            fy = float(np.clip(cc[1], margin + bh / 2, max(margin + bh / 2, H - margin - bh / 2)))
            keep = [dict(cx=fx, cy=fy, rect=_box(fx, fy, bw, bh), leader=None, base=W_OVER)]

        for cd in keep:                      # 預先算好引線的 AABB，供便宜排除
            seg = cd["leader"]
            cd["sbbox"] = ((0.0, 0.0, -1.0, -1.0) if seg is None else
                           (min(seg[0][0], seg[1][0]), min(seg[0][1], seg[1][1]),
                            max(seg[0][0], seg[1][0]), max(seg[0][1], seg[1][1])))
        j["cands"] = keep
        j["base"] = keep[0]["base"]

    # ---------- 手工指定落點優先落位 ----------
    def _apply(j, cd):
        j["cx"], j["cy"] = cd["cx"], cd["cy"]
        j["leader"] = cd["leader"]
        j["base"] = cd["base"]
        j["lhit"] = int(cd.get("lhit", 0))       # 落點矩形碰到的界線像素數
        return dict(rect=cd["rect"], leader=cd["leader"], core=j["core"])

    placed = []
    remaining = []
    for j in jobs:
        if j["core"] in MANUAL_LABEL_POS:
            mx, my = MANUAL_LABEL_POS[j["core"]]
            px, py = _tf(mx, my)
            px, py = float(px), float(py)
            img = j["img"]
            bw, bh = img.width, img.height
            ax, ay = j["anchor"]
            seg = None
            if j["poly"].distance(Point(px, py)) - max(bw, bh) / 2.0 > st["leader_min_gap"]:
                sx, sy = _box_edge_point(px, py, ax, ay, bw, bh)
                seg = ((sx, sy), (ax, ay))
            cd = dict(cx=px, cy=py, rect=_box(px, py, bw, bh), leader=seg, base=-1.0)
            j["entry"] = _apply(j, cd)
            j["final_cost"] = -1.0
            placed.append(j["entry"])
        else:
            remaining.append(j)

    # ---------- 全域貪心：每次落「總成本最低」的一組 ----------
    def _penalty(cd):
        ov = 0.0
        cross = 0
        r = cd["rect"]
        seg = cd["leader"]
        sb = cd["sbbox"]
        for p in placed:
            ov += _rect_overlap_frac(r, p["rect"])
            if ov > 0.85:
                return ov, cross
            if seg is not None:
                pl = p["leader"]
                if pl is not None and _seg_cross(seg[0], seg[1], pl[0], pl[1]):
                    cross += 1
                pr = p["rect"]
                # 先做便宜的 AABB 排除，只有真的可能穿框才沿線取樣
                if sb[0] <= pr[2] and sb[2] >= pr[0] and sb[1] <= pr[3] and sb[3] >= pr[1]:
                    if _seg_hits_box(seg[0], seg[1], pr, slack=2.0):
                        cross += 1
        return ov, cross

    # ---------- 全域貪心：按「面積小者優先」落位 ----------
    # 密集小區（三重/板橋/中和/永和）本地沒白區，必須先讓它們搶到海域/台北市空缺；
    # 大面積外圍區（烏來/坪林/雙溪）周邊全白，最後放也無妨。按 km2 升序，
    # 加上每個 candidate 總成本最低者落位。
    remaining.sort(key=lambda j: j["km2"])

    # **改貪心為「逐區落位」**：面積小的區先放，先挑「當下總成本最低」的候選，
    # 不再每次全域搜尋。這樣密集區被先放時，先佔住海域白區；後放的大區不會被它們擠掉。
    for j in remaining:
        img = j["img"]
        bw_j, bh_j = img.width, img.height
        best = None
        for cd in j["cands"]:
            ov, cross = _penalty(cd)
            c = (cd["base"] + W_OVER * ov + W_CROSS * cross
                 + (W_LINE if cd.get("lhit", 0) > 0 else 0.0))
            if best is None or c < best[0]:
                best = (c, cd, ov)
        if best is None or best[0] >= W_OVER + W_OVER:   # 沒有可接受候選
            cd = dict(cx=w_px / 2, cy=h_px / 2,
                      rect=_box(w_px / 2, h_px / 2, img.width, img.height),
                      leader=None, base=W_OVER)
            j["crowded"] = True
            j["final_cost"] = W_OVER + W_OVER
            j["entry"] = _apply(j, cd)
            placed.append(j["entry"])
            continue
        c, cd, ov = best
        j["crowded"] = ov > 0.05
        j["final_cost"] = c
        j["entry"] = _apply(j, cd)
        placed.append(j["entry"])

    # ---------- 局部改良：反覆讓「目前成本最差」的區重挑落點 ----------
    # 貪心是單向的，先落位者可能佔走了別人更好的位置；這裡做數輪「移除→重挑」，
    # 讓落點整體收斂（實測可明顯縮短引線、消掉邊緣區的互相擠壓）。
    movable = [j for j in jobs if j["how"] != "manual"]
    for _ in range(15):
        improved = False
        for j in sorted(movable, key=lambda t: -t.get("final_cost", 0.0)):
            ent = j.get("entry")
            if ent is not None and ent in placed:
                placed.remove(ent)
            best = None
            for cd in j["cands"]:
                ov, cross = _penalty(cd)
                c = (cd["base"] + W_OVER * ov + W_CROSS * cross
                     + (W_LINE if cd.get("lhit", 0) > 0 else 0.0))
                if best is None or c < best[0]:
                    best = (c, cd, ov)
            if best is None:
                if ent is not None:
                    placed.append(ent)
                continue
            if best[0] < j.get("final_cost", np.inf) - 0.5:
                improved = True
            j["final_cost"] = best[0]
            j["crowded"] = best[2] > 0.18
            j["entry"] = _apply(j, best[1])
            placed.append(j["entry"])
        if not improved:
            break

    if os.environ.get("LABEL_DEBUG"):
        print("  【候選落點除錯】")
        for j in sorted(jobs, key=lambda t: -t.get("final_cost", 0.0))[:12]:
            top = ", ".join(f"({cd['cx']:.0f},{cd['cy']:.0f}|{cd['base']:.0f})"
                            for cd in j["cands"][:4])
            print(f"      {j['name']:<5} 最終 ({j['cx']:.0f},{j['cy']:.0f})"
                  f" cost={j.get('final_cost', 0):.0f}  最佳候選: {top}")

    return jobs


def draw_town_labels(final_img, jobs, y_off, st):
    """把標註疊到完成圖上。

    兩趟繪製：先畫全部引線（白色襯線 + 黑線），再貼全部標註；
    否則後貼的標註會蓋掉先畫的引線。引線與標註框都比對參考圖的
    粗細（由 st 依 S 推得）。
    """
    draw_obj = ImageDraw.Draw(final_img)
    order = sorted(jobs, key=lambda t: t["img"].height, reverse=True)

    for j in order:
        seg = j["leader"]
        if not seg:
            continue
        (sx, sy), (ex, ey) = seg
        p = (sx, sy + y_off)
        q = (ex, ey + y_off)
        draw_obj.line([p, q], fill=(255, 255, 255),
                      width=st["leader_w"] + 2 * st["leader_casing"])
        draw_obj.line([p, q], fill=(0, 0, 0), width=st["leader_w"])

    for j in order:
        img = j["img"]
        blit_rgba(final_img, img,
                  (j["cx"] - img.width / 2, j["cy"] + y_off - img.height / 2))

def make_map(cfg):
    print("=" * 62)
    print(f"  組別：{cfg['tag']}")
    print("=" * 62)

    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(cfg["city"], na=False)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"SHP 中未找到 {cfg['city']} 數據")

    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols = load_rates(cfg)
    # 納入 {city} 資料；縣市欄缺失(NaN / 'nan' 不區分大小寫)者視為同屬該縣市，一併納入
    # Excel 中的縣市名稱可能與 SHP 不同（如 SHP 為新北市、舊檔為臺北縣），用 excel_city 指定
    excel_city = cfg.get("excel_city", cfg["city"])
    city_mask = df_vote["縣市"].str.contains(excel_city, case=False, na=False)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask].copy()

    n_cand = len(cand_cols)
    cand_names = cfg.get("legend_names", [c[:-3] for c in cand_cols])   # 圖例欄名稱＝候選人
    if cfg.get("color_schemes"):
        stops_list = cfg["color_schemes"]
    else:
        stops_list = [RATE_COLOR_STOPS[i % len(RATE_COLOR_STOPS)] for i in range(n_cand)]

    vote_dict = {
        (r["town_core"], r["vill_core"]): tuple(r[c] for c in rate_cols)
        for _, r in df_vote.iterrows()
    }
    vote_by_town = {}
    raw_vote_by_town = {}
    for (t, v), vals in vote_dict.items():
        vote_by_town.setdefault(t, []).append((v, vals))
    for _, r in df_vote.iterrows():
        raw_vote_by_town.setdefault(r["town_core"], {})[r["vill_core"]] = r["區里"]

    # 鄉鎮市區層級資料：村里界無對應（Excel 僅到鄉鎮層級），以鄉鎮數值套用全鄉鎮村里
    town_level_only = bool(df_vote["vill_core"].str.strip().eq("").all())
    town_level_dict = {
        t: vals for (t, v), vals in vote_dict.items() if not v
    }

    def process_row(r):
        town, vill = r["town_core"], r["vill_core"]
        matched_vill, vals, excel_mt = fuzzy_lookup(town, vill, vote_dict, vote_by_town)
        if vals is None and town in town_level_dict:
            vals = town_level_dict[town]
            excel_mt = f"town:{town}"
        if vals is None:
            vals = tuple(np.nan for _ in range(n_cand))
            return pd.Series(list(vals) + ["none"])
        if excel_mt == "exact":
            raw_excel = raw_vote_by_town.get(town, {}).get(matched_vill)
            raw_shp = str(r["VILLNAME"])
            if raw_shp != raw_excel:
                excel_mt = f"variant:{raw_excel}"
        return pd.Series(list(vals) + [excel_mt])

    assign_cols = rate_cols + ["match_type"]
    gdf_nt[assign_cols] = gdf_nt.apply(process_row, axis=1)

    # 有任一候選人得票率可計算，即納入（NaN 以 0 計，不影響其餘候選人） 
    has_data = gdf_nt[rate_cols].notna().any(axis=1)
    gdf_with_data = gdf_nt[has_data].copy()
    gdf_no_data = gdf_nt[~has_data].copy()

    if len(gdf_with_data) == 0:
        raise ValueError(f"{cfg['excel']} 沒有任一村里資料匹配成功。")

    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], stops_list[i])

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 計算圖例起點（所有村里中最低的領先者得票率，向下取整到 5 的倍數） ----
    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0
    legend_start_tier = int(min_win_rate // 5) * 5

    # ---- 統計報告 ----
    exact_cnt = int((gdf_nt["match_type"] == "exact").sum())
    variant_cnt = int(gdf_nt["match_type"].str.startswith("variant", na=False).sum())
    fuzzy_cnt = int(gdf_nt["match_type"].str.startswith("fuzzy", na=False).sum())
    none_cnt = int((gdf_nt["match_type"] == "none").sum())
    cnt_valid = int(has_data.sum())
    no_data_cnt = int((~has_data).sum())

    print(f"  SHP 村里要素     : {len(gdf_nt)}")
    print(f"  Excel 有效記錄   : {len(df_vote)}   (候選人/政黨 {n_cand} 位)")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字匹配       : {variant_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    print(f"  無候選(無匹配)   : {none_cnt}")
    print(f"  有資料           : {cnt_valid}")
    print(f"  無資料/部分缺失  : {no_data_cnt}")

    # 簡要說明異體字 / 模糊匹配情形
    for key, label in [("variant", "異體字匹配（SHP 用字與 Excel 不同，經正規化後配對）"),
                       ("fuzzy", "模糊匹配（同鄉鎮內字串相似度達 50% 以上）")]:
        sub = gdf_nt[gdf_nt["match_type"].str.startswith(key, na=False)]
        if len(sub) == 0:
            continue
        print(f"  ■ {label}：共 {len(sub)} 個")
        for _, r in sub.head(8).iterrows():
            if key == "variant":
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    no_data_by_town = gdf_no_data.groupby("TOWNNAME").size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】")
        for town, cnt2 in no_data_by_town.items():
            print(f"  {town}: {cnt2} 個村里")
        nan_cnt = int(gdf_no_data["VILLNAME"].isna().sum())
        if nan_cnt:
            print(f"  ※ 其中 {nan_cnt} 個 SHP 村里名稱為空值(NaN)，無從比對，以灰色顯示")

    # ===================== 繪圖 =====================
    # 無資料村里著色規則：
    #   SHP 有、Excel 沒有 —— 有具體地名者（當時因行政沿革尚未設立）→ 白色
    #   VILLNAME 為 NaN（無名，多為荒島）→ 灰色
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != "")
    )
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)

    # 將無資料/NaN 村里也納入地圖，新北市全境皆繪製
    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    minx, miny, maxx, maxy = gdf_plot.total_bounds
    # 留白與 Converge_to_map1.py 一致（3%）；區名標註是「見縫插針」落進圖內
    # 既有的空白（台北市空缺、海岸外留白），不靠撐大畫布來騰空間。
    MAP_PAD_FRAC = MAP_PAD_FRAC_LABELS
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    # ---- 尺寸表：底圖/標題/圖例沿用 Converge_to_map1.py 的固定值 ----
    city_w_px = (maxx - minx) / METERS_PER_PIXEL
    st = build_scale(city_w_px, (maxy - miny) / METERS_PER_PIXEL)
    print(f"  尺度基準         : S={st['S']:.3f}（形體寬 {city_w_px:.0f}px）"
          f" → 區名 {st['name_font']}px、得票率 {st['rate_font']}px、"
          f"村里線 {st['vill_line']}px、區界線 {st['town_line']}px、"
          f"外輪廓 {st['outer_line']}px")

    w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}，請調大 METERS_PER_PIXEL")

    DPI = 100
    PX2PT = 72.0 / DPI

    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = st["town_line"] * METERS_PER_PIXEL / 2
    outer_half_m = st["outer_line"] * METERS_PER_PIXEL / 2
    city_geom = gdf_plot.geometry.union_all()

    # ① 村里填色（無邊）
    gdf_plot.plot(
        ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 村里黑線
    village_lines = gdf_plot.boundary.union_all()
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=st["vill_line"] * PX2PT, antialiased=False, zorder=5
        )

    # ③ 鄉鎮市區黑線（黑帶）
    town_lines = gdf_plot.dissolve(by="town_core").boundary.union_all()
    if not town_lines.is_empty:
        town_band = town_lines.buffer(
            town_half_m, resolution=BUF_RES,
            join_style=BUF_JOIN, cap_style=BUF_CAP
        ).intersection(city_geom)
        if not town_band.is_empty:
            gpd.GeoSeries([town_band]).plot(
                ax=ax, facecolor='black', edgecolor='none',
                linewidth=0, antialiased=False, zorder=9
            )

    # ④ 市外輪廓（黑帶）
    outer = city_geom.boundary.buffer(
        outer_half_m, resolution=BUF_RES,
        join_style=BUF_JOIN, cap_style=BUF_CAP
    )
    if not outer.is_empty:
        gpd.GeoSeries([outer]).plot(
            ax=ax, facecolor='black', edgecolor='none',
            linewidth=0, antialiased=False, zorder=11
        )

    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)

    img_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # ===================== 顏色量化（分塊處理）=====================
    allowed_hex = {"#FFFFFF", "#000000", GRAY_COLOR}
    for stops in stops_list:
        allowed_hex.update(hx for _, hx in stops)
    allowed_rgb_255 = np.array([hex2rgb(hx) for hx in allowed_hex]).astype(np.float32) * 255

    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    n_pixels = pixels.shape[0]
    CHUNK_SIZE = 500_000
    quantized_flat = np.empty((n_pixels, 3), dtype=np.uint8)

    for start in range(0, n_pixels, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, n_pixels)
        chunk = pixels[start:end]
        min_dist = np.full(chunk.shape[0], np.inf, dtype=np.float32)
        min_idx = np.zeros(chunk.shape[0], dtype=np.int32)
        for i in range(allowed_rgb_255.shape[0]):
            diff = chunk - allowed_rgb_255[i]
            d = np.sqrt((diff * diff).sum(axis=1))
            mask = d < min_dist
            min_dist[mask] = d[mask]
            min_idx[mask] = i
        quantized_flat[start:end] = allowed_rgb_255[min_idx].astype(np.uint8)

    quantized = quantized_flat.reshape(img_rgb.shape)
    del pixels, img_rgb, quantized_flat

    # ===================== 文字圖像（全部以 Print_word.py 方式產生） =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size

    # 標註可以「插」進去的空白：白色像素。
    # 除了海岸外留白、台北市空缺，無資料而填白（#FFFFFF）的村里也算可用空白。
    free_mask = (quantized.min(axis=2) >= 250)

    # 界線遮罩：村里線／區界／外輪廓都是以純黑、無反鋸齒繪製，
    # 而色階中最深的填色為 #010D29／#071A09 等（非純黑），
    # 因此「三通道皆為 0」正好等於界線像素 → 用來要求標註框與界線保持淨空。
    line_mask = np.all(quantized == 0, axis=2)

    title_img = (render_text_image_cached(cfg["title_lines"], st["title_font"])
                 if cfg.get("title_lines") else None)

    # ---- 圖例只顯示從最低領先得票率色階起的色塊 ----
    legend_stops_list = [
        [(u, c) for u, c in stops if u > legend_start_tier]
        for stops in stops_list
    ]

    # 圖例欄標題（候選人名稱）
    name_imgs = [render_text_image_cached([nm], st["cand_name_font"]) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 各候選人欄的色階標籤
    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier,
                                 is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(render_text_image_cached([txt], st["legend_label_font"]))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    g = dict(st)
    g["max_label_w"] = max_label_w
    col_width = g["block_w"] + SWATCH_TEXT_GAP + max_label_w
    n_cols = len(legend_stops_list)
    group_w = (n_cols - 1) * (col_width + g["h_spacing"]) + g["block_w"]
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = (name_h + g["column_title_gap"]
                + max_n * (g["block_h"] + g["v_spacing"]) - g["v_spacing"])

    # ===================== 畫布佈局（圖例嵌進地圖右下角、標題置頂）=====================
    # 比照參考圖：地圖為主體，圖例包在圓角黑框面板裡、直接畫在地圖右下角的空白處，
    # 「地圖＋圖例」形成單一構圖；只有該角落真的壓到新北市填色時，
    # 才把面板退到地圖右側緊貼擺放（不再出現大面積白色空白）。
    panel_content_w = (n_cols - 1) * (col_width + g["h_spacing"]) + col_width
    panel_w = panel_content_w + 2 * (LEGEND_PANEL_BORDER + LEGEND_PANEL_PAD)
    panel_h = legend_h + 2 * (LEGEND_PANEL_BORDER + LEGEND_PANEL_PAD)

    # 預設落點：地圖畫布右下角（座標以地圖畫布為基準，貼到 final 時再加上 y_off）
    from shapely.geometry import box as _shp_box
    px0 = W - LEGEND_INMAP_MARGIN - panel_w
    py0 = H - LEGEND_INMAP_MARGIN - panel_h
    panel_rect_map = _shp_box(xlim[0] + px0 * METERS_PER_PIXEL,
                              ylim[1] - (py0 + panel_h) * METERS_PER_PIXEL,
                              xlim[0] + (px0 + panel_w) * METERS_PER_PIXEL,
                              ylim[1] - py0 * METERS_PER_PIXEL)
    panel_in_map = bool(px0 > 0 and py0 > 0
                        and not city_geom.intersects(panel_rect_map))
    if panel_in_map:
        new_W = W
        # 面板佔用區域從「可用空白」剔除，標註不會疊到圖例上
        rr0, rr1 = max(0, py0), min(H, py0 + panel_h)
        cc0, cc1 = max(0, px0), min(W, px0 + panel_w)
        free_mask[rr0:rr1, cc0:cc1] = False
    else:
        new_W = W + LEGEND_FALLBACK_GAP + panel_w + 30
        px0 = new_W - 30 - panel_w
        py0 = max(0, (H - panel_h) // 2)

    # 標題置於畫布頂部、水平置中
    top_band = (title_img.height + 50 + 45) if title_img else 0
    new_H = top_band + H + 25

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    y_off = top_band
    final_img.paste(pil_img, (0, y_off))

    if title_img:
        blit_rgba(final_img, title_img,
                  ((new_W - title_img.width) // 2, 50))

    # ---- 鄉鎮市區標註：區名 + 領先者得票率（見縫插針式佈局）----
    if cfg.get("town_labels", True):
        town_rates, rate_mode = compute_town_rates(df_vote, rate_cols, town_level_dict, town_level_only)

        # 得票率色塊底色：取該候選人色階中「≥70%」那一檔（中間調，黑字讀得清楚，
        # 也比照參考圖是固定色而非逐區變色）
        def _box_color(stops):
            for u, c in stops:
                if u >= 70:
                    return c
            return stops[-1][1]
        box_colors = {i: _box_color(stops_list[i]) for i in range(n_cand)}

        jobs = plan_town_labels(gdf_plot, town_rates, xlim, ylim, W, H, st,
                                free_mask=free_mask, box_colors=box_colors,
                                line_mask=line_mask)
        draw_town_labels(final_img, jobs, y_off, st)

        n_line = sum(1 for j in jobs if j["leader"])
        n_crowd = sum(1 for j in jobs if j["crowded"])
        n_touch = sum(1 for j in jobs if j.get("lhit", 0) > 0)
        print(f"  鄉鎮市區標註     : {len(jobs)} 個"
              f"（不需引線 {len(jobs) - n_line} 個、引線 {n_line} 個；區級得票率＝{rate_mode}）")
        print(f"  與界線零接觸     : {len(jobs) - n_touch}/{len(jobs)} 個"
              + (f"（{n_touch} 個區周邊找不到完全不碰界線的落點，已取代價最小者）"
                 if n_touch else "（全部標註框皆與界線保持淨空）"))
        if n_crowd:
            print(f"  ※ 找不到完全不重疊的落點、已接受輕微重疊者：{n_crowd} 個"
                  f"（可填 MANUAL_LABEL_POS 手動固定）")
        print("  【標註落點診斷】把不滿意的區直接複製進 MANUAL_LABEL_POS 即可")
        print("      MANUAL_LABEL_POS = {")
        for j in sorted(jobs, key=lambda t: t["core"]):
            mx = xlim[0] + j["cx"] * METERS_PER_PIXEL
            my = ylim[1] - j["cy"] * METERS_PER_PIXEL
            print(f"          \"{j['core']}\": ({mx:.0f}, {my:.0f}),"
                  f"   # {j['name']} {j['km2']:6.1f}km2 {j['how']}"
                  f" 引線{'有' if j['leader'] else '無'}"
                  + (" <<重疊" if j["crowded"] else ""))
        print("      }")

    # ---- 圖例：圓角黑框面板（已於上方決定落點：地圖右下角或右側緊貼）----
    pfy = py0 + y_off
    ImageDraw.Draw(final_img).rounded_rectangle(
        [px0, pfy, px0 + panel_w, pfy + panel_h],
        fill=(255, 255, 255), outline=(0, 0, 0),
        width=LEGEND_PANEL_BORDER, radius=LEGEND_PANEL_RADIUS)
    draw_legend_on(final_img, g,
                   px0 + LEGEND_PANEL_BORDER + LEGEND_PANEL_PAD,
                   pfy + LEGEND_PANEL_BORDER + LEGEND_PANEL_PAD,
                   cand_names, legend_stops_list, start_tier=legend_start_tier)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；色階從 {legend_start_tier}% 起\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "2010"   # 目前階段僅生成 2010 作為範例
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")