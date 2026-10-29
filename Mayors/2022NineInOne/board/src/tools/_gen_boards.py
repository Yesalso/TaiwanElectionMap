# -*- coding: utf-8 -*-
"""_gen_boards.py —— 2022 九合一縣市長選舉 22 縣市看板建置器。

★ 從零編寫（與 Video/ 的 _gen_*.py 無關）。

讀四份資料，為每縣市產一場看板：
  1. data/<縣>_*.xlsx —— 縣市級別得票（候選人票數/得票率/當選人）
  2. Wikipedia.txt —— 該縣市 選舉人數/投票數/有效票/無效票/投票率
  3. county_map.CAND_PARTY —— 候選人黨籍（色階組別）
  4. 2022县市长选举简报.md —— 「四、各县市结果总表」的時任首長（頁眉右側色卡）

輸出（board/src/boards/<id>/ 只放 meta.json；產物進 dist/boards/<id>/）：
  board/src/boards/<id>/meta.json
  board/dist/boards/<id>/board.js       （window.BOARD，canonical）
  board/dist/boards/<id>/board.files.js （邏輯素材名 → 實際路徑）
  board/dist/boards/<id>/index.html     （薄殼，複製 template）

場次 id：`2022-county-<拼音?>` → 改用 `<縣市>` 直接當 id（純中文，render 檔名消毒後
變全底線）。為避免消毒歧義，id 用英文 slug：`2022-<slug>`。

執行：
    python src/tools/_gen_boards.py               # 全部 22 縣市
    python src/tools/_gen_boards.py 臺北市         # 只做臺北市
"""
import json
import os
import re
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import county_map as CM

BOARD = CM.ROOT
SRC_BOARDS = os.path.join(BOARD, "src", "boards")
DIST_BOARDS = os.path.join(BOARD, "dist", "boards")
ENGINE_INDEX = os.path.join(BOARD, "src", "templates", "index.html")

# 場次 id slug（英文，供檔名/資料夾名用，避免中文路徑消毒歧義）
COUNTY_SLUG = {
    "臺北市": "taipei", "新北市": "newtaipei", "桃園市": "taoyuan", "臺中市": "taichung",
    "臺南市": "tainan", "高雄市": "kaohsiung", "基隆市": "keelung", "新竹市": "hsinchucity",
    "新竹縣": "hsinchucounty", "苗栗縣": "miaoli", "彰化縣": "changhua", "南投縣": "nantou",
    "雲林縣": "yunlin", "嘉義市": "chiayicity", "嘉義縣": "chiayicounty", "宜蘭縣": "yilan",
    "花蓮縣": "hualien", "臺東縣": "taitung", "屏東縣": "pingtung", "澎湖縣": "penghu",
    "金門縣": "kinmen", "連江縣": "lienchiang",
}

# Wikipedia.txt（簡體）標題縣市名 → 繁體全稱 key
WIKI_TITLE_MAP = {
    "台北市": "臺北市", "新北市": "新北市", "桃园市": "桃園市", "台中市": "臺中市",
    "台南市": "臺南市", "高雄市": "高雄市", "基隆市": "基隆市", "宜兰县": "宜蘭縣",
    "新竹县": "新竹縣", "新竹市": "新竹市", "苗栗县": "苗栗縣", "彰化县": "彰化縣",
    "南投县": "南投縣", "云林县": "雲林縣", "嘉义县": "嘉義縣", "嘉义市": "嘉義市",
    "屏东县": "屏東縣", "花莲县": "花蓮縣", "台东县": "臺東縣", "澎湖县": "澎湖縣",
    "金门县": "金門縣", "连江县": "連江縣",
}

# 政黨英文全稱
PARTY_EN = {
    "中國國民黨": "Kuomintang", "民主進步黨": "Democratic Progressive Party",
    "台灣民眾黨": "Taiwan People's Party", "新黨": "New Party",
    "親民黨": "People First Party", "無黨籍": "Independent",
    "時代力量": "New Power Party",
}
PARTY_SHORT_EN = {"中國國民黨": "KMT", "民主進步黨": "DPP", "台灣民眾黨": "TPP",
                  "新黨": "NSC", "親民黨": "PFP", "無黨籍": "IND",
                  "時代力量": "NPP"}


