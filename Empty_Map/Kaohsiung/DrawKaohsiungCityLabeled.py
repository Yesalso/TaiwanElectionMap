# -*- coding: utf-8 -*-
"""
高雄市 · 村里界 + 區界地圖 —— 村里 1px + 區界/市界/海岸線 2px（可選著色/標註）
（由 DrawTainanCityLabeled.py 派生；繪圖邏輯完全一致，僅換縣市、輸出路徑與密集區清單）
兩層各自獨立繪製，最後做聯集疊加：
  1. 純黑白 Bresenham 描繪（無抗鋸齒灰階），分兩層依序疊加：
       ① 村里層（1px）——海南 Empty_Map/Hainan_town_county_1px_labeled.py 的「鄉鎮畫法」：
          1px 直繪 → skimage.morphology.thin 取中心線，全市村里界 1px；
       ② 區界 + 市界 + 海岸線（2px）——Empty_Map/DrawNewTaipei.py 的畫法：
          只取 TOWNNAME 層級的區（高雄市為「區」制，不碰村里資料），matplotlib(Agg, DPI=100) 以
          linewidth = LINE_TOWNSHIP_PT*DPI/72 pt 繪製區面與區界
          （區面的外框就是市界與海岸線，故 coastline 自動同寬，不需另外處理），
          再用閾值 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑 2px 線層。
     疊加：lines_mask = ①1px 裡層 | ②2px 區/市界層（黑疊黑）；
     兩層用同一套像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加處不會錯開 1px。
  2. 可選區 5 色填充（相鄰不同色，圖著色 · 貪心 5 色），WITH_FILL 開關；
     色盤由 PALETTE_KEY（環境變數）決定：
       PALETTE_KEY == "kaohsiung_main"（預設）→ 原本固定 5 色盤（主圖不變）；
       其他 key（= 各獨立放大圖的輸出名稱）→ 固定種子隨機配色，各圖互異；
  3. 可選地名標註（智慧標註：質心/代表點/內縮質心候選 → 壓線檢測 → 16 方向平移搜尋
     → 字號逐級縮小 → 保底加白邊暈圈）、跨單元標註互斥、微小村里改圓圈編號 + 圖例、
     MingLiU（細明體，刪點陣表走 glyf 輪廓）+ Matplotlib(DPI=100) 閾值 200 二值化，
     WITH_LABELS 開關；
     ★ 標註優先權：里的名字是主體，不可為了區名而移動／縮小／刪除。
       繪製順序固定為  村里名 → 編號圓圈 → 區名。
     ★ 需求①（區名不壓村里名）：區名先原地＋16 方向平移搜尋，讓不開就「持續縮字」
       （下限 TOWN_FONT_MIN，主圖 20px／放大圖 24px），再不行才在「本區扣掉所有禁區框
       後的空曠區塊」找落點；
       只有真的無處可放時才允許重疊並記錄告警。也就是說區名大小是可調的，
       而村里名位置永遠不動。
     ★ 需求②（編號過多的區改出獨立圖）：一個區內「需要編號圓圈的村里」超過
       MAX_NUM_PER_TOWN(=6) 個時，該區在主圖上「不再打編號」（避免一坨數字糊在一起），
       並把清單寫入 STANDALONE_FILE（Kaohsiung/_standalone_towns_ks.txt）；
       DrawKaohsiungDense.py 依此清單為每個超標區出一張 1px≈5.45m（設定 6m）的獨立
       放大圖；放大圖上「不用數字」，塞不下的微小村里一律靠繼續縮字＋描邊暈圈標出。
     其他標註前處理：
       - 村里名先去中括號（源資料以 [ ] 標記罕用字）；
       - 環境變數 DENSE_STANDALONE（或 _standalone_towns_ks.txt）指定的區，
         主圖不畫編號圓圈。
★ 高雄市特有處理（本檔與臺南版的唯一實質差異）：
   - 源資料 901 筆中有 11 筆 VILLNAME 為空：9 筆是市區的港區/軍港/工業區水域
     （小港、鹽埕、苓雅、楠梓、岡山、鼓山、旗津、左營、前鎮），
     另 2 筆是旗津區代管的離島「東沙群島」「南沙群島（太平島）」。
     沿用臺南邏輯以 VILLNAME.notna() 過濾 → 離島不會被畫出來（且不會撐爆畫布），
     港區/水域則留白（該處本就是水面，視覺上正確）。
     另加一道 EXPLICIT_ISLAND_BBOX 硬性排除，確保任何離島都不可能被畫出。
   - 密集區清單 DENSE_TOWNS 由臺南（安南/安平/中西/北/南/永康/東）換成
     高雄市區 11 區：鹽埕/鼓山/左營/楠梓/三民/新興/前金/苓雅/前鎮/旗津/小港。
輸出（依開關）：
  WITH_FILL=False, WITH_LABELS=False → Kaohsiung/KaohsiungCity_VillageDistrict_Plain.png
  WITH_LABELS=True                   → Kaohsiung/KaohsiungCity_VillageDistrict_Labeled.png
"""
import os
import math
import random
import colorsys
import warnings
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import Point, Polygon as ShPolygon, box as ShBox
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import thin
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None

# ===================== 配置 =====================
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
SHARED_DIR = r"D:\Windows\TaiwanElection\Empty_Map"          # 共用資源（字體輪廓快取）
out_dir = r"D:\Windows\TaiwanElection\Empty_Map\Kaohsiung"   # 本專案輸出目錄
final_dir = out_dir

TARGET_COUNTY = "高雄市"
TARGET_CRS = "EPSG:3826"

# ★ 高雄市離島排除（含東沙群島、南沙群島/太平島）
#   源資料裡這兩筆的 VILLNAME 為空，本來就會被 notna() 過濾掉；
#   這裡再補一道「代表點必須落在本島範圍內」的硬性關卡，雙重保險。
EXPLICIT_ISLAND_BBOX = (150000.0, 2450000.0, 280000.0, 2620000.0)  # EPSG:3826

# 比例尺：1px = 10m，再放大 10%
# 高雄市 bbox 約 89679 x 110977 m（已排除離島），故地圖約 10062x12452 px
METERS_PER_PIXEL = 10.0
SCALE_UP = 1.10
MAX_PX = 12000
PAD_FRAC = 0.01          # 地圖四周留白

# ★ 關閉簡化（修掉「多餘線條」的關鍵，與 DrawTainanCity.py 一致）
#   simplify 是「按弦長取捨」：緩彎長段只要偏離 < 2m 就被塌縮成一條長直線，
#   憑空造出橫貫村里的斜直線。1px ≈ 9.09m 遠大於 2m，保留原始採點不會讓圖變髒。
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（保留原始測量採點）

# 線寬
LINE_VILLAGE_PX = 1      # ① 村里界（PIL 直繪寬度）
LINE_TOWNSHIP_PT = 1     # ② matplotlib 線寬(pt)：閾值後約 2px
THRESHOLD_VAL = 40       # ② 二值化閾值（沿用 DrawNewTaipei.py）
SAVE_LAYER = False       # ② 層是否單獨存檔（預設關閉，避免產出多餘預覽圖）

# ★ 微孔洞清理（修掉「散點」的關鍵，與 DrawTainanCity.py 一致）
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為雜訊，填平
# ==================================================

# 輸出開關
WITH_FILL = True         # 區著色填充
WITH_LABELS = True       # 地名標註（文字 + 編號圓圈 + 圖例）

# 畫布右側圖例區
LEGEND_W = 700
LEGEND_FONT = 40
LEGEND_HEAD_FONT = 42
LEGEND_TITLE = "村里編號圖例"
LEGEND_X_PAD = 60
LEGEND_DY = 66
LEGEND_DY_MIN = 40       # 行距下限（行數太多時壓縮到此值，再放不下就自動分欄）
LEGEND_BOTTOM_PAD = 110
CIRCLE_R = 22            # 編號圓圈半徑（px），放不下時逐級縮小

# ---------- 標註配置（字號對應本圖 1px≈9.09m） ----------
FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）
GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；
#                          放大圖 DrawKaohsiungDense.py 會調到 12）
# 村里字號分檔：(面積上限 px², 初始字號)
VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]
# 區（TOWNNAME）字號分檔
TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]
# ★ 標註方式門檻（面積 px²）：
#   面積 >= NUMBER_AREA_PX               → 標中文地名（塞不下時自動退回編號圓圈）
#   面積 <  NUMBER_AREA_PX               → 直接用編號圓圈（放不下地名）
#   面積 <  CIRCLE_MIN_AREA_PX           → 太小，連圓圈都不畫
NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）
CIRCLE_MIN_AREA_PX = 0.0  # 小於此面積連編號圓圈都不畫（0 = 不設限）
# ★ 地名塞不下時要不要改畫編號圓圈：
#   True  = 改畫編號圓圈（主圖：面積不足者本來就走圓圈，這裡是「連字都塞不下」的兜底）
#   False = 不用數字，一律用「繼續縮字 → 網格掃描 → 描邊暈圈」把中文地名標上去（放大圖）
NUMBER_WHEN_TEXT_FAILS = True
TEXT_MARGIN_PX = 4.0     # 文字框距本單元邊界最小間隙（px）
LINE_STEP_PX = 6         # 平移搜尋步長（px）
LINE_MAX_STEPS = 30      # 平移搜尋最大步數
BASE_BUFFER_PX = 78      # 內縮質心基準距離（px）
HALO_MAX_FS = 36         # 字號 ≤ 此值的標籤加白邊暈圈（與細線隔離）

