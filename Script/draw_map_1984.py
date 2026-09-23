# -*- coding: utf-8 -*-
"""將 1984 年鄉鎮市界圖畫成 PNG 圖片。

資料來源: JSON/twtown1984.json (GeoJSON FeatureCollection, 經緯度座標)
用法:
    python draw_map_1984.py [JSON檔案路徑] [輸出PNG路徑]

預設輸出: JSON/1984_town_map.png
"""
import json
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
DEFAULT_JSON = BASE + r"\twtown1984.json"
DEFAULT_PNG = BASE + r"\1984_town_map.png"


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


def poly_to_xy(poly_rings):
    x, y = [], []
    for ring in poly_rings:
        x += [pt[0] for pt in ring]
        y += [pt[1] for pt in ring]
    return x, y


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PNG
    print(f"讀取 {src} ...")
    features = load_features(src)
    print(f"共 {len(features)} 個鄉鎮市區")

    fig, ax = plt.subplots(figsize=(12, 16), dpi=150)
    ax.set_aspect("equal")
    ax.set_facecolor("#cfe8f7")

    for f in features:
        props = f.get("properties", {})
        for poly in iter_polygons(f):
            x, y = poly_to_xy(poly)
            ax.fill(x, y, facecolor="#f7f4e9", edgecolor="#555555", linewidth=0.4)

    data_time = features[0]["properties"].get("data_time", "") if features else ""
    ax.set_title("1984 年鄉鎮市區界", fontsize=16)
    ax.set_xlabel("經度 (lon)")
    ax.set_ylabel("緯度 (lat)")
    ax.autoscale_view()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"已輸出 {out}")


if __name__ == "__main__":
    main()