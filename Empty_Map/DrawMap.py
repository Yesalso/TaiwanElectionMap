import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import cv2
import numpy as np
from io import BytesIO

# ----------------------配置----------------------
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"D:\Windows\TaiwanElection\Empty_Map"

# 目标比例尺：1像素 = 10米（若超出上限会自动放大）
METERS_PER_PIXEL = 10
MAX_PX = 12000
SCALE_UP = 1.10          # 比例放大10%
line_village_px = 1      # 村里界宽度
line_township_px = 2     # 乡镇市区界宽度
line_county_px = 3       # 县市地界宽度（台湾本岛等）
line_thin_county_px = 1  # 面积小的岛屿县市地界宽度（金门、连江、澎湖）
thin_counties = {"金門縣", "連江縣", "澎湖縣"}
ISLAND_SCALE = 1.0       # 金门、连江附图比例尺 = 台湾主图的1倍
line_inset_box_px = 6    # 金马附图外框宽度（金门、连江）
PAD_FRAC = 0.01          # 地图四周留白比例
threshold_val = 40
encoding = "UTF-8"

# 台湾省地图（排除金门、连江）
exclude_counties = {"金門縣", "連江縣"}
# ------------------------------------------------

os.makedirs(output_dir, exist_ok=True)

gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(epsg=3826)

# 去除无数据(NaN)或空几何的区域，不绘制
gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
gdf_all = gdf_all[~gdf_all.geometry.isna()].copy()
gdf_all = gdf_all[~gdf_all.geometry.is_empty].copy()

print("字段列表：", gdf_all.columns.tolist())

# 排除金门、连江，得到台湾省地图
gdf_sub = gdf_all[~gdf_all["COUNTYNAME"].isin(exclude_counties)].copy()

# 高雄市无数据区域（VILLNAME为NaN，未編定村里/代管）不绘制
gdf_sub = gdf_sub[~((gdf_sub["COUNTYNAME"] == "高雄市") & gdf_sub["VILLNAME"].isna())].copy()

# 基隆市代管的离岸岛屿（彭佳嶼、棉花嶼、花瓶嶼）不绘制
KEELUNG_OFFSHORE_KM = 25
kl_mask = gdf_sub["COUNTYNAME"] == "基隆市"
if kl_mask.any():
    kl_ref = gdf_sub.loc[kl_mask].geometry.union_all().centroid
    kl_dist_km = gdf_sub.loc[kl_mask].geometry.centroid.distance(kl_ref) / 1000.0
    kl_offshore = kl_dist_km > KEELUNG_OFFSHORE_KM
    gdf_sub = gdf_sub[~(kl_mask & kl_offshore.reindex(gdf_sub.index).fillna(False))].copy()


def drop_offshore_parts(gdf_sub, county, offshore_km):
    # 移除指定县市中远离本县主体的离岸岛屿部件（如宜蘭縣釣魚台列嶼）
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


# 宜蘭縣代管的离岸岛屿（釣魚台列嶼等）不绘制；没有乡镇市区的地方也不绘制
gdf_sub = drop_offshore_parts(gdf_sub, "宜蘭縣", 60)
gdf_sub = gdf_sub[gdf_sub["TOWNNAME"].notna()].copy()

