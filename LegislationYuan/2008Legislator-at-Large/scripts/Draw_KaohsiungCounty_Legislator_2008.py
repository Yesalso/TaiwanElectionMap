# -*- coding: utf-8 -*-
"""
2008 第 7 屆立法委員區域選舉 —— 高雄縣（27 鄉鎮市、4 個選區）
各村（里）得票領先候選人「按得票率配色」地圖。

資料來源：Data/区域/p07_T1_312.xls（4 個工作表 = 4 個選舉區）
    每個工作表結構：
      行 0  標題（第 N 選舉區候選人在各投開票所得票數一覽表）
      行 3  候選人姓名
      行 4  政黨
      行 5  總計
      行 6+ 各區（col0 有值、col1 空）與各里（col1 有值）之得票數

    4 個選區（2008 高雄縣；各鄉鎮市皆只屬單一選區，故選區邊界可直接 dissolve）：
      第1區 桃源鄉、三民鄉、甲仙鄉、六龜鄉、茂林鄉、杉林鄉、內門鄉、旗山鎮、
            美濃鎮、阿蓮鄉、田寮鄉、燕巢鄉、大社鄉、大樹鄉              （14 鄉鎮）
      第2區 茄萣鄉、湖內鄉、路竹鄉、永安鄉、岡山鎮、彌陀鄉、梓官鄉、橋頭鄉 （8 鄉鎮）
      第3區 仁武鄉、鳥松鄉、大寮鄉、林園鄉                              （4 鄉鎮）
      第4區 鳳山市                                                      （1 市）

    名稱對照（2008 → 108 版圖資）：
      - 鄉鎮市區：所有「鄉/鎮/市」→ 現行「區」（strip_town_suffix 後同名，直接匹配）；
        唯獨 **三民鄉 → 那瑪夏區**（2008 年三民鄉更名為那瑪夏鄉，見 TOWN_ALIAS）。
        ⚠️ 舊高雄市另有「三民區」，本圖 TARGET_TOWNS 不含之，不會誤選。
      - 村里：異體字統一（臺/台、峯/峰、舘/館、脚/腳，見 VILL_VARIANT_MAP）；
        2008 舊村名 → 現行里名（見 VILLAGE_ALIAS）：
          桃源 梅蘭→拉芙蘭；那瑪夏 民族→南沙魯、民權→瑪雅、民生→達卡努瓦。
      - 少數村里名在來源 xls 無法解碼、存成 U+FFFD（鳥松 坔埔→「�埔」、
        湖內 公館→「公�」、阿蓮 峰山→「�山」）：以「同鄉鎮、同長度、
        非 U+FFFD 字元全等」的萬用字元比對還原。
      - 杉林 大愛里為 2009 八八風災後新設，2008 年無此村 → 正確地無資料（白）。

村里界圖資：108 年版（2019/11/21）VILLAGE_MOI_1081121.shp（.dbf 為 UTF-8）。
    圖資「高雄市」為 2010 合併後之「大高雄市」（38 區），本圖僅取舊高雄縣 27 鄉鎮市區。
    2008 與 108 版圖資之間有少數里被裁併/改名，這些里以無資料處理（不填色），
    但照常繪製村里界 1px。

繪圖邏輯：完全沿用 Draw_South2_President_2020.py 的「線稿兩層 + 洪水填充」做法
（不再使用先前的 matplotlib 分層直繪 + 顏色量化）：

  ① 線稿（兩層畫法）
     - 村里界 1px：PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線
     - 區界 3px + 縣市界/海岸線 5px：matplotlib(Agg, DPI=100) 繪區面與區界，
       以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層
     - 微孔洞清理（HOLE_MIN_AREA_M2）避免 dissolve 浮點誤差造成的散點
     - 迴針清理（remove_ring_slits）折疊圖資「去而復返」的退化迴針
  ② 填色（油漆桶／洪水填充）
     - 以線稿為封閉堤壩，堤壩以外每一塊 4-連通區域整塊填單色，
       顏色取區域內像素幾何所屬村里的眾數 → 顏色永不跨越任何一條黑線
  ③ 立委選區界 5px（白）——本圖專屬規則：
     - 立委選區界與「縣市界（含海岸線）」重合的段 → **不畫白線**，
       讓黑色縣市界顯示（黑線優先）
     - 其餘段（沿鄉鎮市區界、沿里界、或跨里拆分處）→ **一律畫白線**
     作法（幾何法）：先把「與縣市界/海岸線重合」的段自立委界折線中剔除，
       再對剩餘內部段做 5px 緩衝帶 → 縣市界外緣不會出現白暈圈、
       縣市界本身也不會被白線蓋掉
     ⚠️ 關鍵前置：outer_boundary 須先做 drop_degenerate_holes()。村里界圖資相鄰
       兩里有時只差 <1m 沒接上，unary_union 後會形成「面積≈0 的內環」，被
       `.boundary` 當成海岸線；若不剔除，difference 會在立委白線**中段**挖掉
       一小塊，白線中間就會冒出黑點（鹽埕區/前金區交界即為此例）。
  ④ 疊加：先 arr[lines_mask] = 0 畫黑線，再 arr[立委白線] = 255 畫白線
  - 自檢：① 油漆桶不變式（每塊非線區域皆單色）；② 逐像素幾何參考差異 ≈0、
    村外非白 ≈0；③ 全圖只含允許色（得票率色階 / 黑 / 白）；④ 外輪廓無剩餘退化內環、
    白線帶內無殘留黑線、被剔除碎片不在白線路徑上留下黑像素

填色：按得票率配色（色階來源 D:\\Windows\\TaiwanElection\\LegislationYuan\\color.txt）。
      每里取「該選區得票最高候選人」，以其所屬政黨選定一組色階，再依其得票率
      （= 得票數 ÷ 有效票數 × 100）決定色階深淺：
        中國國民黨→藍、民主進步黨→綠、無黨籍/其他政黨→灰、新黨→黃、
        宋楚瑜→橘、台灣民眾黨→青；無匹配→白。
線寬：村里界 1px（黑）、鄉鎮市區界 3px（黑）、立委選區界 5px（白）、縣市界 5px（黑）。
比例尺：1px = 10m。
輸出：maps/高雄縣2008年立法委員選舉_得票率地圖.png
執行：py Draw_KaohsiungCounty_Legislator_2008.py
"""
import os
import sys
import math
import warnings
from io import BytesIO

