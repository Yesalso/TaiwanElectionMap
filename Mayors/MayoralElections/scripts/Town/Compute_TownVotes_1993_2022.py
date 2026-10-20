# -*- coding: utf-8 -*-
"""
統計新北市（原臺北縣）歷屆首長選舉 1993–2022 各鄉鎮市區的得票數與得票率，輸出 xlsx。

屆次與來源檔（臺北縣長 → 2010 改制後為新北市長）：
    1993（第12屆）  1993台北县长.xlsx        工作表「鄉鎮市區彙總」（已為鄉鎮級）
    1997（第13屆）  1997台北縣長.xlsx        工作表「鄉鎮市區彙總」（已為鄉鎮級）
    2001（第14屆）  台北县2001.xlsx           Sheet1（村里級，每 5 欄一組候選人）
    2005（第15屆）  2005台北县_各乡镇市區得票數.csv
                                             鄉鎮市級長表（地區,姓名,號次,得票數,得票率）
    2010（新北1屆） 2010新北.xlsx            Sheet1（村里級，每 5 欄一組候選人）
    2014（新北2屆） 2014新北_得票数.xlsx     工作表「各里彙總」（村里級寬表）
    2018（新北3屆） 2018新北.xlsx            Sheet1（村里級，每 5 欄一組候選人）
    2022（新北4屆） 新北县市首长_2022.xlsx   工作表「新北市」（村里級寬表）

統計口徑（依使用者指示，全年度統一）：
    有效票數 = 該鄉鎮市區所有候選人得票數加總
    得票率(%) = 該候選人得票數 ÷ 有效票數 × 100
    村里級資料先彙總至鄉鎮市區後，再以「先加總、後相除」計算，避免小里等權扭曲。

輸出：
    data/新北市歷屆首長選舉_各鄉鎮市區得票數得票率_1993-2022.xlsx
        每個年度一個工作表，欄位：
            鄉鎮市區 | <候選人>得票數 | <候選人>得票率 | … | 有效票數 | 領先者

執行：
    py Compute_TownVotes_1993_2022.py
"""
import os
import re
import unicodedata

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data")
OUT_XLSX = os.path.join(DATA, "新北市歷屆首長選舉_各鄉鎮市區得票數得票率_1993-2022.xlsx")

RATE_ROUND = 2
EMPTY = ""          # 無資料時的留白

# 候選人姓名勘誤（來源檔排印用字 → 正式姓名）
CAND_RENAME = {
    "王建火宣": "王建煊",     # 2001：王建煊（檔內拆字）
    "周錫偉": "周錫瑋",       # 2005（本輪略過）
    "羅文佳": "羅文嘉",       # 2005（本輪略過）
}


