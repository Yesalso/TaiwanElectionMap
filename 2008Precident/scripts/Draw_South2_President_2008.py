# -*- coding: utf-8 -*-
"""
南臺兩縣市（高雄市・屏東縣）
2008 第十二屆總統副總統選舉 各村（里）得票領先候選人得票比例圖

資料來源：2008Precident/data/2008總統副總統選舉_得票率.xlsx（工作表「各里彙總」）
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 |
    謝長廷得票率 | 馬英九得票率
    → 2008 第十二屆候選人（號次 01~02）：謝長廷／蘇貞昌(01,民主進步黨)、馬英九／蕭萬長(02,中國國民黨)
      本圖為「兩強」對決（馬英九／謝長廷）；色階（順序與 CAND_NAMES 一致，由使用者指定）：
      馬英九＝中國國民黨→藍、謝長廷＝民主進步黨→綠
      故本檔自帶 RATE_COLOR_STOPS（2 組），不沿用 2020 版的色表。

底圖來源：Base_JSON/twvillage2012.json（民國101年村里界，**取代原本的 107 版 SHP 圖源**）
    欄位 county / town / village（小寫）→ 讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME
    （見 load_base_map；欄位正規化與 EPSG:4326→EPSG:3826 的做法同
      Base_JSON/draw_json_map.py 與 draw_county_maps.py）。

行政區對照：2010 年高雄縣併入高雄市（直轄市），2008 舊名「高雄縣」對 2012 圖資「高雄市」； 原直轄高雄市之 11 區亦屬 2012「高雄市」，鄉鎮市區名不與原高雄縣各鄉鎮市重疊。

繪圖邏輯沿用 Draw_North4_President_2008.py（＝ 2016 版系），只換底圖（JSON）與得票資料（2008）：

  ① 線稿（兩層畫法）
     - 村里界 1px：PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線
     - 區界 3px + 縣市界/海岸線 5px：matplotlib(Agg, DPI=100) 繪區面與區界，
       以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層
     - 微孔洞清理（HOLE_MIN_AREA_M2）避免 dissolve 浮點誤差造成的散點
     - 迴針清理（remove_ring_slits）折疊圖資「去而復返」的退化迴針，避免
       dissolve 後殘留在區／縣市外環、被誤畫成憑空冒出的死線
     - 兩層同一像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加不錯開 1px
  ② 填色（同 2020 全臺腳本）
     - 得票率 Excel 讀取、異體字/模糊匹配、取最高者填色（5% 色階、35% 起）
     - 填色採「油漆桶／洪水填充」規則：以線稿構成封閉堤壩，堤壩以外每一塊
       4-連通區域整塊填單色，顏色取區域內像素幾何所屬村里的眾數
       → 顏色永不跨越任何一條黑線，密集村里區不會出現錯色
      - 自檢：① 油漆桶不變式（每塊非線區域皆單色）；② 與逐像素幾何參考
        （GDAL/rasterio 中心規則，獨立方法）差異 ≈0、村外非白 ≈0
      - 版面：**不畫標題、不畫圖例**——只輸出純地圖

與 2016 版（107 版 SHP 底圖）的差異：
  - 底圖：twvillage2012.json（民國101年村里界）。108/107 版 SHP 的離島與「無村里名」
    圖斑處置（strip_far_parts / DROP_NAN_COUNTIES）於本底圖依實測重新設定。
  - 得票資料：2008 各里彙總（2 位候選人：馬英九／謝長廷）；縣市名對照見 COUNTY_ALIAS。
  - 縣市 / 區層 dissolve（鍵 = COUNTYNAME, TOWNNAME）/ 線寬（村里 1px、區 3px、
    縣市界 5px）/ 比例尺 1px=20m / 不畫標題不畫圖例 —— 均與 2016 版相同。
  - 新增③ 缺資料回報：地圖上有圖斑卻對不上得票資料者，另寫 Markdown 表格（MISSING_MD）。

底圖 × 2008 村里名對齊（參考 `README.md` §5 與 village_name_repair.py）：
  - 村名修補：twvillage2012.json 以私用區(PUA)碼位或「■」代替罕見字，先還原成正字再比對
    （PUA 碼位可全域對應；「■」一字多義，逐一指定，多筆歧義者以同鄉鎮其餘村里的消去法確認）。
    見 village_name_repair.repair_json_vill_name。
  - 2008→2012 更名（同一單元改名）：如 高雄縣三民鄉民族/民權/民生村 →
    高雄市那瑪夏區南沙魯/瑪雅/達卡努瓦里（2007 鄉名改那瑪夏、2008 三村復舊名、2010 縣市合併），
    以及 桃源鄉梅蘭村 → 桃源區拉芙蘭里（2009 正名）。
    見 village_name_repair.TOWN_VILL_RENAME_2008，於得票資料讀入時改寫為 2012 底圖名。
  - 本區無村里「沿革合併」對照表（沿革表目前僅新北市），故不套用拆併合併；
    2012 圖資有、2008 未設立的里若對不上資料，一律留白並記入報告。

比例尺：1px = 20m
輸出：2008Precident/maps/高屏2008年總統副總統選舉_得票率地圖.png
     2008Precident/maps/高屏2008_無資料與未匹配村里.md
執行：py Draw_South2_President_2008.py
"""
import os
import re
import sys
import math
import time
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 共用模組（得票率匹配 / 填色 / 圖例 / 文字渲染）位於 2020Precident/scripts
SHARED_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_DIR)), "2020Precident", "scripts")
if SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS)
import Draw_National_President_2020 as nat
# twvillage2012.json 村里名修補（PUA 碼位 / ■ 佔位符還原；同目錄）
import village_name_repair as nr

