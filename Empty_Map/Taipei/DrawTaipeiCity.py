# -*- coding: utf-8 -*-
"""
臺北市 · 村里界 1px + 區界 3px + 市界 5px（純黑白線稿，無填充、無地名）
（由 Kaohsiung/DrawKaohsiungCity.py 派生；高雄版為「村里 1px + 區/市界 2px」兩層，
  本版依需求改為三層線寬：

  ① 村里層（1px）——沿用海南「鄉鎮畫法」：
     PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線。
     此層只含全市 456 個里的界線，一律 1px。

  ② 區界層（3px）——12 個區 dissolve 後取 boundary 的聯集，
     先用 PIL 畫成 1px 骨架（與①同一套像素網格約定），再以 3x3 方形核
     binary_dilation 一次 → 精確 3px 寬的純黑線層。
     （不經 matplotlib 抗鋸齒＋閾值，寬度由膨脹核尺寸決定，完全可控。）

  ③ 市界層（5px）——全市 dissolve 後取外邊界（臺北市無海岸線、無離島，
     外邊界即市界），同樣先畫 1px 骨架再以 5x5 方形核膨脹一次 → 5px。
     疊加順序：先區界 3px、再市界 5px 蓋在外圈 → 外圈最終 5px。

  疊加：lines_mask = 村里 1px | 區界 3px | 市界 5px（黑疊黑）。
  三層共用同一套像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加處不會錯開。

  自檢：村里層扣除粗線後無 2x2 粗塊（保證 1px）、區界層扣除市界後無 4x4 粗塊
        （保證 3px）、市界層無 6x6 粗塊（保證 5px）、市界層單一連通、
        全圖僅純黑/純白兩色。
輸出：Taipei/TaipeiCity_VillageDistrict.png
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
from scipy import ndimage                    # 自檢／膨脹用

Image.MAX_IMAGE_PIXELS = None

# ===================== 配置 =====================
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map\Taipei"
out_name = "TaipeiCity_VillageDistrict.png"
target_county = "臺北市"
encoding = "UTF-8"
TARGET_CRS = "EPSG:3826"

# 比例尺：1px = 10m，再放大 10%（與高雄版一致）
# 臺北市 bbox 約 26000 x 29000 m，故地圖約 3100x3500 px
METERS_PER_PIXEL = 10.0
MAX_PX = 12000
SCALE_UP = 1.10
PAD_FRAC = 0.01          # 地圖四周留白比例

# ★ 關閉簡化（修掉「多餘線條」的關鍵，說明見 DrawKaohsiungCity.py 檔頭）
SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（保留原始測量採點）

# 線寬
LINE_VILLAGE_PX = 1      # ① 村里界（PIL 直繪寬度，thin 後 1px）
LINE_DISTRICT_PX = 3     # ② 區界（1px 骨架 + 3x3 方形核膨脹）
LINE_CITY_PX = 5         # ③ 市界（1px 骨架 + 5x5 方形核膨脹）

# ★ 微孔洞清理（修掉「散點」的元兇，說明見 DrawKaohsiungCity.py）
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

# ★ 離群圖斑防呆（臺北市轄內無離島；此 bbox 只是防止資料筆誤的離群圖斑
#   把畫布撐爆，範圍取自 DrawTaipeiCityLabeled.py 的 MAINLAND_BBOX）
MAINLAND_BBOX = (290000.0, 2755000.0, 325000.0, 2795000.0)   # EPSG:3826
_mx0, _my0, _mx1, _my1 = MAINLAND_BBOX
_rp = villages.geometry.representative_point()
_in_box = (_rp.x >= _mx0) & (_rp.x <= _mx1) & (_rp.y >= _my0) & (_rp.y <= _my1)
if (~_in_box).any():
    print(f"★ 離群圖斑排除：{int((~_in_box).sum())} 筆")
    villages = villages[_in_box].copy()

townships = villages.dissolve(by="TOWNNAME").reset_index()      # ②③ 層用這一層級
print(f"{target_county}區：{len(townships)}，村里 {len(villages)}")


# ----------------------清理微小內環（散點元兇）----------------------
def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)。這些是 dissolve 浮點誤差造成的細長微孔，
    若不處理會被描成一圈圈細線，二值化後斷成「多餘的點」。
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

# ----------------------像素網格約定（三層共用）----------------------
# 像素 i 的中心對應 minx+(i+0.5)/sx，與 1px 直繪一致，層間疊加不會錯開 1px
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


def thicken(mask_1px, size):
    """1px 骨架 → size px 寬線（size 為奇數；方形核膨脹 (size-1)//2 次）"""
    n = (size - 1) // 2
    out = mask_1px
    for _ in range(n):
        out = ndimage.binary_dilation(out, structure=np.ones((3, 3), dtype=bool))
    return out


