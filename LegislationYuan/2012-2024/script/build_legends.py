# -*- coding: utf-8 -*-
"""
歷屆立法委員不分區（政黨票）得票率地圖 —— 圖例產生器

做法沿用 board 管線的圖例規範（見 map/LEGEND.md §3.3 build_legend）：
  * 左側政黨名 → 右側該黨的得票率色階（每階一格，由淺到深）
  * 頂部一條比例尺，每 2 格標一次（＝每 10 個百分點），最右端標「以上」
  * 色階直接讀 LegislationYuan/color.txt，與地圖填色同一份資料

與 board 版的差異：
  * **深色字**（本專案的地圖是白底，LEGEND.md 的白字版是貼在深色看板上的）
  * 透明背景，方便直接疊在白色地圖的留白處
  * 每年只列「該屆地圖上真的出現過的色階組」

每年列出哪些政黨，是照「該屆地圖實際用色」定的（掃 PNG 像素比對 color.txt 色階）
＋生成日誌裡的「領先村里」統計交叉核對：

    年份   圖例列                       說明
    2008   國民黨、民進黨                —
    2012   國民黨、民進黨、綠黨          綠黨 2 個村里在原圖是自訂綠（40→#25BF52／45→#27CC58，
                                       不在 color.txt 內），故用 CUSTOM_RAMPS 補上，只填這兩格
    2016   國民黨、民進黨、無黨團結聯盟    無黨團結聯盟領先 22 個村里（第 6 組粉紅）
    2020   國民黨、民進黨、民眾黨、時代力量 民眾黨 1 個里；時代力量 1 個里（第 8 組綠，35–80%）
    2024   國民黨、民進黨、民眾黨、時代力量 民眾黨 40 個村里；時代力量 1 個里

輸出：map/legend/<年份>.png（透明背景 RGBA）

執行：
    py script/build_legends.py            # 全部年份
    py script/build_legends.py 2024       # 只做指定年份
"""
import ast
import os
import sys

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                 # …\LegislationYuan\2012-2024
LEGIS_DIR = os.path.dirname(PROJECT_DIR)                  # …\LegislationYuan

COLOR_TXT = os.path.join(LEGIS_DIR, "color.txt")
OUT_DIR = os.path.join(PROJECT_DIR, "map", "legend")

# 字型：與 board 管線（map/LEGEND.md §3.2、national_map.FONT_CANDIDATES）同一支
# 源石黑體 TW Heavy；找不到才退回微軟正黑粗體
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]

# ===================== 版面常數 =====================
NAME_W = 570          # 政黨名欄寬（最長「無黨籍／其他政黨」8 字 × 64px）
CELL = 150            # 每一階色塊寬
CELL_H = 112          # 色塊高
PITCH = 156           # 每列間距
RULER_H = 96          # 頂部比例尺高
TICK_STEP = 2         # 每 2 階標一次（＝10 個百分點）
PAD = 16

INK = (28, 30, 34)    # 深色字（白底用）
# 對照 LEGEND.md 的白字版：深色看板用 (255,255,255)，白底改用深灰

F_NAME, F_TICK, F_UNIT = 64, 40, 32

# ===================== 政黨 → 色階組 =====================
# color.txt 由上而下：0 無黨籍 / 1 國民黨 / 2 民進黨 / 3 新黨 / 4 宋楚瑜 / 5 民眾黨 /
#                 6 無黨團結聯盟 / 7 時代力量（35–80%，10 階）
RAMP_GROUP = {
    "中國國民黨": 1,
    "民主進步黨": 2,
    "台灣民眾黨": 5,
    "新黨": 3,
    "無黨團結聯盟": 6,
    "時代力量": 7,
    "無黨籍／其他政黨": 0,
}

# 少數政黨在原圖用自訂色（不在 color.txt 內），在此補上實際色階
CUSTOM_RAMPS = {
    "綠黨": [(40, "#25BF52"), (45, "#27CC58")],
}

# 每年要列出的政黨（順序即圖例由上而下的順序）
# 2020／2024 的第 0 組灰階＝時代力量（各領先 1 個里），直接寫明黨名不用「其他政黨」
# 2012 另有綠黨 2 個村里，原圖是自訂綠，故補第三列
YEAR_PARTIES = {
    2008: ["中國國民黨", "民主進步黨"],
    2012: ["中國國民黨", "民主進步黨", "綠黨"],
    2016: ["中國國民黨", "民主進步黨", "無黨團結聯盟"],
    2020: ["中國國民黨", "民主進步黨", "台灣民眾黨", "時代力量"],
    2024: ["中國國民黨", "民主進步黨", "台灣民眾黨", "時代力量"],
}


