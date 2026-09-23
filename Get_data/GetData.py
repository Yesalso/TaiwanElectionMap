#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中央選舉委員會投票資料爬蟲（可複用版，支援多層結構）
=====================================================
入口層級依網址自動判斷（vote3 / vote312 / vote313 / vote31 / vote32）：
  * vote3   全國候選人列表 → vote312 縣市 → vote313 鄉鎮市區
            （2008 第12任總統選舉；預設停在鄉鎮市區，加 --village 才下鑽村里）
  * vote312 縣市列表（單一候選人）→ vote313 鄉鎮市區
  * vote313 鄉鎮市區列表（單一候選人；建議搭配 --region 指定縣市以拆出鄉鎮名）
  * vote31  鄉鎮市區列表（單一候選人，舊版入口；固定下鑽 vote32 村里）
  * vote32  村里明細（單一候選人）

輸出一個 xlsx 交叉表（每候選人兩欄：得票數、得票率），工作表依抓到的層級而定：
  - 「縣市級別」    ：縣市 | 候選人1得票數 | 候選人1得票率 | ...
  - 「鄉鎮市區級別」：縣市 | 鄉鎮市區 | 候選人1得票數 | 候選人1得票率 | ...
  - 「村里層級明細」：縣市 | 鄉鎮市區 | 村里 | 候選人1得票數 | ...
各表末列為總計（票數加總；得票率為占全體候選人合計之比率）。

用法：
    python GetData.py <網址> [-o 輸出檔名] [--region 縣市名] [--village] [--delay 秒] [--retry 次]

範例：
    # 2008 第12任總統(副總統)選舉（縣市 + 鄉鎮市區）
    python GetData.py "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=I:88@I8888888888iii((" \\
        -o 2008總統副總統選舉_縣市鄉鎮.xlsx

    # 含村里層
    python GetData.py "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=I:88@I8888888888iii((" \\
        --village -o 2008總統副總統選舉_縣市鄉鎮村里.xlsx

    # 1997 臺北縣縣長選舉（舊版 vote31 連鎖，固定抓到村里）
    python GetData.py "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=N9AA?I8888888888iii((" \\
        --region 台北縣 -o 1997台北縣長.xlsx

    # 直接給縣市層 / 鄉鎮市區層網址
    python GetData.py "https://vote.nccu.edu.tw/cec/vote312.asp?pass1=XXXX"
    python GetData.py "https://vote.nccu.edu.tw/cec/vote313.asp?pass1=XXXX" --region 臺北縣
"""

import argparse
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

DEFAULT_START_URL = "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=N9AA?I8888888888iii(("
DEFAULT_BASE_URL = "https://vote.nccu.edu.tw/cec/"
DEFAULT_OUTPUT = "选举得票数据.xlsx"
DEFAULT_DELAY = 0.5
DEFAULT_RETRY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------- 抓取


def fetch_page(url, encoding="big5", retry=3, delay=0.5):
    """抓取網頁並以指定編碼解碼，自動重試；失敗回傳 None。"""
    for attempt in range(1, retry + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = encoding
            return resp.text
        except Exception as e:
            print(f"  請求失敗（第 {attempt}/{retry} 次）：{url} -> {e}")
            if attempt < retry:
                time.sleep(delay * 2)
    return None


def _join_url(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return DEFAULT_BASE_URL.rstrip("/") + href
    return DEFAULT_BASE_URL + href


def detect_page(url):
    """由網址辨識頁面層級：'3' / '312' / '313' / '31' / '32'。"""
    m = re.search(r"vote(\d+)\.asp", url or "", re.I)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- 解析


def parse_national(html):
    """解析全國入口 vote3.asp，回傳候選人清單（正副總統同號次只取總統列）。
    欄位（10 欄）：地區/姓名/號次/性別/出生年次/推薦政黨/得票數/得票率/當選否/是否現任
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen = set()
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue
        a_tag = tds[1].find("a")
        if not a_tag:
            continue
        number = tds[2].get_text(strip=True)
        if number in seen:
            continue
        seen.add(number)
        candidates.append(
            {
                "region": tds[0].get_text(strip=True),
                "name": a_tag.get_text(strip=True),
                "number": number,
                "party": tds[5].get_text(strip=True),
                "votes": tds[6].get_text(strip=True),
                "rate": tds[7].get_text(strip=True),
                "detail_url": _join_url(a_tag.get("href")),
            }
        )
    return candidates


