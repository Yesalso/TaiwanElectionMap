# -*- coding: utf-8 -*-
"""生成 2000 版四區域繪圖腳本（桃竹苗／雲嘉南／高屏／中彰投）。

以 Draw_North4_President_2000.py 的繪圖管線（自「圖資清理」段落以下）為共用尾段，
只換底圖讀取（JSON）、得票資料（2000）、縣市清單、縣市名對照與輸出檔名。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Draw_North4_President_2000.py")
src = open(SRC, encoding="utf-8").read()
TAIL = src[src.index("# ===================== 圖資清理 ====================="):]
assert TAIL.startswith("# ===================== 圖資清理")

REGIONS = [
    dict(
        code="TCM4", region="桃竹苗",
        doc_title="桃竹苗四縣市（桃園縣・新竹縣・新竹市・苗栗縣）",
        target='["桃園縣", "新竹縣", "新竹市", "苗栗縣"]',
        alias='{}   # 桃園 2012 圖資仍作「桃園縣」，與 2000 相同，故無需對照',
        alias_note="本區 2000 與 2012 圖資縣市名一致（皆為桃園縣、新竹縣、新竹市、苗栗縣），故 COUNTY_ALIAS 為空。",
        drop_nan='[]',
        drop_nan_note="              # 2012 圖資桃竹苗四縣市無「無村里名」圖斑",
        out_png="桃竹苗2000年總統副總統選舉_得票率地圖.png",
        miss_md="桃竹苗2000_無資料與未匹配村里.md",
        layer="layer_tcm4_2000_district_2px.png",
        bbox="桃竹苗 bbox 約 86.9 × 92.5 km（新竹香山～桃園復興、桃園蘆竹～苗栗卓蘭）",
        drop_hint="（本區 2012 圖資無此類圖斑）",
        base="json",
    ),
    dict(
        code="YCT4", region="雲嘉南",
        doc_title="雲嘉南四縣市（雲林縣・嘉義縣・嘉義市・臺南市）",
        target='["雲林縣", "嘉義縣", "嘉義市", "臺南市"]',
        alias='{"臺南縣": "臺南市"}   # 2000 臺南縣 → 2012 直轄市臺南市（2010 縣市合併）',
        alias_note="2010 年臺南縣併入臺南市（直轄市），2000 舊名「臺南縣」對 2012 圖資「臺南市」；\n#   原省轄臺南市亦屬 2012「臺南市」，兩者鄉鎮市區名不重疊，故合併後無衝突。",
        drop_nan='[]',
        drop_nan_note="              # 2012 圖資雲嘉南四縣市無「無村里名」圖斑（臺南市亦無）",
        out_png="雲嘉南2000年總統副總統選舉_得票率地圖.png",
        miss_md="雲嘉南2000_無資料與未匹配村里.md",
        layer="layer_yct4_2000_district_2px.png",
        bbox="雲嘉南 bbox 約 98 × 109 km（雲林臺西～臺南龍崎、雲林麥寮～臺南官田）",
        drop_hint="（本區 2012 圖資無此類圖斑）",
        base="json",
    ),
    dict(
        code="South2", region="高屏",
        doc_title="南臺兩縣市（高雄市・屏東縣）",
        target='["高雄市", "屏東縣"]',
        alias='{"高雄縣": "高雄市"}   # 2000 高雄縣 → 2012 直轄市高雄市（2010 縣市合併）',
        alias_note="2010 年高雄縣併入高雄市（直轄市），2000 舊名「高雄縣」對 2012 圖資「高雄市」；\n#   原直轄高雄市之 11 區亦屬 2012「高雄市」，鄉鎮市區名不與原高雄縣各鄉鎮市重疊。",
        drop_nan='["高雄市"]',
        drop_nan_note="    # 高雄市港區/航道水域（前鎮/小港/旗津/鼓山之無村里名圖斑）整筆不畫",
        out_png="高屏2000年總統副總統選舉_得票率地圖.png",
        miss_md="高屏2000_無資料與未匹配村里.md",
        layer="layer_south2_2000_district_2px.png",
        bbox="高屏 bbox 約 90 × 175 km（高雄梓官～屏東鵝鑾鼻、高雄那瑪夏～小琉球）",
        drop_hint="高雄市港區/航道水域（前鎮、小港、旗津、鼓山之無村里名圖斑）",
        base="json",
    ),
    dict(
        code="TCN3", region="中彰投",
        doc_title="中部三縣市（臺中市・彰化縣・南投縣）",
        target='["臺中市", "彰化縣", "南投縣"]',
        alias='{"臺中縣": "臺中市"}   # 2000 臺中縣 → 2012 直轄市臺中市（2010 縣市合併）',
        alias_note="2010 年臺中縣併入臺中市（直轄市），2000 舊名「臺中縣」對 2012 圖資「臺中市」；\n#   原省轄臺中市亦屬 2012「臺中市」，兩者鄉鎮市區名不重疊，故合併後無衝突。",
        drop_nan='[]',
        drop_nan_note="              # 2012 圖資中彰投三縣市無「無村里名」圖斑（臺中港區水域亦已無）",
        out_png="中彰投2000年總統副總統選舉_得票率地圖.png",
        miss_md="中彰投2000_無資料與未匹配村里.md",
        layer="layer_tcn3_2000_district_2px.png",
        bbox="中彰投 bbox 約 125 × 112 km（彰化沿海～南投東境、臺中清水～南投竹山）",
        drop_hint="（本區 2012 圖資無此類圖斑）",
        base="json_shp",
    ),
    dict(
        code="TaichungCity", region="臺中市（舊市區）",
        doc_title="臺中市（省轄市・舊市區 8 區）",
        target='["臺中市"]',
        alias='{}   # 2000 省轄臺中市 → 同為「臺中市」；不設臺中縣對照，避免把臺中縣村里併入本圖',
        alias_note="本圖只做 2000 年臺中市（省轄市）轄域，故不設縣市名對照；\n#   2000 資料的「臺中縣」不會被併入（否則縣轄 372 里會全成反向缺漏）。",
        drop_nan='[]',
        drop_nan_note="              # 民國85年臺中市 SHP 無「無村里名」圖斑",
        out_png="臺中市2000年總統副總統選舉_得票率地圖.png",
        miss_md="臺中市2000_無資料與未匹配村里.md",
        layer="layer_taichungcity_2000_district_2px.png",
        bbox="臺中舊市區 bbox 約 23.3 × 12.6 km（橫長形）→ 1px≈3.64m 得約 6540 × 3540 px",
        drop_hint="（本圖資無此類圖斑）",
        base="shp",
    ),
]

HEADER = '''# -*- coding: utf-8 -*-
"""
<<<DOC_TITLE>>>
2000 第十屆總統副總統選舉 各村（里）得票領先候選人得票比例圖

