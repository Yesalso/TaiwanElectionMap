#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 7~11 屆立法委員選舉（2008/2012/2016/2020/2024）— 各「選舉區」得票抓取
==============================================================================
輸出層級：只到「選舉區」（區域立法委員 73 個選舉區），不再彙總到鄉鎮市區／縣市。

2008（第 7 屆）：本地資料
  D:/Windows/TaiwanElection/LegislationYuan/2008Legislator-at-Large/Data/区域/p07_T1_*.xls
  （25 個檔案；每檔多個工作表 = 各選舉區，共 73 個工作表 = 73 個選舉區；
   行0 標題（含「臺北市第1選舉區」等選舉區名）、行3 候選人姓名、
   行4 政黨、行5 總計列（= 該選舉區各候選人得票數）、行5 之後為鄉鎮市區／投開票所）

2012/2016/2020/2024（第 8~11 屆）：政治大學選舉研究中心 vote3.asp
  入口頁（10 欄：地區/姓名/號次/性別/出生年次/推薦政黨/得票數/得票率/當選否/是否現任）
  該頁每列即一位區域候選人的「選舉區總得票數」，本版直接採用入口頁數據，
  不再下鑽 vote31.asp（鄉鎮市區層級已不在輸出範圍內）。
  注意：這四屆頁面為 UTF-8 編碼。

★ 無黨籍處理（重點）
  舊版以 (縣市, 鄉鎮市區) 為列、以「無黨籍及未經政黨推薦」單一欄位彙總，
  會把「同一縣市不同選舉區、彼此毫無關係的多位無黨籍候選人」票數加總，
  造成得票率失真（例如 2020 屏東 蘇震清 與 苗栗 陳超明 被併成一欄）。
  本版：
    1) 只輸出選舉區層級，不做跨區加總；
    2) 政黨推薦候選人 → 以政黨為欄位（單一選區制下，同區同黨僅一人）；
    3) 無黨籍候選人 → 逐人獨立欄位「無黨籍-姓名」，絕不合併；
    4) 另附「候選人明細」長表，逐人列出姓名／號次／政黨／得票數／得票率／當選。

輸出：每屆一個 xlsx 至 data/ 子目錄（檔名 {year}立法委員_選舉區得票.xlsx），
      含兩個工作表：
  - 選舉區級別：縣市 | 選舉區 | 候選人數 | 無黨籍候選人數 |
                {政黨}得票數/得票率 ... | 無黨籍-{姓名}得票數/得票率 ... | 總有效票數
  - 候選人明細：縣市 | 選舉區 | 號次 | 姓名 | 政黨 | 得票數 | 得票率 | 當選
（總有效票數 = 該選舉區全部區域候選人得票合計，不含政黨票；2008 取 xls 有效票數A）

用法：
    python "scrape_legislator_2008_2024_party - 副本.py"          # 全部五屆
    python "scrape_legislator_2008_2024_party - 副本.py" 2008     # 只跑某屆
