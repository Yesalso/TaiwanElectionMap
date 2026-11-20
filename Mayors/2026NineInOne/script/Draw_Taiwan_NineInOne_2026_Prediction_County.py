# -*- coding: utf-8 -*-
"""
全臺灣 2026 年九合一選舉（縣市長）**得票率預測**地圖 —— 縣市版 ＋ 圖例

由 `Draw_Taiwan_AtLarge_2016_2020_2024_County.py` 移植（管線、版面、自檢全部重用）：
底圖＝111 年官方村里界歷史圖資 SHP（VILLAGE_MOI_1111118）→ 逐村里 dissolve 到
22 縣市；不畫鄉鎮界、不畫村里界，只有縣市界 6px ＋ 海岸線 1px ＋ 金馬附圖外框黑線。

與參考腳本的差異：**沒有中選會得票資料**，填色完全由本檔 `PREDICTIONS`
（使用者指定的 2026 九合一預測表）決定：
  * 每縣市一格：「勝出政黨 + 得票率區間中值」→ 依 `LegislationYuan/color.txt`
    對應政黨色階取色（得票率 → 落點階色，與歷屆地圖同一套規則）
  * 焦灼縣市（新竹縣／高雄市）：沿用 **平票斜線紋** 畫法——底色＝一方 45–50% 階色、
    45° 對角斜線紋＝另一方 45–50% 階色（`nat.apply_tie_stripes`，界線一律不被侵占）
  * 底／紋誰藍誰綠：跟該縣市上屆縣市長勝方（新竹縣＝藍底綠紋、高雄市＝綠底藍紋），
    在 `PREDICTIONS` 改 `tie_party` 即可對調

輸出（map/，三檔）：
  全臺灣2026年九合一選舉_縣市長得票率預測地圖_縣市版.png   ← 一張地圖（含圖例）
    （圖例直式貼進左下角空海；#FFFFFF 一律轉透明＝無背景 RGBA）
  全臺灣2026年九合一選舉_縣市長得票率預測_圖例.png         ← 一張圖例
    （國民黨／民進黨／民眾黨 三欄直式色階，由下往上；不畫焦灼行；
     色塊描邊與外框＝#FCFCFC；透明背景 RGBA）
  全臺灣2026_九合一預測_縣市版_稽核.md                     ← 預測表與色碼稽核

執行：
  C:/Users/Windows/PyCharmMiscProject/.venv/Scripts/python.exe ^
      D:/Windows/TaiwanElection/Mayors/2026NineInOne/script/Draw_Taiwan_NineInOne_2026_Prediction_County.py
"""
import os
import sys
import time
import math
import ast

