# -*- coding: utf-8 -*-
"""
繪製 1990 年（行政區調整前）臺北市「舊行政區」界線圖 —— 只有區界線、不畫里。

背景：1990 年臺北市把 16 個行政區整併為 12 個。本圖畫的是**調整前**的舊區界，
只畫下列 10 個涉入整併的舊行政區（所轄里對照表見 Taipei1990_OldDistricts.md，
以現行 111 年村里界回推、dissolve 成舊區多邊形）：

    龍山區、城中區、雙園區、古亭區、延平區、建成區、
    大同區、大安區、松山區、中山區

★ 只畫這 10 個舊區（使用者指定），士林/北投/內湖/南港/文山（木柵+景美）不在圖上：
  MD 對照表也只涵蓋這 10 區；其中士林區明勝里、內湖區康寧里因屬舊中山區而納入。

著色：全部白色填色（白底 RGB，之後可走 tool/make_transparent.py 白轉透明），
只以黑色線條表現區界 —— 區界 4px 黑帶、市外輪廓 6px 黑帶（與主腳本一致），
最後做「只允許白/黑」的顏色量化，保證白轉透明流程安全。

輸出：png/map/1990/map.png

執行：
    py Converge_to_map_taipei_1990.py
"""
import os
import re
import unicodedata
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(BASE_DIR, "Taipei1990_OldDistricts.md")
OUT_DIR = os.path.join(BASE_DIR, "png", "map", "1990")
OUT_PNG = os.path.join(OUT_DIR, "map.png")

# 與 Converge_to_map_taipei.py 同一套繪圖參數
SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
SHP_ENCODING = "utf-8"
METERS_PER_PIXEL, MAX_SAFE_PX = 10, 32000   # 1px = 10m
TOWN_LINE_PX = 4              # 舊區界線寬（黑帶）
OUTER_LINE_PX = 6             # 市外輪廓線寬（黑帶）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2
MAP_PAD_FRAC = 0.03

# 對照表用字 → 圖資用字（異體字／近字修正）
VILLAGE_VARIANT_MAP = {
    "凌宵": "凌霄",   # 萬華區凌霄里（MD 寫凌宵里）
}

# 舊區著色（本圖一律白色，僅界線）—— 保留常數便於日後上色
FILL_HEX = "#FFFFFF"
ALLOWED_HEX = ["#FFFFFF", "#000000"]


def normalize_name(s):
    s = unicodedata.normalize('NFKC', str(s).strip())
    s = s.replace('臺', '台').rstrip('里')
    return VILLAGE_VARIANT_MAP.get(s, s)


def parse_md_assignments(md_path):
    """解析 Taipei1990_OldDistricts.md → {舊區名: [(現行區, 里名), ...]}。

    只取直接隸屬的列；備註含「歸」者為重疊里（已在主要舊區），略過；
    現行區為「—」者是已消失的舊里（無幾何），略過。
    """
    text = open(md_path, encoding="utf-8").read()
    assigns = {}
    cur_old = None
    for line in text.splitlines():
        m = re.match(r'^## (\S+?)（', line)
        if m:
            cur_old = m.group(1)
            assigns.setdefault(cur_old, [])
            continue
        if not cur_old:
            continue
        m = re.match(r'^\| (中山|信義|中正|大同|大安|萬華|松山|士林|內湖)區 \| (\S+?)里 \|(.*)\|', line)
        if not m:
            continue
        if '歸' in m.group(3):      # 重疊里，歸主要舊區（該列只是提示）
            continue
        assigns[cur_old].append((m.group(1) + '區', m.group(2) + '里'))
    return assigns


def load_taipei_villages():
    gdf = gpd.read_file(SHP_PATH, encoding=SHP_ENCODING)
    gdf = gdf[gdf["COUNTYNAME"] == "臺北市"].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.is_geographic:
        gdf = gdf.to_crs(epsg=3826)
    gdf["vcore"] = gdf["VILLNAME"].map(normalize_name)
    return gdf


