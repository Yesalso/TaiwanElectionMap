# -*- coding: utf-8 -*-
"""
將「新北市」2010 / 2014 市長選舉的原始寬格式 Excel，
轉換成與「高雄2024.xlsx」相同的新層式格式（3 個工作表）。

轉換規則：
1. 工作表與高雄相同：
     各里彙總、新北市、各選區所含里別
2. 各里彙總欄位：選舉區別、鄉(鎮、市、區)別、村里別、各候選人「得票數」欄、有效票數A
3. 新北市（主工作表）欄位：鄉(鎮、市、區)別、村里別、各候選人「(號次) 姓名」欄、有效票數A
   （原始資料沒有 無效票數B / 投票數C / 已領未投票數D / 發出票數E / 用餘票數F / 選舉人數G / 投票率H，
     故不建立這些欄位）
4. 有效票數A：原始只有「得票數＋百分比」，且 2014 年尚有未列出的候選人票，
   故以「得票數 ÷ 百分比」反推真實有效票數（取最接近且能還原二字化百分比的整數）。
5. 候選人欄位只用候選人姓名（原始資料無政黨欄位）。

執行方式：
    py convert_to_kaohsiung_format.py
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CITY = "新北市"

HEADER_SUMMARY = ["選舉區別", "鄉(鎮、市、區)別", "村里別"]
HEADER_LIST = ["選舉區別", "鄉(鎮、市、區)別", "村里別"]

VALID_VOTES_HEADER = "有效票數A A=1+2+...+N"

SHEET_SUMMARY = "各里彙總"          # 各里彙總（各候選人得票數）
SHEET_CITY = "新北市"                  # 主工作表
SHEET_LIST = "各選區所含里別"       # 各選區所含里別

# ---- 得票率專用（只含百分比，欄位順序固定：國民黨 → 民進黨）----
PARTY_ORDER = ["中國國民黨", "民主進步黨"]

CAND_PARTY = {
    "朱立倫": "中國國民黨",
    "蔡英文": "民主進步黨",
    "游錫堃": "民主進步黨",
    "侯友宜": "中國國民黨",
    "蘇貞昌": "民主進步黨",
}


def parse_location(full_name):
    """將『新北市板橋區留侯里』拆成 (區、里)。"""
    assert full_name.startswith(CITY)
    rest = full_name[len(CITY):]
    idx = rest.find("區")
    if idx == -1:
        raise ValueError("無法解析行政區: %r" % full_name)
    district = rest[: idx + 1]
    village = rest[idx + 1:]
    return district, village


def infer_valid_votes(votes, pct):
    """由『得票數 ÷ 百分比』推估真實有效票數 A。

    pct 為四捨五入到 4 位小數的百分比，故取能同時還原兩位候選人
    百分比之整數 A；若無法同時還原則用推估值的中位數。
    """
    est = [v / p for v, p in zip(votes, pct)]
    candidates = sorted({round(e) for e in est})
    best = None
    for cand in candidates:
        if cand > 0 and all(abs(round(v / cand, 4) - p) < 1e-9 for v, p in zip(votes, pct)):
            best = cand
            break
    if best is None:
        best = round(sum(est) / len(est))
    return best


def read_candidates(sheet_df):
    """從寬格式 DataFrame 取候選人清單，回傳
    [(號次, 姓名)], 與每里的 {姓名: (得票數, 百分比)}。
    """
    left = {str(sheet_df.iloc[i][1]): int(sheet_df.iloc[i][2]) for i in range(len(sheet_df))}
    right = {str(sheet_df.iloc[i][6]): int(sheet_df.iloc[i][7]) for i in range(len(sheet_df))}
    candidates = [(name, num) for name, num in left.items()]
    candidates += [(name, num) for name, num in right.items()]
    # 依號次排序
    candidates = sorted(set(candidates), key=lambda x: x[1])
    return candidates


def convert(source_file, output_file):
    df = pd.read_excel(source_file, header=None, sheet_name="Sheet1")
    candidates = read_candidates(df)

    records = []
    for _, row in df.iterrows():
        full = str(row[0])
        assert str(row[5]) == full
        district, village = parse_location(full)
        vcand = {}
        for name, num in candidates:
            # 依候選人出現的位置（左 = column 1..4，右 = column 6..9）
            if row[1] == name and row[6] != name:
                vcand[name] = (int(row[3]), float(row[4]))
            elif row[6] == name and row[1] != name:
                vcand[name] = (int(row[8]), float(row[9]))
            else:
                raise ValueError("候選人重複出現: %r" % name)
        votes = [vcand[name][0] for name, _ in candidates]
        pcts = [vcand[name][1] for name, _ in candidates]
        A = infer_valid_votes(votes, pcts)
        # 驗證：以 A 反算之百分比需與原始一致
        # （原資料百分比為四捨五入值，遇 0.5 邊界時容許差 1 位小數）
        for name, (v, p) in vcand.items():
            if abs(round(v / A, 4) - p) > 1e-4:
                raise ValueError("有效票推估不符: %s %r A=%s" % (full, name, A))
        records.append({
            "full": full,
            "district": district,
            "village": village,
            "votes": vcand,
            "A": A,
        })

    # 建立輸出工作簿
    wb = Workbook()
    wb.remove(wb.active)

    bold = Font(name="Calibri", size=11, bold=True)
    normal = Font(name="Calibri", size=11)

    # ---- 工作表 1：各里彙總 ----
    ws1 = wb.create_sheet(SHEET_SUMMARY)
    headers1 = HEADER_SUMMARY + [f"{name}得票數" for name, _ in candidates] + ["有效票數A"]
    for c, h in enumerate(headers1, start=1):
        ws1.cell(row=1, column=c).value = h
        ws1.cell(row=1, column=c).font = bold
    for r, rec in enumerate(records, start=2):
        ws1.cell(row=r, column=1).value = CITY
        ws1.cell(row=r, column=2).value = rec["district"]
        ws1.cell(row=r, column=3).value = rec["village"]
        for i, (name, _) in enumerate(candidates, start=4):
            ws1.cell(row=r, column=i).value = rec["votes"][name][0]
        ws1.cell(row=r, column=len(headers1)).value = rec["A"]

    # ---- 工作表 2：新北市（主工作表）----
    ws2 = wb.create_sheet(SHEET_CITY)
    headers2 = ["鄉(鎮、市、區)別", "村里別"] + [f"({num}) {name}" for name, num in candidates] + [VALID_VOTES_HEADER]
    for c, h in enumerate(headers2, start=1):
        ws2.cell(row=1, column=c).value = h
        ws2.cell(row=1, column=c).font = bold
    for r, rec in enumerate(records, start=2):
        ws2.cell(row=r, column=1).value = rec["district"]
        ws2.cell(row=r, column=2).value = rec["village"]
        for i, (name, _) in enumerate(candidates, start=3):
            ws2.cell(row=r, column=i).value = rec["votes"][name][0]
        ws2.cell(row=r, column=len(headers2)).value = rec["A"]

    # ---- 工作表 3：各選區所含里別 ----
    ws3 = wb.create_sheet(SHEET_LIST)
    for c, h in enumerate(HEADER_LIST, start=1):
        ws3.cell(row=1, column=c).value = h
        ws3.cell(row=1, column=c).font = bold
    for r, rec in enumerate(records, start=2):
        ws3.cell(row=r, column=1).value = CITY
        ws3.cell(row=r, column=2).value = rec["district"]
        ws3.cell(row=r, column=3).value = rec["village"]

    wb.save(output_file)
    print(f"已產生: {output_file}  候選人={[(n, k) for n, k in candidates]}  村里數={len(records)}")


def convert_percent(source_file, output_file):
    """產生『只含候選人得票率(%)』的 Excel。

    欄位固定順序：選舉區別、鄉(鎮、市、區)別、村里別、
    中國國民黨得票率、民主進步黨得票率。
    百分比沿用原始資料之官方百分比（得票數 ÷ 有效票 × 100）。
    候選人未列於政黨對照者（如缺漏名單者）其票所佔百分比不會輸出。
    """
    df = pd.read_excel(source_file, header=None, sheet_name="Sheet1")
    candidates = read_candidates(df)

    rows = []
    for _, row in df.iterrows():
        full = str(row[0])
        assert str(row[5]) == full
        district, village = parse_location(full)
        vcand = {}
        for name, num in candidates:
            if row[1] == name and row[6] != name:
                vcand[name] = (int(row[3]), float(row[4]))
            elif row[6] == name and row[1] != name:
                vcand[name] = (int(row[8]), float(row[9]))
            else:
                raise ValueError("候選人重複出現: %r" % name)
        # 依政黨順序取候選人得票率（原始百分比為 0~1 比例，轉為 0~100）
        party_pcts = []
        for party in PARTY_ORDER:
            hit = next((p for n, (_, p) in vcand.items() if CAND_PARTY.get(n) == party), None)
            party_pcts.append(round(hit * 100, 2) if hit is not None else None)
        rows.append([CITY, district, village] + party_pcts)

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("各里彙總")
    headers = HEADER_SUMMARY + [f"{p}得票率" for p in PARTY_ORDER]
    bold = Font(name="Calibri", size=11, bold=True)
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c).value = h
        ws.cell(row=1, column=c).font = bold
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            ws.cell(row=r, column=c).value = v
    wb.save(output_file)
    print(f"已產生: {output_file}  政黨欄位={PARTY_ORDER}  村里數={len(rows)}")


def main():
    base = BASE_DIR
    for y in ("2010", "2014"):
        convert(os.path.join(base, f"{y}新北.xlsx"), os.path.join(base, f"{y}新北_高雄格式.xlsx"))
    for y in ("2010", "2014", "2018"):
        convert_percent(os.path.join(base, f"{y}新北.xlsx"), os.path.join(base, f"{y}新北_得票率.xlsx"))


if __name__ == "__main__":
    main()