"""

import os
import re
import sys
import time
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import xlrd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BASE_URL = "https://vote.nccu.edu.tw/cec/"

# 2008 本地原始資料（區域候選人投開票所一覽表）
DIR_2008 = r"D:/Windows/TaiwanElection/LegislationYuan/2008Legislator-at-Large/Data/区域"

# ===================== 第 8~11 屆入口 token（pass1） =====================
ELECTIONS_WEB = [
    # (年份, token)
    (2012, "J:89:I8888888888iii(("),
    (2016, "J:89%3EI8888888888iii("),
    (2020, "J:8:8I8888888888iii(("),
    (2024, "J:8:%3CI8888888888iii(("),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# 候選人政黨歸類修正（NCCU 頁面登記為無黨籍，依實際黨籍歸類）
# 僅影響指定屆別；key=候選人姓名, value=歸類政黨
CANDIDATE_PARTY_OVERRIDE = {
    2020: {"蘇震清": "民主進步黨"},   # 蘇震清（屏東，頁面登記無黨籍）→ 民進黨
    2024: {"陳超明": "中國國民黨"},   # 陳超明（苗栗，頁面登記無黨籍）→ 國民黨
}
DELAY = 0.2
RETRY = 4

# 兩代縣市名合併清單（2008 為 25 縣市；2012 起五都改制後為 22 縣市）
COUNTIES = [
    "臺北市", "新北市", "高雄市", "桃園市", "臺中市", "臺南市",
    "臺北縣", "宜蘭縣", "桃園縣", "新竹縣", "苗栗縣", "臺中縣",
    "彰化縣", "南投縣", "雲林縣", "嘉義縣", "臺南縣", "高雄縣",
    "屏東縣", "臺東縣", "花蓮縣", "澎湖縣", "基隆市", "新竹市",
    "嘉義市", "金門縣", "連江縣",
]

# 無黨籍在各資料源的登記字樣（NCCU 2012+ 為「無黨籍及未經政黨推薦」）
INDEPENDENT_PREFIX = "無黨籍"

# 2008 工作表標題：「第7屆立法委員區域選舉臺北市第1選舉區候選人在各投開票所得票數一覽表」
TITLE_RE = re.compile(r"立法委員區域選舉(.+?)候選人在各投開票所")


def fetch_page(session, url, retry=RETRY):
    """抓網頁；2012+ 頁面為 UTF-8，失敗時退回 Big5。"""
    for attempt in range(1, retry + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            text = r.content.decode("utf-8", errors="strict")
            return text
        except UnicodeDecodeError:
            try:
                return r.content.decode("big5", errors="replace")
            except Exception:
                pass
        except Exception as e:
            print(f"  請求失敗（{attempt}/{retry}）：{url} -> {e}")
        if attempt < retry:
            time.sleep(DELAY * 3)
    return None


def county_of(district):
    """由選舉區名取縣市：去掉結尾『第X選舉區/第X選區』後比對縣市清單。"""
    name = re.sub(r"第[一二三四五六七八九十\d]+選(?:舉)?區$", "", district).strip()
    for c in COUNTIES:
        if name.startswith(c):
            return c
    return name


def is_independent(party):
    """是否為無黨籍（含「無黨籍及未經政黨推薦」）。"""
    return (party or "").startswith(INDEPENDENT_PREFIX)


def to_int(v):
    """xls 數值（float）或字串 → int。"""
    if v in ("", None):
        return 0
    try:
        return int(round(float(str(v).strip().replace(",", ""))))
    except (ValueError, TypeError):
        return 0


def blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


# ======================================================================
# 2008：本地 xls 解析（每工作表 = 一個選舉區，直接取「總計」列）
# ======================================================================

def parse_2008_file(path):
    """單一縣市檔案 → [ {county, district, cands:[{num,name,party,votes,elected}], valid} ]"""
    wb = xlrd.open_workbook(path)
    recs = []
    for sh in wb.sheets():
        title = str(sh.cell_value(0, 0)).strip()
        m = TITLE_RE.search(title)
        if not m:
            raise ValueError(f"{path} sheet {sh.name} 標題無法解析選舉區：{title}")
        district = m.group(1).strip()
        county = county_of(district)

        # 行3 候選人姓名 / 行4 政黨（欄位自第 3 欄起）
        n_cand = 0
        while (3 + n_cand) < sh.ncols and not blank(sh.cell_value(3, 3 + n_cand)):
            n_cand += 1

        # 總計列（該選舉區各候選人得票數）
        total_row = None
        for r in range(sh.nrows):
            v = sh.cell_value(r, 0)
            if not blank(v) and "總" in str(v):
                total_row = r
                break
        if total_row is None:
            raise ValueError(f"{path} sheet {sh.name} 找不到總計列")

        cands = []
        for j in range(n_cand):
            num = j + 1
            raw_num = str(sh.cell_value(2, 3 + j)).strip()
            mm = re.search(r"\d+", raw_num)
            if mm:
                num = int(mm.group(0))
            party = str(sh.cell_value(4, 3 + j)).strip() or "無黨籍及未經政黨推薦"
            cands.append({
                "num": num,
                "name": str(sh.cell_value(3, 3 + j)).strip(),
                "party": party,
                "votes": to_int(sh.cell_value(total_row, 3 + j)),
                "elected": None,        # 2008 xls 未提供當選欄位
            })

        # 有效票數A（候選人欄之後第一欄）
        valid = 0
        if (3 + n_cand) < sh.ncols:
            valid = to_int(sh.cell_value(total_row, 3 + n_cand))
        if not valid:
            valid = sum(c["votes"] for c in cands)

        recs.append({"county": county, "district": district,
                     "cands": cands, "valid": valid})
    return recs


def scrape_2008():
    print("\n" + "=" * 62)
    print("  2008 年 第七屆立法委員選舉（本地 xls：區域候選人投開票所一覽表）")
    print("=" * 62)

    districts = []
    files = sorted(f for f in os.listdir(DIR_2008) if f.lower().endswith(".xls"))
    for fn in files:
        recs = parse_2008_file(os.path.join(DIR_2008, fn))
        districts.extend(recs)
        print(f"  {recs[0]['county']}：{len(recs)} 個選舉區（{fn}）")

    n_cand = sum(len(r["cands"]) for r in districts)
    print(f"選舉區：{len(districts)} 個；候選人：{n_cand} 位")
    return districts


# ======================================================================
# 2012~2024：vote3.asp 入口頁（每列 = 一位候選人的選舉區總得票）
# ======================================================================

def parse_entry(html, party_override=None):
    """vote3.asp（10 欄）→ (選舉區順序, [ {county,district,cands,valid} ])。

    party_override：{姓名: 歸類政黨}，覆寫頁面登記政黨。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    party_override = party_override or {}
    grouped = OrderedDict()
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        # 只收「號次為數字」的資料列（表頭列 10 欄但號次為文字，須排除）
        if len(vals) != 10 or not vals[2].isdigit():
            continue
        district = vals[0]
        if not district:
            continue
        party = party_override.get(vals[1], vals[5]) or "無黨籍及未經政黨推薦"
        votes = int(vals[6]) if vals[6].isdigit() else 0
        rate = vals[7]
        grouped.setdefault(district, []).append({
            "num": vals[2],
            "name": vals[1],
            "party": party,
            "group": vals[5],          # 頁面登記政黨（未套用 override）
            "votes": votes,
            "rate": rate,
            "elected": vals[8],        # Y / N
            "incumbent": vals[9],      # Y / N
        })

    recs = []
    for district, cands in grouped.items():
        recs.append({
            "county": county_of(district),
            "district": district,
            "cands": cands,
            "valid": sum(c["votes"] for c in cands),
        })
    return recs


