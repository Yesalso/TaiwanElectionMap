#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
111 年縣市長選舉（2022 九合一，非直轄市 16 縣市）— 縣市 / 鄉鎮市區 / 村里 三層級爬蟲（每縣市一檔）
==============================================================================
入口：vote3.asp 全國縣市概況（縣市 × 候選人，10 欄，含性別/出生年/政黨/當選）
下鑽：vote31.asp 鄉鎮市區層（縣市 × 候選人，5 欄）→ vote32.asp 村里層（5 欄）

與直轄市版（scrape_mayor_2022.py）差異：
  * 僅入口網址不同（vote3.asp，涵蓋 13 縣 + 3 市，共 16 縣市）；
  * 輸出檔名前綴改為「2022縣市長選舉」；
  * 其餘抓取、解析、輸出邏輯完全相同。
  * 與直轄市 6 都合併後即為 2022 九合一全部 22 縣市長選舉。

特色：
  * 頁面磁碟快取（快取目錄可指定），中斷後重跑可沿用已抓頁面。
  * 村里層以執行緒池並行抓取，加快大量頁面。

輸出（每個縣市一個檔）：
  「2022縣市長選舉_{縣市}.xlsx」，含三個工作表：
    - 「縣市級別」    ：縣市 | 候選人1得票數 | 候選人1得票率 | ... | 當選人
    - 「鄉鎮市區級別」：縣市 | 鄉鎮市區 | 候選人1得票數 | ...
    - 「村里層級明細」：縣市 | 鄉鎮市區 | 村里 | 候選人1得票數 | ...

用法：
    python scrape_county_2022.py [vote3網址] [--workers 5] [--delay 0.25]
"""

import argparse
import hashlib
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

START_URL = "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=N:8::I8888888888iii"
BASE_URL = "https://vote.nccu.edu.tw/cec/"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PREFIX = "2022縣市長選舉"
DEFAULT_CACHE = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "county2022_cache")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
DELAY = 0.25
RETRY = 3
WORKERS = 5
_progress_lock = threading.Lock()


# ---------------------------------------------------------------- 抓取 + 快取


def _cache_key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def cache_fetch(url, cache_dir, delay=DELAY, retry=RETRY):
    """優先讀取磁碟快取；否則抓取並寫入快取。回傳解碼後之文字。"""
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, _cache_key(url) + ".html")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    text = fetch_page(url, delay=delay, retry=retry)
    if text and cache_dir:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return text


def fetch_page(url, delay=DELAY, retry=RETRY):
    """抓取網頁並以 big5 解碼，自動重試；失敗回傳 None。"""
    for attempt in range(1, retry + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            r.encoding = "big5"
            return r.text
        except Exception as e:
            print(f"  請求失敗（{attempt}/{retry}）：{url} -> {e}")
            if attempt < retry:
                time.sleep(delay * 2)
    return None


def join_url(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    return BASE_URL + href


# ---------------------------------------------------------------- 解析


def parse_entry(html):
    """vote3.asp：縣市 × 候選人（10 欄）。回傳 [ {county, town_url, cands:[...]}, ... ]。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    counties = OrderedDict()
    if not table:
        return list(counties.values())
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 10:
            continue
        if not vals[0] or not vals[2].isdigit():
            continue
        county = vals[0]
        rec = counties.setdefault(
            county,
            {"county": county, "town_url": None, "cands": []},
        )
        a = cells[0].find("a")
        if a and not rec["town_url"]:
            rec["town_url"] = join_url(a.get("href"))
        rec["cands"].append(
            {
                "name": vals[1],
                "number": vals[2],
                "party": vals[5],
                "votes": vals[6],
                "rate": vals[7],
                "elected": vals[8] if len(vals) > 8 else "",
            }
        )
    # 候選人按號次排序
    for rec in counties.values():
        rec["cands"].sort(key=lambda c: int(c["number"]))
    return list(counties.values())


