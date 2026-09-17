# -*- coding: utf-8 -*-
"""
把 2008 年立法委員全國不分區及僑居國外國民選舉原始投開票所資料(*.xls)
整理成仿 2024新北_得票率.xlsx 的格式。

每個縣市產出一個 Excel 檔 (2008{縣市}_得票率.xlsx)，內含三個工作表：
  各里彙總     村里得票率 (同 2024 參考格式)
  各鄉鎮(市、區)彙總  鄉鎮市區層級得票數與得票率
  縣市彙總     縣市層級得票數與得票率
"""
import glob
import os
import re
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "Data")
OUT_DIR = os.path.join(BASE_DIR, "data")

PARTY_COUNT = 12
VALID_COL = 15
INVALID_COL = 16
POLLED_COL = 17


def is_blank(value):
    return pd.isna(value) or (isinstance(value, str) and value.strip() == "")


def parse_xls(path):
    sheet = pd.ExcelFile(path).sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    title = str(df.iloc[0, 0])
    match = re.search(r"選舉(.+?)各政黨", title)
    county = match.group(1) if match else os.path.splitext(os.path.basename(path))[0]

    parties = [str(x).strip() for x in df.iloc[4, 3 : 3 + PARTY_COUNT]]

    for row in range(len(df)):
        if "總" in str(df.iloc[row, 0] if pd.notna(df.iloc[row, 0]) else ""):
            total_row = row
            break
    else:
        raise ValueError(f"{path} 找不到總計列")

    cur_district = None
    records = []
    for row in range(total_row + 1, len(df)):
        district_cell, village_cell = df.iloc[row, 0], df.iloc[row, 1]
        if not is_blank(district_cell) and is_blank(village_cell):
            cur_district = str(district_cell).strip()
        elif not is_blank(village_cell):
            votes = [int(df.iloc[row, 3 + j]) for j in range(PARTY_COUNT)]
            records.append(
                {
                    "county": county,
                    "district": cur_district,
                    "village": str(village_cell).strip(),
                    "votes": votes,
                    "valid": int(df.iloc[row, VALID_COL]),
                    "invalid": int(df.iloc[row, INVALID_COL]),
                    "polled": int(df.iloc[row, POLLED_COL]),
                }
            )
    return county, parties, records


def build_village_frame(county, parties, records):
    rows = []
    for rec in records:
        row = {
            "選舉區別": county,
            "鄉(鎮、市、區)別": rec["district"],
            "村里別": rec["village"],
        }
        for j, party in enumerate(parties):
            row[f"{party}得票率"] = rec["votes"][j] / rec["valid"] * 100
        rows.append(row)
    return pd.DataFrame(rows)


def build_township_frame(county, parties, records):
    grouped = {}
    order = []
    for rec in records:
        d = rec["district"]
        if d not in grouped:
            grouped[d] = {"district": d, "votes": [0] * PARTY_COUNT,
                          "valid": 0, "invalid": 0, "polled": 0}
            order.append(d)
        g = grouped[d]
        for j in range(PARTY_COUNT):
            g["votes"][j] += rec["votes"][j]
        g["valid"] += rec["valid"]
        g["invalid"] += rec["invalid"]
        g["polled"] += rec["polled"]

    rows = []
    for d in order:
        g = grouped[d]
        row = {"選舉區別": county, "鄉(鎮、市、區)別": d}
        for j, party in enumerate(parties):
            row[f"{party}得票數"] = g["votes"][j]
        for j, party in enumerate(parties):
            row[f"{party}得票率"] = g["votes"][j] / g["valid"] * 100
        row["有效票數"] = g["valid"]
        row["無效票數"] = g["invalid"]
        row["投票數"] = g["polled"]
        rows.append(row)
    return pd.DataFrame(rows)


def build_county_frame(county, parties, records):
    votes = [sum(rec["votes"][j] for rec in records) for j in range(PARTY_COUNT)]
    valid = sum(rec["valid"] for rec in records)
    invalid = sum(rec["invalid"] for rec in records)
    polled = sum(rec["polled"] for rec in records)
    row = {"選舉區別": county}
    for j, party in enumerate(parties):
        row[f"{party}得票數"] = votes[j]
    for j, party in enumerate(parties):
        row[f"{party}得票率"] = votes[j] / valid * 100
    row["有效票數"] = valid
    row["無效票數"] = invalid
    row["投票數"] = polled
    return pd.DataFrame([row])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.xls")))
    for path in files:
        county, parties, records = parse_xls(path)
        village_df = build_village_frame(county, parties, records)
        township_df = build_township_frame(county, parties, records)
        county_df = build_county_frame(county, parties, records)

        out_path = os.path.join(OUT_DIR, f"2008{county}_得票率.xlsx")
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            village_df.to_excel(writer, sheet_name="各里彙總", index=False)
            township_df.to_excel(writer, sheet_name="各鄉鎮(市、區)彙總", index=False)
            county_df.to_excel(writer, sheet_name="縣市彙總", index=False)

        print(
            f"{county}  村里 {len(records):>5}  鄉鎮市區 {len(township_df):>3}  "
            f"→ {os.path.basename(out_path)}"
        )
    print(f"完成，共 {len(files)} 個縣市，輸出目錄：{OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())