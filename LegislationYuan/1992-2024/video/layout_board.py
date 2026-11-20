# -*- coding: utf-8 -*-
"""
layout_board.py — 立法院選舉看板「版式唯一真值」

設計座標 2560×1440，輸出 3840×2160（S=1.5）。
任何要改版面的人只改這支檔案；`blank_board.py`（骨架圖）與未來的渲染器都只讀這裡。

★ 頁眉沿用 Mayors/2022NineInOne 縣市長看板的那一套：
  國旗白卡 → 主標題 → 年份圓盤（年 ＋ 月日）→ 席次統計卡（本場新增）。
  頁眉高 236 ＝ 縣市長看板 `layout.js` 的 `header.h`，兩套剪在一起時是同一條線。

★ 地圖區：主圖（本島）＋ 輔圖（離島小圖：金門／馬祖／澎湖），
  素材對應 `video/1992.png` 那一類圖（3203×4404，本島 ＋ 左欄三格離島）。
  主圖 600×1084（0.55）與輔圖 280×340（0.82）比例不同、縮放不同。

版式骨架（設計像素）
    頁眉左半    y   32 – 192   （國旗 ｜ 標題 ｜ 年份圓盤，高 160，按內容動態）
    頁眉右半    y   32 – 268   （席次統計卡，滿帶 236）
    左內欄      y  208 – 1368  （跟著左半頁眉走，比地圖高 76）
    中段／右欄  y  284 – 1368  （被席次統計卡的下緣壓住）
    底部        只有文件說明（不佔版面元素）
"""

W, H = 2560, 1440
SCALE = 1.5
MARGIN = 72

# ---------------------------------------------------------------- 骨架線
HEADER_Y, HEADER_H = 32, 236          # 頁眉帶（236 = 2022 縣市長看板頁眉同高）
MAP_Y, MAP_H = 284, 1120              # 主圖框（取消頁尾後地圖喫到 1404）
# 2026-11-19：主圖加寬 582→608（左右各往欄位邊界內縮），素材 0.727 寬受限，
# 內容高度隨之 800→836，主圖整體放大
MAP1_X, MAP2_X, MAP_W = 736, 1380, 608
LEFT_X, LEFT_W = 72, 656
RIGHT_X, RIGHT_W = 2000, 488
CONTENT_TOP = 284
CONTENT_BOTTOM = 1404

# ---------------------------------------------------------------- 席次卡內部參數
# 頁眉 236 高，扣掉標註條與內距後內容高 184：
#   5 列 × 32 ＋ 4 × 4（列距）= 176 ≤ 184；圓餅直徑 172 置中
SEATS_ROWS = 5
SEATS_ROW_H = 32
SEATS_DONUT = 172

# ---------------------------------------------------------------- 政黨卡（滿色看板）
# 2026-11-19 第五版：比例照使用者樣張實測（911×251，ratio 3.63）等比縮放。
# 樣張結構＝三行文字（與舊版「主席併第 1 行」不同）：
#
#   ┌────────┬──────────────────────────────┬──────┬────────┐
#   │        │  中國國民黨                              │ 黨名 0.36h，基線 0.36h │
#   │ 照片    │  548萬1457票              ◉            │ 票數 0.29h，基線 0.693h│
#   │1:1.58  │  朱立倫 主席  41.02%                   │ 主席 0.165h 基線 0.94h │
#   └────────┴──────────────────────────────┴──────┴────────┘
#    0.602h×0.952h   三行文字                  黨徽 d0.534h  席次塊 0.876h 全高
#
# 實測（÷ 卡高 251）：照片 x7 y9 → 151×239；黨名墨高 84（y 8–91）；
# 票數數字墨高 53／萬 52／票 32（y 122–174）；朱立倫 38（y 199–236）；
# 「主席」小標 27、41.02% 28（y 194–221）；黨徽 d134 圓心 y 173.5；
# 席次塊寬 220 全高、「37」墨高 116。所有參數＝實測 ÷ 251。
CARD = dict(
    inset=0.028,                    # 照片左緣（7/251）
    photo_h=0.952,                  # 照片框高（239/251，近滿高）
    photo_ar=0.632,                 # 照片寬/高＝151/239 ≈ 1:1.58
    photo_w_min=0.30,               # 窄卡可收窄到此寬，再窄就不做
    gap1=0.087,                     # 照片 → 文字（22/251）
    em=0.534,                       # 黨徽直徑（134/251）
    em_cy=0.691,                    # 黨徽圓心 y（173.5/251，跨第 2–3 行）
    gap_em_seat=0.052,              # 黨徽 → 席次塊（13/251）
    gap_text_em=0.060,              # 文字右緣 → 黨徽（15/251）
    deep_w=0.876,                   # 席次深色塊寬（220/251，全高）
    deep_w_3d=1.14,                 # 3 位數（113／225 席）等比放大
    min_text=1.35,                  # 文字區最小寬（× h）
    min_aspect=3.3,                 # 卡寬/卡高 ≥ 3.3 才放照片框
    seat=0.64,                      # 席次數字字級（161/251，另受塊寬約束）
    name=0.36,                      # 黨名字級（墨高 0.335h → em 0.36）
    votes=0.34,                     # 票數數字（2026-11-19：阿拉伯數字再放大）
    votes_cjk=0.15,                 # 「萬」「票」同字級，都比原本小一階
    leader=0.21,                    # 主席姓名（2026-11-19：再放大，貼近「主席」二字）
    leader_tag=0.117,               # 「主席」二字（行內小標）
    pct=0.155,                      # 得票率（0.155h）
    base1=0.360,                    # 行 1 黨名基線（墨底 91/251）
    base2=0.693,                    # 行 2 票數基線（174/251）
    base3=0.940,                    # 行 3 主席姓名基線（236/251）
    tag_base=0.880,                 # 行 3「主席」小標與得票率基線（221/251）
    tag_gap=0.075,                  # 姓名 →「主席」間距（2026-11-19：姓名放大後同步收緊）
    pct_gap=0.044,                  # 「主席」→ 得票率間距（11/251）
    # ---- 左欄專屬（2026-11-19：右欄完全不變）----
    em_scale_left=1.50,             # 左欄黨徽 ×1.50（0.534h → 0.80h，上下居中後放得下）
    photo_w_scale_left=1.10,        # 左欄照片框寬 ×1.1（高已近滿 0.952h，只能加寬）
)


