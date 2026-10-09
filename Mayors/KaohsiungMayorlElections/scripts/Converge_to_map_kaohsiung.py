# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與「高雄市長得票率」Excel 結合，
繪製高雄市 2018 市長選舉各村里候選人得票率地圖（韓國瑜 vs 陳其邁）。

與 MayoralElections/scripts/Converge_to_map.py 的差異（針對高雄市）：
    * drop_nan_vill = True：SHP 中 VILLNAME 為 NaN / 空字串的区块
      （「未編定村里」、旗津區代管離島等無地名區塊）一律排除，不上圖。
    * 資料來源為自行爬蟲之 2018 高雄市長選舉村里資料。

資料格式（各里彙總 工作表）：
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率
得票率(%) = 候選人得票數 ÷ 有效票數A × 100

色階自 45% 起跳：得票率未達 45% 不著色（以灰色顯示）。
候選人數量由 Excel 自動偵測，圖例欄數隨之調整。

執行：
    py Converge_to_map_kaohsiung.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import numpy as np
import re
import cv2
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from difflib import SequenceMatcher
import unicodedata
import warnings

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# ===================== 字体设置 =====================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
MAPS_DIR = os.path.join(os.path.dirname(BASE_DIR), "maps")

# ===================== 配置区 =====================
SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

# 要生成的地圖（高雄市長選舉）
DATASETS = [
    {
        "excel": os.path.join(EXCEL_DIR, "2018高雄市長_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "高雄市",
        "out": os.path.join(MAPS_DIR, "高雄市2018年市長選舉_得票率地圖.png"),
        "tag": "2018 高雄市長選舉（中國國民黨：韓國瑜 / 民主進步黨：陳其邁）",
        "title_lines": ["第三屆高雄市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["韓國瑜", "陳其邁"],
        "drop_nan_vill": True,   # 排除 SHP 中無地名（VILLNAME 為 NaN/空）的区块
    },
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 10, 32000   # 1px = 10m
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
OUTER_LINE_PX = 6             # 市外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階（45% 起跳）=====================
RATE_COLOR_STOPS = [
    [(45, "#00F2FF"), (50, "#00E6FF"), (55, "#00DAFF"), (60, "#00C0F4"),
     (65, "#00A2E8"), (70, "#0080B8"), (75, "#006591"), (80, "#004B6B"), (85, "#003247")],
    [(45, "#CEFFC2"), (50, "#C0FFB1"), (55, "#A4FF90"), (60, "#78FF4F"),
     (65, "#68DE45"), (70, "#54B337"), (75, "#3C8027"), (80, "#2B5C1C"), (85, "#1D3D13")],
    [(45, "#00EBD1"), (50, "#00D9CA"), (55, "#00BFB2"),
     (60, "#00A89C"), (65, "#008080"), (70, "#006666"), (75, "#004C4C")],
]

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LABEL_FONT_SIZE, LEGEND_PADDING = 36, 60
COLUMN_TITLE_GAP = 100      # 圖例欄標題（候選人）與第一個色塊的間距

# ---- 所有文字皆以 Print_word.py 方式輸出，以下字級可依需求適度調整 ----
TITLE_FONT_SIZE = 100        # 標題字級
CAND_NAME_FONT_SIZE = 84     # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE = 56  # 圖例數值標籤（≤45%、45~50%…）字級
NO_DATA_FONT_SIZE = 44       # 無資料說明字級

# ===================== 工具函数 =====================
# 異體字/音同字異 正規化對照（表格資料 vs 圖資用字不同，需先統一）
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',     # 坪林區石[曹] / 石槽
    '磘': '窯',     # 中和區瓦[磘]・灰[磘]
    '獇': '羌',     # 樹林區[獇]寮 / 羌寮
    '舘': '館',     # 板橋區公舘 / 三峽區永舘
    '廍': '部',     # 永和區新廍 / 新部
    '峯': '峰',     # 土城區峯廷 / 新店區五峯 / 瑞芳區爪峯
    '脚': '腳',     # 萬里區崁脚 / 崁腳
    '豊': '豐',     # 內門區內豊 / 內豐（2018高雄）
})

def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    # 圖資以方括號標註疑難字（如 瓦[磘]里），括號本身非地名一部分，去除
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
    if val < stops[0][0]:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]

def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)

def text_width(font, txt):
    try:
        bbox = font.getbbox(txt)
    except AttributeError:
        bbox = font.getmask(txt).getbbox()
    return (bbox[2] - bbox[0]) if bbox else 0

def resolve_shp():
    for p in SHP_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("找不到村里界 SHP：" + "、".join(SHP_CANDIDATE_PATHS))