def assign_old_districts(gdf, assigns):
    """把現行里指派到舊區。回傳 (有指派的 gdf 子集, 未匹配清單)。"""
    lookup = {}
    for i, row in gdf.iterrows():
        lookup[(row["TOWNNAME"], row["vcore"])] = i

    old_of = {}
    unmatched = []
    for old_name, pairs in assigns.items():
        for town, vill in pairs:
            key = (town, normalize_name(vill))
            if key in lookup:
                old_of[lookup[key]] = old_name
            else:
                unmatched.append((old_name, town, vill))

    sub = gdf[gdf.index.isin(old_of)].copy()
    sub["old_district"] = [old_of[i] for i in sub.index]
    return sub, unmatched


def draw_old_districts(gdf_assigned):
    gdf_town = gdf_assigned[["old_district", "geometry"]].dissolve(by="old_district")

    print("  舊區面積(km²)：")
    for name, row in gdf_town.iterrows():
        print(f"    {name}: {row.geometry.area / 1e6:.2f}")

    minx, miny, maxx, maxy = gdf_town.total_bounds
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}，請調大 METERS_PER_PIXEL")

    DPI = 100
    PX2PT = 72.0 / DPI
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = gdf_town.geometry.union_all()

    # ① 舊區填色（白色、無邊）
    gdf_town.plot(
        ax=ax, facecolor=FILL_HEX,
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 舊區界黑線（4px 黑帶）
    town_lines = gdf_town.boundary.union_all()
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

    # ③ 市外輪廓（6px 黑帶）
    outer = city_geom.boundary.buffer(
        outer_half_m, resolution=BUF_RES,
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
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def quantize_bw(img_rgb):
    """只允許純白與純黑兩色的最近鄰量化（白轉透明的安全保證）。"""
    allowed = np.array([[255.0, 255.0, 255.0], [0.0, 0.0, 0.0]], dtype=np.float32)
    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    out = np.empty_like(pixels, dtype=np.uint8)
    CHUNK = 500_000
    for start in range(0, pixels.shape[0], CHUNK):
        chunk = pixels[start:start + CHUNK]
        d0 = ((chunk - allowed[0]) ** 2).sum(axis=1)
        d1 = ((chunk - allowed[1]) ** 2).sum(axis=1)
        out[start:start + CHUNK] = np.where((d1 < d0)[:, None], allowed[1], allowed[0])
    return out.reshape(img_rgb.shape).astype(np.uint8)


def save_png(img, path, retry=6, wait=2.0):
    import time
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(retry):
        try:
            img.save(path, "PNG", optimize=True)
            return path
        except OSError:
            if attempt == retry - 1:
                base, ext = os.path.splitext(path)
                alt = base + "_鎖定重試" + ext
                img.save(alt, "PNG", optimize=True)
                print(f"  ⚠ 無法寫入（檔案可能正被開啟）：{os.path.basename(path)}")
                print(f"     已改存：{os.path.basename(alt)}")
                return alt
            time.sleep(wait)
    return path


def main():
    print("=" * 62)
    print("  1990 臺北市舊行政區界線圖（只有區界線，不畫里）")
    print("=" * 62)

    assigns = parse_md_assignments(MD_PATH)
    total = sum(len(v) for v in assigns.values())
    print(f"  ※ 對照表：{len(assigns)} 個舊區、{total} 個現行里")
    for name, pairs in assigns.items():
        print(f"    {name}: {len(pairs)} 里")

    gdf = load_taipei_villages()
    print(f"  ※ 圖資：現行 111 村里界（臺北市 {len(gdf)} 里）")

    gdf_assigned, unmatched = assign_old_districts(gdf, assigns)
    if unmatched:
        print("  ⚠ 對照表有、圖資無（未畫入）：")
        for old, town, vill in unmatched:
            print(f"      {old} ← {town}{vill}")
    print(f"  ※ 成功指派 {len(gdf_assigned)} 里 → 舊區多邊形")

    img_rgb = draw_old_districts(gdf_assigned)
    quantized = quantize_bw(img_rgb)
    map_img = Image.fromarray(quantized)

    saved = save_png(map_img, OUT_PNG)
    print(f"  輸出: {saved}  ({map_img.width}×{map_img.height}px)")
    print("全部完成。")


if __name__ == "__main__":
    main()
