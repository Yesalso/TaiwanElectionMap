# -*- coding: utf-8 -*-
"""assets.py —— 靜態素材透明化。只有兩件小事：

1. 白底 -> 透明（white_to_alpha）—— 唯一的通用規則，
   alpha = (255 - min(R,G,B)) / soft。

2. 圓形主體內切於正方形 -> 圓外透明（circle_mark）
   「白 -> 透明」會把圖案**內部**的白色一起抽掉（國徽的太陽、
   民進黨徽的十字底），這類圖改用幾何的內切圓遮罩。

3. 尺寸 / 寬高比檢查輔助（png_size / aspect_warning / embed）。

★ 候選人照片**不在這條管線裡**。看板不畫候選人照片（卡面只填政黨純色，
  見 _engine/js/render/layers.js 的 CandidateLayer），所以沒有任何去背、
  裁切或縮放要做；照片怎麼合成由使用者自行後製決定。

成品一律寫到 NewSolution/png/processed/（見 NewSolution/tool/build_assets.py）。
"""

from __future__ import annotations

import base64
import os
from typing import Dict, NamedTuple, Optional, Tuple

import numpy as np


# ==========================================================================
# 白底 -> 透明（唯一規則：越接近純白越透明）
# ==========================================================================
def load_rgb(path: str, bg: Tuple[int, int, int] = (255, 255, 255)):
    """讀圖並回傳 RGB。來源帶 alpha 時先合成到白底，「白底」這個前提才成立。"""
    from PIL import Image
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, bg)
        flat.paste(im, (0, 0), im)
        return flat
    return im.convert("RGB")


def white_to_alpha(src: str, dst: str, soft: int = 30, width: int = 0,
                   crop: bool = True) -> Tuple[int, int]:
    """白底 -> 透明 PNG，回傳成品尺寸。

    alpha = (255 - min(R,G,B)) / soft，夾在 0~1：純白全透明，比白暗超過 soft
    即完全不透明。soft 就是過渡帶的寬度，越大邊緣越柔。

    width 給定時先等比例縮圖，再算 alpha —— 白底大圖先縮小，色塊與白底一起
    被平均，邊緣自然帶出柔順的抗鋸齒。crop=True 再依 alpha 收掉四周透明邊。
    """
    from PIL import Image
    im = load_rgb(src)
    if width and width < im.width:
        scale = float(width) / im.width
        im = im.resize((width, max(1, int(round(im.height * scale)))), Image.LANCZOS)
    rgb = np.asarray(im).astype(np.float32)
    alpha = np.clip((255.0 - rgb.min(axis=2)) / max(float(soft), 1.0), 0.0, 1.0)
    out = Image.fromarray(np.dstack([rgb.astype(np.uint8),
                                     (alpha * 255.0 + 0.5).astype(np.uint8)]), "RGBA")
    if crop:
        box = out.split()[3].getbbox()
        if box:
            out = out.crop(box)
    _save_png(out, dst)
    return out.size


def circle_mark(src: str, dst: str, width: int,
                edge_fill: Optional[Tuple[int, int, int]] = None) -> Tuple[int, int]:
    """「圓形主體內切於正方形、四周白底」的圖 -> 圓形透明 PNG。

    ★ 這類圖不能走 white_to_alpha：白 -> 透明 會把圖案**內部**的白色
      （國徽的太陽、民進黨徽的十字底）一起抽掉。透明範圍是幾何的（內切圓），
      所以改用圓形遮罩，圓內像素原樣保留。

    edge_fill 給圓周是單色時用（國徽 / 國民黨徽都是藍色圓盤）：先把圓外
      填成該色再縮圖，圓周才不會混到白底、在深色底上留一圈白暈。
      edge_fill=None 給圓周顏色會變化的圖（民進黨徽是一圈多色環）：改成
      「先預乘 alpha、縮圖、再反預乘」，圓外那片白縮圖時權重為 0。
    """
    from PIL import Image
    src_img = load_rgb(src)
    w0, h0 = src_img.size
    n0 = float(min(w0, h0))
    arr = np.asarray(src_img).astype(np.float64)

    yy, xx = np.mgrid[0:h0, 0:w0]
    d0 = np.sqrt((xx - (w0 - 1) / 2.0) ** 2 + (yy - (h0 - 1) / 2.0) ** 2)

    if edge_fill is not None:
        arr = arr.copy()
        arr[d0 > n0 / 2.0 - 2.0] = edge_fill      # 含圓周內側 2px 的抗鋸齒殘留
        small = Image.fromarray(arr.astype(np.uint8)).resize((width, width), Image.LANCZOS)
        rgb = np.asarray(small).astype(np.float64)
    else:
        a0 = np.clip(n0 / 2.0 - d0 + 0.5, 0.0, 1.0)
        premul = np.dstack([arr * a0[..., None], a0 * 255.0]).astype(np.uint8)
        small = Image.fromarray(premul, "RGBA").resize((width, width), Image.LANCZOS)
        s = np.asarray(small).astype(np.float64)
        rgb = np.divide(s[..., :3], np.maximum(s[..., 3:4] / 255.0, 1e-6))

    # 圓形 alpha 在輸出尺寸上重做一次（邊界 1px 羽化），圓外全透明
    yy, xx = np.mgrid[0:width, 0:width]
    d = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (width - 1) / 2.0) ** 2)
    alpha = np.clip(width / 2.0 - d + 0.5, 0.0, 1.0)

    out = Image.fromarray(np.dstack([
        np.clip(rgb, 0, 255).astype(np.uint8),
        (alpha * 255.0 + 0.5).astype(np.uint8),
    ]), "RGBA")
    _save_png(out, dst)
    return out.size


