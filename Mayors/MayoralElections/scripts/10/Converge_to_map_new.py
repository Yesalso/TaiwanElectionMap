# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與「高雄格式」得票 Excel 結合，
繪製各村里候選人得票率地圖。

資料格式（各里彙總 工作表）：
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票數 ... | 有效票數A
得票率(%) = 候選人得票數 ÷ 有效票數A × 100

色階 5% 一階（範圍隨資料伸縮），配色查 RATE_COLOR_RAMPS 的「級距 → 色碼」表。
候選人數量由 Excel 自動偵測，圖例欄數隨之調整。

【標註版式】＝「區名 + 領先者得票率色片 + 引線」，比照參考圖 maps/10/1.png：
    第一行  區名    —— 黑字 + 極細白描邊（無底色框）
    第二行  得票率  —— 黑字疊在「該得票率所屬色階」的色片上（2px 黑外框）
    引線 = **單一條 #7F7F7F 灰線**（依使用者要求「只有灰線」，不墊白色襯線）；
    引線末端不停在區界線上，而是再往區內縮 TOWN_LABEL_LEADER_INSIDE_M 公尺，
    從「邊緣那個村里的範圍內」起引；引線也不許借道其他行政區（只會壓過本區
    自己那一段市界線）。
  * 29 區的初始落點寫在 MANUAL_LABEL_POS（語意是「區名那一行的中心」，由 maps/10/1.png
    量出），但**只當作起始位置**：任何落點只要離本區超過 TOWN_LABEL_MAX_GAP_M，
    就會被拉到「離本區最近的可放白地」，讓地名貼著它指向的行政區（依使用者要求）。

執行：
    py Converge_to_map_new.py          # 產生 DATASETS 全部地圖
    py Converge_to_map_new.py 2010     # 只跑檔名／tag 含關鍵字的地圖
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

