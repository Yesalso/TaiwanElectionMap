# -*- coding: utf-8 -*-
"""
鄉鎮市區「唯一色」底圖 → 縣市單色底圖：共用引擎。

適用於 County/Colorful2.png（22 縣市時期）與 Colorful4.png（25 縣市時期）：
兩張圖同為 3203×4404、同一套 380 色色板（368 個鄉鎮市區各一唯一色），
線條編碼也相同：
    白色 #FFFFFF  = 鄉鎮市區界線（要抹去）
    黑色 #000000  = 縣市界線（保留）
    #0066CC       = 海岸線（保留）
    #323232       = 畫布底色／海域（保留）
    #7F7F7F       = 左上角大陸海岸、小圖外框（保留）

使用方式見 make_22county_map.py / make_25county_map.py。
"""
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

# 原圖保留色
CANVAS_COLOR = (0x32, 0x32, 0x32)
BORDER_BLACK = (0x00, 0x00, 0x00)
COAST_BLUE = (0x00, 0x66, 0xCC)
LINE_WHITE = (0xFF, 0xFF, 0xFF)

# 白色像素要判定為「鄉鎮界線」所需的鄰近鄉鎮色像素數（8 鄰域）
LINE_MIN_TOWN_NEIGHBORS = 3


# ===================== 顏色工具 =====================
def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def rgb_to_lab(rgb_arr):
    """sRGB(0-255) → CIE L*a*b*（D65）。"""
    c = np.asarray(rgb_arr, dtype=np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = (c @ m.T) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def hsv_to_rgb(h, s, v):
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


# ===================== 配色 =====================
def build_candidate_colors():
    """配色候選：整圈色相 × 六檔明度／飽和度（避免純螢光色，印刷較耐看）。"""
    TONES = [(0.45, 0.98), (0.60, 0.92), (0.75, 0.88),
             (0.88, 0.78), (0.95, 0.66), (0.55, 0.80)]
    cands = []
    for hi in range(0, 360, 2):
        for s, v in TONES:
            r, g, b = hsv_to_rgb(hi / 360.0, s, v)
            cands.append((int(round(r * 255)), int(round(g * 255)), int(round(b * 255))))
    return np.array(sorted(set(cands)), dtype=np.uint8)


def pick_palette(n, avoid_rgb=()):
    """挑 n 個顏色：先最遠點取樣，再區域搜尋把「任兩色最小色差」推到最大。"""
    cands = build_candidate_colors()
    lab = rgb_to_lab(cands).astype(np.float64)
    # 太暗（對深海背景不清楚）或太接近保留色的先剔除
    ok = lab[:, 0] >= 46
    if len(avoid_rgb):
        avoid = rgb_to_lab(np.array(avoid_rgb, dtype=np.uint8)).astype(np.float64)
        dmin = np.min(np.linalg.norm(lab[:, None, :] - avoid[None, :, :], axis=-1), axis=1)
        ok &= dmin >= 30
    idx = np.nonzero(ok)[0]
    cands, lab = cands[idx], lab[idx]

    # --- 初始：最遠點取樣 ---
    start = int(np.argmin(np.linalg.norm(lab - rgb_to_lab(np.array([228, 50, 43])), axis=1)))
    chosen = [start]
    dist = np.linalg.norm(lab - lab[start], axis=1)
    for _ in range(n - 1):
        nxt = int(np.argmax(dist))
        chosen.append(nxt)
        dist = np.minimum(dist, np.linalg.norm(lab - lab[nxt], axis=1))
    chosen = np.array(chosen)

    # --- 區域搜尋：每次處理最接近的一對 ---
    D = np.linalg.norm(lab[chosen][:, None, :] - lab[chosen][None, :, :], axis=-1)
    for _ in range(400):
        cur = D.copy()
        np.fill_diagonal(cur, np.inf)
        i, j = np.unravel_index(int(np.argmin(cur)), cur.shape)
        worst = cur[i, j]
        improved = False
        for k in (i, j):
            others = np.delete(chosen, k)
            dmin = np.min(np.linalg.norm(lab[:, None, :] - lab[others][None, :, :], axis=-1), axis=1)
            dmin[chosen] = -1.0          # 不可與已有的重複
            best = int(np.argmax(dmin))
            if dmin[best] > worst + 1e-6:
                chosen[k] = best
                D = np.linalg.norm(lab[chosen][:, None, :] - lab[chosen][None, :, :], axis=-1)
                improved = True
                break
        if not improved:
            break

    return [tuple(int(v) for v in cands[i]) for i in chosen]


def county_adjacency(label):
    """回傳縣市相鄰關係（含斜角、跨 1px 縣市界線）。"""
    pairs = set()
    r = 4
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dy == 0 and dx == 0) or abs(dy) + abs(dx) > r + 2:
                continue
            a = label
            b = np.roll(np.roll(label, dy, 0), dx, 1)
            m = (a > 0) & (b > 0) & (a != b)
            if not m.any():
                continue
            code = a[m].astype(np.int32) * 256 + b[m].astype(np.int32)
            for c in np.unique(code):
                x, y = int(c) // 256, int(c) % 256
                pairs.add((min(x, y), max(x, y)))
    return pairs


