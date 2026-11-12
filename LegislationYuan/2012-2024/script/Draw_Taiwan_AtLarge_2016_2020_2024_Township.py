# -*- coding: utf-8 -*-
"""
全臺灣 2016／2020／2024 三屆立法委員全國不分區及僑居國外國民選舉
**鄉鎮市區版** —— 一次性生成三張全島圖
填色單位＝鄉（鎮、市、區），全圖不畫村里界

由 2012 版 `Draw_Taiwan_AtLarge_2012_Township.py` 移植（管線、版面、自檢全部重用），
逐年循環（同村里版 `Draw_Taiwan_AtLarge_2016_2020_2024.py` 只做「換屆差異」）：

1. 底圖＝逐年官方村里界歷史圖資 SHP（2016→民國106年 1070205、
   2020→108年 1081121、2024→111年 1111118）；「未編定村里」兩塊指定圖斑
   （臺中 清水區 66000120S02、高雄 岡山區 64000190S01）併回底圖後逐鄉鎮 dissolve；
   離島碎塊清理改**逐部件**剔除（106 年 SHP 頭城鎮大溪里含釣魚台 100 塊島礁，
   整列剔除會把沿岸陸地陪葬）。
2. 得票資料＝`data/不分区2016`、`data/不分区2020`、`data/不分区2024`
   （中選會原始表，解析器重用 yrs 模組）逐村（里）累加到鄉鎮市區；
   得票率＝「先加總再算率」。2016 起資料側縣市名與底圖同名 → DATA_COUNTY_OF 恆等。
3. 政黨與色階逐年動態建立（重用 yrs 模組的 monkey-patch 慣例）。

輸出（map/，每屆兩檔）：
  全臺灣{year}年立法委員不分區選舉_政黨票得票率地圖_鄉鎮市區版.png
  全臺灣{year}年立法委員不分區選舉_稽核報告.md（每屆一份，
    彙整 村里版／鄉鎮市區版／縣市版 三節，各節由對應腳本寫入）
執行：py script/Draw_Taiwan_AtLarge_2016_2020_2024_Township.py            # 三屆全跑
      py script/Draw_Taiwan_AtLarge_2016_2020_2024_Township.py 2016       # 只跑指定屆
      py script/Draw_Taiwan_AtLarge_2016_2020_2024_Township.py 2020 --test  # 只畫澎湖金門連江
"""
import os
import sys
import time
import math

import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

Image.MAX_IMAGE_PIXELS = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 管線重用：base＝2012 村里版全模組；yrs＝2016/2020/2024 資料讀取與逐年配置；
# t12＝2012 鄉鎮版（未編定村里併回、逐部件離島碎塊清理、鄉鎮聚合與填色函式）
import Draw_Taiwan_AtLarge_2012 as base
import Draw_Taiwan_AtLarge_2016_2020_2024 as yrs
import Draw_Taiwan_AtLarge_2012_Township as t12

nat = base.nat

OUT_DIR = base.OUT_DIR
TEST_COUNTIES = base.TEST_COUNTIES

# 畫布減半（村里版 10000 × 12500 → 鄉鎮版 5000 × 6250；同 2012 鄉鎮版）
MAX_W_PX = 5000
MAX_H_PX = 6250
METERS_PER_PIXEL = base.METERS_PER_PIXEL

# 2016 起資料側縣市名與底圖（逐年 SHP）同名 → 對照表恆等
DATA_COUNTY_OF = {}


def year_outputs(year):
    """逐年輸出路徑（正式圖／合併稽核報告；測試模式另存以免蓋掉正式圖）。"""
    return {
        "png": os.path.join(
            OUT_DIR,
            f"全臺灣{year}年立法委員不分區選舉_政黨票得票率地圖_鄉鎮市區版.png"),
        "report": audit_report_path(year),
        "test_png": os.path.join(
            OUT_DIR, f"全臺灣{year}_離島測試_澎湖金門馬祖_鄉鎮市區版.png"),
    }


# ===================== 每屆一份合併稽核報告 =====================
# 稽核報告每屆只有一個文檔（全臺灣{year}年…_稽核報告.md），彙整
# 村里版／鄉鎮市區版／縣市版 三節；各腳本只覆寫自己那一節，其餘節保留。
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


