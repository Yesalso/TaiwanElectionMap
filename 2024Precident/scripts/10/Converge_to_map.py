# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與「高雄格式」得票 Excel 結合，
繪製各村里候選人得票率地圖。

資料格式（各里彙總 工作表）：
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票數 ... | 有效票數A
得票率(%) = 候選人得票數 ÷ 有效票數A × 100

色階從 0% 起（10% 間距）。
候選人數量由 Excel 自動偵測，圖例欄數隨之調整。

執行：
    py Converge_to_map.py
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
EXCEL_DIR = r"C:\Users\Windows\Desktop\temp"

# ===================== 配置区 =====================
SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

# 要生成的地圖（兩張新北市長選舉）
DATASETS = [
    {
        "excel": os.path.join(EXCEL_DIR, "2010新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "新北市2010年市長選舉_得票率地圖.png"),
        "tag": "2010 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：蔡英文）",
        "title_lines": ["第一屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "蔡英文"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2014新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "新北市2014年市長選舉_得票率地圖.png"),
        "tag": "2014 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：游錫堃）",
        "title_lines": ["第二屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "游錫堃"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2018新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "新北市2018年市長選舉_得票率地圖.png"),
        "tag": "2018 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第三屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "蘇貞昌"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "新北县市首长_2022.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "新北市2022年市長選舉_得票率地圖.png"),
        "tag": "2022 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：林佳龍）",
        "title_lines": ["第四屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "林佳龍"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2005台北县.xlsx"),
        "sheet": "Sheet1",
        "header": 1,
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "臺北縣2005年縣長選舉_得票率地圖.png"),
        "tag": "2005 臺北縣長選舉（中國國民黨：周錫瑋 / 民主進步黨：羅文嘉）",
        "title_lines": ["第十五屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["周錫瑋", "羅文嘉"],
        "cand_columns": ["周錫偉", "羅文佳"],
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "區里",
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "臺北縣2001年縣長選舉_得票率地圖.png"),
        "tag": "2001 臺北縣長選舉（新黨：王建煊 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["王建煊", "蘇貞昌"],
        "color_schemes": [
            [(10, "#FFFFEB"), (20, "#FFFFDC"), (30, "#FFFECD"), (40, "#FFFEBC"),
             (50, "#FFFE91"), (60, "#FFF200"), (70, "#E6DA00"), (80, "#BFB500"),
             (90, "#999100"), (100, "#736D00")],
            [(10, "#E2FFE0"), (20, "#D2FFC9"), (30, "#C0FFB1"), (40, "#A4FF90"),
             (50, "#78FF4F"), (60, "#68DE45"), (70, "#54B337"), (80, "#3C8027"),
             (90, "#2B5C1C"), (100, "#1D3D13")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "臺北縣2001年縣長選舉_王建煊得票率地圖.png"),
        "tag": "2001 王建煊單獨",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）王建煊得票比例圖"],
        "legend_names": ["王建煊"],
        "cand_columns": ["新黨得票率"],
        "color_schemes": [
            [(10, "#FFFFEB"), (20, "#FFFFDC"), (30, "#FFFECD"), (40, "#FFFEBC"),
             (50, "#FFFE91"), (60, "#FFF200"), (70, "#E6DA00"), (80, "#BFB500"),
             (90, "#999100"), (100, "#736D00")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "臺北縣2001年縣長選舉_蘇貞昌得票率地圖.png"),
        "tag": "2001 蘇貞昌單獨",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）蘇貞昌得票比例圖"],
        "legend_names": ["蘇貞昌"],
        "cand_columns": ["民主進步黨得票率"],
        "color_schemes": [
            [(10, "#E2FFE0"), (20, "#D2FFC9"), (30, "#C0FFB1"), (40, "#A4FF90"),
             (50, "#78FF4F"), (60, "#68DE45"), (70, "#54B337"), (80, "#3C8027"),
             (90, "#2B5C1C"), (100, "#1D3D13")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "24总统", "2024新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(BASE_DIR, "新北市2024年總統副總統選舉_得票率地圖.png"),
        "tag": "2024 總統副總統選舉（中國國民黨：侯友宜 / 民主進步黨：賴清德 / 台灣民眾黨：柯文哲）",
        "title_lines": ["中華民國第十六屆總統副總統選舉", "在新北市各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "賴清德", "柯文哲"],
        "color_schemes": [
            [(10, "#00FFFF"), (20, "#00F2FF"), (30, "#00E6FF"), (40, "#00DAFF"),
             (50, "#00C0F4"), (60, "#00A2E8"), (70, "#0080B8"), (80, "#006591"),
             (90, "#004B6B"), (100, "#003247")],
            [(10, "#E2FFE0"), (20, "#D2FFC9"), (30, "#C0FFB1"), (40, "#A4FF90"),
             (50, "#78FF4F"), (60, "#68DE45"), (70, "#54B337"), (80, "#3C8027"),
             (90, "#2B5C1C"), (100, "#1D3D13")],
            [(10, "#F0F0F0"), (20, "#E0E0E0"), (30, "#D0D0D0"), (40, "#C0C0C0"),
             (50, "#B1B1B1"), (60, "#A1A1A1"), (70, "#929292"), (80, "#737373"),
             (90, "#646464"), (100, "#555555")],
        ],
    },
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 20, 32000   # 1px = 20m
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
OUTER_LINE_PX = 6             # 市外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階（0% 起，10% 間距）=====================
RATE_COLOR_STOPS = [
    # 國民黨
    [(10, "#00FFFF"), (20, "#00F2FF"), (30, "#00E6FF"), (40, "#00DAFF"),
     (50, "#00C0F4"), (60, "#00A2E8"), (70, "#0080B8"), (80, "#006591"),
     (90, "#004B6B"), (100, "#003247")],
    # 民進黨
    [(10, "#E2FFE0"), (20, "#D2FFC9"), (30, "#C0FFB1"), (40, "#A4FF90"),
     (50, "#78FF4F"), (60, "#68DE45"), (70, "#54B337"), (80, "#3C8027"),
     (90, "#2B5C1C"), (100, "#1D3D13")],
    # 第三組（備用）
    [(10, "#00EBD1"), (20, "#00D9CA"), (30, "#00BFB2"),
     (40, "#00A89C"), (50, "#008080"), (60, "#006666"), (70, "#004C4C")],
]

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LEGEND_PADDING = 60
MAP_LEGEND_GAP = 700      # 圖例與地圖之間距
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

    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols = load_rates(cfg)
    # 納入 {city} 資料；縣市欄缺失(NaN / 'nan' 不區分大小寫)者視為同屬該縣市，一併納入
    # Excel 中的縣市名稱可能與 SHP 不同（如 SHP 為新北市、舊檔為臺北縣），用 excel_city 指定
    excel_city = cfg.get("excel_city", cfg["city"])
    city_mask = df_vote["縣市"].str.contains(excel_city, case=False, na=False)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask].copy()

    n_cand = len(cand_cols)
    cand_names = cfg.get("legend_names", [c[:-3] for c in cand_cols])   # 圖例欄名稱＝候選人
    if cfg.get("color_schemes"):
        stops_list = cfg["color_schemes"]
    else:
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
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 計算圖例起點（所有村里中最低的領先者得票率，向下取整到 10 的倍數） ----
    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0
    legend_start_tier = int(min_win_rate // 10) * 10

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
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  ↔  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  ↔  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    no_data_by_town = gdf_no_data.groupby("TOWNNAME").size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】")
        for town, cnt2 in no_data_by_town.items():
            print(f"  {town}: {cnt2} 個村里")
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

    # 將無資料/NaN 村里也納入地圖，新北市全境皆繪製
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

    # ---- 圖例只顯示從最低領先得票率色階起的色塊 ----
    legend_stops_list = [
        [(u, c) for u, c in stops if u > legend_start_tier]
        for stops in stops_list
    ]

    # 圖例欄標題（候選人名稱）
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 各候選人欄的色階標籤
    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier)
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(legend_stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ===================== 畫布佈局（右側面板：標題 → 圖例） =====================
    # 圖例第一欄直接始於地圖右緣 + 75px（legend_x = W + 75）
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    LEGEND_X_MARGIN = 75        # 圖例第一欄與地圖右緣的間距
    title_w = title_img.width if title_img else 0
    # 標題水平置中於圖例欄位區域正上方（以 W+75 為起點一同位移）
    title_x_rel = (total_legend_w - title_w) // 2
    content_w = max(title_x_rel + title_w, total_legend_w) if title_img else total_legend_w
    right_panel_w = LEGEND_X_MARGIN + content_w + LEGEND_PADDING
    TITLE_GAP = 70
    panel_content_h = ((title_img.height + TITLE_GAP) if title_img else 0) + legend_h

    new_W = W + right_panel_w
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    # 右側面板：圖例第一欄於 W+75，標題置中於圖例欄位區域上方
    legend_x = W + LEGEND_X_MARGIN
    py = LEGEND_PADDING
    if title_img:
        blit_rgba(final_img, title_img, (legend_x + title_x_rel, py))
        py += title_img.height + TITLE_GAP

    draw_legend_on(final_img, legend_x, py, cand_names, legend_stops_list, col_width, max_label_w, start_tier=legend_start_tier)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；色階從 {legend_start_tier}% 起\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖，如：py Converge_to_map.py 2005
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")