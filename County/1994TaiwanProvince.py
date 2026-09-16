# -*- coding: utf-8 -*-
"""
1994 年臺灣省省長（省主席）選舉 —— 鄉鎮市區得票率地圖

以全台「唯一色」底圖（Colorful.png）直接重著色，無需 SHP：
    - Colorful.png 中每個鄉鎮市區填以單一辨識色
    - Name_Color_Correspondence.xlsx：顏色(HEX) ↔ 鄉鎮市區 對照表
    - 得票資料：1994TaiwanProvince.xlsx（4 位候選人並排，得票率為小數）

  1994 年選舉範圍為當時「臺灣省」轄 21 縣市：
    - 含 臺北縣／桃園縣／臺中縣／臺南縣／高雄縣 等，對照表以現行「區」呈現
    - 不含 臺北市、高雄市（當時為直轄市）、金門縣、連江縣
    - 臺南市 1994 年分為「中區」「西區」，對照表已併為「中西區」→ 以兩區得票率平均

繪圖邏輯（圖例／文字／版面）沿用 Converge_to_map.py。

執行：
    py 1994TaiwanProvince.py
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
VOTE_XLSX = os.path.join(BASE_DIR, "1994TaiwanProvince.xlsx")
OUT_PNG = os.path.join(MAPS_DIR, os.path.basename(BASE_DIR),
                       "1994年臺灣省省長選舉_得票率地圖.png")

CANVAS_COLOR = "#323232"   # 畫布背景；同時作為無資料區域的填色

# ===================== 色階（35% 起，5% 間距）=====================
# 與 Converge_to_map.py 之 RATE_COLOR_STOPS 相同
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

# ===================== 縣市名映射（1994 臺灣省 → 對照表現行縣市） =====================
OLD_COUNTY_MAP = {
    "臺北縣": "新北市", "桃園縣": "桃園市",
    "臺中縣": "台中市", "臺中市": "台中市",
    "臺南縣": "台南市", "臺南市": "台南市",
    "高雄縣": "高雄市",
    "臺東縣": "台東縣",
    "宜蘭縣": "宜蘭縣", "花蓮縣": "花蓮縣", "澎湖縣": "澎湖縣",
    "屏東縣": "屏東縣", "彰化縣": "彰化縣", "南投縣": "南投縣",
    "雲林縣": "雲林縣", "嘉義縣": "嘉義縣", "苗栗縣": "苗栗縣",
    "新竹縣": "新竹縣", "基隆市": "基隆市", "新竹市": "新竹市",
    "嘉義市": "嘉義市",
}

# 異體字／用字差異正規化（對照表 vs 1994 資料）
VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",   # 苗栗南莊/南庄、雲林鬥六鬥南/斗六斗南
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中縣后里鄉 ↔ 對照表後裡區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}

# 跨縣市同名、需按縣市區分的特殊對應
TOWN_MERGE = {   # 1994 臺南市 中區＋西區 → 對照表中西區
    ("台南市", "中"): "中西",
    ("台南市", "西"): "中西",
}
SPECIAL_TOWN = {   # 歷史更名對應（1994 高雄縣三民鄉 → 現那瑪夏區）
    ("高雄市", "三民"): "那瑪夏",
}

# ===================== 繪圖參數（沿用 Converge_to_map.py，縮為 1/2） =====================
BLOCK_WIDTH, BLOCK_HEIGHT = 85, 53
V_SPACING, H_SPACING = 19, 75
LEGEND_PADDING = 30
MAP_LEGEND_GAP = 60
COLUMN_TITLE_GAP = 50

TITLE_FONT_SIZE = 50
CAND_NAME_FONT_SIZE = 42
LEGEND_LABEL_FONT_SIZE = 28
NO_DATA_FONT_SIZE = 22

TEXT_COLOR = (255, 255, 255)   # 標題／圖例白字


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
    if is_first and prev <= 35:
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
        t["county"] = n.translate(VARIANT_CHAR_MAP)   # 統一 臺→台
    return towns, county_code2name


def norm_town_core(name):
    """鄉鎮市區名 → 正規化核心字（表側用）。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


