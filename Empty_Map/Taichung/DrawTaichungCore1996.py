# -*- coding: utf-8 -*-
"""
臺中市核心 8 區 · 民國 85 年（1996）村里界地圖（純黑白線稿）
由 DrawTaichungCity.py 派生：繪圖邏輯一致，僅換資料來源、範圍與比例尺。

資料來源：區里界_region.shp（民國85年臺中市村里界），內容僅含當時臺中市轄區
（中區/東區/南區/西區/北區/北屯區/西屯區/南屯區 共 8 區、224 里），
因此其餘 21 個區不在圖上（民國85年臺中市尚未改制，無 Modern 29 區之分）。

兩層各自獨立繪製，最後聯集疊加：
  ① 村里層（1px）——海南 Empty_Map/Hainan_town_county_1px_labeled.py 的「鄉鎮畫法」：
     PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線。
  ② 區界 + 市界（2px）——Empty_Map/DrawNewTaipei.py 的畫法：
     只取區（區名）層級，matplotlib(Agg, DPI=100) 以 linewidth = LINE_DISTRICT_PT*DPI/72 pt
     繪製區面與區界，再用閾值 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑 2px 線層。
  疊加：lines_mask = 村里 1px 層 | 區/市界 2px 層（黑疊黑）；
  兩層用同一套像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加處不會錯開 1px。

比例尺：核心 8 區 bbox 約 23303 x 12610 m（橫長形），1px=4m 再放大 10%
→ 實際 1px≈3.64m（與 DrawTaichungDense.py 的核心合圖同級），約 5298x2868 px。

自檢：區界 1px 原始線 100% 被 2px 層覆蓋、村里層無 2x2 粗塊、4x4 以上全黑塊為 0、
      ②層無散點、全圖僅純黑/純白兩色。
輸出：Taichung/Taichung1996_Core_Village.png
"""
import os
import math
import warnings
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None

# ===================== 配置 =====================
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\臺中市85年區里界_UTF8\臺中市85年區里界_UTF8\區里界_region.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map\Taichung"
out_name = "Taichung1996_Core_Village.png"
layer_name = "layer_taichung1996_core_district_2px.png"   # ② 層單獨輸出（核對用）
encoding = "UTF-8"
TARGET_CRS = "EPSG:3826"     # 源 prj 為 Hu_Tzu_Shan TM(k=0.9999, FE=250000)，與 3826 一致

# 民國85年（1996）臺中市轄 8 區；此 SHP 僅含這些區，不含其餘 21 區
CORE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]
TOWN_COL = "區名"
VILL_COL = "里名"

# 比例尺：1px = 4m，再放大 10%（核心區村里細碎，需與 Dense 同級解析度）
METERS_PER_PIXEL = 4.0
MAX_PX = 12000
SCALE_UP = 1.10
PAD_FRAC = 0.01          # 地圖四周留白比例

# ★ 關閉簡化：Douglas-Peucker 會把緩彎長段塌縮成「長直線」，
#   憑空造出橫貫村里的斜線（1px≈3.64m 遠小於任何真實曲率所需容差）。
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（保留原始測量採點）

# 線寬
LINE_VILLAGE_PX = 1      # ① 村里界（PIL 直繪寬度）
LINE_DISTRICT_PT = 1     # ② matplotlib 線寬(pt)：閾值後約 2px
THRESHOLD_VAL = 40       # ② 二值化閾值（沿用 DrawNewTaipei.py）
SAVE_LAYER = False       # ② 層是否單獨存檔

# ★ 微孔洞清理（修掉「散點」的關鍵）：相鄰村里共用邊在浮點下不完全一致，
#   dissolve 後留下極窄細長內環；② 層會把每個環描成一圈細線，閾值後斷成散點。
HOLE_MIN_AREA_M2 = 10000.0
# ==================================================

warnings.filterwarnings("ignore")
os.makedirs(output_dir, exist_ok=True)

# ----------------------讀取 SHP----------------------
gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = TARGET_CRS
gdf_all = gdf_all.to_crs(TARGET_CRS)
print(f"原始要素數：{len(gdf_all)}")

gdf_all["geometry"] = gdf_all.geometry.buffer(0)
gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()

