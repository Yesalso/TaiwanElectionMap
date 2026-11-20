# -*- coding: utf-8 -*-
"""
把鄉鎮市區「唯一色」底圖 Colorful4.png 改造成「第 11 屆區域立法委員 73 選區」底圖。

Colorful4.png 是 3203×4404 的鄉鎮市區圖，368 個鄉鎮市區各一唯一辨識色；
白色 #FFFFFF 為鄉鎮市區界線，黑色 #000000 為縣市界線。

改造方式：線的位置完全不動，只改顏色，不另外描任何線。
    每個鄉鎮市區 → 換成所屬立委選區的顏色
    選區之間的界線（原本的白線）→ 原位置改塗 #FEFEFE
    選區內部的鄉鎮界線 → 以最近的鄉鎮色填補（等於抹線，同原腳本手法）
    真正的縣市界（兩側不同縣市）→ 保留黑色
    25 縣市時期才有的台中市／台中縣、台南市／台南縣、高雄市／高雄縣 黑線，
    因為兩側同屬一個現行縣市，會被判定為「縣市內部」，不會留下黑線。

鄉鎮市區 → 選區 的歸屬，以本專案既有資料為準：
    LegislationYuan/2024DistrictLegislator/data/1/<縣市>.xlsx
        13 個縣市（台北、新北、基隆、宜蘭、桃園除外…見下）的村里級得票表，
        每列一個村里，首欄即「選舉區別」，因此可直接數出「某鄉鎮的村里
        分別落在哪些選區」。
    LegislationYuan/2024DistrictLegislator/data/第11屆…第1選舉區….xlsx
        其餘 5 個縣市（桃園市、新竹縣、苗栗縣、彰化縣、台中市）只有「第 1
        選區」的村里清單，用於核對；其餘選區依中選會公告之鄉鎮市區組成
        寫成 DISTRICT_RULES，被拆分鄉鎮的村里數則以 SPLIT_VILLAGES 記錄
        （桃園區、中壢區、竹北市三者，村里數均已用上表與各里彙總核對）。

拆分規則（本腳本的核心）：
    一個鄉鎮市區若被拆到多個選區，整塊鄉鎮市區歸給「村里數最多」的那一區。
    例：三重區 新北2＝16里、新北3＝103里 → 三重區整體歸新北3。
    因此本圖是「鄉鎮市區級」的選區圖，選區界線一定沿著鄉鎮市區界走。

做法：
    1. 建表：368 鄉鎮市區 → 選區（1..73），並記錄各選區的村里數明細
    2. 以顏色為鍵把每個像素對應到所屬選區 → 選區標籤圖
    3. 每個選區填一種顏色（相鄰選區色差最大化）
    4. 選區分界處的原白線改塗 #FEFEFE、其餘線抹掉、真縣市界留黑

共用引擎見 county_map_base.py；22／25 縣市版見 make_22county_map.py、
make_25county_map.py。

執行：
    py make_73district_map.py
"""
import glob
import os
import re
from collections import Counter, OrderedDict, defaultdict

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

import county_map_base as base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(BASE_DIR)
SRC_PNG = os.path.join(BASE_DIR, "Colorful4.png")
CORR_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence.xlsx")
DIST_DATA_DIR = os.path.join(PROJ_DIR, "LegislationYuan", "2024DistrictLegislator", "data")
DIST_DATA_SUB = os.path.join(DIST_DATA_DIR, "1")      # 13 縣市的村里級資料
ATL_DATA_DIR = os.path.join(PROJ_DIR, "LegislationYuan", "2024Legislator-at-Large", "data")
OUT_PNG = os.path.join(BASE_DIR, "Colorful73.png")
OUT_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence_73.xlsx")

