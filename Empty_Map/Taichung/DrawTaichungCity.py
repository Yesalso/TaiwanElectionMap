# -*- coding: utf-8 -*-
"""
臺中市 · 村里界 1px + 區界/市界/海岸線 2px（純黑白線稿，無填充、無地名）
（由 DrawKaohsiungCity.py 派生；繪圖邏輯完全一致，僅換縣市、bbox 與輸出路徑）
兩層各自獨立繪製，最後做聯集疊加：

  ① 村里層（1px）——海南 Empty_Map/Hainan_town_county_1px_labeled.py 的「鄉鎮畫法」：
     PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線。
     此層只含全市 625 個村里的界線，一律 1px；29 個區的區界另由 ② 層以 2px 描出。

  ② 區界 + 市界 + 海岸線（2px）——Empty_Map/DrawNewTaipei.py 的畫法：
     只取 TOWNNAME 層級的區（臺中市為「區」制，不碰村里資料），matplotlib(Agg, DPI=100) 以
     linewidth = LINE_TOWNSHIP_PT*DPI/72 pt 繪製區面與區界
     （區面的外框就是市界與海岸線，故 coastline 自動同寬，不需另外處理），
     再用閾值 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑 2px 線層。
     線寬換算：DrawNewTaipei.py 的 line_township_px=2 → 2.78pt = 3.86px，閾值後約 4px；
     取 1 → 1.39px，閾值後約 2px（3x3 全黑僅 162 px、4x4 為 7 px），故此處取 1。
     此層不含任何村里線，所以「先畫第二層再疊加」不會把村里線加粗。

  疊加：lines_mask = 村里 1px 層 | 區/市界 2px 層（黑疊黑）。
  兩層用同一套像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），故疊加處不會錯開 1px。

  自檢：跨區界與市界 1px 原始線 100% 被 2px 層覆蓋、村里層無 2x2 粗塊（保證 1px）、
        4x4 以上全黑塊為 0（無鼓包）、②層為單一連通網（無散點）、全圖僅純黑/純白兩色。
輸出：Taichung/TaichungCity_VillageDistrict.png
"""
import os
import math
import warnings
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageDraw
from skimage.morphology import thin          # ① 村里層：海南做法（thin 取中心線）
from scipy import ndimage                    # 自檢用
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None

# ===================== 配置 =====================
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map\Taichung"
out_name = "TaichungCity_VillageDistrict.png"
layer_name = "layer_taichung_district_2px.png"   # ② 層單獨輸出（核對用）
target_county = "臺中市"
encoding = "UTF-8"
TARGET_CRS = "EPSG:3826"

# 比例尺：1px = 10m，再放大 10%
# 臺中市 bbox 約 101060 x 49069 m（橫長形狀：西邊梧棲/清水海岸、東邊和平區山區），
# 1px=10m 再放大 10% 後實際 1px=9.091m，故地圖約 11339x5506 px（長寬皆 < MAX_PX）
METERS_PER_PIXEL = 10.0
MAX_PX = 12000
SCALE_UP = 1.10
PAD_FRAC = 0.01          # 地圖四周留白比例

# ★ 關閉簡化（修掉「多餘線條」的關鍵）
#   原設 2.0m（≈0.2px，理論上視覺不可見），但 Douglas-Peucker 是「按弦長取捨」：
#   只要一整段曲線的偏離量都 < 2m，不論它有多長，都會被塌縮成「一條長直線」。
#   （以下為臺南市永康區的實測引用，作為本專案沿用同一設定的依據）
#   臺南市永康區的村里界採點中位數 21m、但 90% 分位已達 95m，本身就有大量
#   緩彎長段；simplify(2.0) 把這些緩彎拉直，憑空造出大量橫貫村里的斜直線。
#   永康區實測：>500m 的直段由 10 條暴增到 48 條，最長單段由 272m 變 1453m。
#   1px ≈ 9.09m 遠大於 2m，保留原始採點並不會讓圖變髒，故直接關閉簡化。
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（保留原始測量採點）

# 線寬
LINE_VILLAGE_PX = 1      # ① 村里界（PIL 直繪寬度）
LINE_TOWNSHIP_PT = 1     # ② matplotlib 線寬(pt)：閾值後約 2px（見檔頭說明）
THRESHOLD_VAL = 40       # ② 二值化閾值（沿用 DrawNewTaipei.py）
SAVE_LAYER = False       # ② 層是否單獨存檔（預設關閉，避免產出多餘預覽圖）

