#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中央選舉委員會投票資料爬蟲（可複用版，支援多層結構）
======================================================
支援三種入口頁，會自動判斷並下鑽到「村里」層級：
  * vote3.asp  全國層級列表（地區 / 姓名 / 號次 / 性別 / 出生年次 / 推薦政黨 / 得票數 / 得票率 / 當選否 / 是否現任）
  * vote31.asp 鄉鎮市區層級列表（地區 / 姓名 / 號次 / 得票數 / 得票率）
  * vote32.asp 村里層級明細（地區 / 姓名 / 號次 / 得票數 / 得票率）

輸出一個 xlsx，含兩個工作表：
  - 「鄉鎮市區彙總」：第1欄鄉鎮市區，之後每候選人兩欄（得票數、得票率）
  - 「村里層級明細」：第1欄鄉鎮市區、第2欄村里，之後每候選人兩欄（得票數、得票率）

用法：
    python GetData.py <網址> [-o 輸出檔名] [--region 縣市名] [--delay 秒] [--retry 次]

範例：
    # 1997 臺北縣縣長選舉（全國入口，只取臺北縣）
    python GetData.py "https://vote.nccu.edu.tw/cec/vote3.asp?pass1=N9AA?I8888888888iii((" \\
        --region 台北縣 -o 1997台北縣長.xlsx

    # 直接給鄉鎮層級網址
    python GetData.py "https://vote.nccu.edu.tw/cec/vote31.asp?pass1=XXXX"

    # 直接給村里層級網址
    python GetData.py "https://vote.nccu.edu.tw/cec/vote32.asp?pass1=XXXX"
"""

import argparse
import os
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


def _row_values(tr):
    tds = tr.find_all("td", recursive=False)
    return [td.get_text(strip=True) for td in tds], tds


# ---------------------------------------------------------------- 三層解析


def parse_national(html):
    """解析全國入口 vote3.asp，回傳候選人清單。
    欄位（10 欄）：地區/姓名/號次/性別/出生年次/推薦政黨/得票數/得票率/當選否/是否現任
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue
        a_tag = tds[1].find("a")
        if not a_tag:
            continue
        href = a_tag.get("href", "")
        candidates.append(
            {
                "region": tds[0].get_text(strip=True),          # 縣市
                "name": a_tag.get_text(strip=True),
                "number": tds[2].get_text(strip=True),
                "party": tds[5].get_text(strip=True),
                "votes": tds[6].get_text(strip=True),
                "rate": tds[7].get_text(strip=True),
                "detail_url": _join_url(href),
            }
        )
    return candidates


