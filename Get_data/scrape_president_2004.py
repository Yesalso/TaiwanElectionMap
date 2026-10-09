#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 11 任總統副總統選舉（2004）— 縣市 + 鄉鎮市區 + 村里 三層級爬蟲（交叉表輸出）
==================================================================================
入口：vote3.asp 全國概況（10 欄總統列 + 4 欄副總統列，正副同號次取總統列代表）
下鑽：vote312.asp 縣市級別 → vote313.asp 鄉鎮市區級別 → vote32.asp 村里級別
      （加 --stations 時續抓 vote33.asp 投票所明細）

特色：
  * 頁面磁碟快取（快取目錄可指定），中斷後重跑只補抓缺頁。
  * 鄉鎮、村里、投票所層級以執行緒池並行抓取，加快大量頁面。
  * 網站為 big5 編碼，抓取後強制以 big5 解碼（否則中文全亂碼）。

輸出兩個 xlsx，每個候選人佔兩欄（得票數、得票率）：
  1. 「2004總統副總統選舉_縣市鄉鎮村里.xlsx」：
     - 「縣市級別」    ：縣市 | 候選人1得票數 | 候選人1得票率 | ...
     - 「鄉鎮市區級別」：縣市 | 鄉鎮市區 | 候選人1得票數 | ...
     - 「村里層級明細」：縣市 | 鄉鎮市區 | 村里 | 候選人1得票數 | ...
     - 「投票所明細」（--stations）：縣市 | 鄉鎮市區 | 村里 | 投票所 | ...
  2. 「2004總統副總統選舉_得票率.xlsx」：得票率專用格式
     - 「各里彙總」：選舉區別(縣市) | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率 ...

用法：
    python scrape_president_2004.py [vote3網址] [--stations] [--workers 5] [--delay 0.25]
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

