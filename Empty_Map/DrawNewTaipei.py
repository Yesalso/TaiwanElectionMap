import os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

# ----------------------配置----------------------
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map"

# 目标比例尺：1像素 = 40米
METERS_PER_PIXEL = 40
MAX_PX = 12000
SCALE_UP = 1.00          # 不放大
line_township_px = 2     # 乡镇界宽度
PAD_FRAC = 0.01          # 地图四周留白比例
threshold_val = 40
encoding = "UTF-8"
target_county = "新北市"
# ------------------------------------------------

os.makedirs(output_dir, exist_ok=True)

gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(epsg=3826)

# 只保留新北市
gdf_sub = gdf_all[gdf_all["COUNTYNAME"] == target_county].copy()
gdf_sub = gdf_sub[gdf_sub["TOWNNAME"].notna()].copy()
gdf_sub = gdf_sub[~gdf_sub.geometry.isna()].copy()
gdf_sub = gdf_sub[~gdf_sub.geometry.is_empty].copy()

# 合并到乡镇层级（只有乡镇，没有村里）
town_gdf = gdf_sub.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
print(f"新北市乡镇数量：{len(town_gdf)}")
print(f"Feature count: {len(town_gdf)}")

out_file = os.path.join(output_dir, "NewTaipei.png")

minx, miny, maxx, maxy = town_gdf.total_bounds
geo_w_m = maxx - minx
geo_h_m = maxy - miny

# 地图四周适度留白（1%宽度）
pad_x = PAD_FRAC * geo_w_m
pad_y = PAD_FRAC * geo_h_m
minx -= pad_x
maxx += pad_x
miny -= pad_y
maxy += pad_y
geo_w_m = maxx - minx
geo_h_m = maxy - miny

# 确保长宽都不超过 MAX_PX，比例尺不低于 1px=40米
scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
img_w_px = int(np.ceil(geo_w_m / scale))
img_h_px = int(np.ceil(geo_h_m / scale))
print(f"统一比例尺：1像素 = {scale:.4f} 米")
print(f"图片尺寸：{img_w_px} × {img_h_px} px")

DPI = 100
fig_w_inch = img_w_px / DPI
fig_h_inch = img_h_px / DPI

fig = plt.figure(figsize=(fig_w_inch, fig_h_inch), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")

town_gdf.plot(
    ax=ax,
    edgecolor="black",
    facecolor="white",
    linewidth=line_township_px * (DPI / 72.0)
)

# 乡镇内部相邻界线（避免海岸线重复加粗，绘制乡镇边界去掉外框的版本）
bounds = town_gdf.geometry.boundary
bounds.plot(
    ax=ax,
    edgecolor="black",
    facecolor="none",
    linewidth=line_township_px * (DPI / 72.0)
)
ax.axis("off")

buf = BytesIO()
plt.savefig(
    buf,
    format="png",
    dpi=DPI,
    pad_inches=0,
    bbox_inches=None,
    facecolor="white"
)
plt.close(fig)
buf.seek(0)

arr = np.frombuffer(buf.getvalue(), np.uint8)
img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, mask = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY_INV)
res_img = np.full_like(img, 255)
res_img[mask > 0] = 0

cv2.imwrite(out_file, res_img)
h, w = res_img.shape[:2]
print(f"Saved: {out_file} | size {w} x {h} px")

print("\n==== All finished ====")
print(f"输出目录：{output_dir}")