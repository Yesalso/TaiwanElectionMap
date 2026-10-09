# -*- coding: utf-8 -*-
"""
把 2024 年第十一屆全國不分區及僑居國外國民立法委員選舉原始投開票所資料
（「第11屆…各政黨在{縣市}各投開票所得票數一覽表.xlsx」）整理成
仿 2008/2016 得票率 Excel 的格式。

每個縣市產出一個 Excel 檔 (2024{縣市}_得票率.xlsx)，內含三個工作表：
  各里彙總     村里得票率（同村里多投開票所以得票數加總後再算得票率）
  各鄉鎮(市、區)彙總  鄉鎮市區層級得票數與得票率
  縣市彙總     縣市層級得票數與得票率

原始檔案格式（2024 版主要為新格式，但各縣市混用兩種版面，程式自動偵測）：

新格式（多數縣市）：
    第0列 標題（含縣市名：…選舉各政黨在○○縣各投開票所…）
    第1列 欄位名（縣市 | 鄉(鎮、市、區)別 | 村里別 | 投開票所別 | 各政黨得票情形 …）
    第2列 政黨名（由第4欄起，共 16 個政黨；格式 '(1)\n\n小民參政歐巴桑聯盟'）
    第5列附近 縣市「總計」列（col0/col1 含「總」字）
    其後各列為投票所資料；鄉鎮小計列無村里名（col2 空白）

舊格式（A05-6，如雲林縣）：
    第0列 標題
    第1列 欄位名（鄉(鎮、市、區)別 | 村里別 | 投開票所別 | 各政黨得票情形 …）
    第2列 政黨名（由第3欄起；格式同新格式）
    第5列附近 縣市「總計」列（col0 含「總」字）
    其後各列為投票所資料；鄉鎮小計列 col0 有鄉鎮名、col1 空白

統一以「第1列 col0 是否為『縣市』」判斷版面：
    - 是 → 政黨自第4欄起，鄉鎮=col1、村里=col2
    - 否 → 政黨自第3欄起，鄉鎮=col0、村里=col1
其後 有效票數A | 無效票數B | 投票數C ，欄位位置隨政黨數浮動（本屆 16 黨）。
"""
import glob
import os
import re
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

PARTY_NAME_ROW = 2        # 政黨名稱列（0-based 第 2 列）


def is_blank(value):
    return pd.isna(value) or (isinstance(value, str) and value.strip() == "")


def parse_xlsx(path):
    sheet = pd.ExcelFile(path).sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    title = str(df.iloc[0, 0])
    match = re.search(r"選舉各政黨在(.+?)各投開票所", title)
    county = match.group(1) if match else os.path.splitext(os.path.basename(path))[0]

    # 版面偵測：新格式第1列 col0 = '縣市'；舊格式(A05-6) col0 = '鄉(鎮、市、區)別'
    header0 = str(df.iloc[1, 0]) if pd.notna(df.iloc[1, 0]) else ""
    if header0.strip() == "縣市":
        party_start_col = 4     # 縣市 | 鄉鎮 | 村里 | 投開票所 | 政黨…
        district_col, village_col = 1, 2
    else:
        party_start_col = 3     # 鄉鎮 | 村里 | 投開票所 | 政黨…
        district_col, village_col = 0, 1

    parties = []
    for col in range(party_start_col, df.shape[1]):
        cell = df.iloc[PARTY_NAME_ROW, col]
        if is_blank(cell):
            break
        # 政黨格格式：'(1)\n\n小民參政歐巴桑聯盟' → 去編號行「(N)」與空行，取第一個
        lines = [ln.strip() for ln in str(cell).split("\n")
                 if ln.strip() and not re.fullmatch(r"\(\d+\)", ln.strip())
                 and not ln.strip().isdigit()]
        name = lines[0] if lines else str(cell).strip()
        # 政黨名統一用字：民众黨的「眾 U+773E」一律改為「衆 U+8846」（如 台灣民眾黨→台灣民衆黨）
        name = name.replace("\u773e", "\u8846")
        parties.append(name)
    n_party = len(parties)
    if n_party == 0:
        raise ValueError(f"{path} 未偵測到政黨欄位")

    # 政黨得票數之後的欄位位置隨政黨數浮動
    valid_col = party_start_col + n_party     # 有效票數A
    invalid_col = valid_col + 1               # 無效票數B
    polled_col = valid_col + 2                # 投票數C

    total_row = None
    for row in range(len(df)):
        c0 = str(df.iloc[row, district_col]) if pd.notna(df.iloc[row, district_col]) else ""
        c1 = str(df.iloc[row, village_col]) if pd.notna(df.iloc[row, village_col]) else ""
        if "總" in c0 or "總" in c1:
            total_row = row
            break
    if total_row is None:
        raise ValueError(f"{path} 找不到總計列")

    records = []
    cur_district = None
    for row in range(total_row + 1, len(df)):
        district_cell, village_cell = df.iloc[row, district_col], df.iloc[row, village_col]
        if is_blank(district_cell) and is_blank(village_cell):
            continue
        if is_blank(village_cell):
            cur_district = _strip_loc(district_cell)   # 鄉鎮小計列：更新現行鄉鎮
            continue
        if cur_district is None:
            continue
        votes = []
        for j in range(n_party):
            v = df.iloc[row, party_start_col + j]
            votes.append(0 if is_blank(v) else int(float(v)))
        records.append(
            {
                "county": county,
                "district": cur_district,
                "village": _strip_loc(village_cell),
                "votes": votes,
                "valid": int(float(df.iloc[row, valid_col])) if pd.notna(df.iloc[row, valid_col]) else 0,
                "invalid": int(float(df.iloc[row, invalid_col])) if pd.notna(df.iloc[row, invalid_col]) else 0,
                "polled": int(float(df.iloc[row, polled_col])) if pd.notna(df.iloc[row, polled_col]) else 0,
            }
        )
    if not records:
        raise ValueError(f"{path} 未找到任何投票所資料列")
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
    files = sorted(glob.glob(os.path.join(DATA_DIR, "第11屆*.xlsx")))
    if not files:
        raise FileNotFoundError(f"找不到 2024 原始投開票所 Excel：{DATA_DIR}/第11屆*.xlsx")

    for path in files:
        county, parties, records = parse_xlsx(path)
        village_df = build_village_frame(county, parties, records)
        township_df = build_township_frame(county, parties, records)
        county_df = build_county_frame(county, parties, records)

        out_path = os.path.join(DATA_DIR, f"2024{county}_得票率.xlsx")
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            village_df.to_excel(writer, sheet_name="各里彙總", index=False)
            township_df.to_excel(writer, sheet_name="各鄉鎮(市、區)彙總", index=False)
            county_df.to_excel(writer, sheet_name="縣市彙總", index=False)

        print(
            f"{county}  村里 {len(village_df):>5}  鄉鎮市區 {len(township_df):>3}  "
            f"投票所 {len(records):>5}  → {os.path.basename(out_path)}"
        )
    print(f"完成，共 {len(files)} 個縣市，輸出目錄：{DATA_DIR}")


if __name__ == "__main__":
    sys.exit(main())