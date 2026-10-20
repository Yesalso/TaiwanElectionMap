# -*- coding: utf-8 -*-
"""
由 DrawTaichungCityLabeled.py 派生：臺中市核心 8 區 · 民國 85 年（1996）村里界「帶地名」地圖。

資料來源：區里界_region.shp（民國85年臺中市村里界），內容僅含當時臺中市轄區
（中區/東區/南區/西區/北區/北屯區/西屯區/南屯區 共 8 區、224 里）。
民國85年臺中市尚未改制為 29 區，故其餘 21 區不在本圖（資料本身即不含）。

相對模板的差異（皆以字串替換達成，模板邏輯完全不動）：
  1. 資料來源換成 85 年區里界 SHP，並把欄位 區名/里名 對應成模板的 TOWNNAME/VILLNAME，
     另外補一個 COUNTYNAME 欄位讓模板的診斷語句照常運作；
  2. 比例尺 1px=4m（放大 10% → 實際 1px≈3.64m），與核心合圖同級；
     本圖範圍只有核心 8 區（23.3×12.6 km），故長寬皆 < MAX_PX；
  3. 全圖皆為核心 8 區，等同 Dense 放大圖設定：
     NUMBER_AREA_PX = DENSE_SKIP_AREA_PX = 0 → 224 里一律先試中文地名；
     NUMBER_WHEN_TEXT_FAILS = False → 塞不下就繼續縮字＋網格掃描＋描邊暈圈，絕不用數字，
     故不產生右側編號圖例，畫布自動裁掉圖例區；
     FONT_MIN 16 / GRID_FONT_MIN 12 / TOWN_FONT_MIN 24（區名寧可字小也不壓村里名）；
  4. 本圖即最終呈現，不做「超標區」判定、不寫主圖的獨立出圖清單；
  5. 配色以檔名為種子（隨機淡雅 5 色，固定種子可重現）。

輸出：Taichung/Taichung1996_Core_Labeled.png

用法：
  python DrawTaichungCore1996Labeled.py
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTaichungCityLabeled.py")

SHP = (r"D:\Windows\Documents\村里界歷史圖資_111\臺中市85年區里界_UTF8"
       r"\臺中市85年區里界_UTF8\區里界_region.shp")
OUT_STEM = "Taichung1996_Core"
CORE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]
# 主圖上「只畫界線（不標字、不標編號）」的區；這兩區另出 1px=2m 放大圖
# （見 DrawTaichungCore1996Zoom.py），故主圖不必勉強塞字
STRICT_TOWNS = ["北區", "中區"]
MILES_PER_PIXEL = 4.0

with open(_SRC, encoding="utf-8") as _f:
    code = _f.read()


def sub(old, new, tag):
    global code
    assert old in code, f"找不到片段：{tag}"
    code = code.replace(old, new, 1)


# ---- 1. 資料來源 + 欄位對應（區名→TOWNNAME、里名→VILLNAME、補 COUNTYNAME）----
sub(
    'shp_path = r"D:\\Windows\\Documents\\村里界歷史圖資_111\\村里界歷史圖資_111\\VILLAGE_MOI_1111118.shp"',
    f'shp_path = r"{SHP}"',
    "shp_path")

_old_read = (
    'gdf = gpd.read_file(shp_path, encoding="UTF-8")\n'
    'if gdf.crs is None:\n'
    '    gdf.crs = "EPSG:4326"\n'
    'gdf = gdf.to_crs(TARGET_CRS)\n'
    'print(f"原始要素數：{len(gdf)}")\n'
)
_new_read = (
    'gdf = gpd.read_file(shp_path, encoding="UTF-8")\n'
    'if gdf.crs is None:\n'
    '    gdf.crs = "EPSG:4326"\n'
    'gdf = gdf.to_crs(TARGET_CRS)\n'
    'print(f"原始要素數：{len(gdf)}")\n'
    '\n'
    '# ★ 85 年區里界檔欄位為「區名 / 里名」，對應到模板的 TOWNNAME / VILLNAME；\n'
    '#   並補 COUNTYNAME 欄位，讓模板的診斷語句與 TARGET_COUNTY 過濾照常運作。\n'
    'gdf = gdf.rename(columns={"區名": "TOWNNAME", "里名": "VILLNAME"})\n'
    'gdf["COUNTYNAME"] = TARGET_COUNTY\n'
)
sub(_old_read, _new_read, "讀檔區塊")

# ---- 2. 比例尺 ----
sub("METERS_PER_PIXEL = 10.0", f"METERS_PER_PIXEL = {MILES_PER_PIXEL}", "METERS_PER_PIXEL")
sub("# 比例尺：1px = 10m，再放大 10%",
    f"# 比例尺：1px = {MILES_PER_PIXEL}m，再放大 10%", "比例尺註解")

# ---- 3. 輸出檔名 ----
sub(
    '_out_name = "TaichungCity_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
    '    else "TaichungCity_VillageDistrict_Plain.png"',
    f'_out_name = "{OUT_STEM}_Labeled.png" if WITH_LABELS \\\n'
    f'    else "{OUT_STEM}_Plain.png"',
    "輸出檔名")

# ---- 4. 本圖即核心 8 區放大圖：全部里先試中文地名，縮字＋暈圈，不用數字 ----
sub("DENSE_SKIP_AREA_PX = 15000",
    "DENSE_SKIP_AREA_PX = 0      # 1996 核心圖：不按面積跳過，全部先試中文地名",
    "DENSE_SKIP_AREA_PX")
sub("NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）",
    "NUMBER_AREA_PX = 0       # 1996 核心圖：不按面積直接走編號，一律先試中文地名",
    "NUMBER_AREA_PX")
sub("CIRCLE_MIN_AREA_PX = 0.0  # 小於此面積連編號圓圈都不畫（0 = 不設限）",
    "CIRCLE_MIN_AREA_PX = 0.0  # 1996 核心圖不使用編號圓圈", "CIRCLE_MIN_AREA_PX")
sub("NUMBER_WHEN_TEXT_FAILS = True",
    "NUMBER_WHEN_TEXT_FAILS = False   # 1996 核心圖：地名塞不下就縮字＋暈圈，不用數字",
    "NUMBER_WHEN_TEXT_FAILS")

# ---- 5. 字號分檔（沿用 Dense 已調好的密集區數值）----
sub('TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]',
    'TOWNSHIP_TIERS = [(350000, 52), (700000, 60), (2500000, 68), (float("inf"), 78)]',
    "TOWNSHIP_TIERS")
sub('VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]',
    'VILLAGE_TIERS = [(30000, 26), (90000, 32), (float("inf"), 40)]', "VILLAGE_TIERS")
sub("FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
    "FONT_MIN = 16            # 第一輪（候選點＋平移搜尋）的最小字號（px）", "FONT_MIN")
sub("GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；\n"
    "#                          放大圖 DrawTaichungDense.py 會調到 12）",
    "GRID_FONT_MIN = 12       # 網格掃描階段可再縮到的最小字號（1996 核心圖放寬到 12，盡可能標滿地名）",
    "GRID_FONT_MIN")
sub("HALO_MAX_FS = 36", "HALO_MAX_FS = 34", "HALO_MAX_FS")
sub("TOWN_FONT_MIN = 20       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）；放大圖用 24",
    "TOWN_FONT_MIN = 24       # 需求①：區名縮字硬下限（寧可字小，也不壓村里名）", "TOWN_FONT_MIN")
sub("TOWN_BRANCH_MIN_PX = 34  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
    "TOWN_BRANCH_MIN_PX = 30  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
    "TOWN_BRANCH_MIN_PX")

# ---- 6. 密集區清單 = 本圖涵蓋的 8 區（與模板同）----
sub('DENSE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]',
    'DENSE_TOWNS = ' + repr(CORE_TOWNS), "DENSE_TOWNS")

# ---- 6b. 只畫界線（不標字、不標編號）的區：僅北區、中區 ----
#   這兩區另由 DrawTaichungCore1996Zoom.py 出 1px=2m 放大圖，
#   故主圖上「字非常小、或必須壓到村里界線才放得下」的里只保留界線、留白。
#   其餘 6 區維持原行為（縮字＋外擴網格＋描邊暈圈，盡可能把地名標滿）。
sub("SKIP_UNFITTABLE_TOWNS = []",
    "SKIP_UNFITTABLE_TOWNS = " + repr(STRICT_TOWNS), "SKIP_UNFITTABLE_TOWNS")
sub("VILLAGE_FONT_FLOOR = 26      # 字號下限（px）；低於此字號視為「非常小」",
    "VILLAGE_FONT_FLOOR = 28      # 字號下限（px）；低於此字號視為「非常小」",
    "VILLAGE_FONT_FLOOR")

# ---- 7. 本圖專屬隨機色盤（以檔名為種子）----
sub('PALETTE_KEY = os.environ.get("PALETTE_KEY", "taichung_main").strip()',
    f'PALETTE_KEY = os.environ.get("PALETTE_KEY", "{OUT_STEM}").strip()', "PALETTE_KEY")

# ---- 8. 本圖即最終呈現：不做超標區判定、不寫清單檔 ----
_old_sa = (
    '_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()\n'
    'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]\n'
)
assert _old_sa in code, "找不到 STANDALONE_TOWNS 判定區塊"
code = code.replace(_old_sa, "STANDALONE_TOWNS = []   # 1996 核心圖為最終呈現，不需排除任何區\n", 1)
sub("MAX_NUM_PER_TOWN = 6",
    "MAX_NUM_PER_TOWN = 10 ** 9   # 1996 核心圖為最終呈現，不做超標區判定", "MAX_NUM_PER_TOWN")
sub('TC_WRITE_STANDALONE = os.environ.get("TC_CHILD_RUN", "") != "1"',
    "TC_WRITE_STANDALONE = False   # 不覆寫主圖寫出的清單檔", "TC_WRITE_STANDALONE")

# ---- 9. 防呆：關鍵替換必須都生效 ----
for _bad in ("METERS_PER_PIXEL = 10.0", "DENSE_SKIP_AREA_PX = 15000",
             "NUMBER_AREA_PX = 15000", "NUMBER_WHEN_TEXT_FAILS = True",
             "MAX_NUM_PER_TOWN = 6", "_DENSE_STANDALONE_ENV.split",
             "FONT_MIN = 26 ", "GRID_FONT_MIN = 20 ", "TOWN_FONT_MIN = 20 ",
             "SKIP_UNFITTABLE_TOWNS = []", "VILLAGE_MOI_1111118"):
    assert _bad not in code, f"模板替換失敗：{_bad}"

os.makedirs(os.path.join(_HERE, "Taichung"), exist_ok=True)
print("=" * 72)
print(f"▶ 臺中市核心 8 區 民國85年（1996）帶地名地圖  1px={MILES_PER_PIXEL}m"
      f"（實際 ≈{MILES_PER_PIXEL / 1.1:.2f}m）  →  {OUT_STEM}_Labeled.png")
print("=" * 72)
exec(compile(code, f"{_SRC} ({OUT_STEM})", "exec"), {"__name__": "__main__"})