import numpy as np
import geopandas as gpd
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REF_SCRIPT_DIR = r"D:\Windows\TaiwanElection\LegislationYuan\2012-2024\script"
for _p in (SCRIPT_DIR, REF_SCRIPT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 管線重用：base＝2012 村里版全模組；yrs＝逐年底圖 SHP 路徑；
# t12＝2012 鄉鎮版（未編定村里併回、逐部件離島碎塊清理）；
# c12＝2012 縣市版（只清孔不砍部件的 clean_county_parts）
import Draw_Taiwan_AtLarge_2012 as base
import Draw_Taiwan_AtLarge_2016_2020_2024 as yrs
import Draw_Taiwan_AtLarge_2012_Township as t12
import Draw_Taiwan_AtLarge_2012_County as c12

nat = base.nat

PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                    # …\Mayors\2026NineInOne
OUT_DIR = os.path.join(PROJECT_DIR, "map")
COLOR_TXT = r"D:\Windows\TaiwanElection\LegislationYuan\color.txt"

# 底圖：111 年村里界 SHP（與 2024 立委版同一份，2026 現行區劃）
SHP_PATH = yrs.YEAR_SHP[2024]

# 畫布（同 2012/2016~2024 縣市版）
MAX_W_PX = 3000
MAX_H_PX = 3750
METERS_PER_PIXEL = base.METERS_PER_PIXEL
PAD_FRAC = base.PAD_FRAC

N_COUNTY = 22
OFFICIAL_ORDER = [
    "臺北市", "新北市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "新竹縣",
    "桃園市", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣",
    "臺東縣", "花蓮縣", "宜蘭縣", "澎湖縣", "金門縣", "連江縣",
]

# ===================== 讀 color.txt（與地圖填色同一份色階） =====================
def load_ramps(path=COLOR_TXT):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    return ast.literal_eval("\n".join(lines).split("=", 1)[1])

RAMPS = load_ramps()
# color.txt 由上而下：0 無黨籍灰 / 1 國民黨藍 / 2 民進黨綠 / 3 新黃 / 4 宋橘 /
#                     5 民眾黨青 / 6 無盟粉 / 7 時力黃
RAMP_GROUP = {
    "中國國民黨": 1,
    "民主進步黨": 2,
    "台灣民眾黨": 5,
}
PARTY_STOPS = {p: RAMPS[g] for p, g in RAMP_GROUP.items()}
# 管線模組（自檢等）統一從 base 取用
base.PARTIES = list(PARTY_STOPS)
base.PARTY_STOPS = PARTY_STOPS

# ===================== 2026 九合一（縣市長）得票率預測表 =====================
# 每格：party＝領先政黨；rate＝得票率區間中值（決定色階深淺落點）；
#       tie_party＝焦灼斜線紋的另一方（None＝單色）
# 縣市鍵＝底圖 OLD_COUNTY 正規名（臺）
PREDICTIONS = {
    "臺北市": {"party": "中國國民黨", "rate": 52.5},
    "新北市": {"party": "中國國民黨", "rate": 47.5, "tie_party": "民主進步黨"},  # 焦灼：藍底綠紋
    "基隆市": {"party": "中國國民黨", "rate": 52.5},
    "桃園市": {"party": "中國國民黨", "rate": 62.5},
    "宜蘭縣": {"party": "民主進步黨", "rate": 47.5, "tie_party": "中國國民黨"},  # 焦灼：綠底藍紋
    "新竹縣": {"party": "中國國民黨", "rate": 47.5, "tie_party": "民主進步黨"},  # 焦灼：藍底綠紋
    "新竹市": {"party": "台灣民眾黨", "rate": 57.5},
    "苗栗縣": {"party": "中國國民黨", "rate": 62.5},
    "臺中市": {"party": "中國國民黨", "rate": 57.5},
    "彰化縣": {"party": "民主進步黨", "rate": 47.5},
    "雲林縣": {"party": "中國國民黨", "rate": 57.5},
    "南投縣": {"party": "中國國民黨", "rate": 62.5},
    "嘉義縣": {"party": "民主進步黨", "rate": 57.5},
    "嘉義市": {"party": "民主進步黨", "rate": 47.5, "tie_party": "中國國民黨"},  # 焦灼：綠底藍紋
    "臺南市": {"party": "民主進步黨", "rate": 62.5},
    "高雄市": {"party": "民主進步黨", "rate": 47.5, "tie_party": "中國國民黨"},  # 焦灼：綠底藍紋
    "屏東縣": {"party": "民主進步黨", "rate": 57.5},
    "花蓮縣": {"party": "中國國民黨", "rate": 52.5},
    "臺東縣": {"party": "中國國民黨", "rate": 57.5},
    "澎湖縣": {"party": "中國國民黨", "rate": 42.5},
    "金門縣": {"party": "中國國民黨", "rate": 80.0},
    "連江縣": {"party": "中國國民黨", "rate": 80.0},
}

# 預測表的原始區間（只供稽核表顯示）
RATE_RANGE_TEXT = {
    "臺北市": "50–55", "新北市": "45–50（焦灼）", "基隆市": "50–55",
    "桃園市": "60–65", "宜蘭縣": "45–50（焦灼）", "新竹縣": "45–50（焦灼）",
    "新竹市": "55–60", "苗栗縣": "60–65", "臺中市": "55–60", "彰化縣": "45–50",
    "雲林縣": "55–60", "南投縣": "60–65", "嘉義縣": "55–60",
    "嘉義市": "45–50（焦灼）", "臺南市": "60–65", "高雄市": "45–50（焦灼）",
    "屏東縣": "55–60", "花蓮縣": "50–55", "臺東縣": "55–60",
    "澎湖縣": "40–45", "金門縣": "80", "連江縣": "80",
}


def assign_prediction_colors(counties):
    """預測表 → 各縣市 fill_hex / tie_hex / win_party / pred_rate。"""
    counties = counties.copy().reset_index(drop=True)
    fills, wins, ties, rates = [], [], [], []
    miss = []
    for _, r in counties.iterrows():
        c = r["OLD_COUNTY"]
        spec = PREDICTIONS.get(c)
        if spec is None:
            miss.append(c)
            fills.append("#FFFFFF")
            wins.append("")
            ties.append(np.nan)
            rates.append(np.nan)
            continue
        p, rate = spec["party"], spec["rate"]
        hx = nat.get_color_by_value(rate, PARTY_STOPS[p])
        fills.append(hx)
        wins.append(p)
        rates.append(rate)
        tp = spec.get("tie_party")
        ties.append(nat.get_color_by_value(rate, PARTY_STOPS[tp]) if tp else np.nan)
    counties["fill_hex"] = fills
    counties["win_party"] = wins
    counties["tie_hex"] = ties
    counties["pred_rate"] = rates
    return counties, miss


# ===================== 圖例（直式：色階由下往上，貼進地圖左下角） =====================
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]
# 圖例邊框（與地圖界線同一近白色）
LEG_BORDER = (252, 252, 252, 255)          # #FCFCFC
LEG_PARTIES = ["中國國民黨", "民主進步黨", "台灣民眾黨"]
# 政黨名換行（每欄 110px 只放得下 2～3 字／行）
LEG_NAME_LINES = {
    "中國國民黨": ("中國", "國民黨"),
    "民主進步黨": ("民主", "進步黨"),
    "台灣民眾黨": ("台灣", "民眾黨"),
}
# 政黨名顏色（取 color.txt 對應黨色階的 65% 深階，白底／透明底皆清晰）
LEG_NAME_COLOR = {
    "中國國民黨": "#006591",    # 藍
    "民主進步黨": "#54B337",    # 綠
    "台灣民眾黨": "#006666",    # 青
}
LEG_CELL_W = 110                            # 每階色塊寬
LEG_CELL_H = 88                             # 每階色塊高（直式＝一階一列）
LEG_COL_GAP = 30                            # 欄與欄之間的間距
LEG_NAME_H = 156                            # 頂部政黨名列高（兩行字）
LEG_TICK_GAP = 30                           # 刻度文字右緣 → 色塊欄左緣
LEG_PAD = 18                                # 外框內左右留白（左右相等）
LEG_MARGIN = 40                             # 貼進地圖左下角的留邊（px）
TICK_STEP = 2                               # 每 2 階標一次（＝10 個百分點）
INK = (28, 30, 34)

