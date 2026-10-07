# -*- coding: utf-8 -*-
"""
新北市 · 2020 總統副總統選舉 各村（里）得票領先候選人得票比例圖

繪圖思路 = 兩份既有腳本的結合：
  ① 線稿（Empty_Map/DrawTaichungCity.py 的兩層畫法 + 2024 參考圖的線寬）
     - 村里界 1px：PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線
     - 區界 4px + 市界/海岸線外輪廓 6px：matplotlib(Agg, DPI=100) 繪區面與區界，
       以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層；較粗的區界使密集村里
       區塊清楚分隔（同 2024 參考圖），不再顯得雜亂
     - 微孔洞清理（HOLE_MIN_AREA_M2）避免 dissolve 浮點誤差造成的散點
     - 兩層同一像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加不錯開 1px
  ② 填色與圖例（2020Precident/scripts/Draw_National_President_2020.py）
     - 得票率 Excel 讀取、異體字/模糊匹配、三候選人取最高者填色（5% 色階、35% 起）
     - 填色採「油漆桶／洪水填充」規則（同畫圖軟體）：先以線稿（村里界 1px +
       區界 4px + 市界/海岸線 6px）構成封閉堤壩，再對堤壩以外的每一塊 4-連通
       區域「整塊填成單一顏色」；顏色取該區域內像素幾何判定所屬村里的眾數
       → 顏色永不跨越任何一條黑線，密集村里區（如永和）的 1px 掃描/幾何落差
       不再產生錯色或色塊滲透
     - 自檢：① 油漆桶不變式——每塊非線連通區域皆為單色；② 與逐像素幾何參考
       （GDAL/rasterio 中心規則，獨立方法）差異 ≈0、村外非白 ≈0
     - 圖例只畫「有村里領先」的候選人欄（如本市宋楚瑜 0 村即不出欄）
     - 版面：標題在上、圖例在下，整組面板置於畫布右上角（同 2024 參考圖）
       圖例自本市最低領先得票率向下取 5 的倍數起

比例尺：1px = 20m（METERS_PER_PIXEL=20，再放大 10%）
輸出：2020Precident/maps/新北市2020年總統副總統選舉_得票率地圖.png
執行：py Draw_NewTaipei_President_2020.py
"""
import os
import sys
import math
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
import Draw_National_President_2020 as nat   # 得票率匹配 / 填色 / 圖例 / 文字渲染

# ===================== 配置 =====================
# 108 年版村里界（2019/11/21），與 2020 選舉年份一致，同 2020 全臺腳本之首選圖資
shp_path = r"D:\Windows\Documents\村里界歷史圖資_111\108\VILLAGE_MOI_1081121.shp"
OUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "maps")
OUT_PNG = os.path.join(OUT_DIR, "新北市2020年總統副總統選舉_得票率地圖.png")
layer_name = "layer_newtaipei_district_2px.png"   # ② 層單獨輸出（核對用）
target_county = "新北市"
encoding = "UTF-8"        # 108 版 .dbf 為 UTF-8；若失效可改 "cp950"
TARGET_CRS = "EPSG:3826"

TITLE_LINES = ["中華民國第十五屆總統副總統選舉",
               "新北市各村（里）得票領先之候選人得票比例圖"]
TITLE_FONT_SIZE = 48      # 標題字級（全臺腳本為 100，本市圖縮小以配合單一縣市版面）

# 比例尺：1px = 20m，再放大 10%
# 新北市 bbox 約 70 x 65 km（北海岸、東北角、烏來山區），1px=20m 放大 10% 後
# 實際 1px≈18.18m，地圖約 4100x3900 px（長寬皆 < MAX_PX）
METERS_PER_PIXEL = 20.0
MAX_PX = 12000
SCALE_UP = 1.10
PAD_FRAC = 0.01

SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（沿用 DrawTaichungCity.py：簡化會把緩彎拉直）

LINE_VILLAGE_PX = 1      # ① 村里界
LINE_TOWNSHIP_PX = 4     # ② 區界線寬(px)：同 2024 參考圖，密集區塊以粗線清楚分隔
LINE_OUTER_PX = 6        # ② 市界/海岸線外輪廓線寬(px)
THRESHOLD_VAL = 40       # ② 二值化閾值
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為 dissolve 雜訊，填平
SAVE_LAYER = False
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)