# 本圖不另外描線：選區界線直接沿用原圖鄉鎮白線的位置，只把顏色換掉；
# 選區內部跨鄉鎮的線以選區色蓋掉；兩側不同縣市的黑線保留。
# 界線色 #FEFEFE（與原圖純白 #FFFFFF 的鄉鎮界線區隔）。
DISTRICT_LINE_RGB = (0xFE, 0xFE, 0xFE)
LINE_GROW = 0          # 接縫再向外擴張幾次（0 = 約 2px，與原白線同寬）
KEEP_COUNTY_BLACK = True   # True：真正的縣市界保留黑線；False：一律 #FEFEFE

# 對照表／圖例的固定順序（北→南、本島→外島），與 22 縣市版一致
COUNTY_ORDER = [
    "臺北市", "新北市", "基隆市", "桃園市", "新竹縣", "新竹市", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣",
    "臺南市", "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣",
]

# 全縣市一個選區（第 11 屆）
SINGLE_DISTRICT = {"新竹市", "澎湖縣", "金門縣", "連江縣"}

# ===================== 5 個縣市：中選會公告的選區組成 =====================
# 只列「整個鄉鎮市區都歸該選區」者；被拆分的鄉鎮見 SPLIT_VILLAGES。
DISTRICT_RULES = {
    "桃園市": {
        1: ["蘆竹區", "龜山區"],                       # ＋桃園區 15 里
        2: ["大園區", "觀音區", "新屋區", "楊梅區"],
        3: [],                                          # ＋中壢區 76 里
        4: [],                                          # ＋桃園區 67 里
        5: ["平鎮區", "龍潭區"],
        6: ["八德區", "大溪區", "復興區"],              # ＋中壢區 12 里
    },
    "新竹縣": {
        1: ["新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", "芎林鄉", "尖石鄉"],  # ＋竹北市 12 里
        2: ["竹東鎮", "橫山鄉", "北埔鄉", "峨眉鄉", "寶山鄉", "五峰鄉"],  # ＋竹北市 19 里
    },
    "苗栗縣": {
        1: ["竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", "造橋鄉", "西湖鄉",
            "三義鄉", "銅鑼鄉"],
        2: ["苗栗市", "頭份市", "公館鄉", "大湖鄉", "卓蘭鎮", "三灣鄉",
            "獅潭鄉", "泰安鄉", "南庄鄉", "頭屋鄉"],
    },
    "彰化縣": {
        1: ["線西鄉", "伸港鄉", "和美鎮", "鹿港鎮", "福興鄉", "秀水鄉"],
        2: ["彰化市", "花壇鄉", "芬園鄉"],
        3: ["北斗鎮", "溪州鄉", "二林鎮", "芳苑鄉", "大城鄉", "竹塘鄉",
            "溪湖鎮", "埔心鄉", "埔鹽鄉", "埤頭鄉"],
        4: ["田中鎮", "田尾鄉", "社頭鄉", "永靖鄉", "員林市", "大村鄉",
            "二水鄉"],
    },
    "臺中市": {
        1: ["大甲區", "大安區", "外埔區", "清水區", "梧棲區"],
        2: ["沙鹿區", "龍井區", "大肚區", "烏日區", "霧峰區"],
        3: ["后里區", "神岡區", "大雅區", "潭子區"],
        4: ["西屯區", "南屯區"],
        5: ["北區", "北屯區"],
        6: ["中區", "東區", "南區", "西區"],
        7: ["太平區", "大里區"],
        8: ["豐原區", "石岡區", "東勢區", "新社區", "和平區"],
    },
}

# 被拆分的鄉鎮市區：{選區: 村里數}（總和須等於該鄉鎮的村里數）
SPLIT_VILLAGES = {
    ("桃園市", "桃園區"): {1: 15, 4: 67},
    ("桃園市", "中壢區"): {3: 76, 6: 12},
    ("新竹縣", "竹北市"): {1: 12, 2: 19},
}


