# -*- coding: utf-8 -*-
"""
build_assets.py
===============
把「使用者提供的素材圖」處理成看板可以直接吃的圖檔，並內嵌成 base64 的 JS。

去白底這件事統一交給 tools/white_to_alpha.py 這個通用工具做，
本檔只負責「這個專案要怎麼用」：選素材、下參數、寫出 data/local-assets.js。

處理七張圖：
  1. Share/Elect.png                                  當選標誌（白底 -> 透明）
  2. 2014NewTaipei/新北市市徽.png                      頁眉左上角市徽（白底 -> 透明）
  3. 2014NewTaipei/国徽.png                            日期底色的圓徽（白底 -> 只留內切圓）
  4. 2014NewTaipei/中国国民党.png                      國民黨徽章（只留內切圓）
  5. 2014NewTaipei/民主进步党.png                      民進黨徽章（只留內切圓）
  6. 2014NewTaipei/map/图例.png                        得票率圖例（已透明 -> 依 alpha 裁齊
                                                        -> 縮到 LEGEND_WIDTH 寬
                                                        -> 切掉頂端標題／人名，只留
                                                           九階色塊；深色文字原文保留，
                                                           靠看板上的淺色底板撐對比）
  7. 村里得票率地圖 —— 交給 tools/build_vote_map.py 做（本檔只負責呼叫）：
                                                        擦掉海報自帶的標題／圖例
                                                        -> 依 alpha 裁齊
                                                        -> 預乘 alpha 面積平均縮到 2400 寬

  地圖的處理順序與寬度都集中在 build_vote_map.py（換版面或換素材時改那支），
  本檔只負責「整包重建」：六張圖都做一次，再一起寫出 data/local-assets.js。
  單獨只想重出地圖時，直接跑：
    python tools/build_vote_map.py [--embed]

  地圖來源刻意用「已經去背過的」透明版本：transparent.py 只把 alpha 設 0、
  不動 RGB，而 white_to_alpha.load_rgb() 遇到帶 alpha 的輸入會先合成回白底，
  所以取到的 RGB 與未去背的原圖完全相同，管線結果一致；
  但來源檔名明確代表「這張透明圖就是看板在用的那張」。

輸出：
  Share/assets/elected_mark.png   去背後（透明）的當選標誌
  Share/assets/city_seal.png      去背後（透明）的新北市市徽（480 寬）
  Share/assets/emblem.png         只留內切圓的圓徽（512 寬，圓外透明）
  Share/assets/party_kmt.png      只留內切圓的國民黨徽章（192 寬，圓外透明）
  Share/assets/party_dpp.png      只留內切圓的民進黨徽章（192 寬，圓外透明）
  Share/assets/legend.png         裁到內容、1100 寬、切掉頂端標題的透明得票率圖例
                                  （只剩「色塊 + 級距」兩欄）
  Share/assets/vote_map.png       只剩地圖本體、2400 寬的透明得票率地圖
  Share/assets/*_preview.png      貼在深色底上的預覽，方便肉眼檢查
  Share/data/local-assets.js      window.NT_ASSETS = {
                                    electedMark, voteMap, citySeal, emblem, partyKmt,
                                    partyDpp, legend }

為什麼要內嵌 base64：
  看板以 canvas 繪製，若圖片以相對路徑載入，在 file:// 下會污染畫布，
  toBlob() 會拋 SecurityError；內嵌 data URI 則不會。

  但內嵌不方便換圖，所以現在的分工是：
    - 得票率地圖：看板優先讀 Share/assets/vote_map.png（換檔即生效，不用重跑本檔）；
      只有在載入失敗、或該圖會污染畫布（file:// 開啟）時，才退回這裡內嵌的版本。
      退回邏輯在 js/slide.js 的 _loadVoteMap()。
    - 當選標誌：仍然只用內嵌版本（檔案小、很少換）。
    - 新北市市徽、日期圓徽、兩張政黨徽章：看板優先讀 assets/ 底下的實體檔，
      file:// 下改用內嵌版本（js/slide.js 的 _loadCitySeal / _loadEmblem /
      _loadPartyMarks），兩邊都讀不到才退回預設畫法。
  因此本檔輸出的 local-assets.js 同時是「資料來源」與「file:// 的後備」。

用法：
  python tools/build_assets.py

需要單獨處理別的白底圖時，直接用工具本身：
  python tools/white_to_alpha.py -i 圖.png -o 圖_alpha.png --trim --width 2400
"""

import base64
import os
import sys

import numpy as np
from PIL import Image