def parse_town(html, county):
    """vote31.asp：鄉鎮市區 × 候選人（5 欄）。回傳 [(township, number, votes, rate, detail_url), ...]。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows = []
    if not table:
        return rows
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 5:
            continue
        if not vals[0] or not vals[3].isdigit():
            continue
        a = cells[1].find("a")  # 姓名列下鑽到村里
        rows.append(
            {
                "township": vals[0][len(county):],
                "number": vals[2],
                "votes": vals[3],
                "rate": vals[4],
                "detail_url": join_url(a.get("href")) if a else None,
            }
        )
    return rows


def parse_village(html, prefix):
    """vote32.asp：村里 × 候選人（5 欄）。回傳 [(village, number, votes, rate), ...]。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows = []
    if not table:
        return rows
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 5:
            continue
        if not vals[0] or not vals[3].isdigit():
            continue
        rows.append(
            {
                "village": vals[0][len(prefix):],
                "number": vals[2],
                "votes": vals[3],
                "rate": vals[4],
            }
        )
    return rows


# ---------------------------------------------------------------- 主流程


def parallel(items, worker, cache_dir, label, workers, delay):
    """並行抓取+解析；items 為 (id, url, ctx)；回傳 {id: worker(...)}。"""
    results = {}
    done = [0]
    total = len(items)

    def run(it):
        idx, url, ctx = it
        html = cache_fetch(url, cache_dir, delay=delay)
        return idx, worker(html, ctx)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run, it): it for it in items}
        for fut in as_completed(futs):
            idx, result = fut.result()
            results[idx] = result
            with _progress_lock:
                done[0] += 1
                if done[0] % 20 == 0 or done[0] == total:
                    print(f"      {label}: {done[0]}/{total}")
    return results


def work_village_job(html, ctx):
    """vote32 村里層。ctx=(county, township)"""
    county, township = ctx
    prefix = county + township
    return parse_village(html, prefix)


def scrape(start_url, out_dir, cache_dir, delay, retry, workers):
    print("抓取入口頁 vote3.asp ...")
    html = cache_fetch(start_url, cache_dir, delay=delay, retry=retry)
    if not html:
        print("入口頁抓取失敗，結束。")
        return 1

    counties = parse_entry(html)
    print(f"縣市：{len(counties)} 個")
    for rec in counties:
        cands = rec["cands"]
        elected = next((c["name"] for c in cands if c["elected"] == "Y"), "")
        print(f"  {rec['county']}：{len(cands)} 候選人，當選 {elected}")

    # ---- 鄉鎮層（每縣市一頁，依序） ----
    town_rows = {}      # county_idx -> [township rows]
    vill_jobs = []      # (id, url, ctx)
    vill_map = {}       # id -> (county_idx, township)
    jid = 0
    for ci, rec in enumerate(counties):
        if not rec["town_url"]:
            continue
        t_html = cache_fetch(rec["town_url"], cache_dir, delay=delay, retry=retry)
        towns = parse_town(t_html, rec["county"]) if t_html else []
        town_rows[ci] = towns
        print(f"  [{ci + 1}/{len(counties)}] 鄉鎮層：{rec['county']} 共 {len(towns)} 筆（鄉鎮×候選人）")
        # 每個「鄉鎮 × 候選人」都有一頁村里（vote32）
        for t in towns:
            if t["detail_url"]:
                vill_map[jid] = (ci, t["township"])
                vill_jobs.append((jid, t["detail_url"], (rec["county"], t["township"])))
                jid += 1
        time.sleep(delay)

    # ---- 村里層（並行） ----
    print(f"村里層 vote32：共 {len(vill_jobs)} 頁 ...")
    vill_res = parallel(vill_jobs, work_village_job, cache_dir, "村里層", workers, delay)
    vill_rows = {ci: [] for ci in range(len(counties))}
    for k in sorted(vill_res):
        ci, township = vill_map[k]
        for v in vill_res[k]:
            vill_rows[ci].append(
                {"township": township, "village": v["village"],
                 "number": v["number"], "votes": v["votes"], "rate": v["rate"]}
            )

    # ---- 每個縣市輸出一個 xlsx ----
    for ci, rec in enumerate(counties):
        path = os.path.join(out_dir, f"{OUT_PREFIX}_{rec['county']}.xlsx")
        write_county_xlsx(rec, town_rows.get(ci, []), vill_rows.get(ci, []), path)
    return 0


# ---------------------------------------------------------------- 輸出


def _styles():
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    return header_font, header_fill, border


