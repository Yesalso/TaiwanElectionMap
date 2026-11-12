# -*- coding: utf-8 -*-
r"""2012-2024 全國不分區立委（政黨票）：各縣市「村里領先政黨」村里數統計。

讀取 `data/` 下的四屆中選會原始檔（每縣市一檔），逐投開票所累加到村里，
判定每個村里得票數最高的政黨，輸出「各縣市 × 各政黨」的領先村里數 Markdown。

資料來源
    2012 → data/2012不分区/*.xls        （11 個政黨）
    2016 → data/不分区2016/*.xls        （18 個政黨）
    2020 → data/不分区2020/*.xls        （19 個政黨）
    2024 → data/不分区24/不分区24/*.xlsx（16 個政黨；檔名亂碼時改由表頭標題認縣市）

輸出
    map/Atlarge2008-2024/全臺灣{年}_村里領先政黨統計.md

用法
    py script/Count_AtLarge_Village_Leaders_2012_2024.py
    py script/Count_AtLarge_Village_Leaders_2012_2024.py --years 2016 2020 2024
    py script/Count_AtLarge_Village_Leaders_2012_2024.py --outdir map/Atlarge2008-2024
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys
import time

BASE = r"D:\Windows\TaiwanElection\LegislationYuan\2012-2024"
DATA = os.path.join(BASE, "data")
DEFAULT_OUTDIR = os.path.join(BASE, "map", "Atlarge2008-2024")

# 各屆設定：資料夾、副檔名、屆次、備援資料夾（同一屆的重複下載目錄）
YEAR_CFG = {
    2012: dict(dir="2012不分区", ext=".xls", session="第8屆", fallback=None),
    2016: dict(dir="不分区2016", ext=".xls", session="第9屆", fallback=None),
    2020: dict(dir="不分区2020", ext=".xls", session="第10屆", fallback=None),
    2024: dict(dir=os.path.join("不分区24", "不分区24"), ext=".xlsx", session="第11屆",
               fallback=os.path.join("不分区2024", "ぃだ跋ミ〆")),
}

# 縣市固定順序（中選會公告排序：直轄市 → 市 → 縣）
OFFICIAL_ORDER = ["臺北市", "新北市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "新竹縣",
                  "桃園市", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣",
                  "臺東縣", "花蓮縣", "宜蘭縣", "澎湖縣", "金門縣", "連江縣"]

TRANS = str.maketrans({"台": "臺"})

# 排序用的別名（2014 年桃園縣升格桃園市，2012 年資料仍為「桃園縣」）
ORDER_ALIAS = {"桃園縣": "桃園市"}


# ---------------------------------------------------------------- 基礎工具
def norm_county(name: str) -> str:
    """縣市名正規化：日/簡体混用的『台』統一為『臺』，去掉空白。"""
    s = re.sub(r"[\s\u3000]", "", str(name or ""))
    return s.translate(TRANS)


def clean(s) -> str:
    return re.sub(r"[\s\u3000]", "", str(s or ""))


def num(v) -> int:
    """把儲存格轉整數：相容 float、'1,286'、''、'-' 等。"""
    if v is None:
        return 0
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(",", "").replace("，", "").replace("\u3000", "")
    if s in ("", "-", "—", "－", "nan", "None"):
        return 0
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


CODE_RE = re.compile(r"^[（(]?\d+[）)]?$")


def party_name(cell) -> str:
    """政黨名稱：儲存格常為『1\\n民主進步黨』或『(3)\\n\\n親民黨』，取出名稱那行。"""
    for line in str(cell or "").split("\n"):
        t = line.strip()
        if not t or CODE_RE.match(t):
            continue
        return t
    return ""


def is_header(cell) -> bool:
    t = clean(cell)
    return "鄉" in t and "區" in t and "別" in t


def find_county(title: str, path: str) -> str:
    """縣市名優先用表頭標題（2024 有檔名亂碼），抓不到才退回檔名。"""
    t = norm_county(title)
    for name in list(ORDER_ALIAS) + OFFICIAL_ORDER:
        if name in t:
            return name
    m = re.search(r"[（(]([^（）()]+)[）)]", os.path.splitext(os.path.basename(path))[0])
    if m:
        return norm_county(m.group(1))
    return ""


def read_sheets(path: str):
    """回傳 [(sheet_name, rows)]，rows 為二維的原值列表。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(path)
        return [(sh.name, [[sh.cell_value(r, c) for c in range(sh.ncols)]
                           for r in range(sh.nrows)]) for sh in wb.sheets()]
    import warnings
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        out = []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            out.append((ws.title, rows))
        wb.close()
    return out