def load_ramps():
    """讀 color.txt（Python 串列字面，跳過註解行）→ 全部色階組。"""
    with open(COLOR_TXT, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    return ast.literal_eval("\n".join(lines).split("=", 1)[1])


def font_path():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError("找不到可用的中文字型：%s" % FONT_CANDIDATES)


_FONT_PATH = None


def font(size):
    global _FONT_PATH
    if _FONT_PATH is None:
        _FONT_PATH = font_path()
    return ImageFont.truetype(_FONT_PATH, size)


def ramp_of(party, ramps):
    """政黨 → [(上限%, 色碼)]。自訂色的（綠黨）走 CUSTOM_RAMPS，其餘查 color.txt 組別。"""
    if party in CUSTOM_RAMPS:
        return CUSTOM_RAMPS[party]
    return ramps[RAMP_GROUP[party]]


def build(year, ramps, out_path):
    parties = YEAR_PARTIES[year]
    cells = {p: ramp_of(p, ramps) for p in parties}

    # 欄位＝百分點刻度，取最長那一組（12 階：35…85＋100）當 grid
    grid = max(cells.values(), key=len)
    columns = [pct for pct, _ in grid]
    col_index = {pct: j for j, pct in enumerate(columns)}
    ticks_src = grid

    W = PAD * 2 + NAME_W + len(columns) * CELL
    H = PAD * 2 + RULER_H + PITCH * len(parties)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_name, f_tick, f_unit = font(F_NAME), font(F_TICK), font(F_UNIT)
    x0_name = PAD
    x0_cell = PAD + NAME_W

    # ---- 頂部比例尺：每 10 個百分點標一次，刻度對齊色階格線 ----
    base_y = PAD + RULER_H - 30
    for j, (pct, _) in enumerate(ticks_src):
        if j % TICK_STEP:                  # 每 2 階標一次：35 / 45 / 55 / 65 / 75 / 85
            continue
        x = x0_cell + j * CELL
        d.line([x, base_y + 10, x, base_y + 40], fill=INK + (110,), width=3)
        d.text((x + 8, base_y + 6), "%d%%" % pct, font=f_tick, fill=INK + (230,), anchor="ls")
    # 最右端「以上」
    tail = "以上"
    d.text((W - PAD - 6, base_y + 6), tail, font=f_unit, fill=INK + (150,), anchor="rs")

    # ---- 各列色階 ----
    for i, p in enumerate(parties):
        top = PAD + RULER_H + i * PITCH
        # 政黨名（垂直居中於色塊）
        d.text((x0_name + 4, top + CELL_H // 2), p, font=f_name, fill=INK + (255,), anchor="lm")
        for pct, hx in cells[p]:
            j = col_index.get(pct)
            if j is None:                  # 落在 grid 外的階（例如 0%）跳過
                continue
            x = x0_cell + j * CELL
            col = tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))
            d.rectangle([x, top, x + CELL - 2, top + CELL_H - 1], fill=col + (255,))
            # 細框：淺階（白底附近）自己也看得見
            d.rectangle([x, top, x + CELL - 2, top + CELL_H - 1],
                        outline=(0, 0, 0, 28), width=1)

    img.save(out_path, "PNG", optimize=True)
    return img.size


def main():
    years = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(YEAR_PARTIES)
    ramps = load_ramps()
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 62)
    print("  立委不分區（政黨票）歷年圖例")
    print(f"  色階：{COLOR_TXT}（{len(ramps)} 組）")
    print(f"  字型：{font_path()}")
    print("=" * 62)
    for y in years:
        if y not in YEAR_PARTIES:
            print(f"  ⚠️ 沒有 {y} 的設定，略過")
            continue
        out = os.path.join(OUT_DIR, f"{y}.png")
        w, h = build(y, ramps, out)
        names = "、".join(YEAR_PARTIES[y])
        print(f"  {y}.png  {w}×{h}  {names}")
    print(f"\n  輸出目錄：{OUT_DIR}")


if __name__ == "__main__":
    main()