TOWN_GUARD_PX = 10.0
TOWN_BRANCH_MIN_PX = 34  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）
TOWN_FONT_MIN = 20       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）；放大圖用 24
# 主圖上「已獨立出圖的區」不標編號圓圈
#   ★ 這份清單每次執行都「重新判定」，結果整檔覆寫到 _standalone_towns_ks.txt；
#     不在這裡讀回舊檔（否則某區村里數變少、跌破門檻後仍會殘留在清單裡，
#     統計與出圖都會多出一張不必要的放大圖）。
#     想手動追加區 → 環境變數 DENSE_STANDALONE="鳳山區,岡山區"
_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()
STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]

# 文字渲染：Matplotlib(DPI=100) 渲染 MingLiU + 閾值 200 二值化，行距 1.5 倍字號
MPL_DPI = 100
BIN_THRESHOLD = 200
LH = 1.5
# ==================================================

# ---------- 密集區標註策略 ----------
# 高雄市區 11 區（原高雄市直轄市範圍）村里細碎，主圖 1px=9.09m 下多數村里放不下中文地名。
# 規則：主圖「只標能塞得下中文地名的村里」，塞不下的「不畫編號圓圈」，
#       改由另一張放大圖（1px≈5.45m）DrawKaohsiungDense.py 標註。
DENSE_TOWNS = ["鹽埕區", "鼓山區", "左營區", "楠梓區", "三民區", "新興區",
               "前金區", "苓雅區", "前鎮區", "旗津區", "小港區"]
# 主圖上這些區的村里若面積小於此值 → 直接跳過（不標文字也不標圓圈）
DENSE_SKIP_AREA_PX = 15000
# ★ 需求②：一個區內「需要編號圓圈」的村里超過此值時，該區在主圖上不再打編號
#   （避免一坨數字糊在一起），改由 DrawKaohsiungDense.py 出該區的獨立放大圖
#   （1px≈5.45m，逐里標中文地名、不用數字）。判定結果寫入 STANDALONE_FILE 供該腳本讀取。
MAX_NUM_PER_TOWN = 6
STANDALONE_FILE = os.path.join(final_dir, "_standalone_towns_ks.txt")
# 子程序（DrawKaohsiungDense.py exec 本檔時）不要覆寫清單檔，以免蓋掉主圖的判定結果
KS_WRITE_STANDALONE = os.environ.get("KS_CHILD_RUN", "") != "1"
# ==================================================

warnings.filterwarnings("ignore")
os.makedirs(out_dir, exist_ok=True)

# ---------- 字體（MingLiU 細明體；刪內嵌點陣表供 Matplotlib 使用） ----------
def find_font_file():
    for p in ["C:/Users/Windows/AppData/Local/Microsoft/Windows/Fonts/mingliu.TTF",
              "C:/Users/Windows/AppData/Local/Microsoft/Windows/Fonts/mingliu_0.TTF",
              "C:/Windows/Fonts/mingliu.ttc",
              "C:/Windows/Fonts/simsun.ttc"]:     # 兜底
        if os.path.exists(p):
            return p, 0
    return None, 0

FONT_PATH, FONT_IDX = find_font_file() if WITH_LABELS else (None, 0)
if WITH_LABELS:
    print("使用字體：", FONT_PATH)

    from fontTools import ttLib as _ttLib
    MPL_FONT_PATH = FONT_PATH
    try:
        # 字體輪廓快取放共用目錄（與臺南共用同一份 4MB 檔，不重複產生）
        _outline_cache = os.path.join(SHARED_DIR, "_mingliu_outline.ttf")
        if not os.path.exists(_outline_cache):
            _f = _ttLib.TTFont(FONT_PATH, fontNumber=FONT_IDX)
            for _tag in ("EBDT", "EBLC", "EBSC", "bdat", "bloc"):
                if _tag in _f:
                    del _f[_tag]
            _f.save(_outline_cache)
        MPL_FONT_PATH = _outline_cache
        print("Matplotlib 用純輪廓字體：", MPL_FONT_PATH)
    except Exception as _e:
        print("⚠️ 點陣表刪除失敗，Matplotlib 直接用原字體：", _e)


_fonts = {}


def get_font(fs):
    if fs not in _fonts:
        _fonts[fs] = ImageFont.truetype(FONT_PATH, fs, index=FONT_IDX)
    return _fonts[fs]


_scratch = ImageDraw.Draw(Image.new("L", (8, 8)))


def measure(lines, font):
    """多行文字塊外包尺寸（px）"""
    w = 0
    for ln in lines:
        l, t, r, b = _scratch.textbbox((0, 0), ln, font=font)
        w = max(w, r - l)
    h = (len(lines) - 1) * font.size * LH + font.size
    return w, h


# ---------- 讀取 SHP ----------
gdf = gpd.read_file(shp_path, encoding="UTF-8")
if gdf.crs is None:
    gdf.crs = "EPSG:4326"
gdf = gdf.to_crs(TARGET_CRS)
print(f"原始要素數：{len(gdf)}")

# 診斷：本縣市共幾筆、其中 VILLNAME 為空（港區/水域/離島）幾筆
_cks = gdf[gdf["COUNTYNAME"] == TARGET_COUNTY]
_n_nan = int(_cks["VILLNAME"].isna().sum())
print(f"{TARGET_COUNTY}：全 {len(_cks)} 筆，其中 VILLNAME 為空（港區/水域/離島）{_n_nan} 筆 → 不繪製")

villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())
               & (gdf["TOWNNAME"].notna())].copy()
villages["geometry"] = villages.geometry.buffer(0)
villages = villages[~villages.geometry.isna() & ~villages.geometry.is_empty].copy()
villages["VILLNAME"] = villages["VILLNAME"].astype(str).str.strip()
villages["TOWNNAME"] = villages["TOWNNAME"].astype(str).str.strip()

# ★ 高雄市離島硬性排除（東沙群島 / 南沙群島-太平島）
#   這兩筆的 VILLNAME 為空，上面 notna() 已擋掉；此處再以「代表點是否落在本島 bbox 內」
#   做第二道關卡，確保任何離島都不可能被畫進來（也不會撐爆畫布）。
_isx0, _isy0, _isx1, _isy1 = EXPLICIT_ISLAND_BBOX
_rp = villages.geometry.representative_point()
_in_box = (_rp.x >= _isx0) & (_rp.x <= _isx1) & (_rp.y >= _isy0) & (_rp.y <= _isy1)
if (~_in_box).any():
    _bad = villages.loc[~_in_box, ["TOWNNAME", "VILLNAME"]]
    print(f"★ 離島排除：再踢掉 {int((~_in_box).sum())} 筆 → "
          f"{list(zip(_bad['TOWNNAME'], _bad['VILLNAME']))}")
    villages = villages[_in_box].copy()

# ★ 需求②：SHP 源資料把罕用字/異體字用中括號標記，例如安南區「公[塭]里」「[塭]南里」。
#   塭 字在 MingLiU 是有的（已核對 cmap），所以直接把中括號去掉即可。
#   涵蓋半角 [ ] 與全角 ［ ］，避免只清一半。
_NAME_BRACKETS = str.maketrans("", "", "[]［］")
villages["VILLNAME"] = villages["VILLNAME"].str.translate(_NAME_BRACKETS).str.strip()
villages["TOWNNAME"] = villages["TOWNNAME"].str.translate(_NAME_BRACKETS).str.strip()
_brk = gdf["VILLNAME"].astype(str).str.contains(r"[\[\]［］]", regex=True, na=False)
if _brk.any():
    _names = sorted(gdf.loc[_brk, "VILLNAME"].astype(str).unique())
    print(f"村里名去中括號：{len(_names)} 個 → {_names}")
villages = villages[["TOWNNAME", "VILLNAME", "geometry"]].reset_index(drop=True)

villages_unsimplified = villages.copy()   # 供簡化自檢比對用

if SIMPLIFY_TOL_M > 0:
    villages["geometry"] = villages.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
print(f"村里幾何清理完成（簡化 {SIMPLIFY_TOL_M}m），有效 {int(villages.geometry.is_valid.sum())}/{len(villages)}")

townships = villages.dissolve(by="TOWNNAME").reset_index()

# ★ 非村里圖斑（港區／水域／軍區／工業區）是否併入「區面」
#   源資料中高雄市有 9 筆 TOWNNAME 有值、VILLNAME 為空的圖斑：
#     旗津區 4.034 km²（高雄港水域）、小港區 3.434、岡山區 3.130（空軍基地）、
#     前鎮區 2.829、左營區 2.702（海軍左營軍港）、鼓山區 1.426、楠梓區 0.355、
#     苓雅區 0.230、鹽埕區 0.089 —— 行政上屬於該區，但不屬任何村里。
#   False（預設）＝沿用臺南邏輯：不併入 → 這些位置留白。港區/水域留白視覺上合理，
#                   但岡山空軍基地等「陸地」會在區內形成白色缺口。
#   True         ＝併入區面 → 全市為完整實心輪廓、無缺口；代價是高雄港水域會被
#                   填成旗津/前鎮/小港的顏色，並在港區長出細長「手指」狀色塊。
INCLUDE_NONVILLAGE_PARCELS = False