# ===================== 名稱工具 =====================
# 對照表（Name_Color_Correspondence.xlsx）的「地名」欄是簡轉繁的產物，出現
# 八裡／萬裡／佳裡／埔裡／水裡／太麻裡、鹿穀、二侖、鬥六、鬥南、樸子、滿洲、
# 恒春、玉裡、富裡 等異體寫法；村里級資料則是官方寫法。比對時先把兩邊
# 收斂到同一組字，顯示時則用官方寫法。
NORM_REPLACE = str.maketrans({
    "臺": "台", "裡": "里", "穀": "谷", "侖": "崙", "鬥": "斗",
    "樸": "朴", "恒": "恆", "洲": "州", "後": "后", "莊": "庄",
})


def norm(s):
    """比對用：去空白、收斂異體字。"""
    return str(s).strip().translate(NORM_REPLACE).replace("　", "")


def town_key(s):
    """比對用：再去掉「鄉／鎮／市／區」後綴（對照表有把玉里「鎮」寫成「鄉」的情形）。"""
    t = norm(s)
    return t[:-1] if t and t[-1] in "鄉鎮市區" else t


def official(name):
    """輸出用：台→臺（僅四個縣市用「臺」）。"""
    return (name.replace("台", "臺")
            if norm(name) in ("台北市", "台中市", "台南市", "台東縣") else name)


def district_name(county, no, n_district):
    if n_district == 1:
        return f"{official(county)}選舉區"
    return f"{official(county)}第{no}選舉區"


# ===================== 1. 讀村里級資料（13 縣市） =====================
def load_village_rows():
    """回傳 {正規化(縣市,鄉鎮市區): {county, town, cnt:{選區別: 村里數}}}。"""
    table = {}
    files = sorted(glob.glob(os.path.join(DIST_DATA_SUB, "*.xlsx")))
    for path in files:
        county = os.path.splitext(os.path.basename(path))[0]
        if "得票率" in county or "整理" in county:
            continue
        df = pd.read_excel(path, header=None)
        if df.shape[1] < 3:
            continue
        body = df.iloc[1:]
        head = str(df.iloc[0, 0]).strip()
        if "選舉區" not in head and "選區" not in head:
            body = df            # 少數檔案沒有表頭列
        per_town = defaultdict(Counter)
        for _, r in body.iterrows():
            dist = str(r.iloc[0]).strip()
            town = str(r.iloc[1]).strip()
            vill = str(r.iloc[2]).strip()
            if "選舉區" not in dist or town in ("nan", "") or vill in ("nan", ""):
                continue
            per_town[town][dist] += 1
        for town, cnt in per_town.items():
            table[(norm(county), town_key(town))] = {
                "county": county, "town": town, "cnt": dict(cnt)}
    return table


# ===================== 2. 合併成 368 鄉鎮市區 → 選區 =====================
def load_town_village_totals():
    """從 2024 不分區政黨票的「各里彙總」補齊各鄉鎮市區的村里總數。

    data/1 只涵蓋 13 個縣市；桃園、新竹縣、苗栗、彰化、台中、澎湖、金門、
    連江沒有村里級明細，村里總數改由不分區（全國性、每村里一列）補上，
    這樣對照表的「村里數」欄才不會空白。
    """
    totals = {}
    for path in sorted(glob.glob(os.path.join(ATL_DATA_DIR, "2024*_得票率.xlsx"))):
        try:
            df = pd.read_excel(path, sheet_name="各里彙總")
        except Exception:
            continue
        if "鄉(鎮、市、區)別" not in df.columns:
            continue
        county = os.path.basename(path)[4:-len("_得票率.xlsx")]
        c = county[:-1] if county.endswith("市") and len(county) > 2 else county
        for town, n in df["鄉(鎮、市、區)別"].astype(str).str.strip().value_counts().items():
            for key in {(norm(county), town_key(town)), (norm(c), town_key(town))}:
                totals.setdefault(key, int(n))
    return totals


