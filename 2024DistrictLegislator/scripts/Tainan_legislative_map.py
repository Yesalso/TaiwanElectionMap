# -*- coding: utf-8 -*-
"""
臺南市 第十一屆區域立法委員 得票率地圖（兩種版本）
  A 版：仿 24区域立法委员/10/Converge_to_map.py（色階 10% 起；無黨籍用 45% 起灰階）
  B 版：仿 24区域立法委员/20/Converge_to_map.py（色階 35% 起 5% 距；無黨籍用 0-100 灰階）
兩版皆採用 台南区域含乡镇市区地图.txt 之畫法：
  立法委員選區界＝6px 白色帶（先以擦除帶擦掉黑線）、鄉鎮市區界＝4px 黑帶、
  村里界＝1px 黑線、市外輪廓＝6px 黑帶。

執行：
  py Tainan_legislative_map.py A    // 或 B
"""
import os
import re
import sys
import unicodedata
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import numpy as np
import cv2
from io import BytesIO
from PIL import Image, ImageDraw
from difflib import SequenceMatcher

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE = r"C:\Users\Windows\Desktop\temp\24区域立法委员"
EXCEL_PATH = os.path.join(BASE, "臺南市_得票率.xlsx")
SHEET_NAME = "各里彙總"
CITY_NAME = "臺南市"

SHP_PATH = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"

TITLE_LINES = ["第十一屆區域立法委員", "在臺南市各村（里）領先之候選人得票比例圖"]

# ---------------- 顏色（版本差異，見文首說明） ----------------
# A 版：10 資料夾
STOPS_A = {
    # 中國國民黨（資料夾10 第1組）
    "中國國民黨": [(10, "#00FFFF"), (20, "#00F2FF"), (30, "#00E6FF"), (40, "#00DAFF"),
                    (50, "#00C0F4"), (60, "#00A2E8"), (70, "#0080B8"), (80, "#006591"),
                    (90, "#004B6B"), (100, "#003247")],
    # 民主進步黨（資料夾10 第2組）
    "民主進步黨": [(10, "#E2FFE0"), (20, "#D2FFC9"), (30, "#C0FFB1"), (40, "#A4FF90"),
                    (50, "#78FF4F"), (60, "#68DE45"), (70, "#54B337"), (80, "#3C8027"),
                    (90, "#2B5C1C"), (100, "#1D3D13")],
    # 無黨籍（45% 起灰階）
    "無": [(45, "#F0F0F0"), (50, "#E0E0E0"), (55, "#D0D0D0"), (60, "#C0C0C0"),
           (65, "#B1B1B1"), (70, "#A1A1A1"), (75, "#929292"), (80, "#737373"),
           (85, "#646464")],
}
# B 版：20 資料夾
STOPS_B = {
    "中國國民黨": [(35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"), (50, "#40C8FF"),
                    (55, "#00C0F4"), (60, "#00A2E8"), (65, "#0080B8"), (70, "#006591"),
                    (75, "#004B6B"), (80, "#003247"), (85, "#001F2E"), (100, "#010D29")],
    "民主進步黨": [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
                    (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
                    (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
    # 無黨籍（0-10 … 90-100 灰階，10 段）
    "無": [(10, "#F0F0F0"), (20, "#E0E0E0"), (30, "#D0D0D0"), (40, "#C0C0C0"),
           (50, "#B1B1B1"), (60, "#A1A1A1"), (70, "#929292"), (80, "#737373"),
           (90, "#646464"), (100, "#555555")],
}
# B 版 無黨籍 各段圖例標籤（0-10 … 90-100）
IND_LABELS_B = ["0-10", "10-20", "20-30", "30-40", "40-50",
                "50-60", "60-70", "70-80", "80-90", "90-100"]

GRAY_COLOR = "#CCCCCC"

# ---------------- 繪圖參數 ----------------
VILL_LINE_PX, TOWN_LINE_PX, DISTRICT_LINE_PX = 1, 4, 6
ERASE_PAD_PX = 2
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2
GRAY_PAD_MARGIN = 6        # 灰色無資料區外緣補充

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LEGEND_PADDING = 60
COLUMN_TITLE_GAP = 100
TITLE_GAP = 70
TITLE_FONT_SIZE = 100
CAND_NAME_FONT_SIZE = 84
LEGEND_LABEL_FONT_SIZE = 56

W_TEXT_CACHE = {}

# ---------------- 正規化 / 異體字 ----------------
VARIANT_MAP = str.maketrans({
    '濓': '濂',
    '𥕢': '曹',      # 龍崎區 石[𥕢]/石[曹]
    '𦰡': '那',      # 新化區 [𦰡]拔/[那]拔
    '檨': '檨',      # 西港區 [檨]林道(檨林)
    '\ue006': '塭',  # 安南區 公[\ue006]/公[塭]・[\ue006]南/[塭]南
})

_CJK_KEEP = re.compile(
    r'[^\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF'
    r'\U00020000-\U0002A6DF\U0002A700-\U0002B73F'
    r'\U0002F800-\U0002FA1F]')


def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_MAP)
    return s


def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))


def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))


