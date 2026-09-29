# -*- coding: utf-8 -*-
"""
2012（馬英九）vs 2016（蔡英文）歷屆總統選舉鄉鎮市區得票率比較地圖

資料來源：Get_data/2012VS2016.xlsx
    （縣市 | 鄉鎮市區 | 蔡英文（02）得票數 | 蔡英文得票率 | 馬英九（02）得票數 | 馬英九得票率）
    得票率為各候選人得票數占「馬英九＋蔡英文」合計之比率。
    各鄉鎮以馬英九(2012)／蔡英文(2016) 得票率較高者為領先方。

繪圖邏輯（圖例／文字／版面）沿用 2008LegislatorParty.py，僅移除標題。

執行：
    py 2012VS2016.py
"""
import os
import re
import warnings

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(os.path.dirname(BASE_DIR), "maps")

COLORFUL_PNG = os.path.join(BASE_DIR, "Colorful.png")
CORR_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence.xlsx")
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "Get_data")
VS_XLSX = os.path.join(DATA_DIR, "2012VS2016.xlsx")
DATA_2016 = os.path.join(DATA_DIR, "2016總統副總統選舉_縣市鄉鎮.xlsx")
OUT_PNG = os.path.join(MAPS_DIR, os.path.basename(BASE_DIR),
                       "2012vs2016總統選舉_得票率比較地圖.png")

CANVAS_COLOR = "#323232"   # 畫布背景；同時作為無資料區域的填色

# ===================== 色階（35% 起，5% 間距） =====================
RATE_COLOR_STOPS = [
    [   # 第 1 组：馬英九（2012，中國國民黨，藍色系）
        (35, "#EAF6FF"), (40, "#B8E2FF"), (45, "#7CC8FF"), (50, "#3AA8FF"),
        (55, "#0088F0"), (60, "#006FCC"), (65, "#0059A8"), (70, "#004684"),
        (75, "#003563"), (80, "#002647"), (85, "#001A31"), (100, "#000D1F"),
    ],
    [   # 第 2 组：蔡英文（2016，民主进步党，綠色系）
        (35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
        (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
        (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09"),
    ],
]

# 圖例順序：候選人 → 對應色階組別
CANDIDATES = [
    ("馬英九", 0),      # → 藍（2012 中國國民黨）
    ("蔡英文", 1),      # → 綠（2016 民主進步黨）
]

TAG = "2012 馬英九 vs 2016 蔡英文 總統選舉得票率比較"

# 異體字／用字差異正規化（對照表 vs 2016 資料）
VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",
    "褔": "福",
})
VARIANT_WORD_MAP = {
    "後里": "后里",
    "滿洲": "滿州",
}

# 縣市名映射（2012 舊縣市制 桃園縣 → 現行桃園市；其餘縣市名已沿用 2016/現行）
OLD_COUNTY_MAP = {
    "桃園縣": "桃園市",
}

# ===================== 繪圖參數 =====================
BLOCK_WIDTH, BLOCK_HEIGHT = 85, 53
V_SPACING, H_SPACING = 19, 75
LEGEND_PADDING = 30
MAP_LEGEND_GAP = 40
COLUMN_TITLE_GAP = 50

CAND_NAME_FONT_SIZE = 42
LEGEND_LABEL_FONT_SIZE = 28

TEXT_COLOR = (255, 255, 255)   # 圖例白字


# ===================== 通用工具 =====================
def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
    if is_first:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"


# ===================== 文字圖片生成（仿 Print_word.py / Converge_to_map.py） =====================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def render_text_image(text_lines, font_size=64, dpi=100, color=TEXT_COLOR):
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
    result[:, :, 0] = color[2]   # B
    result[:, :, 1] = color[1]   # G
    result[:, :, 2] = color[0]   # R
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))


_TEXT_IMG_CACHE = {}


def render_text_image_cached(text_lines, font_size, color=TEXT_COLOR):
    key = (tuple(text_lines), font_size, color)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size, color=color)
    return _TEXT_IMG_CACHE[key]


def render_cand_name_img(nm):
    """候選人圖：名稱太長時縮小字級並換行為兩行。"""
    if len(nm) <= 6:
        return render_text_image_cached([nm], CAND_NAME_FONT_SIZE)
    fs = CAND_NAME_FONT_SIZE - 12
    half = (len(nm) + 1) // 2
    return render_text_image_cached([nm[:half], nm[half:]], fs)


def blit_rgba(base_img, rgba_img, xy):
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))