# ===================== 文字圖片生成（仿 Print_word.py） =====================
def render_text_image(text_lines, font_size=64, dpi=100):
    """以 Print_word.py 方式：Matplotlib 繪字 → OpenCV 二值化 → 透明背景。

    回傳 PIL RGBA（文字不透明黑、背景透明），可直接 paste 到地圖。
    """
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    font_name = None
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            font_name = n
            break
    # 用字型鏈回退：中文字用 CJK 字型，缺少的符號（如 ≤ U+2264）由 DejaVu Sans 補
    font_family = [font_name, "DejaVu Sans"] if font_name else "DejaVu Sans"

    # 測量文字尺寸
    fig_temp = plt.figure(figsize=(1, 1), dpi=dpi)
    ax_temp = fig_temp.add_subplot(111)
    ax_temp.axis("off")
    fig_temp.canvas.draw()
    renderer = fig_temp.canvas.get_renderer()
    line_widths = []
    line_heights = []
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
    result = np.zeros((h, w, 4), dtype=np.uint8)   # B,G,R = 0（黑字）
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))

_TEXT_IMG_CACHE = {}

def render_text_image_cached(text_lines, font_size):
    """快取版 render_text_image：相同文字與字級只渲染一次（Print_word.py 方式）。"""
    key = (tuple(text_lines), font_size)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size)
    return _TEXT_IMG_CACHE[key]

def blit_rgba(base_img, rgba_img, xy):
    """將透明底 RGBA 文字圖以 alpha 為遮罩貼到 base_img 的 (x, y)。"""
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))

# ===================== 读 SHP =====================
SHP_PATH = resolve_shp()
gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
if gdf_all.crs.is_geographic:
    gdf_all = gdf_all.to_crs(epsg=3826)

for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]:
    if c not in gdf_all.columns:
        raise ValueError(f"SHP缺失必要字段：{c}")

# ===================== 读取高雄格式得票 Excel，计算得票率 =====================
def _norm_text(v):
    """正規化：NaN / 'nan'(不區分大小寫) 一律視為空字串（缺失）。"""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s

def load_rates(cfg):
    excel_path = cfg["excel"]
    df = pd.read_excel(excel_path, sheet_name=cfg["sheet"], header=cfg.get("header", 0))
    df.columns = [str(c) for c in df.columns]

    # 支援三種來源：
    #  ① 得票率專用檔：欄位直接是「<政黨>得票率」
    #  ② 高雄格式全量檔：<候選人>得票數 ＋ 有效票數A，再除以 A×100 得得票率
    #  ③ 指定候選人欄位（cfg["cand_columns"]）：欄名即候選人、值為得票率(%)
    pct_cols = [c for c in df.columns if c.endswith("得票率")]
    vote_cols = [c for c in df.columns if c.endswith("得票數")]
    given_cands = cfg.get("cand_columns")

    if given_cands:
        cand_cols = list(given_cands)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = pd.to_numeric(df[c], errors="coerce")
    elif pct_cols:
        cand_cols = pct_cols
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = pd.to_numeric(df[c], errors="coerce")
    elif vote_cols:
        if "有效票數A" not in df.columns:
            raise ValueError(f"{excel_path} 缺少『有效票數A』欄位")
        cand_cols = vote_cols
        A = pd.to_numeric(df["有效票數A"], errors="coerce")
        rate_cols = []
        for i, c0 in enumerate(cand_cols):
            rname = f"rate{i + 1}"
            rate_cols.append(rname)
            df[rname] = pd.to_numeric(df[c0], errors="coerce") / A * 100.0
    else:
        raise ValueError(f"{excel_path} 找不到『得票率』或『得票數』欄位")

    df["縣市"] = df[cfg.get("col_city", "選舉區別")].apply(_norm_text)
    df["鄉鎮市區"] = df[cfg.get("col_town", "鄉(鎮、市、區)別")].apply(_norm_text)
    df["區里"] = df[cfg.get("col_vill", "村里別")].apply(_norm_text)

    df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
    df["vill_core"] = df["區里"].apply(strip_village_suffix)
    return df, cand_cols, rate_cols

# ===================== 精确 + 同乡镇最相似模糊匹配 =====================
MIN_SIMILARITY = 0.5

