# -*- coding: utf-8 -*-
"""
全臺灣（本島＋澎湖＋金門＋馬祖）
2012 第八屆立法委員全國不分區及僑居國外國民選舉
**縣市版** —— 填色單位＝縣市（2012 年行政區，共 **22 個縣市**），全圖只有 22 塊顏色

由 2008 版 `Draw_Taiwan_AtLarge_2008_County.py` 移植（管線、版面、自檢全部重用），
只改參數：底圖＝民國 106 年（1070205）村里界 SHP 全臺一套；得票資料＝
`data/2012不分区`（11 個政黨）逐村（里）直接累加到縣市；2012 已為五都合併後
22 縣市，資料側與底圖縣市同名 → old_county_of 恆等（2008 版五都切分已移除）。

輸出：LegislationYuan/2012-2024/map/全臺灣2012年立法委員不分區選舉_政黨票得票率地圖_縣市版.png
      LegislationYuan/2012-2024/map/全臺灣2012_縣市版_稽核.md
執行：py script/Draw_Taiwan_AtLarge_2012_County.py
"""
import os
import sys
import time

import numpy as np
import geopandas as gpd
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 村里版全模組：底圖載入、2008 縣市還原、版面、縣市界幾何、海岸線、自檢全部重用
import Draw_Taiwan_AtLarge_2012 as base
import Draw_National_President_2020 as nat
# 鄉鎮版：未編定村里併回、逐部件離島碎塊清理（兩者與填色單位無關，直接沿用）
import Draw_Taiwan_AtLarge_2012_Township as town

OUT_PNG = os.path.join(
    base.OUT_DIR, "全臺灣2012年立法委員不分區選舉_政黨票得票率地圖_縣市版.png")
AUDIT_MD = os.path.join(base.OUT_DIR, "全臺灣2012_縣市版_稽核.md")

# 畫布（鄉鎮版 5000 × 6250 的六成）→ 實際輸出約 2720 × 3750（175 m/px）
MAX_W_PX = 3000
MAX_H_PX = 3750
METERS_PER_PIXEL = base.METERS_PER_PIXEL      # 比例尺下限同村里版（不會生效）

# 2012 年 22 縣市（2010 五都合併後；僅用於稽核表排序）
OFFICIAL_ORDER = [
    "臺北市", "新北市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "新竹縣",
    "桃園縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣",
    "臺東縣", "花蓮縣", "宜蘭縣", "澎湖縣", "金門縣", "連江縣",
]
N_COUNTY = 22


def old_county_of(data_county, town_norm):
    """2012 選舉已為五都合併後 22 縣市，資料側與底圖縣市同名 → 恆等。

    （2008 版的 五都切分 SPLIT_COUNTY／CITY_TOWNS 與 臺北縣還原 RENAME_2008
      已隨 base 模組一併移除，不需任何映射。）
    """
    return data_county


def aggregate_county_votes(cnt_by_key):
    """逐村（里）得票數 → 縣市合計。

    cnt_by_key：(資料側縣市, 鄉鎮, 村里) → (12 個政黨得票數…, 有效票數)
    ⚠️ 鄉鎮名在 load_party_votes 內已 norm_town 過一次，**不得再 norm_town 第二次**
       （否則「前鎮→前、平鎮→平、新市→新」會被誤剝，鄉鎮歸屬判斷跟著出錯）。
    回傳 (county_tot, town_set)：
        county_tot : 縣市 → [11 個政黨票數…, 有效票數]（先加總、後算率）
        town_set   : 縣市 → 資料側實際出現的鄉鎮市區集合（稽核用）
    """
    county_tot, town_set = {}, {}
    for (c, t, _v), a in cnt_by_key.items():
        oc = old_county_of(base.norm_county(c), t)
        cur = county_tot.get(oc)
        if cur is None:
            county_tot[oc] = list(a)
            town_set[oc] = {t}
        else:
            for i in range(len(a)):
                cur[i] += a[i]
            town_set[oc].add(t)
    return county_tot, town_set


