# -*- coding: utf-8 -*-
"""將 2012 年村里界圖（資料時間 101.10.30）畫成 PNG 圖片。

資料來源: JSON/twvillage2012.json (GeoJSON FeatureCollection, 座標為 TWD97 公尺)
座標轉換: 參考 JSON/twd97tolatlng.php (TWD97 -> 經緯度 WGS84)
用法:
    python draw_village_2012.py [JSON檔案路徑] [輸出PNG路徑]

預設輸出: JSON/2012_village_map.png
"""
import json
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

_available = {f.name for f in font_manager.fontManager.ttflist}
for name in ("Microsoft JhengHei", "Microsoft YaHei", "SimHei"):
    if name in _available:
        plt.rcParams["font.sans-serif"] = [name]
        break
plt.rcParams["axes.unicode_minus"] = False

BASE = r"D:\Windows\Documents\村里界歷史圖資_111\JSON"
DEFAULT_JSON = BASE + r"\twvillage2012.json"
DEFAULT_PNG = BASE + r"\2012_village_map.png"


def twd97_to_latlng(x, y):
    a = 6378137.0
    b = 6356752.314245
    lng0 = 121 * math.pi / 180
    k0 = 0.9999
    dx = 250000.0
    dy = 0.0
    e = math.sqrt(1 - b * b / (a * a))

    x -= dx
    y -= dy
    M = y / k0
    mu = M / (a * (1.0 - e * e / 4.0 - 3 * e**4 / 64.0 - 5 * e**6 / 256.0))
    e1 = (1.0 - math.sqrt(1.0 - e * e)) / (1.0 + math.sqrt(1.0 - e * e))

    J1 = 3 * e1 / 2 - 27 * e1**3 / 32.0
    J2 = 21 * e1**2 / 16 - 55 * e1**4 / 32.0
    J3 = 151 * e1**3 / 96.0
    J4 = 1097 * e1**4 / 512.0

    fp = mu + J1 * math.sin(2 * mu) + J2 * math.sin(4 * mu) + J3 * math.sin(6 * mu) + J4 * math.sin(8 * mu)

    e2 = (e * a / b) ** 2
    C1 = e2 * math.cos(fp) ** 2
    T1 = math.tan(fp) ** 2
    R1 = a * (1 - e * e) / (1 - e * e * math.sin(fp) ** 2) ** (3.0 / 2.0)
    N1 = a / math.sqrt(1 - e * e * math.sin(fp) ** 2)

    D = x / (N1 * k0)

    Q1 = N1 * math.tan(fp) / R1
    Q2 = D * D / 2.0
    Q3 = (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * e2) * D**4 / 24.0
    Q4 = (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 3 * C1**2 - 252 * e2) * D**6 / 720.0
    lat = fp - Q1 * (Q2 - Q3 + Q4)

    Q5 = D
    Q6 = (1 + 2 * T1 + C1) * D**3 / 6
    Q7 = (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * e2 + 24 * T1**2) * D**5 / 120.0
    lng = lng0 + (Q5 - Q6 + Q7) / math.cos(fp)

    return [lng * 180 / math.pi, lat * 180 / math.pi]


def load_features(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def iter_polygons(feature):
    geom = feature["geometry"]
    if geom is None:
        return
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        yield coords
    elif gtype == "MultiPolygon":
        for poly in coords:
            yield poly


def poly_to_xy(poly_rings, project):
    for ring in poly_rings:
        if project:
            pts = [twd97_to_latlng(p[0], p[1]) for p in ring]
        else:
            pts = ring
        yield [p[0] for p in pts], [p[1] for p in pts]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PNG
    print(f"讀取 {src} ...")
    features = load_features(src)
    print(f"共 {len(features)} 個村里")

    fig, ax = plt.subplots(figsize=(12, 16), dpi=150)
    ax.set_aspect("equal")
    ax.set_facecolor("#cfe8f7")

    for f in features:
        for poly in iter_polygons(f):
            for x, y in poly_to_xy(poly, True):
                ax.fill(x, y, facecolor="#f7f4e9", edgecolor="#888888", linewidth=0.2)

    ax.set_title("2012 年村里界", fontsize=16)
    ax.set_xlabel("經度 (lon)")
    ax.set_ylabel("緯度 (lat)")
    ax.autoscale_view()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"已輸出 {out}")


if __name__ == "__main__":
    main()