def assign_colors(n, pairs, seed=20261119):
    """配色指派：最大化「相鄰縣市」的最小色差（隨機初始 + 兩兩交換爬山）。"""
    palette = pick_palette(n, avoid_rgb=(CANVAS_COLOR, BORDER_BLACK, COAST_BLUE))
    lab = rgb_to_lab(np.array(palette, dtype=np.uint8))
    D = np.linalg.norm(lab[:, None, :] - lab[None, :, :], axis=-1)

    # pairs 用 1-based 標籤 → 0-based 索引
    ei = np.array([a - 1 for a, b in sorted(pairs)])
    ej = np.array([b - 1 for a, b in sorted(pairs)])

    def score(assign):
        return D[assign[ei], assign[ej]].min()

    rng = np.random.default_rng(seed)
    best_assign, best_score = None, -1.0
    for _ in range(200):
        cur = rng.permutation(n)
        cur_s = score(cur)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                for j in range(i + 1, n):
                    cur[i], cur[j] = cur[j], cur[i]
                    s = score(cur)
                    if s > cur_s + 1e-9:
                        cur_s, improved = s, True
                    else:
                        cur[i], cur[j] = cur[j], cur[i]
        if cur_s > best_score:
            best_score, best_assign = cur_s, cur.copy()

    colors = [None] * n
    for county_idx, pal_idx in enumerate(best_assign):
        colors[county_idx] = palette[pal_idx]
    return colors, best_score


# ===================== 對照表 / 標籤圖 =====================
def load_correspondence(xlsx):
    """回傳 list[dict]: id / hex / county22 / town"""
    df = pd.read_excel(xlsx, header=None)
    rows = []
    for i in range(1, len(df)):
        if pd.isna(df.iloc[i, 0]):
            continue
        rows.append({
            "id": int(df.iloc[i, 0]),
            "hex": str(df.iloc[i, 1]).strip().upper(),
            "county22": str(df.iloc[i, 7]).strip(),
            "town": str(df.iloc[i, 8]).strip(),
        })
    return rows


def build_label_map(rgb, townships):
    """以顏色為鍵，產生縣市標籤圖（0 = 非鄉鎮色）；townships 需有 hex / label。"""
    color2label = {}
    for t in townships:
        r, g, b = hex2rgb(t["hex"])
        color2label[(r << 16) | (g << 8) | b] = t["label"]
    key = ((rgb[..., 0].astype(np.int32) << 16)
           | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2].astype(np.int32))
    uniq, inv = np.unique(key.ravel(), return_inverse=True)
    lut = np.array([color2label.get(int(u), 0) for u in uniq], dtype=np.uint8)
    return lut[inv].reshape(rgb.shape[:2])


def erase_township_lines(rgb, label):
    """把白色鄉鎮界線併入鄰近縣市，回傳 (label_filled, n_filled, n_keep)。"""
    town = label > 0
    white = np.all(rgb == np.array(LINE_WHITE, dtype=np.uint8), axis=-1)

    # 8 鄰域中「鄉鎮色」像素數；界線像素會被鄉鎮色包圍，外框／比例尺不會
    nb = np.zeros(label.shape, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nb += np.roll(np.roll(town, dy, 0), dx, 1).astype(np.uint8)
    line = white & (nb >= LINE_MIN_TOWN_NEIGHBORS)

    # 以最近的鄉鎮色像素所屬縣市填補
    _, ind = ndi.distance_transform_edt(~town, return_indices=True)
    filled = label.copy()
    filled[line] = label[ind[0][line], ind[1][line]]
    return filled, int(line.sum()), int((white & ~line).sum())


# ===================== 輸出 =====================
def render(src_png, label_filled, counties):
    """把每個縣市填成一色，其餘像素保留原樣。"""
    arr = np.array(Image.open(src_png).convert("RGB"))
    out = arr.copy()
    for c in counties:
        out[label_filled == c["index"]] = c["color"]
    return arr, out


def save_correspondence(path, counties, townships):
    summary = pd.DataFrame([{
        "序號": c["index"],
        "縣市": c["name"],
        "顏色 (HEX)": rgb2hex(c["color"]),
        "鄉鎮市區數": c["n"],
        "鄉鎮市區": "、".join(c["towns"]),
    } for c in counties])

    detail = pd.DataFrame([{
        "縣市序號": t["label"],
        "縣市": t["county_final"],
        "鄉鎮市區": t["town"],
        "現行縣市": t["county22"],
        "原色 (HEX)": t["hex"],
        "新色 (HEX)": rgb2hex(counties[t["label"] - 1]["color"]),
        "區域 ID": t["id"],
    } for t in townships])

    with pd.ExcelWriter(path) as xw:
        summary.to_excel(xw, sheet_name="縣市彙總", index=False)
        detail.to_excel(xw, sheet_name="鄉鎮市區明細", index=False)


def verify_and_report(out, label_filled, counties):
    """檢查陸地內是否還有殘留白線，並列出各縣市像素數。"""
    is_white = np.all(out == np.array(LINE_WHITE, dtype=np.uint8), axis=-1)
    land = np.zeros(label_filled.shape, dtype=bool)
    for c in counties:
        land |= (label_filled == c["index"])
    print(f"    陸地內殘留白線: {int((is_white & land).sum())} px（應為 0）")
    print(f"    保留白像素    : {int(is_white.sum())} px（小圖外框／比例尺）")
    for c in counties:
        px = int((label_filled == c["index"]).sum())
        print(f"    {c['index']:2d}. {c['name']:4s} {rgb2hex(c['color'])}  "
              f"{c['n']:2d} 鄉鎮市區  {px:7d} px")
