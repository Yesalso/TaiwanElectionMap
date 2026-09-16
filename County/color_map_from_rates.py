# -*- coding: utf-8 -*-
"""
1994 臺灣省省長選舉 —— 鄉鎮市區得票率地圖（由「得票率 Excel」上色）

輸入：
    1. 1994臺灣省_得票率.xlsx  （convert_1994_to_rates.py 產出；標準格式：
       選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率 ...）
    2. Name_Color_Correspondence.xlsx（鄉鎮市區 ↔ 底圖唯一色）
    3. Colorful.png（全台唯一色底圖）

流程：
    步驟 1  讀底圖 Colorful.png → RGB 陣列
    步驟 2  讀對照表 → 顏色→鄉鎮、鄉鎮→顏色 的雙向索引
    步驟 3  讀得票率 Excel → 每個鄉鎮市區的候選人得票率
    步驟 4  取「得票率最高之候選人」決定色系（藍=宋楚瑜、綠=陳定南、青=吳梓、黃=朱高正）
            → 依得票率落在哪一級決定深淺（RATE_COLOR_STOPS）
    步驟 5  numpy 查表把「底圖唯一色 → 得票率繪圖色」整圖替換
    步驟 6  加圖例／標題／無資料說明，輸出 PNG

執行：
    py color_map_from_rates.py
"""
import hashlib
import os
import re
import warnings

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(os.path.dirname(BASE_DIR), "maps")

COLORFUL_PNG = os.path.join(BASE_DIR, "Colorful.png")
CORR_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence.xlsx")
RATES_XLSX = os.path.join(BASE_DIR, "1994臺灣省_得票率.xlsx")
OUT_PNG = os.path.join(MAPS_DIR, os.path.basename(BASE_DIR),
                       "1994年臺灣省省長選舉_得票率地圖.png")

GRAY_COLOR = "#CCCCCC"
NO_DATA_FILL_HEX = "#323232"   # 無資料區域：先填白墊底，再覆蓋此色

