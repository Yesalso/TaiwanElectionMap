# -*- coding: utf-8 -*-
"""
2024 總統副總統選舉 分區村里得票率地圖 —— 共用模組（自包含）

本模組是 5 個分區腳本（Draw_North4 / Draw_South2 / Draw_TCM4 / Draw_TCN3 /
Draw_YCT4 _President_2024.py）共用的實作：得票率讀取、村里名模糊匹配、
色階查色、油漆桶（洪水）填色、平票斜線紋、幾何自檢，全部收在此檔，
不再依賴任何外部共用模組（原 Draw_National_President_2024 已移除）。

配色來源：Precident\\color.txt（6 組政黨色階，Python 串列字面，檔頭註解自動忽略）
    2024 三位候選人依政黨對應其中三組：
        侯友宜 → 組別 1 中國國民黨（藍）
        賴清德 → 組別 2 民主進步黨（綠）
        柯文哲 → 組別 5 台灣民眾黨（青綠）
    RATE_COLOR_STOPS 會依 CAND_NAMES 順序重新排出（侯友宜→賴清德→柯文哲）。

使用：各分區腳本 `import President2024_Common as nat`。
"""
import os
import re
import ast
import glob
import unicodedata
import time

import numpy as np
import pandas as pd
import cv2
from difflib import SequenceMatcher

# ===================== 路徑 =====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)              # ...\2024Precident
PREC_ROOT = os.path.dirname(PROJECT_DIR)               # ...\Precident
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUT_DIR = os.path.join(PROJECT_DIR, "maps")
COLOR_TXT = os.path.join(PREC_ROOT, "color.txt")

VOTE_XLSX = os.path.join(DATA_DIR, "2024總統副總統選舉_得票率.xlsx")
VOTE_SHEET = "各里彙總"

# ===================== 候選人與資料欄位 =====================
# 三組候選人：圖例名稱（順序與色階、RATE_HEADERS 一致）
CAND_NAMES = ["侯友宜", "賴清德", "柯文哲"]
# 得票率欄位名（形如「侯友宜得票率」）
RATE_HEADERS = [f"{c}得票率" for c in CAND_NAMES]
# 候選人 → color.txt 由上而下組別索引（依政黨）
CAND_COLOR_GROUP = {"侯友宜": 1, "賴清德": 2, "柯文哲": 5}