START_URL = "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=I:88%3CI8888888888iii(("
BASE_URL = "https://vote.nccu.edu.tw/cec/"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Precident", "2004Precident", "data")
DEFAULT_RAW = os.path.join(OUT_DIR, "2004總統副總統選舉_縣市鄉鎮村里.xlsx")
DEFAULT_RATE = os.path.join(OUT_DIR, "2004總統副總統選舉_得票率.xlsx")
DEFAULT_CANDS = ["陳水扁", "連戰"]
DEFAULT_CACHE = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "pres2004_cache")

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
def rows_of(html):
    """解析 5 欄表格（地區/姓名/號次/得票數/得票率），姓名欄含下鑽連結。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 5:
            continue
        if not vals[0] or not vals[3].isdigit():
            continue
        a = cells[1].find("a")
        yield {
            "area": vals[0],
            "name": vals[1],
            "number": vals[2],
            "votes": vals[3],
            "rate": vals[4],
            "detail_url": join_url(a.get("href")) if a else None,
        }


def parse_national(html):
    """vote3.asp：候選人清單。

    2004 版面為 rowspan 表格：總統列 10 欄（含政黨/得票數/得票率），
    緊接的副總統列只有 4 欄（姓名/號次/性別/出生年次），故只取 8 欄以上
    且姓名欄有連結的總統列，即代表整組候選人。
    """
    candidates = []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return candidates
    seen = set()
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        vals = [c.get_text(strip=True) for c in cells]
        if len(vals) < 8:
            continue
        a = cells[1].find("a")
        if not a:
            continue
        number = vals[2]
        if number in seen:
            continue
        seen.add(number)
        candidates.append(
            {
                "region": vals[0],
                "name": a.get_text(strip=True),
                "number": number,
                "party": vals[5],
                "votes": vals[6],
                "rate": vals[7],
                "detail_url": join_url(a.get("href")),
            }
        )
    return candidates


# ---------------------------------------------------------------- 主流程
def parallel(items, worker, cache_dir, label, total, workers, delay):
    """並行抓取+解析；items 為 (id, url, *ctx)；回傳 {id: worker(...)}。"""
    results = {}
    done = [0]

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


def work_town(html, ctx):
    """vote313：縣市內各鄉鎮。ctx=(county)"""
    county = ctx
    towns = []
    for tw in rows_of(html):
        towns.append(
            {"county": county, "township": tw["area"][len(county):],
             "votes": tw["votes"], "rate": tw["rate"], "detail_url": tw["detail_url"]}
        )
    return towns


def work_village(html, ctx):
    """vote32：鄉鎮內各村里。ctx=(county, township)"""
    county, township = ctx
    prefix = county + township
    vills = []
    for vl in rows_of(html):
        vills.append(
            {"county": county, "township": township,
             "village": vl["area"][len(prefix):],
             "votes": vl["votes"], "rate": vl["rate"],
             "detail_url": vl["detail_url"]}
        )
    return vills


def work_station(html, ctx):
    """vote33：村里內各投票所（葉子節點，無下鑽連結）。ctx=(county, township, village)"""
    county, township, village = ctx
    prefix = county + township + village
    out = []
    for st in rows_of(html):
        area = st["area"]
        name = area[len(prefix):] if area.startswith(prefix) else area
        out.append({"county": county, "township": township, "village": village,
                    "station": name, "votes": st["votes"], "rate": st["rate"]})
    return out


def scrape(start_url, raw_path, rate_path, cands, delay, retry, workers,
           cache_dir, stations=False):
    print("抓取入口頁 vote3.asp ...")
    html = cache_fetch(start_url, cache_dir, delay=delay, retry=retry)
    if not html:
        print("入口頁抓取失敗，結束。")
        return 1

    candidates = parse_national(html)
    print(f"候選人（正副總統併組）：{len(candidates)} 組")
    for c in candidates:
        print(f"  {c['number']} 號 {c['name']}（{c['party']}）{c['votes']} 票 {c['rate']}")

    county_rows = {}
    town_jobs = []
    town_map = {}
    jid = 0
    for i, c in enumerate(candidates):
        c_html = cache_fetch(c["detail_url"], cache_dir, delay=delay, retry=retry)
        if not c_html:
            continue
        counties = list(rows_of(c_html))
        county_rows[i] = [{"county": co["area"], "votes": co["votes"], "rate": co["rate"]} for co in counties]
        print(f"  [{i+1}/{len(candidates)}] 縣市層：{c['name']} 共 {len(counties)} 縣市")
        for co in counties:
            if not co["detail_url"]:
                continue
            town_map[jid] = (i, co["area"])
            town_jobs.append((jid, co["detail_url"], co["area"]))
            jid += 1
        time.sleep(delay)

    print(f"鄉鎮層投票313：共 {len(town_jobs)} 頁 ...")
    town_res = parallel(town_jobs, work_town, cache_dir, "鄉鎮層", len(town_jobs), workers, delay)
    town_rows = {i: [] for i in range(len(candidates))}
    vill_jobs = []
    vill_map = {}
    jid = 0
    for k in sorted(town_res):
        i, county = town_map[k]
        for t in town_res[k]:
            town_rows[i].append({"county": t["county"], "township": t["township"],
                                 "votes": t["votes"], "rate": t["rate"]})
            if t["detail_url"]:
                vill_map[jid] = (i, t["county"], t["township"])
                vill_jobs.append((jid, t["detail_url"], (t["county"], t["township"])))
                jid += 1

    print(f"村里層投票32：共 {len(vill_jobs)} 頁 ...")
    vill_res = parallel(vill_jobs, work_village, cache_dir, "村里層", len(vill_jobs), workers, delay)
    vill_rows = {i: [] for i in range(len(candidates))}
    station_jobs = []
    station_map = {}
    jid = 0
    for k in sorted(vill_res):
        i, county, township = vill_map[k]
        for v in vill_res[k]:
            vill_rows[i].append({"county": v["county"], "township": v["township"],
                                 "village": v["village"], "votes": v["votes"], "rate": v["rate"]})
            if stations and v.get("detail_url"):
                station_map[jid] = (i, v["county"], v["township"], v["village"])
                station_jobs.append((jid, v["detail_url"],
                                     (v["county"], v["township"], v["village"])))
                jid += 1

    if not any(vill_rows.values()):
        print("未解析到任何村里資料，請確認網址。")
        return 1

    station_rows = {i: [] for i in range(len(candidates))}
    if stations:
        print(f"投票所層投票33：共 {len(station_jobs)} 頁 ...")
        st_res = parallel(station_jobs, work_station, cache_dir, "投票所層",
                          len(station_jobs), workers, delay)
        for k in sorted(st_res):
            i, county, township, village = station_map[k]
            for s in st_res[k]:
                station_rows[i].append(s)

    write_raw_xlsx(candidates, county_rows, town_rows, vill_rows, station_rows, raw_path)
    write_rate_xlsx(candidates, vill_rows, rate_path, cands)
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


def write_raw_xlsx(candidates, county_rows, town_rows, vill_rows, station_rows, path):
    wb = Workbook()
    wb.remove(wb.active)
    header_font, header_fill, border = _styles()

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
        for c in candidates:
            label = f"{c['name']}（{c['number']}）"
            headers.append(f"{label}_得票數")
            headers.append(f"{label}_得票率")
        return headers

    def cand_col(pos, idx):
        return pos + 1 + idx * 2

    def first_rows(rows_by_cand):
        """取第一組「有資料」的候選人列，避免 index 0 抓取失敗時整檔報錯。"""
        for i in sorted(rows_by_cand):
            if rows_by_cand[i]:
                return rows_by_cand[i]
        return []

    def fill(ws, keys, pos, rows_by_cand, key_of):
        data = {}
        for i in range(len(candidates)):
            for r in rows_by_cand.get(i, []):
                data[(i,) + key_of(r)] = (r["votes"], r["rate"])
        for row_no, key in enumerate(keys, 2):
            for c, v in enumerate(key, 1):
                ws.cell(row=row_no, column=c, value=v).border = border
            for i in range(len(candidates)):
                votes, rate = data.get((i,) + key, ("", ""))
                ws.cell(row=row_no, column=cand_col(pos, i), value=votes).border = border
                ws.cell(row=row_no, column=cand_col(pos, i) + 1, value=rate).border = border

    ws1 = new_sheet("縣市級別")
    style_header(ws1, cand_headers(["縣市"]))
    counties = list(OrderedDict.fromkeys(r["county"] for r in first_rows(county_rows)))
    fill(ws1, [(c,) for c in counties], 1, county_rows, lambda r: (r["county"],))
    ws1.column_dimensions["A"].width = 14

    ws2 = new_sheet("鄉鎮市區級別")
    style_header(ws2, cand_headers(["縣市", "鄉鎮市區"]))
    towns = list(OrderedDict.fromkeys((r["county"], r["township"]) for r in first_rows(town_rows)))
    fill(ws2, towns, 2, town_rows, lambda r: (r["county"], r["township"]))
    ws2.column_dimensions["A"].width = 12
    ws2.column_dimensions["B"].width = 12

    ws3 = new_sheet("村里層級明細")
    style_header(ws3, cand_headers(["縣市", "鄉鎮市區", "村里"]))
    villages = list(OrderedDict.fromkeys(
        (r["county"], r["township"], r["village"]) for r in first_rows(vill_rows)))
    fill(ws3, villages, 3, vill_rows, lambda r: (r["county"], r["township"], r["village"]))
    ws3.column_dimensions["A"].width = 12
    ws3.column_dimensions["B"].width = 12
    ws3.column_dimensions["C"].width = 10

    stats = [(len(counties), len(towns), len(villages))]

    if any(station_rows.values()):
        ws4 = new_sheet("投票所明細")
        style_header(ws4, cand_headers(["縣市", "鄉鎮市區", "村里", "投票所"]))
        sts = list(OrderedDict.fromkeys(
            (r["county"], r["township"], r["village"], r["station"])
            for r in first_rows(station_rows)))
        fill(ws4, sts, 4, station_rows,
             lambda r: (r["county"], r["township"], r["village"], r["station"]))
        ws4.column_dimensions["A"].width = 12
        ws4.column_dimensions["B"].width = 12
        ws4.column_dimensions["C"].width = 10
        ws4.column_dimensions["D"].width = 14
        stats.append((len(sts),))

    wb.save(path)
    print(f"\n完成！已儲存至 '{path}'")
    print(f"  縣市級別：{stats[0][0]} 縣市 × {len(candidates)} 候選人")
    print(f"  鄉鎮市區級別：{stats[0][1]} 鄉鎮 × {len(candidates)} 候選人")
    print(f"  村里層級明細：{stats[0][2]} 村里 × {len(candidates)} 候選人")
    if len(stats) > 1:
        print(f"  投票所明細：{stats[1][0]} 投票所 × {len(candidates)} 候選人")


def parse_rate(v):
    """'4.02542372881356%' → 4.03；NaN / 空值 → None。"""
    if v is None:
        return None
    s = re.sub(r"%", "", str(v).strip()).replace("nan", "").replace("NaN", "")
    if not s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def write_rate_xlsx(candidates, vill_rows, path, cand_names):
    """輸出「各里彙總」得票率專用檔：選舉區別(縣市) | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率。"""
    idx_of = {c["name"]: i for i, c in enumerate(candidates)}
    if all(n in idx_of for n in cand_names):
        order = [idx_of[n] for n in cand_names]
        names = list(cand_names)
    else:
        order = list(range(len(candidates)))
        names = [candidates[i]["name"] for i in order]
        print(f"  注意：{cand_names} 與網站候選人不符，改用網站順序 {names}")

    rate_lookup = {}
    for i in order:
        for r in vill_rows.get(i, []):
            rate_lookup[(i, r["county"], r["township"], r["village"])] = r["rate"]

    first_vill_rows = []
    for i in sorted(vill_rows):
        if vill_rows[i]:
            first_vill_rows = vill_rows[i]
            break
    base_keys = list(OrderedDict.fromkeys(
        (r["county"], r["township"], r["village"]) for r in first_vill_rows))
    base_keys.sort()
    rows = []
    for co, tw, vl in base_keys:
        rec = [co, tw, vl]
        for i in order:
            rec.append(parse_rate(rate_lookup.get((i, co, tw, vl))))
        rows.append(rec)

    wb = Workbook()
    wb.remove(wb.active)
    header_font, header_fill, border = _styles()
    ws = wb.create_sheet("各里彙總")
    headers = ["選舉區別", "鄉(鎮、市、區)別", "村里別"] + [f"{n}得票率" for n in names]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    for r, rec in enumerate(rows, 2):
        for c, v in enumerate(rec, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
    for col, w in zip("ABC", (12, 12, 10)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    print(f"完成！已儲存至 '{path}'  候選人={names}  村里數={len(rows)}")


# ---------------------------------------------------------------- CLI
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="爬取 93 年總統(副總統)選舉三層級交叉表與得票率專用檔")
    parser.add_argument("start_url", nargs="?", default=START_URL, help="vote3.asp 入口網址")
    parser.add_argument("--raw", default=DEFAULT_RAW, help="原始交叉表 xlsx 輸出路徑")
    parser.add_argument("--rate", default=DEFAULT_RATE, help="得票率專用 xlsx 輸出路徑")
    parser.add_argument("--cands", nargs="*", default=DEFAULT_CANDS, help="得票率檔要列出的候選人")
    parser.add_argument("--delay", type=float, default=DELAY)
    parser.add_argument("--retry", type=int, default=RETRY)
    parser.add_argument("--workers", type=int, default=WORKERS, help="鄉鎮/村里/投票所層並行數")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="頁面磁碟快取目錄")
    parser.add_argument("--stations", action="store_true", help="續抓 vote33.asp 投票所明細（頁數多，約 1.6 萬頁）")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    raw_path = args.raw if os.path.isabs(args.raw) else os.path.join(OUT_DIR, args.raw)
    rate_path = args.rate if os.path.isabs(args.rate) else os.path.join(OUT_DIR, args.rate)
    os.makedirs(OUT_DIR, exist_ok=True)
    for p in (raw_path, rate_path):
        if os.path.exists(p):
            try:
                os.remove(p)
            except PermissionError:
                print(f"原檔被佔用，將另存新的。")
    return scrape(args.start_url, raw_path, rate_path, args.cands,
                  args.delay, args.retry, args.workers, args.cache,
                  stations=args.stations)


if __name__ == "__main__":
    sys.exit(main())
