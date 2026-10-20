# -*- coding: utf-8 -*-
"""
臺北縣歷屆縣長選舉（1951–1993，第 1–12 屆）各鄉鎮市區得票率地圖 批次產生器

畫法參照同目錄 Draw_Region_Maps_AllYears.py：
  * 鄉鎮市區級填色、**不繪村里界**；鄉鎮界 3px、縣界/海岸線 5px（MATPLOTLIB 繪線→二值化→純黑線層）
  * 洪水填充（油漆桶）：黑線為封閉堤壩，每塊鄉鎮市區整塊填單色
  * **純地圖**：不畫標題、不畫圖例
配色：同目錄 Color2.txt（第 1 組無黨籍灰／第 2 組中國國民黨藍／第 3 組民主進步黨綠／第 4 組新黨黃…）

底圖：內政部 111 年村里界 SHP（VILLAGE_MOI_1111118.shp）
歷史鄉鎮還原：
  * 今新北市 29 區 ＝ 當時 29 鄉鎮市（名稱去尾綴後直接對應）。
  * 1968 年（第 6 屆）以前，臺北縣尚轄今屬臺北市之六鄉鎮市：
      士林區→士林、北投區→北投、內湖區→內湖、南港區→南港；
      文山區依「里」分拆：景美 23 里→景美鄉鎮，其餘→木柵。
  * 第 1–3 屆尚無永和鎮（1958 年始自中和鄉分設），故該三屆將永和併入中和。

資料：data/臺北縣歷屆縣長選舉_各鄉鎮市區得票數.md（鄉鎮市區級候選人「得票數（得票率）」）
候選人政黨直接讀取 md 各屆表頭「姓名（政黨）」欄；第一屆原書未附黨籍，依史料補：
  梅達夫＝中國國民黨（藍）、廖富本＝無黨籍（灰）；中國復興黨（第 11 屆卓定俊）視為無黨籍。
第 7 屆原書僅列人口/票數、未列各候選人鄉鎮得票；依正文「邵恩新於樹林、鶯歌以外均領先」，
  將全縣得票率 68.72% 套用於其餘 27 鄉鎮市（藍），樹林、鶯歌記為無黨籍領先（灰，無從得知得票率，
  以 50% 中性灰代）。

輸出：maps/臺北縣歷屆/臺北縣{年}年縣長選舉_各鄉鎮市得票率地圖.png

執行：
    py Draw_TaipeiCounty_AllYears.py            # 全部屆次
    py Draw_TaipeiCounty_AllYears.py 1960       # 只做指定年份
"""
import os
import re
import sys
import ast
import math
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from affine import Affine
from rasterio.features import rasterize

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")
try:                                     # 避免主控台字碼頁無法編碼 emoji／特殊字而中斷
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===================== 路徑 =====================
HERE = os.path.dirname(os.path.abspath(__file__))                 # ...\scripts\Town
ROOT = os.path.dirname(os.path.dirname(HERE))                     # ...\MayoralElections
MD_PATH = os.path.join(ROOT, "data", "臺北縣歷屆縣長選舉_各鄉鎮市區得票數.md")
COLOR_TXT = os.path.join(HERE, "Color2.txt")
OUT_DIR = os.path.join(ROOT, "maps", "臺北縣歷屆")

SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
SHP_ENCODING = "UTF-8"
TARGET_CRS = "EPSG:3826"

# ===================== 繪圖參數（沿用 Draw_Region_Maps_AllYears.py）=====================
METERS_PER_PIXEL = 20.0
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.01

LINE_TOWNSHIP_PX = 3
LINE_OUTER_PX = 5
THRESHOLD_VAL = 40

NO_DATA_COLOR = "#FFFFFF"
DPI = 100

# ===================== 文字正規化 =====================
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂', '曹': '槽', '磘': '窯', '獇': '羌',
    '舘': '館', '廍': '部', '峯': '峰', '脚': '腳',
    '裡': '里',
})


def normalize_text(s):
    import unicodedata
    if s is None or (isinstance(s, float) and np.isnan(s)) or pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.replace("[", "").replace("]", "").replace("*", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s


def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))


def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))


