#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_vote_map.py —— 產生看板上用的「村里得票率地圖」：assets/vote_map.png
=========================================================================

為什麼要有這支
--------------
原始素材是 9824×7365 的整張海報，右上角自帶「標題＋圖例」，四周還有白邊。
早期是直接在瀏覽器裡用 canvas 擦掉標題再裁（js/core/layout.js 的 Layout.map.crop），
每次開頁面都要重做一遍，檔案也白白帶著 3/4 的空白與重複標題。
改成本腳本一次處理完，輸出一張「只剩地圖本體」的透明 PNG，載入時什麼都不用做。

不產生鋸齒、不產生白邊的關鍵：預乘 alpha 空間做面積平均
--------------------------------------------------
來源圖（新北市2014年市長選舉_得票率地圖_透明.png）的 alpha 是 transparent.py 砍出來的
「硬遮罩」（只有 0 與 255，過渡像素 0 個），而全透明處的 RGB 是純白 255。所以：

  ✗ 舊做法（把圖當白底 RGB 縮放，再用白度換算 alpha）
      縮放時白色會被平均進地圖邊緣 -> 邊緣像素變白；再以 tol/soft 把白度對應成
      alpha，只有一小段白度落在過渡帶內，其餘直接被砍成 0 或 255 —— alpha 邊是
      「一步階梯」，就是鋸齒；反預乘再把誤差放大，邊緣顏色也不對。
  ✓ 本腳本的做法
      1. alpha 當成「覆蓋率」：對 alpha 通道做面積平均，輸出像素的 alpha 就是
         真正被地圖蓋住的百分比，0→255 連續過渡，邊緣天生平滑。
      2. 顏色在「預乘」空間平均：先把每個像素乘上自己的 alpha（P = C × A）再平均，
         縮完再除回去。全透明像素貢獻 0，白色 RGB 永遠不會滲進來 —— 沒有白邊。
      3. 大倍率先做整數倍「面積平均」（Pillow 的 reduce＝真正的 box 平均，無振盪），
         最後的小倍率才用 LANCZOS 收尾。Lanczos 濾器有負瓣，一次縮 3 倍以上時會在
         硬邊緣來回振盪，產生亮邊／暗邊；面積平均不會。
      來源若沒有 alpha 通道（白底圖），先用 white_to_alpha 換算一次 alpha，
      之後走的仍是同一條預乘路徑。

處理順序
--------
  1. 讀入 RGBA（沒有 alpha 就先換算）
  2. 擦掉海報自帶的標題／圖例（以比例描述，換同版面海報不用改數字）
  3. 依 alpha 裁掉外圍全透明區
  4. 預乘 → 整數倍面積平均 → LANCZOS 收尾 → 反預乘 → 縮到目標寬度
  5. 存檔（assets/vote_map.png），並自我檢查邊緣品質、印出「看板上會畫成多大」

寬度怎麼訂
----------
看板 2560×1440，地圖 contain 進 Layout.map 的 1520×1034 框，最大（scale=1）約 1089 寬；
按「下載 2× PNG」會畫到 2174 寬，所以素材 2400 寬剛好留約 10% 餘量。
腳本會把 Layout.map 的框從 js/core/layout.js 讀出來算實際數字並提示餘量，
框改寬了不必回來改這裡（只影響提示，不影響輸出）。

--------------------------------------------------------------------------
用法
--------------------------------------------------------------------------
  # 標準：來源 → assets/vote_map.png（2400 寬）
  python tools/build_vote_map.py

  # 換來源 / 換輸出 / 換寬度
  python tools/build_vote_map.py -i 新北市2014年市長選舉_得票率地圖_透明.png \
      -o assets/vote_map.png --width 3000

  # 順便把新地圖寫回 data/local-assets.js（file:// 開啟時的後備來源）
  python tools/build_vote_map.py --embed

  # 連深色底預覽圖一起輸出（存成 <輸出>_preview.png）
  python tools/build_vote_map.py --preview

參數
----
  -i, --input     來源圖（預設 2014NewTaipei/map/…_透明.png）
  -o, --output    輸出 PNG（預設 Share/assets/vote_map.png）
  --width N       目標寬度，0 = 維持原寬（預設 2400）
  --erase X,Y,W,H 額外要擦掉的矩形（比例，可重複；預設擦右上角標題／圖例那一塊）
  --no-erase      不擦任何東西（來源已經是乾淨的地圖本體時用）
  -t, --tol       純白門檻（僅「來源沒有 alpha 通道」時用於換算 alpha）
  -s, --soft      過渡帶寬度（同上）
  --preview [色碼]  另存深色底預覽圖
  --embed         把結果以 base64 寫回 data/local-assets.js 的 voteMap
  -q, --quiet     只印結果
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import sys

