#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
white_to_alpha.py —— 把圖片的「純白背景」轉成透明，輸出帶 alpha 的 PNG。
==========================================================================

需求：一張白底圖片（地圖、徽標、logo、掃描稿……）放到深色底上時，
      白色背景要消失，只留主體。

核心做法
--------
1) 先算每個像素的「白度」wn（0 = 最濃的墨，255 = 純白），
   白度有高低起伏，於是能做「軟邊」而不是一刀切；
2) 再把白度映射成 alpha：

       alpha = clip( (tol - wn) / soft , 0 , 1 )

     wn >= tol            -> alpha = 0   純白，完全透明
     wn <= tol - soft     -> alpha = 1   實色，完全不透明
     兩者之間              -> 線性過渡     保留抗鋸齒邊緣，不出白邊、不出鋸齒

3) 反預乘（un-premultiply）：抗鋸齒的邊緣像素，它的 RGB 其實是「已經和白色
   混過」的顏色（偏白）。若不還原，貼到深色底上會看到一圈灰白暈邊。
       fg = (rgb - (1 - a) * 255) / a
   全透明的像素則保留原色（白色），避免雙線性取樣時吸到黑色而產生暗邊。

白度 wn 的三種算法（--mode）
----------------------------
  min     wn = min(R,G,B)        預設。適合「白底 + 平面色塊」的圖（地圖、徽標、
                                 插畫）：色塊再淺也不會被誤刪。
  max     wn = max(R,G,B)        最保守。三通道都要接近 255 才透明。適合主體本身
                                 含有淺色（淡黃、淡灰）的圖。
  dist    wn = 255 - 距離(白,px)  適合漸層、照片類的白底。

--------------------------------------------------------------------------
命令列用法
----------
  # 最單純：白底轉透明
  python white_to_alpha.py -i in.png -o out.png

  # 地圖這類大圖：先裁掉白邊、再縮到 2400 寬、順便把主體外的深色字改成亮色
  python white_to_alpha.py -i map.png -o map_alpha.png \
      --trim --width 2400 --recolor-outside-dark "#CEDFFF" --preview

  # 微調門檻（tol 越大越「捨不得」刪白；soft 越大邊緣越柔）
  python white_to_alpha.py -i in.png -o out.png -t 252 -s 8

  # 保留原本的 RGB（不反預乘）：主體是鮮豔單色時可試
  python white_to_alpha.py -i in.png -o out.png --no-unpremultiply

參數
----
  -i, --input        輸入圖片（必填）
  -o, --output       輸出 PNG（預設 <輸入檔名>_alpha.png）
  -t, --tol          純白門檻，wn >= tol 視為背景（預設 250）
  -s, --soft         過渡帶寬度，越大邊緣越柔（預設 20）
  -m, --mode         min | max | dist（預設 min）
      --width N      縮放到指定寬度（在轉 alpha 之前，省記憶體、邊緣更準）
      --trim         先裁掉四周的白邊（以 RGB 判斷，保留原始解析度）
      --no-trim-alpha 最後不依 alpha 裁切
      --no-unpremultiply  不做反預乘
      --recolor-outside-dark COLOR
                     把「主體之外」的深色墨改為 COLOR（例如標題、圖例的文字／
                     框線）；白底抽掉後這些深色字在深色底上會看不見。
      --dark-max N   深色墨判定門檻（三通道最大值 < N，預設 140）
      --preview [COLOR]
                     額外輸出一張深色底預覽圖（預設 #0b1226），存成
                     <輸出檔名>_preview.png
      --bg COLOR     若輸入本身有 alpha，先合成到這個底色（預設白）
  -q, --quiet        只印結果
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None          # 本工具會處理 9000px 以上的大地圖

DEFAULT_TOL = 250
DEFAULT_SOFT = 20
DEFAULT_DARK_MAX = 140
PreviewBG = "#0b1226"


# ==========================================================================
# 色彩工具
# ==========================================================================
def parse_color(s):
    """'#rrggbb' / '#rgb' / 'r,g,b' -> (r, g, b)"""
    s = str(s).strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    parts = [int(float(x)) for x in s.replace(";", ",").split(",")]
    if len(parts) != 3:
        raise ValueError("顏色格式應為 #rrggbb 或 r,g,b：%r" % s)
    return tuple(parts)


def load_rgb(path, bg=(255, 255, 255)):
    """讀圖並確保是 RGB。

    若來源本身帶 alpha（RGBA/LA/P 透明），先合成到底色 bg 上，因為本工具的
    前提是「白底」——先攤平才有一致的判斷基準。
    """
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, bg)
        flat.paste(im, (0, 0), im)
        return flat
    return im.convert("RGB")


# ==========================================================================
# 1. 白度 / alpha
# ==========================================================================
def whiteness_map(rgb, mode="min"):
    """回傳 float32 的白度圖：0 = 最濃的墨，255 = 純白。"""
    if mode == "min":
        return rgb.min(axis=2).astype(np.float32)
    if mode == "max":
        return rgb.max(axis=2).astype(np.float32)
    if mode == "dist":
        d = np.sqrt(np.square(255.0 - rgb.astype(np.float32)).sum(axis=2))
        return 255.0 - d / np.sqrt(3.0)
    raise ValueError("未知的 mode：%r（可用 min / max / dist）" % mode)