# ===================== 讀 Color2.txt =====================
def load_color_stops(path):
    """Color2.txt 檔頭有一個完整的 6 組色階指派（其後重複定義可忽略），
    取『第一個 RATE_COLOR_STOPS =』之後、以括號配對切出的第一個清單。"""
    text = open(path, "r", encoding="utf-8").read()
    i = text.index("RATE_COLOR_STOPS")
    j = text.index("[", i)
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "[":
            depth += 1
        elif text[k] == "]":
            depth -= 1
            if depth == 0:
                return ast.literal_eval(text[j:k + 1])
    raise ValueError("Color2.txt 無法解析")


RATE_COLOR_STOPS = load_color_stops(COLOR_TXT)
# 0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃) / 4 宋楚瑜(橘) / 5 台灣民眾黨(青)


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))) or val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


# ===================== 政黨 → 色組 =====================
# 政黨名稱取自 md 各屆候選人欄「姓名（政黨）」；對應 Color2.txt 色組索引：
#   0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃)
PARTY_NAME_GROUP = {
    "無黨籍": 0,
    "中國復興黨": 0,          # Color2.txt 未收，依使用者指示視為無黨籍（灰）
    "中國國民黨": 1,
    "民主進步黨": 2,
    "新黨": 3,
}
# 原書第一屆未附候選人黨籍（欄位無「（）」）；依史料補：梅達夫＝中國國民黨、廖富本＝無黨籍。
PARTY_FALLBACK = {"梅達夫": 1, "廖富本": 0}
DEFAULT_GROUP = 0            # 未知一律視為無黨籍（灰）

CAND_HDR_RE = re.compile(r'^(.*?)\s*（\s*([^（）]*?)\s*）\s*$')


def split_candidate_header(header):
    """'戴德發（中國國民黨）' → ('戴德發', 1)；無「（）」者用 PARTY_FALLBACK。"""
    m = CAND_HDR_RE.match(header.strip())
    if m:
        name = m.group(1).strip()
        return name, PARTY_NAME_GROUP.get(m.group(2).strip(), DEFAULT_GROUP)
    name = header.strip()
    return name, PARTY_FALLBACK.get(name, DEFAULT_GROUP)


def color_for(group, rate):
    return get_color_by_value(rate, RATE_COLOR_STOPS[group])


# ===================== 解析 Markdown 得票表 =====================
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
HDR_RE = re.compile(r'^##\s*第(\S+?)屆（民國(\d+)年，(\d{4})）')
CAND_RE = re.compile(r'^([\d,]+)\s*[※\*]?\s*（\s*([\d.]+)\s*%\s*）$')


def _split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_table(table):
    rows = [_split_row(ln) for ln in table if ln.strip().startswith("|")]
    if len(rows) < 3:
        return None
    header = rows[0]
    sep = next((k for k, r in enumerate(rows) if any("---" in c for c in r)), 1)
    data = rows[sep + 1:]
    # 候選人欄：以第一列資料列的「得票數（得票率）」樣式判定
    cand_cols = []
    for ci in range(1, len(header)):
        first = data[0][ci] if data and ci < len(data[0]) else ""
        if CAND_RE.match(first.replace("*", "")):
            cand_cols.append((ci, *split_candidate_header(header[ci])))
    towns = {}
    for r in data:
        if not r:
            continue
        town = strip_town_suffix(r[0])
        if not town or ("總計" in r[0]) or ("合计" in r[0]):
            continue
        best = None
        for ci, cname, group in cand_cols:
            if ci >= len(r):
                continue
            m = CAND_RE.match(r[ci].replace("*", ""))
            if not m:
                continue
            rate = float(m.group(2))
            if best is None or rate > best[2]:
                best = (cname, group, rate)
        if best is not None:
            towns[town] = best
    return {"candidates": [c for _, c, _ in cand_cols], "towns": towns}


