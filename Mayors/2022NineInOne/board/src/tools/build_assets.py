# -*- coding: utf-8 -*-
"""build_assets.py —— 2022 九合一縣市長看板素材去背管線。

★ 唯一落點：board/dist/assets/

   原始素材                             成品
   ---------------------------------    ---------------------------------
   map/village/<縣>_村里級.png          dist/assets/map/<縣>/map.png   （村里級主圖）
   map/town/<縣>_鄉鎮級.png             dist/assets/map/<縣>/map2.png  （鄉鎮級右欄圖）
   Video/assets/share/徽章/<檔名>.png    dist/assets/share/<縣>.png      （縣徽）
   Video/assets/share/<分組圖>.png       dist/assets/bg/<key>.png        （背景照）

三種處理：
  * 地圖（map / map2）：白底轉透明 **且** 純黑界線轉白線 —— 看板底色是深色，
    黑界線看不見，轉白才浮得出來。（兩個遮罩在同一次掃描裡從原圖算出。）
  * 縣徽：白底轉透明（threshold 12）。縣徽是圓形主體、白底方框，轉透明後
    貼到白卡上即還原原貌。
  * 背景照：**原樣複製、不做任何轉換**（CoverRecipe）。同組縣市共用一張，
    只存 dist/assets/bg/<key>.png 一份（22 縣市 → 3 個檔），避免 100MB 重複。

執行：
    python src/tools/build_assets.py                 # 全部 22 縣市
    python src/tools/build_assets.py 臺北市           # 只做臺北市
    python src/tools/build_assets.py --bg            # 只補背景照（地圖/縣徽不動）
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import county_map as CM

BOARD = CM.ROOT                                  # board/
OUT_ROOT = os.path.join(BOARD, "dist", "assets")

MAP_WHITE_THRESHOLD = 12                          # 白底容差（>= 243 算白）


def white_to_transparent_black_to_white(src, dst, threshold=MAP_WHITE_THRESHOLD):
    """白底轉透明，同時把純黑界線轉白線（地圖用）。"""
    img = Image.open(src).convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[..., 0], data[..., 1], data[..., 2], data[..., 3]
    limit = 255 - threshold
    white_mask = (r >= limit) & (g >= limit) & (b >= limit)
    black_mask = (r == 0) & (g == 0) & (b == 0) & (a > 0)
    data[..., 0] = np.where(black_mask, 255, r)
    data[..., 1] = np.where(black_mask, 255, g)
    data[..., 2] = np.where(black_mask, 255, b)
    data[..., 3] = np.where(white_mask, 0, a)
    Image.fromarray(data, mode="RGBA").save(dst, "PNG", optimize=True)
    return white_mask.sum(), black_mask.sum()


def white_to_transparent(src, dst, threshold=MAP_WHITE_THRESHOLD):
    """白底轉透明（縣徽用）。"""
    img = Image.open(src).convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[..., 0], data[..., 1], data[..., 2], data[..., 3]
    limit = 255 - threshold
    white_mask = (r >= limit) & (g >= limit) & (b >= limit)
    data[..., 3] = np.where(white_mask, 0, a)
    Image.fromarray(data, mode="RGBA").save(dst, "PNG", optimize=True)
    return white_mask.sum()


def build_map(county):
    """村里級主圖 + 鄉鎮級右欄圖。"""
    os.makedirs(os.path.join(OUT_ROOT, "map", county), exist_ok=True)
    for level, out_name in (("village", "map.png"), ("town", "map2.png")):
        src = CM.map_source(county, level)
        dst = os.path.join(OUT_ROOT, "map", county, out_name)
        if not os.path.isfile(src):
            print("  [缺] %s" % src)
            continue
        wt, bk = white_to_transparent_black_to_white(src, dst)
        print("  ✓ %s/map%s  白底 %d px 轉透明、黑界 %d px 轉白"
              % (county, ("2" if level == "town" else ""), wt, bk))


def build_seal(county):
    """縣徽（白底轉透明）。"""
    os.makedirs(os.path.join(OUT_ROOT, "share"), exist_ok=True)
    src = CM.seal_source(county)
    dst = os.path.join(OUT_ROOT, "share", "%s.png" % county)
    if not os.path.isfile(src):
        print("  [缺] %s" % src)
        return
    wt = white_to_transparent(src, dst)
    print("  ✓ 縣徽 %s  白底 %d px 轉透明" % (county, wt))


def build_bg(county, done=None):
    """背景照：原樣複製到 dist/assets/bg/<key>.png（同組只做一次）。"""
    key = CM.bg_key(county)
    if done is not None and key in done:
        return
    os.makedirs(os.path.join(OUT_ROOT, "bg"), exist_ok=True)
    src = CM.bg_source(county)
    dst = os.path.join(OUT_ROOT, "bg", "%s.png" % key)
    if not os.path.isfile(src):
        print("  [缺] %s" % src)
        return
    shutil.copyfile(src, dst)
    if done is not None:
        done.add(key)
    print("  ✓ 背景 %s → bg/%s.png  %s  %d KB"
          % (os.path.basename(src), key, Image.open(dst).size,
             os.path.getsize(dst) // 1024))


def build_photo_fallback():
    """低得票率候選人的圖片框占位圖：原樣複製到 dist/assets/share/low_pct.png。

    排名 ≥ 3 且得票率 < 3% 的候選人，圖片框改畫這張（灰階人形剪影），
    不再留政黨純色塊 —— 判斷式在 election-model.js 的 usesLowPctPhoto()。
    不做任何去背／縮放：引擎是 cover 進框、圓角裁切，任何比例都吃得下。
    """
    os.makedirs(os.path.join(OUT_ROOT, "share"), exist_ok=True)
    src = CM.PHOTO_LOW_PCT
    dst = os.path.join(OUT_ROOT, "share", "low_pct.png")
    if not os.path.isfile(src):
        print("  [缺] %s" % src)
        return
    shutil.copyfile(src, dst)
    print("  ✓ 占位頭像 %s → share/low_pct.png  %s  %d KB"
          % (os.path.basename(src), Image.open(dst).size,
             os.path.getsize(dst) // 1024))


def main():
    args = [a for a in sys.argv[1:] if a]
    bg_only = "--bg" in args
    counties = [a for a in args if not a.startswith("-") and a in CM.COUNTIES] \
        or CM.COUNTY_ORDER
    build_photo_fallback()          # 22 場共用一張，做一次就夠
    done_bg = set()
    for c in counties:
        print(c)
        build_bg(c, done_bg)
        if bg_only:
            continue
        build_map(c)
        build_seal(c)


if __name__ == "__main__":
    main()