# ---------------------------------------------------------------- 簡報 md（時任首長）
# 簡報是簡體，「時任首長」欄形如「黄敏惠（中国国民党）」「陈章贤（无党籍，代理）」。
# 名字要用繁體上板：只覆蓋 22 位時任首長會用到的字，逐字對照、不多做轉換。
S2T_NAME = {
    "黄": "黃", "杨": "楊", "饶": "饒", "庆": "慶", "铃": "鈴",
    "卢": "盧", "陈": "陳", "迈": "邁", "张": "張", "丽": "麗",
    "郑": "鄭", "灿": "燦", "刘": "劉", "应": "應", "镇": "鎮",
    "赖": "賴", "伟": "偉", "贤": "賢", "浯": "浯",
}

# 簡報的政黨全稱（簡體）→ 本專案用的繁體全稱
PARTY_S2T = {
    "中国国民党": "中國國民黨", "民主进步党": "民主進步黨",
    "台湾民众党": "台灣民眾黨", "无党籍": "無黨籍",
    "时代力量": "時代力量", "新党": "新黨", "亲民党": "親民黨",
}

_INCUMBENT_CACHE = {}


def _to_trad(name):
    return "".join(S2T_NAME.get(ch, ch) for ch in name)


def parse_brief_incumbents():
    """解析簡報「四、各县市结果总表」的『时任首长（党籍）』。

    回傳 {繁體縣市key: {name, party, partyShort, acting}}。
    只看「时任首长（党籍）」那一欄 —— 頁眉顯示的是**選舉當下在位者**，
    不是當選人（當選人已在左右主卡上，不必在頁眉重複）。

    ★ 2026-10-29：上層簡報換成全國看板版（無此欄），改讀
      `county_map.brief_md_with_incumbent()`（優先 Video2022/docs 的詳細版）。
    """
    if _INCUMBENT_CACHE:
        return _INCUMBENT_CACHE

    brief = CM.brief_md_with_incumbent()
    lines = open(brief, encoding="utf-8").read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "时任首长" in ln and ln.lstrip().startswith("|"):
            start = i + 2                      # 跳過表頭與 |---| 分隔行
            break
    if start is None:
        raise RuntimeError("簡報找不到「时任首长」表頭：%s" % brief)

    for ln in lines[start:]:
        if not ln.lstrip().startswith("|"):
            break                              # 表格結束
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        county = WIKI_TITLE_MAP.get(cells[1])
        if not county:
            continue                           # 非 22 縣市（表尾註解等）
        cell = cells[2]                        # 時任首長（黨籍）
        m = re.match(r"^(.+?)（(.+?)）$", cell)
        if not m:
            raise RuntimeError("時任首長欄格式異常：%r" % cell)
        raw_name, raw_party = m.group(1).strip(), m.group(2).strip()
        extra = re.split(r"[，,、]", raw_party)
        party_raw, notes = extra[0].strip(), "".join(extra[1:])
        party = PARTY_S2T.get(party_raw)
        if not party:
            raise RuntimeError("未知政黨（簡報）：%r" % party_raw)
        _INCUMBENT_CACHE[county] = {
            "name": _to_trad(raw_name),
            "party": party,
            "partyShort": PARTY_SHORT_EN[party],
            "acting": "代理" in notes,
        }

    missing = [c for c in CM.COUNTY_ORDER if c not in _INCUMBENT_CACHE]
    if missing:
        raise RuntimeError("簡報缺時任首長：%s" % "、".join(missing))
    return _INCUMBENT_CACHE


# ---------------------------------------------------------------- Wikipedia 解析
def parse_wiki_votes():
    """解析 Wikipedia.txt，回傳 {繁體縣市key: {electorate, cast, valid, invalid, turnout}}。

    策略：先掃全部標題（「2022年XX…選舉結果」）記下「行號 → 縣市 key」，
    再掃「選舉人數」行，向上找最近的標題確定歸屬。投票數據 5 行是連續的
    （選舉人數/投票數/有效票/無效票/投票率），每行格式「鍵\\t　數值」。
    """
    txt = open(CM.WIKI_TXT, encoding="utf-8").read()
    lines = txt.splitlines()

    # 數字：去除千分位逗號；投票率保留小數
    def num(s):
        s = s.replace(",", "").replace("％", "%").replace("%", "").strip()
        return float(s)

    # 第一次掃描：記錄「行號 → 縣市 key」（標題行）
    title_at = {}
    for i, ln in enumerate(lines):
        m = re.search(r"2022年(.+?)(?:市|县)长选举结果", ln)
        if m:
            key = WIKI_TITLE_MAP.get(m.group(1))
            if key:
                title_at[i] = key

    # 第二次掃描：遇到「選舉人數」行，向上找最近的標題
    out = {}
    for i, ln in enumerate(lines):
        if "选举人数" not in ln:
            continue
        key = None
        for j in range(i, -1, -1):
            if j in title_at:
                key = title_at[j]
                break
        if key is None or key in out:
            continue
        d = {}
        for k in range(i, min(i + 6, len(lines))):
            line = lines[k]
            if "选举人数" in line:
                d["electorate"] = int(num(line.split("选举人数")[1]))
            elif "投票数" in line:
                d["cast"] = int(num(line.split("投票数")[1]))
            elif "有效票" in line:
                d["valid"] = int(num(line.split("有效票")[1]))
            elif "无效票" in line:
                d["invalid"] = int(num(line.split("无效票")[1]))
            elif "投票率" in line:
                d["turnout"] = num(line.split("投票率")[1])
        if d.get("valid"):
            out[key] = d
    return out