# ===================== 讀取對照表 + 得票資料 =====================
def load_correspondence():
    """回傳 (towns, county_code2name)。
    towns: list of dict {code, county, name, core, color_hex, fill_hex}
    """
    df = pd.read_excel(CORR_XLSX, header=None)
    towns = []
    for i in range(1, len(df)):
        col5 = df.iloc[i, 5]                     # 縣市編碼（本表欄位）
        if pd.isna(df.iloc[i, 0]) or pd.isna(col5):
            continue
        towns.append({
            "code": int(col5),
            "county": "",
            "name": str(df.iloc[i, 8]).strip(),
            "core": "",
            "color_hex": str(df.iloc[i, 1]).strip().upper(),
            "fill_hex": None,
        })

    # 縣市碼表：右側欄（col12=縣市編碼, col13=縣市名）
    county_code2name = {}
    for i in range(1, min(len(df), 30)):
        c = df.iloc[i, 12]
        nm = df.iloc[i, 13]
        if pd.isna(c) or pd.isna(nm):
            continue
        try:
            code = int(float(c))
        except (TypeError, ValueError):
            continue
        county_code2name[code] = str(nm).strip()

    for t in towns:
        n = county_code2name.get(int(t["code"]), "")
        t["county"] = n.translate(VARIANT_CHAR_MAP)   # 統一 臺→台（臺北市→台北市）

    return towns, county_code2name