# 讓 `python tools/build_assets.py` 能直接 import 同目錄的工具
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import white_to_alpha as w2a                                     # noqa: E402
import build_vote_map as bvm                                     # noqa: E402

# --------------------------------------------------------------------------
# 路徑
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SHARE = os.path.dirname(HERE)
PROJECT = os.path.dirname(SHARE)
ASSET_DIR = os.path.join(SHARE, "assets")
DATA_DIR = os.path.join(SHARE, "data")

SRC_MARK = os.path.join(SHARE, "Elect.png")
# 市徽、圓徽、黨徽原圖放在專案根目錄的素材夾（與候選人照片同一批使用者提供的圖）
SRC_SEAL = os.path.join(PROJECT, "2014NewTaipei", "新北市市徽.png")
SRC_EMBLEM = os.path.join(PROJECT, "2014NewTaipei", "国徽.png")
# 兩張政黨徽章：候選人照片卡下方那條政黨標籤，字左邊的小圓徽。
# key 要與 js/core/theme.js 的政黨 key（kmt / dpp）一致。
SRC_PARTY = {
    "kmt": os.path.join(PROJECT, "2014NewTaipei", "中国国民党.png"),
    "dpp": os.path.join(PROJECT, "2014NewTaipei", "民主进步党.png"),
}
# 得票率圖例：與得票率地圖同一批素材（海報右上角那塊），已經去背成透明 PNG。
# 深藍色文字原本是靠海報的白底才看得見，看板上要靠 js/render/layers.js 的
# LegendLayer 鋪一塊淺色底板撐對比（見 Layout.legend）。
SRC_LEGEND = os.path.join(PROJECT, "2014NewTaipei", "map", "图例.png")
# 地圖的來源、輸出路徑都在 build_vote_map.py（那裡還有寬度與擦除區的設定）

OUT_MARK = os.path.join(ASSET_DIR, "elected_mark.png")
OUT_SEAL = os.path.join(ASSET_DIR, "city_seal.png")
OUT_EMBLEM = os.path.join(ASSET_DIR, "emblem.png")
OUT_PARTY = {
    "kmt": os.path.join(ASSET_DIR, "party_kmt.png"),
    "dpp": os.path.join(ASSET_DIR, "party_dpp.png"),
}
OUT_LEGEND = os.path.join(ASSET_DIR, "legend.png")
OUT_MAP = os.path.join(ASSET_DIR, "vote_map.png")
OUT_JS = os.path.join(DATA_DIR, "local-assets.js")

# 標題／圖例已在地圖預處理階段被擦掉（build_vote_map.py），不再需要改亮色

# 參數（沿用先前已驗證過的數值）
# 標誌：白底 255 完全透明，wn<=90 為實色 -> tol=255, soft=165
#       標誌是鮮紅單色，不做反預乘才不會把紅色推爆
MARK_TOL, MARK_SOFT = 255, 165
# 市徽：純白底，主體含亮黃／亮灰。用 min 通道判斷白度，soft 放寬讓邊緣柔順；
#       主體是平面色塊（不是單色），保留反預乘才不會在深色底上留白暈。
SEAL_TOL, SEAL_SOFT = 250, 30
SEAL_WIDTH = 480           # 頁眉只用到 ~140px 高，480 寬已足夠 2× 匯出的銳利度
PREVIEW_BG = "#0d1730"    # 預覽底色，接近看板背景

# 圓徽（日期底色）：原圖 1280×1280、白底、藍色圓盤剛好是正方形的內切圓。
# 看板上圓盤直徑 ~135px，2× 匯出用到 270px，512 有 1.9× 餘量。
EMBLEM_WIDTH = 512
EMBLEM_BLUE = (0, 0, 149)  # 原圖圓盤的實色；圓外用同一個藍填掉，縮圖才不會混出白暈

# 政黨徽章：看板上的徽章邊長約 0.42 × 標籤高度（76px）≈ 32px，
# 2× 匯出用到 64px，192 有 3× 餘量，放大到 3× 交付也夠。
PARTY_WIDTH = 192
PARTY_BLUE = (0, 0, 149)   # 國民黨徽章是藍色圓盤，圓外填藍（同 EMBLEM_BLUE 的理由）

# 得票率圖例：原圖 2867×2541、內容外框 2633×2120（其餘是透明邊）。
# 看板上圖例框約 500 寬（見 Layout.legend），2× 匯出用到 ~1000px，
# 1100 寬留約 10% 餘量；縮得太小會讓「≥85%」這種小字糊掉。
LEGEND_WIDTH = 1100

