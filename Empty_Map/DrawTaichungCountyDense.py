# -*- coding: utf-8 -*-
"""
由 DrawTaichungCountyLabeled.py 派生，產生臺中縣「獨立放大圖」系列（標註版）。

出圖規則：
   1. 主圖上「一個區內需要編號圓圈的村里超過 MAX_NUM_PER_TOWN(=6) 個」的區，
      在主圖上不再打編號，改由本腳本為「該區單獨」出一張放大圖
      （例如豐原區 → TaichungCountyFengyuan_Labeled.png）。

     ★ 本檔沒有「核心合圖」：原本 Dense 腳本的第 1 組（核心 8 區合圖）在台中縣版
     不存在 —— 核心 8 區（中區/東區/南區/西區/北區/北屯區/西屯區/南屯區）已隨
     範圍一起被排除，只剩其餘 21 區，所以每一個超標區都各出一張單區圖。

     臺中縣主圖 1px=9.091m 下，411 個村里中有 171 個需要編號圓圈，其中 8 個區
     超過門檻（共 124 個里）→ 產生 8 張單區放大圖：
     豐原(27)/太平(25)/大里(18)/大甲(14)/清水(13)/東勢(9)/沙鹿(9)/潭子(9)。

     清單來源（優先序）：
       ① 環境變數 DENSE_STANDALONE="豐原區,大安區,..."
       ② TaichungCounty/_standalone_towns_ks.txt —— 由 DrawTaichungCountyLabeled.py
          執行時自動判定並寫出（本腳本不寫這個檔）。
       ③ 兩者都沒有時（例如還沒跑過主圖）→ 自動先執行一次主圖腳本取得清單。

放大圖比例尺：
  * 每個區單獨出圖 → METERS_PER_PIXEL = ZOOM_METERS_PER_PIXEL = 6.0（→ 1px ≈ 5.45m）
    這 8 個區幅員大、村里也大，6m 已足夠把地名標滿，出圖尺寸也更小
    （最大為太平區 2627x2675 px；和平區雖估算達 11134x6927 px，但它村里很大、
    不會被判超標，故不會出圖）。

放大圖標註策略（不用數字，盡可能縮小字體把地名標滿）：
  * DENSE_SKIP_AREA_PX = NUMBER_AREA_PX = 0 → 所有村里一律先試中文地名；
  * NUMBER_WHEN_TEXT_FAILS = False → 地名塞不下時不會改畫編號圓圈，
    而是由模板繼續「縮字 → 村里內網格掃描 → 外擴網格掃描 → 描邊暈圈」四輪接力；
    FONT_MIN 16px、GRID_FONT_MIN 12px（模板主圖為 26/20），
    所以連 0.05 km² 的細碎里也標得出名字。
  * 區名縮字硬下限 TOWN_FONT_MIN = 24（主圖 20）→ 確保區名永不壓到村里名。
  * 因為不用編號，也就不會產生右側圖例，輸出畫布會自動裁掉圖例區。

配色：每張圖傳入不同的 PALETTE_KEY，模板以固定種子隨機生成色盤，
故各圖配色互異但可重現（主圖維持固定 5 色）。

用法：
  python DrawTaichungCountyLabeled.py      # ① 先跑主圖（同時寫出超標區清單）
  python DrawTaichungCountyDense.py        # ② 再跑本腳本：每個超標區各一張
  python DrawTaichungCountyDense.py 豐原 太平   # 只產生指定區（可比對中文區名或輸出檔名）
  python DrawTaichungCountyDense.py --no-main # 清單不存在時，不要自動先跑主圖
"""
import os
import sys
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "DrawTaichungCountyLabeled.py")
_OUT_DIR = os.path.join(_HERE, "TaichungCounty")
_STANDALONE_FILE = os.path.join(_OUT_DIR, "_standalone_towns_ks.txt")