def build_town_audit_lines(year, towns, miss, orphan, town_tot):
    """鄉鎮市區版稽核內容（節內小節一律「### 」層級）：對位結果、
    無資料／孤兒鄉鎮、各縣市領先統計。"""
    has = towns["win_party"].astype(str) != ""
    L = [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         f"- 底圖：**{os.path.basename(yrs.YEAR_SHP[year])} 村里界 SHP**"
         f" 逐鄉鎮市區 dissolve → 本圖 {len(towns)} 個鄉鎮市區",
         f"- 得票資料：`{yrs.YEAR_DATA_GLOB[year]}`（中選會原始表）"
         f"→ 逐村（里）累加到鄉鎮市區 → 資料側 {len(town_tot)} 個鄉鎮市區",
         f"- 對位結果：有資料 **{int(has.sum())}**、無資料 **{len(miss)}**（圖上留白）",
         f"- 資料側孤兒鄉鎮（地圖無對應）：**{len(orphan)}**", ""]
    if miss:
        L += ["### 1. 地圖上有鄉鎮市區、但對不上得票資料（留白）", "",
              "| # | 縣市 | 鄉鎮市區 |", "|---:|---|---|"]
        L += [f"| {i} | {c} | {t} |" for i, (c, t) in enumerate(miss, 1)]
        L.append("")
    if orphan:
        L += ["### 2. 得票資料有、地圖無對應鄉鎮市區", "",
              "| # | 縣市（資料側） | 鄉鎮市區 |", "|---:|---|---|"]
        L += [f"| {i} | {c} | {t} |" for i, (c, t) in enumerate(sorted(orphan), 1)]
        L.append("")
    L += ["### 3. 各縣市領先政黨統計（鄉鎮市區數）", "",
          "| 縣市 | 鄉鎮市區 | " + " | ".join(base.PARTIES) + " |",
          "|---|---:|" + "---:|" * len(base.PARTIES)]
    for c, sub in towns[has].groupby("OLD_COUNTY"):
        wc = sub["win_party"].value_counts()
        row = [str(int(wc.get(p, 0))) for p in base.PARTIES]
        L.append(f"| {c} | {len(sub)} | " + " | ".join(row) + " |")
    L.append("")
    L += ["### 4. 領先得票率範圍", ""]
    if has.any():
        rmax = towns.loc[has, [f"rate{i}" for i in range(len(base.PARTIES))]]
        lead = rmax.max(axis=1)
        L += [f"- 最低領先得票率 {lead.min():.2f}%、最高 {lead.max():.2f}%", ""]
    return L