資料來源：2000Precident/data/2000總統副總統選舉_得票率.xlsx（工作表「各里彙總」）
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 |
    連戰得票率 | 陳水扁得票率 | 宋楚瑜得票率
    → 2000 第十屆候選人（號次）：宋楚瑜(01) → 連戰(02) → 李敖(03) → 許信良(04) → 陳水扁(05)
      本圖只取三強（連戰／陳水扁／宋楚瑜）；色階（順序與 CAND_NAMES 一致，由使用者指定）：
      連戰＝中國國民黨→藍、陳水扁＝民主進步黨→綠、宋楚瑜→灰
      故本檔自帶 RATE_COLOR_STOPS（3 組），不沿用 2020 版的三組色表。

<<<BASEMAP_DOC>>>

行政區對照：<<<ALIAS_SUMMARY>>>

繪圖邏輯沿用 Draw_North4_President_2000.py（＝ 2016 版系），只換底圖（<<<BASE_KIND>>>）與得票資料（2000）：

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
<<<BASEMAP_DIFF_DOC>>>
  - 得票資料：2000 各里彙總（3 位候選人：連戰／陳水扁／宋楚瑜）；縣市名對照見 COUNTY_ALIAS。
<<<SCALE_LINE_DOC>>>
  - 新增③ 缺資料回報：地圖上有圖斑卻對不上得票資料者，另寫 Markdown 表格（MISSING_MD）。

<<<NAME_ALIGN_DOC>>>

<<<SCALE_DOC>>>
輸出：2000Precident/maps/<<<OUT_PNG>>>
     2000Precident/maps/<<<MISS_MD>>>
執行：py Draw_<<<CODE>>>_President_2000.py
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
# 2000 第十屆總統副總統選舉候選人（號次 01~05）：宋楚瑜(01,無黨籍)、連戰(02,中國國民黨)、
#   李敖(03,新黨)、許信良(04,無黨籍)、陳水扁(05,民主進步黨)；本圖只取三強（連戰／陳水扁／宋楚瑜）。
#   順序＝ RATE_COLOR_STOPS 順序（連戰→藍、陳水扁→綠、宋楚瑜→灰），非 Excel 欄位順序。
CAND_NAMES = ["連戰", "陳水扁", "宋楚瑜"]
CAND_RATE_COLS = [f"{n}得票率" for n in CAND_NAMES]

