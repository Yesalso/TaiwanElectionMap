# -*- coding: utf-8 -*-
"""
金門馬祖版面測試圖（純版面測試，無得票填色）
=============================================

依使用者提供的示意圖（2026-11-03）生成版面測試圖：

  ┌──────────────────────────────┐
  │ 東引                  馬祖列島 │
  │ 北竿／南竿                     │   ← 馬祖（連江縣）＝主圖，
  │ 莒光           ┌───────────┐  │     島群散佈在主框左／上
  │               │ □虛線(烏坵) │  │
  │               │  烈嶼  金門本島│  │   ← 金門框嵌在主框右下角
  └───────────────┴───────────┴──┘     （右緣、底緣與主框重合）

版面規則（2026-11-03 使用者指定）：
  1. 馬祖（連江縣）為主圖：主框＝連江圖斑外接矩形＋留白，佔畫布左上／絕大部分；
     島群（東引、北竿、南竿、莒光及全部無名礁石）按真實相對位置分佈。
  2. 主框右下方為空白海域，**金門框**嵌入該區域右下角，
     金門框的右緣、底緣與主框重合（示意圖中兩框共邊）。
  3. 金門框內：金門本島＋烈嶼等按真實比例繪製（內容貼框左下），
     各鄉鎮之間畫白色界線（示意圖同款）。
  4. **烏坵鄉**（大坵、小坵）不依實際距離擺放（實際距金門本島約 120 km，
     照實擺會把金門框撐爆），另以**黑色虛線小框**嵌在金門框的**右下角**
     （使用者指定；示意圖原本畫在右上）。
  5. **全圖統一比例尺（1:1）**：馬祖、金門、烏坵同一比例，烏坵不另外放大
     （使用者指定：不要擅自放大烏坵鄉）。金門框、烏坵虛線框的大小均由
     各自圖斑的真實外接矩形＋留白決定。
     ※ 唯一例外：距金門主島群超過 `KM_FAR_KM` 的遠島部件（東碇島等）本測試圖
       不畫（示意圖未含；正式版仍全數保留），否則金門框會被撐大、本島群縮小。

底圖：民國 106 年村里界（VILLAGE_MOI_1070205.shp）——金門／連江同一套圖資，
     村里完整並含烏坵鄉（大坵村、小坵村），與正式版 Draw_Taiwan_AtLarge_2008.py
     的金馬拼接來源一致。無名礁石全數保留（只統計、不剔除）。

輸出：LegislationYuan/maps/金門馬祖版面測試_馬祖主圖_金門右下.png
執行：uv run --no-project -p 3.14 --with geopandas --with matplotlib \
        --with pyogrio scripts/atlarge/Draw_Kinmen_Matsu_Layout_Test.py
"""
import os
import math
import warnings

import geopandas as gpd
import pandas as pd
from shapely.affinity import affine_transform
from shapely.geometry import Polygon

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))       # …\2008Legislator-at-Large
ROOT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))         # …\TaiwanElection

# ---- 底圖（與正式版同一套金馬圖資） ----
SHP_106 = os.path.join(r"D:\Windows\Documents\村里界歷史圖資_111",
                       "村里界歷史圖資_106", "村里界歷史圖資_106",
                       "VILLAGE_MOI_1070205.shp")
TARGET_CRS = "EPSG:3826"

OUT_DIR = os.path.join(ROOT_DIR, "LegislationYuan", "maps")
OUT_PNG = os.path.join(OUT_DIR, "金門馬祖版面測試_馬祖主圖_金門右下.png")

# ---- 版面參數 ----
MAIN_PAD_FRAC = 0.030        # 馬祖圖斑 → 主框的留白（佔主框寬/高）
CANVAS_PAD_FRAC = 0.020      # 主框 → 畫布邊緣的留白
KM_FAR_KM = 26.0             # 距金門主島群中位中心超過此距離的遠島部件不畫
                             #     （東碇島等，示意圖未含；正式版仍全數保留）