def norm_town_core(name):
    """鄉鎮市區名 → 正規化核心字（表側用）。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


def parse_2012_vs_2016():
    """2012VS2016.xlsx（含鄉鎮欄）：縣市 | 鄉鎮市區 | 馬英九得票數 | 馬英九得票率 | 蔡英文得票數 | 合計 | 蔡英文得票率
    回傳 (data, cand_names, unmatched)
      data: {(county, town_core): {cand: rate}}
    """
    vs = pd.read_excel(VS_XLSX, header=None)
    vs = vs[1:].copy()                              # 略過表頭列
    vs = vs[vs[0].notna()]
    vs = vs[vs[0].astype(str).ne("總計")].reset_index(drop=True)

    data = {}
    order = []
    for i in range(len(vs)):
        src_county = str(vs.iloc[i, 0]).strip().translate(VARIANT_CHAR_MAP)
        src_county = OLD_COUNTY_MAP.get(src_county, src_county)
        town = str(vs.iloc[i, 1]).strip()
        core = norm_town_core(town)
        key = (src_county, core)
        rec = {
            "馬英九": float(vs.iloc[i, 5]),
            "蔡英文": float(vs.iloc[i, 3]),
        }
        data[key] = rec
        order.append(key)

    cand_names = ["馬英九", "蔡英文"]
    return data, cand_names, []


# ===================== 主程式 =====================
def main():
    print("=" * 62)
    print("  組別：" + TAG)
    print("=" * 62)

    towns, county_code2name = load_correspondence()
    print(f"  對照表鄉鎮市區    : {len(towns)} 個（全市縣 {len(county_code2name)} 個）")

    data, cand_names, unmatched = parse_2012_vs_2016()
    print(f"  2012 vs 2016 資料 : {len(data)} 個鄉鎮市區")

    # ------------- 建立對照表索引 -------------
    by_key = {}
    for t in towns:
        t["core"] = norm_town_core(t["name"])
        by_key[(t["county"], t["core"])] = t

    # ------------- 指派填入色 -------------
    cand_list = [n for n, _ in CANDIDATES if n in cand_names]
    if not cand_list:
        raise ValueError("未偵測到任何候選人")
    cand_idx = {n: i for i, n in enumerate(cand_list)}

    # 資料預先按「縣市 → 鄉鎮市區」分層，對照時先比縣市、再比鄉鎮
    data_by_county = {}
    for (county, core), rec in data.items():
        data_by_county.setdefault(county, {})[core] = rec

    matched_data_keys = []
    no_data_names = []
    for t in towns:
        rec = data_by_county.get(t["county"], {}).get(t["core"])
        if not rec:
            t["fill_hex"] = CANVAS_COLOR   # 無資料區域填背景色（#323232）
            no_data_names.append(t["name"])
            continue
        key = (t["county"], t["core"])
        matched_data_keys.append(key)
        vals = {n: rec.get(n, float("nan")) for n in cand_list}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        scheme = RATE_COLOR_STOPS[CANDIDATES[cand_idx[win_name]][1]]
        t["fill_hex"] = get_color_by_value(vals[win_name], scheme)

    # 未配對到的資料 key（理論上應為空）
    data_keys = set(data.keys())
    matched_set = set(matched_data_keys)
    orphan_keys = sorted(data_keys - matched_set)

    print(f"  有資料(填色)      : {len(matched_data_keys)}")
    print(f"  無資料(不著色)    : {len(no_data_names)}：{'、'.join(no_data_names[:20])}"
          + ("…" if len(no_data_names) > 20 else ""))
    if orphan_keys:
        print("  ※ 資料表有但未配對到對照表的 key：")
        for k in orphan_keys:
            print(f"      {k}")

    # ------------- 統計：領先候選人 -------------
    win_cnt = {n: 0 for n in cand_list}
    win_rates = []
    for t in towns:
        if (t["county"], t["core"]) not in data:
            continue
        rec = data[(t["county"], t["core"])]
        vals = {n: rec.get(n, float("nan")) for n in cand_list}
        win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
        win_cnt[win_name] += 1
        win_rates.append(vals[win_name])
    print("  各候選人領先鄉鎮數:")
    for n in cand_list:
        print(f"      {n}: {win_cnt.get(n, 0)}")
    min_win = min(win_rates) if win_rates else 0
    legend_start_tier = int(min_win // 5) * 5
    print(f"  領先得票率範圍    : {min_win:.1f}% ~ {max(win_rates):.1f}%（圖例自 {legend_start_tier}% 起）")

    if orphan_keys:
        raise SystemExit("有未配對的資料列，請檢查後再輸出。")

    # ------------- 重著色底圖 -------------
    img = Image.open(COLORFUL_PNG).convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3]
    rgb_flat = rgb.reshape(-1, 3)
    uniq, inv = np.unique(rgb_flat, axis=0, return_inverse=True)

    color2fill = {}
    for t in towns:
        if t["fill_hex"]:
            color2fill[hex2rgb(t["color_hex"])] = hex2rgb(t["fill_hex"])

    new_uniq = uniq.copy()
    for i, u in enumerate(uniq):
        f = color2fill.get(tuple(int(x) for x in u))
        if f is not None:
            new_uniq[i] = f
    recolored_flat = new_uniq[inv].reshape(rgb.shape)

    # 合成到畫布底色（保留 alpha）
    out_arr = arr.copy()
    out_arr[..., :3] = recolored_flat
    rgba = Image.fromarray(out_arr)
    bg = Image.new("RGB", rgba.size, hex2rgb(CANVAS_COLOR))
    bg.paste(rgba, mask=rgba.getchannel("A"))
    base = bg.convert("RGB")
    W, H = base.size

    # 主圖最右側實際地圖內容（非畫布留白），圖例以其為基準貼近放置
    canvas_rgb = hex2rgb(CANVAS_COLOR)
    rgba_arr = np.asarray(rgba)[..., :3]
    not_canvas = (np.abs(rgba_arr.astype(int) - np.array(canvas_rgb)).sum(axis=2) > 20)
    content_right = int(np.where(not_canvas.any(axis=0))[0].max())
    print(f"  主圖內容右緣      : x={content_right}（畫布全寬 {W}px）")

    # ------------- 圖例（僅繪製有領先鄉鎮的候選人） -------------
    legend_cand_names = [n for n in cand_list if win_cnt.get(n, 0) > 0]
    legend_stops_list = [
        [(u, c) for u, c in RATE_COLOR_STOPS[CANDIDATES[cand_idx[n]][1]] if u > legend_start_tier]
        for n in legend_cand_names
    ]

    name_imgs = [render_cand_name_img(nm) for nm in legend_cand_names]
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

    col_width = BLOCK_WIDTH + 4 + max_label_w
    n_cols = len(legend_stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ------------- 畫布布局（無標題） -------------
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    # 圖例以主圖實際內容右緣為基準，水平間距不超過 300px
    legend_x = content_right + min(MAP_LEGEND_GAP, 300)
    panel_content_h = legend_h

    # 名稱以整欄為中心，畫布須涵蓋最右側名稱
    legend_name_right = max(
        legend_x + i * (col_width + H_SPACING) + (col_width + name_imgs[i].width) / 2
        for i in range(len(legend_cand_names))
    ) + LEGEND_PADDING

    new_W = int(max(legend_x + group_w + LEGEND_PADDING, legend_name_right))
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    # 文字右側留白約為全圖寬 3%
    RIGHT_MARGIN_RATIO = 0.03
    new_W = int(new_W * (1 + RIGHT_MARGIN_RATIO))

    final_img = Image.new("RGB", (new_W, new_H), hex2rgb(CANVAS_COLOR))
    final_img.paste(base, (0, (new_H - H) // 2))

    # 圖例與主圖垂直置中（受限於畫布留白）
    py = (new_H - legend_h) // 2
    draw_legend_on(final_img, legend_x, py, legend_cand_names, legend_stops_list,
                   max_label_w, start_tier=legend_start_tier)

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    final_img.save(OUT_PNG)
    print(f"  輸出: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(matched_data_keys)} 個有資料鄉鎮市區填色；色階自 {legend_start_tier}% 起\n")


def draw_legend_on(final_img, x0, y0, cand_names, stops_list, max_label_w, start_tier=0):
    """圖例：色塊用 ImageDraw 繪製；文字以 render_text_image 貼上（同 Converge_to_map.py）。"""
    draw_obj = ImageDraw.Draw(final_img)
    col_width = BLOCK_WIDTH + 4 + max_label_w
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(len(cand_names))]
    name_h = max(
        (render_cand_name_img(nm).height for nm in cand_names),
        default=0,
    )
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_cand_name_img(cand_names[col_idx])
            blit_rgba(final_img, nm_img, (x_start + (col_width - nm_img.width) / 2, y0))
        for i, (upper, color_hex) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 4,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))


if __name__ == "__main__":
    main()