# 2000 候選人色階（順序與 CAND_NAMES 一致；由使用者指定）：
#   連戰＝中國國民黨→藍、陳水扁＝民主進步黨→綠、宋楚瑜→灰
RATE_COLOR_STOPS = [
    [(35, "#A6E9FF"), (40, "#73D9FF"), (45, "#40C8FF"), (50, "#00C0F4"),
     (55, "#00A2E8"), (60, "#0080B8"), (65, "#006591"), (70, "#004B6B"),
     (75, "#003247"), (80, "#00283A"), (85, "#001F2E"), (100, "#010D29")],
    [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
     (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
     (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
    [(35, "#D9D9D9"), (40, "#C9C9C9"), (45, "#B6B6B6"), (50, "#A0A0A0"),
     (55, "#898989"), (60, "#727272"), (65, "#5B5B5B"), (70, "#464646"),
     (75, "#333333"), (80, "#232323"), (85, "#151515")],
]

# 2000 舊行政區名 → twvillage2012.json 縣市名（2010 五都升格之縣市合併）
#   <<<ALIAS_NOTE>>>
COUNTY_ALIAS = <<<ALIAS>>>

# 2000 各里得票率 Excel（工作表「各里彙總」）
VOTE_XLSX = os.path.join(os.path.dirname(SCRIPT_DIR), "data",
                         "2000總統副總統選舉_得票率.xlsx")

<<<BASEMAP_CONFIG>>>
OUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "maps")
OUT_PNG = os.path.join(OUT_DIR, "<<<OUT_PNG>>>")
MISSING_MD = os.path.join(OUT_DIR, "<<<MISS_MD>>>")   # ③ 缺資料回報
layer_name = "<<<LAYER>>>"   # ② 層單獨輸出（核對用）
TARGET_COUNTIES = <<<TARGET>>>
TARGET_CRS = "EPSG:3826"

TITLE_LINES = []          # 不畫標題（亦不畫圖例，直接輸出純地圖）

<<<SCALE_CONFIG_HEAD>>>
# <<<BBOX>>>
<<<MAXPX_NOTE>>>
<<<MPP_LINE>>>
MAX_PX = 12000
<<<SCALE_UP_LINE>>>
PAD_FRAC = 0.01

SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（沿用 DrawTaichungCity.py：簡化會把緩彎拉直）

LINE_VILLAGE_PX = 1      # ① 村里界
LINE_TOWNSHIP_PX = 3     # ② 區界線寬(px)
LINE_OUTER_PX = 5        # ② 縣市界/海岸線線寬(px)
THRESHOLD_VAL = 40       # ② 二值化閾值
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為 dissolve 雜訊，填平
# 無村里名(VILLNAME 空)的圖斑：這些縣市整筆不畫
<<<DROP_NAN_NOTE>>>
DROP_NAN_COUNTIES = <<<DROP_NAN>>>
REMOTE_MAX_DIST_M = 2000.0   # 無村里名者：與本島相距超過此值 → 不畫（外海無編制離島）
NAMED_MAX_DIST_M = 20000.0   # 有村里名者：超過此值才視為圖資錯誤碎塊並剔除
# 門檻沿用 2016 版；2012 圖資本區實測依 ② 層連通分量自檢期待值動態決定（EXPECT_CC）。
SAVE_LAYER = False
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)


'''

FUNCS = '''
# ----------------------① 讀底圖 + 讀得票率 + 匹配填色----------------------
def _norm_vill(s):
    """村里名正規化（比對用）：共用 normalize + 去「村/里」尾綴，再套 2000 異體字收斂。

    nr.VARIANT_CHAR_MAP_2000 讓底圖修補後的正名與 2000 資料用字收斂到同一形。
    """
    return nat.strip_village_suffix(s).translate(nr.VARIANT_CHAR_MAP_2000)


def load_vote_data(vote_xlsx=VOTE_XLSX):
    """讀取 2000 各里得票率 Excel（工作表「各里彙總」）。

    欄位：選舉區別 | 鄉(鎮、市、區)別 | 村里別 |
          連戰得票率 | 陳水扁得票率 | 宋楚瑜得票率
    得票率依 CAND_NAMES（= CAND_RATE_COLS）順序擷取為 tuple（字尾 % 移除），
    回傳 (by_key, by_town, n_rows, n_total)，供 nat.fuzzy_lookup 使用。
    縣市名先套 COUNTY_ALIAS 以與 2012 底圖對齊。
    源資料若將多村里併為一列（以 、 分隔），拆解成各村(里)並共用同一組得票率。
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
        county = COUNTY_ALIAS.get(county, county)   # 2000 舊名 → 2012 圖資名
        town = nat.strip_town_suffix(r.get("鄉(鎮、市、區)別"))
        vill_raw = nat.normalize_text(r.get("村里別"))
        if not county or not town or not vill_raw:
            continue
        try:
            vals = tuple(float(str(r[c]).strip().replace("%", "").replace("\\u00a0", ""))
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
            key = (county, town, part_core)
            if key in by_key:
                continue
            by_key[key] = vals
            by_town.setdefault((county, town), []).append((part_core, vals))
            n_rows += 1
    return by_key, by_town, n_rows, n_total


<<<BASEMAP_FUNCS>>>
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
    L.append(f"# <<<REGION>>> 2000 總統副總統選舉 得票率地圖 — 匹配稽核")
    L.append("（無資料／未匹配／村名修補）")
    L.append("")
    L.append(f"- 產生時間：{ts}")
    L.append(f"- 底圖：<<<BASE_LABEL>>> → <<<REGION>>> {len(gdf_all)} 個村里圖斑")
    L.append(f"- 得票資料：`2000總統副總統選舉_得票率.xlsx`（工作表「各里彙總」，全國 {len(vote_dict)} 筆村里）")
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

    L.append(f"## 4. 底圖村名修補（<<<BASE_SRC_LABEL>>> 罕見字還原；{len(repair_df)} 筆）")
    L.append("")
    L.append("> JSON 以私用區(PUA)碼位或「■」代替罕見字，先還原成正字再與 2000 資料比對。")
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
<<<LINEAGE_NOTE>>>
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
        f.write("\\n".join(L) + "\\n")
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
    print("  <<<REGION>>> 2000 總統副總統選舉 各村（里）得票率地圖")
    print("=" * 62)

    gdf_all = load_base_map(<<<BASE_PATH>>>)
<<<BASEMAP_APPLY>>>    gdf_all = repair_base_names(gdf_all)

    # 指定縣市的「無村里名」圖斑整筆不畫 <<<DROP_HINT>>>
    if DROP_NAN_COUNTIES:
        _vv = gdf_all["VILLNAME"].fillna("").astype(str).str.strip()
        _drop = gdf_all["COUNTYNAME"].isin(DROP_NAN_COUNTIES) & _vv.isin(["", "nan", "None"])
        if _m := int(_drop.sum()):
            print(f"  無村里名不畫（{ '、'.join(DROP_NAN_COUNTIES) }）：剔除 {_m} 筆")
            gdf_all = gdf_all[~_drop].copy().reset_index(drop=True)

    # 遠離本島的圖斑處理：無村里名者超 2km 剔除；有村里名者超 20km 才剔除
    gdf_all = strip_far_parts(gdf_all)

    # 得票率（2000 各里彙總 Excel，異體字/模糊匹配沿用全臺腳本）
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
    print(f"  <<<ELEM_LABEL>>> 要素數      : {len(gdf_all)}")
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
    print(f"\\n  Saved: {OUT_PNG}  ({W}×{H}px)")
    print("==== All finished ====")


'''

# ===================== 底圖模式（三種） =====================
#   json     ：只讀 twvillage2012.json（桃竹苗／雲嘉南／高屏）
#   json_shp ：twvillage2012.json ＋ 用民國85年臺中市（省轄市）區里界 SHP 取代 8 個舊市區（中彰投）
#   shp      ：只讀民國85年臺中市（省轄市）區里界 SHP（臺中舊市區單圖）
_CITY_SHP_WIN = ("D:\\Windows\\Documents\\村里界歷史圖資_111\\"
                 "臺中市85年區里界_UTF8\\臺中市85年區里界_UTF8\\區里界_region.shp")
_MAP_JSON_LINE = 'MAP_JSON = r"D:\\Windows\\TaiwanElection\\Base_JSON\\twvillage2012.json"'

# 民國85年臺中市 SHP 的村里用字與 2000 得票資料不一致者（逐筆指定）
#   北屯區 SHP 作「廓子里」、2000 得票資料作「部子里」（皆為「廍子」之異寫）：
#   北屯區 SHP 31 里中唯此里對不上，且資料側同區唯一缺漏即「部子」，一對一（消去法）確認。
#   不對齊則地圖留白 1 筆、報告多 1 筆反向缺漏。
_SHP_REPAIR_CFG = '''# 底圖 SHP 用字 → 2000 得票資料用字（逐筆指定；多筆歧義者以同鄉鎮消去法確認）
SHP_NAME_REPAIR = {("北屯區", "廓子里"): "部子里"}'''

_SHP_REPAIR_FUNC = '''

def _repair_shp_names(df):
    """把 SHP 村里名套用 SHP_NAME_REPAIR（SHP 用字 → 2000 得票資料用字）。"""
    if not SHP_NAME_REPAIR:
        return df
    t = df["TOWNNAME"].astype(str).str.strip()
    v = df["VILLNAME"].astype(str).str.strip()
    nv = [SHP_NAME_REPAIR.get((a, b), b) for a, b in zip(t, v)]
    n = sum(1 for a, b in zip(v, nv) if a != b)
    if n:
        print(f"  SHP 村名對齊 2000 用字（SHP_NAME_REPAIR）：{n} 筆")
    out = df.copy()
    out["VILLNAME"] = nv
    return out
'''

# ---------- json：原文（須與改造前逐字元相同，其餘三區重生成才不會有差異） ----------
BASEMAP_DOC_JSON = '''底圖來源：Base_JSON/twvillage2012.json（民國101年村里界，**取代原本的 107 版 SHP 圖源**）
    欄位 county / town / village（小寫）→ 讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME
    （見 load_base_map；欄位正規化與 EPSG:4326→EPSG:3826 的做法同
      Base_JSON/draw_json_map.py 與 draw_county_maps.py）。'''

BASEMAP_DIFF_DOC_JSON = '''  - 底圖：twvillage2012.json（民國101年村里界）。108/107 版 SHP 的離島與「無村里名」
    圖斑處置（strip_far_parts / DROP_NAN_COUNTIES）於本底圖依實測重新設定。'''

BASEMAP_CONFIG_JSON = '''# 底圖：民國101年村里界 twvillage2012.json（取代原本的 SHP 圖源）
# 欄位為 county / town / village（小寫），讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME；
# 檔案無內建 CRS → 視為 EPSG:4326，再投影至 EPSG:3826
# （欄位正規化與 EPSG:4326→3826 的做法同 Base_JSON/draw_json_map.py、draw_county_maps.py）
''' + _MAP_JSON_LINE

BASEMAP_FUNCS_JSON = '''def load_base_map(path=MAP_JSON):
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

'''

# ---------- json_shp：JSON ＋ 民國85年臺中市 SHP（中彰投用） ----------
BASEMAP_DOC_JSONSHP = '''底圖來源：Base_JSON/twvillage2012.json（民國101年村里界）
    ＋ **民國85年臺中市（省轄市）區里界 SHP**（僅含當時臺中市轄 8 區、224 個里圖斑）
    民國85年（1996）臺中市為省轄市（中區、東區、西區、南區、北區、西屯區、南屯區、北屯區），
    尚未與臺中縣合併；2012 圖資「臺中市」已是大臺中 29 區，且舊市區里界經多次重編
    （8 區僅 214 里）→ 故這 8 區改用 2000 當時的村里界 SHP，其餘（臺中縣 21 鄉鎮市、
    彰化縣、南投縣）仍用 JSON，確保與 2000 各里得票資料逐里對齊。
    欄位 county / town / village（小寫）→ 讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME；
    SHP 欄位為 區名 / 里名 → TOWNNAME / VILLNAME（見 load_base_map、_apply_city_shp）。'''

BASEMAP_DIFF_DOC_JSONSHP = '''  - 底圖：twvillage2012.json（民國101年村里界）＋ 民國85年臺中市（省轄市 8 區）區里界 SHP。
    108/107 版 SHP 的離島與「無村里名」圖斑處置（strip_far_parts / DROP_NAN_COUNTIES）
    於本底圖依實測重新設定。'''

BASEMAP_CONFIG_JSONSHP = '''# 底圖：民國101年村里界 twvillage2012.json ＋ 民國85年臺中市（省轄市）區里界 SHP
#   —— 2000 年臺中市為省轄市（僅中/東/西/南/北/西屯/南屯/北屯 8 區、224 個里圖斑），
#   尚未與臺中縣合併；故這 8 區沿用「民國85年（1996）當時」的村里界 SHP（底圖與 1996 版完全相同），其餘仍用 JSON。
# 欄位為 county / town / village（小寫），讀入時正規化為 COUNTYNAME / TOWNNAME / VILLNAME；
# 檔案無內建 CRS → 視為 EPSG:4326，再投影至 EPSG:3826
# （欄位正規化與 EPSG:4326→3826 的做法同 Base_JSON/draw_json_map.py、draw_county_maps.py）
''' + _MAP_JSON_LINE + '''

# 舊臺中市（省轄市）民國85年區里界 SHP：取代 JSON 的 8 個舊市區圖斑
#   源 prj 為 Hu_Tzu_Shan（TWD67）TM2（k=0.9999、FE=250000、cm=121）；
#   to_crs(EPSG:3826) 後與 JSON 舊市區重合 92~98%（實測）；外緣餘差由 _apply_city_shp
#   做無縫對齊（縣側 -= S_city、市側併回 JSON 殘留），避免區界重疊雙線、填色錯亂。
CITY_SHP = r"''' + _CITY_SHP_WIN + '''"
CITY_SHP_ENCODING = "UTF-8"
CITY_SHP_COUNTY = "臺中市"       # SHP 所屬縣市名（民國85年省轄臺中市）
CITY_SHP_TOWN_COL = "區名"       # SHP 鄉鎮市區欄
CITY_SHP_VILL_COL = "里名"       # SHP 村里欄
''' + _SHP_REPAIR_CFG

BASEMAP_FUNCS_JSONSHP = BASEMAP_FUNCS_JSON + '''def _apply_city_shp(gdf, shp_path=CITY_SHP):
    """以民國85年臺中市（省轄市）區里界 SHP 取代 JSON 的 8 個舊市區圖斑。

    民國85年（1996）臺中市為省轄市（8 區、224 個里圖斑）；2012 圖資「臺中市」已是縣市合併後的大臺中
    （29 區，舊市區 8 區僅 214 里），里界經多次重編 → 用 2000 當時的村里界 SHP 才能與
    2000 各里得票資料逐里對齊。

    兩份圖資的舊市區外緣互有出入（實測：SHP 舊市區 ∩ JSON 臺中縣 = 2.52 km²；
    JSON 舊市區未被 SHP 涵蓋 = 1.10 km²）。若直接併用，區界會被畫成重疊的雙線、填色
    錯亂，故做無縫對齊（S_city ＝ SHP 8 區聯集）：
      - 縣側（JSON 臺中縣各鄉鎮市區）：geometry -= S_city
      - 市側（SHP 各里）：geometry ＝ SHP 里 ∪ (JSON 同區殘留 - S_city)
    → 市側合計 ＝ S_city ∪ (JSON 舊市區 - S_city)，與縣側零重疊且完整覆蓋。
    """
    shp = gpd.read_file(shp_path, encoding=CITY_SHP_ENCODING)
    if shp.crs is None:
        shp.crs = TARGET_CRS
    shp = shp.to_crs(TARGET_CRS)
    lack = [c for c in (CITY_SHP_TOWN_COL, CITY_SHP_VILL_COL) if c not in shp.columns]
    if lack:
        raise ValueError(f"{os.path.basename(shp_path)} 缺少欄位：{'、'.join(lack)}"
                         f"（現有：{shp.columns.tolist()}）")
    city = shp.rename(columns={CITY_SHP_TOWN_COL: "TOWNNAME",
                               CITY_SHP_VILL_COL: "VILLNAME"})
    city = city[["TOWNNAME", "VILLNAME", "geometry"]].copy()
    city["COUNTYNAME"] = CITY_SHP_COUNTY
    city["geometry"] = city.geometry.buffer(0)
    city["TOWNNAME"] = city["TOWNNAME"].astype(str).str.strip()
    city["VILLNAME"] = city["VILLNAME"].astype(str).str.strip()
    city = city[~city.geometry.isna() & ~city.geometry.is_empty].copy()
    city = city.reset_index(drop=True)
    if not len(city):
        print("  SHP 底圖置換：SHP 無有效要素，維持 JSON 底圖")
        return gdf
    city = _repair_shp_names(city)          # SHP 用字 → 2000 得票資料用字

    dists = set(city["TOWNNAME"])
    S = unary_union(city.geometry.tolist())
    is_city = gdf["COUNTYNAME"].eq(CITY_SHP_COUNTY) & gdf["TOWNNAME"].isin(dists)
    json_city = gdf[is_city].copy()
    county = gdf[~is_city].copy()

    # ① 縣側：扣掉舊市區整體，避免與 SHP 重疊
    county["geometry"] = county.geometry.difference(S)
    county = county[~county.geometry.isna() & ~county.geometry.is_empty].copy()

    # ② 市側：JSON 各區殘留（該區各里聯集 - S_city）逐塊併回「最靠近的」SHP 里，
    #    補齊 JSON 舊市區未被 SHP 涵蓋處。同一塊殘留只能併入一個里，否則里與里會大量重疊。
    json_by_dist = {}
    for _t, _g in zip(json_city["TOWNNAME"], json_city["geometry"]):
        json_by_dist.setdefault(_t, []).append(_g)
    _towns = list(city["TOWNNAME"])
    _geoms = list(city["geometry"])
    _n_patch = 0
    for _d, _gl in json_by_dist.items():
        _rows = [k for k, _tt in enumerate(_towns) if _tt == _d]
        if not _rows:
            continue
        _L = unary_union(_gl).difference(S)
        if _L.is_empty:
            continue
        for _c in (list(_L.geoms) if hasattr(_L, "geoms") else [_L]):
            _k = _rows[int(np.argmin([_geoms[r].distance(_c) for r in _rows]))]
            _geoms[_k] = _geoms[_k].union(_c)
            _n_patch += 1
    city["geometry"] = _geoms

    out = pd.concat([county, city], ignore_index=True)
    out = out[~out.geometry.isna() & ~out.geometry.is_empty].copy().reset_index(drop=True)
    print(f"  SHP 底圖置換：{CITY_SHP_COUNTY} 舊市區 {len(dists)} 區 {len(city)} 里改用"
          f"民國85年區里界 SHP（原 JSON {len(json_city)} 筆）")
    print(f"    S_city {S.area / 1e6:.2f} km²、JSON 殘留補丁 {_n_patch} 塊；"
          f"縣側扣除 S_city、市側殘留各併入單一里，接縫無重疊／無破洞")
    return out

''' + _SHP_REPAIR_FUNC

# ---------- shp：只用民國85年臺中市 SHP（舊市區單圖） ----------
BASEMAP_DOC_SHP = '''底圖來源：民國85年臺中市（省轄市）區里界 SHP（**沿用 1996 版底圖**，依需求與 1996 版完全相同）
    ''' + _CITY_SHP_WIN.replace("\\", "\\\\") + '''
    內容為民國85年（1996）臺中市（省轄市）轄域：中區、東區、西區、南區、北區、西屯區、南屯區、
    北屯區 共 8 區、224 個里圖斑 —— **不含臺中縣**（民國85年臺中縣為獨立縣，2010 年才併入臺中市）。
    欄位 區名 / 里名 → 讀入時正規化為 TOWNNAME / VILLNAME，COUNTYNAME 固定為「臺中市」。
    坐標：源 prj 為 Hu_Tzu_Shan（TWD67）TM2（k=0.9999、FE=250000、cm=121）；
    以 to_crs(EPSG:3826) 轉為 TWD97/TM2（實測與 twvillage2012.json 舊市區重合 92~98%）。'''

BASEMAP_DIFF_DOC_SHP = '''  - 底圖：民國85年臺中市（省轄市）區里界 SHP（8 區、224 個里圖斑），**不用 twvillage2012.json**
    ——後者已是縣市合併後的大臺中，且舊市區里界為 2012 年（8 區僅 214 里）。'''

BASEMAP_CONFIG_SHP = '''# 底圖：民國85年臺中市（省轄市）區里界 SHP（沿用 1996 版，依需求與 1996 版完全相同）
#   —— 民國85年（1996）臺中市為省轄市（僅中/東/西/南/北/西屯/南屯/北屯 8 區、224 個里圖斑），
#   未與臺中縣合併，故直接沿用民國85年（1996）當時的村里界 SHP（不用 twvillage2012.json；底圖與 1996 版完全相同）。
#   欄位 區名 / 里名 → TOWNNAME / VILLNAME；COUNTYNAME 固定為 BASE_SHP_COUNTY。
#   坐標：源 prj 為 Hu_Tzu_Shan（TWD67）TM2（k=0.9999、FE=250000、cm=121）
#   → to_crs(EPSG:3826)（TWD97/TM2；實測與 twvillage2012.json 舊市區重合 92~98%）。
BASE_SHP = r"''' + _CITY_SHP_WIN + '''"
BASE_SHP_ENCODING = "UTF-8"
BASE_SHP_COUNTY = "臺中市"       # SHP 所屬縣市名（民國85年省轄臺中市）
BASE_SHP_TOWN_COL = "區名"       # SHP 鄉鎮市區欄
BASE_SHP_VILL_COL = "里名"       # SHP 村里欄
''' + _SHP_REPAIR_CFG

BASEMAP_FUNCS_SHP = '''def load_base_map(path=BASE_SHP):
    """讀入民國85年臺中市（省轄市）區里界 SHP，正規化欄位後回傳 GeoDataFrame。

    此 SHP 內容為民國85年（1996）臺中市（省轄市）轄域：中區、東區、西區、南區、北區、西屯區、
    南屯區、北屯區 共 8 區、224 個里圖斑 —— **不含臺中縣**（民國85年臺中縣為獨立縣）。
    欄位 區名 / 里名 → TOWNNAME / VILLNAME；COUNTYNAME 固定為 BASE_SHP_COUNTY。
    坐標：源 prj 為 Hu_Tzu_Shan（TWD67）TM2（k=0.9999、FE=250000、cm=121）；
    以 to_crs(EPSG:3826) 轉為 TWD97/TM2（實測與 twvillage2012.json 舊市區重合 92~98%）。
    """
    gdf = gpd.read_file(path, encoding=BASE_SHP_ENCODING)
    if gdf.crs is None:
        gdf.crs = TARGET_CRS
    gdf = gdf.to_crs(TARGET_CRS)
    lack = [c for c in (BASE_SHP_TOWN_COL, BASE_SHP_VILL_COL) if c not in gdf.columns]
    if lack:
        raise ValueError(f"{os.path.basename(path)} 缺少欄位：{'、'.join(lack)}"
                         f"（現有：{gdf.columns.tolist()}）")
    gdf = gdf.rename(columns={BASE_SHP_TOWN_COL: "TOWNNAME",
                              BASE_SHP_VILL_COL: "VILLNAME"})
    gdf["COUNTYNAME"] = BASE_SHP_COUNTY
    gdf = gdf[["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry"]].copy()
    gdf["COUNTYNAME"] = gdf["COUNTYNAME"].astype(str).str.strip()
    gdf["TOWNNAME"] = gdf["TOWNNAME"].astype(str).str.strip()
    gdf["VILLNAME"] = gdf["VILLNAME"].astype(str).str.strip()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[~gdf["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf = gdf[gdf["COUNTYNAME"].isin(TARGET_COUNTIES)].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf.reset_index(drop=True)
    gdf = _repair_shp_names(gdf)            # SHP 用字 → 2000 得票資料用字
    print(f"底圖：民國85年{BASE_SHP_COUNTY}（省轄市）區里界 SHP —— "
          f"{gdf['TOWNNAME'].nunique()} 區、{len(gdf)} 里")
    return gdf

''' + _SHP_REPAIR_FUNC

BASEMAP_SCALE_DOC = {
    "json": "比例尺：1px = 20m",
    "json_shp": "比例尺：1px = 20m",
    "shp": "比例尺：1px ≈ 3.64m（1px=4m 再放大 10%）——舊市區村里細碎，需高解析度才看得出各里顏色",
}
BASEMAP_SCALE_HEAD = {
    "json": "# 比例尺：1px = 20m（不再額外放大）",
    "json_shp": "# 比例尺：1px = 20m（不再額外放大）",
    "shp": "# 比例尺：1px = 4m，再放大 10%（舊市區村里細碎，需高解析度）",
}
BASEMAP_MAXPX_NOTE = {
    "json": "# 1px=20m 後地圖長寬皆 < MAX_PX",
    "json_shp": "# 1px=20m 後地圖長寬皆 < MAX_PX",
    "shp": "# 1px≈3.64m 後地圖長寬皆 < MAX_PX",
}
BASEMAP_MPP = {"json": "METERS_PER_PIXEL = 20.0",
               "json_shp": "METERS_PER_PIXEL = 20.0",
               "shp": "METERS_PER_PIXEL = 4.0"}
BASEMAP_SCALEUP = {"json": "SCALE_UP = 1.0",
                   "json_shp": "SCALE_UP = 1.0",
                   "shp": "SCALE_UP = 1.10"}
BASEMAP_BASE_PATH = {"json": "MAP_JSON", "json_shp": "MAP_JSON", "shp": "BASE_SHP"}
BASEMAP_APPLY = {"json": "", "json_shp": "    gdf_all = _apply_city_shp(gdf_all)\n", "shp": ""}
BASEMAP_ELEM_LABEL = {"json": "JSON", "json_shp": "底圖", "shp": "SHP"}
BASEMAP_BASE_LABEL = {
    "json": "`twvillage2012.json`（民國101年村里界）",
    "json_shp": "`twvillage2012.json`（民國101年村里界）＋ 民國85年臺中市（省轄市 8 區）區里界 SHP",
    "shp": "民國85年臺中市（省轄市）區里界 SHP",
}
BASEMAP_BASE_SRC_LABEL = {
    "json": "twvillage2012.json", "json_shp": "twvillage2012.json",
    "shp": "民國85年臺中市區里界 SHP",
}
BASEMAP_LINEAGE_NOTE = {
    "json": '''    L.append("> 本地區無村里沿革對照表（沿革表目前僅新北市，見 `village_lineage_north4.py`），")
    L.append("> 故不套用沿革合併；2012 圖資有、2000 未設立的里若對不上資料，一律留白並記入第 1 節。")''',
    "json_shp": '''    L.append("> 本地區無村里沿革對照表（沿革表目前僅新北市，見 `village_lineage_north4.py`），")
    L.append("> 故不套用沿革合併；2012 圖資有、2000 未設立的里若對不上資料，一律留白並記入第 1 節。")
    L.append("> 惟臺中舊市區 8 區已改用 2000 當時的村里界 SHP，故該區無『2012 新設里』之留白。")''',
    "shp": '''    L.append("> 本圖直接沿用民國85年（1996）當時的村里界 SHP（臺中市 8 區、224 個里圖斑；底圖與 1996 版完全相同），")
    L.append("> 無 2012 圖資新設里之問題；SHP 有、2000 得票資料無者一律留白並記入第 1 節。")''',
}
BASEMAP_BASE_KIND = {"json": "JSON", "json_shp": "JSON＋SHP", "shp": "SHP"}
BASEMAP_SCALE_LINE_DOC = {
    "json": '''  - 縣市 / 區層 dissolve（鍵 = COUNTYNAME, TOWNNAME）/ 線寬（村里 1px、區 3px、
    縣市界 5px）/ 比例尺 1px=20m / 不畫標題不畫圖例 —— 均與 2016 版相同。''',
    "json_shp": '''  - 縣市 / 區層 dissolve（鍵 = COUNTYNAME, TOWNNAME）/ 線寬（村里 1px、區 3px、
    縣市界 5px）/ 比例尺 1px=20m / 不畫標題不畫圖例 —— 均與 2016 版相同。''',
    "shp": '''  - 縣市 / 區層 dissolve（鍵 = COUNTYNAME, TOWNNAME）/ 線寬（村里 1px、區 3px、
    市界 5px）/ 比例尺 1px≈3.64m / 不畫標題不畫圖例 —— 與 2016 版僅差底圖與比例尺。''',
}
_NAME_ALIGN_JSON = '''底圖 × 2000 村里名對齊（參考 `README.md` §5 與 village_name_repair.py）：
  - 村名修補：twvillage2012.json 以私用區(PUA)碼位或「■」代替罕見字，先還原成正字再比對
    （PUA 碼位可全域對應；「■」一字多義，逐一指定，多筆歧義者以同鄉鎮其餘村里的消去法確認）。
    見 village_name_repair.repair_json_vill_name。
  - 本區無村里沿革對照表（沿革表目前僅新北市），故不套用沿革合併；
    2012 圖資有、2000 未設立的里若對不上資料，一律留白並記入報告。'''
BASEMAP_NAME_ALIGN_DOC = {
    "json": _NAME_ALIGN_JSON,
    "json_shp": _NAME_ALIGN_JSON.replace(
        "    見 village_name_repair.repair_json_vill_name。",
        "    見 village_name_repair.repair_json_vill_name。\n"
        "  - SHP 村名對齊：民國85年臺中市 SHP 與 2000 得票資料用字不一致者，以 SHP_NAME_REPAIR\n"
        "    逐筆指定（北屯區「廓子里」←→ 資料「部子里」，皆為「廍子」之異寫）。").replace(
        "    2012 圖資有、2000 未設立的里若對不上資料，一律留白並記入報告。",
        "    2012 圖資有、2000 未設立的里若對不上資料，一律留白並記入報告；\n"
        "    惟臺中舊市區 8 區已改用 2000 當時的村里界 SHP，該區無此類留白。"),
    "shp": '''底圖 × 2000 村里名對齊：
  - SHP 村名對齊：民國85年臺中市 SHP 與 2000 得票資料用字不一致者，以 SHP_NAME_REPAIR
    逐筆指定（北屯區「廓子里」←→ 資料「部子里」，皆為「廍子」之異寫）。
  - 本圖直接沿用民國85年（1996）當時的村里界（8 區、224 個里圖斑；底圖與 1996 版完全相同），故無「2012 新設里」之留白；
    SHP 有、2000 得票資料無者，一律留白並記入報告。''',
}

BASEMAP_DOC = {"json": BASEMAP_DOC_JSON, "json_shp": BASEMAP_DOC_JSONSHP, "shp": BASEMAP_DOC_SHP}
BASEMAP_DIFF_DOC = {"json": BASEMAP_DIFF_DOC_JSON, "json_shp": BASEMAP_DIFF_DOC_JSONSHP,
                    "shp": BASEMAP_DIFF_DOC_SHP}
BASEMAP_CONFIG = {"json": BASEMAP_CONFIG_JSON, "json_shp": BASEMAP_CONFIG_JSONSHP,
                  "shp": BASEMAP_CONFIG_SHP}
BASEMAP_FUNCS = {"json": BASEMAP_FUNCS_JSON, "json_shp": BASEMAP_FUNCS_JSONSHP,
                 "shp": BASEMAP_FUNCS_SHP}


for cfg in REGIONS:
    mode = cfg["base"]
    bm = {
        "BASEMAP_DOC": BASEMAP_DOC[mode],
        "BASEMAP_DIFF_DOC": BASEMAP_DIFF_DOC[mode],
        "BASEMAP_CONFIG": BASEMAP_CONFIG[mode],
        "BASEMAP_FUNCS": BASEMAP_FUNCS[mode],
        "SCALE_DOC": BASEMAP_SCALE_DOC[mode],
        "SCALE_CONFIG_HEAD": BASEMAP_SCALE_HEAD[mode],
        "MAXPX_NOTE": BASEMAP_MAXPX_NOTE[mode],
        "MPP_LINE": BASEMAP_MPP[mode],
        "SCALE_UP_LINE": BASEMAP_SCALEUP[mode],
        "BASE_PATH": BASEMAP_BASE_PATH[mode],
        "BASEMAP_APPLY": BASEMAP_APPLY[mode],
        "ELEM_LABEL": BASEMAP_ELEM_LABEL[mode],
        "BASE_LABEL": BASEMAP_BASE_LABEL[mode],
        "BASE_SRC_LABEL": BASEMAP_BASE_SRC_LABEL[mode],
        "LINEAGE_NOTE": BASEMAP_LINEAGE_NOTE[mode],
        "BASE_KIND": BASEMAP_BASE_KIND[mode],
        "SCALE_LINE_DOC": BASEMAP_SCALE_LINE_DOC[mode],
        "NAME_ALIGN_DOC": BASEMAP_NAME_ALIGN_DOC[mode],
    }
    doc = HEADER
    doc = doc.replace("<<<DOC_TITLE>>>", cfg["doc_title"])
    doc = doc.replace("<<<ALIAS_SUMMARY>>>", " ".join(cfg["alias_note"].replace("#", "").split()))
    doc = doc.replace("<<<ALIAS_NOTE>>>", cfg["alias_note"])
    doc = doc.replace("<<<ALIAS>>>", cfg["alias"])
    doc = doc.replace("<<<TARGET>>>", cfg["target"])
    doc = doc.replace("<<<DROP_NAN_NOTE>>>", cfg["drop_nan_note"])
    doc = doc.replace("<<<DROP_NAN>>>", cfg["drop_nan"])
    doc = doc.replace("<<<OUT_PNG>>>", cfg["out_png"])
    doc = doc.replace("<<<MISS_MD>>>", cfg["miss_md"])
    doc = doc.replace("<<<LAYER>>>", cfg["layer"])
    doc = doc.replace("<<<BBOX>>>", cfg["bbox"])
    doc = doc.replace("<<<CODE>>>", cfg["code"])
    body = FUNCS.replace("<<<REGION>>>", cfg["region"]).replace("<<<DROP_HINT>>>", cfg["drop_hint"])
    for _k, _v in bm.items():
        doc = doc.replace(f"<<<{_k}>>>", _v)
        body = body.replace(f"<<<{_k}>>>", _v)
    out = doc + body + "\n" + TAIL
    path = os.path.join(HERE, f"Draw_{cfg['code']}_President_2000.py")
    open(path, "w", encoding="utf-8").write(out)
    assert "<<<" not in out, f"{path} 仍有未展開的佔位符"
    print(f"written {path}  ({out.count(chr(10))} lines)")
