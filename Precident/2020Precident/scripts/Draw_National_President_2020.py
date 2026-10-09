# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與 2020 總統副總統選舉全臺各村(里)得票率 Excel 結合，
繪製全臺灣候選人得票率地圖（以村里為填色單位）。

資料來源：2020Precident/data/2020總統副總統選舉_縣市鄉鎮村里.xlsx（工作表「村里層級明細」）
    縣市 | 鄉鎮市區 | 村里 | 宋楚瑜（01）_得票數 | 宋楚瑜（01）_得票率
       | 韓國瑜（02）_得票數 | 韓國瑜（02）_得票率
       | 蔡英文（03）_得票數 | 蔡英文（03）_得票率

繪圖邏輯：沿用 Empty_Map/DrawMap.py 之全臺地圖配置與 Draw_National_President_2024.py 之填色/圖例：
    - 臺灣本島 + 澎湖為主題；金門、連江(馬祖)為左上角 1:1 附圖（金門框在上、連江框在下，上下緊貼）
    - 高雄市無資料(未編定村里/代管)區域、基隆離岸島嶼(彭佳嶼等)、宜蘭釣魚台列嶼不繪製
    - 村里界 1px、鄉鎮市區界 2px、縣市地界 3px；金門/連江/澎湖等面積小之縣市海岸線 1px、僅畫內部鄉鎮界
    - 金門/連江附圖外框 6px、烏坵以同比例尺置入金門空餘角落(1px 框)

填色邏輯：油漆桶／洪水填充（同 Draw_NewTaipei_President_2020.py，共用 flood_fill_layer）：
    - 每村里取三候選人得票率最高者為該村里獲勝候選人，以其色階(5% 間距、35% 起)填色
    - 源資料若將多村里併為一列（以 、 分隔），拆解成各村(里)並填入相同顏色
    - SHP 有地名但無資料者、空白/水域地區一律填純白
    - 先畫完所有黑線（村里界/鄉鎮市區界/縣市地界/附圖框），再以線稿為封閉堤壩，
      對堤壩以外每一塊 4-連通區域整塊填單色；顏色取區域內像素幾何所屬村里的眾數
      → 顏色永不跨越黑線，全臺密集村里區不再有孤立錯色斑點
    - 右側圖例顯示候選人色階（自全臺最低領先得票率向下取 5 的倍數起）

執行：
    py Draw_National_President_2020.py
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
DATA_DIR = os.path.join(PROJECT_DIR, "2020Precident", "data")
OUT_DIR = os.path.join(PROJECT_DIR, "2020Precident", "maps")

SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\108\VILLAGE_MOI_1081121.shp",
]
# 不同年份村里界圖資 .dbf 編碼不一：108(2019) 為 UTF-8、106(2018) 為 Big5，依內容自動嘗試
SHP_ENCODINGS = ["utf-8", "cp950"]
SHP_KNOWN_COUNTIES = {"新北市", "臺北市", "桃園市", "臺中市", "臺南市", "高雄市",
                      "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣",
                      "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
                      "臺東縣", "澎湖縣", "金門縣", "連江縣"}

# ---------------------- 候選人與資料欄位 ----------------------
# 2020 三組候選人：圖例順序 韓國瑜(藍) → 蔡英文(綠) → 宋楚瑜(橘)，與政黨常用色系對應
CAND_NAMES = ["韓國瑜", "蔡英文", "宋楚瑜"]
CAND_RATE_SUFFIX = "得票率"          # 欄位名形如「韓國瑜（02）_得票率」

TITLE_LINES = ["中華民國第十五屆總統副總統選舉",
               "在全國各村（里）得票領先之候選人得票比例圖"]
OUT_PNG = os.path.join(OUT_DIR, "全臺灣2020年總統副總統選舉_得票率地圖.png")

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

# ---------------------- 繪圖與圖例參數（對應 Draw_National_President_2024.py） ----------------------
NO_DATA_COLOR = "#FFFFFF"   # 無資料/空白地區一律純白
DPI = 100
PX2PT = 72.0 / DPI