# ===================== 文字／數值工具 =====================
def norm(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip()
    return s.replace("[", "").replace("]", "")


def to_num(v):
    if v is None:
        return np.nan
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return np.nan if (isinstance(v, float) and np.isnan(v)) else float(v)
    s = str(v).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "－", "—", "nan", "None"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


LOC_RE = re.compile(r"^(.*?[縣市])(.*?[鄉鎮市區])(.+)$")


def parse_loc(v):
    """「臺北縣板橋市留侯里」→ (臺北縣, 板橋市, 留侯里)。"""
    m = LOC_RE.match(norm(v))
    return (m.group(1), m.group(2), m.group(3)) if m else (None, None, None)


def strip_county(town):
    """「臺北縣板橋市」→「板橋市」；「新北市板橋區」→「板橋區」。"""
    return re.sub(r"^(臺北縣|台北縣|新北市|新北縣)", "", norm(town)).strip()


def is_total(name):
    return ("總計" in name) or ("合計" in name) or ("总计" in name)


# ===================== 各型來源檔讀取 → town_votes =====================
def read_town_sheet(path, sheet):
    """已是鄉鎮市區級的彙總表：首欄為鄉鎮市區，其後為「<候選人>（NN）_得票數／_得票率」成對欄位。
    回傳 (town_votes, cand_order)。"""
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    towncol = df.columns[0]

    cands = []          # [(name, count_col, no)]
    for c in df.columns[1:]:
        m = re.match(r"^(.*?)（(\d+)）_得票數$", c)
        if m:
            cands.append((norm(m.group(1)), c, int(m.group(2))))
    cands.sort(key=lambda t: t[2])
    cand_order = [CAND_RENAME.get(n, n) for n, _, _ in cands]

    town_votes = {}
    for _, r in df.iterrows():
        raw = norm(r[towncol])
        if not raw or is_total(raw):
            continue
        town = strip_county(raw)
        if not town:
            continue
        d = {}
        for (n, col, _no), disp in zip(cands, cand_order):
            d[disp] = to_num(r[col])
        town_votes[town] = d
    return town_votes, cand_order


def read_blocks5(path, sheet):
    """村里級「每 5 欄一組候選人」版面：(里全名, 候選人, 號次, 得票數, 得票率)。
    回傳 (town_votes, cand_order)。"""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    ncol = raw.shape[1]
    if ncol < 5 or ncol % 5 != 0:
        raise ValueError(f"{os.path.basename(path)}[{sheet}] 欄數 {ncol} 非 5 的倍數")
    nb = ncol // 5

    records = []        # (town, cand, no, votes)
    meta = {}           # cand -> no
    for k in range(nb):
        sub = raw.iloc[:, k * 5:k * 5 + 5].copy()
        sub.columns = ["loc", "cand", "no", "votes", "rate"]
        cname = sub["cand"].dropna()
        if not len(cname):
            continue
        disp = norm(cname.iloc[0])
        no = to_num(sub["no"].dropna().iloc[0]) if sub["no"].notna().any() else np.nan
        meta[disp] = no
        for _, r in sub.iterrows():
            town = parse_loc(r["loc"])[1]
            if not town:
                continue
            v = to_num(r["votes"])
            if np.isnan(v):
                continue
            records.append((strip_county(town), disp, v))

    town_votes = {}
    for town, disp, v in records:
        town_votes.setdefault(town, {})
        town_votes[town][disp] = town_votes[town].get(disp, 0.0) + v

    cand_order = sorted(meta, key=lambda c: (np.isnan(meta[c]), meta[c]))
    cand_order = [CAND_RENAME.get(c, c) for c in cand_order]
    # 同步 town_votes 內的鍵為顯示名
    renamed = {}
    for town, d in town_votes.items():
        renamed[town] = {CAND_RENAME.get(k, k): v for k, v in d.items()}
    return renamed, cand_order


def read_wide(path, sheet, cand_specs):
    """村里級寬表：欄位含「鄉(鎮、市、區)別」與各候選人得票數欄。
    cand_specs: [(顯示名, 欄名關鍵字)]，順序即輸出順序。"""
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    towncol = next(c for c in df.columns if "鄉" in c)

    col_map = {}
    for disp, key in cand_specs:
        col = next((c for c in df.columns
                    if key in c and c != towncol and "率" not in c), None)
        if col is None:
            raise ValueError(f"{os.path.basename(path)}[{sheet}] 找不到候選人 {disp} 的得票數欄")
        col_map[disp] = col
    cand_order = [disp for disp, _ in cand_specs]

    town_votes = {}
    for _, r in df.iterrows():
        raw = norm(r[towncol])
        if not raw or is_total(raw):
            continue
        town = strip_county(raw)
        d = town_votes.setdefault(town, {})
        for disp, col in col_map.items():
            v = to_num(r[col])
            if not np.isnan(v):
                d[disp] = d.get(disp, 0.0) + v
    return town_votes, cand_order


def read_long(path, encoding="utf-8-sig"):
    """鄉鎮市級長表 CSV：(地區, 姓名, 號次, 得票數, 得票率)。
    回傳 (town_votes, cand_order)。"""
    df = pd.read_csv(path, encoding=encoding, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    town_votes, meta = {}, {}          # cand -> 號次
    for _, r in df.iterrows():
        town = strip_county(norm(r["地區"]))
        cand = CAND_RENAME.get(norm(r["姓名"]), norm(r["姓名"]))
        if not town or not cand:
            continue
        v = to_num(r["得票數"])
        if np.isnan(v):
            continue
        if cand not in meta:
            meta[cand] = to_num(r["號次"])
        d = town_votes.setdefault(town, {})
        d[cand] = d.get(cand, 0.0) + v

    cand_order = sorted(meta, key=lambda c: (np.isnan(meta[c]), meta[c]))
    return town_votes, cand_order


# ===================== 年度設定 =====================
def build_configs():
    f = lambda n: os.path.join(DATA, n)
    return [
        {"year": 1993, "label": "1993（第12屆臺北縣長）",
         "kind": "townsheet", "src": f("1993台北县长.xlsx"), "sheet": "鄉鎮市區彙總"},
        {"year": 1997, "label": "1997（第13屆臺北縣長）",
         "kind": "townsheet", "src": f("1997台北縣長.xlsx"), "sheet": "鄉鎮市區彙總"},
        {"year": 2001, "label": "2001（第14屆臺北縣長）",
         "kind": "blocks5", "src": f("台北县2001.xlsx"), "sheet": "Sheet1"},
        {"year": 2005, "label": "2005（第15屆臺北縣長）",
         "kind": "long", "src": f("2005台北县_各乡镇市區得票數.csv")},
        {"year": 2010, "label": "2010（第1屆新北市長）",
         "kind": "blocks5", "src": f("2010新北.xlsx"), "sheet": "Sheet1"},
        {"year": 2014, "label": "2014（第2屆新北市長）",
         "kind": "wide", "src": f("2014新北_得票数.xlsx"), "sheet": "各里彙總",
         "cand_specs": [("游錫堃", "游錫堃"), ("朱立倫", "朱立倫")]},
        {"year": 2018, "label": "2018（第3屆新北市長）",
         "kind": "blocks5", "src": f("2018新北.xlsx"), "sheet": "Sheet1"},
        {"year": 2022, "label": "2022（第4屆新北市長）",
         "kind": "wide", "src": f("新北县市首长_2022.xlsx"), "sheet": "新北市",
         "cand_specs": [("林佳龍", "林佳龍"), ("侯友宜", "侯友宜")]},
    ]


# ===================== 彙總成單一工作表 =====================
def build_sheet(town_votes, cand_order):
    rows = []
    for town, d in town_votes.items():
        votes = [d.get(c, np.nan) for c in cand_order]
        valid = float(np.nansum(votes))
        rec = {"鄉鎮市區": town}
        for c, v in zip(cand_order, votes):
            if np.isnan(v):
                rec[f"{c}得票數"] = EMPTY
                rec[f"{c}得票率"] = EMPTY
            else:
                rec[f"{c}得票數"] = int(round(v))
                rec[f"{c}得票率"] = round(v / valid * 100.0, RATE_ROUND) if valid > 0 else EMPTY
        rec["有效票數"] = int(round(valid))
        lead = max(range(len(cand_order)),
                   key=lambda i: -1.0 if np.isnan(votes[i]) else votes[i])
        rec["領先者"] = cand_order[lead]
        rows.append(rec)
    df = pd.DataFrame(rows)
    df = df.sort_values("有效票數", ascending=False).reset_index(drop=True)
    # 欄位順序：鄉鎮市區 | 各候選人得票數/率 | 有效票數 | 領先者
    cols = ["鄉鎮市區"]
    for c in cand_order:
        cols += [f"{c}得票數", f"{c}得票率"]
    cols += ["有效票數", "領先者"]
    return df[cols]


# ===================== 主流程 =====================
def main():
    print("=" * 68)
    print("  新北市（原臺北縣）歷屆首長選舉 各鄉鎮市區得票數／得票率  1993–2022")
    print("=" * 68)

    sheets = {}
    for cfg in build_configs():
        if not os.path.exists(cfg["src"]):
            print(f"  [略過] 找不到 {cfg['src']}")
            continue
        if cfg["kind"] == "townsheet":
            tv, order = read_town_sheet(cfg["src"], cfg["sheet"])
        elif cfg["kind"] == "blocks5":
            tv, order = read_blocks5(cfg["src"], cfg["sheet"])
        elif cfg["kind"] == "wide":
            tv, order = read_wide(cfg["src"], cfg["sheet"], cfg["cand_specs"])
        elif cfg["kind"] == "long":
            tv, order = read_long(cfg["src"])
        else:
            raise ValueError(cfg["kind"])

        df = build_sheet(tv, order)
        sheets[str(cfg["year"])] = df
        print(f"  {cfg['label']}")
        print(f"      分布 {len(df)} 個鄉鎮市區｜候選人 {'、'.join(order)}"
              f"｜有效票合計 {int(df['有效票數'].sum()):,}")

    if not sheets:
        raise SystemExit("沒有任何年度資料")

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        for y, df in sheets.items():
            df.to_excel(xw, sheet_name=y, index=False)

    print("-" * 68)
    print(f"  輸出：{OUT_XLSX}")
    print(f"  工作表：{'、'.join(sheets.keys())}")


if __name__ == "__main__":
    main()