def parse_level(html):
    """解析 5 欄頁（vote312 / vote313 / vote31 / vote32）。
    欄位：地區/姓名/號次/得票數/得票率；地區為「上層地區+本層地區」相連字串，
    姓名欄含 <a> 則可繼續下鑽。
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows = []
    if not table:
        return rows
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        vals = [td.get_text(strip=True) for td in tds]
        if len(vals) < 5:
            continue
        votes = vals[3]
        if not vals[0] or not votes.isdigit():
            continue
        a_tag = tds[1].find("a")
        rows.append(
            {
                "area": vals[0],
                "name": vals[1],
                "number": vals[2],
                "votes": votes,
                "rate": vals[4],
                "detail_url": _join_url(a_tag.get("href")) if a_tag else None,
            }
        )
    return rows


def build_candidate_key(name, number, region=""):
    return f"{name}（{number}）"


def _to_int(votes):
    try:
        return int(str(votes).replace(",", ""))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- 主流程


def scrape(start_url, output_file, region_filter, delay, retry, with_village):
    print("開始抓取入口頁...")
    html = fetch_page(start_url, retry=retry, delay=delay)
    if not html:
        print("入口頁抓取失敗，結束。")
        return 1

    page = detect_page(start_url)
    candidate_keys = []
    county_data = OrderedDict()   # (縣市,) -> {候選人: (得票數, 得票率)}
    town_data = OrderedDict()     # (縣市, 鄉鎮市區) -> {候選人: ...}
    vill_data = OrderedDict()     # (縣市, 鄉鎮市區, 村里) -> ...
    official = {}                 # 全國公告總票數（vote3 入口）

    def ensure_ck(ck):
        if ck not in candidate_keys:
            candidate_keys.append(ck)

    def put(data, key, ck, votes, rate):
        ensure_ck(ck)
        if not isinstance(key, tuple):
            key = (key,)
        data.setdefault(key, {})[ck] = (votes, rate)

    def town_prefixes(county, township, area):
        opts = [area, township]
        if county and township:
            opts.append(county + township)
        seen = []
        for p in opts:
            if p and p not in seen:
                seen.append(p)
        return seen

    def grab_villages(town_key, prefixes, ck, detail_url):
        v_html = fetch_page(detail_url, retry=retry, delay=delay)
        if v_html:
            for vl in parse_level(v_html):
                varea = vl["area"]
                village = varea
                for p in sorted(prefixes, key=len, reverse=True):
                    if varea.startswith(p):
                        village = varea[len(p):]
                        break
                put(vill_data, town_key + (village,), ck, vl["votes"], vl["rate"])
        time.sleep(delay)

    def walk_counties(cand_ck, counties, do_village, county_filter=None):
        kept = []
        for co in counties:
            if county_filter and co["area"] != county_filter:
                continue
            put(county_data, (co["area"],), cand_ck, co["votes"], co["rate"])
            kept.append(co)
        total = sum(1 for co in kept if co["detail_url"])
        n = 0
        for co in kept:
            if not co["detail_url"]:
                continue
            n += 1
            print(f"    [{n}/{total}] 鄉鎮層：{co['area']}")
            t_html = fetch_page(co["detail_url"], retry=retry, delay=delay)
            if t_html:
                for tw in parse_level(t_html):
                    area = tw["area"]
                    township = area[len(co["area"]):] if area.startswith(co["area"]) else area
                    key = (co["area"], township)
                    put(town_data, key, cand_ck, tw["votes"], tw["rate"])
                    if do_village and tw["detail_url"]:
                        print(f"        村里層：{township}")
                        grab_villages(key, town_prefixes(co["area"], township, area), cand_ck, tw["detail_url"])
            time.sleep(delay)

    def walk_townships_direct(cand_ck, county, rows, do_village):
        for i, tw in enumerate(rows, 1):
            area = tw["area"]
            township = area
            if county and area.startswith(county):
                township = area[len(county):]
            key = (county, township)
            put(town_data, key, cand_ck, tw["votes"], tw["rate"])
            if do_village and tw["detail_url"]:
                print(f"    村里層 [{i}/{len(rows)}]：{township}")
                grab_villages(key, town_prefixes(county, township, area), cand_ck, tw["detail_url"])
        time.sleep(delay)

    if page == "3":
        cands = parse_national(html)
        child = detect_page(cands[0]["detail_url"]) if cands else ""
        if region_filter and child != "312":
            cands = [c for c in cands if c["region"] == region_filter]
        if not cands:
            print("未解析到候選人，請確認網址或 --region。")
            return 1
        print(f"候選人：{len(cands)} 組（下鑽 vote{child}）")
        for c in cands:
            ck = build_candidate_key(c["name"], c["number"])
            official[ck] = (c["votes"], c["rate"])
            print(f"  {c['number']} 號 {c['name']}（{c['party']}）{c['votes']} 票 {c['rate']}")

        do_village = with_village or child == "31"
        for i, c in enumerate(cands, 1):
            ck = build_candidate_key(c["name"], c["number"])
            ensure_ck(ck)
            lvl = "縣市層" if child == "312" else "鄉鎮層"
            print(f"[{i}/{len(cands)}] 抓取{lvl}：{ck}")
            d1 = fetch_page(c["detail_url"], retry=retry, delay=delay)
            if not d1:
                continue
            if child == "312":
                walk_counties(ck, parse_level(d1), do_village, county_filter=region_filter)
            elif child == "31":
                walk_townships_direct(ck, c["region"], parse_level(d1), do_village)
            else:
                print(f"  未知下鑽頁 vote{child}，略過。")
            time.sleep(delay)
    elif page == "312":
        rows = parse_level(html)
        if not rows:
            print("未解析到縣市資料，請確認網址。")
            return 1
        ck = build_candidate_key(rows[0]["name"], rows[0]["number"])
        ensure_ck(ck)
        print(f"入口為縣市層（vote312）：{ck}")
        walk_counties(ck, rows, with_village, county_filter=region_filter)
    elif page in ("313", "31"):
        rows = parse_level(html)
        if not rows:
            print("未解析到鄉鎮市區資料，請確認網址。")
            return 1
        ck = build_candidate_key(rows[0]["name"], rows[0]["number"])
        ensure_ck(ck)
        county = region_filter or ""
        if page == "313" and not county:
            print("入口為鄉鎮市區層（vote313）：未指定 --region，縣市欄將留空。")
        else:
            print(f"入口為鄉鎮市區層（vote{page}）：{ck}，縣市={county}")
        walk_townships_direct(ck, county, rows, with_village or page == "31")
    elif page == "32":
        rows = parse_level(html)
        if not rows:
            print("未解析到村里資料，請確認網址。")
            return 1
        ck = build_candidate_key(rows[0]["name"], rows[0]["number"])
        ensure_ck(ck)
        print(f"入口為村里層（vote32）：{ck}")
        for vl in rows:
            put(vill_data, (vl["area"],), ck, vl["votes"], vl["rate"])
    else:
        print(f"無法辨識入口頁類型：{start_url}")
        return 1

    if not (county_data or town_data or vill_data):
        print("未解析到任何資料，請確認網址。")
        return 1

    # 無縣市層（舊版 vote31 直入或 vote313 直入）時，由鄉鎮加總推得縣市層
    if town_data and not county_data:
        agg = OrderedDict()
        for (co, _tw), row in town_data.items():
            if not co:
                continue
            acc = agg.setdefault((co,), {})
            for ck, (v, _r) in row.items():
                acc[ck] = acc.get(ck, 0) + _to_int(v)
        for key, acc in agg.items():
            tot = sum(acc.values())
            county_data[key] = {
                ck: (str(v), f"{v / tot * 100:.2f}%" if tot else "")
                for ck, v in acc.items()
            }

    # 總計：以縣市層加總最完整，其次鄉鎮、村里
    source = county_data or town_data or vill_data
    candidate_totals = {ck: 0 for ck in candidate_keys}
    for row in source.values():
        for ck, (votes, _rate) in row.items():
            candidate_totals[ck] += _to_int(votes)

    for ck, (ov, _orate) in official.items():
        sv = candidate_totals.get(ck, 0)
        mark = "一致" if _to_int(ov) == sv else f"不一致（差 {sv - _to_int(ov):+d}）"
        print(f"  票數核對 {ck}：各層加總 {sv} vs 全國公告 {ov} → {mark}")

    sheets = []
    if county_data:
        sheets.append(("縣市級別", ["縣市"], county_data))
    if town_data:
        sheets.append(("鄉鎮市區級別", ["縣市", "鄉鎮市區"], town_data))
    if vill_data:
        if page == "32":
            sheets.append(("村里層級明細", ["地區"], vill_data))
        else:
            sheets.append(("村里層級明細", ["縣市", "鄉鎮市區", "村里"], vill_data))

    write_xlsx(output_file, candidate_keys, sheets, candidate_totals)
    return 0


# ---------------------------------------------------------------- 輸出


def write_xlsx(output_file, candidate_keys, sheets, candidate_totals):
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    wb = Workbook()
    wb.remove(wb.active)
    grand = sum(candidate_totals.values())

    for title, prefixes, data in sheets:
        ws = wb.create_sheet(title)
        headers = list(prefixes)
        for ck in candidate_keys:
            headers.append(f"{ck}_得票數")
            headers.append(f"{ck}_得票率")
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
        ws.freeze_panes = ws.cell(row=2, column=len(prefixes) + 1)

        np = len(prefixes)
        for r, (key, cands) in enumerate(data.items(), start=2):
            for ci, part in enumerate(key, start=1):
                ws.cell(row=r, column=ci, value=part).border = thin_border
            for ki, ck in enumerate(candidate_keys):
                votes, rate = cands.get(ck, ("", ""))
                ws.cell(row=r, column=np + 1 + ki * 2, value=votes).border = thin_border
                ws.cell(row=r, column=np + 2 + ki * 2, value=rate).border = thin_border

        # 總計列
        tr = len(data) + 2
        ws.cell(row=tr, column=1, value="總計").font = Font(bold=True)
        for ki, ck in enumerate(candidate_keys):
            v = candidate_totals.get(ck, 0)
            ws.cell(row=tr, column=np + 1 + ki * 2, value=v).font = Font(bold=True)
            rate = f"{v / grand * 100:.2f}%" if grand else ""
            ws.cell(row=tr, column=np + 2 + ki * 2, value=rate).font = Font(bold=True)

        for ci in range(1, np + 1):
            ws.column_dimensions[get_column_letter(ci)].width = 14
        for ki in range(len(candidate_keys)):
            ws.column_dimensions[get_column_letter(np + 1 + ki * 2)].width = 14
            ws.column_dimensions[get_column_letter(np + 2 + ki * 2)].width = 10

        print(f"  「{title}」：{len(data)} 列 × {len(candidate_keys)} 位候選人")

    wb.save(output_file)
    print(f"\n完成！已儲存至 '{output_file}'")


# ---------------------------------------------------------------- CLI


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="抓取中央選舉委員會選舉資料庫（支援 vote3/312/313/31/32 多層結構），輸出交叉表 Excel。")
    parser.add_argument("start_url", nargs="?", default=DEFAULT_START_URL, help="入口網址（vote3 / vote312 / vote313 / vote31 / vote32）")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help=f"輸出檔名（預設 {DEFAULT_OUTPUT}）")
    parser.add_argument("--region", default=None, help="只取指定縣市（vote3/vote312 過濾縣市；vote313 用於拆出鄉鎮名）")
    parser.add_argument("--village", action="store_true", help="下鑽村里層（vote3/vote312/vote313 入口；vote31 舊入口固定下鑽）")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"每頁間隔秒數（預設 {DEFAULT_DELAY}）")
    parser.add_argument("--retry", type=int, default=DEFAULT_RETRY, help=f"失敗重試次數（預設 {DEFAULT_RETRY}）")
    return parser.parse_args(argv)


def decode_region_arg(value):
    """支援直接傳中文或 unicode 轉義（如 \\u81fa\\u5317\\u7e23）防止命令列編碼問題。"""
    if value and "\\u" in value:
        try:
            return value.encode("utf-8").decode("unicode_escape")
        except Exception:
            return value
    return value


def main(argv=None):
    args = parse_args(argv)
    args.region = decode_region_arg(args.region)
    if os.path.exists(args.output):
        try:
            os.remove(args.output)
        except PermissionError:
            base, ext = os.path.splitext(args.output)
            args.output = f"{base}_新{ext}"
            print(f"原檔被佔用，改存為 '{args.output}'")
    return scrape(args.start_url, args.output, args.region, args.delay, args.retry, args.village)


if __name__ == "__main__":
    sys.exit(main())