_FONT_PATH = None


def _font(size):
    global _FONT_PATH
    if _FONT_PATH is None:
        for p in FONT_CANDIDATES:
            if os.path.isfile(p):
                _FONT_PATH = p
                break
        else:
            raise RuntimeError("找不到可用的中文字型：%s" % FONT_CANDIDATES)
    return ImageFont.truetype(_FONT_PATH, size)


def _rgb255(hx):
    return tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))


def _draw_justified(d, cx, y_mid, lines, font, fill):
    """多行文字分散對齊（兩端對齊）：各行拉伸到同一寬度後水平置中。
    字距加寬只加在「行內字與字之間」（首尾字不動），例如
    「中國」兩字拉開成與「國民黨」三字同寬。"""
    lh = 52                                   # 行距
    widths = [d.textlength(ln, font=font) for ln in lines]
    target = max(widths)
    y_start = y_mid - lh * (len(lines) - 1) / 2
    for k, ln in enumerate(lines):
        y = y_start + k * lh
        w = widths[k]
        if len(ln) > 1 and w < target:
            extra = (target - w) / (len(ln) - 1)
            x = cx - target / 2
            for ch in ln:
                d.text((x, y), ch, font=font, fill=fill, anchor="ls")
                x += d.textlength(ch, font=font) + extra
        else:
            d.text((cx, y), ln, font=font, fill=fill, anchor="mm")