# ★ 微孔洞清理（修掉「散點」的關鍵）
#   成因：相鄰村里 polygon 共用邊在 x87 浮點下不完全一致，dissolve 後區面內部
#   留下大量「極窄細長內環(洞)」。② 層把 polygon 的每一個環都描邊，於是這些洞
#   被畫成一圈圈細線——在 1px≈9.09m 下僅 1~2px 寬，抗鋸齒後超過半數像素灰階
#   > THRESHOLD_VAL，二值化時被切斷 → 只剩零星黑點，就是圖上「多餘的點」。
#   處理：把面積 < HOLE_MIN_AREA_M2 的內環視為拓樸雜訊直接移除。
#   10000 m² ≈ 100x100m ≈ 11x11px，遠小於任何真實行政區，故不會誤刪真飛地。
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為雜訊，填平
# ==================================================

warnings.filterwarnings("ignore")
os.makedirs(output_dir, exist_ok=True)

# ----------------------讀取 SHP----------------------
gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(TARGET_CRS)
print(f"原始要素數：{len(gdf_all)}")

# 去除無資料(NaN)或空幾何的區域，不繪製
gdf_sub = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
gdf_sub = gdf_sub[~gdf_sub.geometry.isna() & ~gdf_sub.geometry.is_empty].copy()

# 只保留目標縣市、未編定村里（VILLNAME 為 NaN）不繪製
gdf_sub = gdf_sub[gdf_sub["COUNTYNAME"] == target_county].copy()
gdf_sub = gdf_sub[gdf_sub["VILLNAME"].notna()].copy()
gdf_sub = gdf_sub[gdf_sub["TOWNNAME"].notna()].copy()
gdf_sub = gdf_sub[["TOWNNAME", "VILLNAME", "geometry"]].copy()
gdf_sub["geometry"] = gdf_sub.geometry.buffer(0)
gdf_sub["VILLNAME"] = gdf_sub["VILLNAME"].astype(str).str.strip()
gdf_sub["TOWNNAME"] = gdf_sub["TOWNNAME"].astype(str).str.strip()
gdf_sub = gdf_sub[~gdf_sub.geometry.isna() & ~gdf_sub.geometry.is_empty].copy()
gdf_sub = gdf_sub.reset_index(drop=True)

# 保留一份未簡化的副本，供稍後「簡化是否造出多餘長直段」的自檢比對
gdf_sub_unsimplified = gdf_sub.copy()

if SIMPLIFY_TOL_M > 0:
    gdf_sub["geometry"] = gdf_sub.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
print(f"村里幾何清理完成（簡化 {SIMPLIFY_TOL_M}m），有效 {int(gdf_sub.geometry.is_valid.sum())}/{len(gdf_sub)}")

villages = gdf_sub

# ★ 本島範圍硬性關卡（防呆用，非離島排除）
#   臺中市轄內沒有離島（臺中港外海的東沙/南沙群島屬高雄市旗津區代管），所以這裡
#   不是為了排離島，而是防「離群圖斑」把畫布撐爆：代表點不落在臺中本島 bbox
#   （EPSG:3826，約 194.8k~295.9k / 2654.9k~2704.0k）內者一律不畫。
EXPLICIT_MAINLAND_BBOX = (190000.0, 2640000.0, 300000.0, 2710000.0)   # EPSG:3826
_isx0, _isy0, _isx1, _isy1 = EXPLICIT_MAINLAND_BBOX
_rp = villages.geometry.representative_point()
_in_box = (_rp.x >= _isx0) & (_rp.x <= _isx1) & (_rp.y >= _isy0) & (_rp.y <= _isy1)
if (~_in_box).any():
    print(f"★ 本島範圍排除：{int((~_in_box).sum())} 筆")
    villages = villages[_in_box].copy()

townships = villages.dissolve(by="TOWNNAME").reset_index()      # ② 層只用這一層級