# ===================== 色階（35% 起，5% 間距）=====================
RATE_COLOR_STOPS = [
    [   # 第 1 组：中国国民党候选人（宋楚瑜）
        (35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"), (50, "#40C8FF"),
        (55, "#00C0F4"), (60, "#00A2E8"), (65, "#0080B8"), (70, "#006591"),
        (75, "#004B6B"), (80, "#003247"), (85, "#001F2E"), (100, "#010D29"),
    ],
    [   # 第 2 组：民主进步党候选人（陳定南）
        (35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
        (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
        (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09"),
    ],
    [   # 第 3 组：青色系（無黨籍：吳梓）
        (35, "#B3FFF0"), (40, "#00EBD1"), (45, "#00D9CA"), (50, "#00BFB2"),
        (55, "#00A89C"), (60, "#008080"), (65, "#006666"), (70, "#004C4C"),
        (75, "#003838"), (80, "#003030"), (85, "#002626"), (100, "#021F1F"),
    ],
    [   # 第 4 组：黄色系（新黨：朱高正）
        (0, "#FFFFEB"), (35, "#FFFFEB"), (40, "#FFF8CC"), (45, "#FFF0A8"),
        (50, "#FFE780"), (55, "#FFDD55"), (60, "#FFF200"), (65, "#E6DA00"),
        (70, "#BFB500"), (75, "#999100"), (80, "#736D00"), (85, "#4D4900"),
        (100, "#383502"),
    ],
]

# 圖例順序：候選人 → 對應色階組別
CANDIDATES = [
    ("宋楚瑜", 0),   # 中國國民黨 → 藍
    ("陳定南", 1),   # 民主進步黨 → 綠
    ("朱高正", 3),   # 新黨       → 黃
    ("吳梓",   2),   # 無黨籍     → 青
]

TITLE_LINES = [
    "第一屆臺灣省省長選舉",
    "在全省各鄉鎮市區得票領先之候選人得票比例圖",
]
TAG = ("1994 臺灣省省長選舉（中國國民黨：宋楚瑜 / 民主進步黨：陳定南 "
       "/ 新黨：朱高正 / 無黨籍：吳梓）")

VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中縣后里鄉 ↔ 對照表後裡區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}


def norm_town_core(name):
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


# ===================== 繪圖參數 =====================
BLOCK_WIDTH, BLOCK_HEIGHT = 85, 52
V_SPACING, H_SPACING = 19, 75
LEGEND_PADDING = 30
MAP_LEGEND_GAP = 60
COLUMN_TITLE_GAP = 50

TITLE_FONT_SIZE = 50
CAND_NAME_FONT_SIZE = 42
LEGEND_LABEL_FONT_SIZE = 28
NO_DATA_FONT_SIZE = 22


# ===================== 通用工具 =====================
def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(x) for x in rgb)


def get_color_by_value(val, stops):
    if isinstance(val, (float, np.floating)) and np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def get_label_text(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"


# ===================== 文字圖片生成（仿 Converge_to_map.py） =====================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


_FONT_FAMILY = None
_MEASURE_FIG = None


def _resolve_font_family():
    """只掃描一次字型清單（原寫法每次 render 都重建整個 set）。"""
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            _FONT_FAMILY = n
            break
    return _FONT_FAMILY


def _measure_text(text_lines, font_size, dpi):
    """在「重複使用的量測 figure」上量測字形（原寫法每次新建 figure）。"""
    global _MEASURE_FIG
    family = _resolve_font_family()
    font_family = [family, "DejaVu Sans"] if family else "DejaVu Sans"
    if _MEASURE_FIG is None:
        _MEASURE_FIG = plt.figure(figsize=(1, 1), dpi=dpi)
        _MEASURE_FIG.canvas.draw()
    renderer = _MEASURE_FIG.canvas.get_renderer()
    widths, heights, glyphs = [], [], []
    for line in text_lines:
        t = _MEASURE_FIG.text(0, 0, line, fontsize=font_size, fontfamily=font_family)
        bbox = t.get_window_extent(renderer=renderer)
        widths.append(bbox.width)
        heights.append(bbox.height)
        glyphs.append(t)
    for t in glyphs:
        t.remove()
    return widths, heights, font_family


def render_text_image(text_lines, font_size=64, dpi=100, color=(255, 255, 255)):
    mpl_color = tuple(c / 255.0 for c in color)   # 0-255 → matplotlib 0-1
    line_widths, line_heights, font_family = _measure_text(text_lines, font_size, dpi)

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
                fontfamily=font_family, color=mpl_color)
        y -= line_spacing

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, facecolor="white", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    _, bin_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    h, w = bin_img.shape
    result = np.full((h, w, 4), 255, dtype=np.uint8)   # B,G,R = 255（白字）
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))


_TEXT_IMG_CACHE = {}
TEXT_CACHE_DIR = os.path.join(MAPS_DIR, "_text_cache")
_TEXT_DISK_CACHE_HITS = 0


def _text_cache_path(text_lines, font_size):
    key_material = repr((tuple(text_lines), font_size, 100, (255, 255, 255)))
    return os.path.join(TEXT_CACHE_DIR, hashlib.sha256(key_material.encode("utf-8")).hexdigest() + ".png")


def render_text_image_cached(text_lines, font_size):
    global _TEXT_DISK_CACHE_HITS
    key = (tuple(text_lines), font_size)
    if key not in _TEXT_IMG_CACHE:
        path = _text_cache_path(key[0], key[1])
        img = None
        try:
            if os.path.exists(path):
                with Image.open(path) as im:
                    img = im.convert("RGBA")
                _TEXT_DISK_CACHE_HITS += 1
        except Exception:
            img = None
        if img is None:
            img = render_text_image(text_lines, font_size=font_size)
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                img.save(path, "PNG")
            except Exception:
                pass
        _TEXT_IMG_CACHE[key] = img
    return _TEXT_IMG_CACHE[key]


