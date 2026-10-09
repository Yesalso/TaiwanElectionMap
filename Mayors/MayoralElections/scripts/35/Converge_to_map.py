# -*- coding: utf-8 -*-
"""
第十一屆臺北縣長選舉（1989）各鄉（鎮、市）得票率地圖（鄉鎮市區層級）。

以「村里界歷史圖資_111」SHP 依鄉鎮市 dissolve 出鄉鎮市區輪廓，
結合「1989台北县长.xlsx」之鄉鎮市別得票數，繪製各鄉鎮市
「領先之候選人得票率」地圖。

資料格式（Sheet1，第 1 列為標題）：
    鄉鎮市 | <候選人1>得票數 | 得票率 | <候選人2>得票數 | 得票率 | 有效票數
得票率(%) = 候選人得票數 ÷ 有效票數 × 100

地圖規格：
    比例尺 1px = 35m（METERS_PER_PIXEL = 35）
    僅繪製鄉鎮市區（不畫村里界）
    色階自 45% 起跳：領先候選人得票率未達 45% 不著色（以灰色顯示）

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
import unicodedata
import warnings

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# ===================== 字体设置 =====================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "data")
MAPS_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "maps")

# ===================== 配置区 =====================
SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

DATASETS = [
    {
        "excel": os.path.join(EXCEL_DIR, "1989台北县长.xlsx"),
        "sheet": "Sheet1",
        "city": "新北市",                    # 1989 臺北縣即今新北市
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR),
                            "臺北縣1989年縣長選舉_各鄉鎮市得票率地圖.png"),
        "tag": "1989 臺北縣長選舉（中國國民黨：李錫錕 / 民主進步黨：尤清）",
        "title_lines": ["第十一屆臺北縣長選舉", "各鄉（鎮、市）領先之候選人得票率"],
        "legend_names": ["李錫錕", "尤清"],
        "col_votes": ["李錫錕（4 號）", "尤清（6 號）"],
        "col_town": "鄉鎮市",
        "col_valid": "有效票數",
    },
]

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 35, 32000   # 1px = 35m
TOWN_LINE_PX = 4              # 鄉鎮市區界线宽
OUTER_LINE_PX = 6             # 縣外輪廓線寬（黑）
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

BLOCK_WIDTH, BLOCK_HEIGHT = 96, 60
V_SPACING, H_SPACING = 20, 220
LEGEND_PADDING = 40
COLUMN_TITLE_GAP = 60         # 圖例欄標題（候選人）與第一個色塊的間距

# ---- 所有文字皆以 Print_word.py 方式輸出，以下字級可依需求適度調整 ----
TITLE_FONT_SIZE = 44          # 標題字級（地圖縮小，字級亦縮小）
CAND_NAME_FONT_SIZE = 48      # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE = 34   # 圖例數值標籤（≤45%、45~50%…）字級
NO_DATA_FONT_SIZE = 30        # 無資料說明字級

# ===================== 文字正規化 =====================
# 簡轉繁時易誤把地名「里」轉成「裡」（如八里→八裡），地名一律用「里」
VARIANT_CHAR_MAP = str.maketrans({
    '裡': '里',
})

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

def resolve_shp():
    for p in SHP_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("找不到村里界 SHP：" + "、".join(SHP_CANDIDATE_PATHS))

# ===================== 文字圖片生成（仿 Print_word.py） =====================
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
    key = (tuple(text_lines), font_size)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size)
    return _TEXT_IMG_CACHE[key]

def blit_rgba(base_img, rgba_img, xy):
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))

# ===================== 讀取得票 Excel，計算得票率 =====================
def load_rates(cfg):
    excel_path = cfg["excel"]
    raw = pd.read_excel(excel_path, sheet_name=cfg["sheet"], header=None, dtype=str)

    header = [str(c) if pd.notna(c) else "" for c in raw.iloc[0]]
    col_town = cfg["col_town"]
    col_valid = cfg["col_valid"]
    vote_cols = cfg["col_votes"]

    def col_index(name_re):
        for i, h in enumerate(header):
            if re.match(name_re, h):
                return i
        raise ValueError(f"{excel_path} 找不到欄位：{name_re}（表頭：{header}）")

    i_town = col_index(r"鄉鎮市")
    i_valid = col_index(r"有效票數")
    idx_votes = []
    for vn in vote_cols:
        idx_votes.append(col_index(re.escape(vn)))

    rows = []
    for _, r in raw.iloc[1:].iterrows():
        town_full = normalize_text(r.values[i_town] if i_town < len(r) else "")
        if not town_full or re.search(r"[总總]計", town_full):
            continue
        town_core = strip_town_suffix(town_full)
        if not town_core:
            continue
        vals = [r.values[i] if i < len(r.values) else "" for i in [i_valid] + idx_votes]
        try:
            valid = float(str(vals[0]).replace(",", ""))
            votes = [float(str(v).replace(",", "")) if str(v).strip() else np.nan for v in vals[1:]]
        except ValueError:
            continue
        if valid <= 0:
            continue
        rates = [v / valid * 100.0 if not np.isnan(v) else np.nan for v in votes]
        rows.append((town_core, rates, valid))
    return rows

# ===================== 逐張地圖繪製 =====================
def draw_legend_on(final_img, x0, y0, cand_names, stops_list):
    draw_obj = ImageDraw.Draw(final_img)
    n = len(cand_names)
    col_positions = [x0 + i * (BLOCK_WIDTH + 8 + 30 + H_SPACING) for i in range(n)]
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

    cand_names = cfg["legend_names"]
    n_cand = len(cand_names)
    stops_list = [RATE_COLOR_STOPS[i % len(RATE_COLOR_STOPS)] for i in range(n_cand)]

    # ---------- 鄉鎮市區 SHP（由村里界 dissolve） ----------
    gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    if gdf_all.crs.is_geographic:
        gdf_all = gdf_all.to_crs(epsg=3826)

    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(cfg["city"], na=False)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"SHP 中未找到 {cfg['city']} 數據")
    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)

    town_gdf = gdf_nt.dissolve(by="town_core").reset_index()
    if town_gdf.crs is None:
        town_gdf.crs = "EPSG:3826"

    # ---------- 得票資料 ----------
    rows = load_rates(cfg)
    vote_map = {town: rates for town, rates, _ in rows}
    n_excel = len(rows)

    print(f"  SHP 鄉鎮市區要素  : {len(town_gdf)}")
    print(f"  Excel 有效記錄    : {n_excel}   (候選人 {n_cand} 位：{' / '.join(cand_names)})")

    # ---------- 比對 ----------
    town_gdf["rates"] = town_gdf["town_core"].map(vote_map)
    unmatched = [t for t in town_gdf["town_core"] if t not in vote_map]
    for t in unmatched:
        print(f"  ⚠ SHP 鄉鎮無對應資料：{t}")
    for t in vote_map:
        if t not in set(town_gdf["town_core"]):
            print(f"  ⚠ Excel 鄉鎮無對應 SHP：{t}")

    match_cnt = int(town_gdf["rates"].notna().sum())
    print(f"  成功匹配         : {match_cnt} / {len(town_gdf)}")

    # ---------- 領先候選人得票率 ----------
    def leading(row):
        rates = row["rates"]
        if rates is None:
            return None, None, None
        best_i = int(np.nanargmax(rates))
        return cand_names[best_i], rates[best_i], stops_list[best_i]

    lead = town_gdf.apply(leading, axis=1)
    town_gdf["leader"] = [x[0] for x in lead]
    town_gdf["lead_rate"] = [x[1] for x in lead]
    town_gdf["lead_stops"] = [x[2] for x in lead]

    def pick_fill_color(row):
        if row["lead_rate"] is None:
            return None
        return get_color_by_value(row["lead_rate"], row["lead_stops"])

    town_gdf["fill_hex"] = town_gdf.apply(pick_fill_color, axis=1)
    below_cnt = int(town_gdf["fill_hex"].isna().sum())
    town_gdf["fill_hex"] = town_gdf["fill_hex"].fillna(GRAY_COLOR)
    no_data = town_gdf["lead_rate"].isna()
    town_gdf.loc[no_data, "fill_hex"] = GRAY_COLOR

    for _, r in town_gdf.iterrows():
        print(f"    {r['town_core']:<4} {r['leader']} {r['lead_rate']:.2f}%"
              if not pd.isna(r["lead_rate"]) else f"    {r['town_core']} 無資料")

    print(f"  有資料          : {int((~no_data).sum())}"
          f"（其中領先者得票率<45%未著色 {below_cnt} 個）")
    print(f"  無資料          : {int(no_data.sum())}")

    # ===================== 繪圖 =====================
    minx, miny, maxx, maxy = town_gdf.total_bounds
    MAP_PAD_FRAC = 0.03
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}，請調大 METERS_PER_PIXEL")
    print(f"  主圖像素         : {w_px}×{h_px}")

    DPI = 100
    PX2PT = 72.0 / DPI

    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = town_gdf.geometry.union_all()

    # ① 鄉鎮市區填色（無邊）
    town_gdf.plot(
        ax=ax, facecolor=town_gdf["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 鄉鎮市區黑線（4px 黑帶，不畫村里界）
    town_lines = town_gdf.boundary.union_all()
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

    # ③ 縣外輪廓（6px 黑帶）
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

    # ===================== 顏色量化 =====================
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

    # ===================== 文字圖像 =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size

    title_img = render_text_image_cached(cfg["title_lines"], TITLE_FONT_SIZE)
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    label_img_cols = []
    for stops in stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else None)
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max(len(s) for s in stops_list)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ===================== 畫布佈局（右側面板：標題 → 圖例） =====================
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    panel_content_w = max(title_img.width, group_w + 2 * (col_width - BLOCK_WIDTH))
    right_panel_w = panel_content_w + 2 * LEGEND_PADDING
    TITLE_GAP = 50
    panel_content_h = title_img.height + TITLE_GAP + legend_h

    new_W = W + right_panel_w
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    px0 = W + LEGEND_PADDING
    legend_x = px0 + (panel_content_w - group_w) / 2
    py = LEGEND_PADDING

    # 標題與圖例群組居中对齐
    blit_rgba(final_img, title_img, (px0 + (panel_content_w - title_img.width) / 2, py))
    py += title_img.height + TITLE_GAP

    draw_legend_on(final_img, legend_x, py, cand_names, stops_list)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(town_gdf)} 個鄉鎮市區繪製；色階 45% 起跳\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None
    SHP_PATH = resolve_shp()
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")