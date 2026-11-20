#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 7~11 屆立法委員選舉（2008/2012/2016/2020/2024）— 政黨 × 鄉鎮市區 得票抓取
==============================================================================
2008（第 7 屆）：本地資料
  D:/Windows/TaiwanElection/LegislationYuan/2008Legislator-at-Large/Data/区域/p07_T1_*.xls
  （25 個檔案 = 25 縣市；每檔多個工作表 = 各選舉區；
   行0 標題、行3 候選人、行4 政黨、行5 總計、行6+ 鄉鎮市區彙總列 + 各投開票所列）

2012/2016/2020/2024（第 8~11 屆）：政治大學選舉研究中心 vote3.asp
  入口頁（10 欄：地區/姓名/號次/性別/出生年次/推薦政黨/得票數/得票率/當選否/是否現任）
  下鑽：地區欄的 vote31.asp 連結 → 一頁即含「該選舉區全部候選人 × 各鄉鎮市區」得票
  （5 欄：地區/姓名/號次/得票數/得票率，地區欄 = 選舉區名 + 鄉鎮市區名）
  注意：這四屆頁面為 UTF-8 編碼（1992-2004 為 Big5）。

輸出：與 scrape_legislator_1992_2004_party.py 完全相同的交叉表格式，
每屆一個 xlsx 至 data/ 子目錄，含兩個工作表：
  - 鄉鎮市區級別：縣市 | 鄉鎮市區 | {政黨}得票數/得票率 ... | 總得票數
  - 縣市級別：    縣市 | {政黨}得票數/得票率 ... | 總得票數
（總得票數 = 該鄉鎮市區全部區域候選人得票合計，不含政黨票）

用法：
    python scrape_legislator_2008_2024_party.py          # 全部五屆
    python scrape_legislator_2008_2024_party.py 2008     # 只跑某屆
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
# 2008：本地 xls 解析
# ======================================================================

def parse_2008_file(path):
    """單一縣市檔案 → (縣市, 政黨清單, [(縣市, 鄉鎮市區, {政黨: 票})])。"""
    wb = xlrd.open_workbook(path)
    parties_all = OrderedDict()
    town_rows = OrderedDict()

    for sh in wb.sheets():
        title = str(sh.cell_value(0, 0))
        county = None
        for c in COUNTIES:
            if c in title:
                county = c
                break
        if county is None:
            raise ValueError(f"{path} sheet {sh.name} 標題找不到縣市：{title}")

        # 行3 候選人 / 行4 政黨（欄位自第 3 欄起）
        n_cand = 0
        while (3 + n_cand) < sh.ncols and not blank(sh.cell_value(3, 3 + n_cand)):
            n_cand += 1
        sheet_parties = [str(sh.cell_value(4, 3 + j)).strip() for j in range(n_cand)]
        for p in sheet_parties:
            parties_all.setdefault(p, None)

        # 行5 總計列
        total_row = None
        for r in range(sh.nrows):
            v = sh.cell_value(r, 0)
            if not blank(v) and "總" in str(v):
                total_row = r
                break
        if total_row is None:
            raise ValueError(f"{path} sheet {sh.name} 找不到總計列")

        # 行6+：鄉鎮市區彙總列（col0 有值、col1 空白、非「總計/小計」）
        for r in range(total_row + 1, sh.nrows):
            c0 = "" if blank(sh.cell_value(r, 0)) else str(sh.cell_value(r, 0)).strip()
            c1 = "" if blank(sh.cell_value(r, 1)) else str(sh.cell_value(r, 1)).strip()
            if not c0 or c1 or "計" in c0:
                continue
            votes = {p: to_int(sh.cell_value(r, 3 + j))
                     for j, p in enumerate(sheet_parties)}
            d = town_rows.setdefault((county, c0), {})
            for p, v in votes.items():
                d[p] = d.get(p, 0) + v

    return county, parties_all, town_rows


def scrape_2008():
    print("\n" + "=" * 62)
    print("  2008 年 第七屆立法委員選舉（本地 xls：區域候選人投開票所一覽表）")
    print("=" * 62)

    parties_all = OrderedDict()
    town_rows = {}       # (縣市, 鄉鎮市區) -> {政黨: 票}
    files = sorted(
        f for f in os.listdir(DIR_2008) if f.lower().endswith(".xls")
    )
    for fn in files:
        path = os.path.join(DIR_2008, fn)
        county, pmap, trows = parse_2008_file(path)
        for p in pmap:
            parties_all.setdefault(p, None)
        for key, votes in trows.items():
            d = town_rows.setdefault(key, {})
            for p, v in votes.items():
                d[p] = d.get(p, 0) + v
        print(f"  {county}：{len(trows)} 個鄉鎮市區（{fn}）")

    parties = list(parties_all)
    print(f"政黨：{len(parties)} 個 -> {'、'.join(parties)}")
    return parties, town_rows


# ======================================================================
# 2012~2024：vote3.asp 爬取
# ======================================================================