# ---------------------------------------------------------------- 政黨卡 · 右欄緊湊條
# 2026-11-19 晚：右欄「不分區」卡照使用者新樣張（700×109，6.42:1）統一改成：
#   [黨徽]  黨名 ＋ 票數·得票率（兩行）  [深一階黨色塊 ＋ 席次數字]
# 樣張實測（÷109）：黨徽 d0.945h 左緣 0.33h；席次塊 0.826h 近全高、數字白。
# 本欄卡 3.3–3.7:1 放不下樣張比例，名字由可用寬反解。
# 2026-11-20：應使用者要求補回得票數（政黨票）與得票率 —— 兩行版式：
#   行 1 黨名（基線 0.42h）、行 2 票數＋得票率（基線 0.86h，超寬整行等比縮）。
CARD_COMPACT = dict(
    em=0.80,            # 黨徽直徑
    inset_em=0.10,      # 黨徽左緣
    gap_em_name=0.09,   # 黨徽 → 黨名
    deep_w=0.86,        # 席次塊寬（1–2 位）
    deep_w_3d=1.06,     # 3 位數
    inset_deep=0.06,    # 席次塊右緣內距
    gap_name_deep=0.08, # 黨名 → 席次塊
    name=0.36,          # 行 1 黨名字級（放不下由可用寬反解）
    name_max=0.62,      # 黨名字級上限（單行舊版式遺留，僅作上限保護）
    base1=0.42,         # 行 1 黨名基線
    base2=0.86,         # 行 2 票數·得票率基線
    votes=0.34,         # 行 2 票數數字字級（2026-11-20：再放大）
    votes_cjk=0.18,     # 行 2「萬」「票」字級
    pct=0.15,           # 行 2 得票率字級（2026-11-20：縮小一階）
    pct_gap=0.05,       # 票數 → 得票率間距
    seat_max=0.70,      # 席次數字字級上限（另受塊寬約束）
)


# ---------------------------------------------------------------- 原住民卡 · 緊湊條
# 2026-11-20 深夜四修（使用者指定）：**照右上（右欄）政黨卡的設計** ——
# 每條內部幾何直接用 CARD_COMPACT ＋ party_geom_compact（同一組真值，
# 不再自帶一套比例）：[黨徽] 黨名（行 1）＋票數·得票率（行 2）｜深塊席次。
# 沒有徽章檔的政黨徽位留白、不足 6 黨的格子整格留白（使用者指定
# 「沒有就直接空缺留白」）——固定 3 行 × 2 欄＝6 黨滿版，column-major。
INDIG_COMPACT = dict(
    gap_col=20,         # 兩欄間距（設計 px）
    row_gap=7,          # 條間距（設計 px）
    # 2026-11-20 深夜五修（使用者指定）：得票數／得票率字級 ×1.25
    # 2026-11-20 深夜八修（照使用者樣張逐 px 實測）：
    #   vote_scale 1.50 → 1.85（票數 ≈35px，樣張寬 149px 反解），
    #   票數置於卡片**右下角**（右端貼席次塊、底端貼卡下緣）；
    #   pct_scale＝得票率維持 ×1.50 不變（≈12.4px，與樣張一致）；
    #   黨名 0.80×（深夜八修）→ 0.92×（深夜九修：名稱再放大，≈18.3px）。
    vote_scale=1.85,
    pct_scale=1.50,
)


