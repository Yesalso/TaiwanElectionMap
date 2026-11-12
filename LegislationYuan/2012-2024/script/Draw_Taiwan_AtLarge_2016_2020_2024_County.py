# -*- coding: utf-8 -*-
"""
全臺灣 2016／2020／2024 三屆立法委員全國不分區及僑居國外國民選舉
**縣市版** —— 一次性生成三張全島圖
填色單位＝縣市（22 個縣市），全圖只有 22 塊顏色，不畫鄉鎮界、不畫村里界

由 2012 版 `Draw_Taiwan_AtLarge_2012_County.py` 移植（管線、版面、自檢全部重用），
逐年循環：底圖＝逐年官方村里界歷史圖資 SHP（2016→106年 1070205、2020→108年
1081121、2024→111年 1111118）；得票資料＝`data/不分区{2016,2020,2024}`
（中選會原始表，解析器重用 yrs 模組）逐村（里）直接累加到縣市；
2016 起資料側縣市名與底圖同名 → old_county_of 恆等（無任何映射）。

輸出（map/，每屆兩檔）：
  全臺灣{year}年立法委員不分區選舉_政黨票得票率地圖_縣市版.png
  全臺灣{year}年立法委員不分區選舉_稽核報告.md（每屆一份，
    彙整 村里版／鄉鎮市區版／縣市版 三節，各節由對應腳本寫入）
執行：py script/Draw_Taiwan_AtLarge_2016_2020_2024_County.py            # 三屆全跑
      py script/Draw_Taiwan_AtLarge_2016_2020_2024_County.py 2016       # 只跑指定屆
"""
import os
import sys
import time
import math

import numpy as np
import geopandas as gpd
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon

Image.MAX_IMAGE_PIXELS = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 管線重用：base＝2012 村里版全模組；yrs＝2016/2020/2024 資料讀取與逐年配置；
# t12＝2012 鄉鎮版（未編定村里併回、逐部件離島碎塊清理——兩者與填色單位無關）；
# c12＝2012 縣市版（縣市聚合、填色、只清孔不砍部件的 clean_county_parts）
import Draw_Taiwan_AtLarge_2012 as base
import Draw_Taiwan_AtLarge_2016_2020_2024 as yrs
import Draw_Taiwan_AtLarge_2012_Township as t12
import Draw_Taiwan_AtLarge_2012_County as c12
# 鄉鎮市區版（2016~2024 一次性版）：合併稽核報告的寫入函式與報告路徑
import Draw_Taiwan_AtLarge_2016_2020_2024_Township as tn

nat = base.nat

OUT_DIR = base.OUT_DIR

# 畫布（鄉鎮版 5000 × 6250 的六成；同 2012 縣市版）
MAX_W_PX = 3000
MAX_H_PX = 3750
METERS_PER_PIXEL = base.METERS_PER_PIXEL

# 22 縣市（2010 五都合併＋2014/2015 桃園升格後；僅用於稽核表排序）
OFFICIAL_ORDER = [
    "臺北市", "新北市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "新竹縣",
    "桃園市", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣",
    "臺東縣", "花蓮縣", "宜蘭縣", "澎湖縣", "金門縣", "連江縣",
]
N_COUNTY = 22


def year_outputs(year):
    """逐年輸出路徑。"""
    return {
        "png": os.path.join(
            OUT_DIR,
            f"全臺灣{year}年立法委員不分區選舉_政黨票得票率地圖_縣市版.png"),
        "report": tn.audit_report_path(year),
    }


