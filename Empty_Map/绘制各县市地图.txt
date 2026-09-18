import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import cv2
import numpy as np
from io import BytesIO

# ----------------------配置----------------------
shp_path = r"C:\Users\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
output_dir = r"C:\Users\Windows\Desktop\County"

# 1像素 = 10米
METERS_PER_PIXEL = 10
target_line_px = 1
threshold_val = 40
encoding = "UTF-8"

# 移除：高雄市、宜蘭縣
county_name_mapping = {
    "臺北市": "Taipei",
    "新北市": "NewTaipei",
    "桃園市": "Taoyuan",
    "臺中市": "Taichung",
    "臺南市": "Tainan",
    "基隆市": "Keelung",
    "新竹市": "Hsinchu",
    "嘉義市": "Chiayi",
    "新竹縣": "HsinchuCounty",
    "苗栗縣": "Miaoli",
    "彰化縣": "Changhua",
    "南投縣": "Nantou",
    "雲林縣": "Yunlin",
    "嘉義縣": "ChiayiCounty",
    "屏東縣": "Pingtung",
    "臺東縣": "Taitung",
    "花蓮縣": "Hualien",
    "澎湖縣": "Penghu",
    "金門縣": "Kinmen",
    "連江縣": "Lienjiang"
}
# ------------------------------------------------

os.makedirs(output_dir, exist_ok=True)

gdf_all = gpd.read_file(shp_path, encoding=encoding)
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
gdf_all = gdf_all.to_crs(epsg=3826)

print("字段列表：", gdf_all.columns.tolist())
print(f"统一比例尺：1像素 = {METERS_PER_PIXEL} 米")

for county_cn, file_en in county_name_mapping.items():
    print(f"\nProcessing: {county_cn} -> {file_en}.png")
    gdf_sub = gdf_all[gdf_all["COUNTYNAME"] == county_cn].copy()
    count = len(gdf_sub)
    if count <= 0:
        print(f"⚠️ {county_cn} no data, skip")
        continue
    print(f"Feature count: {count}")

    out_file = os.path.join(output_dir, f"{file_en}.png")

    minx, miny, maxx, maxy = gdf_sub.total_bounds
    geo_w_m = maxx - minx
    geo_h_m = maxy - miny

    img_w_px = int(np.ceil(geo_w_m / METERS_PER_PIXEL))
    img_h_px = int(np.ceil(geo_h_m / METERS_PER_PIXEL))

    # 保护：matplotlib Agg后端安全上限，边长超过32768直接跳过该县市，防止内存崩溃
    MAX_SAFE_PX = 32000
    if img_w_px > MAX_SAFE_PX or img_h_px > MAX_SAFE_PX:
        print(f"❌ {county_cn} 计算像素 {img_w_px}×{img_h_px}，超出安全上限，跳过，请调大METERS_PER_PIXEL")
        continue

    DPI = 100
    fig_w_inch = img_w_px / DPI
    fig_h_inch = img_h_px / DPI

    fig = plt.figure(figsize=(fig_w_inch, fig_h_inch), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")

    linewidth_val = target_line_px * (DPI / 72.0)
    gdf_sub.plot(
        ax=ax,
        edgecolor="black",
        facecolor="white",
        linewidth=linewidth_val
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
    print(f"✅ Saved: {out_file} | size {w} × {h} px")

print("\n==== All finished ====")
print(f"输出目录：{output_dir}")