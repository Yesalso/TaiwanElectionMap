# -*- coding: utf-8 -*-
"""
render_board.py — 用 2024 年第 11 屆立委選舉資料填充看板

左欄＝區域立委（區域得票率／區域席次）
右欄＝不分區立委（政黨票得票率／不分區席次）
右上＝總席次卡（綜述 ＋ 113 席半圓議場圖，不列表格）

★ 字體與樣式一律照 Mayors/2022NineInOne/board 的規格：
   · 標題／黨名／得票率：GenSekiGothic TW H，weight 900，純白
   · 票數：textDim rgba(255,255,255,0.66)，weight 700，右對齊
   · 副行／英文／贅字：textFaint rgba(255,255,255,0.40)
   · 「其他政黨」清單＝2022 的 others 樣式：`- 黨名    票數`，不印百分比，
     列間畫 rgba(255,255,255,0.07) 細線
   · 地圖：contain 進框、不加底板、不加內距（同 MapLayer / Map2Layer）

座標全部來自 `layout_board.py`（設計 2560×1440），輸出 2560×1440（scale 1.0）。
"""
import os
import sys
import math
import argparse
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout_board as L                      # noqa: E402
from blank_board import Board                 # noqa: E402

ASSETS22 = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                        "Mayors", "2022NineInOne", "board",
                                        "dist", "assets"))
# 2026-11-20：頁眉國旗與政黨徽章改用 Video 專案的素材庫（使用者指定）——
#   院徽　 Video/assets/share/LegislativeYuan.png（取代 2022 的 roc_flag.png）
#   徽章　 Video/assets/party/<黨名>.png（取代 2022 的 party_*.png）
VIDEO_ASSETS = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                            "Video", "assets"))
SHARE_SRC = os.path.join(VIDEO_ASSETS, "share")
PARTY_SRC = os.path.join(VIDEO_ASSETS, "party")
# 徽章 key → Video 素材庫檔名。無黨籍／時代力量這次有真徽章可用，
# 不再畫「深色圓牌＋首字」的代用品（mark 仍留 None 走代用品分支作保底）。
PARTY_BADGE = {
    "kmt": "中国国民党.png",
    "dpp": "民主进步党.png",
    "tpp": "台湾民众党.png",
    "npp": "时代力量.png",
    "ind": "无党籍.png",
}