def party_geom_compact(w, h, digits=2):
    """右欄緊湊條內部幾何（相對卡左上角）。渲染器與骨架圖共用。"""
    c = CARD_COMPACT
    em = c["em"] * h
    em_x = c["inset_em"] * h
    em_y = (h - em) / 2.0
    deep_w = (c["deep_w_3d"] if digits >= 3 else c["deep_w"]) * h
    deep_x = w - c["inset_deep"] * h - deep_w
    name_x = em_x + em + c["gap_em_name"] * h
    name_right = deep_x - c["gap_name_deep"] * h
    return dict(em_x=em_x, em_y=em_y, em=em,
                name_x=name_x, name_right=name_right,
                deep_x=deep_x, deep_w=deep_w, deep_h=h)


def party_geom(w, h, digits=2, em_scale=1.0, photo_w_scale=1.0, em_vcenter=False):
    """政黨卡內部幾何（相對卡左上角）。渲染器與骨架圖共用，避免兩套數字漂移。

    photo 為 None 表示這張卡放不下照片框（極窄卡）。
    em_scale／photo_w_scale：左欄卡放大用（黨徽 ×1.5、照片寬 ×1.1），右欄傳 1。
    em_vcenter：黨徽**上下居中**（2026-11-20 使用者指定，左欄用）；
    False 時照樣張釘在圓心 em_cy（0.691h，跨第 2–3 行）。
    """
    c = CARD
    deep_w = (c["deep_w_3d"] if digits >= 3 else c["deep_w"]) * h
    deep_x = w - deep_w
    em = c["em"] * h * em_scale
    if em_vcenter:
        # 上下居中：只受卡高約束（上下各留 3% 邊距）
        em = min(em, 0.94 * h)
        em_y = (h - em) / 2.0
    else:
        # 黨徽以圓心 em_cy 定位：放大後不得溢出卡面（上下各留 1% 邊距）
        em_max = 2.0 * min(c["em_cy"], 1.0 - c["em_cy"] - 0.01) * h
        em = min(em, em_max)
        em_y = c["em_cy"] * h - em / 2.0
    em_x = deep_x - c["gap_em_seat"] * h - em
    text_right = em_x - c["gap_text_em"] * h

    inset = c["inset"] * h
    # 照片框 1:1.58（樣張 151×239）：高 0.952h 推寬；寬度不夠由可用寬反推高；
    # photo_w_scale 把寬再乘 1.1（左欄；高不動，因為已近滿高）
    ph = c["photo_h"] * h
    pw = ph * c["photo_ar"]
    pw_max = text_right - inset - c["min_text"] * h - c["gap1"] * h
    if pw > pw_max:
        pw = max(0.0, pw_max)
        ph = pw / c["photo_ar"]
    ph = min(ph, c["photo_h"] * h)
    pw = min(ph * c["photo_ar"] * photo_w_scale, pw_max)
    if (w / h) >= c["min_aspect"] and pw >= c["photo_w_min"] * h:
        photo = (inset, (h - ph) / 2.0, pw, ph)
        text_x = inset + pw + c["gap1"] * h
    else:
        photo = None
        text_x = inset

    return dict(deep_x=deep_x, deep_w=deep_w, deep_h=h,
                em_x=em_x, em_y=em_y, em=em,
                photo=photo, text_x=text_x,
                text_w=text_right - text_x, text_right=text_right)


# ---------------------------------------------------------------- 色彩
C = {
    "bg_top":   "#101a33",
    "bg_mid":   "#0a1122",
    "bg_bottom": "#05070d",
    "glow_l":   "#2f6bd8",
    "glow_r":   "#00807a",
}

