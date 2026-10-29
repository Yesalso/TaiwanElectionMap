# -*- coding: utf-8 -*-
"""
2022 年地方公職人員選舉（九合一）—— 縣市長選舉 各縣市得票率地圖批次產生器

底圖：內政部 111 年村里界 SHP
      D:\\Windows\\Documents\\村里界歷史圖資_111\\村里界歷史圖資_111\\VILLAGE_MOI_1111118.shp
配色：Precident\\color.txt（6 組政黨色階；檔頭註解會自動忽略）

繪圖邏輯（沿用 Draw_Region_Maps_AllYears.py，只改資料來源與填色組別）：
  * 只繪 鄉鎮市區界 3px + 縣市界/海岸線 5px：matplotlib(Agg,DPI=100) 繪區面與界線，
    以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層（村里界依層級決定是否繪製）
  * 微孔洞清理 clean_tiny_holes、迴針清理 remove_ring_slits
  * 填色：直接讀各縣市「鄉鎮市區級別 / 村里層級明細」官方得票率（得票數加總重算）
    （勝選候選人＝該區得票率最高者；色階深淺＝其官方得票率）
    平票規則：第 1 名與第 2 名得票率相等（|差| ≤ TIE_RATE_EPS）時，
    該區改以「雙色對角斜線紋」填塗——底色＝第 1 名原定顏色、斜線＝第 2 名原定顏色
    洪水填充：黑線為封閉堤壩，每塊區域整塊填單色 → 顏色永不跨越黑線
  * 版面：**不畫標題、不畫圖例**，只輸出純地圖
  * 留白：DROP_NAN_COUNTIES 列出的縣市，其「無村里名」圖斑整筆不畫（港區、機場、軍港、
    海埔新生地等），圖上直接留白

比例尺：1px = 20m（沿用既有腳本）
輸出（每縣市兩張）：
  - 鄉鎮級：Mayors/2022NineInOne/map/town/<縣市>_鄉鎮級.png
  - 村里級：Mayors/2022NineInOne/map/village/<縣市>_村里級.png

候選人 → 政黨色階組別（color.txt 由上而下）：
  0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃)
  4 宋楚瑜(橘) / 5 台灣民眾黨(青綠)
  時代力量、台灣動物保護黨、台澎黨、台灣維新、共和黨、天一黨、龍黨等小黨 → 0（灰）

執行：
    py Draw_CountyMayor_2022.py                 # 全部 22 縣市（鄉鎮級 + 村里級）
    py Draw_CountyMayor_2022.py 台北市          # 只做台北市
    py Draw_CountyMayor_2022.py 台北市 新北市   # 指定多個縣市
"""
import os
import re
import sys
import ast
import math
import time
import unicodedata
import warnings
import collections
from datetime import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from difflib import SequenceMatcher
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===================== 路徑 / 常數 =====================
# 本腳本置於 Mayors/2022NineInOne/script/ 之下，資料在上一層 data/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ...\2022NineInOne
DATA_DIR = os.path.join(ROOT_DIR, "data")
MAP_DIR = os.path.join(ROOT_DIR, "map")
# color.txt 沿用總統線配色
COLOR_TXT = r"D:\Windows\TaiwanElection\Precident\color.txt"
SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
SHP_ENCODING = "UTF-8"
TARGET_CRS = "EPSG:3826"

METERS_PER_PIXEL = 20.0     # 1px = 20m（沿用既有腳本）
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.01
SIMPLIFY_TOL_M = 0.0

LINE_VILLAGE_PX = 1
LINE_TOWNSHIP_PX = 3
LINE_OUTER_PX = 5
THRESHOLD_VAL = 40
HOLE_MIN_AREA_M2 = 10000.0

NO_DATA_COLOR = "#FFFFFF"
DPI = 100

# 平票規則：區內第 1 名與第 2 名得票率差 ≤ 此值 → 雙色斜線紋
TIE_RATE_EPS = 1e-9
# 平票斜線紋每條寬度（px）；1px = 20m → 8px ≈ 160m
TIE_STRIPE_PX = 8

# 「無村里名」圖斑整筆不畫的縣市（港區水域、機場、軍港、海埔新生地等）
DROP_NAN_COUNTIES = ["基隆市", "臺中市", "雲林縣", "高雄市"]
REMOTE_MAX_DIST_M = 2000.0          # 無村里名：距本島 > 2km 剔除
NAMED_MAX_DIST_M = 20000.0          # 有村里名：距本島 > 20km 才剔除

