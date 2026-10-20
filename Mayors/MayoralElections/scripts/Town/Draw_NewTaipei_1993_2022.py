# -*- coding: utf-8 -*-
"""
新北市（原臺北縣）歷屆首長選舉 1993–2022 各鄉鎮市區得票率地圖 批次產生器。

資料來源：data/新北市歷屆首長選舉_各鄉鎮市區得票數得票率_1993-2022.xlsx
    （由 scripts/Town/Compute_TownVotes_1993_2022.py 產生；每年度一個工作表）
    取各鄉鎮市區「領先者」及其「得票率」，以 Color2.txt 政黨色階填色。

畫法與配色沿用 scripts/Town/Draw_TaipeiCounty_AllYears.py：
    鄉鎮市區填色、不繪村里界；鄉鎮界 3px、縣界/海岸線 5px；洪水填充；純地圖（無標題、
    無圖例）。此 8 個年度皆為改制後之 29 個鄉鎮市區（臺北縣→新北市），故底圖直接對應
    今新北市 29 區。

政黨色組（Color2.txt 索引）：
    0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃)
    廖學廣(1997 汐止)＝無黨籍；王建煊(2001)＝新黨；周錫瑋(2005)＝中國國民黨、
    羅文嘉(2005)＝民主進步黨（依使用者指示）。

輸出：maps/新北市歷屆/新北市{年}年首長選舉_各鄉鎮市區得票率地圖.png

執行：
    py Draw_NewTaipei_1993_2022.py            # 全部年度
    py Draw_NewTaipei_1993_2022.py 2014       # 只做指定年份
"""
import os
import sys
import math
import time
import warnings

import numpy as np
import pandas as pd
from PIL import Image
from affine import Affine

# 重用既有繪圖模組（同目錄）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Draw_TaipeiCounty_AllYears as B     # noqa: E402

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC_XLSX = os.path.join(ROOT, "data",
                        "新北市歷屆首長選舉_各鄉鎮市區得票數得票率_1993-2022.xlsx")
OUT_DIR = os.path.join(ROOT, "maps", "新北市歷屆")

# 候選人 → Color2.txt 色組索引
PARTY_GROUP_OF = {
    "尤清": 2, "蘇貞昌": 2, "蔡英文": 2, "游錫堃": 2, "林佳龍": 2,      # 民主進步黨(綠)
    "羅文嘉": 2,
    "蔡勝邦": 1, "謝深山": 1, "朱立倫": 1, "侯友宜": 1,                  # 中國國民黨(藍)
    "周錫瑋": 1,
    "王建煊": 3, "李勝峰": 3, "周荃": 3, "楊泰順": 3,                    # 新黨(黃)
    "廖學廣": 0, "石瓊文": 0, "張馥堂": 0, "林志嘉": 0,                  # 無黨籍(灰)
    "黃福卿": 0, "陳誠鈞": 0, "陳俊傑": 0, "黃茂全": 0,
}
DEFAULT_GROUP = 0


def render_map(rec, out_png):
    minx, miny, maxx, maxy = rec.total_bounds
    pad_x, pad_y = B.PAD_FRAC * (maxx - minx), B.PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny
    scale = max(geo_w_m / B.MAX_PX, geo_h_m / B.MAX_PX, B.METERS_PER_PIXEL) / B.SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m

    lines_mask = B.render_line_layer(rec, w_px, h_px, minx, maxx, miny, maxy,
                                     B.LINE_TOWNSHIP_PX, B.LINE_OUTER_PX, B.DPI, B.THRESHOLD_VAL)
    arr, _ncomp, _comp = B.flood_fill_layer(rec, lines_mask, w_px, h_px, minx, maxy, sx, sy)
    arr[lines_mask] = 0

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    img = Image.fromarray(arr, mode="RGB")
    for attempt in range(8):                 # 新檔有時被即時掃描/索引短暫鎖住，重試
        try:
            img.save(out_png)
            break
        except OSError:
            if attempt == 7:
                raise
            time.sleep(0.4 * (attempt + 1))
    return w_px, h_px


def build_year(df, shp):
    towns = {}
    for _, r in df.iterrows():
        town = B.strip_town_suffix(r["鄉鎮市區"])
        winner = B.normalize_text(r["領先者"])
        col = f"{winner}得票率"
        rate = float(r[col]) if col in df.columns and pd.notna(r[col]) else 50.0
        towns[town] = (winner, rate)

    base = B.build_base(shp, 2020)          # 29 新北市區
    def pick(row):
        tc = row["TOWNNAME"]
        if tc not in towns:
            return B.NO_DATA_COLOR
        winner, rate = towns[tc]
        grp = PARTY_GROUP_OF.get(winner, DEFAULT_GROUP)
        c = B.color_for(grp, rate)
        return c if c is not None else B.NO_DATA_COLOR
    base["fill_hex"] = base.apply(pick, axis=1)

    blank = sorted(set(base["TOWNNAME"]) - set(towns))
    extra = sorted(set(towns) - set(base["TOWNNAME"]))
    rec = base[["COUNTYNAME", "TOWNNAME", "geometry", "fill_hex"]].copy().reset_index(drop=True)
    return rec, blank, extra, towns


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    want = {int(a) for a in args if a.isdigit()} if args else None

    print("=" * 68)
    print("  新北市（原臺北縣）歷屆首長選舉 各鄉鎮市區得票率地圖  1993–2022")
    print("=" * 68)
    if not os.path.exists(SRC_XLSX):
        raise FileNotFoundError("找不到 " + SRC_XLSX)

    t0 = time.time()
    shp = B.load_shp()
    xl = pd.ExcelFile(SRC_XLSX)

    for sheet in xl.sheet_names:
        year = int(sheet)
        if want is not None and year not in want:
            continue
        df = xl.parse(sheet)
        rec, blank, extra, towns = build_year(df, shp)

        wc = {}
        for _t, (w, _r) in towns.items():
            wc[w] = wc.get(w, 0) + 1
        out_png = os.path.join(OUT_DIR, f"新北市{year}年首長選舉_各鄉鎮市區得票率地圖.png")
        w_px, h_px = render_map(rec, out_png)
        print(f"  {year}｜{len(rec)} 區｜領先 " +
              "、".join(f"{k}×{v}" for k, v in sorted(wc.items(), key=lambda x: -x[1])) +
              f"｜{w_px}x{h_px}px")
        if blank:
            print(f"      無資料/留白：{'、'.join(blank)}")
        if extra:
            print(f"      資料無對應底圖：{'、'.join(extra)}")
        print(f"      Saved: {out_png}")

    print("-" * 68)
    print(f"  完成，耗時 {time.time() - t0:.1f} 秒｜輸出目錄 {OUT_DIR}")


if __name__ == "__main__":
    main()