def parse_candidates(html, party_override=None):
    """vote3.asp（10 欄）→ [(選舉區名, vote31 連結)]、政黨清單、號次→政黨對照表。
    party_override：{姓名: 歸類政黨}，覆寫頁面登記政黨。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return [], [], {}
    district_links = OrderedDict()   # href -> 選舉區名
    parties = OrderedDict()          # 政黨 -> 候選人數
    num2party = {}                   # (選舉區, 姓名, 號次) -> 政黨
    party_override = party_override or {}
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) != 10 or not vals[6].isdigit():
            continue
        a = cells[0].find("a")
        if not a:
            continue
        href = a.get("href")
        if href:
            district_links[href] = vals[0]
        p = party_override.get(vals[1], vals[5])
        parties[p] = parties.get(p, 0) + 1
        num2party[(vals[0], vals[1], vals[2])] = p
    return list(district_links.items()), list(parties), num2party


def parse_district_townships(html, district, num2party):
    """vote31.asp（5 欄）→ [(鄉鎮市區, 政黨, 票數)]；此頁含全選區所有候選人。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows = []
    if not table:
        return rows
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 5:
            continue
        area = vals[0]
        if not area.startswith(district):
            continue
        votes = vals[3]
        if not votes.isdigit():
            continue
        township = area[len(district):].strip()
        party = num2party.get((district, vals[1], vals[2]))
        if township and party:
            rows.append((township, party, int(votes)))
    return rows


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
    districts, parties, num2party = parse_candidates(
        html, CANDIDATE_PARTY_OVERRIDE.get(year))
    if not districts:
        print("入口頁未解析出任何選舉區，跳過本屆。")
        return None
    n_cand = len(num2party)
    print(f"選舉區：{len(districts)} 個；候選人：{n_cand} 位；政黨：{len(parties)} 個")
    for p in parties:
        print(f"  {p}: {sum(1 for v in num2party.values() if v == p)} 人")

    town_rows = {}   # (縣市, 鄉鎮市區) -> {政黨: 票}
    for i, (href, district) in enumerate(districts, 1):
        url = href if href.startswith("http") else BASE_URL + href
        html = fetch_page(session, url)
        if not html:
            print(f"  ⚠ {district} 下鑽頁抓取失敗")
            continue
        co = county_of(district)
        for township, party, votes in parse_district_townships(html, district, num2party):
            key = (co, township)
            d = town_rows.setdefault(key, {})
            d[party] = d.get(party, 0) + votes
        time.sleep(DELAY)
        if i % 20 == 0 or i == len(districts):
            print(f"  進度：{i}/{len(districts)}")

    if not town_rows:
        print("未取得任何鄉鎮市區資料，跳過本屆。")
        return None
    return parties, town_rows


# ======================================================================
# 輸出（與 1992-2004 版完全相同的格式）
# ======================================================================

def write_xlsx(county_totals, town_rows, parties, path):
    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
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

    def fill_body(ws, prefix, data_keys, data_lookup):
        pcol = len(prefix(data_keys[0]))
        for r, key in enumerate(data_keys, 2):
            d = data_lookup.get(key) or {}
            total = d.get("_TOTAL_", 0)
            for pc, val in enumerate(prefix(key), 1):
                cell = ws.cell(row=r, column=pc, value=val)
                cell.border = border
            for pi, p in enumerate(parties):
                votes = d.get(p, 0)
                cell = ws.cell(row=r, column=pcol + 1 + pi * 2, value=votes)
                cell.border = border
                rate = f"{votes / total * 100:.2f}%" if total else "-"
                cell2 = ws.cell(row=r, column=pcol + 2 + pi * 2, value=rate)
                cell2.border = border
            ws.cell(row=r, column=pcol + 1 + len(parties) * 2, value=total).border = border

    def widths(ws, prefix_len, parties):
        for i in range(prefix_len):
            ws.column_dimensions[get_column_letter(i + 1)].width = 14
        last = prefix_len + len(parties) * 2 + 1
        for i in range(len(parties)):
            ws.column_dimensions[get_column_letter(prefix_len + 1 + i * 2 + 1)].width = 12
            ws.column_dimensions[get_column_letter(prefix_len + 1 + i * 2 + 2)].width = 10
        ws.column_dimensions[get_column_letter(last)].width = 10

    # ---------- Sheet 1：鄉鎮市區級別 ----------
    ws1 = wb.create_sheet("鄉鎮市區級別")
    headers1 = ["縣市", "鄉鎮市區"]
    for p in parties:
        headers1.append(f"{p}得票數")
        headers1.append(f"{p}得票率")
    headers1.append("總得票數")
    style_header(ws1, headers1)

    town_keys = sorted(town_rows.keys())
    fill_body(ws1, lambda k: [k[0], k[1]], town_keys, town_rows)
    widths(ws1, 2, parties)
    ws1.freeze_panes = "C2"

    # ---------- Sheet 2：縣市級別 ----------
    county_totals = {}
    for (co, _town), d in town_rows.items():
        cd = county_totals.setdefault(co, {})
        for p, v in d.items():
            cd[p] = cd.get(p, 0) + v

    ws2 = wb.create_sheet("縣市級別")
    headers2 = ["縣市"]
    for p in parties:
        headers2.append(f"{p}得票數")
        headers2.append(f"{p}得票率")
    headers2.append("總得票數")
    style_header(ws2, headers2)

    county_keys = sorted(county_totals.keys())
    fill_body(ws2, lambda k: [k], county_keys, county_totals)
    widths(ws2, 1, parties)
    ws2.freeze_panes = "B2"

    wb.save(path)
    print(f"\n完成！已儲存至 '{path}'")
    print(f"  政黨：{len(parties)} 個")
    print(f"  鄉鎮市區級別：{len(town_keys)} 個鄉鎮市區")
    print(f"  縣市級別：{len(county_keys)} 個縣市")


def run_year(session, year):
    output = os.path.join(DATA_DIR, f"{year}立法委員_政黨鄉鎮得票.xlsx")
    if year == 2008:
        result = scrape_2008()
    else:
        token = dict((y, t) for y, t in ELECTIONS_WEB)[year]
        result = scrape_web_year(session, year, token)
    if not result:
        print(f"{year} 年失敗。")
        return False
    parties, town_rows = result

    # 補上各政黨票數（town_rows 內缺的政黨補 0），並計算 _TOTAL_
    for key, d in town_rows.items():
        d["_TOTAL_"] = sum(v for p, v in d.items() if p != "_TOTAL_")
    write_xlsx({}, town_rows, parties, output)
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
