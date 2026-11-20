# -*- coding: utf-8 -*-
"""
blank_board.py — 立法院選舉看板「空白骨架圖」（元素示意）

★ 與 Mayors/2022NineInOne/script/blank_board.py 的差別：
  那一支把 layout.js 的常數**複製**了一份，本次評審就抓到 9 處漂移。
  這一支只 `import layout_board`，所有矩形、字級、色彩都由真值供給，
  骨架圖與未來的渲染器保證同一套數字。

★ PIL 坑（沿用上次結論）：
  往 RGBA 圖上直接畫半透明色是「覆蓋 alpha」而不是混合，存成 RGB 會整塊變白。
  這裡全部先畫到獨立 RGBA 覆蓋層，最後一次 alpha_composite。

用法：
    python video/blank_board.py            # → video/dist/空白看板_立法院_元素示意.png
    python video/blank_board.py --scale 1  # 出 2560×1440 預覽
"""
import os
import sys
import math
import argparse

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_board as L   # noqa: E402

FONT_CANDIDATES = [
    # 2026-11-20：順序照 2022 看板 FONT_STACK 的實際命中結果 ——
    # 瀏覽器逐族往下找「GenSekiGothic TW H／源石黑體 H」都不存在，
    # 實際命中的是 gensekigothic-h.ttc（family "GenSekiGothic TW"・H 面，
    # ttc index 0），所以 PIL 端也把它排最前，與 2022 同一支字型檔。
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\gensekigothic-h.ttc"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf"),
    r"C:\Windows\Fonts\msjhbd.ttc",
    r"C:\Windows\Fonts\msjh.ttc",
]


def pick_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise RuntimeError("找不到中文字型")


FONT_PATH = pick_font()