# 候選人色階順序與 CAND_NAMES 一致：韓國瑜(藍)、蔡英文(綠)、宋楚瑜(橘)
RATE_COLOR_STOPS = [
    # 第 1 組：中國國民黨 韓國瑜（藍色系，同 2024 侯友宜）
    [(35, "#EAF6FF"), (40, "#B8E2FF"), (45, "#7CC8FF"), (50, "#3AA8FF"),
     (55, "#0088F0"), (60, "#006FCC"), (65, "#0059A8"), (70, "#004684"),
     (75, "#003563"), (80, "#002647"), (85, "#001A31"), (100, "#000D1F")],
    # 第 2 組：民主進步黨 蔡英文（綠色系，同 2024 賴清德）
    [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
     (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
     (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
    # 第 3 組：親民黨 宋楚瑜（橘色系）
    [(35, "#FFF3E0"), (40, "#FFE0B2"), (45, "#FFCC80"), (50, "#FFB74D"),
     (55, "#FFA726"), (60, "#FF9800"), (65, "#FB8C00"), (70, "#F57C00"),
     (75, "#E65100"), (80, "#C24500"), (85, "#9C3A00"), (100, "#6E2600")],
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
# 2020 源資料用字（含中選會常用異體/簡筆）與 SHP 圖資用字不同，統一對照後再比對
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',
    '\U00025562': '槽',   # 坪林區石𕢥里 / 石槽
    '磘': '窯',
    '獇': '羌',
    '舘': '館',
    '廍': '部',
    '峯': '峰',
    '脚': '腳',
    '\ue006': '塭',      # 臺南安南區 塭南里 / 公(塭)里
    '\U00026c21': '那',  # 臺南新化區 𦰡拔里 / 那拔里
    '売': '壳',           # 臺中大安區 龜売里 / 龜壳里
    # ---- 2020 資料新增異體/通用字對照（SHP → 源資料）----
    '台': '臺',           # 富台/台西/臺子/霧台/丁台
    '双': '雙',           # 双溪/双福/双湖/双潭/双龍
    '豊': '豐',           # 和豊/豊崙/上豊/內豊/豊稠/豊收
    '塩': '鹽',           # 塩田/塩埕/塩行/塩洲/塩舘
    '硦': '弄',           # 中埔鄉 石硦 / 石弄
    '瑶': '瑤',           # 彰化市 南瑶 / 南瑤
    '凉': '涼',           # 瑪家鄉 凉山 / 涼山
    '壠': '壟',           # 關山鎮 里壠 / 里壟
    '菓': '果',           # 湖西 菓葉/大園 菓林 / 果葉/果林
    '壳': '殼',           # 大安區 龜[壳] / 龜殼
    '鷄': '雞',           # 竹東 鷄林 / 雞林
    '晋': '晉',           # 麻豆 晋江 / 晉江
    '厦': '廈',           # 萬丹 厦北/厦南 / 廈北/廈南
    '响': '響',           # 滿州 响林 / 響林
    '槺': '康',           # 清水/新屋 槺榔 / 康榔
    '嵵': '時',           # 馬公 [嵵]裡 / 時裡
    '萡': '箔',           # 四湖 [萡]子/[萡]東 / 箔子/箔東
    '坂': '板',           # 達仁 台坂/土坂 / 台板/土板
    '磜': '祭',           # 北埔 水磜 / 水祭
    '蘆': '盧',           # 蘆竹 蘆興 / 盧興
})

# 106 年村里界圖資（107 年 2 月版）以方括號內「同音字」代替 Big5 無法表示的罕見字，
# 此表將「含方括號之原名」還原成源資料/官方所用正字（僅影響含 '[' 的 SHP 名稱）。
BRACKET_HOMONYM = {
    '[回][瑤]里': '硘磘里',    # 南投竹山（原 硘磘里）
    '磚[瑤]里': '磚窯里',      # 彰化市、嘉義市西區
    '瓦[瑤]村': '瓦窯村',      # 埔鹽、麥寮、元長、新園
    '瓦[瑤]里': '瓦窯里',      # 新北中和
    '灰[瑤]里': '灰窯里',      # 新北中和
    '[柏]子村': '箔子村',      # 雲林四湖
    '[柏]東村': '箔東村',      # 雲林四湖
    '[舊]埔村': '欍埔村',      # 雲林水林
    '[慷]榔里': '康榔里',      # 臺中清水、桃園新屋
    '[槍]寮里': '羌寮里',      # 新北樹林
    '[帝]埔里': '坔埔里',      # 高雄鳥松
    '水[砌]村': '水祭村',      # 新竹北埔
    '里[龍]里': '里壟里',      # 臺東關山（原 里壠里）
}

# 多村里合併共用一組得票率（2020 資料以合併後之名稱代表，例如連江縣 22 村→9 村）。
# 每組第一個為源資料所用之名稱(錨點)，其餘為 SHP 中隸屬同一合併單位的村里，
# 填入與錨點相同之顏色。此表亦可視「、」分隔之 2024 資料整合後反推。
MERGE_GROUPS = {
    ("連江縣", "南竿"): [
        ["介壽村"],
        ["復興村", "福沃村"],
        ["清水村", "珠螺村"],
        ["仁愛村", "津沙村", "馬祖村", "四維村"],
    ],
    ("連江縣", "北竿"): [
        ["塘岐村", "后沃村"],
        ["橋仔村", "芹壁村", "坂里村", "白沙村"],
    ],
    ("連江縣", "莒光"): [
        ["青帆村", "田沃村", "西坵村"],
        ["福正村", "大坪村"],
    ],
    ("連江縣", "東引"): [
        ["中柳村", "樂華村"],
    ],
}

VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"}, {"舘", "館"}, {"磘", "窯"}, {"獇", "羌"}, {"曹", "槽"}, {"脚", "腳"},
]


def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    if "[" in s and s in BRACKET_HOMONYM:
        s = BRACKET_HOMONYM[s]
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


# ===================== 讀取得票率 Excel =====================
def load_vote_data(data_dir):
    """讀取 2020 全臺單一 Excel（工作表「村里層級明細」）。

    得票率欄位：{候選人}（{號次}）_得票率，依 CAND_NAMES 順序擷取（字尾 % 移除）。
    源資料若將多村里併為一列（以 、 分隔，如連江縣「復興村、福沃村」），
    拆解成各村(里)並共用同一組得票率，使多村合併地區能填入相同顏色。
    """
    by_key, by_town = {}, {}
    n_total, n_rows = 0, 0
    rate_cols_by_cand = {}
    files = sorted(glob.glob(os.path.join(data_dir, "2020*縣市鄉鎮村里.xlsx")))
    for f in files:
        df = pd.read_excel(f, sheet_name="村里層級明細", dtype=str)
        df.columns = [str(c) for c in df.columns]
        for cand in CAND_NAMES:
            cols = [c for c in df.columns if c.startswith(cand) and c.endswith(f"_{CAND_RATE_SUFFIX}")]
            if len(cols) != 1:
                raise ValueError(f"{os.path.basename(f)} 找不到 {cand} 得票率欄位：{CAND_RATE_SUFFIX}")
            rate_cols_by_cand[cand] = cols[0]
        rate_cols = [rate_cols_by_cand[c] for c in CAND_NAMES]
        for _, r in df.iterrows():
            county = normalize_text(r.get("縣市"))
            town = strip_town_suffix(r.get("鄉鎮市區"))
            vill_raw = normalize_text(r.get("村里"))
            if not county or not town or not vill_raw:
                continue
            try:
                vals = tuple(float(str(r[c]).strip().replace("%", "").replace("\u00a0", "")) for c in rate_cols)
            except (TypeError, ValueError):
                continue
            if not all(np.isfinite(v) for v in vals):
                continue
            n_total += 1
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
    # ---- 多村里合併單位：非錨點村里沿用同組得票率（如連江縣 22 村→9 村） ----
    for (m_county, m_town), groups in MERGE_GROUPS.items():
        for group in groups:
            anchor = strip_village_suffix(normalize_text(group[0]))
            akey = (m_county, m_town, anchor)
            if akey not in by_key:
                continue
            a_vals = by_key[akey]
            for alias in group[1:]:
                a_part = strip_village_suffix(normalize_text(alias))
                if not a_part:
                    continue
                key = (m_county, m_town, a_part)
                if key in by_key:
                    continue
                by_key[key] = a_vals
                by_town.setdefault((m_county, m_town), []).append((a_part, a_vals))
                n_rows += 1
    return by_key, by_town, n_rows, n_total


# ===================== 填色：油漆桶／洪水填充（共用） =====================
def flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy):
    """油漆桶式填色（畫圖軟體「填充／洪水填充」規則），單一縣市與全臺地圖共用。

    1) 堤壩 = 線稿 lines_mask（村里界 1px、鄉鎮市區界 2px、縣市地界 3px、
       金門/連江附圖外框 6px …）。線稿由同一組 matplotlib 繪線指令產生。
    2) 對堤壩以外的像素做 4-連通標記：1px 斜線也能阻斷 8 連通的斜向滲漏，
       故顏色不可能跨越任何一條黑線。
    3) 每個區域整塊填單色，顏色 = 區域內像素「中心點幾何所屬圖斑 id」的眾數。
       界線上 1px 的渲染/幾何落差會被眾數吸收，密集村里區（如永和）不再出現
       孤立錯色斑點或色塊滲透（單一取樣點則可能恰好落在落差像素而選錯圖斑）。

    為支援全臺圖（>1 億像素、上萬個圖斑），眾數不用 ncomp×nlab 的計數矩陣，
    而是「每區域散佈取樣 id → 一致度驗證 → 少數不一致的區域才精算」，記憶體 O(N)。

    回傳 (arr, ncomp, comp)：arr 為填色後 RGB uint8 陣列（尚未畫黑線）；
    ncomp/comp 為非線像素的 4-連通標記，供自檢重用避免重算。"""
    from rasterio.features import rasterize
    from affine import Affine

    # 顏色查找表：id 0 = 無資料（白），id i+1 = 第 i 個圖斑的填色
    lut = np.vstack([
        np.array([[255, 255, 255]], dtype=np.uint8),
        np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                  for hx in records["fill_hex"]], dtype=np.uint8),
    ])

    # 逐像素幾何判定（GDAL/rasterio 像素中心規則）：id = 圖斑序號 + 1，0 = 無圖斑
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)

    free = ~lines_mask
    ncomp, comp = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)

    seed = np.zeros(ncomp, dtype=np.int32)
    seed[comp.ravel()] = ids.ravel()          # 每區域代表 id（散佈賦值，O(N)）
    reps = seed[comp]
    agree = (ids == reps)
    cnt_all = np.bincount(comp.ravel(), minlength=ncomp)
    cnt_ok = np.bincount(comp.ravel(), weights=agree.ravel(), minlength=ncomp)
    del reps, agree
    bad = np.nonzero(cnt_ok < 0.5 * cnt_all)[0]
    for b in bad:                              # 正常情形 bad 為 0 個
        m = (comp == b)
        seed[b] = int(np.bincount(ids[m].ravel()).argmax())
    if len(bad):
        print(f"    洪水填充：{len(bad)} 個區域取樣不一致 → 已精算眾數")

    arr = lut[seed[comp]].astype(np.uint8)
    del ids, seed
    return arr, ncomp, comp