# ---------------------------------------------------------------- xlsx 解析
def parse_county_votes(county):
    """讀該縣市 xlsx 的「縣市級別」表，回傳候選人清單 + 當選人。"""
    path = CM.data_path(county)
    df = pd.read_excel(path, sheet_name="縣市級別")
    row = df.iloc[0]
    cands = []
    for col in df.columns:
        if col.endswith("_得票數") and col != "當選人":
            name = col[: -len("_得票數")]
            # 去掉「（01）」號次
            name_clean = re.sub(r"（\d+）$", "", name)
            # 去掉英文羅馬拼音（只留中文）
            name_clean = CM.clean_name(name_clean)
            votes = int(row[col])
            cands.append({"name": name_clean, "votes": votes})
    # 當選人
    winner = str(row["當選人"]) if "當選人" in df.columns else None
    winner = CM.clean_name(winner)
    return cands, winner


def party_of(name):
    """候選人姓名 → 政黨（全稱）。"""
    # 先查原名，查不到再查「去英文拼音」的中文名
    grp = CM.CAND_PARTY.get(name, CM.CAND_PARTY.get(CM.clean_name(name), 0))
    return CM.party_short_by_group(grp), grp


# ---------------------------------------------------------------- 兩張地圖的擺位
# 2026-10-28 改：不再用固定框（1430×470／1430×390 這種），也拋開「比例定死」。
# 規則只有兩條：
#   ① 村里圖是主圖，先盡量放大（寬或高先頂到可用區為止）；
#   ② 鄉鎮圖吃剩下的空間，但必須比村里圖小、又不能小到看不清。
# 所以每縣市的框都由「兩張圖各自的寬高比」算出來，框＝圖，contain 不再留白邊
# （原本臺中框 1430×470 只畫到 968×470，左右各空 231px；苗栗更浪費，只用了 43% 寬）。
MAP_ENV = {"x": 560, "y": 196, "w": 1444}      # 可用區左右界（右主卡左緣 2024）
MAP_TOP_SAFE = 236               # 鄉鎮圖不得高過此線（頁眉下緣）
MAP_BOTTOM_SAFE = 1092           # 兩張圖都不得越過此線（小卡帶上緣 1102，留 10px）
MAP_BOTTOM_TALL = 1230           # 左右並排時村里圖可用到的高度（沿用舊版 y196+1034）
MAP_GAP = 36                     # 兩圖間距
TOWN_MIN_SHORT = 200             # 鄉鎮圖短邊下限（1× 像素），再小就看不清楚
TOWN_MIN_REL = 0.40              # 鄉鎮圖長邊 ≥ 村里圖長邊 × 0.40（不讓它變成小貼紙）
VILLAGE_AREA_MIN = 1.35          # 村里圖面積 ≥ 鄉鎮圖面積 × 1.35（保證主圖明顯更大）
# 兩個「村圖下探到小卡帶」的實測例外（由 verify_layout 的 L9 定出來；改版面要重跑驗證）：
#   臺北市：下探段只剩文山一帶（窄），整組往右讓 85px 就閃得開左側的 others 卡。
#   彰化縣：下探段幾乎橫貫全圖（寬），往右讓也躲不掉 → 村圖壓回 1092 之上。
MAP_BAND_INSET = {"臺北市": 85}
MAP_TALL_OFF = {"彰化縣"}


