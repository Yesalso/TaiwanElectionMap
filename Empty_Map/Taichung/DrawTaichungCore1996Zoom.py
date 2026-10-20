# -*- coding: utf-8 -*-
"""
臺中市核心 8 區 · 民國 85 年（1996）：「北區」「中區」放大圖（1px=2m）並排合成一張。

以 DrawTaichungCityLabeled.py 為模板（沿用其智慧標註），再套用 DrawTaichungDense.py
的放大圖設計：
  * 單區一張圖、1px=2m（放大 10% → 實際 ≈1.82m），逐里標中文地名；
  * NUMBER_AREA_PX = DENSE_SKIP_AREA_PX = 0 → 里一律先試中文地名；
    NUMBER_WHEN_TEXT_FAILS = False → 塞不下就繼續縮字＋網格掃描＋描邊暈圈，不用數字，
    故不產生右側編號圖例；
  * 字號與面積門檻依本圖比例等比放大（模板 Dense 的數值是以 ≈3.64/5.45m 調的）：
    面積門檻（px²）×(5.45/1.82)²≈9、字號（px）×3 → 與主圖的視覺相對大小一致；
  * 每張圖以檔名為種子取隨機淡雅色盤（與主圖配色不同，兩圖並排可區分）。

與主圖的分工（對應主圖 SKIP_UNFITTABLE_TOWNS = ["北區", "中區"]）：
  主圖（1px=4m）上北區、中區「字非常小、或必須壓村里界線才放得下」的里只留界線；
  這兩區的地名改由本腳本的放大圖逐里完整標出。

合成：北區（左）、中區（右）並排，中間留白 GAP px、各圖垂直置中，
      輸出 Taichung/Taichung1996_Zoom_BeiZhong.png；
      同時各自輸出單區圖 Taichung1996_{Bei,Zhong}_Labeled.png 供核對。

用法：
  python DrawTaichungCore1996Zoom.py
"""
import os

from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTaichungCityLabeled.py")
_OUT_DIR = os.path.join(_HERE, "Taichung")

SHP = (r"D:\Windows\Documents\村里界歷史圖資_111\臺中市85年區里界_UTF8"
       r"\臺中市85年區里界_UTF8\區里界_region.shp")
ZOOM_TOWNS = [("北區", "Bei"), ("中區", "Zhong")]
ZOOM_MILES_PER_PIXEL = 2.0
GAP = 120                 # 兩圖之間留白（px）
STITCH_STEM = "Taichung1996_Zoom_BeiZhong"

