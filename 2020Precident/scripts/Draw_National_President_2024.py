# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與 2024 總統副總統選舉全臺各村(里)得票率 Excel 結合，
繪製全臺灣候選人得票率地圖（以村里為填色單位）。

資料來源：2024Precident/data/2024{縣市}_得票率.xlsx（convert_2024_president_percent.py 產出）
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | 中國國民黨得票率 | 民主進步黨得票率 | 台灣民眾黨得票率

繪圖邏輯：沿用 Empty_Map/DrawMap.py 之全臺地圖配置：
    - 臺灣本島 + 澎湖為主題；金門、連江(馬祖)為左上角 1:1 附圖（金門框在上、連江框在下，上下緊貼）
    - 高雄市無資料(未編定村里/代管)區域、基隆離岸島嶼(彭佳嶼等)、宜蘭釣魚台列嶼不繪製
    - 村里界 1px、鄉鎮市區界 2px、縣市地界 3px；金門/連江/澎湖等面積小之縣市海岸線 1px、僅畫內部鄉鎮界
    - 金門/連江附圖外框 6px、烏坵以同比例尺置入金門空餘角落(1px 框)

填色邏輯：沿用 scripts/20/Converge_to_map.py：
    - 每村里取三候選人得票率最高者為該村里獲勝候選人，以其色階(5% 間距、35% 起)填色
    - SHP 有地名但無資料者填白色；VILLNAME 為空值(多為荒島)者填灰色
    - 右側圖例顯示候選人色階（自全臺最低領先得票率向下取 5 的倍數起）

執行：
    py Draw_National_President_2024.py