# ---------------------------------------------------------------- 解析單一縣市檔
def parse_county_file(path: str):
    """解析一個縣市檔。

    回傳 (縣市名, 政黨順序, {(鄉鎮市區,村里): {政黨: 票數, "_valid": 有效票}}, 全縣有效票合計)。
    """
    sheets = read_sheets(path)
    county, parties = "", []
    acc = {}                      # (town, raw_village) -> [counts..., valid]
    official_total = 0

    for _, rows in sheets:
        if not rows:
            continue
        if not county and rows[0]:
            county = find_county(str(rows[0][0] or ""), path)

        hdr = None
        for r in range(min(8, len(rows))):
            row = rows[r]
            if row and is_header(row[0]):
                hdr = r
                break
        if hdr is None:
            continue

        hrow = rows[hdr]
        prow = rows[hdr + 1] if hdr + 1 < len(rows) else []
        valid_col = None
        for c, v in enumerate(hrow):
            if "有效票數" in clean(v):
                valid_col = c
                break
        if valid_col is None:
            raise RuntimeError(f"{os.path.basename(path)}: 找不到『有效票數』欄")

        if not parties:
            parties = [party_name(prow[c]) for c in range(3, valid_col)]
            parties = [p for p in parties if p]
        pcols = list(range(3, 3 + len(parties)))

        town = ""
        for r in range(hdr + 2, len(rows)):
            row = rows[r] + [None] * max(0, valid_col + 1 - len(rows[r]))
            c0, c1 = clean(row[0]), clean(row[1])
            if not c0 and not c1:
                continue
            if "總" in c0 and not c1:          # 『總　計』列（全縣合計）
                official_total = num(row[valid_col]) or official_total
                continue
            if c0 and not c1:                  # 鄉鎮市區列
                town = c0
                continue
            if not c1 or "合計" in c1 or "總計" in c1:
                continue
            counts = [num(row[c]) for c in pcols]
            valid = num(row[valid_col])
            if not town or (valid <= 0 and sum(counts) <= 0):
                continue
            k = (town, c1)
            rec = {nm: counts[i] for i, nm in enumerate(parties)}
            rec["_valid"] = valid
            if k not in acc:
                acc[k] = rec
            else:
                for nm, v in rec.items():
                    acc[k][nm] = acc[k].get(nm, 0) + v

    if not county:
        raise RuntimeError(f"無法辨識縣市：{path}")
    return county, parties, acc, official_total


def build_villages(acc: dict):
    """村里層級整併（acc 值為 {政黨: 票數, "_valid": 有效票}）。

    1) 該村里有自己的投開票所（單一村里列）→ 優先採用；
    2) 同一投開票所涵蓋多村里（「、」分隔）→ 只補給「沒有自己投開票所」的村里。
    這樣每個村里只算一次，且不會把共用票所的票重複灌給已有自己票所的村里。
    """
    direct, shared = {}, collections.defaultdict(list)
    for (town, raw), a in acc.items():
        names = [p.strip() for p in re.split(r"[、，,]", raw) if p.strip()]
        if len(names) == 1:
            direct[(town, names[0])] = a
        else:
            for nm in names:
                shared[(town, nm)].append(a)

    def merge(alist):
        out = collections.Counter()
        for a in alist:
            out.update(a)
        return dict(out)

    villages = {k: dict(a) for k, a in direct.items()}
    for k, alist in shared.items():
        if k in villages:
            continue
        villages[k] = merge(alist)
    return villages