def clean_cjk(s):
    return "" if pd.isna(s) else _CJK_KEEP.sub('', normalize_text(s))


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def get_color_by_value(val, stops):
    if val is None or np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def resolve_shp():
    return SHP_PATH


# ---------------- 文字圖片（Print_word.py 方式） ----------------
def render_text_image(text_lines, font_size=64, dpi=100):
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


def render_text_image_cached(text_lines, font_size):
    key = (tuple(text_lines), font_size)
    if key not in W_TEXT_CACHE:
        W_TEXT_CACHE[key] = render_text_image(text_lines, font_size=font_size)
    return W_TEXT_CACHE[key]


def blit_rgba(base_img, rgba_img, xy):
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))


# ---------------- 填充小白點（保護白帶） ----------------
WHITE_THRESH, MAX_WHITE_BLOB_PX, RING_ITER = 250, 2000, 2


def fill_small_white_blobs(img, protect_mask=None):
    h, w = img.shape[:2]
    mask = np.all(img >= WHITE_THRESH, axis=2).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    res = img.copy(); filled = 0
    kernel = np.ones((3, 3), np.uint8)
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if area > MAX_WHITE_BLOB_PX:
            continue
        if x == 0 or y == 0 or (x + bw) == w or (y + bh) == h:
            continue
        cm = (labels == i).astype(np.uint8)
        if protect_mask is not None and np.any(protect_mask & cm.astype(bool)):
            continue
        dil = cv2.dilate(cm, kernel, iterations=RING_ITER)
        rm = (dil > 0) & (cm == 0)
        rp = img[rm]
        if len(rp) == 0:
            continue
        nw = rp[~np.all(rp >= WHITE_THRESH, axis=1)]
        if len(nw) == 0:
            continue
        colors, counts = np.unique(nw.reshape(-1, 3), axis=0, return_counts=True)
        res[cm.astype(bool)] = colors[np.argmax(counts)]
        filled += 1
    return res, filled


# ---------------- 讀取 Excel：候選人得票率 ----------------
CAND_RE = re.compile(r"^(.*)\(([^()]*)\)得票率$")


def load_rates():
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    df.columns = [str(c) for c in df.columns]
    rate_cols = [c for c in df.columns if c.endswith("得票率")]
    cand_meta = []
    for c in rate_cols:
        m = CAND_RE.match(c)
        if not m:
            raise ValueError("無法解析候選人欄名: %s" % c)
        cand_meta.append((m.group(1), m.group(2), c))
    # 找出各里『領先者』所在欄位（無黨籍/高得票率者皆納入）
    winners = set()
    for _, r in df.iterrows():
        vals = {c: r[c] for c in rate_cols if pd.notna(r[c])}
        if vals:
            winners.add(max(vals, key=vals.get))
    sel = [(n, p, c) for n, p, c in cand_meta if c in winners]
    df["town_core"] = df["鄉(鎮、市、區)別"].apply(strip_town_suffix)
    df["vill_core"] = df["村里別"].apply(strip_village_suffix)
    df["district"] = df["選舉區別"].astype(str).str.extract(r"第(\d+)選舉區").astype(float)
    return df, sel