# 要生成的地圖：**只跑 2010 這一張**（其餘年份的設定已移除，見下方註解）
DATASETS = [
    {
        # 改用 compute_town_rates_2010.py 的輸出（含得票數／有效票數A），
        # 區級標註才能走「Σ得票數 ÷ Σ有效票數」的人口加權，而非村里得票率平均
        "excel": os.path.join(EXCEL_DIR, "2010新北_各區得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2010年市長選舉_得票率地圖.png"),
        "tag": "2010 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：蔡英文）",
        "title_lines": ["第一屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "蔡英文"],
    },
    # ── 只生成 2010 這一張地圖。──
    # 其餘年份（2014 / 2018 / 2022 / 2005 / 2001×3 / 1993 / 1997）的 DATASETS 設定已移除，
    # 要恢復時直接從 .workbuddy/backup_Converge_to_map_new_得票率標註版_20260928.py 取回那幾筆。
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 15, 32000   # 1px = 15m（依使用者要求；輸出約 7027×6671）
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
OUTER_LINE_PX = 6             # 市外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階：5% 級距固定色階表（35 / 40 / … / 100）=====================
# 每個色階表是「級距（%）→ 色碼」的對照表，級距鍵＝該階的**上界**。
# 分箱仍由該次選舉「村里領先者得票率」的實際範圍決定（見 build_bins），
# 配色則以「該分箱的上界」查本表（見 step_colors）：
#     55 以下 → 鍵 55、55-60 → 60、…、80-85 → 85；
#     末階「85 以上」往再深一階取（鍵 90）——表內沒有 90，就取「不小於它的最淺一階」＝100。
# 表內查不到鍵（資料範圍跑出表外）時，一律夾到表的最淺／最深一階。
RATE_COLOR_RAMPS = [
    {   # 第 1 組：中國國民黨候選人
        35: "#D9F6FF",
        40: "#A6E9FF",
        45: "#73D9FF",
        50: "#40C8FF",
        55: "#00C0F4",
        60: "#00A2E8",
        65: "#0080B8",
        70: "#006591",
        75: "#004B6B",
        80: "#003247",
        85: "#001F2E",
        100: "#010D29",
    },
    {   # 第 2 組：民主進步黨候選人
        35: "#E8FFE0",
        40: "#CEFFC2",
        45: "#C0FFB1",
        50: "#A4FF90",
        55: "#78FF4F",
        60: "#68DE45",
        65: "#54B337",
        70: "#3C8027",
        75: "#2B5C1C",
        80: "#1D3D13",
        85: "#0F210A",
        100: "#071A09",
    },
    {   # 第 3 組（備用；青色系，於同樣 12 個級距上等距內插）
        35: "#00EBD1",
        40: "#00DDC5",
        45: "#00CEB9",
        50: "#00C0AD",
        55: "#00B1A1",
        60: "#00A395",
        65: "#009488",
        70: "#00867C",
        75: "#007770",
        80: "#006964",
        85: "#005A58",
        100: "#004C4C",
    },
]
BIN_STEP = 5                  # 色階級距（%）
MAX_BINS = 8                  # 色階數上限：長尾資料（如眷村村里飆到 9 成）不該把階數撐爆，
                              # 超出部分一律併入末階開放的「X <」箱

# ---- 圖例：浮貼於地圖右下角的圓角方框（標題置於框內頂部）----
LG_SW_W, LG_SW_H = 190, 92    # 色塊寬 / 高
LG_ROW_GAP = 30               # 色塊列與列之間的間距
LG_COL_GAP = 76               # 候選人色塊欄之間的間距
LG_LABEL_GAP = 40             # 區間標籤與第一排色塊的間距
LG_PAD = 32                  # 框內四周留白
LG_TITLE_GAP = 30             # 框內標題與候選人名稱的間距
LG_CAND_GAP = 34              # 候選人名稱與第一列色塊的間距
LG_BORDER_W = 4               # 框線寬
LG_BORDER_RADIUS = 34         # 圓角半徑
LG_BORDER_COLOR = "#3C3C3C"   # 框線顏色
LG_BG = "#FFFFFF"             # 框底色
LG_MARGIN = 60                # 方框與畫布右下角的邊距
LG_SW_OUTLINE = "#222222"     # 色塊描邊色
LG_SW_OUTLINE_W = 2           # 色塊描邊寬

# ---- 所有文字皆以 Print_word.py 方式輸出，以下字級可依需求適度調整 ----
TITLE_FONT_SIZE = 60         # 圖例框內標題字級
TITLE_LINE_RATIO = 1.35      # 標題行距／字級（多行標題要收緊，否則框太高）
CAND_NAME_FONT_SIZE = 56     # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE = 50  # 圖例區間標籤（55 以下、55-60…85 以上）字級
NO_DATA_FONT_SIZE = 44       # 無資料說明字級

# ---- 鄉鎮市區標註（區名 + 領先者得票率色片）----
# 版式取自參考圖 maps/10/1.png：第一行「區名」是黑字（只加極細白描邊、沒有底色框），
# 第二行「得票率」是黑字疊在該得票率色階的色片上。
# 依使用者要求：區名字級再縮小、區名與色片間距再收緊、色片**不加黑外框**。
TOWN_LABEL_FONT = "GenSekiGothic TW H"   # 源真ゴシック（可變字型，H 軸 = Heavy）
TOWN_LABEL_FONT_PATH = r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf"
TOWN_LABEL_FONT_FALLBACK = r"C:\Windows\Fonts\msyhbd.ttc"
TOWN_NAME_FONT_SIZE = 34         # 區名（漢字）字級(px)：原本 53，依使用者要求再縮小
TOWN_RATE_FONT_SIZE = 44        # 得票率（數字）字級(px)：對齊參考圖的色片寬約 162px
TOWN_NAME_HALO_PX = 3            # 區名白色描邊(px)：白底上看不出來，壓深色填色仍可讀
TOWN_CHIP_PAD_X = 6              # 得票率色片左右留白(px)
TOWN_CHIP_PAD_Y = 4            # 得票率色片上下留白(px)
TOWN_CHIP_BORDER = 0             # 得票率色片外框寬(px)：0＝無外框（依使用者要求去掉黑框）
TOWN_NAME_GAP = 6                # 區名墨跡底緣 → 色片頂緣的距離(px)：原本 12，
                                 # 依使用者要求收緊（PIL 的文字框比實際墨跡高，故數字偏小）
TOWN_LABEL_TIGHT_PX = 8          # 標註框碰撞檢測的收縮量(px/側)：允許標註緊貼排列
TOWN_LABEL_LINE_RATIO = 1.15     # 行距／字級（保留給多行標註時使用）
TOWN_LABEL_PAD = 6               # 標註影像四周留白(px)，越小框越緊湊
TOWN_LABEL_HALO_WIDTH = 2.5      # 白色描邊寬度：黑字疊在深色填色上仍可讀
TOWN_LABEL_SMALL_KM2 = 35.0      # 面積小於此值 → 標註外置 + 引線（大面積區標在區內）
TOWN_LABEL_OFFSET_M = 6000       # 判不出方向時的預設外推距離（公尺）
TOWN_LABEL_DIR_ANGLES = 24       # 方向探測數（15° 一格，正東／北／西／南都取得到）
TOWN_LABEL_DIR_RADII_M = (500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000,
                          8000, 10000, 13000, 16000, 20000)   # 探測半徑（公尺）
TOWN_LABEL_DIR_MIN_RUN_M = 3000  # 只採「連續空白 ≥ 此深度」的方向（濾掉細縫與資料碎洞）
TOWN_LABEL_DIR_BIG_RUN_M = 20000 # 「大空白」門檻：探到最外圈仍空白＝海面或圖外
TOWN_LABEL_DIR_RADIAL_MAX_M = 8000  # 徑向方向上要在此距離內就碰到大空白，才優先採徑向
TOWN_LABEL_DIR_WIDTH_PROBE_M = 3000 # 檢查空白「寬不寬」時，從空白起點再往外多遠取樣
TOWN_LABEL_DIR_WIDTH_MIN = 4        # 5 個取樣點（0／±15°／±30°／±45°）至少幾個要是空白
TOWN_LABEL_MARGIN_PX = 6         # 標註不可超出地圖畫布邊緣
TOWN_LABEL_LEADER_FULL_M = 6000  # 引線短於此值→直接指向區中心（最清楚）；超過則把
                                 # 落點收到「標註→區中心」射線與區界的交點（線只畫到
                                 # 區界、方向仍指向區中心），避免橫貫整個區的長引線
TOWN_LABEL_LINE_W = 5            # 引線寬度（px）：**單一條灰線**
                                 # （原本是「2px 灰芯 + 外圍 3px 白襯線」，依使用者要求
                                 #   「灰線指的是只有灰線，原本的白線也改成灰線」，
                                 #   故取消白色襯線；總寬維持 5px，視覺重量不變）
TOWN_LABEL_LEADER_INSIDE_M = 800 # 引線末端「再往行政區內縮」的距離（公尺）：讓引線不要停在
                                 # 區界線上，而是從「邊緣那個村里的範圍內」起引（依使用者要求）
TOWN_LABEL_MAX_GAP_M = 1200      # 標註框與「本區幾何」的最大允許距離（公尺）：超過就自動搬到
                                 # 「離本區最近的可放白地」，讓地名盡量貼著它指向的行政區
                                 # （依使用者要求：地名要靠近指向的區域、不要被推開）。
                                 # 設成很大的值＝關掉這個拉近行為。
TOWN_LABEL_LEADER_AVOID_TOWNS = True  # 引線盡量不要借道其他行政區（借道就會壓到那一區的
                                      # 市界黑線）。內陸區（土城／板橋／中和…）四周全是別的
                                      # 行政區，最近的白色空隙一定要跨過鄰區才到得了，所以
                                      # 這是**偏好**不是硬限制：落點評分＝距離 + 借道數×
                                      # TOWN_LABEL_CROSS_PENALTY_PX，借道一區就得多近 2.4km 才划算。
TOWN_LABEL_CROSS_PENALTY_PX = 160     # 每借道一個行政區的距離罰分（px；160px＝2.4km）
MAP_PAD_FRAC_LABELS = 0.22       # 開啟區標註時的地圖留白比例：標註只能放在白色邊際，需足夠空間
LEADER_COLOR = (127, 127, 127)   # 引線顏色 #7F7F7F（中灰；依使用者指定）
TOWN_RATE_MODE = "auto"          # 區級得票率：auto / weighted / mean
# 手工指定標註落點：鍵為 town_core（去「鄉/鎮/市/區」後的核心名），值為 (x, y)，
# 座標系 EPSG:3826（TWD97 公尺），代表「**區名那一行的中心**」。
#
# 這裡 29 區的數值全部是從參考圖 maps/10/1.png **直接量出來**的：
#   1. 在 1.png 上偵測出 29 個「得票率色片」矩形（實心色塊 + 黑外框 + 塊內黑字數字），
#      色片尺寸一致（約 162 × 80 px）。
#   2. 用色片上方的地名墨跡和親手渲染的 29 個區名做模板比對 → 決定每個色片屬於哪一區
#      （並用「色片顏色 = 該區 2022 得票率所屬色階」做交叉驗證，29 區全數吻合）。
#   3. 實測「區名墨跡中心」落在色片頂緣上方 47px（三芝、石門兩處獨立量測一致），
#      故 區名中心 y = 色片頂緣 y − 47。
#   4. 像素 → 公尺：X = 262409.1 + px × 20，Y = 2814434.0 − py × 20。
#      （1.png 是 1px=20m 的圖；本腳本輸出後來改成 1px=15m，但落點以公尺儲存，
#        所以不受比例尺影響，圖上的相對位置仍然一樣。）
# 驗證方式：把量到的中心畫成十字線疊回 1.png，29 個都落在該行地名的正中。
#
# 這 29 個落點當作**起始位置**（先照它擺），但收尾時會被「拉近」步驟修正：
# 只要標註框離本區超過 TOWN_LABEL_MAX_GAP_M，就改放到「離本區最近的可放白地」，
# 讓地名貼著它指向的行政區（依使用者要求）。想固定某區的位置，就把它的距離
# 手動調到上限內，或把 TOWN_LABEL_MAX_GAP_M 設得很大。
# 要微調就直接改這裡的數字。
MANUAL_LABEL_POS = {
    "三峽": (282659, 2752934),      # 三峽區  189.6km2
    "三芝": (296239, 2798254),      # 三芝區   67.5km2
    "三重": (302679, 2777374),      # 三重區   18.0km2
    "中和": (304139, 2770694),      # 中和區   19.4km2
    "五股": (288199, 2788354),      # 五股區   34.3km2
    "八里": (286679, 2784734),      # 八里區   39.8km2
    "土城": (291019, 2745394),      # 土城區   29.9km2
    "坪林": (328999, 2750054),      # 坪林區  168.3km2
    "平溪": (324799, 2775454),      # 平溪區   71.2km2
    "新店": (308339, 2765034),      # 新店區  121.2km2
    "新莊": (287779, 2770394),      # 新莊區   20.7km2
    "板橋": (304139, 2773914),      # 板橋區   21.3km2
    "林口": (282279, 2782994),      # 林口區   54.3km2
    "樹林": (286819, 2767094),      # 樹林區   31.9km2
    "永和": (307279, 2768354),      # 永和區    6.2km2
    "汐止": (317769, 2779434),      # 汐止區   71.8km2
    "泰山": (284279, 2772554),      # 泰山區   18.1km2
    "淡水": (291359, 2792414),      # 淡水區   73.1km2
    "深坑": (310509, 2771174),      # 深坑區   20.9km2
    "烏來": (311809, 2740134),      # 烏來區  333.5km2
    "瑞芳": (335509, 2783254),      # 瑞芳區   72.2km2
    "石碇": (321659, 2745874),      # 石碇區  141.9km2
    "石門": (314459, 2799294),      # 石門區   53.0km2（依使用者要求，由 1.png 量測值往西北移 500m）
    "萬里": (322779, 2791394),      # 萬里區   63.6km2
    "蘆洲": (299179, 2780234),      # 蘆洲區    7.7km2
    "貢寮": (345909, 2773594),      # 貢寮區  101.8km2
    "金山": (316159, 2795154),      # 金山區   47.7km2
    "雙溪": (337979, 2758914),      # 雙溪區  145.7km2
    "鶯歌": (280659, 2762634),      # 鶯歌區   21.8km2
}

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

def build_bins(min_rate, max_rate, step=BIN_STEP, max_bins=MAX_BINS):
    """依「領先者得票率」的實際範圍切出 step% 一階的分箱。

    首階標「55 以下」、末階標「85 以上」（開放區間），中間為閉區間。
    例：領先者得票率落在 50.2%~63.9% → 邊界 55、60、65 →
        [55以下, 55-60, 60-65, 65以上] 共 4 階。
    階數超過 max_bins 時（長尾資料），把末階上界往回收，超出的極端值併入
    開放的末階——否則幾個眷村村里就能把圖例撐到十幾階。
    回傳 [(下界, 上界, 標籤), ...]；下界 None＝開放，上界 None＝開放。
    """
    b0 = int(np.floor(min_rate / step) * step) + step      # 首階上界
    bk = int(np.ceil(max_rate / step) * step)              # 末階之前的最後一個邊界
    bk = min(bk, b0 + (max_bins - 2) * step)               # 上限：首階 + 末階 + 中間
    if bk < b0 + step:                                     # 全部落在同一階
        return [(None, b0, f"{b0} 以下")]
    bounds = list(range(b0, bk + 1, step))
    bins = [(None, bounds[0], f"{bounds[0]} 以下")]
    for i in range(1, len(bounds)):
        bins.append((bounds[i - 1], bounds[i], f"{bounds[i - 1]}-{bounds[i]}"))
    bins.append((bounds[-1], None, f"{bounds[-1]} 以上"))
    return bins

def bin_index(val, bins):
    """回傳數值落在第幾個分箱；超出範圍者歸給首／末箱。"""
    for j, (lo, hi, _lab) in enumerate(bins):
        if lo is None:
            if val <= hi:
                return j
        elif hi is None:
            if val > lo:
                return j
        elif lo < val <= hi:
            return j
    return len(bins) - 1

def step_colors(table, bins):
    """把「5% 級距 → 色碼」的色階表，展開成與 bins 逐一對應的色碼清單。

    查表鍵＝該分箱的上界（語意同 build_bins 的「X 以下 / X-Y / X 以上」；
    首階開放端為下界之上的那個級距、末階開放端再深一階 = 上界 + BIN_STEP）。
    級距鍵在表內沒有對應時，取「不小於該鍵的最淺一階」；連最深一階都不到，
    就直接用最深一階（表外的高／低端一律夾到表的最深／最淺色）。
    """
    keys = sorted(table)
    out, prev_hi = [], None
    for _lo, hi, _lab in bins:
        key = hi if hi is not None else (prev_hi if prev_hi is not None else keys[0]) + BIN_STEP
        if hi is not None:
            prev_hi = hi
        pick = next((k for k in keys if k >= key), keys[-1])
        out.append(table[pick])
    return out

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

def render_town_label(name, rate_txt=None, chip_hex=None):
    """鄉鎮市區標註影像：兩行堆疊（比照參考圖 maps/10/1.png）。

      第一行  區名     —— 黑字 + 極細白描邊，**不加底色框**
                          （白底上看不出描邊，壓到深色填色／黑色界線仍可讀）
      第二行  得票率   —— 黑字 ＋ chip_hex 色片（無外框），色片大小由文字決定
    chip_hex 為 None（或 rate_txt 為空）時退回「只有地名」的單行版。

    回傳 (RGBA 影像, 區名墨跡在影像中的中心 (x, y))。
    「區名墨跡中心」是給呼叫端定位用的：MANUAL_LABEL_POS 的語意就是這個點，
    排版／碰撞則用整張影像的方框，故兩者的換算集中在 plan_town_labels 一處。
    """
    key = (name, rate_txt, chip_hex)
    if key in _TOWN_LABEL_CACHE:
        return _TOWN_LABEL_CACHE[key]

    nf = _town_font(TOWN_NAME_FONT_SIZE)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    nw = probe.textlength(name, font=nf)
    na, nd = nf.getmetrics()
    nh = na + nd
    pad = TOWN_NAME_HALO_PX + 1          # 讓描邊不被裁掉

    if rate_txt and chip_hex:
        rf = _town_font(TOWN_RATE_FONT_SIZE)
        rw = probe.textlength(rate_txt, font=rf)
        ra, rd = rf.getmetrics()
        chip_w = int(round(rw)) + 2 * TOWN_CHIP_PAD_X
        chip_h = (ra + rd) + 2 * TOWN_CHIP_PAD_Y
        extra = TOWN_NAME_GAP + chip_h
    else:
        rf = rw = chip_w = chip_h = 0
        extra = 0

    W_ = int(max(int(round(nw)), chip_w) + 2 * pad)
    H_ = int(pad + nh + extra + pad)
    img = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- 第一行：區名（黑字 + 白描邊，無底色）----
    d.text(((W_ - nw) / 2, pad), name, font=nf, fill=(0, 0, 0),
           stroke_width=TOWN_NAME_HALO_PX, stroke_fill=(255, 255, 255))

    # ---- 第二行：得票率色片（TOWN_CHIP_BORDER=0 時不畫外框）----
    if chip_h:
        bx0 = (W_ - chip_w) / 2.0
        by0 = pad + nh + TOWN_NAME_GAP
        if TOWN_CHIP_BORDER > 0:
            d.rectangle([bx0, by0, bx0 + chip_w - 1, by0 + chip_h - 1],
                        fill=chip_hex, outline=(0, 0, 0), width=TOWN_CHIP_BORDER)
        else:
            d.rectangle([bx0, by0, bx0 + chip_w - 1, by0 + chip_h - 1],
                        fill=chip_hex)
        d.text((bx0 + (chip_w - rw) / 2.0, by0 + TOWN_CHIP_PAD_Y),
               rate_txt, font=rf, fill=(0, 0, 0))

    # ---- 量出區名墨跡中心（只算字本身，不含描邊）----
    mk = Image.new("L", (W_, H_), 0)
    ImageDraw.Draw(mk).text(((W_ - nw) / 2, pad), name, font=nf, fill=255)
    a = np.asarray(mk)
    ys, xs = np.nonzero(a > 128)
    name_c = (float(xs.min() + xs.max()) / 2.0, float(ys.min() + ys.max()) / 2.0)

    _TOWN_LABEL_CACHE[key] = (img, name_c)
    return img, name_c

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
def build_legend_box(bins, cand_names, bin_colors, title_lines):
    """組成「浮貼於地圖右下角」的圓角圖例方框，回傳 (RGBA 影像, (寬, 高))。

    版面（與參考圖一致）：
        框內標題（可多行，置中）
        候選人名稱（各自置中於自己的色塊欄上方）
        每一列＝區間標籤（右對齊）＋各候選人色塊
    色塊顏色由 bin_colors[候選人索引][分箱索引] 決定；框外為透明，貼上時不遮地圖。
    """
    title_img = (render_text_image_cached(title_lines, TITLE_FONT_SIZE,
                                          line_ratio=TITLE_LINE_RATIO)
                 if title_lines else None)
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    label_imgs = [render_text_image_cached([lb], LEGEND_LABEL_FONT_SIZE)
                  for _, _, lb in bins]
    name_h = max((im.height for im in name_imgs), default=0)
    label_w = max((im.width for im in label_imgs), default=0)

    n_col = len(cand_names)
    block_w = (label_w + LG_LABEL_GAP + n_col * LG_SW_W
               + (n_col - 1) * LG_COL_GAP)
    box_w = LG_PAD * 2 + block_w
    if title_img is not None:                       # 標題過長時由標題決定框寬
        box_w = max(box_w, title_img.width + LG_PAD * 2)

    rows_h = len(bins) * LG_SW_H + (len(bins) - 1) * LG_ROW_GAP
    box_h = (LG_PAD * 2 + name_h + LG_CAND_GAP + rows_h
             + ((title_img.height + LG_TITLE_GAP) if title_img is not None else 0))

    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([1, 1, box_w - 2, box_h - 2], radius=LG_BORDER_RADIUS,
                        fill=LG_BG, outline=LG_BORDER_COLOR, width=LG_BORDER_W)

    y = LG_PAD
    if title_img is not None:
        blit_rgba(canvas, title_img, ((box_w - title_img.width) // 2, y))
        y += title_img.height + LG_TITLE_GAP

    off = LG_PAD + max(0, (box_w - 2 * LG_PAD - block_w) // 2)   # 內容區塊置中
    label_right = off + label_w
    x_sw0 = label_right + LG_LABEL_GAP
    for i, nm in enumerate(name_imgs):
        x_sw = x_sw0 + i * (LG_SW_W + LG_COL_GAP)
        blit_rgba(canvas, nm, (x_sw + (LG_SW_W - nm.width) // 2, y))
    y += name_h + LG_CAND_GAP

    for j in range(len(bins)):
        y_row = y + j * (LG_SW_H + LG_ROW_GAP)
        blit_rgba(canvas, label_imgs[j],
                  (label_right - label_imgs[j].width,
                   y_row + (LG_SW_H - label_imgs[j].height) // 2))
        for i in range(n_col):
            x_sw = x_sw0 + i * (LG_SW_W + LG_COL_GAP)
            d.rectangle([x_sw, y_row, x_sw + LG_SW_W, y_row + LG_SW_H],
                        fill=bin_colors[i][j], outline=LG_SW_OUTLINE,
                        width=LG_SW_OUTLINE_W)
    return canvas, (box_w, box_h)

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

def _box_hits(box, placed):
    return any(not (box[2] <= o[0] or box[0] >= o[2] or box[3] <= o[1] or box[1] >= o[3])
               for o in placed)

def _shrink_box(b, s):
    """四邊各內縮 s px：讓標註可以緊貼排列（參考圖式的緊湊排版）。"""
    return (b[0] + s, b[1] + s, b[2] - s, b[3] - s)

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

def _geom_points(geom):
    """取出 Point／MultiPoint／GeometryCollection 內的所有 (x, y) 座標。"""
    if geom is None or geom.is_empty:
        return []
    gt = geom.geom_type
    if gt == "Point":
        return [(geom.x, geom.y)]
    out = []
    if gt in ("MultiPoint", "GeometryCollection"):
        for g in geom.geoms:
            out.extend(_geom_points(g))
    return out

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

def _wide_free(rp, direction, radius, free):
    """在 direction 上距 rp 半徑 radius 處，左右 ±15°／±30°／±45° 是否也都是空白。

    用來分辨「開闊地」與「細縫」：海岸／市界外的空白左右都空（海面、鄰縣），
    河川白廊與村里界之間的細縫則是左右都是填色——標註要的是前者。
    """
    a0 = np.arctan2(direction[1], direction[0])
    cnt = 0
    for da in (-np.pi / 4, -np.pi / 6, 0.0, np.pi / 6, np.pi / 4):
        th = a0 + da
        if free(rp.x + np.cos(th) * radius, rp.y + np.sin(th) * radius):
            cnt += 1
    return cnt >= TOWN_LABEL_DIR_WIDTH_MIN

def _outward_dir(geom, rp, city_prep, radial):
    """挑選本區標註「往外推」的方向，回傳 (單位方向, 離開本市的距離m, 是否為外圍區)。

    以區代表點為圓心，在 24 個方向 × 14 個半徑上探測該點是否落在本市之外，
    得到每個方向的「第一個空白半徑 r0」與「連續空白深度 run」。挑法：

      1. 徑向（地圖中心 → 本區中心）若在 TOWN_LABEL_DIR_RADIAL_MAX_M 內就碰到
         大空白（run ≥ TOWN_LABEL_DIR_BIG_RUN_M，即海面或圖外）→ 採徑向。
         北海岸的三芝／石門／金山／萬里就是這樣被推到各自海岸正外側的海上，
         四個標註排成一列。
      2. 否則採「r0 最小的合格方向」——內陸區（三重／中和／永和…）最近的空白
         通常是台北市那圈空缺或縣市界，標註貼著自己的區最好。
      3. 都不合格（四面都是填色）→ 退回徑向。

    為何不直接平均海岸線法線：本區與鄰縣的長邊界會把方向帶偏。萬里與基隆的
    交界長達 20km（94 個取樣點裡有 50 個朝南），平均下來方向變成東南，標註
    照樣被推進基隆的空缺處——比不改還糟。
    """
    from shapely.geometry import Point
    RAD = TOWN_LABEL_DIR_RADII_M
    NA = TOWN_LABEL_DIR_ANGLES

    def free(x, y):
        return not city_prep.contains(Point(x, y))

    found = []                       # (方向索引, r0, run, 單位向量)
    for a in range(NA):
        th = 2 * np.pi * a / NA
        cx, cy = np.cos(th), np.sin(th)
        i0 = -1
        for i, R in enumerate(RAD):
            if free(rp.x + cx * R, rp.y + cy * R):
                i0 = i
                break
        if i0 < 0:                   # 這個方向一路都是填色
            continue
        j = i0
        while j + 1 < len(RAD) and free(rp.x + cx * RAD[j + 1], rp.y + cy * RAD[j + 1]):
            j += 1
        # 把最後一圈之後再撐一環估進去；已撐到最外圈就當成無限延伸（海／圖外）
        run = (RAD[j + 1] if j + 1 < len(RAD) else RAD[j] * 4) - RAD[i0]
        found.append((a, RAD[i0], run, (cx, cy)))

    if not found:
        return radial, TOWN_LABEL_OFFSET_M, False

    rad_a = int(round((np.arctan2(radial[1], radial[0]) % (2 * np.pi)) /
                      (2 * np.pi / NA))) % NA
    for a, r0, run, d in found:
        if (a == rad_a and run >= TOWN_LABEL_DIR_BIG_RUN_M
                and r0 <= TOWN_LABEL_DIR_RADIAL_MAX_M
                and _wide_free(rp, radial, r0 + TOWN_LABEL_DIR_WIDTH_PROBE_M, free)):
            return radial, float(r0), True

    ok = [(r0, -run, d) for a, r0, run, d in found if run >= TOWN_LABEL_DIR_MIN_RUN_M]
    if ok:
        r0, _, d = min(ok)
        return d, float(r0), False
    return radial, TOWN_LABEL_OFFSET_M, False

def plan_town_labels(gdf_plot, town_rates, xlim, ylim, w_px, h_px, y_off, city_geom=None,
                     chip_color=None, reserved=()):
    """依「已畫好的完整地圖」決定各鄉鎮市區標註的落點，並在像素層級做碰撞避讓。

    流程（皆以完整地圖為基準）：
      1. 溶出各區幾何、算面積。標註＝「區名 + 領先者得票率色片」兩行 + 引線。
      2. 標註一律不得壓在地圖填色區上（city_geom 以外），故候選落點以
         「貼著本區近距螺旋」優先（引線最短），往外成長直到進入白色區域。
      3. 逐區在像素層級檢查：不與已放置標註重疊、不出血、不壓填色區；
         不合則繼續往外圈試，最後全畫布網格掃描。
      4. 全部標註皆為外置 + 引線（引線可壓填色區）。
      5. MANUAL_LABEL_POS 內的區（本檔＝全部 29 區）**無條件照用**：不檢查重疊／
         填色、不參與自動排版與二次修正。這樣輸出才會和參考圖 1.png 完全一致。

    chip_color  (callable) 得票率色片配色：chip_color(候選人索引, 得票率) → 色碼；
                          None 時退回「只寫地名」的單行標註。
    reserved    (list)   一開始就視為已佔用的矩形（如右下角圖例方框），
                         標註與引線都會避開，避免被圖例蓋住

    town_rates  仍傳入，只作為「這區有沒有得票資料」的判斷（無資料者不標名）；
                標註本身不再顯示得票率。
    reserved    (list)   一開始就視為已佔用的矩形（如右下角圖例方框），
                         標註與引線都會避開，避免被圖例蓋住
    """
    from shapely.geometry import box as shp_box
    from shapely.geometry import LineString as shp_LineString
    from shapely.prepared import prep

    # 方向探測要做上萬次「這點在不在本市內」的判定，用 prepared 幾何才夠快
    # （市界有一萬多個頂點）。
    city_prep = prep(city_geom) if city_geom is not None else None
    # LABEL_DEBUG=三芝,萬里（或 =1 全部）會印出各區的排版診斷，方便查「為何落在這裡」
    debug_want = {c.strip() for c in
                  os.environ.get("LABEL_DEBUG", "").replace("，", ",").split(",") if c.strip()}
    debug_all = bool(debug_want & {"1", "all", "ALL"})

    map_center = gdf_plot.geometry.union_all().centroid
    display_of = (gdf_plot.drop_duplicates("town_core")
                            .set_index("town_core")["TOWNNAME"].to_dict())
    src = gdf_plot[gdf_plot["town_core"].str.strip() != ""]
    gdf_town = src.dissolve(by="town_core").reset_index()
    gdf_town["area_km2"] = gdf_town.geometry.area / 1e6

    mpp = METERS_PER_PIXEL
    to_px, to_map = _xy_maps(xlim, ylim, w_px, h_px, y_off, mpp)
    m = TOWN_LABEL_MARGIN_PX

    # ---- 引線不得穿過其他行政區 ----
    # 引線由標註（白色邊際）走進本區，途中若借道別的行政區，就會壓過那一區的市界黑線
    # （依使用者要求：「引線要盡量少壓到各個行政區的邊界線」）。這裡把 29 區幾何各內縮
    # 1px 後建空間索引（內縮可避免「只是貼著共用邊界」被誤判），候選落點只要引線穿過
    # 任一「別的區」就淘汰。唯一允許穿越的是本區自己的區界——引線本來就得進本區。
    from shapely.strtree import STRtree
    _t_cores = list(gdf_town["town_core"])
    _t_geoms = [g.buffer(-mpp) for g in gdf_town.geometry]
    _t_tree = STRtree(_t_geoms) if TOWN_LABEL_LEADER_AVOID_TOWNS else None

    def seg_other_towns(p_px, q_px, own_core):
        """引線（像素座標的起點→終點）穿過哪些「本區以外」的行政區，回傳它們的 core。"""
        if _t_tree is None:
            return ()
        seg = shp_LineString([to_map(p_px[0], p_px[1]), to_map(q_px[0], q_px[1])])
        return tuple(_t_cores[i] for i in _t_tree.query(seg)
                     if _t_cores[i] != own_core and _t_geoms[i].intersects(seg))

    def seg_through_other(p_px, q_px, own_core):
        return bool(seg_other_towns(p_px, q_px, own_core))

    # 標註僅能落在白色區域：市界往外擴一點（涵蓋外框黑帶與文字白描邊）後，
    # 候選框與之交疊即淘汰。prepared 加速大量候選的相交測試。
    city_free = None
    if city_geom is not None:
        # 只留極小餘量：參考圖的標註允許壓在市界黑線上、緊貼色塊邊緣，
        # 中部河川空隙也要能放標註，故緩衝儘量小。
        city_free = prep(city_geom.buffer(20))

    def box_off_city(box):
        """標註框是否完全落在白色區域（不與地圖填色範圍交疊）。"""
        if city_free is None:
            return True
        x0 = to_map(box[0], 0)[0]
        x1 = to_map(box[2], 0)[0]
        ytop = to_map(0, box[1])[1]
        ybot = to_map(0, box[3])[1]
        return not city_free.intersects(shp_box(x0, ybot, x1, ytop))

    def gap_px(j, cx, cy):
        """標註框到「本區」幾何的最短距離（像素；框壓在本區上時為 0）。

        排版偏好一律看這個值，而不是引線長度：引線會被裁短到區界
        （超過 TOWN_LABEL_LEADER_FULL_M 的落點一律裁成一樣長），距離差好幾倍的
        候選因此在「引線最短」的比較裡打平，遠處的怪落點就有機會僥倖勝出
        ——萬里被丟到基隆空缺處就是這樣來的。量真正的距離就沒這個問題。
        """
        w, h = j["text"].width, j["text"].height
        x0 = to_map(cx - w / 2, 0)[0]
        x1 = to_map(cx + w / 2, 0)[0]
        y1 = to_map(0, cy - h / 2)[1]
        y0 = to_map(0, cy + h / 2)[1]
        return j["geom"].distance(shp_box(x0, y0, x1, y1)) / mpp

    jobs = []
    for _, r in gdf_town.iterrows():
        core = r["town_core"]
        vals = town_rates.get(core)
        if not vals:
            continue
        vals = [np.nan if v is None or pd.isna(v) else float(v) for v in vals]
        if all(np.isnan(v) for v in vals):
            continue
        geom = r.geometry
        rp = geom.representative_point()
        km2 = float(r["area_km2"])
        manual = core in MANUAL_LABEL_POS

        if manual:
            lx, ly = MANUAL_LABEL_POS[core]
            is_outward = True
            odir = None                       # 手工位置不指定方向，稍後由落點反推
        else:
            # 外推方向：見 _outward_dir。北海岸的萬里若用「地圖中心→本區」的純徑向，
            # 會被推進東南方基隆的空缺處（離本區海岸十幾公里），故以「徑向上有無
            # 大片空白」優先判斷，並把起點擺在「剛離開本區」的位置。
            vx, vy = rp.x - map_center.x, rp.y - map_center.y
            n = (vx * vx + vy * vy) ** 0.5 or 1.0
            radial = (vx / n, vy / n)
            if city_prep is not None:
                odir, exit_m, is_outward = _outward_dir(geom, rp, city_prep, radial)
            else:
                odir, exit_m, is_outward = radial, TOWN_LABEL_OFFSET_M, False
            lx = rp.x + odir[0] * exit_m
            ly = rp.y + odir[1] * exit_m

        name = str(display_of.get(core, core))
        lead = int(np.nanargmax(vals))
        chip_hex = chip_color(lead, vals[lead]) if chip_color else None
        # 版式＝「區名 + 領先者得票率色片」兩行
        txt, name_c = render_town_label(name, f"{vals[lead]:.1f}%", chip_hex)
        cpx, cpy = to_px(lx, ly)
        # MANUAL_LABEL_POS 的語意是「區名那一行的中心」，但排版／碰撞一律以整張標註
        # 影像的方框（含色片）為準，這裡把兩者換算過去：
        #   方框中心 = 區名中心 + (影像中心 − 區名墨跡中心)
        cpx += txt.width / 2.0 - name_c[0]
        cpy += txt.height / 2.0 - name_c[1]
        # 引線方向：由本區代表點指向標註落點（像素座標 y 軸向下，故取負）。
        # 手工位置（odir is None）與自動排版共用同一條式子，落點＝代表點時退回 odir。
        vx2, vy2 = (lx - rp.x), (ly - rp.y)
        n2 = (vx2 * vx2 + vy2 * vy2) ** 0.5
        if n2 < 1.0:
            vx2, vy2 = (odir if odir is not None else (0.0, 1.0))
            n2 = (vx2 * vx2 + vy2 * vy2) ** 0.5 or 1.0
        odir_eff = (vx2 / n2, vy2 / n2)
        ux, uy = odir_eff[0], -odir_eff[1]
        d_center = ((rp.x - map_center.x) ** 2 +
                    (rp.y - map_center.y) ** 2) ** 0.5    # 區代表點至地圖中心距離
        jobs.append(dict(core=core, name=name, geom=geom, rp=rp, text=txt,
                         name_c=name_c,
                         cx=cpx, cy=cpy, ux=ux, uy=uy, odir=odir_eff, km2=km2,
                         d_center=d_center, outward=is_outward,
                         external=True,
                         how="manual" if manual else "auto",
                         hugged=False, crowded=False, cands=[]))

    # 分類：外圍區（徑向方向上就是大片空白——沿海／沿市界的三芝、石門、金山、萬里、
    # 貢寮、烏來…）優先往市界外側推；內陸區（三重／中和／永和／板橋…，最近的空白是
    # 台北市那圈空缺）優先貼著本區。判定見 _outward_dir（回傳的 is_outward）。
    # 大面積先定位：小面積的標註才有空間往邊際推。處理順序（使用者指定流程）：
    #   ① 手工指定位置最先放（必須搶到指定spot）
    #   ② 外圍區先放——優先試探外圍白邊能否容納
    #   ③ 內陸區最後放，且「離地圖中心越近越先放」：
    #      最內團（永和／中和／三重／板橋／新店）先搶佔台北空隙沿線的窄位，
    #      外圍內陸區（新莊／樹林／泰山等）再落到外側——形成參考圖式環狀排佈
    def _sort_key(j):
        if j["core"] in MANUAL_LABEL_POS:
            return (0, 0.0)
        if j["outward"]:
            return (1, j["km2"])          # 外圍區：小面積優先（可落點少、最受限）
        return (2, j["d_center"])         # 內陸區：越靠近地圖核心越先放

    jobs.sort(key=_sort_key)

    placed = [tuple(b) for b in reserved]   # 預留區（圖例方框）先佔位，標註一律避開
    placed_leaders = []          # (core, (起點, 終點)) 已確定的引線，供交叉檢查

    def box_of(j):
        w, h = j["text"].width, j["text"].height
        return _box(j["cx"], j["cy"], w, h)

    def leader_of(j, cx, cy, obstacles):
        """回傳該落點的引線 (起點, 終點)；標註壓在區上、或距區太近不需引線則 None。"""
        w, h = j["text"].width, j["text"].height
        a = _leader_anchor(j["geom"], j["rp"], cx, cy, w, h, to_map, to_px, obstacles)
        if a is None:
            return None
        return _box_edge_point(cx, cy, a[0], a[1], w, h), a

    def try_place(j, c, w, h, placed_boxes):
        """評估單一候選落點；可行則回傳 (box, leader, 距本區距離px)，不可行回傳 None。

        可行條件：不出血、不壓填色區、不與已放置標註重疊；引線不穿任何
        已放置標註框、不與任何已確定引線交叉（含共線重合）。
        """
        box = _box(c[0], c[1], w, h)
        if box[0] < m or box[1] < m or box[2] > w_px - m or box[3] > h_px - m:
            return None
        if not box_off_city(box) and j["core"] not in MANUAL_LABEL_POS:
            return None
        if _box_hits(_shrink_box(box, TOWN_LABEL_TIGHT_PX),
                     [_shrink_box(b, TOWN_LABEL_TIGHT_PX) for b in placed_boxes]):
            return None
        ln = leader_of(j, c[0], c[1], placed_boxes)
        n_cross = 0
        if ln is not None:
            p, q = ln
            if any(_seg_hits_box(p, q, ob) for ob in placed_boxes):
                return None
            for core2, s2 in placed_leaders:
                if core2 != j["core"] and _seg_cross(p, q, s2[0], s2[1]):
                    return None
            n_cross = len(seg_other_towns(p, q, j["core"]))     # 借道幾個別的行政區
        g = gap_px(j, c[0], c[1])               # 無引線（蓋住本區）時 gap 亦為 0
        return box, ln, g, g + TOWN_LABEL_CROSS_PENALTY_PX * n_cross

    for j in jobs:
        w, h = j["text"].width, j["text"].height
        ux, uy = j["ux"], j["uy"]

        if j["core"] in MANUAL_LABEL_POS:
            # 手工落點＝參考圖 1.png 量出來的位置，**無條件採用**：不做出血／壓填色／
            # 重疊檢查，也不進二次修正（下方各迴圈都會跳過 MANUAL 的區）。否則演算法
            # 會為了避讓把標註搬走，就對不上參考圖了——參考圖本身就有幾處標註緊靠
            # （泰山／新莊、三重／蘆洲）。
            box = box_of(j)
            j["gap_px"] = gap_px(j, j["cx"], j["cy"])
            j["external"] = True
            placed.append(tuple(box))
            ln = leader_of(j, j["cx"], j["cy"], placed)
            if ln is not None:
                placed_leaders.append((j["core"], ln))
            continue

        # 候選分組，組序依「外緣區優先外推、內陸區優先貼區」排列：
        #   out  往市界外側外推（方向＝本區海岸線／縣市界法線）
        #   near 貼區螺旋（近→遠，引線短）
        #   inn  往市界內側收、glob 全域螺旋（最後手段）
        jrp = j["rp"]
        rpx, rpy = to_px(jrp.x, jrp.y)
        base = max(w, h) * 0.5
        near = []
        for k in range(1, 21):                                   # 貼區螺旋（近→遠，細半徑成長找窄縫）
            rad = base * (1.22 ** (k - 1))
            for a in range(24):
                th = 2 * np.pi * a / 24 + k * 0.41
                near.append((rpx + rad * np.cos(th), rpy + rad * np.sin(th)))
        # 外推候選：起始落點已在「剛離開本區」的位置（見 _outward_dir 的 exit_m），
        # 沿外推方向以約一個標註高的間距往外佈點，愈遠間距愈大。
        step = h * 1.06
        out = [(j["cx"] + ux * k * step, j["cy"] + uy * k * step)
               for k in (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 19)]
        inn = [(j["cx"] - ux * k * h * 1.06, j["cy"] - uy * k * h * 1.06)
               for k in (0, 1, 2, 3, 4, 6, 8, 11)]
        r, nang = h * 1.06, 12
        glob = []
        for k in range(1, 14):                                   # 全域螺旋散開
            for a in range(nang):
                th = 2 * np.pi * a / nang + k * 0.37
                glob.append((j["cx"] + r * k * np.cos(th), j["cy"] + r * k * np.sin(th)))
        if j["core"] in MANUAL_LABEL_POS:
            groups = [[(j["cx"], j["cy"])], out + near + inn + glob]
        elif j["outward"]:                                       # 外圍區：先外後貼區
            groups = [out, near, inn, glob]
        else:                                                    # 內陸區：先貼區後外推
            groups = [near, out, inn, glob]
        j["groups"] = groups

        chosen = None
        chosen_gi = -1
        feasible_n = []
        for gi, group in enumerate(groups):
            best_g = None
            ok_n = 0
            for c in group:
                res = try_place(j, c, w, h, placed)
                if res is None:
                    continue
                ok_n += 1
                if best_g is None or res[3] < best_g[3]:         # 評分＝距本區距離 + 借道罰分
                    best_g = res
                if gi > 0:                                       # 後備組取首個可行即可
                    break
            feasible_n.append(ok_n)
            if best_g is not None:
                chosen = best_g
                chosen_gi = gi
                break

        if chosen is None:                                       # 全畫布網格掃描
            step_x, step_y = max(int(w * 0.25), 4), max(int(h * 0.25), 4)
            for yc in range(int(m), int(h_px - m - h), step_y):
                for xc in range(int(m), int(w_px - m - w), step_x):
                    res = try_place(j, (xc + w / 2, yc + h / 2), w, h, placed)
                    if res is not None:
                        chosen = res
                        break
                if chosen:
                    break

        if chosen:
            box, ln, _L = chosen[0], chosen[1], chosen[2]
            j["cx"], j["cy"] = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        else:
            j["crowded"] = True
            box = _box(j["cx"], j["cy"], w, h)
            ln = leader_of(j, j["cx"], j["cy"], placed)
        placed.append(box)
        if ln is not None:
            placed_leaders.append((j["core"], ln))

        if debug_all or j["core"] in debug_want:
            print(f"    [debug] {j['name']:<4} 外圍={j['outward']}"
                  f" 外推方向=({ux:+.2f},{uy:+.2f}) 區代表點=({rpx:.0f},{rpy:.0f})"
                  f" 用組={chosen_gi}(0=首選) 各組可行數={feasible_n}"
                  f" 落點=({j['cx']:.0f},{j['cy']:.0f})"
                  f" 距本區={gap_px(j, j['cx'], j['cy']) * mpp / 1000:.1f}km"
                  + ("  << 找不到落點、接受重疊" if j["crowded"] else ""))

    # 二次修正：標註框彼此不重疊，但引線仍可能被別的標註（連同不透明白描邊）壓掉，
    # 或兩條引線彼此交叉。對這些標註重新挑一個落點：新落點不但框不重疊，引線也
    # 不穿過任何其他標註框、不與其他引線交叉。
    m = TOWN_LABEL_MARGIN_PX
    reserved_boxes = [tuple(b) for b in reserved]
    for _round in range(6):
        boxes = {j["core"]: box_of(j) for j in jobs}
        all_others = {j["core"]: ([boxes[o["core"]] for o in jobs if o is not j]
                                  + reserved_boxes) for j in jobs}
        leaders = {}
        for o in jobs:
            if o["core"] in MANUAL_LABEL_POS or not o["external"]:
                continue
            lo = leader_of(o, o["cx"], o["cy"], all_others[o["core"]])
            if lo is not None:
                leaders[o["core"]] = lo

        def leader_crosses(core, seg):
            p, q = seg
            for c2, s2 in leaders.items():
                if c2 == core:
                    continue
                if _seg_cross(p, q, s2[0], s2[1]):
                    return True
            return False

        moved = 0
        for j in jobs:
            if j["core"] in MANUAL_LABEL_POS or not j["external"]:
                continue
            others = all_others[j["core"]]
            ln = leader_of(j, j["cx"], j["cy"], others)
            cur_bad = False
            if ln is not None:
                p, q = ln
                if any(_seg_hits_box(p, q, ob) for ob in others):
                    cur_bad = True
                elif leader_crosses(j["core"], ln):
                    cur_bad = True
            if not cur_bad:
                continue
            w, h = j["text"].width, j["text"].height
            jrp = to_px(j["rp"].x, j["rp"].y)
            d_cur = ((j["cx"] - jrp[0]) ** 2 + (j["cy"] - jrp[1]) ** 2) ** 0.5
            d_cap = max(d_cur * 1.2, 700.0)   # 換位不可離本區更遠（引線從區中心出發，寧可短線被壓）
            for group in j["groups"]:
                best_g = None
                for c in group:
                    box = _box(c[0], c[1], w, h)
                    if box[0] < m or box[1] < m or box[2] > w_px - m or box[3] > h_px - m:
                        continue
                    if not box_off_city(box) and j["core"] not in MANUAL_LABEL_POS:
                        continue
                    if ((c[0] - jrp[0]) ** 2 + (c[1] - jrp[1]) ** 2) ** 0.5 > d_cap:
                        continue
                    if _box_hits(_shrink_box(box, TOWN_LABEL_TIGHT_PX),
                                 [_shrink_box(b, TOWN_LABEL_TIGHT_PX) for b in others]):
                        continue
                    ln2 = leader_of(j, c[0], c[1], others)
                    if ln2 is not None:
                        p2, q2 = ln2
                        if any(_seg_hits_box(p2, q2, ob) for ob in others):
                            continue
                        if leader_crosses(j["core"], ln2):
                            continue
                    # ln2 為 None 代表標註直接蓋住本區、無需引線——不會壓到別人，
                    # 反而是最優解，不可當成無效候選跳過（曾因此把標註推到遠處）
                    d_gap = gap_px(j, c[0], c[1])
                    if best_g is None or d_gap < best_g[2]:      # 離本區最近優先
                        best_g = (c, box, d_gap)
                    if group is not j["groups"][0]:              # 後備組取首個可行即可
                        break
                if best_g is not None:
                    c = best_g[0]
                    j["cx"], j["cy"] = c
                    boxes[j["core"]] = _box(c[0], c[1], w, h)   # 立刻更新，否則本輪後續標註
                    moved += 1                                    # 會對著舊框判斷而挪進重疊處
                    break
            else:
                continue
        if not moved:
            break

    # ---- 引線終點：指向區中心，過長則收到「區界」----
    # 「引線指向區中心」在多數情況下最清楚；但當標註離本區中心很遠時——例如烏來／
    # 石碇／坪林這類大面積山區（中心深藏在區內，標註卻只能擺在區界外的白地）、或
    # 標註被外推到圖幅邊緣——引線會橫貫整個區、又長又亂。這種情況把落點收到
    # 「標註中心 → 區中心」射線與本區邊界的交點：線只畫到區界、方向仍指向區中心，
    # 長度大幅縮短，也不會指錯區（參考圖的長引線同樣只到區界）。
    def anchor_at(j, cx, cy, refine=False):
        """回傳該落點的引線終點（像素）；None 表示標註已蓋住/貼住本區、免引線。

        refine=True 時連「只有一個交點」也做幾何自檢（確認往區內縮之後真的落在本區
        裡面）；排版搜尋期間（呼叫上千次）單一交點不做自檢以省時間。
        """
        w, h = j["text"].width, j["text"].height
        bx = _box(cx, cy, w, h)
        rp_px = to_px(j["rp"].x, j["rp"].y)
        if bx[0] <= rp_px[0] <= bx[2] and bx[1] <= rp_px[1] <= bx[3]:
            return None                                   # 標註就壓在本區上，免引線
        d_m = ((cx - rp_px[0]) ** 2 + (cy - rp_px[1]) ** 2) ** 0.5 * mpp
        if d_m <= TOWN_LABEL_LEADER_FULL_M:
            return rp_px                                  # 線不長，直接指區中心
        lx, ly = to_map(cx, cy)                           # 標註中心（投影座標）
        seg = shp_LineString([(j["rp"].x, j["rp"].y), (lx, ly)])
        # 區界先簡化（100m 容差，每個區只算一次）再求交點：足夠精確且快得多
        edge = j.get("edge_s")
        if edge is None:
            edge = j["edge_s"] = j["geom"].simplify(mpp * 5).boundary
        pts = _geom_points(edge.intersection(seg))
        if not pts:
            return rp_px
        # 取離標註最近的交點：由標註看過去「進入本區」的位置（凹形區可能多個交點）
        pts_sorted = sorted(pts, key=lambda p: (p[0] - lx) ** 2 + (p[1] - ly) ** 2)

        # 引線末端再往區內縮一段（方向朝區中心，且不越過區中心）：依使用者要求，
        # 引線不要停在區界線上，改從「行政區靠裡一點」的位置起引。
        #
        # 凹形／楔形區常有多個交點，而「離標註最近」的那個可能只是本區伸出的一片
        # 窄尖角，往內推立刻又穿出去（實例：泰山區西側尖角僅約 200m 寬，再往西就是
        # 桃園市，所以舊版引線會退化成「幾乎貼在區界上」）。故對每個交點都試推：
        # 優先取「第一個能推滿 TOWN_LABEL_LEADER_INSIDE_M 的交點」（＝真正進到本區
        # 主要範圍的那一個），都推不滿時取推得最遠的，全推不進去才退回交點本身。
        FRACS = (1.0, 0.8, 0.6, 0.45, 0.3, 0.2, 0.12, 0.06)
        multi = len(pts_sorted) > 1

        def _gv():
            gv = j.get("geom_v")
            if gv is None:
                gv = j["geom_v"] = j["geom"].buffer(0)
            return gv

        def _push(qx, qy):
            """回傳 ((落點), 推距)；完全推不進去＝(None, 0.0)。"""
            vx, vy = j["rp"].x - qx, j["rp"].y - qy
            vn = (vx * vx + vy * vy) ** 0.5
            if vn <= 1e-6:
                return (qx, qy), 0.0
            st = min(TOWN_LABEL_LEADER_INSIDE_M, vn)
            gv = _gv()
            for frac in FRACS:
                d = st * frac
                px_, py_ = qx + vx / vn * d, qy + vy / vn * d
                if gv.contains(Point(px_, py_)):
                    return (px_, py_), d
            return None, 0.0

        # 交點離標註太近（此時標註已貼住區界）→ 免引線
        _qx0, _qy0 = pts_sorted[0]
        _ax0, _ay0 = to_px(_qx0, _qy0)
        if bx[0] <= _ax0 <= bx[2] and bx[1] <= _ay0 <= bx[3]:
            return None

        if not multi and not refine:
            # 單一交點且只是排版搜尋（呼叫上千次）：不做幾何自檢以省時間，直接推滿
            # ——與舊行為相同。
            pt_, _ = _push(pts_sorted[0][0], pts_sorted[0][1])
            if pt_ is None:
                pt_ = pts_sorted[0]
            ax, ay = to_px(pt_[0], pt_[1])
            return (ax, ay)

        full_pt = None
        best_d, best_pt = -1.0, None
        for qx_, qy_ in pts_sorted:
            pt_, d_ = _push(qx_, qy_)
            if pt_ is None:
                continue                              # 這個交點完全推不進去 → 換下一個
            if d_ >= TOWN_LABEL_LEADER_INSIDE_M - 1e-6:
                full_pt = pt_                         # 這個交點可以推滿 → 就用它
                break
            if d_ > best_d:
                best_d, best_pt = d_, pt_
        tx_, ty_ = full_pt or best_pt or pts_sorted[0]
        ax, ay = to_px(tx_, ty_)
        return (ax, ay)

    # ---- 收尾：離本區過遠者，搬到「離本區最近的可放白地」----
    # 依使用者要求「各地名要盡量靠近它指向的行政區、不要被推開」：**所有**標註（含
    # MANUAL_LABEL_POS 的落點）只要「標註框離本區」超過 TOWN_LABEL_MAX_GAP_M，就改用
    # 細環逐圈外擴搜索可放點，明顯拉近才搬（且須維持既有版面約束：不壓填色區、
    # 不與其他標註重疊、引線不穿標註框／不交叉其他引線）。
    # 原本 MANUAL_LABEL_POS 是指參考圖 1.png 量到的位置，但那份版面把好幾區推得很遠
    # （土城 13km、石碇／五股 6.7km、板橋 4.3km、泰山／中和 2.6km），故改為「先照手工
    # 落點擺，再拉近」——近的維持、遠的收回本區旁邊。
    # 手工落點的參考價值仍在：它決定「先擺哪裡」，也是尋找新位子時 d_cap 的基準。
    # 用「標註框到本區的距離」而非引線長度當判準：引線會被裁短到區界，距離遠近
    # 在引線長度上分不出來（見 gap_px 的說明）。
    gap_cap = TOWN_LABEL_MAX_GAP_M / mpp
    GAP_GAIN_PX = 25.0               # 至少拉近 25px（0.375km）才值得搬動，避免來回抖動
    for _round in range(6):
        boxes = {t["core"]: _box(t["cx"], t["cy"], t["text"].width, t["text"].height)
                 for t in jobs}
        anchors = {t["core"]: anchor_at(t, t["cx"], t["cy"]) for t in jobs}
        jobs_by_core = {t["core"]: t for t in jobs}

        def leader_span(j, cx, cy):
            """該落點的引線 (像素起點, 終點)；None 表免引線。"""
            a = anchor_at(j, cx, cy)
            if a is None:
                return None
            w, h = j["text"].width, j["text"].height
            return _box_edge_point(cx, cy, a[0], a[1], w, h), a

        def key_of(j, cx, cy, span):
            """落點評分＝離本區距離 + 借道罰分×借道數（愈小愈好）。
            借道＝引線穿過別的行政區（會壓過那一區的市界黑線）；因為內陸區的白色空隙
            幾乎都得跨過鄰區才到得了，這裡用罰分而不是禁止。"""
            g = gap_px(j, cx, cy)
            if span is None:
                return g
            return g + TOWN_LABEL_CROSS_PENALTY_PX * len(seg_other_towns(span[0], span[1], j["core"]))

        def fits(j, cx, cy, sink=None):
            """候選落點是否可行；可行則回傳 (評分, 距本區距離)、否則 None。
            sink（dict）給 LABEL_DEBUG 診斷用，會累計各項淘汰原因。"""
            def no(why):
                if sink is not None:
                    sink[why] = sink.get(why, 0) + 1
                return None

            w, h = j["text"].width, j["text"].height
            box = _box(cx, cy, w, h)
            if box[0] < m or box[1] < m or box[2] > w_px - m or box[3] > h_px - m:
                return no("出血")
            if not box_off_city(box):           # 手工落點也一樣：搬到新位子就得守規矩
                return no("壓填色")
            tin = _shrink_box(box, TOWN_LABEL_TIGHT_PX)
            if any(_box_hits(tin, [_shrink_box(b, TOWN_LABEL_TIGHT_PX)])
                   for c2, b in boxes.items() if c2 != j["core"]):
                return no("與他標註重疊")
            if any(_box_hits(tin, [_shrink_box(b, TOWN_LABEL_TIGHT_PX)])
                   for b in reserved_boxes):
                return no("壓圖例")
            span = leader_span(j, cx, cy)
            if span is None:
                return gap_px(j, cx, cy), gap_px(j, cx, cy)   # 標註就蓋在本區上，免引線
            (ex, ey), a2 = span
            for c2, b in boxes.items():
                if c2 != j["core"] and _seg_hits_box((ex, ey), a2, b):
                    return no("引線穿他標註")
            if any(_seg_hits_box((ex, ey), a2, b) for b in reserved_boxes):
                return no("引線穿圖例")
            for c2, s2 in anchors.items():
                if c2 == j["core"] or s2 is None:
                    continue
                p1 = _box_edge_point(jobs_by_core[c2]["cx"], jobs_by_core[c2]["cy"],
                                     s2[0], s2[1], jobs_by_core[c2]["text"].width,
                                     jobs_by_core[c2]["text"].height)
                if _seg_cross((ex, ey), a2, p1, s2):
                    return no("引線與他引線交叉")
            return key_of(j, cx, cy, span), gap_px(j, cx, cy)

        moved = 0
        order = sorted(jobs, key=lambda t: -gap_px(t, t["cx"], t["cy"]))
        for j in order:
            cur = key_of(j, j["cx"], j["cy"], leader_span(j, j["cx"], j["cy"]))
            if gap_px(j, j["cx"], j["cy"]) <= gap_cap:
                continue
            w, h = j["text"].width, j["text"].height
            rpx, rpy = to_px(j["rp"].x, j["rp"].y)
            best = None
            best_ring = None
            sink = {}
            # 環上取樣間距：原本用 0.4×標註尺寸（≈70px＝1km）太粗，會整圈跳過窄窄的
            # 可放窗口（例：泰山區西側的白色空隙只有兩三公里寬，70px 的取樣密度找不到），
            # 於是標註停在 2.5km 外。改成固定弧長取樣，環距成長 1.18→1.10。
            step = max(w, h) * 0.4                       # 環距成長基準
            arc = max(20.0, step * 0.28)                 # 環上取樣弧長（px）
            ring = step                                  # 逐圈外擴（先近後遠）
            # 不能「第一圈有解就停」：取樣加密後第一圈常常只有遠角落可行，會比稍外圈
            # 的貼區落點差（五股因此從 4.7km 退到 7.7km）。改成找到首解後再多搜 25%
            # 半徑範圍，取整段掃描裡評分最好的那一個。
            while ring <= 1600:
                ns = max(24, int(2 * np.pi * ring / arc))
                for a_i in range(ns):
                    th = 2 * np.pi * a_i / ns + ring * 0.13
                    cx = rpx + ring * np.cos(th)
                    cy = rpy + ring * np.sin(th)
                    g2 = fits(j, cx, cy, sink)
                    if g2 is not None and (best is None or g2[0] < best[0]):
                        best = (g2[0], cx, cy)
                        best_ring = ring
                if best is not None and ring > best_ring * 1.25:
                    break
                ring *= 1.10                                 # 往外一圈
            if best is not None and best[0] < cur - GAP_GAIN_PX:
                _, nx, ny = best
                j["cx"], j["cy"] = nx, ny
                boxes[j["core"]] = _box(nx, ny, w, h)
                anchors[j["core"]] = anchor_at(j, nx, ny)
                j["hugged"] = True
                moved += 1
            if debug_all or j["core"] in debug_want:
                top = sorted(sink.items(), key=lambda kv: -kv[1])[:4]
                print(f"    [hug] {j['name']:<4} 第{_round + 1}輪"
                      f" 現距 {cur * mpp / 1000:.2f}km"
                      + (f" → 最近可行 {best[0] * mpp / 1000:.2f}km"
                         f" 落點 ({best[1]:.0f},{best[2]:.0f})" if best else " → 找不到可行點")
                      + ("  [搬]" if j.get("hugged") else "")
                      + "  淘汰原因 " + str(top))
        if not moved:
            break

    for j in jobs:
        w, h = j["text"].width, j["text"].height
        j["anchor_px"] = anchor_at(j, j["cx"], j["cy"], refine=True)
        j["gap_px"] = gap_px(j, j["cx"], j["cy"])
        a = j["anchor_px"]
        if a is None:
            j["leader_px"] = 0.0
            j["leader_inside"] = None                     # 免引線，無從檢查
            j["leader_cross_other"] = False
        else:
            ex, ey = _box_edge_point(j["cx"], j["cy"], a[0], a[1], w, h)
            j["leader_px"] = ((a[0] - ex) ** 2 + (a[1] - ey) ** 2) ** 0.5
            # 診斷：引線末端（區內縮 800m 之後）是否真的落在本區裡面。
            # 「引線不要停在區界線上、要從區裡一點的位置起引」是使用者的要求，
            # 這裡逐區驗證，落在外面的會在下方的落點診斷標記出來。
            qx, qy = to_map(a[0], a[1])
            j["leader_inside"] = bool(j["geom"].buffer(0).contains(Point(qx, qy)))
            # 診斷：引線是否借道了別的行政區（會壓到那一區的市界黑線）
            j["leader_cross_other"] = bool(seg_through_other((ex, ey), a, j["core"]))
    return jobs

def _leader_anchor(geom, rp, cx, cy, w, h, to_map, to_px, obstacles=()):
    """算出引線在「完整地圖」上的落點：一律取行政區中心（區幾何代表點）。

    引線從標註框邊緣直達區中心；若區中心被標註框本身覆蓋（標註就在區上），
    則不需引線，回傳 None。
    """
    bx = _box(cx, cy, w, h)
    rp_px = to_px(rp.x, rp.y)
    if bx[0] <= rp_px[0] <= bx[2] and bx[1] <= rp_px[1] <= bx[3]:
        return None
    return rp_px

def draw_town_labels(final_img, jobs, xlim, ylim, w_px, h_px, y_off):
    """在已渲染完成的完整地圖上疊加標註。

    分兩趟：先畫完所有引線，再貼所有標註文字。否則後貼的標註（連同不透明的白色
    描邊）會把先畫的引線擦掉一段。
    """
    draw_obj = ImageDraw.Draw(final_img)
    mpp = METERS_PER_PIXEL
    to_px, to_map = _xy_maps(xlim, ylim, w_px, h_px, y_off, mpp)
    boxes = {j["core"]: _box(j["cx"], j["cy"], j["text"].width, j["text"].height)
             for j in jobs}

    for j in sorted(jobs, key=lambda t: t["text"].height, reverse=True):  # 先大後小
        if not j["external"]:
            continue
        w, h = j["text"].width, j["text"].height
        cx, cy = j["cx"], j["cy"]
        obstacles = [boxes[o["core"]] for o in jobs if o is not j]
        # 落點已由 plan_town_labels 收尾決定（過長引線已收到區界），直接用；
        # 未帶該欄位時（例：手動呼叫）退回即時計算。
        if "anchor_px" in j:
            anchor = j["anchor_px"]            # 排版收尾已定（過長引線已收到區界）
        else:
            anchor = _leader_anchor(j["geom"], j["rp"], cx, cy, w, h, to_map, to_px, obstacles)
        if anchor is None:
            continue
        ax_px, ay_px = anchor
        ex, ey = _box_edge_point(cx, cy, ax_px, ay_px, w, h)
        # 單一條灰色引線（依使用者要求「只有灰線」：不再墊白色襯線）。
        # 少了白襯線後，灰線壓在深色填色上仍看得見（#7F7F7F 對藍綠填色對比足夠）。
        draw_obj.line([(ex, ey), (ax_px, ay_px)],
                      fill=LEADER_COLOR, width=TOWN_LABEL_LINE_W)
        j["anchor_px"] = (ax_px, ay_px)

    for j in sorted(jobs, key=lambda t: t["text"].height, reverse=True):  # 先大後小，小的疊上面
        w, h = j["text"].width, j["text"].height
        blit_rgba(final_img, j["text"], (j["cx"] - w / 2, j["cy"] - h / 2))

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
    if cfg.get("color_ramps"):
        ramps = cfg["color_ramps"]
    else:
        ramps = [RATE_COLOR_RAMPS[i % len(RATE_COLOR_RAMPS)] for i in range(n_cand)]
    # 備註：ramps[i] 是「5% 級距 → 色碼」的 dict（見 RATE_COLOR_RAMPS 說明）。

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

    # ---- 色階分箱：依「全市村里領先者得票率」的實際範圍切出 5% 一階 ----
    # 領先者得票率必定落在中高區間（例：50.2%~63.9%），固定 0%~100% 分箱會讓整張圖
    # 擠在兩三格裡，故分箱範圍改由資料本身決定，首末階再各自開放一端。
    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0.0
    max_win_rate = max(all_win_rates) if all_win_rates else 100.0
    bins = build_bins(min_win_rate, max_win_rate)
    bin_colors = [step_colors(ramps[i], bins) for i in range(n_cand)]

    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return bin_colors[i][bin_index(vals[i], bins)]

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

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
    # 區名標註有外置 + 引線的版本，必須留足邊際空間讓標註堆疊，否則會全擠在圖上互相重疊
    MAP_PAD_FRAC = MAP_PAD_FRAC_LABELS if cfg.get("town_labels", True) else 0.03
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
    for col in bin_colors:
        allowed_hex.update(col)
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

    # ===================== 畫布佈局（地圖佔滿畫布，圖例浮貼右下角） =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size
    final_img = pil_img.copy()
    y_off = 0                         # 無右側面板，地圖即整張畫布

    # ---- 圖例方框先算好（含落點），才能先把該區域預留給鄉鎮標註避讓 ----
    legend_canvas, (lg_w, lg_h) = build_legend_box(
        bins, cand_names, bin_colors, cfg.get("title_lines"))
    lg_x = final_img.width - lg_w - LG_MARGIN
    lg_y = final_img.height - lg_h - LG_MARGIN
    legend_rect = (lg_x, lg_y, lg_x + lg_w, lg_y + lg_h)

    # ---- 得票率色片配色：領先候選人索引 + 得票率 → 該格色階色碼 ----
    def chip_color(cand_idx, value):
        return bin_colors[cand_idx][bin_index(value, bins)]

    # ---- 鄉鎮市區標註：區名 + 領先者得票率色片（比照參考圖 1.png）----
    if cfg.get("town_labels", True):
        town_rates, rate_mode = compute_town_rates(df_vote, rate_cols, town_level_dict, town_level_only)
        jobs = plan_town_labels(gdf_plot, town_rates, xlim, ylim, W, H, y_off,
                                city_geom=city_geom, chip_color=chip_color,
                                reserved=[legend_rect])
        draw_town_labels(final_img, jobs, xlim, ylim, W, H, y_off)
        n_ext = sum(1 for j in jobs if j["external"])
        n_crowd = sum(1 for j in jobs if j["crowded"])
        print(f"  鄉鎮市區標註     : {len(jobs)} 個"
              f"（區名 + 領先者得票率色片，全部外置於白色邊際、以引線指向各區；"
              f"區級得票率＝{rate_mode}）")
        if n_crowd:
            print(f"  ※ 找不到不重疊落點、已接受重疊者：{n_crowd} 個（可填 MANUAL_LABEL_POS 手調）")
        print("  【標註落點診斷】（依「標註框離本區的距離」由遠到近排序；"
              "落點為標註框中心的畫布像素座標）")
        n_li = n_lout = 0
        for j in sorted(jobs, key=lambda t: -t.get("gap_px", 0.0)):
            G = j.get("gap_px", 0.0)
            nc = j.get("name_c")
            # 區名那一行的中心（＝MANUAL_LABEL_POS 的語意）
            ncx = j["cx"] + (nc[0] - j["text"].width / 2.0) if nc else j["cx"]
            ncy = j["cy"] + (nc[1] - j["text"].height / 2.0) if nc else j["cy"]
            ins = j.get("leader_inside")
            if ins is True:
                n_li += 1
                mark = "  引線入區 OK"
            elif ins is False:
                n_lout += 1
                mark = "  << 引線末端在本區外"
            else:
                mark = "  免引線"
            if j.get("leader_cross_other"):
                mark += "  << 引線壓到別區"
            tag = j["how"] + ("→拉近" if j.get("hugged") else "")
            print(f"      {j['name']:<5} 面積 {j['km2']:7.1f}km2  {tag:<9}"
                  f" 距本區 {G * METERS_PER_PIXEL / 1000:5.1f}km"
                  f"  引線 {j.get('leader_px', 0) * METERS_PER_PIXEL / 1000:4.1f}km"
                  f"  區名中心 ({ncx:7.0f}, {ncy:7.0f})"
                  f"  方框中心 ({j['cx']:7.0f}, {j['cy']:7.0f})"
                  + mark
                  + ("  << 重疊" if j["crowded"] else ""))
        n_cross = sum(1 for j in jobs if j.get("leader_cross_other"))
        n_far = sum(1 for j in jobs
                    if j.get("gap_px", 0.0) * METERS_PER_PIXEL > TOWN_LABEL_MAX_GAP_M)
        if n_cross:
            print(f"  ※ 引線借道其他行政區者 {n_cross} 個（已盡量避免；"
                  f"這幾區找不到更乾淨的落點）")
        print(f"  ※ 標註框離本區超過 {TOWN_LABEL_MAX_GAP_M / 1000:.1f}km 者 {n_far} 個"
              f"（拉近上限 {TOWN_LABEL_MAX_GAP_M}m）")
        print(f"  ※ 引線末端落在本區內者 {n_li} 個；落在本區外者 {n_lout} 個"
              f"（引線末端一律再往區內縮 {TOWN_LABEL_LEADER_INSIDE_M}m）")

    # ---- 貼上圖例方框（最後一步，確保不被標註的白描邊擦到）----
    region = final_img.crop(legend_rect).convert("RGBA")
    region.alpha_composite(legend_canvas)
    final_img.paste(region.convert("RGB"), (lg_x, lg_y))

    # 寫入偶發被其他程序（看圖軟體／預覽）短暫鎖定 → 重試，仍失敗改存副檔名
    import time
    for attempt in range(6):
        try:
            final_img.save(cfg["out"])
            break
        except OSError as e:
            if attempt == 5:
                alt = cfg["out"][:-4] + "_1.png"
                final_img.save(alt)
                print(f"  ※ 原路徑無法寫入（{e}），已改存: {alt}")
            else:
                time.sleep(1.0)
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；"
          f"色階 {bins[0][2]} / … / {bins[-1][2]}（共 {len(bins)} 階，{BIN_STEP}% 級距）")
    print(f"     圖例方框 {lg_w}×{lg_h}px，落點 ({lg_x}, {lg_y})\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖，如：py Converge_to_map.py 2005
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")