def check_region_single_color(arr, ncomp, comp):
    """油漆桶不變式自檢：每個非線 4-連通區域必須只含單一顏色（色不越過黑線）。"""
    from scipy import ndimage
    c = (arr[..., 0].astype(np.int32) << 16) | \
        (arr[..., 1].astype(np.int32) << 8) | arr[..., 2].astype(np.int32)
    idx = np.arange(1, ncomp)
    mn = ndimage.minimum(c, comp, index=idx)
    mx = ndimage.maximum(c, comp, index=idx)
    return ncomp - 1, int((mn != mx).sum())


def full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy):
    """全圖逐像素幾何參考比對（獨立方法：GDAL/rasterio 像素中心規則）。

    黑線像素不計。回傳 (與幾何參考不同色的像素數, 無圖斑處非白的像素數)。"""
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


# ===================== 主流程 =====================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 62)
    print("  2020 總統副總統選舉 全臺灣各村（里）得票率地圖")
    print("=" * 62)

    # ---- 讀 SHP（依內容自動判斷 .dbf 編碼：UTF-8 或 Big5）----
    shp_path = resolve_shp()
    gdf_all = None
    for enc in SHP_ENCODINGS:
        g = gpd.read_file(shp_path, encoding=enc)
        names = set(g["COUNTYNAME"].dropna().astype(str))
        if len(names & SHP_KNOWN_COUNTIES) >= 15:
            gdf_all = g
            break
    if gdf_all is None:
        gdf_all = g
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

    rate_cols = [f"rate{i}" for i in range(len(CAND_NAMES))]
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
    ax.set_facecolor(NO_DATA_COLOR)

    # ① 這裡「不」先填色：改成先把所有黑線畫完，再以線稿為堤壩做油漆桶洪水填充
    #    （見下方「顏色量化」段；顏色永不跨越黑線，密集村里區不再有孤立錯色斑點）
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
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor=NO_DATA_COLOR)
    plt.close(fig)
    buf.seek(0)

    img_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    del img_bgr
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    # ===================== 填色：油漆桶／洪水填充 =====================
    # 線稿（純黑線）即封閉堤壩；對堤壩以外每一塊 4-連通區域整塊填單色，
    # 顏色取該區域內像素幾何所屬村里的眾數 → 顏色永不跨越任何一條黑線。
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）...")
    lines_mask = np.zeros((img_h_px, img_w_px), dtype=bool)
    h2 = min(img_h_px, gray.shape[0]); w2 = min(img_w_px, gray.shape[1])
    lines_mask[:h2, :w2] = gray[:h2, :w2] < 128
    del gray
    sx = img_w_px / (maxx - minx)
    sy = img_h_px / (maxy - miny)
    arr, ncomp, comp = flood_fill_layer(records, lines_mask, img_w_px, img_h_px,
                                        minx, maxy, sx, sy)
    arr[lines_mask] = 0
    print(f"  黑像素合計：{int(lines_mask.sum())}  非線連通區域：{ncomp - 1} 塊")

    _nc, _nbad = check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")
    _nw, _nout = full_geom_check(arr, records, img_w_px, img_h_px, minx, maxy, sx, sy)
    print(f"  與逐像素幾何參考差異：{_nw} px、無圖斑處非白 {_nout} px（皆應 ≈0）")
    del lines_mask, comp
    quantized = arr
    del img_rgb

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