# 個別縣市覆寫「距本島距離」門檻：(無村里名, 有村里名)，單位 m。
# 群島縣的正常領土本來就超過 20km，用單一門檻會把整座島（甚至整個鄉）砍掉：
#   澎湖縣——七美鄉距本島 34.5～37.1km、望安鄉東吉 28.0km／東坪 31.6km／西坪 26.9km／
#   花嶼 31.1km、西安村外礁 20.0～20.8km（原本全被剔除，七美鄉整鄉消失）。
#   放寬到 45km 後上列全部保留；本島群（102km²）仍為最大分量，不影響主圖斑判定。
COUNTY_DIST_OVERRIDE = {
    "澎湖縣": (45000.0, 45000.0),
}

MIN_SIMILARITY = 0.5

# ===================== 22 縣市配置 =====================
# 鍵＝縣市名（SHP 111 版正規名，用於比對圖資）；值＝data 目錄 xlsx 檔名
COUNTY_FILES = collections.OrderedDict([
    ("臺北市", "2022直轄市長選舉_台北市.xlsx"),
    ("新北市", "2022直轄市長選舉_新北市.xlsx"),
    ("桃園市", "2022直轄市長選舉_桃園市.xlsx"),
    ("臺中市", "2022直轄市長選舉_臺中市.xlsx"),
    ("臺南市", "2022直轄市長選舉_臺南市.xlsx"),
    ("高雄市", "2022直轄市長選舉_高雄市.xlsx"),
    ("南投縣", "2022縣市長選舉_南投縣.xlsx"),
    ("嘉義市", "2022縣市長選舉_嘉義市.xlsx"),
    ("嘉義縣", "2022縣市長選舉_嘉義縣.xlsx"),
    ("基隆市", "2022縣市長選舉_基隆市.xlsx"),
    ("宜蘭縣", "2022縣市長選舉_宜蘭縣.xlsx"),
    ("屏東縣", "2022縣市長選舉_屏東縣.xlsx"),
    ("彰化縣", "2022縣市長選舉_彰化縣.xlsx"),
    ("新竹市", "2022縣市長選舉_新竹市.xlsx"),
    ("新竹縣", "2022縣市長選舉_新竹縣.xlsx"),
    ("澎湖縣", "2022縣市長選舉_澎湖縣.xlsx"),
    ("臺東縣", "2022縣市長選舉_臺東縣.xlsx"),
    ("花蓮縣", "2022縣市長選舉_花蓮縣.xlsx"),
    ("苗栗縣", "2022縣市長選舉_苗栗縣.xlsx"),
    ("連江縣", "2022縣市長選舉_連江縣.xlsx"),
    ("金門縣", "2022縣市長選舉_金門縣.xlsx"),
    ("雲林縣", "2022縣市長選舉_雲林縣.xlsx"),
])

# 縣市名（Excel 簡寫/異體）→ SHP 111 版正規名（皆經 臺/台 正規化後比對）
COUNTY_ALIAS = {
    "台北市": "臺北市", "台北縣": "新北市",
    "台中市": "臺中市", "台中縣": "臺中市",
    "台南市": "臺南市", "台南縣": "臺南市",
    "台東縣": "臺東縣",
}

# 鄉鎮市區改制更名：鍵 = (舊縣市名正規鍵, 舊鄉鎮核心) → 111 版鄉鎮核心
TOWN_ALIAS = {}

# 村里更名：111 版鄉鎮核心 → {資料側村里核心: 圖資側村里核心}
#   針對「上下文相關的異體字」（無法全局安全映射者），例如：
#   康→槺（新屋/清水槺榔里，但「安康里」的康不能動）、果→菓（大園菓林/湖西菓葉，
#   但「果林」與「菓林」並非全台皆同）、盧→蘆、時→嵵、板→坂、殼→壳、弄→硦、
#   祭→磜、箔→萡 等——只對特定鄉鎮的特定村里做替換。
VILLAGE_ALIAS = {
    "中埔": {"石弄": "石硦"},
    "北埔": {"水祭": "水磜"},
    "大園": {"果林": "菓林"},
    "新屋": {"康榔": "槺榔"},
    "清水": {"康榔": "槺榔"},
    "蘆竹": {"盧興": "蘆興"},
    "湖西": {"果葉": "菓葉"},
    "馬公": {"時裡": "嵵裡"},
    "大安": {"龜殼": "龜壳"},
    "達仁": {"台板": "台坂", "土板": "土坂"},
    "四湖": {"箔子": "萡子", "箔東": "萡東"},
}