# ===================== 配置 =====================
# 2008 第十二屆總統副總統選舉候選人（號次 01~02）：謝長廷／蘇貞昌(01,民主進步黨)、
#   馬英九／蕭萬長(02,中國國民黨)；本圖為「兩強」對決（馬英九／謝長廷）。
#   順序＝ RATE_COLOR_STOPS 順序（馬英九→藍、謝長廷→綠），非 Excel 欄位順序。
CAND_NAMES = ["馬英九", "謝長廷"]
CAND_RATE_COLS = [f"{n}得票率" for n in CAND_NAMES]

# 2008 候選人色階（順序與 CAND_NAMES 一致；由使用者指定）：
#   馬英九＝中國國民黨→藍、謝長廷＝民主進步黨→綠
RATE_COLOR_STOPS = [
    [(35, "#A6E9FF"), (40, "#73D9FF"), (45, "#40C8FF"), (50, "#00C0F4"),
     (55, "#00A2E8"), (60, "#0080B8"), (65, "#006591"), (70, "#004B6B"),
     (75, "#003247"), (80, "#00283A"), (85, "#001F2E"), (100, "#010D29")],
    [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
     (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
     (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
]

# 2008 舊行政區名 → twvillage2012.json 縣市名（2010 五都升格之縣市合併）
#   2010 年高雄縣併入高雄市（直轄市），2008 舊名「高雄縣」對 2012 圖資「高雄市」；
#   原直轄高雄市之 11 區亦屬 2012「高雄市」，鄉鎮市區名不與原高雄縣各鄉鎮市重疊。
COUNTY_ALIAS = {"高雄縣": "高雄市"}   # 2008 高雄縣 → 2012 直轄市高雄市（2010 縣市合併）

# 2008 各里得票率 Excel（工作表「各里彙總」）
VOTE_XLSX = os.path.join(os.path.dirname(SCRIPT_DIR), "data",
                         "2008總統副總統選舉_得票率.xlsx")

# 底圖：民國101年村里界 twvillage2012.json（取代原本的 SHP 圖源）
# 欄位為 county / town / village（小寫），讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME；
# 檔案無內建 CRS → 視為 EPSG:4326，再投影至 EPSG:3826
# （欄位正規化與 EPSG:4326→3826 的做法同 Base_JSON/draw_json_map.py、draw_county_maps.py）
MAP_JSON = r"D:\Windows\TaiwanElection\Base_JSON\twvillage2012.json"
OUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "maps")
OUT_PNG = os.path.join(OUT_DIR, "高屏2008年總統副總統選舉_得票率地圖.png")
MISSING_MD = os.path.join(OUT_DIR, "高屏2008_無資料與未匹配村里.md")   # ③ 缺資料回報
layer_name = "layer_south2_2008_district_2px.png"   # ② 層單獨輸出（核對用）
TARGET_COUNTIES = ["高雄市", "屏東縣"]
TARGET_CRS = "EPSG:3826"

# 比例尺：1px = 20m（不再額外放大）
# 高屏 bbox 約 90 × 175 km（高雄梓官～屏東鵝鑾鼻、高雄那瑪夏～小琉球）
# 1px=20m 後地圖長寬皆 < MAX_PX
METERS_PER_PIXEL = 20.0
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.01

SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（沿用 DrawTaichungCity.py：簡化會把緩彎拉直）

LINE_TOWNSHIP_PX = 3     # ② 區界線寬(px)
LINE_OUTER_PX = 5        # ② 縣市界/海岸線線寬(px)
THRESHOLD_VAL = 40       # ② 二值化閾值
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為 dissolve 雜訊，填平
# 無村里名(VILLNAME 空)的圖斑：這些縣市整筆不畫
    # 高雄市港區/航道水域（前鎮/小港/旗津/鼓山之無村里名圖斑）整筆不畫
DROP_NAN_COUNTIES = ["高雄市"]
REMOTE_MAX_DIST_M = 2000.0   # 無村里名者：與本島相距超過此值 → 不畫（外海無編制離島）
NAMED_MAX_DIST_M = 20000.0   # 有村里名者：超過此值才視為圖資錯誤碎塊並剔除
# 門檻沿用 2016 版；2012 圖資本區實測依 ② 層連通分量自檢期待值動態決定（EXPECT_CC）。
SAVE_LAYER = False
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)



# ----------------------① 讀底圖 + 讀得票率 + 匹配填色----------------------
def _norm_vill(s):
    """村里名正規化（比對用）：共用 normalize + 去「村/里」尾綴，再套 2008 異體字收斂。

    nr.VARIANT_CHAR_MAP_2008 讓底圖修補後的正名與 2008 資料用字收斂到同一形。
    """
    return nat.strip_village_suffix(s).translate(nr.VARIANT_CHAR_MAP_2008)


def load_vote_data(vote_xlsx=VOTE_XLSX):
    """讀取 2008 各里得票率 Excel（工作表「各里彙總」）。

    欄位：選舉區別 | 鄉(鎮、市、區)別 | 村里別 |
          謝長廷得票率 | 馬英九得票率
    得票率依 CAND_NAMES（= CAND_RATE_COLS）順序擷取為 tuple（字尾 % 移除），
    回傳 (by_key, by_town, n_rows, n_total)，供 nat.fuzzy_lookup 使用。
    縣市名先套 COUNTY_ALIAS 以與 2012 底圖對齊。
    源資料若將多村里併為一列（以 、 分隔），拆解成各村(里)並共用同一組得票率。
    村里名再套 VOTE_NAME_REPAIR（破損/誤植）與 TOWN_VILL_RENAME_2008（2008→2012 更名）。
    """
    by_key, by_town = {}, {}
    n_total, n_rows = 0, 0
    df = pd.read_excel(vote_xlsx, sheet_name="各里彙總", dtype=str)
    df.columns = [str(c) for c in df.columns]
    need = ["選舉區別", "鄉(鎮、市、區)別", "村里別"] + CAND_RATE_COLS
    lack = [c for c in need if c not in df.columns]
    if lack:
        raise ValueError(f"{os.path.basename(vote_xlsx)} 缺少欄位：{'、'.join(lack)}")
    for _, r in df.iterrows():
        county = nat.normalize_text(r.get("選舉區別"))
        county = COUNTY_ALIAS.get(county, county)   # 2008 舊名 → 2012 圖資名
        town = nat.strip_town_suffix(r.get("鄉(鎮、市、區)別"))
        vill_raw = nat.normalize_text(r.get("村里別"))
        if not county or not town or not vill_raw:
            continue
        try:
            vals = tuple(float(str(r[c]).strip().replace("%", "").replace("\u00a0", ""))
                         for c in CAND_RATE_COLS)
        except (TypeError, ValueError):
            continue
        if not all(np.isfinite(v) for v in vals):
            continue
        n_total += 1
        parts = [p for p in re.split(r"[、，,]", vill_raw) if p.strip()]
        for part in parts:
            part_core = _norm_vill(part.strip())
            part_core = nr.VOTE_NAME_REPAIR.get((county, town, part_core), part_core)
            if not part_core:
                continue
            # 2008→2012 更名（如同單元改名：高雄縣三民鄉民族村 → 高雄市那瑪夏區南沙魯里）；
            # 改寫後即與 2012 底圖名一致，能精確匹配。
            town, part_core = nr.rename_town_vill_2008(county, town, part_core)
            key = (county, town, part_core)
            if key in by_key:
                continue
            by_key[key] = vals
            by_town.setdefault((county, town), []).append((part_core, vals))
            n_rows += 1
    return by_key, by_town, n_rows, n_total


def load_base_map(path=MAP_JSON):
    """讀入 JSON 村里界底圖，正規化欄位後回傳 GeoDataFrame。

    取代原本的 SHP 讀取，做法與 Base_JSON/draw_json_map.py、draw_county_maps.py 一致：
      gpd.read_file(json) → 無 CRS 者補 EPSG:4326 → to_crs(EPSG:3826)。
    JSON 欄位為 county / town / village（小寫），統一改名為 COUNTYNAME / TOWNNAME /
    VILLNAME，讓後續 dissolve / 匹配 / 清理邏輯直接沿用原 SHP 版的欄位名。
    """
    gdf = gpd.read_file(path)
    rename = {}
    lower = {c.lower(): c for c in gdf.columns}
    for src, dst in (("county", "COUNTYNAME"), ("town", "TOWNNAME"),
                     ("village", "VILLNAME")):
        if dst in gdf.columns:
            continue
        if src in lower:
            rename[lower[src]] = dst
    if rename:
        gdf = gdf.rename(columns=rename)
        print("底圖欄位正規化：" + "、".join(f"{k}->{v}" for k, v in rename.items()))
    lack = [c for c in ("COUNTYNAME", "TOWNNAME", "VILLNAME") if c not in gdf.columns]
    if lack:
        raise ValueError(f"{os.path.basename(path)} 缺少欄位：{'、'.join(lack)}"
                         f"（現有：{gdf.columns.tolist()}）")

    if gdf.crs is None:
        gdf.crs = "EPSG:4326"
    gdf = gdf.to_crs(TARGET_CRS)

    gdf = gdf[gdf["COUNTYNAME"].notna()].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf[gdf["COUNTYNAME"].astype(str).str.strip().isin(TARGET_COUNTIES)].copy()
    gdf = gdf[gdf["TOWNNAME"].notna()].copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf["COUNTYNAME"] = gdf["COUNTYNAME"].astype(str).str.strip()
    gdf["TOWNNAME"] = gdf["TOWNNAME"].astype(str).str.strip()
    gdf = gdf[~gdf["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf.reset_index(drop=True)
    return gdf


def repair_base_names(gdf):
    """還原 twvillage2012.json 的村里名正字（私用區 PUA 碼位 / 「■」佔位符）。

    就地改寫 VILLNAME；另存 VILLNAME_RAW（原名）與 NAME_REPAIR
    （非空者＝該列曾修補，值為「原名 → 正名」），供缺資料報告第 4 節逐筆核對。
    修補規則見 village_name_repair.repair_json_vill_name。
    """
    raw = gdf["VILLNAME"].tolist()
    fixed, notes = [], []
    for c, t, v in zip(gdf["COUNTYNAME"], gdf["TOWNNAME"], raw):
        fv, _chg, note = nr.repair_json_vill_name(str(c), str(t), v)
        fixed.append(fv)
        notes.append(note)
    out = gdf.copy()
    out["VILLNAME_RAW"] = raw
    out["VILLNAME"] = fixed
    out["NAME_REPAIR"] = notes
    _n = int((out["NAME_REPAIR"].astype(str).str.len() > 0).sum())
    if _n:
        print(f"  ② 底圖村名修補（PUA 碼位／■ 還原）：{_n} 筆")
    return out


def write_missing_report(gdf_all, vote_dict):
    """把匹配稽核結果寫成 Markdown（MISSING_MD）：

     ① 地圖有村里圖斑、卻對不上得票資料（留白）
     ② 模糊匹配（異體字/近似）
     ③ 得票資料有、底圖無對應村里圖斑（反向缺漏）
     ④ 底圖村名修補（PUA 碼位／■ 還原）——校對用
     ⑤ 村里沿革合併（本地區無沿革表，故此節為空）
     ⑥ 各縣市比對統計
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    none_df = gdf_all[gdf_all["match_type"] == "none"].sort_values(
        ["COUNTYNAME", "TOWNNAME", "VILLNAME"])
    fuzzy_df = gdf_all[gdf_all["match_type"].str.startswith("fuzzy", na=False)]
    repair_df = gdf_all[gdf_all["NAME_REPAIR"].astype(str).str.len() > 0].sort_values(
        ["COUNTYNAME", "TOWNNAME", "VILLNAME"])
    exact_n = int((gdf_all["match_type"] == "exact").sum())

    used = {(r["county_core"], r["town_core"], r["matched_vill"])
            for _, r in gdf_all[gdf_all["match_type"] != "none"].iterrows()}
    tgt = set(TARGET_COUNTIES)
    orphan = sorted(k for k in vote_dict if k[0] in tgt and k not in used)

    L = []
    L.append(f"# 高屏 2008 總統副總統選舉 得票率地圖 — 匹配稽核")
    L.append("（無資料／未匹配／村名修補）")
    L.append("")
    L.append(f"- 產生時間：{ts}")
    L.append(f"- 底圖：`twvillage2012.json`（民國101年村里界） → 高屏 {len(gdf_all)} 個村里圖斑")
    L.append(f"- 得票資料：`2008總統副總統選舉_得票率.xlsx`（工作表「各里彙總」，全國 {len(vote_dict)} 筆村里）")
    L.append(f"- 匹配結果：精確 **{exact_n}**、模糊 **{len(fuzzy_df)}**、無資料 **{len(none_df)}**（圖上留白）")
    L.append("")

    L.append(f"## 1. 地圖上有村里圖斑、但對不上得票資料（{len(none_df)} 筆 → 留白）")
    L.append("")
    if len(none_df):
        L.append("| # | 縣市 | 鄉鎮市區 | 村里 | 說明 |")
        L.append("|---:|---|---|---|---|")
        for i, (_, r) in enumerate(none_df.iterrows(), 1):
            L.append(f"| {i} | {r['COUNTYNAME']} | {r['TOWNNAME']} | {r['VILLNAME']} | 無對應得票資料 |")
        L.append("")
        L.append("### 依縣市統計")
        L.append("")
        L.append("| 縣市 | 無資料村里數 |")
        L.append("|---|---:|")
        for c, n in none_df.groupby("COUNTYNAME").size().items():
            L.append(f"| {c} | {int(n)} |")
    else:
        L.append("（無）")
    L.append("")

    L.append(f"## 2. 模糊匹配（異體字/近似；{len(fuzzy_df)} 筆）")
    L.append("")
    if len(fuzzy_df):
        L.append("| # | 縣市 | 鄉鎮市區 | 底圖村里 | 對應得票資料村里 | 匹配方式 |")
        L.append("|---:|---|---|---|---|---|")
        for i, (_, r) in enumerate(fuzzy_df.iterrows(), 1):
            L.append(f"| {i} | {r['COUNTYNAME']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
                     f"{r['matched_vill']} | {r['match_type']} |")
    else:
        L.append("（無）")
    L.append("")

    L.append(f"## 3. 得票資料有、底圖卻無對應村里圖斑（本區內，{len(orphan)} 筆）")
    L.append("")
    if orphan:
        L.append("| # | 縣市 | 鄉鎮市區 | 村里（得票資料） |")
        L.append("|---:|---|---|---|")
        for i, (c, t, v) in enumerate(orphan, 1):
            L.append(f"| {i} | {c} | {t} | {v} |")
    else:
        L.append("（無）")
    L.append("")

    L.append(f"## 4. 底圖村名修補（twvillage2012.json 罕見字還原；{len(repair_df)} 筆）")
    L.append("")
    L.append("> JSON 以私用區(PUA)碼位或「■」代替罕見字，先還原成正字再與 2008 資料比對。")
    L.append("> 規則見 `village_name_repair.repair_json_vill_name`。")
    L.append("")
    if len(repair_df):
        L.append("| # | 縣市 | 鄉鎮市區 | 圖資原名 | 修補後 |")
        L.append("|---:|---|---|---|---|")
        for i, (_, r) in enumerate(repair_df.iterrows(), 1):
            L.append(f"| {i} | {r['COUNTYNAME']} | {r['TOWNNAME']} | "
                     f"{r['VILLNAME_RAW']} | {r['VILLNAME']} |")
    else:
        L.append("（無）")
    L.append("")

    L.append("## 5. 村里沿革合併")
    L.append("")
    L.append("> 本地區無村里沿革對照表（沿革表目前僅新北市，見 `village_lineage_north4.py`），")
    L.append("> 故不套用沿革合併；2012 圖資有、2008 未設立的里若對不上資料，一律留白並記入第 1 節。")
    L.append("（無）")
    L.append("")

    # 5b. 2008→2012 更名（同一單元改名，非拆併）：得票資料已改寫為 2012 底圖名
    rename_rows = [(c, t1, v1, t2, v2)
                   for (c, t1, v1), (t2, v2) in sorted(nr.TOWN_VILL_RENAME_2008.items())
                   if c in tgt]
    L.append(f"## 5b. 2008→2012 鄉鎮市區／村里更名（{len(rename_rows)} 筆）")
    L.append("")
    L.append("> 同一行政單元改名（非拆併）：得票資料讀入時已改寫為 2012 底圖名，故能精確匹配。")
    L.append("> 規則見 `village_name_repair.TOWN_VILL_RENAME_2008`。")
    L.append("")
    if rename_rows:
        L.append("| # | 縣市 | 2008 鄉鎮市區 | 2008 村里 | → 2012 鄉鎮市區 | → 2012 村里 |")
        L.append("|---:|---|---|---|---|---|")
        for i, (c, t1, v1, t2, v2) in enumerate(rename_rows, 1):
            L.append(f"| {i} | {c} | {t1} | {v1} | {t2} | {v2} |")
    else:
        L.append("（無）")
    L.append("")

    L.append("## 6. 各縣市比對統計")
    L.append("")
    L.append("| 縣市 | 村里圖斑 | 精確 | 模糊 | 無資料 |")
    L.append("|---|---:|---:|---:|---:|")
    for c in TARGET_COUNTIES:
        s = gdf_all[gdf_all["COUNTYNAME"] == c]
        if not len(s):
            continue
        L.append(f"| {c} | {len(s)} | {int((s['match_type'] == 'exact').sum())} | "
                 f"{int(s['match_type'].str.startswith('fuzzy', na=False).sum())} | "
                 f"{int((s['match_type'] == 'none').sum())} |")
    L.append("")

    with open(MISSING_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  ③ 匹配稽核報告：{MISSING_MD}")
    print(f"     （無資料 {len(none_df)}、村名修補 {len(repair_df)}、模糊 {len(fuzzy_df)}、反向缺漏 {len(orphan)}）")


def expected_line_components(gdf):
    """由幾何拓樸導出 ② 層線稿連通分量的「上限」＝ 陸塊數 ＋ 內環(洞)數。

    線稿由各區面聯集的外環與內環構成：每個陸塊外環、每個內環各自是一條獨立閉合線。
    柵格化（加粗描線）只會把鄰近圖斑併為同一分量、或略去極小圖斑，故實際分量數
    <= 此上限。較「1 + 保留離島數」穩健——後者無法反映同一島上多里（會多算）、
    或一里含多個離岸圖斑（會少算）。
    """
    U = unary_union(gdf.geometry.tolist())
    polys = list(U.geoms) if hasattr(U, "geoms") else [U]
    n = 0
    for p in polys:
        if p.geom_type != "Polygon":
            continue
        n += 1 + len(p.interiors)
    return n


def main():
    print("=" * 62)
    print("  高屏 2008 總統副總統選舉 各村（里）得票率地圖")
    print("=" * 62)

    gdf_all = load_base_map(MAP_JSON)
    gdf_all = repair_base_names(gdf_all)

    # 指定縣市的「無村里名」圖斑整筆不畫 高雄市港區/航道水域（前鎮、小港、旗津、鼓山之無村里名圖斑）
    if DROP_NAN_COUNTIES:
        _vv = gdf_all["VILLNAME"].fillna("").astype(str).str.strip()
        _drop = gdf_all["COUNTYNAME"].isin(DROP_NAN_COUNTIES) & _vv.isin(["", "nan", "None"])
        if _m := int(_drop.sum()):
            print(f"  無村里名不畫（{ '、'.join(DROP_NAN_COUNTIES) }）：剔除 {_m} 筆")
            gdf_all = gdf_all[~_drop].copy().reset_index(drop=True)

    # 遠離本島的圖斑處理：無村里名者超 2km 剔除；有村里名者超 20km 才剔除
    gdf_all = strip_far_parts(gdf_all)

    # 得票率（2008 各里彙總 Excel，異體字/模糊匹配沿用全臺腳本）
    vote_dict, vote_by_town, n_rows, n_total = load_vote_data()
    print(f"  Excel 得票率記錄 : {n_total} 筆（去重後 {n_rows} 筆）")

    gdf_all["county_core"] = gdf_all["COUNTYNAME"].apply(nat.normalize_text)
    gdf_all["town_core"] = gdf_all["TOWNNAME"].apply(nat.strip_town_suffix)
    gdf_all["vill_core"] = gdf_all["VILLNAME"].apply(_norm_vill)

    rate_cols = [f"rate{i}" for i in range(len(CAND_NAMES))]

    # 本地區無村里沿革對照表 → 行政單元即村里本身
    gdf_all["unit_core"] = gdf_all["vill_core"]

    def process_row(r):
        matched, vals, mt = nat.fuzzy_lookup(
            r["county_core"], r["town_core"], r["vill_core"], vote_dict, vote_by_town)
        if vals is None:
            return pd.Series([np.nan] * len(CAND_NAMES) + [mt, ""])
        return pd.Series(list(vals) + [mt, matched])

    gdf_all[rate_cols + ["match_type", "matched_vill"]] = gdf_all.apply(process_row, axis=1)

    exact_cnt = int((gdf_all["match_type"] == "exact").sum())
    fuzzy_cnt = int((gdf_all["match_type"].str.startswith("fuzzy", na=False)).sum())

    # ③ 缺資料／未匹配回報（Markdown 表格；含 ④ 村名修補校對表）
    write_missing_report(gdf_all, vote_dict)

    # 三位候選人取最高者填色；無資料(含 VILLNAME 空值)一律純白
    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return nat.get_color_by_value(vals[i], RATE_COLOR_STOPS[i])

    gdf_all["fill_hex"] = np.where(
        gdf_all[rate_cols].notna().any(axis=1),
        gdf_all.apply(pick_fill_color, axis=1),
        nat.NO_DATA_COLOR,
    )
    gdf_all["fill_hex"] = gdf_all["fill_hex"].fillna(nat.NO_DATA_COLOR)

    has_data = gdf_all[rate_cols].notna().any(axis=1)
    print(f"  JSON 要素數      : {len(gdf_all)}")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字/模糊匹配   : {fuzzy_cnt}")
    print(f"  有資料填色       : {int(has_data.sum())}")
    print(f"  無資料（純白）    : {int((~has_data).sum())}")

    # 各候選人領先村里數（僅供統計；不畫圖例）
    _win = np.argmax(gdf_all.loc[has_data, rate_cols].fillna(0.0).to_numpy(dtype=float), axis=1)
    active_idx = [i for i in range(len(CAND_NAMES)) if int((_win == i).sum()) > 0]
    for i, nm in enumerate(CAND_NAMES):
        print(f"    領先村里：{nm} {int((_win == i).sum())} 村")
    assert active_idx, "無任何候選人領先村里"

    min_win_rate = 100.0
    for _, row in gdf_all[has_data].iterrows():
        win = max(row[c] for c in rate_cols)
        if win < min_win_rate:
            min_win_rate = win
    print(f"  最低領先得票率   : {min_win_rate:.2f}%")

    records = gdf_all.copy()
    villages = records[records["VILLNAME"].notna()].copy()   # ① 村里層
    if SIMPLIFY_TOL_M > 0:
        villages["geometry"] = villages.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
    # 村里界線以「當年行政單元」為單位（本地區 = 村里本身）
    _ukey = (villages["COUNTYNAME"].astype(str) + "|" + villages["TOWNNAME"].astype(str)
             + "|" + villages["unit_core"].astype(str))
    _blank = villages["unit_core"].astype(str).str.strip().eq("")
    _ukey = _ukey.where(~_blank, _ukey + "#" + villages.index.astype(str))
    unit_polys = villages.assign(_unit_key=_ukey).dissolve(by="_unit_key").reset_index()
    # ② 區層：含未編定村里圖斑（港區/水域等），區界才完整。
    #    必須以 (縣市, 區) 為鍵——同名之區（如臺南/高雄各有「中正、三民」類）不可合併
    townships = records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
    print(f"  縣市：{records['COUNTYNAME'].nunique()}，區：{len(townships)}，村里 {len(villages)}"
          f"（單元 {len(unit_polys)}）")
    for c in TARGET_COUNTIES:
        print(f"    {c}：村里 {int((records['COUNTYNAME'] == c).sum())}")

    townships = remove_ring_slits(townships)
    townships = clean_tiny_holes(townships)
    # ② 層連通分量期待值：由幾何拓樸導出（見 expected_line_components）
    EXPECT_CC = expected_line_components(townships)

    # ----------------------畫布尺寸----------------------
    minx, miny, maxx, maxy = records.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w_m, geo_h_m = maxx - minx, maxy - miny

    scale = max(geo_w_m / MAX_PX, geo_h_m / MAX_PX, METERS_PER_PIXEL) / SCALE_UP
    w_px = int(math.ceil(geo_w_m / scale))
    h_px = int(math.ceil(geo_h_m / scale))
    sx, sy = w_px / geo_w_m, h_px / geo_h_m
    print(f"  統一比例尺：1像素 = {geo_w_m / w_px:.4f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px")

    DPI = nat.DPI

    # ----------------------② 區界 + 縣市界 + 海岸線----------------------
    print(f"  ② 區界 {LINE_TOWNSHIP_PX}px + 縣市界/海岸線 {LINE_OUTER_PX}px（matplotlib + 閾值二值化）...")
    town_layer = render_line_layer(townships, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    print(f"  區/縣市界層：{int(town_layer.sum())} px"
          f"（區界 {LINE_TOWNSHIP_PX}px、縣市界/外輪廓 {LINE_OUTER_PX}px，閾值 {THRESHOLD_VAL}）")

    # ----------------------① 村里界 1px----------------------
    print("  ① 村里界 1px（1px 直繪 → thin 中心線）...")
    village_lines = extract_lines(unary_union(unit_polys.geometry.boundary.tolist()))
    village_arr = draw_layer(village_lines, 1, w_px, h_px, minx, maxy, sx, sy)
    village_skel = thin(village_arr)
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # 對齊自檢：② 層必須覆蓋區界/縣市界 1px 原始線
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1,
                           w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
    print(f"  區/縣市界 1px 原始線 {int(_town_1px.sum())} px，未被 {LINE_TOWNSHIP_PX}/{LINE_OUTER_PX}px 層覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層不得有 <=40px 碎塊；連通分量數不得超過「陸塊＋顯著內環」幾何上限。
    #   柵格化畫（加粗）只會把鄰近圖斑併為同一分量、或略去極小圖斑，故 實際 <= 上限；
    #   超過上限（憑空多出的孤立線）或有 <=40px 小分量，才示警。
    _cc_n, _, _cc_st, _ = cv2.connectedComponentsWithStats(town_layer.astype(np.uint8), connectivity=8)
    _cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
    _cc_small = int((_cc_area <= 40).sum())
    print(f"  ② 層連通分量：{_cc_n - 1} 個（幾何上限 {EXPECT_CC}＝陸塊＋顯著內環；"
          f"僅超過上限或出現碎塊才示警）；<=40px 小分量 {_cc_small} 個（應為 0）")
    if _cc_n - 1 > EXPECT_CC or _cc_small:
        for _i in range(1, _cc_n):
            _x, _y, _w, _h, _a = _cc_st[_i]
            print(f"    ⚠️ comp{_i}: area={_a} bbox=({_x},{_y})-({_x + _w},{_y + _h})")

    lines_mask = village_skel | town_layer

    # 村里線自檢：扣掉 ② 層後不應出現 2x2 粗塊
    _v_only = village_skel & ~town_layer
    _2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
    print(f"  村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")

    # ----------------------填色（線稿為堤壩，逐塊洪水填充）----------------------
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）...")
    arr, ncomp, comp = flood_fill_layer(
        records, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ----------------------疊加線界----------------------
    arr[lines_mask] = 0
    print(f"  黑像素合計：{int(lines_mask.sum())}  非線連通區域：{ncomp - 1} 塊")

    # 自檢 A：油漆桶不變式——每塊非線 4-連通區域必須只含單一顏色（色不越過黑線）
    _nc, _nbad = check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")

    # 自檢 B：與逐像素幾何參考的差異
    _nw, _nout = full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%；"
          f"村外非白 {_nout}；皆應 ≈0）")

    # 顏色驗證：全圖只應含允許色（填色 + 純白底 + 純黑線）
    allowed = {(255, 255, 255), (0, 0, 0)}
    for stops in RATE_COLOR_STOPS:
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in nat.hex2rgb(hx)))
    _uniq, _cnt = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    _bad = [(tuple(int(x) for x in c), int(n))
            for c, n in zip(_uniq, _cnt) if tuple(int(x) for x in c) not in allowed]
    _n_bad = sum(n for _, n in _bad)
    print(f"  全圖顏色種類：{len(_uniq)}（允許 {len(allowed)}）；非允許色像素：{_n_bad} px（應為 0）")
    if _bad:
        print(f"  ⚠️ 非允許色：{_bad[:5]}")

    pil_img = Image.fromarray(arr, mode="RGB")
    del arr

    # ----------------------不畫標題、不畫圖例：直接輸出純地圖----------------------
    if SAVE_LAYER:
        _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
        _la[town_layer] = 0
        Image.fromarray(_la, mode="RGB").save(os.path.join(OUT_DIR, layer_name))

    W, H = pil_img.size
    pil_img.save(OUT_PNG)
    del pil_img

    # 存檔後自檢
    _re = np.asarray(Image.open(OUT_PNG).convert("RGB"))
    _re_map = _re[:H, :W]
    _u2, _c2 = np.unique(_re_map.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _nw2, _nout2 = full_geom_check(_re_map, records, w_px, h_px, minx, maxy, sx, sy)
    _tol2 = 0.0002 * w_px * h_px
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、"
          f"幾何參考差異 {_nw2} px（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    if _bad2 or _nout2 or _nw2 > _tol2:
        print(f"  ⚠️ bad={_bad2[:5]} wrong={_nw2} out={_nout2}")
    print(f"\n  Saved: {OUT_PNG}  ({W}×{H}px)")
    print("==== All finished ====")



# ===================== 圖資清理 =====================
def strip_far_parts(gdf, max_dist_nameless=REMOTE_MAX_DIST_M, max_dist_named=NAMED_MAX_DIST_M):
    """剔除遠離本島的離島圖斑與圖資錯誤碎塊，門檻依「該圖斑所屬記錄有無村里名」而異。

    作法是取全部圖斑的聯集，其最大連通分量即為本島；再對每個圖斑算與本島的距離：
      - 無村里名（無編制）者：> max_dist_nameless(2km) 即剔除
      - 有村里名（有編制）者：> max_dist_named(20km) 才剔除
    有編制的離島必須保留（如屏東琉球鄉的小琉球、宜蘭頭城鎮龜山島）。

    本檔底圖 twvillage2012.json 的北北基宜子集本身即為單一連通塊、無 >500m 離岸
    圖斑，故實測「無需剔除」、n_islands=0（2016 版所用的 108 版 SHP 則會剔除基隆
    外海礁岩、宜蘭大溪里 120km 外海碎塊）。
    """
    parts, owner = [], []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for pp in ps:
            parts.append(pp)
            owner.append(i)
    if not parts:
        return gdf
    merged = unary_union(parts)
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)

    vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
    named = (~vv.isin(["", "nan", "None"])).to_numpy()
    thr = np.where(named[np.array(owner, dtype=int)], max_dist_named, max_dist_nameless)
    dist = np.array([main.distance(pp) for pp in parts])
    keep_flags = dist <= thr

    dropped = np.nonzero(~keep_flags)[0]
    if len(dropped):
        print(f"  離島/碎塊清理：剔除 {len(dropped)} 個圖斑"
              f"（無村里名 > {max_dist_nameless / 1000:.0f}km、有村里名 > {max_dist_named / 1000:.0f}km）")
        import collections
        cnt = collections.Counter(owner[j] for j in dropped)
        for i, n in cnt.most_common(12):
            tot = len(list(gdf.geometry.iloc[i].geoms)) if hasattr(gdf.geometry.iloc[i], "geoms") else 1
            nm = vv.iloc[i]
            nm = "（無村里名）" if nm in ("", "nan", "None") else nm
            ds = dist[[j for j in dropped if owner[j] == i]]
            print(f"    {gdf['COUNTYNAME'].iloc[i]} {gdf['TOWNNAME'].iloc[i]} {nm}"
                  f"：剔除 {n}/{tot} 塊（距本島 {ds.min() / 1000:.1f}~{ds.max() / 1000:.1f}km）")
    else:
        print("  離島/碎塊清理：無需剔除")

    # 保留的有編制離島（如龜山島）——列出來供核對
    kept_far = [j for j in range(len(parts)) if keep_flags[j] and dist[j] > 500]
    kept_cent = []
    if kept_far:
        import collections
        cnt = collections.Counter(owner[j] for j in kept_far)
        for i, n in cnt.most_common(8):
            ds = dist[[j for j in kept_far if owner[j] == i]]
            c = parts[[j for j in kept_far if owner[j] == i][0]].centroid
            kept_cent.append((c.x, c.y))
            print(f"    保留離島：{gdf['COUNTYNAME'].iloc[i]} {gdf['TOWNNAME'].iloc[i]} {vv.iloc[i]}"
                  f"（{n} 塊，距本島 {ds.min() / 1000:.1f}~{ds.max() / 1000:.1f}km）")

    # 以 part 索引重建各記錄的幾何
    idx0 = 0
    rebuilt = []
    for i, geom in enumerate(gdf.geometry):
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kp = [ps[k] for k in range(len(ps)) if keep_flags[idx0 + k]]
        idx0 += len(ps)
        if not kp:
            rebuilt.append(None)
        elif len(kp) == 1:
            rebuilt.append(kp[0])
        else:
            rebuilt.append(MultiPolygon(kp))
    out = gdf.copy()
    out["geometry"] = rebuilt
    out = out[~out["geometry"].isna() & ~out["geometry"].is_empty].copy().reset_index(drop=True)
    print(f"  清理後要素數：{len(out)}（原 {len(gdf)}）")
    out.attrs["n_islands"] = len(kept_cent)   # 供 ② 層連通分量自檢期待值用
    return out


# ===================== 線稿工具 =====================
def _despike_ring(coords, tol=5.0, area_thr=5000.0, min_path=100.0):
    """折疊單一線環（ring）中的「迴針／零寬裂縫」退化子路徑。

    村里界圖資在少數里別邊界有數位化瑕疵：線環從某點出發、沿同一條路徑往外
    走數百公尺～數公里後又原路折返（去而復返），圍出的面積近乎 0。dissolve
    後這種退化迴針會殘留在區／縣市外環或內環上，繪圖時就變成地圖中間憑空
    冒出的「死線」（一端接邊界、另一端懸空）。新竹市香山區、臺南市歸仁區等
    皆有數筆。

    作法：對每個頂點 i 找最近的其他頂點 j（僅計 i+2 之後、排除線環首尾
    閉合），若 |Pj-Pi| <= tol 且子路徑 i..j 的長度 > min_path、圍出面積 <
    area_thr，即視為退化迴針，刪除 i+1..j-1 之間的頂點將其折疊回一個點。
    三道門檻（位移、長度、面積）確保真實的半島、岬角、細長沙洲不會被誤刪。
    """
    P = np.asarray(coords, dtype=float)
    n = len(P)
    if n < 5:
        return P
    dead = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        if dead[i]:
            i += 1
            continue
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        d[:i + 2] = np.inf            # 至少隔 2 個點才算「繞了一大圈」
        if i == 0:
            d[n - 1] = np.inf         # 排除線環正常的首尾閉合
        j = int(np.argmin(d))
        if d[j] <= tol:
            seg = P[i:j + 1]
            path_len = float(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])).sum())
            _x, _y = seg[:, 0], seg[:, 1]
            area = 0.5 * abs(np.dot(_x[:-1], _y[1:]) - np.dot(_x[1:], _y[:-1]))
            if path_len > min_path and area < area_thr:
                dead[i + 1:j] = True  # 折疊此迴針
        i += 1
    return P[~dead]


def remove_ring_slits(gdf, tol=5.0, area_thr=5000.0, min_path=100.0, verbose=True):
    """移除區層多邊形外環/內環的退化迴針（見 _despike_ring）。

    只作用於 dissolve 後的區層；村里層（① 1px）實測無此瑕疵，不需處理。
    """
    n_ring_fixed = 0
    n_vert_removed = 0

    def _fix(geom):
        nonlocal n_ring_fixed, n_vert_removed
        if geom is None or geom.is_empty:
            return geom
        out = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            ext = _despike_ring(poly.exterior.coords, tol, area_thr, min_path)
            if len(ext) != len(poly.exterior.coords):
                n_ring_fixed += 1
                n_vert_removed += len(poly.exterior.coords) - len(ext)
            holes = []
            for r in poly.interiors:
                h = _despike_ring(r.coords, tol, area_thr, min_path)
                if len(h) != len(r.coords):
                    n_ring_fixed += 1
                    n_vert_removed += len(r.coords) - len(h)
                if len(h) >= 4:
                    holes.append(h)
            out.append(Polygon(ext, holes).buffer(0))
        if not out:
            return geom
        return out[0] if len(out) == 1 else MultiPolygon(out)

    o = gdf.copy()
    o["geometry"] = o.geometry.apply(_fix)
    o = o[~o.geometry.isna() & ~o.geometry.is_empty].copy().reset_index(drop=True)
    if verbose:
        print(f"  區層迴針清理：修正 {n_ring_fixed} 個線環、折疊 {n_vert_removed} 個頂點"
              f"（tol={tol:.0f}m、面積<{area_thr:.0f}m²、長度>{min_path:.0f}m）"
              if n_ring_fixed else "  區層迴針清理：無退化迴針")
    return o


def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環(洞)與過小碎片（dissolve 浮點誤差造成的微孔）。"""
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        kept = []
        for poly in parts:
            if poly.geom_type != "Polygon":
                continue
            if poly.area < min_area:
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


def to_px(coords, minx, maxy, sx, sy):
    """像素網格約定：像素 i 中心 = minx+(i+0.5)/sx（floor，與 matplotlib 渲染網格一致）"""
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def extract_lines(gs):
    if hasattr(gs, "geoms"):
        parts = list(gs.geoms)
    else:
        parts = [gs]
    out = []
    for g in parts:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(list(g.coords))
        elif g.geom_type == "MultiLineString":
            out.extend(list(ls.coords) for ls in g.geoms)
        elif g.geom_type == "GeometryCollection":
            out.extend(extract_lines(g))
    return out


def draw_layer(lines, width, w_px, h_px, minx, maxy, sx, sy):
    """Bresenham 逐段描繪 width 像素寬的純黑白線，返回 bool 陣列"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords, minx, maxy, sx, sy)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    return np.asarray(im) < 128


def render_line_layer(gdf, w_px, h_px, minx, maxx, miny, maxy,
                      town_px, outer_px, dpi, threshold):
    """matplotlib 繪區面+區界+縣市界 → 二值化 → 純黑線層。

    區界畫 town_px px；縣市界（各縣市聯集的邊界，含海岸線）與全體外輪廓
    畫 outer_px px——縣市交界以較粗線清楚分隔。"""
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    px2pt = 72.0 / dpi
    town_lw = town_px * px2pt
    outer_lw = outer_px * px2pt
    gdf.plot(ax=ax, edgecolor="black", facecolor="white", linewidth=town_lw)
    gdf.geometry.boundary.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=town_lw)
    # 縣市界：各縣市自身聯集的邊界（含海岸線）
    for cname, sub in gdf.groupby("COUNTYNAME"):
        cbd = unary_union(sub.geometry).boundary
        gpd.GeoSeries([cbd]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    # 全體外輪廓（海岸線）
    outer = unary_union(gdf.geometry).boundary
    gpd.GeoSeries([outer]).plot(ax=ax, edgecolor="black", facecolor="none", linewidth=outer_lw)
    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, pad_inches=0, bbox_inches=None, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, tmask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    del gray
    return tmask > 0


def flood_fill_layer(*a, **k):
    """油漆桶式填色（共用實作：Draw_National_President_2020.flood_fill_layer）。"""
    return nat.flood_fill_layer(*a, **k)


def check_region_single_color(*a, **k):
    """油漆桶不變式自檢（共用實作）。"""
    return nat.check_region_single_color(*a, **k)


def full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy):
    return nat.full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy)


if __name__ == "__main__":
    main()