def _plan_one(r1, r2, W, H1, H2, gap, mode):
    """單一擺法：回傳 (w1,h1,w2,h2) 或 None。

    H1 = 村里圖可用的高度上限，H2 = 鄉鎮圖可用的高度上限
    （左右並排時村里圖可以長到 y1230，鄉鎮圖則要留在小卡帶 1102 之上）。

    在「兩張都放得下 + 村里的比鄉鎮的大 + 鄉鎮不至於看不清」的前提下，
    挑**兩張面積和最大**的那一組（純粹「村里先吃滿」會把鄉鎮圖壓成裝飾品）。
    """
    best = None
    if mode == "stack":
        w1_max = min(W, r1 * (H1 - gap))
        w1 = 4
        while w1 <= w1_max:
            h1 = w1 / r1
            rem = H1 - gap - h1
            if rem > 0:
                w2, h2 = _cap_town(w1 * h1, min(W, rem * r2), r2)
                if _ok(w1, h1, w2, h2):
                    score = w1 * h1 + w2 * h2
                    if best is None or score > best[0]:
                        best = (score, w1, h1, w2, h2)
            w1 += 4
    else:
        h1_max = min(H1, W / r1)
        h1 = 4
        while h1 <= h1_max:
            w1 = r1 * h1
            rem = W - gap - w1
            if rem > 0:
                w2, h2 = _cap_town(w1 * h1, min(H2, rem / r2) * r2, r2)
                if _ok(w1, h1, w2, h2):
                    score = w1 * h1 + w2 * h2
                    if best is None or score > best[0]:
                        best = (score, w1, h1, w2, h2)
            h1 += 4
    return None if best is None else best[1:]


def _cap_town(area1, w2, r2):
    """鄉鎮圖最大可用寬度 w2 再壓一次：面積不得超過村里圖的 1/VILLAGE_AREA_MIN。"""
    h2 = w2 / r2
    max_a2 = area1 / VILLAGE_AREA_MIN
    if w2 * h2 > max_a2:
        k = (max_a2 / (w2 * h2)) ** 0.5
        w2 *= k
        h2 *= k
    return w2, h2


def _ok(w1, h1, w2, h2):
    """村里圖必須明顯大於鄉鎮圖，鄉鎮圖也不能縮到看不清楚。"""
    a1, a2 = w1 * h1, w2 * h2
    if a1 < VILLAGE_AREA_MIN * a2:
        return False
    s1, s2 = max(w1, h1), max(w2, h2)
    if s2 < TOWN_MIN_SHORT:
        return False
    return s2 >= TOWN_MIN_REL * s1


def plan_maps(county):
    """回傳 (map_box, map2_box)：兩張圖各佔的框（框＝圖，不留白邊）。"""
    r1 = CM.map_aspect(county, "village")
    r2 = CM.map_aspect(county, "town")
    W = MAP_ENV["w"]
    h_safe = MAP_BOTTOM_SAFE - MAP_ENV["y"]      # 兩張圖都必須留在此線之上（小卡帶 1102）
    h_tall = MAP_BOTTOM_TALL - MAP_ENV["y"]      # 左右並排時，村里圖可以更長（沿用舊版 1034）

    cands = []
    for mode in ("stack", "side"):
        if mode == "stack":
            got = _plan_one(r1, r2, W, h_safe, h_safe, MAP_GAP, mode)
        else:
            got = _plan_one(r1, r2, W, h_tall, MAP_BOTTOM_SAFE - MAP_TOP_SAFE,
                            MAP_GAP, mode)
        if got:
            w1, h1, w2, h2 = got
            cands.append((mode, w1, h1, w2, h2))
    if not cands:
        raise RuntimeError("地圖擺位無解：%s" % county)

    # 兩張總面積優先；同分再看主圖
    cands.sort(key=lambda c: (c[1] * c[2] + c[3] * c[4], c[1] * c[2]), reverse=True)
    mode, w1, h1, w2, h2 = cands[0]

    # 少數場次的村圖下探段會撞到下方小卡，按例外表處理（見檔頭常數）
    inset = MAP_BAND_INSET.get(county, 0) if mode == "side" else 0
    if mode == "side" and county in MAP_TALL_OFF:
        got = _plan_one(r1, r2, W, h_safe, MAP_BOTTOM_SAFE - MAP_TOP_SAFE,
                        MAP_GAP, "side")
        if got:
            w1, h1, w2, h2 = got
            h_tall = h_safe
    if inset:
        got = _plan_one(r1, r2, W - inset, h_tall, MAP_BOTTOM_SAFE - MAP_TOP_SAFE,
                        MAP_GAP, "side")
        if got:
            w1, h1, w2, h2 = got
        else:
            inset = 0

    if mode == "stack":
        total = h1 + MAP_GAP + h2
        top = MAP_ENV["y"] + (h_safe - total) / 2.0
        x1 = MAP_ENV["x"] + (W - w1) / 2.0
        x2 = MAP_ENV["x"] + (W - w2) / 2.0
        map_box = {"x": x1, "y": top, "w": w1, "h": h1}
        map2_box = {"x": x2, "y": top + h1 + MAP_GAP, "w": w2, "h": h2}
    else:
        total = w1 + MAP_GAP + w2
        left = MAP_ENV["x"] + inset + (W - inset - total) / 2.0
        y1 = MAP_ENV["y"] + (h_tall - h1) / 2.0
        # 鄉鎮圖與村里圖垂直對齊（同一中心線），但不得越過小卡帶
        y2 = y1 + (h1 - h2) / 2.0
        y2 = min(y2, MAP_BOTTOM_SAFE - h2)
        y2 = max(y2, MAP_TOP_SAFE)
        map_box = {"x": left, "y": y1, "w": w1, "h": h1}
        map2_box = {"x": left + w1 + MAP_GAP, "y": y2, "w": w2, "h": h2}

    for b in (map_box, map2_box):
        for k in ("x", "y"):
            b[k] = round(b[k], 1)
        for k in ("w", "h"):
            b[k] = round(b[k], 1)
    return map_box, map2_box


