# -*- coding: utf-8 -*-
"""
臺北市 · 村里界 + 區界地圖（1px≈2.7m）—— 全市 12 區、456 個「里」逐里中文標註

作法：以 Empty_Map/DrawTaichungCityLabeled.py 為模板（沿用其智慧標註：
候選點／16 方向平移／2D 網格掃描／逐級縮字／描邊暈圈），
只替換「縣市、經緯範圍、比例尺、輸出目錄、密集區清單」等設定，
不複製整份 1500 行模板 → 模板若更新，本圖自動跟著更新。
（此手法與 Empty_Map/DrawTaichungCore1996ZoomCombined.py 相同。）

臺北市特性：
  * 全市 12 區、456 里，最小里僅約 0.032 km²，屬高度密集的都會區。
  * 因此比照 DrawTaichungCore1996ZoomCombined.py 的「放大圖」策略：
      NUMBER_AREA_PX = DENSE_SKIP_AREA_PX = 0 → 每個里一律先試中文地名；
      NUMBER_WHEN_TEXT_FAILS = False          → 塞不下就縮字＋網格掃描＋描邊暈圈，
                                                不使用編號（故本圖無圖例）。
  * 比例尺 1px = 3m（再放大 10% → 實際 ≈2.73m），全市一張，逐里標滿地名。

輸出：Taipei/TaipeiCity_VillageDistrict_Labeled.png

用法：
  python DrawTaipeiCityLabeled.py
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTaichungCityLabeled.py")
_OUT_DIR = os.path.join(_HERE, "Taipei")

TARGET_COUNTY = "臺北市"
# 臺北市轄內無離島；此 bbox 只是防止離群圖斑把畫布撐爆（EPSG:3826）
MAINLAND_BBOX = (290000.0, 2755000.0, 325000.0, 2795000.0)
METERS_PER_PIXEL = 3.0
OUT_STEM = "TaipeiCity_VillageDistrict"
# 全市 12 區
TAIPEI_TOWNS = ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區",
                "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"]

with open(_SRC, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()


def build_taipei():
    code = _TEMPLATE

    def sub(old, new, tag):
        nonlocal code
        assert old in code, f"找不到片段：{tag}"
        code = code.replace(old, new, 1)

    # 1. 輸出目錄
    sub(r'out_dir = r"D:\Windows\TaiwanElection\Empty_Map\Taichung"   # 本專案輸出目錄',
        rf'out_dir = r"{_OUT_DIR}"   # 本專案輸出目錄', "out_dir")

    # 2. 縣市與本島 bbox
    sub('TARGET_COUNTY = "臺中市"', f'TARGET_COUNTY = "{TARGET_COUNTY}"', "TARGET_COUNTY")
    sub('EXPLICIT_MAINLAND_BBOX = (190000.0, 2640000.0, 300000.0, 2710000.0)  # EPSG:3826',
        f'EXPLICIT_MAINLAND_BBOX = {MAINLAND_BBOX}  # EPSG:3826', "EXPLICIT_MAINLAND_BBOX")

    # 3. 比例尺
    sub('METERS_PER_PIXEL = 10.0', f'METERS_PER_PIXEL = {METERS_PER_PIXEL}', "METERS_PER_PIXEL")

    # 4. 密集區清單＝全市 12 區（僅供統計）
    sel = "[" + ", ".join(f'"{t}"' for t in TAIPEI_TOWNS) + "]"
    sub('DENSE_TOWNS = ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區"]',
        f'DENSE_TOWNS = {sel}', "DENSE_TOWNS")

    # 5. 逐里中文標註（不用編號、無圖例）
    sub("DENSE_SKIP_AREA_PX = 15000", "DENSE_SKIP_AREA_PX = 0", "DENSE_SKIP_AREA_PX")
    sub("NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）",
        "NUMBER_AREA_PX = 0       # 全部村里一律先試中文地名", "NUMBER_AREA_PX")
    sub("NUMBER_WHEN_TEXT_FAILS = True", "NUMBER_WHEN_TEXT_FAILS = False", "NUMBER_WHEN_TEXT_FAILS")

    # 6. 字號下限放低（盡可能把地名標滿）
    sub("FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
        "FONT_MIN = 16            # 第一輪（候選點＋平移搜尋）的最小字號（px）", "FONT_MIN")
    sub("GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；\n"
        "#                          放大圖 DrawTaichungDense.py 會調到 12）",
        "GRID_FONT_MIN = 10       # 網格掃描階段可再縮到的最小字號（盡可能把地名標滿）",
        "GRID_FONT_MIN")

    # 7. 不寫獨立出圖清單、不另出放大圖
    sub('_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()\n'
        'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]',
        "STANDALONE_TOWNS = []\n", "STANDALONE_TOWNS")
    sub("MAX_NUM_PER_TOWN = 6", "MAX_NUM_PER_TOWN = 10**9", "MAX_NUM_PER_TOWN")
    sub('TC_WRITE_STANDALONE = os.environ.get("TC_CHILD_RUN", "") != "1"',
        "TC_WRITE_STANDALONE = False", "TC_WRITE_STANDALONE")

    # 8. 配色種子（全市一張圖）
    sub('PALETTE_KEY = os.environ.get("PALETTE_KEY", "taichung_main").strip()',
        'PALETTE_KEY = os.environ.get("PALETTE_KEY", "taipei_main").strip()',
        "PALETTE_KEY")

    # 9. 輸出檔名
    sub('_out_name = "TaichungCity_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
        '    else "TaichungCity_VillageDistrict_Plain.png"',
        f'_out_name = "{OUT_STEM}_Labeled.png" if WITH_LABELS \\\n'
        f'    else "{OUT_STEM}_Plain.png"', "輸出檔名")

    # 10. 防呆（關鍵片段全部替換完成）
    for _bad in ("METERS_PER_PIXEL = 10.0", "DENSE_SKIP_AREA_PX = 15000",
                 "NUMBER_AREA_PX = 15000", "NUMBER_WHEN_TEXT_FAILS = True",
                 "MAX_NUM_PER_TOWN = 6", "_DENSE_STANDALONE_ENV.split",
                 'TARGET_COUNTY = "臺中市"'):
        assert _bad not in code, f"模板替換失敗：{_bad}"

    _g = {"__name__": "__main__"}
    exec(compile(code, f"{_SRC} (臺北市)", "exec"), _g)
    return _g["canvas"]


def main():
    os.makedirs(_OUT_DIR, exist_ok=True)
    print("\n" + "=" * 72)
    print(f"▶ 臺北市全市村里地圖  1px={METERS_PER_PIXEL}m"
          f"（實際 ≈{METERS_PER_PIXEL / 1.1:.2f}m）  →  {OUT_STEM}_Labeled.png")
    print("=" * 72)
    build_taipei()
    print("=" * 72)
    print("完成：", os.path.join(_OUT_DIR, OUT_STEM + "_Labeled.png"))


if __name__ == "__main__":
    main()