import numpy as np
import pandas as pd
import geopandas as gpd
import xlrd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 共用模組（洪水填充 / 自檢 / 文字正規化）：2024Precident/scripts/20
_NAT_DIR = r"D:\Windows\TaiwanElection\Precident\2024Precident\scripts\20"
if _NAT_DIR not in sys.path:
    sys.path.insert(0, _NAT_DIR)
import Draw_National_President_2024 as nat

# ===================== 配置 =====================
# 2008 高雄縣立委選舉資料（4 選區）
VOTE_XLS = r"D:\Windows\TaiwanElection\LegislationYuan\2008Legislator-at-Large\Data\区域\p07_T1_312.xls"

# 108 年版村里界（UTF-8 編碼）
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\108\VILLAGE_MOI_1081121.shp"
encoding = "UTF-8"
TARGET_CRS = "EPSG:3826"

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "maps")
OUT_PNG = os.path.join(OUT_DIR, "高雄縣2008年立法委員選舉_得票率地圖.png")
layer_name = "layer_kaohsiungcounty_district_white.png"   # 立委界白線層單獨輸出（核對用）

# 舊高雄縣 27 鄉鎮市（2008 年範圍）→ 對應 108 版圖資（合併後大高雄市）之區名。
# 圖資 COUNTYNAME 一律為「高雄市」，故以 TOWNNAME 篩選本縣 27 鄉鎮市區。
TARGET_COUNTIES = ["高雄市"]
TARGET_TOWNS = ["桃源區", "那瑪夏區", "甲仙區", "六龜區", "茂林區", "杉林區",
                "內門區", "旗山區", "美濃區", "阿蓮區", "田寮區", "燕巢區",
                "大社區", "大樹區",                                    # 第1選區
                "茄萣區", "湖內區", "路竹區", "永安區", "岡山區", "彌陀區",
                "梓官區", "橋頭區",                                    # 第2選區
                "仁武區", "鳥松區", "大寮區", "林園區",                 # 第3選區
                "鳳山區"]                                             # 第4選區

# 2008 鄉鎮市名 → SHP 區名 的別名（僅套用於「選舉資料側」，不動 SHP）：
#   三民鄉（2008）於同年更名為那瑪夏鄉 → 108 版圖資為「那瑪夏區」。
#   注意：舊高雄市另有「三民區」，因其不在 TARGET_TOWNS，不會被誤選。
TOWN_ALIAS = {"三民": "那瑪夏"}

# 村里名異體字統一（兩側都套用；臺/台最常見，岡山「臺上村」↔圖資「台上里」）
VILL_VARIANT_MAP = str.maketrans({"臺": "台", "峯": "峰", "舘": "館", "脚": "腳"})

# 村里名別名：（鄉鎮core, 資料側里名）→ 圖資側里名。
#   僅套用於「選舉資料側」，把 2008 舊村名對到 108 版圖資的里名。
#   那瑪夏（2008 三民鄉）：民族→南沙魯、民權→瑪雅、民生→達卡努瓦
#     （2008-01-01 三民鄉更名那瑪夏鄉時，三村同步恢復舊名）
#   桃源：梅蘭村 → 拉芙蘭里
VILLAGE_ALIAS = {
    ("桃源", "梅蘭"): "拉芙蘭",
    ("那瑪夏", "民族"): "南沙魯",
    ("那瑪夏", "民權"): "瑪雅",
    ("那瑪夏", "民生"): "達卡努瓦",
}


def norm_village(s):
    """村里名正規化：去「村里」後綴 + 異體字統一；U+FFFD 原樣保留（供萬用字元比對）。"""
    return nat.strip_village_suffix(s).translate(VILL_VARIANT_MAP)

# 政黨填色 → 改為「按得票率配色」（色階來源 color.txt）
NO_DATA_COLOR = "#FFFFFF"           # 無資料 / 無匹配 → 純白

