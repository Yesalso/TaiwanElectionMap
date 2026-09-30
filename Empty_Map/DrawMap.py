# -*- coding: utf-8 -*-
"""
基隆市地图（纯黑白线稿）—— 村里界 1px + 区界线 3px，比例尺 1px = 7 米
只画「有名字」的面：COUNTYNAME / TOWNNAME / VILLNAME 皆非空才绘制；
基隆市的 VILLNAME 为空者是「未編定村里」（彭佳嶼、棉花嶼、花瓶嶼等离岛 33~59 km，
以及零星未编定区块），全部不绘制，故离岛自然排除，无需另加离岛过滤。

两层各自独立绘制，最后做并集叠加：
  ① 村里层（1px）：PIL Bresenham 逐段 1px 直绘 → skimage.morphology.thin 取中心线。
     实测游程以 1px 为主、2x2 全黑 = 0，保证全图村里界都是 1px。
  ② 区界层（3px）：只取 TOWNNAME 层级（基隆 7 个区）dissolve，不碰村里资料，
     matplotlib(Agg, DPI=100) 以 linewidth = LINE_DISTRICT_PT*DPI/72 pt 绘制区面与区界
     （区面的外框就是市界与海岸线，故海岸线自动同宽，不需另外处理），
     再用阈值 THRESHOLD_VAL 二值化切掉抗锯齿灰边 → 纯黑 3px 线层。
     线宽标定（本画布 2665x2001 实测）：0.5pt→1px、1.0pt→2px、1.5pt→3px、
     2.0pt→4px、3.0pt→5px；故 3px 取 1.5pt。
     此层不含任何村里线，所以叠加后不会把村里线加粗。
  叠加：lines_mask = ①1px 村里层 | ②3px 区界层（黑叠黑）。
  两层用同一套像素网格约定（像素 i 中心 = minx+(i+0.5)/sx），叠加处不会错开 1px。

  自检：区界 1px 原始线 100% 被 3px 层覆盖、村里层无 2x2 粗块（保证 1px）、
        5x5 以上全黑块 ≈0（无鼓包）、全图仅纯黑/纯白两色。
输出：Empty_Map/Keelung_village.png   （含村里界线的版本，无地名）
      Empty_Map/layer_district_3px.png（②层单独输出，便于核对）
诊断：Empty_Map/diag_keelung.png（仁爱区密集区 1:1 裁片）
"""
import os
import math
import warnings
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from PIL import Image, ImageDraw
from skimage.morphology import thin          # ① 村里层：1px 直绘 → thin 中心线
from scipy import ndimage                    # 自检用
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None

# ===================== 配置 =====================
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map"
out_name = "Keelung_village.png"      # 村里界线版（无地名）；原 Keelung.png 保留不动
layer_name = "layer_district_3px.png"    # ② 层单独输出（核对用）
diag_name = "diag_keelung.png"            # 1:1 诊断裁片
TARGET_COUNTY = "基隆市"
TARGET_CRS = "EPSG:3826"
encoding = "UTF-8"

# 比例尺：1 像素 = 7 米
METERS_PER_PIXEL = 7.0
MAX_PX = 12000
SCALE_UP = 1.0          # 不额外放大，严格 1px = 7m
PAD_FRAC = 0.01         # 地图四周留白比例

# 线宽
LINE_VILLAGE_PX = 1     # ① 村里界（PIL 直绘宽度）
LINE_DISTRICT_PT = 1.5  # ② matplotlib 线宽(pt)：阈值后约 3px（见档头标定）
THRESHOLD_VAL = 40      # ② 二值化阈值
SAVE_LAYER = True       # ② 层是否单独存档
MAKE_DIAG = True        # 是否输出 1:1 诊断裁片
DIAG_AREA = "仁愛區"     # 诊断裁片区域（基隆最密集：29 村里 / 4.48 km²）
# ==================================================

warnings.filterwarnings("ignore")
os.makedirs(output_dir, exist_ok=True)

# ----------------------读取 SHP ----------------------
gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(TARGET_CRS)
print(f"原始要素数：{len(gdf_all)}")

# ----------------------只保留「有名字」的面 ----------------------
def named_mask(df, cols):
    """各指定栏位皆非空、且剝除空白后仍有字串"""
    m = np.ones(len(df), dtype=bool)
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c].astype(str).str.strip()
        m &= df[c].notna().to_numpy() & (s != "") & (s != "nan") & (s != "None")
    return m


