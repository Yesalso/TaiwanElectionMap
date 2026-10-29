# -*- coding: utf-8 -*-
"""national_map.py —— 2022 全國縣市長看板（政黨版圖）的統一配置表。

★ 唯一真值來源：兩張全國地圖的來源路徑、去底參數、裁切規則、圖例配色、
  政黨對照（簡體全稱 → 繁體全稱／縮寫／引擎政黨 key）、版面常數。
  build_national_assets.py（素材）與 _gen_national.py（建看板）都讀這裡。

這一場的「候選人」是**政黨**：candidates[].votes = 全台總得票、
seats = 拿下的縣市長席次。資料全部來自
`Mayors/2022NineInOne/2022县市长选举简报.md`（該檔以 Wikipedia.txt 為底編成）。
"""
import ast
import os

# ---------------------------------------------------------------- 路徑
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ROOT = board/（與 county_map.py 同一個定位方式）
BASE = os.path.dirname(ROOT)                     # Mayors/2022NineInOne

MAP_COUNTY_SRC = os.path.join(BASE, "map", "2022县市.png")
MAP_TOWN_SRC = os.path.join(BASE, "map", "2022縣市長選舉_鄉鎮市區得票率.png")
BRIEF_MD = os.path.join(BASE, "2022县市长选举简报.md")
WIKI_TXT = os.path.join(BASE, "Wikipedia.txt")

OUT_ASSETS = os.path.join(ROOT, "dist", "assets", "national")
# 地圖成品（邏輯名 assets/map.png / assets/map2.png 由 board.files.js 指過來）
OUT_COUNTY = os.path.join(OUT_ASSETS, "county.png")
OUT_TOWN = os.path.join(OUT_ASSETS, "town.png")
OUT_LEGEND = os.path.join(OUT_ASSETS, "legend.png")
OUT_META = os.path.join(OUT_ASSETS, "maps.json")   # 成品尺寸／裁切框，給建看板用

# 字型：與看板同一支（源石黑體 TW Heavy）；找不到才退回微軟正黑粗體
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]

# ---------------------------------------------------------------- 地圖去底
# 兩張來源圖都是「不透明平面底色」的成品圖（不是透明 PNG）：
#   縣市級 2022县市.png        底色 (120,120,120) 淺灰
#   鄉鎮級 …得票率.png          底色 (50,50,50)    #323232（繪圖腳本的 CANVAS_COLOR）
MAP_COUNTY_BG = (120, 120, 120)
MAP_TOWN_BG = (50, 50, 50)
BG_TOL = 8            # 與底色三通道差都 <= 8 視為底色（連抗鋸齒暈邊一起去掉）

# 左上角「中國大陸輪廓」不是選舉資料，留著會變成一大塊雜訊 → 整區挖掉。
# 範圍是來源圖像素座標（兩張圖同畫布同範圍）；918 是它的下緣（含海界線），
# 1400 讓開台灣本島（本島最西約 x1450）。三張放大框從 y≈925 起，不會被切到。
CHINA_BOX = (0, 0, 1400, 918)

# 界線：來源圖的縣市界／鄉鎮界是**純黑 3–5px 線**（繪圖腳本用純黑堤壩再洪水填色）。
# 看板底是深色，黑線看不見 → 轉白並加粗一級（來源 2753px 寬 → 看板 678px，縮 4 倍，
# 不先加粗的話細線會被縮沒）。
LINE_MAX = 12         # max(R,G,B) <= 12 視為黑線（來源只有純黑與 1–3 的抗鋸齒）
LINE_DILATE = 1       # 3×3 最大值濾波次數（1 次＝線寬 +2px）
LINE_COLOR = (255, 255, 255)

# 裁切：用「每列／每行墨跡像素數 > BBOX_MIN_INK」的範圍求外框，
# 避免右上角的零星小島點把畫布拉到整張來源圖。兩張圖共用同一個裁切框
# （同畫布同範圍 → 兩張圖擺在一起時比例與位置完全一致）。
BBOX_MIN_INK = 40
CROP_PAD = 8

# ---------------------------------------------------------------- 版面色階
# 地圖上的實際填色來自 Precident/color.txt（35% 起、5% 一階，深＝得票率高）。
# 圖例**直接讀這個檔**，畫出四家（國民黨／民進黨／民眾黨／無黨籍）各自的色階，
# 除黨名外不加任何文字。
COLOR_TXT = r"D:\Windows\TaiwanElection\Precident\color.txt"
# color.txt 的組別索引（由上而下）：0 無黨籍／1 國民黨／2 民進黨／3 新黨／4 宋楚瑜／5 民眾黨
RAMP_GROUP = {"中國國民黨": 1, "民主進步黨": 2, "台灣民眾黨": 5, "無黨籍": 0}
# 圖例顯示順序（使用者指定：國民黨 → 民進黨 → 民眾黨 → 無黨籍）
LEGEND_PARTIES = ["中國國民黨", "民主進步黨", "台灣民眾黨", "無黨籍"]


