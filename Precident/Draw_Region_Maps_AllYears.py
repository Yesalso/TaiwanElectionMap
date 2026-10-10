# -*- coding: utf-8 -*-
"""
跨屆（1996–2024）總統副總統選舉 五大分區 各村（里）得票率地圖 批次產生器

底圖：內政部 111 年村里界 SHP
      D:\\Windows\\Documents\\村里界歷史圖資_111\\村里界歷史圖資_111\\VILLAGE_MOI_1111118.shp
配色：Precident\\color.txt（6 組政黨色階；檔頭註解會自動忽略）

繪圖邏輯：【鄉鎮市區級填色，不繪村里界線】
  * 只繪 鄉鎮市區界 3px + 縣市界/海岸線 5px：matplotlib(Agg,DPI=100) 繪區面與界線，
    以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層（村里界不再繪製）
  微孔洞清理 clean_tiny_holes、迴針清理 remove_ring_slits
  填色：直接讀各屆『鄉鎮市區級別』官方得票率（得票數加總重算）
        （勝選候選人＝該區得票率最高者；色階深淺＝其官方得票率）
        洪水填充：黑線為封閉堤壩，每塊鄉鎮市區整塊填單色 → 顏色永不跨越黑線
  版面：**不畫標題、不畫圖例**，只輸出純地圖
  留白：DROP_NAN_COUNTIES 列出的縣市，其「無村里名」圖斑整筆不畫（港區、機場、軍港、
        海埔新生地等），圖上直接留白；目前為 基隆市 / 臺中市 / 雲林縣 / 高雄市

比例尺：1px = 20m（與 2020 腳本相同）
分區：北北基宜 / 桃竹苗 / 中彰投 / 雲嘉南 / 高屏
輸出：各屆 <year>Precident/maps/<分區><年份>年總統副總統選舉_得票率地圖.png

執行：
    py Precident\\Draw_Region_Maps_AllYears.py                 # 全部年份 × 全部分區
    py Precident\\Draw_Region_Maps_AllYears.py 2020            # 只做 2020（全分區）
    py Precident\\Draw_Region_Maps_AllYears.py 2020 高屏       # 只做 2020 高屏
    py Precident\\Draw_Region_Maps_AllYears.py all 中彰投,雲嘉南  # 只做指定分區（多個用逗號）
"""
import os
import re
import sys
import ast
import glob
import math
import time
import unicodedata
import warnings
import collections

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from difflib import SequenceMatcher
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===================== 路徑 / 常數 =====================
PREC_ROOT = os.path.dirname(os.path.abspath(__file__))          # ...\Precident
COLOR_TXT = os.path.join(PREC_ROOT, "color.txt")
SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"
SHP_ENCODING = "UTF-8"
TARGET_CRS = "EPSG:3826"

METERS_PER_PIXEL = 20.0     # 1px = 20m（沿用 2020 腳本）
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.01
SIMPLIFY_TOL_M = 0.0

LINE_VILLAGE_PX = 1
LINE_TOWNSHIP_PX = 3
LINE_OUTER_PX = 5
THRESHOLD_VAL = 40
HOLE_MIN_AREA_M2 = 10000.0

NO_DATA_COLOR = "#FFFFFF"
DPI = 100

DROP_NAN_COUNTIES = ["基隆市", "臺中市", "雲林縣", "高雄市"]
# ↑ 這些縣市「無村里名」的圖斑（港區水域、機場、軍港、海埔新生地等）整筆不畫，
#   圖上直接留白、不畫外框。名稱以 111 村里界原始 COUNTYNAME 為準，比對時會正規化
#   （臺/台、高雄縣→高雄市…），所以寫「台中市」也能命中「臺中市」。
REMOTE_MAX_DIST_M = 2000.0          # 無村里名：距本島 > 2km 剔除
NAMED_MAX_DIST_M = 20000.0          # 有村里名：距本島 > 20km 才剔除

MIN_SIMILARITY = 0.5

# ===================== 五大地區（111 版村里界縣市名）=====================
REGIONS = collections.OrderedDict([
    ("北北基宜", ["臺北市", "新北市", "基隆市", "宜蘭縣"]),
    ("桃竹苗",   ["桃園市", "新竹縣", "新竹市", "苗栗縣"]),
    ("中彰投",   ["臺中市", "彰化縣", "南投縣"]),
    ("雲嘉南",   ["雲林縣", "嘉義縣", "嘉義市", "臺南市"]),
    ("高屏",     ["高雄市", "屏東縣"]),
])