def scrape_web_year(session, year, token):
    start_url = BASE_URL + "vote3.asp?pass1=" + token
    print("\n" + "=" * 62)
    print(f"  {year} 年 立法委員選舉（vote3.asp，UTF-8）")
    print("=" * 62)
    print(f"入口頁：{start_url}")

    html = fetch_page(session, start_url)
    if not html:
        print("入口頁抓取失敗，跳過本屆。")
        return None
    districts = parse_entry(html, CANDIDATE_PARTY_OVERRIDE.get(year))
    if not districts:
        print("入口頁未解析出任何選舉區，跳過本屆。")
        return None

    n_cand = sum(len(r["cands"]) for r in districts)
    parties = OrderedDict()
    for r in districts:
        for c in r["cands"]:
            parties[c["party"]] = parties.get(c["party"], 0) + 1
    n_indep = sum(1 for r in districts for c in r["cands"] if is_independent(c["party"]))
    print(f"選舉區：{len(districts)} 個；候選人：{n_cand} 位；"
          f"政黨：{len(parties)} 個；無黨籍候選人：{n_indep} 位")
    return districts


# ======================================================================
# 欄位規劃（政黨彙總 + 無黨籍逐人）
# ======================================================================

def build_columns(districts):
    """回傳 (政黨欄位清單, 無黨籍候選人欄位清單)。

    政黨欄位：(政黨,)；無黨籍欄位：(欄名, 選舉區, 姓名)。"""
    party_total = {}
    indep_entries = []
    for rec in districts:
        occ = {}
        for c in rec["cands"]:
            if is_independent(c["party"]):
                k = c["name"]
                o = occ.get(k, 0)
                occ[k] = o + 1
                indep_entries.append({
                    "district": rec["district"], "name": c["name"],
                    "occ": o, "votes": c["votes"],
                })
            else:
                party_total[c["party"]] = party_total.get(c["party"], 0) + c["votes"]

    parties = [p for p, _ in sorted(party_total.items(), key=lambda kv: (-kv[1], kv[0]))]
    indep_entries.sort(key=lambda e: (-e["votes"], e["district"], e["name"]))

    used = set()
    indep_cols = []
    for e in indep_entries:
        key = f"無黨籍-{e['name']}"
        if key in used:
            key = f"無黨籍-{e['name']}（{e['district']}）"
        base = key
        n = 2
        while key in used:
            key = f"{base}#{n}"
            n += 1
        used.add(key)
        indep_cols.append((key, e["district"], e["name"], e["occ"]))
    return parties, indep_cols