def run_year(year, test_only=False):
    t0 = time.time()
    yrs._CUR_YEAR[0] = year
    out = year_outputs(year)
    out_png = out["test_png"] if test_only else out["png"]

    print("=" * 66)
    print(f"  全臺灣 {year} 立法委員不分區（政黨票）鄉鎮市區得票率地圖"
          f"　【底圖＝{os.path.basename(yrs.YEAR_SHP[year])} 村里界 SHP】"
          + ("　【測試模式：只畫澎湖／金門／連江】" if test_only else ""))
    print("=" * 66)

    # ---- ① 得票資料：逐村（里）→ 鄉鎮市區合計 ----
    by_key, by_town, vote_display, cnt_by_key, n_total, parties = \
        yrs.load_raw_party_votes(yrs.YEAR_DATA_GLOB[year])
    if not parties:
        raise ValueError(f"{year} 未解析到任何政黨欄位")
    # monkey-patch：把逐年政黨表／色階餵給重用的填色函式（同 yrs 村里版慣例）
    base.PARTIES = parties
    base.PARTY_STOPS = yrs.make_stops(parties)
    town_tot = t12.aggregate_town_votes(cnt_by_key)
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(by_key)} 個村里 → "
          f"聚合為 {len(town_tot)} 個鄉鎮市區（資料側）；{len(parties)} 個政黨："
          + "、".join(parties))

    # ---- ② 底圖：逐年村里界 SHP，全臺一套 ----
    gdf = base._read_shp_base(yrs.YEAR_SHP[year])
    gdf = t12.reattach_unassigned_villages(gdf, path=yrs.YEAR_SHP[year])
    gdf = base.add_old_county(gdf)
    print(f"  底圖（{os.path.basename(yrs.YEAR_SHP[year])}）村里圖斑：{len(gdf)}；"
          f"縣市：{gdf['OLD_COUNTY'].nunique()}")
    if test_only:
        print("  跨縣市重疊清理：測試模式略過（離島三縣市互不相鄰）")
    else:
        gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = t12.strip_far_parts_by_part(gdf)
    if test_only:
        _m = gdf["COUNTYNAME"].isin(TEST_COUNTIES)
        print(f"  測試模式：只保留 {'、'.join(TEST_COUNTIES)} → "
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
    print(f"  縣市：{len(counties)}、鄉鎮市區：{len(towns)}"
          f"（村里圖斑 {len(gdf)}）")

    # ---- ⑤ 鄉鎮市區對位與填色 ----
    towns, miss = t12.assign_town_colors(towns, town_tot)
    map_keys = {(DATA_COUNTY_OF.get(r["OLD_COUNTY"], r["OLD_COUNTY"]),
                 base.norm_town(r["TOWNNAME"])) for _, r in towns.iterrows()}
    orphan = [k for k in town_tot if k not in map_keys]
    print(f"  鄉鎮市區對位：有資料 {int((towns['win_party'] != '').sum())}／"
          f"{len(towns)}；無資料 {len(miss)} {miss if miss else ''}；"
          f"資料側孤兒鄉鎮 {len(orphan)} {orphan[:5] if orphan else ''}")
    for p, n in towns.loc[towns["win_party"] != "", "win_party"] \
            .value_counts().items():
        print(f"    領先鄉鎮市區：{p} {int(n)}")
    write_audit_section(year, "鄉鎮市區版稽核",
                        build_town_audit_lines(year, towns, miss, orphan,
                                               town_tot))

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
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（上限 {MAX_W_PX}×{MAX_H_PX}，"
          f"{w_px * h_px / 1e6:.0f} 百萬像素）")

    # ---- ② 界線層：鄉鎮市區界 2px ＋ 縣市界 6px（附圖外框另成像） ----
    _thick_cty, coast_geom, county_segs = base.compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g_.length for g_ in county_segs) / 1000:.0f} km）")
    base.audit_county_segments(counties, county_segs)
    print(f"  ② 鄉鎮市區界 {base.LINE_TOWNSHIP_PX}px ＋ 縣市界 "
          f"{base.LINE_COUNTY_INNER_PX}px ＋ 附圖外框 {base.LINE_INSET_BOX_PX}px"
          f"（matplotlib + 閾值二值化；澎湖／金門／連江本層不描外緣）…")
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
          f"＝縣市聯集邊界，1px 直繪 → thin 中心線）…")
    coast_skel = base.render_main_coast_layer(coast_geom, w_px, h_px,
                                              minx, maxy, sx, sy)
    # 澎湖／金門／連江外緣用「清理前」的村里級 gdf 聯集邊界：
    # dissolve 後的縣市層經 clean_tiny_holes 會把 <1 公頃的小礁石整塊丟掉，
    # 鄉鎮版沒有村里界層，必須在縣市層清理前取外緣（同 2012 鄉鎮版作法）
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
    rate_cols = [f"rate{i}" for i in range(len(base.PARTIES))]
    records = towns[["OLD_COUNTY", "TOWNNAME", "fill_hex", "win_party"]
                    + rate_cols].copy()
    records = gpd.GeoDataFrame(records, geometry=towns.geometry.values,
                               crs=towns.crs)
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    arr[lines_mask] = np.array(base.LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0        # 附圖外框（金門／連江／烏坵框）＝黑線
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
    base.save_png(pil_img, out_png)
    W, H = pil_img.size
    del pil_img

    print(f"\n  Saved: {out_png}  ({W}×{H}px)")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print(f"==== {year} 鄉鎮市區版 finished ====")


def main():
    years, test_only = [], False
    for a in sys.argv[1:]:
        la = str(a).lower()
        if la in ("--test", "--only-islands", "-t"):
            test_only = True
        elif la.isdigit() and int(la) in yrs.YEAR_SHP:
            years.append(int(la))
    if not years:
        years = sorted(yrs.YEAR_SHP)
    for y in years:
        run_year(y, test_only=test_only)


if __name__ == "__main__":
    main()