MAX_NUM_PER_TOWN = 6           # 與 DrawTaichungCountyLabeled.py 的同名常數保持一致
ZOOM_METERS_PER_PIXEL = 6.0    # 單區放大圖：1px=6m（→ 1px ≈ 5.45m）
CIRCLE_MIN_AREA_PX = 0.0      # 放大圖不用數字，故不設「太小不畫」門檻
# 放大圖的村里字號：第一輪最小 16px，網格掃描階段可再縮到 12px（盡可能把地名標滿）
FONT_MIN_ZOOM = 16
GRID_FONT_MIN_ZOOM = 12
TOWN_FONT_MIN_ZOOM = 24       # ★ 區名縮字硬下限（主圖 20）
TOWN_BRANCH_MIN_PX_ZOOM = 30

# ---------- 區名 → 輸出檔名副檔名（29 區全收，方便日後調整 EXCLUDE_TOWNS）----------
_TOWN_STEM = {
    # 核心 8 區（台中縣版已排除，不會用到；保留下列名稱以備範圍調整）
    "中區": "Zhong", "東區": "Dong", "南區": "Nan", "西區": "Xi", "北區": "Bei",
    "北屯區": "Beitun", "西屯區": "Xitun", "南屯區": "Nantun",
    # 次級都會區與原鄉市（本檔實際會用到的 21 區）
    "太平區": "Taiping", "大里區": "Dali", "潭子區": "Tanzi", "大雅區": "Daya",
    "豐原區": "Fengyuan", "后里區": "Houli", "神岡區": "Shengang", "石岡區": "Shigang",
    "東勢區": "Dongshi", "霧峰區": "Wufeng", "烏日區": "Wuri",
    "大肚區": "Dadu", "龍井區": "Longjing", "梧棲區": "Wuqi", "清水區": "Qingshui",
    "沙鹿區": "Shalu", "大甲區": "Dajia", "外埔區": "Waipu", "大安區": "Daan",
    "和美區": "Hemei", "新社區": "Xinshe", "和平區": "Heping",
}


def read_standalone_towns(auto_run=True):
    """取得「主圖上不打編號、由本腳本單獨出圖」的區清單。"""
    if os.path.exists(_STANDALONE_FILE):
        with open(_STANDALONE_FILE, encoding="utf-8-sig") as _f:
            _txt = _f.read()
        return [t.strip() for t in _txt.replace("\n", ",").split(",") if t.strip()]

    _env = os.environ.get("DENSE_STANDALONE", "").strip()
    if _env:
        return [t.strip() for t in _env.split(",") if t.strip()]

    if auto_run:
        print(f"找不到超標區清單 {_STANDALONE_FILE}，先執行主圖腳本取得清單 ...")
        subprocess.run([sys.executable, _SRC], cwd=_HERE, check=False)
        if os.path.exists(_STANDALONE_FILE):
            with open(_STANDALONE_FILE, encoding="utf-8-sig") as _f:
                _txt = _f.read()
            return [t.strip() for t in _txt.replace("\n", ",").split(",") if t.strip()]
    return []


def build_groups(extra_towns):
    """(顯示名稱, 區名清單, 輸出檔名主幹, 比例尺) 清單。
       台中縣版沒有核心合圖：每個超標區各一張、走 6m。"""
    groups = []
    for t in extra_towns:
        groups.append((t, [t], "TaichungCounty" + _TOWN_STEM.get(t, t),
                       ZOOM_METERS_PER_PIXEL))
    return groups