if INCLUDE_NONVILLAGE_PARCELS:
    _keep_t = set(villages["TOWNNAME"].unique())
    _parcels = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY)
                   & (gdf["TOWNNAME"].notna())
                   & (gdf["TOWNNAME"].astype(str).str.strip().isin(_keep_t))].copy()
    _parcels["geometry"] = _parcels.geometry.buffer(0)
    _parcels = _parcels[~_parcels.geometry.isna() & ~_parcels.geometry.is_empty].copy()
    _parcels["TOWNNAME"] = _parcels["TOWNNAME"].astype(str).str.strip()
    _prp = _parcels.geometry.representative_point()
    _parcels = _parcels[(_prp.x >= _isx0) & (_prp.x <= _isx1)
                        & (_prp.y >= _isy0) & (_prp.y <= _isy1)].copy()
    townships = _parcels[["TOWNNAME", "geometry"]].dissolve(by="TOWNNAME").reset_index()
    print(f"★ 非村里圖斑已併入區面：{len(_parcels)} 筆（區數 {len(townships)}）")

print(f"{TARGET_COUNTY} 區：{len(townships)}，村里 {len(villages)}")


# ---------- 清理微小內環（散點元兇，與 DrawTainanCity.py 同） ----------
def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)與過小碎片，避免 ② 層描出細碎散點。"""
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
            holes = [r for r in poly.interiors if ShPolygon(r).area >= min_area]
            kept.append(ShPolygon(poly.exterior, holes))
        if not kept:
            return geom
        from shapely.geometry import MultiPolygon as ShMultiPolygon
        return kept[0] if len(kept) == 1 else ShMultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


_hb = sum(len(p.interiors) for g0 in townships.geometry
          for p in ([g0] if g0.geom_type == "Polygon" else list(g0.geoms)))
townships = clean_tiny_holes(townships)
_ha = sum(len(p.interiors) for g0 in townships.geometry
          for p in ([g0] if g0.geom_type == "Polygon" else list(g0.geoms)))
print(f"微孔洞清理：內環 {_hb} → {_ha}（移除 {_hb - _ha} 個 < {HOLE_MIN_AREA_M2:.0f}m² 的洞）")

# ---------- 畫布尺寸 ----------
minx, miny, maxx, maxy = villages.total_bounds
geo_w, geo_h = maxx - minx, maxy - miny
pad_x, pad_y = PAD_FRAC * geo_w, PAD_FRAC * geo_h
minx -= pad_x
maxx += pad_x
miny -= pad_y
maxy += pad_y
geo_w, geo_h = maxx - minx, maxy - miny

scale = max(geo_w / MAX_PX, geo_h / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
w_px = int(math.ceil(geo_w / scale))
h_px = int(math.ceil(geo_h / scale))
sx, sy = w_px / geo_w, h_px / geo_h
CANVAS_W = w_px + (LEGEND_W if WITH_LABELS else 0)
CANVAS_H = h_px
Y_OFF = 0
print(f"比例尺 1px = {geo_w / w_px:.4f} m，範圍 {geo_w:.0f}×{geo_h:.0f} m，"
      f"地圖 {w_px}×{h_px}，畫布 {CANVAS_W}×{CANVAS_H}")

# ---------- 行政區著色（WITH_FILL 時：相鄰不同色，圖著色 · 貪心 5 色） ----------
# 色盤由 PALETTE_KEY 決定。
#   PALETTE_KEY == "kaohsiung_main"（預設）→ 沿用原本固定的 5 色盤（主圖不變）；
#   其他 key（= 各獨立放大圖的輸出名稱）→ 以固定種子隨機生成淡雅色盤，
#   於是各放大圖配色互異、但同一張圖可重現。
PALETTE_KEY = os.environ.get("PALETTE_KEY", "kaohsiung_main").strip()

# 原本的固定 5 色盤（主圖專用，保持不變）
PALETTE_FIXED = [(0xc7, 0xcd, 0xe7),   # 淺紫藍
                 (0xf8, 0xc7, 0xdc),   # 淺粉
                 (0xfa, 0xe0, 0xbf),   # 淺橙
                 (0xff, 0xfd, 0xd7),   # 淺黃
                 (0xc5, 0xe4, 0xd4)]   # 淺綠


def _make_palette(key, n=5):
    """由 key 生成 n 個穩定、淡雅、彼此可辨的填充色（明度高、飽和度中低）"""
    rng = random.Random(f"taiwan-map-palette::{key}")
    hues = list(np.linspace(0.0, 1.0, n, endpoint=False))
    rng.shuffle(hues)          # 打散色相順序 → 每次不同但仍穩定可重現
    out = []
    for h in hues:
        hh = (h + rng.uniform(-0.035, 0.035)) % 1.0
        s = rng.uniform(0.18, 0.34)      # 低飽和 → 淡雅，不搶黑色線界
        v = rng.uniform(0.90, 0.97)      # 高明度 → 白底上柔和
        r, g, b = colorsys.hsv_to_rgb(hh, s, v)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


PALETTE = PALETTE_FIXED if PALETTE_KEY == "kaohsiung_main" else _make_palette(PALETTE_KEY)
N_COLORS = len(PALETTE)
print(f"配色鍵 {PALETTE_KEY} → 色盤 " +
      "、".join("#%02x%02x%02x" % c for c in PALETTE) +
      ("（原本固定 5 色）" if PALETTE_KEY == "kaohsiung_main" else "（隨機生成）"))

_adj_geoms = list(townships.geometry)
_n_t = len(_adj_geoms)
color_of = None
if WITH_FILL:
    print("\n行政區著色（相鄰不同色）...")
    from shapely.strtree import STRtree
    _tree = STRtree(_adj_geoms)
    adj = [set() for _ in range(_n_t)]
    for _i, _g in enumerate(_adj_geoms):
        _gb = _g.boundary
        for _j in _tree.query(_g.buffer(100.0)):      # 100m 緩衝取候選
            _j = int(_j)
            if _j == _i:
                continue
            if _gb.intersection(_adj_geoms[_j].boundary).length > 50.0:   # 共享邊界 >50m
                adj[_i].add(_j)
                adj[_j].add(_i)

    color_of = [-1] * _n_t
    for _i in sorted(range(_n_t), key=lambda k: -len(adj[k])):   # 度數降序（難點先著色）
        used = {color_of[j] for j in adj[_i] if color_of[j] >= 0}
        color_of[_i] = next((c for c in range(N_COLORS) if c not in used),
                            min(range(N_COLORS),
                                key=lambda c: sum(1 for j in adj[_i] if color_of[j] == c)))
    _conf = sum(1 for i in range(_n_t) for j in adj[i]
                if j > i and color_of[i] == color_of[j])
    print(f"區數 {_n_t}，鄰接對 {sum(len(a) for a in adj) // 2}，"
          f"著色衝突 {int(_conf)}（應為 0），色數 {N_COLORS}")


# ---------- 收集矢量邊界線 ----------
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


# 像素網格約定：像素 i 的中心對應 minx+(i+0.5)/sx，與 matplotlib 的渲染網格一致，
# ①（1px 村里層）與 ②（2px 區/市界層）疊加才不會錯開 1px（故用 floor 而非 round）
def to_px(coords):
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def draw_layer(lines, width=1):
    """Bresenham 逐段描繪（width 像素寬的純黑白線），返回 bool 陣列"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


S3 = np.ones((3, 3), dtype=bool)

# ---------- ① 村里界 1px：海南「鄉鎮畫法」1px 直繪 → thin 中心線 ----------
print("\n① 村里界 1px（1px 直繪 → thin 中心線）...")
village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
village_arr = draw_layer(village_lines, 1)
village_skel = thin(village_arr)
print(f"村里層 {LINE_VILLAGE_PX}px 中心線：{int(village_skel.sum())} px"
      f"（1px 線 {int(village_arr.sum())} px）")

