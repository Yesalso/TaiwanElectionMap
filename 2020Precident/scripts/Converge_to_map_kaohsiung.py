# -*- coding: utf-8 -*-
"""
將村里界 SHP（108 版，與 2020 選舉同期）與「2020 總統副總統選舉」得票 Excel 結合，
繪製 臺北市・基隆市・新北市・宜蘭縣・桃園市 各村里候選人得票率地圖。

資料格式（村里層級明細 工作表）：
    縣市 | 鄉鎮市區 | 村里 | <候選人>（0N）_得票數 ... | <候選人>（0N）_得票率
得票率欄位直接採用（% 字串 → 數值）。

色階 35% 起（5% 間距）。
候選人數量由 Excel 自動偵測；未在任何村里領先的候選人不列入圖例。
比例尺：1px = 30m。

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
from shapely.geometry import Polygon, MultiPolygon
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
    # 108 版（2019/11）：與 2020 選舉年份一致，優先採用
    r"D:\Windows\Documents\村里界歷史圖資_111\108\VILLAGE_MOI_1081121.shp",
    # 後備：111 版（2022/11）
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

# 要生成的地圖（2020 總統副總統選舉・北臺五縣市）
CITIES = ["臺北市", "基隆市", "新北市", "宜蘭縣", "桃園市"]
DATASETS = [
    {
        "excel": os.path.join(EXCEL_DIR, "2020總統副總統選舉_縣市鄉鎮村里.xlsx"),
        "sheet": "村里層級明細",
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "村里",
        "cities": CITIES,
        "out": os.path.join(MAPS_DIR, "臺北市·基隆市·新北市·宜蘭縣·桃園市2020年總統副總統選舉_得票率地圖.png"),
        "tag": "2020 總統副總統選舉（中國國民黨：韓國瑜 / 民主進步黨：蔡英文 / 親民黨：宋楚瑜）",
        "title_lines": [],           # 不顯示標題
        "legend_names": ["韓國瑜", "蔡英文", "宋楚瑜"],
        "drop_nan_vill": True,   # 排除 SHP 中無地名（VILLNAME 為 NaN/空）的区块
    },
]
# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 30, 32000   # 1px = 30m
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
COUNTY_LINE_PX = 5            # 县市界线宽（黑）
OUTER_LINE_PX = 5             # 海岸线／外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階（35% 起，5% 間距）=====================
RATE_COLOR_STOPS = [
    [   # 第 1 组：中国国民党候选人
        (35, "#D9F6FF"),
        (40, "#A6E9FF"),
        (45, "#73D9FF"),
        (50, "#40C8FF"),
        (55, "#00C0F4"),
        (60, "#00A2E8"),
        (65, "#0080B8"),
        (70, "#006591"),
        (75, "#004B6B"),
        (80, "#003247"),
        (85, "#001F2E"),
        (100, "#010D29"),
    ],
    [   # 第 2 组：民主进步党候选人
        (35, "#E8FFE0"),
        (40, "#CEFFC2"),
        (45, "#C0FFB1"),
        (50, "#A4FF90"),
        (55, "#78FF4F"),
        (60, "#68DE45"),
        (65, "#54B337"),
        (70, "#3C8027"),
        (75, "#2B5C1C"),
        (80, "#1D3D13"),
        (85, "#0F210A"),
        (100, "#071A09"),
    ],
    [   # 第 3 组：台湾民众党候选人（图中未出现）
        (35, "#B3FFF0"),
        (40, "#00EBD1"),
        (45, "#00D9CA"),
        (50, "#00BFB2"),
        (55, "#00A89C"),
        (60, "#008080"),
        (65, "#006666"),
        (70, "#004C4C"),
        (75, "#003838"),
        (80, "#003030"),
        (85, "#002626"),
        (100, "#021F1F"),
    ],
    [   # 第 4 组：黄新党王建煊
        (0,   "#FFFFEB"),
        (35,  "#FFFFEB"),
        (40,  "#FFF8CC"),
        (45,  "#FFF0A8"),
        (50,  "#FFE780"),
        (55,  "#FFDD55"),
        (60,  "#FFF200"),
        (65,  "#E6DA00"),
        (70,  "#BFB500"),
        (75,  "#999100"),
        (80,  "#736D00"),
        (85,  "#4D4900"),
        (100, "#383502"),
    ],
]

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LEGEND_PADDING = 60
MAP_LEGEND_GAP = 125      # 圖例與地圖之間距
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
    '\U00025562': '槽',   # 坪林區石𕢥里（2024 源資料） / 石槽
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

def county_key(s):
    """縣市鍵：正規化（不剝後綴，臺北市/新北市等全名比對）。"""
    return "" if pd.isna(s) else normalize_text(s)

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

    # 模式 ④：地名在單列完整路徑（如「臺北縣板橋市留侯里」），得票率為小數
    if cfg.get("loc_col") is not None and (cfg.get("rate_col") is not None or cfg.get("rate_cols")):
        loc_idx = str(cfg["loc_col"])
        rate_mult = cfg.get("rate_multiplier", 100)
        cand_names = cfg.get("legend_names", [""])
        rc_list = cfg.get("rate_cols") or [cfg["rate_col"]]
        rnames = []
        for i, rc in enumerate(rc_list):
            rname = f"rate_{cand_names[i]}" if i < len(cand_names) else f"rate{i + 1}"
            rnames.append(rname)
            df[rname] = pd.to_numeric(df[str(rc)], errors="coerce") * rate_mult

        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.+)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""

        parsed = df[loc_idx].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_names, rnames

    # 支援三種來源（原有邏輯）：
    #  ① 得票率專用檔：欄位直接是「<政黨>得票率」
    #  ② 高雄格式全量檔：<候選人>得票數 ＋ 有效票數A，再除以 A×100 得得票率
    #  ③ 指定候選人欄位（cfg["cand_columns"]）：欄名即候選人、值為得票率(%)
    #  ⑤ 鄉鎮市區層級檔（cfg["full_loc_col"]）：單一欄含完整路徑（如「臺北縣板橋市」），無村里資料
    pct_cols = [c for c in df.columns if c.endswith("得票率")]
    vote_cols = [c for c in df.columns if c.endswith("得票數")]
    given_cands = cfg.get("cand_columns")

    # 字串百分比（如 "51.54%"）→ 數值
    def _to_pct_numeric(v):
        if v is None:
            return np.nan
        s = str(v).strip()
        if s.endswith("%"):
            s = s[:-1]
        return pd.to_numeric(s, errors="coerce")

    if cfg.get("full_loc_col"):
        cand_cols = list(cfg.get("cand_columns") or pct_cols or vote_cols)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = df[c].apply(_to_pct_numeric)
        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.*)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""
        parsed = df[cfg["full_loc_col"]].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_cols, rate_cols

    if given_cands:
        cand_cols = list(given_cands)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    elif pct_cols:
        cand_cols = pct_cols
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
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

def _char_pairs(a, b):
    """回傳逐字對應 (a字, b字)；長度不同時補上長度差異標記。"""
    pairs = []
    la, lb = len(a), len(b)
    if la != lb:
        return None  # 長度不同：不視為異體字匹配
    for ca, cb in zip(a, b):
        pairs.append((ca, cb))
    return pairs

# 異體字模糊匹配表（模糊候選彼此間「單字異體」的許可字對）
# 格式：同一組內的字互為異體；用於 fuzzy（相似度≥50% 且逐字僅一案異體）
VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"},   # 瑞芳區爪峯/爪峰
    {"舘", "館"},   # 板橋區公舘/公館、三峽區永舘/永館
    {"磘", "窯"},   # 中和區瓦磘/瓦窯
    {"獇", "羌"},   # 樹林區獇寮/羌寮
    {"曹", "槽"},   # 坪林區石曹/石槽
    {"脚", "腳"},
]


def is_variant_fuzzy(a, b):
    """判斷兩個（core）里名是否屬『異體字模糊匹配』：
    相似度 ≥ MIN_SIMILARITY，且逐字比較中『最多一個字不相等，且該字對落在異體字組』。
    """
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False  # 長度不同（字數差）不視為異體字模糊
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    for group in VARIANT_FUZZY_GROUPS:
        if ca in group and cb in group:
            return True
    return False

def fuzzy_lookup(county, town, vill, by_key, by_town):
    if not county or not town or not vill:
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
    # 只有逐字差異恰好一個字且該字對屬異體字組，才接受模糊匹配；
    # 其餘「雖然相似度達 50% 但並非異體字」的情形，視為無資料（白底）。
    if not is_variant_fuzzy(vill, best_v):
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"

# ===================== 逐張地圖繪製 =====================
def draw_legend_on(final_img, x0, y0, cand_names, stops_list, col_width, max_label_w, start_tier=0):
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
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))

def get_label_text(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"

def make_map(cfg):
    print("=" * 62)
    print(f"  組別：{cfg['tag']}")
    print("=" * 62)

    # ---- 鎖定多縣市（cfg["cities"]；相容舊版單一 cfg["city"]） ----
    cities = [str(c).strip() for c in (cfg.get("cities") or [cfg["city"]])]
    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.strip().isin(cities)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"SHP 中未找到 {'、'.join(cities)} 數據")

    # ---- 排除 SHP 中無地名（VILLNAME 為 NaN / 空字串）的区块 ----
    dropped = 0
    if cfg.get("drop_nan_vill", False):
        nan_mask = gdf_nt["VILLNAME"].isna() | (gdf_nt["VILLNAME"].astype(str).str.strip() == "")
        dropped = int(nan_mask.sum())
        gdf_nt = gdf_nt[~nan_mask].copy()
        print(f"  ※ 依 drop_nan_vill 排除無地名区块 {dropped} 個（未編定村里 / 代管離島）")

    gdf_nt["county_core"] = gdf_nt["COUNTYNAME"].apply(county_key)
    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols = load_rates(cfg)
    # 只納入指定縣市；Excel 中縣市名可能與 SHP 不同（如舊檔臺北縣 vs 新北市），
    # 可用 excel_cities 覆寫。縣市欄缺失(NaN/'nan')者僅在單一縣市時視為同屬該縣市。
    excel_cities = [str(c).strip() for c in cfg.get("excel_cities", cities)]
    city_mask = df_vote["縣市"].astype(str).str.strip().isin(excel_cities)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask if len(excel_cities) == 1 else city_mask].copy()
    if len(df_vote) == 0:
        raise ValueError(f"{cfg['excel']} 中 {'、'.join(excel_cities)} 無任何資料")
    df_vote["county_core"] = df_vote["縣市"].apply(county_key)

    n_cand = len(cand_cols)
    cand_names = cfg.get("legend_names", [c[:-3] for c in cand_cols])   # 圖例欄名稱＝候選人
    # 依圖例名稱順序重排候選人欄位：確保位置式配色（如國黨藍/民進黨綠）對到正確候選人，
    # Excel 欄位順序可與圖例順序不同
    if cfg.get("legend_names"):
        def _cand_key(c):
            s = str(c)
            for suf in ("得票率", "得票數"):
                if s.endswith(suf):
                    s = s[:-len(suf)]
            return s
        key_map = {_cand_key(rc): rc for rc in rate_cols}
        new_rc, new_cc, used = [], [], set()
        for nm in cand_names:
            k = next((k for k in key_map if k == nm or nm in k or k in nm), None)
            if k is not None:
                rc = key_map[k]
                new_rc.append(rc)
                new_cc.append(rc)
                used.add(rc)
        rest = [c for c in rate_cols if c not in used]
        if len(new_rc) + len(rest) == len(rate_cols) and len(new_rc) == len(cand_names):
            rate_cols = new_rc + rest
            cand_cols = [c for c in rate_cols]
    if cfg.get("color_schemes"):
        stops_list = cfg["color_schemes"]
    else:
        stops_list = [RATE_COLOR_STOPS[i % len(RATE_COLOR_STOPS)] for i in range(n_cand)]

    # 鍵含縣市：避免跨縣市同名鄉鎮/村里互相撞名（如基隆/臺北 中山里、建國里）
    vote_dict = {
        (r["county_core"], r["town_core"], r["vill_core"]): tuple(r[c] for c in rate_cols)
        for _, r in df_vote.iterrows()
    }
    vote_by_town = {}
    raw_vote_by_town = {}
    for (cty, t, v), vals in vote_dict.items():
        vote_by_town.setdefault((cty, t), []).append((v, vals))
    for _, r in df_vote.iterrows():
        raw_vote_by_town.setdefault((r["county_core"], r["town_core"]), {})[r["vill_core"]] = r["區里"]

    # 鄉鎮市區層級資料：村里界無對應（Excel 僅到鄉鎮層級），以鄉鎮數值套用全鄉鎮村里
    town_level_only = bool(df_vote["vill_core"].str.strip().eq("").all())
    town_level_dict = {
        (cty, t): vals for (cty, t, v), vals in vote_dict.items() if not v
    }

    def process_row(r):
        county, town, vill = r["county_core"], r["town_core"], r["vill_core"]
        matched_vill, vals, excel_mt = fuzzy_lookup(county, town, vill, vote_dict, vote_by_town)
        if vals is None and (county, town) in town_level_dict:
            vals = town_level_dict[(county, town)]
            excel_mt = f"town:{town}"
        if vals is None:
            vals = tuple(np.nan for _ in range(n_cand))
            return pd.Series(list(vals) + ["none"])
        if excel_mt == "exact":
            raw_excel = raw_vote_by_town.get((county, town), {}).get(matched_vill)
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

    # ---- 圖例過濾：未在任何村里領先的候選人不列入圖例 ----
    if len(gdf_with_data):
        lead_arr = gdf_with_data[rate_cols].astype(float).fillna(0.0).to_numpy()
        lead_cnt = np.bincount(lead_arr.argmax(axis=1), minlength=len(rate_cols))
    else:
        lead_cnt = np.zeros(len(rate_cols), dtype=int)
    n_legend = min(len(rate_cols), len(cand_names), len(stops_list))
    keep = [i for i in range(n_legend) if lead_cnt[i] > 0]
    dropped_names = [cand_names[i] for i in range(n_legend) if lead_cnt[i] == 0]
    if not keep:                      # 全 0（理論上不發生）→ 退回收錄全部
        keep = list(range(n_legend))
        dropped_names = []
    legend_cand_names = [cand_names[i] for i in keep]
    legend_stops_full = [stops_list[i] for i in keep]
    print(f"  圖例候選人       : {'、'.join(legend_cand_names)}"
          + (f"   （{'、'.join(dropped_names)} 未在任何村里領先，不列入圖例）" if dropped_names else ""))

    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], stops_list[i])

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 計算圖例起點（所有村里中最低的領先者得票率，向下取整到 10 的倍數） ----
    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0
    legend_start_tier = int(min_win_rate // 5) * 5

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
    print(f"  有資料           : {cnt_valid}")
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
                print(f"      {r['COUNTYNAME']} {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['COUNTYNAME']} {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    no_data_by_town = gdf_no_data.groupby(["COUNTYNAME", "TOWNNAME"]).size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】")
        for (cty, town), cnt2 in no_data_by_town.items():
            print(f"  {cty} {town}: {cnt2} 個村里")
        nan_cnt = int(gdf_no_data["VILLNAME"].isna().sum())
        if nan_cnt:
            print(f"  ※ 其中 {nan_cnt} 個 SHP 村里名稱為空值(NaN)，無從比對，以灰色顯示")

    # ===================== 繪圖 =====================
    # 無資料村里著色規則：
    #   SHP 有、Excel 沒有 —— 有具體地名者（當時因行政沿革尚未設立）→ 白色
    #   VILLNAME 為 NaN（無名，多為荒島）→ 灰色
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != "")
    )
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)

    # 將無資料/NaN 村里也納入地圖，全區皆繪製
    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    # ---- 排除離島：僅保留主島（最大陸塊）範圍內的幾何 ----
    # 宜蘭頭城鎮大溪里含釣魚臺列嶼、另有龜山島、基隆北方三島等；依需求不繪製離島，
    # 故以最大陸塊裁切：多島村里只留本島部分，純離島村里（如龜山里）整筆剔除。
    city_geom = gdf_plot.geometry.union_all()
    if cfg.get("main_island_only", True) and city_geom.geom_type == "MultiPolygon":
        main_island = max(city_geom.geoms, key=lambda p: p.area)
        gdf_plot = gdf_plot.copy()
        gdf_plot["geometry"] = gdf_plot.geometry.intersection(main_island)
        gdf_plot = gdf_plot[~gdf_plot.geometry.is_empty].copy()
        city_geom = gdf_plot.geometry.union_all()
        print(f"  ※ 已排除離島，僅繪製主島（剩餘 {len(gdf_plot)} 個村里）")

    # ---- 空隙填平（預設停用）----
    # 依需求：SHP 未涵蓋的地方（河川／港灣／水庫）不擅自填色，保持白色。
    # 若真要填，設 cfg gap_fill_m>0（公尺）。
    gap_fill_m = cfg.get("gap_fill_m", 0)
    gap_gdf = None
    if gap_fill_m:
        land_closed = city_geom.buffer(
            gap_fill_m, join_style=1, cap_style=1).buffer(
            -gap_fill_m, join_style=1, cap_style=1)
        gaps = land_closed.difference(city_geom)
        gap_polys = list(gaps.geoms) if gaps.geom_type == "MultiPolygon" else (
            [gaps] if not gaps.is_empty else [])
        gap_polys = [g for g in gap_polys if g.area > 0]
        if gap_polys:
            gg = gpd.GeoDataFrame(geometry=gap_polys, crs=gdf_plot.crs)
            j = gpd.sjoin_nearest(gg, gdf_plot[["fill_hex", "geometry"]], how="left")
            j = j[~j.index.duplicated(keep="first")]
            gg["fill_hex"] = j["fill_hex"].reindex(gg.index).fillna(GRAY_COLOR).values
            gap_gdf = gg
            print(f"  ※ 填平河川/港灣空隙 {len(gap_polys)} 塊（閉合半徑 {gap_fill_m}m）")

    # ---- 鄉鎮市區／縣市界用幾何 ----
    # 直接取村里 dissolve 的邊界（忠於村里界線）；僅移除「次像素細縫」內環
    # （面積 < SMALL_HOLE_AREA 者），避免再出現不是行政界的碎線。
    # 不補平、不合併、不擅自拆分：河川缺口等原貌保留（如三重被河川切成兩塊即照村里線呈現）。
    SMALL_HOLE_AREA = 1000.0   # m²；小於此的內環視為細縫移除

    def _remove_small_holes(geom):
        if geom.is_empty:
            return geom
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        out = []
        for p in polys:
            if p.is_empty:
                continue
            keep = [r for r in p.interiors if Polygon(r).area >= SMALL_HOLE_AREA]
            out.append(Polygon(p.exterior, keep))
        if not out:
            return geom
        return MultiPolygon(out) if len(out) > 1 else out[0]

    towns = gdf_plot.dissolve(by=["county_core", "town_core"])
    towns["geometry"] = towns.geometry.apply(_remove_small_holes)
    counties = gdf_plot.dissolve(by="county_core")
    counties["geometry"] = counties.geometry.apply(_remove_small_holes)
    outer_geom = city_geom

    minx, miny, maxx, maxy = outer_geom.bounds
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
    county_half_m = COUNTY_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2

    # ① 空隙填色（無邊，置於村里下層）：以最近村里填色補平河川/港灣縫隙
    if gap_gdf is not None and len(gap_gdf):
        gap_gdf.plot(
            ax=ax, facecolor=gap_gdf["fill_hex"].tolist(),
            edgecolor='none', linewidth=0, antialiased=False, zorder=1
        )

    # ② 村里填色（無邊）
    gdf_plot.plot(
        ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False, zorder=2
    )

    # ③ 村里黑線（1px）
    village_lines = gdf_plot.boundary.union_all()
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=VILL_LINE_PX * PX2PT, antialiased=False, zorder=5
        )

    # ④ 鄉鎮市區黑線（4px 黑帶）：直接取村里 dissolve 的鄉鎮界（忠於村里線）
    if cfg.get("draw_town_lines", True):
        town_lines = towns.boundary.union_all()
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

    # ⑤ 縣市界（5px 黑帶）：由村里 dissolve 的縣市界線繪製
    if cfg.get("draw_county_lines", True):
        county_lines = counties.boundary.union_all()
        if not county_lines.is_empty:
            county_band = county_lines.buffer(
                county_half_m, resolution=BUF_RES,
                join_style=BUF_JOIN, cap_style=BUF_CAP
            ).intersection(city_geom)
            if not county_band.is_empty:
                gpd.GeoSeries([county_band]).plot(
                    ax=ax, facecolor='black', edgecolor='none',
                    linewidth=0, antialiased=False, zorder=10
                )

    # ⑥ 海岸線／外輪廓（5px 黑帶）：由村里邊界線（union）取外緣
    outer = outer_geom.boundary.buffer(
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

    # ---- 圖例只顯示從最低領先得票率色階起的色塊（且已剔除未領先的候選人） ----
    legend_stops_list = [
        [(u, c) for u, c in stops if u > legend_start_tier]
        for stops in legend_stops_full
    ]

    # 圖例欄標題（候選人名稱）
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in legend_cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 各候選人欄的色階標籤
    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier, is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(legend_stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ===================== 畫布佈局（整體懸浮右下方：左緣距同高陸地400、下緣距頁底400） =====================
    TITLE_GAP = 70                # 標題視覺下緣與圖例上緣的間距
    UNIT_GAP_X = 800              # 整體視覺左緣與其同高附近陸地右緣的間距
    UNIT_GAP_BOTTOM = 400         # 整體下緣與頁面底緣的間距
    RECT_GAP_TOP = 400            # 整體上緣與其上（同寬範圍內）陸地的最小間距；不足則向下擴增畫布

    # 圖例為純色塊+文字（無內部透明留白）；標題影像可能含四周透明留白，
    # 故以「視覺墨跡」定位，使視覺左緣=同高陸地+800、視覺中心與圖例中心重合
    title_ink_w, title_ink_h, title_off_x, title_off_y = 0, 0, 0, 0
    if title_img:
        if "A" in title_img.getbands():
            m = np.asarray(title_img.getchannel("A")) > 0
        else:
            m = np.any(np.asarray(title_img.convert("RGB")) != 255, axis=2)
        if m.any():
            vy, vx = np.where(m)
            title_off_x, title_off_y = int(vx.min()), int(vy.min())
            title_ink_w, title_ink_h = int(vx.max()) - title_off_x + 1, int(vy.max()) - title_off_y + 1
        else:
            title_ink_w, title_ink_h = title_img.width, title_img.height

    unit_w = max(total_legend_w, title_ink_w)
    unit_h = legend_h + (TITLE_GAP + title_ink_h if title_img else 0)

    # 依「整體所處高度帶」內陸地最右側定位：左緣 = 該陸地右緣 + 400；
    # 整體下緣固定 = 頁底 - 400；若上緣離上方（同寬範圍內）陸地 < 400，則向下擴增畫布。
    land_mask = np.any(np.asarray(pil_img) != 255, axis=2)

    new_H = H
    unit_left = UNIT_GAP_X
    for _ in range(8):
        rect_bottom = new_H - UNIT_GAP_BOTTOM
        rect_top = rect_bottom - unit_h
        r0, r1 = max(0, rect_top), min(H - 1, rect_bottom)
        band = land_mask[r0:r1 + 1, :]
        if band.any():
            unit_left = int(np.where(band)[1].max()) + UNIT_GAP_X
        # 上方守則：整體上緣與其上方（同寬範圍內）陸地保持至少 RECT_GAP_TOP
        c0, c1 = int(min(unit_left, W)), int(min(unit_left + unit_w, W))
        top = land_mask[:min(H - 1, rect_top) + 1, c0:c1] if c1 > c0 else None
        if top is not None and top.any():
            nearest = int(np.where(top)[0].max())
            if rect_top - nearest < RECT_GAP_TOP:
                new_H += RECT_GAP_TOP - (rect_top - nearest)
                continue
        break

    new_W = max(W, int(unit_left + unit_w + LEGEND_PADDING))
    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, 0))

    # 標題視覺中心 = 圖例群組視覺中心；整體視覺左下角 = (同高陸地+400, 新頁底-400)
    unit_center = unit_left + unit_w / 2
    legend_x = int(round(unit_center - total_legend_w / 2))
    legend_y = int(round(new_H - UNIT_GAP_BOTTOM - legend_h))
    if title_img:
        title_x = int(round(unit_center - title_ink_w / 2 - title_off_x))
        title_y = int(round(legend_y - TITLE_GAP - title_ink_h - title_off_y))

    if title_img:
        blit_rgba(final_img, title_img, (title_x, title_y))

    draw_legend_on(final_img, legend_x, legend_y, legend_cand_names, legend_stops_list, col_width, max_label_w, start_tier=legend_start_tier)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；色階從 {legend_start_tier}% 起；排除無地名区块 {dropped} 個\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖，如：py Converge_to_map.py 2005
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")