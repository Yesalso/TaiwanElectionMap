# -*- coding: utf-8 -*-
"""
全臺灣 2016／2020／2024 三屆立法委員全國不分區及僑居國外國民選舉
各村（里）得票領先政黨得票比例圖 —— **一次性生成三張全島圖**

由 `Draw_Taiwan_AtLarge_2012.py` 改造（該腳本以模組方式 import，管線函式全部重用：
底圖讀取／跨縣市重疊仲裁／沿革合併＋跨里合併＋萬用字元＋模糊四層比對／填色／
金門連江附圖版面／線稿分層渲染／洪水填充／全套自檢）。本腳本只做「換屆差異」：

1. 底圖改為**逐年 SHP**（官方村里界歷史圖資，取代 2012 的 JSON 底圖＋金馬拼接）：
   - 2016 → 民國106年（1070205，.dbf=cp950/Big5，_read_shp_base 自動試編碼）
   - 2020 → 民國108年（1081121，UTF-8）
   - 2024 → 民國111年（1111118，UTF-8；亦為跨縣市重疊仲裁的權威圖資）
   三版 SHP 村里完整（含烏坵鄉、龜山島、離島礁石），2012 版的
   replace_counties_from_shp／supplement_missing_towns／add_gueishan_island 補漏
   一律不再需要；跨縣市重疊仲裁（resolve_cross_county_overlaps）照舊。
   **遠島剔除（2026-11-12 修正）改為「逐部件」**：106/108/111 年 SHP 的
   宜蘭縣頭城鎮**大溪里是 101 部件的 MultiPolygon**（1 塊 13.7 km² 沿岸陸地
   ＋ 100 塊釣魚台列嶼島礁，釣魚台行政上劃歸大溪里）。base.strip_far_parts
   以「整列」為單位剔除，只要有一個部件 >100 km 就把整列砍掉 → 大溪里 13.7 km²
   沿岸陸地陪葬，宜蘭頭城東北角出現一大塊白色缺口（「缺一角」），且該里在
   稽核報告裡被誤列為「得票資料有、底圖卻無對應村里圖斑」。改用本檔
   `strip_far_parts_by_part`：只剔遠島部件、近岸部件以原屬性保留，
   整列全為遠島者才整列剔除。
2. 得票資料皆為中選會原始表（每縣市一檔），三屆同一解析器（依副檔名分派
   xlrd／openpyxl）：
   - 2016／2020：data/不分区2016、data/不分区2020 的 .xls（檔名簡體，工作表名傳統）。
   - 2024：data/不分区2024 的 .xlsx —— **檔名為 Big5→GBK 亂碼**（ぃだ跋ミ〆…），
     但**工作表名與內容完好**（雲林縣…），縣市一律從工作表名解析。
     政黨名取儲存格「(序號)\\n黨名」**最後一行**；2020 數字含千分位逗號須先清；
     同一村里多投票所逐列累加，得票率＝得票數÷有效票數A。
3. 政黨與色階逐年動態建立（PARTIES 取自資料表頭；色階組沿用 2012 版慣例：
   中國國民黨＝1 藍、民主進步黨＝2 綠、台灣民眾黨＝5 青綠、新黨＝3 黃，
   其餘政黨一律第 0 組灰階），透過 monkey-patch `base.PARTIES／base.PARTY_STOPS`
   餵給重用的比對／填色函式。

輸出（map/）：
  全臺灣{2016,2020,2024}年立法委員不分區選舉_政黨票得票率地圖.png
  全臺灣{2016,2020,2024}年立法委員不分區選舉_稽核報告.md（每屆一份，
    彙整 村里版／鄉鎮市區版／縣市版 三節，各節由對應腳本寫入）

執行：py script/Draw_Taiwan_AtLarge_2016_2020_2024.py            # 三屆全跑
      py script/Draw_Taiwan_AtLarge_2016_2020_2024.py 2016       # 只跑指定屆
      py script/Draw_Taiwan_AtLarge_2016_2020_2024.py 2020 --test  # 只畫澎湖金門連江
"""
import os
import re
import sys
import glob
import math
import time
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import xlrd
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union
from scipy import ndimage
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                    # …\LegislationYuan\2012-2024
LEGIS_DIR = os.path.dirname(PROJECT_DIR)                     # …\LegislationYuan
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# 重用 2012 版管線（import 時僅載入模組設定，不會執行其 main）
import Draw_Taiwan_AtLarge_2012 as base
nat = base.nat

# ===================== 配置 =====================
TARGET_CRS = base.TARGET_CRS

# 逐年底圖（官方村里界歷史圖資；編碼由 base._read_shp_base 自動嘗試 utf-8/cp950）
YEAR_SHP = {
    2016: r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_106\村里界歷史圖資_106\VILLAGE_MOI_1070205.shp",
    2020: r"D:\Windows\Documents\村里界歷史圖資_111\108\VILLAGE_MOI_1081121.shp",
    2024: r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
}

# 逐年得票資料（中選會原始表：2016/2020 為 .xls；2024 為 .xlsx、檔名亂碼但內容完好）
YEAR_DATA_GLOB = {
    2016: os.path.join(PROJECT_DIR, "data", "不分区2016", "*.xls"),
    2020: os.path.join(PROJECT_DIR, "data", "不分区2020", "*.xls"),
    2024: os.path.join(PROJECT_DIR, "data", "不分区2024", "**", "*.xlsx"),
}