"""
import os
import re
import glob
import unicodedata
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO
from difflib import SequenceMatcher
from PIL import Image, ImageDraw

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# ---------------------- 字体设置 ----------------------
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
DATA_DIR = os.path.join(PROJECT_DIR, "2024Precident", "data")
OUT_DIR = os.path.join(PROJECT_DIR, "2024Precident", "maps")

SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]
SHP_ENCODING = "UTF-8"

# ---------------------- 候選人與資料欄位 ----------------------
# 三組候選人：得票率欄位名 → 圖例名稱
RATE_HEADERS = ["中國國民黨得票率", "民主進步黨得票率", "台灣民眾黨得票率"]
CAND_NAMES = ["侯友宜", "賴清德", "柯文哲"]

TITLE_LINES = ["中華民國第十六屆總統副總統選舉",
               "在全國各村（里）得票領先之候選人得票比例圖"]
OUT_PNG = os.path.join(OUT_DIR, "全臺灣2024年總統副總統選舉_得票率地圖.png")

# ---------------------- 全臺地圖配置（對應 DrawMap.py） ----------------------
EXCLUDE_COUNTIES = {"金門縣", "連江縣"}
THIN_COUNTIES = {"金門縣", "連江縣", "澎湖縣"}
ISLAND_SCALE = 1.0          # 金門、連江附圖比例尺 = 主圖 1 倍
LINE_VILLAGE_PX = 1         # 村里界寬
LINE_TOWNSHIP_PX = 2        # 鄉鎮市區界寬
LINE_COUNTY_PX = 3          # 縣市地界寬（本島等）
LINE_THIN_COUNTY_PX = 1     # 面積小島嶼縣市地界寬（金門、連江、澎湖）
LINE_INSET_BOX_PX = 6       # 金門、連江附圖外框寬
PAD_FRAC = 0.01             # 地圖四周留白比例

METERS_PER_PIXEL = 12       # 目標比例尺（若超出上限會自動放大）
MAX_PX = 11000              # 長寬上限
SCALE_UP = 1.10             # 比例放大 10%

# ---------------------- 繪圖與圖例參數（對應 scripts/20） ----------------------
NO_DATA_COLOR = "#FFFFFF"   # 無資料/空白地區一律純白
DPI = 100
PX2PT = 72.0 / DPI

RATE_COLOR_STOPS = [
    # 第 1 组：中國國民黨 侯友宜（藍色系）
    [(35, "#EAF6FF"), (40, "#B8E2FF"), (45, "#7CC8FF"), (50, "#3AA8FF"),
     (55, "#0088F0"), (60, "#006FCC"), (65, "#0059A8"), (70, "#004684"),
     (75, "#003563"), (80, "#002647"), (85, "#001A31"), (100, "#000D1F")],
    # 第 2 组：民主進步黨 賴清德（綠色系）
    [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
     (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
     (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
    # 第 3 组：台灣民眾黨 柯文哲（青綠色系）
    [(35, "#00D9CA"), (40, "#00BFB2"), (45, "#00A89C"), (50, "#008080"),
     (55, "#006666"), (60, "#004C4C"), (65, "#003838"), (70, "#003030"),
     (75, "#002626"), (80, "#021F1F"), (85, "#001919")],
]

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LEGEND_PADDING = 60
COLUMN_TITLE_GAP = 100
TITLE_FONT_SIZE = 100
CAND_NAME_FONT_SIZE = 84
LEGEND_LABEL_FONT_SIZE = 56

MIN_SIMILARITY = 0.5

# ---------------------- 異體字正規化 ----------------------
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',
    '\U00025562': '槽',   # 坪林區石𕢥里（2024 源資料） / 石槽
    '磘': '窯',
    '獇': '羌',
    '舘': '館',
    '廍': '部',
    '峯': '峰',
    '脚': '腳',
    '\ue006': '塭',      # 臺南安南區 塭南里 / 公(塭)里（中選會資料以私用區字形 U+E006 表示「塭」）
    '\U00026c21': '那',  # 臺南新化區 𦰡拔里 / 那拔里
    '売': '壳',           # 臺中大安區 龜売里 / 龜壳里
    '欍': '春',           # 雲林水林鄉 欍埔村 / 春埔村
})

VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"}, {"舘", "館"}, {"磘", "窯"}, {"獇", "羌"}, {"曹", "槽"}, {"脚", "腳"},
]


def normalize_text(s):
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


def get_color_by_value(val, stops):
    if val is None or np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def resolve_shp():
    for p in SHP_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("找不到村里界 SHP：" + "、".join(SHP_CANDIDATE_PATHS))


def _char_pairs(a, b):
    pairs = []
    la, lb = len(a), len(b)
    if la != lb:
        return None
    for ca, cb in zip(a, b):
        pairs.append((ca, cb))
    return pairs


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
    for group in VARIANT_FUZZY_GROUPS:
        if ca in group and cb in group:
            return True
    return False


def fuzzy_lookup(county, town, vill, by_key, by_town):
    if not town or not vill:
        return None, None, "none"
    key = (county, town, vill)
    if key in by_key:
        return vill, by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get((county, town), []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, None, "none"
    if not is_variant_fuzzy(vill, best_v):
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"


def drop_offshore_parts(gdf_sub, county, offshore_km):
    """移除指定縣市中遠離本縣主体的離岸島嶼部件（如宜蘭縣釣魚台列嶼）。"""
    mask = gdf_sub["COUNTYNAME"] == county
    if not mask.any():
        return gdf_sub
    sub = gdf_sub.loc[mask].copy()
    ref = sub.geometry.union_all().centroid
    exploded = sub.geometry.explode(index_parts=True)
    fr = gpd.GeoDataFrame(exploded.reset_index(), geometry="geometry", crs=sub.crs)
    far = fr.geometry.centroid.distance(ref) / 1000.0 > offshore_km
    if not far.any():
        return gdf_sub
    from shapely.geometry import MultiPolygon
    out = gdf_sub.copy()
    for oi in fr.loc[far, "level_0"].unique():
        keep = fr.loc[(fr["level_0"] == oi) & ~far, "geometry"].tolist()
        if keep:
            out.loc[oi, "geometry"] = MultiPolygon(keep) if len(keep) > 1 else keep[0]
    return out


# ===================== 文字圖片生成（仿 Print_word.py） =====================
def render_text_image(text_lines, font_size=64, dpi=100):
    """Matplotlib 繪字 → OpenCV 二值化 → 透明背景（PIL RGBA）。"""
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    font_name = None
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            font_name = n
            break
    font_family = [font_name, "DejaVu Sans"] if font_name else "DejaVu Sans"

    fig_temp = plt.figure(figsize=(1, 1), dpi=dpi)
    ax_temp = fig_temp.add_subplot(111)
    ax_temp.axis("off")
    fig_temp.canvas.draw()
    renderer = fig_temp.canvas.get_renderer()
    line_widths, line_heights = [], []
    for line in text_lines:
        t = ax_temp.text(0, 0, line, fontsize=font_size, fontfamily=font_family)
        bbox = t.get_window_extent(renderer=renderer)
        line_widths.append(bbox.width)
        line_heights.append(bbox.height)
    plt.close(fig_temp)

    line_spacing = font_size * 1.5
    total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing
    max_width = max(line_widths)
    PAD = 20
    fig_w_pt = max_width + 2 * PAD
    fig_h_pt = total_height + 2 * PAD

    fig = plt.figure(figsize=(fig_w_pt / dpi, fig_h_pt / dpi), dpi=dpi, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w_pt)
    ax.set_ylim(0, fig_h_pt)
    ax.set_facecolor("white")
    ax.axis("off")

    y = PAD + total_height
    for i, line in enumerate(text_lines):
        x = (fig_w_pt - line_widths[i]) / 2
        y -= line_heights[i]
        ax.text(x, y, line, fontsize=font_size, ha="left", va="bottom",
                fontfamily=font_family, color="black")
        y -= line_spacing

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, facecolor="white", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    _, bin_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    h, w = bin_img.shape
    result = np.zeros((h, w, 4), dtype=np.uint8)
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))


_TEXT_IMG_CACHE = {}


def render_text_image_cached(text_lines, font_size):
    key = (tuple(text_lines), font_size)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size)
    return _TEXT_IMG_CACHE[key]


def blit_rgba(base_img, rgba_img, xy):
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))


def get_label_text(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"


# ===================== 讀取得票率 Excel（各縣市） =====================
def load_vote_data(data_dir):
    by_key, by_town = {}, {}
    n_total, n_rows = 0, 0
    files = sorted(glob.glob(os.path.join(data_dir, "2024*得票率.xlsx")))
    for f in files:
        df = pd.read_excel(f, sheet_name=0, dtype=str)
        df.columns = [str(c) for c in df.columns]
        rate_cols = [c for c in RATE_HEADERS if c in df.columns]
        if len(rate_cols) != len(RATE_HEADERS):
            raise ValueError(f"{os.path.basename(f)} 缺少得票率欄位：{RATE_HEADERS}")
        for _, r in df.iterrows():
            county = normalize_text(r.get("選舉區別"))
            town = strip_town_suffix(r.get("鄉(鎮、市、區)別"))
            vill_raw = normalize_text(r.get("村里別"))
            if not county or not town or not vill_raw:
                continue
            try:
                vals = tuple(float(r[c]) for c in rate_cols)
            except (TypeError, ValueError):
                continue
            n_total += 1
            # 源資料有時將多村里合併為一列（以 、 分隔，如連江縣「復興村、福沃村」），
            # 拆解成各村(里)並共用同一組得票率，使連江等多村合併地區能填入顏色。
            parts = [p for p in re.split(r"[、，,]", vill_raw) if p.strip()]
            for part in parts:
                part_core = strip_village_suffix(part.strip())
                if not part_core:
                    continue
                key = (county, town, part_core)
                if key in by_key:
                    continue
                by_key[key] = vals
                by_town.setdefault((county, town), []).append((part_core, vals))
                n_rows += 1
    return by_key, by_town, n_rows, n_total


# ===================== 主流程 =====================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 62)
    print("  2024 總統副總統選舉 全臺灣各村（里）得票率地圖")
    print("=" * 62)

    # ---- 讀 SHP ----
    shp_path = resolve_shp()
    gdf_all = gpd.read_file(shp_path, encoding=SHP_ENCODING)
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    gdf_all = gdf_all.to_crs(epsg=3826)
    gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
    gdf_all = gdf_all[~gdf_all.geometry.isna()].copy()
    gdf_all = gdf_all[~gdf_all.geometry.is_empty].copy()

    # ---- 讀得票率資料 ----
    vote_dict, vote_by_town, n_rows, n_total = load_vote_data(DATA_DIR)
    print(f"  Excel 得票率記錄 : {n_total} 筆（去重後 {n_rows} 筆）")

    # ---- 匹配（縣市+鄉鎮+村里三鍵精確；同鄉鎮單字異體模糊）----
    gdf_all["county_core"] = gdf_all["COUNTYNAME"].apply(normalize_text)
    gdf_all["town_core"] = gdf_all["TOWNNAME"].apply(strip_town_suffix)
    gdf_all["vill_core"] = gdf_all["VILLNAME"].apply(strip_village_suffix)

    def process_row(r):
        county, town, vill = r["county_core"], r["town_core"], r["vill_core"]
        matched_vill, vals, mt = fuzzy_lookup(county, town, vill, vote_dict, vote_by_town)
        if vals is None:
            return pd.Series([np.nan, np.nan, np.nan, "none"])
        return pd.Series(list(vals) + [mt])

    rate_cols = [f"rate{i}" for i in range(len(RATE_HEADERS))]
    gdf_all[rate_cols + ["match_type"]] = gdf_all.apply(process_row, axis=1)

    # ---- 統計匹配 ----
    exact_cnt = int((gdf_all["match_type"] == "exact").sum())
    fuzzy_cnt = int(gdf_all["match_type"].str.startswith("fuzzy", na=False).sum())

    # ---- 填色：三取最高者，以其色階填色；無資料(含 VILLNAME 空值)一律純白 ----
    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], RATE_COLOR_STOPS[i])

    gdf_all["fill_hex"] = np.where(
        gdf_all[rate_cols].notna().any(axis=1),
        gdf_all.apply(pick_fill_color, axis=1),
        NO_DATA_COLOR,
    )
    gdf_all["fill_hex"] = gdf_all["fill_hex"].fillna(NO_DATA_COLOR)

    has_data = gdf_all[rate_cols].notna().any(axis=1)
    cnt_valid = int(has_data.sum())
    print(f"  SHP 村里要素     : {len(gdf_all)}")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字/模糊匹配   : {fuzzy_cnt}")
    print(f"  有資料填色       : {cnt_valid}")
    print(f"  無資料（純白）    : {len(gdf_all) - cnt_valid}")

    # ---- 圖例起點：全臺最低領先得票率，向下取 5 的倍數 ----
    min_win_rate = 100.0
    for _, row in gdf_all[has_data].iterrows():
        win = max(row[c] for c in rate_cols)
        if win < min_win_rate:
            min_win_rate = win
    legend_start_tier = int(min_win_rate // 5) * 5
    print(f"  全臺最低領先得票率 : {min_win_rate:.2f}% → 圖例自 {legend_start_tier}% 起")

    # ===================== 全臺地圖佈局（沿用 DrawMap.py） =====================
    # 排除金門、連江，得到臺灣省主題
    gdf_sub = gdf_all[~gdf_all["COUNTYNAME"].isin(EXCLUDE_COUNTIES)].copy()

    # 高雄市無資料區域（VILLNAME 為 NaN，未編定村里/代管）不繪製
    gdf_sub = gdf_sub[~((gdf_sub["COUNTYNAME"] == "高雄市") & gdf_sub["VILLNAME"].isna())].copy()

    # 基隆市代管離岸島嶼（彭佳嶼、棉花嶼、花瓶嶼）不繪製
    KEELUNG_OFFSHORE_KM = 25
    kl_mask = gdf_sub["COUNTYNAME"] == "基隆市"
    if kl_mask.any():
        kl_ref = gdf_sub.loc[kl_mask].geometry.union_all().centroid
        kl_dist_km = gdf_sub.loc[kl_mask].geometry.centroid.distance(kl_ref) / 1000.0
        kl_offshore = kl_dist_km > KEELUNG_OFFSHORE_KM
        gdf_sub = gdf_sub[~(kl_mask & kl_offshore.reindex(gdf_sub.index).fillna(False))].copy()

    # 宜蘭縣離岸島嶼（釣魚台列嶼等）不繪製；無鄉鎮市區者也不繪製
    gdf_sub = drop_offshore_parts(gdf_sub, "宜蘭縣", 60)
    gdf_sub = gdf_sub[gdf_sub["TOWNNAME"].notna()].copy()

    # 金門、連江：1:1 平移到主題左上方作為附圖；烏坵以同比例尺放進金門框內空餘區域
    islands = gdf_all[gdf_all["COUNTYNAME"].isin({"金門縣", "連江縣"})].copy()
    island_boxes = []
    if len(islands) > 0:
        m_minx, m_miny, m_maxx, m_maxy = gdf_sub.total_bounds
        m_w, m_h = m_maxx - m_minx, m_maxy - m_miny
        margin_x = 0.02 * m_w
        margin_y = 0.02 * m_h
        box_pad = 0.03
        tgt_left = m_minx + margin_x
        filled_top = m_maxy - margin_y
        island_parts = []
        jinmen = islands[(islands["COUNTYNAME"] == "金門縣") & (islands["TOWNNAME"] != "烏坵鄉")]
        wuci = islands[(islands["COUNTYNAME"] == "金門縣") & (islands["TOWNNAME"] == "烏坵鄉")]
        lianjiang = islands[islands["COUNTYNAME"] == "連江縣"]
        groups = [("金門縣", jinmen), ("連江縣", lianjiang)]
        for cn, part in groups:
            if len(part) == 0:
                continue
            part = part.copy()
            x0, y0, x1, y1 = part.total_bounds
            part.geometry = part.geometry.scale(
                xfact=ISLAND_SCALE, yfact=ISLAND_SCALE, origin=(x0, y0)
            )
            cx0, cy0, cx1, cy1 = part.total_bounds
            cw, ch = cx1 - cx0, cy1 - cy0
            xp, yp = box_pad * cw, box_pad * ch
            box_top = filled_top
            content_top = box_top - yp
            part.geometry = part.geometry.translate(
                xoff=(tgt_left + xp) - cx0, yoff=content_top - cy1
            )
            island_parts.append(part)
            box = (tgt_left, box_top - ch - 2 * yp, tgt_left + cw + 2 * xp, box_top)
            island_boxes.append((cn, box, LINE_INSET_BOX_PX))
            filled_top = box[1]
        # 烏坵：放進金門框內不與其他島嶼重疊之角落
        if len(wuci) > 0:
            from shapely.geometry import box as shapely_box
            wuci = wuci.copy()
            wx0, wy0, wx1, wy1 = wuci.total_bounds
            wuci.geometry = wuci.geometry.scale(
                xfact=ISLAND_SCALE, yfact=ISLAND_SCALE, origin=(wx0, wy0)
            )
            wb0, wby0, wb1, wby1 = wuci.total_bounds
            ww, wh = wb1 - wb0, wby1 - wby0
            gx0, gy0, gx1, gy1 = island_parts[0].total_bounds
            gw, gh = gx1 - gx0, gy1 - gy0
            mx, my = 0.06 * gw, 0.06 * gh
            jm_geom = island_parts[0].geometry.union_all()
            candidates = [
                (gx0 + mx, gy1 - my - wh),
                (gx1 - mx - ww, gy1 - my - wh),
                (gx0 + mx, gy0 + my),
                (gx1 - mx - ww, gy0 + my),
            ]
            for cx, cy in candidates:
                candidate = wuci.geometry.translate(
                    xoff=cx - wb0, yoff=cy - (wby1 - wh)
                )
                test_box = shapely_box(*candidate.total_bounds)
                if not test_box.intersects(jm_geom):
                    candidate_box = (
                        cx - 0.1 * ww, cy - 0.1 * wh,
                        cx + 1.1 * ww, cy + 1.1 * wh,
                    )
                    island_parts.append(wuci.assign(geometry=candidate))
                    island_boxes.append(("烏坵鄉", candidate_box, LINE_THIN_COUNTY_PX))
                    break
            else:
                print("警告：未找到烏坵空餘位置，跳過烏坵附圖")
        islands = gpd.GeoDataFrame(
            pd.concat(island_parts, ignore_index=True), geometry="geometry", crs=gdf_all.crs
        )
        keep_cols = ["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry"] + rate_cols + ["match_type", "fill_hex"]
        gdf_sub = gpd.GeoDataFrame(
            pd.concat(
                [gdf_sub[keep_cols], islands[keep_cols]], ignore_index=True
            ), geometry="geometry", crs=gdf_all.crs
        )

    print(f"  臺灣含縣市：{sorted(gdf_sub['COUNTYNAME'].unique())}")
    print(f"  繪製要素數：{len(gdf_sub)}")

    # ===================== 決定比例尺與畫布尺寸 =====================
    records = gdf_sub[["COUNTYNAME", "TOWNNAME", "geometry", "fill_hex"]].copy()
    minx, miny, maxx, maxy = records.total_bounds
    geo_w_m, geo_h_m = maxx - minx, maxy - miny
    pad_x, pad_y = PAD_FRAC * geo_w_m, PAD_FRAC * geo_h_m
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny

    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    img_w_px = int(np.ceil(geo_w_m / scale))
    img_h_px = int(np.ceil(geo_h_m / scale))
    print(f"  統一比例尺：1 像素 = {scale:.4f} 米")
    print(f"  圖片尺寸：{img_w_px} × {img_h_px} px")

    fig = plt.figure(figsize=(img_w_px / DPI, img_h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("#FFFFFF")

    # ① 村里填色（無邊）
    records.plot(
        ax=ax, facecolor=records["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )
    # ② 村里黑線（1px）
    gdf_plot_border = gpd.GeoDataFrame(records, geometry="geometry", crs=gdf_all.crs)
    gdf_plot_border.plot(
        ax=ax, edgecolor='black', facecolor='none',
        linewidth=LINE_VILLAGE_PX * PX2PT, antialiased=False, zorder=5
    )
    # ③ 鄉鎮市區界（2px）：金門、連江、澎湖只畫內部相鄰界線
    county_gdf = gdf_plot_border.dissolve(by="COUNTYNAME").reset_index()
    town_gdf = gdf_plot_border.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
    town_thick = town_gdf[~town_gdf["COUNTYNAME"].isin(THIN_COUNTIES)]
    town_thick.plot(
        ax=ax, edgecolor='black', facecolor='none',
        linewidth=LINE_TOWNSHIP_PX * PX2PT, antialiased=False, zorder=7
    )
    internal_lines = []
    for cn in THIN_COUNTIES:
        crows = county_gdf[county_gdf["COUNTYNAME"] == cn]
        if len(crows) == 0:
            continue
        cbound = crows.geometry.iloc[0].boundary
        for tg in town_gdf[town_gdf["COUNTYNAME"] == cn].geometry:
            seg = tg.boundary.difference(cbound)
            if not seg.is_empty:
                internal_lines.append(seg)
    if internal_lines:
        gpd.GeoSeries(internal_lines, crs=gdf_all.crs).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=LINE_TOWNSHIP_PX * PX2PT, antialiased=False, zorder=7
        )
    # ④ 縣市地界：本島 3px；金門、連江、澎湖海岸線 1px
    county_thick = county_gdf[~county_gdf["COUNTYNAME"].isin(THIN_COUNTIES)]
    county_thick.plot(
        ax=ax, edgecolor='black', facecolor='none',
        linewidth=LINE_COUNTY_PX * PX2PT, antialiased=False, zorder=9
    )
    county_thin = county_gdf[county_gdf["COUNTYNAME"].isin(THIN_COUNTIES)]
    county_thin.plot(
        ax=ax, edgecolor='black', facecolor='none',
        linewidth=LINE_THIN_COUNTY_PX * PX2PT, antialiased=False, zorder=9
    )
    # ⑤ 金門/連江附圖外框（6px）、烏坵附圖外框（1px）
    if island_boxes:
        from matplotlib.patches import Rectangle
        for cn, (bx0, by0, bx1, by1), lw in island_boxes:
            box = Rectangle(
                (bx0, by0), bx1 - bx0, by1 - by0,
                fill=False, edgecolor='black', linewidth=lw * PX2PT,
            )
            ax.add_patch(box)
    ax.axis("off")

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)

    img_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # ===================== 顏色量化（分塊處理） =====================
    allowed_hex = {"#FFFFFF", "#000000"}
    for stops in RATE_COLOR_STOPS:
        allowed_hex.update(hx for _, hx in stops)
    allowed_rgb_255 = np.array([hex2rgb(hx) for hx in allowed_hex]).astype(np.float32) * 255

    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    n_pixels = pixels.shape[0]
    CHUNK_SIZE = 500_000
    quantized_flat = np.empty((n_pixels, 3), dtype=np.uint8)
    for start in range(0, n_pixels, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, n_pixels)
        chunk = pixels[start:end]
        min_dist = np.full(chunk.shape[0], np.inf, dtype=np.float32)
        min_idx = np.zeros(chunk.shape[0], dtype=np.int32)
        for i in range(allowed_rgb_255.shape[0]):
            diff = chunk - allowed_rgb_255[i]
            d = np.sqrt((diff * diff).sum(axis=1))
            mask = d < min_dist
            min_dist[mask] = d[mask]
            min_idx[mask] = i
        quantized_flat[start:end] = allowed_rgb_255[min_idx].astype(np.uint8)
    quantized = quantized_flat.reshape(img_rgb.shape)

    # ===================== 文字與圖例 =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size

    title_img = render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)

    legend_stops_list = [
        [(u, c) for u, c in stops if u > legend_start_tier]
        for stops in RATE_COLOR_STOPS
    ]
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in CAND_NAMES]
    name_h = max((im.height for im in name_imgs), default=0)

    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier,
                                 is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(legend_stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    TITLE_GAP = 70
    panel_content_h = title_img.height + TITLE_GAP + legend_h
    legend_x = W + 115
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    title_x = legend_x + (group_w - title_img.width) / 2
    title_right = title_x + title_img.width
    new_W = int(max(title_right + 225, legend_x + group_w + LEGEND_PADDING))
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    # 右側面板：標題＋圖例垂直置中，與地圖右緣對齊
    py = (new_H - panel_content_h) // 2
    blit_rgba(final_img, title_img, (title_x, py))
    py += title_img.height + TITLE_GAP

    draw_obj = ImageDraw.Draw(final_img)
    col_positions = [legend_x + i * (col_width + H_SPACING) for i in range(n_cols)]
    for col_idx, stops in enumerate(legend_stops_list):
        x_start = col_positions[col_idx]
        nm_img = name_imgs[col_idx]
        blit_rgba(final_img, nm_img, (x_start + (BLOCK_WIDTH - nm_img.width) / 2, py))
        for i, (upper, color_hex) in enumerate(stops):
            y = py + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            limg = label_img_cols[col_idx][i]
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))

    final_img.save(OUT_PNG)
    print(f"\n  Saved: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print("  均已完成。")


if __name__ == "__main__":
    main()