# ★ 非村里圖斑（港區／水域／軍區／工業區）是否併入「區面」，詳見
#   DrawTaichungCityLabeled.py 同名開關的說明。預設 False＝沿用高雄邏輯（留白）。
#   臺中市源資料有 5 筆 TOWNNAME 有值、VILLNAME 為空的圖斑（合計約 23.3 km²）：
#     梧棲區 8.748（臺中港外港區水域）、清水區 7.127 + 4.741 + 1.520（港區與工業區）、
#     龍井區 1.118（工業區）—— 行政上屬該區但不屬任何村里，預設留白。
INCLUDE_NONVILLAGE_PARCELS = False
if INCLUDE_NONVILLAGE_PARCELS:
    _keep_t = set(villages["TOWNNAME"].unique())
    _parcels = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.strip() == target_county].copy()
    _parcels["geometry"] = _parcels.geometry.buffer(0)
    _parcels = _parcels[~_parcels.geometry.isna() & ~_parcels.geometry.is_empty].copy()
    _parcels["TOWNNAME"] = _parcels["TOWNNAME"].astype(str).str.strip()
    _parcels = _parcels[_parcels["TOWNNAME"].isin(_keep_t)].copy()
    _prp = _parcels.geometry.representative_point()
    _parcels = _parcels[(_prp.x >= _isx0) & (_prp.x <= _isx1)
                        & (_prp.y >= _isy0) & (_prp.y <= _isy1)].copy()
    townships = _parcels[["TOWNNAME", "geometry"]].dissolve(by="TOWNNAME").reset_index()
    print(f"★ 非村里圖斑已併入區面：{len(_parcels)} 筆")

print(f"{target_county}區：{len(townships)}，村里 {len(villages)}")


# ----------------------清理微小內環（散點元兇）----------------------
def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)。這些是 dissolve 浮點誤差造成的細長微孔，
    若不處理，② 層會把每個洞描成一圈細線，二值化後斷成「多餘的點」。
    同時丟棄面積過小的獨立多邊形部件（若資料中有）。"""
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kept = []
        for poly in parts:
            if poly.geom_type != "Polygon":
                continue
            if poly.area < min_area:          # 丟掉過小的獨立碎片
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


_hole_before = sum(len(p.interiors)
                   for g0 in townships.geometry
                   for p in ([g0] if g0.geom_type == "Polygon" else list(g0.geoms)))
townships = clean_tiny_holes(townships)
_hole_after = sum(len(p.interiors)
                  for g0 in townships.geometry
                  for p in ([g0] if g0.geom_type == "Polygon" else list(g0.geoms)))
print(f"微孔洞清理：內環 {_hole_before} → {_hole_after}"
      f"（移除 {_hole_before - _hole_after} 個 < {HOLE_MIN_AREA_M2:.0f}m² 的洞）")

# ----------------------畫布尺寸----------------------
minx, miny, maxx, maxy = villages.total_bounds
geo_w_m = maxx - minx
geo_h_m = maxy - miny

pad_x = PAD_FRAC * geo_w_m
pad_y = PAD_FRAC * geo_h_m
minx -= pad_x
maxx += pad_x
miny -= pad_y
maxy += pad_y
geo_w_m = maxx - minx
geo_h_m = maxy - miny

# 自動調整比例尺，確保長寬都不超過 MAX_PX，並放大 10%
scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
w_px = int(math.ceil(geo_w_m / scale))
h_px = int(math.ceil(geo_h_m / scale))
sx, sy = w_px / geo_w_m, h_px / geo_h_m
print(f"統一比例尺：1像素 = {geo_w_m / w_px:.4f} 米")
print(f"圖片尺寸：{w_px} × {h_px} px")

# ----------------------① 村里界 1px（海南「鄉鎮畫法」）----------------------
# 像素網格約定：像素 i 的中心對應 minx+(i+0.5)/sx，與 matplotlib 的渲染網格一致，
# 兩層疊加才不會錯開 1px（故這裡用 floor 而非 round）
def to_px(coords):
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


def draw_layer(lines, width=1):
    """Bresenham 逐段描繪（width 像素寬的純黑白線），返回 bool 陣列"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


print("\n① 村里界 1px（1px 直繪 → thin 中心線）...")
village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
village_arr = draw_layer(village_lines, 1)
village_skel = thin(village_arr)
print(f"村里層 {LINE_VILLAGE_PX}px 中心線：{int(village_skel.sum())} px"
      f"（1px 線 {int(village_arr.sum())} px）")

