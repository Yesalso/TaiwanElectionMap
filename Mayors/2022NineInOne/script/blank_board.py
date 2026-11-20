# -*- coding: utf-8 -*-
"""
blank_board.py — 画一张「什么都不配置」的空白看板骨架图（元素示意）

尺寸与坐标全部照抄 board/src/engine/js/core/layout.js（设计坐标 2560×1440），
按 S=1.5 输出 3840×2160，与正式交付尺寸一致。

不带任何数据：没有街景照片、没有地图、没有候选人、没有县徽与党徽，
只留版面的骨架 + 每个元素的编号标注。

★ 实现注意：所有半透明内容先画到独立的 RGBA 图层，最后一次性
  alpha_composite 到底图。直接往 RGBA 图上画半透明色，PIL 是「覆盖」
  alpha 而不是混合，存成 RGB 时半透明块会整块变白。
"""
import os
import math
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 基本设定
W, H = 2560, 1440          # 设计坐标（layout.js Layout.W / Layout.H）
S = 1.5                    # 输出倍率 → 3840×2160
FONT = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf")
if not os.path.exists(FONT):
    FONT = r"C:\Windows\Fonts\msjhbd.ttc"

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "board", "dist"))
OUT = os.path.join(OUT_DIR, "空白看板_元素示意.png")

W2, H2 = int(W * S), int(H * S)


def px(v):
    return int(round(v * S))


def P(*vals):
    return [px(v) for v in vals]


_fonts = {}


def font(size):
    """size 用设计像素传入，内部换算到输出像素。"""
    key = int(round(size * S))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT, key)
    return _fonts[key]


# ---------------------------------------------------------------- 底色
def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def build_bg():
    """渐层底 + 两侧政党色光晕（无街景照片，等于引擎的 fallback 路径）"""
    top, mid, bottom = hexc("#0d1738"), hexc("#0a1128"), hexc("#05080f")
    img = Image.new("RGB", (W2, H2), bottom)
    d = ImageDraw.Draw(img)
    for y in range(H2):
        t = y / (H2 - 1)
        c = lerp(top, mid, t / 0.55) if t < 0.55 else lerp(mid, bottom, (t - 0.55) / 0.45)
        d.line([(0, y), (W2, y)], fill=c)

    # 光晕（decor.glowLeft / glowRight）：直接在 RGB 上做加色混合
    for cx, cy, r, col, a in ((420, 620, 1180, "#2f6bd8", 0.30),
                              (2140, 600, 1180, "#23a455", 0.26)):
        glow = Image.new("RGB", (W2, H2), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        steps = 44
        for i in range(steps, 0, -1):
            rr = px(r) * i / steps
            k = a * (1 - i / steps) ** 1.7
            gd.ellipse([px(cx) - rr, px(cy) - rr, px(cx) + rr, px(cy) + rr],
                       fill=lerp((0, 0, 0), hexc(col), k))
        img = Image.blend(img, Image.blend(img, glow, 0.85), 0.5)

    # 细网格
    grid = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W + 1, 80):
        gd.line([(px(x), 0), (px(x), H2)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, H + 1, 80):
        gd.line([(0, px(y)), (W2, px(y))], fill=(255, 255, 255, 12), width=1)
    img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")

    # 暗角
    vig = Image.new("L", (W2, H2), 0)
    ImageDraw.Draw(vig).ellipse(
        [-W2 * 0.28, -H2 * 0.40, W2 * 1.28, H2 * 1.40], fill=150)
    vig = vig.point(lambda v: int((255 - v) * 0.62))
    img = Image.composite(Image.new("RGB", (W2, H2), (0, 0, 0)), img, vig)
    return img.convert("RGBA")


# ---------------------------------------------------------------- 绘图小工具
def rr_pts(x, y, w, h, r, step=2.0):
    pts = []
    r = min(r, w / 2, h / 2)

    def arc(cx, cy, a0, a1):
        n = max(6, int(abs(a1 - a0) * r / step / 6))
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    def line(x0, y0, x1, y1):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
        for i in range(1, n + 1):
            pts.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))

    arc(x + w - r, y + r, -90, 0)
    line(x + w, y + r, x + w, y + h - r)
    arc(x + w - r, y + h - r, 0, 90)
    line(x + w - r, y + h, x + r, y + h)
    arc(x + r, y + h - r, 90, 180)
    line(x, y + h - r, x, y + r)
    arc(x + r, y + r, 180, 270)
    line(x + r, y, x + w - r, y)
    return pts