def parse_1994_votes():
    """1994 xlsx 為 4 候選人並排（每組: 地區,姓名,號次,得票數,得票率）。
    回傳 (data, cand_names, unmatched)
      data: {(target_county, town_core): {cand: [rate...]}}（同 key 多列 → 平均）
    """
    df = pd.read_excel(VOTE_XLSX, header=None)
    cand_names = []
    data = {}
    unmatched = []

    for i in range(1, len(df)):
        region = df.iloc[i, 0]
        if pd.isna(region):
            continue
        region = str(region).strip()
        m = re.match(r"^(.*?[縣市])(.*)$", region)
        if not m:
            unmatched.append((region, ""))
            continue
        old_county, town = m.group(1), m.group(2)
        county = OLD_COUNTY_MAP.get(old_county)
        core = norm_town_core(town)
        if county is None:
            unmatched.append((region, ""))
            continue
        merge = TOWN_MERGE.get((county, core))
        if merge:
            core = merge
        core = SPECIAL_TOWN.get((county, core), core)
        key = (county, core)
        rates = {}
        for b in range(4):                       # 4 個候選人區塊
            nm = df.iloc[i, 5 * b + 1]
            rate = df.iloc[i, 5 * b + 4]
            if pd.isna(nm) or pd.isna(rate):
                continue
            name = str(nm).strip()
            try:
                v = float(rate) * 100.0          # 小數 → %
            except (TypeError, ValueError):
                v = float("nan")
            if name not in cand_names:
                cand_names.append(name)
            rates.setdefault(name, []).append(v)
        rec = data.setdefault(key, {})
        for name, vals in rates.items():
            rec.setdefault(name, []).extend(vals)
        if not rates:
            unmatched.append((region, str(key)))

    # 平均（中西區等合併後多列）
    avg_data = {}
    for key, rec in data.items():
        avg_data[key] = {n: float(np.mean(v)) for n, v in rec.items()}
    return avg_data, cand_names, unmatched


# ===================== 主程式 =====================
def main():
    print("=" * 62)
    print("  組別：" + TAG)
    print("=" * 62)

    towns, county_code2name = load_correspondence()
    print(f"  對照表鄉鎮市區    : {len(towns)} 個（全市縣 {len(county_code2name)} 個）")

    data, cand_names, unmatched = parse_1994_votes()
    print(f"  1994 選舉資料      : {len(data)} 個鄉鎮市區（候選人 {cand_names}）")

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
    orphan_keys = data_keys - matched_set

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
        # 重新算領先者與得票率
        win_name, rate = winning_cand(t, data, cand_list, cand_idx)
        win_cnt[win_name] += 1
        win_rates.append(rate)
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

    # ------------- 圖例（僅繪製有領先鄉鎮的候選人） -------------
    legend_cand_names = [n for n in cand_list if win_cnt.get(n, 0) > 0]
    legend_stops_list = [
        [(u, c) for u, c in RATE_COLOR_STOPS[CANDIDATES[cand_idx[n]][1]] if u > legend_start_tier]
        for n in legend_cand_names
    ]

    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in legend_cand_names]
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

    # ------------- 畫布布局 -------------
    title_img = render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    legend_x = W + MAP_LEGEND_GAP
    TITLE_GAP = 35
    panel_content_h = title_img.height + TITLE_GAP + legend_h

    title_x = legend_x + (group_w - title_img.width) / 2
    title_right = title_x + title_img.width

    new_W = int(max(title_right + 110, legend_x + group_w + LEGEND_PADDING))
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), hex2rgb(CANVAS_COLOR))
    final_img.paste(base, (0, (new_H - H) // 2))

    py = LEGEND_PADDING
    blit_rgba(final_img, title_img, (title_x, py))
    py += title_img.height + TITLE_GAP

    draw_legend_on(final_img, legend_x, py, legend_cand_names, legend_stops_list,
                   max_label_w, start_tier=legend_start_tier)

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    final_img.save(OUT_PNG)
    print(f"  輸出: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(matched_data_keys)} 個有資料鄉鎮市區填色；色階自 {legend_start_tier}% 起\n")


def winning_cand(t, data, cand_list, cand_idx):
    """回傳 (領先候選人名, 得票率)。"""
    rec = data[(t["county"], t["core"])]
    vals = {n: rec.get(n, float("nan")) for n in cand_list}
    win_name = max(vals, key=lambda n: (vals[n] if not np.isnan(vals[n]) else -1.0))
    return win_name, vals[win_name]


def draw_legend_on(final_img, x0, y0, cand_names, stops_list, max_label_w, start_tier=0):
    """圖例：色塊用 ImageDraw 繪製；文字以 render_text_image 貼上（同 Converge_to_map.py）。"""
    draw_obj = ImageDraw.Draw(final_img)
    col_width = BLOCK_WIDTH + 4 + max_label_w
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
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 4,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))


if __name__ == "__main__":
    main()