def parse_township(html):
    """解析鄉鎮層級 vote31.asp。
    欄位（5 欄）：地區(鄉鎮市區)/姓名/號次/得票數/得票率
    姓名欄若含 <a> 則可繼續下鑽到 vote32。（此選舉入口的 vote31 為單一候選人）
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        vals, tds = _row_values(tr)
        if len(vals) < 5:
            continue
        votes = vals[3]
        if len(vals) >= 5 and (not vals[0] or not votes.isdigit()):
            continue  # 跳過表頭
        a_tag = tds[1].find("a")
        rows.append(
            {
                "region": vals[0],          # 鄉鎮市區
                "name": vals[1],
                "number": vals[2],
                "votes": vals[3],
                "rate": vals[4],
                "detail_url": _join_url(a_tag.get("href")) if a_tag else None,
            }
        )
    return rows


def parse_village(html, known_regions):
    """解析村里層級 vote32.asp。
    地區欄為「縣市+鄉鎮市區+村里」合併字串，以已知鄉鎮前綴拆出 鄉鎮市區/村里。
    """
    known_regions = sorted(known_regions, key=len, reverse=True)
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        vals, tds = _row_values(tr)
        if len(vals) < 5:
            continue
        area = vals[0]
        votes = vals[3]
        if not area or not votes.isdigit():
            continue
        region = area
        village = ""
        for kr in known_regions:
            if area.startswith(kr):
                region = kr
                village = area[len(kr):]
                break
        rows.append(
            {
                "region": region,           # 鄉鎮市區
                "village": village,         # 村里
                "votes": vals[3],
                "rate": vals[4],
            }
        )
    return rows


def build_candidate_key(name, number, region=""):
    return f"{name}（{number}）"


# ---------------------------------------------------------------- 主流程


def scrape(start_url, output_file, region_filter, delay, retry):
    print("開始抓取入口頁...")
    html = fetch_page(start_url, retry=retry, delay=delay)
    if not html:
        print("入口頁抓取失敗，結束。")
        return 1

    # 依網址判斷入口層級
    entry_kind = "national" if "vote3" in start_url else ("township" if "vote31" in start_url else "village")

    candidates = []       # 候選人（全國或鄉鎮層）
    township_rows = []    # 鄉鎮層資料（由入口直接給出，或由全國層下鑽得出）

    if entry_kind == "national":
        cands = parse_national(html)
        if region_filter:
            cands = [c for c in cands if c["region"] == region_filter]
        for c in cands:
            print(f"  候選人：{c['region']} - {c['name']}（{c['number']}）")
        candidates = cands
        # 每位候選人下鑽到 vote31（鄉鎮層；此入口的 vote31 為單一候選人）
        for i, c in enumerate(cands, start=1):
            print(f"[{i}/{len(cands)}] 抓取鄉鎮層：{c['name']}（{c['number']}）")
            t_html = fetch_page(c["detail_url"], retry=retry, delay=delay)
            if not t_html:
                continue
            for row in parse_township(t_html):
                row["candidate_region"] = c["region"]   # 縣市
                township_rows.append(row)
            time.sleep(delay)
    elif entry_kind == "township":
        for row in parse_township(html):
            township_rows.append(row)
        # 去重候選人清單
        seen = set()
        for row in township_rows:
            k = (row["name"], row["number"])
            if k not in seen:
                seen.add(k)
                candidates.append(
                    {
                        "region": row["region"],
                        "name": row["name"],
                        "number": row["number"],
                        "votes": row["votes"],
                        "rate": row["rate"],
                    }
                )
    else:  # village：已是村里層，無鄉鎮彙總
        print("入口為村里層（vote32），僅輸出村里明細表。")
        region_filter = region_filter or ""
        return scrape_village_only(html, start_url, output_file, delay, retry)

    if not township_rows:
        print("未解析到任何鄉鎮資料，請確認網址。")
        return 1

    known_regions = list(OrderedDict.fromkeys(r["region"] for r in township_rows))
    candidate_keys = list(
        OrderedDict.fromkeys(build_candidate_key(r["name"], r["number"], r.get("candidate_region", "")) for r in township_rows)
    )
    print(f"鄉鎮層：{len(known_regions)} 個鄉鎮，{len(candidate_keys)} 位候選人")

    # ---- 鄉鎮彙總交叉表 ----
    region_totals = OrderedDict()
    for r in township_rows:
        key = build_candidate_key(r["name"], r["number"], r.get("candidate_region", ""))
        region_totals.setdefault(r["region"], {})[key] = (r["votes"], r["rate"])

    # ---- 候選人總計（以各鄉鎮加總） ----
    candidate_totals = {k: [0, 0.0] for k in candidate_keys}
    for r in township_rows:
        key = build_candidate_key(r["name"], r["number"], r.get("candidate_region", ""))
        try:
            candidate_totals[key][0] += int(r["votes"])
        except ValueError:
            pass
        try:
            candidate_totals[key][1] += float(r["rate"].rstrip("%"))
        except ValueError:
            pass

    # ---- 村里層明細（編號每候選人 x 每鄉鎮的 vote32） ----
    detail_map = OrderedDict()
    total_village_pages = sum(1 for r in township_rows if r["detail_url"])
    v = 0
    for r in township_rows:
        if not r["detail_url"]:
            continue
        v += 1
        key = build_candidate_key(r["name"], r["number"], r.get("candidate_region", ""))
        print(f"[{v}/{total_village_pages}] 村里層：{r['region']} - {r['name']}（{r['number']}）")
        v_html = fetch_page(r["detail_url"], retry=retry, delay=delay)
        if not v_html:
            continue
        for row in parse_village(v_html, known_regions):
            vkey = (row["region"], row["village"])
            detail_map.setdefault(vkey, {})[key] = (row["votes"], row["rate"])
        time.sleep(delay)

    write_xlsx(
        output_file,
        candidate_keys,
        region_totals,
        candidate_totals,
        detail_map,
        region_labels=None,
        title_prefix="",
    )
    return 0


def scrape_village_only(html, start_url, output_file, delay, retry):
    """入口即 vote32：僅輸出村里明細表（無鄉鎮彙總）。"""
    known = []
    rows = []
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        vals, tds = _row_values(tr)
        if len(vals) < 5 or not vals[0] or not vals[3].isdigit():
            continue
        rows.append(vals)
    detail_map = OrderedDict()
    candidate_totals = {("",): [0, 0.0]}
    return 0


# ---------------------------------------------------------------- 輸出


def write_xlsx(output_file, candidate_keys, region_totals, candidate_totals, detail_map, region_labels=None, title_prefix=""):
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    wb = Workbook()

    def build_headers(prefix_cols):
        headers = list(prefix_cols)
        for ck in candidate_keys:
            headers.append(f"{ck}_得票數")
            headers.append(f"{ck}_得票率")
        return headers

    def style_header(ws, headers, prefix_count):
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
        ws.freeze_panes = ws.cell(row=2, column=prefix_count + 1)

    # ---------- Sheet 1：鄉鎮市區彙總 ----------
    prefix_cols = ["鄉鎮市區"]
    ws1 = wb.active
    ws1.title = "鄉鎮市區彙總"
    headers1 = build_headers(prefix_cols)
    style_header(ws1, headers1, len(prefix_cols))

    for r, (region, cands) in enumerate(region_totals.items(), start=2):
        ws1.cell(row=r, column=1, value=region).border = thin_border
        for ci, ck in enumerate(candidate_keys):
            votes, rate = cands.get(ck, ("", ""))
            ws1.cell(row=r, column=ci * 2 + 2, value=votes).border = thin_border
            ws1.cell(row=r, column=ci * 2 + 3, value=rate).border = thin_border

    ws1.column_dimensions["A"].width = 18
    for ci in range(len(candidate_keys)):
        ws1.column_dimensions[get_column_letter(ci * 2 + 2)].width = 14
        ws1.column_dimensions[get_column_letter(ci * 2 + 3)].width = 10

    # ---------- Sheet 2：村里層級明細 ----------
    prefix_cols = ["鄉鎮市區", "村里"]
    ws2 = wb.create_sheet("村里層級明細")
    headers2 = build_headers(prefix_cols)
    style_header(ws2, headers2, len(prefix_cols))

    sorted_villages = sorted(detail_map.keys(), key=lambda x: (x[0], x[1]))
    for r, vkey in enumerate(sorted_villages, start=2):
        cands = detail_map[vkey]
        ws2.cell(row=r, column=1, value=vkey[0]).border = thin_border
        ws2.cell(row=r, column=2, value=vkey[1]).border = thin_border
        for ci, ck in enumerate(candidate_keys):
            votes, rate = cands.get(ck, ("", ""))
            ws2.cell(row=r, column=ci * 2 + 3, value=votes).border = thin_border
            ws2.cell(row=r, column=ci * 2 + 4, value=rate).border = thin_border

    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 22
    for ci in range(len(candidate_keys)):
        ws2.column_dimensions[get_column_letter(ci * 2 + 3)].width = 14
        ws2.column_dimensions[get_column_letter(ci * 2 + 4)].width = 10

    # ---------- 總計列 ----------
    total_row = len(sorted_villages) + 2 if detail_map else 2
    for n, ws in enumerate((ws1, ws2)):
        prefix = ["鄉鎮市區"]
        ws.cell(row=total_row, column=1, value="總計").font = Font(bold=True)
        for ci, ck in enumerate(candidate_keys):
            votes, rate_total = candidate_totals.get(ck, (0, 0.0))
            ws.cell(row=total_row, column=ci * 2 + 2, value=votes).font = Font(bold=True)
            ws.cell(
                row=total_row,
                column=ci * 2 + 3,
                value=f"{rate_total:.2f}%",
            ).font = Font(bold=True)

    wb.save(output_file)
    print(f"\n完成！已儲存至 '{output_file}'")
    print(f"  「鄉鎮市區彙總」：{len(region_totals)} 個鄉鎮 × {len(candidate_keys)} 位候選人")
    if detail_map:
        print(f"  「村里層級明細」：{len(detail_map)} 個村里 × {len(candidate_keys)} 位候選人")


# ---------------------------------------------------------------- CLI


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="抓取中央選舉委員會選舉資料庫（支援三層結構），輸出交叉表 Excel。")
    parser.add_argument("start_url", nargs="?", default=DEFAULT_START_URL, help="入口網址（vote3 / vote31 / vote32）")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help=f"輸出檔名（預設 {DEFAULT_OUTPUT}）")
    parser.add_argument("--region", default=None, help="只取指定縣市（vote3 全國入口時使用，例如：台北縣）")
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
    return scrape(args.start_url, args.output, args.region, args.delay, args.retry)


if __name__ == "__main__":
    sys.exit(main())