def dashed_rr(d, x, y, w, h, r=18, color=(255, 255, 255, 128),
              dash=10, gap=8, width=2):
    pts = rr_pts(x, y, w, h, r)
    acc = 0.0
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if seg == 0:
            continue
        on = (acc % (dash + gap)) < dash
        acc += seg
        if on:
            d.line([(px(p0[0]), px(p0[1])), (px(p1[0]), px(p1[1]))],
                   fill=color, width=width)


def fill_rr(d, x, y, w, h, r, color):
    d.rounded_rectangle(P(x, y, x + w, y + h), radius=px(r), fill=color)


def text(d, xy, s, size, color, anchor="la"):
    d.text((px(xy[0]), px(xy[1])), s, font=font(size), fill=color, anchor=anchor)


def chip(d, num, x, y, w=46, h=30):
    label = "%02d" % num
    d.rounded_rectangle(P(x, y, x + w, y + h), radius=px(8),
                        fill=(255, 255, 255, 34), outline=(255, 255, 255, 105),
                        width=2)
    d.text((px(x + w / 2), px(y + h / 2 - 1)), label, font=font(16),
           fill=(255, 255, 255, 235), anchor="mm")


def label(d, num, title, x, y, spec=None):
    chip(d, num, x, y - 6)
    text(d, (x + 56, y), title, 21, (255, 255, 255, 220))
    if spec:
        text(d, (x + 56, y + 26), spec, 15, (255, 255, 255, 115))


# ---------------------------------------------------------------- 版面常量
HEADER_H = 236
CARD_W, CARD_H, CARD_Y = 452, 620, 274
CHIP_Y, CHIP_H = 910, 84
NAME_BL, PCT_BL, VOTE_BL = 1096, 1282, 1386
LEFT_CX, RIGHT_CX = 310, 2250
MAP = (560, 196, 1020, 1034)
MAP2 = (1440, 360, 564, 700)
MINORS_Y, MINORS_H = 1230, 160
BIG = (1520, 1102, 470, 288)
RIBBON_Y, RIBBON_H = 1396, 44


