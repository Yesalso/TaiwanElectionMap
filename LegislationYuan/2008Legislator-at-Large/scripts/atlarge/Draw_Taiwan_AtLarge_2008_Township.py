# -*- coding: utf-8 -*-
"""
全臺灣（本島＋澎湖＋金門＋馬祖）
2008 第七屆立法委員全國不分區及僑居國外國民選舉
**鄉鎮市區版** —— 填色單位＝鄉（鎮、市、區），全圖不畫村里界

底圖（2026-11-03 使用者指定：以**民國 106 年（2017）地圖**為基礎）：
    全臺 22 縣市 → `VILLAGE_MOI_1070205.shp`（民國106年村里界，檔名 1070205）
        —— 即主圖（村里版）金門／連江的拼接來源，本版整張圖都改用它：
        逐鄉鎮市區 dissolve（`load_shp_base` 保留無村里名礁石圖斑以撐面積），
        368 個鄉鎮市區一次到位（**含烏坵鄉**、龜山島也在 106 年圖資內，無需任何補漏）。
        （村里版底圖＝2012 json＋嘉義市 pre2010＋金馬 106 SHP 拼接；鄉鎮版不需
          村里細分線，直接以 106 年 SHP 一套到底，底圖來源單一、無拼接縫。）
        **未編定村里**：106 年 SHP 高雄市 9 塊／臺中市 5 塊 NOTE＝「未編定村里」
        的無名圖斑（機場、港區…）原被 drop_nan_village_parts 剔除 → 圖上白缺。
        2026-11-03 使用者指定**只併回兩塊**：66000120S02（臺中市，原掛清水區）
        → 歸 **梧棲區**；64000190S01（岡山區）→ 維持 **岡山區**；
        其餘未編定圖斑照舊剔除（reattach_unassigned_villages）。
得票：`Data/2008不分区`（中選會原始 xls）**逐村（里）累加到鄉鎮市區**：
        鄉鎮得票率＝轄內各村得票數逐黨合計 ÷ 該鄉鎮有效票數合計 × 100，
        取領先政黨依得票率選色階深淺（色階來源 `LegislationYuan/color.txt`，同村里版）。
        資料側沿用村里版全部改名機制（TOWN_VILL_RENAME_2008：高雄縣三民鄉→
        高雄市那瑪夏區 等），再以「去尾綴＋異體字收斂」對位鄉鎮市區。

版面（**與村里版完全一致** —— 金門／馬祖擺放位置不變）：
    沿用 `layout_insets`：臺灣本島＋澎湖依真實位置為主圖；**連江框在主圖左上角，
    金門框嵌在連江框右下角（右緣、底緣與連江框共邊，L 形嵌合）**；
    烏坵鄉以 2px 虛線小方框嵌在金門框右下角。附圖倍率以 1.6× 為上限、
    自動逐級下降避讓本島／澎湖（淨空 250m），與村里版同一函式、同一參數，
    故金門／馬祖在圖上的位置、大小與村里版完全相同。

線稿（鄉鎮市區版＝村里版去掉村里界層）：
    - **不畫村里界**
    - 鄉鎮市區界 2px（小島縣市只畫內部鄉鎮界、不描外緣，同村里版）
    - 縣市界 6px（只畫內陸交界；compute_county_boundary 原樣沿用）
    - 海岸線 1px：本島＝縣市聯集外輪廓、澎湖／金門／連江＝縣市聯集邊界
      （**村里版沒有 1px 海岸線層時由村里界層兼任；鄉鎮版不畫村里界，
        故另以 render_thin_coast_layer 補上離島外緣**，兩者皆
        「1px 直繪 → thin 中心線」，與村里版金馬畫法完全相同）
    - 附圖外框 6px、烏坵框 2px —— **一律黑線**（2026-11-03 使用者指定：
      金門／馬祖附圖方框改黑線，與其他界線區隔；`render_inset_box_mask`
      與 ② 層同一 matplotlib 畫法，像素對齊後在最後改上純黑）
    - 其餘所有界線一律 #FCFCFC（LINE_COLOR，同村里版：先以純黑成像取遮罩，
      最後才上色為近白）
畫布：長寬上限 **5000 × 6250 px**（＝村里版 10000 × 12500 的一半；
      實際輸出約 4539 × 6250）。

自檢：油漆桶不變式、逐像素幾何參考（rasterio 獨立方法）、全圖只含允許色、
      金門／連江無名礁石必須全部畫出（check_reef_drawn）、縣市界稽核表。

輸出：LegislationYuan/maps/全臺灣2008年立法委員不分區選舉_政黨票得票率地圖_鄉鎮市區版.png
      LegislationYuan/maps/全臺灣2008_鄉鎮市區版_稽核.md
執行：py scripts/atlarge/Draw_Taiwan_AtLarge_2008_Township.py
      加 --test 只畫 澎湖／金門／連江（快速核對線寬與版面）。
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 村里版全模組：資料讀取、底圖載入、版面、界線繪製、自檢全部重用
import Draw_Taiwan_AtLarge_2008 as base
import Draw_National_President_2020 as nat

OUT_PNG = os.path.join(base.OUT_DIR,
                       "全臺灣2008年立法委員不分區選舉_政黨票得票率地圖_鄉鎮市區版.png")
TEST_OUT_PNG = os.path.join(base.OUT_DIR,
                            "全臺灣2008_離島測試_澎湖金門馬祖_鄉鎮市區版.png")
AUDIT_MD = os.path.join(base.OUT_DIR, "全臺灣2008_鄉鎮市區版_稽核.md")

# 畫布減半（村里版 10000 × 12500 → 鄉鎮版 5000 × 6250）
MAX_W_PX = 5000
MAX_H_PX = 6250
METERS_PER_PIXEL = base.METERS_PER_PIXEL   # 比例尺下限同村里版（不會生效，
                                           #   實際由畫布上限決定 ≈105 m/px）

# 2008 縣市（OLD_COUNTY）→ 得票資料側縣市名（2010 五都合併後名，FILENAME_COUNTY 同）
#   - 五都：臺中市/臺中縣 → 資料側都掛在「臺中市」下（FILENAME_COUNTY 同）
#   - RENAME_2008 是「新名 → 舊名」，這裡要反向：臺北縣 → 新北市
DATA_COUNTY_OF = {v: k for k, (_c1, _c2) in base.SPLIT_COUNTY.items()
                  for v in (_c1, _c2)}
for _new, _old in base.RENAME_2008.items():
    DATA_COUNTY_OF[_old] = _new


def aggregate_town_votes(cnt_by_key):
    """把逐村（里）得票數（末位＝有效票數）累加到鄉鎮市區層級。

    鍵＝(資料側縣市, 鄉鎮)；逐黨累加後由呼叫端重算得票率
    （＝「先加總再算率」，非「率平均」）。
    ⚠️ cnt_by_key 的鄉鎮名在 load_party_votes 內已 norm_town 過一次
    （去尾綴＋異體收斂），這裡**不得再 norm_town 第二次**——否則
    「前鎮→前、平鎮→平、新市→新」之類尾字恰為 鎮/市/區 的名稱會被誤剝。
    """
    town_tot = {}
    for (c, t, _v), a in cnt_by_key.items():
        k = (base.norm_county(c), t)
        cur = town_tot.get(k)
        if cur is None:
            town_tot[k] = list(a)
        else:
            for i in range(len(a)):
                cur[i] += a[i]
    return town_tot


def assign_town_colors(towns, town_tot):
    """每個鄉鎮市區：得票率＝各村合計 ÷ 有效票合計 → 領先政黨色階（依率選深淺）。

    對不上資料的鄉鎮留白（NO_DATA_COLOR），逐筆回傳供稽核。
    """
    rate_cols = [f"rate{i}" for i in range(len(base.PARTIES))]
    n = len(towns)
    rate_arr = np.full((n, len(base.PARTIES)), np.nan)
    fills = [base.NO_DATA_COLOR] * n
    wins = [""] * n
    miss = []
    towns = towns.copy().reset_index(drop=True)
    for pos in range(n):
        oc, tn = towns.at[pos, "OLD_COUNTY"], towns.at[pos, "TOWNNAME"]
        k = (DATA_COUNTY_OF.get(oc, oc), base.norm_town(tn))
        tot = town_tot.get(k)
        if tot is None or tot[-1] <= 0:
            miss.append((oc, tn))
            continue
        rates = [v / tot[-1] * 100.0 for v in tot[:-1]]
        j = int(np.argmax(rates))
        col = nat.get_color_by_value(rates[j], base.PARTY_STOPS[base.PARTIES[j]])
        fills[pos] = col or base.NO_DATA_COLOR
        wins[pos] = base.PARTIES[j]
        rate_arr[pos] = rates
    for kk, rc in enumerate(rate_cols):
        towns[rc] = rate_arr[:, kk]
    towns["fill_hex"] = fills
    towns["win_party"] = wins
    return towns, miss


def write_audit_md(towns, miss, orphan, town_tot, md_path):
    """鄉鎮市區版稽核報告：對位結果、無資料／孤兒鄉鎮、各縣市領先統計。"""
    has = towns["win_party"].astype(str) != ""
    L = ["# 全臺灣 2008 立法委員不分區（政黨票）得票率地圖 — 鄉鎮市區版稽核", ""]
    L += [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
          "- 底圖：**民國106年（1070205）村里界 SHP** 逐鄉鎮市區 dissolve"
          f" → 本圖 {len(towns)} 個鄉鎮市區",
          "- 得票資料：`Data/2008不分区`（中選會原始 xls）→ 逐村（里）累加到"
          f"鄉鎮市區 → 資料側 {len(town_tot)} 個鄉鎮市區",
          f"- 對位結果：有資料 **{int(has.sum())}**、無資料 **{len(miss)}**（圖上留白）",
          f"- 資料側孤兒鄉鎮（地圖無對應）：**{len(orphan)}**", ""]
    if miss:
        L += ["## 1. 地圖上有鄉鎮市區、但對不上得票資料（留白）", "",
              "| # | 縣市（2008） | 鄉鎮市區 |", "|---:|---|---|"]
        L += [f"| {i} | {c} | {t} |" for i, (c, t) in enumerate(miss, 1)]
        L.append("")
    if orphan:
        L += ["## 2. 得票資料有、地圖無對應鄉鎮市區", "",
              "| # | 縣市（資料側） | 鄉鎮市區 |", "|---:|---|---|"]
        L += [f"| {i} | {c} | {t} |" for i, (c, t) in enumerate(sorted(orphan), 1)]
        L.append("")
    L += ["## 3. 各縣市（2008）領先政黨統計（鄉鎮市區數）", "",
          "| 縣市 | 鄉鎮市區 | " + " | ".join(base.PARTIES) + " |",
          "|---|---:|" + "---:|" * len(base.PARTIES)]
    for c, sub in towns[has].groupby("OLD_COUNTY"):
        wc = sub["win_party"].value_counts()
        row = [str(int(wc.get(p, 0))) for p in base.PARTIES]
        L.append(f"| {c} | {len(sub)} | " + " | ".join(row) + " |")
    L.append("")
    L += ["## 4. 領先得票率範圍", ""]
    if has.any():
        rmax = towns.loc[has, [f"rate{i}" for i in range(len(base.PARTIES))]]
        lead = rmax.max(axis=1)
        L += [f"- 最低領先得票率 {lead.min():.2f}%、最高 {lead.max():.2f}%", ""]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  鄉鎮市區版稽核報告：{md_path}")


# 「未編定村里」圖斑只處理使用者指定的兩塊（2026-11-03），其餘維持剔除：
#   66000120S02  臺中市（原掛 清水區）  → **梧棲區**
#   64000190S01  高雄市（原掛 岡山區）  → **岡山區**（原屬不變，僅併回）
UNASSIGNED_REATTACH = {
    "66000120S02": ("臺中市", "梧棲區"),
    "64000190S01": ("高雄市", "岡山區"),
}


def reattach_unassigned_villages(gdf, path=base.SHP_106):
    """把使用者指定的「未編定村里」圖斑（VILLCODE S 尾碼、無村里名）併回底圖。

    106 年 SHP（1070205）中 高雄市 9 塊、臺中市 5 塊 VILLNAME 為空、
    NOTE＝「未編定村里」的圖斑（岡山機場、臺中港、高雄港區…），
    `base.load_shp_base()` 內 `drop_nan_village_parts` 會把它們當港區碎塊
    全數剔除 → 圖上出現白色缺口。**僅併回下列兩塊**（2026-11-03 使用者指定）：

        66000120S02  臺中市，原掛 清水區（7.13 km²）→ 改歸 **梧棲區**
        64000190S01  高雄市，原掛 岡山區（3.13 km²）→ 維持 **岡山區**

    其餘未編定圖斑照舊剔除、不予處理。併回後隨 dissolve 併入該鄉鎮市區，
    得票沿用該鄉鎮資料，缺口補滿。
    """
    raw = None
    for enc in ("utf-8", "cp950"):
        try:
            raw = gpd.read_file(path, encoding=enc)
            break
        except UnicodeDecodeError as e:
            err = e
    if raw is None:
        raise err
    raw = raw[raw["VILLCODE"].isin(UNASSIGNED_REATTACH)].copy()
    if raw.crs is None:
        raw = raw.set_crs("EPSG:4326")
    raw = raw.to_crs(base.TARGET_CRS)
    raw["geometry"] = raw.geometry.buffer(0)
    raw = raw[~raw.geometry.isna() & ~raw.geometry.is_empty]
    if not len(raw):
        print(f"  未編定村里圖斑：SHP 中找不到 {sorted(UNASSIGNED_REATTACH)}，無需併回")
        return gdf
    raw["TOWNNAME"] = raw["VILLCODE"].map(
        lambda v: UNASSIGNED_REATTACH[v][1])
    raw["COUNTYNAME"] = raw["VILLCODE"].map(
        lambda v: UNASSIGNED_REATTACH[v][0])
    raw["VILLNAME"] = ""
    print(f"  未編定村里圖斑：併回 {len(raw)} 塊 → "
          + "、".join(f"{r['COUNTYNAME']}{r['TOWNNAME']}"
                      f"（{r['VILLCODE']}，{r.geometry.area / 1e6:.2f} km²）"
                      for _, r in raw.iterrows()))
    cols = ["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry"]
    out = pd.concat([gdf[cols], raw[cols]], ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def strip_far_parts_by_part(gdf, max_km=base.FAR_PART_MAX_KM):
    """同 `base.strip_far_parts`（剔除距本島 > max_km 的東沙/南沙/釣魚台等碎塊），
    但改為**逐部件**剔除、不以「整列」為單位。

    為什麼必須改：106 年 SHP 中 **宜蘭縣頭城鎮大溪里是 101 部件的 MultiPolygon**
    ——1 塊 15.297 km² 的本島沿岸陸地 ＋ 100 塊釣魚台列嶼島礁（釣魚台行政上
    劃入頭城鎮大溪里）。村里版的整列剔除會把沿岸陸地陪葬 → 頭城東北角出現
    15.3 km² 的白色缺口。村里版無此問題（2012 json 不含釣魚台、106 SHP 只用於
    金馬且不參與此清理）；鄉鎮版全圖使用 106 SHP，必須逐部件處理：
    只剔遠島部件，近岸部件以原屬性保留；整列全為遠島者整列剔除。
    """
    cover = ~gdf["COUNTYNAME"].isin(base.EXCLUDE_INSET)
    sub = gdf[cover]
    parts = [pp for geom in sub.geometry
             for pp in (list(geom.geoms) if hasattr(geom, "geoms") else [geom])]
    if len(parts) <= 1:
        return gdf
    merged = unary_union(parts)
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)
    keep_idx, new_geoms, n_far = [], [], 0
    for i, geom in sub.geometry.items():
        ps = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        near = [p for p in ps if main.distance(p) <= max_km * 1000.0]
        n_far += len(ps) - len(near)
        if not near:
            continue
        keep_idx.append(i)
        new_geoms.append(near[0] if len(near) == 1 else MultiPolygon(near))
    out = gdf.loc[keep_idx].copy()
    out["geometry"] = new_geoms
    out = gpd.GeoDataFrame(pd.concat([gdf[~cover], out], ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    if n_far:
        print(f"  離島碎塊清理（逐部件）：剔除 {n_far} 塊（距本島 > {max_km:.0f} km），"
              f"近岸部件全數保留；保留後圖斑 {len(out)} 筆")
    else:
        print(f"  離島碎塊清理（逐部件）：無需剔除（門檻 {max_km:.0f} km）")
    return out


def main():
    t0 = time.time()
    test_only = base._test_only(sys.argv)
    print("=" * 66)
    print("  全臺灣 2008 立法委員不分區（政黨票）鄉鎮市區得票率地圖"
          "　【底圖＝民國106年村里界 SHP】"
          + ("　【測試模式：只畫澎湖／金門／連江】" if test_only else ""))
    print("=" * 66)

    # ---- ① 得票資料：逐村（里）→ 鄉鎮市區合計 ----
    by_key, by_town, vote_display, cnt_by_key, n_total = base.load_party_votes()
    town_tot = aggregate_town_votes(cnt_by_key)
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(by_key)} 個村里 → "
          f"聚合為 {len(town_tot)} 個鄉鎮市區（資料側）；{len(base.PARTIES)} 個政黨")

    # ---- ② 底圖：民國106年（1070205）村里界 SHP，全臺一套 ----
    gdf = base.load_shp_base()
    gdf = reattach_unassigned_villages(gdf)
    gdf = base.add_old_county(gdf)
    print(f"  底圖（106 年 SHP）村里圖斑：{len(gdf)}；"
          f"2008 縣市：{gdf['OLD_COUNTY'].nunique()}")
    if test_only:
        print("  跨縣市重疊清理：測試模式略過（離島三縣市互不相鄰）")
    else:
        gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = strip_far_parts_by_part(gdf)
    if test_only:
        _m = gdf["COUNTYNAME"].isin(base.TEST_COUNTIES)
        print(f"  測試模式：只保留 {'、'.join(base.TEST_COUNTIES)} → "
              f"{int(_m.sum())} 個村里圖斑（原 {len(gdf)}）")
        gdf = gdf[_m].copy().reset_index(drop=True)

    # ---- ③ 版面：金馬附圖（與村里版同一函式 → 擺放位置完全一致） ----
    if test_only:
        gdf, boxes = base.layout_stack_all(gdf)
    else:
        gdf, boxes = base.layout_insets(gdf)

    # ---- ④ dissolve 到鄉鎮市區（附圖平移縮放之後） ----
    towns = gdf.dissolve(by=["OLD_COUNTY", "TOWNNAME"]).reset_index()
    towns = base.remove_ring_slits(towns)
    towns = base.clean_tiny_holes(towns)
    counties = gdf.dissolve(by=["OLD_COUNTY"]).reset_index()
    counties = base.remove_ring_slits(counties)
    counties = base.clean_tiny_holes(counties)
    print(f"  縣市（2008）：{len(counties)}、鄉鎮市區：{len(towns)}"
          f"（村里圖斑 {len(gdf)}）")

    # ---- ⑤ 鄉鎮市區對位與填色 ----
    towns, miss = assign_town_colors(towns, town_tot)
    map_keys = {(DATA_COUNTY_OF.get(r["OLD_COUNTY"], r["OLD_COUNTY"]),
                 base.norm_town(r["TOWNNAME"])) for _, r in towns.iterrows()}
    orphan = [k for k in town_tot if k not in map_keys]
    print(f"  鄉鎮市區對位：有資料 {int((towns['win_party'] != '').sum())}／"
          f"{len(towns)}；無資料 {len(miss)} {miss if miss else ''}；"
          f"資料側孤兒鄉鎮 {len(orphan)} {orphan[:5] if orphan else ''}")
    for p, n in towns.loc[towns["win_party"] != "", "win_party"] \
            .value_counts().items():
        print(f"    領先鄉鎮市區：{p} {int(n)}")
    write_audit_md(towns, miss, orphan, town_tot, AUDIT_MD)

    # ---- 畫布（長寬上限 5000 × 6250 px，為村里版一半） ----
    minx, miny, maxx, maxy = towns.total_bounds
    for _cn, (_bx0, _by0, _bx1, _by1), _lw in boxes:
        minx, miny = min(minx, _bx0), min(miny, _by0)
        maxx, maxy = max(maxx, _bx1), max(maxy, _by1)
    pad_x, pad_y = base.PAD_FRAC * (maxx - minx), base.PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w, geo_h = maxx - minx, maxy - miny
    scale = max(geo_w / MAX_W_PX, geo_h / MAX_H_PX, METERS_PER_PIXEL)
    w_px = int(np.ceil(geo_w / scale))
    h_px = int(np.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（上限 {MAX_W_PX}×{MAX_H_PX}，"
          f"{w_px * h_px / 1e6:.0f} 百萬像素）")

    # ---- ② 界線層：鄉鎮市區界 2px ＋ 縣市界 6px ＋ 附圖外框 ----
    _thick_cty, coast_geom, county_segs = base.compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g_.length for g_ in county_segs) / 1000:.0f} km）")
    base.audit_county_segments(counties, county_segs)
    print(f"  ② 鄉鎮市區界 {base.LINE_TOWNSHIP_PX}px ＋ 縣市界 "
          f"{base.LINE_COUNTY_INNER_PX}px ＋ 附圖外框 {base.LINE_INSET_BOX_PX}px"
          f"（matplotlib + 閾值二值化；澎湖／金門／連江本層不描外緣）…")
    # ② 層不畫附圖外框（boxes 傳空）——外框只由 render_inset_box_mask 單一成像，
    # 並在洪水填充前併入堤壩，最後改上黑線（避免兩處成像的亞像素錯位）
    town_layer = base.render_boundary_layer(towns, counties, county_segs, [],
                                            w_px, h_px, minx, maxx, miny, maxy)
    print(f"  界線層：{int(town_layer.sum())} px（閾值 {base.THRESHOLD_VAL}）")

    # ---- 附圖外框專用遮罩（金門／連江／烏坵框；唯一成像來源） ----
    print(f"  附圖外框遮罩（金門／連江／烏坵框；最後改上黑線，"
          f"其餘界線維持 {base.LINE_COLOR}）…")
    box_mask = base.render_inset_box_mask(boxes, w_px, h_px,
                                          minx, maxx, miny, maxy)
    print(f"  附圖外框遮罩：{int(box_mask.sum())} px")

    # ---- 海岸線 1px（本島 ＋ 澎湖金馬，金馬同款畫法） ----
    print(f"  海岸線 {base.LINE_COAST_PX}px（本島縣市聯集外輪廓；澎湖／金門／連江"
          f"＝縣市聯集邊界，1px 直繪 → thin 中心線，與村里版金馬同一畫法）…")
    coast_skel = base.render_main_coast_layer(coast_geom, w_px, h_px,
                                              minx, maxy, sx, sy)
    # 澎湖／金門／連江的外緣直接用「清理前」的村里級 gdf 聯集邊界：
    # dissolve 後的縣市層經 clean_tiny_holes 會把 <1 公頃的小礁石整塊丟掉
    # （村里版由村里界 1px 層兼任，鄉鎮版沒有那一層，必須在縣市層清理前取外緣）
    thin_skel = base.render_thin_coast_layer(gdf, w_px, h_px,
                                             minx, maxy, sx, sy)
    if thin_skel is None:                     # 測試模式無本島 → thin 層即全部
        thin_skel = np.zeros((h_px, w_px), dtype=bool)
    print(f"  海岸線層：本島 {int(coast_skel.sum())} px ＋ "
          f"澎湖金馬 {int(thin_skel.sum())} px")

    lines_mask = town_layer | coast_skel | thin_skel | box_mask
    del coast_skel, thin_skel

    # 自檢：金門／連江的無名礁石必須全部畫出（鄉鎮版不畫村里界，
    #       礁石外緣由「澎湖金馬海岸線 1px 層」負責）
    base.check_reef_drawn(gdf, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ---- 填色（洪水填充；填色單位＝鄉鎮市區） ----
    print("  填色（洪水填充／油漆桶規則，填色單位＝鄉鎮市區）…")
    records = towns[["OLD_COUNTY", "TOWNNAME", "fill_hex", "win_party"]
                    + [f"rate{i}" for i in range(len(base.PARTIES))]].copy()
    records = gpd.GeoDataFrame(records, geometry=towns.geometry.values,
                               crs=towns.crs)
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    arr[lines_mask] = np.array(base.LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0        # 附圖外框（金門／連江／烏坵框）＝黑線（使用者指定）
    print(f"  非線連通區域：{ncomp - 1} 塊；線色 {base.LINE_COLOR}、"
          f"附圖外框 黑 (0,0,0)")

    # ---- 自檢 ----
    _nc, _nbad = nat.check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")
    del comp
    _nw, _nout = nat.full_geom_check(arr, records, w_px, h_px, minx, maxy,
                                     sx, sy, lines_mask=lines_mask,
                                     ignore_mask=lines_mask)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%）；"
          f"圖斑外非白 {_nout} px（皆應 ≈0）")
    allowed = {(255, 255, 255), (0, 0, 0),
               tuple(int(v) for v in base.LINE_RGB)}
    for stops in base.PARTY_STOPS.values():
        for _u, hx in stops:
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
    out_png = TEST_OUT_PNG if test_only else OUT_PNG
    base.save_png(pil_img, out_png)
    W, H = pil_img.size
    del pil_img

    print(f"\n  Saved: {out_png}  ({W}×{H}px)")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== All finished ====")


if __name__ == "__main__":
    main()