# ---------------------------------------------------------------- 元素清單（唯一真值）
# rect = (x, y, w, h)；kind 決定骨架圖要畫哪種「幽靈內容」
ELEMENTS = [
    # ---- 頁眉 ----
    dict(no=1, key="flag", name="院徽白卡", kind="flag", radius=24, strip=48,
         rect=(72, 32, 163, 160),
         spec="白卡 163×160 —— 寬度按院徽實際比例反解（160×1280/1255），"
              "院徽等比鋪滿整卡、不再裁切 · 圓角 24"),

    dict(no=2, key="title", name="主標題", kind="title", radius=14,
         rect=(269, 32, 741, 160),
         spec="56px（放不下反解）／900 · 垂直置中 · 例：第十一屆立法院立法委員選舉（無副標）"),

    dict(no=3, key="disc", name="年份圓盤", kind="disc", radius=80,
         rect=(1056, 32, 160, 160),
         spec="照 2022 dateBlock：年份 96＋年 32 · 投票日 36／月日 23 · 盤徑＝年份墨高×1.95（外框 160 定位用）"),

    dict(no=4, key="seats", name="席次統計卡", kind="seats", radius=28,
         rect=(1300, 32, 1188, 236),
         spec="左：四黨席次滿色條（單欄，順序照樣張）　中：半圓點陣（政黨分塊＋白字 113）　右：預留欄（本屆留白）"),

    # ---- 左內欄 ----
    # 2026-11-20 深夜 7：區域小黨補全 29 黨（兩欄清單）—— 四張卡 156→132／
    # 136→120、間距 20→16，讓位給加高的小黨清單（使用者同意「調整其他地方」）。
    dict(no=5, key="left1", name="左 · 政黨卡 1", kind="party", radius=18,
         rect=(72, 208, 656, 132),
         spec="照片位 84×126 · 黨名 26 · 主席 15.5 · 得票率 44 · 票數 16 · 席次牌 108×89"),
    dict(no=6, key="left2", name="左 · 政黨卡 2", kind="party", radius=18,
         rect=(72, 356, 656, 132), spec="同上"),
    dict(no=7, key="left3", name="左 · 政黨卡 3", kind="party", radius=18,
         rect=(72, 504, 628, 132), spec="同上（第 3 名起收窄 28）"),
    dict(no=8, key="left4", name="左 · 政黨卡 4（窄）", kind="party", radius=16,
         rect=(72, 652, 600, 120), spec="寬 600 · 高 120（第 4 名起收窄）"),

    dict(no=9, key="others_l", name="左 · 其他政黨", kind="list", radius=16,
         rect=(48, 782, 680, 408), rows=29, cols=2,
         spec="兩欄（左 15／右 14 列）· `黨名  X萬XXXX票`（無行首「-」、無得票率）："
              "字級雙向自適應取最大（欄寬束縛 × 0.74rowH，上限 28），萬·票 0.62×黨名 · "
              "左緣外擴 48、上緣距政黨卡 10、下緣距原住民卡留白 10"),

    dict(no=10, key="indig", name="原住民各政黨得票", kind="indig", radius=18,
         rect=(48, 1200, 680, 204), rows=3,
         spec="平地＋山地合併計：**照右欄政黨卡設計**（CARD_COMPACT 同款幾何）——"
              "[黨徽] 黨名＋票數·得票率（兩行）｜深塊席次；固定 3 行×2 欄（6 黨滿版），"
              "缺徽章／缺黨整格留白；右上白字標籤「原住民」在卡片外上緣；"
              "左緣 48、寬 680"),

    # ---- 中段地圖 ----
    # （2026-11-19 第五版）素材＝整張海報等比縮放（金馬面板、右上角方框、
    # 大陸輪廓都原樣保留），原本單獨抽離島的輔圖 12／14 已取消。
    # （2026-11-20）依使用者指定換源：主圖 1＝選區級、主圖 2＝鄉鎮市區級。
    dict(no=11, key="map1", name="主圖 1 · 選區級", kind="map", radius=22,
         rect=(736, 284, 608, 1120),
         spec="608×1120 框 · legislative_district_2024 整張等比縮放（0.190）"),
    dict(no=13, key="map2", name="主圖 2 · 鄉鎮市區級", kind="map", radius=22,
         rect=(1380, 284, 608, 1120),
         spec="608×1120 框 · legislative_township_2024 整張等比縮放（0.190）"),

    # ---- 縮小版輔圖（2026-11-19 新增）----
    # 壓在兩張主圖的左上角。
    # 主圖素材 0.727 比框「胖」、寬受限後下緣對齊，留白集中到上方 ——
    # 輔圖 330×454（同素材比例 0.727、正好鋪滿），位於主圖框左上角。
    # （2026-11-20）依使用者指定換源：輔圖 1＝選舉得票級、輔圖 2＝縣市級。
    dict(no=20, key="minimap1", name="輔圖 1 · 選舉得票級（縮小版）", kind="minimap", radius=12,
         rect=(752, 296, 330, 454),
         spec="330×454 · legislative_election_2024 整張等比縮小 · 透明疊主圖 1 左上角"),
    dict(no=21, key="minimap2", name="輔圖 2 · 縣市級（縮小版）", kind="minimap", radius=12,
         rect=(1396, 296, 330, 454),
         spec="330×454 · legislative_county_2024 整張等比縮小 · 透明疊主圖 2 左上角"),

    # ---- 右內欄 ----
    dict(no=15, key="right1", name="右 · 政黨卡 1", kind="party", radius=18,
         rect=(2000, 284, 488, 136),
         spec="照片位 95×116 · 黨名 25 · 得票率 42.5 · 席次牌 85×86"),
    dict(no=16, key="right2", name="右 · 政黨卡 2", kind="party", radius=18,
         rect=(2000, 436, 488, 136), spec="同上"),
    dict(no=17, key="right3", name="右 · 政黨卡 3（窄）", kind="party", radius=16,
         rect=(2028, 588, 460, 126), spec="寬 460 · 高 126"),
    dict(no=18, key="right4", name="右 · 政黨卡 4（窄）", kind="party", radius=16,
         rect=(2048, 730, 440, 118), spec="寬 440 · 高 118"),

    dict(no=19, key="others_r", name="右 · 其他政黨", kind="list", radius=16,
         rect=(2068, 864, 420, 540), rows=12,
         spec="逐黨一行（緊湊，無標題字樣、無行首「-」、無得票率）· `黨名  X萬XXXX票`"
              "（萬·票壓小；票數欄跟著最長黨名走，黨名過長換行、不縮字）"),
]

