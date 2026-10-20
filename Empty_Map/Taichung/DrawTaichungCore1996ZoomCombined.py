# -*- coding: utf-8 -*-
"""
臺中市核心 8 區 · 民國 85 年（1996）：「北區」「中區」放大圖（1px=2m）
合成成「一張圖」（北區＋中區同一張地圖）。

作法：以 DrawTaichungCityLabeled.py 為模板（沿用智慧標註），一次讀取整份 85 年 SHP，
只篩選出 TOWNNAME 屬於 ['北區','中區'] 的村里，**不切成兩張獨立圖再並排**，
而是以同一個群組、同一個畫布繪製整體範圍（整體 bbox，比例尺統一為 1px=2m）。

放大圖設計：
  * 1px=2m（放大 10% → 實際 ≈1.82m）
  * NUMBER_AREA_PX = DENSE_SKIP_AREA_PX = 0 → 里一律先試中文地名
  * NUMBER_WHEN_TEXT_FAILS = False → 塞不下就縮字＋網格掃描＋描邊暈圈，不用數字（無圖例）
  * 字號下限放低（接近主圖 4m 時的「縮字到底」邏輯），盡可能把地名標滿（符合「放大圖文字下限低一點」）

與主圖分工（對應 SKIP_UNFITTABLE_TOWNS = ["北區","中區"]）：
  主圖（1px=4m）上北區、中區「字非常小、或必須壓村里界線才放得下」的里只留界線；
  本圖（1px=2m、整體一張）將北區＋中區的村里名盡量完整標出。

輸出：Taichung/Taichung1996_Zoom_BeiZhong_Combined.png

用法：
  python DrawTaichungCore1996ZoomCombined.py
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTaichungCityLabeled.py")
_OUT_DIR = os.path.join(_HERE, "Taichung")

SHP = (r"D:\Windows\Documents\村里界歷史圖資_111\臺中市85年區里界_UTF8"
       r"\臺中市85年區里界_UTF8\區里界_region.shp")
COMBINED_TOWNS = ["北區", "中區"]
COMBINED_STEM = "Taichung1996_Zoom_BeiZhong_Combined"
ZOOM_MILES_PER_PIXEL = 2.0

with open(_SRC, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()


def build_combined():
    code = _TEMPLATE

    def sub(old, new, tag):
        nonlocal code
        assert old in code, f"找不到片段：{tag}"
        code = code.replace(old, new, 1)

    # 1. SHP 欄位對應（85年）
    sub(
        'shp_path = r"D:\\Windows\\Documents\\村里界歷史圖資_111\\村里界歷史圖資_111\\VILLAGE_MOI_1111118.shp"',
        f'shp_path = r"{SHP}"', "shp_path")
    sub(
        'gdf = gpd.read_file(shp_path, encoding="UTF-8")\n'
        'if gdf.crs is None:\n'
        '    gdf.crs = "EPSG:4326"\n'
        'gdf = gdf.to_crs(TARGET_CRS)\n'
        'print(f"原始要素數：{len(gdf)}")\n',
        'gdf = gpd.read_file(shp_path, encoding="UTF-8")\n'
        'if gdf.crs is None:\n'
        '    gdf.crs = "EPSG:4326"\n'
        'gdf = gdf.to_crs(TARGET_CRS)\n'
        'print(f"原始要素數：{len(gdf)}")\n'
        '\n'
        'gdf = gdf.rename(columns={"區名": "TOWNNAME", "里名": "VILLNAME"})\n'
        'gdf["COUNTYNAME"] = TARGET_COUNTY\n', "讀檔區塊")

    # 2. 只取北區+中區
    sel = "[" + ", ".join(f'"{t}"' for t in COMBINED_TOWNS) + "]"
    sub(
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())].copy()',
        f'_ZOOM_COMB = {sel}\n'
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].isin(_ZOOM_COMB))].copy()', "villages 過濾")

    # 3. 比例尺 1px=2m
    sub("METERS_PER_PIXEL = 10.0", f"METERS_PER_PIXEL = {ZOOM_MILES_PER_PIXEL}",
        "METERS_PER_PIXEL")
    sub("# 比例尺：1px = 10m，再放大 10%",
        f"# 比例尺：1px = {ZOOM_MILES_PER_PIXEL}m（放大圖，整體一張），再放大 10%",
        "比例尺註解")

    # 4. 輸出檔名
    sub('_out_name = "TaichungCity_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
        '    else "TaichungCity_VillageDistrict_Plain.png"',
        f'_out_name = "{COMBINED_STEM}.png" if WITH_LABELS \\\n'
        f'    else "{COMBINED_STEM}_Plain.png"', "輸出檔名")

    # 5. 盡量標滿地名（不用數字）
    sub("DENSE_SKIP_AREA_PX = 15000", "DENSE_SKIP_AREA_PX = 0", "DENSE_SKIP_AREA_PX")
    sub("NUMBER_AREA_PX = 15000", "NUMBER_AREA_PX = 0", "NUMBER_AREA_PX")
    sub("NUMBER_WHEN_TEXT_FAILS = True", "NUMBER_WHEN_TEXT_FAILS = False", "NUMBER_WHEN_TEXT_FAILS")

    # 6. 字號下限放低（貼近主圖縮字到底的「低一點」要求）
    sub("FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
        "FONT_MIN = 14            # 第一輪（候選點＋平移搜尋）的最小字號（px）", "FONT_MIN")
    sub("GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；\n"
        "#                          放大圖 DrawTaichungDense.py 會調到 12）",
        "GRID_FONT_MIN = 10       # 網格掃描階段可再縮到的最小字號（盡可能把地名標滿）",
        "GRID_FONT_MIN")
    sub("HALO_MAX_FS = 36", "HALO_MAX_FS = 42", "HALO_MAX_FS")
    sub("TOWN_FONT_MIN = 20       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）；放大圖用 24",
        "TOWN_FONT_MIN = 36       # 需求①：區名縮字硬下限（寧可字小，也不壓村里名）",
        "TOWN_FONT_MIN")
    sub("TOWN_BRANCH_MIN_PX = 34  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
        "TOWN_BRANCH_MIN_PX = 44  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
        "TOWN_BRANCH_MIN_PX")
    sub("TOWN_GUARD_PX = 10.0", "TOWN_GUARD_PX = 20.0", "TOWN_GUARD_PX")
    sub("BASE_BUFFER_PX = 78      # 內縮質心基準距離（px）",
        "BASE_BUFFER_PX = 120     # 內縮質心基準距離（px）", "BASE_BUFFER_PX")

    # 7. 面積分檔不強行拉高（放大圖保留足夠下限）
    sub('VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]',
        'VILLAGE_TIERS = [(180000, 66), (540000, 80), (float("inf"), 96)]',
        "VILLAGE_TIERS")
    sub('TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]',
        'TOWNSHIP_TIERS = [(2100000, 104), (4200000, 120), (15000000, 136), (float("inf"), 156)]',
        "TOWNSHIP_TIERS")

    # 8. DENSE 清單＝這兩區（僅統計，不影響門檻）
    sub('DENSE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]',
        f'DENSE_TOWNS = {sel}', "DENSE_TOWNS")

    # 9. 配色種子（整體一張圖）
    sub('PALETTE_KEY = os.environ.get("PALETTE_KEY", "taichung_main").strip()',
        f'PALETTE_KEY = os.environ.get("PALETTE_KEY", "{COMBINED_STEM}").strip()',
        "PALETTE_KEY")

    # 10. 不寫獨立出圖清單
    sub('_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()\n'
        'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]\n',
        "STANDALONE_TOWNS = []\n", "STANDALONE_TOWNS")
    sub("MAX_NUM_PER_TOWN = 6", "MAX_NUM_PER_TOWN = 10**9", "MAX_NUM_PER_TOWN")
    sub('TC_WRITE_STANDALONE = os.environ.get("TC_CHILD_RUN", "") != "1"',
        "TC_WRITE_STANDALONE = False", "TC_WRITE_STANDALONE")

    # 11. 防呆（關鍵片段全部替換完成）
    for _bad in ("METERS_PER_PIXEL = 10.0", "DENSE_SKIP_AREA_PX = 15000",
                 "NUMBER_AREA_PX = 15000", "NUMBER_WHEN_TEXT_FAILS = True",
                 "MAX_NUM_PER_TOWN = 6", "_DENSE_STANDALONE_ENV.split",
                 "FONT_MIN = 26 ", "GRID_FONT_MIN = 20 ", "TOWN_FONT_MIN = 20 ",
                 "VILLAGE_MOI_1111118"):
        assert _bad not in code, f"模板替換失敗：{_bad}"

    _g = {"__name__": "__main__"}
    exec(compile(code, f"{_SRC} ({COMBINED_STEM})", "exec"), _g)
    return _g["canvas"]


def main():
    os.makedirs(_OUT_DIR, exist_ok=True)
    print("\n" + "=" * 72)
    print(f"▶ 北區＋中區 整體一張放大圖  1px={ZOOM_MILES_PER_PIXEL}m"
          f"（實際 ≈{ZOOM_MILES_PER_PIXEL / 1.1:.2f}m）  →  {COMBINED_STEM}.png")
    print("=" * 72)
    build_combined()
    print("=" * 72)
    print("完成：", os.path.join(_OUT_DIR, COMBINED_STEM + ".png"))


if __name__ == "__main__":
    main()