dropped_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty]
dropped_all = dropped_all[~named_mask(dropped_all, ["COUNTYNAME", "TOWNNAME", "VILLNAME"])]
print(f"无名称（COUNTYNAME/TOWNNAME/VILLNAME 有空值）不绘制：{len(dropped_all)} 个要素")

gdf_sub = gdf_all[named_mask(gdf_all, ["COUNTYNAME", "TOWNNAME", "VILLNAME"])].copy()
gdf_sub = gdf_sub[gdf_sub["COUNTYNAME"] == TARGET_COUNTY].copy()
gdf_sub = gdf_sub[~gdf_sub.geometry.isna() & ~gdf_sub.geometry.is_empty].copy()
gdf_sub = gdf_sub[["TOWNNAME", "VILLNAME", "geometry"]].copy()
gdf_sub["geometry"] = gdf_sub.geometry.buffer(0)
gdf_sub["TOWNNAME"] = gdf_sub["TOWNNAME"].astype(str).str.strip()
gdf_sub["VILLNAME"] = gdf_sub["VILLNAME"].astype(str).str.strip()

villages = gdf_sub.reset_index(drop=True)
districts = villages.dissolve(by="TOWNNAME").reset_index()      # ② 层只用这一层级
print(f"{TARGET_COUNTY}：{len(districts)} 个区，{len(villages)} 个村里"
      f"（有效几何 {int(villages.geometry.is_valid.sum())}/{len(villages)}）")
print("区：", "、".join(districts["TOWNNAME"].tolist()))

# 被排除的无名称要素离主体多远（确认离岛已排除）
_kl_drop = dropped_all[dropped_all["COUNTYNAME"] == TARGET_COUNTY]
if len(_kl_drop) > 0:
    _ref = villages.geometry.union_all().centroid
    _d = _kl_drop.geometry.distance(_ref) / 1000.0
    print(f"排除的{TARGET_COUNTY}无名称要素 {len(_kl_drop)} 个，距主体最近 {_d.min():.1f} km"
          f"（最远 {_d.max():.1f} km，不入图）")

# ----------------------画布尺寸 ----------------------
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

# 统一比例尺，长宽都不超过 MAX_PX
scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
w_px = int(math.ceil(geo_w_m / scale))
h_px = int(math.ceil(geo_h_m / scale))
sx, sy = w_px / geo_w_m, h_px / geo_h_m
print(f"统一比例尺：1像素 = {geo_w_m / w_px:.4f} 米")
print(f"图片尺寸：{w_px} × {h_px} px")