# color.txt 內 RATE_COLOR_STOPS 的分組順序（見檔內註解）：
#   0 無黨籍 / 1 中國國民黨 / 2 民主進步黨 / 3 新黨 / 4 宋楚瑜(橘) / 5 台灣民眾黨
COLOR_TXT = r"D:\Windows\TaiwanElection\LegislationYuan\color.txt"
PARTY_STOPS_INDEX = {
    "無黨籍": 0,
    "無黨籍及未經政黨推薦": 0,
    "中國國民黨": 1,
    "民主進步黨": 2,
    "新黨": 3,
    "親民黨": 4,
    "台灣民眾黨": 5,
    "臺灣民眾黨": 5,
}
DEFAULT_STOPS_INDEX = 0             # 其餘政黨（公民黨、台灣農民黨、客家黨…）→ 無黨籍灰階


def load_rate_color_stops(path):
    """讀取 color.txt（內容為純 Python 賦值敘述）並取出 RATE_COLOR_STOPS。"""
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    ns = {}
    exec(compile(src, path, "exec"), ns)
    stops = ns.get("RATE_COLOR_STOPS")
    if not stops:
        raise RuntimeError(f"{path} 找不到 RATE_COLOR_STOPS")
    return stops


RATE_COLOR_STOPS = load_rate_color_stops(COLOR_TXT)