# ---------------------------------------------------------------- 統計
TOTAL_SEATS = 113          # 2008 起；1992–2004 屆次另設（見 README）
LEGEND_Y_TICKS = [32, 192, 208, 284, 1404]
LEGEND_X_TICKS = [72, 728, 736, 1344, 1380, 1988, 2000, 2488]


def _party_spec(w, h, key=""):
    """政黨卡的規格文字由 CARD 現算 —— 不再手抄數字。

    2022 骨架圖最大的教訓就是「手抄 layout 常量，最後 9 處漂移」；
    這裡連說明文字都走同一組來源，改 CARD 不可能忘掉 spec。
    左欄卡（key 以 left 開頭）帶上黨徽／照片放大系數，與渲染器同一組數字。
    """
    c = CARD
    left = key.startswith("left")
    if key.startswith("right"):
        # 右欄緊湊條（2026-11-20 兩行版式）：黨徽｜黨名＋票數·得票率｜席次塊
        g = party_geom_compact(w, h)
        cc = CARD_COMPACT
        return ("緊湊條 · 黨徽 %.0f（左緣 %.0f）· 黨名 ≤%.1f（基線 %.2fh）· "
                "票數 %.1f／萬·票 %.1f ＋ 得票率 %.1f（基線 %.2fh）· "
                "席次塊 %.0f×%.0f"
                % (g["em"], g["em_x"], cc["name"] * h, cc["base1"],
                   cc["votes"] * h, cc["votes_cjk"] * h, cc["pct"] * h, cc["base2"],
                   g["deep_w"], g["deep_h"]))
    g = party_geom(w, h,
                   em_scale=c["em_scale_left"] if left else 1.0,
                   photo_w_scale=c["photo_w_scale_left"] if left else 1.0,
                   em_vcenter=left)
    photo = ("照片框 %.0f×%.0f" % (g["photo"][2], g["photo"][3])) if g["photo"] else "無照片框"
    return ("滿色圓角 · %s · 黨名 %.1f · 票數 %.1f／萬·票 %.1f · 主席 %.1f＋小標 %.1f · "
            "得票率 %.1f · 黨徽 %.0f（cy %.2fh%s）· 席次塊 %.0f×%.0f"
            % (photo, c["name"] * h, c["votes"] * h, c["votes_cjk"] * h,
               c["leader"] * h, c["leader_tag"] * h, c["pct"] * h,
               g["em"], (g["em_y"] + g["em"] / 2.0) / h,
               "，上下居中" if left else "", g["deep_w"], g["deep_h"]))


for _e in ELEMENTS:
    if _e["kind"] == "party":
        _e["spec"] = _party_spec(_e["rect"][2], _e["rect"][3], _e["key"])


def by_key(key):
    for e in ELEMENTS:
        if e["key"] == key:
            return e
    raise KeyError(key)