with open(_SRC, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()


def build_one(town, stem):
    """把 DrawTaichungCityLabeled.py 改成「1996 單區放大圖」並執行，回傳成圖。"""
    code = _TEMPLATE

    def sub(old, new, tag):
        nonlocal code
        assert old in code, f"找不到片段：{tag}"
        code = code.replace(old, new, 1)

    # ---- 1. 資料來源 + 欄位對應（區名→TOWNNAME、里名→VILLNAME、補 COUNTYNAME）----
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
        '# ★ 85 年區里界檔欄位為「區名 / 里名」，對應模板的 TOWNNAME / VILLNAME；\n'
        '#   補 COUNTYNAME 讓模板的診斷語句與 TARGET_COUNTY 過濾照常運作。\n'
        'gdf = gdf.rename(columns={"區名": "TOWNNAME", "里名": "VILLNAME"})\n'
        'gdf["COUNTYNAME"] = TARGET_COUNTY\n', "讀檔區塊")

    # ---- 2. 只畫本區 ----
    sub(
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())].copy()',
        f'_ZOOM_TOWNS_SEL = ["{town}"]\n'
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].isin(_ZOOM_TOWNS_SEL))].copy()', "villages 過濾")

    # ---- 3. 比例尺 1px=2m ----
    sub("METERS_PER_PIXEL = 10.0", f"METERS_PER_PIXEL = {ZOOM_MILES_PER_PIXEL}",
        "METERS_PER_PIXEL")
    sub("# 比例尺：1px = 10m，再放大 10%",
        f"# 比例尺：1px = {ZOOM_MILES_PER_PIXEL}m（放大圖），再放大 10%", "比例尺註解")

    # ---- 4. 輸出檔名 ----
    sub('_out_name = "TaichungCity_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
        '    else "TaichungCity_VillageDistrict_Plain.png"',
        f'_out_name = "Taichung1996_{stem}_Labeled.png" if WITH_LABELS \\\n'
        f'    else "Taichung1996_{stem}_Plain.png"', "輸出檔名")

    # ---- 5. 放大圖＝最終呈現：里一律先試中文地名，不用數字 ----
    sub("DENSE_SKIP_AREA_PX = 15000",
        "DENSE_SKIP_AREA_PX = 0      # 1996 放大圖：不按面積跳過，全部先試中文地名",
        "DENSE_SKIP_AREA_PX")
    sub("NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）",
        "NUMBER_AREA_PX = 0       # 1996 放大圖：不按面積直接走編號，一律先試中文地名",
        "NUMBER_AREA_PX")
    sub("NUMBER_WHEN_TEXT_FAILS = True",
        "NUMBER_WHEN_TEXT_FAILS = False   # 1996 放大圖：地名塞不下就縮字＋暈圈，不用數字",
        "NUMBER_WHEN_TEXT_FAILS")

# ---- 6. 字號分檔／字號下限（依 1px≈1.82m 等比放大：px² ×9、px ×3）----
    sub('VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]',
        'VILLAGE_TIERS = [(360000, 90), (1350000, 108), (float("inf"), 126)]',
        "VILLAGE_TIERS")
    sub('TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]',
        'TOWNSHIP_TIERS = [(3150000, 156), (6300000, 180), (22500000, 204), (float("inf"), 234)]',
        "TOWNSHIP_TIERS")
    sub("FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
        "FONT_MIN = 20            # 第一輪（候選點＋平移搜尋）的最小字號（px）", "FONT_MIN")
    sub("GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；\n"
        "#                          放大圖 DrawTaichungDense.py 會調到 12）",
        "GRID_FONT_MIN = 12       # 網格掃描階段可再縮到的最小字號（盡可能把地名標滿）",
        "GRID_FONT_MIN")
    sub("HALO_MAX_FS = 36", "HALO_MAX_FS = 60", "HALO_MAX_FS")
    sub("TOWN_FONT_MIN = 20       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）；放大圖用 24",
        "TOWN_FONT_MIN = 48       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）",
        "TOWN_FONT_MIN")
    sub("TOWN_BRANCH_MIN_PX = 34  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
        "TOWN_BRANCH_MIN_PX = 60  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
        "TOWN_BRANCH_MIN_PX")
    sub("TOWN_GUARD_PX = 10.0", "TOWN_GUARD_PX = 30.0", "TOWN_GUARD_PX")
    sub("BASE_BUFFER_PX = 78      # 內縮質心基準距離（px）",
        "BASE_BUFFER_PX = 200     # 內縮質心基準距離（px）", "BASE_BUFFER_PX")
    sub("LINE_STEP_PX = 6         # 平移搜尋步長（px）",
        "LINE_STEP_PX = 14        # 平移搜尋步長（px）", "LINE_STEP_PX")
    sub("TEXT_MARGIN_PX = 4.0     # 文字框距本單元邊界最小間隙（px）",
        "TEXT_MARGIN_PX = 8.0     # 文字框距本單元邊界最小間隙（px）", "TEXT_MARGIN_PX")

    # ---- 7. 密集區清單＝本圖這一個區（僅影響統計訊息，門檻已為 0）----
    sub('DENSE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]',
        f'DENSE_TOWNS = ["{town}"]', "DENSE_TOWNS")

    # ---- 8. 本圖專屬隨機色盤（以檔名為種子）----
    sub('PALETTE_KEY = os.environ.get("PALETTE_KEY", "taichung_main").strip()',
        f'PALETTE_KEY = os.environ.get("PALETTE_KEY", "Taichung1996_{stem}").strip()',
        "PALETTE_KEY")

    # ---- 9. 本圖即最終呈現：不做超標區判定、不寫清單檔 ----
    sub('_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()\n'
        'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]\n',
        "STANDALONE_TOWNS = []   # 1996 放大圖為最終呈現，不需排除任何區\n", "STANDALONE_TOWNS")
    sub("MAX_NUM_PER_TOWN = 6",
        "MAX_NUM_PER_TOWN = 10 ** 9   # 放大圖是本區最終呈現，不做超標區判定", "MAX_NUM_PER_TOWN")
    sub('TC_WRITE_STANDALONE = os.environ.get("TC_CHILD_RUN", "") != "1"',
        "TC_WRITE_STANDALONE = False   # 不覆寫主圖寫出的清單檔", "TC_WRITE_STANDALONE")

    # ---- 10. 防呆：關鍵替換必須都生效 ----
    for _bad in ("METERS_PER_PIXEL = 10.0", "DENSE_SKIP_AREA_PX = 15000",
                 "NUMBER_AREA_PX = 15000", "NUMBER_WHEN_TEXT_FAILS = True",
                 "MAX_NUM_PER_TOWN = 6", "_DENSE_STANDALONE_ENV.split",
                 "FONT_MIN = 26 ", "GRID_FONT_MIN = 20 ", "TOWN_FONT_MIN = 20 ",
                 "HALO_MAX_FS = 36", 'VILLAGE_TIERS = [(40000, 30)',
                 'TOWNSHIP_TIERS = [(300000, 58)', "VILLAGE_MOI_1111118"):
        assert _bad not in code, f"模板替換失敗：{_bad}"

    _g = {"__name__": "__main__"}
    exec(compile(code, f"{_SRC} (1996 {stem})", "exec"), _g)
    return _g["canvas"]