# ---------------- 匹配 ----------------
MIN_SIMILARITY = 0.5


def fuzzy_lookup(town, vill, vote_dict, vote_by_town):
    tn, vn = normalize_text(town), normalize_text(vill)
    if (tn, vn) in vote_dict:
        return vill, vote_dict[(tn, vn)], "exact"
    vc = clean_cjk(vn)
    if not vc:
        return None, None, "none"
    best_v, best_val, best_r = None, None, -1.0
    for cand, val in vote_by_town.get(tn, []):
        cc = clean_cjk(cand)
        if not cc:
            continue
        if cc == vc:
            return cand, val, f"fuzzy:{cand}(1.00)"
        r = SequenceMatcher(None, vc, cc).ratio()
        if r > best_r:
            best_r, best_v, best_val = r, cand, val
    if best_val is None or best_r < MIN_SIMILARITY:
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_r:.2f})"


# 台南区域含乡镇市区地图.txt 之選區對照（東區需里級，作為無法由 Excel 取得時之備援）
district_full_town_raw = {
    "後壁區": 1, "白河區": 1, "北門區": 1, "學甲區": 1, "鹽水區": 1,
    "新營區": 1, "柳營區": 1, "東山區": 1, "將軍區": 1, "下營區": 1, "六甲區": 1,
    "七股區": 2, "佳里區": 2, "麻豆區": 2, "官田區": 2, "善化區": 2,
    "大內區": 2, "玉井區": 2, "楠西區": 2, "西港區": 2, "安定區": 2,
    "山上區": 2, "左鎮區": 2, "南化區": 2,
    "安南區": 3, "北區": 3,
    "新市區": 4, "永康區": 4, "新化區": 4,
    "安平區": 5, "中西區": 5, "南區": 5,
    "仁德區": 6, "歸仁區": 6, "關廟區": 6, "龍崎區": 6}
district_full_town = {strip_town_suffix(t): d for t, d in district_full_town_raw.items()}


def build_district_map(df):
    """由 Excel（選舉區別）建 (town_core, vill_core) → 選區；再以 txt 對照補滿東區以外。"""
    dmap = {}
    for _, r in df.iterrows():
        if pd.notna(r["district"]):
            dmap[(r["town_core"], r["vill_core"])] = int(r["district"])
    return dmap


# ---------------- 圖例 ----------------
def get_label_text_A(upper, prev=None):
    return f"≤{upper}%" if prev is None else f"{prev}~{upper}%"