def build(county):
    cands_raw, winner = parse_county_votes(county)
    wiki = parse_wiki_votes().get(county, {})
    valid = int(wiki.get("valid", sum(c["votes"] for c in cands_raw)))
    turnout = wiki.get("turnout", None)

    # 組候選人（補黨籍、得票率、號次、當選）
    total = sum(c["votes"] for c in cands_raw)
    cands_out = []
    for i, c in enumerate(cands_raw, 1):
        party, grp = party_of(c["name"])
        # 顯示名：超長姓名按 county_map.NAME_WRAP 拆成兩行（\n 斷行）；
        # 邏輯判斷（黨籍、當選）一律用原始名，不受換行影響。
        disp_name = CM.NAME_WRAP.get(c["name"], c["name"])
        cand = {
            "key": "c%d" % i, "name": disp_name, "nameEn": "",
            "party": party, "partyShort": PARTY_SHORT_EN[party],
            "partyEn": PARTY_EN[party], "number": i,
            "votes": c["votes"],
            "pct": round(c["votes"] / total * 100, 2) if total else 0.0,
            "elected": (winner is not None and c["name"] == winner),
        }
        # 色票：只有在 county_map.PARTY_COLOR 有登記的政黨才寫 candidates[].color。
        # 引擎看到 color 就走 Theme.fromColor 推導亮暗階（時代力量 #FFBE00）；
        # 沒有登記的候選人不寫這個欄位，board.js 與原本完全一致。
        color_hex = CM.PARTY_COLOR.get(party)
        if color_hex:
            cand["color"] = color_hex
        cands_out.append(cand)

    # 按得票排序（主卡左高右低由引擎處理；這裡照號次排即可，引擎會重排）
    n_elected = sum(1 for c in cands_out if c["elected"])
    if n_elected != 1:
        print("  [警告] %s 當選者 %d 位（應為 1）" % (county, n_elected))

    # 頁眉「現任縣市長」色卡：改用**選舉當下的時任首長**（來源：簡報 md 的
    # 「时任首长（党籍）」欄）。當選人已在左右主卡與底部小卡帶上，頁眉不重複。
    inc = parse_brief_incumbents()[county]
    # 逐場修正（只列在 county_map.INCUMBENT_PARTY_OVERRIDE 的場次才動）：
    # 目前只有臺北市 —— 柯文哲 2022 年為台灣民眾黨主席，簡報記「無黨籍」。
    if county in CM.INCUMBENT_PARTY_OVERRIDE:
        p = CM.INCUMBENT_PARTY_OVERRIDE[county]
        inc = dict(inc, party=p, partyShort=PARTY_SHORT_EN[p])
    if inc["acting"]:
        header = {"role": "時任縣市長（代理）", "name": inc["name"],
                  "party": inc["party"], "partyShort": inc["partyShort"]}
    else:
        header = {"role": "時任縣市長", "name": inc["name"],
                  "party": inc["party"], "partyShort": inc["partyShort"]}

    # 版面：兩張地圖的框由各自的寬高比算出來（見 plan_maps）。
    #   村里圖優先放大、鄉鎮圖吃剩下的空間；不再有「橫圖／直圖」兩套固定數字。
    map_box, map2_box = plan_maps(county)
    layout = {"legend": {"disabled": True},
              "map": map_box,
              "map2": dict(map2_box, enabled=True)}

    slug = COUNTY_SLUG[county]
    bid = "2022-%s" % slug

    # 逐場日期覆寫（預設 11月26日；嘉義市因候選人死亡延後單獨投票）。
    date = CM.COUNTY_DATE.get(county, ("11月26日", "26 Nov"))

    meta = {
        "id": bid,
        "meta": {
            "election": "2022年九合一選舉",
            "electionEn": "2022 Nine-in-One Election",
            "year": 2022,
            "date": date[0], "dateEn": date[1],
            "country": "中華民國（台灣）",
            "countryEn": "Republic of China (Taiwan)",
            "office": "%s縣市長" % county,
            "officeEn": "County Magistrate / Mayor of %s" % county,
            "county": county, "countyShort": CM.COUNTY_SHORT[county],
            "electorate": wiki.get("electorate"),
            "turnout": turnout,
            "validVotes": valid,
            "invalidVotes": wiki.get("invalid"),
            "castVotes": wiki.get("cast"),
            "header": header,
        },
        "candidates": cands_out,
        "districts": [],
        "layout": layout,
    }

    # board.js canonical
    board = {
        "meta": dict(meta["meta"], id=bid, layout=layout),
        "candidates": cands_out,
        "districts": [],
        "geojson": {"type": "FeatureCollection", "features": []},
    }

    src_dir = os.path.join(SRC_BOARDS, bid)
    out_dir = os.path.join(DIST_BOARDS, bid)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(src_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "board.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。\n"
                "   來源：Mayors/2022NineInOne/data + Wikipedia.txt\n"
                "   建置：board/src/tools/_gen_boards.py（2022 九合一縣市長）\n*/\n")
        f.write("window.BOARD = " + json.dumps(board, ensure_ascii=False) + ";\n")

    # board.files.js：邏輯素材名 → 實際路徑（相對 dist/boards/<id>/）
    files = {
        "emblem.png": "../../assets/share/emblem.png",
        "roc_flag.png": "../../assets/share/roc_flag.png",
        "street_bg.png": "../../assets/bg/%s.png" % CM.bg_key(county),
        "mark_elected.png": "../../assets/share/mark_elected.png",
        "city_seal.png": "../../assets/share/%s.png" % county,
        "map.png": "../../assets/map/%s/map.png" % county,
        "map2.png": "../../assets/map/%s/map2.png" % county,
        # 低得票率候選人的圖片框占位圖（排名 ≥ 3 且得票率 < 3% 的人用）
        "low_pct.png": "../../assets/share/low_pct.png",
    }
    # 政黨徽章
    used_short = {c["partyShort"] for c in cands_out}
    for s in sorted(used_short):
        key = s.lower()
        p = "../../assets/party/party_%s.png" % key
        if os.path.isfile(os.path.join(BOARD, "dist", "assets", "party", "party_%s.png" % key)):
            files["party_%s.png" % key] = p

    with open(os.path.join(out_dir, "board.files.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。邏輯素材名 -> 實際檔案。\n"
                "   建置：board/src/tools/_gen_boards.py\n*/\n")
        f.write("window.BOARD_FILES = " +
                json.dumps({"files": files}, ensure_ascii=False, indent=2) + ";\n")

    shutil.copyfile(ENGINE_INDEX, os.path.join(out_dir, "index.html"))

    print("  ✓ %s  (%s)  有效票 %s  當選 %s  頁眉時任 %s（%s）"
          % (bid, county, format(valid, ","), winner,
             inc["name"], inc["party"]))
    for c in cands_out:
        mark = "★" if c["elected"] else " "
        print("    %s %-8s %-6s %10s  %5.2f%%" %
              (mark, c["name"], c["partyShort"], format(c["votes"], ","), c["pct"]))


def main():
    counties = [a for a in sys.argv[1:] if a in CM.COUNTIES] or CM.COUNTY_ORDER
    # 預先解析 Wikipedia（一次）
    for c in counties:
        print(c)
        build(c)


if __name__ == "__main__":
    main()
