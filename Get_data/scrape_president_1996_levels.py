#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
96 年總統(副總統)選舉 — 縣市 + 鄉鎮市區 兩層級爬蟲（交叉表輸出）
===========================================================
入口：vote3.asp 全國概況（含候選人清單）
下鑽：vote312.asp 縣市級別 → vote313.asp 鄉鎮市區級別

輸出一個 xlsx，含兩個工作表，每個候選人佔兩欄（得票數、得票率）：
  - 「縣市級別」：欄位 = 縣市 | 候選人1得票數 | 候選人1得票率 | 候選人2得票數 | ...
  - 「鄉鎮市區級別」：欄位 = 縣市 | 鄉鎮市區 | 候選人1得票數 | 候選人1得票率 | ...

用法：
    python scrape_president_1996_levels.py
"""

import os
import time

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

START_URL = "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=I9AA%3EI8888888888iii(("
BASE_URL = "https://vote.nccu.edu.tw/cec/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
DELAY = 0.3
RETRY = 3


def fetch_page(url, retry=RETRY):
    for attempt in range(1, retry + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = "big5"
            return r.text
        except Exception as e:
            print(f"  請求失敗（{attempt}/{retry}）：{url} -> {e}")
            if attempt < retry:
                time.sleep(DELAY * 2)
    return None


def join_url(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    return BASE_URL + href


def rows_of(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 5:
            continue
        a = cells[1].find("a")
        yield {
            "area": vals[0],          # 縣市 或 縣市+鄉鎮市區（字串相連）
            "name": vals[1],
            "number": vals[2],
            "votes": vals[3],
            "rate": vals[4],
            "detail_url": join_url(a.get("href")) if a else None,
        }


def parse_national(html):
    """vote3.asp：候選人清單（地區/姓名/號次/政黨/得票數/得票率 + 縣市層網址）"""
    candidates = []
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find("table").find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 8:
            continue
        a = cells[1].find("a")
        if not a:
            continue
        candidates.append(
            {
                "region": vals[0],
                "name": a.get_text(strip=True),
                "number": vals[2],
                "party": vals[5],
                "votes": vals[6],
                "rate": vals[7],
                "detail_url": join_url(a.get("href")),
            }
        )
    return candidates


def write_xlsx(candidates, county_rows, town_rows, path):
    """交叉表格式：每候選人兩欄（得票數、得票率）。"""
    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    def new_sheet(title):
        ws = wb.create_sheet(title)
        ws.freeze_panes = "A2"
        return ws

    def style_header(ws, headers):
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border
            ws.column_dimensions[get_column_letter(c)].width = max(8, len(h) * 1.8)

    def cand_col(prefix_count, key):
        return prefix_count + 1 + (key * 2)  # 候選人得票數欄位；+1 為得票率

    # ---------- Sheet 1：縣市級別 ----------
    ws1 = new_sheet("縣市級別")
    headers1 = ["縣市"]
    for c in candidates:
        headers1.append(f"{c['name']}得票數")
        headers1.append(f"{c['name']}得票率")
    style_header(ws1, headers1)

    counties = []
    county_data = {}  # (candidate_idx, county) -> (votes, rate)
    for i, c in enumerate(candidates):
        for row in county_rows[i]:
            counties.append(row["area"])
            county_data[(i, row["area"])] = (row["votes"], row["rate"])
    counties = list(dict.fromkeys(counties))

    for r, co in enumerate(counties, 2):
        ws1.cell(row=r, column=1, value=co).border = border
        for i, c in enumerate(candidates):
            votes, rate = county_data.get((i, co), ("", ""))
            ws1.cell(row=r, column=cand_col(1, i), value=votes).border = border
            ws1.cell(row=r, column=cand_col(1, i) + 1, value=rate).border = border
    ws1.column_dimensions["A"].width = 16

    # ---------- Sheet 2：鄉鎮市區級別 ----------
    ws2 = new_sheet("鄉鎮市區級別")
    headers2 = ["縣市", "鄉鎮市區"]
    for c in candidates:
        headers2.append(f"{c['name']}得票數")
        headers2.append(f"{c['name']}得票率")
    style_header(ws2, headers2)

    townships = []
    town_data = {}  # (candidate_idx, county, township) -> (votes, rate)
    for i, c in enumerate(candidates):
        for row in town_rows[i]:
            townships.append((row["county"], row["township"]))
            town_data[(i, row["county"], row["township"])] = (row["votes"], row["rate"])
    townships = list(dict.fromkeys(townships))

    for r, (co, tw) in enumerate(townships, 2):
        ws2.cell(row=r, column=1, value=co).border = border
        ws2.cell(row=r, column=2, value=tw).border = border
        for i, c in enumerate(candidates):
            votes, rate = town_data.get((i, co, tw), ("", ""))
            ws2.cell(row=r, column=cand_col(2, i), value=votes).border = border
            ws2.cell(row=r, column=cand_col(2, i) + 1, value=rate).border = border
    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 14

    wb.save(path)
    print(f"\n完成！已儲存至 '{path}'")
    print(f"  縣市級別：{len(counties)} 縣市 × {len(candidates)} 候選人")
    print(f"  鄉鎮市區級別：{len(townships)} 鄉鎮市區 × {len(candidates)} 候選人")


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="爬取總統(副總統)選舉 縣市+鄉鎮市區 交叉表")
    parser.add_argument("start_url", nargs="?", default=START_URL, help="vote3.asp 入口網址")
    parser.add_argument("-o", "--output", default=None, help="輸出 xlsx 檔名")
    args = parser.parse_args(argv)

    outdir = os.path.dirname(os.path.abspath(__file__))
    if args.output is None:
        base = "1996" if "I9AA" in args.start_url else "20XX"
        OUTPUT = os.path.join(outdir, f"{base}總統副總統選舉_縣市鄉鎮.xlsx")
    else:
        OUTPUT = args.output if os.path.isabs(args.output) else os.path.join(outdir, args.output)

    print("抓取入口頁 vote3.asp ...")
    html = fetch_page(args.start_url)
    if not html:
        print("入口頁抓取失敗，結束。")
        return 1

    candidates = parse_national(html)
    # 去重：每組候選人（正+副）只取總統作為代表，避免重複抓取
    seen = set()
    uniq = []
    for c in candidates:
        if c["number"] not in seen:
            seen.add(c["number"])
            uniq.append(c)
    candidates = uniq
    print(f"候選人：{len(candidates)} 組")
    for c in candidates:
        print(f"  {c['number']} 號 {c['name']}（{c['party']}）")

    county_rows = {}  # candidate_idx -> [ {area, votes, rate}, ... ]
    town_rows = {}    # candidate_idx -> [ {county, township, votes, rate}, ... ]

    for i, c in enumerate(candidates):
        print(f"\n[{i+1}/{len(candidates)}] 縣市層：{c['name']}（{c['number']}）")
        c_html = fetch_page(c["detail_url"])
        if not c_html:
            continue
        counties = list(rows_of(c_html))
        county_rows[i] = counties
        time.sleep(DELAY)

        towns = []
        nth = 0
        total = sum(1 for co in counties if co["detail_url"])
        for co in counties:
            if not co["detail_url"]:
                continue
            nth += 1
            print(f"    [{nth}/{total}] 鄉鎮層：{co['area']}")
            t_html = fetch_page(co["detail_url"])
            if not t_html:
                continue
            for tw in rows_of(t_html):
                township = tw["area"][len(co["area"]):]  # 去掉縣市前綴
                towns.append(
                    {"county": co["area"], "township": township, "votes": tw["votes"], "rate": tw["rate"]}
                )
            time.sleep(DELAY)
        town_rows[i] = towns

    write_xlsx(candidates, county_rows, town_rows, OUTPUT)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())