def disc_badge(src, col, ratio=0.62):
    """把徽章內容墊進實心圓盤：盤徑＝內容外接框長邊 ÷ ratio，內容原解析度
    置中（不重採樣）。回傳正方形 RGBA，contain() 會把它整顆縮進黨徽框。"""
    bbox = src.getbbox()
    if not bbox:
        return src
    content = src.crop(bbox)
    bw, bh = content.size
    S = int(round(max(bw, bh) / ratio)) + 2
    disc = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse((1, 1, S - 2, S - 2), fill=col)
    disc.alpha_composite(content, ((S - bw) // 2, (S - bh) // 2))
    return disc


def badge_transparent(im, threshold=12, tol=90):
    """徽章／院徽的背景轉透明。

    配方出自 Video/src/mapgen/tool/make_transparent.py 的
    white_to_transparent()：逐通道判準，三通道都 >= 255-threshold 才算白
    （threshold 用同一個 build_white 的 12）。

    但直接全域套用會把徽章**內部**的白一起吃掉 —— KMT 白日、DPP 十字、
    無黨籍「無」字都會被摳成透明、露出卡面底色。看板徽章要去的只是
    **背景**，所以加一條收緊：背景遮罩只吃**與圖片邊緣連通**的區域（BFS）。
    底色不是白的（民眾黨青底、時代力量黃底）則改吃四角取樣的背景色，
    用同一套「連得上才吃」的邏輯。
    """
    a = np.array(im.convert("RGBA"))
    h, w = a.shape[:2]
    # ⓪ 角落已經透明（背景本來就去好，如 Video 素材庫的民主進步黨.png）
    #    → 一個像素都不吃，原樣返回。徽章的白邊／白十字是**內容**，
    #    「與邊緣連通」的遮罩會沿著透明底→白邊→白十字一路吃進徽章，
    #    綠圓綠卡直接隱形（2026-11-20 實測 alpha0 21%→63%）。
    if min(a[0, 0, 3], a[0, w - 1, 3], a[h - 1, 0, 3], a[h - 1, w - 1, 3]) < 128:
        return Image.fromarray(a, "RGBA")
    rgb = a[..., :3].astype(int)
    limit = 255 - threshold
    # ① 白遮罩：make_transparent 同一套逐通道判準（逐通道差的最大值 <= threshold）
    ok = np.clip(255 - rgb, 0, 255).max(axis=2) <= threshold
    # ② 四角取樣：角落不是白（青底／黃底）→ 補一組曼哈頓距離判準
    for s in (rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]):
        if int(s[0]) + int(s[1]) + int(s[2]) >= 3 * limit:
            continue                             # 白角：①已涵蓋
        ok |= (np.abs(rgb - s.reshape(1, 1, 3)).sum(axis=2) <= tol)
    # ③ 只吃與邊緣連通的背景
    visited = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if ok[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if ok[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        a[y, x, 3] = 0
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and ok[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))
    return Image.fromarray(a, "RGBA")
A = os.path.join(HERE, "assets")

WHITE = (255, 255, 255)
TEXT_DIM = (255, 255, 255, 168)      # T.BG.textDim  0.66
TEXT_FAINT = (255, 255, 255, 102)    # T.BG.textFaint 0.40
RULE = (255, 255, 255, 18)           # others.ruleColor 0.07

# ---------------------------------------------------------------- 政黨代表色
# 2026-11-19 改版：政黨卡改成**滿色橫帶**（照使用者給的電視看板樣張），
# base ＝ 卡面代表色、deep ＝ 右端席次塊的「深一階同色」。
# 樣張的 KMT 用 #00B0F0、席次塊 #0070C0 —— 這裡沿用同一組色階邏輯，
# 其他政黨按同一比例（G×0.64、B×0.80）推深階，四黨放在一起才像同一套系統。
PAL = {
    "kmt": dict(base=(0, 176, 240), deep=(0, 112, 192)),
    "dpp": dict(base=(0, 176, 80),  deep=(0, 113, 64)),
    "tpp": dict(base=(0, 176, 176), deep=(0, 113, 113)),
    "npp": dict(base=(255, 192, 0), deep=(178, 132, 0)),
    "ind": dict(base=(166, 166, 166), deep=(96, 102, 110)),
}


def card_ink(base):
    """滿色卡上的字色：亮卡（時代力量黃、無黨籍灰）改深字，其餘純白。"""
    return WHITE if _lum(base) <= 168 else (16, 26, 44)


def mix(bg, fg, t):
    """把 fg 以 t 的比例「壓」進 bg，回傳**不透明**色。

    滿色卡上不能用半透明色：PIL 在 RGBA 畫布上填 rgba(255,255,255,28)
    是「覆蓋 alpha」而不是混合（本專案的老坑），卡片底色會被直接擦掉，
    所以照片框、主席標籤這種「淡一階」的地方一律先算成實色。
    """
    return tuple(int(round(bg[i] + (fg[i] - bg[i]) * t)) for i in range(3)) + (255,)


# ---------------------------------------------------------------- 資料
# 2026-11-20：卡片排序＝**席次優先、票数次之**（使用者指定）——
# 區域：國民黨 37 > 民進黨 36 > 無黨籍 0（901325 票）> 民眾黨 0（397214 票）；
# 無黨籍唯一 1 席來自山地原住民（2026-11-20 深夜七修使用者指定：區域 0 席）。
# 不分區：民進黨 13（498萬）> 國民黨 13（476萬）> 民眾黨 8 > 時代力量 0（同票數序）。
# leader ＝ 投票日當天的政黨主席（無黨籍沒有主席，印「—」）。
REGIONAL = [
    dict(cn="中國國民黨", en="KMT", pct=41.02, votes=5481457, seats=37,
         mark="kmt", leader="朱立倫", **PAL["kmt"]),
    dict(cn="民主進步黨", en="DPP", pct=45.17, votes=6035971, seats=36,
         mark="dpp", leader="賴清德", **PAL["dpp"]),
    # 無黨籍沒有主席（印「—」）；徽章 2026-11-20 起改用 Video 素材庫的
    # 无党籍.png（黑圓「無」），不再畫深色圓牌＋首字的代用品
    dict(cn="無黨籍", en="IND", pct=6.75, votes=901325, seats=0,
         mark="ind", leader="—", **PAL["ind"]),
    dict(cn="台灣民眾黨", en="TPP", pct=2.97, votes=397214, seats=0,
         mark="tpp", leader="柯文哲", **PAL["tpp"]),
]
# 區域小黨完整名單（2026-11-20 使用者提供中選會資料補全；台灣民眾黨 397214
# 已是主卡 4，不入清單）。排序＝票數降序；只列得票數、不列得票率（使用者指定）。
REG_OTHERS = [
    ("時代力量", 96589), ("小民參政歐巴桑聯盟", 78138), ("社會民主黨", 74375),
    ("台灣雙語無法黨", 55937), ("司法改革黨", 38334), ("台灣基進", 32583),
    ("台灣維新", 32292), ("人民最大黨", 25216), ("台灣綠黨", 15557),
    ("喜樂島聯盟", 15433), ("中華統一促進黨", 13203), ("制度救世島", 11260),
    ("新黨", 8280), ("台灣麻將最大黨", 7839), ("復康聯盟黨", 7441),
    ("勞動黨", 6453), ("司法正義黨", 6331), ("中華聯合黨", 4139),
    ("台灣國民黨", 3293), ("台灣革命黨", 3072), ("中華文化共和黨", 2583),
    ("家庭基本收入", 2361), ("台灣整復師聯盟工黨", 1881), ("中華婦女黨", 1029),
    ("人民民主黨", 836), ("經濟黨", 472), ("中華愛國同心黨", 310),
    ("合一行動聯盟", 174), ("興中同盟會", 136),
]

ATLARGE = [
    dict(cn="民主進步黨", en="DPP", pct=36.16, votes=4982062, seats=13,
         mark="dpp", leader="賴清德", **PAL["dpp"]),
    dict(cn="中國國民黨", en="KMT", pct=34.58, votes=4764576, seats=13,
         mark="kmt", leader="朱立倫", **PAL["kmt"]),
    dict(cn="台灣民眾黨", en="TPP", pct=22.07, votes=3040615, seats=8,
         mark="tpp", leader="柯文哲", **PAL["tpp"]),
    dict(cn="時代力量", en="NPP", pct=2.57, votes=353412, seats=0,
         mark="npp", leader="王婉諭", **PAL["npp"]),
]
ATL_OTHERS = [("小民參政歐巴桑聯盟", 128613), ("台灣綠黨", 117298),
              ("台灣基進", 95078), ("親民黨", 69818),
              ("台灣雙語無法黨", 44852), ("台灣團結聯盟", 43375),
              ("新黨", 40288), ("司法改革黨", 37615),
              ("制度救世島", 19665), ("中華統一促進黨", 17423),
              ("人民最大黨", 11746), ("台灣維新", 10300)]
# 2026-11-20 深夜：使用者提供**不分區完整表格**重新修正 —— 主卡 4 黨
# （國 4764576／34.58%／13、民 4982062／36.16%／13、眾 3040615／22.07%／8、
# 時代力量 353412／2.57%／0）與既有資料一致不動；清單由 8 黨補全為
# **12 黨**（票數降序，得票率欄仍不畫）。「得票率增減」欄看板不呈現。

# ---------------------------------------------------------------- 小黨得票率
# 2026-11-20 深夜 9：得票率欄**再度移除**（使用者指定），空出的寬度全部讓給
# 字級、縱向再擴給行距；TOTAL_REG／TOTAL_ATL 與 pct_txt() 隨之移除。

INDIG = {
    "平地原住民": [("中國國民黨", 65329, "54.87%", 2),
                   ("民主進步黨", 27431, "23.04%", 1),
                   ("無黨籍", 24385, "20.48%", 0)],
    "山地原住民": [("無黨籍", 62258, "43.28%", 1),
                   ("中國國民黨", 43588, "30.22%", 1),
                   ("民主進步黨", 31874, "22.10%", 1)],
}

# 2026-11-20 深夜：使用者指定「兩個原住民**加在一起算**，只顯示這些即可」——
# 同黨票數、席次相加，得票率按合併後重算。分區總票數中選會資料未列入本檔，
# 以「該區各黨票數和 ÷ 各黨得票率和」反推（平地 ≈119,062、山地 ≈144,209，
# 三黨各自反解一致到 ±0.1%，可信），合併得票率＝合併票數 ÷ 兩區總和。
# 排序＝合併票數降序（與左欄／右欄一致）。
def _indig_combined():
    tot = 0.0
    per = {}
    for rows in INDIG.values():
        v_sum = sum(r[1] for r in rows)
        p_sum = sum(float(r[2].rstrip("%")) / 100.0 for r in rows)
        tot += v_sum / p_sum
        for name, votes, _pct, seat in rows:
            v, s = per.get(name, (0, 0))
            per[name] = (v + votes, s + seat)
    rows = [(n, v, "%.2f%%" % (v / tot * 100.0), s)
            for n, (v, s) in per.items()]
    rows.sort(key=lambda r: -r[1])
    return rows


INDIG_ALL = _indig_combined()
# → [("中國國民黨", 108917, "41.38%", 3),
#    ("無黨籍",     86643, "32.91%", 1),
#    ("民主進步黨", 59305, "22.52%", 2)]
PARTY_COLOR = {"中國國民黨": PAL["kmt"]["base"], "民主進步黨": PAL["dpp"]["base"],
               "台灣民眾黨": PAL["tpp"]["base"], "無黨籍": PAL["ind"]["base"]}
PARTY_DEEP = {"中國國民黨": PAL["kmt"]["deep"], "民主進步黨": PAL["dpp"]["deep"],
              "台灣民眾黨": PAL["tpp"]["deep"], "無黨籍": PAL["ind"]["deep"]}

# 2026-11-20：分組白字標籤（使用者指定）—— 各組**第一張卡**的右上角，
# 且在**卡片外**（緊貼卡片上緣、右端對齊卡片右緣，深夜二修指定「不是在
# 卡片裡面」）：區域組 → left1「區域立法委員」、不分區組 → right1
# 「不分區立法委員」；原住民面板右上角「原住民」（見 indig_card）。
GROUP_TAGS = {"left1": "區域立法委員", "right1": "不分區立法委員"}
TAG_SIZE = 14          # 設計 px（標籤行高只有 16px：頁眉／清單下緣到卡上緣）
# 2026-11-20：使用者指定「區域立法委員／不分區立法委員」標籤字級 ×2（14→28）；
# 「原住民」標籤維持原字級不動。
TAG_SIZE_X2 = TAG_SIZE * 2


def group_tag_size(tag):
    """分組標籤字級：區域／不分區 ×2，其餘（原住民）照舊。"""
    return TAG_SIZE_X2 if tag in GROUP_TAGS.values() else TAG_SIZE
# 黨名 → 徽章 key（原住民卡照右欄政黨卡設計後要畫黨徽用）——
# 從 REGIONAL／ATLARGE 的 mark 欄位彙整；不在表內（無徽章檔）→ 徽位留白
PARTY_MARK = {d["cn"]: d.get("mark") for d in REGIONAL + ATLARGE}

# 2026-11-20 修正：席次合計照 indig 資料 —— 國民黨 53（區域 37＋不分區 13
# ＋平地 2＋山地 1）、民進黨 51（36＋13＋1＋1）、民眾黨 8、無黨籍 1（山地），
# 合計 113；**排序＝席次優先**（使用者指定）。先前「國 52／無 2」與原住民
# 資料對不上，本輪一併更正。
TOTAL = [("中國國民黨", 53, PAL["kmt"]["base"]),
         ("民主進步黨", 51, PAL["dpp"]["base"]),
         ("台灣民眾黨", 8, PAL["tpp"]["base"]),
         ("無黨籍", 1, PAL["ind"]["base"])]
TOTAL_SEATS = 113

# ---------------------------------------------------------------- 議場半圓點陣
# 2026-11-20：照使用者樣張逐點提取的 113 席座位的**歸一化座標**（×3348、÷1680），
# 排佈＝樣張原樣（同心弧緻密點陣），點色亦照樣張：kmt 深藍/dpp 綠/tpp 青/ind 灰。
# 樣張本是 **53藍＋1灰**（與本板資料 53/51/8/1 一致）；先前誤用 52/2 改掉一顆，
# 本輪還原 —— 頂點中央偏右（nx 0.5275）那顆灰點歸還深藍。
HEMICYCLE_DOTS = [
    ("kmt", 0.6929, 0.9001),
    ("dpp", 0.2478, 0.9001),
    ("kmt", 0.7376, 0.9000),
    ("kmt", 0.8717, 0.9000),
    ("dpp", 0.1136, 0.9000),
    ("kmt", 0.8270, 0.9000),
    ("kmt", 0.9164, 0.9000),
    ("dpp", 0.2031, 0.9000),
    ("dpp", 0.0243, 0.9000),
    ("dpp", 0.0690, 0.9000),
    ("dpp", 0.1583, 0.9000),
    ("kmt", 0.7823, 0.9000),
    ("kmt", 0.9109, 0.7917),
    ("dpp", 0.0298, 0.7917),
    ("kmt", 0.8654, 0.7897),
    ("dpp", 0.0753, 0.7897),
    ("dpp", 0.2130, 0.7873),
    ("kmt", 0.7276, 0.7873),
    ("kmt", 0.8196, 0.7872),
    ("dpp", 0.1210, 0.7872),
    ("kmt", 0.7734, 0.7838),
    ("dpp", 0.1673, 0.7837),
    ("kmt", 0.6799, 0.7826),
    ("dpp", 0.2607, 0.7826),
    ("dpp", 0.0419, 0.6855),
    ("kmt", 0.8988, 0.6855),
    ("kmt", 0.8515, 0.6822),
    ("dpp", 0.0892, 0.6822),
    ("kmt", 0.7059, 0.6814),
    ("dpp", 0.2348, 0.6814),
    ("dpp", 0.1374, 0.6781),
    ("kmt", 0.8033, 0.6781),
    ("kmt", 0.6517, 0.6764),
    ("dpp", 0.2889, 0.6763),
    ("dpp", 0.1870, 0.6728),
    ("kmt", 0.7537, 0.6728),
    ("kmt", 0.6103, 0.5890),
    ("dpp", 0.3304, 0.5890),
    ("kmt", 0.6732, 0.5871),
    ("dpp", 0.2674, 0.5871),
    ("dpp", 0.0604, 0.5831),
    ("kmt", 0.8802, 0.5831),
    ("dpp", 0.1105, 0.5796),
    ("kmt", 0.8302, 0.5796),
    ("dpp", 0.1623, 0.5756),
    ("kmt", 0.7784, 0.5756),
    ("kmt", 0.7238, 0.5713),
    ("dpp", 0.2169, 0.5713),
    ("dpp", 0.3820, 0.5270),
    ("kmt", 0.5586, 0.5270),
    ("kmt", 0.6313, 0.5089),
    ("dpp", 0.3094, 0.5089),
    ("ind", 0.5005, 0.4948),
    ("tpp", 0.4402, 0.4948),
    ("kmt", 0.8555, 0.4860),
    ("dpp", 0.0851, 0.4860),
    ("kmt", 0.8021, 0.4838),
    ("dpp", 0.1386, 0.4838),
    ("kmt", 0.6849, 0.4828),
    ("dpp", 0.2558, 0.4828),
    ("kmt", 0.7457, 0.4824),
    ("dpp", 0.1950, 0.4823),
    ("kmt", 0.5819, 0.4503),
    ("dpp", 0.3587, 0.4503),
    ("dpp", 0.4132, 0.4140),
    ("ind", 0.5275, 0.4140),
    ("dpp", 0.3023, 0.4105),
    ("kmt", 0.6383, 0.4105),
    ("tpp", 0.4703, 0.4018),
    ("dpp", 0.2347, 0.4006),
    ("kmt", 0.7059, 0.4006),
    ("kmt", 0.7675, 0.3967),
    ("dpp", 0.1732, 0.3967),
    ("dpp", 0.1156, 0.3955),
    ("kmt", 0.8251, 0.3955),
    ("kmt", 0.5858, 0.3569),
    ("dpp", 0.3549, 0.3569),
    ("kmt", 0.6601, 0.3326),
    ("dpp", 0.2805, 0.3326),
    ("dpp", 0.4116, 0.3239),
    ("kmt", 0.5291, 0.3239),
    ("dpp", 0.2134, 0.3200),
    ("kmt", 0.7273, 0.3200),
    ("kmt", 0.7894, 0.3132),
    ("dpp", 0.1513, 0.3132),
    ("tpp", 0.4703, 0.3128),
    ("kmt", 0.6095, 0.2801),
    ("dpp", 0.3312, 0.2801),
    ("dpp", 0.2586, 0.2551),
    ("kmt", 0.6821, 0.2551),
    ("kmt", 0.5553, 0.2442),
    ("dpp", 0.3854, 0.2442),
    ("dpp", 0.1919, 0.2402),
    ("kmt", 0.7488, 0.2402),
    ("kmt", 0.4989, 0.2261),
    ("tpp", 0.4418, 0.2261),
    ("kmt", 0.6328, 0.2032),
    ("dpp", 0.3079, 0.2032),
    ("dpp", 0.2366, 0.1776),
    ("kmt", 0.7041, 0.1776),
    ("dpp", 0.3603, 0.1655),
    ("kmt", 0.5804, 0.1655),
    ("tpp", 0.4148, 0.1426),
    ("kmt", 0.5259, 0.1426),
    ("tpp", 0.4703, 0.1348),
    ("kmt", 0.6559, 0.1263),
    ("dpp", 0.2848, 0.1263),
    ("dpp", 0.3358, 0.0872),
    ("kmt", 0.6049, 0.0872),
    ("kmt", 0.5519, 0.0609),
    ("dpp", 0.3888, 0.0609),
    ("tpp", 0.4430, 0.0476),
    ("tpp", 0.4977, 0.0476),
]
HEMICYCLE_AR = 3348 / 1680.0        # 樣張寬高比
HEMICYCLE_R = 59.4 / 1680.0         # 點半徑 ÷ 樣張高
HEMICYCLE_NUM = (0.49, 0.82, 0.2388)   # 「113」中心 x/y（歸一）與字高（÷樣張高）
# 2026-11-20：字級 0.20 → 0.2388×半圓高；半圓高 201 設計 px 時＝48 設計 px
# ＝1920×1080 輸出下的 36px（使用者指定）；顏色＝純白、位置照新樣張（nx 0.49/ny 0.82）
# 2026-11-20 深夜：**藍左綠右**（使用者指定）—— 點陣座標是樣張原樣
# （dpp 在左半、kmt 在右半），把兩黨的顏色對調即可：左半 51 顆藍、右半 52 顆綠。
HEMICYCLE_COL = {"kmt": (27, 148, 49), "dpp": (0, 0, 153),
                 "tpp": (40, 200, 200), "ind": (153, 153, 153)}   # 樣張實測色（kmt/dpp 對調）


def txt_votes(v):
    """千分位版本（僅清單用；主卡的票數走 vote_wan）。"""
    return f"{v:,}"


def vote_wan(v):
    """與 2022 引擎的 Utils.voteWan 同一套規則：
    ≤10000 原樣不加千分位；>10000 用「萬」分段，尾數補足 4 位（959302 → 95萬9302）。
    """
    v = int(round(v))
    if abs(v) <= 10000:
        return str(v)
    wan, rest = divmod(abs(v), 10000)
    if rest == 0:
        return f"{wan}萬"
    return f"{wan}萬{rest:04d}"


def vote_parts(v):
    """"603萬5971票" → [('603',True),('萬',False),('5971',True),('票',False)]"""
    s = vote_wan(v) + "票"
    out = []
    for ch in s:
        num = ch.isdigit()
        if out and out[-1][1] == num:
            out[-1] = (out[-1][0] + ch, num)
        else:
            out.append((ch, num))
    return out


def _lum(rgb):
    """牌面亮度（0–255）。決定席次數字要白字還是深字。"""
    r, g, b = rgb[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


class Render(Board):
    def __init__(self, scale):
        super().__init__(scale, grid=False)
        self.cache = {}
        self.badges = {}                             # 徽章 key → RGBA（已轉透明）

    # ---------------------------------------------------------- 圖片
    def load(self, path, circle=False):
        key = (path, circle)
        if key in self.cache:
            return self.cache[key]
        im = Image.open(path).convert("RGBA")
        if circle:
            s = min(im.size)
            im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                          (im.width + s) // 2, (im.height + s) // 2))
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, im.width - 1, im.height - 1), fill=255)
            im.putalpha(Image.composite(im.getchannel("A"),
                                        Image.new("L", im.size, 0), mask))
        self.cache[key] = im
        return im

    def badge(self, key):
        """Video 素材庫（Video/assets/party）的政黨徽章，背景已轉透明；
        每個 key 只轉檔一次（badge_transparent 是全圖 numpy 運算）。"""
        if key not in self.badges:
            src = Image.open(os.path.join(PARTY_SRC, PARTY_BADGE[key]))
            im = badge_transparent(src)
            if key == "tpp":
                # 台灣民眾黨：白「眾」墊進**亮青實心圓**（2026-11-20 使用者指定，
                # 照 dist/_tmp_board.png 舊版看板的樣式）。盤面用素材自帶的
                # 品牌青 (40,200,200)——「眾」筆畫之間的原青色縫隙與盤面
                # 同色、自然融合成官方 Logo 觀感，又與卡面 (0,176,176) 拉開一階。
                im = disc_badge(im, (40, 200, 200, 255), ratio=0.62)
            self.badges[key] = im
        return self.badges[key]

    def fit_text(self, s, size, maxw, min_size=9):
        # 量寬一律走 measure()：數字與中文是兩支字型，用單一字型量會低估
        w = self.measure(s, size)
        if w <= self.px(maxw):
            return size
        return max(min_size, size * self.px(maxw) / w * 0.98)

    def contain(self, im, x, y, w, h, radius=0, va="center"):
        """與 MapLayer 同一套：contain 進框、依 anchor 置中、不加底板。
        va="bottom" 時貼框下緣（主圖用：素材比例比框「胖」，框內上下留白，
        下緣對齊讓留白集中到上方，給左上角的輔圖让位）。
        """
        k = min(w / im.width, h / im.height)
        sw, sh = im.width * k, im.height * k
        size = (max(1, self.px(sw)), max(1, self.px(sh)))
        im2 = im.resize(size, Image.LANCZOS)
        if radius:
            m = Image.new("L", size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1),
                                                radius=self.px(radius), fill=255)
            im2.putalpha(Image.composite(im2.getchannel("A"),
                                         Image.new("L", size, 0), m))
        oy = (h - sh) if va == "bottom" else (0 if va == "top" else (h - sh) / 2.0)
        self.ov.alpha_composite(im2, (self.px(x + (w - sw) / 2),
                                      self.px(y + oy)))
        return (x + (w - sw) / 2, y + oy, sw, sh)

    # ---------------------------------------------------------- 文字工具
    def drop_shadow(self, im, x, y, size, strength=0.30):
        """把圖片的 alpha 剪影壓成一團模糊黑影，墊在圖片下面。

        黨徽拿掉白框後，KMT 深藍徽、TPP 青徽與卡面同色系會黏在一起 ——
        這一層「投影」讓它浮起來，而不是加回一個白底方塊。
        """
        s = max(1, self.px(size))
        sh = im.resize((s, s), Image.LANCZOS)
        a = sh.getchannel("A").point(lambda v: int(v * strength))
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste((0, 0, 0, 255), (0, 0), a)
        layer = layer.filter(ImageFilter.GaussianBlur(max(1, int(s * 0.07))))
        self.ov.alpha_composite(layer, (self.px(x), self.px(y + size * 0.05)))

    def glow_text(self, xy, s, size, color, glow, radius=16, alpha=110, anchor="ls"):
        """同色光暈：2022 主卡的得票率就是靠這一層從街景底色浮起來的
        （`shadowColor = alpha(party.light, .5)`, blur 36 —— 不是黑陰影）。
        """
        f = self.font(size)
        bx0, by0, bx1, by1 = self.d.textbbox((0, 0), s, font=f, anchor=anchor)
        pad = int(self.px(radius) * 1.6)
        w = max(1, bx1 - bx0 + pad * 2)
        h = max(1, by1 - by0 + pad * 2)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((pad - bx0, pad - by0), s, font=f,
                                   fill=glow + (alpha,), anchor=anchor)
        layer = layer.filter(ImageFilter.GaussianBlur(self.px(radius) / 2.2))
        self.ov.alpha_composite(layer, (self.px(xy[0]) + bx0 - pad,
                                        self.px(xy[1]) + by0 - pad))
        self.text(xy, s, size, color, anchor=anchor)

    def votes_bold(self, cjk_size):
        """「萬」「票」小字號防糊規則（深夜十一修）：像素字號 <22 改用
        Bold 字面（Heavy ≤20px 草字頭糊死；Bold 13px 起清晰）。"""
        return max(1, int(round(cjk_size * self.s))) < 22

    def votes_rich(self, x, base_y, v, num_size, cjk_size, color, align="left",
                   anchor="ls"):
        """得票數富文本（2026-11-19 修訂）：阿拉伯數字放大、「萬」「票」同字級。
        align="right" 時 x 是右緣；anchor 預設 "ls"（基線對齊），
        清單版改傳 "lm" 與黨名／得票率同一條中線。

        2026-11-20 深夜十一修：「萬」「票」小字號防糊 —— Heavy 字重
        ≤20px 時草字頭兩點糊成橫杠（實測 20 糊／22 勉強／24 清晰），
        同家族 Bold 13px 起即清晰。故 CJK 段**像素字號 < 22** 時自動
        改走 Bold 字面：字級、版面完全不變，只換字重。
        """
        bold = self.votes_bold(cjk_size)
        segs = [(t, num_size if num else cjk_size, bool(bold and not num))
                for t, num in vote_parts(v)]
        widths = [self.measure(t, sz, cjk_bold=cb) / self.s
                  for t, sz, cb in segs]
        cx = x - sum(widths) if align == "right" else x
        for (t, sz, cb), w in zip(segs, widths):
            self.text((cx, base_y), t, sz, color, anchor=anchor, cjk_bold=cb)
            cx += w
        return sum(widths)

    # ---------------------------------------------------------- 頁眉
    def flag_card(self, el):
        """頁眉第一格（2026-11-20 三修）：**立法院院徽**卡——
        素材 Video/assets/share/LegislativeYuan.png（1280×1255）。
        卡片本身按院徽實際比例反解：高 160 不變、寬 163（160×1280/1255），
        院徽**等比鋪滿整卡**、不再裁切也不再硬塞 1.5:1。院徽白底先走
        badge_transparent()（只剩金色線條），四週各留 4px 呼吸邊。
        """
        x, y, w, h = el["rect"]
        self.fill_rr(x, y, w, h, el["radius"], (250, 250, 252, 255))
        f = badge_transparent(Image.open(os.path.join(SHARE_SRC,
                                                      "LegislativeYuan.png")))
        k = min((w - 8) / f.width, (h - 8) / f.height)   # 四週各留 4px
        dw, dh = f.width * k, f.height * k               # 設計座標尺寸
        im2 = f.resize((max(1, self.px(dw)), max(1, self.px(dh))), Image.LANCZOS)
        self.ov.alpha_composite(im2, (self.px(x + (w - dw) / 2),
                                      self.px(y + (h - dh) / 2)))

    def title_card(self, el):
        """主標題（2026-11-20 改版）：照 2022 九合一頁眉 leftText 同款 ——
        字級 56、weight 900、**字間距 6**（spacing 只加在字與字之間）、
        純白（T.BG.text）、帶 rgba(0,0,0,0.5) blur14 y+4 投影；
        垂直＝與年份圓盤**同心**（2022：blockCY＝db.y＋boxH/2，boxH＝盤徑）。
        本板標題 13 字比 2022 的 8 字長，放不下時照 2022 自己的 nameScale
        規則：字級與字距**一起**等比縮（headless.js nameScale 同款）。
        """
        x, y, w, h = el["rect"]
        s = "第十一屆立法院立法委員選舉"
        SIZE, SPACING = 56, 6.0
        ws = [self.measure(c, SIZE) / self.s for c in s]
        natural = sum(ws) + SPACING * (len(s) - 1)
        maxw = w - 24                                    # 右側留隙給圓盤文字
        k = min(1.0, maxw / natural)
        size, spacing = SIZE * k, SPACING * k
        # 垂直＝與圓盤同心；基線＝blockCY＋(墨高 ascent−descent)/2（canvas 同款）
        blockCY = y + self.disc_diameter() / 2.0
        _, by0, _, by1 = self.d.textbbox((0, 0), s, font=self.font(size),
                                         anchor="ls")
        a, dd = -by0 / self.s, by1 / self.s
        self._spaced_line(x, blockCY + (a - dd) / 2.0, s, size, spacing,
                          WHITE, shadow=(14, 4, 0.5))

    def disc_diameter(self):
        """2022 dateBlock 盤徑公式：年份數字墨高（actual ascent）× dRatio 1.95。
        year_disc 與 title_card 共用，保證兩者幾何不漂移。"""
        _, by0, _, _ = self.d.textbbox((0, 0), "2024", font=self.num_font(96),
                                       anchor="ls")
        return -by0 / self.s * 1.95

    def _spaced_line(self, x, base_y, s, size, spacing, color, shadow=None):
        """2022 leftText 同款的一行字：逐字繪製、字距 spacing 只加在
        字與字之間（Utils.measureSpaced 同款）；shadow＝(blur, dy, alpha)
        對應 canvas shadowBlur／shadowOffsetY／rgba(0,0,0,alpha)。"""
        ws = [self.measure(c, size) / self.s for c in s]
        total = sum(ws) + spacing * max(0, len(s) - 1)

        def fonts_of(c):
            return self.num_font(size) if ("0" <= c <= "9") else self.font(size)

        asc = max(fonts_of(c).getmetrics()[0] for c in s) / self.s
        desc = max(fonts_of(c).getmetrics()[1] for c in s) / self.s
        if shadow:
            blur, dy, alpha = shadow
            pad = 40.0
            lw = max(1, self.px(total + pad * 2))
            lh = max(1, self.px(asc + desc + pad * 2))
            ox, oy = self.px(x - pad), self.px(base_y - asc - pad)
            layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            pos = x
            for c, wd in zip(s, ws):
                ld.text((self.px(pos) - ox, self.px(base_y) - oy), c,
                        font=fonts_of(c), fill=(0, 0, 0, 255), anchor="ls")
                pos += wd + spacing
            sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            sh.paste((0, 0, 0, 255), (0, 0), layer.getchannel("A"))
            sh = sh.filter(ImageFilter.GaussianBlur(
                max(1, int(self.px(blur) / 2.2))))
            sh.putalpha(sh.getchannel("A").point(lambda v: int(v * alpha)))
            self.ov.alpha_composite(sh, (ox, oy + self.px(dy)))
        pos = x
        for c, wd in zip(s, ws):
            self.text((pos, base_y), c, size, color, anchor="ls")
            pos += wd + spacing
        return total

    def year_disc(self, el):
        """年份圓盤（2026-11-20 改版）：照 2022 九合一縣市長看板頁眉「日期塊」
        的同一套設計與字級（Mayors/2022NineInOne/board/src engine：
        layout.js dateBlock ＋ layers.js HeaderLayer）：
          · 行 1：年份數字 96（數字字型 900）＋「年」32（700），段距 6
          · 行 2：投票日「1月13日」數字 36（900）／「月」「日」23（700），
            段距 5（「月」→「日」10）
          · 兩行行距 lineGap 21；年份基線＝盤心 − 0.70×數字墨高 ＋ 年份行墨高
            （cyRatio 0.70，量墨高用 canvas actualBoundingBox 同一把尺）
          · 圓盤直徑＝年份數字墨高 × 1.95（dRatio），盤頂貼元素上緣
          · 盤面＝emblem 圓徽拉伸鋪滿 ＋ 徑向暗 scrim（rgba(3,7,22)
            0.62/0.38/0.12 @ r 0/0.58/1.0×0.62盤徑）＋盤投影（blur 36、y+10）
          · 文字純白、rgba(0,0,0,0.5) blur 16 y+5 投影
        """
        x, y, w, h = el["rect"]
        cx = x + w / 2.0
        Y_NUM, Y_CJK, Y_GAP = 96, 32, 6.0
        D_NUM, D_CJK, D_GAP = 36, 23, 5.0
        LINE_GAP, D_RATIO, CY_RATIO = 21.0, 1.95, 0.70
        m, d = "1", "13"                       # 投票日 2024-01-13
        ysegs = [("2024", Y_NUM, Y_GAP), ("年", Y_CJK, 0.0)]
        dsegs = [(m, D_NUM, D_GAP), ("月", D_CJK, D_GAP * 2.0),
                 (d, D_NUM, D_GAP), ("日", D_CJK, 0.0)]

        def ink(t, sz):
            """實際墨高（ascent/descent，設計 px）——對應 canvas
            measureRich 的 actualBoundingBoxAscent／Descent。"""
            f = self.num_font(sz) if any("0" <= c <= "9" for c in t) else self.font(sz)
            _, by0, _, by1 = self.d.textbbox((0, 0), t, font=f, anchor="ls")
            return (-by0 / self.s, by1 / self.s)

        digitH = ink("2024", Y_NUM)[0]
        discD = digitH * D_RATIO
        discCY = y + discD / 2.0
        yAsc = max(ink(t, sz)[0] for t, sz, _ in ysegs)
        yDesc = max(ink(t, sz)[1] for t, sz, _ in ysegs)
        dAsc = max(ink(t, sz)[0] for t, sz, _ in dsegs)
        baseY = discCY - CY_RATIO * digitH + yAsc
        dayBaseY = baseY + yDesc + LINE_GAP + dAsc

        # 圓盤投影（2022：shadowColor rgba(0,0,0,0.5)、blur 36、y+10）
        d_ = max(1, self.px(discD))
        dsh = Image.new("RGBA", (d_ + 80, d_ + 80), (0, 0, 0, 0))
        ImageDraw.Draw(dsh).ellipse((40, 40, 40 + d_, 40 + d_), fill=(0, 0, 0, 128))
        dsh = dsh.filter(ImageFilter.GaussianBlur(max(1, int(self.px(36) / 2.2))))
        self.ov.alpha_composite(dsh, (self.px(cx) - d_ // 2 - 40,
                                      self.px(y) - 40 + self.px(10)))

        # 盤面：emblem 拉伸鋪滿（2022 drawImage 同款），徑向 scrim 疊上一層後裁圓
        disc = Image.new("RGBA", (d_, d_), (0, 0, 0, 0))
        em = self.load(os.path.join(ASSETS22, "share", "emblem.png"))
        disc.alpha_composite(em.resize((d_, d_), Image.LANCZOS))
        scrim = Image.new("RGBA", (d_, d_), (0, 0, 0, 0))
        sd = ImageDraw.Draw(scrim)
        SC = (3, 7, 22)
        sr = int(d_ * 0.62)
        sd.ellipse((0, 0, d_ - 1, d_ - 1), fill=SC + (int(255 * 0.12),))
        steps = 48
        for i in range(steps, 0, -1):
            t = i / steps
            a = (0.62 + (0.38 - 0.62) * (t / 0.58) if t <= 0.58 else
                 0.38 + (0.12 - 0.38) * ((t - 0.58) / 0.42))
            r = max(1.0, sr * t)
            sd.ellipse((d_ / 2 - r, d_ / 2 - r, d_ / 2 + r, d_ / 2 + r),
                       fill=SC + (int(255 * a),))
        disc.alpha_composite(scrim)
        mask = Image.new("L", (d_, d_), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, d_ - 1, d_ - 1), fill=255)
        disc.putalpha(mask)
        self.ov.alpha_composite(disc, (self.px(cx) - d_ // 2, self.px(y)))

        # 兩行文字（白字＋投影；整行以 cx 置中、共用基線）
        self._date_line(cx, baseY, ysegs)
        self._date_line(cx, dayBaseY, dsegs)

    def _date_line(self, cx, base_y, segs):
        """2022 日期塊的一行混字級富文本：segs＝[(文字, 字級, 後間距)]，
        整行以 cx 置中、共用 base_y 基線；白字帶 rgba(0,0,0,0.5)
        blur 16、y+5 投影（dateStyle.shadow 同款）。"""
        widths = [self.measure(t, sz) / self.s for t, sz, _ in segs]
        total = sum(widths) + sum(g for _, _, g in segs[:-1])
        x0 = cx - total / 2.0

        def fonts_of(t, sz):
            return self.num_font(sz) if any("0" <= c <= "9" for c in t) \
                else self.font(sz)

        asc = max(fonts_of(t, sz).getmetrics()[0] for t, sz, _ in segs) / self.s
        desc = max(fonts_of(t, sz).getmetrics()[1] for t, sz, _ in segs) / self.s
        pad = 40.0                             # 設計 px：容納投影 blur
        lw = max(1, self.px(total + pad * 2))
        lh = max(1, self.px(asc + desc + pad * 2))
        ox, oy = self.px(x0 - pad), self.px(base_y - asc - pad)
        layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        x = self.px(x0)
        for (t, sz, g), wd in zip(segs, widths):
            ld.text((x - ox, self.px(base_y) - oy), t, font=fonts_of(t, sz),
                    fill=(0, 0, 0, 255), anchor="ls")
            x += self.px(wd + g)
        sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 255), (0, 0), layer.getchannel("A"))
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, int(self.px(16) / 2.2))))
        sh.putalpha(sh.getchannel("A").point(lambda v: int(v * 0.5)))
        self.ov.alpha_composite(sh, (ox, oy + self.px(5)))
        # 本體
        x = x0
        for (t, sz, g), wd in zip(segs, widths):
            self.text((x, base_y), t, sz, WHITE, anchor="ls")
            x += wd + g

    # ---------------------------------------------------------- 總席次卡（綜述）
    def total_card(self, el):
        x, y, w, h = el["rect"]
        # 2026-11-20 新樣張（789×190）：四黨條改**單欄**放左側（順序照樣張：
        # 國民黨 52／民眾黨 8／民進黨 51／無黨籍 2），右側整欄是「未來政黨增加
        # 時的預留區」——本屆留白不畫（使用者指定）。中間＝議場半圓點陣。
        # 條幾何＝樣張實測（231×38、間距 8）×(236/190)：條 287×47、間距 10。
        MARKD = {"中國國民黨": ("kmt", PAL["kmt"]["deep"]),
                 "民主進步黨": ("dpp", PAL["dpp"]["deep"]),
                 "台灣民眾黨": ("tpp", PAL["tpp"]["deep"]),
                 "無黨籍": ("ind", PAL["ind"]["deep"])}
        bw, bh, bgap = 287, 47, 10
        by = y + (h - (4 * bh + 3 * bgap)) / 2.0
        for i, (name, n, pcol) in enumerate(TOTAL):
            sx = x + 24
            sy = by + i * (bh + bgap)
            deep = MARKD[name][1]
            base = pcol
            col = card_ink(base)
            g = L.party_geom_compact(bw, bh, len(str(n)))
            # 滿色條面
            self.fill_rr(sx, sy, bw, bh, 10, base + (255,))
            # 右端深色席次塊（貼條右緣、全高）＋數字
            self.deep_block(sx, sy, bw, bh, 10, g["deep_x"], deep + (255,))
            num = str(n)
            ncol = WHITE if _lum(deep) <= 170 else (16, 26, 44)
            ns = self.fit_text(num, bh * 0.70, g["deep_w"] * 0.86)
            self.text((sx + g["deep_x"] + g["deep_w"] / 2, sy + bh / 2 + ns * 0.035),
                      num, ns, ncol, anchor="mm")
            # 黨徽（不墊白框；無徽檔畫深色圓牌＋首字）
            m = MARKD[name][0]
            ex, ey, es = sx + g["em_x"], sy + g["em_y"], g["em"]
            if m:
                src = self.badge(m)
                self.contain(src, ex, ey, es, es)
            else:
                self.d.ellipse(self.box(ex, ey, es, es), fill=deep + (255,))
                self.text((ex + es / 2, ey + es / 2 + es * 0.02), name[0],
                          es * 0.50, WHITE if _lum(deep) <= 150 else col, anchor="mm")
            # 黨名照樣張「頂滿黨徽→席次塊」，剩餘空隙按字間距均分
            ns_name = self.fit_text(name, bh * 0.78, g["name_right"] - g["name_x"])
            tw = self.measure(name, ns_name) / self.s
            extra = max(0.0, (g["name_right"] - g["name_x"]) - tw)
            cy2 = sy + bh / 2 + ns_name * 0.02
            if extra > 1.5 and len(name) > 1:
                step = extra / (len(name) - 1)
                cx2 = sx + g["name_x"]
                for chn in name:
                    self.text((cx2, cy2), chn, ns_name, col, anchor="lm")
                    cx2 += self.measure(chn, ns_name) / self.s + step
            else:
                self.text((sx + g["name_x"], cy2), name, ns_name, col, anchor="lm")

        # 113 席半圓議場圖：位置照新樣張（半圓中心在卡寬 0.494 處、兩欄之間），
        # 高 201（樣張 162×1.242）；右欄預留區本屆留白
        hh = 201
        hw = hh * HEMICYCLE_AR
        self.hemicycle(x + w * 0.494 - hw / 2.0, y + 11, hw, hh)

    def hemicycle(self, x, y, w, h):
        """議場半圓＝樣張逐點座標（HEMICYCLE_DOTS）等比縮放繪製。

        2026-11-20 新樣張改**政黨分塊**排列：點座標沿用逐點提取值，
        色塊重排 —— 綠（民進黨 51）佔左半、藍（國民黨 52）佔右半；
        青（民眾黨 8）與灰（無黨籍 2）維持原座標的頂點中央位置。
        底部中央白字「113」（0.2388×半圓高＝1920 輸出下 36px）。
        """
        k = h / 1680.0                              # 縮放係數（以樣張高為基準）
        dr = 59.4 * k
        # 政黨分塊（2026-11-20 修正為 53/51/8/1）：kmt/dpp 共 103 點按 nx 排序
        # → 左 51 = dpp、右 52 = kmt；頂點中央兩顆灰點中偏右（nx 0.5275）那顆
        # 歸還深藍 → 藍 53、灰 1（樣張原樣），青 8 維持頂點中央。
        order = sorted(((nx, ny) for p, nx, ny in HEMICYCLE_DOTS
                        if p in ("kmt", "dpp")), key=lambda t: t[0])
        ind_dots = sorted((nx, ny) for p, nx, ny in HEMICYCLE_DOTS if p == "ind")
        dots = ([("dpp", nx, ny) for nx, ny in order[:51]] +
                [("kmt", nx, ny) for nx, ny in order[51:]] +
                [("kmt", ind_dots[-1][0], ind_dots[-1][1])] +
                [("tpp", nx, ny) for p, nx, ny in HEMICYCLE_DOTS if p == "tpp"] +
                [("ind", ind_dots[0][0], ind_dots[0][1])])
        for party, nx, ny in dots:
            px_, py_ = x + nx * w, y + ny * h
            self.d.ellipse(self.box(px_ - dr, py_ - dr, 2 * dr, 2 * dr),
                           fill=HEMICYCLE_COL[party] + (255,))
        nx_, ny_, nh = HEMICYCLE_NUM
        # 樣張是白底黑字；本卡深色底，等價呈現改純白
        self.text((x + nx_ * w, y + ny_ * h), str(TOTAL_SEATS),
                  nh * h, WHITE, anchor="mm")

    def _card_mask(self, w, h, r, bx=None, by=None):
        """卡片形狀（圓角）的遮罩；bx／by 之外的區域挖空，用來做「貼邊」的色塊。"""
        pw_, ph_ = self.px(w), self.px(h)
        mask = Image.new("L", (pw_, ph_), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw_ - 1, ph_ - 1],
                                               radius=self.px(r), fill=255)
        if bx is not None and self.px(bx) > 0:
            ImageDraw.Draw(mask).rectangle([0, 0, self.px(bx), ph_], fill=0)
        if by is not None and self.px(by) > 0:
            ImageDraw.Draw(mask).rectangle([0, 0, pw_, self.px(by)], fill=0)
        return mask

    def deep_block(self, x, y, w, h, r, bx, color):
        """卡片右端的深色席次塊：左邊是直邊、右邊跟卡片同一條圓角外緣。
        直接畫矩形會把圓角切掉，所以先做一張「卡片形狀」的遮罩，再遮掉左半。
        """
        blk = Image.new("RGBA", (self.px(w), self.px(h)), color)
        blk.putalpha(self._card_mask(w, h, r, bx=bx))
        self.ov.alpha_composite(blk, (self.px(x), self.px(y)))

    # ---------------------------------------------------------- 政黨卡（右欄緊湊條）
    def party_card_compact(self, el, d):
        """右欄「不分區」卡（2026-11-20 修訂）：
        [黨徽] 黨名 ＋ 票數·得票率（兩行） [深一階黨色塊＋席次數字]。
        2026-11-20：應使用者要求補回得票數（政黨票）與得票率 ——
        行 1 黨名（基線 0.42h）、行 2 票數＋得票率（基線 0.86h，整行超寬等比縮）。
        黨徽 d0.80h、席次塊近全高的骨架不變。
        """
        c = L.CARD_COMPACT
        x, y, w, h = el["rect"]
        g = L.party_geom_compact(w, h, len(str(d["seats"])))
        base, deep = d["base"], d["deep"]
        col = card_ink(base)

        # 滿色卡面
        self.fill_rr(x, y, w, h, el["radius"], base + (255,))

        # 右端深色席次塊 ＋ 純數字（塊內置中，字級受塊寬約束）
        self.deep_block(x, y, w, h, el["radius"], g["deep_x"], deep + (255,))
        num = str(d["seats"])
        ncol = WHITE if _lum(deep) <= 170 else (16, 26, 44)
        ns = self.fit_text(num, h * c["seat_max"], g["deep_w"] * 0.86)
        self.text((x + g["deep_x"] + g["deep_w"] / 2, y + h / 2 + ns * 0.035),
                  num, ns, ncol, anchor="mm")

        # 黨徽：不墊白框，同色投影托起；無徽檔的政黨畫深色圓牌＋首字
        mark = d.get("mark")
        ex, ey, es = x + g["em_x"], y + g["em_y"], g["em"]
        if mark:
            src = self.badge(mark)
            self.contain(src, ex, ey, es, es)
        else:
            self.d.ellipse(self.box(ex, ey, es, es), fill=deep + (255,))
            self.text((ex + es / 2, ey + es / 2 + es * 0.02), d["cn"][0],
                      es * 0.50, WHITE if _lum(deep) <= 150 else col, anchor="mm")

        # 文字區（黨徽 → 席次塊之間）
        tx, tw = x + g["name_x"], g["name_right"] - g["name_x"]

        # 行 1：黨名
        ns_name = self.fit_text(d["cn"], h * c["name"], tw)
        self.text((tx, y + h * c["base1"]), d["cn"], ns_name, col, anchor="ls")

        # 行 2：票數 ＋ 得票率（整行是一個不可拆的序列，超寬一起等比縮，
        # 不越過席次塊左緣 —— 與大卡的行 3 同一套規則）
        pct = "%.2f%%" % d["pct"]
        vs, cs, ps = h * c["votes"], h * c["votes_cjk"], h * c["pct"]
        cb = self.votes_bold(cs)
        vw = sum(self.measure(t, vs if n else cs,
                              cjk_bold=cb and not n) / self.s
                 for t, n in vote_parts(d["votes"]))
        row = vw + c["pct_gap"] * h + self.measure(pct, ps) / self.s
        if row > tw:
            k = tw / row
            vs, cs, ps = vs * k, cs * k, ps * k
            vw *= k
        self.votes_rich(tx, y + h * c["base2"], d["votes"], vs, cs, col)
        self.text((tx + vw + c["pct_gap"] * h, y + h * c["base2"]),
                  pct, ps, col, anchor="ls")

        # 分組白字標籤（2026-11-20 深夜二修）：卡片**外**右上角 ——
        # 緊貼卡片上緣、右端對齊卡片右緣（頁眉席次卡與右欄卡之間 16px 帶）
        tag = GROUP_TAGS.get(el["key"])
        if tag:
            self.text((x + w - 4, y - 4), tag, group_tag_size(tag), WHITE,
                      anchor="rs")

    # ---------------------------------------------------------- 政黨卡（滿色橫帶）
    def party_card(self, el, d):
        # 右欄「不分區」卡（2026-11-19 晚）：照新樣張統一改緊湊條，走獨立方法
        if el["key"].startswith("right"):
            return self.party_card_compact(el, d)
        """政黨卡＝滿色圓角橫帶，比例照樣張實測（2026-11-19 第五版，911×251）。

        結構＝三行文字（與舊版不同，主席不併第 1 行）：
          行 1  黨名（0.36h，基線 0.36h）
          行 2  票數（數字 0.34h／萬·票 0.15h 同字級，基線 0.693h）
          行 3  主席姓名（0.21h，基線 0.94h）＋「主席」小標（0.117h）＋得票率（0.155h，
                兩者基線 0.88h）—— 無主席時只印得票率
        右側：黨徽 d0.534h（圓心 y 0.691h，跨行 2–3；左欄卡 ×1.15）＋ 全高席次塊
        0.876h（純數字 0.64h）。
        左側：照片框 1:1.58（0.602h×0.952h，近滿高；左欄卡寬再 ×1.1）。
        """
        c = L.CARD
        x, y, w, h = el["rect"]
        leader = d["leader"] not in ("", "—", None)
        # 左欄卡（2026-11-19 指定）：黨徽 ×1.5、照片框寬 ×1.1、上下居中；
        # 右欄完全不變
        left = el["key"].startswith("left")
        g = L.party_geom(w, h, len(str(d["seats"])),
                         em_scale=c["em_scale_left"] if left else 1.0,
                         photo_w_scale=c["photo_w_scale_left"] if left else 1.0,
                         em_vcenter=left)
        base, deep = d["base"], d["deep"]
        col = card_ink(base)

        # ① 滿色卡面
        self.fill_rr(x, y, w, h, el["radius"], base + (255,))

        # ⑥ 右端深色席次塊（全高）＋ 純數字（樣張「37」墨高 0.46h，塊內置中）
        self.deep_block(x, y, w, h, el["radius"], g["deep_x"], deep + (255,))
        num = str(d["seats"])
        ncol = WHITE if _lum(deep) <= 170 else (16, 26, 44)
        ns = h * c["seat"]
        nw = self.measure(num, ns) / self.s
        if nw > g["deep_w"] * 0.84:                    # 塊寬約束（樣張數字佔塊寬 0.80）
            ns *= g["deep_w"] * 0.84 / nw
        self.text((x + g["deep_x"] + g["deep_w"] / 2, y + h * 0.476),
                  num, ns, ncol, anchor="mm")

        # ① 照片框：空的圓角框（淡一階底色 ＋ 亮框線），照片由後製合成
        if g["photo"]:
            px_, py_, pw_, ph_ = g["photo"]
            self.fill_rr(x + px_, y + py_, pw_, ph_, 9, mix(base, col, 0.16))
            self.stroke_rr(x + px_, y + py_, pw_, ph_, 9, mix(base, col, 0.55), 1.5)

        # ⑥ 黨徽：跨行 2–3（圓心 0.691h），不墊白框，同色投影托起
        mark = d.get("mark")
        ex, ey, es = x + g["em_x"], y + g["em_y"], g["em"]
        if mark:
            src = self.badge(mark)
            self.contain(src, ex, ey, es, es)
        else:
            # 沒有徽章檔時的保底：深色圓牌 ＋ 黨名首字
            self.d.ellipse(self.box(ex, ey, es, es), fill=deep + (255,))
            self.text((ex + es / 2, ey + es / 2 + es * 0.02), d["cn"][0],
                      es * 0.50, WHITE if _lum(deep) <= 150 else col, anchor="mm")

        tx, tw = x + g["text_x"], g["text_w"]

        # 行 1：黨名（0.36h）—— 放不下往席次塊左緣收
        name_max = (x + g["deep_x"] - 0.05 * h) - tx
        ns_name = self.fit_text(d["cn"], h * c["name"], name_max)
        self.text((tx, y + h * c["base1"]), d["cn"], ns_name, col, anchor="ls")

        # 行 2：票數（2026-11-19：數字 0.34h 放大；「萬」「票」同字級 0.15h，
        # 整行超寬一起縮）
        vs, cs = h * c["votes"], h * c["votes_cjk"]
        cb2 = self.votes_bold(cs)
        total = sum(self.measure(t, vs if n else cs,
                                 cjk_bold=cb2 and not n) / self.s
                    for t, n in vote_parts(d["votes"]))
        if total > tw:
            k = tw / total
            vs, cs = vs * k, cs * k
        self.votes_rich(tx, y + h * c["base2"], d["votes"], vs, cs, col)

        # 行 3：主席姓名 ＋「主席」小標 ＋ 得票率（左→右序列，照樣張）
        # 整行是一個不可拆的序列，右緣不得越過文字區（壓到黨徽）——
        # 超寬時整行等比縮小（右欄窄卡之前就是這裡溢出壓到徽章）。
        pct = "%.2f%%" % d["pct"]
        if leader:
            ls_, ts_, ps_ = h * c["leader"], h * c["leader_tag"], h * c["pct"]
            lw = self.measure(d["leader"], ls_) / self.s
            tgw = self.measure("主席", ts_) / self.s
            pcw = self.measure(pct, ps_) / self.s
            row3 = lw + c["tag_gap"] * h + tgw + c["pct_gap"] * h + pcw
            if row3 > tw:
                k = tw / row3
                ls_, ts_, ps_ = ls_ * k, ts_ * k, ps_ * k
                lw = self.measure(d["leader"], ls_) / self.s
                tgw = self.measure("主席", ts_) / self.s
            self.text((tx, y + h * c["base3"]), d["leader"], ls_, col, anchor="ls")
            self.text((tx + lw + c["tag_gap"] * h, y + h * c["tag_base"]),
                      "主席", ts_, col, anchor="ls")   # 2026-11-20：小標也改白字
            self.text((tx + lw + c["tag_gap"] * h + tgw + c["pct_gap"] * h,
                       y + h * c["tag_base"]), pct, ps_, col, anchor="ls")
        else:
            self.text((tx, y + h * c["tag_base"]), pct, h * c["pct"], col, anchor="ls")

        # 分組白字標籤（2026-11-20 深夜二修）：卡片**外**右上角 ——
        # 緊貼卡片上緣、右端對齊卡片右緣（頁眉左半與左欄卡之間 16px 帶）
        tag = GROUP_TAGS.get(el["key"])
        if tag:
            self.text((x + w - 4, y - 4), tag, group_tag_size(tag), WHITE,
                      anchor="rs")

    # ---------------------------------------------------------- 其他政黨（2022 樣式）
    def other_list(self, el, rows, title=None, cols=1):
        """小黨清單（2026-11-20 緊湊版七）：`黨名  X萬XXXX票`。

        2026-11-20 深夜回饋 5：
        · 得票率欄**再度移除**（使用者指定），寬度全部讓給字級。
        · 字級**雙向自適應取最大**：寬度束縛（最長黨名＋最寬票數＋間距 ≤ 欄寬，
          參考字級 100 量寬反解 ×0.95 安全係數）× 行高束縛（0.74×rowH，
          2022 密集清單比例），上限放寬到 28、下限 12。
        · 「萬／票」0.62×黨名（數字大漢字小）。
        · 內距收緊（上 12／左右 14／下 8）；黨名單行放不下才拆兩行（平衡拆點）。
        """
        x, y, w, h = el["rect"]
        if title:
            self.text((x + 14, y + 10), title, 11, TEXT_FAINT)
            cy, ch = y + 28, h - 36
        else:
            cy, ch = y + 12, h - 20
        cx, cw = x + 14, w - 28
        cols = max(1, min(cols, len(rows)))
        per = -(-len(rows) // cols)                        # ceil，直式填欄
        columns = [c for c in (rows[i * per:(i + 1) * per]
                               for i in range(cols)) if c]
        nmax = max(len(c) for c in columns)
        rh = ch / nmax
        gap_nv, col_gap = 12.0, 24.0
        col_w = (cw - col_gap * (cols - 1)) / cols

        # ---- 字級自適應：以參考字級 100 量寬，反解「剛好塞滿欄寬」的字級
        #（扣掉 name_x 的 2px 內距；再乘 0.95 安全係數 —— PIL 不同字級的
        #  座標取整會讓臨界值翻車，必須留余量，寧可小一點也不觸發換行）
        REF = 100.0
        w_name = max(self.measure(nm, REF) / self.s for nm, _ in rows)
        w_v = max(sum(self.measure(t, REF * (1.15 if num else 0.62)) / self.s
                      for t, num in vote_parts(v)) for _, v in rows)
        ns_w = (col_w - 2 - gap_nv) / ((w_name + w_v) / REF)
        ns = max(12, min(28, ns_w * 0.95, rh * 0.74))      # 寬度 × 行高 取小
        vs_, cs_ = ns * 1.15, ns * 0.62                    # 票數數字／萬·票（漢字壓小）

        for ci, colrows in enumerate(columns):
            colx = cx + ci * (col_w + col_gap)
            name_x = colx + 2                              # 行首「-」已移除
            vw_all = [sum(self.measure(t, vs_ if num else cs_) / self.s
                          for t, num in vote_parts(v)) for _, v in colrows]
            # 黨名單行可用寬：右緣讓給票數欄；放不下拆兩行不縮字
            lim = colx + col_w - name_x - gap_nv - max(vw_all)

            def wrap(name):
                """單行放不下 → 兩行：在所有放得下的拆點裡選**最平衡**的
                （兩半行長度最接近，避免 8+1 孤字）；全都不放得下回 None。"""
                if self.measure(name, ns) / self.s <= lim:
                    return [name]
                n = len(name)
                best = None
                for k in range(1, n):
                    l1, l2 = name[:k], name[k:]
                    if (self.measure(l1, ns) / self.s <= lim
                            and self.measure(l2, ns) / self.s <= lim):
                        d = abs(n - 2 * k)
                        if best is None or d < best[0]:
                            best = (d, [l1, l2])
                return best[1] if best else None

            names = []                                    # 每列＝[(行文字, 字級), …]
            for name, _ in colrows:
                wl = wrap(name)
                if wl is None:                            # 保底：等比縮到塞得下
                    s1 = self.fit_text(name, ns, lim, min_size=12)
                    names.append([(name, s1)])
                else:
                    names.append([(t, ns) for t in wl])
            # 票數左緣跟著「最長的第一行黨名」走
            col1 = max(name_x + self.measure(nl[0][0], nl[0][1]) / self.s
                       for nl in names) + gap_nv
            lh = ns * 1.2                                 # 兩行黨名的行距
            n = len(colrows)

            for i, ((name, votes), vw) in enumerate(zip(colrows, vw_all)):
                rcy = cy + rh * (i + 0.5)
                lines = names[i]
                if len(lines) == 1:
                    self.text((name_x, rcy), lines[0][0], lines[0][1], WHITE,
                              anchor="lm")
                else:
                    # 兩行黨名：整組在行高內置中，字級不變
                    self.text((name_x, rcy - lh / 2), lines[0][0], lines[0][1],
                              WHITE, anchor="lm")
                    self.text((name_x, rcy + lh / 2), lines[1][0], lines[1][1],
                              WHITE, anchor="lm")
                self.votes_rich(col1, rcy, votes, vs_, cs_, TEXT_DIM, anchor="lm")
                if i < n - 1:
                    self.d.line([(self.px(colx), self.px(round(rcy + rh / 2))),
                                 (self.px(colx + col_w),
                                  self.px(round(rcy + rh / 2)))],
                                fill=RULE, width=max(1, self.px(1)))
            # 欄間淡分隔線
            if ci < len(columns) - 1:
                vx = colx + col_w + col_gap / 2
                self.d.line([(self.px(vx), self.px(cy)),
                             (self.px(vx), self.px(cy + ch))],
                            fill=RULE, width=max(1, self.px(1)))

    def indig_card(self, el):
        """原住民立委（2026-11-20 深夜五修）：**照右上（右欄）政黨卡的設計** ——
        每條＝緊湊政黨卡同款幾何（party_geom_compact ＋ CARD_COMPACT 同一組
        真值，比例完全一致）：[黨徽] 黨名（行 1）＋ 得票率（行 2，黨名正下方）｜
        右側空白處票數（右對齊緊貼席次塊）｜右端深色塊席次數字。
        得票數／得票率字級 ×1.25（INDIG_COMPACT.vote_scale，使用者指定）。
        資料＝INDIG_ALL（平地＋山地合併：票數、席次
        相加、得票率按合併總票數重算），票數降序。
        **沒有就直接空缺留白**（使用者指定）：
        · 沒有徽章檔的政黨（mark 缺）→ 徽位留白，不畫「深色圓牌＋首字」
          的代用品（名字 x 不變，各條黨名對齊）；
        · 不足 6 黨 → 固定 3 行×2 欄（6 黨滿版）column-major 左欄先填滿，
          空格整格留白 —— 2024 現況 3 黨＝左欄滿、右欄全空。
        右上白字分組標籤「原住民」在卡片外上緣；左緣 48、寬 680。
        """
        x, y, w, h = el["rect"]
        ig = L.INDIG_COMPACT
        cc = L.CARD_COMPACT
        cx, cy = x + 14, y + 14
        cw, ch = w - 28, h - 24
        # 分組白字標籤：卡片**外**右上角（緊貼上緣、右端對齊卡片右緣）
        self.text((x + w - 4, y - 4), "原住民", TAG_SIZE, WHITE, anchor="rs")

        rows = 3                                 # 3 行 × 2 欄＝6 黨滿版
        col_w = (cw - ig["gap_col"]) / 2
        bar_h = (ch - (rows - 1) * ig["row_gap"]) / rows
        for ci in range(2):
            bx = cx + ci * (col_w + ig["gap_col"])
            for ri in range(rows):
                idx = ci * rows + ri             # column-major：左欄先填滿
                if idx >= len(INDIG_ALL):
                    continue                     # 沒有就直接空缺留白
                name, votes, pct, seat = INDIG_ALL[idx]
                by = cy + ri * (bar_h + ig["row_gap"])
                base = PARTY_COLOR.get(name, PAL["ind"]["base"])
                deep = PARTY_DEEP.get(name, PAL["ind"]["deep"])
                col = card_ink(base)
                # 滿色條面
                self.fill_rr(bx, by, col_w, bar_h, 10, base + (255,))
                # 右端深色席次塊 ＋ 數字（與右欄政黨卡同一組比例）
                g = L.party_geom_compact(col_w, bar_h, len(str(seat)))
                self.deep_block(bx, by, col_w, bar_h, 10, g["deep_x"],
                                deep + (255,))
                num = str(seat)
                ns = self.fit_text(num, bar_h * cc["seat_max"], g["deep_w"] * 0.86)
                self.text((bx + g["deep_x"] + g["deep_w"] / 2,
                           by + bar_h / 2 + ns * 0.035), num, ns,
                          WHITE if _lum(deep) <= 170 else (16, 26, 44),
                          anchor="mm")
                # 黨徽：有徽章檔才畫；沒有就直接空缺留白（名字 x 不變、對齊）
                mark = PARTY_MARK.get(name)
                if mark and mark in PARTY_BADGE:
                    self.contain(self.badge(mark), bx + g["em_x"], by + g["em_y"],
                                 g["em"], g["em"])
                # 2026-11-20 深夜八修（照使用者樣張逐 px 實測重排）：
                #   行 1 黨名（統一 0.80×＝樣張 ~15px）＋ 行 2 得票率（×1.50 不變）；
                #   票數 ×1.85（≈35px，樣張寬 149px 反解）置於卡片**右下角** ——
                #   右端貼席次塊（deep_x − 2px）、底端貼卡下緣（基線 bar_h − 4px），
                #   中段清空（樣張黑塊＝舊票數位已移除）；
                #   票數壓到得票率「%」時等比縮兜底。
                tx, tw = bx + g["name_x"], g["name_right"] - g["name_x"]
                # 行 1：黨名（2026-11-20 深夜九修：字級再放大 0.80×→0.92×）
                ns = self.fit_text(name, bar_h * cc["name"] * 0.92, tw)
                self.text((tx, by + bar_h * cc["base1"]), name, ns,
                          col, anchor="ls")
                # 行 2（左）：得票率，黨名正下方
                ps = bar_h * cc["pct"] * ig["pct_scale"]
                self.text((tx, by + bar_h * cc["base2"]), pct, ps, col,
                          anchor="ls")
                # 右下角：票數
                vs = bar_h * cc["votes"] * ig["vote_scale"]
                cs = bar_h * cc["votes_cjk"] * ig["vote_scale"]
                cb3 = self.votes_bold(cs)
                vw = sum(self.measure(t, vs if dig else cs,
                                      cjk_bold=cb3 and not dig) / self.s
                         for t, dig in vote_parts(votes))
                right = bx + g["deep_x"] - 2.0               # deep_x 為條內相對座標，須加 bx
                pct_end = tx + self.measure(pct, ps) / self.s
                if right - vw < pct_end + 4.0:               # 不壓「%」兜底
                    k2 = max(0.0, right - pct_end - 4.0) / vw
                    vs, cs = vs * k2, cs * k2
                # 2026-11-20 深夜十修（萬字渲染檢查後修復）：樣張實測萬/票與數字
                # 是**中心對齊**（票心 47＝數字心 47，墨底高於數字墨底 4px），
                # 原先基線對齊會讓萬/票整字下沉（墨頂低數字 9px、墨底反低 2px，
                # 看起來像掉下去）。改逐段 "lm" 中心對齊，中心 0.72h——
                # 數字位置幾乎不動（墨 28–52 vs 原 27–51），萬/票上浮居中。
                self.votes_rich(right, by + bar_h * 0.72, votes, vs, cs, col,
                                align="right", anchor="lm")

    # ---------------------------------------------------------- 地圖
    def map_panel(self, el, path):
        x, y, w, h = el["rect"]
        # 主圖貼框下緣（2026-11-19：使用者指出框內下方有空白 —— 素材 0.727 比
        # 框 0.52「胖」，寬受限後上下各剩 160；下移讓留白集中到上方，輔圖放大頂上）
        self.contain(self.load(path), x, y, w, h, va="bottom")

    def minimap_panel(self, el, path):
        """縮小版輔圖：輔圖 1＝選舉得票級、輔圖 2＝縣市級，壓在兩張主圖的左上角。
        **不鋪底板** —— 素材本身透明底直接疊上，
        主圖墨跡在輔圖空白處照常透出，不會被背景色蓋掉。
        """
        x, y, w, h = el["rect"]
        self.contain(self.load(path), x, y, w, h)

    # ---------------------------------------------------------- 頁尾（已取消）
    # 2026-11-19：使用者要求移除底部說明條 —— 版面下方整塊清空，
    # 政黨卡與地圖直接吃到 1368。資料來源等註記移到 README。

    # ---------------------------------------------------------- 主流程
    def build(self):
        E = L.by_key
        self.flag_card(E("flag"))
        self.title_card(E("title"))
        self.year_disc(E("disc"))
        self.total_card(E("seats"))

        for key, d in zip(("left1", "left2", "left3", "left4"), REGIONAL):
            self.party_card(E(key), d)
        for key, d in zip(("right1", "right2", "right3", "right4"), ATLARGE):
            self.party_card(E(key), d)

        # 「區域 · 其他政黨」「不分區 · 其他政黨」字樣均已移除（使用者指定）
        # 2026-11-20 深夜 9：得票率再度移除，字級自適應放大、縱向擴張。
        self.other_list(E("others_l"), REG_OTHERS, cols=2)
        self.other_list(E("others_r"), ATL_OTHERS)
        self.indig_card(E("indig"))

        # 四張圖各不相同（2026-11-20 依使用者指定換源，素材由 build_map_assets 產出）：
        #   主圖 1＝選區級、主圖 2＝鄉鎮市區級、輔圖 1＝選舉得票級、輔圖 2＝縣市級。
        self.map_panel(E("map1"), os.path.join(A, "tw2024_district.png"))
        self.map_panel(E("map2"), os.path.join(A, "tw2024_township.png"))
        # 縮小版輔圖壓在兩張主圖左上角（後畫才壓得住）
        self.minimap_panel(E("minimap1"), os.path.join(A, "tw2024_election.png"))
        self.minimap_panel(E("minimap2"), os.path.join(A, "tw2024_county.png"))
        # （2026-11-19 第五版）原本單獨抽離島的輔圖 12／14 已隨「不剪裁」指示取消：
        # 金馬面板已隨整張海報保留在主圖內，不再另做 tw2024_islands.png。


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    r = Render(a.scale)
    r.build()
    out = a.out or os.path.join(HERE, "dist", "2024_立法院看板_2560x1440.png")
    print("saved:", out, r.save(out))


if __name__ == "__main__":
    main()
