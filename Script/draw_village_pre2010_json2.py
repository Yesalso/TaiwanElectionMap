import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from io import BytesIO

json_path = r"D:\Windows\Documents\村里界歷史圖資_111\JSON2\json\twVillage_pre2010.geo.json"
output_dir = r"D:\Windows\Documents\村里界歷史圖資_111\output"

METERS_PER_PIXEL = 10
MAX_PX = 12000
SCALE_UP = 1.10
line_village_px = 1
line_township_px = 2
line_county_px = 3
line_thin_county_px = 1
thin_counties = {"澎湖縣"}
PAD_FRAC = 0.01
threshold_val = 40

exclude_counties = {"金門縣", "連江縣"}

os.makedirs(output_dir, exist_ok=True)

gdf_all = gpd.read_file(json_path)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(epsg=3826)

gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
gdf_all = gdf_all[~gdf_all.geometry.isna()].copy()
gdf_all = gdf_all[~gdf_all.geometry.is_empty].copy()

print("字段列表：", gdf_all.columns.tolist())
print(f"Feature count(total): {len(gdf_all)}")

gdf_sub = gdf_all[~gdf_all["COUNTYNAME"].isin(exclude_counties)].copy()

def drop_offshore_parts(gdf_sub, county, offshore_km):
    mask = gdf_sub["COUNTYNAME"] == county
    if not mask.any():
        return gdf_sub
    sub = gdf_sub.loc[mask].copy()
    ref = sub.geometry.union_all().centroid
    exploded = sub.geometry.explode(index_parts=True)
    fr = gpd.GeoDataFrame(exploded.reset_index(), geometry="geometry", crs=sub.crs)
    far = fr.geometry.centroid.distance(ref) / 1000.0 > offshore_km
    if not far.any():
        return gdf_sub
    from shapely.geometry import MultiPolygon
    out = gdf_sub.copy()
    for oi in fr.loc[far, "level_0"].unique():
        keep = fr.loc[(fr["level_0"] == oi) & ~far, "geometry"].tolist()
        if keep:
            out.loc[oi, "geometry"] = MultiPolygon(keep) if len(keep) > 1 else keep[0]
    return out

gdf_sub = drop_offshore_parts(gdf_sub, "宜蘭縣", 60)
gdf_sub = gdf_sub[gdf_sub["TOWNNAME"].notna()].copy()
gdf_sub.geometry = gdf_sub.geometry.make_valid()

print(f"縣市：{sorted(gdf_sub['COUNTYNAME'].unique())}")
print(f"Feature count: {len(gdf_sub)}")

out_file = os.path.join(output_dir, "Taiwan_village_pre2010_JSON2.png")

minx, miny, maxx, maxy = gdf_sub.total_bounds
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
img_w_px = int(np.ceil(geo_w_m / scale))
img_h_px = int(np.ceil(geo_h_m / scale))
print(f"統一比例尺：1像素 = {scale:.4f} 米")
print(f"圖片尺寸：{img_w_px} × {img_h_px} px")

DPI = 100
fig_w_inch = img_w_px / DPI
fig_h_inch = img_h_px / DPI

fig = plt.figure(figsize=(fig_w_inch, fig_h_inch), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")

linewidth_val = line_village_px * (DPI / 72.0)
gdf_sub.plot(
    ax=ax,
    edgecolor="black",
    facecolor="white",
    linewidth=linewidth_val
)

county_gdf = gdf_sub.dissolve(by="COUNTYNAME").reset_index()
town_gdf = gdf_sub.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
town_thick = town_gdf[~town_gdf["COUNTYNAME"].isin(thin_counties)]
town_thick.plot(
    ax=ax,
    edgecolor="black",
    facecolor="none",
    linewidth=line_township_px * (DPI / 72.0)
)

internal_lines = []
for cn in thin_counties:
    crows = county_gdf[county_gdf["COUNTYNAME"] == cn]
    if len(crows) == 0:
        continue
    cbound = crows.geometry.iloc[0].boundary
    for tg in town_gdf[town_gdf["COUNTYNAME"] == cn].geometry:
        seg = tg.boundary.difference(cbound)
        if not seg.is_empty:
            internal_lines.append(seg)
if internal_lines:
    gpd.GeoSeries(internal_lines, crs=gdf_sub.crs).plot(
        ax=ax,
        edgecolor="black",
        facecolor="none",
        linewidth=line_township_px * (DPI / 72.0)
    )

county_thick = county_gdf[~county_gdf["COUNTYNAME"].isin(thin_counties)]
county_thick.plot(
    ax=ax,
    edgecolor="black",
    facecolor="none",
    linewidth=line_county_px * (DPI / 72.0)
)
county_thin = county_gdf[county_gdf["COUNTYNAME"].isin(thin_counties)]
county_thin.plot(
    ax=ax,
    edgecolor="black",
    facecolor="none",
    linewidth=line_thin_county_px * (DPI / 72.0)
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

from PIL import Image
buf.seek(0)
im = Image.open(buf).convert("RGB")
arr = np.asarray(im)
gray = (arr[..., 0].astype(np.int16) + arr[..., 1].astype(np.int16) + arr[..., 2].astype(np.int16)) // 3
res_img = np.full(arr.shape[:2], 255, np.uint8)
res_img[gray < threshold_val] = 0
Image.fromarray(res_img, mode="L").save(out_file)
h, w = res_img.shape[:2]
print(f"Saved: {out_file} | size {w} x {h} px")

print("\n==== All finished ====")
print(f"輸出目錄：{output_dir}")