# ===================== 各屆資料與候選人 → color.txt 色階組別 =====================
# 色階組別索引＝ color.txt 由上而下的順序：
#   0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃)
#   4 宋楚瑜無黨籍(橘) / 5 台灣民眾黨(青綠)
_RATE_SHEET = "各里彙總"
_RATE_COLS = dict(county_col="選舉區別", town_col="鄉(鎮、市、區)別", vill_col="村里別")

YEAR_CONFIGS = collections.OrderedDict([
    (1996, dict(dir="1996Precident", file="1996總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("陳履安", 0), ("李登輝", 1), ("彭明敏", 2), ("林洋港", 3)])),
    (2000, dict(dir="2000Precident", file="2000總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("宋楚瑜", 4), ("連戰", 1), ("李敖", 3), ("許信良", 5), ("陳水扁", 2)])),
    (2004, dict(dir="2004Precident", file="2004總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("陳水扁", 2), ("連戰", 1)])),
    (2008, dict(dir="2008Precident", file="2008總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("馬英九", 1), ("謝長廷", 2)])),
    (2012, dict(dir="2012Precident", file="2012總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("蔡英文", 2), ("馬英九", 1), ("宋楚瑜", 4)])),
    (2016, dict(dir="2016Precident", file="2016總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("朱立倫", 1), ("蔡英文", 2), ("宋楚瑜", 4)])),
    (2020, dict(dir="2020Precident", file="2020總統副總統選舉_縣市鄉鎮村里.xlsx",
                sheet="村里層級明細",
                county_col="縣市", town_col="鄉鎮市區", vill_col="村里",
                candidates=[("宋楚瑜", 4), ("韓國瑜", 1), ("蔡英文", 2)])),
    (2024, dict(dir="2024Precident", file="2024總統副總統選舉_得票率.xlsx",
                **_RATE_COLS,
                candidates=[("柯文哲", 5), ("賴清德", 2), ("侯友宜", 1)])),
])

# 舊縣市名 → 111 版縣市名（皆經 臺→台 正規化後比對）
COUNTY_ALIAS = {
    "台北縣": "新北市", "桃園縣": "桃園市",
    "台中縣": "台中市", "台中市": "台中市",
    "台南縣": "台南市", "台南市": "台南市",
    "高雄縣": "高雄市", "高雄市": "高雄市",
}

# 鄉鎮市區改制更名：鍵 = (舊縣市名正規鍵, 舊鄉鎮核心) → 111 版鄉鎮核心。
#   高雄縣三民鄉於 2008 年正名為那瑪夏鄉（今那瑪夏區）；必須連同「舊縣市」比對，
#   否則縣市合併後會與高雄市三民區同名互撞，導致那瑪夏區無法對到村里資料。
TOWN_ALIAS = {
    ("高雄縣", "三民"): "那瑪夏",   # 2008 正名為那瑪夏鄉；須避開與高雄市三民區撞名
    ("台南市", "中"): "中西",        # 1996/2000 臺南市中區
    ("台南市", "西"): "中西",        # 1996/2000 臺南市西區（2004 與中區合併為中西區）
}
# 村里更名：111 版鄉鎮核心 → {舊村里核心: 111 版村里核心}。
#   三民鄉三村於 2008 年隨鄉名正名：
#   民族村→南沙魯里、民權村→瑪雅里、民生村→達卡努瓦里。
VILLAGE_ALIAS = {
    "那瑪夏": {"民族": "南沙魯", "民權": "瑪雅", "民生": "達卡努瓦"},
}


# ===================== 讀 color.txt =====================
def load_color_stops(path):
    """讀 color.txt（Python 串列字面）。忽略整行註解，取 '=' 之後做 literal_eval。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    rhs = "\n".join(lines).split("=", 1)[1]
    return ast.literal_eval(rhs)


RATE_COLOR_STOPS = load_color_stops(COLOR_TXT)


# ===================== 文字正規化 / 顏色 =====================
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂', '曹': '槽', '\U00025562': '槽', '磘': '窯', '獇': '羌',
    '舘': '館', '廍': '部', '峯': '峰', '脚': '腳',
    '\ue006': '塭', '\U00026c21': '那', '売': '壳', '欍': '春',
})
VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"}, {"舘", "館"}, {"磘", "窯"}, {"獇", "羌"}, {"曹", "槽"}, {"脚", "腳"},
]


def normalize_text(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s


def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))


def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))


def canon_county(s):
    """縣市名 → 111 版正規鍵（臺/台 統一、舊名對照）。"""
    s = normalize_text(s).replace("臺", "台")
    return COUNTY_ALIAS.get(s, s)


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and np.isnan(val)) or val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _char_pairs(a, b):
    if len(a) != len(b):
        return None
    return list(zip(a, b))


def is_variant_fuzzy(a, b):
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    return any(ca in g and cb in g for g in VARIANT_FUZZY_GROUPS)


def fuzzy_lookup(county, town, vill, by_key, by_town):
    if not town or not vill:
        return None, "none"
    key = (county, town, vill)
    if key in by_key:
        return by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get((county, town), []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, "none"
    if not is_variant_fuzzy(vill, best_v):
        return None, "none"
    return best_val, f"fuzzy:{best_v}({best_ratio:.2f})"


# ===================== 讀取得票率 Excel =====================
def load_vote_data(cfg):
    """回傳 (by_key, by_town, n)。
    by_key : (county_key, town_core, vill_core) -> {候選人名: 得票率}
    by_town: (county_key, town_core) -> [(vill_core, {候選人:率}), ...]
    多村里合併為一列（以 、 分隔）時拆解共用同組得票率。"""
    xlsx = os.path.join(PREC_ROOT, cfg["dir"], "data", cfg["file"])
    sheet = cfg.get("sheet", _RATE_SHEET)
    df = pd.read_excel(xlsx, sheet_name=sheet, dtype=str)
    cols = [str(c) for c in df.columns]

    cands = cfg["candidates"]
    rate_col = {}
    for name, _gi in cands:
        col = next((c for c in cols if c.strip().endswith("得票率") and name in c), None)
        if col is None:
            raise ValueError(f"{os.path.basename(xlsx)} 找不到「{name}」得票率欄位")
        rate_col[name] = col

    f_county, f_town, f_vill = cfg["county_col"], cfg["town_col"], cfg["vill_col"]
    by_key, by_town = {}, {}
    for _, r in df.iterrows():
        county_raw = normalize_text(r.get(f_county)).replace("臺", "台")
        county = canon_county(r.get(f_county))
        town = strip_town_suffix(r.get(f_town))
        town = TOWN_ALIAS.get((county_raw, town), town)
        vill_raw = normalize_text(r.get(f_vill))
        if not county or not town or not vill_raw:
            continue
        vals, ok = {}, True
        for name, _gi in cands:
            try:
                v = float(str(r[rate_col[name]]).strip().replace("%", "").replace("\u00a0", ""))
            except (TypeError, ValueError):
                ok = False
                break
            if not np.isfinite(v):
                ok = False
                break
            vals[name] = v
        if not ok:
            continue
        vill_alias = VILLAGE_ALIAS.get(town, {})
        for part in re.split(r"[、，,]", vill_raw):
            pc = strip_village_suffix(part.strip())
            pc = vill_alias.get(pc, pc)
            if not pc:
                continue
            key = (county, town, pc)
            if key in by_key:
                continue
            by_key[key] = vals
            by_town.setdefault((county, town), []).append((pc, vals))
    return by_key, by_town, len(by_key)


# ===================== 讀取鄉鎮市區級官方得票率 =====================
_TOWN_SHEET = "鄉鎮市區級別"


def load_town_rates(year, cands):
    """讀 `<年份>總統副總統選舉_縣市鄉鎮村里.xlsx` 的『鄉鎮市區級別』工作表，
    回傳 {(county_core, town_core): {候選人名: 得票率(%)}}。

    以官方「得票數」加總後重算得票率（＝候選人得票數 / 該區候選人得票數合計），
    因此同一鄉鎮市區若有多列（如 1996/2000 臺南市中區、西區合併為中西區）會自動合併。
    這可避免「村里平均」造成的色階失真：得票率低者反而被塗成較深顏色。"""
    xlsx = os.path.join(PREC_ROOT, f"{year}Precident", "data",
                        f"{year}總統副總統選舉_縣市鄉鎮村里.xlsx")
    df = pd.read_excel(xlsx, sheet_name=_TOWN_SHEET, dtype=str)
    cols = [str(c) for c in df.columns]

    vote_col = {}
    for name, _gi in cands:
        col = next((c for c in cols if c.strip().endswith("得票數") and name in c), None)
        if col is None:
            raise ValueError(f"{os.path.basename(xlsx)} 找不到「{name}」得票數欄位")
        vote_col[name] = col

    acc = {}
    for _, r in df.iterrows():
        county_raw = normalize_text(r.get("縣市")).replace("臺", "台")
        county = canon_county(r.get("縣市"))
        town = strip_town_suffix(r.get("鄉鎮市區"))
        town = TOWN_ALIAS.get((county_raw, town), town)
        if not county or not town:
            continue
        d = acc.setdefault((county, town), {name: 0.0 for name, _ in cands})
        for name, _gi in cands:
            try:
                v = float(str(r[vote_col[name]]).strip().replace(",", "").replace("\u00a0", ""))
            except (TypeError, ValueError):
                v = 0.0
            if np.isfinite(v):
                d[name] += v

    rates = {}
    for key, d in acc.items():
        total = sum(d.values())
        if total <= 0:
            continue
        rates[key] = {name: d[name] / total * 100.0 for name, _ in cands}
    return rates


# ===================== 圖資清理（沿用 2024 版）=====================
def strip_far_parts(gdf, max_dist_nameless=REMOTE_MAX_DIST_M, max_dist_named=NAMED_MAX_DIST_M):
    parts, owner = [], []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for pp in ps:
            if pp is None or pp.is_empty:
                continue
            parts.append(pp)
            owner.append(i)
    if not parts:
        return gdf
    merged = unary_union(parts)
    comps = [c for c in (merged.geoms if hasattr(merged, "geoms") else [merged])
             if c.geom_type in ("Polygon", "MultiPolygon")]
    if not comps:
        comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)

    vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
    named = (~vv.isin(["", "nan", "None"])).to_numpy()
    owner_arr = np.array(owner, dtype=int)
    thr = np.where(named[owner_arr], max_dist_named, max_dist_nameless)
    dist = np.array([main.distance(pp) for pp in parts])
    keep_flags = dist <= thr

    dropped = np.nonzero(~keep_flags)[0]
    if len(dropped):
        print(f"    離島/碎塊清理：剔除 {len(dropped)} 個圖斑"
              f"（無村里名 > {max_dist_nameless / 1000:.0f}km、有村里名 > {max_dist_named / 1000:.0f}km）")

    idx0, rebuilt = 0, []
    for geom in gdf.geometry:
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kp = [ps[k] for k in range(len(ps)) if keep_flags[idx0 + k]]
        idx0 += len(ps)
        kp = [g for g in kp if g is not None and not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon")]
        if not kp:
            rebuilt.append(None)
        elif len(kp) == 1:
            rebuilt.append(kp[0])
        else:
            rebuilt.append(MultiPolygon(kp))
    out = gdf.copy()
    out["geometry"] = rebuilt
    out = out[~out["geometry"].isna() & ~out["geometry"].is_empty].copy().reset_index(drop=True)

    # 保留的有編制離島數（供 ② 層連通分量自檢期待值用）
    kept_far = [j for j in range(len(parts)) if keep_flags[j] and dist[j] > 500]
    n_islands = len(set(owner[j] for j in kept_far))
    out.attrs["n_islands"] = n_islands
    return out


def _despike_ring(coords, tol=5.0, area_thr=5000.0, min_path=100.0):
    P = np.asarray(coords, dtype=float)
    n = len(P)
    if n < 5:
        return P
    dead = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        if dead[i]:
            i += 1
            continue
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        d[:i + 2] = np.inf
        if i == 0:
            d[n - 1] = np.inf
        j = int(np.argmin(d))
        if d[j] <= tol:
            seg = P[i:j + 1]
            path_len = float(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])).sum())
            _x, _y = seg[:, 0], seg[:, 1]
            area = 0.5 * abs(np.dot(_x[:-1], _y[1:]) - np.dot(_x[1:], _y[:-1]))
            if path_len > min_path and area < area_thr:
                dead[i + 1:j] = True
        i += 1
    return P[~dead]


def remove_ring_slits(gdf, tol=5.0, area_thr=5000.0, min_path=100.0):
    n_ring_fixed = 0

    def _fix(geom):
        nonlocal n_ring_fixed
        if geom is None or geom.is_empty:
            return geom
        out = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            ext = _despike_ring(poly.exterior.coords, tol, area_thr, min_path)
            if len(ext) != len(poly.exterior.coords):
                n_ring_fixed += 1
            holes = []
            for r in poly.interiors:
                h = _despike_ring(r.coords, tol, area_thr, min_path)
                if len(h) != len(r.coords):
                    n_ring_fixed += 1
                if len(h) >= 4:
                    holes.append(h)
            out.append(Polygon(ext, holes).buffer(0))
        if not out:
            return geom
        return out[0] if len(out) == 1 else MultiPolygon(out)

    o = gdf.copy()
    o["geometry"] = o.geometry.apply(_fix)
    return o[~o.geometry.isna() & ~o.geometry.is_empty].copy().reset_index(drop=True)


def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kept = []
        for poly in parts:
            if poly.geom_type != "Polygon" or poly.area < min_area:
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


# ===================== 線稿工具（沿用 2024 版）=====================
def to_px(coords, minx, maxy, sx, sy):
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def extract_lines(gs):
    parts = list(gs.geoms) if hasattr(gs, "geoms") else [gs]
    out = []
    for g in parts:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(list(g.coords))
        elif g.geom_type == "MultiLineString":
            out.extend(list(ls.coords) for ls in g.geoms)
        elif g.geom_type == "GeometryCollection":
            out.extend(extract_lines(g))
    return out


def draw_layer(lines, width, w_px, h_px, minx, maxy, sx, sy):
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords, minx, maxy, sx, sy)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


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


# ===================== 填色（油漆桶／洪水填充）=====================
def flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy):
    from rasterio.features import rasterize
    from affine import Affine

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


def check_region_single_color(arr, ncomp, comp):
    c = (arr[..., 0].astype(np.int32) << 16) | \
        (arr[..., 1].astype(np.int32) << 8) | arr[..., 2].astype(np.int32)
    idx = np.arange(1, ncomp)
    mn = ndimage.minimum(c, comp, index=idx)
    mx = ndimage.maximum(c, comp, index=idx)
    return ncomp - 1, int((mn != mx).sum())


def full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy):
    from rasterio.features import rasterize
    from affine import Affine
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)
    fill = np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                     for hx in records["fill_hex"]], dtype=np.uint8)
    exp = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    inside = ids > 0
    exp[inside] = fill[ids[inside] - 1]
    black = img.sum(axis=2) == 0
    wrong = (img != exp).any(axis=2) & ~black
    return int(wrong.sum()), int((wrong & ~inside).sum())


# ===================== 讀 SHP（一次）=====================
def load_shp():
    g = gpd.read_file(SHP_PATH, encoding=SHP_ENCODING)
    if g.crs is None:
        g.crs = "EPSG:4326"
    g = g.to_crs(TARGET_CRS)
    g = g[g["COUNTYNAME"].notna()].copy()
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g["COUNTYNAME"] = g["COUNTYNAME"].astype(str).str.strip()
    g["TOWNNAME"] = g["TOWNNAME"].astype(str).str.strip()
    g["county_canon"] = g["COUNTYNAME"].apply(canon_county)
    return g


# ===================== 繪製單一（年份 × 分區）=====================
def build_region_map(year, region_name, counties, shp, cfg, town_rates):
    cands = cfg["candidates"]
    region_canon = {canon_county(c) for c in counties}

    print("-" * 62)
    print(f"  【{year} {region_name}】{'、'.join(counties)}")

    gdf = shp[shp["county_canon"].isin(region_canon)].copy()
    gdf = gdf[gdf["TOWNNAME"].notna()].copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[~gdf["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy().reset_index(drop=True)
    if len(gdf) == 0:
        print("    ⚠️ 無圖斑，略過")
        return

    if DROP_NAN_COUNTIES:
        _vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
        _canon_drop = {canon_county(c) for c in DROP_NAN_COUNTIES}
        _drop = (gdf["COUNTYNAME"].apply(canon_county).isin(_canon_drop)
                 & _vv.isin(["", "nan", "None"]))
        if int(_drop.sum()):
            print(f"    DROP_NAN_COUNTIES：剔除 {int(_drop.sum())} 筆無村里名圖斑"
                  f"（{'、'.join(DROP_NAN_COUNTIES)}）")
            gdf = gdf[~_drop].copy().reset_index(drop=True)

    gdf = strip_far_parts(gdf)

    # ---- 對應鄉鎮市區級官方得票率 ----
    gdf["county_core"] = gdf["COUNTYNAME"].apply(canon_county)
    gdf["town_core"] = gdf["TOWNNAME"].apply(strip_town_suffix)
    n = len(gdf)

    # 每個鄉鎮市區：勝選候選人＝官方得票率最高者；色階深淺＝其官方得票率
    town_color = {}
    for (cc, tc), rates in town_rates.items():
        if cc not in region_canon or not rates:
            continue
        name = max(rates, key=rates.get)
        gi = next(g for cn, g in cands if cn == name)
        town_color[(cc, tc)] = get_color_by_value(rates[name], RATE_COLOR_STOPS[gi])

    fill_hex = np.array([NO_DATA_COLOR] * n, dtype=object)
    for i in range(n):
        c = town_color.get((gdf["county_core"].iat[i], gdf["town_core"].iat[i]))
        if c is not None:
            fill_hex[i] = c
    gdf["fill_hex"] = fill_hex

    shp_towns = set(zip(gdf["county_core"], gdf["town_core"]))
    blank = shp_towns - set(town_color)
    print(f"    鄉鎮市區 {len(shp_towns)}｜對到官方資料 {len(shp_towns) - len(blank)}｜留白 {len(blank)}")
    if blank:
        print(f"    ⚠️ 無資料：{'、'.join(sorted(f'{c}/{t}' for c, t in blank))}")

    records = gdf[["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry", "fill_hex"]].copy()
    villages = records[records["VILLNAME"].notna()].copy()
    if len(villages) == 0:
        print("    ⚠️ 無村里層，略過")
        return
    townships = records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
    townships = remove_ring_slits(townships)
    townships = clean_tiny_holes(townships)

    # ---- 畫布 ----
    minx, miny, maxx, maxy = records.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny
    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m
    print(f"    1px = {geo_w_m / w_px:.4f} m，圖幅 {w_px}x{h_px} px")

    # ---- 鄉鎮市區界 + 縣市界/海岸線（不繪村里界）----
    town_layer = render_line_layer(townships, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    lines_mask = town_layer

    # ---- 填色 ----
    arr, ncomp, comp = flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy)
    arr[lines_mask] = 0

    # ---- 自檢 ----
    _nc, _nbad = check_region_single_color(arr, ncomp, comp)
    _nw, _nout = full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy)
    _tot = w_px * h_px
    allowed = {(255, 255, 255), (0, 0, 0)}
    for stops in RATE_COLOR_STOPS:
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in hex2rgb(hx)))
    _uniq = np.unique(arr.reshape(-1, 3), axis=0)
    _n_bad = int(sum(1 for c in _uniq if tuple(int(x) for x in c) not in allowed))
    print(f"    自檢：非單色區 {_nbad}｜幾何差異 {_nw}px({_nw / _tot * 100:.4f}%)｜"
          f"村外非白 {_nout}｜非允許色種類 {_n_bad}")

    # ---- 輸出（純地圖）----
    # 統一輸出到 Precident/maps/<年份>/，避免覆蓋各屆既有成品
    out_dir = os.path.join(PREC_ROOT, "maps", str(year))
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"{region_name}{year}年總統副總統選舉_得票率地圖.png")
    Image.fromarray(arr, mode="RGB").save(out_png)
    del arr
    print(f"    Saved: {out_png}")


# ===================== 主流程 =====================
def main():
    args = sys.argv[1:]
    want_years = [int(args[0])] if args and args[0].isdigit() else list(YEAR_CONFIGS.keys())
    if len(args) > 1:
        want_regions = [z for z in re.split(r"[,，、\s]+", args[1]) if z]   # 可用逗號指定多個分區
    else:
        want_regions = list(REGIONS.keys())

    print("=" * 62)
    print("  跨屆總統副總統選舉 五大分區 村里得票率地圖（111 村里界 + color.txt）")
    print("=" * 62)
    if not os.path.exists(SHP_PATH):
        raise FileNotFoundError("找不到村里界 SHP：" + SHP_PATH)

    t_all = time.time()
    shp = load_shp()
    print(f"  SHP 圖斑：{len(shp)}，縣市：{len(shp['county_canon'].unique())}")

    for y in want_years:
        if y not in YEAR_CONFIGS:
            print(f"  ⚠️ 無 {y} 設定，略過")
            continue
        cfg = YEAR_CONFIGS[y]
        town_rates = load_town_rates(y, cfg["candidates"])
        print("=" * 62)
        print(f"  {y} 鄉鎮市區得票率記錄：{len(town_rates)}")
        for rn in want_regions:
            if rn not in REGIONS:
                print(f"  ⚠️ 無分區 {rn}，略過")
                continue
            try:
                build_region_map(y, rn, REGIONS[rn], shp, cfg, town_rates)
            except Exception as e:
                import traceback
                print(f"    ✗ {y} {rn} 失敗：{e}")
                traceback.print_exc()

    print("=" * 62)
    print(f"  全部完成，耗時 {time.time() - t_all:.1f} 秒")


if __name__ == "__main__":
    main()