GAP_FRAC = 0.05              # 框內留白基準（佔金門內容高；馬祖側另有 MAIN_PAD_FRAC）
WUQIU_PAD_EXTRA = 1.0        # 烏坵虛線框在圖斑外接矩形外再加 GAP_FRAC×此係數 的留白

METERS_PER_PIXEL = 12.0      # 1 px = 12 m（與正式版一致）
DPI = 100
MAX_W_PX, MAX_H_PX = 10000, 12500

# ---- 配色（對照示意圖） ----
BG_COLOR = "#FFFFFF"         # 背景：白
ISLAND_FILL = "#1B3A5C"      # 島嶼填充：深藏青（示意圖同款）
TOWN_LINE = "#FFFFFF"        # 金門鄉鎮界：白
FRAME_COLOR = "#000000"      # 主框／金門框：黑
FRAME_LW_PX = 2              # 主框、金門框線寬（px）
WUQIU_LW_PX = 1.5            # 烏坵虛線框線寬（px）
DASH_PATTERN = (6, 4)        # 虛線樣式


def read_shp(path=SHP_106):
    """讀 106 年村里界 SHP，僅取金門／連江；礁石（無村里名）全數保留。"""
    g, err = None, None
    for enc in ("utf-8", "cp950"):
        try:
            g = gpd.read_file(path, encoding=enc)
            break
        except UnicodeDecodeError as e:
            err = e
    if g is None:
        raise err
    if g.crs is None:                     # SHP 無內建 CRS → 視為 WGS84（同正式版）
        g = g.set_crs("EPSG:4326")
    g = g.to_crs(TARGET_CRS)
    for c in ("COUNTYNAME", "TOWNNAME", "VILLNAME"):
        if c not in g.columns:
            raise KeyError(f"{os.path.basename(path)} 缳少欄位 {c}")
        g[c] = g[c].apply(lambda x: "" if pd.isna(x) else str(x).strip())
    g["geometry"] = g.geometry.buffer(0)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty]
    g = g[g["COUNTYNAME"].isin(("金門縣", "連江縣"))].copy().reset_index(drop=True)
    return g