# 色階表（同 2012 版：LegislationYuan/color.txt）
COLOR_TXT = os.path.join(LEGIS_DIR, "color.txt")
_ALL_STOPS = nat.load_color_stops(COLOR_TXT)
# 政黨 → 色階組別（0 無黨籍灰 / 1 國民黨藍 / 2 民進黨綠 / 3 新黨黃 / 4 橘 /
#                 5 民眾黨青綠 / 6 無黨團結聯盟粉紅 / 7 時代力量綠（35–80%））
# 只給主要政黨專色，其餘一律灰階
PARTY_COLOR_GROUP = {
    "中國國民黨": 1, "民主進步黨": 2, "台灣民眾黨": 5, "新黨": 3,
    "無黨團結聯盟": 6,
    # 時代力量：color.txt 第 8 組（2026-11-12 使用者指定，原本吃第 0 組灰階）
    "時代力量": 7,
}
# 政黨名正字收斂（2024 前處理表用「民衆」異體）
PARTY_NAME_TRANS = str.maketrans({"衆": "眾"})

# 2016／2020 原始 xls 的檔名為簡體（云林县.xls）→ 對照傳統縣市名
FILENAME_COUNTY_S2T = {
    "台北市": "臺北市", "新北市": "新北市", "桃園市": "桃園市", "桃园市": "桃園市",
    "台中市": "臺中市", "台南市": "臺南市", "高雄市": "高雄市",
    "基隆市": "基隆市", "新竹市": "新竹市", "嘉義市": "嘉義市", "嘉义市": "嘉義市",
    "新竹縣": "新竹縣", "苗栗縣": "苗栗縣", "彰化縣": "彰化縣", "南投縣": "南投縣",
    "雲林縣": "雲林縣", "嘉義縣": "嘉義縣", "屏東縣": "屏東縣", "宜蘭縣": "宜蘭縣",
    "花蓮縣": "花蓮縣", "臺東縣": "臺東縣", "澎湖縣": "澎湖縣", "金門縣": "金門縣",
    "連江縣": "連江縣",
    "云林县": "雲林縣", "南投县": "南投縣", "台东县": "臺東縣", "台东县": "臺東縣",
    "嘉义县": "嘉義縣", "宜兰县": "宜蘭縣", "屏东县": "屏東縣", "彰化县": "彰化縣",
    "新竹县": "新竹縣", "桃园市": "桃園市", "澎湖县": "澎湖縣", "花莲县": "花蓮縣",
    "苗栗县": "苗栗縣", "连江县": "連江縣", "金门县": "金門縣", "台中市": "臺中市",
    "台北市": "臺北市", "台南市": "臺南市", "台东县": "臺東縣",
}
COUNTY_NAME_RE = re.compile(r"^[\u4e00-\u9fff]{2,3}[縣市]$")

OUT_DIR = base.OUT_DIR
TEST_COUNTIES = base.TEST_COUNTIES


def year_outputs(year):
    """逐年輸出路徑（正式圖／合併稽核報告；測試模式另存以免蓋掉正式圖）。"""
    return {
        "png": os.path.join(OUT_DIR, f"全臺灣{year}年立法委員不分區選舉_政黨票得票率地圖.png"),
        "missing": os.path.join(OUT_DIR, f"全臺灣{year}_無資料與未匹配村里.md"),
        "report": audit_report_path(year),
        "test_png": os.path.join(OUT_DIR, f"全臺灣{year}_離島測試_澎湖金門馬祖.png"),
        "test_missing": os.path.join(OUT_DIR, f"全臺灣{year}_離島測試_無資料與未匹配村里.md"),
    }


# ---------------------- 每屆一份合併稽核報告 ----------------------
# 稽核報告每屆只有一個文檔（全臺灣{year}年…_稽核報告.md），彙整
# 村里版／鄉鎮市區版／縣市版 三節；各腳本只覆寫自己那一節，其餘節保留。
# （與 Draw_Taiwan_AtLarge_2016_2020_2024_Township.write_audit_section 同構；
#   因該模組 import 本模組，為避免循環匯入故在此複製一份）
AUDIT_SECTIONS = ("村里版稽核", "鄉鎮市區版稽核", "縣市版稽核")


def audit_report_path(year):
    return os.path.join(OUT_DIR,
                        f"全臺灣{year}年立法委員不分區選舉_稽核報告.md")


