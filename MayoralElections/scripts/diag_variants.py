# -*- coding: utf-8 -*-
# 诊断：找出 SHP 里没匹配到 Excel 的村里，分析是否为异体字/字因问题
import geopandas as gpd
import pandas as pd
import re
import unicodedata
from difflib import SequenceMatcher

SHP = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"

VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '𥕢': '曹',
})

def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.translate(VARIANT_CHAR_MAP)
    return s

def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))

def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))

gdf_all = gpd.read_file(SHP, encoding="UTF-8")
gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains("新北", na=False)].copy()
gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

out = []
for y in ["2010", "2014"]:
    df = pd.read_excel(f"{y}新北.xlsx", header=None, sheet_name="Sheet1")
    d = pd.DataFrame({
        "town_core": df[0].str[3:].str.split("區", n=1, expand=True)[0] + "區",
        "vill_core": df[0].str[3:].str.split("區", n=1, expand=True)[1],
    })
    d["town_core"] = d["town_core"].apply(strip_town_suffix)
    d["vill_core"] = d["vill_core"].apply(strip_village_suffix)
    excel_keys = set(zip(d["town_core"], d["vill_core"]))

    out.append(f"===== {y} =====")
    unmatched = []
    for _, r in gdf_nt.iterrows():
        k = (r["town_core"], r["vill_core"])
        if k not in excel_keys:
            unmatched.append((r["TOWNNAME"], r["VILLNAME"], r["town_core"], r["vill_core"]))
    out.append(f"SHP 總數 {len(gdf_nt)}, 未匹配 {len(unmatched)}")
    for t, v, tc, vc in unmatched:
        # 找出 Excel 同區內最相似候選
        cands = [(tt, vv) for (tt, vv) in excel_keys if tt == tc]
        best, br = None, 0.0
        for (tt, vv) in cands:
            r = SequenceMatcher(None, vc, vv).ratio()
            if r > br:
                br, best = r, vv
        note = f"  → 最相近 '{best}' (ratio={br:.3f})" if best else "  (同區無候選)"
        out.append(f"  {t} {v}  [{tc}|{vc}]{note}")
    out.append("")

    # Excel 有但 SHP 沒有的（反方向）
    shp_keys = set(zip(gdf_nt["town_core"], gdf_nt["vill_core"]))
    missing_shp = [k for k in excel_keys if k not in shp_keys]
    out.append(f"  Excel 有但 SHP 沒有: {len(missing_shp)}")
    for k in missing_shp[:40]:
        out.append("    " + repr(k))
    out.append("")

open("diag.txt", "w", encoding="utf-8").write("\n".join(out))
print("done")