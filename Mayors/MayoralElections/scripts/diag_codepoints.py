# -*- coding: utf-8 -*-
import geopandas as gpd
import pandas as pd

SHP = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
gdf = gpd.read_file(SHP, encoding="UTF-8")
gdf_nt = gdf[gdf["COUNTYNAME"].astype(str).str.contains("新北", na=False)]

def show(s):
    if pd.isna(s):
        return "<NaN>"
    return [f"{ch}(U+{ord(ch):04X})" for ch in str(s)]

targets = ["瓦", "灰", "石", "獇", "峰", "公", "崁", "峰"]
rows = []
import unicodedata
for _, r in gdf_nt.iterrows():
    v = str(r["VILLNAME"]) if not pd.isna(r["VILLNAME"]) else ""
    t = str(r["TOWNNAME"]) if not pd.isna(r["TOWNNAME"]) else ""
    # 找包含非常見字的里名（含對照表目標字或 Unihan 外部字）
    is_special = ("磘" in v or "窯" in v or "獇" in v or "羌" in v or
                  "𥕢" in v or any(ord(c) > 0x2FFFF for c in v) or
                  "曹" in v or "槽" in v)
    if is_special:
        rows.append(f"{t} | {v} | codepoints=" + " ".join(f"{ch}(U+{ord(ch):04X})" for ch in v))

open("special_chars.txt", "w", encoding="utf-8").write("\n".join(rows))
print("n=", len(rows))