def build_county_audit_lines(year, counties, miss, orphan, town_set,
                             county_tot):
    """縣市版稽核內容（節內小節一律「### 」層級）：22 縣市得票率一覽、
    全國政黨合計、對位檢查。"""
    rate_cols = [f"rate{i}" for i in range(len(base.PARTIES))]
    has = counties["win_party"].astype(str) != ""
    order = {c: i for i, c in enumerate(OFFICIAL_ORDER)}
    rows = counties.assign(_o=counties["OLD_COUNTY"].map(
        lambda c: order.get(c, 999))).sort_values(["_o", "OLD_COUNTY"])
    # 兩大黨欄位（2016/2020/2024 政黨表皆含；若缺則跳過該欄）
    has_kmt = "中國國民黨" in base.PARTIES
    has_dpp = "民主進步黨" in base.PARTIES
    ik = base.PARTIES.index("中國國民黨") if has_kmt else None
    idk = base.PARTIES.index("民主進步黨") if has_dpp else None

    L = [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         "- 填色單位：**縣市**，全圖只有 22 塊顏色",
         f"- 底圖：**{os.path.basename(yrs.YEAR_SHP[year])} 村里界 SHP**"
         " → 逐村里 dissolve 到縣市"
         f" → 本圖 {len(counties)} 個縣市",
         f"- 得票資料：`{yrs.YEAR_DATA_GLOB[year]}`（中選會原始表）"
         "→ 逐村（里）**直接累加**到縣市"
         f" → 資料側 {len(county_tot)} 個縣市",
         f"- 對位結果：有資料 **{int(has.sum())}**、無資料 **{len(miss)}**（圖上留白）",
         f"- 資料側孤兒縣市（地圖無對應）：**{len(orphan)}**"
         f"{'：' + '、'.join(orphan) if orphan else ''}", ""]

    if len(counties) != N_COUNTY:
        L += [f"> ⚠️ **填色單位為 {len(counties)} 個，不是 22 個**，請檢查底圖縣市名。", ""]

    L += ["### 1. 22 縣市得票一覽（依中選會公告順序）", "",
          "| # | 縣市 | 鄉鎮市區 | 有效票 | "
          + ("中國國民黨 % | " if has_kmt else "")
          + ("民主進步黨 % | " if has_dpp else "")
          + "領先政黨 | 領先得票率 | 色碼 |",
          "|---:|---|---:|---:|" + ("---:|" if has_kmt else "")
          + ("---:|" if has_dpp else "") + "---|---:|---|"]
    for i, (_, r) in enumerate(rows.iterrows(), 1):
        lead = max(r[rc] for rc in rate_cols) if str(r["win_party"]) != "" else None
        cells = [f"{i}", r["OLD_COUNTY"], str(int(r["n_town"]))]
        if str(r["win_party"]) == "":
            cells += ["—"]
            cells += [f"{r[f'rate{ik}']:.2f}" if has_kmt else ""]
            cells += [f"{r[f'rate{idk}']:.2f}" if has_dpp else ""]
            cells += ["（無資料）", "—", "—"]
        else:
            cells += [f"{int(r['valid_votes']):,}"]
            cells += [f"{r[f'rate{ik}']:.2f}" if has_kmt else ""]
            cells += [f"{r[f'rate{idk}']:.2f}" if has_dpp else ""]
            cells += [f"<b>{r['win_party']}</b>", f"{lead:.2f}",
                      f"`{r['fill_hex']}`"]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    L += ["### 2. 全國政黨得票合計（22 縣市累加）", "",
          "| 政黨 | 得票數 | 得票率 |", "|---|---:|---:|"]
    tot_v = np.zeros(len(base.PARTIES), dtype=np.int64)
    tot_valid = 0
    for c in county_tot:
        tot_v += np.array([int(v) for v in county_tot[c][:-1]], dtype=np.int64)
        tot_valid += int(county_tot[c][-1])
    for j, p in enumerate(base.PARTIES):
        L.append(f"| {p} | {int(tot_v[j]):,} | "
                 f"{tot_v[j] / tot_valid * 100:.2f} |")
    L.append(f"| **有效票合計** | **{tot_valid:,}** | **100.00** |")
    L.append("")

    L += ["### 3. 對位檢查", ""]
    if miss:
        L += ["**地圖上有縣市、但對不上得票資料（留白）：**", ""]
        L += [f"- {c}" for c in miss] + [""]
    diff = [c for c in county_tot if not len(counties[counties["OLD_COUNTY"] == c])]
    if diff:
        L += ["**得票資料有、地圖無對應縣市：**", ""] + [f"- {c}" for c in diff] + [""]
    L += ["**各縣市資料側鄉鎮市區數（應與地圖一致，供交叉核對）：**", "",
          "| 縣市 | 資料側鄉鎮市區數 | 地圖鄉鎮市區數 |", "|---|---:|---:|"]
    for _, r in rows.iterrows():
        c = r["OLD_COUNTY"]
        L.append(f"| {c} | {len(town_set.get(c, ()))} | {int(r['n_town'])} |")
    L.append("")

    L += ["### 4. 領先得票率範圍", ""]
    if has.any():
        lead = counties.loc[has, rate_cols].max(axis=1)
        L += [f"- 最低領先得票率 {lead.min():.2f}%、最高 {lead.max():.2f}%", ""]
    return L