def affine_scale_translate(gdf, scale, tx, ty):
    """等比縮放後，把圖斑自身 bounds 的左下角 (x0, y0) 放到目標位置 (tx, ty)。"""
    x0, y0, _x1, _y1 = gdf.total_bounds
    # affine_transform: [a,b,d,e,c,f] → x' = a*x + e*y + c；y0 縮放後恰好落在 ty
    mat = [scale, 0.0, 0.0, scale, tx - scale * x0, ty - scale * y0]
    out = gdf.copy()
    out["geometry"] = out.geometry.apply(lambda g: affine_transform(g, mat))
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 66)
    print("  金門馬祖版面測試圖（馬祖主圖＋金門右下＋烏坵嵌角）")
    print("=" * 66)

    # ---- ① 底圖 ----
    gdf = read_shp()
    n_reef = int((gdf["VILLNAME"] == "").sum())
    print(f"  底圖：106 年村里界 → 金門＋連江共 {len(gdf)} 個村里圖斑"
          f"（含無村里名礁石 {n_reef} 塊，全數保留）")

    matsu = gdf[gdf["COUNTYNAME"] == "連江縣"].copy()
    is_wuqiu = (gdf["COUNTYNAME"] == "金門縣") & (gdf["TOWNNAME"] == "烏坵鄉")
    kinmen = gdf[(gdf["COUNTYNAME"] == "金門縣") & ~is_wuqiu].copy()
    wuqiu = gdf[is_wuqiu].copy()
    print(f"  馬祖 {len(matsu)} 圖斑、金門（不含烏坵）{len(kinmen)} 圖斑、"
          f"烏坵 {len(wuqiu)} 圖斑")

    # 剔除遠島部件（東碇島等）：多村里圖斑先 explode 到「單一多邊形部件」再判距離，
    # 以免烈嶼鄉上岐村（大膽＋二膽＋東碇同一筆 MultiPolygon）整筆被誤刪。
    kinmen = kinmen.explode(index_parts=False).reset_index(drop=True)
    _c = kinmen.geometry.centroid
    med_cx, med_cy = float(_c.x.median()), float(_c.y.median())
    _d_km = ((kinmen.geometry.centroid.x - med_cx) ** 2
             + (kinmen.geometry.centroid.y - med_cy) ** 2).pow(0.5) / 1000.0
    _far = _d_km > KM_FAR_KM
    if int(_far.sum()):
        _names = (kinmen.loc[_far, "TOWNNAME"].astype(str) + "／"
                  + kinmen.loc[_far, "VILLNAME"].astype(str)).value_counts().to_dict()
        print(f"  剔除遠島部件 {int(_far.sum())} 塊（距主島群中位中心 > {KM_FAR_KM:.0f} km，"
              f"示意圖未含；正式版仍全數保留）：{_names}")
        kinmen = kinmen[~_far].copy().reset_index(drop=True)

    # ---- ② 版面（全圖統一比例尺 1:1：馬祖、金門、烏坵同一比例，烏坵不放大） ----
    # 主框：馬祖圖斑 bounds ＋ 留白
    mx0, my0, mx1, my1 = matsu.total_bounds
    mw, mh = mx1 - mx0, my1 - my0
    pad_x, pad_y = MAIN_PAD_FRAC / (1.0 - 2.0 * MAIN_PAD_FRAC) * mw, \
                   MAIN_PAD_FRAC / (1.0 - 2.0 * MAIN_PAD_FRAC) * mh
    fx0, fy0, fx1, fy1 = mx0 - pad_x, my0 - pad_y, mx1 + pad_x, my1 + pad_y
    fw, fh = fx1 - fx0, fy1 - fy0
    print(f"  馬祖圖斑範圍 {mw / 1000:.1f} × {mh / 1000:.1f} km → "
          f"主框 {fw / 1000:.1f} × {fh / 1000:.1f} km")

    # 金門框：嵌在主框右下角，右緣、底緣與主框重合（示意圖兩框共邊）。
    # 框的大小由金門內容（1:1）＋烏坵虛線框＋留白決定：
    #   水平：[留白][金門內容][留白][烏坵虛線框][留白]（內容貼左下、烏坵框貼右下）
    #   垂直：[留白][內容／烏坵框（都貼底）][留白]
    kx0g, ky0g, kx1g, ky1g = kinmen.total_bounds
    kcw, kch = kx1g - kx0g, ky1g - ky0g
    g = GAP_FRAC * kch                                # 框內留白基準（米）
    wx0g, wy0g, wx1g, wy1g = wuqiu.total_bounds
    wcw, wch = wx1g - wx0g, wy1g - wy0g
    uw = wcw + 2 * g * WUQIU_PAD_EXTRA                # 烏坵虛線框寬（圖斑＋留白）
    uh = wch + 2 * g * WUQIU_PAD_EXTRA                # 烏坵虛線框高
    kw = kcw + uw + 3 * g
    kh = max(kch, uh) + 2 * g
    kx0, ky0, kx1, ky1 = fx1 - kw, fy0, fx1, fy0 + kh
    print(f"  金門框 {kw / 1000:.1f} × {kh / 1000:.1f} km"
          f"（主框的 {kw / fw:.2f} × {kh / fh:.2f}，右下角共邊；內容 1:1）")

    # 金門內容：1:1（僅平移），貼金門框左下
    k_tx, k_ty = kx0 + g, ky0 + g
    kinmen_t = affine_scale_translate(kinmen, 1.0, k_tx, k_ty)
    print(f"  金門圖斑 {kcw / 1000:.1f} × {kch / 1000:.1f} km（1:1，貼框左下）")

    # 烏坵虛線小框：嵌在金門框右下角（使用者指定；示意圖原本畫在右上），
    # 同一比例尺 1:1、不放大，烏坵圖斑在虛線框內置中
    ux1, uy0 = kx1 - g, ky0 + g
    ux0, uy1 = ux1 - uw, uy0 + uh
    wuqiu_t = None
    if len(wuqiu):
        w_tx = (ux0 + ux1) / 2.0 - wcw / 2.0          # 虛線框內水平置中
        w_ty = (uy0 + uy1) / 2.0 - wch / 2.0          # 虛線框內垂直置中
        wuqiu_t = affine_scale_translate(wuqiu, 1.0, w_tx, w_ty)
        print(f"  烏坵虛線框 {uw / 1000:.1f} × {uh / 1000:.1f} km（金門框右下角），"
              f"烏坵圖斑 {wcw / 1000:.1f} × {wch / 1000:.1f} km（1:1，不放大）")

    # 自檢：金門框（與烏坵虛線框）必須完全落在空白海域，不得壓到馬祖任何圖斑
    km_box = Polygon([(kx0, ky0), (kx1, ky0), (kx1, ky1), (kx0, ky1)])
    n_hit = int(matsu.geometry.intersects(km_box).sum())
    print(f"  自檢：金門框壓到馬祖圖斑 {n_hit} 塊（應為 0）")

    # 畫布：主框 ＋ 邊距
    c_pad_x, c_pad_y = CANVAS_PAD_FRAC * fw, CANVAS_PAD_FRAC * fh
    cx0, cy0, cx1, cy1 = fx0 - c_pad_x, fy0 - c_pad_y, fx1 + c_pad_x, fy1 + c_pad_y
    geo_w, geo_h = cx1 - cx0, cy1 - cy0
    scale = max(geo_w / MAX_W_PX, geo_h / MAX_H_PX, METERS_PER_PIXEL)
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（上限 {MAX_W_PX}×{MAX_H_PX}）")

    # ---- ③ 繪製 ----
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(cx0, cx1)
    ax.set_ylim(cy0, cy1)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    px2pt = 72.0 / DPI

    # 馬祖（主圖）：整體填深藏青，不畫村里內線（示意圖同款純色）
    matsu.plot(ax=ax, facecolor=ISLAND_FILL, edgecolor=ISLAND_FILL, linewidth=0.4)
    # 主框：黑色實線
    ax.add_patch(Rectangle((fx0, fy0), fw, fh, fill=False,
                           edgecolor=FRAME_COLOR,
                           linewidth=FRAME_LW_PX * px2pt, zorder=5))

    # 金門（金門框內）：填深藏青；鄉鎮之間畫白色界線（示意圖同款）
    kinmen_t.plot(ax=ax, facecolor=ISLAND_FILL, edgecolor=ISLAND_FILL, linewidth=0.4)
    towns = kinmen_t[kinmen_t["TOWNNAME"] != ""].dissolve(by="TOWNNAME").reset_index()
    towns.boundary.plot(ax=ax, color=TOWN_LINE, linewidth=1.0 * px2pt, zorder=3)
    # 金門框：黑色實線
    ax.add_patch(Rectangle((kx0, ky0), kw, kh, fill=False,
                           edgecolor=FRAME_COLOR,
                           linewidth=FRAME_LW_PX * px2pt, zorder=5))

    # 烏坵：填深藏青；虛線小框（示意圖同款黑色虛線）
    if wuqiu_t is not None:
        wuqiu_t.plot(ax=ax, facecolor=ISLAND_FILL, edgecolor=ISLAND_FILL,
                     linewidth=0.4, zorder=4)
    ax.add_patch(Rectangle((ux0, uy0), uw, uh, fill=False,
                           edgecolor=FRAME_COLOR, linewidth=WUQIU_LW_PX * px2pt,
                           linestyle=(0, DASH_PATTERN), zorder=5))

    out = os.path.join(OUT_DIR, os.path.basename(OUT_PNG))
    fig.savefig(out, dpi=DPI, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  輸出：{out}")


if __name__ == "__main__":
    main()