def get_label_text_B(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev is not None and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"


def draw_legend(final_img, x0, y0, cand_names, stops_list, ind_flags, labels_list,
                col_width, mode, start_tier=0):
    draw_obj = ImageDraw.Draw(final_img)
    n = len(cand_names)
    pos = [x0 + i * (col_width + H_SPACING) for i in range(n)]
    name_h = max((render_text_image_cached([nm], CAND_NAME_FONT_SIZE).height for nm in cand_names),
                 default=0)
    for ci, stops in enumerate(stops_list):
        x_start = pos[ci]
        nm_img = render_text_image_cached([cand_names[ci]], CAND_NAME_FONT_SIZE)
        blit_rgba(final_img, nm_img, (x_start + (BLOCK_WIDTH - nm_img.width) / 2, y0))
        for i, (upper, hx) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle([x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                               fill=hx, outline="#000000", width=1)
            if labels_list[ci] is not None:
                label = labels_list[ci][i]
            elif mode == "A":
                label = get_label_text_A(upper, stops[i - 1][0] if i > 0 else start_tier)
            else:
                label = get_label_text_B(upper, stops[i - 1][0] if i > 0 else start_tier,
                                         is_first=(i == 0), is_last=(i == len(stops) - 1))
            limg = render_text_image_cached([label], LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))


def make_map(mode):
    stops_by_party = STOPS_A if mode == "A" else STOPS_B
    MPP = 20 if mode == "A" else 10          # A=20m/px(資料夾10)  B=10m/px(資料夾20)
    MAX_SAFE_PX = 32000
    OUT_PNG = os.path.join(BASE, f"臺南市第十一屆立法委員_得票率地圖_{mode}版.png")

    print("=" * 62)
    print(f"  版本 {mode}：{OUT_PNG}")
    print("=" * 62)

    gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    if gdf_all.crs.is_geographic:
        gdf_all = gdf_all.to_crs(epsg=3826)

    gdf = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(CITY_NAME, na=False)].copy()
    if len(gdf) == 0:
        raise ValueError("SHP 中未找到臺南市")
    gdf["town_core"] = gdf["TOWNNAME"].apply(strip_town_suffix)
    gdf["vill_core"] = gdf["VILLNAME"].apply(strip_village_suffix)

    df_vote, sel = load_rates()
    rate_cols = [c for _, _, c in sel]
    cand_names = [n for n, _, _ in sel]
    cand_parties = [p for _, p, _ in sel]
    n_cand = len(sel)

    vote_dict = {
        (r["town_core"], r["vill_core"]): tuple(r[c] for c in rate_cols)
        for _, r in df_vote.iterrows()
    }
    vote_by_town = {}
    for (t, v), vals in vote_dict.items():
        vote_by_town.setdefault(t, []).append((v, vals))
    dmap = build_district_map(df_vote)

    # 匹配：Excel 里名 → SHP 里名
    def process_row(r):
        town, vill = r["town_core"], r["vill_core"]
        mv, vals, mt = fuzzy_lookup(town, vill, vote_dict, vote_by_town)
        if vals is None:
            vals = tuple(np.nan for _ in range(n_cand))
        d = dmap.get((town, mv)) if mv is not None else dmap.get((town, vill))
        if d is None:
            d = district_full_town.get(town)
        if d is None:
            d = np.nan
        return pd.Series(list(vals) + [mt, d],
                         index=list(rate_cols) + ["match_type", "district"])

    res = gdf.apply(process_row, axis=1)
    gdf[rate_cols] = res[rate_cols]
    gdf["match_type"] = res["match_type"]
    gdf["district"] = res["district"]

    has_data = gdf[rate_cols].notna().any(axis=1)
    gdf_with_data = gdf[has_data].copy()
    gdf_no_data = gdf[~has_data].copy()

    if len(gdf_with_data) == 0:
        raise ValueError("沒有任何村里資料匹配成功")

    # ---- 選區多邊形（全部 SHP 里依選區 dissolve，保證白帶完整）----
    gdf_all_dist = gdf[gdf["district"].notna()]
    districts_gdf = gdf_all_dist.dissolve(by="district", aggfunc="first")

    # ---- 填色：勝出候選人得票率 → 依其政黨色階 ---- 
    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], stops_by_party[cand_parties[i]])

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0
    step = 10 if mode == "A" else 5
    legend_start_tier = int(min_win_rate // step) * step

    # ---- 統計 ----
    exact_cnt = int((gdf["match_type"] == "exact").sum())
    fuzzy_cnt = int(gdf["match_type"].astype(str).str.startswith("fuzzy", na=False).sum())
    none_cnt = int((gdf["match_type"] == "none").sum())
    print(f"  SHP 村里要素     : {len(gdf)}")
    print(f"  Excel 有效記錄   : {len(df_vote)}  (候選人/政黨欄 {n_cand} 位)")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    print(f"  無匹配           : {none_cnt}")
    print(f"  有資料           : {len(gdf_with_data)}")
    print(f"  最低領先得票率   : {min_win_rate:.2f}% → 圖例起 {legend_start_tier}%")

    # ---- 無資料村里著色 ----
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != ""))
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)
    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    # ===================== 繪製地圖 =====================
    minx, miny, maxx, maxy = gdf_plot.total_bounds
    MAP_PAD_FRAC = 0.03
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)
    w_px = int(np.ceil((xlim[1] - xlim[0]) / MPP))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / MPP))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}")

    DPI = 100
    PX2PT = 72.0 / DPI
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    dist_half_m = DISTRICT_LINE_PX * MPP / 2
    town_half_m = TOWN_LINE_PX * MPP / 2
    erase_half_m = dist_half_m + ERASE_PAD_PX * MPP

    city_geom = gdf_plot.geometry.union_all()
    district_rows = gdf_plot[gdf_plot["district"].notna()].copy()
    if district_rows.empty:
        raise ValueError("無選區資料")
    # dissolve 需包含所有里；無資料里也可能有選區
    all_rows_dist = gdf[gdf["district"].notna()]
    districts_bd = all_rows_dist.dissolve(by="district", aggfunc="first").boundary.union_all()

    erase_geom = districts_bd.buffer(erase_half_m, resolution=BUF_RES,
                                     join_style=BUF_JOIN, cap_style=BUF_CAP)

    gray_mask = gdf_plot["fill_hex"] == GRAY_COLOR
    gray_pad = (gdf_plot.loc[gray_mask, "geometry"].union_all().buffer(
        dist_half_m + GRAY_PAD_MARGIN * MPP, resolution=BUF_RES,
        join_style=BUF_JOIN, cap_style=BUF_CAP)
        if gray_mask.any() else None)
    exclude = erase_geom if gray_pad is None else erase_geom.union(gray_pad)

    # ① 村里填色（無邊）
    gdf_plot.plot(ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
                  edgecolor='none', linewidth=0, antialiased=False, legend=False)

    # ② 村里黑線（1px，扣除擦除帶）
    village_lines = gdf_plot.boundary.union_all().difference(exclude)
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(ax=ax, edgecolor='black', facecolor='none',
                                            linewidth=VILL_LINE_PX * PX2PT,
                                            antialiased=False, zorder=5)

    # ③ 鄉鎮市區黑線（4px，扣除擦除帶）
    town_lines = gdf_plot.dissolve(by="town_core").boundary.union_all().difference(exclude)
    if not town_lines.is_empty:
        town_band = town_lines.buffer(town_half_m, resolution=BUF_RES,
                                      join_style=BUF_JOIN, cap_style=BUF_CAP
                                      ).intersection(city_geom)
        if not town_band.is_empty:
            gpd.GeoSeries([town_band]).plot(ax=ax, facecolor='black', edgecolor='none',
                                            linewidth=0, antialiased=False, zorder=9)

    # ④ 立法委員選區白帶（6px）
    white_band = None
    white_lines = districts_bd if gray_pad is None else districts_bd.difference(gray_pad)
    if not white_lines.is_empty:
        wb = white_lines.buffer(dist_half_m, resolution=BUF_RES,
                                join_style=BUF_JOIN, cap_style=BUF_CAP
                                ).intersection(city_geom)
        if not wb.is_empty:
            white_band = wb
            gpd.GeoSeries([wb]).plot(ax=ax, facecolor='white', edgecolor='none',
                                     linewidth=0, antialiased=False, zorder=10)

    # ⑤ 市外輪廓（6px 黑帶）
    outer = city_geom.boundary.buffer(dist_half_m, resolution=BUF_RES,
                                      join_style=BUF_JOIN, cap_style=BUF_CAP)
    if not outer.is_empty:
        gpd.GeoSeries([outer]).plot(ax=ax, facecolor='black', edgecolor='none',
                                    linewidth=0, antialiased=False, zorder=11)

    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)
    img_rgb = cv2.cvtColor(
        cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR),
        cv2.COLOR_BGR2RGB)

    # ---- 保護 mask（白帶位置）----
    fig_m = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax_m = fig_m.add_axes([0, 0, 1, 1])
    ax_m.set_xlim(*xlim)
    ax_m.set_ylim(*ylim)
    ax_m.set_facecolor("#000000")
    if white_band is not None:
        gpd.GeoSeries([white_band]).plot(ax=ax_m, facecolor='white', edgecolor='none',
                                         linewidth=0, antialiased=False)
    ax_m.axis("off")
    buf_m = BytesIO()
    plt.savefig(buf_m, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#000000")
    plt.close(fig_m)
    buf_m.seek(0)
    mask_rgb = cv2.cvtColor(
        cv2.imdecode(np.frombuffer(buf_m.getvalue(), np.uint8), cv2.IMREAD_COLOR),
        cv2.COLOR_BGR2RGB)
    protect_mask = np.all(mask_rgb >= WHITE_THRESH, axis=2)

    # ---- 顏色量化 ----
    allowed_hex = {"#FFFFFF", "#000000", GRAY_COLOR}
    for stops in stops_by_party.values():
        allowed_hex.update(hx for _, hx in stops)
    allowed_rgb = np.array([hex2rgb(h) for h in allowed_hex]).astype(np.float32) * 255
    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    n_px = pixels.shape[0]
    CHUNK = 500_000
    quantized = np.empty((n_px, 3), dtype=np.uint8)
    for s in range(0, n_px, CHUNK):
        e = min(s + CHUNK, n_px)
        chunk = pixels[s:e]
        dist = np.full(chunk.shape[0], np.inf, dtype=np.float32)
        idx = np.zeros(chunk.shape[0], dtype=np.int32)
        for i in range(allowed_rgb.shape[0]):
            d = np.sqrt(((chunk - allowed_rgb[i]) ** 2).sum(axis=1))
            m = d < dist
            dist[m] = d[m]
            idx[m] = i
        quantized[s:e] = allowed_rgb[idx].astype(np.uint8)
    quantized = quantized.reshape(img_rgb.shape)
    quantized, n_filled = fill_small_white_blobs(quantized, protect_mask=protect_mask)
    print(f"  ★ 已填平 {n_filled} 處小白點")

    # ===================== 圖例與標題 =====================
    # 各候選人欄色階與標籤
    stops_list, labels_list, ind_flags = [], [], []
    for party in cand_parties:
        stops = list(stops_by_party[party])
        if mode == "A":
            stops_f = [(u, c) for u, c in stops if u > legend_start_tier]
            stops_list.append(stops_f)
            labels_list.append(None)
            ind_flags.append(False)
        else:
            if party == "無":
                stops_list.append(stops)             # 全程 0-10…90-100
                labels_list.append(list(IND_LABELS_B))
                ind_flags.append(True)
            else:
                stops_f = [(u, c) for u, c in stops if u > legend_start_tier]
                stops_list.append(stops_f)
                labels_list.append(None)
                ind_flags.append(False)

    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size
    title_img = render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)

    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    label_img_cols = []
    for ci, stops in enumerate(stops_list):
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            if labels_list[ci] is not None:
                txt = labels_list[ci][i]
            elif mode == "A":
                txt = get_label_text_A(u, stops[i - 1][0] if i > 0 else legend_start_tier)
            else:
                txt = get_label_text_B(u, stops[i - 1][0] if i > 0 else legend_start_tier,
                                       is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])
    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(cand_names)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING
    panel_content_h = title_img.height + TITLE_GAP + legend_h

    if mode == "A":
        # 資料夾10 佈局：圖例自 W+75 起，標題置中於圖例區域
        LEGEND_X_MARGIN = 75
        legend_x = W + LEGEND_X_MARGIN
        title_x_rel = (total_legend_w - title_img.width) // 2
        content_w = max(title_x_rel + title_img.width, total_legend_w)
        right_panel_w = LEGEND_X_MARGIN + content_w + LEGEND_PADDING
    else:
        # 資料夾20 佈局：圖例自 W+115 起，標題對齊圖例群組中心
        group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
        legend_x = W + 115
        title_x_rel = int((group_w - title_img.width) / 2)
        title_right = legend_x + title_x_rel + title_img.width
        right_panel_w = int(max(title_right + LEGEND_PADDING, legend_x + group_w + LEGEND_PADDING) - W)

    new_W = W + right_panel_w
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    py = LEGEND_PADDING
    blit_rgba(final_img, title_img, (legend_x + title_x_rel, py))
    py += title_img.height + TITLE_GAP
    draw_legend(final_img, legend_x, py, cand_names, stops_list, ind_flags, labels_list,
                col_width, mode, start_tier=legend_start_tier)

    final_img.save(OUT_PNG)
    print(f"  輸出: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖 {len(gdf_with_data)} 里；色階起 {legend_start_tier}%；選區界白帶 {DISTRICT_LINE_PX}px\n")


if __name__ == "__main__":
    mode = sys.argv[1].strip().upper() if len(sys.argv) > 1 else "A"
    if mode not in ("A", "B"):
        raise SystemExit("請指定版本 A 或 B")
    make_map(mode)
    print("完成。")