def parse_md(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    elections = {}
    i = 0
    while i < len(lines):
        m = HDR_RE.match(lines[i])
        if not m:
            i += 1
            continue
        no = CN_NUM.get(m.group(1))
        year = int(m.group(3))
        i += 1
        while i < len(lines) and not lines[i].strip():     # 略過標題後的空行
            i += 1
        tbl = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            tbl.append(lines[i])
            i += 1
        parsed = _parse_table(tbl) if tbl else None
        if no is not None:
            elections[no] = {"no": no, "year": year, "parsed": parsed}
    return elections


# ===================== 讀 SHP =====================
def load_shp():
    g = gpd.read_file(SHP_PATH, encoding=SHP_ENCODING)
    if g.crs is None:
        g.crs = "EPSG:4326"
    g = g.to_crs(TARGET_CRS)
    g = g[g["COUNTYNAME"].notna()].copy()
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g["COUNTYNAME"] = g["COUNTYNAME"].astype(str).str.strip()
    g["TOWNNAME"] = g["TOWNNAME"].astype(str).str.strip()
    g["VILLNAME"] = g["VILLNAME"].astype(str)
    g["county_canon"] = g["COUNTYNAME"].str.replace("臺", "台", regex=False)
    g = g[g["county_canon"].isin(["新北市", "台北市"])].copy().reset_index(drop=True)
    return g


# ===================== 歷史鄉鎮市區底圖 =====================
# 景美鄉鎮（1950–1968）＝今文山區下列 23 里；文山區其餘 20 里＝木柵鄉。
JINGMEI_VILLAGES = {
    "萬年", "萬和", "萬盛", "萬祥", "萬有", "萬隆",
    "景仁", "景慶", "景美", "景華", "景東", "景行",
    "興福", "興安", "興豐", "興邦", "興得", "興昌",
    "興光", "興家", "興旺", "興業", "興泰",
}
TAIPEI_1TO1 = {"士林", "北投", "內湖", "南港"}


def build_base(shp, year):
    """依該屆年分組出當時臺北縣之鄉鎮市區輪廓。"""
    use_tpe = year < 1968          # 第 6 屆(1968.7.1 六鄉鎮改隸臺北市)起不再含今臺北市六區
    towns, geoms = [], []
    for _, r in shp.iterrows():
        cc = r["county_canon"]
        core = strip_town_suffix(r["TOWNNAME"])
        if cc == "新北市":
            town = core
        elif cc == "台北市":
            if not use_tpe:
                continue
            if core in TAIPEI_1TO1:
                town = core
            elif core == "文山":
                vill = strip_village_suffix(r["VILLNAME"])
                town = "景美" if vill in JINGMEI_VILLAGES else "木柵"
            else:
                continue
        else:
            continue
        if year <= 1957 and town == "永和":     # 1958 年前永和屬中和鄉
            town = "中和"
        towns.append(town)
        geoms.append(r["geometry"])
    g = gpd.GeoDataFrame({"TOWNNAME": towns}, geometry=geoms, crs=shp.crs)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.buffer(0)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g = g.dissolve(by="TOWNNAME").reset_index()
    g["COUNTYNAME"] = "臺北縣"
    return g


# ===================== 渲染（洪水填充，沿用 Draw_Region_Maps_AllYears.py）=====================
def render_line_layer(gdf, w_px, h_px, minx, maxx, miny, maxy,
                      town_px, outer_px, dpi, threshold):
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    px2pt = 72.0 / dpi
    town_lw = town_px * px2pt
    outer_lw = outer_px * px2pt
    gdf.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=town_lw)
    gdf.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=town_lw)
    for _cname, sub in gdf.groupby("COUNTYNAME"):
        cbd = unary_union(sub.geometry).boundary
        gpd.GeoSeries([cbd]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    outer = unary_union(gdf.geometry).boundary
    gpd.GeoSeries([outer]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, pad_inches=0, bbox_inches=None, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, tmask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    del gray
    return tmask > 0


def flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy):
    lut = np.vstack([
        np.array([[255, 255, 255]], dtype=np.uint8),
        np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                  for hx in records["fill_hex"]], dtype=np.uint8),
    ])
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)
    free = ~lines_mask
    ncomp, comp = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    seed = np.zeros(ncomp, dtype=np.int32)
    seed[comp.ravel()] = ids.ravel()
    reps = seed[comp]
    agree = (ids == reps)
    cnt_all = np.bincount(comp.ravel(), minlength=ncomp)
    cnt_ok = np.bincount(comp.ravel(), weights=agree.ravel(), minlength=ncomp)
    del reps, agree
    bad = np.nonzero(cnt_ok < 0.5 * cnt_all)[0]
    for b in bad:
        m = (comp == b)
        seed[b] = int(np.bincount(ids[m].ravel()).argmax())
    arr = lut[seed[comp]].astype(np.uint8)
    del ids, seed
    return arr, ncomp, comp


