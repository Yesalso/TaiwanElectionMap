# -*- coding: utf-8 -*-
"""全年度 × 全分區：逐鄉鎮市區取樣比對「應填色 vs 實際顏色」。
用來確認 maps/ 內是否存在任何「舊版邏輯留下的錯色圖」。"""
import os, sys, importlib.util, math, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("dm", os.path.join(HERE, "Draw_Region_Maps_AllYears.py"))
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)

shp = dm.load_shp()
summary = {}
for rg, counties in dm.REGIONS.items():
    rc = {dm.canon_county(c) for c in counties}
    g = shp[shp["county_canon"].isin(rc)].copy()
    g = g[g["TOWNNAME"].notna()].copy(); g["geometry"] = g.geometry.buffer(0)
    g = g[~g["TOWNNAME"].isin(["", "nan", "None"])].copy()
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy().reset_index(drop=True)
    vv = g["VILLNAME"].fillna("").astype(str).str.strip()
    g = g[~(g["COUNTYNAME"].isin(dm.DROP_NAN_COUNTIES) & vv.isin(["", "nan", "None"]))].copy().reset_index(drop=True)
    g = dm.strip_far_parts(g)
    g["county_core"] = g["COUNTYNAME"].apply(dm.canon_county)
    g["town_core"] = g["TOWNNAME"].apply(dm.strip_town_suffix)
    b = g.total_bounds
    minx, maxx = b[0] - dm.PAD_FRAC * (b[2] - b[0]), b[2] + dm.PAD_FRAC * (b[2] - b[0])
    miny, maxy = b[1] - dm.PAD_FRAC * (b[3] - b[1]), b[3] + dm.PAD_FRAC * (b[3] - b[1])
    gw, gh = maxx - minx, maxy - miny
    scale = max(gw / dm.MAX_PX, gh / dm.MAX_PX, dm.METERS_PER_PIXEL) / dm.SCALE_UP
    W = int(math.ceil(gw / scale)); H = int(math.ceil(gh / scale)); sx, sy = W / gw, H / gh
    towns = g.dissolve(by=["COUNTYNAME", "town_core"]).reset_index()
    for y, cfg in dm.YEAR_CONFIGS.items():
        p = os.path.join(HERE, "maps", str(y), f"{rg}{y}年總統副總統選舉_得票率地圖.png")
        if not os.path.exists(p):
            summary[(y, rg)] = ("缺檔", 0, 0); continue
        im = np.asarray(Image.open(p).convert("RGB")); hh, ww, _ = im.shape
        if (ww, hh) != (W, H):
            summary[(y, rg)] = (f"尺寸不符{ww}x{hh}", 0, 0); continue
        rates = dm.load_town_rates(y, cfg["candidates"])
        bad = miss = 0; det = []
        for _, r in towns.iterrows():
            rt = rates.get((r["county_core"], r["town_core"]))
            if not rt:
                miss += 1; continue
            name = max(rt, key=rt.get)
            gi = next(gg for cn, gg in cfg["candidates"] if cn == name)
            exp = tuple(int(round(v * 255)) for v in dm.hex2rgb(dm.get_color_by_value(rt[name], dm.RATE_COLOR_STOPS[gi])))
            pt = r.geometry.representative_point()
            px = min(max(int((pt.x - minx) * sx), 0), W - 1); py = min(max(int((maxy - pt.y) * sy), 0), H - 1)
            win = im[max(0, py - 3):py + 4, max(0, px - 3):px + 4].reshape(-1, 3)
            cols, cnts = np.unique(win, axis=0, return_counts=True); got = None
            for o in np.argsort(-cnts):
                c = tuple(int(v) for v in cols[o])
                if c != (0, 0, 0): got = c; break
            if got != exp:
                bad += 1
                det.append(f"{r['county_core']}/{r['town_core']} 應#{exp[0]:02X}{exp[1]:02X}{exp[2]:02X} "
                           f"實{('#'+''.join('%02X'%v for v in got)) if got else '無'} ({name} {rt[name]:.2f}%)")
        summary[(y, rg)] = ("", bad, len(towns) - miss)
        mark = "OK" if bad == 0 else "!!"
        print(f"{mark} {y} {rg}: 比對 {len(towns)-miss}/{len(towns)} 鄉鎮，不符 {bad}")
        for d in det[:15]:
            print("      ", d)

print("\n===== 總表 =====")
for y in dm.YEAR_CONFIGS:
    row = " ".join(f"{rg}:{'OK' if summary.get((y,rg),('',1,0))[1]==0 and not summary.get((y,rg),('',1,0))[0] else summary[(y,rg)]}"
                   for rg in dm.REGIONS)
    print(f"{y}  {row}")