# 金门、连江：1倍比例尺，平移到台湾岛左上方作为附图；
# 金门框在上、连江框在下，最左侧边界对齐，上下边界紧贴重合（各6px框），
# 乌坵以同比例尺放进金门框内空余区域（1px框）
islands = gdf_all[gdf_all["COUNTYNAME"].isin({"金門縣", "連江縣"})].copy()
island_boxes = []
if len(islands) > 0:
    m_minx, m_miny, m_maxx, m_maxy = gdf_sub.total_bounds
    m_w, m_h = m_maxx - m_minx, m_maxy - m_miny
    margin_x = 0.02 * m_w
    margin_y = 0.02 * m_h
    box_pad = 0.03           # 附图方框内容边距
    tgt_left = m_minx + margin_x
    filled_top = m_maxy - margin_y
    island_parts = []
    jinmen = islands[(islands["COUNTYNAME"] == "金門縣") & (islands["TOWNNAME"] != "烏坵鄉")]
    wuci = islands[(islands["COUNTYNAME"] == "金門縣") & (islands["TOWNNAME"] == "烏坵鄉")]
    lianjiang = islands[islands["COUNTYNAME"] == "連江縣"]
    groups = [("金門縣", jinmen), ("連江縣", lianjiang)]
    for cn, part in groups:
        if len(part) == 0:
            continue
        part = part.copy()
        x0, y0, x1, y1 = part.total_bounds
        part.geometry = part.geometry.scale(
            xfact=ISLAND_SCALE, yfact=ISLAND_SCALE, origin=(x0, y0)
        )
        cx0, cy0, cx1, cy1 = part.total_bounds
        cw, ch = cx1 - cx0, cy1 - cy0
        xp = box_pad * cw
        yp = box_pad * ch
        box_top = filled_top
        content_top = box_top - yp
        part.geometry = part.geometry.translate(
            xoff=(tgt_left + xp) - cx0, yoff=content_top - cy1
        )
        island_parts.append(part)
        box = (tgt_left, box_top - ch - 2 * yp, tgt_left + cw + 2 * xp, box_top)
        island_boxes.append((cn, box, line_inset_box_px))
        print(f"{cn}附图：{ISLAND_SCALE}倍比例尺，内容约 {cw/1000:.0f}×{ch/1000:.0f} km，位于左上")
        filled_top = box[1]  # 下一个框与当前框下边重合（上下紧贴）
    # 乌坵：以同比例尺放进金门内容框内的空余角落（不与其他岛屿重叠）
    if len(wuci) > 0:
        from shapely.geometry import box as shapely_box
        wuci = wuci.copy()
        wx0, wy0, wx1, wy1 = wuci.total_bounds
        wuci.geometry = wuci.geometry.scale(
            xfact=ISLAND_SCALE, yfact=ISLAND_SCALE, origin=(wx0, wy0)
        )
        wb0, wby0, wb1, wby1 = wuci.total_bounds
        ww, wh = wb1 - wb0, wby1 - wby0
        gx0, gy0, gx1, gy1 = island_parts[0].total_bounds
        gw, gh = gx1 - gx0, gy1 - gy0
        mx, my = 0.06 * gw, 0.06 * gh
        jm_geom = island_parts[0].geometry.union_all()
        candidates = [
            (gx0 + mx, gy1 - my - wh),        # 框内左上
            (gx1 - mx - ww, gy1 - my - wh),   # 框内右上
            (gx0 + mx, gy0 + my),             # 框内左下
            (gx1 - mx - ww, gy0 + my),        # 框内右下
        ]
        for cx, cy in candidates:
            candidate = wuci.geometry.translate(
                xoff=cx - wb0, yoff=cy - (wby1 - wh)
            )
            test_box = shapely_box(*candidate.total_bounds)
            if not test_box.intersects(jm_geom):
                candidate_box = (
                    cx - 0.1 * ww, cy - 0.1 * wh,
                    cx + 1.1 * ww, cy + 1.1 * wh,
                )
                island_parts.append(wuci.assign(geometry=candidate))
                island_boxes.append(("烏坵鄉", candidate_box, line_thin_county_px))
                print(f"烏坵鄉附图：{ISLAND_SCALE}倍比例尺，置于金门框内，内容约 {ww/1000:.0f}×{wh/1000:.0f} km")
                break
        else:
            print("警告：未找到乌坵空余位置，跳过乌坵附图")
    islands = gpd.GeoDataFrame(
        pd.concat(island_parts, ignore_index=True),
        geometry="geometry",
        crs=gdf_all.crs,
    )
    gdf_sub = gpd.GeoDataFrame(
        pd.concat(
            [gdf_sub[["COUNTYNAME", "TOWNNAME", "VILLCODE", "VILLNAME", "geometry"]],
             islands[["COUNTYNAME", "TOWNNAME", "VILLCODE", "VILLNAME", "geometry"]]],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=gdf_all.crs,
    )
print(f"台湾省包含县市：{sorted(gdf_sub['COUNTYNAME'].unique())}")
print(f"Feature count: {len(gdf_sub)}")

out_file = os.path.join(output_dir, "Taiwan.png")

minx, miny, maxx, maxy = gdf_sub.total_bounds
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

# 自动调整比例尺，确保长宽都不超过 MAX_PX，并放大10%
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

linewidth_val = line_village_px * (DPI / 72.0)
gdf_sub.plot(
    ax=ax,
    edgecolor="black",
    facecolor="white",
    linewidth=linewidth_val
)

# 乡镇市区界（2px）：金门、连江、澎湖只画内部相邻界线（外部海岸线由1px县界承担）
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

# 县市地界（3px）；金门、连江、澎湖等面积小的岛屿县海岸线用 1px
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

# 金门附图框、连江附图框（6px，左对齐、上下紧贴）、乌坵附图框（1px）
if island_boxes:
    from matplotlib.patches import Rectangle

    for cn, (bx0, by0, bx1, by1), lw in island_boxes:
        box = Rectangle(
            (bx0, by0),
            bx1 - bx0,
            by1 - by0,
            fill=False,
            edgecolor="black",
            linewidth=lw * (DPI / 72.0),
        )
        ax.add_patch(box)
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