def blit_rgba(base_img, rgba_img, xy):
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))


# ===================== 底圖唯一色 ↔ 鄉鎮：以底圖為準重新驗證 =====================
# Name_Color_Correspondence.xlsx 的「色欄」對多數鄉鎮正確，但少數列有問題：
#   - 臺北市信義區、基隆市信義區兩列的色欄彼此轉置；
#   - 部分鄉鎮（基隆市中正區、臺中市大甲區、屏東縣枋山鄉等）的「中心座標」恰好
#     落在相鄰鄉鎮多邊形上，以致形心像素踩到鄰居顏色；
#   - 臺東縣鹿野鄉的「中心座標／面積」欄被寫成高雄市茄萣區一帶（在臺灣西部海岸），
#     其真正多邊形位於臺灣東部（關山鎮與卑南鄉之間）。
# 因此，上色時逐一以底圖像素驗證：對照表色存在於形心附近 → 直接用；
# 否則改取「形心實際像素鄰域內、屬於對照表色之眾數」重綁定（以底圖為準）。
TOWN_BASE_COLOR_OVERRIDE = {
    # 台東縣鹿野鄉：中心座標已汙染，但其「色欄」是對的（底圖東部之 #002AB4 即為鹿野）。
    ("台東縣", "鹿野"): "#002AB4",
}

BASE_COLOR_SEARCH_RADIUS = 20


def derive_base_color(arr, towns):
    """依底圖 Colors 像素，回傳 {id(town): 底圖唯一色}（以底圖為準）。"""
    H, W = arr.shape[:2]
    corr_colors = {t["color_hex"] for t in towns}
    override_color = {
        (t["county"], t["core"]): t["color_hex"]
        for t in towns
        if (t["county"], t["core"]) in TOWN_BASE_COLOR_OVERRIDE
    }

    def _dominant_corr_color(cxx, cyy):
        for rad in (1, 4, 8, 16):
            y0, y1 = max(0, cyy - rad), min(H, cyy + rad + 1)
            x0, x1 = max(0, cxx - rad), min(W, cxx + rad + 1)
            patch = arr[y0:y1, x0:x1].reshape(-1, 3)
            if patch.shape[0] == 0:
                continue
            uniq, cnt = np.unique(patch, axis=0, return_counts=True)
            for oi in np.argsort(-cnt):
                if rgb_hex(uniq[oi]) in corr_colors:
                    return rgb_hex(uniq[oi])
        return None

    base_of = {}
    for t in towns:
        key = (t["county"], t["core"])
        cxx, cyy = t["center"]
        ccorr = rgb_hex(hex2rgb(t["color_hex"]))

        if key in override_color:                    # 1) 顯式覆寫（信任色欄）
            base_of[id(t)] = t["color_hex"]
            continue

        r = BASE_COLOR_SEARCH_RADIUS                # 2) 對照表色存在於形心附近
        y0, y1 = max(0, cyy - r), min(H, cyy + r + 1)
        x0, x1 = max(0, cxx - r), min(W, cxx + r + 1)
        local = (arr[y0:y1, x0:x1] == hex2rgb(t["color_hex"])).all(axis=2)
        if local.any():
            base_of[id(t)] = t["color_hex"]
            continue

        dom = _dominant_corr_color(cxx, cyy)        # 3) 重綁定：形心鄰域眾數
        base_of[id(t)] = dom if dom else t["color_hex"]

    # 防呆：底圖色必須一對一
    dup = {c: [] for c in base_of.values()}
    for tid, c in base_of.items():
        dup[c].append(tid)
    conflicts = {c: ids for c, ids in dup.items() if len(ids) > 1}
    if conflicts:
        for c, ids in conflicts.items():
            names = [towns[_]["name"] for _ in ids]
            print(f"  ⚠ 底圖色衝突 {c}: {names}")
        raise SystemExit("底圖色一對一檢查失敗，請確認對照表與底圖。")
    return base_of