# ---------------------------------------------------------------- 單屆統計
def peek_title(path: str) -> str:
    """只讀第一列標題，用來快速判斷這是哪個縣市的檔（2024 有整批檔名亂碼）。"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".xls":
            import xlrd
            sh = xlrd.open_workbook(path).sheet_by_index(0)
            return str(sh.cell_value(0, 0) or "")
        import warnings
        import openpyxl
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            for row in wb[wb.sheetnames[0]].iter_rows(max_row=1, values_only=True):
                wb.close()
                return str(row[0] or "")
            wb.close()
    except Exception:
        pass
    return ""


def analyse_year(year: int):
    cfg = YEAR_CFG[year]
    d = os.path.join(DATA, cfg["dir"])
    files = sorted(glob.glob(os.path.join(d, "*" + cfg["ext"])))
    if not files:
        raise RuntimeError(f"{year}: {d} 沒有 {cfg['ext']} 檔")

    counties = {}
    party_order = []
    for p in files:
        county, parties, acc, total = parse_county_file(p)
        if county in counties:
            print(f"  ! {year} 重複縣市 {county}（{os.path.basename(p)}），略過")
            continue
        counties[county] = (build_villages(acc), total, os.path.basename(p))
        for nm in parties:
            if nm not in party_order:
                party_order.append(nm)

    # 主資料夾缺縣市時，才去備援資料夾補（以表頭標題判斷縣市，不看檔名）
    if cfg.get("fallback"):
        alt = os.path.join(DATA, cfg["fallback"])
        for p in sorted(glob.glob(os.path.join(alt, "*" + cfg["ext"]))):
            if all(c in counties for c in OFFICIAL_ORDER):
                break
            cty = find_county(peek_title(p), p)
            if not cty or cty in counties:
                continue
            county, parties, acc, total = parse_county_file(p)
            counties[county] = (build_villages(acc), total, os.path.basename(p))
            for nm in parties:
                if nm not in party_order:
                    party_order.append(nm)
            print(f"  · {year} 由備援資料夾補入 {county}")

    missing = [c for c in OFFICIAL_ORDER if c not in {ORDER_ALIAS.get(x, x) for x in counties}]
    extra = [c for c in counties if ORDER_ALIAS.get(c, c) not in OFFICIAL_ORDER]
    if missing:
        print(f"  ! {year} 缺縣市：{'、'.join(missing)}")
    if extra:
        print(f"  ! {year} 未知縣市：{'、'.join(extra)}")

    order = sorted(counties, key=lambda c: OFFICIAL_ORDER.index(ORDER_ALIAS.get(c, c))
                   if ORDER_ALIAS.get(c, c) in OFFICIAL_ORDER else 999)

    # 檢查各檔政黨欄位數是否一致（不同檔若黨名不同，代表解析有問題）
    psets = set()
    rows, ties = [], []
    grand = collections.Counter()
    grand_n = grand_tie = 0
    qa = []
    for c in order:
        villages, total, fname = counties[c]
        cnt = collections.Counter()
        tie_cnt = 0
        ballots = 0
        for (town, vill), a in sorted(villages.items()):
            ballots += a.get("_valid", 0)
            votes = {p: a.get(p, 0) for p in party_order}
            mx = max(votes.values()) if votes else 0
            if mx <= 0:
                continue
            leaders = [p for p, v in votes.items() if v == mx]
            if len(leaders) > 1:
                tie_cnt += 1
                order_i = sorted(leaders, key=lambda p: party_order.index(p))
                ties.append((c, town, vill, order_i, int(mx), int(a.get("_valid", 0))))
            else:
                cnt[leaders[0]] += 1
        top = max(party_order, key=lambda p: (cnt[p], -party_order.index(p)))
        rows.append((c, len(villages), cnt, tie_cnt, top, cnt[top]))
        grand_n += len(villages)
        grand_tie += tie_cnt
        for p in party_order:
            grand[p] += cnt[p]
        qa.append((c, fname, len(villages), ballots, total))

    return dict(year=year, cfg=cfg, parties=party_order, rows=rows, grand=grand,
                grand_n=grand_n, grand_tie=grand_tie, ties=ties, qa=qa, order=order)


def pct(a, b):
    return f"{a / b * 100:.2f}" if b else "—"


# ---------------------------------------------------------------- 產出 Markdown
def render(st: dict) -> str:
    year, parties = st["year"], st["parties"]
    rows, grand = st["rows"], st["grand"]
    grand_n, grand_tie = st["grand_n"], st["grand_tie"]
    ties = st["ties"]
    session = st["cfg"]["session"]
    n_party = len(parties)

    # 全國依領先村里數排序，供第 2、3 節使用
    ranked = sorted([p for p in parties if grand[p] > 0], key=lambda p: -grand[p])
    top3 = ranked[:3]

    L = []
    L.append(f"# 全臺灣 {year} 立法委員不分區（政黨票）— 各縣市「村里領先政黨」統計")
    L.append("")
    L.append(f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"- 選舉屆次：{session}全國不分區及僑居國外國民立法委員選舉")
    L.append(f"- 資料來源：`data/{st['cfg']['dir'].replace(os.sep, '/')}`（中選會原始檔，22 個縣市各一檔，{n_party} 個政黨）")
    L.append("- 統計單位：**村里**。同一村里若有多個投開票所，先合併該村里全部得票再判定領先政黨。")
    L.append("- 判定方式：以該村里**得票數最高**的政黨為「領先政黨」（同一村里各黨得票率分母相同，故以得票數判定與得票率判定結果一致）。")
    L.append("- 同票並列：得票數相同且同為最高票時，**不計入任何政黨**，另列「並列」欄，並在文末列出清單。")
    L.append("- 共用投開票所：原表若同一個投開票所對應多個村里（以「、」分隔），優先採用該村里自己的投開票所資料；沒有自己投開票所的村里，才使用共用投開票所的合計得票。")
    L.append(f"- 全國合計：**{grand_n:,} 個村里**（含並列 {grand_tie} 個）")
    L.append("")

    # 1. 各縣市 × 各政黨
    L.append("## 1. 各縣市政黨領先村里數")
    L.append("")
    L.append("| 縣市 | 村里數 | " + " | ".join(parties) + " | 並列 | 領先政黨（村里數） |")
    L.append("|---|---:|" + "---:|" * n_party + "---:|---|")
    for c, n, cnt, tie, top, topn in rows:
        vals = " | ".join(str(cnt[p]) for p in parties)
        L.append(f"| {c} | {n} | {vals} | {tie} | {top}（{topn}） |")
    top_grand = ranked[0] if ranked else "—"
    L.append(f"| **合計** | **{grand_n:,}** | "
             + " | ".join(f"**{grand[p]:,}**" for p in parties)
             + f" | **{grand_tie}** | {top_grand}（{grand[top_grand]:,}） |")
    L.append("")
    L.append("> 註：各縣市「村里數」為資料表中實際出現的村里數（同一村里只計一次）；共用投開票所依上述規則處理，因此可能與行政區村里總數略有差異。")
    L.append("")

    # 2. 全國合計
    L.append("## 2. 全國村里領先政黨合計")
    L.append("")
    L.append("| 政黨 | 領先村里數 | 佔全部村里 % | 佔有唯一領先村里 % |")
    L.append("|---|---:|---:|---:|")
    uniq = grand_n - grand_tie
    for p in ranked:
        L.append(f"| {p} | {grand[p]:,} | {pct(grand[p], grand_n)} | {pct(grand[p], uniq)} |")
    L.append(f"| **唯一領先合計** | **{uniq:,}** | **{pct(uniq, grand_n)}** | **100.00** |")
    L.append(f"| 並列（無唯一領先） | {grand_tie} | {pct(grand_tie, grand_n)} | — |")
    L.append(f"| **村里總數** | **{grand_n:,}** | **100.00** | — |")
    L.append("")
    zero = [p for p in parties if grand[p] == 0]
    if zero:
        L.append(f"> 註：{'、'.join(zero)} 在全國 {grand_n:,} 個村里中均未取得任何村里的最高票，故未列入上表。")
        L.append("")

    # 3. 各縣市領先政黨佔比（取全國前 3 大黨，其餘合併為「其他」）
    others = [p for p in ranked if p not in top3]
    L.append("## 3. 各縣市領先政黨佔比")
    L.append("")
    head = "| 縣市 | 村里數 | " + " | ".join(f"{p}" for p in top3)
    if others:
        head += f" | 其他（{len(others)} 黨）"
    head += " | 並列 | 最大領先政黨 |"
    L.append(head)
    L.append("|---|---:|" + "---:|" * len(top3) + ("---:|" if others else "") + "---:|---|")
    for c, n, cnt, tie, top, topn in rows:
        cells = [f"{c}", f"{n}"]
        cells += [f"{cnt[p]}（{pct(cnt[p], n)}%）" for p in top3]
        if others:
            cells.append(f"{sum(cnt[p] for p in others)}（{pct(sum(cnt[p] for p in others), n)}%）")
        cells += [f"{tie}（{pct(tie, n)}%）", top]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    if others:
        L.append(f"> 「其他」＝{'、'.join(others)}，合計 {sum(grand[p] for p in others):,} 個村里。")
        L.append("")

    # 4. 並列清單
    sec = 4
    if ties:
        L.append(f"## {sec}. 同票並列村里清單")
        L.append("")
        L.append("| # | 縣市 | 鄉鎮市區 | 村里 | 並列政黨 | 最高票 | 有效票 |")
        L.append("|---:|---|---|---|---|---:|---:|")
        for i, (c, t, v, ps, mx, valid) in enumerate(ties, 1):
            L.append(f"| {i} | {c} | {t} | {v} | {'、'.join(ps)} | {mx:,} | {valid:,} |")
        L.append("")
        sec += 1

    # 5. 資料核對
    L.append(f"## {sec}. 資料核對（村里合計 vs 原表中選會全縣合計）")
    L.append("")
    L.append("| 縣市 | 村里數 | 村里有效票合計 | 原表全縣有效票 | 差額 | 說明 |")
    L.append("|---|---:|---:|---:|---:|---|")
    bad = 0
    for c, fname, n, ballots, total in st["qa"]:
        diff = ballots - total
        if diff == 0:
            note = "相符"
        elif diff > 0:
            note = "共用票所票數計給多個村里"
        else:
            note = "原表重複列已排除（該里有自有票所）"
        if diff != 0:
            bad += 1
        L.append(f"| {c} | {n:,} | {ballots:,} | {total:,} | {diff:+,} | {note} |")
    L.append("")
    if bad:
        L.append("> 註：差額為 0 表示該縣市村里得票可完整還原中選會公告數。差額為正者，是同一投開票所的票被計給多個村里（該票所涵蓋的村里都沒有自己的票所，只能共用同一筆得票）；差額為負者，是原表對某些村里同時列了自有票所與共用票所，本統計只取自有票所、把重複列排除。兩者都不改變各村里的領先政黨。")
        L.append("")

    # 6. 處理說明
    L.append(f"## {sec + 1}. 處理說明")
    L.append("")
    L.append("1. 直接讀取 22 個縣市原始檔的「各政黨得票數」欄，不經任何地圖對位或村里名稱修補，避免名稱比對造成的遺漏。")
    L.append("2. 原表按投開票所逐列登錄，同一村里可能出現多列；本統計以「鄉鎮市區＋村里」為鍵先合併得票，再判定領先政黨。")
    L.append("3. 少數投開票所同時對應多個村里（例如連江縣南竿鄉一次涵蓋 6 個村），原表僅提供該組合計得票。本統計對「沒有自己投開票所」的村里使用該組合計得票；若該村里另有自己的投開票所，則只採自己的資料，避免重複計算。")
    L.append("4. 並列村里不歸屬任何政黨，以維持「領先村里數」的互斥性；若改以「並列各黨各記 1 村」計算，參與並列的政黨可再各加相應村里數。")
    L.append("5. 本表僅統計「村里數」，不涉及得票率高低或當選席次。")
    L.append(f"6. 2020 年原始檔的得票數為文字格式（含千分位逗號），2016／2024 為數值格式，程式已統一轉為整數後計算。")
    L.append("")
    return "\n".join(L)


def render_compare(stats: list) -> str:
    """跨屆比較：各縣市歷屆最大領先政黨、各黨歷屆領先村里數。"""
    years = [st["year"] for st in stats]
    L = ["# 全臺灣 2012-2024 立法委員不分區（政黨票）— 村里領先政黨跨屆比較", ""]
    L.append(f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("- 資料來源：各年度明細見同目錄 `全臺灣{年}_村里領先政黨統計.md`")
    L.append("- 說明：以「村里」為單位，取該村里得票數最高的政黨；並列村里不計入任何政黨。")
    L.append("")

    L.append("## 1. 各縣市歷屆最大領先政黨")
    L.append("")
    L.append("| 縣市 | " + " | ".join(f"{y} 村里數" for y in years) + " | " + " | ".join(f"{y} 最大黨" for y in years) + " |")
    L.append("|---|" + "---:|" * len(years) + "---|" * len(years))
    order = []
    for st in stats:
        for r in st["rows"]:
            c = ORDER_ALIAS.get(r[0], r[0])
            if c not in order:
                order.append(c)
    order.sort(key=lambda c: OFFICIAL_ORDER.index(c) if c in OFFICIAL_ORDER else 999)
    lookup = [{r[0]: r for r in st["rows"]} for st in stats]
    alias_merged = False
    for c in order:
        keys = [c] + [k for k, v in ORDER_ALIAS.items() if v == c]
        cells = [c]
        for lk in lookup:
            hit = next((lk[k] for k in keys if k in lk), None)
            cells.append(str(hit[1]) if hit else "—")
        for lk in lookup:
            hit = next((lk[k] for k in keys if k in lk), None)
            cells.append(f"{hit[4]}（{hit[5]:,}）" if hit else "—")
        if len(keys) > 1 and any(k in lk for k in keys for lk in lookup):
            alias_merged = True
        L.append("| " + " | ".join(cells) + " |")
    cells = ["**全國**"]
    cells += [f"**{st['grand_n']:,}**" for st in stats]
    for st in stats:
        top = max(st["parties"], key=lambda p: st["grand"][p])
        cells.append(f"{top}（{st['grand'][top]:,}）")
    L.append("| " + " | ".join(cells) + " |")
    L.append("")
    if alias_merged:
        L.append("> 註：2014 年桃園縣升格為桃園市，2012 年資料的「桃園縣」與其他屆的「桃園市」在本表合併為同一列。")
        L.append("")

    L.append("## 2. 各政黨歷屆領先村里數")
    L.append("")
    L.append("| 政黨 | " + " | ".join(f"{y}" for y in years) + " |")
    L.append("|---|" + "---:|" * len(years))
    allp = []
    for st in stats:
        for p in st["parties"]:
            if p not in allp:
                allp.append(p)
    allp.sort(key=lambda p: -sum(st["grand"][p] for st in stats))
    for p in allp:
        if sum(st["grand"][p] for st in stats) == 0:
            continue
        L.append(f"| {p} | " + " | ".join(f"{st['grand'][p]:,}" for st in stats) + " |")
    L.append("| **唯一領先合計** | " + " | ".join(f"**{st['grand_n'] - st['grand_tie']:,}**" for st in stats) + " |")
    L.append("| 並列 | " + " | ".join(str(st["grand_tie"]) for st in stats) + " |")
    L.append("| **村里總數** | " + " | ".join(f"**{st['grand_n']:,}**" for st in stats) + " |")
    L.append("")
    L.append("> 註：各屆村里總數不同，係因 2014 年桃園縣升格、2018 年後各縣市多次里鄰編組調整，村里數本身有增減。")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="2012-2024 不分區政黨票村里領先政黨統計")
    ap.add_argument("--years", nargs="+", type=int, default=[2012, 2016, 2020, 2024])
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    ap.add_argument("--no-compare", action="store_true", help="不輸出跨屆比較檔")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    stats = []
    for year in args.years:
        if year not in YEAR_CFG:
            print(f"跳過未支援的年份 {year}")
            continue
        print(f"=== {year} ===")
        st = analyse_year(year)
        md = render(st)
        out = os.path.join(args.outdir, f"全臺灣{year}_村里領先政黨統計.md")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        grand = st["grand"]
        top = max(st["parties"], key=lambda p: grand[p])
        print(f"  村里 {st['grand_n']:,}（並列 {st['grand_tie']}）｜最大黨 {top} {grand[top]:,}"
              f"｜政黨數 {len(st['parties'])}｜並列村里 {len(st['ties'])}")
        print(f"  寫出 {out}")
        stats.append(st)

    if not args.no_compare and len(stats) > 1:
        out = os.path.join(args.outdir, "全臺灣2012-2024_村里領先政黨比較.md")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_compare(stats))
        print(f"寫出 {out}")


if __name__ == "__main__":
    sys.exit(main())
