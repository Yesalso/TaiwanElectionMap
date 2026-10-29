# -*- coding: utf-8 -*-
"""_gen_national.py —— 2022 全國縣市長看板（政黨版圖）建置器。

★ 這一場的「候選人」是**政黨**：candidates[].votes＝全台總得票、
  seats＝拿下的縣市長席次，姓名欄放政黨全稱。得票前兩名進左右主卡，
  其餘依票數排進底部小卡帶（第 3 名高卡 ＋ 窄卡 ＋「其他政黨」清單格）。

資料**只讀一份**：`Mayors/2022NineInOne/2022县市长选举简报.md`
  · 「一、总体结果」表  → 選舉人數／投票數／投票率／有效票／無效票
  · 「2.4 看板采用口径」表 → **各政黨／身份的席次、得票數、得票率（唯一候選人來源）**
    （国民党／民进党沿用 2.1 广义口径；其余按候选人登记党籍计算，其他政黨逐党列出）
  · 「3.1 席次分布」表    → 六都／台灣省／福建省的席次（只寫進 log）
  （該簡報本身以 Wikipedia.txt 為底編成，數字是中選會開票統計。）

地圖素材來自 build_national_assets.py（成品尺寸寫在 dist/assets/national/maps.json），
兩張圖的框由成品寬高比反算 → 「框＝圖」，contain 後不留白邊。

輸出：
  board/src/boards/2022-national/meta.json
  board/dist/boards/2022-national/{board.js, board.files.js, index.html}
  board/dist/assets/national/{county,town,legend}.png   ← 由 build_national_assets.py 產

執行：
    python src/tools/_gen_national.py
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import national_map as NM
import county_map as CM          # 只借 ROOT 定位與 map_aspect 的寫法

BOARD = CM.ROOT
SRC_BOARDS = os.path.join(BOARD, "src", "boards")
DIST_BOARDS = os.path.join(BOARD, "dist", "boards")
ENGINE_INDEX = os.path.join(BOARD, "src", "templates", "index.html")

BOARD_ID = "2022-national"


# ---------------------------------------------------------------- md 解析
def _tables(text):
    """把 markdown 切成表格：回傳 [(header_cells, [row_cells, ...]), ...]。"""
    out, cur = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(c and set(c) <= set("-: ") for c in cells):
                continue                      # |---|---| 分隔行
            if cur is None:
                cur = (cells, [])
            else:
                cur[1].append(cells)
        else:
            if cur:
                out.append(cur)
                cur = None
    if cur:
        out.append(cur)
    return out


def _find(tables, *needles):
    """找出「表頭同時含這些欄名」的那張表。"""
    for header, rows in tables:
        if all(any(n in c for c in header) for n in needles):
            return header, rows
    raise RuntimeError("簡報找不到表頭含 %s 的表格" % "、".join(needles))


def _num(s):
    """'5,761,851' / '50.14%' / '36†' → 數字（百分比去 %，註腳符號去尾）。"""
    s = re.sub(r"[†‡]", "", str(s)).replace(",", "").strip()
    s = s.replace("％", "%").replace("%", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def _trad(name):
    """簡體政黨名 → 繁體全稱（對照表在 national_map.PARTY_S2T）。"""
    key = re.sub(r"[†‡]", "", name).strip()
    if key not in NM.PARTY_S2T:
        raise RuntimeError("簡報出現未收錄的政黨：%r" % name)
    return NM.PARTY_S2T[key]


def parse_brief():
    text = open(NM.BRIEF_MD, encoding="utf-8").read()
    tables = _tables(text)

    # ① 總體結果（项目 / 数值 兩欄）
    _, overall_rows = _find(tables, "项目", "数值")
    overall = {}
    for cells in overall_rows:
        if len(cells) >= 2:
            overall[cells[0]] = cells[1]

    def pick(key):
        for k, v in overall.items():
            if key in k:
                return v
        raise RuntimeError("簡報「总体结果」缺 %s" % key)

    total = {
        "seats": int(_num(pick("应选席次"))),
        "electorate": int(_num(pick("选举人数"))),
        "cast": int(_num(pick("投票数"))),
        "turnout": _num(pick("整体投票率")),
        "valid": int(_num(pick("有效票"))),
        "invalid": int(_num(pick("无效票"))),
        "candidates": int(_num(pick("候选人总数"))),
        "women": int(_num(pick("女性当选人"))),
        "women_pct": _num(pick("女性当选人").split("占")[1]) if "占" in pick("女性当选人") else None,
    }

    # ② 政黨資料：**「2.4 看板采用口径」表**（政党名称/身份、席次、得票数、得票率）
    #    ★ 2026-10-29 使用者提供新數據：国民党／民进党沿用 2.1 的广义口径，
    #      其餘政黨与身份按「候选人登记党籍」计算；「其他政黨」也逐党列出。
    #      这张表是看板的唯一数据源（2.1 只留作本文分析，不再参与建置）。
    parties = parse_board_parties(tables)
    if len(parties) < 3:
        raise RuntimeError("2.4 看板采用口径表应有政党列，实得 %d 列" % len(parties))

    # ③ 區域席次（六都 / 台灣省 / 福建省）
    _, region_rows = _find(tables, "政党", "六都", "台湾省", "福建省")
    regions = {}
    for cells in region_rows:
        if len(cells) >= 5 and "合计" not in cells[0]:
            regions[_trad(cells[0])] = {"六都": int(_num(cells[1])),
                                        "台灣省": int(_num(cells[2])),
                                        "福建省": int(_num(cells[3])),
                                        "合計": int(_num(cells[4]))}

    return total, parties, regions


def _board_name(raw):
    """簡報上的政黨／身份 → 看板顯示名（繁體）。

    查三張表：看板專用（「无党籍或未经政党推荐」→ 無黨籍、「台澎党」→ 台澎黨）
    → 2.1 的政黨名 → 2.1 註腳的其他政黨明細。都沒收錄就沿用簡體並警告。
    """
    for tbl in (NM.BOARD_S2T, NM.PARTY_S2T, NM.OTHER_PARTY_S2T):
        if raw in tbl:
            return tbl[raw]
    print("  ! 未收錄的政黨名（沿用簡體）：%s" % raw)
    return raw


def parse_board_parties(tables):
    """讀「2.4 看板采用口径」表 → [{name, seats, votes, pct}, …]（依票數遞減）。

    表頭是「政党名称 / 席次 / 得票数 / 得票率」—— 用「政党名称」這個字串定位，
    才不會撞到 2.1（政黨／得票數／得票率／席次／候選人數）那張舊表。
    """
    _, rows = _find(tables, "政党名称", "席次", "得票数")
    out = []
    for cells in rows:
        if len(cells) < 4:
            continue
        raw = re.sub(r"[†‡]", "", cells[0]).strip()
        if not raw or "合计" in raw:
            continue
        out.append({
            "name": _board_name(raw),
            "seats": int(_num(cells[1])),
            "votes": int(_num(cells[2])),
            "pct": round(_num(cells[3]), 2),
        })
    out.sort(key=lambda p: -p["votes"])
    return out


# ---------------------------------------------------------------- 版面
def plan_maps():
    """兩張全國地圖的框：高度吃满頁眉下緣→小卡帶上緣，寬度＝高 × 成品寬高比。"""
    with open(NM.OUT_META, encoding="utf-8") as f:
        meta = json.load(f)
    asp = meta["maps"]["county"]["aspect"]
    h = NM.MAP_H
    w = round(h * asp, 1)
    total = w * 2 + NM.MAP_GAP
    env = NM.MAP_ENV_X1 - NM.MAP_ENV_X0
    if total > env:
        # 寬度不夠 → 改由寬度決定（高度跟著縮），並回報實際餘裕
        w = round((env - NM.MAP_GAP) / 2, 1)
        h = round(w / asp, 1)
        total = w * 2 + NM.MAP_GAP
    x0 = round(NM.MAP_ENV_X0 + (env - total) / 2, 1)
    box1 = {"x": x0, "y": NM.MAP_Y, "w": w, "h": h}
    box2 = {"x": round(x0 + w + NM.MAP_GAP, 1), "y": NM.MAP_Y, "w": w, "h": h}
    return box1, box2, meta


def build():
    total, parties, regions = parse_brief()
    text = open(NM.BRIEF_MD, encoding="utf-8").read()

    # ---- 候選人（＝政黨） ----
    # ★ 2026-10-29（使用者要求）：
    #   ① 小卡副行是**該黨黨主席**（民眾黨＝柯文哲、時代力量＝陳椒華）；
    #      無黨籍／其他小黨沒有單一負責人 → 副行留白（sub=''）。
    #   ② 「其他政黨」不分組，2.4 表裡逐黨列的 6 家各自成為一位「候選人」，
    #      在底部清單格逐列顯示（＝台北市底部那一套）。
    #      真的多到列不下（> NM.OTHERS_MAX_ROWS）才收成一列「其他政黨」。
    named = [p for p in parties if p["name"] in NM.PARTY_SHORT]
    others = [p for p in parties if p["name"] not in NM.PARTY_SHORT]

    cands = []
    for p in named:
        short, en = NM.PARTY_SHORT[p["name"]]
        leader = NM.PARTY_LEADER.get(p["name"])
        cand = {
            "key": short.lower(),
            "name": p["name"],
            "nameEn": "",
            "party": p["name"],
            "partyShort": short,
            "partyEn": en,
            "number": len(cands) + 1,
            "votes": p["votes"],
            "pct": p["pct"],
            "elected": False,          # 政黨沒有「當選」這回事，主卡不蓋當選章
            "seats": p["seats"],       # → 姓名左邊的席次牌（c.seats）
            # 副行＝黨主席；沒有主席（無黨籍）就留白，卡片仍保留四行的節奏
            "sub": leader or "",
        }
        # 黨主席：主卡（得票前兩名）的大字姓名印主席名，黨名留在 chip 上
        if leader:
            cand["leader"] = leader
        # 色票：兩大黨與民眾黨／無黨籍走引擎內建的政黨色（Theme.parties，
        # 與 22 場縣市長看板同一個色）；只有「沒有預設色」的黨才在這裡宣告
        # 主色，由 Theme.fromColor 推導亮暗階 —— 與 _gen_boards.py 同一個規則。
        col = CM.PARTY_COLOR.get(p["name"]) or NM.PARTY_COLOR.get(p["name"])
        if col:
            cand["color"] = col
        cands.append(cand)

    n_others = len(others)
    if n_others > NM.OTHERS_MAX_ROWS:
        others = [{
            "name": "其他政黨",
            "seats": sum(p["seats"] for p in others),
            "votes": sum(p["votes"] for p in others),
            "pct": round(sum(p["pct"] for p in others), 2),
        }]
    for p in others:
        cands.append({
            "key": "oth%d" % (len(cands) + 1),
            "name": p["name"],
            "nameEn": "",
            "party": "其他政黨",         # 只影響 chip 分組，清單格不印政黨
            "partyShort": "OTH",
            "partyEn": "",
            "number": len(cands) + 1,
            "votes": p["votes"],
            "pct": p["pct"],
            "elected": False,
            "seats": p["seats"],
            "sub": "",
            "color": NM.PARTY_COLOR["其他政黨"],
        })
    print("  · 其他政黨 %d 家 → %s" % (n_others,
          "清單格逐黨列出" if n_others <= NM.OTHERS_MAX_ROWS
          else "超過上限 %d，收成單列「其他政黨」" % NM.OTHERS_MAX_ROWS))

    # ---- 版面 ----
    map_box, map2_box, asset_meta = plan_maps()
    legend_box = dict(asset_meta["legend"]["box"])
    layout = {
        # 圖例擺在頁眉右側 → allowInHeader 讓 verify_layout 的 L3 不對整塊頁眉判定
        "legend": dict(legend_box, disabled=False, inner=0, title="",
                       allowInHeader=True),
        # ★ 地圖不加底板（使用者要求）：直接貼在看板底色／街景上
        "map": dict(map_box, src="assets/map.png"),
        "map2": dict(map2_box, src="assets/map2.png", enabled=True,
                     allowWithLegend=True),
        # ★ 底部得票比例帶關掉（使用者要求 2026-10-29）：小卡帶已經把
        #   席次／得票率／票數都講完了，比例帶只是重複。
        "ribbon": {"disabled": True},
        # ★ 底部政黨小卡＝台北市那一套：照片位 + 黨名／黨主席／得票率／票數；
        #   席次另外畫成一塊小方塊「貼」在照片框右下角（layers.js#seatChip），
        #   不佔用照片本身。
        # ★ 政黨多 → 只留 2 張窄卡，其餘（其他政黨的 6 家明細）進清單格，
        #   也就是台北市底部的處理方式。groupGap 64 → 36：兩張卡＋清單格
        #   要塞進 560..1990 這條帶。
        # ★ subInk 0.86：副行是黨主席姓名、底色又是街景照片，
        #   預設的 0.40 白幾乎看不見（其他場次不受影響）。
        "minors": {"smallMax": 2, "groupGap": 36,
                   "subInk": "rgba(255,255,255,0.86)",
                   "othersMaxTextW": 338},
    }

    # ---- 頁眉 ----
    def wan(n):
        """與引擎 Utils.voteWan 同一套「萬」制寫法（頁眉四行數據用）。"""
        n = int(round(n))
        if abs(n) <= 10000:
            return str(n)
        w, rest = divmod(n, 10000)
        return ("%d萬" % w) if rest == 0 else ("%d萬%04d" % (w, rest))

    header = {
        # ★ 2026-10-29（使用者要求）：右側色卡改成「時任總統」蔡英文
        #   （2022/11/26 投票當下在位）。對應總統看板的「現任元首」欄，
        #   左側民進黨綠純色卡（照片由使用者後製），右側三行字。
        "role": "時任總統",
        "name": "蔡英文",
        "party": "民主進步黨",
        "partyShort": "DPP",
        # 四行數據：全國只有「總計」一組，標籤用繁體（無效票／選舉人數）
        "stats": [
            {"label": "投票率", "value": "%.2f%%" % total["turnout"]},
            {"label": "有效票", "value": wan(total["valid"]) + " 票"},
            {"label": "無效票", "value": wan(total["invalid"]) + " 票"},
            {"label": "選舉人數", "value": wan(total["electorate"]) + " 人"},
        ],
    }

    meta_meta = {
        "election": "2022年縣市長選舉",
        "electionEn": "2022 Local Elections — County Magistrates & Mayors",
        "year": 2022,
        "date": "11月26日", "dateEn": "26 Nov",
        "country": "中華民國（台灣）",
        "countryEn": "Republic of China (Taiwan)",
        # ★ 2026-10-29（使用者要求）：所有阿拉伯數字改用日期塊那支
        #   Noto Sans UI Black（＝頁眉「2022」的字型）。theme.js 會把它排到
        #   字型堆疊最前面，中文照舊掉回源石黑體。其他場次沒這個欄位 → 不變。
        "figures": "display",
        "office": "全國 22 縣市長",
        "officeEn": "County Magistrates & Mayors, All 22",
        "county": "全國", "countyShort": "全國",
        "electorate": total["electorate"],
        "turnout": total["turnout"],
        "validVotes": total["valid"],
        "invalidVotes": total["invalid"],
        "castVotes": total["cast"],
        "header": header,
    }

    meta = {"id": BOARD_ID, "meta": meta_meta, "candidates": cands,
            "districts": [], "layout": layout}
    board = {
        "meta": dict(meta_meta, id=BOARD_ID, layout=layout),
        "candidates": cands, "districts": [],
        "geojson": {"type": "FeatureCollection", "features": []},
    }

    src_dir = os.path.join(SRC_BOARDS, BOARD_ID)
    out_dir = os.path.join(DIST_BOARDS, BOARD_ID)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(src_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "board.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。\n"
                "   來源：Mayors/2022NineInOne/2022县市长选举简报.md\n"
                "   建置：board/src/tools/_gen_national.py（2022 全國縣市長看板）\n*/\n")
        f.write("window.BOARD = " + json.dumps(board, ensure_ascii=False) + ";\n")

    files = {
        "emblem.png": "../../assets/share/emblem.png",
        "roc_flag.png": "../../assets/share/roc_flag.png",
        "street_bg.png": "../../assets/bg/north.png",
        "mark_elected.png": "../../assets/share/mark_elected.png",
        "map.png": "../../assets/national/county.png",
        "map2.png": "../../assets/national/town.png",
        "legend.png": "../../assets/national/legend.png",
    }
    # 政黨徽章：只有真的有素材的才登記（時代力量／其他政黨沒有 → 引擎退回色塊）
    used_short = {c["partyShort"] for c in cands}
    for s in sorted(used_short):
        key = s.lower()
        if os.path.isfile(os.path.join(BOARD, "dist", "assets", "party",
                                       "party_%s.png" % key)):
            files["party_%s.png" % key] = "../../assets/party/party_%s.png" % key

    with open(os.path.join(out_dir, "board.files.js"), "w", encoding="utf-8") as f:
        f.write("/* 自動產生，請勿手改。邏輯素材名 -> 實際檔案。\n"
                "   建置：board/src/tools/_gen_national.py\n*/\n")
        f.write("window.BOARD_FILES = " +
                json.dumps({"files": files}, ensure_ascii=False, indent=2) + ";\n")

    shutil.copyfile(ENGINE_INDEX, os.path.join(out_dir, "index.html"))

    # ---- log ----
    print("  ✓ %s  有效票 %s  投票率 %.2f%%  應選 %d 席"
          % (BOARD_ID, format(total["valid"], ","), total["turnout"], total["seats"]))
    print("    地圖框  map %s / map2 %s（成品 %.0f×%.0f，寬高比 %.4f）"
          % (map_box, map2_box, map_box["w"], map_box["h"],
             asset_meta["maps"]["county"]["aspect"]))
    for c in cands:
        print("    %-12s %-4s %10s  %5.2f%%  %2d 席"
              % (c["name"], c["partyShort"], format(c["votes"], ","),
                 c["pct"], c["seats"]))
    print("    區域席次：" + "；".join(
        "%s 六都%d／省%d／閩%d" % (k, v["六都"], v["台灣省"], v["福建省"])
        for k, v in regions.items()))


def main():
    if not os.path.isfile(NM.OUT_META):
        raise SystemExit("缺 dist/assets/national/maps.json —— 先跑 "
                         "python src/tools/build_national_assets.py")
    build()


if __name__ == "__main__":
    main()