def main():
    base = build_bg()
    ov = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # ---------------- 页眉带：顶部渐层 + 分隔线 ----------------
    for y in range(px(HEADER_H)):
        t = y / px(HEADER_H)
        d.line([(0, y), (W2, y)], fill=(4, 7, 16, int(210 * (1 - t) ** 0.85)))
    d.line([(0, px(HEADER_H - 1)), (W2, px(HEADER_H - 1))],
           fill=(255, 255, 255, 42), width=2)
    text(d, (72, 200), "頁眉  HEADER   0 – 236 px", 17, (255, 255, 255, 105))

    # ① 国旗白卡
    x, y, w, h = 72, 28, 240, 160
    fill_rr(d, x, y, w, h, 24, (255, 255, 255, 26))
    dashed_rr(d, x, y, w, h, 24)
    label(d, 1, "國旗白卡", x + 16, y + 16, "240×160")

    # ② 主标题
    x, y, w, h = 346, 74, 620, 94
    fill_rr(d, x, y, w, h, 14, (255, 255, 255, 20))
    dashed_rr(d, x, y, w, h, 14)
    label(d, 2, "主標題", x + 16, y + 10, "56px / 900")
    text(d, (x + 16, y + 58), "2022年九合一選舉", 26, (255, 255, 255, 74))

    # ③ 年份圆盘 + 投票日
    cx, cy, dd = 1140, 116, 176
    x, y = cx - dd / 2, cy - dd / 2
    d.ellipse(P(x, y, x + dd, y + dd), fill=(109, 12, 34, 105))
    dashed_rr(d, x, y, dd, dd, dd / 2, color=(255, 255, 255, 110))
    chip(d, 3, cx - 23, y + 26)
    text(d, (cx, y + 60), "年份圓盤", 17, (255, 255, 255, 222), anchor="ma")
    text(d, (cx, cy + 16), "2022", 34, (255, 255, 255, 92), anchor="mm")
    text(d, (cx, cy + 52), "11 月 26 日", 15, (255, 255, 255, 82), anchor="mm")

    # ④ 县徽白卡
    x, y, w, h = 1289, 28, 174, 174
    fill_rr(d, x, y, w, h, 22, (255, 255, 255, 26))
    dashed_rr(d, x, y, w, h, 22)
    label(d, 4, "縣徽白卡", x + 14, y + 14, "150×150")

    # ⑤ 四行数据
    x, y, w, h = 1477, 52, 268, 128
    fill_rr(d, x, y, w, h, 10, (255, 255, 255, 16))
    dashed_rr(d, x, y, w, h, 10, color=(255, 255, 255, 88))
    chip(d, 5, x + 12, y + 8)
    text(d, (x + 68, y + 14), "四行數據", 21, (255, 255, 255, 220))
    for i, s in enumerate(("投票率", "有效票", "無效票", "選舉人數")):
        ty = y + 46 + i * 20
        text(d, (x + 14, ty), s, 13, (255, 255, 255, 96))
        text(d, (x + 92, ty), "—", 13, (255, 255, 255, 76))

    # ⑥ 时任首长
    x, y, w, h = 2376, 34, 112, 132
    fill_rr(d, x, y, w, h, 20, (255, 255, 255, 24))
    dashed_rr(d, x, y, w, h, 20)
    chip(d, 6, 2302, y - 2)
    text(d, (2348, y + 40), "時任縣市長", 15, (255, 255, 255, 130), anchor="ra")
    text(d, (2348, y + 64), "姓名", 24, (255, 255, 255, 130), anchor="ra")
    text(d, (2348, y + 100), "政黨", 15, (255, 255, 255, 115), anchor="ra")

    # ---------------- 左右主卡 ----------------
    for k, cx0 in ((7, LEFT_CX), (8, RIGHT_CX)):
        x = cx0 - CARD_W / 2
        fill_rr(d, x, CARD_Y, CARD_W, CARD_H, 40, (255, 255, 255, 26))
        dashed_rr(d, x, CARD_Y, CARD_W, CARD_H, 40)
        text(d, (cx0, CARD_Y + CARD_H / 2), "政黨色卡／照片框", 20,
             (255, 255, 255, 96), anchor="mm")
        text(d, (cx0, CARD_Y + CARD_H / 2 + 32), "452 × 620", 15,
             (255, 255, 255, 74), anchor="mm")
        chip(d, k, x + 18, CARD_Y + 14)
        text(d, (x + 74, CARD_Y + 18), "第 1 名主卡" if k == 7 else "第 2 名主卡",
             21, (255, 255, 255, 222))
        text(d, (x + 74, CARD_Y + 44), "得票前二名", 15, (255, 255, 255, 115))

        # 政党胶囊
        fill_rr(d, x, CHIP_Y, CARD_W, CHIP_H, 42, (255, 255, 255, 24))
        dashed_rr(d, x, CHIP_Y, CARD_W, CHIP_H, 42, color=(255, 255, 255, 96))
        text(d, (cx0, CHIP_Y + CHIP_H / 2), "◯ 政黨徽章 ＋ 政黨名", 18,
             (255, 255, 255, 105), anchor="mm")

        # 姓名 / 得票率 / 得票数
        for top, bot, cap in ((1022, 1106, "姓名 104px"),
                              (1188, 1300, "得票率 128px"),
                              (1316, 1392, "得票數 80px")):
            fill_rr(d, x, top, CARD_W, bot - top, 10, (255, 255, 255, 10))
            dashed_rr(d, x, top, CARD_W, bot - top, 10,
                      color=(255, 255, 255, 58), dash=6, gap=8, width=1)
            text(d, (x + 14, bot - 24), cap, 15, (255, 255, 255, 105))

    # ---------------- 主图 ----------------
    # 画到 1424 就停：layout 的框是 560–1580，但实际图墨跡右缘只到 ≈1408，
    # 再往右就和副图（1440 起）在画面上叠框，示意图里收在 1424 更好读。
    x, y, w, h = MAP[0], MAP[1], 864, MAP[3]
    fill_rr(d, x, y, w, h, 18, (255, 255, 255, 16))
    dashed_rr(d, x, y, w, h, 18)
    label(d, 9, "主圖 · 村里級得票地圖", x + 20, y + 52,
          "框 1020×1034（右緣 1580）")
    text(d, (x + w / 2, y + h / 2 - 10), "未配置地圖", 30, (255, 255, 255, 74),
         anchor="mm")
    text(d, (x + w / 2, y + h / 2 + 34), "assets/map.png（透明底 PNG）", 15,
         (255, 255, 255, 64), anchor="mm")

    # ---------------- 第二张图 ----------------
    x, y, w, h = MAP2
    fill_rr(d, x, y, w, h, 16, (255, 255, 255, 14))
    dashed_rr(d, x, y, w, h, 16)
    label(d, 10, "副圖 · 鄉鎮市區", x + 16, y + 16, "564×700")
    text(d, (x + w / 2, y + h / 2 - 20), "未配置", 22, (255, 255, 255, 66),
         anchor="mm")

    # ⑭ 图例：与副图共用右栏，本批关闭
    chip(d, 14, x + 16, y + h - 92)
    text(d, (x + 72, y + h - 88), "圖例（選配）", 15, (255, 255, 255, 135))
    text(d, (x + 16, y + h - 48), "與副圖共用右欄 · 22 場關閉", 14,
         (255, 255, 255, 88))

    # ---------------- 第3名高卡 ----------------
    x, y, w, h = BIG
    fill_rr(d, x, y, w, h, 18, (255, 255, 255, 20))
    dashed_rr(d, x, y, w, h, 18)
    label(d, 11, "第 3 名 高卡", x + 14, y + 14, "470×288 · 往上長")
    text(d, (x + 14, y + 78), "占位框 175×240", 14, (255, 255, 255, 100))
    for i, s in enumerate(("姓名", "政黨", "得票率", "票數")):
        text(d, (x + 232, y + 80 + i * 44), s, 15, (255, 255, 255, 90))

    # ---------------- 小卡带 + others ----------------
    x, y, w, h = 560, MINORS_Y, 896, MINORS_H
    fill_rr(d, x, y, w, h, 12, (255, 255, 255, 14))
    dashed_rr(d, x, y, w, h, 12, color=(255, 255, 255, 96))
    label(d, 12, "第 4 名起 小卡帶 ＋ 其他候選人清單", x + 14, y + 14,
          "92×118 小卡 · 一行一位")
    for i in range(4):
        bx = x + 424 + i * 104
        fill_rr(d, bx, y + 26, 92, 118, 10, (255, 255, 255, 20))
        dashed_rr(d, bx, y + 26, 92, 118, 10, color=(255, 255, 255, 80),
                  dash=6, gap=6)
    for i, s in enumerate(("- 姓名      票數", "- 姓名      票數", "- 姓名      票數")):
        text(d, (x + 26, y + 58 + i * 28), s, 17, (255, 255, 255, 100 - i * 18))
    text(d, (x + 26, y + 138), "↑ 其他候選人清單格", 13, (255, 255, 255, 78))

    # ---------------- 底部得票比例带 ----------------
    y = RIBBON_Y
    d.rectangle(P(0, y, W, y + RIBBON_H), fill=(255, 255, 255, 16))
    d.line([(0, px(y)), (W2, px(y))], fill=(255, 255, 255, 90), width=2)
    for i in range(1, 6):
        d.line([(px(i * W / 6), px(y)), (px(i * W / 6), px(y + RIBBON_H))],
               fill=(255, 255, 255, 55), width=2)
    chip(d, 13, 16, y + 6)
    text(d, (74, y + 12), "得票比例帶   0 – 2560 × 44 px（依得票率分塊）", 16,
         (255, 255, 255, 160))

    # ---------------- 左边缘：关键 y 坐标 ----------------
    for ty in (HEADER_H, CARD_Y, CHIP_Y, NAME_BL, MINORS_Y, RIBBON_Y):
        d.line([(24, px(ty)), (56, px(ty))], fill=(255, 255, 255, 78), width=2)
        d.text((px(10), px(ty - 8)), str(ty), font=font(12),
               fill=(255, 255, 255, 105))

    # ---------------- 文档说明（主图区下部）----------------
    text(d, (MAP[0] + 20, MAP[1] + MAP[3] - 104),
         "2022 縣市長選舉看板 · 空白骨架", 26, (255, 255, 255, 140))
    text(d, (MAP[0] + 20, MAP[1] + MAP[3] - 68),
         "設計座標 2560 × 1440　·　輸出 3840 × 2160（1.5×）　·　不含任何資料",
         15, (255, 255, 255, 90))
    text(d, (MAP[0] + 20, MAP[1] + MAP[3] - 44),
         "虛線＝版面框位置（尺寸取自 layout.js）", 15, (255, 255, 255, 74))

    out = Image.alpha_composite(base, ov).convert("RGB")
    os.makedirs(OUT_DIR, exist_ok=True)
    out.save(OUT)
    print("saved:", OUT, out.size)


if __name__ == "__main__":
    main()