def assign_county_colors(counties, county_tot):
    """每個縣市：得票率＝各村合計 ÷ 有效票合計 → 領先政黨色階（依率選深淺）。

    對不上資料的縣市留白（NO_DATA_COLOR），逐筆回傳供稽核。
    """
    rate_cols = [f"rate{i}" for i in range(len(base.PARTIES))]
    n = len(counties)
    rate_arr = np.full((n, len(base.PARTIES)), np.nan)
    vote_arr = np.zeros((n, len(base.PARTIES) + 1), dtype=np.int64)
    fills = [base.NO_DATA_COLOR] * n
    wins = [""] * n
    miss = []
    counties = counties.copy().reset_index(drop=True)
    for pos in range(n):
        oc = counties.at[pos, "OLD_COUNTY"]
        tot = county_tot.get(oc)
        if tot is None or tot[-1] <= 0:
            miss.append(oc)
            continue
        rates = [v / tot[-1] * 100.0 for v in tot[:-1]]
        j = int(np.argmax(rates))
        col = nat.get_color_by_value(rates[j], base.PARTY_STOPS[base.PARTIES[j]])
        fills[pos] = col or base.NO_DATA_COLOR
        wins[pos] = base.PARTIES[j]
        rate_arr[pos] = rates
        vote_arr[pos] = list(tot)
    for kk, rc in enumerate(rate_cols):
        counties[rc] = rate_arr[:, kk]
    for kk, p in enumerate(base.PARTIES):
        counties[f"vote_{p}"] = vote_arr[:, kk]
    counties["valid_votes"] = vote_arr[:, -1]
    counties["fill_hex"] = fills
    counties["win_party"] = wins
    return counties, miss, rate_cols


def clean_county_parts(gdf, min_hole=base.HOLE_MIN_AREA_M2):
    """清掉 <1 公頃的微孔，但**不丟棄任何小圖斑**（縣市版專用）。

    `base.clean_tiny_holes` 會把面積 <1 ha 的**多邊形部件**一併丟掉（離島礁石），
    村里／鄉鎮版靠「礁石填鄉鎮色」補救；縣市版填色單位就是縣市，
    每個礁石都屬於某個有資料的縣市，留白只會變成白色斑點 → 這裡只清孔、不砍部件。
    """
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        kept = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            if poly.geom_type != "Polygon":
                kept.append(poly)
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_hole]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out[~out.geometry.isna() & ~out.geometry.is_empty].copy().reset_index(drop=True)