import numpy as np
from PIL import Image, ImageChops

# 讓 `python tools/build_vote_map.py` 能直接 import 同目錄的工具
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import white_to_alpha as w2a                                     # noqa: E402

Image.MAX_IMAGE_PIXELS = None       # 這支工具會處理 9000px 以上的大地圖

# --------------------------------------------------------------------------
# 路徑
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SHARE = os.path.dirname(HERE)
ROOT = os.path.dirname(SHARE)                       # D:\Windows\TaiwanElection\Video

SRC_MAP = os.path.join(ROOT, "2014NewTaipei", "map",
                       "新北市2014年市長選舉_得票率地圖_透明.png")
OUT_MAP = os.path.join(SHARE, "assets", "vote_map.png")
OUT_JS = os.path.join(SHARE, "data", "local-assets.js")
LAYOUT_JS = os.path.join(SHARE, "js", "core", "layout.js")

# 海報右上角自帶的「標題＋圖例」（看板頁眉本來就有選舉名稱，這塊重複）。
# 以比例描述 (x, y, w, h)：x ≥ 0.685 且 y ≤ 0.304。實測該範圍內地圖本體最高只到
# y ≈ 0.38，中間是透明帶，擦掉不會傷到地圖。
DEFAULT_BANDS = [(0.685, 0.0, 0.315, 0.304)]

# 目標寬度：見檔頭「寬度怎麼訂」。2400 > 2 × 1089（2× 匯出需求），留約 10% 餘量。
DEFAULT_WIDTH = 2400

# 只在「來源沒有 alpha 通道（白底圖）」時用來換算 alpha；
# 有 alpha 的來源（正常情況）完全走預乘路徑，不看這兩個值。
MAP_TOL, MAP_SOFT = 245, 40

PREVIEW_BG = "#0d1730"          # 接近看板底色，方便肉眼確認

# 邊界內側那一圈比主體亮超過這個值就視為有白邊（0~255 的灰階差）
HALO_LIMIT = 12.0

