# -*- coding: utf-8 -*-
"""
南臺六縣市（雲林縣・嘉義縣・嘉義市・臺南市・高雄市・屏東縣）
2020 總統副總統選舉 各村（里）得票領先候選人得票比例圖

繪圖邏輯完全沿用 Draw_North5_President_2020.py（其本身沿用
Draw_NewTaipei_President_2020.py），只把「北北基宜桃五縣市」改為
「雲嘉南高屏六縣市」，並依需求調整無村里名圖斑與離島的處理：

  ① 線稿（兩層畫法）
     - 村里界 1px：PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線
     - 區界 3px + 縣市界/海岸線 5px：matplotlib(Agg, DPI=100) 繪區面與區界，
       以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 → 純黑線層
     - 微孔洞清理（HOLE_MIN_AREA_M2）避免 dissolve 浮點誤差造成的散點
     - 兩層同一像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加不錯開 1px
  ② 填色與圖例
     - 得票率 Excel 讀取、異體字/模糊匹配、三候選人取最高者填色（5% 色階、35% 起）
     - 填色採「油漆桶／洪水填充」規則：以線稿構成封閉堤壩，堤壩以外每一塊
       4-連通區域整塊填單色，顏色取區域內像素幾何所屬村里的眾數
       → 顏色永不跨越任何一條黑線，密集村里區不會出現錯色
     - 自檢：① 油漆桶不變式（每塊非線區域皆單色）；② 與逐像素幾何參考
       （GDAL/rasterio 中心規則，獨立方法）差異 ≈0、村外非白 ≈0
     - 版面：不畫標題，只把圖例置於畫布右上角

與北五縣版的差異：
  - 縣市：雲林縣 / 嘉義縣 / 嘉義市 / 臺南市 / 高雄市 / 屏東縣
  - 無村里名（VILLNAME 空）圖斑「整筆不畫」的縣市為
    雲林縣、嘉義縣、臺南市、高雄市（＝ DROP_NAN_COUNTIES）：
      雲林縣 麥寮鄉、臺西鄉（六輕/海埔地水域）
      嘉義縣 布袋鎮（布袋港/鹽田水域）
      高雄市 苓雅/鹽埕/左營/楠梓/岡山/鼓山/前鎮/旗津/小港（港區與航道水域）
             ★ 其中 旗津區 的圖資夾帶 **東沙群島**（距本島約 1450km）與
               **南沙太平島**（距本島約 423km）——若不剔除，地圖範圍會被撐成
               1400 餘公里寬，故這一步是必要的前置處理
      臺南市 無（該市無無村里名圖斑）
    屏東縣不在此列：其無村里名圖斑（東港鎮/枋寮鄉/車城鄉/滿州鄉水域）維持填白
  - 屏東縣離島特例（ISLAND_KEEP）：除**琉球鄉（小琉球）**外，凡脫離本島的
    圖斑一律不畫。實測 108 版圖資中屏東縣唯一脫離本島的離島就是琉球鄉
    （8 個村，距本島 12.2~14.8km），故此規則為安全護欄
  - 保留的有村里編制離岸圖斑：雲林縣口湖鄉台子村的**外傘頂洲**等沙洲
    （距本島 0.5~2.3km，有村里編制，依規則保留）
  - 比例尺 1px = 30m

比例尺：1px = 30m
輸出：2020Precident/maps/雲嘉南高屏2020年總統副總統選舉_得票率地圖.png
執行：py Draw_South6_President_2020.py
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
OUT_PNG = os.path.join(OUT_DIR, "雲嘉南高屏2020年總統副總統選舉_得票率地圖.png")
layer_name = "layer_south6_district_3px.png"   # ② 層單獨輸出（核對用）
TARGET_COUNTIES = ["雲林縣", "嘉義縣", "嘉義市", "臺南市", "高雄市", "屏東縣"]
encoding = "UTF-8"        # 108 版 .dbf 為 UTF-8；若失效可改 "cp950"
TARGET_CRS = "EPSG:3826"

TITLE_LINES = []          # 不畫標題（只保留右側圖例）
TITLE_FONT_SIZE = 48      # 標題字級（TITLE_LINES 非空時才用）

# 比例尺：1px = 30m（不再額外放大）
# 六縣市 bbox 約 107.5 x 218.4 km（雲林口湖外傘頂洲～嘉義阿里山、屏東鵝鑾鼻～雲林麥寮），
# 1px=30m 後地圖約 3655x7427 px（長寬皆 < MAX_PX）
METERS_PER_PIXEL = 30.0
MAX_PX = 12000
SCALE_UP = 1.0
PAD_FRAC = 0.01

SIMPLIFY_TOL_M = 0.0     # 0 = 不簡化（簡化會把緩彎拉直）

LINE_VILLAGE_PX = 1      # ① 村里界
LINE_TOWNSHIP_PX = 3     # ② 區界線寬(px)
LINE_OUTER_PX = 5        # ② 縣市界/海岸線線寬(px)
THRESHOLD_VAL = 40       # ② 二值化閾值
HOLE_MIN_AREA_M2 = 10000.0   # 小於此面積的內環視為 dissolve 雜訊，填平
# 無村里名(VILLNAME 空)的圖斑：這些縣市整筆不畫
# （雲林麥寮/臺西水域、嘉義布袋水域、高雄港區與東沙/南沙）
DROP_NAN_COUNTIES = ["雲林縣", "嘉義縣", "臺南市", "高雄市"]
REMOTE_MAX_DIST_M = 2000.0   # 無村里名者：與本島相距超過此值 → 不畫（外海無編制離島）
NAMED_MAX_DIST_M = 20000.0   # 有村里名者：超過此值才視為圖資錯誤碎塊並剔除
# 屏東縣離島特例：此名單內的鄉鎮（琉球鄉＝小琉球）即使遠離本島也保留；
# 其餘屏東縣圖斑一旦脫離本島（距離 > ISLAND_DETACH_M）就不畫
ISLAND_KEEP = {"屏東縣": ["琉球鄉"]}
ISLAND_DETACH_M = 1000.0     # 判定「脫離本島」的距離門檻
MIN_COMP_AREA_M2 = HOLE_MIN_AREA_M2  # 幾何連通分量面積門檻（與 clean_tiny_holes 一致，
#                                      否則 ② 層會濾掉 <10000 m² 的碎塊，分量數對不上）
SAVE_LAYER = False
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)


# ----------------------① 讀 SHP + 讀得票率 + 匹配填色----------------------
def main():
    print("=" * 62)
    print("  雲嘉南高屏 2020 總統副總統選舉 各村（里）得票率地圖")
    print("=" * 62)

    gdf_all = gpd.read_file(shp_path, encoding=encoding)
    if gdf_all.crs is None:
        gdf_all.crs = "EPSG:4326"
    gdf_all = gdf_all.to_crs(TARGET_CRS)

    gdf_all = gdf_all[gdf_all["COUNTYNAME"].notna()].copy()
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.strip().isin(TARGET_COUNTIES)].copy()
    gdf_all = gdf_all[gdf_all["TOWNNAME"].notna()].copy()
    gdf_all["geometry"] = gdf_all.geometry.buffer(0)
    gdf_all["COUNTYNAME"] = gdf_all["COUNTYNAME"].astype(str).str.strip()
    gdf_all["TOWNNAME"] = gdf_all["TOWNNAME"].astype(str).str.strip()
    gdf_all = gdf_all[~gdf_all["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf_all = gdf_all[~gdf_all.geometry.isna() & ~gdf_all.geometry.is_empty].copy()
    gdf_all = gdf_all.reset_index(drop=True)

    # 指定縣市的「無村里名」圖斑整筆不畫（港區/航道水域，含高雄東沙與南沙）
    if DROP_NAN_COUNTIES:
        _vv = gdf_all["VILLNAME"].fillna("").astype(str).str.strip()
        _drop = gdf_all["COUNTYNAME"].isin(DROP_NAN_COUNTIES) & _vv.isin(["", "nan", "None"])
        if int(_drop.sum()):
            _byc = gdf_all.loc[_drop, "COUNTYNAME"].value_counts().to_dict()
            _det = "、".join(f"{c}{n}筆" for c, n in _byc.items())
            print(f"  無村里名不畫（{ '、'.join(DROP_NAN_COUNTIES) }）：剔除 {int(_drop.sum())} 筆（{_det}）")
            gdf_all = gdf_all[~_drop].copy().reset_index(drop=True)

    # 遠離本島的圖斑處理（含屏東縣離島特例）
    gdf_all = strip_far_parts(gdf_all)
    EXPECT_CC = int(gdf_all.attrs.get("n_geo_comps", 1))

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
    fuzzy_cnt = int((gdf_all["match_type"].str.startswith("fuzzy", na=False)).sum())

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

    # 各候選人領先村里數：完全沒人領先的候選人不畫圖例欄
    _win = np.argmax(gdf_all.loc[has_data, rate_cols].fillna(0.0).to_numpy(dtype=float), axis=1)
    active_idx = [i for i in range(len(nat.CAND_NAMES)) if int((_win == i).sum()) > 0]
    for i, nm in enumerate(nat.CAND_NAMES):
        print(f"    領先村里：{nm} {int((_win == i).sum())} 村"
              + ("" if i in active_idx else " → 不畫圖例"))
    assert active_idx, "無任何候選人領先村里"

    # 圖例起點：全部村里中最低領先得票率向下取 5 的倍數
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
    # ② 區層：含未編定村里圖斑（港區/水域等），區界才完整。
    #    必須以 (縣市, 區) 為鍵——嘉義縣/嘉義市、高雄市/屏東縣等同名之區不可合併
    townships = records.dissolve(by=["COUNTYNAME", "TOWNNAME"]).reset_index()
    print(f"  縣市：{records['COUNTYNAME'].nunique()}，區：{len(townships)}，村里 {len(villages)}")
    for c in TARGET_COUNTIES:
        print(f"    {c}：村里 {int((records['COUNTYNAME'] == c).sum())}")

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

    # ----------------------② 區界 + 縣市界 + 海岸線----------------------
    print(f"  ② 區界 {LINE_TOWNSHIP_PX}px + 縣市界/海岸線 {LINE_OUTER_PX}px（matplotlib + 閾值二值化）...")
    town_layer = render_line_layer(townships, w_px, h_px, minx, maxx, miny, maxy,
                                   LINE_TOWNSHIP_PX, LINE_OUTER_PX, DPI, THRESHOLD_VAL)
    print(f"  區/縣市界層：{int(town_layer.sum())} px"
          f"（區界 {LINE_TOWNSHIP_PX}px、縣市界/外輪廓 {LINE_OUTER_PX}px，閾值 {THRESHOLD_VAL}）")

    # ----------------------① 村里界 1px----------------------
    print("  ① 村里界 1px（1px 直繪 → thin 中心線）...")
    village_lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
    village_arr = draw_layer(village_lines, 1, w_px, h_px, minx, maxy, sx, sy)
    village_skel = thin(village_arr)
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # 對齊自檢：② 層必須覆蓋區界/縣市界 1px 原始線
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())), 1,
                           w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(town_layer, structure=S3)).sum())
    print(f"  區/縣市界 1px 原始線 {int(_town_1px.sum())} px，"
          f"未被 {LINE_TOWNSHIP_PX}/{LINE_OUTER_PX}px 層覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層連通分量應等於幾何連通分量數（本島＋保留之離島/沙洲）
    _cc_n, _, _cc_st, _ = cv2.connectedComponentsWithStats(town_layer.astype(np.uint8), connectivity=8)
    _cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
    _cc_small = int((_cc_area <= 40).sum())
    print(f"  ② 層連通分量：{_cc_n - 1} 個（幾何期待 {EXPECT_CC}＝本島＋保留離島/沙洲）；"
          f"<=40px 小分量 {_cc_small} 個（應為 0）")
    if _cc_small or (_cc_n - 1) < EXPECT_CC:
        for _i in range(1, _cc_n):
            _x, _y, _w, _h, _a = _cc_st[_i]
            if _a <= 40:
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

    # ----------------------版面：圖例置於右上角（無標題）----------------------
    print("  圖例（右上角；不畫標題）...")
    W, H = pil_img.size
    title_img = (nat.render_text_image_cached(TITLE_LINES, TITLE_FONT_SIZE)
                 if TITLE_LINES else None)

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
    # 群組寬度須含「最後一欄的標籤」（無標題時 content_w 就等於它，否則會被裁掉）
    group_w = (n_cols - 1) * (col_width + nat.H_SPACING) + col_width
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + nat.COLUMN_TITLE_GAP + max_n * (nat.BLOCK_HEIGHT + nat.V_SPACING) - nat.V_SPACING

    LEGEND_X_MARGIN = 80
    TITLE_GAP = 70
    # 候選人姓名比色塊寬時，居中後會向左溢出；把面板起點再右移溢出量，
    # 保證姓名的左緣正好落在 LEGEND_X_MARGIN，不會壓到地圖區
    name_overhang = max(0, (max((im.width for im in name_imgs), default=0)
                            - nat.BLOCK_WIDTH + 1) // 2)
    panel_x = W + LEGEND_X_MARGIN + name_overhang
    title_w = title_img.width if title_img is not None else 0
    content_w = int(max(title_w, group_w))
    title_x = panel_x + (content_w - title_w) / 2
    legend_x = panel_x + (content_w - group_w) / 2
    new_W = int(panel_x + content_w + nat.LEGEND_PADDING)
    head_h = (title_img.height + TITLE_GAP) if title_img is not None else 0
    panel_content_h = head_h + legend_h
    new_H = int(max(H, panel_content_h + 2 * nat.LEGEND_PADDING))
    print(f"  版型：地圖 {W}x{H}，圖例寬 {int(group_w)}px（姓名溢出補正 {name_overhang}px）；"
          f"面板 x={int(panel_x)}、內容寬 {content_w}px（圖例置於右上角）")

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))
    del pil_img

    py = nat.LEGEND_PADDING
    if title_img is not None:
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

    # 存檔後自檢
    _re = np.asarray(Image.open(OUT_PNG).convert("RGB"))
    _off = (new_H - H) // 2
    _re_map = _re[_off:_off + H, :W]
    _u2, _c2 = np.unique(_re_map.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _nw2, _nout2 = full_geom_check(_re_map, records, w_px, h_px, minx, maxy, sx, sy)
    _tol2 = 0.0002 * w_px * h_px
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、"
          f"幾何參考差異 {_nw2} px（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    if _bad2 or _nout2 or _nw2 > _tol2:
        print(f"  ⚠️ bad={_bad2[:5]} wrong={_nw2} out={_nout2}")
    print(f"\n  Saved: {OUT_PNG}  ({final_img.width}×{final_img.height}px)")
    print("==== All finished ====")


# ===================== 圖資清理 =====================
def strip_far_parts(gdf, max_dist_nameless=REMOTE_MAX_DIST_M, max_dist_named=NAMED_MAX_DIST_M):
    """剔除遠離本島的離島圖斑與圖資錯誤碎塊，門檻依「該圖斑所屬記錄有無村里名」而異。

    作法是取全部圖斑的聯集，其最大連通分量即為本島；再對每個圖斑算與本島的距離：
      - 無村里名（無編制）者：> max_dist_nameless(2km) 即剔除
      - 有村里名（有編制）者：> max_dist_named(20km) 才剔除
      - 屏東縣特例（ISLAND_KEEP）：名單內鄉鎮（琉球鄉＝小琉球）一律保留；
        其餘屏東縣圖斑一旦脫離本島（> ISLAND_DETACH_M）即剔除

    實測（108 版村里界，雲嘉南高屏 2853 筆 / 2896 個圖斑）：
      - 剔除外海圖資錯誤碎塊（大溪里式）與無編制離島
      - 保留 雲林縣口湖鄉台子村的**外傘頂洲**等沙洲（0.5~2.3km，有村里編制）
      - 保留 屏東縣琉球鄉（小琉球，8 村，12.2~14.8km）
      - 高雄市旗津區的東沙/南沙（無村里名）已於 DROP_NAN_COUNTIES 前置移除
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

    owner = np.array(owner, dtype=int)
    vv = gdf["VILLNAME"].fillna("").astype(str).str.strip()
    named = (~vv.isin(["", "nan", "None"])).to_numpy()
    county = gdf["COUNTYNAME"].to_numpy()
    town = gdf["TOWNNAME"].to_numpy()
    dist = np.array([main.distance(pp) for pp in parts])

    thr = np.where(named[owner], max_dist_named, max_dist_nameless)
    keep_flags = dist <= thr

    # 屏東縣離島特例：除 ISLAND_KEEP 名單外，脫離本島的圖斑一律不畫
    for cname, keep_towns in ISLAND_KEEP.items():
        m = county[owner] == cname
        if not m.any():
            continue
        allowed = np.isin(town[owner], keep_towns)
        keep_flags[m] = allowed[m] | (dist[m] <= ISLAND_DETACH_M)

    dropped = np.nonzero(~keep_flags)[0]
    if len(dropped):
        print(f"  離島/碎塊清理：剔除 {len(dropped)} 個圖斑"
              f"（無村里名 > {max_dist_nameless / 1000:.0f}km、有村里名 > {max_dist_named / 1000:.0f}km、"
              f"屏東非琉球鄉 > {ISLAND_DETACH_M / 1000:.0f}km）")
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

    # 保留的有編制離島/沙洲——列出來供核對
    kept_far = [j for j in range(len(parts)) if keep_flags[j] and dist[j] > 500]
    if kept_far:
        import collections
        cnt = collections.Counter(owner[j] for j in kept_far)
        print("  保留離島/沙洲：")
        for i, n in cnt.most_common(12):
            ds = dist[[j for j in kept_far if owner[j] == i]]
            print(f"    {gdf['COUNTYNAME'].iloc[i]} {gdf['TOWNNAME'].iloc[i]} {vv.iloc[i]}"
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

    # ② 層連通分量自檢期待值＝保留幾何的連通分量數（僅計面積 >= MIN_COMP_AREA_M2 者）
    kept_geoms = [g for g in out.geometry if g is not None and not g.is_empty]
    if kept_geoms:
        u = unary_union(kept_geoms)
        ucs = list(u.geoms) if hasattr(u, "geoms") else [u]
        out.attrs["n_geo_comps"] = int(sum(1 for c in ucs if c.area >= MIN_COMP_AREA_M2))
    else:
        out.attrs["n_geo_comps"] = 1
    print(f"  幾何連通分量（面積 >= {MIN_COMP_AREA_M2:.0f} m²）：{out.attrs['n_geo_comps']}")
    return out


# ===================== 線稿工具 =====================
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
    畫 outer_px px——六縣市交界以較粗線清楚分隔。"""
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