# ----------------------② 區界 + 市界 + 海岸線 2px（DrawNewTaipei.py 畫法）----------------------
print("② 區界/市界/海岸線 2px（matplotlib + 閾值二值化）...")
DPI = 100
fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")
_lw = LINE_TOWNSHIP_PT * (DPI / 72.0)
townships.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=_lw)
townships.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=_lw)
ax.axis("off")
_buf = BytesIO()
plt.savefig(_buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="white")
plt.close(fig)
_buf.seek(0)
_img = cv2.imdecode(np.frombuffer(_buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
_buf.close()
_gray = cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY)
del _img
_, _tmask = cv2.threshold(_gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
del _gray
town_layer = _tmask > 0                              # 純黑 2px 線層（含縣界與海岸線）
print(f"區/市界層：{int(town_layer.sum())} px"
      f"（線寬 {LINE_TOWNSHIP_PT}pt={_lw:.2f}px，閾值 {THRESHOLD_VAL}）")

S3 = np.ones((3, 3), dtype=bool)
# 對齊自檢：② 層必須覆蓋區界 1px 原始線（含市界/海岸線），否則兩層網格不一致
_town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1)
_miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
print(f"區界+市界 1px 原始線 {int(_town_1px.sum())} px，未被 2px 層覆蓋 {_miss} px（應 ≈0）")
del _town_1px

# ★ 散點自檢：② 層應為「單一連通網」，不應有大量小連通分量
#   （若未清微孔洞，此處會顯示 300+ 個分量、最小僅 1px，即圖上的多餘點）
_cc_n, _cc_lab, _cc_st, _cc_ce = cv2.connectedComponentsWithStats(
    town_layer.astype(np.uint8), connectivity=8)
_cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
_cc_small = int((_cc_area <= 40).sum())
print(f"② 層連通分量：{_cc_n - 1} 個（應為 1）；面積中位 {np.median(_cc_area):.0f}px、"
      f"最小 {_cc_area.min()}px；<=40px 小分量 {_cc_small} 個（應為 0）")
if _cc_small > 0:
    print(f"⚠️ 仍有 {_cc_small} 個散點分量，請調高 HOLE_MIN_AREA_M2 或檢查資料")

# ★ 簡化自檢：simplify 會把緩彎拉直成橫貫村里的斜直線
#   統計村里界中過長的「兩點直段」，並與原始資料對比；若簡化造成的暴增過多即告警。
def _long_straight_count(gdf, min_len, max_pts=3):
    """統計邊界中長度 >= min_len 且點數 <= max_pts 的直段（疑似被拉直）"""
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


_STRAIGHT_MIN_LEN = 500.0
_na = _long_straight_count(gdf_sub_unsimplified, _STRAIGHT_MIN_LEN)
_nb = _long_straight_count(villages, _STRAIGHT_MIN_LEN)
print(f"簡化自檢（{SIMPLIFY_TOL_M}m）：>={_STRAIGHT_MIN_LEN:.0f}m 直段 "
      f"原始 {_na} → 簡化後 {_nb}（應持平；暴增表示緩彎被拉直成多餘斜線）")
if _nb > _na * 1.5 + 5:
    print(f"⚠️ 簡化造出 {_nb - _na} 條額外長直段，建議把 SIMPLIFY_TOL_M 調小或設為 0")

# ----------------------疊加----------------------
lines_mask = village_skel | town_layer

# 村里線自檢：扣掉 2px 層後不應出現 2x2 連續黑塊（1px 線不會有 2x2 方塊）
_v_only = village_skel & ~town_layer
_2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
print(f"村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")
# 鼓包自檢：2px 層只允許在交叉點出現 3x3 全黑，4x4 以上應 ≈0
_e3 = ndimage.binary_erosion(lines_mask, structure=np.ones((3, 3), dtype=bool))
_e4 = ndimage.binary_erosion(lines_mask, structure=np.ones((4, 4), dtype=bool))
_e5 = ndimage.binary_erosion(lines_mask, structure=np.ones((5, 5), dtype=bool))
print(f"粗細自檢：3x3 全黑 {int(_e3.sum())} px（僅交叉點），4x4 {int(_e4.sum())}，5x5 {int(_e5.sum())}")
print(f"黑像素合計：{int(lines_mask.sum())}")

arr = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
arr[lines_mask] = 0          # 線界以純黑疊加（無灰階）
canvas = Image.fromarray(arr, mode="RGB")

# 顏色驗證：全圖應只含純黑 / 純白兩級像素
_uniq = np.unique(arr.reshape(-1, 3), axis=0)
print(f"全圖顏色種類：{len(_uniq)}（應為 2：純黑線界 + 純白底）")

# ----------------------保存----------------------
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


if SAVE_LAYER:
    _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    _la[town_layer] = 0
    print("② 層單獨輸出:", save_png(Image.fromarray(_la, mode="RGB"),
                                     os.path.join(output_dir, layer_name)))

out_file = save_png(canvas, os.path.join(output_dir, out_name))
print(f"Saved: {out_file} | size {w_px} x {h_px} px")

print("\n==== All finished ====")
print(f"輸出目錄：{output_dir}")
