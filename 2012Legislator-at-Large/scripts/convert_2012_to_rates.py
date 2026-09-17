# -*- coding: utf-8 -*-
"""
把 2012 年第八屆全國不分區及僑居國外國民立法委員選舉原始投開票所資料
（立委-A05-6-(縣市).xls）整理成仿 2008 得票率 Excel 的格式。

每個縣市產出一個 Excel 檔 (2012{縣市}_得票率.xlsx)，內含三個工作表：
  各里彙總     村里得票率（同村里多投開票所以得票數加總後再算得票率）
  各鄉鎮(市、區)彙總  鄉鎮市區層級得票數與得票率
  縣市彙總     縣市層級得票數與得票率

原始檔案格式（A05-6）：
    第0列 標題（含縣市名）
    第1列 欄位名（鄉(鎮、市、區)別 | 村里別 | 投票所別 | 各候選人得票情形 ...）
    第2列 政黨名（由第3欄起，共 N 個政黨）
    第5列 總計（其後各列為村里投票所資料；縣市/鄉鎮小計列無村里名）
"""
import glob
import os
import re
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "Data")
OUT_DIR = os.path.join(BASE_DIR, "data")

PARTY_START_COL = 3       # 政黨得票數自第 3 欄（0-based）起
VALID_COL = 14            # 有效票數A
INVALID_COL = 15          # 無效票數B
POLLED_COL = 16           # 投票數C


def is_blank(value):
    return pd.isna(value) or (isinstance(value, str) and value.strip() == "")


def parse_xls(path):
    sheet = pd.ExcelFile(path).sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    title = str(df.iloc[0, 0])
    match = re.search(r"選舉(.+?)各政黨", title)
    county = match.group(1) if match else os.path.splitext(os.path.basename(path))[0]

    parties = []
    for col in range(PARTY_START_COL, df.shape[1]):
        cell = df.iloc[2, col]
        if is_blank(cell):
            break
        # 政黨格格式：'1\n台灣國民會議\n台灣國民會議' → 取政黨名稱（去掉編號數字行）
        lines = [ln.strip() for ln in str(cell).split("\n") if ln.strip() and not ln.strip().isdigit()]
        parties.append(lines[0] if lines else str(cell).strip())

    total_row = None
    for row in range(len(df)):
        if "總" in str(df.iloc[row, 0] if pd.notna(df.iloc[row, 0]) else ""):
            total_row = row
            break
    if total_row is None:
        raise ValueError(f"{path} 找不到總計列")

    records = []
    cur_district = None
    for row in range(total_row + 1, len(df)):
        district_cell, village_cell = df.iloc[row, 0], df.iloc[row, 1]
        if not is_blank(district_cell) and is_blank(village_cell):
            cur_district = str(district_cell).strip()
        elif not is_blank(village_cell):
            votes = []
            for j in range(len(parties)):
                v = df.iloc[row, PARTY_START_COL + j]
                votes.append(0 if is_blank(v) else int(v))
            records.append(
                {
                    "county": county,
                    "district": cur_district,
                    "village": str(village_cell).strip(),
                    "votes": votes,
                    "valid": int(df.iloc[row, VALID_COL]) if pd.notna(df.iloc[row, VALID_COL]) else 0,
                    "invalid": int(df.iloc[row, INVALID_COL]) if pd.notna(df.iloc[row, INVALID_COL]) else 0,
                    "polled": int(df.iloc[row, POLLED_COL]) if pd.notna(df.iloc[row, POLLED_COL]) else 0,
                }
            )
    return county, parties, records


def _strip_loc(s):
    """去除前導全形空白（如 ' 北投區'）。"""
    return re.sub(r"^[\u3000\s]+", "", str(s).strip())


def build_village_frame(county, parties, records):
    """同一村里多投開票所 → 以得票數加總後再算得票率。"""
    grouped = {}
    order = []
    for rec in records:
        key = (_strip_loc(rec["district"]), _strip_loc(rec["village"]))
        if key not in grouped:
            grouped[key] = {"votes": [0] * len(parties), "valid": 0}
            order.append(key)
        g = grouped[key]
        for j in range(len(parties)):
            g["votes"][j] += rec["votes"][j]
        g["valid"] += rec["valid"]

    rows = []
    for (district, village) in order:
        g = grouped[(district, village)]
        row = {"選舉區別": county, "鄉(鎮、市、區)別": district, "村里別": village}
        for j, party in enumerate(parties):
            row[f"{party}得票率"] = g["votes"][j] / g["valid"] * 100
        row["有效票數A"] = g["valid"]
        rows.append(row)
    return pd.DataFrame(rows)


def build_township_frame(county, parties, records):
    grouped = {}
    order = []
    for rec in records:
        d = _strip_loc(rec["district"])
        if d not in grouped:
            grouped[d] = {"district": d, "votes": [0] * len(parties),
                          "valid": 0, "invalid": 0, "polled": 0}
            order.append(d)
        g = grouped[d]
        for j in range(len(parties)):
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
    votes = [sum(rec["votes"][j] for rec in records) for j in range(len(parties))]
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
    files = sorted(glob.glob(os.path.join(DATA_DIR, "立委-A05-6-*.xls")))
    for path in files:
        county, parties, records = parse_xls(path)
        village_df = build_village_frame(county, parties, records)
        township_df = build_township_frame(county, parties, records)
        county_df = build_county_frame(county, parties, records)

        out_path = os.path.join(OUT_DIR, f"2012{county}_得票率.xlsx")
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            village_df.to_excel(writer, sheet_name="各里彙總", index=False)
            township_df.to_excel(writer, sheet_name="各鄉鎮(市、區)彙總", index=False)
            county_df.to_excel(writer, sheet_name="縣市彙總", index=False)

        print(
            f"{county}  村里 {len(village_df):>5}  鄉鎮市區 {len(township_df):>3}  "
            f"→ {os.path.basename(out_path)}"
        )
    print(f"完成，共 {len(files)} 個縣市，輸出目錄：{OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())