def get_color_by_value(val, stops):
    """依得票率(%)取色：回傳第一個 upper ≥ val 的色；超過末階則取末階色。"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def pick_rate_color(party, rate):
    """依「領先候選人所屬政黨」選色階組、依「其得票率」選深淺；無資料→純白。"""
    if party is None or (isinstance(party, float) and math.isnan(party)):
        return NO_DATA_COLOR
    if rate is None or (isinstance(rate, float) and math.isnan(rate)):
        return NO_DATA_COLOR
    idx = PARTY_STOPS_INDEX.get(str(party).strip(), DEFAULT_STOPS_INDEX)
    stops = RATE_COLOR_STOPS[idx % len(RATE_COLOR_STOPS)]
    hx = get_color_by_value(rate, stops)
    return hx if hx else NO_DATA_COLOR

TITLE_LINES = []          # 不畫標題、不畫圖例：只輸出純地圖

# 比例尺：1px = 10m
METERS_PER_PIXEL = 10.0
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.02
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化

LINE_VILLAGE_PX = 1      # ① 村里界（黑）
LINE_TOWNSHIP_PX = 3     # ② 區界（黑）
LINE_OUTER_PX = 5        # ② 縣市界/海岸線（黑）
LINE_DISTRICT_PX = 5     # ③ 立委選區界（白）
THRESHOLD_VAL = 40       # ② 二值化閾值

HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為 dissolve 雜訊，填平

# 無村里名(VILLNAME 空)的圖斑：轄內港區/水庫/航道水域等無編制圖斑整筆不畫
DROP_NAN_COUNTIES = ["高雄市"]
REMOTE_MAX_DIST_M = 2000.0   # 無村里名者：與本島相距超過此值 → 不畫
NAMED_MAX_DIST_M = 20000.0   # 有村里名者：超過此值才剔除
SAVE_LAYER = False
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)


# ===================== 讀取 2008 立委選舉 xls =====================
def load_legislator_vote_data(xls_path):
    """解析 p07_T1_312.xls（4 個選區工作表），回傳：
      vote_by_vill : dict[(區core, 里core)] = {"district": 選區號, "votes": [...],
                     "valid": 有效票數, "parties": [...], "cands": [...]}
    得票率 = 該候選人得票數 ÷ 有效票數A × 100
    ⚠️ 資料為「一列一所」：同一村里若有多個投開票所會出現多列，
       故得票數與有效票數須逐列累加（不可只取第一列）。
    """
    wb = xlrd.open_workbook(xls_path)
    vote_by_vill = {}
    for sname in wb.sheet_names():
        sh = wb.sheet_by_name(sname)
        district_no = int(sname[-1])
        cands = []
        for c in range(3, sh.ncols):
            nm = str(sh.cell_value(3, c)).strip()
            if nm:
                cands.append((nm, str(sh.cell_value(4, c)).strip()))
        n_cand = len(cands)
        # 有效票數 A 欄：表頭（第 1 列）含「有效票數」者；找不到則取候選人欄之後一欄
        valid_col = None
        for c in range(3, sh.ncols):
            if "有效票數" in str(sh.cell_value(1, c)):
                valid_col = c
                break
        if valid_col is None:
            valid_col = 3 + n_cand
        cur_town = None
        for r in range(6, sh.nrows):
            v0 = str(sh.cell_value(r, 0)).replace("\u3000", "").strip()
            v1 = str(sh.cell_value(r, 1)).strip()
            if v0 and not v1 and v0 not in ("總計", "总计"):
                _tcore = nat.strip_town_suffix(v0)
                cur_town = TOWN_ALIAS.get(_tcore, _tcore)   # 三民鄉 → 那瑪夏
            elif v1 and cur_town:
                vill = norm_village(v1)
                vill = VILLAGE_ALIAS.get((cur_town, vill), vill)   # 舊村名 → 圖資里名
                votes = []
                for j in range(n_cand):
                    v = sh.cell_value(r, 3 + j)
                    try:
                        votes.append(float(v))
                    except (TypeError, ValueError):
                        votes.append(0.0)
                try:
                    valid = float(sh.cell_value(r, valid_col))
                except (TypeError, ValueError):
                    valid = 0.0
                key = (cur_town, vill)
                # 同一村里可能有多個投開票所（一列一所）→ 得票數與有效票數須逐列累加
                if key not in vote_by_vill:
                    vote_by_vill[key] = {
                        "district": district_no,
                        "votes": list(votes),
                        "valid": valid,
                        "parties": [p for _, p in cands],
                        "cands": [n for n, _ in cands],
                    }
                else:
                    rec = vote_by_vill[key]
                    for j in range(n_cand):
                        rec["votes"][j] += votes[j]
                    rec["valid"] += valid
    return vote_by_vill


# ===================== 主流程 =====================
def main():
    print("=" * 62)
    print("  2008 高雄縣立法委員選舉 各村（里）得票率配色地圖")
    print("=" * 62)

    # ---- 讀立委選舉得票資料 ----
    vote_by_vill = load_legislator_vote_data(VOTE_XLS)
    print(f"  立委選舉村里記錄 : {len(vote_by_vill)} 筆")

    # ---- 讀 SHP ----
    gdf_all = gpd.read_file(shp_path, encoding=encoding)
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    gdf_all = gdf_all.to_crs(TARGET_CRS)

    gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all["COUNTYNAME"] = gdf_all["COUNTYNAME"].astype(str).str.strip()
    gdf_all["TOWNNAME"] = gdf_all["TOWNNAME"].astype(str).str.strip()
    gdf_all = gdf_all[gdf_all["COUNTYNAME"].isin(TARGET_COUNTIES)].copy()
    gdf_all = gdf_all[gdf_all["TOWNNAME"].isin(TARGET_TOWNS)].copy()
    gdf_all["geometry"] = gdf_all.geometry.buffer(0)
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all = gdf_all.reset_index(drop=True)
    print(f"  SHP 舊高雄縣 27 鄉鎮市區要素 : {len(gdf_all)}")

    # 無村里名圖斑整筆不畫（港區/航道水域）
    if DROP_NAN_COUNTIES:
        _vv = gdf_all["VILLNAME"].fillna("").astype(str).str.strip()
        _drop = gdf_all["COUNTYNAME"].isin(DROP_NAN_COUNTIES) & _vv.isin(["", "nan", "None"])
        if _m := int(_drop.sum()):
            print(f"  無村里名不畫：剔除 {_m} 筆")
            gdf_all = gdf_all[~_drop].copy().reset_index(drop=True)

    # 遠離本島的圖斑處理（安全護欄）
    gdf_all = strip_far_parts(gdf_all)

    # ---- 匹配：區 + 里 兩鍵（精確 → 同區萬用字元 → 同區模糊）----
    gdf_all["town_core"] = gdf_all["TOWNNAME"].apply(nat.strip_town_suffix)
    gdf_all["vill_core"] = gdf_all["VILLNAME"].apply(norm_village)

    from difflib import SequenceMatcher
    vote_by_town = {}
    for (t, v), info in vote_by_vill.items():
        vote_by_town.setdefault(t, []).append((v, info))

    def _fffd_match(a, b):
        """長度相同、逐字僅在 U+FFFD 處不同 → 視為同一村里。
        來源 xls 有少數字元無法解碼（存成 U+FFFD 取代字元），例如
        鳥松「坔埔」→「�埔」、湖內「公館」→「公�」、阿蓮「峰山」→「�山」。
        比對限同鄉鎮內且長度相同，安全無虞。"""
        if len(a) != len(b) or len(a) == 0:
            return False
        return all((ca == cb) or ca == "\ufffd" or cb == "\ufffd"
                   for ca, cb in zip(a, b))

    def lookup(town, vill):
        key = (town, vill)
        if key in vote_by_vill:
            return key[1], vote_by_vill[key], "exact"
        # U+FFFD 可能在資料側（來源 xls 無法解碼）→ 逐一同鄉鎮候選做萬用字元比對
        if "\ufffd" in vill or any("\ufffd" in v for v, _ in vote_by_town.get(town, [])):
            for cand_v, info in vote_by_town.get(town, []):
                if _fffd_match(vill, cand_v):
                    return cand_v, info, f"fffd:{cand_v}"
        best_v, best_info, best_ratio = None, None, -1.0
        for cand_v, info in vote_by_town.get(town, []):
            ratio = SequenceMatcher(None, vill, cand_v).ratio()
            if ratio > best_ratio:
                best_ratio, best_v, best_info = ratio, cand_v, info
        if best_info is None or best_ratio < 0.6:
            return None, None, "none"
        return best_v, best_info, f"fuzzy:{best_v}({best_ratio:.2f})"

    def process_row(r):
        matched_v, info, mt = lookup(r["town_core"], r["vill_core"])
        if info is None:
            return pd.Series([np.nan, np.nan, np.nan, "none"])
        votes = np.asarray(info["votes"], dtype=float)
        wi = int(np.argmax(votes))
        party = info["parties"][wi]
        district = info["district"]
        valid = info.get("valid", 0.0)
        rate = (votes[wi] / valid * 100.0) if valid else np.nan
        return pd.Series([district, party, rate, mt])

    gdf_all[["district", "winner_party", "winner_rate", "match_type"]] = \
        gdf_all.apply(process_row, axis=1)

    exact_cnt = int((gdf_all["match_type"] == "exact").sum())
    fffd_cnt = int((gdf_all["match_type"].str.startswith("fffd", na=False)).sum())
    fuzzy_cnt = int((gdf_all["match_type"].str.startswith("fuzzy", na=False)).sum())
    none_cnt = int((gdf_all["match_type"] == "none").sum())

    # ---- 填色：按得票率配色（政黨 → 色階組；得票率 → 深淺）----
    gdf_all["fill_hex"] = [
        pick_rate_color(p, rt)
        for p, rt in zip(gdf_all["winner_party"], gdf_all["winner_rate"])
    ]

    has_data = gdf_all["match_type"] != "none"
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  取代字元萬用匹配  : {fffd_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    print(f"  無匹配（無資料）  : {none_cnt}")
    for p, n in gdf_all.loc[has_data, "winner_party"].value_counts().items():
        print(f"    領先村里：{p} {n} 村")
    _rate = gdf_all.loc[has_data, "winner_rate"].dropna()
    if len(_rate):
        print(f"    領先得票率範圍：{_rate.min():.2f}% ~ {_rate.max():.2f}%")
    for d in sorted(gdf_all.loc[has_data, "district"].dropna().unique()):
        sub = gdf_all[(gdf_all["district"] == d) & has_data]
        print(f"    第{int(d)}選區：{len(sub)} 里")

    records = gdf_all.copy()

    # 無匹配的里：按「區」兜底分配選區（僅當該區不拆分、只屬單一選區時），
    # 使選區邊界完整無缺口（避免 dissolve 缺口產生退化迴針）。
    town_district = records.loc[has_data].groupby("town_core")["district"].nunique()

    def _fill_district(row):
        if not np.isnan(row["district"]):
            return row["district"]
        if town_district.get(row["town_core"], 0) == 1:
            return records.loc[has_data & (records["town_core"] == row["town_core"]), "district"].iloc[0]
        return np.nan

    records["district_filled"] = records.apply(_fill_district, axis=1)
    print(f"  兜底後無選區里 : {int(records['district_filled'].isna().sum())}")

    # ① 村里層：村里界 1px
    villages = records[records["VILLNAME"].notna()].copy()
    if SIMPLIFY_TOL_M > 0:
        villages["geometry"] = villages.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
    # ② 區層：dissolve 以 (縣市, 區) 為鍵（含全部里，區界完整）
    townships = records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
    # ③ 立委選區層：dissolve 以選區號為鍵（含全部里）
    districts = records[records["district_filled"].notna()].dissolve(by="district_filled").reset_index()
    print(f"  縣市：{records['COUNTYNAME'].nunique()}，區：{len(townships)}，"
          f"立委選區：{len(districts)}，村里 {len(villages)}")

    # dissolve 後清理退化迴針與微孔洞（避免選區白帶/區界出現死線）
    townships = remove_ring_slits(townships)
    townships = clean_tiny_holes(townships)
    districts = remove_ring_slits(districts)
    districts = clean_tiny_holes(districts)

    # ----------------------畫布尺寸----------------------
    minx, miny, maxx, maxy = records.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny

    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m
    m_per_px = geo_w_m / w_px
    print(f"  統一比例尺：1像素 = {m_per_px:.4f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px")

    DPI = nat.DPI

    # ----------------------② 區界 + 縣市界 + 海岸線（線稿層，黑）----------------------
    print(f"  ② 區界 {LINE_TOWNSHIP_PX}px + 縣市界/海岸線 {LINE_OUTER_PX}px"
          f"（matplotlib + 閾值二值化）...")
    town_layer = render_line_layer(townships, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    print(f"  區/縣市界層：{int(town_layer.sum())} px"
          f"（區界 {LINE_TOWNSHIP_PX}px、縣市界/外輪廓 {LINE_OUTER_PX}px，閾值 {THRESHOLD_VAL}）")

    # 縣市界（含海岸線）幾何——供立委白線「讓位」判斷（重合段不畫白線）
    # 先剔除亞像素退化內環：村里間 <1m 的細縫若不剔除，difference 會把立委白線打洞
    _union_all = unary_union(records.geometry.tolist())
    _union_fix = drop_degenerate_holes(_union_all)
    _n_ring = lambda gm: sum(len(p.interiors) for p in
                             (gm.geoms if hasattr(gm, "geoms") else [gm])
                             if p.geom_type == "Polygon")
    _n_all, _n_kept = _n_ring(_union_all), _n_ring(_union_fix)
    print(f"  外輪廓退化內環：剔除 {_n_all - _n_kept} / {_n_all} 個＜"
          f"{HOLE_MIN_AREA_M2 / 1e4:.0f}ha 的亞像素細縫（村里間 <1m 縫隙，"
          f"不剔除會把立委白線打洞）")
    if _n_kept:
        _harea = sum(Polygon(r).area
                     for p in (_union_fix.geoms if hasattr(_union_fix, "geoms") else [_union_fix])
                     if p.geom_type == "Polygon" for r in p.interiors) / 1e6
        print(f"  保留內環 {_n_kept} 個（合計 {_harea:.2f} km²）＝真實水域鏤空"
              f"（如阿公店水庫）：以黑線描邊、內部填白（正常，非瑕疵）")
    else:
        print("  保留內環 0 個")
    outer_boundary = _union_fix.boundary
    del _union_all

    # ----------------------① 村里界 1px（黑）----------------------
    print("  ① 村里界 1px（1px 直繪 → thin 中心線）...")
    village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
    village_arr = draw_layer(village_lines, 1, w_px, h_px, minx, maxy, sx, sy)
    village_skel = thin(village_arr)
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # 對齊自檢：② 層必須覆蓋區界/縣市界 1px 原始線
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1,
                           w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
    print(f"  區/縣市界 1px 原始線 {int(_town_1px.sum())} px，"
          f"未被 {LINE_TOWNSHIP_PX}/{LINE_OUTER_PX}px 層覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層連通分量不應有 <=40px 的小分量
    _cc_n, _, _cc_st, _ = cv2.connectedComponentsWithStats(town_layer.astype(np.uint8), connectivity=8)
    _cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
    _cc_small = int((_cc_area <= 40).sum())
    print(f"  ② 層連通分量：{_cc_n - 1} 個；<=40px 小分量 {_cc_small} 個（應為 0）")

    lines_mask = village_skel | town_layer

    # 村里線自檢：扣掉 ② 層後不應出現 2x2 粗塊
    _v_only = village_skel & ~town_layer
    _2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
    print(f"  村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")

    # ----------------------③ 立委選區界 5px（白）----------------------
    # 規則：立委界與「縣市界（含海岸線）」重合的段 → 不畫白線（黑色縣市界優先）；
    #       其餘段（沿鄉鎮市區界、沿里界、跨里拆分處）→ 一律畫白線。
    # 作法（幾何法，不做遮罩相減——遮罩相減會因抗鋸齒差異在縣市界外緣留下白暈圈）：
    #   先把「與縣市界/海岸線重合」的段自立委界折線中剔除，再對剩餘段做 5px 緩衝帶。
    print(f"  ③ 立委選區界 {LINE_DISTRICT_PX}px（白；與縣市界重合處讓位黑線）...")
    half_w_m = LINE_DISTRICT_PX * m_per_px / 2.0
    district_boundary = districts.geometry.boundary.union_all()
    band_layer = np.zeros((h_px, w_px), dtype=bool)
    white_line = district_boundary
    if not district_boundary.is_empty:
        # 立委界 − 縣市界（含海岸線）：重合段一律剔除
        white_line = district_boundary.difference(outer_boundary.buffer(half_w_m))
        if not white_line.is_empty:
            band_geom = white_line.buffer(half_w_m)
            band_layer = render_poly_layer(band_geom, w_px, h_px, minx, maxx, miny, maxy,
                                           DPI, THRESHOLD_VAL)
            print(f"  立委界白線帶面積：{band_geom.area / 1e6:.2f} km²")
    electoral_white = band_layer
    _kept_km = (0.0 if white_line.is_empty else white_line.length) / 1000.0
    print(f"  立委界白線帶 {int(electoral_white.sum())} px"
          f"（保留內部段 ≈{_kept_km:.1f} km；與縣市界/海岸線重合段已剔除）")

    # 被剔除的立委界段＝① 與海岸線重合的海岸弧（正常）＋② 少數 GEOS 浮點碎片。
    # 碎片多半落在 T 形接頭或海面上（看不到），但若村里間亞像素細縫混進
    # outer_boundary，difference 會在**白線中段**挖掉一塊 → 白線中間冒黑點。
    # 這裡先把碎片記下來，稍後在「實際像素」上驗證（自檢 D）。
    _hole_frag = None
    _removed = district_boundary.difference(white_line) if not district_boundary.is_empty else None
    if _removed is not None and not _removed.is_empty:
        _hole_frag = _removed.difference(outer_boundary.buffer(half_w_m + 2.0))
        if _hole_frag.is_empty:
            _hole_frag = None
        print(f"  立委界剔除段 {_removed.length / 1000:.2f} km（海岸弧，正常）"
              + (f"；另 {_hole_frag.length:.2f} m 浮點碎片待像素自檢" if _hole_frag else "；無碎片"))
    else:
        print("  立委界剔除段：無（無海岸重合段）")
    del _removed

    # ----------------------填色（線稿為堤壩，逐塊洪水填充）----------------------
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）...")
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ----------------------疊加黑線----------------------
    arr[lines_mask] = 0
    print(f"  黑像素合計：{int(lines_mask.sum())}  非線連通區域：{ncomp - 1} 塊")

    # 自檢 A：油漆桶不變式——每塊非線 4-連通區域必須只含單一顏色（畫白線前）
    _nc, _nbad = nat.check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")

    # 自檢 B：與逐像素幾何參考的差異（畫白線前）
    _nw, _nout = nat.full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%；"
          f"村外非白 {_nout}；皆應 ≈0）")

    # ----------------------疊加立委選區界白線----------------------
    arr[electoral_white] = 255
    print(f"  立委選區界白線已疊加：{int(electoral_white.sum())} px")
    # 自檢 C：白線帶內不得殘留黑線（黑不該「卡在白線中間」）。
    # 注意：白帶若被 difference 打洞，洞內黑像素並不落在 band_layer 上，
    # 所以同時檢查「白線走廊」（白帶向外膨脹 1px）內的黑像素。
    _blk = (arr == 0).all(axis=2)
    _corridor = ndimage.binary_dilation(band_layer, structure=np.ones((3, 3), dtype=bool))
    print(f"  白線帶內殘留黑線：{int((_blk & band_layer).sum())} px（應為 0）；"
          f"白線帶邊緣(±1px)黑線 {int((_blk & _corridor).sum())} px（T 形接頭，正常）")
    del _corridor

    # 自檢 D：被剔除的浮點碎片若真的落在白線路徑上，就會留下黑點。
    # 以 1px 折線光柵化碎片位置，檢查該處是否為黑像素（應為 0）。
    if _hole_frag is not None:
        _frag_mask = draw_layer(extract_lines(_hole_frag), 1, w_px, h_px, minx, maxy, sx, sy)
        _vis = int((_blk & _frag_mask).sum())
        print(f"  {'✅' if _vis == 0 else '⚠️'} 被剔除碎片在白線路徑上殘留黑像素："
              f"{_vis} px（應為 0）")
        del _frag_mask
    else:
        print("  ✅ 無被剔除碎片（白線無打洞）")

    # 顏色驗證：全圖只應含允許色（得票率色階 + 純白底 + 純黑線）
    allowed = {(255, 255, 255), (0, 0, 0)}
    for stops in RATE_COLOR_STOPS:
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in nat.hex2rgb(hx)))
    _uniq, _cnt = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    _bad = [(tuple(int(x) for x in c), int(n))
            for c, n in zip(_uniq, _cnt) if tuple(int(x) for x in c) not in allowed]
    _n_bad = sum(n for _, n in _bad)
    print(f"  全圖顏色種類：{len(_uniq)}（允許 {len(allowed)}）；非允許色像素：{_n_bad} px（應為 0）")
    if _bad:
        print(f"  ⚠️ 非允許色：{_bad[:5]}")

    pil_img = Image.fromarray(arr, mode="RGB")
    del arr

    # ----------------------不畫標題、不畫圖例：直接輸出純地圖----------------------
    if SAVE_LAYER:
        _cmp = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
        _cmp[town_layer] = [200, 200, 200]          # ② 線稿層（區界+縣市界）淡灰
        _cmp[electoral_white] = [30, 60, 220]       # ③ 立委界白線帶 藍
        Image.fromarray(_cmp, mode="RGB").save(os.path.join(OUT_DIR, layer_name))

    W, H = pil_img.size
    try:
        pil_img.save(OUT_PNG)
    except OSError:
        import time as _t
        for _ in range(6):
            _t.sleep(0.5)
            try:
                pil_img.save(OUT_PNG)
                break
            except OSError:
                continue
        else:
            print(f"  ⚠️ 無法寫入 {OUT_PNG}（可能被檢視器鎖定，請關閉後重跑）")
    del pil_img

    # 存檔後自檢（白線像素以黑線計，讓幾何參考比對忽略之）
    _re = np.asarray(Image.open(OUT_PNG).convert("RGB"))
    _re_map = _re[:H, :W]
    _u2, _c2 = np.unique(_re_map.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _check = _re_map.copy()
    _check[electoral_white] = 0
    _nw2, _nout2 = nat.full_geom_check(_check, records, w_px, h_px, minx, maxy, sx, sy)
    _tol2 = 0.0002 * w_px * h_px
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、"
          f"幾何參考差異 {_nw2} px（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    if _bad2 or _nout2 or _nw2 > _tol2:
        print(f"  ⚠️ bad={_bad2[:5]} wrong={_nw2} out={_nout2}")
    print(f"\n  Saved: {OUT_PNG}  ({W}×{H}px)")
    print("==== All finished ====")


# ===================== 圖資清理 =====================
def strip_far_parts(gdf, max_dist_nameless=REMOTE_MAX_DIST_M, max_dist_named=NAMED_MAX_DIST_M):
    """剔除遠離本島的離島圖斑與圖資錯誤碎塊（高雄縣無離島，此為安全護欄）。"""
    parts, owner = [], []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for pp in ps:
            parts.append(pp)
            owner.append(i)
    if not parts:
        return gdf
    merged = unary_union(parts)
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)

    vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
    named = (~vv.isin(["", "nan", "None"])).to_numpy()
    thr = np.where(named[np.array(owner, dtype=int)], max_dist_named, max_dist_nameless)
    dist = np.array([main.distance(pp) for pp in parts])
    keep_flags = dist <= thr

    dropped = np.nonzero(~keep_flags)[0]
    if len(dropped):
        print(f"  離島/碎塊清理：剔除 {len(dropped)} 個圖斑")

    idx0 = 0
    rebuilt = []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kp = [ps[k] for k in range(len(ps)) if keep_flags[idx0 + k]]
        idx0 += len(ps)
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


# ===================== 線稿工具 =====================
def _despike_ring(coords, tol=5.0, area_thr=5000.0, min_path=100.0):
    """折疊單一線環中的「迴針／零寬裂縫」退化子路徑（去而復返、面積近乎 0）。

    三道門檻（位移 tol、長度 min_path、面積 area_thr）確保真實的半島、岬角、
    細長沙洲不會被誤刪。
    """
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
        d[:i + 2] = np.inf            # 至少隔 2 個點才算「繞了一大圈」
        if i == 0:
            d[n - 1] = np.inf         # 排除線環正常的首尾閉合
        j = int(np.argmin(d))
        if d[j] <= tol:
            seg = P[i:j + 1]
            path_len = float(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])).sum())
            _x, _y = seg[:, 0], seg[:, 1]
            area = 0.5 * abs(np.dot(_x[:-1], _y[1:]) - np.dot(_x[1:], _y[:-1]))
            if path_len > min_path and area < area_thr:
                dead[i + 1:j] = True  # 折疊此迴針
        i += 1
    return P[~dead]


def remove_ring_slits(gdf, tol=5.0, area_thr=5000.0, min_path=100.0, verbose=True):
    """移除區層／選區層多邊形外環/內環的退化迴針（見 _despike_ring）。"""
    n_ring_fixed = 0

    def _fix(geom):
        nonlocal n_ring_fixed
        if geom is None or geom.is_empty:
            return geom
        out = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            ext = _despike_ring(poly.exterior.coords, tol, area_thr, min_path)
            if len(ext) != len(poly.exterior.coords):
                n_ring_fixed += 1
            holes = []
            for r in poly.interiors:
                h = _despike_ring(r.coords, tol, area_thr, min_path)
                if len(h) != len(r.coords):
                    n_ring_fixed += 1
                if len(h) >= 4:
                    holes.append(h)
            out.append(Polygon(ext, holes).buffer(0))
        if not out:
            return geom
        return out[0] if len(out) == 1 else MultiPolygon(out)

    o = gdf.copy()
    o["geometry"] = o.geometry.apply(_fix)
    o = o[~o.geometry.isna() & ~o.geometry.is_empty].copy().reset_index(drop=True)
    if verbose:
        print(f"  迴針清理：修正 {n_ring_fixed} 個線環" if n_ring_fixed else "  迴針清理：無退化迴針")
    return o


def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)與過小碎片（dissolve 浮點誤差造成的微孔）。"""
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kept = []
        for poly in parts:
            if poly.geom_type != "Polygon":
                continue
            if poly.area < min_area:
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


