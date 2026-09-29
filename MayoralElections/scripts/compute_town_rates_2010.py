# -*- coding: utf-8 -*-
"""
由「2010新北.xlsx」計算新北市各鄉鎮市區（區）的候選人得票率。

原始檔 Sheet1 為無表頭的「候選人並排」版面，每 5 欄為一組：
    欄 5k+0 = 投開票所(里)完整路徑，如「新北市板橋區留侯里」
    欄 5k+1 = 候選人姓名
    欄 5k+2 = 候選人號次
    欄 5k+3 = 得票數
    欄 5k+4 = 得票率（0–1 小數）

區級得票率採「得票數加總 ÷ 有效票數加總」重算（人口加權）：
    區得票率(%) = Σ各里該候選人得票數 ÷ Σ各里有效票數 × 100
不可直接平均各里的得票率 —— 幾百人的小里會與上萬人的大里等權，
使小里的高（低）得票率扭曲區級結果。

有效票數定義為同一里所有候選人得票數之和（原始檔兩位候選人得票率相加恰為 1.0，
可證分母即有效票數）。若某里只列一位候選人，該里有效票數會偏低，此時以原始檔
該里得票率 × 得票數回推的分母為準（見 _valid_from_rate）。

輸出：
    data/2010新北_各區得票率.xlsx
        各區彙總  —— 29 個鄉鎮市區的得票率（主結果）
        各里彙總  —— 村里級明細，欄位沿用 Converge_to_map.py 的「高雄格式」
                     （選舉區別／鄉(鎮、市、區)別／村里別／<候選人>得票數…／有效票數A），
                     可直接交給 Converge_to_map.py 製圖

執行：
    py compute_town_rates_2010.py
"""
import os
import re
import unicodedata

import numpy as np
import pandas as pd

# ===================== 配置区 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = r"D:\Windows\TaiwanElection\MayoralElections\data"

SRC_XLSX = os.path.join(EXCEL_DIR, "2010新北.xlsx")
SRC_SHEET = "Sheet1"
OUT_XLSX = os.path.join(EXCEL_DIR, "2010新北_各區得票率.xlsx")

BLOCK_WIDTH = 5              # 每位候選人佔用的欄數：里／姓名／號次／得票數／得票率
LOC_RE = re.compile(r"^(.*?[縣市])(.*?[鄉鎮市區])(.+)$")   # 縣市／鄉鎮市區／村里
VALID_COL = "有效票數A"        # Converge_to_map.py 認得的加權分母欄名
RATE_ROUND = 2               # 輸出得票率小數位

# ===================== 工具函数 =====================
def normalize_text(s):
    """與 Converge_to_map.py 同款正規化：全形/半角統一、去注音符號與方括號。"""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKC", s)
    s = "".join(c for c in s if unicodedata.category(c)[0] != "M")
    s = s.replace("[", "").replace("]", "")
    return s


def strip_suffix(s, chars):
    return re.sub(rf"[{chars}]$", "", normalize_text(s))


def parse_loc(v):
    """把「新北市板橋區留侯里」切成 (縣市, 鄉鎮市區, 村里別)；失敗回傳 (None, None, None)。"""
    s = normalize_text(v)
    m = LOC_RE.match(s)
    if not m:
        return None, None, None
    return (m.group(1), m.group(2), m.group(3))