def build_legend(out_path):
    """直式圖例：三黨各一欄、色階**由上往下**（得票率低在上、高在下），
    政黨名兩行分散對齊＋黨色、欄間留距、左側百分比刻度＋短刻度線；
    「得票柱」到外框的距離左右相等（刻度文字收在左側留白內）；
    不畫焦灼行；全部邊框（色塊描邊＋外框）＝#FCFCFC；透明背景 RGBA。"""
    cells = {p: PARTY_STOPS[p] for p in LEG_PARTIES}
    grid = max(cells.values(), key=len)
    columns = [pct for pct, _ in grid]
    col_index = {pct: j for j, pct in enumerate(columns)}
    n_lv = len(columns)

    # ---- 左右留白＝「得票柱」到外框的距離：左側（含刻度）＝右側（純空白） ----
    f_name, f_tick, f_unit = _font(36), _font(30), _font(26)
    tick_pcts = [pct for j, (pct, _) in enumerate(grid) if j % TICK_STEP == 0]
    tick_w = max(max(f_tick.getlength("%d%%" % pct) for pct in tick_pcts),
                 f_unit.getlength("以上"))
    x_text = LEG_PAD + tick_w                 # 刻度文字右緣（右對齊基準）
    x0_cell = x_text + LEG_TICK_GAP           # 第一欄得票柱左緣
    margin = x0_cell                          # 左側：外框 → 得票柱距離
    n_cols = len(LEG_PARTIES)
    W = int(round(x0_cell + n_cols * LEG_CELL_W + (n_cols - 1) * LEG_COL_GAP
                  + margin))                  # 右側：得票柱 → 外框同距
    H = LEG_PAD * 2 + LEG_NAME_H + n_lv * LEG_CELL_H

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y_top = LEG_PAD + LEG_NAME_H              # 最淺階（35%）頂邊＝得票率低在上
    y_bottom = y_top + n_lv * LEG_CELL_H      # 最深階底邊＝得票率高在下

    # ---- 三黨欄：政黨名（兩行分散對齊、黨色）在上，色階由上往下加深 ----
    for i, p in enumerate(LEG_PARTIES):
        x = x0_cell + i * (LEG_CELL_W + LEG_COL_GAP)
        cx = x + LEG_CELL_W // 2
        lines = LEG_NAME_LINES.get(p, (p,))
        fill = _rgb255(LEG_NAME_COLOR.get(p, INK)) + (255,)
        _draw_justified(d, cx, LEG_PAD + LEG_NAME_H // 2, lines,
                        f_name, fill)
        for pct, hx in cells[p]:
            j = col_index.get(pct)
            if j is None:
                continue
            y = y_top + j * LEG_CELL_H        # j=0（35%）→ 最上（低得票率在上）
            col = tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))
            d.rectangle([x, y, x + LEG_CELL_W - 2, y + LEG_CELL_H - 1],
                        fill=col + (255,), outline=LEG_BORDER, width=1)

    # ---- 左側刻度：每 2 階標一次（短刻度線＋百分比）；最底端標「以上」 ----
    for j, (pct, _) in enumerate(grid):
        if j % TICK_STEP:
            continue
        y = y_top + j * LEG_CELL_H            # 該階的頂邊界線
        d.line([x_text + 6, y, x_text + 24, y], fill=INK + (110,), width=2)
        d.text((x_text, y), "%d%%" % pct, font=f_tick, fill=INK + (230,),
               anchor="rs")
    d.text((x_text, y_bottom), "以上", font=f_unit, fill=INK + (150,),
           anchor="rs")

    # ---- 外框：#FCFCFC ----
    d.rectangle([0, 0, W - 1, H - 1], outline=LEG_BORDER, width=3)

    img.save(out_path, "PNG", optimize=True)
    return img.size