def fuzzy_lookup(town, vill, by_key, by_town):
    if not town or not vill:
        return None, None, "none"
    key = (town, vill)
    if key in by_key:
        return vill, by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get(town, []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"

# ===================== 逐張地圖繪製 =====================
def draw_legend_on(final_img, x0, y0, cand_names, stops_list, col_width, max_label_w):
    """圖例：色塊用 ImageDraw 繪製；所有文字以 Print_word.py 方式（render_text_image）貼上。"""
    draw_obj = ImageDraw.Draw(final_img)
    n = len(cand_names)
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(n)]
    name_h = max(
        (render_text_image_cached([nm], CAND_NAME_FONT_SIZE).height for nm in cand_names),
        default=0,
    )
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_text_image_cached([cand_names[col_idx]], CAND_NAME_FONT_SIZE)
            blit_rgba(final_img, nm_img, (x_start + (BLOCK_WIDTH - nm_img.width) / 2, y0))
        for i, (upper, color_hex) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else None
            limg = render_text_image_cached([get_label_text(upper, prev)], LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))

def get_label_text(upper, prev=None):
    return f"≤{upper}%" if prev is None else f"{prev}~{upper}%"

def make_map(cfg):
    print("=" * 62)
    print(f"  組別：{cfg['tag']}")
    print("=" * 62)

    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(cfg["city"], na=False)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"SHP 中未找到 {cfg['city']} 數據")

    # ---- 高雄市特殊處理：排除 SHP 中無地名（VILLNAME 為 NaN / 空字串）的区块 ----
    dropped = 0
    if cfg.get("drop_nan_vill", False):
        nan_mask = gdf_nt["VILLNAME"].isna() | (gdf_nt["VILLNAME"].astype(str).str.strip() == "")
        dropped = int(nan_mask.sum())
        gdf_nt = gdf_nt[~nan_mask].copy()
        print(f"  ※ 依 drop_nan_vill 排除無地名区块 {dropped} 個（未編定村里 / 代管離島）")

    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols = load_rates(cfg)
    # 納入 {city} 資料；縣市欄缺失(NaN / 'nan' 不區分大小寫)者視為同屬該縣市，一併納入
    city_mask = df_vote["縣市"].str.contains(cfg["city"], case=False, na=False)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask].copy()

    n_cand = len(cand_cols)
    cand_names = cfg.get("legend_names", [c[:-3] for c in cand_cols])   # 圖例欄名稱＝候選人
    stops_list = [RATE_COLOR_STOPS[i % len(RATE_COLOR_STOPS)] for i in range(n_cand)]

    vote_dict = {
        (r["town_core"], r["vill_core"]): tuple(r[c] for c in rate_cols)
        for _, r in df_vote.iterrows()
    }
    vote_by_town = {}
    raw_vote_by_town = {}
    for (t, v), vals in vote_dict.items():
        vote_by_town.setdefault(t, []).append((v, vals))
    for _, r in df_vote.iterrows():
        raw_vote_by_town.setdefault(r["town_core"], {})[r["vill_core"]] = r["區里"]

    def process_row(r):
        town, vill = r["town_core"], r["vill_core"]
        matched_vill, vals, excel_mt = fuzzy_lookup(town, vill, vote_dict, vote_by_town)
        if vals is None:
            vals = tuple(np.nan for _ in range(n_cand))
            return pd.Series(list(vals) + ["none"])
        if excel_mt == "exact":
            raw_excel = raw_vote_by_town.get(town, {}).get(matched_vill)
            raw_shp = str(r["VILLNAME"])
            if raw_shp != raw_excel:
                excel_mt = f"variant:{raw_excel}"
        return pd.Series(list(vals) + [excel_mt])

    assign_cols = rate_cols + ["match_type"]
    gdf_nt[assign_cols] = gdf_nt.apply(process_row, axis=1)

    # 有任一候選人得票率可計算，即納入（NaN 以 0 計，不影響其餘候選人） 
    has_data = gdf_nt[rate_cols].notna().any(axis=1)
    gdf_with_data = gdf_nt[has_data].copy()
    gdf_no_data = gdf_nt[~has_data].copy()

    if len(gdf_with_data) == 0:
        raise ValueError(f"{cfg['excel']} 沒有任一村里資料匹配成功。")

    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], stops_list[i])

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    below_cnt = int(gdf_with_data["fill_hex"].isna().sum())
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 統計報告 ----
    exact_cnt = int((gdf_nt["match_type"] == "exact").sum())
    variant_cnt = int(gdf_nt["match_type"].str.startswith("variant", na=False).sum())
    fuzzy_cnt = int(gdf_nt["match_type"].str.startswith("fuzzy", na=False).sum())
    none_cnt = int((gdf_nt["match_type"] == "none").sum())
    cnt_valid = int(has_data.sum())
    no_data_cnt = int((~has_data).sum())

    print(f"  SHP 村里要素     : {len(gdf_nt)}")
    print(f"  Excel 有效記錄   : {len(df_vote)}   (候選人/政黨 {n_cand} 位)")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字匹配       : {variant_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    print(f"  無候選(無匹配)   : {none_cnt}")
    print(f"  有資料           : {cnt_valid}（其中得票率<45%未著色 {below_cnt} 個）")
    print(f"  無資料/部分缺失  : {no_data_cnt}")

    # 簡要說明異體字 / 模糊匹配情形
    for key, label in [("variant", "異體字匹配（SHP 用字與 Excel 不同，經正規化後配對）"),
                       ("fuzzy", "模糊匹配（同鄉鎮內字串相似度達 50% 以上）")]:
        sub = gdf_nt[gdf_nt["match_type"].str.startswith(key, na=False)]
        if len(sub) == 0:
            continue
        print(f"  ■ {label}：共 {len(sub)} 個")
        for _, r in sub.head(8).iterrows():
            if key == "variant":
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  →  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  →  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    no_data_by_town = gdf_no_data.groupby("TOWNNAME").size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】")
        for town, cnt2 in no_data_by_town.items():
            print(f"  {town}: {cnt2} 個村里")

    # ===================== 繪圖 =====================
    # 無資料村里著色規則：
    #   SHP 有、Excel 沒有 —— 有具體地名者（當時因行政沿革尚未設立）→ 白色
    #   （NaN 無地名区块已於上方依 drop_nan_vill 排除，不再上圖）
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != "")
    )
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)

    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    minx, miny, maxx, maxy = gdf_plot.total_bounds
    MAP_PAD_FRAC = 0.03
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}，請調大 METERS_PER_PIXEL")

    DPI = 100
    PX2PT = 72.0 / DPI

    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = gdf_plot.geometry.union_all()

    # ① 村里填色（無邊）
    gdf_plot.plot(
        ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 村里黑線（1px）
    village_lines = gdf_plot.boundary.union_all()
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=VILL_LINE_PX * PX2PT, antialiased=False, zorder=5
        )

    # ③ 鄉鎮市區黑線（4px 黑帶）
    town_lines = gdf_plot.dissolve(by="town_core").boundary.union_all()
    if not town_lines.is_empty:
        town_band = town_lines.buffer(
            town_half_m, resolution=BUF_RES,
            join_style=BUF_JOIN, cap_style=BUF_CAP
        ).intersection(city_geom)
        if not town_band.is_empty:
            gpd.GeoSeries([town_band]).plot(
                ax=ax, facecolor='black', edgecolor='none',
                linewidth=0, antialiased=False, zorder=9
            )

    # ④ 市外輪廓（6px 黑帶）
    outer = city_geom.boundary.buffer(
        outer_half_m, resolution=BUF_RES,
        join_style=BUF_JOIN, cap_style=BUF_CAP
    )
    if not outer.is_empty:
        gpd.GeoSeries([outer]).plot(
            ax=ax, facecolor='black', edgecolor='none',
            linewidth=0, antialiased=False, zorder=11
        )

    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)

    img_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # ===================== 顏色量化（分塊處理）=====================
    allowed_hex = {"#FFFFFF", "#000000", GRAY_COLOR}
    for stops in stops_list:
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

    # ===================== 文字圖像（全部以 Print_word.py 方式產生） =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size

    title_img = render_text_image_cached(cfg["title_lines"], TITLE_FONT_SIZE) if cfg.get("title_lines") else None

    # 圖例欄標題（候選人名稱）
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 各候選人欄的色階標籤
    label_img_cols = []
    for stops in stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else None)
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    gray_label_img = render_text_image_cached(["未達45% 或無數據"], LEGEND_LABEL_FONT_SIZE)
    max_label_w = max([im.width for col in label_img_cols for im in col] + [gray_label_img.width])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max(len(s) for s in stops_list)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ===================== 畫布佈局（右側面板：標題 → 圖例） =====================
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    panel_content_w = max(
        title_img.width if title_img else 0,
        group_w + 2 * (col_width - BLOCK_WIDTH),   # 置中後仍能容納最右欄的數值標籤
    )
    right_panel_w = panel_content_w + 2 * LEGEND_PADDING
    TITLE_GAP = 70
    panel_content_h = ((title_img.height + TITLE_GAP) if title_img else 0) + legend_h

    new_W = W + right_panel_w
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    # 右側面板：標題置中於面板最上方（緊鄰圖例）
    px0 = W + LEGEND_PADDING
    py = LEGEND_PADDING
    if title_img:
        blit_rgba(final_img, title_img, (px0 + (panel_content_w - title_img.width) / 2, py))
        py += title_img.height + TITLE_GAP

    legend_x = px0 + (panel_content_w - group_w) / 2
    draw_legend_on(final_img, legend_x, py, cand_names, stops_list, col_width, max_label_w)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；色階 45% 起跳；排除無地名区块 {dropped} 個\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")