# ===================== 讀取對照表 + 得票率 =====================
def load_correspondence():
    """回傳 (towns, county_code2name)。
    towns: list of dict {code, county, name, core, color_hex, center, fill_hex}
    新版對照表欄位：0 區域ID | 1 填充顏色(HEX) | 2 面積 | 3 中心X | 4 中心Y
                    | 5 縣市編碼 | 6 全域ID | 7 縣市 | 8 地名
    """
    df = pd.read_excel(CORR_XLSX, header=None)
    towns = []
    for i in range(1, len(df)):
        col5 = df.iloc[i, 5]
        if pd.isna(df.iloc[i, 0]) or pd.isna(col5):
            continue
        towns.append({
            "code": int(col5),
            "county": str(df.iloc[i, 7]).strip().translate(VARIANT_CHAR_MAP),
            "name": str(df.iloc[i, 8]).strip(),
            "core": "",
            "color_hex": str(df.iloc[i, 1]).strip().upper(),
            "center": (int(df.iloc[i, 3]), int(df.iloc[i, 4])),
            "fill_hex": None,
        })

    county_code2name = {}
    for t in towns:
        county_code2name.setdefault(t["code"], t["county"])

    for t in towns:
        t["core"] = norm_town_core(t["name"])
    return towns, county_code2name


def load_rates():
    """讀標準得票率格式，回傳 (by_key, cand_names)。
      by_key: {(county_norm, town_core): {cand: rate(%)}}
      同一 key 多列 → 平均（如中西區合併情形）
    """
    df = pd.read_excel(RATES_XLSX, sheet_name="各里彙總")
    df.columns = [str(c) for c in df.columns]
    rate_cols = [c for c in df.columns if c.endswith("得票率")]
    cand_names = [c[: -len("得票率")] for c in rate_cols]

    def _norm_county(v):
        if pd.isna(v):
            return ""
        return str(v).strip().translate(VARIANT_CHAR_MAP)

    data = {}
    for _, r in df.iterrows():
        key = (_norm_county(r["選舉區別"]), norm_town_core(str(r["鄉(鎮、市、區)別"])))
        rec = data.setdefault(key, {})
        for n, c in zip(cand_names, rate_cols):
            try:
                v = float(r[c])
            except (TypeError, ValueError):
                v = float("nan")
            if not np.isnan(v):
                rec.setdefault(n, []).append(v)
    by_key = {k: {n: float(np.mean(v)) for n, v in rec.items()} for k, rec in data.items()}
    return by_key, cand_names