# ----------------------① 讀 SHP + 讀得票率 + 匹配填色----------------------
def main():
    print("=" * 62)
    print("  新北市 2020 總統副總統選舉 各村（里）得票率地圖")
    print("=" * 62)

    gdf_all = gpd.read_file(shp_path, encoding=encoding)
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    gdf_all = gdf_all.to_crs(TARGET_CRS)

    gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.strip() == target_county].copy()
    gdf_all = gdf_all[gdf_all["TOWNNAME"].notna()].copy()
    gdf_all["geometry"] = gdf_all.geometry.buffer(0)
    gdf_all["TOWNNAME"] = gdf_all["TOWNNAME"].astype(str).str.strip()
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all = gdf_all.reset_index(drop=True)

    # 得票率（沿用 2020 全臺腳本的 Excel 讀取與異體字/模糊匹配）
    vote_dict, vote_by_town, n_rows, n_total = nat.load_vote_data(nat.DATA_DIR)
    print(f"  Excel 得票率記錄 : {n_total} 筆（去重後 {n_rows} 筆）")

    gdf_all["county_core"] = gdf_all["COUNTYNAME"].apply(nat.normalize_text)
    gdf_all["town_core"] = gdf_all["TOWNNAME"].apply(nat.strip_town_suffix)
    gdf_all["vill_core"] = gdf_all["VILLNAME"].apply(nat.strip_village_suffix)

    rate_cols = [f"rate{i}" for i in range(len(nat.CAND_NAMES))]

    def process_row(r):
        matched, vals, mt = nat.fuzzy_lookup(
            r["county_core"], r["town_core"], r["vill_core"],
            vote_dict, vote_by_town)
        if vals is None:
            return pd.Series([np.nan, np.nan, np.nan, "none"])
        return pd.Series(list(vals) + [mt])

    gdf_all[rate_cols + ["match_type"]] = gdf_all.apply(process_row, axis=1)

    exact_cnt = int((gdf_all["match_type"] == "exact").sum())
    fuzzy_cnt = int(gdf_all["match_type"].str.startswith("fuzzy", na=False).sum())

    # 三候選人取最高者填色；無資料(含 VILLNAME 空值)一律純白
    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return nat.get_color_by_value(vals[i], nat.RATE_COLOR_STOPS[i])

    gdf_all["fill_hex"] = np.where(
        gdf_all[rate_cols].notna().any(axis=1),
        gdf_all.apply(pick_fill_color, axis=1),
        nat.NO_DATA_COLOR,
    )
    gdf_all["fill_hex"] = gdf_all["fill_hex"].fillna(nat.NO_DATA_COLOR)

    has_data = gdf_all[rate_cols].notna().any(axis=1)
    print(f"  SHP 要素數       : {len(gdf_all)}")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字/模糊匹配   : {fuzzy_cnt}")
    print(f"  有資料填色       : {int(has_data.sum())}")
    print(f"  無資料（純白）    : {int((~has_data).sum())}")

    # 各候選人領先村里數：完全沒人領先的候選人不畫圖例欄（如本市宋楚瑜 0 村）
    _win = np.argmax(gdf_all.loc[has_data, rate_cols].fillna(0.0).to_numpy(dtype=float), axis=1)
    active_idx = [i for i in range(len(nat.CAND_NAMES)) if int((_win == i).sum()) > 0]
    for i, nm in enumerate(nat.CAND_NAMES):
        print(f"    領先村里：{nm} {int((_win == i).sum())} 村"
              + ("" if i in active_idx else " → 不畫圖例"))
    assert active_idx, "無任何候選人領先村里"

    # 圖例起點：本市最低領先得票率向下取 5 的倍數
    min_win_rate = 100.0
    for _, row in gdf_all[has_data].iterrows():
        win = max(row[c] for c in rate_cols)
        if win < min_win_rate:
            min_win_rate = win
    legend_start_tier = int(min_win_rate // 5) * 5
    print(f"  最低領先得票率   : {min_win_rate:.2f}% → 圖例自 {legend_start_tier}% 起")

    records = gdf_all.copy()
    villages = records[records["VILLNAME"].notna()].copy()   # ① 村里層
    if SIMPLIFY_TOL_M > 0:
        villages["geometry"] = villages.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)
    # ② 區層：含未編定村里圖斑（港區/水域等），區界才完整
    townships = records.dissolve(by="TOWNNAME").reset_index()
    print(f"{target_county} 區：{len(townships)}，村里 {len(villages)}")

    townships = clean_tiny_holes(townships)

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

    # ----------------------② 區界 + 市界 + 海岸線----------------------
    print(f"  ② 區界 {LINE_TOWNSHIP_PX}px + 市界/海岸線 {LINE_OUTER_PX}px（matplotlib + 閾值二值化）...")
    town_layer = render_line_layer(townships, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    print(f"  區/市界層：{int(town_layer.sum())} px"
          f"（區界 {LINE_TOWNSHIP_PX}px、外輪廓 {LINE_OUTER_PX}px，閾值 {THRESHOLD_VAL}）")

    # ----------------------① 村里界 1px----------------------
    print("  ① 村里界 1px（1px 直繪 → thin 中心線）...")
    village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
    village_arr = draw_layer(village_lines, 1, w_px, h_px, minx, maxy, sx, sy)
    village_skel = thin(village_arr)
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # 對齊自檢：② 層必須覆蓋區界/市界 1px 原始線
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1,
                           w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
    print(f"  區界+市界 1px 原始線 {int(_town_1px.sum())} px，未被 2px 層覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層應為單一連通網
    _cc_n, _, _cc_st, _ = cv2.connectedComponentsWithStats(town_layer.astype(np.uint8), connectivity=8)
    _cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
    _cc_small = int((_cc_area <= 40).sum())
    print(f"  ② 層連通分量：{_cc_n - 1} 個（應為 1）；<=40px 小分量 {_cc_small} 個（應為 0）")

    lines_mask = village_skel | town_layer

    # 村里線自檢：扣掉 2px 層後不應出現 2x2 粗塊
    _v_only = village_skel & ~town_layer
    _2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
    print(f"  村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")

    # ----------------------填色（線稿為堤壩，逐塊洪水填充）----------------------
    # 畫圖軟體「油漆桶」規則：村里界(1px)與區界/市界(4/6px)構成封閉堤壩，
    # 每個被堤壩圍住的 4-連通區域整塊填一色，顏色取區域內像素幾何判定所屬村里的
    # 眾數。顏色因此永不跨越任何黑線——密集村里區（如永和）不再出現 1px 掃描/
    # 幾何落差造成的錯色或色塊滲透。
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）...")
    arr, ncomp, comp = flood_fill_layer(
        records, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # ----------------------疊加線界----------------------
    arr[lines_mask] = 0
    print(f"  黑像素合計：{int(lines_mask.sum())}  非線連通區域：{ncomp - 1} 塊")

    # 自檢 A：油漆桶不變式——每塊非線 4-連通區域必須只含單一顏色（色不越過黑線）
    _nc, _nbad = check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")

    # 自檢 B：與逐像素幾何參考的差異。油漆桶會把邊界 1px 的落差直接吸附到整塊
    # 眾數色上，故差異應僅為這些被吸附的邊界像素，遠小於全圖像素數。
    _nw, _nout = full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%；"
          f"村外非白 {_nout}；皆應 ≈0）")

    # 顏色驗證：全圖只應含允許色（填色 + 純白底 + 純黑線），有雜色即在此現形
    allowed = {(255, 255, 255), (0, 0, 0)}
    for stops in nat.RATE_COLOR_STOPS:
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

    # ----------------------版面：標題與圖例置於右上角（同 2024 參考圖）----------------------
    # 標題在上、圖例在下，整組面板貼齊畫布右上角；地圖置於左側並垂直居中。
    print("  標題與圖例（右上角）...")
    W, H = pil_img.size
    title_img = nat.render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)

    # 只畫「有村里領先」的候選人欄（active_idx 以外者不出現在圖例）
    legend_stops_list = [
        [(u, c) for u, c in nat.RATE_COLOR_STOPS[i] if u > legend_start_tier]
        for i in active_idx
    ]
    name_imgs = [nat.render_text_image_cached([nat.CAND_NAMES[i]], nat.CAND_NAME_FONT_SIZE)
                 for i in active_idx]
    name_h = max((im.height for im in name_imgs), default=0)

    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = nat.get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier,
                                     is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(nat.render_text_image_cached([txt], nat.LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    col_width = nat.BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(legend_stops_list)
    # 圖例群組寬度：以「色塊 + 標籤」實際佔用為準（最後一欄不含右側標籤亦無妨）
    group_w = (n_cols - 1) * (col_width + nat.H_SPACING) + nat.BLOCK_WIDTH
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + nat.COLUMN_TITLE_GAP + max_n * (nat.BLOCK_HEIGHT + nat.V_SPACING) - nat.V_SPACING

    LEGEND_X_MARGIN = 80       # 面板左緣與地圖右緣的水平間距
    TITLE_GAP = 70             # 標題與圖例的垂直間距
    panel_x = W + LEGEND_X_MARGIN
    content_w = int(max(title_img.width, group_w))
    # 標題與圖例群組在同一內容框內各自水平置中（同 2024 參考圖）
    title_x = panel_x + (content_w - title_img.width) / 2
    legend_x = panel_x + (content_w - group_w) / 2
    new_W = int(panel_x + content_w + nat.LEGEND_PADDING)
    panel_content_h = title_img.height + TITLE_GAP + legend_h
    new_H = int(max(H, panel_content_h + 2 * nat.LEGEND_PADDING))
    print(f"  版型：地圖 {W}x{H}，標題寬 {title_img.width}px、圖例寬 {int(group_w)}px，"
          f"面板 x={int(panel_x)}、內容寬 {content_w}px（面板置於右上角）")

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))
    del pil_img

    py = nat.LEGEND_PADDING
    nat.blit_rgba(final_img, title_img, (title_x, py))
    py += title_img.height + TITLE_GAP

    draw_obj = ImageDraw.Draw(final_img)
    col_positions = [legend_x + i * (col_width + nat.H_SPACING) for i in range(n_cols)]
    for col_idx, stops in enumerate(legend_stops_list):
        x_start = col_positions[col_idx]
        nm_img = name_imgs[col_idx]
        nat.blit_rgba(final_img, nm_img, (x_start + (nat.BLOCK_WIDTH - nm_img.width) / 2, py))
        for i, (upper, color_hex) in enumerate(stops):
            y = py + name_h + nat.COLUMN_TITLE_GAP + i * (nat.BLOCK_HEIGHT + nat.V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + nat.BLOCK_WIDTH, y + nat.BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            limg = label_img_cols[col_idx][i]
            nat.blit_rgba(final_img, limg, (x_start + nat.BLOCK_WIDTH + 8,
                                            y + (nat.BLOCK_HEIGHT - limg.height) / 2))

    if SAVE_LAYER:
        _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
        _la[town_layer] = 0
        Image.fromarray(_la, mode="RGB").save(os.path.join(OUT_DIR, layer_name))

    final_img.save(OUT_PNG)

    # 存檔後自檢：地圖區（不含右側面板）不得含非允許色；油漆桶吸收的邊界像素
    # 遠小於容差，且村外必為純白
    _re = np.asarray(Image.open(OUT_PNG).convert("RGB"))
    _off = (new_H - H) // 2
    _re_map = _re[_off:_off + H, :W]
    _u2, _c2 = np.unique(_re_map.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _nw2, _nout2 = full_geom_check(_re_map, records, w_px, h_px, minx, maxy, sx, sy)
    _tol2 = 0.0002 * w_px * h_px       # 油漆桶把邊界 1px 落差吸附掉的容許像素數
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、"
          f"幾何參考差異 {_nw2} px（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    if _bad2 or _nout2 or _nw2 > _tol2:
        print(f"  ⚠️ bad={_bad2[:5]} wrong={_nw2} out={_nout2}")
    print(f"\n  Saved: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print("==== All finished ====")


# ===================== 線稿工具（DrawTaichungCity.py） =====================
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
    """matplotlib 繪區面+區界 → 二值化 → 純黑線層。

    區界畫 town_px px、市界/海岸線外輪廓畫 outer_px px（同 2024 參考圖：
    密集村里區以較粗的區界切分，視覺上不再像雜色斑點）。"""
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