def write_audit_md(counties, miss, orphan, town_set, county_tot, md_path):
    """縣市版稽核報告：22 縣市得票率一覽、全國政黨合計、對位檢查。"""
    rate_cols = [f"rate{i}" for i in range(len(base.PARTIES))]
    has = counties["win_party"].astype(str) != ""
    order = {c: i for i, c in enumerate(OFFICIAL_ORDER)}
    rows = counties.assign(_o=counties["OLD_COUNTY"].map(
        lambda c: order.get(c, 999))).sort_values(["_o", "OLD_COUNTY"])
    ik = base.PARTIES.index("中國國民黨")
    idk = base.PARTIES.index("民主進步黨")

    L = ["# 全臺灣 2012 立法委員不分區（政黨票）得票率地圖 — **縣市版**稽核", ""]
    L += [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
          "- 填色單位：**縣市（2012 年行政區）**，全圖只有 22 塊顏色",
          "- 底圖：**民國106年（1070205）村里界 SHP** → 逐村里 dissolve 到鄉鎮市區"
          f" → 再 dissolve 到縣市 → 本圖 {len(counties)} 個縣市",
          "- 得票資料：`data/2012不分区`（中選會原始 xls）→ 逐村（里）**直接累加**到縣市"
          f" → 資料側 {len(county_tot)} 個縣市",
          f"- 對位結果：有資料 **{int(has.sum())}**、無資料 **{len(miss)}**（圖上留白）",
          f"- 資料側孤兒縣市（地圖無對應）：**{len(orphan)}**"
          f"{'：' + '、'.join(orphan) if orphan else ''}", ""]

    if len(counties) != N_COUNTY:
        L += [f"> ⚠️ **填色單位為 {len(counties)} 個，不是 22 個**，請檢查底圖縣市名。", ""]

    L += ["## 1. 22 縣市得票一覽（依中選會公告順序）", "",
          "| # | 縣市 | 鄉鎮市區 | 有效票 | 中國國民黨 % | 民主進步黨 % | 領先政黨 | 領先得票率 | 色碼 |",
          "|---:|---|---:|---:|---:|---:|---|---:|---|"]
    for i, (_, r) in enumerate(rows.iterrows(), 1):
        if str(r["win_party"]) == "":
            L.append(f"| {i} | {r['OLD_COUNTY']} | {int(r['n_town'])} | — | — | — | （無資料） | — | — |")
            continue
        lead = max(r[rc] for rc in rate_cols)
        L.append(f"| {i} | {r['OLD_COUNTY']} | {int(r['n_town'])} | "
                 f"{int(r['valid_votes']):,} | {r[f'rate{ik}']:.2f} | {r[f'rate{idk}']:.2f} | "
                 f"<b>{r['win_party']}</b> | {lead:.2f} | `{r['fill_hex']}` |")
    L.append("")

    L += ["## 2. 全國政黨得票合計（22 縣市累加）", "",
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

    L += ["## 3. 對位檢查", ""]
    if miss:
        L += ["**地圖上有縣市、但對不上得票資料（留白）：**", ""]
        L += [f"- {c}" for c in miss] + [""]
    diff = []
    for c in county_tot:
        m = counties[counties["OLD_COUNTY"] == c]
        if not len(m):
            diff.append(c)
    if diff:
        L += ["**得票資料有、地圖無對應縣市：**", ""] + [f"- {c}" for c in diff] + [""]
    L += ["**各縣市資料側鄉鎮市區數（應與地圖一致，供交叉核對）：**", "",
          "| 縣市 | 資料側鄉鎮市區數 | 地圖鄉鎮市區數 |", "|---|---:|---:|"]
    for _, r in rows.iterrows():
        c = r["OLD_COUNTY"]
        L.append(f"| {c} | {len(town_set.get(c, ()))} | {int(r['n_town'])} |")
    L.append("")

    L += ["## 4. 領先得票率範圍", ""]
    if has.any():
        lead = counties.loc[has, rate_cols].max(axis=1)
        L += [f"- 最低領先得票率 {lead.min():.2f}%、最高 {lead.max():.2f}%", ""]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  縣市版稽核報告：{md_path}")


def main():
    t0 = time.time()
    print("=" * 66)
    print("  全臺灣 2012 立法委員不分區（政黨票）得票率地圖 —— 縣市版（22 縣市）")
    print("  填色單位＝縣市；不畫鄉鎮界、不畫村里界")
    print("=" * 66)

    # ---- ① 得票資料：逐村（里）→ 縣市合計 ----
    by_key, by_town, vote_display, cnt_by_key, n_total = base.load_party_votes()
    county_tot, town_set = aggregate_county_votes(cnt_by_key)
    _v = sum(int(a[-1]) for a in county_tot.values())
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(by_key)} 個村里 → "
          f"聚合為 {len(county_tot)} 個縣市（資料側）；{len(base.PARTIES)} 個政黨；"
          f"有效票合計 {_v:,}")

    # ---- ② 底圖：民國106年（1070205）村里界 SHP，全臺一套 ----
    gdf = base.load_shp_base()
    gdf = town.reattach_unassigned_villages(gdf)
    gdf = base.add_old_county(gdf)
    print(f"  底圖（106 年 SHP）村里圖斑：{len(gdf)}；"
          f"2012 縣市：{gdf['OLD_COUNTY'].nunique()}")
    gdf = base.resolve_cross_county_overlaps(gdf)
    gdf = town.strip_far_parts_by_part(gdf)

    # ---- ③ 版面：金馬附圖（與另兩版同一函式 → 擺放位置完全一致） ----
    gdf, boxes = base.layout_insets(gdf)

    # ---- ④ dissolve 到縣市（附圖平移縮放之後） ----
    counties = gdf.dissolve(by=["OLD_COUNTY"]).reset_index()
    counties = base.remove_ring_slits(counties)
    counties = clean_county_parts(counties)
    n_town = gdf.groupby("OLD_COUNTY")["TOWNNAME"].nunique()
    counties["n_town"] = counties["OLD_COUNTY"].map(n_town).fillna(0).astype(int)
    print(f"  縣市：{len(counties)}、鄉鎮市區合計 {int(n_town.sum())}"
          f"（村里圖斑 {len(gdf)}）")
    if len(counties) != N_COUNTY:
        print(f"  ⚠️ 填色單位 {len(counties)} 個 ≠ 22 個："
              f"{sorted(counties['OLD_COUNTY'])}")

    # ---- ⑤ 縣市對位與填色 ----
    counties, miss, rate_cols = assign_county_colors(counties, county_tot)
    map_set = set(counties["OLD_COUNTY"])
    orphan = sorted(c for c in county_tot if c not in map_set)
    print(f"  縣市對位：有資料 {int((counties['win_party'] != '').sum())}／"
          f"{len(counties)}；無資料 {len(miss)} {miss if miss else ''}；"
          f"資料側孤兒縣市 {len(orphan)} {orphan if orphan else ''}")
    for p, n in counties.loc[counties["win_party"] != "", "win_party"] \
            .value_counts().items():
        print(f"    領先縣市：{p} {int(n)}")
    write_audit_md(counties, miss, orphan, town_set, county_tot, AUDIT_MD)

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
    w_px = int(np.ceil(geo_w / scale))
    h_px = int(np.ceil(geo_h / scale))
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
    # 澎湖／金門／連江的外緣用「清理前」的村里級 gdf 聯集邊界：
    # dissolve 後的縣市層清微孔時可能丟掉小礁石，村里版由村里界 1px 層兼任，
    # 縣市版沒有那一層，必須在縣市層清理前取外緣（同鄉鎮版作法）。
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
    base.save_png(pil_img, OUT_PNG)
    W, H = pil_img.size
    del pil_img

    print(f"\n  Saved: {OUT_PNG}  ({W}×{H}px)")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== All finished ====")


if __name__ == "__main__":
    main()
