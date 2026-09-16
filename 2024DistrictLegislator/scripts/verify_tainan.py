# -*- coding: utf-8 -*-
"""驗證：取每個村里 interior point，對照 PNG 像素顏色與預期勝出者色階是否一致。"""
import os, re, unicodedata
import warnings
warnings.filterwarnings("ignore")
import geopandas as gpd
import pandas as pd
import numpy as np
from PIL import Image

BASE = r"D:\Windows\TaiwanElection\2024DistrictLegislator\data"
MAPS = os.path.join(os.path.dirname(BASE), "maps")
SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
CITY = "臺南市"

VARIANT_MAP = str.maketrans({
    '濓': '濂', '𥕢': '曹', '𦰡': '那', '檨': '檨', '\ue006': '塭',})

def norm(s):
    if pd.isna(s): return ""
    s = unicodedata.normalize('NFKC', str(s).strip())
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    return s.replace("[", "").replace("]", "").translate(VARIANT_MAP)

def st(s):  return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", norm(s))
def sv(s):  return "" if pd.isna(s) else re.sub(r"[村里]$", "", norm(s))

def rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

# 候選人
df = pd.read_excel(os.path.join(BASE, "臺南市_得票率.xlsx"), sheet_name="各里彙總")
df.columns = [str(c) for c in df.columns]
rate_cols = [c for c in df.columns if c.endswith("得票率")]
meta = []
for c in rate_cols:
    m = re.match(r"^(.*)\(([^()]*)\)得票率$", c)
    meta.append((m.group(1), m.group(2), c))
winners = set()
for _, r in df.iterrows():
    v = {c: r[c] for c in rate_cols if pd.notna(r[c])}
    if v: winners.add(max(v, key=v.get))
sel = [(n,p,c) for n,p,c in meta if c in winners]
names = [n for n,_,_ in sel]
parties = [p for _,p,_ in sel]
cols = [c for _,_,c in sel]
names_full = [f"{n}({p})" for n,p,_ in sel]

gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
if gdf_all.crs is None: gdf_all.crs = "EPSG:4326"
if gdf_all.crs.is_geographic: gdf_all = gdf_all.to_crs(epsg=3826)
g = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(CITY, na=False)].copy()
g["tc"] = g["TOWNNAME"].apply(st)
g["vc"] = g["VILLNAME"].apply(sv)

vote = {(r["鄉(鎮、市、區)別"] and st(r["鄉(鎮、市、區)別"]), sv(r["村里別"])): tuple(r[c] for c in cols)
        for _, r in df.iterrows()}

sopA = {
 "中國國民黨": [(10,"#00FFFF"),(20,"#00F2FF"),(30,"#00E6FF"),(40,"#00DAFF"),(50,"#00C0F4"),(60,"#00A2E8"),(70,"#0080B8"),(80,"#006591"),(90,"#004B6B"),(100,"#003247")],
 "民主進步黨": [(10,"#E2FFE0"),(20,"#D2FFC9"),(30,"#C0FFB1"),(40,"#A4FF90"),(50,"#78FF4F"),(60,"#68DE45"),(70,"#54B337"),(80,"#3C8027"),(90,"#2B5C1C"),(100,"#1D3D13")],
 "無": [(45,"#F0F0F0"),(50,"#E0E0E0"),(55,"#D0D0D0"),(60,"#C0C0C0"),(65,"#B1B1B1"),(70,"#A1A1A1"),(75,"#929292"),(80,"#737373"),(85,"#646464")]}
sopB = {
 "中國國民黨": [(35,"#D9F6FF"),(40,"#A6E9FF"),(45,"#73D9FF"),(50,"#40C8FF"),(55,"#00C0F4"),(60,"#00A2E8"),(65,"#0080B8"),(70,"#006591"),(75,"#004B6B"),(80,"#003247"),(85,"#001F2E"),(100,"#010D29")],
 "民主進步黨": [(35,"#E8FFE0"),(40,"#CEFFC2"),(45,"#C0FFB1"),(50,"#A4FF90"),(55,"#78FF4F"),(60,"#68DE45"),(65,"#54B337"),(70,"#3C8027"),(75,"#2B5C1C"),(80,"#1D3D13"),(85,"#0F210A"),(100,"#071A09")],
 "無": [(10,"#F0F0F0"),(20,"#E0E0E0"),(30,"#D0D0D0"),(40,"#C0C0C0"),(50,"#B1B1B1"),(60,"#A1A1A1"),(70,"#929292"),(80,"#737373"),(90,"#646464"),(100,"#555555")]}
GRAY="#CCCCCC"

def color_for(val, stops, gray=GRAY):
    if val is None or np.isnan(val): return gray
    if val < 0: return gray
    for up,h in stops:
        if val <= up: return h
    return stops[-1][1]

MPP = {"A":20,"B":10}
outs = {
 "A": os.path.join(MAPS,"臺南市第十一屆立法委員_得票率地圖_A版.png"),
 "B": os.path.join(MAPS,"臺南市第十一屆立法委員_得票率地圖_B版.png")}

for mode, path in outs.items():
    img = Image.open(path).convert("RGB")
    W,H = img.size
    mpp = MPP[mode]
    padded_bounds = g.total_bounds
    minx,miny,maxx,maxy = padded_bounds
    padx=(maxx-minx)*0.03; pady=(maxy-miny)*0.03
    x0,y0 = minx-padx, maxy+pady
    sop = sopA if mode=="A" else sopB
    ok=0; tot=0; bad=[]
    for _, row in g.iterrows():
        key=(row["tc"],row["vc"])
        vals = vote.get(key)
        if vals is None:
            continue
        arr = [v if not np.isnan(v) else 0.0 for v in vals]
        i = int(np.argmax(arr))
        exp = color_for(vals[i], sop[parties[i]])
        pt = row.geometry.representative_point()
        px = int((pt.x - x0)/mpp); py = int((y0 - pt.y)/mpp)
        if px<0 or py<0 or px>=W or py>=H:
            bad.append((mode,row["TOWNNAME"],row["VILLNAME"],"out-of-bounds")); continue
        got = img.getpixel((px,py))
        if got == rgb(exp):
            ok += 1
        else:
            pt2 = row.geometry.centroid
            px2 = int((pt2.x - x0)/mpp); py2 = int((y0 - pt2.y)/mpp)
            got2 = img.getpixel((px2,py2)) if (0<=px2<W and 0<=py2<H) else None
            if got2 == rgb(exp):
                ok += 1
            else:
                bad.append((mode,row["TOWNNAME"],row["VILLNAME"],f"exp{rgb(exp)} got{got} cent{got2}"))
        tot += 1
    print(f"[{mode}] {W}x{H}  sampled {tot}  match {ok}  ({ok/tot*100:.2f}%)  mismatch {len(bad)}")
    for b in bad[:8]: print("   ", b)