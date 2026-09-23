import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import cv2
from io import BytesIO

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===================== 配置区 =====================
SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
OUT_PNG = os.path.join(os.path.expanduser("~"), "Desktop", "Penghu_Empty_Map.png")
CITY_NAME = "澎湖縣"

METERS_PER_PIXEL = 10          # 比例尺：1像素 = 10米（1-10）
MAX_SAFE_PX = 32000

VILL_LINE_PX = 1               # 村里界线宽
TOWN_LINE_PX = 3               # 乡镇市区界线宽（3px）
COAST_LINE_PX = 2              # 海岸线外轮廓宽

MAP_PAD_FRAC = 0.03            # 适度留白 3%

BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2   # 缓冲用直线多边形

os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)

# ===================== 读取 SHP =====================
gdf = gpd.read_file(SHP_PATH, encoding="UTF-8")
for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]:
    if c not in gdf.columns:
        raise ValueError(f"SHP缺失必要字段：{c}")

if gdf.crs is None:
    gdf.crs = "EPSG:4326"
if gdf.crs.is_geographic:
    gdf = gdf.to_crs(epsg=3826)

gdf = gdf[gdf["COUNTYNAME"].astype(str).str.contains("澎湖", na=False)].copy()
if len(gdf) == 0:
    raise ValueError("SHP 中未找到澎湖縣数据")

gdf = gdf[gdf["VILLNAME"].notna()].copy()
gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
print(f"澎湖縣村里要素总数：{len(gdf)}")

# ===================== 画布 =====================
minx, miny, maxx, maxy = gdf.total_bounds
pad_x = (maxx - minx) * MAP_PAD_FRAC
pad_y = (maxy - miny) * MAP_PAD_FRAC
xlim = (minx - pad_x, maxx + pad_x)
ylim = (miny - pad_y, maxy + pad_y)

w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))

if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
    raise Exception(f"图像尺寸超限 {w_px}×{h_px}，调大METERS_PER_PIXEL")

print(f"比例尺：1像素 = {METERS_PER_PIXEL} 米，图像 {w_px}×{h_px} px，四周留白 {MAP_PAD_FRAC*100:.0f}%")

DPI = 100
PX2PT = 72.0 / DPI

fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(*xlim)
ax.set_ylim(*ylim)
ax.set_facecolor("#FFFFFF")

town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
coast_half_m = COAST_LINE_PX * METERS_PER_PIXEL / 2

city_geom = gdf.geometry.union_all()
town_gdf = gdf.dissolve(by="TOWNNAME")

# ① 白色填充（无边）
gdf.plot(ax=ax, facecolor="#FFFFFF", edgecolor="none",
         linewidth=0, antialiased=False, legend=False)

# ② 村里界 1px 黑线
vill_lines = gdf.boundary.union_all()
if not vill_lines.is_empty:
    gpd.GeoSeries([vill_lines]).plot(
        ax=ax, edgecolor='black', facecolor='none',
        linewidth=VILL_LINE_PX * PX2PT, antialiased=False, zorder=5
    )

# ③ 乡镇市区界 3px 黑带（只落在陆地侧）
town_lines = town_gdf.boundary.union_all()
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

# ④ 海岸线外轮廓 2px 黑带
outer = city_geom.boundary.buffer(
    coast_half_m, resolution=BUF_RES,
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

# 量化到白/黑两色
allowed_rgb_255 = np.array([[255, 255, 255], [0, 0, 0]], dtype=np.float32)
pixels = img_rgb.reshape(-1, 3).astype(np.float32)
d_white = np.sqrt(((pixels - allowed_rgb_255[0]) ** 2).sum(axis=1))
d_black = np.sqrt(((pixels - allowed_rgb_255[1]) ** 2).sum(axis=1))
idx = np.where(d_black < d_white, 1, 0)
quantized = allowed_rgb_255[idx].astype(np.uint8).reshape(img_rgb.shape)

cv2.imwrite(OUT_PNG, cv2.cvtColor(quantized, cv2.COLOR_RGB2BGR))
print(f"✅ 输出: {OUT_PNG}  ({w_px}×{h_px}px)")
print(f"   线宽: 村里{VILL_LINE_PX}px | 乡镇{TOWN_LINE_PX}px | 海岸外轮廓{COAST_LINE_PX}px")