def load_ramps():
    """讀 color.txt（Python 串列字面）→ {政黨: [(上限%, "#RRGGBB"), …]}。"""
    with open(COLOR_TXT, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    stops = ast.literal_eval("\n".join(lines).split("=", 1)[1])
    return {p: stops[RAMP_GROUP[p]] for p in LEGEND_PARTIES}


def all_ramp_colors():
    """color.txt 裡**所有組**的階色（＝地圖上合法的填色），回傳 {(r,g,b), …}。

    ★ 2026-10-29（使用者回報「苗栗縣有一塊 #333333 被渲染成別的顏色」）：
      去底原本只憑「與底色三通道差 ≤ BG_TOL」，而鄉鎮圖的底色是 #323232，
      無黨籍 75% 那一階 **#333333 只差 1** → 被當成底色挖成透明，露出一大片街景。
      所以去底要先把「資料填色」保護起來：這些顏色再接近底色也不是背景。
      這裡不只用圖例那四家 —— 地圖上可能出現 color.txt 任何一組的顏色。
    """
    with open(COLOR_TXT, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    stops = ast.literal_eval("\n".join(lines).split("=", 1)[1])
    out = set()
    for group in stops:
        for _, hexv in group:
            h = hexv.lstrip("#")
            out.add((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
    return out

# ---------------------------------------------------------------- 政黨對照
# 簡報 md 的政黨名（簡體）→ 繁體全稱
PARTY_S2T = {
    "中国国民党": "中國國民黨",
    "民主进步党": "民主進步黨",
    "台湾民众党": "台灣民眾黨",
    "无党籍": "無黨籍",
    "时代力量": "時代力量",
    "其他政党": "其他政黨",
}

# 「其他政黨」這一列的明細（簡報 2.1 的註腳 ‡ 才有，逐黨列出）：
# 簡體 → 繁體。★ 2026-10-29（使用者要求）：其他政黨不再合併成一列，
# 而是照台北市底部的做法**逐黨列名＋票數**（清單格），所以需要這張對照表。
# 表裡沒收錄的新政黨會直接沿用簡體名並在建置 log 警告 —— 不會讓整條管線掛掉。
OTHER_PARTY_S2T = {
    "台湾动物保护党": "台灣動物保護黨",
    "台湾维新": "台灣維新",
    "天一党": "天一黨",
    "共和党": "共和黨",
    "台澎国际法法理建国党": "台澎國際法法理建國黨",
    "龙党": "龍黨",
}

# 簡報「2.4 看板采用口径」表的專用名稱對照：那張表用的是中選會的完整標籤
# （例如「无党籍或未经政党推荐」），看板上要顯示成短名。
BOARD_S2T = {
    "无党籍或未经政党推荐": "無黨籍",
    "台澎党": "台澎黨",
}

# 繁體全稱 → (引擎 partyShort, 英文全稱)
PARTY_SHORT = {
    "中國國民黨": ("KMT", "Kuomintang"),
    "民主進步黨": ("DPP", "Democratic Progressive Party"),
    "台灣民眾黨": ("TPP", "Taiwan People's Party"),
    "無黨籍": ("IND", "Independent"),
    "時代力量": ("NPP", "New Power Party"),
    "其他政黨": ("OTH", "Others"),
}

# 沒有預設政黨色／沒有黨徽素材的政黨，在這裡給主色（寫成 candidates[].color，
# 引擎用 Theme.fromColor 推導亮暗階）。OTH 也不能落到 ind 灰，否則會跟無黨籍同色。
PARTY_COLOR = {
    "其他政黨": "#5f6779",
}

# 黨主席（2022-11-26 投票當下在任者）。主卡的大字姓名印的是黨主席，
# 黨名留在政黨標籤（chip）上 —— 與使用者的參考看板（黨名 tab + 領袖大名）一致。
# 無黨籍／其他政黨沒有單一負責人，不列 → 主卡／小卡照舊印黨名。
PARTY_LEADER = {
    "中國國民黨": "朱立倫",
    "民主進步黨": "蔡英文",
    "台灣民眾黨": "柯文哲",
    "時代力量": "陳椒華",
}

# 「其他政黨」在清單格裡最多列幾列。超過就退回單列「其他政黨」
# （清單格高度上限 268px、每列下限 22px → 實際可放約 10 列；這裡留餘裕）
OTHERS_MAX_ROWS = 8

# ---------------------------------------------------------------- 版面常數
# 看板座標（2560×1440）。兩張地圖的框由「成品寬高比」反算（框＝圖），
# 高度吃满頁眉下緣到小卡帶上緣這一段；左右置中於兩張主卡之間。
#   y 248 = 頁眉線 236 + 12px 淨空（成品已裁到墨跡，地圖墨跡就從框頂開始，
#   所以不能再讓它鑽到頁眉底下）；下緣 1102 = 第 3 名高卡上緣。
MAP_Y = 248
MAP_H = 854                 # 1102 − 248
MAP_ENV_X0 = 560            # 可用區左界（左主卡色卡右緣 536 + 24）
MAP_ENV_X1 = 2004           # 可用區右界（右主卡色卡左緣 2024 − 20）
MAP_GAP = 36                # 兩張圖之間
# ★ 2026-10-29（使用者要求）：地圖**不加底板**，直接貼在看板底色／街景上
#   （第一版鋪過 rgba(6,11,28,0.88) 的暗板，已移除）。

# 圖例：放在頁眉右側（四行數據右邊、席次說明左邊），與地圖框不重疊。
# 內容＝四家各自的色階（讀 color.txt），除黨名外沒有任何文字。
LEGEND_BOX = {"x": 1600, "y": 62, "w": 480, "h": 118}
LEGEND_SCALE = 2            # 圖例 PNG 以 2× 繪製（960×236），contain 後仍清楚
# 圖例最上方那條「比例尺」：每 2 階標一次 = 每 10 個百分點（35／45／55／65…）。
# color.txt 的階距是 5%，所以 2 階剛好 10%。
LEGEND_TICK_STEP = 2


def font_path():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError("找不到可用的中文字型：%s" % FONT_CANDIDATES)