def build_township_table(rows):
    """rows: base.load_correspondence 的結果。回傳整併後的鄉鎮市區清單。"""
    village = load_village_rows()
    totals = load_town_village_totals()

    # 縣市 → 該縣市有幾個選區
    n_district = {}
    for (nc, _), info in village.items():
        nos = [int(re.search(r"第(\d+)選舉區", d).group(1))
               for d in info["cnt"] if "第" in d]
        n_district[nc] = max(nos) if nos else 1
    for c in COUNTY_ORDER:
        if c in SINGLE_DISTRICT:
            n_district[norm(c)] = 1
        elif c in DISTRICT_RULES:
            n_district[norm(c)] = max(DISTRICT_RULES[c])

    # SPLIT_VILLAGES 的鄉鎮先建好
    split_map = {}
    for (county, town), cnt in SPLIT_VILLAGES.items():
        split_map[(norm(county), town_key(town))] = cnt

    towns = []
    for r in rows:
        county = official(r["county22"].strip())
        town = r["town"].strip()
        nkey = (norm(county), town_key(town))
        item = {"county": county, "town": town, "hex": r["hex"], "id": r["id"],
                "n_district": n_district[norm(county)]}

        if nkey in village:                              # (a) 村里級資料
            info = village[nkey]
            item["town"] = info["town"]                  # 用官方寫法
            detail = OrderedDict()
            for d, n in sorted(info["cnt"].items(), key=lambda kv: -kv[1]):
                no = int(re.search(r"第(\d+)選舉區", d).group(1)) if "第" in d else 1
                detail[no] = detail.get(no, 0) + n
            total = sum(detail.values())
            item["village_total"] = total
            item["village_by_district"] = dict(detail)
            item["split"] = len(detail) > 1
            item["majority"] = max(detail.items(), key=lambda kv: (kv[1], -kv[0]))[0]
        elif nkey in split_map:                          # (b) 手動拆分的鄉鎮
            cnt = split_map[nkey]
            item["village_total"] = sum(cnt.values())
            item["village_by_district"] = dict(cnt)
            item["split"] = len(cnt) > 1
            item["majority"] = max(cnt.items(), key=lambda kv: (kv[1], -kv[0]))[0]
        else:                                            # (c) 整個鄉鎮在同一選區
            no = None
            for d, towns_in in DISTRICT_RULES.get(county, {}).items():
                if town_key(town) in {town_key(x) for x in towns_in}:
                    no = d
                    break
            if no is None:
                if county not in SINGLE_DISTRICT:
                    raise ValueError(f"鄉鎮市區未歸屬任何選區：{county} {town}")
                no = 1
            item["village_total"] = None
            item["village_by_district"] = {no: None}
            item["split"] = False
            item["majority"] = no

        item["district_no"] = item["majority"]
        # 村里總數：村里級資料沒有的，用不分區各里彙總補
        if not item["village_total"]:
            item["village_total"] = totals.get(nkey)
        elif nkey in totals and totals[nkey] != item["village_total"]:
            print(f"    ⚠️ 村里數不一致：{county}{item['town']}"
                  f"（村里級 {item['village_total']} vs 各里彙總 {totals[nkey]}）")
        towns.append(item)

    # 檢查：每個鄉鎮都要有歸屬，每個選區至少一個鄉鎮
    used = defaultdict(list)
    for t in towns:
        used[(t["county"], t["district_no"])].append(t["town"])
    empty = [(c, d) for c, rules in DISTRICT_RULES.items() for d in rules
             if not used.get((c, d))]
    if empty:
        raise ValueError(f"以下選區在鄉鎮整併後變成空選區：{empty}")
    return towns


# ===================== 3. 選區總表（固定順序 1..73） =====================
def build_districts(towns):
    group = defaultdict(list)
    for t in towns:
        group[(t["county"], t["district_no"])].append(t)

    districts = []
    for county in COUNTY_ORDER:
        n = max(t["n_district"] for t in towns if t["county"] == county)
        for no in range(1, n + 1):
            members = group.get((county, no), [])
            districts.append({
                "index": len(districts) + 1,
                "county": county,
                "no": no,
                "name": district_name(county, no, n),
                "towns": sorted([m["town"] for m in members]),
                "members": members,
            })
    for d in districts:
        for m in d["members"]:
            m["district"] = d["index"]
    return districts