# ★ 只保留「色塊 + 級距」那兩欄，上面的標題與人名整段切掉。
#   實測內容（已裁邊、縮到 1100 寬後，共 1100 × 886）的分帶：
#     0 – 54    標題「第二屆新北市市長選舉」
#     129 – 184 副標「在各村（里）得票領先之候選人得票比例圖」
#     255 – 301 人名「朱立倫 / 游錫堃」
#     363 – 885 九列色塊（第 1 列 363–407、列距 60，最底列切齊 885）
#   切點 = 第一列色塊上緣減 20px 的呼吸量 = 343：
#   落在人名（收在 301）與第一列（從 363 起）之間，標題層級一刀切乾淨，
#   九階色塊連同「45~50%」那一列的第一排文字都完整保留。
LEGEND_KEEP_TOP = 343


# --------------------------------------------------------------------------
# 1. 當選標誌：白底 -> 透明
# --------------------------------------------------------------------------
def build_elected_mark():
    """標誌是「白底 + 單一紅色」的平面向量圖。

    以每像素的最小通道值當作「白度」：純白 -> 透明，正紅 -> 不透明，
    邊緣落在過渡帶，自然抗鋸齒。RGB 保持原色（不反預乘），
    讓印記在深色背景上仍是原本的正紅。
    """
    return w2a.process(SRC_MARK, OUT_MARK, tol=MARK_TOL, soft=MARK_SOFT,
                       mode="min", unpremultiply=False, preview=PREVIEW_BG)


# --------------------------------------------------------------------------
# 1b. 新北市市徽：白底 -> 透明（頁眉左上角）
# --------------------------------------------------------------------------
def build_city_seal():
    """市徽原圖是 1920 × 1280、四周大片純白，主體（彩色心型 + 底下「新北市」）居中。

    先裁掉白邊再縮到 SEAL_WIDTH 寬，讓輸出檔只剩主體、比例也乾淨；
    之後看板只要指定「高度」，寬度自然依比例得出（見 Layout.header.seal）。
    """
    return w2a.process(SRC_SEAL, OUT_SEAL, tol=SEAL_TOL, soft=SEAL_SOFT,
                       mode="min", width=SEAL_WIDTH, trim=True,
                       preview=PREVIEW_BG)


# --------------------------------------------------------------------------
# 1c. 「圓形主體 + 白底」的通用處理：只留內切圓，圓外透明
# --------------------------------------------------------------------------
def circle_asset(src_path, out_path, width, edge_fill=None, preview_bg=PREVIEW_BG):
    """把「圓形主體內切於正方形、四周白底」的圖裁成圓形透明 PNG。

    ★ 這類圖不能走 white_to_alpha.py：那條管線是「白 -> 透明」，
      但圖案**內部**的白色也是圖案的一部分（圓徽的太陽、民進黨徽的十字底色），
      會被一起抽掉。透明範圍是「幾何」的（內切圓），所以改用圓形遮罩，
      圓內像素原樣保留。

    縮圖方式依圓周顏色分兩條路（edge_fill 決定）：

    edge_fill 給定顏色 —— 圓周是單一顏色時用（國徽／國民黨徽都是藍色圓盤）。
      先把圓外（含圓周內側 2px 的殘留抗鋸齒）一律填成該色，**再**縮圖。
      這樣連原圖圓周上那圈「實色混白」的抗鋸齒都會被覆蓋掉，
      縮圖後邊緣是乾淨的實色，深色底上不會有一圈白暈。

    edge_fill 為 None —— 圓周顏色會變化的圖用（民進黨徽是一圈多色環，
      沒有單一顏色可以填）。改成「先預乘 alpha、再縮圖、再反預乘」：
      圓外的大片白在縮圖時權重為 0，不會被平均進圓周；
      圓內顏色則因為反預乘而完整還原。
    """
    src = Image.open(src_path).convert("RGB")
    w0, h0 = src.size
    n0 = float(min(w0, h0))
    arr = np.asarray(src).astype(np.float64)

    yy, xx = np.mgrid[0:h0, 0:w0]
    d0 = np.sqrt((xx - (w0 - 1) / 2.0) ** 2 + (yy - (h0 - 1) / 2.0) ** 2)

    if edge_fill is not None:
        arr = arr.copy()
        arr[d0 > n0 / 2.0 - 2.0] = edge_fill
        small = Image.fromarray(arr.astype(np.uint8)).resize((width, width), Image.LANCZOS)
        rgb = np.asarray(small).astype(np.float64)
    else:
        a0 = np.clip(n0 / 2.0 - d0 + 0.5, 0.0, 1.0)
        premul = np.dstack([arr * a0[..., None], a0 * 255.0]).astype(np.uint8)
        small = Image.fromarray(premul, "RGBA").resize((width, width), Image.LANCZOS)
        s = np.asarray(small).astype(np.float64)
        a = s[..., 3:4] / 255.0
        rgb = np.divide(s[..., :3], np.maximum(a, 1e-6))     # 反預乘，還原圓內顏色

    # 圓形 alpha 在「輸出尺寸」上重做一次（邊界 1px 羽化），圓外全透明
    yy, xx = np.mgrid[0:width, 0:width]
    d = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (width - 1) / 2.0) ** 2)
    alpha = np.clip(width / 2.0 - d + 0.5, 0.0, 1.0)

    out = Image.fromarray(np.dstack([
        np.clip(rgb, 0, 255).astype(np.uint8),
        (alpha * 255.0 + 0.5).astype(np.uint8)
    ]), "RGBA")
    os.makedirs(ASSET_DIR, exist_ok=True)
    out.save(out_path, optimize=True)
    print("  輸出   %-46s %s  (%.0f KB)" % (
        os.path.basename(out_path), out.size, os.path.getsize(out_path) / 1024.0))

    pv = w2a.make_preview(out, preview_bg)
    pv.save(os.path.splitext(out_path)[0] + "_preview.png")
    return out