def build_and_render(election, shp, out_dir):
    no, year = election["no"], election["year"]
    parsed = election["parsed"]
    print("-" * 62)
    print(f"  【第 {no} 屆 {year} 年】")

    base = build_base(shp, year)

    # ---- 勝選者 / 得票率 ----
    towns = parsed["towns"] if parsed else {}
    if no == 7:
        # 原書未列鄉鎮級候選人得票：依正文，僅樹林、鶯歌非邵恩新領先
        towns = {t: ("邵恩新", 1, 68.72) for t in base["TOWNNAME"]}
        for t in ("樹林", "鶯歌"):
            if t in towns:
                towns[t] = ("無黨籍領先", 0, 50.0)
        print("    第7屆：原書無鄉鎮級候選人得票，依正文以邵恩新全縣 68.72% 套色；樹林、鶯歌記無黨籍。")

    def pick(row):
        tc = row["TOWNNAME"]
        if tc not in towns:
            return NO_DATA_COLOR
        _, group, rate = towns[tc]
        c = color_for(group, rate)
        return c if c is not None else NO_DATA_COLOR

    base["fill_hex"] = base.apply(pick, axis=1)
    blank = sorted(set(base["TOWNNAME"]) - set(towns))
    extra = sorted(set(towns) - set(base["TOWNNAME"]))
    print(f"    鄉鎮市區 {len(base)}｜有資料 {len(base) - len(blank)}｜無資料/留白 {len(blank)}"
          + (f"（{'、'.join(blank)}）" if blank else ""))
    if extra:
        print(f"    注意：資料中鄉鎮無對應底圖：{'、'.join(extra)}")

    rec = base[["COUNTYNAME", "TOWNNAME", "geometry", "fill_hex"]].copy().reset_index(drop=True)

    # ---- 畫布 ----
    minx, miny, maxx, maxy = rec.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny
    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m
    print(f"    底圖 {len(rec)} 鄉鎮市區，1px = {geo_w_m / w_px:.3f}m，圖幅 {w_px}x{h_px}px")

    lines_mask = render_line_layer(rec, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    arr, ncomp, comp = flood_fill_layer(rec, lines_mask, w_px, h_px, minx, maxy, sx, sy)
    arr[lines_mask] = 0

    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"臺北縣{year}年縣長選舉_各鄉鎮市得票率地圖.png")
    Image.fromarray(arr, mode="RGB").save(out_png)
    del arr
    print(f"    Saved: {out_png}")


# ===================== 主流程 =====================
def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    want_years = {int(a) for a in args if a.isdigit()} if args else None

    print("=" * 62)
    print("  臺北縣歷屆縣長選舉 各鄉鎮市區得票率地圖（1951–1993｜111 村里界 + Color2.txt）")
    print("=" * 62)
    if not os.path.exists(SHP_PATH):
        raise FileNotFoundError("找不到村里界 SHP：" + SHP_PATH)

    t0 = time.time()
    elections = parse_md(MD_PATH)
    print(f"  解析得票表：{len(elections)} 屆（{min(elections)}–{max(elections)}）")
    shp = load_shp()
    print(f"  SHP 圖斑：{len(shp)}（新北市 + 臺北市）")

    for no in sorted(elections):
        e = elections[no]
        if want_years is not None and e["year"] not in want_years:
            continue
        if e["parsed"] is None and no != 7:
            print(f"  注意：第 {no} 屆無候選人鄉鎮得票表，略過")
            continue
        build_and_render(e, shp, OUT_DIR)

    print("=" * 62)
    print(f"  全部完成，耗時 {time.time() - t0:.1f} 秒")


if __name__ == "__main__":
    main()
