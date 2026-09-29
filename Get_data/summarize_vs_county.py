# -*- coding: utf-8 -*-
"""
2008vs2020.xlsx 各縣市得票數與得票率彙總

資料來源：Get_data/2008vs2020.xlsx（Sheet1，左右兩組欄位並排）
    左半（欄 0~3）：縣市 | 鄉鎮市區 | 蔡英文（03）得票數 | 蔡英文（03）得票率
    右半（欄 4~7）：縣市 | 鄉鎮市區 | 馬英九（02）得票數 | 馬英九（02）得票率
    同一列的兩半為同一鄉鎮市區（僅行政區劃後綴不同：區/市 vs 鄉/鎮）。

彙總方式：先加總各縣市底下所有鄉鎮市區的得票數，再計算得票率
    兩人佔比得票率 = 該候選人得票數 ÷（兩人得票數合計）　（與地圖上色同一口徑）
    原始欄加權得票率 = 以得票數加權平均原表第 3 / 7 欄的百分比（供對照用）

輸出：Get_data/2008vs2020_各縣市得票數與得票率.xlsx

執行：
    py summarize_vs_county.py [來源檔名] [輸出檔名]
"""
import os
import sys

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SRC = os.path.join(BASE_DIR, "2008vs2020.xlsx")
DEFAULT_OUT = os.path.join(BASE_DIR, "2008vs2020_各縣市得票數與得票率.xlsx")

# 候選人：名稱、縣市欄、鄉鎮欄、得票數欄、原始得票率欄
CAND_A = ("蔡英文", 0, 1, 2, 3)
CAND_B = ("馬英九", 4, 5, 6, 7)


def parse_number(v):
    """'12558' / '12,558' → float；無法解析回傳 nan。"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return float("nan")
    try:
        return float(str(v).strip().replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return float("nan")


def parse_rate(v):
    """'69.232%' / 69.232 → float；無法解析回傳 nan。"""
    return parse_number(v)


def summarize(src=DEFAULT_SRC, out=DEFAULT_OUT):
    raw = pd.read_excel(src, sheet_name="Sheet1", header=None)
    df = raw[1:].copy()                               # 略過表頭列
    df = df[df[CAND_A[1]].notna()]
    df = df[df[CAND_A[1]].astype(str).ne("總計")].reset_index(drop=True)

    name_a, cty_col_a, town_col_a, vote_col_a, rate_col_a = CAND_A
    name_b, cty_col_b, town_col_b, vote_col_b, rate_col_b = CAND_B

    # 兩半的縣市名必須一致，否則無法確定該列屬於哪個縣市
    bad = df[cty_col_a].astype(str).str.strip() != df[cty_col_b].astype(str).str.strip()
    if bad.any():
        print(f"  ※ 左右兩半縣市名不一致 {int(bad.sum())} 列，將以左半為準。")

    rec = pd.DataFrame({
        "county": df[cty_col_a].astype(str).str.strip(),
        "town": df[town_col_a].astype(str).str.strip(),
        f"votes_{name_a}": df[vote_col_a].map(parse_number),
        f"rate_{name_a}": df[rate_col_a].map(parse_rate),
        f"votes_{name_b}": df[vote_col_b].map(parse_number),
        f"rate_{name_b}": df[rate_col_b].map(parse_rate),
    })

    rows = []
    for county, g in rec.groupby("county", sort=False):
        va = g[f"votes_{name_a}"].sum()
        vb = g[f"votes_{name_b}"].sum()
        total = va + vb
        rows.append({
            "縣市": county,
            "鄉鎮市區數": len(g),
            f"{name_a}得票數": int(va),
            f"{name_a}得票率": va / total * 100 if total > 0 else float("nan"),
            f"{name_a}原始欄加權得票率": (g[f"rate_{name_a}"] * g[f"votes_{name_a}"]).sum() / va
                                        if va > 0 else float("nan"),
            f"{name_b}得票數": int(vb),
            f"{name_b}得票率": vb / total * 100 if total > 0 else float("nan"),
            f"{name_b}原始欄加權得票率": (g[f"rate_{name_b}"] * g[f"votes_{name_b}"]).sum() / vb
                                        if vb > 0 else float("nan"),
            "兩人合計得票數": int(total),
        })

    out_df = pd.DataFrame(rows)
    diff = out_df[f"{name_a}得票率"] - out_df[f"{name_b}得票率"]
    out_df = out_df.assign(兩人差值=diff.round(2))
    out_df = out_df.sort_values(f"{name_a}得票率", ascending=False).reset_index(drop=True)

    total_row = {
        "縣市": "全台合計",
        "鄉鎮市區數": int(out_df["鄉鎮市區數"].sum()),
        f"{name_a}得票數": int(out_df[f"{name_a}得票數"].sum()),
        f"{name_b}得票數": int(out_df[f"{name_b}得票數"].sum()),
        "兩人合計得票數": int(out_df["兩人合計得票數"].sum()),
    }
    grand = out_df["兩人合計得票數"].sum()
    for name in (name_a, name_b):
        total_row[f"{name}得票率"] = out_df[f"{name}得票數"].sum() / grand * 100
        total_row[f"{name}原始欄加權得票率"] = (
            (out_df[f"{name}原始欄加權得票率"] * out_df[f"{name}得票數"]).sum()
            / out_df[f"{name}得票數"].sum())
    total_row["兩人差值"] = round(total_row[f"{name_a}得票率"] - total_row[f"{name_b}得票率"], 2)

    out_df = pd.concat([out_df, pd.DataFrame([total_row])], ignore_index=True)
    for col in out_df.columns:
        if out_df[col].dtype.kind == "f":
            out_df[col] = out_df[col].round(4)

    return out_df


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    print("=" * 78)
    print(f"  來源：{src}")
    print("=" * 78)

    table = summarize(src, out)
    with pd.option_context("display.width", 240, "display.max_rows", 60,
                           "display.unicode.east_asian_width", True):
        print(table.to_string(index=False))

    table.to_excel(out, index=False)
    print(f"\n  輸出：{out}")


if __name__ == "__main__":
    main()
