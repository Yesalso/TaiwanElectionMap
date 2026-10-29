# -*- coding: utf-8 -*-
"""build_party_marks.py —— 政黨徽章重製管線（192×192、圓外透明）。

★ 為什麼需要這支：`layers.js` 把黨徽當**內切於正方形的圓徽**畫在深藍底上
  （drawImage(img, sx, markY, markW, markW)，見 render/layers.js 徽章段），
  所以成品必須「圓內不透明、圓外 alpha=0」。直接把方形原圖丟進去，
  深藍底上就會多出一個色塊。

   原始素材                                  成品
   ----------------------------------------  ------------------------------
   Video/assets/party/<中文>.png             dist/assets/party/party_<key>.png

兩種原圖形態、兩種處理（`MODES` 表，逐檔指定；`auto` 依邊框色判斷）：

  keywhite  白底圓徽（PFP / NSC / IND）
            白底轉透明 → 裁到 alpha 外框 → 等比縮進 192×192。
            原圖本身就是圓形主體，去背後圓自然內切，圓外已是透明。

  alpha     已去背圓徽（DPP 新版：935²、圓外已透明、圓內是白底）
            **不能再去白**：白底是徽章本體，去白會只剩綠十字＋台灣地圖浮在深藍底上。
            只裁 alpha 外框 → 等比縮進 192×192，白色圓盤原樣保留。

  circle    方框內切圓（TPP 方形色塊、KMT 2026 版）
            底色即徽章本體、不能去背 → 置中裁正方形 → **內切圓遮罩** → 192×192。
            TPP：蒂芬妮綠方底＋奶油色「眾」→ 綠圓＋白字。
            ★ KMT 2026-10-28 換版：1280² 不透明方框、藍圓盤內切、**盤心是純白「白日」＋12 道光芒**。
              這張若走 keywhite 會把白日一起挖掉（實測圓心 75.7% 變透明，深藍底上只剩一個藍圈），
              所以必須走 circle：只切掉四個白角，白日原樣保留（圓心 alpha 全 255）。
            圓遮罩與圓盤邊緣重合（內切），邊緣靠 4× 超採樣抗鋸齒。

執行：
    python src/tools/build_party_marks.py            # 只補缺的（既有成品不動）
    python src/tools/build_party_marks.py tpp        # 指定重做
    python src/tools/build_party_marks.py --all      # 六枚全部重做

★ 預設只做「成品不存在」的檔，避免無謂地重算其他五枚（成品位元組會變，
  但畫面無差；要嚴格保持其他檔不變就別加 --all）。
"""
import os
import sys

import numpy as np
from PIL import Image

BOARD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(BOARD)))   # board → 2022NineInOne → Mayors → 倉庫根
SRC_DIR = os.path.join(REPO, "Video", "assets", "party")
OUT_DIR = os.path.join(BOARD, "dist", "assets", "party")

SIZE = 192          # 成品邊長（layers.js 以 markW 正方形繪製）
SS = 4              # 圓遮罩超採樣倍率（邊緣抗鋸齒）
WHITE_TOL = 12      # 白底容差（>= 243 算白），與 build_assets.py 一致

# key → (原圖檔名, 形態)
MARKS = {
    # ★ 2026-10-28 換版：新圖是不透明方框＋內切藍圓盤＋純白白日。
    #   走 keywhite 會把白日挖空（圓心 75.7% 透明），只能走 circle（只切四個白角）。
    "kmt": ("中国国民党.png", "circle"),
    "dpp": ("民主进步党.png", "alpha"),
    "pfp": ("亲民党.png", "keywhite"),
    "nsc": ("新党.png", "keywhite"),
    "ind": ("无党籍.png", "keywhite"),
    "tpp": ("台湾民众党.png", "circle"),
}