# ===================== 4. 配色 =====================
def pick_palette_n(n):
    return base.pick_palette(n, avoid_rgb=(base.CANVAS_COLOR,
                                           base.BORDER_BLACK,
                                           base.COAST_BLUE))


def assign_colors(districts, pairs, seed=20261120):
    """73 色一色一選區：先挑「全域最小色差最大」的 73 色，再排成
    「相鄰選區色差最大」的對應（貪婪初始＋兩兩交換爬山）。"""
    n = len(districts)
    palette = pick_palette_n(n)
    assert len(set(palette)) == n, "色盤必須一色一選區"
    lab = base.rgb_to_lab(np.array(palette, dtype=np.uint8))
    D = np.linalg.norm(lab[:, None, :] - lab[None, :, :], axis=-1)

    ed = sorted(pairs)
    ei = np.array([a - 1 for a, b in ed], dtype=np.int64)
    ej = np.array([b - 1 for a, b in ed], dtype=np.int64)

    nbr = defaultdict(list)
    for a, b in ed:
        nbr[a - 1].append(b - 1)
        nbr[b - 1].append(a - 1)
    deg = np.array([len(nbr[i]) for i in range(n)])

    def score(a):
        return float(D[a[ei], a[ej]].min())

    rng = np.random.default_rng(seed)
    best_a, best_s = None, -1.0
    for _ in range(10):
        # --- 貪婪初始（度數大的先挑顏色，且每個顏色只用一次）---
        order = np.argsort(-(deg + rng.random(n) * 1.5))
        a = -np.ones(n, dtype=np.int64)
        used = np.zeros(n, dtype=bool)
        for v in order:
            assigned = [u for u in nbr[v] if a[u] >= 0]
            dist = (D[:, a[assigned]].min(axis=1) if assigned
                    else np.full(n, 1e9))
            cand = np.where(used, -1.0, dist)
            a[v] = int(np.argmax(cand)) if (cand >= 0).any() else int(np.argmax(dist))
            used[a[v]] = True

        # --- 交換爬山：只交換兩個選區的顏色，保持一色一選區 ---
        s = score(a)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                for j in range(i + 1, n):
                    a[i], a[j] = a[j], a[i]
                    ns = score(a)
                    if ns > s + 1e-9:
                        s, improved = ns, True
                    else:
                        a[i], a[j] = a[j], a[i]
        if s > best_s:
            best_s, best_a = s, a.copy()

    colors = [palette[int(p)] for p in best_a]
    return colors, best_s


# ===================== 5. 標籤圖與界線 =====================
def build_label_map(rgb, towns):
    """回傳 (選區標籤圖, 縣市標籤圖)，0 = 非鄉鎮色。"""
    c2d, c2c = {}, {}
    for t in towns:
        r, g, b = base.hex2rgb(t["hex"])
        key = (r << 16) | (g << 8) | b
        c2d[key] = t["district"]
        c2c[key] = t["county_index"]

    key = ((rgb[..., 0].astype(np.int32) << 16)
           | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2].astype(np.int32))
    uniq, inv = np.unique(key.ravel(), return_inverse=True)
    lut_d = np.array([c2d.get(int(u), 0) for u in uniq], dtype=np.uint8)
    lut_c = np.array([c2c.get(int(u), 0) for u in uniq], dtype=np.uint8)
    return lut_d[inv].reshape(key.shape), lut_c[inv].reshape(key.shape)