# ===================== 稽核報告 =====================
def write_audit_md(counties, miss, md_path):
    order = {c: i for i, c in enumerate(OFFICIAL_ORDER)}
    rows = counties.assign(_o=counties["OLD_COUNTY"].map(
        lambda c: order.get(c, 999))).sort_values(["_o", "OLD_COUNTY"])
    L = [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         "- 性質：**2026 九合一（縣市長）得票率預測**（非官方選舉結果）",
         "- 填色單位：**縣市**，全圖只有 22 塊顏色（焦灼縣市另有 45° 斜線紋）",
         f"- 底圖：**{os.path.basename(SHP_PATH)} 村里界 SHP** → 逐村里 dissolve 到縣市",
         f"- 色階：`{COLOR_TXT}`（與歷屆地圖同一份）", "",
         "### 1. 22 縣市預測填色一覽（依中選會公告順序）", "",
         "| # | 縣市 | 預測領先 | 得票率區間 | 取色得票率 | 底色色碼 | 斜線紋色碼 |",
         "|---:|---|---|---|---:|---|---|"]
    for i, (_, r) in enumerate(rows.iterrows(), 1):
        c = r["OLD_COUNTY"]
        if str(r["win_party"]) == "":
            L.append(f"| {i} | {c} | （無預測資料，留白） | — | — | — | — |")
            continue
        tie = r["tie_hex"]
        tie_txt = f"`{tie}`" if isinstance(tie, str) else "—"
        L.append(f"| {i} | {c} | {r['win_party']} | {RATE_RANGE_TEXT.get(c, '—')} | "
                 f"{r['pred_rate']:.1f} | `{r['fill_hex']}` | {tie_txt} |")
    L.append("")
    L += ["### 2. 焦灼縣市（平票斜線紋畫法）", ""]
    tie_rows = rows[rows["tie_hex"].notna()]
    if len(tie_rows):
        for _, r in tie_rows.iterrows():
            L.append(f"- **{r['OLD_COUNTY']}**：底色 {r['win_party']} "
                     f"`{r['fill_hex']}` ＋ 45° 斜線紋 "
                     f"{PREDICTIONS[r['OLD_COUNTY']]['tie_party']} `{r['tie_hex']}`"
                     "（兩黨預測皆 45–50%）")
    else:
        L.append("-（無）")
    L.append("")
    if miss:
        L += ["### 3. 底圖有、預測表缺的縣市（留白）", ""] + [f"- {c}" for c in miss] + [""]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ===================== 主流程 =====================