gdf_all[TOWN_COL] = gdf_all[TOWN_COL].astype(str).str.strip()
gdf_all[VILL_COL] = gdf_all[VILL_COL].astype(str).str.strip()

# 只保留核心 8 區（此檔應僅含這 8 區，仍過濾一次以防資料混雜）
gdf_sub = gdf_all[gdf_all[TOWN_COL].isin(CORE_TOWNS)].copy()
gdf_sub = gdf_sub.rename(columns={TOWN_COL: "TOWNNAME", VILL_COL: "VILLNAME"})
gdf_sub = gdf_sub[["TOWNNAME", "VILLNAME", "geometry"]].copy()
gdf_sub = gdf_sub.reset_index(drop=True)
print(f"核心 {len(CORE_TOWNS)} 區過濾後村里數：{len(gdf_sub)}")

if SIMPLIFY_TOL_M > 0:
    gdf_sub["geometry"] = gdf_sub.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
print(f"村里幾何清理完成（簡化 {SIMPLIFY_TOL_M}m），"
      f"有效 {int(gdf_sub.geometry.is_valid.sum())}/{len(gdf_sub)}")

villages = gdf_sub
townships = villages.dissolve(by="TOWNNAME").reset_index()
print(f"區：{len(townships)}，村里 {len(villages)}")
print("  " + "、".join(f"{t}({int(c)})" for t, c in
                       villages.groupby("TOWNNAME").size().items()))


# ----------------------清理微小內環（散點元兇）----------------------
def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)與過小的獨立碎片"""
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

scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
w_px = int(math.ceil(geo_w_m / scale))
h_px = int(math.ceil(geo_h_m / scale))
sx, sy = w_px / geo_w_m, h_px / geo_h_m
print(f"統一比例尺：1像素 = {geo_w_m / w_px:.4f} 米")
print(f"圖片尺寸：{w_px} × {h_px} px")

# ----------------------① 村里界 1px（海南「鄉鎮畫法」）----------------------
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

# ----------------------② 區界 + 市界 2px（DrawNewTaipei.py 畫法）----------------------
print("② 區界/市界 2px（matplotlib + 閾值二值化）...")
DPI = 100
fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")
_lw = LINE_DISTRICT_PT * (DPI / 72.0)
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
town_layer = _tmask > 0
print(f"區/市界層：{int(town_layer.sum())} px"
      f"（線寬 {LINE_DISTRICT_PT}pt={_lw:.2f}px，閾值 {THRESHOLD_VAL}）")

S3 = np.ones((3, 3), dtype=bool)
_town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1)
_miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
print(f"區界+市界 1px 原始線 {int(_town_1px.sum())} px，未被 2px 層覆蓋 {_miss} px（應 ≈0）")
del _town_1px

_cc_n, _cc_lab, _cc_st, _cc_ce = cv2.connectedComponentsWithStats(
    town_layer.astype(np.uint8), connectivity=8)
_cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
_cc_small = int((_cc_area <= 40).sum())
print(f"② 層連通分量：{_cc_n - 1} 個（應為 1）；面積中位 {np.median(_cc_area):.0f}px、"
      f"最小 {_cc_area.min()}px；<=40px 小分量 {_cc_small} 個（應為 0）")
if _cc_small > 0:
    print(f"⚠️ 仍有 {_cc_small} 個散點分量，請調高 HOLE_MIN_AREA_M2 或檢查資料")

# ----------------------疊加----------------------
lines_mask = village_skel | town_layer

_v_only = village_skel & ~town_layer
_2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
print(f"村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")
_e3 = ndimage.binary_erosion(lines_mask, structure=np.ones((3, 3), dtype=bool))
_e4 = ndimage.binary_erosion(lines_mask, structure=np.ones((4, 4), dtype=bool))
_e5 = ndimage.binary_erosion(lines_mask, structure=np.ones((5, 5), dtype=bool))
print(f"粗細自檢：3x3 全黑 {int(_e3.sum())} px（僅交叉點），4x4 {int(_e4.sum())}，5x5 {int(_e5.sum())}")
print(f"黑像素合計：{int(lines_mask.sum())}")

arr = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
arr[lines_mask] = 0
canvas = Image.fromarray(arr, mode="RGB")

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