def drop_degenerate_holes(geom, min_area=HOLE_MIN_AREA_M2):
    """剔除（多）邊形中面積 < min_area 的退化內環（洞）。

    為什麼要做這件事：
      村里界圖資相鄰兩里有時只差 <1m（亞像素）沒接上，unary_union 後這個細縫
      就變成一個「面積≈0 的內環」。內環會被 `.boundary` 當成外輪廓（海岸線）
      看待——於是 (a) 被畫成 5px 粗黑線，(b) 在立委白線 difference 時把白線打洞，
      結果白線中間冒出黑點。
      真正的海岸線/水域在這個圖資中不會以「內環」形式存在（水域是獨立圖斑），
      因此把面積 < min_area 的內環一律填平是安全的。
    """
    if geom is None or geom.is_empty:
        return geom
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    kept = []
    for p in parts:
        if p.geom_type != "Polygon":
            continue
        holes = [r for r in p.interiors if Polygon(r).area >= min_area]
        kept.append(Polygon(p.exterior, holes))
    if not kept:
        return geom
    return kept[0] if len(kept) == 1 else MultiPolygon(kept)


def to_px(coords, minx, maxy, sx, sy):
    """像素網格約定：像素 i 中心 = minx+(i+0.5)/sx（floor，與 matplotlib 渲染網格一致）"""
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def extract_lines(gs):
    if hasattr(gs, "geoms"):
        parts = list(gs.geoms)
    else:
        parts = [gs]
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
    """Bresenham 逐段描繪 width 像素寬的純黑白線，返回 bool 陣列"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords, minx, maxy, sx, sy)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


def _render_mask(draw_fn, w_px, h_px, minx, maxx, miny, maxy, dpi, threshold):
    """把 draw_fn(ax) 的繪製結果以 matplotlib(Agg) 光柵化 → 二值化 → 純黑白遮罩。"""
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    draw_fn(ax)
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


def render_line_layer(gdf, w_px, h_px, minx, maxx, miny, maxy,
                      town_px, outer_px, dpi, threshold):
    """matplotlib 繪區面+區界+縣市界/海岸線 → 二值化 → 純黑線層。

    區界畫 town_px px；縣市界（各縣市聯集的邊界，含海岸線）與全體外輪廓
    畫 outer_px px——縣市交界以較粗線清楚分隔。"""
    px2pt = 72.0 / dpi
    town_lw = town_px * px2pt
    outer_lw = outer_px * px2pt

    def _draw(ax):
        gdf.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=town_lw)
        gdf.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=town_lw)
        # 縣市界：各縣市自身聯集的邊界（含海岸線）
        # 先剔除亞像素退化內環，否則村里間 <1m 的細縫會被當成海岸線畫成粗黑線
        for _, sub in gdf.groupby("COUNTYNAME"):
            cbd = drop_degenerate_holes(unary_union(sub.geometry)).boundary
            gpd.GeoSeries([cbd]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
        # 全體外輪廓（海岸線）
        outer = drop_degenerate_holes(unary_union(gdf.geometry)).boundary
        gpd.GeoSeries([outer]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)

    return _render_mask(_draw, w_px, h_px, minx, maxx, miny, maxy, dpi, threshold)


def render_poly_layer(geom, w_px, h_px, minx, maxx, miny, maxy, dpi, threshold):
    """把一個（多）邊形整塊填黑再二值化 → 遮罩；用於立委選區界的白色擦除帶。"""
    def _draw(ax):
        gpd.GeoSeries([geom]).plot(ax=ax, facecolor="black", edgecolor="black",
                                   linewidth=0, antialiased=False)

    return _render_mask(_draw, w_px, h_px, minx, maxx, miny, maxy, dpi, threshold)


if __name__ == "__main__":
    main()