# 像素网格约定：像素 i 的中心对应 minx+(i+0.5)/sx，与 matplotlib 渲染网格一致，
# ①（1px 村里层）与 ②（3px 区界层）叠加才不会错开 1px（故用 floor 而非 round）
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
    """Bresenham 逐段描绘（width 像素宽的纯黑白线），返回 bool 阵列"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


# ----------------------① 村里界 1px ----------------------
print(f"\n① 村里界 {LINE_VILLAGE_PX}px（1px 直绘 → thin 中心线）...")
village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
village_arr = draw_layer(village_lines, 1)
village_skel = thin(village_arr)
print(f"村里层 {LINE_VILLAGE_PX}px 中心线：{int(village_skel.sum())} px"
      f"（1px 线 {int(village_arr.sum())} px）")

# ----------------------② 区界线 3px（含市界与海岸线）----------------------
print("② 区界线 3px（matplotlib + 阈值二值化）...")
DPI = 100
fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")
_lw = LINE_DISTRICT_PT * (DPI / 72.0)
districts.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=_lw)
districts.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=_lw)
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
district_layer = _tmask > 0          # 纯黑 3px 线层（区界 + 市界 + 海岸线），不含村里线
print(f"区界层：{int(district_layer.sum())} px"
      f"（线宽 {LINE_DISTRICT_PT}pt={_lw:.2f}px，阈值 {THRESHOLD_VAL}）")

S3 = np.ones((3, 3), dtype=bool)
# 对齐自检：② 层必须覆盖区界 1px 原始线（含市界/海岸线），否则两层网格不一致
_district_1px = draw_layer(extract_lines(unary_union(districts.geometry.boundary.tolist())), 1)
_miss = int((_district_1px & ~ndimage.binary_dilation(district_layer, structure=S3)).sum())
print(f"区界+市界 1px 原始线 {int(_district_1px.sum())} px，未被 3px 层覆盖 {_miss} px（应 ≈0）")
del _district_1px

# ----------------------叠加 ----------------------
lines_mask = village_skel | district_layer

# 村里线自检：扣掉 3px 层后不应出现 2x2 连续黑块（1px 线不会有 2x2 方块）
_v_only = village_skel & ~district_layer
_2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
print(f"村里层 1px 像素：{int(_v_only.sum())}，2x2 粗块（应 ≈0）：{int(_2x2.sum())}")
# 鼓包自检：3px 线允许在交叉点出现 4x4/5x4 全黑，更大应 ≈0
_e3 = ndimage.binary_erosion(lines_mask, structure=np.ones((3, 3), dtype=bool))
_e4 = ndimage.binary_erosion(lines_mask, structure=np.ones((4, 4), dtype=bool))
_e5 = ndimage.binary_erosion(lines_mask, structure=np.ones((5, 5), dtype=bool))
_e6 = ndimage.binary_erosion(lines_mask, structure=np.ones((6, 6), dtype=bool))
print(f"粗细自检：3x3 {int(_e3.sum())}，4x4 {int(_e4.sum())}，5x5 {int(_e5.sum())}，6x6 {int(_e6.sum())}（应 ≈0）")
print(f"黑像素合计：{int(lines_mask.sum())}")

# 游程分布（横向，直观确认 1px 与 3px）
def run_lengths(mask, step=3):
    runs = []
    for r in range(0, h_px, step):
        s = mask[r]
        if not s.any():
            continue
        d_ = np.diff(np.concatenate(([0], s.astype(np.int8), [0])))
        runs.extend((np.where(d_ == -1)[0] - np.where(d_ == 1)[0]).tolist())
    return np.array(runs)


for _nm, _m in (("① 村里层(1px)", _v_only), ("② 区界层(3px)", district_layer)):
    _r = run_lengths(_m)
    _u, _c = np.unique(_r, return_counts=True)
    _top = sorted(zip(_u.tolist(), _c.tolist()), key=lambda z: -z[1])[:4]
    print(f"{_nm} 横向游程（像素宽:出现次数，前4多）= {_top}")

arr = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
arr[lines_mask] = 0          # 线界以纯黑叠加（无灰阶）
canvas = Image.fromarray(arr, mode="RGB")

# 颜色验证：全图应只含纯黑 / 纯白两级像素
_uniq = np.unique(arr.reshape(-1, 3), axis=0)
print(f"全图颜色种类：{len(_uniq)}（应为 2：纯黑线界 + 纯白底）")

# ----------------------保存 ----------------------
def save_png(img, path):
    """目标档被看图程式锁定时（Windows Errno 22/32），自动改存 _new.png"""
    try:
        img.save(path, format="png")
        return path
    except OSError as e:
        alt = path[:-4] + "_new.png"
        print(f"⚠️ {os.path.basename(path)} 写入失败（{e}），改存 {os.path.basename(alt)}")
        img.save(alt, format="png")
        return alt


if SAVE_LAYER:
    _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    _la[district_layer] = 0
    print("② 层单独输出:", save_png(Image.fromarray(_la, mode="RGB"),
                                   os.path.join(output_dir, layer_name)))

out_file = save_png(canvas, os.path.join(output_dir, out_name))
print(f"Saved: {out_file} | size {w_px} x {h_px} px")

# ----------------------诊断裁片（1:1）----------------------
if MAKE_DIAG:
    _sub = villages[villages["TOWNNAME"] == DIAG_AREA].total_bounds
    _x0 = int(max(0, (_sub[0] - minx) * sx - 80))
    _y0 = int(max(0, (maxy - _sub[3]) * sy - 80))
    _x1 = int(min(w_px, (_sub[2] - minx) * sx + 80))
    _y1 = int(min(h_px, (maxy - _sub[1]) * sy + 80))
    try:
        canvas.crop((_x0, _y0, _x1, _y1)).save(os.path.join(output_dir, diag_name))
        print("诊断裁片:", os.path.join(output_dir, diag_name), (_x1 - _x0, _y1 - _y0))
    except OSError as _e:
        print("⚠️ 诊断裁片输出失败（可忽略）:", _e)

print("\n==== All finished ====")
print(f"输出目录：{output_dir}")
