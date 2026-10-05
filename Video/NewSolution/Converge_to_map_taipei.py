# -*- coding: utf-8 -*-
"""
將村里界圖資與「臺北市長選舉各里得票」Excel 結合，繪製各里候選人得票率地圖。

圖資版本隨選舉年切換（見下方 SHP_SOURCES）：
    >= 2019  現行村里界圖資_111（VILLAGE_MOI_1111118.shp，UTF-8）—— 2022
    <  2019  村里界歷史圖資_106（VILLAGE_MOI_1070205.shp，Big5/cp950）—— 1994–2018
內政部每次選舉前會公告當年度有效的里界，里界調整會改變圖形，
所以地圖要用「該場選舉當下」的那一版，不能一律用最新圖資。

資料來源：data/2022台北市長選舉_各里得票.xlsx（工作表「村里層級明細」）：
    縣市 | 鄉鎮市區 | 村里 | <候選人>（號次，政黨）_得票數 | ..._得票率
得票率欄位值為字串（如 "48.14%"），載入時轉為數值。

輸出至 png/map/<year>/（資料夾即年份，檔名固定）：
    1994 / 1998 / 2002 / 2006 / 2010 / 2014 / 2018 / 2022 臺北市長選舉
（1994–2018 走歷史圖資 106；2022 走現行圖資 111）。地圖與圖例分成兩個檔案：
    * map.png    —— 純地圖（白底 RGB，交給 tool/build_assets.py 轉透明）
    * map2.png   —— 區級地圖（只畫區、不畫里；畫布與 map.png 完全同尺寸同範圍，
                    可疊合對位）。區級得票率＝該區各候選人得票數加總 ÷ 全體
                    候選人得票數加總（以票數加權，不做里的得票率平均）。
                    色階沿用村里地圖同一套（stops_for_column），故**不另出圖例**，
                    直接沿用各年 png/map/<year>/legend.png。
    * legend.png —— 僅候選人姓名與色階，不加標題。**本身就是透明底 RGBA**
                    （色塊不透明、文字純白），不必也不可以再過「白底轉透明」
                    —— 白字就是 RGB(255,255,255)，過一次會被整片吃掉。

圖例只列出「至少在某一里領先」的候選人，色階依政黨固定（見 stops_for_column）。
色階檔再依實際資料收斂：全部領先里的得票率落在 [lo, hi]，區間之外的檔
（例如所有領先里都 >40% 時的「≤35%」）不對應任何一里，畫出來只是空佔位，直接省略。

每一里以得票率最高之候選人著色；不設得票率下限
（最低一檔涵蓋所有較低得票率，以該色階最淺色顯示），不會留下大片灰色。

執行：
    py Converge_to_map_taipei.py
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

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# 輸出至主控台一律以 UTF-8，避免 Windows gbk 編碼無法列印某些符號
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ===================== 字体设置 =====================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(BASE_DIR, "data")
MAPS_DIR = os.path.join(BASE_DIR, "png", "map", "2022")

# ===================== 配置区 =====================
# 村里界圖資依「選舉年」切換（與 tools/boardlib/geo.py 同一套規則）
#   內政部每次選舉前公告當年度有效的村里界，里界會調整（合併、分割、界線微調）。
#   地圖畫的是「那場選舉當下」的里界，所以不能一律用最新圖資。
#
#     year <  2019  ->  村里界歷史圖資_106（VILLAGE_MOI_1070205）
#     year >= 2019  ->  現行村里界圖資_111（VILLAGE_MOI_1111118）
#
#   兩版欄位相同（COUNTYNAME / TOWNNAME / VILLNAME）但**編碼不同**：
#   106 版是 Big5（cp950）、111 版是 UTF-8。硬用 UTF-8 讀 106 版會 UnicodeDecodeError，
#   所以讀檔時逐一嘗試候選編碼，並以「這份圖資裡到不到得了指定縣市」當解碼正確的判準
#   （編碼錯了 COUNTYNAME 必是亂碼，縣市一定對不上，比只看有沒有丟例外可靠）。
HIST_ROOT = r"D:\Windows\Documents\村里界歷史圖資_111"
HISTORICAL_CUTOFF_YEAR = 2019

SHP_SOURCES = [
    {
        "id": "moi106",
        "label": "村里界歷史圖資_106（VILLAGE_MOI_1070205）",
        "paths": [
            os.path.join(HIST_ROOT, "村里界歷史圖資_106",
                         "村里界歷史圖資_106", "VILLAGE_MOI_1070205.shp"),
        ],
        "encoding": "cp950",
        "year_min": 0,
        "year_max": HISTORICAL_CUTOFF_YEAR - 1,
    },
    {
        "id": "moi111",
        "label": "現行村里界圖資_111（VILLAGE_MOI_1111118）",
        "paths": [
            os.path.join(HIST_ROOT, "村里界歷史圖資_111", "VILLAGE_MOI_1111118.shp"),
            os.path.join(HIST_ROOT, "VILLAGE_MOI_1111118.shp"),
        ],
        "encoding": "utf-8",
        "year_min": HISTORICAL_CUTOFF_YEAR,
        "year_max": None,
    },
]

# 要生成的地圖（1994 第一屆直選 ~ 2022 第八屆臺北市長選舉，各里得票領先之候選人）
# ★ 只做臺北市。新北市（2014）不在本腳本的範圍內，也不要加進來 ——
#   主程式開頭會擋掉 city 不是「臺北市」的資料集。
MAPS_DIR_2018 = os.path.join(BASE_DIR, "png", "map", "2018")


def _year_map_dir(year):
    """各場地圖／圖例的輸出資料夾：png/map/<year>/。"""
    return os.path.join(BASE_DIR, "png", "map", str(year))


DATASETS = [
    # ==== 1994–2014：圖資一律走歷史圖資 106（year < 2019）====
    # 這些年份的得票資料欄位沒有人名以外的政黨資訊（見 PARTY_COLOR_GROUPS），
    # 色階由候選人姓名對照推出：兩大黨仍是藍／綠，其餘（新黨、無黨籍…）走灰。
    # 圖資是 2018 年的里界，早年尚未設立／已合併的里對不到資料 → 留白不著色。
    {
        "year": 1994,
        "excel": os.path.join(EXCEL_DIR, "1994台北市长.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(1994), "map.png"),
        "out2": os.path.join(_year_map_dir(1994), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(1994), "legend.png"),
        "tag": "1994 臺北市長選舉（4 位候選人）",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    {
        "year": 1998,
        "excel": os.path.join(EXCEL_DIR, "1998台北市长.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(1998), "map.png"),
        "out2": os.path.join(_year_map_dir(1998), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(1998), "legend.png"),
        "tag": "1998 臺北市長選舉（3 位候選人）",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    {
        "year": 2002,
        # 這份村里明細沒有「縣市」欄（只有鄉鎮市區＋村里）→ 一律視為臺北市。
        "excel": os.path.join(EXCEL_DIR, "2002台北市長_選舉得票資料.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(2002), "map.png"),
        "out2": os.path.join(_year_map_dir(2002), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(2002), "legend.png"),
        "tag": "2002 臺北市長選舉（2 位候選人）",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    {
        "year": 2006,
        "excel": os.path.join(EXCEL_DIR, "2006台北市長_選舉得票資料.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(2006), "map.png"),
        "out2": os.path.join(_year_map_dir(2006), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(2006), "legend.png"),
        "tag": "2006 臺北市長選舉（6 位候選人）",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    {
        "year": 2010,
        "excel": os.path.join(EXCEL_DIR, "2010台北市長_選舉得票資料.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(2010), "map.png"),
        "out2": os.path.join(_year_map_dir(2010), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(2010), "legend.png"),
        "tag": "2010 臺北市長選舉（5 位候選人）",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    {
        "year": 2014,
        "excel": os.path.join(EXCEL_DIR, "2014台北市长选举_各里得票.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(_year_map_dir(2014), "map.png"),
        "out2": os.path.join(_year_map_dir(2014), "map2.png"),
        "legend_out": os.path.join(_year_map_dir(2014), "legend.png"),
        "tag": "2014 臺北市長選舉（7 位候選人）",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
    # ==== 既有兩場 ====
    {
        "year": 2022,      # >= 2019 -> 現行圖資 111
        "excel": os.path.join(EXCEL_DIR, "2022台北市長選舉_各里得票.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(MAPS_DIR, "map.png"),
        "out2": os.path.join(MAPS_DIR, "map2.png"),
        "legend_out": os.path.join(MAPS_DIR, "legend.png"),
        "tag": "2022 臺北市長選舉（12 位候選人）",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,   # 不設得票率門檻，≤45% 一檔以最淺色顯示
        "drop_nan_vill": False,
    },
    {
        "year": 2018,      # < 2019 -> 歷史圖資 106
        "excel": os.path.join(EXCEL_DIR, "2018台北市长选举.xlsx"),
        "sheet": "村里層級明細",
        "city": "臺北市",
        "out": os.path.join(MAPS_DIR_2018, "map.png"),
        "out2": os.path.join(MAPS_DIR_2018, "map2.png"),
        "legend_out": os.path.join(MAPS_DIR_2018, "legend.png"),
        "tag": "2018 臺北市長選舉（5 位候選人）",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "no_floor": True,
        "drop_nan_vill": False,
    },
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 10, 32000   # 1px = 10m
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
OUTER_LINE_PX = 6             # 市外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階（固定四組，依政黨指派） =====================
# ★ 色階不再「依欄位順序循環取色」，而是**依政黨固定**：
#
#     第 1 組  中國國民黨      藍
#     第 2 組  民主進步黨      綠
#     第 3 組  台灣民眾黨      青 —— 柯文哲、黃珊珊
#     第 4 組  新黨            黃 —— 趙少康、王建煊
#
#   四組以外的候選人（無黨籍、親民黨、台聯、各小黨）走 OTHER_RATE_STOPS 灰階。
#
# 為什麼要固定：以前是「圖例只列會領先的候選人，色階依欄位序分配」，
# 於是同一個政黨在不同選舉、不同縣市可能拿到不同顏色，
# 換一份資料就要重看一次圖例；而且兩大黨的藍綠也不保證是慣用的那組藍綠。
# 現在顏色變成政黨的屬性，跟資料有幾位候選人、排序如何都無關。
RATE_COLOR_STOPS = [
    [   # 第 1 組：中國國民黨候選人
        (35,  "#EAF6FF"),
        (40,  "#B8E2FF"),
        (45,  "#7CC8FF"),
        (50,  "#3AA8FF"),
        (55,  "#0088F0"),
        (60,  "#006FCC"),
        (65,  "#0059A8"),
        (70,  "#004684"),
        (75,  "#003563"),
        (80,  "#002647"),
        (85,  "#001A31"),
        (100, "#000D1F"),
    ],
    [   # 第 2 組：民主進步黨候選人
        (35, "#C9F2DE"),
        (40, "#A8E8C9"),
        (45, "#7EDBB2"),
        (50, "#4FCC98"),
        (55, "#25BC7F"),
        (60, "#12A66C"),
        (65, "#0A8A57"),
        (70, "#066F45"),
        (75, "#045836"),
        (80, "#034329"),
        (85, "#022E1C"),
        (100, "#011E13"),
    ],
    [   # 第 3 組：台灣民眾黨候選人（柯文哲、黃珊珊）
        (35,  "#B3FFF0"),
        (40,  "#00EBD1"),
        (45,  "#00D9CA"),
        (50,  "#00BFB2"),
        (55,  "#00A89C"),
        (60,  "#008080"),
        (65,  "#006666"),
        (70,  "#004C4C"),
        (75,  "#003838"),
        (80,  "#003030"),
        (85,  "#002626"),
        (100, "#021F1F"),
    ],
    [   # 第 4 組：新黨候選人（趙少康、王建煊）—— 黃
        (0,   "#FFF6CC"),
        (35,  "#FFE999"),
        (40,  "#FFDD66"),
        (45,  "#FFD12E"),
        (50,  "#FFC000"),
        (55,  "#F5B000"),
        (60,  "#D98E00"),
        (65,  "#BF7400"),
        (70,  "#A45B00"),
        (75,  "#854600"),
        (80,  "#663400"),
        (85,  "#4A2400"),
        (100, "#2E1600"),
    ],
]

# 四組以外的候選人（無黨籍、親民黨、台聯、台灣動物保護黨、台澎黨、台灣維新、共和黨……）：
# 沒有既定識別色，用中性灰階，跟藍／綠／青都不會混淆，
# 在深色看板底上仍看得出深淺差。
OTHER_RATE_STOPS = [
    (35,  "#E4E6EC"),
    (40,  "#D2D5DE"),
    (45,  "#C0C4D0"),
    (50,  "#AEB3C2"),
    (55,  "#9CA2B4"),
    (60,  "#8A91A6"),
    (65,  "#7A8095"),
    (70,  "#6A7084"),
    (75,  "#5A6073"),
    (80,  "#4A5062"),
    (85,  "#3A4051"),
    (100, "#2A3040"),
]

# 別名：舊程式碼（單一候選人模式）以這兩個名字取色階。
# 既然顏色已經固定成政黨屬性，這裡直接指向對應的那一組，不再另立一套。
KMT_RATE_STOPS = RATE_COLOR_STOPS[0]        # 國民黨單一候選人
KO_WEN_JE_RATE_STOPS = RATE_COLOR_STOPS[2]  # 柯文哲（2018 無黨籍身分參選，仍用民眾黨青）

# 政黨名 -> 色階。key 是中選會資料欄位裡會出現的字串片段。
# ★ 1994–2010 的得票資料欄位**只有人名、沒有政黨**（如「馬英九（01）_得票率」），
#   所以除政黨全稱／簡稱外，這裡一併列出各屆兩大黨候選人的姓名 ——
#   同一個政黨在任何選舉都拿到同一組色階（見上方說明），不因資料缺政黨欄而變灰。
#   判準只是「這段字串有沒有出現在欄名裡」，不影響有政黨標註的 2014/2018/2022。
#   姓名一律放「該黨」那一組；無黨籍與親民黨／台聯等小黨不入表 → 走灰階。
PARTY_COLOR_GROUPS = [
    (("中國國民黨", "國民黨",
      "黃大洲", "馬英九", "郝龍斌", "連勝文"), RATE_COLOR_STOPS[0]),
    (("民主進步黨", "民進黨",
      "陳水扁", "李應元", "謝長廷", "蘇貞昌"), RATE_COLOR_STOPS[1]),
    (("台灣民眾黨", "民眾黨", "柯文哲", "黃珊珊"), RATE_COLOR_STOPS[2]),
    (("新黨", "新党", "趙少康", "王建煊", "王建火宣"), RATE_COLOR_STOPS[3]),
]


def stops_for_column(col_name):
    """依候選人欄位名挑色階：先看政黨全稱／簡稱，再看人名，都沒有就給灰。

    ★ 順序有意義：姓名判準（柯文哲／黃珊珊）放在最後，
      因為他們在資料裡的政黨欄是「無黨籍及未經政黨推薦」，
      若先比對不到才輪到人名；反過來放也對，但這樣寫比較不容易誤判。
    """
    s = str(col_name)
    for keys, stops in PARTY_COLOR_GROUPS:
        for k in keys:
            if k in s:
                return stops
    return OTHER_RATE_STOPS

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LABEL_FONT_SIZE, LEGEND_PADDING = 36, 60
COLUMN_TITLE_GAP = 100      # 圖例候選人姓名與第一個色塊的間距

# ---- 所有文字皆以 Print_word.py 方式輸出，以下字級可依需求適度調整 ----
CAND_NAME_FONT_SIZE = 84     # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE = 56  # 圖例數值標籤（≤45%、45~50%…）字級

# ===================== 工具函数 =====================
# 異體字/音同字異 正規化對照（表格資料 vs 圖資用字不同，需先統一）
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',     # 坪林區石[曹] / 石槽
    '磘': '窯',     # 中和區瓦[磘]・灰[磘]
    '獇': '羌',     # 樹林區[獇]寮 / 羌寮
    '舘': '館',     # 板橋區公舘 / 三峽區永舘
    '廍': '部',     # 永和區新廍 / 新部
    '峯': '峰',     # 土城區峯廷 / 新店區五峯 / 瑞芳區爪峯
    '脚': '腳',     # 萬里區崁脚 / 崁腳
    '豊': '豐',     # 內門區內豊 / 內豐（2018高雄）
    '臺': '台',     # 信義區富臺里 / 富台里（臺北 2002/2006/2010）
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
    """鄉鎮市區名 → 去尾綴、也去掉縣市前綴。

    1994–2010 的得票資料把「鄉鎮市區」寫成「臺北市松山區」（含縣市前綴），
    圖資的 TOWNNAME 只有「松山區」；不比對前綴就整場對不上（1994 實測 0 匹配）。
    只在「前綴 + 鄉鎮市區」可以切開時才去前綴，單獨的「松山區」「三重市」不動。
    """
    if pd.isna(s):
        return ""
    t = normalize_text(s)
    t = re.sub(r"^.+?[市縣](?=.+[鄉鎮市區]$)", "", t)
    return re.sub(r"[鄉鎮市區]$", "", t)

def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))

def get_color_by_value(val, stops, below_color=None):
    if val is None or np.isnan(val):
        return None
    if val < stops[0][0]:
        return below_color
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

def resolve_source(year=None, source_id=None, shp=None):
    """挑一份村里界圖資，回傳 (path, encoding, label)。

    shp        直接指定路徑（覆寫 year / source_id）
    source_id  指定圖資 id（見 SHP_SOURCES）
    year       選舉年；<2019 走歷史圖資 106，否則走現行圖資 111
    """
    if shp:
        return shp, "utf-8", os.path.basename(shp)

    src = None
    if source_id:
        for s in SHP_SOURCES:
            if s["id"] == source_id:
                src = s
                break
        if src is None:
            raise ValueError("未知的圖資 id：%r（可用：%s）"
                             % (source_id, "、".join(s["id"] for s in SHP_SOURCES)))
    else:
        y = HISTORICAL_CUTOFF_YEAR if year is None else int(year)
        for s in SHP_SOURCES:
            if y >= s["year_min"] and (s["year_max"] is None or y <= s["year_max"]):
                src = s
                break
        if src is None:
            raise ValueError("沒有任何圖資涵蓋 %r 年" % year)

    for p in src["paths"]:
        if os.path.exists(p):
            return p, src["encoding"], src["label"]
    raise FileNotFoundError("找不到 %s 的 SHP，找過：%s"
                            % (src["label"], "、".join(src["paths"])))


def load_village_boundaries(year=None, source_id=None, shp=None):
    """載入村里界圖資，統一欄位 COUNTYNAME / TOWNNAME / VILLNAME，投影至 EPSG:3826。

    圖資版本由 year 決定（<2019 用歷史圖資 106），編碼自動適配。
    """
    path, preferred, label = resolve_source(year=year, source_id=source_id, shp=shp)
    print(f"  ※ 圖資來源：{label}")
    print(f"    {path}")

    gdf = None
    tried = []
    for enc in dict.fromkeys([preferred, "utf-8", "cp950", "big5"]):
        try:
            cand = gpd.read_file(path, encoding=enc)
        except Exception as e:
            tried.append(f"{enc}×({e.__class__.__name__})")
            continue
        if not all(c in cand.columns for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]):
            tried.append(f"{enc}×(欄位不符)")
            continue
        # 解碼正確的判準：讀得到中文縣市名（編碼錯了必是亂碼）
        names = [str(v) for v in cand["COUNTYNAME"].dropna().unique()]
        if not any(unicodedata.category(ch) == "Lo" for n in names for ch in n):
            tried.append(f"{enc}×(縣市名非中文)")
            continue
        gdf = cand
        if enc != preferred:
            print(f"    （{preferred} 讀不到，改用 {enc}）")
        break

    if gdf is None:
        raise RuntimeError(f"讀取村里界 SHP 失敗：{path}（試過 {'、'.join(tried)}）")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.is_geographic:
        gdf = gdf.to_crs(epsg=3826)

    for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]:
        if c not in gdf.columns:
            raise ValueError(f"圖資缺失必要欄位：{c}")
    return gdf

# ===================== 文字圖片生成（仿 Print_word.py） =====================
def render_text_image(text_lines, font_size=64, dpi=100, color=(255, 255, 255)):
    """以 Print_word.py 方式：Matplotlib 繪字 → OpenCV 二值化 → 透明背景。

    回傳 PIL RGBA（文字為 color（預設純白）、背景透明），可直接 paste 到任何底色的圖上。
    字緣形狀只由二值化遮罩決定，換色不影響字形——所以白字與黑字的位置完全一致。
    """
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    font_name = None
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            font_name = n
            break
    # 用字型鏈回退：中文字用 CJK 字型，缺少的符號（如 ≤ U+2264）由 DejaVu Sans 補
    font_family = [font_name, "DejaVu Sans"] if font_name else "DejaVu Sans"

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

    line_spacing = font_size * 1.5
    total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing
    max_width = max(line_widths)
    PAD = 20
    fig_w_pt = max_width + 2 * PAD
    fig_h_pt = total_height + 2 * PAD

    # matplotlib 這一步一律「白底黑字」——只是為了取得乾淨的遮罩，
    # 真正的文字顏色在第 ⑤ 步用遮罩上色。
    fig = plt.figure(figsize=(fig_w_pt / dpi, fig_h_pt / dpi), dpi=dpi, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w_pt)
    ax.set_ylim(0, fig_h_pt)
    ax.set_facecolor("white")
    ax.axis("off")

    y = PAD + total_height
    for i, line in enumerate(text_lines):
        x = (fig_w_pt - line_widths[i]) / 2
        y -= line_heights[i]
        ax.text(x, y, line, fontsize=font_size, ha="left", va="bottom",
                fontfamily=font_family, color="black")
        y -= line_spacing

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, facecolor="white", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    _, bin_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    h, w = bin_img.shape
    # 透明底 + 指定色文字：alpha 由遮罩決定，RGB 整張塗成 color
    r, g, b = (int(c) for c in color)
    bgra = np.zeros((h, w, 4), dtype=np.uint8)
    bgra[:, :, 0] = b
    bgra[:, :, 1] = g
    bgra[:, :, 2] = r
    bgra[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA))

_TEXT_IMG_CACHE = {}

def render_text_image_cached(text_lines, font_size, color=(255, 255, 255)):
    """快取版 render_text_image：相同文字、字級、顏色只渲染一次（Print_word.py 方式）。"""
    key = (tuple(text_lines), font_size, tuple(color))
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size, color=color)
    return _TEXT_IMG_CACHE[key]

def blit_rgba(base_img, rgba_img, xy):
    """將透明底 RGBA 文字圖以 alpha 為遮罩貼到 base_img 的 (x, y)。"""
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))

# ===================== 读取得票 Excel，计算得票率 =====================
def _norm_text(v):
    """正規化：NaN / 'nan'(不區分大小寫) 一律視為空字串（缺失）。"""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s

def _to_rate(v):
    """得票率轉 float：支援 "48.14%" / "48.14" / 數值；無法解析回傳 NaN。"""
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return np.nan
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return np.nan

def cand_display_name(col):
    """欄名（『蔣萬安（06，中國國民黨）_得票率』）→ 圖例顯示名（『蔣萬安』）。"""
    s = str(col)
    for suf in ("_得票率", "得票率", "_得票數", "得票數"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    s = s.rstrip("_").strip()
    m = re.match(r"^(.*?)[（(]", s)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return s

def load_rates(cfg):
    excel_path = cfg["excel"]
    df = pd.read_excel(excel_path, sheet_name=cfg["sheet"], header=cfg.get("header", 0))
    df.columns = [str(c) for c in df.columns]

    # 支援三種來源：
    #  ① 得票率專用檔：欄位直接是「<候選人>（號次，政黨）_得票率」，值為 "48.14%" 字串
    #  ② 高雄格式全量檔：<候選人>得票數 ＋ 有效票數A，再除以 A×100 得得票率
    #  ③ 指定候選人欄位（cfg["cand_columns"]）：欄名即候選人、值為得票率(%)
    pct_cols = [c for c in df.columns if c.endswith("得票率")]
    vote_cols = [c for c in df.columns if c.endswith("得票數")]
    given_cands = cfg.get("cand_columns")

    if given_cands:
        cand_cols = list(given_cands)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = df[c].map(_to_rate)
    elif pct_cols:
        cand_cols = pct_cols
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = df[c].map(_to_rate)
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

    # 區級地圖（map2）用：與各得票率欄**成對**的得票數欄。
    #   * 中選會格式：欄名同前綴、後綴「得票率」換成「得票數」（如
    #     「蔣萬安（06，中國國民黨）_得票率」↔「…_得票數」），各年都有。
    #   * 高雄格式全量檔：cand_cols 本身就是得票數欄，與 rate1..rateN 順序一致。
    # 找不到成對欄的候選人記 None（該場會跳過區級地圖並提示）。
    if vote_cols and not pct_cols and not given_cands:
        vote_num_cols = list(cand_cols)
    else:
        vote_num_cols = []
        for c in rate_cols:
            s = str(c)
            vcol = None
            if s.endswith("得票率"):
                cand = s[: -len("得票率")] + "得票數"
                if cand in df.columns:
                    vcol = cand
            vote_num_cols.append(vcol)
    for v in dict.fromkeys(v for v in vote_num_cols if v):
        df[v] = pd.to_numeric(df[v], errors="coerce")

    # 縣市欄：2002 / 2006 / 2010 的村里明細只有「鄉鎮市區 + 村里」，沒有縣市欄，
    # 這種情況一律視為本市（下方 make_map 會把空縣市視為同屬 cfg["city"]）。
    city_col = cfg.get("col_city", "選舉區別")
    if city_col in df.columns:
        df["縣市"] = df[city_col].apply(_norm_text)
    else:
        df["縣市"] = ""
    df["鄉鎮市區"] = df[cfg.get("col_town", "鄉(鎮、市、區)別")].apply(_norm_text)
    df["區里"] = df[cfg.get("col_vill", "村里別")].apply(_norm_text)

    df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
    df["vill_core"] = df["區里"].apply(strip_village_suffix)

    # 去掉彙總列與空列。2002 / 2006 / 2010 的明細最後一列是「總計」，而且欄位錯位
    # （村里欄放票數、得票率欄放總和 → 出現 873102% 這種值），留著會污染圖例的
    # 領先率區間，還會讓某位候選人莫名多一「里」而擠進圖例。
    summary = df["town_core"].isin({"總計", "合計", "總　計", "总计", "总　计"})
    blank = (df["town_core"] == "") & (df["vill_core"] == "")
    df = df[~(summary | blank)].copy()
    return df, cand_cols, rate_cols, vote_num_cols

# ===================== 精确 + 同乡镇最相似模糊匹配 =====================
MIN_SIMILARITY = 1.0   # 臺北市實際皆精確/異體字匹配，關閉模糊以免誤配額外村里

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
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"

# ===================== 圖例繪製 =====================
def as_legend_stops(stops, lo=None, hi=None):
    """色階表 (upper, hex) → 圖例用的 (upper, hex, lower)，並依 [lo, hi] 收斂檔位。

    lo / hi 是「所有領先里的得票率」的最小／最大值。檔位第 i 檔涵蓋
    (stops[i-1].upper, stops[i].upper]，與 [lo, hi] 沒有交集的檔就不畫：
      * stops[i].upper < lo  —— 全部領先里都高於這一檔（例如都 >40% 時的「≤35%」）
      * 前一檔 upper >= hi   —— 全部領先里都低於這一檔

    第三個元素 lower 是**原始表**的前一檔上界（不是收斂後的前一檔），
    這樣留下的第一檔仍標成「35~40%」而不是「≤40%」——顏色代表的區間不變。
    """
    out, prev = [], None
    for upper, hx in stops:
        if (lo is None or upper >= lo) and (hi is None or prev is None or prev < hi):
            out.append((upper, hx, prev))
        prev = upper
    return out

def draw_legend_on(final_img, x0, y0, cand_names, stops_list, col_width):
    """圖例：色塊用 ImageDraw 繪製；所有文字以 Print_word.py 方式（render_text_image）貼上。

    final_img 是透明底 RGBA：色塊不透明、文字純白，整張圖不留白底。
    stops_list 的每一項是 as_legend_stops() 的結果 [(upper, hex, lower), …]。
    """
    draw_obj = ImageDraw.Draw(final_img)
    n = len(cand_names)
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(n)]
    name_h = max(
        (render_text_image_cached([nm], CAND_NAME_FONT_SIZE).height for nm in cand_names),
        default=0,
    )
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_text_image_cached([cand_names[col_idx]], CAND_NAME_FONT_SIZE)
            blit_rgba(final_img, nm_img, (x_start + (BLOCK_WIDTH - nm_img.width) / 2, y0))
        for i, (upper, color_hex, lower) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            limg = render_text_image_cached([get_label_text(upper, lower)], LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))

def render_legend_image(cand_names, stops_list):
    """產生獨立圖例圖檔：透明底、每欄一列候選人姓名 + 色階，不加任何標題。

    ★ 直接輸出透明底 RGBA（色塊不透明、文字純白），不是「白底 + 深色字」再
      交給 build_assets 去背 —— 白字本身就是 RGB(255,255,255)，再過一次
      「白底轉透明」會被整片吃掉。所以這張圖的成品就是它自己。

    候選人姓名以該欄色塊為中心置中，姓名可能比色塊（BLOCK_WIDTH）寬而向左右溢出，
    故先量測所有元素的實際左右邊界，再據以決定畫布尺寸與起點，
    確保中文字元完整顯示、不被畫布裁掉。
    """
    if not cand_names or not stops_list:
        raise ValueError("圖例沒有任何候選人欄位可繪製")

    # 標籤最大寬度決定欄寬
    label_w = 0
    for stops in stops_list:
        for upper, _hex, lower in stops:
            txt = get_label_text(upper, lower)
            label_w = max(label_w, render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE).width)
    col_width = BLOCK_WIDTH + 8 + label_w

    n_cols = len(stops_list)
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 內容左右邊界（各欄起點以 0 為基準）：色塊/標籤 欄寬 + 居中姓名的溢出
    min_x = 0.0
    max_x = float(n_cols * col_width + (n_cols - 1) * H_SPACING)
    for i, nm in enumerate(name_imgs):
        x_start = i * (col_width + H_SPACING)
        nm_x = x_start + (BLOCK_WIDTH - nm.width) / 2
        min_x = min(min_x, nm_x)
        max_x = max(max_x, nm_x + nm.width)

    content_w = max_x - min_x
    max_n = max(len(s) for s in stops_list)
    content_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    img = Image.new(
        "RGBA",
        (int(np.ceil(content_w + 2 * LEGEND_PADDING)),
         int(np.ceil(content_h + 2 * LEGEND_PADDING))),
        (0, 0, 0, 0),
    )
    draw_legend_on(img, LEGEND_PADDING - min_x, LEGEND_PADDING, cand_names, stops_list, col_width)
    return img

def get_label_text(upper, prev=None):
    return f"≤{upper}%" if prev is None else f"{prev}~{upper}%"

def _quantize_to_allowed(img_rgb, allowed_rgb_255):
    """最近鄰顏色量化（分塊），與村里地圖同一套算法：把整張圖限制在
    允許色（白/黑/灰 + 各候選人色階）內，確保後續「白→透明」容差安全。"""
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
    return quantized_flat.reshape(img_rgb.shape)

def draw_district_map(cfg, gdf_plot, df_vote, rate_cols, vote_num_cols,
                      pick_stops, no_floor, kmt_col, xlim, ylim, w_px, h_px):
    """區級地圖（map2.png）：只畫區、不畫里，不另出圖例（沿用村里地圖的 legend.png）。

    * 區級得票率 = 該區各候選人**得票數**加總 ÷ 該區全體候選人得票數加總 × 100。
      用票數加權而非「里的得票率平均」，人口大里才不會被小里稀釋。
    * 著色規則與村里地圖完全一致（領先候選人 + stops_for_column 色階 + no_floor
      最淺色補位），所以同一份圖例直接通用。
    * 區界由同一份村里圖資 dissolve(by=TOWNNAME) 而來，畫布範圍／解析度也與
      map.png 完全相同（同 xlim/ylim/w/h），兩圖可疊合對位。
    * 線寬沿用村里圖：區界 4px 黑帶、市外輪廓 6px 黑帶；村里細線不畫。
    """
    out2 = cfg.get("out2")
    if not out2:
        return
    if not all(vote_num_cols):
        print("  ※ 缺少成對的得票數欄位，跳過區級地圖（map2）")
        return

    print("  ---- 區級地圖（map2：只畫區界、不畫里，沿用村里圖例） ----")

    # ① 區級得票率：各候選人得票數按區加總，除以該區全體得票數
    vote_num = pd.DataFrame({
        c: pd.to_numeric(df_vote[v], errors="coerce")
        for c, v in zip(rate_cols, vote_num_cols)
    })
    vote_num["town_core"] = df_vote["town_core"].values
    agg = vote_num.groupby("town_core").sum(min_count=1)
    total = agg.sum(axis=1)
    dist = agg.div(total.replace(0, np.nan), axis=0) * 100.0

    # ② 區界幾何（由村里圖資 dissolve，界線與 map.png 同源）
    gdf_town = gdf_plot[["town_core", "geometry"]].dissolve(by="town_core")

    def town_fill(town):
        if town not in dist.index:
            return "#FFFFFF"
        row = dist.loc[town]
        if kmt_col:
            stops = pick_stops[0]
            val = row.get(kmt_col, np.nan) if hasattr(row, "get") else np.nan
            return get_color_by_value(
                float(val) if pd.notna(val) else np.nan, stops,
                below_color=stops[0][1])
        vals = row.to_numpy(dtype=float)
        if np.isnan(vals).all():
            return "#FFFFFF"
        i = int(np.argmax(np.where(np.isnan(vals), 0.0, vals)))
        stops = pick_stops[i]
        return get_color_by_value(
            vals[i], stops, below_color=stops[0][1] if no_floor else None)

    gdf_town["fill_hex"] = gdf_town.index.map(town_fill)

    # 各區領先者報告
    for town in gdf_town.index:
        if town not in dist.index:
            print(f"      {town}：無資料（白色）")
            continue
        vals = dist.loc[town].to_numpy(dtype=float)
        if np.isnan(vals).all():
            print(f"      {town}：無資料（白色）")
        elif kmt_col:
            print(f"      {town}：{cand_display_name(kmt_col)} {vals[list(dist.columns).index(kmt_col)]:.2f}%")
        else:
            i = int(np.argmax(np.where(np.isnan(vals), 0.0, vals)))
            print(f"      {town}：{cand_display_name(rate_cols[i])} 領先 {vals[i]:.2f}%")

    # ③ 繪圖（與 map.png 同畫布）
    DPI = 100
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = gdf_plot.geometry.union_all()

    # ① 區填色（無邊）
    gdf_town.plot(
        ax=ax, facecolor=gdf_town["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 區界黑線（4px 黑帶）
    town_lines = gdf_town.boundary.union_all()
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

    # ③ 市外輪廓（6px 黑帶）
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

    # ④ 顏色量化：允許色與村里地圖同一組（白/黑/灰 + 各候選人色階）
    allowed_hex = {"#FFFFFF", "#000000", GRAY_COLOR}
    for stops in pick_stops:
        allowed_hex.update(hx for _, hx in stops)
    allowed_rgb_255 = np.array([hex2rgb(hx) for hx in allowed_hex]).astype(np.float32) * 255

    quantized = _quantize_to_allowed(img_rgb, allowed_rgb_255)
    map2_img = Image.fromarray(quantized)
    saved_map2 = save_png(map2_img, out2)
    print(f"  輸出(區級地圖): {saved_map2}  ({map2_img.width}×{map2_img.height}px)")

def make_map(cfg):
    print("=" * 62)
    print(f"  組別：{cfg['tag']}")
    print("=" * 62)

    gdf_all = load_village_boundaries(year=cfg.get("year"),
                                      source_id=cfg.get("geoSource"),
                                      shp=cfg.get("shp"))

    # 縣市名稱經異體字正規化（臺→台）後比對：圖資寫「臺北市」、Excel 寫「台北市」
    city_key = normalize_text(cfg["city"])
    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].map(normalize_text).str.contains(city_key, na=False)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"圖資中未找到 {cfg['city']} 數據")

    dropped = 0
    if cfg.get("drop_nan_vill", False):
        nan_mask = gdf_nt["VILLNAME"].isna() | (gdf_nt["VILLNAME"].astype(str).str.strip() == "")
        dropped = int(nan_mask.sum())
        gdf_nt = gdf_nt[~nan_mask].copy()
        print(f"  ※ 依 drop_nan_vill 排除無地名区块 {dropped} 個（未編定村里 / 代管離島）")

    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols, vote_num_cols = load_rates(cfg)
    # 納入 {city} 資料；縣市欄缺失(NaN / 'nan' 不區分大小寫)者視為同屬該縣市，一併納入
    city_mask = df_vote["縣市"].map(normalize_text).str.contains(city_key, na=False)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask].copy()

    n_cand = len(cand_cols)
    kmt_col = cfg.get("kmt_rate_col")
    no_floor = bool(cfg.get("no_floor", False))

    if kmt_col:
        # 國民黨候選人得票率模式：單一候選人、單一色階（35%~85%，每 5% 一檔）
        # 特殊處理：2018 柯文哲使用專用色階
        is_ko_wen_je = "柯文哲" in str(cfg.get("legend_names", [""])) or "柯文哲" in str(kmt_col)
        selected_stops = KO_WEN_JE_RATE_STOPS if is_ko_wen_je else KMT_RATE_STOPS
        cand_names = cfg.get("legend_names", [cand_display_name(kmt_col)])
        stops_list = [as_legend_stops(selected_stops)]
        pick_stops = [selected_stops]
        leaders = None
        lead_counts = None
        legend_range = None
    else:
        # 先算每一里的領先候選人：只有真的會出現在地圖上的候選人進圖例，
        # 色階依政黨指派：藍=國民黨、綠=民進黨、青=民眾黨（柯文哲／黃珊珊）、
        # 灰=其他（無黨籍與各小黨）。規則集中在檔案上方的 stops_for_column()。
        rate_matrix = df_vote[rate_cols].to_numpy(dtype=float)
        filled = np.where(np.isnan(rate_matrix), 0.0, rate_matrix)
        lead_idx = filled.argmax(axis=1)
        lead_counts = np.bincount(lead_idx, minlength=n_cand)
        leaders = [i for i in range(n_cand) if lead_counts[i] > 0]

        palette_for = {}
        for i in range(n_cand):
            palette_for[i] = stops_for_column(rate_cols[i])

        cand_names = [cand_display_name(rate_cols[i]) for i in leaders]

        # 圖例的色階檔依實際資料收斂：全部領先里的得票率都落在 [lo, hi]，
        # 區間之外的檔位不對應任何一里（例如所有領先里都 >40% 時的「≤35%」），
        # 畫出來只是空佔位、還讓人以為地圖上會有那個顏色，所以直接省略。
        # 收斂用**全體**領先里的區間（不是各欄各自的），三欄的列數才會一致、對得齊。
        lead_rate = filled[np.arange(filled.shape[0]), lead_idx]
        legend_range = (float(lead_rate.min()), float(lead_rate.max()))
        stops_list = [as_legend_stops(palette_for[i], *legend_range)   # 圖例用
                      for i in leaders]
        pick_stops = [palette_for[i] for i in range(n_cand)]     # 地圖著色用（依欄位索引）

    def below_color(stops):
        """未達首檔門檻的顏色：不設門檻（或單一候選人模式）時用最淺色，否則不著色。"""
        return stops[0][1] if (no_floor or kmt_col) else None

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

    def process_row(r):
        town, vill = r["town_core"], r["vill_core"]
        matched_vill, vals, excel_mt = fuzzy_lookup(town, vill, vote_dict, vote_by_town)
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
        if kmt_col:
            is_ko_wen_je = "柯文哲" in str(cfg.get("legend_names", [""])) or "柯文哲" in str(kmt_col)
            selected_stops = KO_WEN_JE_RATE_STOPS if is_ko_wen_je else KMT_RATE_STOPS
            return get_color_by_value(row[kmt_col], selected_stops, below_color=below_color(selected_stops))
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        stops = pick_stops[i]
        return get_color_by_value(vals[i], stops, below_color=below_color(stops))

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    if kmt_col:
        is_ko_wen_je = "柯文哲" in str(cfg.get("legend_names", [""])) or "柯文哲" in str(kmt_col)
        selected_stops = KO_WEN_JE_RATE_STOPS if is_ko_wen_je else KMT_RATE_STOPS
        first_bin = selected_stops[0][0]
        below_cnt = int((gdf_with_data[kmt_col] < first_bin).sum())
    else:
        first_bin = RATE_COLOR_STOPS[0][0][0]
        vals = gdf_with_data[rate_cols].to_numpy(dtype=float)
        v = np.where(np.isnan(vals), 0.0, vals)
        leader_rate = v[np.arange(v.shape[0]), v.argmax(axis=1)]
        below_cnt = int((leader_rate < first_bin).sum())
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 統計報告 ----
    exact_cnt = int((gdf_nt["match_type"] == "exact").sum())
    variant_cnt = int(gdf_nt["match_type"].str.startswith("variant", na=False).sum())
    fuzzy_cnt = int(gdf_nt["match_type"].str.startswith("fuzzy", na=False).sum())
    none_cnt = int((gdf_nt["match_type"] == "none").sum())
    cnt_valid = int(has_data.sum())
    no_data_cnt = int((~has_data).sum())

    print(f"  圖資村里要素     : {len(gdf_nt)}")
    if kmt_col:
        print(f"  Excel 有效記錄   : {len(df_vote)}   (圖例：{cand_names[0]} 得票率)")
    else:
        print(f"  Excel 有效記錄   : {len(df_vote)}   (候選人 {n_cand} 位，圖例列示領先者 {len(leaders)} 位)")
        print("  領先里數         : " + "、".join(
            f"{cand_names[k]} {int(lead_counts[leaders[k]])} 里" for k in range(len(leaders))
        ))
        if leaders:
            print(f"  圖例色階         : 保留 {len(stops_list[0])} / {len(palette_for[leaders[0]])} 檔"
                  f"（領先率 {legend_range[0]:.2f}~{legend_range[1]:.2f}%，區間外的檔不畫）")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字匹配       : {variant_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    print(f"  無候選(無匹配)   : {none_cnt}")
    if kmt_col:
        print(f"  有資料           : {cnt_valid}（其中得票率<{first_bin}% 以最淺色顯示 {below_cnt} 個）")
    elif no_floor:
        print(f"  有資料           : {cnt_valid}（全部著色，不設門檻；≤{first_bin}% 一檔以最淺色顯示 {below_cnt} 個）")
    else:
        print(f"  有資料           : {cnt_valid}（其中得票率<{first_bin}% 未著色 {below_cnt} 個）")
    print(f"  無資料/部分缺失  : {no_data_cnt}")

    # 簡要說明異體字 / 模糊匹配情形
    for key, label in [("variant", "異體字匹配（圖資用字與 Excel 不同，經正規化後配對）"),
                       ("fuzzy", "模糊匹配（同鄉鎮內字串相似度達 50% 以上）")]:
        sub = gdf_nt[gdf_nt["match_type"].str.startswith(key, na=False)]
        if len(sub) == 0:
            continue
        print(f"  ■ {label}：共 {len(sub)} 個")
        for _, r in sub.head(8).iterrows():
            if key == "variant":
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  ↔  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  ↔  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    no_data_by_town = gdf_no_data.groupby("TOWNNAME").size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】")
        for town, cnt2 in no_data_by_town.items():
            print(f"  {town}: {cnt2} 個村里")
        nan_cnt = int(gdf_no_data["VILLNAME"].isna().sum())
        if nan_cnt:
            print(f"  ※ 其中 {nan_cnt} 個村里名稱為空值(NaN)，無從比對，以灰色顯示")

    # ===================== 繪圖 =====================
    # 無資料村里著色規則：
    #   圖資有、Excel 沒有 —— 有具體地名者（當年尚未設立或行政沿革調整）→ 白色
    #   VILLNAME 為 NaN（無名，多為荒島）→ 灰色
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != "")
    )
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)

    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    minx, miny, maxx, maxy = gdf_plot.total_bounds
    MAP_PAD_FRAC = 0.03
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

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

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = gdf_plot.geometry.union_all()

    # ① 村里填色（無邊）
    gdf_plot.plot(
        ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 村里黑線（1px）
    village_lines = gdf_plot.boundary.union_all()
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=VILL_LINE_PX * PX2PT, antialiased=False, zorder=5
        )

    # ③ 鄉鎮市區黑線（4px 黑帶）
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

    # ④ 市外輪廓（6px 黑帶）
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
    for stops in pick_stops:
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

    # ===================== 地圖（純地圖：不含標題、不含圖例） =====================
    map_img = Image.fromarray(quantized)
    saved_map = save_png(map_img, cfg["out"])
    print(f"  輸出(地圖): {saved_map}  ({map_img.width}×{map_img.height}px)")

    # ===================== 區級地圖（map2：只畫區，沿用原圖例） =====================
    draw_district_map(cfg, gdf_plot, df_vote, rate_cols, vote_num_cols,
                      pick_stops, no_floor, kmt_col, xlim, ylim, w_px, h_px)

    # ===================== 圖例（獨立圖檔：僅候選人姓名 + 色階） =====================
    legend_out = cfg.get("legend_out")
    if legend_out:
        legend_img = render_legend_image(cand_names, stops_list)
        saved_legend = save_png(legend_img, legend_out)
        print(f"  輸出(圖例): {saved_legend}  ({legend_img.width}×{legend_img.height}px)")

    print(f"     主圖基於 {len(gdf_with_data)} 個有資料里繪製；"
          f"圖例列出 {len(cand_names)} 位領先候選人\n")

SAVE_RETRY = 6
SAVE_RETRY_WAIT = 2.0   # 檔案若正被看圖軟體開啟鎖定，重試間隔（秒）

def save_png(img, path):
    """儲存 PNG。若檔案正被其他程式開啟鎖定，稍候重試；超過重試次數則改存
    同目錄附加 _鎖定重試 的檔名並提示，不中斷整批生成。"""
    import time
    for attempt in range(SAVE_RETRY):
        try:
            img.save(path)
            return path
        except OSError:
            if attempt == SAVE_RETRY - 1:
                base, ext = os.path.splitext(path)
                alt = base + "_鎖定重試" + ext
                img.save(alt)
                print(f"  ⚠ 無法寫入（檔案可能正被開啟）：{os.path.basename(path)}")
                print(f"     已改存：{os.path.basename(alt)}")
                return alt
            time.sleep(SAVE_RETRY_WAIT)
    return path

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖，如：py Converge_to_map_taipei.py 2002
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        # 本腳本只產出台北市的地圖；新北（2014）不在範圍內
        if normalize_text(cfg["city"]) != normalize_text("臺北市"):
            raise SystemExit("只產出台北市的地圖，%s 不在範圍內（見 DATASETS）"
                             % cfg["city"])
        make_map(cfg)
    print("全部完成。")