def alpha_from_whiteness(wn, tol=DEFAULT_TOL, soft=DEFAULT_SOFT):
    """白度 -> alpha（0..1）。tol 以上全透明，tol-soft 以下全不透明。"""
    soft = max(float(soft), 1e-6)
    return np.clip((float(tol) - wn) / soft, 0.0, 1.0)


def to_rgba(rgb, alpha, unpremultiply=True):
    """組出 RGBA。

    unpremultiply：把「和白色混過」的邊緣色還原成真實色，避免深色底上的白暈。
    全透明像素保留原色（不還原），避免被算成黑色而在縮放時產生暗邊。
    """
    a3 = alpha[..., None]
    src = rgb.astype(np.float32)

    if unpremultiply:
        den = np.maximum(a3, 0.15)                       # 避免除以趨近 0
        fg = np.clip((src - (1.0 - a3) * 255.0) / den, 0.0, 255.0)
        fg = np.where(a3 > 0.02, fg, src)                # 透明的留原色
    else:
        fg = src

    out = np.dstack([fg.astype(np.uint8), (alpha * 255.0 + 0.5).astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def convert(rgb_image, tol=DEFAULT_TOL, soft=DEFAULT_SOFT, mode="min",
            unpremultiply=True):
    """一張白底 RGB 圖 -> 白底透明的 RGBA 圖。"""
    rgb = np.asarray(rgb_image)
    wn = whiteness_map(rgb, mode)
    alpha = alpha_from_whiteness(wn, tol, soft)
    return to_rgba(rgb, alpha, unpremultiply)


# ==========================================================================
# 2. 裁切 / 縮放
# ==========================================================================
def content_bbox(rgb_image, tol=DEFAULT_TOL):
    """非白內容的 (x0, y0, x1, y1)（含端點）；整張全白則回傳 None。

    不用 np.where（大圖會產生兩個上億元素的索引陣列），改用逐軸 any。
    """
    a = np.asarray(rgb_image)
    if a.ndim == 3:
        mask = a.min(axis=2) < tol
    else:
        mask = a < tol
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return None
    cols = np.flatnonzero(mask.any(axis=0))
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def trim_white(rgb_image, tol=DEFAULT_TOL):
    """裁掉四周的白邊。"""
    bbox = content_bbox(rgb_image, tol)
    if bbox is None:
        return rgb_image
    x0, y0, x1, y1 = bbox
    return rgb_image.crop((x0, y0, x1 + 1, y1 + 1))


def trim_alpha(rgba_image):
    """依 alpha 再裁一次四周全透明的部分。"""
    bbox = rgba_image.split()[3].getbbox()
    return rgba_image.crop(bbox) if bbox else rgba_image


def resize_width(rgb_image, width):
    """等比例縮到指定寬度（LANCZOS）。

    刻意在「轉 alpha 之前」縮放：白底大圖先縮小，中央的色塊與白底一起被平均，
    邊緣自然帶出中間色的漸層，之後再算 alpha 就得到柔順的抗鋸齒；
    同時記憶體只用縮圖的量。
    """
    if not width or width >= rgb_image.width:
        return rgb_image
    scale = float(width) / rgb_image.width
    size = (int(width), max(1, int(round(rgb_image.height * scale))))
    return rgb_image.resize(size, Image.LANCZOS)


# ==========================================================================
# 3. 主體之外的深色墨改亮色（標題、圖例）
# ==========================================================================
def recolor_outside_dark(rgba_image, color=(206, 223, 255), dark_max=DEFAULT_DARK_MAX):
    """把「最大連通區域（主體）之外」的深色墨改成指定顏色。

    白底抽掉後，原本靠白底才看得見的深色標題／圖例文字，在深色看板上會消失，
    所以獨立偵測後改成亮色。找不到主體就原樣回傳。
    """
    try:
        from scipy import ndimage
    except ImportError:
        print("  ! 需要 scipy 才能改色（pip install scipy），已略過", file=sys.stderr)
        return rgba_image, 0

    a = np.asarray(rgba_image).copy()
    rgb = a[..., :3].astype(np.float32)
    alpha = a[..., 3].astype(np.float32) / 255.0

    content = alpha > 0.02
    labels, n = ndimage.label(content, structure=np.ones((3, 3), dtype=np.int32))
    if n <= 1:
        return rgba_image, 0

    sizes = ndimage.sum(content, labels, index=np.arange(1, n + 1))
    main = int(np.argmax(sizes)) + 1                  # 最大連通區域 = 圖的主體
    outside = content & (labels != main)
    dark = rgb.max(axis=2) < dark_max
    hit = outside & dark

    rgb[hit] = np.asarray(color, dtype=np.float32)
    alpha[hit] = 1.0

    a[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    a[..., 3] = (alpha * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(a, "RGBA"), int(hit.sum())


# ==========================================================================
# 4. 預覽
# ==========================================================================
def make_preview(rgba_image, bg=PreviewBG, max_w=1100):
    """把透明圖貼到指定底色上，方便肉眼檢查邊緣與配色。"""
    im = rgba_image
    if im.width > max_w:
        s = max_w / float(im.width)
        im = im.resize((max_w, max(1, int(round(im.height * s)))), Image.LANCZOS)
    out = Image.new("RGB", im.size, parse_color(bg))
    out.paste(im, (0, 0), im)
    return out


# ==========================================================================
# CLI
# ==========================================================================
def build_parser():
    p = argparse.ArgumentParser(
        prog="white_to_alpha.py",
        description="把圖片的純白背景轉成透明（輸出 PNG）。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--input", required=True, help="輸入圖片")
    p.add_argument("-o", "--output", help="輸出 PNG（預設 <輸入>_alpha.png）")
    p.add_argument("-t", "--tol", type=float, default=DEFAULT_TOL,
                   help="純白門檻，預設 %(default)s")
    p.add_argument("-s", "--soft", type=float, default=DEFAULT_SOFT,
                   help="過渡帶寬度，預設 %(default)s")
    p.add_argument("-m", "--mode", default="min", choices=["min", "max", "dist"],
                   help="白度算法，預設 %(default)s")
    p.add_argument("--width", type=int, default=0,
                   help="縮放到指定寬度（在轉 alpha 之前）")
    p.add_argument("--trim", action="store_true", help="先裁掉四周白邊")
    p.add_argument("--no-trim-alpha", action="store_true", help="最後不依 alpha 裁切")
    p.add_argument("--no-unpremultiply", action="store_true", help="不做反預乘")
    p.add_argument("--recolor-outside-dark", metavar="COLOR", default=None,
                   help="主體之外的深色墨改為此色，例如 '#CEDFFF'")
    p.add_argument("--dark-max", type=float, default=DEFAULT_DARK_MAX,
                   help="深色墨判定門檻，預設 %(default)s")
    p.add_argument("--preview", nargs="?", const=PreviewBG, default=None,
                   metavar="COLOR", help="另存深色底預覽圖（預設 %s）" % PreviewBG)
    p.add_argument("--bg", default="#ffffff", help="輸入若帶 alpha，先合成到此底色")
    p.add_argument("-q", "--quiet", action="store_true", help="只印結果")
    return p


def process(path_in, path_out=None, tol=DEFAULT_TOL, soft=DEFAULT_SOFT, mode="min",
            width=0, trim=False, trim_alpha_out=True, unpremultiply=True,
            recolor=None, dark_max=DEFAULT_DARK_MAX, preview=None,
            bg="#ffffff", quiet=False):
    """轉檔主流程；可當函式庫直接呼叫，回傳輸出的 RGBA Image。"""
    if path_out is None:
        stem, _ = os.path.splitext(path_in)
        path_out = stem + "_alpha.png"

    rgb = load_rgb(path_in, parse_color(bg))
    if not quiet:
        print("  讀入 %-46s %s" % (os.path.basename(path_in), rgb.size))

    if trim:
        before = rgb.size
        rgb = trim_white(rgb, tol)
        if not quiet and rgb.size != before:
            print("  裁白邊 %-44s %s -> %s" % ("", before, rgb.size))

    if width:
        before = rgb.size
        rgb = resize_width(rgb, width)
        if not quiet and rgb.size != before:
            print("  縮放   %-44s %s -> %s" % ("", before, rgb.size))

    img = convert(rgb, tol=tol, soft=soft, mode=mode, unpremultiply=unpremultiply)

    if recolor is not None:
        img, hit = recolor_outside_dark(img, parse_color(recolor), dark_max)
        if not quiet:
            print("  主體外的深色墨改亮色 %s：%d px" % (recolor, hit))

    if trim_alpha_out:
        img = trim_alpha(img)

    os.makedirs(os.path.dirname(os.path.abspath(path_out)) or ".", exist_ok=True)
    img.save(path_out, optimize=True)
    kb = os.path.getsize(path_out) / 1024.0
    print("  輸出   %-46s %s  (%.0f KB)" % (os.path.basename(path_out), img.size, kb))

    if preview is not None:
        pv = make_preview(img, preview)
        pv_path = os.path.splitext(path_out)[0] + "_preview.png"
        pv.save(pv_path)
        if not quiet:
            print("  預覽   %-46s %s  （底 %s）" %
                  (os.path.basename(pv_path), pv.size, preview))

    return img


def main(argv=None):
    args = build_parser().parse_args(argv)
    print("白底轉透明：")
    process(args.input, args.output, tol=args.tol, soft=args.soft, mode=args.mode,
            width=args.width, trim=args.trim,
            trim_alpha_out=not args.no_trim_alpha,
            unpremultiply=not args.no_unpremultiply,
            recolor=args.recolor_outside_dark, dark_max=args.dark_max,
            preview=args.preview, bg=args.bg, quiet=args.quiet)
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