def run():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_png = os.path.join(
        OUT_DIR, "全臺灣2026年九合一選舉_縣市長得票率預測地圖_縣市版.png")
    out_legend = os.path.join(
        OUT_DIR, "全臺灣2026年九合一選舉_縣市長得票率預測_圖例.png")
    out_md = os.path.join(OUT_DIR, "全臺灣2026_九合一預測_縣市版_稽核.md")

    print("=" * 66)
    print("  全臺灣 2026 九合一（縣市長）得票率預測地圖 —— 縣市版（22 縣市）")
    print(f"  【底圖＝{os.path.basename(SHP_PATH)} 村里界 SHP】")
    print("  填色單位＝縣市；不畫鄉鎮界、不畫村里界；焦灼＝平票斜線紋")
    print("=" * 66)

    # ---- ① 底圖：村里界 SHP，全臺一套 ----
    gdf = base._read_shp_base(SHP_PATH)
    gdf = t12.reattach_unassigned_villages(gdf, path=SHP_PATH)
    gdf = base.add_old_county(gdf)
    print(f"  底圖（{os.path.basename(SHP_PATH)}）村里圖斑：{len(gdf)}；"
          f"縣市：{gdf['OLD_COUNTY'].nunique()}")
    gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = t12.strip_far_parts_by_part(gdf)

    # ---- ② 版面：金馬附圖 ----
    gdf, boxes = base.layout_insets(gdf)

    # ---- ③ dissolve 到縣市 ----
    counties = gdf.dissolve(by=["OLD_COUNTY"]).reset_index()
    counties = base.remove_ring_slits(counties)
    counties = c12.clean_county_parts(counties)
    print(f"  縣市：{len(counties)}")
    if len(counties) != N_COUNTY:
        print(f"  ⚠️ 填色單位 {len(counties)} 個 ≠ 22 個："
              f"{sorted(counties['OLD_COUNTY'])}")

    # ---- ④ 預測表對位與填色 ----
    counties, miss = assign_prediction_colors(counties)
    map_set = set(counties["OLD_COUNTY"])
    orphan = sorted(c for c in PREDICTIONS if c not in map_set)
    print(f"  預測對位：有預測 {int((counties['win_party'] != '').sum())}／"
          f"{len(counties)}；無預測 {len(miss)} {miss if miss else ''}；"
          f"預測表孤兒縣市 {len(orphan)} {orphan if orphan else ''}")
    for p, n in counties.loc[counties["win_party"] != "", "win_party"] \
            .value_counts().items():
        print(f"    預測領先縣市：{p} {int(n)}")
    n_tie = int(counties["tie_hex"].notna().sum())
    print(f"    焦灼（斜線紋）縣市：{n_tie}")
    write_audit_md(counties, miss, out_md)
    print(f"  稽核報告：{out_md}")

    # ---- 畫布（長寬上限 3000 × 3750 px） ----
    minx, miny, maxx, maxy = counties.total_bounds
    for _cn, (_bx0, _by0, _bx1, _by1), _lw in boxes:
        minx, miny = min(minx, _bx0), min(miny, _by0)
        maxx, maxy = max(maxx, _bx1), max(maxy, _by1)
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w, geo_h = maxx - minx, maxy - miny
    scale = max(geo_w / MAX_W_PX, geo_h / MAX_H_PX, METERS_PER_PIXEL)
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（上限 {MAX_W_PX}×{MAX_H_PX}，"
          f"{w_px * h_px / 1e6:.1f} 百萬像素）")

    # ---- ⑤ 縣市界層：只有縣市界 6px ----
    _thick_cty, coast_geom, county_segs = base.compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g_.length for g_ in county_segs) / 1000:.0f} km）")
    base.audit_county_segments(counties, county_segs)
    county_layer = base.render_county_segments_mask(
        county_segs, counties.crs, w_px, h_px, minx, maxx, miny, maxy)
    print(f"  縣市界層：{int(county_layer.sum())} px（閾值 {base.THRESHOLD_VAL}）")

    # ---- 附圖外框專用遮罩 ----
    box_mask = base.render_inset_box_mask(boxes, w_px, h_px,
                                          minx, maxx, miny, maxy)
    print(f"  附圖外框遮罩：{int(box_mask.sum())} px")

    # ---- 海岸線 1px（本島 ＋ 澎湖金馬） ----
    coast_skel = base.render_main_coast_layer(coast_geom, w_px, h_px,
                                              minx, maxy, sx, sy)
    thin_skel = base.render_thin_coast_layer(gdf, w_px, h_px,
                                             minx, maxy, sx, sy)
    if thin_skel is None:
        thin_skel = np.zeros((h_px, w_px), dtype=bool)
    print(f"  海岸線層：本島 {int(coast_skel.sum())} px ＋ "
          f"澎湖金馬 {int(thin_skel.sum())} px")

    lines_mask = county_layer | coast_skel | thin_skel | box_mask
    del coast_skel, thin_skel

    base.check_reef_drawn(gdf, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ---- 填色（洪水填充；填色單位＝縣市） ----
    print("  填色（洪水填充／油漆桶規則，填色單位＝縣市）…")
    records = counties[["OLD_COUNTY", "fill_hex", "tie_hex", "win_party",
                        "pred_rate"]].copy()
    records = gpd.GeoDataFrame(records, geometry=counties.geometry.values,
                               crs=counties.crs)
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    arr[lines_mask] = np.array(base.LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0        # 附圖外框＝黑線
    print(f"  非線連通區域：{ncomp - 1} 塊（填色單位 {len(records)} 個縣市）；"
          f"線色 {base.LINE_COLOR}、附圖外框 黑 (0,0,0)")

    # ---- 自檢（單色不變式須在斜線紋「之前」） ----
    _nc, _nbad = nat.check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")
    del comp

    # ---- 焦灼斜線紋（界線像素一律保護，不侵占） ----
    if n_tie:
        n_done = nat.apply_tie_stripes(arr, records, w_px, h_px, minx, maxy,
                                       sx, sy, lines_mask=lines_mask)
        _line_kept = int((arr[lines_mask] == np.array(base.LINE_RGB,
                        dtype=np.uint8)).all(axis=1).sum())
        print(f"  斜線紋後界線完整性：{_line_kept}/{int(lines_mask.sum())} "
              f"線像素仍為線色（應相等）")

    # ---- 自檢：逐像素幾何參考 ----
    _nw, _nout = nat.full_geom_check(arr, records, w_px, h_px, minx, maxy,
                                     sx, sy, lines_mask=lines_mask,
                                     ignore_mask=lines_mask)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%）；"
          f"圖斑外非白 {_nout} px（皆應 ≈0）")

    # ---- 自檢：全圖只含允許色 ----
    allowed = {(255, 255, 255), (0, 0, 0),
               tuple(int(v) for v in base.LINE_RGB)}
    for stops in PARTY_STOPS.values():
        for _u, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in nat.hex2rgb(hx)))
    _uniq, _cnt = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    _bad = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_uniq, _cnt)
            if tuple(int(x) for x in c) not in allowed]
    print(f"  全圖顏色 {len(_uniq)} 種（允許 {len(allowed)}）；"
          f"非允許色像素 {sum(n for _, n in _bad)}（應為 0）")
    if _bad:
        print(f"  ⚠️ 非允許色：{_bad[:5]}")

    # ---- 圖例（直式一張，單獨輸出） ----
    lw, lh = build_legend(out_legend)
    print(f"  Saved: {out_legend}  ({lw}×{lh}px, 透明背景)")

    # ---- 合成：#FFFFFF → 透明（無背景），圖例貼進左下角空地 ----
    white = (arr == 255).all(axis=2)
    rgba = np.dstack([arr, np.where(white, 0, 255).astype(np.uint8)])
    pil_img = Image.fromarray(rgba, mode="RGBA")
    del arr
    H, W = white.shape
    legend_img = Image.open(out_legend)
    paste_x = LEG_MARGIN
    paste_y = H - legend_img.height - LEG_MARGIN
    pil_img.alpha_composite(legend_img, dest=(paste_x, paste_y))
    print(f"  圖例貼入左下角：({paste_x}, {paste_y})、"
          f"{legend_img.width}×{legend_img.height}px")
    del legend_img
    base.save_png(pil_img, out_png)
    print(f"\n  Saved: {out_png}  ({W}×{H}px, 白色已轉透明＋含圖例)")

    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== 2026 九合一預測 縣市版 finished ====")


if __name__ == "__main__":
    run()