# ======================================================================
# 輸出
# ======================================================================

def write_xlsx(districts, path, year):
    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    indep_fill = PatternFill(start_color="8FAADC", end_color="8FAADC", fill_type="solid")
    border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    def style_header(ws, headers):
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center",
                                       wrap_text=True)
            cell.border = border

    def num_text(num):
        s = str(num)
        return s.zfill(2) if s.isdigit() else s

    def rate(votes, total):
        return f"{votes / total * 100:.2f}%" if total else "-"

    parties, indep_cols = build_columns(districts)

    # ---------- Sheet 1：選舉區級別 ----------
    ws1 = wb.create_sheet("選舉區級別")
    prefix = ["縣市", "選舉區", "候選人數", "無黨籍候選人數"]
    headers1 = list(prefix)
    for p in parties:
        headers1.append(f"{p}得票數")
        headers1.append(f"{p}得票率")
    for key, _d, _n, _o in indep_cols:
        headers1.append(f"{key}得票數")
        headers1.append(f"{key}得票率")
    headers1.append("總有效票數")
    style_header(ws1, headers1)
    # 無黨籍逐人欄位改用較淺底色，避免與政黨欄位混淆
    pstart = len(prefix) + len(parties) * 2 + 1
    for c in range(pstart, pstart + len(indep_cols) * 2):
        ws1.cell(row=1, column=c).fill = indep_fill

    for r, rec in enumerate(districts, 2):
        cands = rec["cands"]
        total = rec["valid"]
        party_votes = {}
        indep_votes = {}      # (姓名, 同名出現序) -> 票數；只放本選舉區的無黨籍
        occ = {}
        for c in cands:
            if is_independent(c["party"]):
                k = c["name"]
                o = occ.get(k, 0)
                occ[k] = o + 1
                indep_votes[(k, o)] = indep_votes.get((k, o), 0) + c["votes"]
            party_votes[c["party"]] = party_votes.get(c["party"], 0) + c["votes"]

        # 前 4 欄
        head = [rec["county"], rec["district"], len(cands),
                sum(1 for c in cands if is_independent(c["party"]))]
        for ci, v in enumerate(head, 1):
            ws1.cell(row=r, column=ci, value=v).border = border

        col = len(prefix) + 1
        # 政黨欄位（單一選區制：同區同黨僅一人）
        for p in parties:
            v = party_votes.get(p, 0)
            ws1.cell(row=r, column=col, value=v).border = border
            ws1.cell(row=r, column=col + 1, value=rate(v, total)).border = border
            col += 2
        # 無黨籍逐人欄位：非本選舉區的候選人留空，不填 0 以免誤讀
        for _key, d, n, o in indep_cols:
            if d == rec["district"] and (n, o) in indep_votes:
                v = indep_votes[(n, o)]
                ws1.cell(row=r, column=col, value=v).border = border
                ws1.cell(row=r, column=col + 1, value=rate(v, total)).border = border
            col += 2
        ws1.cell(row=r, column=col, value=total).border = border

    widths1 = [8, 18, 8, 12]
    for i, w in enumerate(widths1, 1):
        ws1.column_dimensions[get_column_letter(i)].width = w
    for i in range(len(parties) + len(indep_cols)):
        ws1.column_dimensions[get_column_letter(len(prefix) + 1 + i * 2)].width = 10
        ws1.column_dimensions[get_column_letter(len(prefix) + 2 + i * 2)].width = 9
    ws1.column_dimensions[get_column_letter(len(headers1))].width = 11
    ws1.freeze_panes = "C2"
    ws1.auto_filter.ref = f"A1:{get_column_letter(len(headers1))}{len(districts) + 1}"

    # ---------- Sheet 2：候選人明細（無黨籍逐人，不合併） ----------
    ws2 = wb.create_sheet("候選人明細")
    headers2 = ["縣市", "選舉區", "號次", "姓名", "政黨", "得票數", "得票率", "當選"]
    style_header(ws2, headers2)

    r = 2
    for rec in districts:
        total = rec["valid"]
        for c in rec["cands"]:
            vals = [rec["county"], rec["district"], num_text(c["num"]), c["name"],
                    c["party"], c["votes"], rate(c["votes"], total),
                    "當選" if c.get("elected") == "Y" else ""]
            for ci, v in enumerate(vals, 1):
                cell = ws2.cell(row=r, column=ci, value=v)
                cell.border = border
            if is_independent(c["party"]):
                ws2.cell(row=r, column=5).font = Font(italic=True, color="C00000")
            r += 1

    for i, w in enumerate([8, 18, 6, 10, 24, 10, 9, 8], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:H{r - 1}"

    wb.save(path)
    n_indep = sum(1 for rec in districts for c in rec["cands"] if is_independent(c["party"]))
    print(f"\n完成！已儲存至 '{path}'")
    print(f"  選舉區：{len(districts)} 個；候選人：{r - 2} 位")
    print(f"  政黨欄位：{len(parties)} 個；無黨籍逐人欄位：{len(indep_cols)} 個"
          f"（無黨籍候選人 {n_indep} 位，未合併計算）")


def run_year(session, year):
    output = os.path.join(DATA_DIR, f"{year}立法委員_選舉區得票.xlsx")
    if year == 2008:
        districts = scrape_2008()
    else:
        token = dict((y, t) for y, t in ELECTIONS_WEB)[year]
        districts = scrape_web_year(session, year, token)
    if not districts:
        print(f"{year} 年失敗。")
        return False
    write_xlsx(districts, output, year)
    return True


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    only = [int(a) for a in sys.argv[1:] if a.isdigit()] or \
           [2008] + [y for y, _ in ELECTIONS_WEB]
    session = requests.Session()
    ok, bad = [], []
    for year in only:
        try:
            if run_year(session, year):
                ok.append(year)
            else:
                bad.append(year)
        except Exception as e:
            print(f"{year} 年發生錯誤：{e}")
            bad.append(year)

    print("\n" + "#" * 62)
    print(f"全部完成：成功 {ok}；失敗 {bad if bad else '無'}")


if __name__ == "__main__":
    sys.exit(main())