def write_county_xlsx(county_rec, towns, vills, path):
    cands = county_rec["cands"]
    county = county_rec["county"]
    header_font, header_fill, border = _styles()

    wb = Workbook()
    wb.remove(wb.active)

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

    def cand_headers(prefix):
        headers = list(prefix)
        for c in cands:
            label = f"{c['name']}（{c['number']}）"
            headers.append(f"{label}_得票數")
            headers.append(f"{label}_得票率")
        return headers

    def cand_col(pos, idx):
        return pos + 1 + idx * 2

    # ---------- Sheet 1：縣市級別（單一縣市，1 列） ----------
    ws1 = new_sheet("縣市級別")
    elected = next((c["name"] for c in cands if c["elected"] == "Y"), "")
    headers1 = cand_headers(["縣市"]) + ["當選人"]
    style_header(ws1, headers1)
    ws1.cell(row=2, column=1, value=county).border = border
    for i, c in enumerate(cands):
        ws1.cell(row=2, column=cand_col(1, i), value=c["votes"]).border = border
        ws1.cell(row=2, column=cand_col(1, i) + 1, value=c["rate"]).border = border
    ws1.cell(row=2, column=len(headers1), value=elected).border = border
    ws1.column_dimensions["A"].width = 14

    # ---------- Sheet 2：鄉鎮市區級別 ----------
    ws2 = new_sheet("鄉鎮市區級別")
    style_header(ws2, cand_headers(["縣市", "鄉鎮市區"]))
    town_order = list(OrderedDict.fromkeys(t["township"] for t in towns))
    town_lookup = {}
    for t in towns:
        town_lookup[(t["number"], t["township"])] = (t["votes"], t["rate"])
    for r, tw in enumerate(town_order, 2):
        ws2.cell(row=r, column=1, value=county).border = border
        ws2.cell(row=r, column=2, value=tw).border = border
        for i, c in enumerate(cands):
            votes, rate = town_lookup.get((c["number"], tw), ("", ""))
            ws2.cell(row=r, column=cand_col(2, i), value=votes).border = border
            ws2.cell(row=r, column=cand_col(2, i) + 1, value=rate).border = border
    ws2.column_dimensions["A"].width = 12
    ws2.column_dimensions["B"].width = 12

    # ---------- Sheet 3：村里層級明細 ----------
    ws3 = new_sheet("村里層級明細")
    style_header(ws3, cand_headers(["縣市", "鄉鎮市區", "村里"]))
    vill_order = list(OrderedDict.fromkeys((v["township"], v["village"]) for v in vills))
    vill_lookup = {}
    for v in vills:
        vill_lookup[(v["number"], v["township"], v["village"])] = (v["votes"], v["rate"])
    for r, (tw, vl) in enumerate(vill_order, 2):
        ws3.cell(row=r, column=1, value=county).border = border
        ws3.cell(row=r, column=2, value=tw).border = border
        ws3.cell(row=r, column=3, value=vl).border = border
        for i, c in enumerate(cands):
            votes, rate = vill_lookup.get((c["number"], tw, vl), ("", ""))
            ws3.cell(row=r, column=cand_col(3, i), value=votes).border = border
            ws3.cell(row=r, column=cand_col(3, i) + 1, value=rate).border = border
    ws3.column_dimensions["A"].width = 12
    ws3.column_dimensions["B"].width = 12
    ws3.column_dimensions["C"].width = 10

    wb.save(path)
    print(f"\n完成！已儲存至 '{path}'")
    print(f"  縣市級別：1 列 × {len(cands)} 候選人（當選 {elected}）")
    print(f"  鄉鎮市區級別：{len(town_order)} 鄉鎮 × {len(cands)} 候選人")
    print(f"  村里層級明細：{len(vill_order)} 村里 × {len(cands)} 候選人")


# ---------------------------------------------------------------- CLI


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="爬取 111 年縣市長選舉（2022）三層級，每縣市一檔")
    parser.add_argument("start_url", nargs="?", default=START_URL, help="vote3.asp 入口網址")
    parser.add_argument("--out", default=OUT_DIR, help="輸出路徑（目錄）")
    parser.add_argument("--delay", type=float, default=DELAY)
    parser.add_argument("--retry", type=int, default=RETRY)
    parser.add_argument("--workers", type=int, default=WORKERS, help="村里層並行數")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="頁面磁碟快取目錄")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(OUT_DIR, args.out)
    os.makedirs(out_dir, exist_ok=True)
    return scrape(args.start_url, out_dir, args.cache, args.delay, args.retry, args.workers)


if __name__ == "__main__":
    sys.exit(main())