# ---------- ② 區界 + 市界 + 海岸線 2px：DrawNewTaipei.py 畫法 ----------
print("② 區界/市界/海岸線 2px（matplotlib + 閾值二值化）...")
DPI = 100
_fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
_ax = _fig.add_axes([0, 0, 1, 1])
_ax.set_xlim(minx, maxx)
_ax.set_ylim(miny, maxy)
_ax.set_facecolor("white")
_lw = LINE_TOWNSHIP_PT * (DPI / 72.0)
townships.plot(ax=_ax, edgecolor="black", facecolor="white", linewidth=_lw)
townships.geometry.boundary.plot(ax=_ax, edgecolor="black", facecolor="none", linewidth=_lw)
_ax.axis("off")
_buf = BytesIO()
plt.savefig(_buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="white")
plt.close(_fig)
_buf.seek(0)
_img = cv2.imdecode(np.frombuffer(_buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
_buf.close()
_gray = cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY)
del _img
_, _tmask = cv2.threshold(_gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
del _gray
town_layer = _tmask > 0          # 純黑 2px 線層（區界 + 市界 + 海岸線），不含村里線
print(f"區/市界層：{int(town_layer.sum())} px"
      f"（線寬 {LINE_TOWNSHIP_PT}pt={_lw:.2f}px，閾值 {THRESHOLD_VAL}）")

# 對齊自檢：② 層必須覆蓋區界 1px 原始線（含市界/海岸線），否則兩層網格不一致
_town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1)
_miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
print(f"區界+市界 1px 原始線 {int(_town_1px.sum())} px，未被 2px 層覆蓋 {_miss} px（應 ≈0）")
del _town_1px

# ★ 簡化自檢：simplify 會把緩彎拉直成橫貫村里的斜直線（「多餘線條」元兇）
_straight_min = 500.0


def _long_straight_count(gdf, min_len):
    n = 0
    for geom in gdf.geometry:
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for p in parts:
            if p.geom_type != "Polygon":
                continue
            coords = list(p.exterior.coords)
            for i in range(len(coords) - 1):
                x0, y0 = coords[i]
                x1, y1 = coords[i + 1]
                if math.hypot(x1 - x0, y1 - y0) >= min_len:
                    n += 1
    return n


_na = _long_straight_count(villages_unsimplified, _straight_min)
_nb = _long_straight_count(villages, _straight_min)
print(f"簡化自檢（{SIMPLIFY_TOL_M}m）：>={_straight_min:.0f}m 直段 "
      f"原始 {_na} → 簡化後 {_nb}（應持平；暴增表示緩彎被拉直成多餘斜線）")
if _nb > _na * 1.5 + 5:
    print(f"⚠️ 簡化造出 {_nb - _na} 條額外長直段，建議把 SIMPLIFY_TOL_M 調小或設為 0")

# ---------- 疊加：村里 1px 層 | 區/市界 2px 層 ----------
lines_mask = village_skel | town_layer
# 村里線自檢：扣掉 2px 層後不應出現 2x2 連續黑塊（1px 線不會有 2x2 方塊）
_v_only = village_skel & ~town_layer
_2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
print(f"村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")
# 鼓包自檢：2px 線僅允許在交叉點出現 3x3 全黑，4x4 以上應 ≈0
_e3 = ndimage.binary_erosion(lines_mask, structure=np.ones((3, 3), dtype=bool))
_e4 = ndimage.binary_erosion(lines_mask, structure=np.ones((4, 4), dtype=bool))
_e5 = ndimage.binary_erosion(lines_mask, structure=np.ones((5, 5), dtype=bool))
print(f"粗細自檢：3x3 全黑 {int(_e3.sum())} px（僅交叉點），4x4 {int(_e4.sum())}，5x5 {int(_e5.sum())}")
print(f"黑像素合計：{int(lines_mask.sum())}")
if SAVE_LAYER:
    _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    _la[town_layer] = 0
    _lp = os.path.join(out_dir, "layer_kaohsiung_district_2px.png")
    try:
        Image.fromarray(_la, mode="RGB").save(_lp)
        print("② 層單獨輸出:", _lp)
    except OSError as _e:
        print("⚠️ ② 層輸出失敗（可忽略）:", _e)

# ---------- 底圖（WITH_FILL 時區按色光柵化填充 + 黑色線界疊加） ----------
fill_arr = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
if WITH_FILL:
    for _i in range(_n_t):
        _g = _adj_geoms[_i]
        _parts = _g.geoms if hasattr(_g, "geoms") else [_g]
        _col = PALETTE[color_of[_i]]
        for _poly in _parts:
            if _poly is None or _poly.is_empty or _poly.geom_type != "Polygon":
                continue
            _ext = to_px(_poly.exterior.coords)
            _xs = [p[0] for p in _ext]
            _ys = [p[1] for p in _ext]
            _x0 = max(0, min(_xs)); _x1 = min(w_px, max(_xs) + 1)
            _y0 = max(0, min(_ys)); _y1 = min(h_px, max(_ys) + 1)
            if _x1 <= _x0 or _y1 <= _y0:
                continue
            _im = Image.new("L", (_x1 - _x0, _y1 - _y0), 0)
            _dd = ImageDraw.Draw(_im)
            _dd.polygon([(px - _x0, py - _y0) for px, py in _ext], fill=1)
            for _ring in _poly.interiors:      # 內環（洞）保持底色
                _rin = to_px(_ring.coords)
                _dd.polygon([(px - _x0, py - _y0) for px, py in _rin], fill=0)
            _m = np.asarray(_im, dtype=bool)
            fill_arr[_y0:_y1, _x0:_x1][_m] = _col

rgb_map = fill_arr.copy()
rgb_map[lines_mask] = 0     # 線界（村里 1px + 區/市界 2px）以純黑疊加在彩填上

# ===================== 地名標註 =====================
map_img = Image.fromarray(rgb_map, mode="RGB")
canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
canvas.paste(map_img, (0, Y_OFF))
d = ImageDraw.Draw(canvas)
text_jobs = []   # (lines, fs, cx, cy_canvas, anchor, halo) —— 統一 Matplotlib 渲染後二值化

placed = []          # 已放置標籤/圓圈的佔用框（shapely box，px）
text_boxes = []      # (種類, 框)：種類 "town" = 區名、"village" = 村里名，供疊壓自檢
town_boxes = []      # 僅「區名」框，外擴 TOWN_GUARD_PX 後作為村里標籤的硬性禁區
circle_info = []     # (編號, 村里名, 半徑, x, y)
DIRS = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
        for a in np.arange(0, 360, 22.5)]



def spot_ok(p, w, h, boundary, margin=TEXT_MARGIN_PX, forbid=None):
    """文字框是否既不壓本單元邊界、也不與已放置標籤衝突
    （forbid：額外禁區形狀清單，供區名避讓村里名使用）"""
    bx = ShBox(p.x - w / 2 - margin, p.y - h / 2 - margin,
               p.x + w / 2 + margin, p.y + h / 2 + margin)
    if bx.intersects(boundary):
        return None
    if forbid and any(bx.intersects(fb) for fb in forbid):
        return None
    for pb in placed:
        if bx.intersects(pb):
            return None
    return bx


def translate_search(geom, boundary, p0, w, h, step=LINE_STEP_PX, max_steps=LINE_MAX_STEPS,
                     forbid=None):
    """16 方向平移搜尋可放置位置（forbid = 額外硬性禁區，例如村里名框）"""
    best, best_d = None, -1.0
    for ddx, ddy in DIRS:
        for i in range(1, max_steps + 1):
            p = Point(p0.x + ddx * step * i, p0.y + ddy * step * i)
            if not geom.contains(p):
                break
            bx = spot_ok(p, w, h, boundary, forbid=forbid)
            if bx is not None:
                return p, bx
            dd = p.distance(boundary)
            if dd > best_d:
                best_d, best = dd, p
    return best, None


def candidate_points(geom):
    """標籤候選點（質心 / 代表點 / 多級內縮質心）"""
    cands = [geom.centroid, geom.representative_point()]
    for r in (0.8, 0.5, 0.3, 0.1):
        try:
            b = geom.buffer(-BASE_BUFFER_PX * r)
            if b.is_valid and not b.is_empty and b.area > 50:
                cands.append(b.centroid)
        except Exception:
            pass
    out = []
    for p in cands:
        try:
            if not (geom.contains(p) or geom.touches(p)):
                continue
        except Exception:
            continue
        if any(p.distance(q) < 0.5 for q in out):
            continue
        out.append(p)
    return out


def _draw_lines(p, lines, font, halo=False):
    """登記文字任務（地圖座標 → 畫布座標）"""
    text_jobs.append((list(lines), font.size, p.x, p.y + Y_OFF, "mm", halo))


def build_text_variants(name):
    """原樣 → 後綴斷行（XX鎮/鄉/市/區/里/村）→ 平衡斷行"""
    variants = [name]

    def add(t):
        if t and t not in variants:
            variants.append(t)

    for suf in ("鎮", "鄉", "市", "區", "里", "村", "市鎮"):
        if name.endswith(suf) and len(name) - len(suf) >= 3:
            add(name[:-len(suf)] + "\n" + suf)
            break
    if len(name) >= 5 and "\n" not in name:
        half = (len(name) + 1) // 2
        add(name[:half] + "\n" + name[half:])
    return variants


def _block(p, w, h):
    return ShBox(p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2)


def _sep(bx, pb):
    """帶符號分離度：不相交返回框間距（越大越好），相交返回負的交疊深度"""
    if bx.intersects(pb):
        ax0, ay0, ax1, ay1 = bx.bounds
        bx0, by0, bx1, by1 = pb.bounds
        ow = min(ax1, bx1) - max(ax0, bx0)
        oh = min(ay1, by1) - max(ay0, by0)
        return -min(ow, oh)
    return bx.distance(pb)


def _blocked(p, w, h, boundary):
    bx = _block(p, w, h)
    if bx.intersects(boundary):
        return True
    return any(bx.intersects(pb) for pb in placed)