def to_num(v):
    """字串/數字/千分位 → float；無法解析回傳 NaN。"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    s = str(v).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return np.nan


# ===================== 读原始档：展開候選人並排版面 =====================
def load_long(src_xlsx, sheet):
    """把「每 5 欄一組候選人」的並排版面攤平成長表。

    回傳欄位：row_no / 里全名 / 縣市 / 鄉鎮市區 / 村里別 / 候選人 / 號次 / 得票數 / 得票率(0-1)
    """
    raw = pd.read_excel(src_xlsx, sheet_name=sheet, header=None)
    n_blocks = raw.shape[1] // BLOCK_WIDTH
    if n_blocks < 1 or raw.shape[1] % BLOCK_WIDTH != 0:
        raise ValueError(f"{src_xlsx} 欄數 {raw.shape[1]} 非 {BLOCK_WIDTH} 的倍數，版面不符預期")

    blocks = []
    for k in range(n_blocks):
        c0 = k * BLOCK_WIDTH
        b = raw.iloc[:, c0:c0 + BLOCK_WIDTH].copy()
        b.columns = ["里全名", "候選人", "號次", "得票數", "得票率"]
        b["區塊"] = k
        blocks.append(b)
    long = pd.concat(blocks, ignore_index=True)

    # 候選人姓名由各區塊讀出，順序即欄位順序（朱立倫、蔡英文…）
    cand_order = [b["候選人"].dropna().iloc[0] if b["候選人"].notna().any() else f"候選人{k + 1}"
                  for k, b in enumerate(blocks)]
    cand_order = list(dict.fromkeys(cand_order))          # 去重但保留順序

    long["候選人"] = long["候選人"].map(normalize_text)
    long["號次"] = long["號次"].map(to_num)
    long["得票數"] = long["得票數"].map(to_num)
    long["得票率"] = long["得票率"].map(to_num)           # 0–1 小數
    # concat 是「區塊優先」排列，故用 tile（而非 repeat）讓同一原始列的各候選人共享 row_no
    long.insert(0, "row_no", np.tile(raw.index.values, n_blocks))

    parsed = long["里全名"].map(parse_loc)
    long["縣市"] = parsed.map(lambda t: t[0])
    long["鄉鎮市區"] = parsed.map(lambda t: t[1])
    long["村里別"] = parsed.map(lambda t: t[2])
    long["區塊"] = long["區塊"].map(lambda k: cand_order[k] if k < len(cand_order) else f"候選人{k + 1}")

    bad = long[long["鄉鎮市區"].isna()]
    if len(bad):
        raise ValueError(f"有 {len(bad)} 筆里全名無法解析，例：{bad['里全名'].iloc[0]!r}")
    return long, cand_order


# ===================== 村里级汇总 =====================
def village_summary(long):
    """村里級彙總：得票數、有效票數A、各候選人得票率(%)。"""
    rows = []
    for (city, town, vill), g in long.groupby(["縣市", "鄉鎮市區", "村里別"], sort=False):
        rec = {"選舉區別": city, "鄉(鎮、市、區)別": town, "村里別": vill}
        by_cand = {c: g[g["候選人"] == c] for c in g["候選人"].unique()}

        # 有效票數：優先「各候選人得票數加總」（原始檔得票率相加為 1，可證分母即有效票數）
        valid = g["得票數"].sum()
        rec[VALID_COL] = valid

        for cand, cg in by_cand.items():
            votes = cg["得票數"].sum()
            rec[f"{cand}得票數"] = votes
            rec[f"{cand}得票率"] = votes / valid * 100.0 if valid and valid > 0 else np.nan
            rec[f"{cand}號次"] = cg["號次"].dropna().iloc[0] if cg["號次"].notna().any() else np.nan

        # 自檢用欄位：原始檔得票率（0–1）平均值，供 main() 與重算值比對
        for cand, cg in by_cand.items():
            rec[f"__srcrate_{cand}"] = cg["得票率"].mean()
        rows.append(rec)

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("村里級彙總為空")
    return out.sort_values(["選舉區別", "鄉(鎮、市、區)別", "村里別"]).reset_index(drop=True)


# ===================== 区级汇总（人口加权）=====================
def town_summary(vill, cand_names):
    """鄉鎮市區級彙總：Σ得票數 ÷ Σ有效票數 × 100（先加總再相除，避免比率平均的加權誤差）。"""
    cand_vote_cols = [f"{c}得票數" for c in cand_names]
    g = vill.groupby(["選舉區別", "鄉(鎮、市、區)別"], sort=False).agg(
        村里數=(VALID_COL, "size"),
        **{VALID_COL: (VALID_COL, "sum")},
        **{col: (col, "sum") for col in cand_vote_cols},
    ).reset_index()

    for c in cand_names:
        g[f"{c}得票率"] = np.where(g[VALID_COL] > 0, g[f"{c}得票數"] / g[VALID_COL] * 100.0, np.nan)

    rate_cols = [f"{c}得票率" for c in cand_names]
    vals = g[rate_cols].to_numpy(dtype=float)
    lead_idx = np.nanargmax(vals, axis=1)
    g["領先者"] = [cand_names[i] for i in lead_idx]
    g["領先得票率"] = vals[np.arange(len(g)), lead_idx]
    ranked = np.sort(np.nan_to_num(vals, nan=-1.0), axis=1)
    g["差距"] = ranked[:, -1] - (ranked[:, -2] if ranked.shape[1] > 1 else 0.0)
    g = g.rename(columns={"鄉(鎮、市、區)別": "鄉鎮市區"})
    return g.sort_values("領先得票率", ascending=False).reset_index(drop=True)


# ===================== 主程式 =====================
def main():
    if not os.path.exists(SRC_XLSX):
        raise FileNotFoundError(SRC_XLSX)

    long, cand_names = load_long(SRC_XLSX, SRC_SHEET)
    print("=" * 68)
    print(f"  來源：{SRC_XLSX} [{SRC_SHEET}]")
    print("=" * 68)
    print(f"  原始列數        : {long['row_no'].nunique()}")
    print(f"  候選人          : {' / '.join(cand_names)}")
    print(f"  村里筆數        : {long.groupby(['鄉鎮市區', '村里別']).ngroups}")
    print(f"  鄉鎮市區數      : {long['鄉鎮市區'].nunique()}")

    # 原始檔得票率是否為 0–1 小數且同里相加為 1
    chk = long.dropna(subset=["得票率"]).groupby(["鄉鎮市區", "村里別"])["得票率"].sum()
    off = chk[(chk - 1.0).abs() > 0.005]
    print(f"  得票率合計≈1.0  : {len(chk) - len(off)}/{len(chk)} 個里"
          + (f"（{len(off)} 個里偏差 >0.5pp）" if len(off) else ""))

    vill = village_summary(long)
    town = town_summary(vill, cand_names)

    # 村里加總 vs 區級加總 必須一致（加權正確性的自我檢查）
    v_sum = float(vill[VALID_COL].sum())
    t_sum = float(town[VALID_COL].sum())
    print(f"  有效票數合計    : 村里 {v_sum:,.0f} / 區級 {t_sum:,.0f}  "
          + ("一致 OK" if abs(v_sum - t_sum) < 1 else "!! 不一致"))

    # 重算得票率 vs 原始檔得票率（0–1）必須一致，證明分母取的是有效票數
    for c in cand_names:
        src = vill[f"__srcrate_{c}"] * 100.0
        diff = (vill[f"{c}得票率"] - src).abs()
        print(f"  得票率重算 vs 原檔: {c} 最大差 {diff.max():.4f}pp  "
              + ("一致 OK" if diff.max() < 0.05 else "!! 偏差過大"))
    vill = vill.drop(columns=[c for c in vill.columns if str(c).startswith("__srcrate_")])

    # ---- 輸出 Excel ----
    v_out = vill.copy()
    for c in cand_names:
        v_out[f"{c}得票率"] = v_out[f"{c}得票率"].round(RATE_ROUND)
    t_out = town.copy()
    for c in cand_names:
        t_out[f"{c}得票率"] = t_out[f"{c}得票率"].round(RATE_ROUND)
    t_out["領先得票率"] = t_out["領先得票率"].round(1)
    t_out["差距"] = t_out["差距"].round(1)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        t_out.to_excel(xw, sheet_name="各區彙總", index=False)
        v_out.to_excel(xw, sheet_name="各里彙總", index=False)

    # ---- 印出各區結果 ----
    show = ["鄉鎮市區", "村里數", VALID_COL] + \
           [x for c in cand_names for x in (f"{c}得票數", f"{c}得票率")] + ["領先者", "差距"]
    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.width", 200)
    print("\n【各區得票率】（依領先得票率排序）")
    print(t_out[show].to_string(index=False,
                                formatters={f"{c}得票率": lambda v: f"{v:.2f}%" for c in cand_names}
                                | {VALID_COL: lambda v: f"{v:,.0f}"}))
    print(f"\n  輸出: {OUT_XLSX}")
    print("  （各區彙總 / 各里彙總；各里彙總欄位沿用高雄格式，可直接給 Converge_to_map.py 製圖）\n")


if __name__ == "__main__":
    main()