def run_year(year):
    t0 = time.time()
    yrs._CUR_YEAR[0] = year
    out = year_outputs(year)
    out_png = out["png"]

    print("=" * 66)
    print(f"  全臺灣 {year} 立法委員不分區（政黨票）得票率地圖 —— 縣市版（22 縣市）"
          f"　【底圖＝{os.path.basename(yrs.YEAR_SHP[year])} 村里界 SHP】")
    print("  填色單位＝縣市；不畫鄉鎮界、不畫村里界")
    print("=" * 66)

    # ---- ① 得票資料：逐村（里）→ 縣市合計 ----
    by_key, by_town, vote_display, cnt_by_key, n_total, parties = \
        yrs.load_raw_party_votes(yrs.YEAR_DATA_GLOB[year])
    if not parties:
        raise ValueError(f"{year} 未解析到任何政黨欄位")
    base.PARTIES = parties
    base.PARTY_STOPS = yrs.make_stops(parties)
    county_tot, town_set = c12.aggregate_county_votes(cnt_by_key)
    _v = sum(int(a[-1]) for a in county_tot.values())
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(by_key)} 個村里 → "
          f"聚合為 {len(county_tot)} 個縣市（資料側）；{len(parties)} 個政黨："
          + "、".join(parties) + f"；有效票合計 {_v:,}")

    # ---- ② 底圖：逐年村里界 SHP，全臺一套 ----
    gdf = base._read_shp_base(yrs.YEAR_SHP[year])
    gdf = t12.reattach_unassigned_villages(gdf, path=yrs.YEAR_SHP[year])
    gdf = base.add_old_county(gdf)
    print(f"  底圖（{os.path.basename(yrs.YEAR_SHP[year])}）村里圖斑：{len(gdf)}；"
          f"縣市：{gdf['OLD_COUNTY'].nunique()}")
    gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = t12.strip_far_parts_by_part(gdf)

    # ---- ③ 版面：金馬附圖（與另兩版同一函式 → 擺放位置完全一致） ----
    gdf, boxes = base.layout_insets(gdf)

    # ---- ④ dissolve 到縣市（附圖平移縮放之後） ----
    counties = gdf.dissolve(by=["OLD_COUNTY"]).reset_index()
    counties = base.remove_ring_slits(counties)
    counties = c12.clean_county_parts(counties)
    n_town = gdf.groupby("OLD_COUNTY")["TOWNNAME"].nunique()
    counties["n_town"] = counties["OLD_COUNTY"].map(n_town).fillna(0).astype(int)
    print(f"  縣市：{len(counties)}、鄉鎮市區合計 {int(n_town.sum())}"
          f"（村里圖斑 {len(gdf)}）")
    if len(counties) != N_COUNTY:
        print(f"  ⚠️ 填色單位 {len(counties)} 個 ≠ 22 個："
              f"{sorted(counties['OLD_COUNTY'])}")

    # ---- ⑤ 縣市對位與填色 ----
    counties, miss, rate_cols = c12.assign_county_colors(counties, county_tot)
    map_set = set(counties["OLD_COUNTY"])
    orphan = sorted(c for c in county_tot if c not in map_set)
    print(f"  縣市對位：有資料 {int((counties['win_party'] != '').sum())}／"
          f"{len(counties)}；無資料 {len(miss)} {miss if miss else ''}；"
          f"資料側孤兒縣市 {len(orphan)} {orphan if orphan else ''}")
    for p, n in counties.loc[counties["win_party"] != "", "win_party"] \
            .value_counts().items():
        print(f"    領先縣市：{p} {int(n)}")
    tn.write_audit_section(year, "縣市版稽核",
                           build_county_audit_lines(year, counties, miss,
                                                    orphan, town_set,
                                                    county_tot))

    # ---- 畫布（長寬上限 3000 × 3750 px） ----
    minx, miny, maxx, maxy = counties.total_bounds
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
          f"{w_px * h_px / 1e6:.1f} 百萬像素）")

    # ---- ② 縣市界層：只有縣市界 6px（無鄉鎮界、無村里界） ----
    _thick_cty, coast_geom, county_segs = base.compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g_.length for g_ in county_segs) / 1000:.0f} km）")
    base.audit_county_segments(counties, county_segs)
    print(f"  ② 縣市界 {base.LINE_COUNTY_INNER_PX}px（只畫內陸交界；"
          f"不畫鄉鎮界、不畫村里界；matplotlib + 閾值二值化）…")
    county_layer = base.render_county_segments_mask(
        county_segs, counties.crs, w_px, h_px, minx, maxx, miny, maxy)
    print(f"  縣市界層：{int(county_layer.sum())} px（閾值 {base.THRESHOLD_VAL}）")

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
    # 澎湖／金門／連江外緣用「清理前」的村里級 gdf 聯集邊界（同 2012 縣市版作法）
    thin_skel = base.render_thin_coast_layer(gdf, w_px, h_px,
                                             minx, maxy, sx, sy)
    if thin_skel is None:
        thin_skel = np.zeros((h_px, w_px), dtype=bool)
    print(f"  海岸線層：本島 {int(coast_skel.sum())} px ＋ "
          f"澎湖金馬 {int(thin_skel.sum())} px")

    lines_mask = county_layer | coast_skel | thin_skel | box_mask
    del coast_skel, thin_skel

    # 自檢：金門／連江的無名礁石必須全部畫出（縣市版不畫村里界，
    #       礁石外緣由「澎湖金馬海岸線 1px 層」負責）
    base.check_reef_drawn(gdf, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ---- 填色（洪水填充；填色單位＝縣市） ----
    print("  填色（洪水填充／油漆桶規則，填色單位＝縣市）…")
    records = counties[["OLD_COUNTY", "fill_hex", "win_party", "n_town",
                        "valid_votes"] + rate_cols].copy()
    records = gpd.GeoDataFrame(records, geometry=counties.geometry.values,
                               crs=counties.crs)
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    arr[lines_mask] = np.array(base.LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0        # 附圖外框（金門／連江／烏坵框）＝黑線
    print(f"  非線連通區域：{ncomp - 1} 塊（填色單位 {len(records)} 個縣市）；"
          f"線色 {base.LINE_COLOR}、附圖外框 黑 (0,0,0)")

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
    print(f"==== {year} 縣市版 finished ====")


def main():
    years = []
    for a in sys.argv[1:]:
        la = str(a).lower()
        if la.isdigit() and int(la) in yrs.YEAR_SHP:
            years.append(int(la))
    if not years:
        years = sorted(yrs.YEAR_SHP)
    for y in years:
        run_year(y)


if __name__ == "__main__":
    main()