# ----------------------① 村里界 1px（海南「鄉鎮畫法」）----------------------
print("\n① 村里界 1px（1px 直繪 → thin 中心線）...")
village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
village_arr = draw_layer(village_lines, 1)
village_skel = thin(village_arr)
print(f"村里層 {LINE_VILLAGE_PX}px 中心線：{int(village_skel.sum())} px"
      f"（1px 線 {int(village_arr.sum())} px）")

# ----------------------② 區界 3px----------------------
print("② 區界 3px（1px 骨架 + 3x3 膨脹）...")
district_lines = extract_lines(unary_union(townships.geometry.boundary.tolist()))
district_1px = draw_layer(district_lines, 1)
district_3px = thicken(district_1px, LINE_DISTRICT_PX)
print(f"區界層 {LINE_DISTRICT_PX}px：{int(district_3px.sum())} px"
      f"（1px 骨架 {int(district_1px.sum())} px）")

# ----------------------③ 市界 5px----------------------
print("③ 市界 5px（全市 dissolve 外邊界 + 5x5 膨脹）...")
city_geom = unary_union(townships.geometry.tolist())
# ★ 只取「外環」當市界：淡水河／基隆河沿岸屬未編定圖斑，dissolve 後在市內
#   留有大空洞，boundary() 會把洞的內環也當邊界；內環實為區界層級（3px，
#   由②層的區界涵蓋），只有外環才是真正的市界（5px）。
_city_parts = list(city_geom.geoms) if hasattr(city_geom, "geoms") else [city_geom]
city_lines = []
for _p in _city_parts:
    if _p.geom_type == "Polygon":
        city_lines.append(list(_p.exterior.coords))
city_1px = draw_layer(city_lines, 1)
city_5px = thicken(city_1px, LINE_CITY_PX)
print(f"市界層 {LINE_CITY_PX}px：{int(city_5px.sum())} px"
      f"（1px 骨架 {int(city_1px.sum())} px）")

# 市界層自檢：應為單一連通網（臺北市僅一塊完整市域，無離島）
_cc_lab, _cc_n = ndimage.label(city_5px, structure=np.ones((3, 3), dtype=bool))
print(f"市界層連通分量：{_cc_n} 個（應為 1）")
if _cc_n != 1:
    print("⚠️ 市界層出現多個連通分量，請檢查資料是否含離島或碎片")

# ★ 簡化自檢：simplify 會把緩彎拉直成橫貫村里的斜直線
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
# ★ 村里線先「剪貼」：把貼著區界 3px／市界 5px 帶的村里像素剪掉，
#   否則 thin() 後的村里中心線與未 thin 的區界原始線錯開 1px，
#   疊加處會參差地多出 1px（區界局部變 4~5px 粗細不均）。
#   剪貼後村里線止於粗線帶邊緣，接點自然被粗線帶覆蓋，不會產生縫隙。
_S3 = np.ones((3, 3), dtype=bool)
village_draw = (village_skel
                & ~ndimage.binary_dilation(district_3px, structure=_S3)
                & ~ndimage.binary_dilation(city_5px, structure=_S3))
_clipped = int(village_skel.sum() - village_draw.sum())
print(f"村里線剪貼：貼近粗線帶剪去 {_clipped} px（避免區界/市界邊緣參差）")

lines_mask = village_draw | district_3px | city_5px

# 村里線自檢：扣掉 3px/5px 層後不應出現 2x2 連續黑塊（1px 線不會有 2x2 方塊）
_v_only = village_draw & ~district_3px & ~city_5px
_2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
print(f"村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")

# 區界自檢：扣掉市界 5px 後，3px 線不應有 4x4 全黑塊
_d_only = district_3px & ~city_5px
_4x4 = ndimage.binary_erosion(_d_only, structure=np.ones((4, 4), dtype=bool))
print(f"區界層 3px 像素（扣除市界）：{int(_d_only.sum())}，4x4 粗塊（應≈0）：{int(_4x4.sum())}")

# 市界自檢：5px 線不應有 6x6 全黑塊（交叉點除外，應極少）
_6x6 = ndimage.binary_erosion(city_5px, structure=np.ones((6, 6), dtype=bool))
print(f"市界層 5px 像素：{int(city_5px.sum())}，6x6 粗塊（應≈0）：{int(_6x6.sum())}")
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


out_file = save_png(canvas, os.path.join(output_dir, out_name))
print(f"Saved: {out_file} | size {w_px} x {h_px} px")

print("\n==== All finished ====")
print(f"輸出目錄：{output_dir}")