def _save_png(img, dst: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    img.save(dst, optimize=True)


# ==========================================================================
# 靜態素材配方表 —— 「哪張圖用哪種透明化方式」
# ==========================================================================
CIRCLE_BLUE = (0, 0, 149)          # 國徽 / 國民黨徽的圓盤藍，圓外填同色
PARTY_WIDTH = 192                  # 看板標籤上的徽章約 32px，192 是 3× 餘量
EMBLEM_WIDTH = 512                 # 國徽圓盤看板上約 135px 直徑，近 2× 餘量
SEAL_WIDTH = 480                   # 市徽頁眉約 140px 高


class WhiteRecipe(NamedTuple):
    """白底 -> 透明。參數意義見 white_to_alpha()。"""
    soft: int = 30
    width: int = 0
    crop: bool = True


class CircleRecipe(NamedTuple):
    """圓形主體內切於正方形 -> 圓外透明。"""
    width: int
    edge_fill: Optional[Tuple[int, int, int]] = None


# 沒列在這裡的靜態素材（map.png / legend.png）維持裸複製：它們在 source/
# 就已經是透明成品（地圖柵格由 NewSolution/Converge_to_map_taipei.py 產生、
# 再過 make_transparent.py），這裡再轉一次只會把 alpha 重算壞掉。
STATIC_RECIPES: Dict[str, object] = {
    # 當選標誌：白底 + 單一正紅。過渡帶拉寬，邊緣才柔
    "mark_elected.png": WhiteRecipe(soft=165),
    # 國徽 / 兩張政黨徽章：圓形主體內切於正方形，走內切圓
    "emblem.png": CircleRecipe(width=EMBLEM_WIDTH, edge_fill=CIRCLE_BLUE),
    "party_kmt.png": CircleRecipe(width=PARTY_WIDTH, edge_fill=CIRCLE_BLUE),
    "party_dpp.png": CircleRecipe(width=PARTY_WIDTH),
    "party_nsc.png": CircleRecipe(width=PARTY_WIDTH),   # 新黨徽：黃圓 +「新」，同民進黨徽做法
    "party_pfp.png": CircleRecipe(width=PARTY_WIDTH),   # 親民黨徽：橘圓 +「親」，同上
    # 市徽：不規則主體 + 大片純白，縮到 SEAL_WIDTH
    "city_seal.png": WhiteRecipe(soft=30, width=SEAL_WIDTH),
}


def recipe_for(filename: str):
    """這個檔名要不要透明化？要的話回傳配方，不要就回 None。"""
    return STATIC_RECIPES.get(filename.replace("\\", "/"))


def build_static(src: str, dst: str, filename: str) -> Optional[str]:
    """依配方把 source/ 的圖處理成透明成品寫進 assets/。

    回傳處理方式的簡短描述（給建置訊息用）；沒有配方時回 None，
    由呼叫端決定要不要裸複製。
    """
    recipe = recipe_for(filename)
    if recipe is None:
        return None
    if isinstance(recipe, CircleRecipe):
        size = circle_mark(src, dst, recipe.width, recipe.edge_fill)
        return "內切圓 %d×%d，圓外透明%s" % (
            size[0], size[1],
            "（填色 #%02x%02x%02x）" % recipe.edge_fill if recipe.edge_fill else "")
    size = white_to_alpha(src, dst, soft=recipe.soft, width=recipe.width,
                          crop=recipe.crop)
    return "白底轉透明 %d×%d" % (size[0], size[1])


# ==========================================================================
# 輔助
# ==========================================================================
def embed(png_path: str) -> str:
    """把圖檔轉成 base64 data URI。"""
    with open(png_path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def png_size(png_path: str):
    """讀 PNG 寬高，不需 Pillow。"""
    with open(png_path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def aspect_warning(png_path: str, tolerance: float = 0.2) -> Optional[str]:
    """地圖寬高比離群警告（對應 JS 端 mapIssue() 的 1.2 閾值）。"""
    size = png_size(png_path)
    if not size:
        return "%s 不是 PNG，無法判斷寬高比" % os.path.basename(png_path)
    w, h = size
    ratio = w / h
    if abs(ratio - 1.0) > tolerance:
        return ("%s 寬高比 %.3f（%d × %d），偏離 1.0 超過 %.0f%%；"
                "地圖通常是接近正方形的版面，請確認是否選錯圖"
                % (os.path.basename(png_path), ratio, w, h, tolerance * 100))
    return None
