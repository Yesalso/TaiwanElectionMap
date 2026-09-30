# -*- coding: utf-8 -*-
"""
由 DrawTainanCityLabeled.py 派生，產生「臺南市密集區 / 獨立出圖區放大圖」系列。

輸出（全部 1px ≈ 4.54m，即設定 5m 再放大 10%；皆為標註版）：
  1. TainanDense6_Labeled.png   安南/安平/中西/北/南/東 六區合圖（不含永康）
  2. TainanYongkang_Labeled.png 永康區
  3. TainanXinying_Labeled.png  新營區
  4. TainanGuiren_Labeled.png   歸仁區
  5. TainanMadou_Labeled.png    麻豆區

主圖（DrawTainanCityLabeled.py）對密集六區「只標能塞得下中文地名的村里」，
塞不下的不畫編號圓圈；那些村里就在放大圖上以中文地名標出。

本腳本同時負責「告知主圖哪些區已獨立出圖」：
  執行時寫出 _standalone_towns.txt（= 所有非合圖群組的區），
  主圖以環境變數 DENSE_STANDALONE 讀取，於是這些區在主圖上不再標編號序號（需求③）。

配色（需求④）：每張圖傳入不同的 PALETTE_KEY，模板以固定種子隨機生成色盤，
故各圖配色互異但可重現。

用法：
  python DrawTainanDense.py            # 產生上面 5 張（標註版）
  python DrawTainanDense.py 六區        # 只產生指定群組（可多個關鍵字）
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTainanCityLabeled.py")
_STANDALONE_FILE = os.path.join(_HERE, "_standalone_towns.txt")

with open(_SRC, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()


# ============================================================
# 群組定義：(顯示名稱, 區名清單, 輸出檔名主幹)
# 合圖 = 清單長度 > 1；清單長度 == 1 視為「該區獨立出圖」，
# 對應的區會被寫進 _standalone_towns.txt，主圖不再標序號。
# ============================================================
GROUPS = [
    ("臺南密集六區（安南/安平/中西/北/南/東，不含永康）",
     ["安南區", "安平區", "中西區", "北區", "南區", "東區"],
     "TainanDense6"),
    ("永康區",
     ["永康區"],
     "TainanYongkang"),
    ("新營區",
     ["新營區"],
     "TainanXinying"),
    ("歸仁區",
     ["歸仁區"],
     "TainanGuiren"),
    ("麻豆區",
     ["麻豆區"],
     "TainanMadou"),
]

METERS_PER_PIXEL = 5.0


def standalone_towns():
    """單區群組 → 已獨立出圖的區清單（主圖不再標序號）"""
    out = []
    for _name, _towns, _stem in GROUPS:
        if len(_towns) == 1:
            out.extend(_towns)
    return out


def build_group(towns, out_stem, mpp=METERS_PER_PIXEL):
    """以 DrawTainanCityLabeled.py 為模板，改寫成單一群組的放大圖並執行。"""
    code = _TEMPLATE

    # ---- 1. 比例尺 ----
    old_scale = "METERS_PER_PIXEL = 10.0"
    assert old_scale in code, "找不到 METERS_PER_PIXEL 宣告"
    code = code.replace(old_scale, f"METERS_PER_PIXEL = {mpp}", 1)
    code = code.replace(
        "# 比例尺：1px = 10m，再放大 10%",
        f"# 比例尺：1px = {mpp}m（密集區放大圖），再放大 10%", 1)

    # ---- 2. villages 只取本群組的區 ----
    old_filter = (
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())].copy()'
    )
    assert old_filter in code, "找不到 villages 過濾語句"
    sel_literal = "[" + ", ".join(f'"{t}"' for t in towns) + "]"
    new_filter = (
        f'_DENSE_TOWNS_SEL = {sel_literal}\n'
        'villages = gdf[(gdf["COUNTYNAME"] == TARGET_COUNTY) & (gdf["VILLNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].notna())\n'
        '               & (gdf["TOWNNAME"].isin(_DENSE_TOWNS_SEL))].copy()'
    )
    code = code.replace(old_filter, new_filter, 1)

    # ---- 3. 輸出檔名 ----
    code = code.replace(
        '_out_name = "TainanCity_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
        '    else "TainanCity_VillageDistrict_Plain.png"',
        f'_out_name = "{out_stem}_Labeled.png" if WITH_LABELS \\\n'
        f'    else "{out_stem}_Plain.png"', 1)

    # ---- 4. 本圖為放大圖：村里全部標中文地名，不走主圖的跳過規則 ----
    code = code.replace(
        "DENSE_SKIP_AREA_PX = 15000",
        "DENSE_SKIP_AREA_PX = 0      # 本圖為放大圖，村里全部以中文地名標註", 1)

    # ---- 5. 字號分檔對應本圖比例（1px≈4.5m，面積為 10m 版的 4 倍） ----
    code = code.replace(
        'TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]',
        'TOWNSHIP_TIERS = [(350000, 52), (700000, 60), (2500000, 68), (float("inf"), 78)]',
        1)
    code = code.replace(
        'VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]',
        'VILLAGE_TIERS = [(30000, 26), (90000, 32), (float("inf"), 40)]',
        1)
    code = code.replace("FONT_MIN = 26", "FONT_MIN = 20", 1)
    code = code.replace("HALO_MAX_FS = 36", "HALO_MAX_FS = 34", 1)

    # ---- 6) 需求④：本圖專屬隨機色盤（以輸出名稱為種子；主圖維持固定 5 色） ----
    code = code.replace(
        'PALETTE_KEY = os.environ.get("PALETTE_KEY", "tainan_main").strip()',
        f'PALETTE_KEY = os.environ.get("PALETTE_KEY", "{out_stem}").strip()', 1)

    # ---- 7) 放大圖內全部村里都要標中文，不需要「主圖跳過序號」的規則 ----
    code = code.replace(
        'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]',
        'STANDALONE_TOWNS = []   # 放大圖本身不需排除任何區', 1)

    # ---- 8) 防呆：確認診斷裁片與 layer 輸出已關閉 ----
    if "_diag_tag" in code:
        print("⚠️ 模板仍含診斷裁片碼，請確認 DrawTainanCityLabeled.py 已清理")

    exec(compile(code, f"{_SRC} ({out_stem})", "exec"), {"__name__": "__main__"})


def main():
    # 先把「獨立出圖的區」寫檔，供主圖以 DENSE_STANDALONE 讀取
    _sa = standalone_towns()
    with open(_STANDALONE_FILE, "w", encoding="utf-8") as _f:
        _f.write(",".join(_sa))
    print(f"獨立出圖的區（主圖將不標序號）→ {_STANDALONE_FILE}：{_sa}")

    kws = sys.argv[1:]
    for name, towns, stem in GROUPS:
        if kws and not any(k in name or k in stem for k in kws):
            continue
        print("\n" + "=" * 72)
        print(f"▶ {name}   [{', '.join(towns)}]  →  {stem}_Labeled.png")
        print("=" * 72)
        build_group(towns, stem)
    print("\n🎉 全部放大圖生成完畢")


if __name__ == "__main__":
    main()