with open(_SRC, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()


def build_group(towns, out_stem, mpp=ZOOM_METERS_PER_PIXEL):
    """以 DrawTaichungCountyLabeled.py 為模板，改寫成單一群組的放大圖並執行。"""
    code = _TEMPLATE

    # ---- 0. 本腳本是子程序：不要覆寫主圖的「超標區清單」檔 ----
    os.environ["TC_CHILD_RUN"] = "1"

    # ---- 1. 比例尺 ----
    old_scale = "METERS_PER_PIXEL = 10.0"
    assert old_scale in code, "找不到 METERS_PER_PIXEL 宣告"
    code = code.replace(old_scale, f"METERS_PER_PIXEL = {float(mpp)}", 1)
    code = code.replace(
        "# 比例尺：1px = 10m，再放大 10%",
        f"# 比例尺：1px = {mpp}m（放大圖），再放大 10%", 1)

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
        '_out_name = "TaichungCounty_VillageDistrict_Labeled.png" if WITH_LABELS \\\n'
        '    else "TaichungCounty_VillageDistrict_Plain.png"',
        f'_out_name = "{out_stem}_Labeled.png" if WITH_LABELS \\\n'
        f'    else "{out_stem}_Plain.png"', 1)

    # ---- 4. 本圖為放大圖：村里一律標中文地名、「盡可能縮小字體」也要標滿，不用數字 ----
    code = code.replace(
        "DENSE_SKIP_AREA_PX = 15000",
        "DENSE_SKIP_AREA_PX = 0      # 放大圖：不按面積跳過，全部先試中文地名", 1)
    code = code.replace(
        "NUMBER_AREA_PX = 15000   # 小於此面積的村里改用編號圓圈（放不下地名）",
        "NUMBER_AREA_PX = 0       # 放大圖：不按面積直接走編號，一律先試中文地名", 1)
    code = code.replace(
        "CIRCLE_MIN_AREA_PX = 0.0  # 小於此面積連編號圓圈都不畫（0 = 不設限）",
        f"CIRCLE_MIN_AREA_PX = {CIRCLE_MIN_AREA_PX}   # 放大圖不用數字", 1)
    code = code.replace(
        "NUMBER_WHEN_TEXT_FAILS = True",
        "NUMBER_WHEN_TEXT_FAILS = False   # 放大圖：地名塞不下就繼續縮字＋暈圈，不用數字", 1)

    # ---- 5. 字號分檔：沿用原 DrawTaichungCountyDense 已調好的密集區數值，
    #      並把「網格掃描可再縮到的最小字號」放寬 → 盡可能把地名標滿 ----
    code = code.replace(
        'TOWNSHIP_TIERS = [(300000, 58), (1200000, 70), (float("inf"), 84)]',
        'TOWNSHIP_TIERS = [(350000, 52), (700000, 60), (2500000, 68), (float("inf"), 78)]',
        1)
    code = code.replace(
        'VILLAGE_TIERS = [(40000, 30), (150000, 36), (float("inf"), 42)]',
        'VILLAGE_TIERS = [(30000, 26), (90000, 32), (float("inf"), 40)]', 1)
    code = code.replace(
        "FONT_MIN = 26            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
        f"FONT_MIN = {FONT_MIN_ZOOM}            # 第一輪（候選點＋平移搜尋）的最小字號（px）",
        1)
    code = code.replace(
        "GRID_FONT_MIN = 20       # ★ 網格掃描階段可再縮到的最小字號（「盡可能縮小字體」標滿地名；\n"
        "#                          放大圖 DrawTaichungCountyDense.py 會調到 12）",
        f"GRID_FONT_MIN = {GRID_FONT_MIN_ZOOM}       "
        "# 網格掃描階段可再縮到的最小字號（放大圖放寬到 12，盡可能標滿地名）", 1)
    code = code.replace("HALO_MAX_FS = 36", "HALO_MAX_FS = 34", 1)
    code = code.replace(
        'TOWN_FONT_MIN = 20       # ★ 需求①：區名縮字硬下限（寧可字小，也不壓村里名）；放大圖用 24',
        f"TOWN_FONT_MIN = {TOWN_FONT_MIN_ZOOM}       "
        "# 需求①：區名縮字硬下限（放大圖比主圖 20 略大）", 1)
    code = code.replace(
        "TOWN_BRANCH_MIN_PX = 34  # 區名「首輪」縮字下限（首輪允許 16 方向平移搜尋）",
        f"TOWN_BRANCH_MIN_PX = {TOWN_BRANCH_MIN_PX_ZOOM}  # 區名「首輪」縮字下限（放大圖略放寬）", 1)

    # ---- 6. 本圖專屬隨機色盤（以輸出名稱為種子；主圖維持固定 5 色） ----
    code = code.replace(
        'PALETTE_KEY = os.environ.get("PALETTE_KEY", "taichung_main").strip()',
        f'PALETTE_KEY = os.environ.get("PALETTE_KEY", "{out_stem}").strip()', 1)

    # ---- 7. 放大圖本身就是最終呈現：不做「超標區」判定、不排除任何區 ----
    old_sa_block = (
        '_DENSE_STANDALONE_ENV = os.environ.get("DENSE_STANDALONE", "").strip()\n'
        'STANDALONE_TOWNS = [t for t in _DENSE_STANDALONE_ENV.split(",") if t]\n'
    )
    assert old_sa_block in code, "找不到 STANDALONE_TOWNS 判定區塊"
    code = code.replace(
        old_sa_block,
        "STANDALONE_TOWNS = []   # 放大圖本身不需排除任何區\n", 1)
    code = code.replace(
        "MAX_NUM_PER_TOWN = 6",
        "MAX_NUM_PER_TOWN = 10 ** 9   # 放大圖是本區最終呈現，不再做超標區判定", 1)
    code = code.replace(
        'TC_WRITE_STANDALONE = os.environ.get("TC_CHILD_RUN", "") != "1"',
        "TC_WRITE_STANDALONE = False   # 子程序不覆寫主圖寫出的清單檔", 1)

    # ---- 8. 防呆：關鍵替換必須都生效（漏掉會讓子圖悄悄沿用主圖設定）----
    for _bad in ("METERS_PER_PIXEL = 10.0", "DENSE_SKIP_AREA_PX = 15000",
                 "NUMBER_AREA_PX = 15000", "NUMBER_WHEN_TEXT_FAILS = True",
                 "MAX_NUM_PER_TOWN = 6", "_DENSE_STANDALONE_ENV.split",
                 "FONT_MIN = 26 ", "GRID_FONT_MIN = 20 ", "TOWN_FONT_MIN = 20 ",
                 '_out_name = "TaichungCounty_VillageDistrict_Labeled.png"'):
        assert _bad not in code, f"模板替換失敗：{_bad}"
    # 範圍過濾仍由模板自己的 EXCLUDE_TOWNS 負責（單區圖本來就只會命中 1 個區）
    assert "EXCLUDE_TOWNS" in code, "模板缺少 EXCLUDE_TOWNS，請確認範圍設定未被改掉"
    if "_diag_tag" in code:
        print("⚠️ 模板仍含診斷裁片碼，請確認 DrawTaichungCountyLabeled.py 已清理")

    exec(compile(code, f"{_SRC} ({out_stem})", "exec"), {"__name__": "__main__"})


def main():
    kws = [a for a in sys.argv[1:] if not a.startswith("--")]
    auto_main = "--no-main" not in sys.argv

    os.makedirs(_OUT_DIR, exist_ok=True)
    extra = read_standalone_towns(auto_run=auto_main)
    print(f"超標區（編號 > {MAX_NUM_PER_TOWN} 個 → 主圖不打編號、本腳本單獨出圖）："
          f"{extra if extra else '（無）'}")

    groups = build_groups(extra)
    done = []
    for name, towns, stem, mpp in groups:
        if kws and not any(k in name or k in stem or k in ",".join(towns) for k in kws):
            continue
        print("\n" + "=" * 72)
        print(f"▶ {name}   [{', '.join(towns)}]  "
              f"1px={mpp}m（實際 ≈{mpp / 1.1:.2f}m）  →  {stem}_Labeled.png")
        print("=" * 72)
        build_group(towns, stem, mpp=mpp)
        done.append(f"{stem}_Labeled.png")

    print("\n🎉 全部放大圖生成完畢：")
    for d in done:
        print(f"   {os.path.join(_OUT_DIR, d)}")


if __name__ == "__main__":
    main()