# ===================== 主程式 =====================
def main():
    print("=" * 62)
    print("  組別：" + TAG)
    print("=" * 62)

    towns, county_code2name = load_correspondence()
    print(f"  對照表鄉鎮市區    : {len(towns)} 個（全市縣 {len(county_code2name)} 個）")

    rates, rate_names = load_rates()
    print(f"  得票率資料        : {len(rates)} 個鄉鎮市區（候選人 {rate_names}）")

    cand_list = [n for n, _ in CANDIDATES if n in rate_names]
    if not cand_list:
        raise ValueError("得票率檔案未偵測到候選人欄位")
    cand_idx = {n: i for i, n in enumerate(cand_list)}

    matched_data_keys = []
    no_data_names = []
    for t in towns:
        rec = rates.get((t["county"], t["core"]))
        if not rec:
            t["fill_hex"] = NO_DATA_FILL_HEX      # 無資料區域：白底 → 再覆蓋底色（深灰）
            no_data_names.append(t["name"])
            continue
        matched_data_keys.append((t["county"], t["core"]))
        vals = {n: rec.get(n, float("nan")) for n in cand_list}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        scheme = RATE_COLOR_STOPS[CANDIDATES[cand_idx[win_name]][1]]
        t["fill_hex"] = get_color_by_value(vals[win_name], scheme)

    orphan_keys = set(rates.keys()) - set(matched_data_keys)
    print(f"  有資料(填色)      : {len(matched_data_keys)}")
    print(f"  無資料(不著色)    : {len(no_data_names)}：{'、'.join(no_data_names[:20])}"
          + ("…" if len(no_data_names) > 20 else ""))
    if orphan_keys:
        for k in orphan_keys:
            print(f"  ※ 資料有但未配對到對照表的 key：{k}")

    # ---- 統計：領先候選人 ----
    win_cnt = {n: 0 for n in cand_list}
    win_rates = []
    for t in towns:
        rec = rates.get((t["county"], t["core"]))
        if not rec:
            continue
        vals = {n: rec.get(n, float("nan")) for n in cand_list}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        win_cnt[win_name] += 1
        win_rates.append(vals[win_name])
    print("  各候選人領先鄉鎮數:")
    for n in cand_list:
        print(f"      {n}: {win_cnt.get(n, 0)}")
    legend_cand = [n for n in cand_list if win_cnt.get(n, 0) > 0]
    print("  圖例僅顯示有領先鄉鎮之候選人:", "、".join(legend_cand))
    min_win = min(win_rates) if win_rates else 0
    legend_start_tier = int(min_win // 5) * 5
    print(f"  領先得票率範圍    : {min_win:.1f}% ~ {max(win_rates):.1f}%（圖例自 {legend_start_tier}% 起）")

    if orphan_keys:
        raise SystemExit("有未配對的資料列，請檢查後再輸出。")

    # ===================== 重著色底圖 =====================
    img = Image.open(COLORFUL_PNG).convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3]

    # 以底圖像素重新驗證「對照表色 ↔ 鄉鎮」；少數被汙染的列改以底圖為準
    base_of = derive_base_color(rgb, towns)
    rebound = [(t["county"], t["name"], base_of[id(t)]) for t in towns
               if base_of[id(t)] != t["color_hex"]]
    if rebound:
        print("  ※ 已依底圖重綁定顏色（對照表與底圖不符）:")
        for co, nm, hx in rebound:
            print(f"      {co}{nm} → 底圖色 {hx}")

    color2fill = {}
    for t in towns:
        if t["fill_hex"]:
            color2fill[hex2rgb(base_of[id(t)])] = hex2rgb(t["fill_hex"])

    #    對 19M 像素：以 24-bit 全色域 LUT 直接 fancy-index 整圖一次到位，
    #    取代「np.unique + argsort（~0.8s）+ 索引回全圖」的舊流程
    pack = ((rgb[..., 0].astype(np.uint32) << 16)
            | (rgb[..., 1].astype(np.uint32) << 8)
            | rgb[..., 2].astype(np.uint32))
    LUT_N = 0x1000000
    lut = np.arange(LUT_N, dtype=np.uint32)      # 預設 = 原色不變
    for base_rgb, fill_rgb in color2fill.items():
        lut[(base_rgb[0] << 16) | (base_rgb[1] << 8) | base_rgb[2]] = \
            (fill_rgb[0] << 16) | (fill_rgb[1] << 8) | fill_rgb[2]
    recolored_pk = lut[pack]

    out_rgb = np.dstack([
        ((recolored_pk >> 16) & 255).astype(np.uint8),
        ((recolored_pk >> 8) & 255).astype(np.uint8),
        (recolored_pk & 255).astype(np.uint8),
    ])

    # 無資料區域：先整塊填白色墊底，再以 #323232 覆蓋內部；
    # 外緣一層（去鋸齒雜色區）保留白色以顯現區界
    def _pk(hx):
        r, g, b = hex2rgb(hx)
        return (r << 16) | (g << 8) | b

    no_data_pk = np.array([_pk(base_of[id(t)]) for t in towns
                           if t["fill_hex"] == NO_DATA_FILL_HEX], dtype=np.uint32)
    all_base_pk = np.array([_pk(base_of[id(t)]) for t in towns], dtype=np.uint32)
    # 用「同名 24-bit LUT」直接標記全圖像素，免去整圖 np.isin
    lut_nd = np.zeros(LUT_N, dtype=np.uint8); lut_nd[no_data_pk] = 1
    lut_ab = np.zeros(LUT_N, dtype=np.uint8); lut_ab[all_base_pk] = 1
    nd_mask = lut_nd[pack].astype(bool)
    dil8 = nd_mask.copy()
    dil8[1:, :] |= nd_mask[:-1, :]; dil8[:-1, :] |= nd_mask[1:, :]
    dil8[:, 1:] |= nd_mask[:, :-1]; dil8[:, :-1] |= nd_mask[:, 1:]
    dil8[1:, 1:] |= nd_mask[:-1, :-1]; dil8[:-1, :-1] |= nd_mask[1:, 1:]
    dil8[1:, :-1] |= nd_mask[:-1, 1:]; dil8[:-1, 1:] |= nd_mask[1:, :-1]
    rim = dil8 & ~nd_mask & (lut_ab[pack] == 0) & (pack != 0x323232) & (pack != 0xFFFFFF)
    out_rgb[rim] = (255, 255, 255)      # 1) 先填白色（墊底）
    out_rgb[nd_mask] = (50, 50, 50)     # 2) 再填 #323232（覆蓋）

    out_arr = np.dstack([out_rgb, arr[..., 3]])
    rgba = Image.fromarray(out_arr)
    W, H = rgba.size

    # ===================== 圖例 =====================
    legend_stops_list = [
        [(u, c) for u, c in RATE_COLOR_STOPS[CANDIDATES[cand_idx[n]][1]] if u > legend_start_tier]
        for n in legend_cand
    ]

    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in legend_cand]
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

    no_data_img = render_text_image_cached(
        ["無資料區域以海洋底色（#323232）標示：臺北市・高雄市（轄區）・金門縣・連江縣（1994 年非臺灣省轄區）"],
        NO_DATA_FONT_SIZE)

    # ===================== 畫布布局 =====================
    title_img = render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    legend_x = W + MAP_LEGEND_GAP
    TITLE_GAP = 35
    panel_content_h = title_img.height + TITLE_GAP + legend_h + (no_data_img.height + 20)

    title_x = legend_x + (group_w - title_img.width) / 2
    title_right = title_x + title_img.width

    new_W = int(max(title_right + 110, legend_x + group_w + LEGEND_PADDING))
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (0x32, 0x32, 0x32))
    final_img.paste(rgba, (0, (new_H - H) // 2), mask=rgba.getchannel("A"))

    py = LEGEND_PADDING
    blit_rgba(final_img, title_img, (title_x, py))
    py += title_img.height + TITLE_GAP

    draw_legend_on(final_img, legend_x, py, legend_cand, legend_stops_list,
                   max_label_w, start_tier=legend_start_tier)
    py += legend_h + 20

    blit_rgba(final_img, no_data_img, (legend_x, py))

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    final_img.save(OUT_PNG)
    print(f"  輸出: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(matched_data_keys)} 個有資料鄉鎮市區填色；色階自 {legend_start_tier}% 起")
    print(f"     圖例：{'、'.join(legend_cand)}（僅顯示有領先鄉鎮之候選人）\n")


def draw_legend_on(final_img, x0, y0, cand_names, stops_list, max_label_w, start_tier=0):
    draw_obj = ImageDraw.Draw(final_img)
    col_width = BLOCK_WIDTH + 8 + max_label_w
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(len(cand_names))]
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
                fill=color_hex, outline="#FFFFFF", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))


if __name__ == "__main__":
    main()