def _avoid_spot(geom, boundary, w, h, radius=28, step=2, start=None):
    """保底位置搜尋：優先找「不壓本單元邊界、且不與已放置標籤衝突」的位置；
    全找不到時退而求其次，取「離邊界與既有標籤最遠」的點。"""
    p0 = start if start is not None else geom.representative_point()
    offs = [(ddx * step * i, ddy * step * i)
            for i in range(1, radius // step + 1) for ddx, ddy in DIRS]
    inside = [p0] + [Point(p0.x + ox, p0.y + oy) for ox, oy in offs
                     if geom.contains(Point(p0.x + ox, p0.y + oy))]

    # ---- 階段 1：完全乾淨 ----
    best, best_s = None, -1.0
    for p in inside:
        if _blocked(p, w, h, boundary):
            continue
        bx = _block(p, w, h)
        s = bx.distance(boundary)
        for pb in placed:
            s = min(s, bx.distance(pb))
        if s > best_s:
            best_s, best = s, p
    if best is not None:
        return best

    # ---- 階段 2：允許與既有標籤略微重疊，取分離度最佳者 ----
    best, best_s = p0, -1e18
    for p in inside:
        bx = _block(p, w, h)
        s = min((_sep(bx, pb) for pb in placed), default=0.0)
        s += 0.05 * min(p.distance(boundary), 20.0)
        if s > best_s:
            best_s, best = s, p
    return best


def _avoid_spot_outside(geom, w, h, forbidden, reach=200, ring=6):
    """區名專用的最後手段：允許離開本區邊界，在附近找一個「離村里名最遠」的落點。
    村里名是主體，所以區名寧可略微出界（或壓到區界線）也不去蓋住村里名。
    回傳 (位置, 是否仍有重疊)。"""
    p0 = geom.representative_point()
    best, best_s = p0, -1e18
    for r in range(0, reach + 1, ring):
        for ddx, ddy in DIRS:
            p = Point(p0.x + ddx * r, p0.y + ddy * r)
            bx = _block(p, w, h)
            # 離最近村里名框的距離（>0 表示完全不重疊）
            d = min((bx.distance(fb) for fb in forbidden), default=1e6)
            s = min(d, 60.0) - 0.05 * p.distance(p0)   # 越近原區中心越好（仍看得出歸屬）
            if s > best_s:
                best_s, best = s, p
        if min((_block(best, w, h).distance(fb) for fb in forbidden),
               default=1e6) > 0:
            break          # 已找到完全不重疊的落點，不必再外推
    clash = min((_block(best, w, h).distance(fb) for fb in forbidden),
                default=1e6) <= 0
    return best, clash


def _aabb_arr(boxes):
    """把一堆 shapely 框轉成 (N,4) 的 numpy bbox 陣列（快速碰撞預篩用）"""
    if not boxes:
        return np.zeros((0, 4), dtype=float)
    return np.asarray([b.bounds for b in boxes], dtype=float)


def _aabb_clear(bb, arr):
    """bb=(x0,y0,x1,y1) 是否與 arr(Nx4) 全部框都不相交（含相接）。

    所有框都是軸對齊矩形，所以「回傳 True」保證真的不相交（保守判定 → 安全可跳過精確檢查）。
    """
    if arr is None or len(arr) == 0:
        return True
    x0, y0, x1, y1 = bb
    return not bool(np.any((arr[:, 0] <= x1) & (arr[:, 2] >= x0) &
                           (arr[:, 1] <= y1) & (arr[:, 3] >= y0)))


def free_grid_search(geom, w, h, avoid, step=None, pad_frac=0.10):
    """需求① 的最後一道（在「允許重疊」之前）：在本區（略外擴）bbox 內做 2D 網格掃描，
    找出與村里名/圓圈/既有區名「完全不重疊」的落點。

    優先回傳「落在本區內、且離代表點最近」的落點；區內真的找不到才退到區外最近的落點。
    回傳 (Point, 是否在本區內) 或 (None, False)。
    """
    arr = _aabb_arr(list(avoid))
    if len(arr) == 0:
        return None, False
    x0, y0, x1, y1 = geom.bounds
    _px, _py = (x1 - x0) * pad_frac, (y1 - y0) * pad_frac
    x0 -= _px
    x1 += _px
    y0 -= _py
    y1 += _py
    if step is None:
        step = max(6.0, min(w, h) * 0.5)
    p0 = geom.representative_point()
    best_in, best_in_d = None, None
    best_out, best_out_d = None, None
    nx = int((x1 - x0) / step) + 1
    ny = int((y1 - y0) / step) + 1
    for _ix in range(nx):
        cx = x0 + _ix * step
        for _iy in range(ny):
            cy = y0 + _iy * step
            if not _aabb_clear((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), arr):
                continue
            _d = math.hypot(cx - p0.x, cy - p0.y)
            if geom.contains(Point(cx, cy)):
                if best_in_d is None or _d < best_in_d:
                    best_in, best_in_d = Point(cx, cy), _d
            elif best_out_d is None or _d < best_out_d:
                best_out, best_out_d = Point(cx, cy), _d
    if best_in is not None:
        return best_in, True
    return best_out, False


def grid_spot_inside(inner, geom, w, h, avoid, step=None, max_cells=22500):
    """2D 網格掃描：找一個「整個文字框都落在 inner 內、且與 avoid 完全不重疊」的落點。

    這是「盡可能縮小字體把地名標滿」的核心：只要單元內還有任一塊夠大的空地，
    即使不在質心附近，也能被找到（平移搜尋只看 16 個方向、常常漏掉斜向的空隙）。
    優先回傳離代表點最近者。回傳 Point 或 None。
    """
    arr = _aabb_arr(list(avoid))
    x0, y0, x1, y1 = geom.bounds
    span = max(x1 - x0, y1 - y0)
    if step is None:
        step = max(4.0, min(w, h) * 0.5)
    step = max(step, span / 150.0)          # 上限 150x150 格，避免大單元掃描過久
    p0 = geom.representative_point()
    best, best_d = None, None
    nx = int((x1 - x0) / step) + 1
    ny = int((y1 - y0) / step) + 1
    for _ix in range(nx):
        cx = x0 + _ix * step
        for _iy in range(ny):
            cy = y0 + _iy * step
            if not _aabb_clear((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), arr):
                continue
            if not inner.contains(ShBox(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)):
                continue
            _d = math.hypot(cx - p0.x, cy - p0.y)
            if best_d is None or _d < best_d:
                best, best_d = Point(cx, cy), _d
    return best


def free_spot_candidates(geom, forbidden, margin=TEXT_MARGIN_PX, top=20):
    """需求①：在本區多邊形內「扣掉所有禁區框」後，取出空曠區塊的候選落點。

    用途：區名縮字後仍找不到位置時，直接在真正的空白處找點，
    避免落入「允許重疊」的兜底（村里名位置永不動，所以寧可把區名縮小、挪到空白處）。
    """
    try:
        area = geom.buffer(-margin)
    except Exception:
        return []
    if area is None or area.is_empty:
        return []
    if forbidden:
        try:
            area = area.difference(unary_union(list(forbidden)))
        except Exception:
            pass
    if area is None or area.is_empty:
        return []
    parts = list(area.geoms) if hasattr(area, "geoms") else [area]
    parts = [p for p in parts if p.geom_type in ("Polygon", "MultiPolygon")]
    parts.sort(key=lambda p: -p.area)
    out = []
    for p in parts[:top]:
        try:
            out.append(p.representative_point())
            out.append(p.centroid)
        except Exception:
            pass
    return out


def draw_text_label(geom, name, tiers, f_min=FONT_MIN, allow_fallback=True,
                    grid_min_f=None):
    """放置村里名（村里名是主體，落點即最終落點，不被區名影響）。

    三輪落點策略（一輪比一輪放寬，目標是「把地名標滿、盡量不用數字」）：
      ① 候選點（質心／代表點／內縮質心）＋ 16 方向平移搜尋，字號 f_def → f_min
         —— 框必須完整落在本村里內、且不與既有標籤重疊；
      ② 網格掃描（字號 f_min-1 → grid_min_f）：同樣要求框在本村里內，
         但會把村里內每一塊空地都掃過，補足「平移只看 16 方向」的盲區；
      ③ 外擴網格掃描（同字號範圍）：允許框壓到本村里的界線（不壓別的標籤），
         純幾何上根本塞不下的細碎村里由這一輪接手。
    以上三輪都失敗時：
      allow_fallback=True  → 保底：描邊暈圈硬標（回傳 False，但地名一定畫得出來）；
      allow_fallback=False → 什麼都不登記、回傳 False，由呼叫端改畫編號圓圈。
    """
    boundary = geom.boundary
    area_px = geom.area
    f_def = next(fs for lim, fs in tiers if area_px < lim)
    variants = build_text_variants(name)
    cands = candidate_points(geom) or [geom.representative_point()]

    def _commit(p, lines, font, halo, w, h):
        _draw_lines(p, lines, font, halo=halo)
        _bx = ShBox(p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2)
        placed.append(_bx)
        text_boxes.append(("village", _bx))

    # ---- ① 候選點 ＋ 平移搜尋 ----
    for fs in range(f_def, f_min - 1, -1):
        font = get_font(fs)
        for txt in variants:
            lines = txt.split("\n")
            w, h = measure(lines, font)
            for p0 in cands:
                bx = spot_ok(p0, w, h, boundary)
                if bx is not None:
                    _commit(p0, lines, font, fs <= HALO_MAX_FS, w, h)
                    return True
                if geom.area < w * h:
                    continue  # 多邊形根本裝不下，平移無意義
                p2, bx2 = translate_search(geom, boundary, p0, w, h)
                if p2 is not None and bx2 is not None:
                    _commit(p2, lines, font, fs <= HALO_MAX_FS, w, h)
                    return True

    if grid_min_f is not None and grid_min_f < f_min:
        # ---- ② 網格掃描（框必須完整在本村里內）----
        try:
            inner = geom.buffer(-TEXT_MARGIN_PX)
        except Exception:
            inner = None
        if inner is not None and not inner.is_empty:
            for fs in range(f_min - 1, grid_min_f - 1, -1):
                font = get_font(fs)
                for txt in variants:
                    lines = txt.split("\n")
                    w, h = measure(lines, font)
                    p = grid_spot_inside(inner, geom, w, h, placed)
                    if p is not None:
                        _commit(p, lines, font, fs <= HALO_MAX_FS, w, h)
                        return True
        # ---- ③ 外擴網格掃描（允許壓到本村里的界線，但不壓別的標籤）----
        for fs in range(f_min - 1, grid_min_f - 1, -1):
            font = get_font(fs)
            for txt in variants:
                lines = txt.split("\n")
                w, h = measure(lines, font)
                p, _inside = free_grid_search(geom, w, h, placed, pad_frac=0.35)
                if p is not None:
                    _commit(p, lines, font, True, w, h)
                    return True

    if not allow_fallback:
        return False
    # 保底：全變體中選最緊湊者，先做避讓搜尋，仍壓線則描邊直放
    font = get_font(f_min)
    best_txt, best_w, best_h = None, None, None
    for txt in variants:
        lines = txt.split("\n")
        w, h = measure(lines, font)
        if best_txt is None or w + h < best_w + best_h:
            best_txt, best_w, best_h = txt, w, h
    p = _avoid_spot(geom, boundary, best_w, best_h)
    lines = best_txt.split("\n")
    halo = _blocked(p, best_w, best_h, boundary)
    _draw_lines(p, lines, font, halo=halo)
    _bx = _block(p, best_w, best_h)
    placed.append(_bx)
    text_boxes.append(("village", _bx))
    return False


def _fit_number_font(snum, r):
    fs = int(r * 1.5) if len(snum) == 1 else int(r * 1.15)
    while fs > 8:
        bb = _scratch.textbbox((0, 0), snum, font=get_font(fs))
        if bb[2] - bb[0] <= 2 * r - 5:
            break
        fs -= 1
    return get_font(fs)


def _draw_circle(p, r, snum, fnt):
    """圓圈用 PIL 硬邊直接繪製（純黑白），圈內數字走文字任務（不加暈圈）"""
    cy = p.y + Y_OFF
    d.ellipse([p.x - r, cy - r, p.x + r, cy + r],
              fill=(255, 255, 255), outline=(0, 0, 0), width=(4 if r >= 20 else 2))
    text_jobs.append(([snum], fnt.size, p.x, cy, "mm", False))


def draw_number_label(geom, num, name):
    boundary = geom.boundary
    snum = str(num)
    if geom.area >= math.pi * CIRCLE_R ** 2:
        rmax = CIRCLE_R
    else:
        rmax = min(CIRCLE_R, max(14, int(math.sqrt(geom.area / math.pi) * 0.75)))
    for r in range(min(rmax, CIRCLE_R), 13, -1):
        fnt = _fit_number_font(snum, r)
        w = h = 2.0 * r
        for p0 in candidate_points(geom) or [geom.representative_point()]:
            bx = spot_ok(p0, w, h, boundary, margin=1.2)
            if bx is None and geom.area > w * h:
                p0b, bxb = translate_search(geom, boundary, p0, w, h, step=2, max_steps=12)
                if p0b is not None and bxb is not None:
                    p0, bx = p0b, bxb
            if bx is not None:
                _draw_circle(p0, r, snum, fnt)
                placed.append(ShBox(p0.x - r, p0.y - r, p0.x + r, p0.y + r))
                circle_info.append((num, name, r, p0.x, p0.y))
                return True
    # 保底：圈心留在自家多邊形內，小步挪動以帶符號分離度打分遠離已放置圈/標籤
    p0 = geom.representative_point()
    best_s, best_r, best_p, best_fnt = -1e18, None, p0, None
    for r in range(min(rmax, 18), 13, -1):
        fnt = _fit_number_font(snum, r)
        for ddx, ddy in DIRS:
            for i in range(0, 8):
                p = Point(p0.x + ddx * 3.0 * i, p0.y + ddy * 3.0 * i)
                if i > 0 and not geom.contains(p):
                    continue
                bx = _block(p, 2 * r, 2 * r)
                s = min((_sep(bx, pb) for pb in placed), default=0.0)
                s += 0.05 * min(p.distance(boundary), 10.0)
                if s > best_s:
                    best_s, best_r, best_p, best_fnt = s, r, p, fnt
        if best_s >= 0:
            break
    if best_s < 0 and best_r is not None:      # 二輪精修：1px 網格微調
        for ddx in range(-16, 17):
            for ddy in range(-16, 17):
                p = Point(best_p.x + ddx * 1.0, best_p.y + ddy * 1.0)
                if not geom.contains(p):
                    continue
                bx = _block(p, 2 * best_r, 2 * best_r)
                s = min((_sep(bx, pb) for pb in placed), default=0.0)
                s += 0.05 * min(p.distance(boundary), 10.0)
                if s > best_s:
                    best_s, best_p = s, p
    if best_r is None:      # 極端保底：用最小半徑放在代表點
        best_r = 14
        best_p = geom.representative_point()
        best_fnt = _fit_number_font(snum, best_r)
    r = best_r
    _draw_circle(best_p, r, snum, best_fnt)
    placed.append(_block(best_p, 2 * r, 2 * r))
    circle_info.append((num, name, r, best_p.x, best_p.y))
    return False


def to_px_geom(g):
    """米制幾何 → 像素幾何（取最大圖斑用於標註）"""
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    best = None
    for poly in parts:
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        ext = [((x - minx) * sx, (maxy - y) * sy) for x, y in poly.exterior.coords]
        ints = [[((x - minx) * sx, (maxy - y) * sy) for x, y in ring.coords]
                for ring in poly.interiors]
        try:
            sp = ShPolygon(ext, ints)
        except Exception:
            continue
        if best is None or sp.area > best.area:
            best = sp
    return best


if WITH_LABELS:
    # ---------- 統計各里面積（像素），決定標註方式 ----------
    villages["area_m2"] = villages.geometry.area
    villages["area_px"] = villages["area_m2"] / (geo_w / w_px) ** 2

    # ★ 標註方式（三分法，門檻皆為 px²）：
    #     面積 >= NUMBER_AREA_PX           → 標中文地名
    #     面積 <  NUMBER_AREA_PX           → 改用編號圓圈（放不下地名）
    #     面積 <  CIRCLE_MIN_AREA_PX       → 太小，連圓圈都不畫
    #   另外兩種「塞不下就改編號」的情形：
    #     ① 面積 >= NUMBER_AREA_PX 但描繪時「真的塞不下地名」（見 allow_fallback=False）
    #        → 直接在該村里位置改畫編號圓圈（不再用描邊硬壓別人）；
    #     ② 密集 11 區在主圖另有更嚴門檻 DENSE_SKIP_AREA_PX（小於該值在主圖完全不畫，
    #        改由 1px≈5.45m 的放大圖呈現）。
    _is_dense = villages["TOWNNAME"].isin(DENSE_TOWNS)
    _too_small = villages["area_px"] < NUMBER_AREA_PX
    _skip_main = _is_dense & (villages["area_px"] < DENSE_SKIP_AREA_PX)
    _hidden = _skip_main | (villages["area_px"] < CIRCLE_MIN_AREA_PX)
    print(f"密集 11 區 {DENSE_TOWNS}：村里 {int(_is_dense.sum())} 個，"
          f"其中主圖跳過（面積 < {DENSE_SKIP_AREA_PX}px²，改由放大圖標註）"
          f"{int(_skip_main.sum())} 個")

    small_area = villages[~_hidden & _too_small].copy()   # 面積不足 → 直接編號
    big = villages[~_hidden & ~_too_small].copy()         # 先試中文地名
    print(f"村里標註初判：中文地名候選 {len(big)} 個、"
          f"編號圓圈 {len(small_area)} 個（面積 < {NUMBER_AREA_PX:.0f}px² ≈ "
          f"{NUMBER_AREA_PX * (geo_w / w_px) ** 2 / 1e6:.2f} km²）")

    # ---------- 標註順序（需求① 核心）----------
    #   里的名字是主體：先把村里名放好、落點即最終落點；區名再主動避讓村里名。
    #   1) 村里文字（中文名，優先權最高；塞不下者改編號圓圈）
    #   2) 編號圓圈
    #   3) 區名（大字，避讓 1)/2) 的佔位；讓不開就持續縮字，絕不壓村里名）
    print("\n地名標註 ...")
    n_town_fallback = 0
    n_town_overlap = 0
    n_numbered = 0

    # ---- 1) 村里中文名（不可被移動／縮小／刪除）----
    #   NUMBER_WHEN_TEXT_FAILS=False（放大圖）→ allow_fallback=True：
    #     塞不下就繼續縮字／網格掃描／描邊暈圈，地名一定標得出來，絕不用數字。
    #   NUMBER_WHEN_TEXT_FAILS=True（主圖）→ allow_fallback=False：
    #     真的塞不下才回傳 False，由下方改畫編號圓圈。
    _use_number_backup = NUMBER_WHEN_TEXT_FAILS
    _text_fail = []
    for _, row in big.sort_values("area_px", ascending=False).iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            if _use_number_backup:
                _text_fail.append(row)
            continue
        _ok = draw_text_label(gpx, row["VILLNAME"], VILLAGE_TIERS,
                              allow_fallback=(not _use_number_backup),
                              grid_min_f=GRID_FONT_MIN)
        if not _ok and _use_number_backup:
            _text_fail.append(row)
    if _use_number_backup:
        print(f"村里文字標註：{len(big)} 個嘗試，成功 {len(big) - len(_text_fail)} 個；"
              f"塞不下 → 改用編號圓圈 {len(_text_fail)} 個")
    else:
        print(f"村里文字標註：{len(big)} 個嘗試，全部以中文地名標出"
              f"（塞不下者自動縮字＋描邊暈圈，不使用數字）")

    # ---- 2) 彙整「所有需要編號的村里」= 面積不足者 + 塞不下地名者 ----
    small = small_area
    if _text_fail:
        small = pd.concat([small, pd.DataFrame(_text_fail)], ignore_index=True)

    # ★ 需求②：一個區內需要編號的村里超過 MAX_NUM_PER_TOWN 個 → 該區在主圖上不再打編號，
    #   改由 DrawKaohsiungDense.py 出獨立放大圖（逐里中文標註）。
    _cnt_by_town = small.groupby("TOWNNAME").size().to_dict()
    _auto_standalone = sorted(t for t, c in _cnt_by_town.items() if c > MAX_NUM_PER_TOWN)
    # 完整列出每個區的編號村里數（>0 才列），方便核對超標判定口徑
    _overview = "、".join(f"{t}({c})" for t, c in
                          sorted(_cnt_by_town.items(), key=lambda kv: (-kv[1], kv[0])) if c > 0)
    print(f"各區編號村里數：{_overview if _overview else '（無）'}")
    print(f"★ 編號超過 {MAX_NUM_PER_TOWN} 個的區（主圖不標序號，改出獨立放大圖）"
          f"{len(_auto_standalone)} 個：" +
          ("、".join(f"{t}({_cnt_by_town[t]})" for t in _auto_standalone)
           if _auto_standalone else "（無）"))
    STANDALONE_ALL = sorted(set(_auto_standalone) | set(STANDALONE_TOWNS))
    if STANDALONE_ALL:
        _sa_cir = small["TOWNNAME"].isin(STANDALONE_ALL)
        print(f"獨立出圖區 {STANDALONE_ALL}：主圖不標序號 {int(_sa_cir.sum())} 個")
        small = small[~_sa_cir].copy()
    if KS_WRITE_STANDALONE:
        with open(STANDALONE_FILE, "w", encoding="utf-8") as _f:
            _f.write(",".join(STANDALONE_ALL))
        print(f"獨立出圖清單已寫出 → {STANDALONE_FILE}（{len(STANDALONE_ALL)} 區）")

    # 編號順序：先按區、再按村里名（圖例自然分組）
    small = small.sort_values(["TOWNNAME", "VILLNAME"]).reset_index(drop=True)
    small["num"] = np.arange(1, len(small) + 1)
    print(f"村里標註方式：文字 {len(big) - len(_text_fail)} 個，編號圓圈 {len(small)} 個")

    # ---------- 圖例版面（按區分組，置於右側；行數過多自動分欄） ----------
    #   （修掉舊版以 {村里名: 編號} 為鍵的寫法：跨區同名里會互相覆蓋、圖例漏項）
    town_order = sorted(townships["TOWNNAME"].tolist())
    legend_lines = []      # (類型, 文字)
    if len(small):         # 無編號圓圈時不出圖例
        legend_lines.append(("title", LEGEND_TITLE))
        for t in town_order:
            sub = small[small["TOWNNAME"] == t].sort_values("num")
            if not len(sub):
                continue
            legend_lines.append(("head", t))
            for _, r in sub.iterrows():
                legend_lines.append(("item", f'{int(r["num"])}. {r["VILLNAME"]}'))
    n_lines = len(legend_lines)
    _avail_h = CANVAS_H - 60 - LEGEND_BOTTOM_PAD
    legend_cols = 1
    while legend_cols < 4 and n_lines > (max(1, _avail_h // LEGEND_DY_MIN)) * legend_cols:
        legend_cols += 1
    rows_per_col = max(1, int(math.ceil(n_lines / legend_cols)))
    LEGEND_DY_USE = LEGEND_DY
    if rows_per_col > 1 and (rows_per_col - 1) * LEGEND_DY_USE > _avail_h:
        LEGEND_DY_USE = max(LEGEND_DY_MIN, int(_avail_h / (rows_per_col - 1)))
    LEGEND_Y0 = max(60, CANVAS_H - LEGEND_BOTTOM_PAD
                    - (rows_per_col - 1) * LEGEND_DY_USE)
    print(f"圖例 {n_lines} 行，{legend_cols} 欄（每欄 {rows_per_col} 行），"
          f"y0={LEGEND_Y0}，行距 {LEGEND_DY_USE}")
    # 需要多欄時先把畫布加寬（右側圖例區），並重取 ImageDraw；無圖例則裁掉右側空白
    if legend_cols > 1:
        _old_canvas = canvas
        CANVAS_W = w_px + LEGEND_W * legend_cols
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
        canvas.paste(_old_canvas, (0, 0))
        d = ImageDraw.Draw(canvas)
        print(f"  畫布加寬至 {CANVAS_W}×{CANVAS_H}（圖例 {legend_cols} 欄）")
    elif n_lines == 0:
        _old_canvas = canvas
        CANVAS_W = w_px
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
        canvas.paste(_old_canvas, (0, 0))
        d = ImageDraw.Draw(canvas)
        print(f"  本圖無編號圖例 → 畫布裁掉右側圖例區（{CANVAS_W}×{CANVAS_H}）")

    # ---------- 圖例文字（右側，按區分組） ----------
    for i, (kind, txt) in enumerate(legend_lines):
        _col, _row = i // rows_per_col, i % rows_per_col
        _bx = w_px + LEGEND_X_PAD + _col * LEGEND_W
        _by = LEGEND_Y0 + _row * LEGEND_DY_USE
        if kind == "title":
            text_jobs.append(([txt], LEGEND_HEAD_FONT + 4, _bx, _by, "lm", False))
        elif kind == "head":
            text_jobs.append(([txt], LEGEND_HEAD_FONT, _bx + 14, _by, "lm", False))
        else:
            text_jobs.append(([txt], LEGEND_FONT, _bx + 48, _by, "lm", False))

    # ---- 3) 編號圓圈（面積不足 + 塞不下地名的村里）----
    for _, row in small.sort_values("area_px").iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            continue
        if draw_number_label(gpx, int(row["num"]), row["VILLNAME"]):
            n_numbered += 1
    print(f"編號圓圈：{n_numbered} 個（保底 {len(small) - n_numbered} 個）")

    # ---- 4) 區名（大字）—— 主動避讓村里名/圓圈；寧可縮字，也不壓村里名 ----
    #   村里名框（外擴 TOWN_GUARD_PX）與圓圈框構成區名的禁區。區名落點順序：
    #     ① 由大字開始（f_def → TOWN_BRANCH_MIN_PX）：質心/代表點 + 16 方向平移搜尋；
    #     ② 讓不開 → 繼續縮字（→ TOWN_FONT_MIN），改在「本區扣掉禁區後的空曠區塊」找點；
    #     ③ 縮到底仍無位（極罕見）→ 才允許離開區界/重疊，並記錄告警。
    _village_blocks = [bx for _k, bx in text_boxes if _k == "village"]
    _circle_blocks = [ShBox(x - r, y - r, x + r, y + r)
                      for _n, _nm, r, x, y in circle_info]
    _tf = tuple([bx.buffer(TOWN_GUARD_PX) for bx in _village_blocks] +
                [bx.buffer(TOWN_GUARD_PX * 0.5) for bx in _circle_blocks])

    def _place_town(p, lines, font, w, h):
        _draw_lines(p, lines, font, halo=(font.size <= HALO_MAX_FS))
        _tb = ShBox(p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2)
        placed.append(_tb)
        text_boxes.append(("town", _tb))
        town_boxes.append(_tb.buffer(TOWN_GUARD_PX))

    def _try_town(nm, gpx, fs, cands, translate_all=True, translate_top=0):
        """在給定字號下，為區名找一個「不壓村里名/圓圈/既有區名、也不出區界」的落點"""
        font = get_font(fs)
        boundary = gpx.boundary
        for txt in build_text_variants(nm):
            lines = txt.split("\n")
            w, h = measure(lines, font)
            for i, p0 in enumerate(cands):
                bx = spot_ok(p0, w, h, boundary, forbid=_tf)
                if bx is not None:
                    return p0, lines, font, w, h
                if translate_all or i < translate_top:
                    p2, bx2 = translate_search(gpx, boundary, p0, w, h, forbid=_tf)
                    if p2 is not None and bx2 is not None:
                        return p2, lines, font, w, h
        return None

    n_town_shrunk = 0
    n_town_grid = 0
    for _, row in townships.sort_values("TOWNNAME", ascending=False).iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            continue
        nm = row["TOWNNAME"]
        f_def = next(fs for lim, fs in TOWNSHIP_TIERS if gpx.area < lim)
        _base_cands = candidate_points(gpx) or [gpx.representative_point()]

        res = None
        # ① 大字優先
        for fs in range(f_def, TOWN_BRANCH_MIN_PX - 1, -2):
            res = _try_town(nm, gpx, fs, _base_cands)
            if res:
                break
        # ② 仍無位 → 繼續縮字，改在「扣掉禁區後的空曠區塊」找點
        if not res:
            _free_cands = free_spot_candidates(gpx, _tf)
            for fs in range(TOWN_BRANCH_MIN_PX - 1, TOWN_FONT_MIN - 1, -1):
                res = _try_town(nm, gpx, fs, _free_cands,
                                translate_all=False, translate_top=6)
                if res:
                    n_town_shrunk += 1
                    break
        # ③ 仍無位 → 2D 網格掃描（寧可離開本區邊界，也要與村里名/圓圈完全不重疊）
        if not res:
            _out_res = None
            for fs in range(TOWN_BRANCH_MIN_PX - 1, TOWN_FONT_MIN - 1, -2):
                font = get_font(fs)
                txt = min(build_text_variants(nm),
                          key=lambda t: sum(measure(t.split("\n"), font)))
                lines = txt.split("\n")
                w, h = measure(lines, font)
                _p, _inside = free_grid_search(gpx, w, h, list(_tf) + list(placed))
                if _p is None:
                    continue
                if _inside:
                    res = (_p, lines, font, w, h)
                    n_town_grid += 1
                    break
                if _out_res is None:      # 先記下區外落點，繼續找更小的字號看能否留在區內
                    _out_res = (_p, lines, font, w, h)
            if not res and _out_res is not None:
                res = _out_res
                n_town_grid += 1
        if res:
            p, lines, font, w, h = res
            _place_town(p, lines, font, w, h)
            continue

        # ④ 保底（極罕見）：允許離開本區邊界，找一個離村里名/圓圈最遠的落點
        font = get_font(TOWN_FONT_MIN)
        txt = min(build_text_variants(nm), key=lambda t: sum(measure(t.split("\n"), font)))
        lines = txt.split("\n")
        w, h = measure(lines, font)
        p, _clash = _avoid_spot_outside(gpx, w, h, _tf, reach=360)
        _place_town(p, lines, font, w, h)
        n_town_fallback += 1
        if _clash:
            n_town_overlap += 1
    print(f"區標註：{len(townships)} 個（其中縮字後才放得下 {n_town_shrunk} 個、"
          f"網格掃描落點 {n_town_grid} 個、離界保底 {n_town_fallback} 個、"
          f"仍重疊 {n_town_overlap} 個）")

    # ★ 需求① 自檢：區名是否壓到村里名／編號圓圈（村里名為主體，理應為 0）
    #   用「實際重疊面積」判定：允許邊框線接觸（intersects 對擦邊為真），
    #   只有真的蓋住字形才算違規。AREA_EPS 以下的擦邊視為不重疊。
    AREA_EPS = 20.0

    def _ov(a, b):
        try:
            return a.intersection(b).area
        except Exception:
            return 0.0

    _town_real = [_tb.buffer(-TOWN_GUARD_PX) for _tb in town_boxes]  # 還原成真正的區名框
    n_town_hit_txt, n_town_hit_cir = 0, 0
    for _kind, _pb in text_boxes:
        if _kind != "village":
            continue
        if any(_ov(_pb, _tb) > AREA_EPS for _tb in _town_real):
            n_town_hit_txt += 1
    for num, nm, r, cx_, cy_ in circle_info:
        _cb = ShBox(cx_ - r, cy_ - r, cx_ + r, cy_ + r)
        if any(_ov(_cb, _tb) > AREA_EPS for _tb in _town_real):
            n_town_hit_cir += 1
            print(f"  ⚠️ 圈{num}{nm}(r{r}) @({cx_:.0f},{cy_:.0f}) 與區名框重疊")
    print(f"★ 區名疊壓自檢：村里文字被區名壓 {n_town_hit_txt} 處、"
          f"編號圓圈被區名壓 {n_town_hit_cir} 處（村里名為主體，應皆為 0）")

    # 區名框之間也不應互相重疊
    n_town_town = 0
    for _i in range(len(town_boxes)):
        for _j in range(_i + 1, len(town_boxes)):
            if town_boxes[_i].intersects(town_boxes[_j]):
                n_town_town += 1
    print(f"  區名框互相重疊：{n_town_town} 對（相鄰兩區區名本就可能挨近，僅供參考）")

    n_overlap = 0
    for i in range(len(circle_info)):
        for j in range(i + 1, len(circle_info)):
            n1, nm1, r1, x1, y1 = circle_info[i]
            n2, nm2, r2, x2, y2 = circle_info[j]
            dist = math.hypot(x1 - x2, y1 - y2)
            if dist < r1 + r2:
                n_overlap += 1
                print(f"  ⚠️ 圈號疊壓：圈{n1}{nm1}(r{r1}) 與 圈{n2}{nm2}(r{r2}) 中心距 {dist:.1f}px")
    print(f"圈號疊壓自檢：{n_overlap} 處")

    # 圓圈 vs 文字框重疊自檢（`placed` 含圓圈自身，須用 text_boxes）
    n_cl_overlap = 0
    for num, nm, r, cx_, cy_ in circle_info:
        cb = ShBox(cx_ - r, cy_ - r, cx_ + r, cy_ + r)
        hit = sum(1 for _kind, pb in text_boxes if cb.intersects(pb))
        if hit:
            n_cl_overlap += 1
            print(f"  ⚠️ 圈{num}{nm}(r{r}) 與 {hit} 個文字框重疊")
    print(f"圓圈與文字框重疊：{n_cl_overlap} 個（{len(circle_info)} 個圓圈）")

if WITH_LABELS:
    # ---------- 文字渲染：Matplotlib(DPI=100) 渲染 MingLiU → 閾值 200 二值化 ----------
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import font_manager as _fm

    # 必須用 FontProperties(fname=...) 鎖定輪廓版，否則 fontManager 會選回帶點陣的原版字體
    MPL_FP = _fm.FontProperties(fname=MPL_FONT_PATH)
    MPL_FAMILY = MPL_FP.get_name()
    print(f"Matplotlib 文字渲染：family={MPL_FAMILY}，DPI={MPL_DPI}，閾值={BIN_THRESHOLD}，行距={LH}")

    m_halo = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    m_plain = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)


    def _mpl_text_mask(lines, fs, cx, cy, anchor):
        """Matplotlib 渲染一個文字任務（黑字白底），返回 (bool 掩膜, 左上角貼圖座標)"""
        fs_pt = fs * 72.0 / MPL_DPI
        pad = max(4, fs // 4)
        font_p = get_font(fs)
        w_est = max(_scratch.textbbox((0, 0), ln, font=font_p)[2] for ln in lines)
        h_est = (len(lines) - 1) * fs * LH + fs * 1.35
        W = int(math.ceil(w_est * 1.25)) + 2 * pad
        H = int(math.ceil(h_est * 1.25)) + 2 * pad
        fig = Figure(figsize=(W / MPL_DPI, H / MPL_DPI), dpi=MPL_DPI, facecolor="white")
        cvs = FigureCanvasAgg(fig)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.axis("off")
        tx = ax.text(W / 2, H / 2, "\n".join(lines), fontsize=fs_pt,
                     fontproperties=MPL_FP, linespacing=LH,
                     ha="center", va="center", color="black")
        cvs.draw()
        bb = tx.get_window_extent(renderer=cvs.get_renderer())
        buf = np.asarray(cvs.buffer_rgba())
        mask = buf[:, :, 0] < BIN_THRESHOLD
        bcx = (bb.x0 + bb.x1) / 2.0
        bcy = H - (bb.y0 + bb.y1) / 2.0
        if anchor == "mm":
            ox, oy = cx - bcx, cy - bcy
        else:                                    # "lm" 左對齊、垂直居中
            ox, oy = cx - bb.x0, cy - bcy
        return mask, ox, oy


    for lines, fs, cx, cy, anchor, halo in text_jobs:
        small_m, ox, oy = _mpl_text_mask(lines, fs, cx, cy, anchor)
        th, tw = small_m.shape
        tgt = m_halo if halo else m_plain
        x0i, y0i = int(round(ox)), int(round(oy))
        xs0, ys0 = max(0, x0i), max(0, y0i)
        xs1, ys1 = min(CANVAS_W, x0i + tw), min(CANVAS_H, y0i + th)
        if xs1 > xs0 and ys1 > ys0:
            tgt[ys0:ys1, xs0:xs1] |= small_m[ys0 - y0i:ys1 - y0i, xs0 - x0i:xs1 - x0i]

    m_all = m_halo | m_plain
    halo_arr = ndimage.binary_dilation(m_halo, iterations=4) & ~m_all   # 白邊暈圈（避開線界）
    arr = np.array(canvas)
    arr[halo_arr] = 255
    arr[m_all] = 0
    canvas = Image.fromarray(arr, mode="RGB")

    # 顏色驗證：全圖應只含 黑線界/文字、白底、N_COLORS 種填充色
    _packed = ((arr[:, :, 0].astype(np.uint32) << 16)
               | (arr[:, :, 1].astype(np.uint32) << 8) | arr[:, :, 2])
    _uniq = np.unique(_packed)
    _allowed = {(0x000000,), (0xFFFFFF,)} | {(c[0] << 16 | c[1] << 8 | c[2],) for c in PALETTE}
    _unexpected = [v for v in _uniq.tolist() if (v,) not in _allowed]
    print(f"全圖顏色種類：{len(_uniq)}（應 ≤{2 + N_COLORS}：黑/白/{N_COLORS} 填充色），"
          f"未預期顏色 {len(_unexpected)} 種")

# ---------- 線寬自檢（距離變換筆畫寬度；dt=1.0 → 1px 線，dt=2.0 → 3px 線） ----------
_dt = ndimage.distance_transform_edt(lines_mask)
_core = (_dt >= ndimage.maximum_filter(_dt, size=5)) & (_dt > 0.4)
_vals, _cnts = np.unique(np.round(_dt[_core], 1), return_counts=True)
print("線界筆畫核心半徑分布：",
      {float(a): int(b) for a, b in zip(_vals.tolist(), _cnts.tolist()) if b > 20})

# ---------- 保存 ----------
def save_png(img, path):
    """目標檔被看圖程式鎖住時（Windows Errno 22/32），自動改存 _new.png 再試一次"""
    try:
        img.save(path, format="png")
        return path
    except OSError as e:
        alt = path[:-4] + "_new.png"
        print(f"⚠️ {os.path.basename(path)} 寫入失敗（{e}），改存 {os.path.basename(alt)}")
        img.save(alt, format="png")
        return alt


_out_name = "KaohsiungCity_VillageDistrict_Labeled.png" if WITH_LABELS \
    else "KaohsiungCity_VillageDistrict_Plain.png"
out_file = save_png(canvas, os.path.join(out_dir, _out_name))
print(f"已保存 {out_file}（{CANVAS_W}×{CANVAS_H}，填充={'開' if WITH_FILL else '關'}，"
      f"標註={'開' if WITH_LABELS else '關'}）")

if WITH_LABELS:
    print("\n✅ 標註版地圖生成完畢")
    print("編號對照：")
    for t in town_order:
        sub = small[small["TOWNNAME"] == t].sort_values("num")
        if len(sub):
            print(f"  {t}：" + "、".join(
                f'{int(r["num"])}.{r["VILLNAME"]}' for _, r in sub.iterrows()))
else:
    print("\n✅ 線稿版地圖生成完畢（無填充、無地名）")
