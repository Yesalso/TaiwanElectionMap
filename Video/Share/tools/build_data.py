# -*- coding: utf-8 -*-
"""
build_data.py
=============
把 2014 新北市長選舉的村里得票資料 + 新北市鄉鎮市區邊界，
整理成前端可直接載入的 JS 資料檔（免 http server，file:// 可直接開）。

輸出：
  Share/data/election-2014.js   選舉資料（總計、29 區得票、地圖 GeoJSON）
  Share/assets/candidates.js    候選人照片（base64 data URI）+ 標準化後的去背圖

用法：
  python build_data.py
"""

import base64
import json
import os

import geopandas as gpd
import numpy as np
import openpyxl

# --------------------------------------------------------------------------
# 路徑設定
# --------------------------------------------------------------------------
ROOT = r"D:\Windows\TaiwanElection"
SHARE = os.path.join(ROOT, "Video", "Share")
DATA_DIR = os.path.join(SHARE, "data")
ASSET_DIR = os.path.join(SHARE, "assets")

XLS_VOTE = os.path.join(ROOT, "MayoralElections", "data", "2014新北.xlsx")
XLS_RATE = os.path.join(ROOT, "MayoralElections", "data", "2014新北_得票率.xlsx")
SHP = r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp"

PHOTO_ZHU = os.path.join(ROOT, "Video", "2014NewTaipei", "candidate", "朱立伦.png")
PHOTO_YOU = os.path.join(ROOT, "Video", "2014NewTaipei", "candidate", "游锡堃.png")

# 收斂到 29 個行政區的標準名稱（資料檔裡的簡稱 -> 全名）
TOWN_FULL = {
    "板橋": "板橋區", "三重": "三重區", "中和": "中和區", "永和": "永和區",
    "新莊": "新莊區", "新店": "新店區", "樹林": "樹林區", "鶯歌": "鶯歌區",
    "三峽": "三峽區", "淡水": "淡水區", "汐止": "汐止區", "瑞芳": "瑞芳區",
    "土城": "土城區", "蘆洲": "蘆洲區", "五股": "五股區", "泰山": "泰山區",
    "林口": "林口區", "深坑": "深坑區", "石碇": "石碇區", "坪林": "坪林區",
    "三芝": "三芝區", "石門": "石門區", "八里": "八里區", "平溪": "平溪區",
    "雙溪": "雙溪區", "貢寮": "貢寮區", "金山": "金山區", "萬里": "萬里區",
    "烏來": "烏來區",
}

# 官方公告數字（中選會）：第三位候選人不在村里檔中，單獨補上
OFFICIAL = {
    "zhu":  {"name": "朱立倫", "party": "中國國民黨", "party_short": "KMT",
             "party_en": "Kuomintang", "number": 3, "votes": 959302},
    "you":  {"name": "游錫堃", "party": "民主進步黨", "party_short": "DPP",
             "party_en": "Democratic Progressive Party", "number": 1, "votes": 934774},
    "lee":  {"name": "李進順", "party": "無黨籍", "party_short": "IND",
             "party_en": "Independent", "number": 2, "votes": 22207},
}
TOTAL_VALID = 1916283      # 有效票
TOTAL_CAST = 1946063       # 實際投票數
TOTAL_INVALID = 29780      # 無效票
ELECTORATE = 3156402       # 選舉人數


