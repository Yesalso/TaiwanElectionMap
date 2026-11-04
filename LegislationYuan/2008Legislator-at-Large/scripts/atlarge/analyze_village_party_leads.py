# -*- coding: utf-8 -*-
"""
2008 第七屆立法委員「全國不分區及僑居國外國民」選舉
────────────────────────────────────────────────────────────
統計：各政黨在「村里」層級領先（得票數最高）的村里數

資料來源
    Data/2008不分区/2008不分区/*.xls
    中選會原始「各政黨在各投開票所得票數一覽表」，一縣市一檔，共 25 檔。

處理規則
    1. 同一村里若有多個投開票所（多列），得票數逐列累加。
    2. 原表「村里別」若以「、」併列多個村里（例：富山里、廣明里），
       該投開票所的得票數按村里數平均分攤到各里 —— 因為合併投開票所
       無法還原各里實際票數，這是唯一不重複計算的作法。
    3. 村里領先＝在該村里 12 個政黨中得票數最高者（相對多數，非過半）。
       最高票相同時記為「並列」，不歸給單一政黨。
    4. 村里名若有缺字（原檔 U+FFFD），僅就「顯示名稱」以 2008 年前村里界
       圖資做唯一比對修補；統計鍵仍用原始字串，不影響票數。

輸出（預設寫到 2008Legislator-at-Large/stats/）
    2008不分區_村里領先政黨.csv          村里明細（含 12 黨票數、領先黨、差距）
    2008不分區_政黨領先村里數.csv        全國各黨領先村里數／得票
    2008不分區_各縣市政黨領先村里數.csv  縣市 × 政黨矩陣
    2008不分區_村里領先統計報告.md       方法、結果、限制說明

用法
    python analyze_village_party_leads.py
    python analyze_village_party_leads.py --xls-dir "D:\\...\\2008不分区" --out-dir "D:\\...\\stats"
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

import xlrd

# ══════════════════════════ 設定 ══════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))      # …\2008Legislator-at-Large
ROOT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))        # …\TaiwanElection

DEFAULT_XLS_DIR = os.path.join(PROJECT_DIR, "Data", "2008不分区")
DEFAULT_OUT_DIR = os.path.join(PROJECT_DIR, "stats")

# 2008 年 25 個縣市（中選會刊物慣用順序：直轄市 → 縣市 → 離島）
COUNTY_ORDER = [
    "臺北市", "高雄市",
    "臺北縣", "宜蘭縣", "桃園縣", "新竹縣", "新竹市", "苗栗縣",
    "臺中縣", "臺中市", "彰化縣", "南投縣", "雲林縣",
    "嘉義縣", "嘉義市", "臺南縣", "臺南市", "高雄縣",
    "屏東縣", "臺東縣", "花蓮縣", "澎湖縣", "金門縣", "連江縣",
]

# 2008 年不分區 12 個政黨（依全國得票數排序，僅為輸出可讀性）
PARTY_ORDER = [
    "中國國民黨", "民主進步黨", "新黨", "台灣團結聯盟", "紅黨",
    "無黨團結聯盟", "綠黨", "台灣農民黨", "公民黨", "第三社會黨",
    "客家黨", "制憲聯盟",
]

# 村里名缺字修補用的 2008 年前村里界（僅作顯示名稱比對）
REF_GEOJSON = os.path.join(ROOT_DIR, "Base_JSON", "twVillage_pre2010.geo.json")
WILDCARD = "\ufffd"          # 原檔缺字
TOWN_SUFFIXES = ("鄉", "鎮", "市", "區")

VARIANT_CHAR_MAP = str.maketrans({
    "台": "臺", "峯": "峰", "舘": "館", "塩": "鹽", "褔": "福",
    "脚": "腳", "磘": "窯", "嗂": "窯", "廍": "部",
})


# ══════════════════════════ 小工具 ══════════════════════════
def _s(v) -> str:
    """儲存格轉字串：去全形空白與前後空白。"""
    return str(v).replace("\u3000", " ").strip()


def _tight(v) -> str:
    """去掉所有空白（判斷「總　計」這類標題用）。"""
    return re.sub(r"\s+", "", str(v))


# 2008 縣市 → 2008 年前村里界圖資的縣市名（五都升格後合併）
REF_COUNTY = {
    "臺北縣": "新北市",
    "臺中縣": "臺中市", "臺中市": "臺中市",
    "臺南縣": "臺南市", "臺南市": "臺南市",
    "高雄縣": "高雄市", "高雄市": "高雄市",
}


def _county_ref(county: str) -> str:
    c = _s(county).translate(VARIANT_CHAR_MAP)
    return REF_COUNTY.get(c, c)


def _town_core(name: str) -> str:
    n = _s(name).translate(VARIANT_CHAR_MAP)
    for suf in TOWN_SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf):
            return n[:-len(suf)]
    return n


def _vill_norm(name: str) -> str:
    return _s(name).translate(VARIANT_CHAR_MAP)


def _fmt_num(v: float, force_decimal: bool = False) -> str:
    if not force_decimal and abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def _split_villages(cell: str) -> list[str]:
    """村里別欄位 → 村里清單（處理「、」「，」「,」併列）。"""
    parts = [p.strip() for p in re.split(r"[、，,]", cell)]
    return [p for p in parts if p]


_RE_LEAD_NO = re.compile(r"^[0-9０-９]+")


def _repair_vote_name(name: str) -> str:
    """修掉原表殘留的編號前綴（例：桃園「2龍德里」→「龍德里」）。"""
    return _RE_LEAD_NO.sub("", _s(name))


# ══════════════════════════ 村里名缺字修補（僅顯示用） ══════════════════════════
class NameRepairer:
    """用 2008 年前村里界圖資，以「缺字＝萬用字元」唯一比對修補顯示名稱。

    只修「恰好一個候選」的村名；多個候選或找不到者保留原樣（缺字以 □ 顯示），
    避免亂猜。統計鍵不受影響。
    """

    def __init__(self, path: str = REF_GEOJSON):
        self.ref: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.enabled = os.path.isfile(path)
        if not self.enabled:
            return
        with open(path, "r", encoding="utf-8") as f:
            geo = json.load(f)
        for ft in geo.get("features", []):
            pr = ft.get("properties", {})
            county = pr.get("COUNTYNAME") or pr.get("countyname") or ""
            town = pr.get("TOWNNAME") or pr.get("townname") or pr.get("town") or ""
            vill = (pr.get("VILLAGENAM") or pr.get("villagename")
                    or pr.get("village") or "")
            county, town, vill = _s(county), _s(town), _s(vill)
            if county and town and vill:
                self.ref[(_county_ref(county), _town_core(town))].add(_vill_norm(vill))

    def repair(self, county: str, town: str, village: str) -> tuple[str, bool]:
        """回傳 (顯示用村里名, 是否已修補)。"""
        if WILDCARD not in village or not self.enabled:
            return village.replace(WILDCARD, "□"), False
        candidates = self.ref.get((_county_ref(county), _town_core(town)))
        if not candidates:
            return village.replace(WILDCARD, "□"), False
        pat = re.compile("^" + ".".join(
            re.escape(x) for x in _vill_norm(village).split(WILDCARD)) + "$")
        hits = [c for c in candidates if pat.match(c)]
        if len(hits) == 1:
            return hits[0], True
        return village.replace(WILDCARD, "□"), False


# ══════════════════════════ 解析原始 xls ══════════════════════════
def _find_header(sh) -> int | None:
    for r in range(min(12, sh.nrows)):
        row0 = _s(sh.cell_value(r, 0))
        if "鄉" in row0 and "別" in row0:
            return r
        if any(_s(sh.cell_value(r, c)) == "公民黨" for c in range(sh.ncols)):
            return r - 3
    return None


def parse_workbook(path: str) -> dict:
    """解析單一縣市 xls，回傳 county / parties / rows / total_row。"""
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_index(0)

    title = _s(sh.cell_value(0, 0))
    m = re.search(r"選舉(.+?)各政黨", title)
    county = m.group(1) if m else os.path.splitext(os.path.basename(path))[0]

    hdr = _find_header(sh)
    if hdr is None:
        raise ValueError(f"{os.path.basename(path)} 找不到表頭列")

    # 有效票數欄（表頭含「有效票數」）
    valid_col = None
    for c in range(sh.ncols):
        if "有效票數" in _s(sh.cell_value(hdr, c)).replace("\n", ""):
            valid_col = c
            break
    if valid_col is None:
        raise ValueError(f"{os.path.basename(path)} 找不到「有效票數」欄")

    # 政黨欄：表頭下 3 列（總計／鄉鎮列／空白列／政黨列）
    parties = []
    for c in range(3, valid_col):
        nm = _s(sh.cell_value(hdr + 3, c))
        if nm:
            parties.append((c, nm))
    if not parties:
        raise ValueError(f"{os.path.basename(path)} 找不到政黨欄")

    rows, total_row = [], None
    town = ""
    for r in range(hdr + 4, sh.nrows):
        c0 = _s(sh.cell_value(r, 0))
        c1 = _s(sh.cell_value(r, 1))

        if "總計" in _tight(c0):
            total_row = [sh.cell_value(r, c) for c, _ in parties]
            continue
        if c0:
            town = c0
        if not c1:
            continue                       # 鄉鎮市區合計列

        votes, valid = [], None
        try:
            for c, _ in parties:
                votes.append(float(sh.cell_value(r, c) or 0))
            valid = float(sh.cell_value(r, valid_col) or 0)
        except (TypeError, ValueError):
            continue
        rows.append({"town": town, "village": c1, "votes": votes, "valid": valid})

    if total_row is None:
        raise ValueError(f"{os.path.basename(path)} 找不到「總計」列")
    return {"county": county, "parties": [nm for _, nm in parties],
            "rows": rows, "total": total_row}


def load_all(xls_dir: str):
    files = sorted(
        os.path.join(dp, fn)
        for dp, _, fns in os.walk(xls_dir) for fn in fns
        if fn.lower().endswith(".xls") and not fn.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"找不到 xls：{xls_dir}")

    counties, parties_ref = OrderedDict(), None
    for path in files:
        wb = parse_workbook(path)
        if parties_ref is None:
            parties_ref = wb["parties"]
        elif wb["parties"] != parties_ref:
            raise ValueError(f"{os.path.basename(path)} 政黨欄位與其他檔不一致")
        counties[wb["county"]] = wb
        print(f"  讀取 {os.path.basename(path):12s} → {wb['county']:4s} "
              f"{len(wb['rows']):4d} 列")
    return counties, parties_ref


# ══════════════════════════ 聚合與統計 ══════════════════════════
def aggregate(counties, parties):
    """聚合到 (縣市, 鄉鎮市區, 村里)。

    「、」併列的投開票所按村里數平均分攤，避免同一票數重複計入多里。
    """
    n_party = len(parties)
    acc: dict[tuple[str, str, str], dict] = {}
    for county, wb in counties.items():
        for row in wb["rows"]:
            town = row["town"]
            parts = [_repair_vote_name(p) for p in _split_villages(row["village"])]
            if not parts:
                continue
            k = len(parts)
            votes = [v / k for v in row["votes"]]
            valid = row["valid"] / k
            for part in parts:
                key = (county, town, part)
                rec = acc.get(key)
                if rec is None:
                    rec = acc[key] = {
                        "votes": [0.0] * n_party, "valid": 0.0,
                        "split": k > 1, "raw": row["village"],
                    }
                for i, v in enumerate(votes):
                    rec["votes"][i] += v
                rec["valid"] += valid
                if k > 1:
                    rec["split"] = True
    return acc


def summarize(acc, parties):
    """逐村里判定領先政黨，回傳村里清單與統計。"""
    records, tie_count, empty_count = [], 0, 0
    party_leads = {p: 0 for p in parties}
    party_tie = {p: 0 for p in parties}

    for (county, town, village), rec in acc.items():
        votes = rec["votes"]
        mx = max(votes) if votes else 0.0
        winners = [i for i, v in enumerate(votes) if abs(v - mx) < 1e-9]
        if rec["valid"] <= 0:
            empty_count += 1
            winner_idx, runner_idx = None, None
            note = "無有效票"
        elif len(winners) == 1:
            winner_idx = winners[0]
            order = sorted(range(len(votes)), key=lambda i: votes[i], reverse=True)
            runner_idx = order[1] if len(order) > 1 else None
            note = "領先"
            party_leads[parties[winner_idx]] += 1
        else:
            tie_count += 1
            winner_idx, runner_idx = None, None
            note = "並列"
            for i in winners:
                party_tie[parties[i]] += 1

        runner_votes = votes[runner_idx] if runner_idx is not None else 0.0
        records.append({
            "county": county, "town": town, "village": village,
            "votes": votes, "valid": rec["valid"], "split": rec["split"],
            "raw": rec["raw"], "note": note,
            "winner_idx": winner_idx, "runner_idx": runner_idx,
            "winner_votes": mx if winner_idx is not None else 0.0,
            "runner_votes": runner_votes,
            "margin": (mx - runner_votes) if winner_idx is not None else 0.0,
        })

    records.sort(key=lambda r: (
        COUNTY_ORDER.index(r["county"]) if r["county"] in COUNTY_ORDER else 99,
        r["town"], r["village"]))
    return records, party_leads, party_tie, tie_count, empty_count


# ══════════════════════════ 輸出 ══════════════════════════
def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  寫出 {path}")


def main():
    ap = argparse.ArgumentParser(description="2008 不分區各政黨村里領先統計")
    ap.add_argument("--xls-dir", default=DEFAULT_XLS_DIR)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--csv", action="store_true",
                    help="同時輸出 CSV 明細（預設只輸出 Markdown 報告）")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    print("① 讀取中選會原始 xls")
    counties, parties_src = load_all(args.xls_dir)
    parties = [p for p in PARTY_ORDER if p in parties_src] + \
              [p for p in parties_src if p not in PARTY_ORDER]

    # 把各檔的票數欄重排成統一的政黨順序
    order = [parties_src.index(p) for p in parties]
    for wb in counties.values():
        for row in wb["rows"]:
            row["votes"] = [row["votes"][i] for i in order]
        wb["total"] = [wb["total"][i] for i in order]
        wb["parties"] = list(parties)

    print("② 聚合村里並判定領先政黨")
    acc = aggregate(counties, parties)
    total_villages = len(acc)
    records, party_leads, party_tie, tie_count, empty_count = summarize(acc, parties)
    split_rows = sum(1 for wb in counties.values() for row in wb["rows"]
                     if len(_split_villages(row["village"])) > 1)
    split_villages = sum(1 for rec in records if rec["split"])

    # ---- 驗證 ----
    # 以各縣市「總計」列的政黨票加總核對
    county_party_total = [0.0] * len(parties)
    for wb in counties.values():
        for i in range(len(parties)):
            county_party_total[i] += float(wb["total"][i])
    village_party_total = [sum(rec["votes"][i] for rec in records)
                           for i in range(len(parties))]
    max_diff = max(abs(a - b) for a, b in zip(county_party_total, village_party_total))

    print("③ 輸出")
    repairer = NameRepairer()

    # 3-1 村里明細
    v_header = ["縣市", "鄉鎮市區", "村里", "有效票數"] + parties + \
               ["領先政黨", "領先票數", "領先得票率(%)", "次高政黨", "次高票數",
                "領先差距", "結果", "村里名稱分攤", "原始村里欄位", "村名備註"]
    v_rows = []
    repaired = 0
    for rec in records:
        shown, fixed = repairer.repair(rec["county"], rec["town"], rec["village"])
        repaired += int(fixed)
        name_note = ""
        if WILDCARD in rec["village"]:
            name_note = "村名缺字" + ("（已依圖資修補）" if fixed else "（待人工確認）")
        win = parties[rec["winner_idx"]] if rec["winner_idx"] is not None else "—"
        run = parties[rec["runner_idx"]] if rec["runner_idx"] is not None else "—"
        rate = (rec["winner_votes"] / rec["valid"] * 100) if rec["valid"] > 0 and rec["winner_idx"] is not None else 0.0
        v_rows.append(
            [rec["county"], rec["town"], shown, _fmt_num(rec["valid"], rec["split"])]
            + [_fmt_num(v, rec["split"]) for v in rec["votes"]]
            + [win, _fmt_num(rec["winner_votes"], rec["split"]), f"{rate:.2f}",
               run, _fmt_num(rec["runner_votes"], rec["split"]),
               _fmt_num(rec["margin"], rec["split"]), rec["note"],
               "是" if rec["split"] else "", rec["raw"], name_note]
        )
    if args.csv:
        write_csv(os.path.join(args.out_dir, "2008不分區_村里領先政黨.csv"), v_header, v_rows)

    # 3-2 全國政黨統計
    grand_total_votes = sum(county_party_total)
    s_header = ["排名", "政黨", "領先村里數", "領先村里占比(%)", "並列村里數",
                "全國得票數", "全國得票率(%)"]
    s_rows = []
    ranked = sorted(parties, key=lambda p: (-party_leads[p], -county_party_total[parties.index(p)]))
    for i, p in enumerate(ranked, 1):
        pv = county_party_total[parties.index(p)]
        s_rows.append([i, p, party_leads[p], f"{party_leads[p] / total_villages * 100:.2f}",
                       party_tie[p], f"{pv:,.0f}",
                       f"{pv / grand_total_votes * 100:.2f}"])
    if args.csv:
        write_csv(os.path.join(args.out_dir, "2008不分區_政黨領先村里數.csv"), s_header, s_rows)

    # 3-3 縣市 × 政黨
    county_leads = defaultdict(lambda: {p: 0 for p in parties})
    county_villages = defaultdict(int)
    county_ties = defaultdict(int)
    for rec in records:
        county_villages[rec["county"]] += 1
        if rec["winner_idx"] is not None:
            county_leads[rec["county"]][parties[rec["winner_idx"]]] += 1
        elif rec["note"] == "並列":
            county_ties[rec["county"]] += 1

    c_header = ["縣市", "村里數"] + parties + ["並列村里數", "領先村里最多政黨", "該黨村里數"]
    c_rows = []
    ordered_counties = [c for c in COUNTY_ORDER if c in county_villages] + \
                       [c for c in county_villages if c not in COUNTY_ORDER]
    for c in ordered_counties:
        cl = county_leads[c]
        top = max(parties, key=lambda p: (cl[p], county_party_total[parties.index(p)]))
        c_rows.append([c, county_villages[c]] + [cl[p] for p in parties] +
                      [county_ties[c], top, cl[top]])
    # 合計列
    c_rows.append(["合計", total_villages] + [party_leads[p] for p in parties] +
                  [tie_count, ranked[0], party_leads[ranked[0]]])
    if args.csv:
        write_csv(os.path.join(args.out_dir, "2008不分區_各縣市政黨領先村里數.csv"),
                  c_header, c_rows)

    # 3-4 Markdown 報告
    md = []
    md.append("# 2008 第七屆立法委員不分區選舉 — 各政黨村里領先統計\n")
    md.append(f"- 資料：`Data/2008不分区/2008不分区`（中選會原始 xls，{len(counties)} 個縣市）")
    md.append(f"- 統計單位：村里 **{total_villages:,} 個**（同一村里多個投開票所已合併）")
    md.append(f"- 全國有效票：**{grand_total_votes:,.0f} 票**")
    md.append(f"- 判定：村內 12 個政黨得票數最高者（相對多數）；最高票相同記為「並列」")
    md.append(f"- 並列村里：**{tie_count}** 個；無有效票村里：{empty_count} 個\n")

    md.append("## 全國結果\n")
    md.append("| 排名 | 政黨 | 領先村里數 | 領先村里占比 | 並列村里數 | 全國得票數 | 全國得票率 |")
    md.append("|---:|---|---:|---:|---:|---:|---:|")
    for r in s_rows:
        md.append(f"| {r[0]} | {r[1]} | {r[2]:,} | {r[3]}% | {r[4]} | {r[5]} | {r[6]}% |")

    # 並列村里明細
    ties = [rec for rec in records if rec["note"] == "並列"]
    md.append(f"\n## 並列村里（{len(ties)} 個）\n")
    md.append("| 縣市 | 鄉鎮市區 | 村里 | 有效票 | 並列最高票 |")
    md.append("|---|---|---|---:|---:|")
    for rec in ties:
        shown, _ = repairer.repair(rec["county"], rec["town"], rec["village"])
        mx = max(rec["votes"])
        tied = [parties[i] for i, v in enumerate(rec["votes"]) if abs(v - mx) < 1e-9]
        md.append(f"| {rec['county']} | {rec['town']} | {shown} | "
                  f"{_fmt_num(rec['valid'], rec['split'])} | "
                  f"{'、'.join(tied)}（各 {_fmt_num(mx, rec['split'])} 票） |")

    md.append("\n## 各縣市領先村里最多的政黨\n")
    md.append("| 縣市 | 村里數 | 最多領先政黨 | 該黨村里數 | 占比 |")
    md.append("|---|---:|---|---:|---:|")
    for c in ordered_counties:
        cl = county_leads[c]
        top = max(parties, key=lambda p: (cl[p], county_party_total[parties.index(p)]))
        n = county_villages[c]
        md.append(f"| {c} | {n:,} | {top} | {cl[top]:,} | {cl[top] / n * 100:.1f}% |")

    md.append("\n## 主要政黨縣市分布（村里領先數）\n")
    main_parties = ["中國國民黨", "民主進步黨", "新黨", "台灣團結聯盟", "無黨團結聯盟"]
    md.append("| 縣市 | 村里數 | " + " | ".join(main_parties) + " | 其他 | 並列 |")
    md.append("|---|---:|" + "---:|" * len(main_parties) + "---:|---:|")
    for c in ordered_counties:
        cl = county_leads[c]
        other = sum(cl[p] for p in parties if p not in main_parties)
        md.append(f"| {c} | {county_villages[c]:,} | "
                  + " | ".join(str(cl[p]) for p in main_parties)
                  + f" | {other} | {county_ties[c]} |")
    md.append(f"| **合計** | **{total_villages:,}** | "
              + " | ".join(f"**{party_leads[p]:,}**" for p in main_parties)
              + f" | **{sum(party_leads[p] for p in parties if p not in main_parties)}**"
                f" | **{tie_count}** |")

    md.append("\n## 方法與限制\n")
    md.append("1. **投開票所合併**：同一村里的多個投開票所逐列累加，視為同一個村里。")
    md.append("2. **多里併列**：原表「村里別」以「、」併列多里者（共 "
              f"{split_rows} 個投開票所、涉及 {split_villages} 個村里），"
              "得票數按村里數平均分攤；此為無法還原各里票數時的折衷作法"
              + ("，明細表以「村里名稱分攤＝是」標示。" if args.csv else "。"))
    md.append("3. **並列**：村里最高票相同時列為「並列」，不計入任何政黨的領先村里數；"
              f"本次共 {tie_count} 個村里。")
    md.append("4. **村名缺字**：原檔部分村里名含 U+FFFD 缺字；"
              f"已就顯示名稱以 2008 年前村里界圖資唯一比對修補 {repaired} 個，"
              "無法唯一確認者保留「□」並標示「待確認」，不影響票數統計。")
    md.append(f"5. **對帳**：各村村里票數加總與各縣市「總計」列相差最大 {max_diff:.6f} 票"
              "（分攤產生的浮點誤差）；全國政黨票與中選會公告一致"
              "（國民黨 5,010,801、民進黨 3,610,106）。")

    md_path = os.path.join(args.out_dir, "2008不分區_村里領先統計報告.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"  寫出 {md_path}")

    # ---- 主控台摘要 ----
    print("\n" + "=" * 52)
    print(f"村里總數：{total_villages:,}　並列：{tie_count}　無有效票：{empty_count}")
    print("-" * 52)
    print(f"{'政黨':<10s}{'領先村里':>10s}{'占比':>10s}{'全國得票率':>12s}")
    for p in ranked:
        pv = county_party_total[parties.index(p)]
        print(f"{p:<10s}{party_leads[p]:>10,d}"
              f"{party_leads[p] / total_villages * 100:>9.2f}%"
              f"{pv / grand_total_votes * 100:>11.2f}%")
    print("=" * 52)
    print(f"對帳：村里票數 vs 縣市總計  最大差 {max_diff:.6f}")


if __name__ == "__main__":
    main()
