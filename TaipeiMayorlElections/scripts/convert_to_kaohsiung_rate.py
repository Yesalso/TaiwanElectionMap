# -*- coding: utf-8 -*-
"""
將爬蟲產出「高雄市長選舉村里層級明細」xlsx 轉換為「得票率專用」格式，
與 MayoralElections/data/2018新北_得票率.xlsx 相同欄位結構：

    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率 ...

選項 --cands 指定納入圖例的候選人（以得票率欄位名稱含之名稱比對，預設韓國瑜、陳其邁）。

執行：
    py convert_to_kaohsiung_rate.py
"""
import argparse
import os
import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

CITY = "高雄市"
SHEET_SUMMARY = "各里彙總"

# 原始爬蟲檔：村里層級明細 工作表
DEFAULT_SOURCE = os.path.join(ROOT_DIR, "2018高雄市長_村里得票.xlsx")
DEFAULT_OUTPUT = os.path.join(ROOT_DIR, "data", "2018高雄市長_得票率.xlsx")
RATE_SHEET = "村里層級明細"

# 得票率欄名規則：<姓名>（<號次>）_得票率
RATE_COL_RE = re.compile(r"^(.*?)（\d{1,2}）_得票率$")


def build_rate_map(df):
    """回傳 {候選人名稱: [欄索引...]} 只取結尾為「_得票率」的欄。"""
    rate_cols = [c for c in df.columns if str(c).endswith("_得票率")]
    mapping = {}
    for c in rate_cols:
        m = RATE_COL_RE.match(str(c))
        if m:
            mapping.setdefault(m.group(1), []).append(c)
    return mapping


def parse_rate(v):
    """'45.33%' → 45.33；NaN / 空值 → None；"nan"字串 → None。"""
    if pd.isna(v):
        return None
    s = re.sub(r"%", "", str(v).strip())
    s = s.replace("nan", "").replace("NaN", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def convert(source_file, output_file, cands):
    df = pd.read_excel(source_file, sheet_name=RATE_SHEET)
    df.columns = [str(c) for c in df.columns]

    rate_map = build_rate_map(df)
    cand_cols = []
    for name in cands:
        cols = rate_map.get(name)
        if not cols:
            raise ValueError(f"找不到候選人『{name}』的得票率欄；現有：{list(rate_map)}")
        cand_cols.append(cols[0])

    records = []
    for _, row in df.iterrows():
        raw_town = str(row["鄉鎮市區"]).strip()
        raw_vill = str(row["村里"]).strip()
        if (not raw_town) or raw_town == "總計" or raw_vill == "總計" or raw_town.lower() == "nan" or raw_vill.lower() == "nan":
            continue
        town = raw_town[len(CITY):] if raw_town.startswith(CITY) else raw_town
        rates = []
        ok = True
        for c in cand_cols:
            r = parse_rate(row[c])
            if r is None:
                ok = False
            rates.append(r)
        records.append([CITY, town, raw_vill] + rates)

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(SHEET_SUMMARY)
    headers = ["選舉區別", "鄉(鎮、市、區)別", "村里別"] + [f"{name}得票率" for name in cands]
    bold = Font(name="Calibri", size=11, bold=True)
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c).value = h
        ws.cell(row=1, column=c).font = bold
    for r, rec in enumerate(records, start=2):
        for c, v in enumerate(rec, start=1):
            ws.cell(row=r, column=c).value = v
    wb.save(output_file)
    print(f"已產生: {output_file}  候選人={cands}  村里數={len(records)}")


def main():
    parser = argparse.ArgumentParser(description="轉換高雄市長選舉爬蟲資料為得票率專用格式")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cands", nargs="*", default=["韓國瑜", "陳其邁"])
    args = parser.parse_args()
    convert(args.source, args.output, args.cands)


if __name__ == "__main__":
    main()