def build_emblem():
    """日期底色的圓徽：國徽原圖 1280 × 1280、白底，藍色圓盤剛好是內切圓。"""
    return circle_asset(SRC_EMBLEM, OUT_EMBLEM, EMBLEM_WIDTH, edge_fill=EMBLEM_BLUE)


# --------------------------------------------------------------------------
# 1d. 政黨徽章：只留內切圓（候選人卡片下方政黨標籤用）
# --------------------------------------------------------------------------
def build_party_marks():
    """兩張政黨徽章原圖都是 1280 × 1280 上下、白底、圓形主體內切於正方形。

    差別在圓周顏色，因此縮圖方式不同：
      - 國民黨徽（青天白日）：藍色圓盤 → edge_fill 填藍，邊緣乾淨實色
      - 民進黨徽：外圈是「民主進步黨 / DEMOCRATIC PROGRESSIVE PARTY」的多色環，
        沒有單一顏色可填 → 走預乘 alpha，避免圓外的白被平均進圓周
    輸出尺寸相同（PARTY_WIDTH），看板把它畫成正方形即可（圓外已透明）。
    """
    outs = {}
    for key, src in SRC_PARTY.items():
        fill = PARTY_BLUE if key == "kmt" else None
        outs[key] = circle_asset(src, OUT_PARTY[key], PARTY_WIDTH, edge_fill=fill)
    return outs


# --------------------------------------------------------------------------
# 1e. 得票率圖例：已透明 -> 依 alpha 裁齊 -> 縮到 LEGEND_WIDTH 寬
# --------------------------------------------------------------------------
def build_legend():
    """得票率圖例（2014NewTaipei/map/图例.png）。

    來源已經是透明 PNG（92.9% 的像素 alpha = 0），圓角色塊與深藍文字是主體，
    所以**不能**再走 white_to_alpha.py：「白 -> 透明」會把色塊裡的亮色一起抽掉，
    而且來源本來就有 alpha，直接處理即可。

    這裡只做三件事：
      1. 依 alpha 裁掉四周的透明邊（原圖四周各留了 100px 上下的空白）
      2. 縮到 LEGEND_WIDTH 寬，縮圖用 LANCZOS：主體是實色塊 + 文字，
         不是 0/255 的硬遮罩，不會有 build_vote_map 那種振盪問題
      3. ★ 從 LEGEND_KEEP_TOP 切掉上半段的標題／副標／人名，
         只留「色塊 + 級距」——那兩行字是海報的標題層級，
         看板自己用底板小標題（Layout.legend.title）說明就夠了，
         貼上去只會跟看板的大標題打架。

    ★ 文字顏色原樣保留。圖例是深藍近黑的字，貼在深色看板上會看不見，
      所以對比是由「看板上的淺色底板」負責（js/render/layers.js 的
      LegendLayer 先鋪底色再貼這張圖），不是改這張圖。
    """
    src = Image.open(SRC_LEGEND).convert("RGBA")
    w0, h0 = src.size

    # 依 alpha 裁掉外圍透明區
    box = src.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox()
    im = src.crop(box) if box else src

    # 縮到目標寬度（用 LANCZOS，文字邊緣比 BOX 銳利）
    if LEGEND_WIDTH and im.width > LEGEND_WIDTH:
        h = max(1, int(round(im.height * LEGEND_WIDTH / float(im.width))))
        im = im.resize((LEGEND_WIDTH, h), Image.LANCZOS)

    # 切掉上半段的標題／副標／人名，只留九階色塊圖例
    top = max(0, min(LEGEND_KEEP_TOP, im.height - 1))
    im = im.crop((0, top, im.width, im.height))
    # 切完再依 alpha 收一次邊，免得留下透明帶（也讓檔名對應的框更貼合）
    box2 = im.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox()
    if box2:
        im = im.crop(box2)

    os.makedirs(ASSET_DIR, exist_ok=True)
    im.save(OUT_LEGEND, optimize=True)
    print("  裁邊   %-46s %s -> %s (切掉頂端 %d px 標題)" % (
        os.path.basename(SRC_LEGEND), "%d × %d" % (w0, h0),
        "%d × %d" % im.size, top))
    print("  輸出   %-46s %s  (%.0f KB)" % (
        os.path.basename(OUT_LEGEND), im.size, os.path.getsize(OUT_LEGEND) / 1024.0))

    pv = w2a.make_preview(im, PREVIEW_BG)
    pv.save(os.path.splitext(OUT_LEGEND)[0] + "_preview.png")
    return im


