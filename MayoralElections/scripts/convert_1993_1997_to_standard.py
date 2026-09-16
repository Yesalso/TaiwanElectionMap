# -*- coding: utf-8 -*-
"""
將 1993、1997 臺北縣長選舉「村里層級明細」工作表轉為標準得票率格式
（與 2010新北_得票率.xlsx 相同結構），供 Converge_to_map.py 繪圖使用。

輸出：
  1993_得票率.xlsx  →  各里彙總 (選舉區別 | 鄉鎮市區 | 村里別 | 尤清得票率 | 蔡勝邦得票率)
  1997_得票率.xlsx  →  各里彙總 (選舉區別 | 鄉鎮市區 | 村里別 | 蘇貞昌得票率 | 謝深山得票率)
"""
import os
import openpyxl

DATA_DIR = r"D:\Windows\TaiwanElection\MayoralElections\data"

# 鄉鎮市區後綴 轉換（舊制→新制）
SUFFIX_MAP = {"鎮": "區", "鄉": "區", "市": "區"}


def convert_suffix(town_full):
    """「臺北縣三峽鎮」→「新北市三峽區」"""
    if not town_full or town_full == "總計":
        return None, None, None
    # 拆城市＋鄉鎮
    for old_suf, new_suf in SUFFIX_MAP.items():
        if town_full.endswith(old_suf):
            # 找縣市：臺北縣 → 新北市
            city = "新北市"
            town_body = town_full.replace("臺北縣", "").replace(old_suf, "")
            return city, town_body + new_suf, town_body
    return None, None, None


def pct_str_to_num(v):
    """「51.54%」→ 51.54"""
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith("%"):
        s = s[:-1]
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def process_file(src_xlsx, sheet_name, out_xlsx, cand_names):
    """
    src_xlsx:  原始 xlsx 檔名
    sheet_name: 村里層級明細
    out_xlsx:  輸出標準格式檔名
    cand_names: (target_cand, other_cand) → 選圖例用的兩位候選人
    """
    wb = openpyxl.load_workbook(os.path.join(DATA_DIR, src_xlsx))
    ws = wb[sheet_name]
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    print(f"  原始欄位: {headers}")

    # 找出目標候選人的得票率欄位索引
    # headers like: ['鄉鎮市區', '里', '石瓊文（01）_得票數', '石瓊文（01）_得票率', ...]
    pct_indices = {}  # name → index of 得票率 column
    for i, h in enumerate(headers):
        if h and "得票率" in str(h):
            name = str(h).split("（")[0].split("_")[0]  # e.g. "尤清"
            pct_indices[name] = i

    target, other = cand_names
    if target not in pct_indices or other not in pct_indices:
        raise ValueError(f"找不到候選人 {target} 或 {other} 的得票率欄位，可用: {list(pct_indices.keys())}")

    # 建立輸出
    out_wb = openpyxl.Workbook()
    out_ws = out_wb.active
    out_ws.title = "各里彙總"
    out_ws.append(["選舉區別", "鄉(鎮、市、區)別", "村里別", f"{target}得票率", f"{other}得票率"])

    count = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        town_full = row[0]
        village = row[1]
        if not town_full or town_full == "總計":
            continue
        city, town_modern, town_body = convert_suffix(town_full)
        if city is None:
            continue
        rate_target = pct_str_to_num(row[pct_indices[target]])
        rate_other = pct_str_to_num(row[pct_indices[other]])
        # 村里名：已有後綴（如「三峽里」）；若無則補（不太可能缺）
        vill_full = str(village).strip() if village else ""
        out_ws.append([city, town_modern, vill_full, rate_target, rate_other])
        count += 1

    out_path = os.path.join(DATA_DIR, out_xlsx)
    out_wb.save(out_path)
    print(f"  輸出: {out_path}  ({count} 里)")


if __name__ == "__main__":
    print("=" * 50)
    print("  1993 臺北縣長 → 標準格式")
    process_file("1993台北县长.xlsx", "村里層級明細", "1993台北縣_得票率.xlsx",
                 cand_names=("尤清", "蔡勝邦"))

    print("=" * 50)
    print("  1997 臺北縣長 → 標準格式")
    process_file("1997台北縣長.xlsx", "村里層級明細", "1997台北縣_得票率.xlsx",
                 cand_names=("蘇貞昌", "謝深山"))
    print("完成。")