# js/core/layout.js 讀不到時的後備框（只影響提示數字）
FALLBACK_BOX = {"x": 520, "y": 196, "w": 1520, "h": 1034, "scale": 0.9}


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def band_arg(s):
    """'0.685,0,0.315,0.304' -> (x, y, w, h)（比例 0~1）"""
    parts = [p for p in re.split(r"[\s,]+", s.strip()) if p]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("要四個數字：x,y,w,h（比例）")
    try:
        v = tuple(float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("必須是數字：%r" % s)
    if v[2] <= 0 or v[3] <= 0:
        raise argparse.ArgumentTypeError("w、h 必須大於 0：%r" % s)
    return v


def log(quiet, msg):
    if not quiet:
        print(msg)


def kb(path):
    return os.path.getsize(path) / 1024.0


def erode(mask, n=1):
    """4-鄰接侵蝕 n 次（純 numpy 位移，夠用且不依賴 scipy）。"""
    for _ in range(n):
        m = mask.copy()
        m[1:, :] &= mask[:-1, :]
        m[:-1, :] &= mask[1:, :]
        m[:, 1:] &= mask[:, :-1]
        m[:, :-1] &= mask[:, 1:]
        mask = m
    return mask


def pinholes(alpha):
    """完全透明、但四鄰有非透明的像素。

    來源本身就有 1px 的透明縣市界線，那部分算出來是正常的；要看的是有沒有比
    基準值多出來的「孤立針孔」——那通常是 LANCZOS 之類帶負瓣的濾波器在
    0/255 硬遮罩邊緣戳出來的振盪。
    """
    nb = np.zeros(alpha.shape, bool)
    nb[1:, :] |= alpha[:-1, :] > 0
    nb[:-1, :] |= alpha[1:, :] > 0
    nb[:, 1:] |= alpha[:, :-1] > 0
    nb[:, :-1] |= alpha[:, 1:] > 0
    return int(((alpha == 0) & nb).sum())


# --------------------------------------------------------------------------
# 步驟
# --------------------------------------------------------------------------
def load_rgba(path, tol=MAP_TOL, soft=MAP_SOFT):
    """讀成 RGBA。來源若全不透明（其實是白底圖），先換算一次 alpha。"""
    im = Image.open(path)
    im = im.convert("RGBA")
    lo, _ = im.split()[3].getextrema()
    if lo >= 250:
        im = w2a.convert(w2a.load_rgb(path), tol=tol, soft=soft, mode="min")
    return im


def erase_bands(im, bands):
    """把比例矩形設成全透明。"""
    W, H = im.size
    for (x, y, w, h) in bands:
        box = (int(round(x * W)), int(round(y * H)),
               int(round((x + w) * W)), int(round((y + h) * H)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        im.paste((0, 0, 0, 0), box)
    return im


def trim_transparent(im, thresh=2):
    """依 alpha 裁掉外圍全透明區。thresh 略大於 0：避免 1~2 級殘留噪點撐大畫布。"""
    box = im.split()[3].point(lambda v: 255 if v > thresh else 0).getbbox()
    return im.crop(box) if box else im


def resize_rgba(im, width):
    """等比縮到指定寬度；預乘 alpha 空間的面積平均，邊緣平滑且不帶白邊。

    步驟：
      1. 預乘 P = C × A（全透明像素貢獻 0，白色 RGB 進不來）
      2. 整數倍面積平均（Pillow reduce＝真正的 box 平均）降到 1.4 倍以內
      3. 剩下的倍率用 BOX 收尾。BOX 也是面積平均，不會像 LANCZOS/BICUBIC 那樣
         產生負瓣：在 0/255 的硬遮罩邊緣會戳出孤立針孔與暗點
      4. 反預乘 C = P × 255 / A
    """
    W0, H0 = im.size
    if not width or W0 <= width:
        return im

    alpha = im.getchannel("A")
    # ImageChops.multiply 要求兩個影像同 mode，所以 alpha 先轉成 RGB
    pm = ImageChops.multiply(im.convert("RGB"), alpha.convert("RGB"))   # 預乘

    while pm.width * 0.7 > width:                          # 大倍率：面積平均
        pm = pm.reduce(max(2, pm.width // width))
        alpha = alpha.reduce(max(2, alpha.width // width))

    h = max(1, int(round(H0 * float(width) / W0)))         # 高度照原圖比例，避免累積誤差
    pm = pm.resize((width, h), Image.BOX)
    alpha = alpha.resize((width, h), Image.BOX)

    # 反預乘：P × 255 / A；A = 0 的像素 RGB 沒有意义，直接給 0（省記憶體也省雜訊）
    p = np.asarray(pm).astype(np.uint16)
    a = np.asarray(alpha).astype(np.uint16)
    safe = np.maximum(a, 1)[..., None]
    rgb = np.where(a[..., None] > 0,
                   np.minimum(255, (p * 255 + safe // 2) // safe), 0)
    out = np.dstack([rgb.astype(np.uint8), a.astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def build(src=SRC_MAP, out=OUT_MAP, width=DEFAULT_WIDTH, bands=DEFAULT_BANDS,
          tol=MAP_TOL, soft=MAP_SOFT, preview=None, quiet=False):
    """海報 → 乾淨的地圖本體透明 PNG。回傳輸出的 PIL Image。"""
    if not os.path.isfile(src):
        raise SystemExit("找不到來源圖：%s\n（用 -i 指定，或先產生那張 9824×7365 的透明海報）" % src)

    # 1) 讀入（沒有 alpha 就先換算）
    im = load_rgba(src, tol, soft)
    log(quiet, "  讀入   %-38s %s" % (os.path.basename(src), "%d × %d" % im.size))

    # 2) 擦掉海報自帶的標題／圖例
    if bands:
        im = erase_bands(im, bands)
        log(quiet, "  擦標題 %-38s %d 個矩形" % ("", len(bands)))

    # 3) 依 alpha 裁掉外圍空白
    before = im.size
    im = trim_transparent(im)
    log(quiet, "  裁邊   %-38s %s -> %s" % ("", "%d × %d" % before, "%d × %d" % im.size))

    # 4) 預乘面積平均縮圖
    if width:
        before = im.size
        im = resize_rgba(im, width)
        im = trim_transparent(im)
        log(quiet, "  縮放   %-38s %s -> %s" % ("", "%d × %d" % before, "%d × %d" % im.size))

    # 5) 存檔
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    im.save(out, optimize=True)
    log(quiet, "  輸出   %-38s %s  (%.0f KB)" %
        (os.path.basename(out), "%d × %d" % im.size, kb(out)))
    log(quiet, "  路徑   %s" % os.path.abspath(out))

    if preview is not None:
        pv = w2a.make_preview(im, preview)
        pv_path = os.path.splitext(out)[0] + "_preview.png"
        pv.save(pv_path)
        log(quiet, "  預覽   %-38s %s  （底 %s）" %
            (os.path.basename(pv_path), "%d × %d" % pv.size, preview))

    edge_report(im, quiet)
    report(im)
    return im


# --------------------------------------------------------------------------
# 邊緣品質自檢：鋸齒與白邊都抓得到
# --------------------------------------------------------------------------
def edge_report(img, quiet=False):
    """邊緣品質自檢：鋸齒與白邊都抓得到。

      · 抗鋸齒帶：0 < alpha < 250 的像素。預乘面積平均會把覆蓋率攤成連續的過渡帶，
        寬度約 1 px；幾乎沒有 = 邊被砍成 0/255 的階梯，就是鋸齒。
      · 邊緣顏色誤差：過渡帶像素「還原回來的顏色」對照它旁邊最近的不透明像素。
        兩者本來是同一個顏色（縮圖只是把覆蓋率攤開）；偏亮＝白色 RGB 滲進來
        （白邊），偏暗＝反預乘把邊緣壓黑（墨邊），誤差應該接近 0。
      · 針孔：全透明卻四周有色的像素。來源本來就有 1px 的透明縣市界線，所以不會
        是 0；比「界線長度」多出一大截就是振盪。
    """
    a = np.asarray(img)[:, :, 3]
    rgb = np.asarray(img)[:, :, :3].astype(np.float32)
    nz = a > 0
    op = a >= 250
    if not op.any() or not nz.any():
        return

    band = nz & ~op                       # 半透明過渡帶
    if not band.any():
        return

    # 每個過渡帶像素的參考色＝四鄰居中 alpha 最大者（必須是不透明的那個鄰居）
    best_a = np.zeros(a.shape, np.uint8)
    best_c = np.zeros(a.shape + (3,), np.float32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        an = np.roll(np.roll(a, dy, 0), dx, 1)
        take = an > best_a
        best_a = np.where(take, an, best_a)
        best_c = np.where(take[..., None],
                          np.roll(np.roll(rgb, dy, 0), dx, 1), best_c)
    ok = band & (best_a >= 250)
    if not ok.any():
        return
    diff = best_c[ok].mean(axis=1) - rgb[ok].mean(axis=1)
    med_d, mean_d = float(np.median(diff)), float(diff.mean())

    per = int((nz[1:, :] != nz[:-1, :]).sum() + (nz[:, 1:] != nz[:, :-1]).sum())
    width = int(band.sum()) / max(1, per)
    pct = 100.0 * int(band.sum()) / a.size

    log(quiet, "  邊緣   抗鋸齒帶 %.3f%%（%d px，寬 %.1f px）· 邊緣顏色誤差 中位數 %+.1f"
               "（平均 %+.1f）· 針孔 %d px" %
        (pct, int(band.sum()), width, med_d, mean_d, pinholes(a)))
    if pct < 0.05 or width < 0.5:
        print("  ! 過渡帶太窄，邊緣可能是鋸齒", file=sys.stderr)
    if abs(med_d) > HALO_LIMIT:
        print("  ! 邊緣顏色中位數偏%s %.1f 階（> %.0f），疑似%s" %
              ("亮" if med_d > 0 else "暗", abs(med_d), HALO_LIMIT,
               "白邊" if med_d > 0 else "墨邊"), file=sys.stderr)


# --------------------------------------------------------------------------
# 提示：這張圖在看板上會被畫成多大
# --------------------------------------------------------------------------
def read_layout_box(path=LAYOUT_JS):
    """從 js/core/layout.js 讀出 Layout.map 的框與 scale。

    只有 crop 是巢狀物件會干擾（裡面也有 x/y/w/h），先把它拿掉再比對。
    讀不到就回傳 FALLBACK_BOX —— 這裡算的數字只是給人看的，不影響輸出。
    """
    box = dict(FALLBACK_BOX)
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return box
    m = re.search(r"Layout\.map\s*=\s*\{(.*?)\n\s*\};", txt, re.S)
    if not m:
        return box
    body = re.sub(r"\bcrop\s*:\s*\{.*?\}\s*,?", "", m.group(1), flags=re.S)
    for k in ("x", "y", "w", "h", "scale"):
        v = re.search(r"\b%s\s*:\s*(-?[\d.]+)" % k, body)
        if v:
            box[k] = float(v.group(1))
    return box


def drawn_size(img_size, box, scale):
    """回傳地圖在看板上的繪製尺寸（layers.js MapLayer 的 contain 數學）。"""
    w, h = img_size
    k = min(box["w"] / float(w), box["h"] / float(h)) * scale
    return w * k, h * k


def report(img):
    """印出素材與「看板上實際會畫多大 / 2× 匯出夠不夠」；寬度不夠會提出警告。"""
    box = read_layout_box()
    for scale in (box["scale"], 1.0):
        dw, dh = drawn_size(img.size, box, scale)
        label = "預設 scale %d%%" % round(scale * 100) if scale < 1 else "scale 100%"
        print("  看板上 %s：%d × %d px" % (label, round(dw), round(dh)))

    need = drawn_size(img.size, box, 1.0)[0] * 2.0      # 2× 匯出需要的地圖寬
    have = img.size[0]
    print("  2× 匯出需要 %d px 寬，素材 %d px  → 餘量 %.2f×" %
          (round(need), have, have / max(need, 1.0)))
    if have < need:
        print("  ! 寬度不足，2× 匯出的地圖會糊掉，請用 --width %d 以上重跑" %
              int(need + 1), file=sys.stderr)
    print("  版面來源：js/core/layout.js（Layout.map %d × %d）" % (box["w"], box["h"]))


# --------------------------------------------------------------------------
# file:// 後備：把地圖 base64 寫回 data/local-assets.js
# --------------------------------------------------------------------------
def embed(map_path=OUT_MAP, out_js=OUT_JS):
    """把地圖換成 base64 寫回 data/local-assets.js，其他欄位（electedMark）原樣保留。

    只有在 file:// 直接開 index.html、讀不到 assets/vote_map.png 時才會用到這份內嵌圖。
    （整包重建請用 tools/build_assets.py，那支會連當選標誌一起重寫。）
    """
    if not os.path.isfile(map_path):
        raise SystemExit("找不到要內嵌的圖：%s" % map_path)
    if not os.path.isfile(out_js):
        raise SystemExit("找不到 %s（請先跑 python tools/build_assets.py 產生）" % out_js)

    with open(map_path, "rb") as f:
        uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    with open(out_js, encoding="utf-8") as f:
        txt = f.read()

    new, n = re.subn(r'("voteMap"\s*:\s*")[^"]*(")',
                     lambda m: m.group(1) + uri + m.group(2), txt)
    if not n:
        raise SystemExit("%s 裡找不到 voteMap 欄位，未修改。" % out_js)

    with open(out_js, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("  內嵌   %-38s %.0f KB" % (os.path.basename(out_js), kb(out_js)))
    return out_js


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="build_vote_map.py",
        description="把得票率海報處理成看板上用的透明地圖 assets/vote_map.png"
                    "（預乘 alpha 面積平均，不產生鋸齒與白邊）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例：python tools/build_vote_map.py --width 2400 --embed --preview")
    p.add_argument("-i", "--input", default=SRC_MAP, help="來源圖（預設 %(default)s）")
    p.add_argument("-o", "--output", default=OUT_MAP,
                   help="輸出 PNG（預設 Share/assets/vote_map.png）")
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                   help="目標寬度，0 = 維持原寬（預設 %(default)s）")
    p.add_argument("--erase", type=band_arg, action="append", metavar="X,Y,W,H",
                   help="額外要擦掉的矩形（比例，可重複；不加則用預設的右上角標題／圖例）")
    p.add_argument("--no-erase", action="store_true", help="完全不擦（來源已是乾淨地圖本體）")
    p.add_argument("-t", "--tol", type=float, default=MAP_TOL,
                   help="純白門檻（僅來源沒有 alpha 通道時用，預設 %(default)s）")
    p.add_argument("-s", "--soft", type=float, default=MAP_SOFT,
                   help="過渡帶寬度（同上，預設 %(default)s）")
    p.add_argument("--preview", nargs="?", const=PREVIEW_BG, default=None, metavar="COLOR",
                   help="另存深色底預覽圖（預設 %s）" % PREVIEW_BG)
    p.add_argument("--embed", action="store_true",
                   help="把結果 base64 寫回 data/local-assets.js 的 voteMap（file:// 後備）")
    p.add_argument("-q", "--quiet", action="store_true", help="只印結果")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.no_erase:
        bands = []
    elif args.erase:
        bands = list(args.erase)
    else:
        bands = list(DEFAULT_BANDS)

    print("得票率地圖：")
    build(src=args.input, out=args.output, width=args.width, bands=bands,
          tol=args.tol, soft=args.soft, preview=args.preview, quiet=args.quiet)
    if args.embed:
        embed(args.output)
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