# ===================== 候選人 → 政黨色階組別 =====================
# 組別索引＝ color.txt 由上而下順序：0 無黨籍(灰) / 1 國民黨(藍) / 2 民進黨(綠)
#   3 新黨(黃) / 4 宋楚瑜(橘) / 5 民眾黨(青綠)
# 候選人名以 Excel 欄位（繁體）為準；小黨一律歸 0（灰）
CAND_PARTY = {
    "侯友宜": 1, "劉建國": 2, "劉復嵐": 0, "劉櫂豪": 2,
    "吳炳輝": 0, "吳盛聖": 0, "周春米": 2, "周江杰": 2,
    "唐新民": 0, "宋國鼎": 0, "張善政": 1, "張家豪": 0,
    "張麗善": 1, "徐定禎": 2, "徐榛蔚": 1, "施奉先": 0,
    "曹爾元": 1, "曾國民": 0, "曾尹儷": 0, "朱振東": 0,
    "朱紀瑋": 0, "李俊俋": 2, "李問": 2, "李應文": 0,
    "李驥羣": 0, "林佳瑜": 0, "林佳龍": 2, "林姿妙": 1,
    "林志錦": 0, "林義豐": 0, "林耕仁": 1, "柯志恩": 1,
    "楊文科": 1, "楊鎮浯": 1, "江聰淵": 2, "沈慧虹": 2,
    "洪志恒": 0, "王忠銘": 1, "王惠美": 1, "王文娟": 0,
    "王永慶": 0, "王育敏": 1, "盧秀燕": 1, "童文薰": 0,
    "翁章梁": 2, "范振揆": 0, "葉竹林": 0, "蔡其昌": 2,
    "蔡培慧": 2, "蔡適應": 2, "蔣萬安": 1, "蕭仁正": 0,
    "蘇清泉": 1, "蘇煥智": 0, "許忠信": 0, "許淑華": 1,
    "許鋐哲": 0, "詹智鈞": 0, "謝國樑": 1, "謝福弘": 1,
    "謝立康": 0, "謝龍介": 1, "谷辣斯．尤達卡 Kolas Yotaka": 2,
    "賴峰偉": 1, "賴香伶": 5, "鄭凱升": 0, "鄭匡宇": 0,
    "鄭宇翔": 0, "鄭寶清": 0, "鄭運鵬": 2, "鍾東錦": 0,
    "陳光復": 2, "陳其邁": 2, "陳時中": 2, "陳泰山": 0,
    "陳琬惠": 5, "陳福海": 0, "陳秋境": 0, "陳美妃": 0,
    "陳薇仲": 0, "陳長宏": 0, "饒慶鈴": 1, "高虹安": 5,
    "黃偉哲": 2, "黃宏成台灣阿成世界偉人財神總統": 0, "黃希賢": 0,
    "黃敏惠": 1, "黃源甫": 0, "黃珊珊": 0, "黃秀芳": 2,
    "黃秀龍": 0, "黃聖峰": 0, "黄師鵬": 0, "龔偉綸": 0,
}