# --------------------------------------------------------------------------
# 2. 得票率地圖：交給 build_vote_map.py（擦標題／圖例 -> 依 alpha 裁齊 -> 預乘面積平均縮圖）
# --------------------------------------------------------------------------
def build_vote_map():
    """原圖 9824×7365、七成是純白，右上角還有海報自帶的標題／圖例。

    這些以前是在瀏覽器裡用 canvas 擦的（Layout.map.crop），現在改在這裡一次做完，
    輸出的 assets/vote_map.png 就是「只剩地圖本體」的乾淨素材，載入時不必再處理。
    寬度、擦除區等參數都在 build_vote_map.py 那裡。
    """
    return bvm.build(src=bvm.SRC_MAP, out=OUT_MAP, preview=PREVIEW_BG)


# --------------------------------------------------------------------------
def data_uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def write_js(assets):
    """把素材寫成 data/local-assets.js 的內嵌 base64。

    assets 是 {欄位名: data URI}，欄位名必須與 js/slide.js 讀的一致：
      當選標誌 (electedMark)、地圖 (voteMap)、市徽 (citySeal)、圓徽 (emblem)、
      兩張政黨徽章 (partyKmt / partyDpp，對應 Layout 的政黨 key kmt / dpp)、
      得票率圖例 (legend，對應 Layout.legend)。
    """
    lines = "".join('  "%s": "%s"%s\n' % (k, assets[k], "," if i < len(assets) - 1 else "")
                    for i, k in enumerate(assets))
    js = ("/* 自動產生，請勿手改。來源：tools/build_assets.py */\n"
          "/* 使用者提供的素材（當選標誌、村里得票率地圖、新北市市徽、日期圓徽、\n"
          "   兩張政黨徽章、得票率圖例）以 base64 內嵌。正式來源是 assets/ 底下的\n"
          "   實體檔；這份不只是備份，而是 file:// 開啟時的必要來源：file:// 下只要把本機\n"
          "   圖檔畫上 canvas，canvas 就會被汙染成「畫得出來、讀不回去」，縮圖的\n"
          "   toDataURL 與匯出的 toBlob 都會拋 SecurityError。js/slide.js 會在\n"
          "   file:// 下自動改用這幾份內嵌副本。 */\n"
          "window.NT_ASSETS = {\n" + lines + "};\n")
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    print("  %-32s %.0f KB" % (os.path.basename(OUT_JS),
                               os.path.getsize(OUT_JS) / 1024.0))


def main():
    os.makedirs(ASSET_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    print("產生素材：")
    build_elected_mark()
    build_city_seal()
    build_emblem()
    build_party_marks()
    build_legend()
    build_vote_map()
    write_js({
        "electedMark": data_uri(OUT_MARK),
        "voteMap": data_uri(OUT_MAP),
        "citySeal": data_uri(OUT_SEAL),
        "emblem": data_uri(OUT_EMBLEM),
        "partyKmt": data_uri(OUT_PARTY["kmt"]),
        "partyDpp": data_uri(OUT_PARTY["dpp"]),
        "legend": data_uri(OUT_LEGEND)
    })
    print("完成。")


if __name__ == "__main__":
    main()