def write_audit_section(year, section, lines):
    """把本節內容（lines，不含節標題）覆寫進該屆合併稽核報告的對應節。

    既有文檔按「## 」節標題切分保留其餘節；節順序依 AUDIT_SECTIONS。
    節內小節一律用「### 」以下層級，不得出現「## 」。
    """
    path = audit_report_path(year)
    sections = {}
    if os.path.exists(path):
        cur = None
        with open(path, encoding="utf-8") as f:
            for ln in f.read().splitlines():
                if ln.startswith("## "):
                    cur = ln[3:].strip()
                    sections.setdefault(cur, [ln])
                elif cur is not None:
                    sections[cur].append(ln)
    sections[section] = ["## " + section] + [str(x) for x in lines]
    L = [f"# 全臺灣 {year} 立法委員不分區（政黨票）稽核報告", "",
         f"- 最近更新：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         "- 每屆一份文檔，彙整 村里版／鄉鎮市區版／縣市版 三節；"
         "各節由對應腳本（村里版／鄉鎮市區版／縣市版）寫入。", ""]
    for s in AUDIT_SECTIONS:
        if s in sections:
            L += sections[s] + [""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  合併稽核報告（{section} 節）：{path}")


# ---------------------- 共用小工具 ----------------------
def _num(cell):
    """儲存格 → float（清千分位逗號與空白；空白／非數值回 0）。"""
    s = str(cell).replace(",", "").replace("\u3000", "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _party_name(cell):
    """2016「1\\n \\n民主進步黨」／2020「(1)\\n\\n合一行動聯盟」→ 取最後一行黨名。"""
    lines = [s.strip() for s in str(cell).split("\n") if s.strip()]
    nm = lines[-1] if lines else ""
    return nm.translate(PARTY_NAME_TRANS).strip()


def fix_party_name(nm):
    return str(nm).translate(PARTY_NAME_TRANS).strip()


def make_stops(parties):
    """依政黨表建立逐年 PARTY_STOPS（未列入 PARTY_COLOR_GROUP 者一律灰階第 0 組）。"""
    out = {}
    for p in parties:
        g = PARTY_COLOR_GROUP.get(p, 0)
        if g >= len(_ALL_STOPS):
            g = 0
        out[p] = _ALL_STOPS[g]
    return out


# ---------------------- ① 讀 2016／2020／2024 中選會原始表 ----------------------
def _open_workbook(path):
    """依副檔名讀原始表 → 統一的 (n_sheets, cell(r,c)) 介面（0 起、含表頭）。"""
    import openpyxl
    if str(path).lower().endswith((".xlsx", ".xlsm")):
        wb = openpyxl.load_workbook(path, data_only=True)
        sheets = wb.worksheets
        def cell(sh, r, c):
            v = sh.cell(row=r + 1, column=c + 1).value
            return "" if v is None else v
        return sheets, cell
    wb = xlrd.open_workbook(path)
    sheets = wb.sheets()
    def cell(sh, r, c):
        return sh.cell_value(r, c)
    return sheets, cell


def load_raw_party_votes(files_glob):
    """解析中選會原始表（每縣市一檔；.xls/.xlsx 皆可），聚合到村里層級。

    表頭列＝「鄉(鎮、市、區)別」所在列；政黨名在表頭 +1 列（儲存格最後一行）；
    政黨欄位＝第 3 欄起至「有效票數」前；資料列自表頭 +4 列起
    （鄉鎮列＝第 0 欄有值、第 1 欄空；總計列跳過；多投票所逐列累加）。
    縣市名優先從工作表名解析（2016/2020 檔名簡體、2024 檔名亂碼，
    但三屆工作表名皆為傳統縣市名），失敗才退回檔名對照表。

    回傳 (by_key, by_town, display, cnt_by_key, n_total, parties)：
      by_key     : (縣市, 鄉鎮市區, 村里) → 各政黨得票率 tuple
      by_town    : (縣市, 鄉鎮市區) → [(村里, rates), ...]
      display    : 同鍵 → (縣市, 鄉鎮原文, 村里原文)
      cnt_by_key : 同鍵 → (各政黨得票數…, 有效票數)
      parties    : 政黨表（取自表頭列 +1，儲存格最後一行）
    """
    files = sorted(glob.glob(files_glob, recursive=True))
    if not files:
        raise FileNotFoundError(f"找不到得票資料：{files_glob}")
    by_key, by_town, display, cnt_by_key = {}, {}, {}, {}
    parties_ref, n_total, skipped = None, 0, []

    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        sheets, cell = _open_workbook(path)
        county = None
        for sh in sheets:
            hdr = None
            for r in range(min(6, _nrows(sh))):
                if "鄉(鎮、市、區)別" in str(cell(sh, r, 0)):
                    hdr = r
                    break
            if hdr is None:
                continue
            if county is None and COUNTY_NAME_RE.match(str(sh.title if hasattr(sh, "title") else sh.name).strip()):
                county = base.norm_county(sh.title if hasattr(sh, "title") else sh.name)
            if county is None:
                county = FILENAME_COUNTY_S2T.get(stem)
                if county:
                    county = base.norm_county(county)
            if county is None:
                break

            valid_col = None
            for c in range(_ncols(sh)):
                if "有效票數" in str(cell(sh, hdr, c)).replace("\n", ""):
                    valid_col = c
                    break
            if valid_col is None:
                raise ValueError(f"{stem} 找不到「有效票數」欄")
            pcols = [(c, _party_name(cell(sh, hdr + 1, c)))
                     for c in range(3, valid_col)]
            pcols = [(c, nm) for c, nm in pcols if nm]
            names = [nm for _, nm in pcols]
            if parties_ref is None:
                parties_ref = names
            elif names != parties_ref:
                raise ValueError(f"{stem} 政黨欄位與其他檔不一致：{names}")

            acc = {}      # (鄉鎮原文, 村里原文) → [counts..., valid]
            town = ""
            for r in range(hdr + 4, _nrows(sh)):
                c0 = str(cell(sh, r, 0)).strip()
                c1 = str(cell(sh, r, 1)).strip()
                if c0 == "None" or c0 == "nan":
                    c0, c1 = "", c1 if c1 != "None" and c1 != "nan" else ""
                if c0 and not c1:
                    if "總" not in c0:      # 總計列不更新鄉鎮
                        town = c0
                    continue
                if not c1:
                    continue
                if not town:
                    continue
                counts = [_num(cell(sh, r, c)) for c, _ in pcols]
                valid = _num(cell(sh, r, valid_col))
                if valid <= 0:
                    continue
                n_total += 1
                k = (town, c1)
                a = acc.get(k)
                if a is None:
                    acc[k] = counts + [valid]
                else:
                    for i, v in enumerate(counts):
                        a[i] += v
                    a[-1] += valid

            # 逐村里換算得票率（多村里併列者拆開，共用同一組得票數）
            for (town_raw, vill_raw), a in acc.items():
                counts, valid = a[:-1], a[-1]
                rates = tuple(v / valid * 100.0 for v in counts)
                town_core = base.norm_town(town_raw)
                for part in [p for p in re.split(r"[、，,]", vill_raw) if p.strip()]:
                    part = _BRACKET_RE.sub("", base.VOTE_NAME_REPAIR_2012.get(
                        (county, town_core, part), part))
                    part = YEAR_VOTE_NAME_REPAIR.get(_CUR_YEAR[0], {}).get(
                        (county, town_core, part), part)
                    vk = base.norm_vill(base.repair_vote_name(part))
                    if not vk:
                        continue
                    key = (county, town_core, vk)
                    if key in by_key:
                        print(f"  ⚠️ 資料側村里鍵撞名（後者略過）：{key} "
                              f"{display.get(key)} vs {part}")
                        continue
                    by_key[key] = rates
                    cnt_by_key[key] = tuple(counts) + (valid,)
                    by_town.setdefault((county, town_core), []).append((vk, rates))
                    display[key] = (county, town_raw.strip(), part.strip())
        if county is None:
            skipped.append(stem)
    if skipped:
        print(f"  ⚠️ 略過無法對應縣市的檔案：{skipped}")
    return by_key, by_town, display, cnt_by_key, n_total, parties_ref


def _nrows(sh):
    return sh.nrows if hasattr(sh, "nrows") else sh.max_row


def _ncols(sh):
    return sh.ncols if hasattr(sh, "ncols") else sh.max_column


LOADERS = {
    2016: load_raw_party_votes,
    2020: load_raw_party_votes,
    2024: load_raw_party_votes,
}

# ---------------------- 逐年「新設村（里）併入母里」表 ----------------------
# 圖資（SHP）比得票資料新：2015~2016 桃園市里行政區重劃（2015-03-01）等新設的
# 村里，在當屆中選會得票資料中仍併在母里內 → 比對前把 unit_core 指向母里
# （同「沿革合併」：共用母里得票率、其間不畫 1px 村里界）。
# 鍵＝(縣市, 鄉鎮(已正規化), 圖資村里(去尾綴)) → 值＝母里(去尾綴)。
# 2016 使用者查證沿革（2020/2024 資料已含新設村，無需合併）：
#   竹北 中崙←斗崙；大溪 仁美←仁義；桃園 大業←大興、大樹←大林、福元←忠義；
#   蘆竹 正興←蘆興、濱海←海湖（蘆竹 2014 升格重劃）；龍潭 祥和←龍祥；
#   龜山 文青←樂善、楓福←楓樹
YEAR_VOTE_MERGE = {
    2016: {
        ("新竹縣", "竹北", "中崙"): "斗崙",
        ("桃園市", "大溪", "仁美"): "仁義",
        ("桃園市", "桃園", "大業"): "大興",
        ("桃園市", "桃園", "大樹"): "大林",
        ("桃園市", "桃園", "福元"): "忠義",
        ("桃園市", "盧竹", "正興"): "盧興",
        ("桃園市", "盧竹", "濱海"): "海湖",
        ("桃園市", "龍潭", "祥和"): "龍祥",
        ("桃園市", "龜山", "文青"): "樂善",
        ("桃園市", "龜山", "楓福"): "楓樹",
    },
    2020: {},
    2024: {},
}
_CUR_YEAR = [None]      # run_year 每屆設定（wrapper 讀取）

# ---------------------- 逐年「异体字/俗字村名正名」表 ----------------------
# 圖資（SHP）與中選會資料對同一村用了不同寫法（MOI SHP 常以同音/形近字替代
# 罕見字；中選會亦有自己的俗字），比對前就地改寫正名 → 精確對位。
# 2016 使用者查證＋反查表配對（2020/2024 資料如出現同類留白再逐年補）：
#   瓦瑤→瓦磘（新園/埔鹽/元長/麥寮/中和）、磚瑤→磚磘（嘉市西區/彰化市）、
#   回瑤→硘磘（竹山）、槍寮→羌寮（樹林；資料作「獇寮」）、水砌→水磜（北埔；
#   資料作「水磜」）、慷榔→槺榔（新屋/清水）、柏子/柏東→箔子/箔東（四湖）、
#   帝埔→坔埔（鳥松）
YEAR_MAP_NAME_REPAIR = {
    2016: {
        ("新北市", "中和區", "瓦瑤里"): "瓦磘里",
        ("南投縣", "竹山鎮", "回瑤里"): "硘磘里",
        ("嘉義市", "西區", "磚瑤里"): "磚磘里",
        ("彰化縣", "彰化市", "磚瑤里"): "磚磘里",
        ("屏東縣", "新園鄉", "瓦瑤村"): "瓦磘村",
        ("彰化縣", "埔鹽鄉", "瓦瑤村"): "瓦磘村",
        ("雲林縣", "元長鄉", "瓦瑤村"): "瓦磘村",
        ("雲林縣", "麥寮鄉", "瓦瑤村"): "瓦磘村",
        ("新北市", "樹林區", "槍寮里"): "羌寮里",
        ("新竹縣", "北埔鄉", "水砌村"): "水磜村",
        ("桃園市", "新屋區", "慷榔里"): "槺榔里",
        ("臺中市", "清水區", "慷榔里"): "槺榔里",
        ("雲林縣", "四湖鄉", "柏子村"): "箔子村",
        ("雲林縣", "四湖鄉", "柏東村"): "箔東村",
        ("高雄市", "鳥松區", "帝埔里"): "坔埔里",
    },
    2020: {},
    2024: {},
}

# 資料側村名正名（鍵＝(縣市, 鄉鎮core, 原始村名)）：
#   水林 欍埔村＝SHP 的 舊埔村（base 異體表「欍→春」會誤斂成春埔村撞名，
#   資料被静默丟棄）→ 先正名為 舊埔村 再正規化
YEAR_VOTE_NAME_REPAIR = {
    2016: {
        ("雲林縣", "水林", "欍埔村"): "舊埔村",
    },
    2020: {},
    2024: {},
}

# SHP 村里名的 MOI 罕見字標記：字面 ASCII 方括號（灰[瑤]里 等 94 筆）→ 剝除
# （中選會資料側一律寫正字無括號；兩側剝除後即可精確對位）
_BRACKET_RE = re.compile(r"[\[\]［］]")


def _install_year_merger():
    """包一層 base.add_unit_core：沿革合併之後，再套用逐年新設村併入母里表。"""
    orig = base.add_unit_core

    def _patched(gdf, idx):
        gdf = orig(gdf, idx)
        merge = YEAR_VOTE_MERGE.get(_CUR_YEAR[0])
        if not merge:
            return gdf
        hits = []
        for i in gdf.index:
            k = (base.norm_county(gdf.at[i, "COUNTYNAME"]),
                 base.norm_town(gdf.at[i, "TOWNNAME"]),
                 str(gdf.at[i, "vill_core"]))
            mother = merge.get(k)
            if mother:
                gdf.at[i, "unit_core"] = mother
                gdf.at[i, "merged_into"] = mother
                hits.append(f"{k[1]}{k[2]}→{mother}")
        if hits:
            print(f"  逐年新設村併入母里（{_CUR_YEAR[0]} 合併表）：{len(hits)} 個 "
                  f"{'、'.join(sorted(hits))}")
        miss = {k for k in merge
                if k not in {(base.norm_county(gdf.at[i, "COUNTYNAME"]),
                              base.norm_town(gdf.at[i, "TOWNNAME"]),
                              str(gdf.at[i, "vill_core"])) for i in gdf.index}}
        if miss:
            print(f"  ⚠️ 合併表鍵未命中圖資：{sorted(miss)}")
        return gdf

    base.add_unit_core = _patched


_install_year_merger()


# ---------------------- 遠島碎塊清理（逐部件） ----------------------
def strip_far_parts_by_part(gdf, max_km=None):
    """同 `base.strip_far_parts`（剔除距本島 > max_km 的東沙／南沙／釣魚台等碎塊），
    但改為**逐部件**剔除、不以「整列」為單位。

    為什麼必須改（2026-11-12 宜蘭「缺一角」事故）：
      106／108／111 年 SHP 中 **宜蘭縣頭城鎮大溪里是 101 部件的 MultiPolygon**
      ——1 塊 13.7 km² 的沿岸陸地 ＋ 100 塊釣魚台列嶼島礁（釣魚台列嶼行政上
      劃歸頭城鎮大溪里）。`base.strip_far_parts` 以「村里列」為剔除單位，
      只要該列有任何部件離本島 >100 km 就把**整列** drop → 大溪里沿岸 13.7 km²
      陸地連帶消失，宜蘭頭城東北角出現一塊橢圓形白色缺口（使用者所見「缺了一角」），
      同時該里被稽核報告誤判為「得票資料有、底圖卻無對應村里圖斑」。
    正解：只剔遠島部件，近岸部件以原屬性（村里名／代碼）保留；
    整列部件全部是遠島者（如純礁石列）才整列剔除。
    """
    if max_km is None:
        max_km = base.FAR_PART_MAX_KM
    cover = ~gdf["COUNTYNAME"].isin(base.EXCLUDE_INSET)
    sub = gdf[cover]
    parts = [pp for geom in sub.geometry
             for pp in (list(geom.geoms) if hasattr(geom, "geoms") else [geom])]
    if len(parts) <= 1:
        return gdf
    merged = unary_union(parts)
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)
    keep_idx, new_geoms, n_far, lost_vill, shrunk_vill = [], [], 0, [], []
    for i, geom in sub.geometry.items():
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        near = [p for p in ps if main.distance(p) <= max_km * 1000.0]
        n_far += len(ps) - len(near)
        if not near:
            lost_vill.append(f"{sub.at[i, 'COUNTYNAME']}{sub.at[i, 'TOWNNAME']}"
                             f"{sub.at[i, 'VILLNAME']}")
            continue
        if len(near) != len(ps):
            shrunk_vill.append(
                f"{sub.at[i, 'COUNTYNAME']}{sub.at[i, 'TOWNNAME']}"
                f"{sub.at[i, 'VILLNAME']}（保留 {len(near)} 塊／"
                f"剔 {len(ps) - len(near)} 塊，本體 "
                f"{sum(p.area for p in near) / 1e6:.2f} km²）")
        keep_idx.append(i)
        new_geoms.append(near[0] if len(near) == 1 else MultiPolygon(near))
    out = gdf.loc[keep_idx].copy()
    out["geometry"] = new_geoms
    out = gpd.GeoDataFrame(pd.concat([gdf[~cover], out], ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    if n_far:
        print(f"  離島碎塊清理（逐部件）：剔除 {n_far} 塊（距本島 > {max_km:.0f} km），"
              f"近岸部件全數保留；保留後圖斑 {len(out)} 筆（清理前 {len(gdf)}）")
    else:
        print(f"  離島碎塊清理（逐部件）：無需剔除（門檻 {max_km:.0f} km）")
    for s in shrunk_vill:
        print(f"    ↳ 保留本體、僅剔遠島部件：{s}")
    for s in lost_vill:
        print(f"    ↳ 整列皆為遠島 → 整列剔除：{s}")
    return out


# ---------------------- 主流程（逐年；鏡像 base.main ①→⑤） ----------------------
def run_year(year, test_only=False):
    t0 = time.time()
    _CUR_YEAR[0] = year
    out = year_outputs(year)
    out_png = out["test_png"] if test_only else out["png"]
    miss_md = out["test_missing"] if test_only else out["missing"]

    print("=" * 66)
    print(f"  全臺灣 {year} 立法委員不分區（政黨票）村里得票率地圖"
          + ("　【測試模式：只畫澎湖／金門／連江】" if test_only else ""))
    print("=" * 66)

    # ---- ① 得票資料 ----
    by_key, by_town, vote_display, cnt_by_key, n_total, parties = \
        LOADERS[year](YEAR_DATA_GLOB[year])
    if not parties:
        raise ValueError(f"{year} 未解析到任何政黨欄位")
    # monkey-patch：把逐年政黨表／色階餵給重用的比對／填色函式
    base.PARTIES = parties
    base.PARTY_STOPS = make_stops(parties)
    print(f"  得票資料：{n_total} 個村里列 → {len(by_key)} 個村里、"
          f"{len(parties)} 個政黨：{'、'.join(parties)}")

    # ---- ② 底圖（逐年 SHP；補漏機制不再需要） ----
    gdf = base._read_shp_base(YEAR_SHP[year])
    # MOI 罕見字標記：剝除村名中的字面方括號（灰[瑤]里 → 灰瑤里），與資料側對位
    _br = gdf["VILLNAME"].astype(str).str.contains(_BRACKET_RE, regex=True)
    if int(_br.sum()):
        gdf["VILLNAME"] = gdf["VILLNAME"].astype(str).str.replace(
            _BRACKET_RE, "", regex=True)
        print(f"  底圖村名剝除罕見字方括號：{int(_br.sum())} 筆"
              f"（如 中和區灰[瑤]里→灰瑤里）")
    # 异体字/俗字正名（SHP 側；詳見 YEAR_MAP_NAME_REPAIR 表）
    _rep = YEAR_MAP_NAME_REPAIR.get(year, {})
    if _rep:
        _keys_before = {(str(gdf.at[i, "COUNTYNAME"]), str(gdf.at[i, "TOWNNAME"]),
                         str(gdf.at[i, "VILLNAME"])) for i in gdf.index}
        _hits = []
        for i in gdf.index:
            k = (str(gdf.at[i, "COUNTYNAME"]), str(gdf.at[i, "TOWNNAME"]),
                 str(gdf.at[i, "VILLNAME"]))
            if k in _rep:
                gdf.at[i, "VILLNAME"] = _rep[k]
                _hits.append(f"{k[1]}{k[2]}→{_rep[k]}")
        if _hits:
            print(f"  底圖村名正名（异体字/俗字）：{len(_hits)} 筆 "
                  f"{'、'.join(sorted(_hits))}")
        _miss = [k for k in _rep if k not in _keys_before]
        if _miss:
            print(f"  ⚠️ 正名表鍵未命中圖資：{_miss}")
    gdf = base.add_old_county(gdf)
    print(f"  底圖：{os.path.basename(YEAR_SHP[year])} → {len(gdf)} 個村里圖斑、"
          f"{gdf['OLD_COUNTY'].nunique()} 個縣市、"
          f"{gdf.groupby(['OLD_COUNTY', 'TOWNNAME']).ngroups} 個鄉鎮市區")
    if test_only:
        print("  跨縣市重疊清理：測試模式略過（離島三縣市互不相鄰）")
    else:
        gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = strip_far_parts_by_part(gdf)
    if test_only:
        _m = gdf["COUNTYNAME"].isin(TEST_COUNTIES)
        print(f"  測試模式：只保留 {'、'.join(TEST_COUNTIES)} → "
              f"{int(_m.sum())} 個村里圖斑（原 {len(gdf)}）")
        gdf = gdf[_m].copy().reset_index(drop=True)

    # ---- ③ 比對（沿革合併 → 跨里合併 → 萬用字元 → 異體模糊） ----
    lin_idx = base.build_lineage_index(by_key)
    gdf, rate_cols = base.match_votes(gdf, by_key, by_town, cnt_by_key, lin_idx)
    mt = gdf["match_type"].astype(str)
    stats = {
        "exact": int((mt == "exact").sum()),
        "merged": int(mt.str.startswith("merged").sum()),
        "mergevote": int(mt.str.startswith("mergevote").sum()),
        "wildcard": int(mt.str.startswith("wildcard").sum()),
        "elimination": int(mt.str.startswith("elimination").sum()),
        "fuzzy": int(mt.str.startswith("fuzzy").sum()),
        "none": int((mt == "none").sum()),
    }
    print(f"  精確 {stats['exact']}、沿革合併 {stats['merged']}、跨里合併 "
          f"{stats['mergevote']}、萬用字元 {stats['wildcard']}、消去法 "
          f"{stats['elimination']}、模糊 {stats['fuzzy']}、無資料 {stats['none']}")

    # 缺口自檢（宜蘭頭城大溪里事故的回歸守門）：底圖村里數不得少於得票資料村里數。
    # 只針對「圖資側本應涵蓋得票資料」的縣市檢查——全臺各縣市皆適用，
    # 但臺南市／屏東縣等少數村里在資料側為舊名（已在稽核報告第 7 節逐筆列出），
    # 故僅列印、不中斷；宜蘭縣若少於 233 即代表又有人把整列剔掉。
    _map_cnt = gdf.groupby("COUNTYNAME").size().to_dict()
    _vote_cnt = {}
    for (c, _t, _v) in by_key:
        _vote_cnt[c] = _vote_cnt.get(c, 0) + 1
    _short = {c: (_map_cnt.get(c, 0), n) for c, n in _vote_cnt.items()
              if _map_cnt.get(c, 0) < n}
    _yl = (_map_cnt.get("宜蘭縣", 0), _vote_cnt.get("宜蘭縣", 0))
    print(f"  宜蘭縣村里圖斑自檢：圖資 {_yl[0]} / 得票資料 {_yl[1]}"
          + ("　✅（含頭城鎮大溪里）" if _yl[0] > 0 and _yl[0] >= _yl[1]
             else "　⚠️ 圖斑少於資料，檢查是否整列剔除"))
    if _short:
        print("  圖資村里數少於得票資料的縣市（多為資料側舊名，見稽核報告第 7 節）："
              + "；".join(f"{c} {a}/{b}" for c, (a, b) in sorted(_short.items())))

    # ---- ④ 填色 ----
    gdf, has_data, min_win = base.pick_colors(gdf, rate_cols, cnt_by_key)
    gdf, has_data, n_town_fill = base.fill_blank_islets_town_colors(
        gdf, has_data, cnt_by_key, rate_cols)
    print(f"  有資料填色 {int(has_data.sum())}／{len(gdf)}"
          f"（含金馬澎空白島嶼填鄉鎮色 {n_town_fill} 塊）；"
          f"全臺最低領先得票率 {min_win:.2f}%")
    for p, n in gdf.loc[has_data, "win_party"].value_counts().items():
        print(f"    領先村里：{p} {int(n)}")

    _tie_rows = gdf[gdf["tie_hex"].notna()]
    print(f"  平票村里（第 1、2 名同票 → 疊 45° 斜線紋）：{len(_tie_rows)} 個")
    if len(_tie_rows):
        _pairs = (_tie_rows["win_party"].astype(str) + "／"
                  + _tie_rows["tie_party"].astype(str))
        print(f"    平票組合：{_pairs.value_counts().to_dict()}")

    if test_only:
        # 測試模式：離島小圖另存獨立報告（不併入正式合併稽核）
        base.write_missing_report(gdf, vote_display, stats, md_path=miss_md)
    else:
        # 正式模式：先寫暫存檔，去掉 # 主標題、次級標題降一級後，
        # 併入每屆一份的合併稽核報告「村里版稽核」節
        _tmp = miss_md + ".tmp"
        base.write_missing_report(gdf, vote_display, stats, md_path=_tmp)
        with open(_tmp, encoding="utf-8") as _f:
            _body = _f.read().splitlines()
        os.remove(_tmp)
        _body = [ln.replace("### ", "#### ", 1) if ln.startswith("### ")
                 else ("### " + ln[3:] if ln.startswith("## ") else ln)
                 for ln in _body if not ln.startswith("# ")]
        write_audit_section(year, "村里版稽核", _body)

    # ---- ⑤ 版面 ----
    if test_only:
        gdf, boxes = base.layout_stack_all(gdf)
    else:
        gdf, boxes = base.layout_insets(gdf)
    records = gpd.GeoDataFrame(
        gdf[["COUNTYNAME", "TOWNNAME", "VILLNAME", "OLD_COUNTY", "unit_core",
             "merged_into", "fill_hex", "tie_hex", "match_type"] + rate_cols].copy(),
        geometry=gdf.geometry, crs=gdf.crs)

    # ---- 畫布（長寬硬上限 10000 × 12500 px） ----
    minx, miny, maxx, maxy = records.total_bounds
    for _cn, (_bx0, _by0, _bx1, _by1), _lw in boxes:
        minx, miny = min(minx, _bx0), min(miny, _by0)
        maxx, maxy = max(maxx, _bx1), max(maxy, _by1)
    pad_x, pad_y = base.PAD_FRAC * (maxx - minx), base.PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w, geo_h = maxx - minx, maxy - miny

    scale = max(geo_w / base.MAX_W_PX, geo_h / base.MAX_H_PX, base.METERS_PER_PIXEL)
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（{w_px * h_px / 1e6:.0f} 百萬像素）")

    # ---- 區／縣市層（dissolve 後清理退化迴針與微孔） ----
    gdf_plot = gpd.GeoDataFrame(records, geometry="geometry", crs=records.crs)
    townships = gdf_plot.dissolve(by=["OLD_COUNTY", "TOWNNAME"]).reset_index()
    counties = gdf_plot.dissolve(by=["OLD_COUNTY"]).reset_index()
    townships = base.remove_ring_slits(townships)
    townships = base.clean_tiny_holes(townships)
    counties = base.remove_ring_slits(counties)
    counties = base.clean_tiny_holes(counties)
    print(f"  縣市：{len(counties)}、鄉鎮市區：{len(townships)}、村里：{len(gdf_plot)}")

    # ---- ② 區界 + 縣市界 + 附圖外框（海岸線另以 1px 金馬畫法繪製） ----
    _thick_cty, coast_geom, county_segs = base.compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g.length for g in county_segs) / 1000:.0f} km）")
    base.audit_county_segments(counties, county_segs)
    town_layer = base.render_boundary_layer(townships, counties, county_segs, [],
                                            w_px, h_px, minx, maxx, miny, maxy)
    print(f"  區/縣市界層：{int(town_layer.sum())} px"
          f"（區界 {base.LINE_TOWNSHIP_PX}px、縣市界 {base.LINE_COUNTY_INNER_PX}px）")

    print("  附圖外框遮罩（金門／連江／烏坵框，最後改上黑線）…")
    box_mask = base.render_inset_box_mask(boxes, w_px, h_px, minx, maxx, miny, maxy)
    print(f"  附圖外框遮罩：{int(box_mask.sum())} px")

    # ---- ① 村里界 1px ----
    print("  ① 村里界 1px（1px 直繪 → thin 中心線；沿革合併單元其間不畫線）…")
    villages = gdf_plot if not base.SIMPLIFY_TOL_M else (
        gdf_plot.set_geometry(gdf_plot.geometry.simplify(base.SIMPLIFY_TOL_M, True)))
    _ukey = (villages["COUNTYNAME"].astype(str) + "|" + villages["TOWNNAME"].astype(str)
             + "|" + villages["unit_core"].astype(str))
    _blank = villages["unit_core"].astype(str).str.strip().eq("")
    _ukey = _ukey.where(~_blank, _ukey + "#" + villages.index.astype(str))
    unit_polys = villages.assign(_unit_key=_ukey).dissolve(by="_unit_key").reset_index()
    print(f"  沿革合併後行政單元：{len(unit_polys)}（村里圖斑 {len(villages)}）")
    village_skel = base.render_village_layer(unit_polys, w_px, h_px, minx, maxy, sx, sy)
    del unit_polys
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # ---- 海岸線 1px（本島，金馬同款畫法） ----
    coast_skel = base.render_main_coast_layer(coast_geom, w_px, h_px, minx, maxy, sx, sy)
    print(f"  海岸線層 1px 中心線：{int(coast_skel.sum())} px")

    lines_mask = village_skel | town_layer | coast_skel | box_mask
    del village_skel, coast_skel

    base.check_reef_drawn(gdf_plot, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # 對齊自檢：所有區界/縣市界/小島海岸線的 1px 原始線都必須被線稿覆蓋
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = base.draw_layer(
        base.extract_lines(unary_union(townships.geometry.boundary.tolist())),
        1, w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(lines_mask, structure=S3)).sum())
    print(f"  區/縣市界 1px 原始線 {int(_town_1px.sum())} px，"
          f"未被線稿覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層連通分量
    _cc_n, _, _cc_st, _ = cv2_connected(town_layer)
    _cc_area = _cc_st[1:, cv2_CC_AREA()]
    print(f"  ② 層連通分量：{_cc_n - 1} 個；<=40px 小分量 {int((_cc_area <= 40).sum())} 個（應為 0）")

    # 村里線自檢：扣掉 ② 層後不應出現 2x2 粗塊
    _v_only = lines_mask & ~town_layer
    _2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
    print(f"  村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")
    del _v_only, _2x2

    # ---- 填色（洪水填充） ----
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）…")
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    arr[lines_mask] = np.array(base.LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0
    print(f"  非線連通區域：{ncomp - 1} 塊；線色 {base.LINE_COLOR}、附圖外框 黑 (0,0,0)")

    # 自檢 A：油漆桶不變式
    _nc, _nbad = nat.check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")
    del comp

    # 平票斜線紋（必須在線稿上色之後才疊）
    _line_before = arr[lines_mask].copy()
    _n_tie = nat.apply_tie_stripes(arr, records, w_px, h_px, minx, maxy, sx, sy,
                                   lines_mask=lines_mask, stripe_px=base.TIE_STRIPE_PX)
    _n_line = int(lines_mask.sum())
    _line_kept = int((arr[lines_mask] == _line_before).all(axis=1).sum())
    print(f"  平票後線稿：{_line_kept}/{_n_line} 線像素仍為原線色"
          f"（應相等＝界線完整；斜線紋 {_n_tie} 個村里圖斑）")
    del _line_before

    # 自檢 B：逐像素幾何參考
    _nw, _nout = nat.full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy,
                                     lines_mask=lines_mask, ignore_mask=lines_mask)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%）；"
          f"村外非白 {_nout} px（皆應 ≈0）")

    # 自檢 C：全圖只含允許色
    allowed = {(255, 255, 255), (0, 0, 0), tuple(int(v) for v in base.LINE_RGB)}
    for stops in base.PARTY_STOPS.values():
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in nat.hex2rgb(hx)))
    _uniq, _cnt = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    _bad = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_uniq, _cnt)
            if tuple(int(x) for x in c) not in allowed]
    print(f"  全圖顏色 {len(_uniq)} 種（允許 {len(allowed)}）；"
          f"非允許色像素 {sum(n for _, n in _bad)}（應為 0）")
    if _bad:
        print(f"  ⚠️ 非允許色：{_bad[:5]}")

    pil_img = Image.fromarray(arr, mode="RGB")
    del arr
    base.save_png(pil_img, out_png)
    W, H = pil_img.size
    del pil_img

    # ---- 存檔後自檢 ----
    _re = np.asarray(Image.open(out_png).convert("RGB"))
    _u2, _c2 = np.unique(_re.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _nw2, _nout2 = nat.full_geom_check(_re, records, w_px, h_px, minx, maxy, sx, sy,
                                       lines_mask=lines_mask, ignore_mask=lines_mask)
    _tol2 = 0.0002 * w_px * h_px
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、幾何參考差異 {_nw2} px"
          f"（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    print(f"\n  Saved: {out_png}  ({W}×{H}px)")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print(f"==== {year} finished ====")


# cv2 經由 base 模組引用（避免重複 import 副作用）
def cv2_connected(mask):
    import cv2
    return cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)


def cv2_CC_AREA():
    import cv2
    return cv2.CC_STAT_AREA


# ---------------------- 入口 ----------------------
def main():
    years, test_only = [], False
    for a in sys.argv[1:]:
        la = str(a).lower()
        if la in ("--test", "--only-islands", "-t"):
            test_only = True
        elif la.isdigit() and int(la) in YEAR_SHP:
            years.append(int(la))
    if not years:
        years = sorted(YEAR_SHP)
    for y in years:
        run_year(y, test_only=test_only)


if __name__ == "__main__":
    main()