# ===================== 讀 color.txt =====================
def load_color_stops(path):
    """讀 color.txt（Python 串列字面）。忽略整行註解，取 '=' 之後做 literal_eval。

    回傳 6 組政黨色階；組別索引＝由上而下：0 無黨籍(灰) / 1 中國國民黨(藍) /
    2 民主進步黨(綠) / 3 新黨(黃) / 4 宋楚瑜(橘) / 5 台灣民眾黨(青綠)。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    rhs = "\n".join(lines).split("=", 1)[1]
    return ast.literal_eval(rhs)


_ALL_STOPS = load_color_stops(COLOR_TXT)
# 依 CAND_NAMES 順序挑出各候選人所屬政黨色階組
RATE_COLOR_STOPS = [_ALL_STOPS[CAND_COLOR_GROUP[nm]] for nm in CAND_NAMES]

# ===================== 繪圖與填色常數 =====================
NO_DATA_COLOR = "#FFFFFF"   # 無資料/空白地區一律純白
DPI = 100
PX2PT = 72.0 / DPI

# 平票規則：第 1 名與第 2 名得票率同至小數點後 3 位（或得票數相同）→ 疊加斜線紋
TIE_RATE_EPS = 1e-9
TIE_STRIPE_PX = 8           # 平票斜線紋每條寬度（px）

MIN_SIMILARITY = 0.5

# ---------------------- 異體字正規化 ----------------------
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',
    '\U00025562': '槽',   # 坪林區石𕢥里（2024 源資料） / 石槽
    '磘': '窯',
    '獇': '羌',
    '舘': '館',
    '廍': '部',
    '峯': '峰',
    '脚': '腳',
    '\ue006': '塭',      # 臺南安南區 塭南里 / 公(塭)里（中選會以私用區字形 U+E006 表示「塭」）
    '\U00026c21': '那',  # 臺南新化區 𦰡拔里 / 那拔里
    '売': '壳',           # 臺中大安區 龜売里 / 龜壳里
    '欍': '春',           # 雲林水林鄉 欍埔村 / 春埔村
})

VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"}, {"舘", "館"}, {"磘", "窯"}, {"獇", "羌"}, {"曹", "槽"}, {"脚", "腳"},
]


def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s


def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))


def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))


def get_color_by_value(val, stops):
    if val is None or np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _char_pairs(a, b):
    pairs = []
    la, lb = len(a), len(b)
    if la != lb:
        return None
    for ca, cb in zip(a, b):
        pairs.append((ca, cb))
    return pairs


def is_variant_fuzzy(a, b):
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    for group in VARIANT_FUZZY_GROUPS:
        if ca in group and cb in group:
            return True
    return False


def fuzzy_lookup(county, town, vill, by_key, by_town):
    if not town or not vill:
        return None, None, "none"
    key = (county, town, vill)
    if key in by_key:
        return vill, by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get((county, town), []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, None, "none"
    if not is_variant_fuzzy(vill, best_v):
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"


# ===================== 讀取得票率 Excel（全臺單一檔） =====================
def load_vote_data(data_dir):
    """讀取 2024 全臺單一 Excel（工作表「各里彙總」）。

    得票率欄位依 CAND_NAMES 順序：侯友宜得票率、賴清德得票率、柯文哲得票率。
    源資料有時將多村里合併為一列（以 、 分隔，如連江縣「復興村、福沃村」），
    拆解成各村(里)並共用同一組得票率，使多村合併地區能填入相同顏色。

    回傳 (by_key, by_town, n_rows, n_total)：
      by_key : (county, town, vill) -> (rate侯, rate賴, rate柯)
      by_town: (county, town) -> [(vill, vals), ...]
    """
    by_key, by_town = {}, {}
    n_total, n_rows = 0, 0
    xlsx = os.path.join(data_dir, os.path.basename(VOTE_XLSX))
    df = pd.read_excel(xlsx, sheet_name=VOTE_SHEET, dtype=str)
    df.columns = [str(c) for c in df.columns]
    rate_cols = []
    for h in RATE_HEADERS:
        if h not in df.columns:
            raise ValueError(f"{os.path.basename(xlsx)} 缺少得票率欄位：{h}")
        rate_cols.append(h)
    for _, r in df.iterrows():
        county = normalize_text(r.get("選舉區別"))
        town = strip_town_suffix(r.get("鄉(鎮、市、區)別"))
        vill_raw = normalize_text(r.get("村里別"))
        if not county or not town or not vill_raw:
            continue
        try:
            vals = tuple(float(str(r[c]).strip().replace("%", "").replace("\u00a0", ""))
                         for c in rate_cols)
        except (TypeError, ValueError):
            continue
        if not all(np.isfinite(v) for v in vals):
            continue
        n_total += 1
        parts = [p for p in re.split(r"[、，,]", vill_raw) if p.strip()]
        for part in parts:
            part_core = strip_village_suffix(part.strip())
            if not part_core:
                continue
            key = (county, town, part_core)
            if key in by_key:
                continue
            by_key[key] = vals
            by_town.setdefault((county, town), []).append((part_core, vals))
            n_rows += 1
    return by_key, by_town, n_rows, n_total


# ===================== 填色：油漆桶／洪水填充（共用） =====================
def flood_fill_layer(records, lines_mask, w_px, h_px, minx, maxy, sx, sy):
    """油漆桶式填色（畫圖軟體「填充／洪水填充」規則），各分區地圖共用。

    1) 堤壩 = 線稿 lines_mask（村里界 1px、鄉鎮市區界、縣市地界 …）。
    2) 對堤壩以外的像素做 4-連通標記：1px 斜線也能阻斷 8 連通的斜向滲漏，
       故顏色不可能跨越任何一條黑線。
    3) 每個區域整塊填單色，顏色 = 區域內像素「中心點幾何所屬圖斑 id」的眾數。

    回傳 (arr, ncomp, comp)：arr 為填色後 RGB uint8 陣列（尚未畫黑線）；
    ncomp/comp 為非線像素的 4-連通標記，供自檢重用避免重算。"""
    from rasterio.features import rasterize
    from affine import Affine

    # 顏色查找表：id 0 = 無資料（白），id i+1 = 第 i 個圖斑的填色
    lut = np.vstack([
        np.array([[255, 255, 255]], dtype=np.uint8),
        np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                  for hx in records["fill_hex"]], dtype=np.uint8),
    ])

    # 逐像素幾何判定（GDAL/rasterio 像素中心規則）：id = 圖斑序號 + 1，0 = 無圖斑
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)

    free = ~lines_mask
    ncomp, comp = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)

    seed = np.zeros(ncomp, dtype=np.int32)
    seed[comp.ravel()] = ids.ravel()
    reps = seed[comp]
    agree = (ids == reps)
    cnt_all = np.bincount(comp.ravel(), minlength=ncomp)
    cnt_ok = np.bincount(comp.ravel(), weights=agree.ravel(), minlength=ncomp)
    del reps, agree
    bad = np.nonzero(cnt_ok < 0.5 * cnt_all)[0]
    for b in bad:
        m = (comp == b)
        seed[b] = int(np.bincount(ids[m].ravel()).argmax())
    if len(bad):
        print(f"    洪水填充：{len(bad)} 個區域取樣不一致 → 已精算眾數")

    arr = lut[seed[comp]].astype(np.uint8)
    del ids, seed
    return arr, ncomp, comp


def check_region_single_color(arr, ncomp, comp):
    """油漆桶不變式自檢：每個非線 4-連通區域必須只含單一顏色（色不越過黑線）。"""
    from scipy import ndimage
    c = (arr[..., 0].astype(np.int32) << 16) | \
        (arr[..., 1].astype(np.int32) << 8) | arr[..., 2].astype(np.int32)
    idx = np.arange(1, ncomp)
    mn = ndimage.minimum(c, comp, index=idx)
    mx = ndimage.maximum(c, comp, index=idx)
    return ncomp - 1, int((mn != mx).sum())


def apply_tie_stripes(arr, records, w_px, h_px, minx, maxy, sx, sy,
                      lines_mask=None, stripe_px=TIE_STRIPE_PX):
    """平票圖斑：把「第 2 名應填色」以 45° 對角斜線紋疊在基底色上。

    條紋方向 45°（右下→左上），每條寬 stripe_px；只覆寫 records["tie_hex"]
    非空的圖斑。村里界線一律保留、不被斜線覆蓋，故界線維持完整：
    有 lines_mask（權威界線掩碼）時以 ~lines_mask 排除，否則退回純黑像素判斷。
    records 無 tie_hex 欄（或全空）時不動作，回傳處理的圖斑數。"""
    if "tie_hex" not in records.columns:
        return 0
    from rasterio.features import rasterize
    from affine import Affine
    tie = records[records["tie_hex"].notna()]
    if len(tie) == 0:
        return 0
    tids = rasterize(((g, i + 1) for i, g in enumerate(tie.geometry)),
                     out_shape=(h_px, w_px),
                     transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                     fill=0, dtype="int32", all_touched=False)
    yy, xx = np.indices((h_px, w_px))
    stripe = ((xx + yy) // stripe_px) % 2 == 1

    if lines_mask is not None:
        fillable = ~np.asarray(lines_mask, dtype=bool)
    else:
        fillable = arr.any(axis=2)

    m = (tids > 0) & stripe & fillable
    lut = {}
    for hx in tie["tie_hex"]:
        if hx not in lut:
            lut[hx] = [int(round(v * 255)) for v in hex2rgb(hx)]
    vals = np.array([lut[hx] for hx in tie["tie_hex"]], dtype=np.uint8)
    arr[m] = vals[tids[m] - 1]
    print(f"    平票斜線紋：{len(tie)} 個村里圖斑")
    return len(tie)


def full_geom_check(img, records, w_px, h_px, minx, maxy, sx, sy,
                    lines_mask=None):
    """全圖逐像素幾何參考比對（獨立方法：GDAL/rasterio 像素中心規則）。

    黑線像素不計。回傳 (與幾何參考不同色的像素數, 無圖斑處非白的像素數)。"""
    from rasterio.features import rasterize
    from affine import Affine
    ids = rasterize(((g, i + 1) for i, g in enumerate(records.geometry)),
                    out_shape=(h_px, w_px),
                    transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                    fill=0, dtype="int32", all_touched=False)
    fill = np.array([[int(round(v * 255)) for v in hex2rgb(hx)]
                     for hx in records["fill_hex"]], dtype=np.uint8)
    exp = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    inside = ids > 0
    exp[inside] = fill[ids[inside] - 1]
    # 平票斜線紋：期望圖同步疊加（與 apply_tie_stripes 同一套條紋規則）
    if "tie_hex" in records.columns:
        tie = records[records["tie_hex"].notna()]
        if len(tie):
            tids = rasterize(((g, i + 1) for i, g in enumerate(tie.geometry)),
                             out_shape=(h_px, w_px),
                             transform=Affine(1.0 / sx, 0, minx, 0, -1.0 / sy, maxy),
                             fill=0, dtype="int32", all_touched=False)
            yy, xx = np.indices((h_px, w_px))
            m = (tids > 0) & (((xx + yy) // TIE_STRIPE_PX) % 2 == 1)
            if lines_mask is not None:
                m &= ~np.asarray(lines_mask, dtype=bool)
            tl = {}
            for hx in tie["tie_hex"]:
                if hx not in tl:
                    tl[hx] = [int(round(v * 255)) for v in hex2rgb(hx)]
            tvals = np.array([tl[hx] for hx in tie["tie_hex"]], dtype=np.uint8)
            exp[m] = tvals[tids[m] - 1]
    black = img.sum(axis=2) == 0
    wrong = (img != exp).any(axis=2) & ~black
    return int(wrong.sum()), int((wrong & ~inside).sum())


# ===================== 無資料/未匹配村里清單（Markdown 稽核報告） =====================
def write_missing_report(gdf_all, vote_dict, out_path, target_counties,
                         title, base_label="", vote_label=""):
    """把「村里圖斑 ↔ 得票資料」比對結果寫成 Markdown（供人工核對）。

    內容對應 2012 版 Draw_*_2012 的稽核段落（去除 2012 專屬的名稱修復／沿革合併）：
      ① 地圖上有村里圖斑、卻對不上得票資料者（圖上留白）
      ② 模糊匹配（異體字／近似）
      ③ 得票資料有、底圖卻無對應村里圖斑者（反向缺漏）
      ④ 各縣市比對統計

    gdf_all 需含 COUNTYNAME/TOWNNAME/VILLNAME、county_core/town_core/vill_core、
    match_type；②③ 段另需 matched_vill（缺欄位時自動略過對應內容）。
    vote_dict 鍵為 (county_core, town_core, vill_core)。
    """
    mt = gdf_all["match_type"].fillna("none").astype(str)
    mv = (gdf_all["matched_vill"].fillna("").astype(str)
          if "matched_vill" in gdf_all.columns
          else pd.Series([""] * len(gdf_all), index=gdf_all.index))
    exact_n = int((mt == "exact").sum())
    none_df = gdf_all[mt == "none"].sort_values(["COUNTYNAME", "TOWNNAME", "VILLNAME"])
    fuzzy_df = gdf_all[mt.str.startswith("fuzzy")].sort_values(
        ["COUNTYNAME", "TOWNNAME", "VILLNAME"])

    # 反向缺漏：本區縣市的得票資料、卻沒有任何圖斑配對到它
    used = {(c, t, v) for c, t, v in
            zip(gdf_all["county_core"], gdf_all["town_core"], mv) if v}
    tgt = set(target_counties)
    orphan = sorted(k for k in vote_dict if k[0] in tgt and k not in used)

    L = [title, ""]
    L.append(f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    if base_label:
        L.append(f"- 底圖：{base_label} → 本區 {len(gdf_all)} 個村里圖斑")
    else:
        L.append(f"- 本區村里圖斑：{len(gdf_all)} 個")
    if vote_label:
        L.append(f"- 得票資料：{vote_label}")
    L.append(f"- 匹配結果：精確 **{exact_n}**、模糊 **{len(fuzzy_df)}**、"
             f"無資料 **{len(none_df)}**（圖上留白）")

    L += ["", "## 1. 地圖上有村里圖斑、但對不上得票資料", ""]
    if len(none_df):
        L += [f"共 **{len(none_df)}** 筆 → 地圖上留白。", "",
              "| # | 縣市 | 鄉鎮市區 | 村里 |", "|---:|---|---|---|"]
        L += [f"| {i} | {r['COUNTYNAME']} | {r['TOWNNAME']} | {r['VILLNAME']} |"
              for i, (_, r) in enumerate(none_df.iterrows(), 1)]
        L += ["", "### 依縣市統計", "", "| 縣市 | 無資料村里數 |", "|---|---:|"]
        L += [f"| {c} | {int(n)} |"
              for c, n in none_df.groupby("COUNTYNAME").size().items()]
    else:
        L.append("（無）")

    L += ["", "## 2. 模糊匹配（異體字／近似）", ""]
    if len(fuzzy_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 底圖村里 | 對應得票資料村里 | 匹配方式 |",
              "|---:|---|---|---|---|---|"]
        for i, (idx, r) in enumerate(fuzzy_df.iterrows(), 1):
            L.append(f"| {i} | {r['COUNTYNAME']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
                     f"{mv.loc[idx]} | {r['match_type']} |")
    else:
        L.append("（無）")

    L += ["", "## 3. 得票資料有、底圖卻無對應村里圖斑", ""]
    if orphan:
        L += [f"共 **{len(orphan)}** 筆（本區縣市的得票資料未被任何圖斑配對到）。", "",
              "| # | 縣市 | 鄉鎮市區 | 村里（得票資料） |", "|---:|---|---|---|"]
        L += [f"| {i} | {c} | {t} | {v} |" for i, (c, t, v) in enumerate(orphan, 1)]
    else:
        L.append("（無）")

    L += ["", "## 4. 各縣市比對統計", "",
          "| 縣市 | 村里圖斑 | 精確 | 模糊 | 無資料 |", "|---|---:|---:|---:|---:|"]
    for c in target_counties:
        s = gdf_all[gdf_all["COUNTYNAME"] == c]
        if not len(s):
            continue
        smt = s["match_type"].fillna("none").astype(str)
        L.append(f"| {c} | {len(s)} | {int((smt == 'exact').sum())} | "
                 f"{int(smt.str.startswith('fuzzy').sum())} | {int((smt == 'none').sum())} |")
    L.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  ③ 無資料/未匹配清單：{out_path}")
    print(f"     無資料 {len(none_df)}、模糊 {len(fuzzy_df)}、反向缺漏 {len(orphan)}")
