#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""legend_president.py —— 總統副總統選舉（北北基宜）圖例產生器。

仿 mayor 看板的圖例樣式（透明底 + 白字 + 色塊，how=copy 不再轉透明）：
  * 每位「在北北基宜至少領先一個鄉鎮市區」的候選人一欄：姓名 + 該候選人
    實際出現的色階檔位（色階取 Precident/color.txt 的政黨組）。
  * 檔位判定與地圖腳本一致：得票率 v -> 第一個 upper >= v 的 stop 色；
    標籤 35~40% / 40~45% ...（u=35 -> 「<35%」、u=100 -> 「>85%」）。
  * 資料：各屆 Precident/<year>Precident/data/*縣市鄉鎮村里.xlsx 的
    「鄉鎮市區級別」工作表（官方得票數），只取 北北基宜 四縣市。

輸出：assets/map/<year>/legend.png（透明 RGBA；build_assets 走 copy）

用法：
    "C:/Users/Windows/AppData/Local/Microsoft/WindowsApps/python.exe" tool/legend_president.py [年份 ...]
"""
import ast
import glob
import os
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../src/mapgen
VIDEO_ROOT = os.path.dirname(os.path.dirname(BASE))                   # .../Video
PRECIDENT = r"D:/Windows/TaiwanElection/Precident"
COLOR_TXT = os.path.join(PRECIDENT, "color.txt")
OUT_ROOT = os.path.join(VIDEO_ROOT, "assets", "map")

# 北北基宜四縣市（xlsx 裡的寫法：1996/2000 用「台北縣」）
REGION_COUNTIES = {"台北市", "台北縣", "新北市", "基隆市", "宜蘭縣"}

# 每屆候選人 -> color.txt 色階組 index（與 Draw_Region_Maps_AllYears.YEAR_CONFIGS 一致）
YEAR_CAND_GROUPS = {
    1996: [("陳履安", 0), ("李登輝", 1), ("彭明敏", 2), ("林洋港", 3)],
    2000: [("宋楚瑜", 0), ("連戰", 1), ("李敖", 3), ("許信良", 0), ("陳水扁", 2)],
    2004: [("陳水扁", 2), ("連戰", 1)],
    2008: [("馬英九", 1), ("謝長廷", 2)],
    2012: [("蔡英文", 2), ("馬英九", 1), ("宋楚瑜", 4)],
    2016: [("朱立倫", 1), ("蔡英文", 2), ("宋楚瑜", 4)],
    2020: [("宋楚瑜", 4), ("韓國瑜", 1), ("蔡英文", 2)],
    2024: [("柯文哲", 5), ("賴清德", 2), ("侯友宜", 1)],
}

FONT_BOLD = "C:/Windows/Fonts/msjhbd.ttc"
FONT = "C:/Windows/Fonts/msjh.ttc"

SWATCH_W, SWATCH_H = 120, 64
ROW_GAP = 20
NAME_SIZE = 58
LABEL_SIZE = 44
CELL_W = 560
NAME_H = 96
PAD = 30


def load_color_stops():
    with open(COLOR_TXT, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    rhs = "\n".join(lines).split("=", 1)[1]
    return ast.literal_eval(rhs)


def bin_of(val, stops):
    """得票率 -> (stop_upper, hex)，與地圖腳本 get_color_by_value 同一判準。"""
    for upper, hx in stops:
        if val <= upper:
            return upper, hx
    return stops[-1][0], stops[-1][1]


def bin_label(upper):
    if upper <= 35:
        return "<35%"
    if upper >= 100:
        return ">85%"
    return "%d~%d%%" % (upper - 5, upper)


def town_table(year):
    """回傳 df：縣市 / 鄉鎮 / 各候選人得票率（北北基宜限定）。"""
    paths = glob.glob(os.path.join(PRECIDENT, "%dPrecident" % year,
                                   "data", "*縣市鄉鎮村里*.xlsx"))
    if not paths:
        raise SystemExit("%d：找不到縣市鄉鎮村里 xlsx" % year)
    df = pd.read_excel(paths[0], sheet_name="鄉鎮市區級別")
    df = df[df["縣市"].str.replace("臺", "台", regex=False).isin(REGION_COUNTIES)].copy()
    return df


def legend_for(year, stops):
    cands = YEAR_CAND_GROUPS[year]
    df = town_table(year)

    columns = []          # (name, [(label, hex), ...])
    for name, gi in cands:
        rate_col = "%s_得票率" % name
        if rate_col not in df.columns:
            # 欄位帶號（陳履安（01）_得票率），用前綴比對
            pref = [c for c in df.columns
                    if c.startswith(name) and c.endswith("_得票率")]
            rate_col = pref[0]
        sub = df[["縣市", rate_col]].dropna()
        # 領先鄉鎮：該候選人得票率為該鄉鎮最大者
        rate_cols = []
        for n, _ in cands:
            pref = [c for c in df.columns
                    if c.startswith(n) and c.endswith("_得票率")]
            if pref:
                rate_cols.append((n, pref[0]))
        winners = df[[c for _, c in rate_cols]].idxmax(axis=1)
        lead_mask = winners == rate_col
        if not lead_mask.any():
            continue
        bins = {}
        for v in df.loc[lead_mask, rate_col].dropna():
            s = str(v).replace("%", "").strip()
            u, hx = bin_of(float(s), stops[gi])
            bins[u] = hx
        rows = [(bin_label(u), bins[u]) for u in sorted(bins)]
        columns.append((name, rows))

    if not columns:
        raise SystemExit("%d：北北基宜無任何領先鄉鎮？" % year)

    # 版面：單欄直排（看板右欄是高瘦框，contain 後文字最大）
    f_name = ImageFont.truetype(FONT_BOLD, NAME_SIZE)
    f_label = ImageFont.truetype(FONT, LABEL_SIZE)

    def cell_h(rows):
        return NAME_H + len(rows) * (SWATCH_H + ROW_GAP)

    W = PAD + CELL_W
    H = PAD + sum(cell_h(r) for _, r in columns) + PAD * (len(columns) - 1)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    y = PAD
    for name, rows in columns:
        dr.text((PAD, y), name, font=f_name, fill=(255, 255, 255, 255))
        ry = y + NAME_H
        for label, hx in rows:
            rgb = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
            dr.rectangle([PAD + 4, ry, PAD + 4 + SWATCH_W, ry + SWATCH_H],
                         fill=rgb + (255,))
            dr.text((PAD + 4 + SWATCH_W + 30,
                     ry + (SWATCH_H - LABEL_SIZE * 1.1) / 2),
                    label, font=f_label, fill=(255, 255, 255, 255))
            ry += SWATCH_H + ROW_GAP
        y += cell_h(rows) + PAD

    out = os.path.join(OUT_ROOT, str(year), "legend.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print("%d legend.png  %dx%d  %d 欄（%s）" %
          (year, W, H, len(columns), "、".join(n for n, _ in columns)))


def main():
    stops = load_color_stops()
    years = [int(a) for a in sys.argv[1:]] or sorted(YEAR_CAND_GROUPS)
    for y in years:
        legend_for(y, stops)


if __name__ == "__main__":
    main()
