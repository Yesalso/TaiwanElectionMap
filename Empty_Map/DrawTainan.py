# -*- coding: utf-8 -*-
"""
臺南市 · 村里界 + 區界地圖 —— 村里 1px + 區界/市界/海岸線 2px（可選著色/標註）
兩層各自獨立繪製，最後做聯集疊加：
  1. 純黑白 Bresenham 描繪（無抗鋸齒灰階），分兩層依序疊加：
       ① 村里層（1px）——海南 Empty_Map/Hainan_town_county_1px_labeled.py 的「鄉鎮畫法」：
          1px 直繪 → skimage.morphology.thin 取中心線，全市村里界 1px；
       ② 區界 + 市界 + 海岸線（2px）——Empty_Map/DrawNewTaipei.py 的畫法：
          只取 TOWNNAME 層級的區（臺南市為「區」制，不碰村里資料），matplotlib(Agg, DPI=100) 以
          linewidth = LINE_TOWNSHIP_PT*DPI/72 pt 繪製區面與區界
          （區面的外框就是市界與海岸線，故 coastline 自動同寬，不需另外處理），
          再用閾值 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑 2px 線層。
          線寬換算：DrawNewTaipei.py 的 line_township_px=2 → 2.78pt = 3.86px，閾值後約 4px；
          取 1 → 1.39px，閾值後約 2px（3x3 全黑僅 162 px、4x4 為 7 px），故此處取 1。
          此層不含任何村里線，所以「先畫第二層再疊加」不會把村里線加粗。
     疊加：lines_mask = ①1px 裡層 | ②2px 區/市界層（黑疊黑）；
     兩層用同一套像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加處不會錯開 1px。
     自檢：跨區界與市界 1px 原始線 100% 被 2px 層覆蓋、村里層無 2x2 粗塊（保證 1px）、
           4x4 以上全黑塊 ≈0（無鼓包）；
  2. 可選區 5 色填充（相鄰不同色，圖著色 · 貪心 5 色），WITH_FILL 開關；
     色盤由 PALETTE_KEY（環境變數）決定：
       PALETTE_KEY == "tainan_main"（預設）→ 原本固定 5 色盤（主圖不變）；
       其他 key（= 各獨立放大圖的輸出名稱）→ 固定種子隨機配色，各圖互異（需求④）；
  3. 可選地名標註（智慧標註：質心/代表點/內縮質心候選 → 壓線檢測 → 16 方向平移搜尋
     → 字號逐級縮小 → 保底加白邊暈圈）、跨單元標註互斥、微小村里改圓圈編號 + 圖例、
     MingLiU（細明體，刪點陣表走 glyf 輪廓）+ Matplotlib(DPI=100) 閾值 200 二值化，
     WITH_LABELS 開關；
     ★ 標註優先權（需求①）：里的名字是主體，不可為了區名而移動／縮小／刪除。
       繪製順序固定為  村里名 → 編號圓圈 → 區名：
         1) 村里中文名先放，落點即最終落點；
         2) 村里塞不下的畫編號圓圈；
         3) 區名（大字）最後放，主動避讓 1) 2) 的佔位框
            （村里名框再外擴 TOWN_GUARD_PX 作為禁區）；
            讓不開就逐級縮字（下限 TOWN_BRANCH_MIN_PX），
            縮到底仍無位才允許離開本區邊界另尋淨地。
     其他標註前處理：
       - 村里名先去中括號（源資料以 [ ] 標記罕用字，如「公[塭]里」→「公塭里」，需求②）；
       - 環境變數 DENSE_STANDALONE（或 _standalone_towns.txt）指定的區，
         主圖不畫編號圓圈（該區已獨立出放大圖，需求③）；
輸出（依開關）：
  WITH_FILL=False, WITH_LABELS=False → Empty_Map/TainanCity_VillageDistrict_Plain.png
  WITH_LABELS=True                   → Empty_Map/TainanCity_VillageDistrict_Labeled.png
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
out_dir = r"D:\Windows\TaiwanElection\Empty_Map"
final_dir = out_dir

TARGET_COUNTY = "臺南市"
TARGET_CRS = "EPSG:3826"

# 比例尺：1px = 10m，再放大 10%
# 臺南市 bbox 約 64527 x 58238 m（新竹縣的 1.6 倍），故地圖約 7240x6535 px
METERS_PER_PIXEL = 10.0
SCALE_UP = 1.10
MAX_PX = 12000
PAD_FRAC = 0.01          # 地圖四周留白

# ★ 關閉簡化（修掉「多餘線條」的關鍵，與 DrawTainanCity.py 一致）
#   simplify 是「按弦長取捨」：緩彎長段只要偏離 < 2m 就被塌縮成一條長直線，
#   憑空造出橫貫村里的斜直線。永康區實測 >500m 直段由 10 條暴增到 48 條。
#   1px ≈ 9.09m 遠大於 2m，保留原始採點不會讓圖變髒，故關閉簡化。
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（保留原始測量採點）

# 線寬
LINE_VILLAGE_PX = 1      # ① 村里界（PIL 直繪寬度）
LINE_TOWNSHIP_PT = 1     # ② matplotlib 線寬(pt)：閾值後約 2px（見檔頭說明）
THRESHOLD_VAL = 40       # ② 二值化閾值（沿用 DrawNewTaipei.py）
SAVE_LAYER = False       # ② 層是否單獨存檔（預設關閉，避免產出多餘預覽圖）

# ★ 微孔洞清理（修掉「散點」的關鍵，與 DrawTainanCity.py 一致）
#   相鄰村里 polygon 共用邊在 x87 浮點下不完全一致，dissolve 後區面內部留下大量
#   極窄細長內環(洞)（臺南市共 1186 個，全部 <500 m²）。② 層會逐環描邊，這些洞在
#   1px≈9.09m 下僅 1~2px 寬，抗鋸齒後二值化斷裂 → 圖上出現一堆「多餘的點」。
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為雜訊，填平
# ==================================================

# 輸出開關
WITH_FILL = True         # 區著色填充
WITH_LABELS = True       # 地名標註（文字 + 編號圓圈 + 圖例）

# 畫布右側圖例區（臺南市村里 649 個，較新竹縣 192 個多 3.4 倍 → 圖例加寬）
LEGEND_W = 700
LEGEND_FONT = 40
LEGEND_HEAD_FONT = 42
LEGEND_TITLE = "村里編號圖例"
LEGEND_X_PAD = 60
LEGEND_DY = 66
LEGEND_BOTTOM_PAD = 110
CIRCLE_R = 22            # 編號圓圈半徑（px），放不下時逐級縮小

# ---------- 標註配置（字號對應本圖 7240x6535 / 1px=9.09m） ----------
# 註：臺南市「區」面積普遍大於新竹縣鄉鎮市（新竹縣多山、鄉鎮細碎），
#     故 TOWNSHIP_TIERS 門檻上調，避免所有區都落到同一檔。
FONT_MIN = 26            # 最小字號（px）
# 村里字號分檔：(面積上限 px², 初始字號)
VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]
# 區（TOWNNAME）字號分檔
TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]
NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）
TEXT_MARGIN_PX = 4.0     # 文字框距本單元邊界最小間隙（px）
LINE_STEP_PX = 6         # 平移搜尋步長（px）
LINE_MAX_STEPS = 30      # 平移搜尋最大步數
BASE_BUFFER_PX = 78      # 內縮質心基準距離（px）
HALO_MAX_FS = 36         # 字號 ≤ 此值的標籤加白邊暈圈（與細線隔離）

# ★ 需求①：原則 —— 里的名字是主體，不可為了區名而移動／縮小／刪除。
#   因此順序是：
#     1) 先把「村里的中文名」全部放好（優先權最高，落點就是最終落點）；
#     2) 再放「區名」，區名主動避讓已放置的村里名；讓不開就逐級縮字；
#     3) 若縮到底仍無處可放 → 才允許區名與村里名略微重疊（並記錄告警）。
#   TOWN_GUARD_PX      ：區名避讓村里名時，村里名框再外擴這麼多 px 作為禁區。
#   TOWN_BRANCH_MIN_PX ：區名縮字下限；低於此值仍無位則允許重疊。
TOWN_GUARD_PX = 10.0
TOWN_BRANCH_MIN_PX = 34
# 主圖上「已獨立出圖的區」不標編號圓圈（見 SKILL.md 需求③）
#   來源二選一（優先環境變數）：
#     DENSE_STANDALONE="永康區,新營區,..."  或  _standalone_towns.txt（由 DrawTainanDense.py 產生）
_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()
if _DENSE_STANDALONE_ENV:
    STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]
else:
    _sa_file = os.path.join(final_dir, "_standalone_towns.txt")
    if os.path.exists(_sa_file):
        with open(_sa_file, encoding="utf-8") as _f:
            STANDALONE_TOWNS = [t for t in _f.read().strip().split(",") if t]
    else:
        STANDALONE_TOWNS = []

# 文字渲染：Matplotlib(DPI=100) 渲染 MingLiU + 閾值 200 二值化，行距 1.5 倍字號
MPL_DPI = 100
BIN_THRESHOLD = 200
LH = 1.5
# ==================================================

# ---------- 密集區（安南/安平/中西/北/南/永康/東）標註策略 ----------
# 這七區村里細碎，主圖 1px=9.09m 下多數村里放不下中文地名。
# 規則：主圖「只標能塞得下中文地名的村里」，塞不下的『不畫編號圓圈』，
#       改由另一張放大圖（1px=5m）DrawTainanDense.py 標註。
DENSE_TOWNS = ["安南區", "安平區", "中西區", "北區", "南區", "永康區", "東區"]
# 主圖上這些區的村里若面積小於此值 → 直接跳過（不標文字也不標圓圈）
DENSE_SKIP_AREA_PX = 15000
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
        _outline_cache = os.path.join(final_dir, "_mingliu_outline.ttf")
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

villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())
               & (gdf["TOWNNAME"].notna())].copy()
villages["geometry"] = villages.geometry.buffer(0)
villages = villages[~villages.geometry.isna() & ~villages.geometry.is_empty].copy()
villages["VILLNAME"] = villages["VILLNAME"].astype(str).str.strip()
villages["TOWNNAME"] = villages["TOWNNAME"].astype(str).str.strip()

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
# 需求④：色盤由 PALETTE_KEY 決定。
#   PALETTE_KEY == "tainan_main"（預設）→ 沿用原本固定的 5 色盤（主圖不變）；
#   其他 key（= 各獨立放大圖的輸出名稱）→ 以固定種子隨機生成淡雅色盤，
#   於是各放大圖配色互異、但同一張圖可重現。
PALETTE_KEY = os.environ.get("PALETTE_KEY", "tainan_main").strip()

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


PALETTE = PALETTE_FIXED if PALETTE_KEY == "tainan_main" else _make_palette(PALETTE_KEY)
N_COLORS = len(PALETTE)
print(f"配色鍵 {PALETTE_KEY} → 色盤 " +
      "、".join("#%02x%02x%02x" % c for c in PALETTE) +
      ("（原本固定 5 色）" if PALETTE_KEY == "tainan_main" else "（隨機生成）"))

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
    _lp = os.path.join(out_dir, "layer_tainan_district_2px.png")
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


def draw_text_label(geom, name, tiers, f_min=FONT_MIN):
    """放置村里名（需求①：村里名是主體，落點即最終落點，不被區名影響）。
    返回 True=常規放置成功；False=保底描邊放置。"""
    boundary = geom.boundary
    area_px = geom.area
    f_def = next(fs for lim, fs in tiers if area_px < lim)
    variants = build_text_variants(name)
    cands = candidate_points(geom) or [geom.representative_point()]
    for fs in range(f_def, f_min - 1, -1):
        font = get_font(fs)
        for txt in variants:
            lines = txt.split("\n")
            w, h = measure(lines, font)
            for p0 in cands:
                bx = spot_ok(p0, w, h, boundary)
                if bx is not None:
                    _draw_lines(p0, lines, font, halo=(fs <= HALO_MAX_FS))
                    _bx = ShBox(p0.x - w / 2, p0.y - h / 2, p0.x + w / 2, p0.y + h / 2)
                    placed.append(_bx)
                    text_boxes.append(("village", _bx))
                    return True
                if geom.area < w * h:
                    continue  # 多邊形根本裝不下，平移無意義
                p2, bx2 = translate_search(geom, boundary, p0, w, h)
                if p2 is not None and bx2 is not None:
                    _draw_lines(p2, lines, font, halo=(fs <= HALO_MAX_FS))
                    _bx = ShBox(p2.x - w / 2, p2.y - h / 2, p2.x + w / 2, p2.y + h / 2)
                    placed.append(_bx)
                    text_boxes.append(("village", _bx))
                    return True
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

    # ★ 密集七區策略：主圖只標「塞得下中文地名」的村里；塞不下的不畫編號圓圈，
    #   改由 DrawTainanDense.py（1px=5m 放大圖）標註。
    _is_dense = villages["TOWNNAME"].isin(DENSE_TOWNS)
    _too_small = villages["area_px"] < DENSE_SKIP_AREA_PX
    # 主圖要跳過的村里（密集七區 ∩ 面積過小）
    _skip_main = _is_dense & _too_small
    print(f"密集七區 {DENSE_TOWNS}：村里 {int(_is_dense.sum())} 個，"
          f"其中主圖跳過（面積 < {DENSE_SKIP_AREA_PX}px²，改由放大圖標註）"
          f"{int(_skip_main.sum())} 個")

    # 其餘（非密集區）沿用原本「小面積 → 編號圓圈」的規則
    small = villages[~_is_dense & _too_small].copy()
    big = villages[~_too_small | (_is_dense & ~_too_small)].copy()

    # ★ 需求③：已獨立出放大圖的區（永康、新營、歸仁、麻豆…）在主圖上不標序號。
    #   這些區的村里仍保留中文地名（見 big），只是不再畫編號圓圈 → 圖例也不再列出。
    if STANDALONE_TOWNS:
        _sa_cir = small["TOWNNAME"].isin(STANDALONE_TOWNS)
        _sa_txt = big["TOWNNAME"].isin(STANDALONE_TOWNS)
        print(f"獨立出圖區 {STANDALONE_TOWNS}：主圖不標序號 "
              f"{int(_sa_cir.sum())} 個（其中 {int(_sa_txt.sum())} 個保留中文地名）")
        small = small[~_sa_cir].copy()

    # 編號順序：先按區、再按村里名（圖例自然分組）
    small = small.sort_values(["TOWNNAME", "VILLNAME"]).reset_index(drop=True)
    small["num"] = np.arange(1, len(small) + 1)
    num_of = {r["VILLNAME"]: int(r["num"]) for _, r in small.iterrows()}
    print(f"村里標註方式：文字 {len(big)} 個，編號圓圈 {len(small)} 個"
          f"（面積 < {DENSE_SKIP_AREA_PX:.0f}px² ≈ {DENSE_SKIP_AREA_PX * (geo_w / w_px) ** 2 / 1e6:.2f} km²）")

    # ---------- 圖例版面（按區分組，置於右下角） ----------
    town_order = sorted(townships["TOWNNAME"].tolist())
    legend_lines = []      # (類型, 文字)
    if len(small):         # 無編號圓圈時不出圖例（如密集七區放大圖）
        legend_lines.append(("title", LEGEND_TITLE))
        for t in town_order:
            ns = [n for n in num_of if small.loc[small["num"] == num_of[n], "TOWNNAME"].iloc[0] == t]
            if not ns:
                continue
            legend_lines.append(("head", t))
            for n in sorted(ns, key=lambda k: num_of[k]):
                legend_lines.append(("item", f"{num_of[n]}. {n}"))
    n_lines = len(legend_lines)
    LEGEND_Y0 = CANVAS_H - LEGEND_BOTTOM_PAD - (n_lines - 1) * LEGEND_DY
    if LEGEND_Y0 < 60:      # 條目過多時自動壓縮行距
        LEGEND_DY = max(40, int((CANVAS_H - LEGEND_BOTTOM_PAD - 60) / max(1, n_lines - 1)))
        LEGEND_Y0 = CANVAS_H - LEGEND_BOTTOM_PAD - (n_lines - 1) * LEGEND_DY
    print(f"圖例 {n_lines} 行，y0={LEGEND_Y0}，行距 {LEGEND_DY}")

    # ---------- 標註順序（需求① 核心）----------
    #   里的名字是主體：先把村里名放好、落點即最終落點；區名再主動避讓村里名。
    #   1) 村里文字（中文名，優先權最高）
    #   2) 編號圓圈（放不下的村里）
    #   3) 區名（大字，避讓 1)/2) 的佔位；讓不開就縮字；縮到底仍無位才允許重疊）
    print("\n地名標註 ...")
    n_fallback = 0
    n_numbered = 0
    n_town_fallback = 0
    n_town_overlap = 0

    # ---- 1) 村里中文名（不可被移動／縮小／刪除）----
    for _, row in big.sort_values("area_px", ascending=False).iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            continue
        if not draw_text_label(gpx, row["VILLNAME"], VILLAGE_TIERS):
            n_fallback += 1
    print(f"村里文字標註：{len(big)} 個（其中保底描邊 {n_fallback} 個）")

    # ---- 2) 編號圓圈 ----
    for _, row in small.sort_values("area_px").iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            continue
        if draw_number_label(gpx, int(row["num"]), row["VILLNAME"]):
            n_numbered += 1
    print(f"編號圓圈：{n_numbered} 個（保底 {len(small) - n_numbered} 個）")

    # ---- 3) 區名（大字）—— 主動避讓村里名/圓圈 ----
    #   村里名框（含外擴 TOWN_GUARD_PX）構成區名的禁區；區名先原地試、再 16 方向平移，
    #   再逐級縮字；真的縮到底仍無處可放，才允許與村里名重疊（記錄告警）。
    _village_blocks = [bx for _k, bx in text_boxes if _k == "village"]
    _circle_blocks = [ShBox(x - r, y - r, x + r, y + r)
                      for _n, _nm, r, x, y in circle_info]

    def _town_forbidden():
        out = []
        for bx in _village_blocks:
            out.append(bx.buffer(TOWN_GUARD_PX))
        out.extend(_circle_blocks)
        return tuple(out)

    _tf = _town_forbidden()

    def _town_conflict(bx):
        return any(bx.intersects(fb) for fb in _tf) or \
               any(bx.intersects(tb) for tb in town_boxes)

    for _, row in townships.sort_values("TOWNNAME", ascending=False).iterrows():
        gpx = to_px_geom(row.geometry)
        if gpx is None or gpx.is_empty:
            continue
        nm = row["TOWNNAME"]
        boundary = gpx.boundary
        f_def = next(fs for lim, fs in TOWNSHIP_TIERS if gpx.area < lim)
        placed_ok = False
        for fs in range(f_def, TOWN_BRANCH_MIN_PX - 1, -2):
            font = get_font(fs)
            for txt in build_text_variants(nm):
                lines = txt.split("\n")
                w, h = measure(lines, font)
                # 原地 + 16 方向平移搜尋（避開村里名框與既有區名框，仍不壓本區邊界）
                for p0 in candidate_points(gpx) or [gpx.representative_point()]:
                    bx = spot_ok(p0, w, h, boundary, forbid=_tf)
                    if bx is not None:
                        _draw_lines(p0, lines, font, halo=(fs <= HALO_MAX_FS))
                        _tb = ShBox(p0.x - w / 2, p0.y - h / 2,
                                    p0.x + w / 2, p0.y + h / 2)
                        placed.append(_tb)
                        text_boxes.append(("town", _tb))
                        town_boxes.append(_tb.buffer(TOWN_GUARD_PX))
                        placed_ok = True
                        break
                    p2, bx2 = translate_search(gpx, boundary, p0, w, h, forbid=_tf)
                    if p2 is not None and bx2 is not None:
                        _draw_lines(p2, lines, font, halo=(fs <= HALO_MAX_FS))
                        _tb = ShBox(p2.x - w / 2, p2.y - h / 2,
                                    p2.x + w / 2, p2.y + h / 2)
                        placed.append(_tb)
                        text_boxes.append(("town", _tb))
                        town_boxes.append(_tb.buffer(TOWN_GUARD_PX))
                        placed_ok = True
                        break
                if placed_ok:
                    break
            if placed_ok:
                break
        if placed_ok:
            continue
        # 縮到底仍無位 → 允許離開本區邊界，找一個離村里名/圓圈最遠的落點
        font = get_font(TOWN_BRANCH_MIN_PX)
        txt = min(build_text_variants(nm), key=lambda t: sum(measure(t.split("\n"), font)))
        lines = txt.split("\n")
        w, h = measure(lines, font)
        p, _clash = _avoid_spot_outside(gpx, w, h, _tf, reach=360)
        _draw_lines(p, lines, font, halo=True)
        _tb = _block(p, w, h)
        placed.append(_tb)
        text_boxes.append(("town", _tb))
        town_boxes.append(_tb.buffer(TOWN_GUARD_PX))
        n_town_fallback += 1
        if _clash:
            n_town_overlap += 1
    print(f"區標註：{len(townships)} 個（其中縮字到底仍重疊 {n_town_overlap} 個）")

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

    # ---------- 圖例文字（右側，按區分組） ----------
    for i, (kind, txt) in enumerate(legend_lines):
        if kind == "title":
            text_jobs.append(([txt], LEGEND_HEAD_FONT + 4, w_px + LEGEND_X_PAD,
                              LEGEND_Y0 + i * LEGEND_DY, "lm", False))
        elif kind == "head":
            text_jobs.append(([txt], LEGEND_HEAD_FONT, w_px + LEGEND_X_PAD + 14,
                              LEGEND_Y0 + i * LEGEND_DY, "lm", False))
        else:
            text_jobs.append(([txt], LEGEND_FONT, w_px + LEGEND_X_PAD + 48,
                              LEGEND_Y0 + i * LEGEND_DY, "lm", False))

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


_out_name = "TainanCity_VillageDistrict_Labeled.png" if WITH_LABELS \
    else "TainanCity_VillageDistrict_Plain.png"
out_file = save_png(canvas, os.path.join(out_dir, _out_name))
print(f"已保存 {out_file}（{CANVAS_W}×{CANVAS_H}，填充={'開' if WITH_FILL else '關'}，"
      f"標註={'開' if WITH_LABELS else '關'}）")

if WITH_LABELS:
    print("\n✅ 標註版地圖生成完畢")
    print("編號對照：")
    for t in town_order:
        ns = [(num_of[n], n) for n in num_of
              if small.loc[small["num"] == num_of[n], "TOWNNAME"].iloc[0] == t]
        if ns:
            print(f"  {t}：" + "、".join(f"{a}.{b}" for a, b in sorted(ns)))
else:
    print("\n✅ 線稿版地圖生成完畢（無填充、無地名）")