def line_mask(arr, label):
    """原圖的界線像素（白＝鄉鎮界、黑＝縣市界），排除外框／比例尺。

    用「8 鄰域有 3 個以上鄉鎮色」把畫布外框、小圖框、比例尺的白/黑像素濾掉。
    """
    land = label > 0
    is_line = (np.all(arr == np.array(base.LINE_WHITE, dtype=np.uint8), axis=-1)
               | np.all(arr == np.array(base.BORDER_BLACK, dtype=np.uint8), axis=-1))
    nb = np.zeros(arr.shape[:2], dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nb += np.roll(np.roll(land, dy, 0), dx, 1).astype(np.uint8)
    return is_line & (nb >= base.LINE_MIN_TOWN_NEIGHBORS)


def fill_lines(label, lines):
    """把界線像素填成「最近的鄉鎮所屬選區」，等於把線抹掉。"""
    land = label > 0
    _, ind = ndi.distance_transform_edt(~land, return_indices=True)
    filled = label.copy()
    filled[lines] = label[ind[0][lines], ind[1][lines]]
    return filled


def seam_mask(label, grow=0):
    """同一張標籤圖上「相鄰不同」的接縫；grow = 再向外擴張次數。"""
    m = np.zeros(label.shape, dtype=bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        s = np.roll(label, (dy, dx), (0, 1))
        m |= (label != s) & (label > 0) & (s > 0)
    m[[0, -1], :] = False
    m[:, [0, -1]] = False
    if grow > 0:
        m = ndi.binary_dilation(m, structure=ndi.generate_binary_structure(2, 1),
                                iterations=grow)
    return m


def render(src_png, filled, filled_county, lines, districts):
    """線的位置不動，只改線的顏色：

      - 兩側不同選區的界線 → 原位置改塗 #FEFEFE
      - 同一選區內部的界線 → 用選區色蓋掉（等於抹線）
      - 真正的縣市界（兩側不同縣市）→ 保留原來的黑色

    Colorful4.png 是 25 縣市時期的圖，台中市／台中縣、台南市／台南縣、
    高雄市／高雄縣 之間那條黑線現在已經不存在；因為兩側同屬一個現行縣市，
    會被當成「縣市內部」處理，所以不會留下黑線。
    """
    arr = np.array(Image.open(src_png).convert("RGB"))
    out = arr.copy()
    for d in districts:
        out[filled == d["index"]] = d["color"]

    seam = seam_mask(filled, LINE_GROW) & lines
    out[seam] = DISTRICT_LINE_RGB

    # 縣市界：把黑色線裡「兩側不同縣市」的部分留下來
    is_black = np.all(arr == np.array(base.BORDER_BLACK, dtype=np.uint8), axis=-1)
    keep = (is_black & seam_mask(filled_county, 1) & lines
            if KEEP_COUNTY_BLACK else np.zeros_like(is_black))
    out[keep] = (0, 0, 0)
    return arr, out, int(seam.sum()), int(keep.sum())


# ===================== 6. 輸出對照表 =====================
def save_xlsx(path, districts, towns):
    summary = []
    for d in districts:
        vills = []
        for m in d["members"]:
            v = m["village_by_district"].get(d["no"])
            if v is None:                      # 全鄉鎮同一選區時只知村里總數
                v = 0 if m["split"] else (m["village_total"] or 0)
            vills.append(v)
        vsum = sum(vills)
        summary.append({
            "序號": d["index"],
            "選舉區": d["name"],
            "顏色 (HEX)": base.rgb2hex(d["color"]),
            "縣市": d["county"],
            "鄉鎮市區數": len(d["towns"]),
            "村里數": int(vsum) if vsum else "",
            "鄉鎮市區": "、".join(d["towns"]),
            "備註": "" if d["towns"] else "整併後無鄉鎮市區（村里全部併入同鄉鎮的其他選區）",
        })
    detail = []
    for t in towns:
        vb = t["village_by_district"]
        # 對照表（13 縣市）是村里級；手動規則只知村里數
        if t["split"]:
            txt = " / ".join(f"第{k}選區 {v}里" for k, v in sorted(vb.items()))
        else:
            txt = ""
        detail.append({
            "鄉鎮市區": t["town"],
            "縣市": t["county"],
            "選區序號": t["district"],
            "選舉區": next(d["name"] for d in districts if d["index"] == t["district"]),
            "總村里數": int(t["village_total"]) if t["village_total"] else "",
            "被拆分": "是" if t["split"] else "",
            "各選區村里數": txt,
            "歸屬依據": "村里數最多" if t["split"] else "全鄉鎮同一選區",
            "原色 (HEX)": t["hex"],
            "新色 (HEX)": base.rgb2hex(districts[t["district"] - 1]["color"]),
            "區域 ID": t["id"],
        })
    with pd.ExcelWriter(path) as xw:
        pd.DataFrame(summary).to_excel(xw, sheet_name="選區彙總", index=False)
        pd.DataFrame(detail).to_excel(xw, sheet_name="鄉鎮市區明細", index=False)


# ===================== 主流程 =====================
def main():
    print("=" * 70)
    print("  Colorful4.png → 第 11 屆區域立法委員 73 選區底圖")
    print("=" * 70)

    rows = base.load_correspondence(CORR_XLSX)
    towns = build_township_table(rows)
    districts = build_districts(towns)
    print(f"  鄉鎮市區        : {len(towns)} 個")
    print(f"  選區            : {len(districts)} 個"
          f"（{len({d['county'] for d in districts})} 縣市）")

    county_index = {c: i + 1 for i, c in enumerate(COUNTY_ORDER)}
    for t in towns:
        t["county_index"] = county_index[t["county"]]
    for d in districts:
        d["county_index"] = county_index[d["county"]]

    arr = np.array(Image.open(SRC_PNG).convert("RGB"))
    H, W = arr.shape[:2]
    dlabel, clabel = build_label_map(arr, towns)
    if (dlabel == 0).all():
        raise ValueError("底圖與對照表顏色不符，無法上標籤")
    print(f"  底圖            : {W}×{H}，陸地像素 {int((dlabel > 0).sum())}")

    lines = line_mask(arr, dlabel)
    filled = fill_lines(dlabel, lines)
    filled_county = fill_lines(clabel, lines)
    print(f"  界線像素        : {int(lines.sum())} px（白線＋黑線，外框／比例尺已排除）")

    pairs = base.county_adjacency(dlabel)
    print(f"  選區相鄰關係    : {len(pairs)} 組")

    colors, min_de = assign_colors(districts, pairs)
    for d, c in zip(districts, colors):
        d["color"] = c
    print(f"  配色            : 相鄰選區最小色差 ΔE={min_de:.1f}（Lab）")

    _, out, n_seam, n_black = render(SRC_PNG, filled, filled_county, lines, districts)
    print(f"  選區界線換色    : {n_seam} px → #FEFEFE")
    print(f"  保留縣市界黑線  : {n_black} px（僅兩側不同縣市者）")
    Image.fromarray(out).save(OUT_PNG)
    print(f"  輸出底圖        : {OUT_PNG}")

    save_xlsx(OUT_XLSX, districts, towns)
    print(f"  輸出對照表      : {OUT_XLSX}")

    print("-" * 70)
    print("  驗證：")
    covered = set(np.unique(filled).tolist()) - {0}
    lacks = [d["name"] for d in districts if d["index"] not in covered]
    print(f"    在底圖上有像素的選區: {len(covered)}/{len(districts)}"
          f"{'，缺：' + str(lacks) if lacks else ''}")
    print(f"    整併後變成 0 鄉鎮的選區: "
          f"{[d['name'] for d in districts if not d['towns']]}")
    splits = [t for t in towns if t["split"]]
    print(f"    被拆分的鄉鎮市區: {len(splits)} 個")
    for t in splits:
        vb = " / ".join(f"第{k}選區 {v}里" for k, v in sorted(t["village_by_district"].items()))
        print(f"      {t['county']}{t['town']:<5s} {vb}  → 歸第{t['district_no']}選區")
    print(f"    總村里數        : "
          f"{sum(t['village_total'] for t in towns if t['village_total'])}")
    print("=" * 70)


if __name__ == "__main__":
    main()