def _alpha_circle(im, size=SIZE, ss=SS):
    """置中裁正方形 → 內切圓遮罩（alpha）→ size×size。"""
    w, h = im.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)

    big = size * ss
    yy, xx = np.mgrid[0:big, 0:big]
    c = (big - 1) / 2.0
    r = big / 2.0
    mask = (((xx - c) ** 2 + (yy - c) ** 2) <= r * r).astype(np.uint8) * 255
    mask = Image.fromarray(mask, mode="L").resize((size, size), Image.LANCZOS)

    out = im.convert("RGBA")
    out.putalpha(Image.fromarray(
        (np.array(out.split()[3]).astype(np.uint16) * np.array(mask).astype(np.uint16) // 255)
        .astype(np.uint8), mode="L"))
    return out


def _fit_square(img, size=SIZE):
    """裁 alpha 外框 → 等比縮進 size×size（置中，不拉伸）。"""
    box = img.split()[3].getbbox()
    if box:
        img = img.crop(box)
    w, h = img.size
    k = size / float(max(w, h))
    img = img.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.size[0]) // 2, (size - img.size[1]) // 2), img)
    return canvas


def _alpha_trim(im, size=SIZE):
    """原圖圓外已是透明 → 只裁外框、縮放（白底是徽章本體，不可去白）。"""
    return _fit_square(im.convert("RGBA"), size)


def _alpha_keywhite(im, size=SIZE, tol=WHITE_TOL):
    """白底轉透明 → 裁 alpha 外框 → 等比 fit 進 size×size（置中）。"""
    d = np.array(im.convert("RGBA"))
    r, g, b, a = d[..., 0], d[..., 1], d[..., 2], d[..., 3]
    limit = 255 - tol
    white = (r >= limit) & (g >= limit) & (b >= limit)
    d[..., 3] = np.where(white & (a > 0), 0, a)
    return _fit_square(Image.fromarray(d, mode="RGBA"), size)


def _detect_mode(path):
    """圓外已透明 → alpha；邊框色是白 → keywhite；否則視為方形色塊 → circle。"""
    d = np.array(Image.open(path).convert("RGBA"))
    edge = np.concatenate([d[0], d[-1], d[:, 0], d[:, -1]])
    if (edge[:, 3] < 10).mean() > 0.9:
        return "alpha"
    rgb = edge[:, :3].astype(int)
    whiteish = (rgb >= 255 - WHITE_TOL).all(axis=1)
    return "keywhite" if whiteish.mean() > 0.9 else "circle"


def build(key, force=True):
    src_name, mode = MARKS[key]
    src = os.path.join(SRC_DIR, src_name)
    dst = os.path.join(OUT_DIR, "party_%s.png" % key)
    if not os.path.isfile(src):
        print("  [缺] %s" % src)
        return False
    if not force and os.path.isfile(dst):
        print("  · %s 已存在，跳過（--all 可強制重做）" % os.path.basename(dst))
        return False

    if mode == "auto":
        mode = _detect_mode(src)

    im = Image.open(src).convert("RGBA")
    fn = {"circle": _alpha_circle, "alpha": _alpha_trim, "keywhite": _alpha_keywhite}[mode]
    out = fn(im)
    os.makedirs(OUT_DIR, exist_ok=True)
    out.save(dst, "PNG", optimize=True)

    a = np.array(out)[..., 3]
    inside = np.array(out)[..., :3][a > 200]
    print("  ✓ party_%s.png  %s  %s  透明 %.1f%%  邊框 alpha=%d  圓內平均色 %s"
          % (key, mode, out.size, (a < 10).mean() * 100, a[0, 0],
             tuple(int(v) for v in inside.mean(axis=0)) if len(inside) else "-"))
    return True


def main():
    args = [x for x in sys.argv[1:] if x]
    force_all = "--all" in args
    keys = [x for x in args if not x.startswith("-")] or list(MARKS)
    for k in keys:
        if k not in MARKS:
            print("  [略] 未知 key：%s（可用：%s）" % (k, ", ".join(MARKS)))
            continue
        build(k, force=force_all or k in args)


if __name__ == "__main__":
    main()