# 2026-11-20 深夜十一修：**小字號中文備用字重（Bold）**。
# 源石黑體 Heavy 在 ≤20px 時「萬」的草字頭兩點間隙不足 1px，反鋸齒後
# 糊成一條橫杠（實測 20px 糊死、22px 勉強、24px 起清晰）；同家族 Bold
# 筆畫細一階，**13px 起草字頭即可分辨**。票數「萬」「票」這類小字號
# 中文改用本字面，字級與版面完全不受影響。
CJK_BOLD_PATH = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\gensekigothic-b.ttc")
if not os.path.exists(CJK_BOLD_PATH):
    CJK_BOLD_PATH = FONT_PATH
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 數字字型
# 規則：**所有阿拉伯數字一律用 Noto Sans TC**，中文仍走 FONT_PATH。
# PIL 沒有 CSS 那種「逐字回退」，所以由 Board.text() 把字串切成「數字段／非數字段」，
# 各自用不同字型畫、共用同一條基線 —— 也就是 2022 看板在 canvas 上做到的效果。
#
# 機器上沒有 Noto Sans TC，依序往後找同一家族的字重（拉丁數字三種變體同形）：
#   ① 專案內 assets/fonts/NotoSansTC-*.otf  ← 丟檔進來就會自動優先採用
#   ② Noto Sans UI Black（2022 看板「2022／11 月 26 日」用的那一支，900）
#   ③ Noto Sans SC（系統內建，拉丁字形與 TC 相同，但只有 Regular）
NUM_FONT_CANDIDATES = [
    os.path.join(HERE, "assets", "fonts", "NotoSansTC-Black.otf"),
    os.path.join(HERE, "assets", "fonts", "NotoSansTC-Bold.otf"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\NotoSansUI-Black.ttf"),
    r"C:\Windows\Fonts\Noto Sans SC.ttf",
]


def pick_num_font():
    for p in NUM_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


NUM_FONT_PATH = pick_num_font()

# 台灣輪廓佔位（僅用來核對主圖框比例，不含任何資料）
SILHOUETTE = os.path.join(HERE, "assets", "tw_silhouette.png")
SHOW_SILHOUETTE = True


def split_digits(s):
    """'45.17%' → [('45',1),('.',0),('17',1),('%',0)]；'第 11 屆' 同理。"""
    out = []
    for ch in s:
        isnum = "0" <= ch <= "9"
        if out and out[-1][1] == isnum:
            out[-1] = (out[-1][0] + ch, isnum)
        else:
            out.append((ch, isnum))
    return out


class Board:
    """把設計座標（2560×1440）換算到輸出像素的一個薄包裝。"""

    def __init__(self, scale=1.5, grid=True):
        self.s = scale
        self.use_grid = grid
        self.W = int(round(L.W * scale))
        self.H = int(round(L.H * scale))
        self._fonts = {}
        self.img = self._bg().convert("RGBA")
        self.ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.ov)

    # ---------------------------------------------------------- 座標 / 字型
    def px(self, v):
        return int(round(v * self.s))

    def box(self, x, y, w, h):
        return [self.px(x), self.px(y), self.px(x + w), self.px(y + h)]

    def font(self, size):
        k = max(1, int(round(size * self.s)))
        if k not in self._fonts:
            self._fonts[k] = ImageFont.truetype(FONT_PATH, k)
        return self._fonts[k]

    def num_font(self, size):
        """阿拉伯數字專用字型；沒有這支字型就退回中文字型（等同舊行為）。"""
        if not NUM_FONT_PATH:
            return self.font(size)
        k = max(1, int(round(size * self.s)))
        key = ("n", k)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(NUM_FONT_PATH, k)
        return self._fonts[key]

    def font_b(self, size):
        """中文 Bold 字面（小字號「萬」「票」專用，防草字頭糊死）。"""
        k = max(1, int(round(size * self.s)))
        key = ("b", k)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(CJK_BOLD_PATH, k)
        return self._fonts[key]

    def measure(self, s, size, cjk_bold=False):
        """混合字型下的實際寬度（像素）。fit_text / 對齊都要用這一個。
        cjk_bold=True 時中文段按 Bold 字面量寬（與 text(cjk_bold=True) 對齊）。
        """
        if not NUM_FONT_PATH:
            f = self.font_b(size) if cjk_bold else self.font(size)
            return f.getlength(s)
        w = 0.0
        for t, isnum in split_digits(s):
            if isnum:
                w += self.num_font(size).getlength(t)
            else:
                w += (self.font_b(size) if cjk_bold
                      else self.font(size)).getlength(t)
        return w

    def text(self, xy, s, size, color, anchor="la", cjk_bold=False):
        """畫一行字：**數字走 NUM_FONT_PATH、其餘走 FONT_PATH**，共用一條基線。
        cjk_bold=True 時中文段改走 Bold 字面（小字號「萬」「票」防糊）。

        PIL 的垂直錨點與基線關係（實測）：
            a → y + ascent ／ m → y + (ascent−descent)/2 ／ d → y − descent ／ s → y
        所以這裡一律換算成基線，再用 'ls' 逐段畫，兩支字型才不會一高一低。
        """
        if not NUM_FONT_PATH:
            f = self.font_b(size) if cjk_bold else self.font(size)
            self.d.text((self.px(xy[0]), self.px(xy[1])), s,
                        font=f, fill=color, anchor=anchor)
            return

        runs = split_digits(s)
        fonts = [self.num_font(size) if n
                 else (self.font_b(size) if cjk_bold else self.font(size))
                 for _, n in runs]
        widths = [f.getlength(t) for (t, _), f in zip(runs, fonts)]
        total = sum(widths)

        x = self.px(xy[0])
        y = self.px(xy[1])
        ha = anchor[0] if len(anchor) > 0 else "l"
        va = anchor[1] if len(anchor) > 1 else "a"
        if ha == "m":
            x -= total / 2.0
        elif ha == "r":
            x -= total

        asc, desc = self.font(size).getmetrics()
        if va == "a":
            base = y + asc
        elif va == "m":
            base = y + (asc - desc) / 2.0
        elif va == "d":
            base = y - desc
        else:
            base = y

        for (t, _), f, w in zip(runs, fonts, widths):
            self.d.text((x, base), t, font=f, fill=color, anchor="ls")
            x += w

    # ---------------------------------------------------------- 底色
    def _bg(self):
        W2, H2 = self.W, self.H

        def hexc(s):
            s = s.lstrip("#")
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

        def lerp(a, b, t):
            return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))

        top, mid, bot = hexc(L.C["bg_top"]), hexc(L.C["bg_mid"]), hexc(L.C["bg_bottom"])
        img = Image.new("RGB", (W2, H2), bot)
        d = ImageDraw.Draw(img)
        for y in range(H2):
            t = y / (H2 - 1)
            c = lerp(top, mid, t / 0.55) if t < 0.55 else lerp(mid, bot, (t - 0.55) / 0.45)
            d.line([(0, y), (W2, y)], fill=c)

        # 兩側中性光暈（刻意不用藍/綠，避免暗示特定政黨）
        for cx, cy, r, col, a in ((430, 560, 1180, hexc(L.C["glow_l"]), 0.20),
                                  (2130, 1080, 1180, hexc(L.C["glow_r"]), 0.16)):
            glow = Image.new("RGB", (W2, H2), (0, 0, 0))
            gd = ImageDraw.Draw(glow)
            steps = 40
            for i in range(steps, 0, -1):
                rr = self.px(r) * i / steps
                k = a * (1 - i / steps) ** 1.8
                gd.ellipse([self.px(cx) - rr, self.px(cy) - rr,
                            self.px(cx) + rr, self.px(cy) + rr],
                           fill=lerp((0, 0, 0), col, k))
            img = Image.blend(img, Image.blend(img, glow, 0.9), 0.55)

        # 80px 細網格（正式看板關掉，但暗角照留）
        if getattr(self, "use_grid", True):
            grid = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grid)
            for x in range(0, L.W + 1, 80):
                gd.line([(self.px(x), 0), (self.px(x), H2)], fill=(255, 255, 255, 10), width=1)
            for y in range(0, L.H + 1, 80):
                gd.line([(0, self.px(y)), (W2, self.px(y))], fill=(255, 255, 255, 10), width=1)
            img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")

        # 暗角
        vig = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(vig).ellipse([-W2 * .26, -H2 * .38, W2 * 1.26, H2 * 1.38], fill=150)
        vig = vig.point(lambda v: int((255 - v) * 0.60))
        img = Image.composite(Image.new("RGB", (W2, H2), (0, 0, 0)), img, vig)
        return img

    # ---------------------------------------------------------- 基本圖形
    def rr_points(self, x, y, w, h, r, step=2.0):
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

    def dashed_rr(self, x, y, w, h, r=16, color=(255, 255, 255, 140),
                  dash=10, gap=8, width=2):
        pts = self.rr_points(x, y, w, h, r)
        acc = 0.0
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            seg = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if seg == 0:
                continue
            on = (acc % (dash + gap)) < dash
            acc += seg
            if on:
                self.d.line([(self.px(p0[0]), self.px(p0[1])),
                             (self.px(p1[0]), self.px(p1[1]))],
                            fill=color, width=max(1, int(round(width * self.s))))

    def fill_rr(self, x, y, w, h, r, color):
        self.d.rounded_rectangle(self.box(x, y, w, h), radius=self.px(r), fill=color)

    def stroke_rr(self, x, y, w, h, r, color, width=1):
        self.d.rounded_rectangle(self.box(x, y, w, h), radius=self.px(r),
                                 outline=color, width=max(1, int(round(width * self.s))))

    def ghost(self, x, y, w, h, label="", size=10, r=6):
        """帶標籤的佔位框：淡填充 + 細線框（給「照片 / 席次 / 徽章」這種真實區塊用）"""
        if w <= 2 or h <= 2:
            return
        self.fill_rr(x, y, w, h, r, (255, 255, 255, 16))
        self.stroke_rr(x, y, w, h, r, (255, 255, 255, 40), 1)
        if label and h >= size * 1.5:
            self.text((x + w / 2, y + h / 2), label, size,
                      (255, 255, 255, 92), anchor="mm")

    def bar(self, x, y, w, h, a=44):
        """文字佔位：一條灰槓，代表一行字（比「框套框」乾淨得多）"""
        if w <= 2 or h <= 1:
            return
        self.fill_rr(x, y, max(2, w), max(2, h), h / 2, (255, 255, 255, a))

    def chip(self, no, x, y, w=34, h=22):
        self.fill_rr(x, y, w, h, 7, (255, 255, 255, 34))
        self.stroke_rr(x, y, w, h, 7, (255, 255, 255, 120), 1)
        self.text((x + w / 2, y + h / 2 + 0.5), "%02d" % no, 11,
                  (255, 255, 255, 235), anchor="mm")

    # ---------------------------------------------------------- 元素標籤
    def strip_h(self, el):
        if el.get("strip"):
            return el["strip"]
        return 30 if el["rect"][3] < 200 else 42

    def label_strip(self, el):
        """所有元素統一：編號牌 + 名稱 + 規格。
        圓形元素（年份圓盤）例外：標籤擺在圓的上方、規格擺在圓的下方。"""
        x, y, w, h = el["rect"]
        if el.get("kind") == "disc":
            self.chip(el["no"], x, y + h + 6, 30, 20)
            self.text((x + 38, y + h + 7), el["name"], 14, (255, 255, 255, 228))
            self.text((x, y + h + 30), el["spec"], 9, (255, 255, 255, 112))
            return
        small = h < 200
        self.chip(el["no"], x + 10, y + (6 if small else 8),
                  w=30 if small else 34, h=20 if small else 22)
        self.text((x + 48 if small else x + 52, y + (7 if small else 9)),
                  el["name"], 14 if small else 15, (255, 255, 255, 228))
        if el.get("spec") and h >= 74:
            self.text((x + 48 if small else x + 52, y + (23 if small else 27)),
                      el["spec"], 9 if small else 10, (255, 255, 255, 118))

    def content(self, el):
        x, y, w, h = el["rect"]
        top = self.strip_h(el)
        return x + 14, y + top, w - 28, h - top - 10

    # ---------------------------------------------------------- 各元素幽靈內容
    def k_flag(self, el):
        x, y, w, h = el["rect"]
        cx, cy, cw, ch = self.content(el)
        self.fill_rr(cx, cy, cw, ch, 10, (255, 255, 255, 46))
        self.stroke_rr(cx, cy, cw, ch, 10, (255, 255, 255, 90), 1)
        self.text((cx + cw / 2, cy + ch / 2), "國旗 3 : 2", 12, (30, 40, 55, 200), anchor="mm")

    def k_title(self, el):
        x, y, w, h = el["rect"]
        cx, cy, cw, ch = self.content(el)
        self.text((cx + 10, cy + ch * 0.50), "第十一屆立法院立法委員選舉", 50,
                  (255, 255, 255, 96), anchor="lm")

    def k_disc(self, el):
        x, y, w, h = el["rect"]
        r = w / 2
        ccx, ccy = x + r, y + r
        self.d.ellipse(self.box(x, y, w, h), fill=(255, 255, 255, 12),
                       outline=(255, 255, 255, 120), width=max(1, self.px(1.5)))
        # 2026-11-20：字級照 2022 九合一 dateBlock（年份 96＋年 32／投票日 36·23）；
        # 實際盤徑＝年份數字墨高×1.95（≈135），外框 160 僅為定位示意
        self.text((ccx, ccy - 2), "2024", 96, (255, 255, 255, 96), anchor="mm")
        self.text((ccx, ccy + 44), "1月13日", 36, (255, 255, 255, 82), anchor="mm")

    def k_seats(self, el):
        x, y, w, h = el["rect"]
        # 2026-11-20 新樣張：四黨條**單欄**在左（右欄＝未來政黨增加的預留區，
        # 本屆留白只畫虛線框）；中間＝半圓點陣＋白字 113。
        bw, bh, bgap = 287, 47, 10
        by0 = y + (h - (4 * bh + 3 * bgap)) / 2.0
        for i in range(4):
            sx = x + 24
            sy = by0 + i * (bh + bgap)
            self.fill_rr(sx, sy, bw, bh, 10, (255, 255, 255, 30))
            # 右端席次塊＋數字
            dw = bh * 0.86
            self.fill_rr(sx + bw - dw, sy, dw, bh, 10, (255, 255, 255, 46))
            self.bar(sx + bw - dw + dw * 0.24, sy + bh * 0.30,
                     dw * 0.52, bh * 0.40, 64)
            # 黨徽（圓形佔位）
            self.d.ellipse(self.box(sx + 8, sy + 5, 36, 36),
                           outline=(255, 255, 255, 110), width=1)
            # 黨名
            self.bar(sx + 50, sy + bh * 0.34, bw * 0.55, bh * 0.30, 62)
        # 預留欄（本屆留白，只畫虛線框示意）
        self.dashed_rr(x + 818, by0, bw, 4 * bh + 3 * bgap, 10,
                       color=(255, 255, 255, 60), dash=6, gap=8, width=1)
        # 中：半圓點陣（中心在卡寬 0.494、高 201）
        import math as _m
        hh = 201
        hw = hh * 3348 / 1680.0
        cx0 = x + w * 0.494 - hw / 2.0
        cy0 = y + 11
        R = hh * 0.44
        ccx, ccy = cx0 + hw / 2.0, cy0 + hh - 24
        for i in range(8):
            r = R * (0.14 + 0.86 * i / 7)
            n = max(3, int(r / R * 24))
            for j in range(n):
                ang = _m.radians(180 + (j + 0.5) * 180 / n)
                dx = ccx + r * _m.cos(ang)
                dy = ccy + r * _m.sin(ang)
                self.d.ellipse(self.box(dx - 3.2, dy - 3.2, 6.4, 6.4),
                               fill=(255, 255, 255, 55))
        self.text((cx0 + hw * 0.49, cy0 + hh * 0.82), "113", 48,
                  (255, 255, 255, 110), anchor="mm")

    def k_party_compact(self, el):
        """右欄緊湊條骨架（2026-11-20 兩行版式）：
        黨徽 ｜ 黨名＋票數·得票率 ｜ 席次塊。
        幾何走 `layout_board.party_geom_compact()`，與渲染器同一組數字。
        """
        x, y, w, h = el["rect"]
        c = L.CARD_COMPACT
        g = L.party_geom_compact(w, h)

        self.fill_rr(x, y, w, h, el["radius"], (255, 255, 255, 18))
        self.fill_rr(x + g["deep_x"], y, g["deep_w"], h, el["radius"],
                     (255, 255, 255, 30))
        self.ghost(x + g["em_x"], y + g["em_y"], g["em"], g["em"], "黨徽", 10, 6)

        # 席次數字
        self.bar(x + g["deep_x"] + g["deep_w"] * 0.24, y + h * 0.30,
                 g["deep_w"] * 0.52, h * 0.40, 64)

        # 兩行文字：行 1 黨名（基線 0.42h）、行 2 票數＋得票率（基線 0.86h）
        nx = x + g["name_x"]
        nw = g["name_right"] - g["name_x"]
        self.bar(nx, y + h * 0.24, nw * 0.72, h * 0.24, 62)
        self.bar(nx, y + h * 0.68, nw * 0.52, h * 0.13, 46)
        self.bar(nx + nw * 0.58, y + h * 0.70, nw * 0.24, h * 0.11, 38)

    def k_party(self, el):
        # 右欄「不分區」卡（2026-11-19 晚）：緊湊條版式，走獨立骨架
        if el["key"].startswith("right"):
            return self.k_party_compact(el)
        """滿色政黨卡（照樣張實測比例）：照片 1:1.58 ｜ 黨名／票數／主席＋率 三行 ｜
        黨徽（跨行 2–3）｜ 全高席次塊。幾何全部走 `layout_board.party_geom()`。
        """
        x, y, w, h = el["rect"]
        c = L.CARD
        # 與渲染器同一組縮放：左欄卡黨徽 ×1.5、照片寬 ×1.1、上下居中，右欄不變
        left = el["key"].startswith("left")
        g = L.party_geom(w, h,
                         em_scale=c["em_scale_left"] if left else 1.0,
                         photo_w_scale=c["photo_w_scale_left"] if left else 1.0,
                         em_vcenter=left)

        self.fill_rr(x, y, w, h, el["radius"], (255, 255, 255, 18))
        self.fill_rr(x + g["deep_x"], y, g["deep_w"], h, el["radius"],
                     (255, 255, 255, 30))

        if g["photo"]:
            px_, py_, pw_, ph_ = g["photo"]
            self.ghost(x + px_, y + py_, pw_, ph_, "照片", 10, 8)
        self.ghost(x + g["em_x"], y + g["em_y"], g["em"], g["em"], "黨徽", 10, 6)

        # 席次數字（實色塊上的純數字）
        self.bar(x + g["deep_x"] + g["deep_w"] * 0.24, y + h * 0.30,
                 g["deep_w"] * 0.52, h * 0.34, 64)

        # 三行文字佔位
        tx = x + g["text_x"]
        tw = g["text_right"] - g["text_x"]
        self.bar(tx, y + h * 0.14, tw * 0.62, h * 0.22, 62)      # 黨名（基線 0.36h）
        self.bar(tx, y + h * 0.52, tw * 0.56, h * 0.15, 46)      # 票數（基線 0.693h）
        self.bar(tx, y + h * 0.80, tw * 0.30, h * 0.13, 52)      # 主席姓名
        self.bar(tx + tw * 0.36, y + h * 0.82, tw * 0.26, h * 0.10, 40)  # 得票率

    def k_list(self, el):
        """小黨清單骨架（2026-11-20 深夜 9）：無行首「-」、無得票率條；
        cols=2 時畫兩欄（直式填欄）＋欄間分隔線。"""
        x, y, w, h = el["rect"]
        cx, cy, cw, ch = self.content(el)
        rows = el.get("rows", 4)
        cols = el.get("cols", 1)
        per = -(-rows // cols)
        col_gap = 24
        col_w = (cw - col_gap * (cols - 1)) / cols
        gap = 4
        row_h = (ch - (per - 1) * gap) / per
        for ci in range(cols):
            colx = cx + ci * (col_w + col_gap)
            n_ci = min(per, rows - ci * per)
            if n_ci <= 0:
                continue
            for i in range(n_ci):
                ry = cy + i * (row_h + gap)
                self.bar(colx + 2, ry + row_h * 0.32, col_w * 0.50,                 # 黨名
                         row_h * 0.36, 46)
                self.bar(colx + col_w * 0.60, ry + row_h * 0.36,                    # 票數（萬）
                         col_w * 0.30, row_h * 0.28, 38)
            if ci < cols - 1:
                vx = colx + col_w + col_gap / 2
                self.d.line([(self.px(vx), self.px(cy)), (self.px(vx), self.px(cy + ch))],
                            fill=(255, 255, 255, 28), width=max(1, self.px(1)))

    def k_indig(self, el):
        """原住民卡骨架（2026-11-20 深夜四修）：**照右上（右欄）政黨卡設計** ——
        [黨徽] 黨名＋票數·得票率（兩行）｜深塊席次，內部幾何＝
        party_geom_compact ＋ CARD_COMPACT 同一組真值。
        固定 3 行×2 欄（6 黨滿版），缺黨整格留白；右上白字分組標籤
        「原住民」在**卡片外**上緣。內距與渲染器同一組（14/14）。"""
        x, y, w, h = el["rect"]
        ig = L.INDIG_COMPACT
        cc = L.CARD_COMPACT
        cx, cy = x + 14, y + 14
        cw, ch = w - 28, h - 24
        self.bar(x + w - 4 - 66, y - 16, 66, 12, 92)                         # 分組標籤（卡外）
        rows = 3
        col_w = (cw - ig["gap_col"]) / 2
        bar_h = (ch - (rows - 1) * ig["row_gap"]) / rows
        for ci in range(2):
            bx = cx + ci * (col_w + ig["gap_col"])
            for ri in range(rows):
                if ci * rows + ri >= 3:
                    break                                                    # 缺黨留白
                by = cy + ri * (bar_h + ig["row_gap"])
                self.fill_rr(bx, by, col_w, bar_h, 10, (255, 255, 255, 30))
                g = L.party_geom_compact(col_w, bar_h, 1)
                self.fill_rr(bx + g["deep_x"], by, g["deep_w"], bar_h, 10,
                             (255, 255, 255, 46))                            # 席次塊
                self.bar(bx + g["em_x"], by + g["em_y"], g["em"], g["em"], 60)
                tx = bx + g["name_x"]
                tw = g["name_right"] - g["name_x"]
                self.bar(tx, by + bar_h * cc["base1"] - bar_h * 0.13,
                         tw * 0.44, bar_h * 0.15, 62)                        # 行 1 黨名
                self.bar(tx, by + bar_h * cc["base2"] - bar_h * 0.11,
                         tw * 0.58, bar_h * 0.13, 46)                        # 行 2 票數·率

    def k_map(self, el):
        x, y, w, h = el["rect"]
        # 極淡的台灣輪廓（只為了核對框比例，不是資料）
        if SHOW_SILHOUETTE and os.path.exists(SILHOUETTE):
            sil = Image.open(SILHOUETTE).convert("RGBA")
            fw, fh = w - 48, h - 96
            k = min(fw / sil.width, fh / sil.height)
            sw, sh = sil.width * k, sil.height * k          # 設計像素
            sil = sil.resize((max(1, self.px(sw)), max(1, self.px(sh))), Image.LANCZOS)
            sil.putalpha(sil.getchannel("A").point(lambda v: int(v * 0.55)))
            self.ov.alpha_composite(sil, (self.px(x + (w - sw) / 2),
                                          self.px(y + 60 + (fh - sh) / 2)))
        self.text((x + w / 2, y + h * 0.52), "未配置主圖", 30, (255, 255, 255, 78), anchor="mm")
        self.text((x + w / 2, y + h * 0.52 + 40), "assets/map.png（透明底 PNG）", 13,
                  (255, 255, 255, 66), anchor="mm")
        # 內縮安全框
        self.dashed_rr(x + 24, y + 24, w - 48, h - 48, 12,
                       color=(255, 255, 255, 30), dash=6, gap=10, width=1)

    def k_minimap(self, el):
        """縮小版輔圖（輔圖 1＝選舉得票級、輔圖 2＝縣市級）：透明底直接疊在主圖左上角
        （不鋪底板），骨架圖只畫虛線框標示位置。"""
        x, y, w, h = el["rect"]
        self.dashed_rr(x, y, w, h, el["radius"], color=(255, 255, 255, 110),
                       dash=8, gap=7, width=1.5)
        self.label_strip(el)
        cx, cy, cw, ch = self.content(el)
        # 0.52 比例的島形佔位，與主圖同一個形狀語言
        bw, bh = cw * 0.62, ch * 0.58
        self.fill_rr(cx + (cw - bw) / 2, cy + (ch - bh) / 2, bw, bh, 8,
                     (255, 255, 255, 30))
        self.dashed_rr(cx + (cw - bw) / 2, cy + (ch - bh) / 2, bw, bh, 8,
                       color=(255, 255, 255, 40), dash=5, gap=6, width=1)

    def k_note(self, el):
        x, y, w, h = el["rect"]
        cx, cy, cw, ch = self.content(el)
        self.bar(cx, cy + ch * 0.35, cw * 0.30, ch * 0.30, 40)
        self.bar(cx + cw * 0.34, cy + ch * 0.35, cw * 0.30, ch * 0.30, 40)
        self.bar(cx + cw * 0.68, cy + ch * 0.35, cw * 0.28, ch * 0.30, 40)

    # ---------------------------------------------------------- 尺標
    def ruler(self):
        for ty in L.LEGEND_Y_TICKS:
            self.d.line([(self.px(22), self.px(ty)), (self.px(56), self.px(ty))],
                        fill=(255, 255, 255, 82), width=max(1, self.px(1)))
            self.text((9, ty - 7), str(ty), 10, (255, 255, 255, 110))

    # ---------------------------------------------------------- 輸出
    def save(self, path):
        out = Image.alpha_composite(self.img, self.ov).convert("RGB")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        out.save(path)
        return out.size


KINDS = {
    "flag": "k_flag", "title": "k_title", "disc": "k_disc", "seats": "k_seats", "party": "k_party", "list": "k_list",
    "indig": "k_indig", "map": "k_map", "minimap": "k_minimap", "note": "k_note",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=L.SCALE)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-silhouette", action="store_true",
                    help="不畫極淡的台灣輪廓（純空框）")
    a = ap.parse_args()

    global SHOW_SILHOUETTE
    if a.no_silhouette:
        SHOW_SILHOUETTE = False

    b = Board(a.scale)

    # 頂部暗帶：只做柔和漸層、不畫橫線 —— 左內欄上移到 208 後，
    # 原本 268 的分隔線會從卡片中間穿過去。
    for i in range(b.px(L.HEADER_Y + L.HEADER_H + 80)):
        t = max(0.0, (i / max(1, b.px(L.HEADER_Y + L.HEADER_H + 80)) - 0.25))
        b.d.line([(0, i), (b.W, i)], fill=(3, 5, 12, int(140 * t ** 0.9)))

    for el in L.ELEMENTS:
        x, y, w, h = el["rect"]
        b.fill_rr(x, y, w, h, el["radius"], (255, 255, 255, 14))
        b.dashed_rr(x, y, w, h, el["radius"], color=(255, 255, 255, 120),
                    dash=10, gap=8, width=1.5)
        b.label_strip(el)
        getattr(b, KINDS[el["kind"]])(el)

    # 文件說明：取消頁尾後版面吃到 1404，只剩最底下 36px —— 說明改成兩行 8–9px
    b.text((72, 1407), "立法院選舉看板 · 空白骨架　·　2560×1440（輸出 3840×2160）"
                       "　·　虛線＝版面框，灰條＝文字行示意　·　真值：video/layout_board.py",
           9, (255, 255, 255, 120))
    b.text((72, 1421), "X 軸：72 / 692 ┃ 720 / 1320 ┃ 1360 / 1960 ┃ 2000 / 2488　"
                       "·　右欄 15–19 右對齊 2488，左欄 05–09 左對齊 72",
           8, (255, 255, 255, 92))

    b.ruler()

    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "dist", "空白看板_立法院_元素示意.png")
    size = b.save(out)
    print("saved:", out, size)


if __name__ == "__main__":
    main()
