# -*- coding: utf-8 -*-
"""build_national_assets.py —— 2022 全國縣市長看板（政黨版圖）素材管線。

兩張來源圖都是「全台單張、不透明平面底色」的成品圖，不能直接上看板：

  來源                                  成品（dist/assets/national/）
  -----------------------------------   ------------------------------
  map/2022县市.png                      county.png  （縣市級：當選政黨）
  map/2022縣市長選舉_鄉鎮市區得票率.png   town.png    （鄉鎮級：得票率深淺）
  （現畫）                               legend.png  （透明底圖例）

四種處理（全部按 national_map.py 的常數）：
  1. **底色轉透明**：來源底色是淺灰 (120,120,120) / #323232 (50,50,50)，
     用「三通道差都 <= 8」判底色，連抗鋸齒暈邊一起去掉。
  2. **挖掉中國大陸輪廓**：來源左上角有一大塊大陸與海界線（不是選舉資料），
     整區（CHINA_BOX）alpha 歸零 —— 留著會在深色看板上變成一團雜訊。
  3. **黑界線轉白並加粗**：來源的縣市界／鄉鎮界是純黑 3–5px（繪圖腳本用純黑
     堤壩再洪水填色）。看板底是深色，黑線看不見；而且成品會縮到看板的
     678px 寬（縮 4 倍），不先加粗一級細線會被縮沒。
  4. **兩張圖共用同一個裁切框**：來源是同一張畫布、同一組座標（實測兩張的
     墨跡外框只差 16px），裁切框取兩者聯集 → 兩張圖擺在一起時比例、
     位置、放大框全部對得齊。

執行：
    python src/tools/build_national_assets.py            # 地圖 + 圖例
    python src/tools/build_national_assets.py --legend    # 只重畫圖例
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import national_map as NM

Image.MAX_IMAGE_PIXELS = None


# ---------------------------------------------------------------- 地圖
def _dilate(mask, times):
    """3×3 最大值濾波：把線層加粗（times 次＝寬度 +2×times px）。"""
    im = Image.fromarray((mask * 255).astype(np.uint8))
    for _ in range(times):
        im = im.filter(ImageFilter.MaxFilter(3))
    return np.array(im) > 127


def _fill_color_mask(rgb):
    """「這是資料填色」的遮罩：顏色剛好等於 color.txt 裡的某一階。

    ★ 去底只看「與底色差多少」會誤殺：鄉鎮圖底色 #323232、無黨籍 75% 是 #333333，
      只差 1 → 那塊會被挖成透明（2026-10-29 使用者回報的苗栗縣）。
      所以先把色階表裡的顏色標出來，這些一律當前景。
    """
    key = (rgb[..., 0].astype(np.int32) << 16) | \
          (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2].astype(np.int32)
    keys = np.array([(r << 16) | (g << 8) | b for r, g, b in NM.all_ramp_colors()],
                    dtype=np.int32)
    return np.isin(key, keys)


def prepare(src, bg):
    """回傳 (RGBA 陣列, 前景遮罩)：去底 + 挖掉大陸 + 黑線轉白。"""
    arr = np.array(Image.open(src).convert("RGBA"))
    rgb = arr[..., :3].astype(int)

    close = np.abs(rgb - np.array(bg)).max(axis=-1) <= NM.BG_TOL
    fill = _fill_color_mask(rgb)
    fg = ~close | fill                            # 資料填色再接近底色也不算背景
    x0, y0, x1, y1 = NM.CHINA_BOX
    fg[y0:y1, x0:x1] = False                      # 左上角大陸輪廓不是資料

    line = (rgb.max(axis=-1) <= NM.LINE_MAX) & fg  # 純黑界線（含 1–3 的抗鋸齒）
    line = _dilate(line, NM.LINE_DILATE)

    out = arr.copy()
    out[..., 0][line], out[..., 1][line], out[..., 2][line] = NM.LINE_COLOR
    out[..., 3][line] = 255
    out[..., 3][~fg] = 0
    return out, fg, int(line.sum())


def robust_bbox(fg, min_ink=NM.BBOX_MIN_INK):
    """墨跡外框：只算「整列／整行墨跡像素數 > min_ink」的範圍，
    避免右上角零星小島點把畫布拉到整張來源圖。"""
    rows = fg.sum(axis=1)
    cols = fg.sum(axis=0)
    ys = np.where(rows > min_ink)[0]
    xs = np.where(cols > min_ink)[0]
    if not len(ys) or not len(xs):
        raise RuntimeError("地圖沒有墨跡，來源檔可能有問題")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def build_maps():
    os.makedirs(NM.OUT_ASSETS, exist_ok=True)
    jobs = [
        ("county", NM.MAP_COUNTY_SRC, NM.MAP_COUNTY_BG, NM.OUT_COUNTY),
        ("town", NM.MAP_TOWN_SRC, NM.MAP_TOWN_BG, NM.OUT_TOWN),
    ]
    prepped = []
    for key, src, bg, dst in jobs:
        if not os.path.isfile(src):
            raise RuntimeError("缺來源地圖：%s" % src)
        with Image.open(src) as im:
            src_size = im.size
        arr, fg, n_line = prepare(src, bg)
        prepped.append((key, arr, fg, dst, n_line))

    bbs = [robust_bbox(fg) for _, _, fg, _, _ in prepped]
    crop = (min(b[0] for b in bbs), min(b[1] for b in bbs),
            max(b[2] for b in bbs), max(b[3] for b in bbs))
    # 往外留 CROP_PAD（不是往內縮 —— 往內縮會切到台灣最北端與最南端）
    h_src, w_src = prepped[0][1].shape[:2]
    p = NM.CROP_PAD
    crop = (max(0, crop[0] - p), max(0, crop[1] - p),
            min(w_src - 1, crop[2] + p), min(h_src - 1, crop[3] + p))

    info = {"crop": list(crop), "source_size": list(src_size), "maps": {}}
    for (key, arr, fg, dst, n_line), bb in zip(prepped, bbs):
        im = Image.fromarray(arr, "RGBA").crop(
            (crop[0], crop[1], crop[2] + 1, crop[3] + 1))
        im.save(dst, "PNG", optimize=True)
        info["maps"][key] = {
            "file": os.path.basename(dst),
            "w": im.width, "h": im.height,
            "aspect": round(im.width / im.height, 6),
            "ink_bbox": list(bb),
            "line_px": n_line,
            "bytes": os.path.getsize(dst),
        }
        print("  ✓ %-6s %s  %d×%d  （來源 %d×%d，墨跡框 %s，界線 %s px，%d KB）"
              % (key, os.path.basename(dst), im.width, im.height,
                 src_size[0], src_size[1], bb, format(n_line, ","),
                 os.path.getsize(dst) // 1024))
    print("  裁切框共同適用：x %d..%d  y %d..%d（%d×%d）"
          % (crop[0], crop[2], crop[1], crop[3],
             crop[2] - crop[0] + 1, crop[3] - crop[1] + 1))
    return info


# ---------------------------------------------------------------- 圖例
def _font(size):
    return ImageFont.truetype(NM.font_path(), size)


def build_legend():
    """透明底圖例：四家政黨各自的**得票率色階**（直接讀 color.txt）。

    ★ 2026-10-29 第二版（使用者要求）：
      · 色階來源改成 `Precident/color.txt`（也就是地圖實際填色那一份）；
      · 只畫四家：中國國民黨／民主進步黨／台灣民眾黨／無黨籍；
      · **除黨名外不畫任何文字**（原本的說明句、35…65% 刻度全部拿掉）。

    版面（2× 繪製 960×236，contain 進 LEGEND_BOX 480×118）：
      · 頂部 40px（看板 20px）＝**比例尺**：每 2 階標一次（35%／45%／55%…＝每 10 個百分點），
        刻度線直接對齊下方色階的格線，右端補「以上」（最後一格是 85+）；
      · 下面四列，每列＝黨名（左，34px）＋ 該黨在 color.txt 裡的全部階色塊（右，各 65px 寬）。
      國民黨／民進黨／民眾黨各 12 階（35→100%），無黨籍 11 階（35→85%，沒有 100% 那階）。
    """
    W, H = int(NM.LEGEND_BOX["w"] * NM.LEGEND_SCALE), \
           int(NM.LEGEND_BOX["h"] * NM.LEGEND_SCALE)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    ramps = NM.load_ramps()

    rows = len(NM.LEGEND_PARTIES)
    f_name = _font(34)
    name_w = 178                      # 色條起點（黨名最寬 5 字 × 34 ≈ 170）
    cell = 65                         # 每一階的寬度（12 階 = 780，剛好吃滿 960−178）

    # ---- 頂部比例尺（2026-10-29 第六版，使用者要求）----
    # 用最長的那一組色階當尺（國民黨／民進黨／民眾黨都是 12 階，無黨籍 11 階），
    # 每 LEGEND_TICK_STEP 階標一次 = 每 10 個百分點；刻度線對齊色階格線。
    SCALE_H = 40                      # 2× 繪製 → 看板 20px
    widest = max((ramps[p] for p in NM.LEGEND_PARTIES), key=len)
    f_tick = _font(26)
    f_unit = _font(22)
    for j in range(0, len(widest), NM.LEGEND_TICK_STEP):
        pct = widest[j][0]
        x0 = name_w + j * cell
        d.line([x0, SCALE_H - 12, x0, SCALE_H - 3],
               fill=(255, 255, 255, 120), width=2)
        d.text((x0 + 4, SCALE_H - 40), "%d%%" % pct,
               font=f_tick, fill=(255, 255, 255, 205))
    # 尺規最右端補一個「以上」（最後一格是 85+，右對齊貼齊畫布邊）
    _t = "以上"
    d.text((W - 4 - d.textlength(_t, font=f_unit), SCALE_H - 36), _t,
           font=f_unit, fill=(255, 255, 255, 140))

    pitch = (H - SCALE_H) / rows
    for i, party in enumerate(NM.LEGEND_PARTIES):
        top = SCALE_H + i * pitch
        d.text((2, top + 4), party, font=f_name, fill=white)
        ry = round(top + 4)
        rh = round(pitch - 9)
        for j, (_, hexv) in enumerate(ramps[party]):
            col = tuple(int(hexv[k:k + 2], 16) for k in (1, 3, 5))
            x0 = round(name_w + j * cell)
            d.rectangle([x0, ry, x0 + cell - 1, ry + rh], fill=col + (255,))

    img.save(NM.OUT_LEGEND, "PNG", optimize=True)
    print("  ✓ legend %s  %d×%d  （看板框 %d×%d，%d 列 × 各 %s 階，%d KB）"
          % (os.path.basename(NM.OUT_LEGEND), W, H,
             NM.LEGEND_BOX["w"], NM.LEGEND_BOX["h"], rows,
             "/".join(str(len(ramps[p])) for p in NM.LEGEND_PARTIES),
             os.path.getsize(NM.OUT_LEGEND) // 1024))
    return {"file": os.path.basename(NM.OUT_LEGEND), "w": W, "h": H,
            "box": dict(NM.LEGEND_BOX)}


def main():
    only_legend = "--legend" in sys.argv[1:]
    print("全國看板素材")
    info = {"maps": {}, "crop": None}
    if only_legend:
        if os.path.isfile(NM.OUT_META):
            with open(NM.OUT_META, encoding="utf-8") as f:
                info = json.load(f)
    else:
        info = build_maps()
    info["legend"] = build_legend()
    with open(NM.OUT_META, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("  ✓ 尺寸表 %s" % os.path.relpath(NM.OUT_META, NM.ROOT))


if __name__ == "__main__":
    main()
