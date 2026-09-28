# -*- coding: utf-8 -*-
"""
build_assets.py
===============
把「使用者提供的素材圖」處理成看板可以直接吃的圖檔，並內嵌成 base64 的 JS。

去白底這件事統一交給 tools/white_to_alpha.py 這個通用工具做，
本檔只負責「這個專案要怎麼用」：選素材、下參數、寫出 data/local-assets.js。

處理三張圖：
  1. Share/Elect.png                                  當選標誌（白底 -> 透明）
  2. 2014NewTaipei/新北市市徽.png                      頁眉左上角市徽（白底 -> 透明）
  3. 村里得票率地圖 —— 交給 tools/build_vote_map.py 做（本檔只負責呼叫）：
                                                        擦掉海報自帶的標題／圖例
                                                        -> 依 alpha 裁齊
                                                        -> 預乘 alpha 面積平均縮到 2400 寬

  地圖的處理順序與寬度都集中在 build_vote_map.py（換版面或換素材時改那支），
  本檔只負責「整包重建」：三張圖都做一次，再一起寫出 data/local-assets.js。
  單獨只想重出地圖時，直接跑：
    python tools/build_vote_map.py [--embed]

  地圖來源刻意用「已經去背過的」透明版本：transparent.py 只把 alpha 設 0、
  不動 RGB，而 white_to_alpha.load_rgb() 遇到帶 alpha 的輸入會先合成回白底，
  所以取到的 RGB 與未去背的原圖完全相同，管線結果一致；
  但來源檔名明確代表「這張透明圖就是看板在用的那張」。

輸出：
  Share/assets/elected_mark.png   去背後（透明）的當選標誌
  Share/assets/city_seal.png      去背後（透明）的新北市市徽（480 寬）
  Share/assets/vote_map.png       只剩地圖本體、2400 寬的透明得票率地圖
  Share/assets/*_preview.png      貼在深色底上的預覽，方便肉眼檢查
  Share/data/local-assets.js      window.NT_ASSETS = {electedMark, voteMap}

為什麼要內嵌 base64：
  看板以 canvas 繪製，若圖片以相對路徑載入，在 file:// 下會污染畫布，
  toBlob() 會拋 SecurityError；內嵌 data URI 則不會。

  但內嵌不方便換圖，所以現在的分工是：
    - 得票率地圖：看板優先讀 Share/assets/vote_map.png（換檔即生效，不用重跑本檔）；
      只有在載入失敗、或該圖會污染畫布（file:// 開啟）時，才退回這裡內嵌的版本。
      退回邏輯在 js/slide.js 的 _loadVoteMap()。
    - 當選標誌：仍然只用內嵌版本（檔案小、很少換）。
    - 新北市市徽：看板讀 Share/assets/city_seal.png，讀不到就退回預設圈勾方塊，
      不做內嵌備援（見 js/slide.js 的 _loadCitySeal）。
  因此本檔輸出的 local-assets.js 同時是「資料來源」與「file:// 的後備」。

用法：
  python tools/build_assets.py

需要單獨處理別的白底圖時，直接用工具本身：
  python tools/white_to_alpha.py -i 圖.png -o 圖_alpha.png --trim --width 2400
"""

import base64
import os
import sys

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
# 市徽原圖放在專案根目錄的素材夾（與候選人照片、黨徽同一批使用者提供的圖）
SRC_SEAL = os.path.join(PROJECT, "2014NewTaipei", "新北市市徽.png")
# 地圖的來源、輸出路徑都在 build_vote_map.py（那裡還有寬度與擦除區的設定）

OUT_MARK = os.path.join(ASSET_DIR, "elected_mark.png")
OUT_SEAL = os.path.join(ASSET_DIR, "city_seal.png")
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


def write_js(mark_uri, map_uri, seal_uri):
    js = ("/* 自動產生，請勿手改。來源：tools/build_assets.py */\n"
          "/* 使用者提供的素材（當選標誌、村里得票率地圖、新北市市徽）以 base64 內嵌。\n"
          "   正式來源是 assets/ 底下的實體檔；這份不只是備份，而是 file:// 開啟時的\n"
          "   必要來源：file:// 下只要把本機圖檔畫上 canvas，canvas 就會被汙染成\n"
          "   「畫得出來、讀不回去」，縮圖的 toDataURL 與匯出的 toBlob 都會拋\n"
          "   SecurityError。js/slide.js 會在 file:// 下自動改用這三份內嵌副本。 */\n"
          "window.NT_ASSETS = {\n"
          '  "electedMark": "' + mark_uri + '",\n'
          '  "voteMap": "' + map_uri + '",\n'
          '  "citySeal": "' + seal_uri + '"\n'
          "};\n")
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
    build_vote_map()
    write_js(data_uri(OUT_MARK), data_uri(OUT_MAP), data_uri(OUT_SEAL))
    print("完成。")


if __name__ == "__main__":
    main()