# --------------------------------------------------------------------------
# 1. 讀村里得票，聚合成 29 區
# --------------------------------------------------------------------------
def build_districts():
    wb = openpyxl.load_workbook(XLS_VOTE, data_only=True)
    ws = wb["Sheet1"]
    agg = {}
    for r in range(1, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if not name:
            continue
        rest = str(name).replace("新北市", "", 1)
        idx = rest.find("區")
        short = rest[:idx] if idx >= 0 else rest
        zhu = ws.cell(r, 4).value or 0
        you = ws.cell(r, 9).value or 0
        if short not in agg:
            agg[short] = {"zhu": 0, "you": 0, "villages": 0}
        agg[short]["zhu"] += zhu
        agg[short]["you"] += you
        agg[short]["villages"] += 1

    out = []
    for short, v in agg.items():
        z, y = v["zhu"], v["you"]
        valid = z + y
        out.append({
            "town": TOWN_FULL.get(short, short + "區"),
            "short": short,
            "villages": v["villages"],
            "zhu": z,
            "you": y,
            "valid": valid,
            "zhuPct": round(z / valid * 100, 2),
            "youPct": round(y / valid * 100, 2),
            "winner": "zhu" if z > y else "you",
            "margin": round(abs(z - y) / valid * 100, 2),
        })
    out.sort(key=lambda d: -d["valid"])
    return out


# --------------------------------------------------------------------------
# 2. 由村里界 shapefile 產生 29 區 GeoJSON（WGS84、簡化、座標取 5 位小數）
# --------------------------------------------------------------------------
def build_geojson():
    gdf = gpd.read_file(SHP, encoding="UTF-8")
    gdf = gdf[gdf["COUNTYNAME"] == "新北市"].copy()
    gdf = gdf[gdf["TOWNNAME"].notna() & gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    gdf = gdf.to_crs(epsg=3826)
    town = gdf.dissolve(by="TOWNNAME").reset_index()
    # 簡化：容差 60 公尺（投影座標單位 = 公尺）
    town["geometry"] = town["geometry"].simplify(60, preserve_topology=True)
    town = town.to_crs(epsg=4326)

    features = []
    for _, row in town.iterrows():
        geom = json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"]
        features.append({"type": "Feature",
                         "properties": {"town": row["TOWNNAME"]},
                         "geometry": _round_geom(geom)})
    return {"type": "FeatureCollection", "features": features}


def _round_geom(geom):
    def r(ring):
        return [[round(x, 5), round(y, 5)] for x, y in ring]
    t = geom["type"]
    if t == "Polygon":
        return {"type": "Polygon", "coordinates": [r(c) for c in geom["coordinates"]]}
    return {"type": "MultiPolygon",
            "coordinates": [[r(c) for c in poly] for poly in geom["coordinates"]]}


# --------------------------------------------------------------------------
# 3. 候選人照片 -> 透明背景去背圖 + base64
# --------------------------------------------------------------------------
def imread_u(path):
    import cv2
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite_u(path, img):
    import cv2
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    if ok:
        buf.tofile(path)
    return ok


def build_bg_model(img):
    """逐列建立背景色模型（由左右邊界取樣），可適應垂直漸層背景。
    自影像上緣往下逐列檢查：左右邊界顏色相近、且與前一段背景顏色連續時才採用；
    一旦遇到主體（例如西裝肩線）就停止，之後的列沿用最後一段背景色。"""
    import cv2
    h, w = img.shape[:2]
    s = max(3, int(w * 0.02))
    left = np.median(img[:, :s].astype(np.float32), axis=1)
    right = np.median(img[:, -s:].astype(np.float32), axis=1)
    row = (left + right) / 2.0

    ref = row[min(h - 1, max(2, int(h * 0.04)))]
    limit = h
    for y in range(max(2, int(h * 0.03)), h):
        if np.linalg.norm(left[y] - right[y]) > 40:
            limit = y
            break
        if np.linalg.norm(row[y] - ref) > 45:
            limit = y
            break
        ref = 0.85 * ref + 0.15 * row[y]
    limit = max(limit, int(h * 0.35))
    row[limit:] = row[limit - 1]
    row = cv2.GaussianBlur(row.reshape(-1, 1, 3), (0, 0), 6.0).reshape(-1, 3)
    return np.repeat(row[:, None, :], w, axis=1)


def cutout_alpha(img, iters=8, debug=False):
    """以 seeded GrabCut + 背景色模型，取出人像 alpha（0~255）。"""
    import cv2
    h, w = img.shape[:2]
    bg_model = build_bg_model(img)
    dist = cv2.GaussianBlur(
        np.linalg.norm(img.astype(np.float32) - bg_model, axis=2), (0, 0), 1.6)

    # 初始遮罩：預設「可能背景」；外框與接近背景色者 → 確定背景；臉部橢圓 → 確定前景
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    tb = max(2, int(h * 0.012))
    sb = max(2, int(w * 0.02))
    mask[:tb, :] = cv2.GC_BGD
    mask[:, :sb] = cv2.GC_BGD
    mask[:, -sb:] = cv2.GC_BGD
    mask[dist < 35] = cv2.GC_BGD
    mask[dist > 80] = cv2.GC_PR_FGD
    cv2.ellipse(mask, (w // 2, int(h * 0.30)),
                (int(w * 0.20), int(h * 0.24)), 0, 0, 360, cv2.GC_FGD, -1)

    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # 與上／左／右邊界相連、且顏色接近背景模型的區域 → 一律視為背景
    near_bg = cv2.morphologyEx((dist < 48).astype(np.uint8), cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    ffill = (near_bg & (alpha > 0)).astype(np.uint8)
    mm = np.zeros((h + 2, w + 2), np.uint8)
    seeds = ([(x, 0) for x in range(w)]
             + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    for sx, sy in seeds:
        if ffill[sy, sx] == 1 and mm[sy + 1, sx + 1] == 0:
            cv2.floodFill(ffill, mm, (sx, sy), 2)
    alpha[ffill == 2] = 0

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, k, iterations=2)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, k, iterations=1)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(alpha, 8)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        alpha = np.where(lbl == big, 255, 0).astype(np.uint8)
    ff = alpha.copy()
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 128)
    alpha[(ff != 128) & (alpha == 0)] = 255

    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.6)
    alpha = np.clip((alpha.astype(np.float32) - 100.0) * 2.0, 0, 255).astype(np.uint8)

    if debug:
        imwrite_u(os.path.join(ASSET_DIR, "_dbg_dist.png"),
                  np.clip(dist, 0, 255).astype(np.uint8))
        imwrite_u(os.path.join(ASSET_DIR, "_dbg_mask.png"),
                  np.where(mask == cv2.GC_FGD, 255,
                           np.where(mask == cv2.GC_PR_FGD, 128, 0)).astype(np.uint8))
        imwrite_u(os.path.join(ASSET_DIR, "_dbg_alpha.png"), alpha)
    return alpha


def make_card(img, alpha, out_w, out_h, side_pad=0.06, top_pad=0.06, bottom_fade=0.14):
    """依 alpha 的主體範圍裁切，輸出固定尺寸的透明立繪卡。"""
    import cv2
    ys, xs = np.nonzero(alpha > 120)
    x0, x1 = int(xs.min()), int(xs.max())
    y0 = int(ys.min())
    cx = (x0 + x1) / 2.0
    cw = max(x1 - x0, 1) * (1.0 + side_pad * 2)
    ch = cw * (out_h / out_w)
    left = int(round(cx - cw / 2))
    top = int(round(y0 - ch * top_pad))
    h, w = alpha.shape
    left = max(0, min(left, max(0, w - int(cw))))
    top = max(0, top)
    right, bottom = left + int(cw), top + int(ch)
    rgba = cv2.merge([img[:, :, 0], img[:, :, 1], img[:, :, 2], alpha])
    pad_b, pad_r = max(0, bottom - h), max(0, right - w)
    if pad_b or pad_r:
        rgba = cv2.copyMakeBorder(rgba, 0, pad_b, 0, pad_r,
                                  cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        bottom, right = rgba.shape[0], rgba.shape[1]
    card = rgba[top:bottom, left:right]
    card = cv2.resize(card, (out_w, out_h), interpolation=cv2.INTER_AREA)
    fh = int(out_h * bottom_fade)
    ramp = np.ones(out_h, np.float32)
    ramp[out_h - fh:] = np.linspace(1.0, 0.0, fh) ** 1.35
    card[:, :, 3] = (card[:, :, 3].astype(np.float32) * ramp[:, None]).astype(np.uint8)
    return card


def build_photos(debug=False):
    """把候選人照片去背，輸出透明立繪 PNG，並回傳 {key: data_uri}。"""
    cards = {"zhu": (860, 1180), "you": (860, 1180)}
    res = {}
    for key, src in (("zhu", PHOTO_ZHU), ("you", PHOTO_YOU)):
        img = imread_u(src)
        alpha = cutout_alpha(img, debug=debug)
        card = make_card(img, alpha, cards[key][0], cards[key][1])
        out_png = os.path.join(ASSET_DIR, "candidate_%s.png" % key)
        imwrite_u(out_png, card)
        with open(out_png, "rb") as f:
            res[key] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return res


# --------------------------------------------------------------------------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ASSET_DIR, exist_ok=True)

    districts = build_districts()
    geojson = build_geojson()
    photos = build_photos()

    total_two = sum(d["valid"] for d in districts)
    payload = {
        "meta": {
            "election": "第二屆新北市市長選舉",
            "electionEn": "New Taipei City Mayoral Election",
            "year": 2014,
            "date": "11月29日",
            "dateEn": "29 Nov",
            "country": "中華民國（台灣）",
            "countryEn": "Republic of China (Taiwan)",
            "office": "新北市市長",
            "officeEn": "Mayor of New Taipei City",
            "electorate": ELECTORATE,
            "turnout": round(TOTAL_CAST / ELECTORATE * 100, 2),
            "validVotes": TOTAL_VALID,
            "invalidVotes": TOTAL_INVALID,
            "castVotes": TOTAL_CAST,
        },
        "candidates": {
            "zhu": dict(OFFICIAL["zhu"], votes=OFFICIAL["zhu"]["votes"],
                        pct=round(OFFICIAL["zhu"]["votes"] / TOTAL_VALID * 100, 2),
                        share=round(OFFICIAL["zhu"]["votes"] / TOTAL_CAST * 100, 2),
                        elected=True),
            "you": dict(OFFICIAL["you"], votes=OFFICIAL["you"]["votes"],
                        pct=round(OFFICIAL["you"]["votes"] / TOTAL_VALID * 100, 2),
                        share=round(OFFICIAL["you"]["votes"] / TOTAL_CAST * 100, 2)),
            "lee": dict(OFFICIAL["lee"], votes=OFFICIAL["lee"]["votes"],
                        pct=round(OFFICIAL["lee"]["votes"] / TOTAL_VALID * 100, 2),
                        share=round(OFFICIAL["lee"]["votes"] / TOTAL_CAST * 100, 2)),
        },
        "districts": districts,
        "geojson": geojson,
        "photos": photos,
    }

    js = "/* 自動產生，請勿手改。來源：2014新北.xlsx / 村里界歷史圖資_111 */\n"
    js += "window.ELECTION_2014 = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    out = os.path.join(DATA_DIR, "election-2014.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write(js)

    print("村里兩候選人票數合計 =", total_two)
    print("行政區數 =", len(districts))
    kmt = sum(1 for d in districts if d["winner"] == "zhu")
    print("朱立倫勝 =", kmt, " 游錫堃勝 =", len(districts) - kmt)
    print("GeoJSON features =", len(geojson["features"]))
    print("輸出:", out, f"({os.path.getsize(out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