def stitch(images, path):
    """並排合成一張整體圖（各圖垂直置中）"""
    w = sum(im.width for im in images) + GAP * (len(images) - 1)
    h = max(im.height for im in images)
    out = Image.new("RGB", (w, h), (255, 255, 255))
    x = 0
    for im in images:
        out.paste(im, (x, (h - im.height) // 2))
        x += im.width + GAP
    try:
        out.save(path, format="png")
        return path
    except OSError as e:      # 目標檔被看圖程式鎖住
        alt = path[:-4] + "_new.png"
        print(f"⚠️ {os.path.basename(path)} 寫入失敗（{e}），改存 {os.path.basename(alt)}")
        out.save(alt, format="png")
        return alt


def main():
    os.makedirs(_OUT_DIR, exist_ok=True)
    imgs = []
    for town, stem in ZOOM_TOWNS:
        print("\n" + "=" * 72)
        print(f"▶ {town}   1px={ZOOM_MILES_PER_PIXEL}m"
              f"（實際 ≈{ZOOM_MILES_PER_PIXEL / 1.1:.2f}m）"
              f"  →  Taichung1996_{stem}_Labeled.png")
        print("=" * 72)
        imgs.append(build_one(town, stem))

    print("\n" + "=" * 72)
    print(f"合成：{' ＋ '.join(t for t, _ in ZOOM_TOWNS)}"
          f"（{GAP}px 間隔、垂直置中）  →  {STITCH_STEM}.png")
    for im, (t, _) in zip(imgs, ZOOM_TOWNS):
        print(f"  {t}：{im.width} × {im.height}")
    print("=" * 72)
    print("Saved:", stitch(imgs, os.path.join(_OUT_DIR, STITCH_STEM + ".png")))


if __name__ == "__main__":
    main()