# ===================== 讀 color.txt =====================
def load_color_stops(path):
    """讀 color.txt（Python 串列字面）。忽略整行註解，取 '=' 之後做 literal_eval。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    rhs = "\n".join(lines).split("=", 1)[1]
    return ast.literal_eval(rhs)


RATE_COLOR_STOPS = load_color_stops(COLOR_TXT)


# ===================== 文字正規化 / 顏色 =====================
# 異體字/音同字異 正規化對照（表格資料 vs 圖資用字不同，需先統一）
#  方向：把「資料側（Excel）用字」統一映射到「圖資側（111 村里界 SHP）主流用字」。
#  normalize_text 對資料與圖資兩側都套用，故只要同一組同義字都歸一到同一個字，
#  兩側即可精確比對。注意「台/臺」：圖資村里名慣用「台」（台西村/霧台村/丁台里…），
#  故資料側的「臺」在此統一為「台」；縣市名則由 canon_county 另行處理。
VARIANT_CHAR_MAP = str.maketrans({
    # —— 沿用總統線既有異體字 ——
    '濓': '濂', '曹': '槽', '\U00025562': '槽', '磘': '窯', '獇': '羌',
    '舘': '館', '廍': '部', '峯': '峰', '脚': '腳',
    '\ue006': '塭', '\U00026c21': '那', '売': '壳', '欍': '春',
    # —— 新增：嗂→窯（中和區灰嗂，Excel 用字 / 圖資灰磘）——
    '嗂': '窯',
    # —— 新增：繁/簡/異體同義字，統一為圖資慣用字 ——
    '雙': '双',     # 双溪/双福/双龍/双湖/双潭（圖資慣用簡體「双」）
    '鹽': '塩',     # 塩埕/塩田/塩洲/塩行/塩舘（圖資慣用「塩」）
    '豐': '豊',     # 豊收/豊稠/上豊/和豊/豊崙/內豊（圖資慣用「豊」）
    '廈': '厦',     # 厦北/厦南/厦安/厦粘/厦莊（圖資慣用「厦」）
    '雞': '鷄',     # 鷄林（圖資慣用「鷄」）
    '晉': '晋',     # 晋江（圖資慣用「晋」）
    '壟': '壠',     # 里壠（圖資慣用「壠」）
    '響': '响',     # 响林（圖資慣用「响」）
    '涼': '凉',     # 凉山（圖資慣用「凉」）
    '瑤': '瑶',     # 南瑶（圖資慣用「瑶」）
    '臺': '台',     # 台西/霧台/丁台/富台/台子（圖資村里名慣用「台」）
})
VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"}, {"舘", "館"}, {"磘", "窯"}, {"獇", "羌"}, {"曹", "槽"}, {"脚", "腳"},
    {"嗂", "窯"}, {"雙", "双"}, {"鹽", "塩"}, {"豐", "豊"}, {"廈", "厦"},
    {"雞", "鷄"}, {"晉", "晋"}, {"壟", "壠"}, {"響", "响"}, {"涼", "凉"},
    {"瑤", "瑶"}, {"臺", "台"},
]


def normalize_text(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s


def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))


def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))


def canon_county(s):
    """縣市名 → 111 版正規鍵（臺/台 統一、舊名對照）。"""
    s = normalize_text(s).replace("臺", "台")
    return COUNTY_ALIAS.get(s, s)


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and np.isnan(val)) or val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _char_pairs(a, b):
    if len(a) != len(b):
        return None
    return list(zip(a, b))


def is_variant_fuzzy(a, b):
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    return any(ca in g and cb in g for g in VARIANT_FUZZY_GROUPS)


def fuzzy_lookup(county, town, vill, by_key, by_town):
    if not town or not vill:
        return None, "none"
    key = (county, town, vill)
    if key in by_key:
        return by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get((county, town), []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, "none"
    if not is_variant_fuzzy(vill, best_v):
        return None, "none"
    return best_val, f"fuzzy:{best_v}({best_ratio:.2f})"


# ===================== 讀取得票資料（單一縣市 xlsx）=====================
def _cand_name_from_col(col):
    """欄位「張家豪（01）_得票率」→ 候選人名「張家豪」。"""
    c = str(col).strip()
    c = re.sub(r"_得票[數率]$", "", c)
    c = re.sub(r"（\d+）$", "", c)
    return c


def load_county_vote_data(filepath):
    """讀單一縣市 xlsx，回傳：
      town_rates: {(county_core, town_core): {候選人名: 得票率(%)}}
      town_votes: {(county_core, town_core): {候選人名: 得票數}}
      vill_rates: {(county_core, town_core, vill_core): {候選人名: 得票率(%)}}
      candidates: [候選人名, ...]（依欄位順序）
      county_core: 縣市正規鍵
    以官方「得票數」加總後重算得票率（＝候選人得票數 / 該區候選人得票數合計）。"""
    def _parse_sheet(sheet, group_key):
        df = pd.read_excel(filepath, sheet_name=sheet, dtype=str)
        cols = [str(c) for c in df.columns]
        # 找得票數/得票率欄位
        vote_cols, rate_cols = {}, {}
        for c in cols:
            if c.endswith("得票數"):
                vote_cols[_cand_name_from_col(c)] = c
            elif c.endswith("得票率"):
                rate_cols[_cand_name_from_col(c)] = c
        cands = list(vote_cols.keys())
        # 讀「縣市」欄（首列即縣市名）
        f_county = "縣市"
        acc = {}
        for _, r in df.iterrows():
            county_raw = normalize_text(r.get(f_county)).replace("臺", "台")
            county = canon_county(r.get(f_county))
            town = strip_town_suffix(r.get("鄉鎮市區"))
            town = TOWN_ALIAS.get((county_raw, town), town)
            if not county or not town:
                continue
            if group_key == "town":
                key = (county, town)
            else:
                vill_raw = normalize_text(r.get("村里"))
                if not vill_raw:
                    continue
                vill = strip_village_suffix(vill_raw)
                vill = VILLAGE_ALIAS.get(town, {}).get(vill, vill)
                key = (county, town, vill)
            d = acc.setdefault(key, {name: 0.0 for name in cands})
            for name in cands:
                try:
                    v = float(str(r[vote_cols[name]]).strip().replace(",", "").replace("\u00a0", ""))
                except (TypeError, ValueError):
                    v = 0.0
                if np.isfinite(v):
                    d[name] += v
        # 重算得票率
        rates = {}
        votes = {}
        for key, d in acc.items():
            total = sum(d.values())
            votes[key] = {name: float(d[name]) for name in cands}
            if total <= 0:
                continue
            rates[key] = {name: d[name] / total * 100.0 for name in cands}
        return rates, votes, cands

    town_rates, town_votes, town_cands = _parse_sheet("鄉鎮市區級別", "town")
    vill_rates, vill_votes, vill_cands = _parse_sheet("村里層級明細", "vill")
    # 候選人應一致（取鄉鎮級欄位序為準）
    return town_rates, town_votes, vill_rates, town_cands


# ===================== 圖資清理（沿用既有腳本）=====================
def strip_far_parts(gdf, max_dist_nameless=REMOTE_MAX_DIST_M, max_dist_named=NAMED_MAX_DIST_M):
    parts, owner = [], []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for pp in ps:
            if pp is None or pp.is_empty:
                continue
            parts.append(pp)
            owner.append(i)
    if not parts:
        return gdf
    merged = unary_union(parts)
    comps = [c for c in (merged.geoms if hasattr(merged, "geoms") else [merged])
             if c.geom_type in ("Polygon", "MultiPolygon")]
    if not comps:
        comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)

    vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
    named = (~vv.isin(["", "nan", "None"])).to_numpy()
    owner_arr = np.array(owner, dtype=int)
    thr = np.where(named[owner_arr], max_dist_named, max_dist_nameless)
    dist = np.array([main.distance(pp) for pp in parts])
    keep_flags = dist <= thr

    dropped = np.nonzero(~keep_flags)[0]
    if len(dropped):
        print(f"    離島/碎塊清理：剔除 {len(dropped)} 個圖斑")

    idx0, rebuilt = 0, []
    for geom in gdf.geometry:
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kp = [ps[k] for k in range(len(ps)) if keep_flags[idx0 + k]]
        idx0 += len(ps)
        kp = [g for g in kp if g is not None and not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon")]
        if not kp:
            rebuilt.append(None)
        elif len(kp) == 1:
            rebuilt.append(kp[0])
        else:
            rebuilt.append(MultiPolygon(kp))
    out = gdf.copy()
    out["geometry"] = rebuilt
    out = out[~out["geometry"].isna() & ~out["geometry"].is_empty].copy().reset_index(drop=True)
    return out


def _despike_ring(coords, tol=5.0, area_thr=5000.0, min_path=100.0):
    P = np.asarray(coords, dtype=float)
    n = len(P)
    if n < 5:
        return P
    dead = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        if dead[i]:
            i += 1
            continue
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        d[:i + 2] = np.inf
        if i == 0:
            d[n - 1] = np.inf
        j = int(np.argmin(d))
        if d[j] <= tol:
            seg = P[i:j + 1]
            path_len = float(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])).sum())
            _x, _y = seg[:, 0], seg[:, 1]
            area = 0.5 * abs(np.dot(_x[:-1], _y[1:]) - np.dot(_x[1:], _y[:-1]))
            if path_len > min_path and area < area_thr:
                dead[i + 1:j] = True
        i += 1
    return P[~dead]


def remove_ring_slits(gdf, tol=5.0, area_thr=5000.0, min_path=100.0):
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        out = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            ext = _despike_ring(poly.exterior.coords, tol, area_thr, min_path)
            holes = []
            for r in poly.interiors:
                h = _despike_ring(r.coords, tol, area_thr, min_path)
                if len(h) >= 4:
                    holes.append(h)
            out.append(Polygon(ext, holes).buffer(0))
        if not out:
            return geom
        return out[0] if len(out) == 1 else MultiPolygon(out)

    o = gdf.copy()
    o["geometry"] = o.geometry.apply(_fix)
    return o[~o.geometry.isna() & ~o.geometry.is_empty].copy().reset_index(drop=True)


def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kept = []
        for poly in parts:
            if poly.geom_type != "Polygon" or poly.area < min_area:
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


# ===================== 線稿工具（沿用既有腳本）=====================
def to_px(coords, minx, maxy, sx, sy):
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def extract_lines(gs):
    parts = list(gs.geoms) if hasattr(gs, "geoms") else [gs]
    out = []
    for g in parts:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(list(g.coords))
        elif g.geom_type == "MultiLineString":
            out.extend(list(ls.coords) for ls in g.geoms)
        elif g.geom_type == "GeometryCollection":
            out.extend(extract_lines(g))
    return out


def draw_layer(lines, width, w_px, h_px, minx, maxy, sx, sy):
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords, minx, maxy, sx, sy)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


def render_line_layer(gdf, w_px, h_px, minx, maxx, miny, maxy,
                      town_px, outer_px, dpi, threshold):
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    px2pt = 72.0 / dpi
    town_lw = town_px * px2pt
    outer_lw = outer_px * px2pt
    gdf.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=town_lw)
    gdf.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=town_lw)
    for _cname, sub in gdf.groupby("COUNTYNAME"):
        cbd = unary_union(sub.geometry).boundary
        gpd.GeoSeries([cbd]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    outer = unary_union(gdf.geometry).boundary
    gpd.GeoSeries([outer]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, pad_inches=0, bbox_inches=None, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, tmask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    del gray
    return tmask > 0


# ===================== 填色（油漆桶／洪水填充）=====================
def flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy):
    from rasterio.features import rasterize
    from affine import Affine

    lut = np.vstack([
        np.array([[255, 255, 255]], dtype=np.uint8),
        np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                  for hx in records["fill_hex"]], dtype=np.uint8),
    ])
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)
    free = ~lines_mask
    ncomp, comp = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    seed = np.zeros(ncomp, dtype=np.int32)
    seed[comp.ravel()] = ids.ravel()
    reps = seed[comp]
    agree = (ids == reps)
    cnt_all = np.bincount(comp.ravel(), minlength=ncomp)
    cnt_ok = np.bincount(comp.ravel(), weights=agree.ravel(), minlength=ncomp)
    del reps, agree
    bad = np.nonzero(cnt_ok < 0.5 * cnt_all)[0]
    for b in bad:
        m = (comp == b)
        seed[b] = int(np.bincount(ids[m].ravel()).argmax())
    arr = lut[seed[comp]].astype(np.uint8)
    del ids, seed
    return arr, ncomp, comp


def check_region_single_color(arr, ncomp, comp):
    c = (arr[..., 0].astype(np.int32) << 16) | \
        (arr[..., 1].astype(np.int32) << 8) | arr[..., 2].astype(np.int32)
    idx = np.arange(1, ncomp)
    mn = ndimage.minimum(c, comp, index=idx)
    mx = ndimage.maximum(c, comp, index=idx)
    return ncomp - 1, int((mn != mx).sum())


def apply_tie_stripes(arr, records, w_px, h_px, minx, maxy, sx, sy,
                      stripe_px=TIE_STRIPE_PX):
    from rasterio.features import rasterize
    from affine import Affine
    tie = records[records["tie_hex"].notna()]
    if len(tie) == 0:
        return 0
    tids = rasterize(((g, i + 1) for i, g in enumerate(tie.geometry)),
                     out_shape=(h_px, w_px),
                     transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                     fill=0, dtype="int32", all_touched=False)
    yy, xx = np.indices((h_px, w_px))
    stripe = ((xx + yy) // stripe_px) % 2 == 1
    m = (tids > 0) & stripe
    lut = {}
    for i, hx in enumerate(tie["tie_hex"]):
        if hx not in lut:
            lut[hx] = [int(round(v * 255)) for v in hex2rgb(hx)]
    vals = np.array([lut[hx] for hx in tie["tie_hex"]], dtype=np.uint8)
    arr[m] = vals[tids[m] - 1]
    return len(tie)


def full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy):
    from rasterio.features import rasterize
    from affine import Affine
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)
    fill = np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                     for hx in records["fill_hex"]], dtype=np.uint8)
    exp = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    inside = ids > 0
    exp[inside] = fill[ids[inside] - 1]
    tie = records[records["tie_hex"].notna()]
    if len(tie):
        tids = rasterize(((g, i + 1) for i, g in enumerate(tie.geometry)),
                         out_shape=(h_px, w_px),
                         transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                         fill=0, dtype="int32", all_touched=False)
        yy, xx = np.indices((h_px, w_px))
        m = (tids > 0) & (((xx + yy) // TIE_STRIPE_PX) % 2 == 1)
        lut = {}
        for i, hx in enumerate(tie["tie_hex"]):
            if hx not in lut:
                lut[hx] = [int(round(v * 255)) for v in hex2rgb(hx)]
        vals = np.array([lut[hx] for hx in tie["tie_hex"]], dtype=np.uint8)
        exp[m] = vals[tids[m] - 1]
    black = img.sum(axis=2) == 0
    wrong = (img != exp).any(axis=2) & ~black
    return int(wrong.sum()), int((wrong & ~inside).sum())


# ===================== 讀 SHP（一次）=====================
def load_shp():
    g = gpd.read_file(SHP_PATH, encoding=SHP_ENCODING)
    if g.crs is None:
        g.crs = "EPSG:4326"
    g = g.to_crs(TARGET_CRS)
    g = g[g["COUNTYNAME"].notna()].copy()
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g["COUNTYNAME"] = g["COUNTYNAME"].astype(str).str.strip()
    g["TOWNNAME"] = g["TOWNNAME"].astype(str).str.strip()
    g["county_canon"] = g["COUNTYNAME"].apply(canon_county)
    return g


# ===================== 候選人色階查色 =====================
def _cand_group(name, candidates, group_map):
    """候選人名 → color.txt 色階組別索引；未知候選人（未列入 CAND_PARTY）→ None（留白）。"""
    return group_map.get(name)


# ===================== 繪製單一（縣市 × 層級）=====================
def build_county_map(county, shp, rates, votes, candidates, level):
    """level = 'town' 或 'village'。"""
    county_canon = canon_county(county)
    cand_groups = {name: CAND_PARTY.get(name) for name in candidates}

    label = "鄉鎮級" if level == "town" else "村里級"
    print("-" * 62)
    print(f"  【{county}】{label}")

    gdf = shp[shp["county_canon"] == county_canon].copy()
    gdf = gdf[gdf["TOWNNAME"].notna()].copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[~gdf["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy().reset_index(drop=True)
    if len(gdf) == 0:
        print("    ⚠️ 無圖斑，略過")
        return

    if DROP_NAN_COUNTIES:
        _vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
        _canon_drop = {canon_county(c) for c in DROP_NAN_COUNTIES}
        _drop = (gdf["COUNTYNAME"].apply(canon_county).isin(_canon_drop)
                 & _vv.isin(["", "nan", "None"]))
        if int(_drop.sum()):
            print(f"    DROP_NAN_COUNTIES：剔除 {int(_drop.sum())} 筆無村里名圖斑")
            gdf = gdf[~_drop].copy().reset_index(drop=True)

    _d_nameless, _d_named = COUNTY_DIST_OVERRIDE.get(
        county_canon, (REMOTE_MAX_DIST_M, NAMED_MAX_DIST_M))
    gdf = strip_far_parts(gdf, max_dist_nameless=_d_nameless, max_dist_named=_d_named)

    gdf["county_core"] = gdf["COUNTYNAME"].apply(canon_county)
    gdf["town_core"] = gdf["TOWNNAME"].apply(strip_town_suffix)
    n = len(gdf)

    # ---- 勝選候選人＝得票率最高者；色階深淺＝其得票率 ----
    # rates 鍵：town → (county, town)；village → (county, town, vill)
    area_color = {}
    area_tie = {}
    for key, rdict in rates.items():
        cc = key[0]
        if cc != county_canon or not rdict:
            continue
        ranked = sorted(rdict.items(), key=lambda kv: kv[1], reverse=True)
        name = ranked[0][0]
        gi = cand_groups.get(name)
        if gi is None:
            area_color[key] = None
            continue
        c1 = get_color_by_value(rdict[name], RATE_COLOR_STOPS[gi])
        area_color[key] = c1
        if len(ranked) > 1:
            v1, v2 = votes.get(key, {}).get(ranked[0][0]), votes.get(key, {}).get(ranked[1][0])
            tied = (round(ranked[0][1], 3) == round(ranked[1][1], 3)) or (
                v1 is not None and v2 is not None and float(v1) == float(v2))
            if tied:
                name2 = ranked[1][0]
                gi2 = cand_groups.get(name2)
                if gi2 is not None:
                    c2 = get_color_by_value(rdict[name2], RATE_COLOR_STOPS[gi2])
                    if c2 is not None and c1 is not None and c2.upper() != c1.upper():
                        area_tie[key] = c2

    if level == "town":
        fill_hex = np.array([NO_DATA_COLOR] * n, dtype=object)
        tie_hex_list = [None] * n
        for i in range(n):
            key = (gdf["county_core"].iat[i], gdf["town_core"].iat[i])
            c = area_color.get(key)
            if c is not None:
                fill_hex[i] = c
            tie_hex_list[i] = area_tie.get(key)
        gdf["fill_hex"] = fill_hex
        gdf["tie_hex"] = tie_hex_list
        # 鄉鎮級：以 (縣市, 鄉鎮市區) 溶解
        records = gdf[["COUNTYNAME", "TOWNNAME", "geometry", "fill_hex", "tie_hex"]].copy()
        townships = records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
        # 溶解後 fill_hex/tie_hex 取 first（同鄉鎮各村同色）
        townships = remove_ring_slits(townships)
        townships = clean_tiny_holes(townships)
        # 重排 records 供填色（以鄉鎮為填色單元）
        fill_records = townships[["COUNTYNAME", "TOWNNAME", "geometry", "fill_hex", "tie_hex"]].copy()
        line_records = townships
        n_area = len(townships)
    else:
        # 村里級：需先算村里關鍵字
        gdf["vill_core"] = gdf["VILLNAME"].apply(strip_village_suffix)
        fill_hex = np.array([NO_DATA_COLOR] * n, dtype=object)
        tie_hex_list = [None] * n
        for i in range(n):
            key = (gdf["county_core"].iat[i], gdf["town_core"].iat[i], gdf["vill_core"].iat[i])
            c = area_color.get(key)
            if c is not None:
                fill_hex[i] = c
            tie_hex_list[i] = area_tie.get(key)
        gdf["fill_hex"] = fill_hex
        gdf["tie_hex"] = tie_hex_list
        fill_records = gdf[["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry", "fill_hex", "tie_hex"]].copy()
        # 村里級：以 (縣市, 鄉鎮市區) 溶解出區層，畫區界
        line_records = gdf[["COUNTYNAME", "TOWNNAME", "geometry"]].copy()
        line_records = line_records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
        line_records = remove_ring_slits(line_records)
        line_records = clean_tiny_holes(line_records)
        n_area = len(gdf)

    if n_area == 0:
        print("    ⚠️ 無有效區域，略過")
        return

    # ---- 畫布 ----
    minx, miny, maxx, maxy = fill_records.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny
    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m
    print(f"    1px = {geo_w_m / w_px:.4f} m，圖幅 {w_px}x{h_px} px，區域 {n_area}")

    # ---- 線稿：鄉鎮市區界 + 縣市界/海岸線 ----
    town_layer = render_line_layer(line_records, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    lines_mask = town_layer

    if level == "village":
        # 村里級另繪 1px 村里界（thin 取中心線）
        villages = fill_records[fill_records["VILLNAME"].notna()].copy()
        if len(villages):
            village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
            village_arr = draw_layer(village_lines, 1, w_px, h_px, minx, maxy, sx, sy)
            village_skel = thin(village_arr)
            lines_mask = village_skel | town_layer

    # ---- 填色 ----
    arr, ncomp, comp = flood_fill_layer(fill_records, lines_mask, w_px, h_px, minx, maxy, sx, sy)
    _nc, _nbad = check_region_single_color(arr, ncomp, comp)
    if any(area_tie.values()):
        apply_tie_stripes(arr, fill_records, w_px, h_px, minx, maxy, sx, sy)
    arr[lines_mask] = 0

    # ---- 自檢 ----
    _nw, _nout = full_geom_check(arr, fill_records, w_px, h_px, minx, maxy, sx, sy)
    _tot = w_px * h_px
    allowed = {(255, 255, 255), (0, 0, 0)}
    for stops in RATE_COLOR_STOPS:
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in hex2rgb(hx)))
    _uniq = np.unique(arr.reshape(-1, 3), axis=0)
    _n_bad = int(sum(1 for c in _uniq if tuple(int(x) for x in c) not in allowed))
    print(f"    自檢：非單色區 {_nbad}｜幾何差異 {_nw}px({_nw / _tot * 100:.4f}%)｜"
          f"區域外非白 {_nout}｜非允許色種類 {_n_bad}")

    # ---- 輸出（純地圖）----
    out_sub = "town" if level == "town" else "village"
    out_dir = os.path.join(MAP_DIR, out_sub)
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"{county}_{label}.png")
    Image.fromarray(arr, mode="RGB").save(out_png)
    del arr
    print(f"    Saved: {out_png}")


# ===================== 主流程 =====================
def main():
    args = sys.argv[1:]
    if args and args[0].isdigit() is False and args[0].lower() not in ("all",):
        # 指定縣市
        want = [canon_county(a) for a in args]
    else:
        want = list(COUNTY_FILES.keys())

    print("=" * 62)
    print("  2022 縣市長選舉 各縣市得票率地圖（111 村里界 + color.txt）")
    print("=" * 62)
    if not os.path.exists(SHP_PATH):
        raise FileNotFoundError("找不到村里界 SHP：" + SHP_PATH)

    t_all = time.time()
    shp = load_shp()
    print(f"  SHP 圖斑：{len(shp)}，縣市：{len(shp['county_canon'].unique())}")

    for county in want:
        if county not in COUNTY_FILES:
            print(f"  ⚠️ 無縣市 {county}，略過")
            continue
        xlsx = os.path.join(DATA_DIR, COUNTY_FILES[county])
        if not os.path.exists(xlsx):
            print(f"  ⚠️ 缺資料 {xlsx}，略過")
            continue
        print("=" * 62)
        print(f"  {county} ← {os.path.basename(xlsx)}")
        try:
            town_rates, town_votes, vill_rates, candidates = load_county_vote_data(xlsx)
            print(f"  候選人 {len(candidates)}：{'、'.join(candidates)}")
            build_county_map(county, shp, town_rates, town_votes, candidates, "town")
            build_county_map(county, shp, vill_rates, town_votes, candidates, "village")
        except Exception as e:
            import traceback
            print(f"    ✗ {county} 失敗：{e}")
            traceback.print_exc()

    print("=" * 62)
    print(f"  全部完成，耗時 {time.time() - t_all:.1f} 秒")


if __name__ == "__main__":
    main()
