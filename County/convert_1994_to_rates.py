# -*- coding: utf-8 -*-
"""
將 1994 臺灣省省長選舉原始資料 1994TaiwanProvince.xlsx
轉為「標準得票率格式」（與 MayoralElections/data/1997台北縣_得票率.xlsx 相同結構）：

    工作表「各里彙總」：
        選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票率 ...

原始資料特性：
    - 每列 = 一個鄉鎮市區，4 位候選人並排（地區 | 姓名 | 號次 | 得票數 | 得票率）
    - 得票率為 0~1 小數（本腳本 ×100 轉為百分數，四捨五入至小數 2 位）
    - 地區為當時行政區（如「臺北縣板橋市」），縣市／鄉鎮名稱與現行不同
    - 臺南市當時分「中區」「西區」，現對照表已合併為「中西區」→ 兩區得票平均
    - 高雄縣三民鄉 → 現行 高雄市那瑪夏區

輸出的「選舉區別」「鄉(鎮、市、區)別」直接採用 Name_Color_Correspondence.xlsx 的
現行（正規化後）名稱，如此繪圖腳本 color_map_from_rates.py 可 100% 配對成功。

執行：
    py convert_1994_to_rates.py
"""
import os
import re

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VOTE_XLSX = os.path.join(BASE_DIR, "1994TaiwanProvince.xlsx")
CORR_XLSX = os.path.join(BASE_DIR, "Name_Color_Correspondence.xlsx")
OUT_XLSX = os.path.join(BASE_DIR, "1994臺灣省_得票率.xlsx")

OUT_SHEET = "各里彙總"

# ===================== 候選人順序（依原始檔出現順序偵測） =====================

# ===================== 正規化對照 =====================
VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",   # 苗栗南莊/南庄、雲林鬥六鬥南/斗六斗南
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中縣后里鄉 ↔ 對照表後裡區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}

# 1994 縣市 → 對照表現行縣市
OLD_COUNTY_MAP = {
    "臺北縣": "新北市", "桃園縣": "桃園市",
    "臺中縣": "台中市", "臺中市": "台中市",
    "臺南縣": "台南市", "臺南市": "台南市",
    "高雄縣": "高雄市",
    "臺東縣": "台東縣",
    "宜蘭縣": "宜蘭縣", "花蓮縣": "花蓮縣", "澎湖縣": "澎湖縣",
    "屏東縣": "屏東縣", "彰化縣": "彰化縣", "南投縣": "南投縣",
    "雲林縣": "雲林縣", "嘉義縣": "嘉義縣", "苗栗縣": "苗栗縣",
    "新竹縣": "新竹縣", "基隆市": "基隆市", "新竹市": "新竹市",
    "嘉義市": "嘉義市",
}

# 跨縣市同名須按縣市區分、且需合併的特殊對應
TOWN_MERGE = {   # 1994 臺南市 中區＋西區 → 對照表中西區
    ("台南市", "中"): "中西",
    ("台南市", "西"): "中西",
}
SPECIAL_TOWN = {   # 歷史更名對應（1994 高雄縣三民鄉 → 現那瑪夏區）
    ("高雄市", "三民"): "那瑪夏",
}


def norm_town_core(name):
    """鄉鎮市區名 → 正規化核心字（去後綴 + 異體字正規化）。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(name).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    core = VARIANT_WORD_MAP.get(core, core)
    return core


def load_correspondence():
    """讀取對照表：縣市碼表 + (縣市, core) → 現行名稱。"""
    df = pd.read_excel(CORR_XLSX, header=None)
    county_code2name = {}
    for i in range(1, min(len(df), 30)):
        c, nm = df.iloc[i, 11], df.iloc[i, 12]
        if pd.isna(c) or pd.isna(nm):
            continue
        try:
            code = int(float(c))
        except (TypeError, ValueError):
            continue
        county_code2name[code] = str(nm).strip().translate(VARIANT_CHAR_MAP)

    corr_idx = {}
    for i in range(1, len(df)):
        col5 = df.iloc[i, 5]
        if pd.isna(df.iloc[i, 0]) or pd.isna(col5):
            continue
        county = county_code2name.get(int(col5), "")
        name = str(df.iloc[i, 7]).strip()
        base = re.sub(r"[鄉鎮市區]$", "", name)
        base = base.translate(VARIANT_CHAR_MAP)
        base = VARIANT_WORD_MAP.get(base, base)
        norm_name = base + name[-1] if name[-1] in "鄉鎮市區" else base
        key = (county, norm_town_core(norm_name))
        corr_idx[key] = norm_name
    return county_code2name, corr_idx


def parse_1994_votes():
    """1994 xlsx 為 4 候選人並排（每組: 地區,姓名,號次,得票數,得票率）。

    回傳 (data, cand_names, unmatched):
      data: {(target_county, town_core): {cand: [rate...]}}
      得票率已 ×100（%）；同 key 多列 → 保留清單稍後平均。
    """
    df = pd.read_excel(VOTE_XLSX, header=None)
    cand_names = []
    data = {}
    unmatched = []

    for i in range(1, len(df)):
        region = df.iloc[i, 0]
        if pd.isna(region):
            continue
        region = str(region).strip()
        m = re.match(r"^(.*?[縣市])(.*)$", region)
        if not m:
            unmatched.append(region)
            continue
        old_county, town = m.group(1), m.group(2)
        county = OLD_COUNTY_MAP.get(old_county)
        if county is None:
            unmatched.append(region)
            continue
        core = norm_town_core(town)
        merge = TOWN_MERGE.get((county, core))
        if merge:
            core = merge
        core = SPECIAL_TOWN.get((county, core), core)
        key = (county, core)

        rates = {}
        for b in range(4):                       # 4 個候選人區塊
            nm = df.iloc[i, 5 * b + 1]
            rate = df.iloc[i, 5 * b + 4]
            if pd.isna(nm) or pd.isna(rate):
                continue
            name = str(nm).strip()
            try:
                v = float(rate) * 100.0          # 小數 → %
            except (TypeError, ValueError):
                v = float("nan")
            if name not in cand_names:
                cand_names.append(name)
            rates.setdefault(name, []).append(v)
        rec = data.setdefault(key, {})
        for name, vals in rates.items():
            rec.setdefault(name, []).extend(vals)
        if not rates:
            unmatched.append(region)

    avg_data = {}
    for key, rec in data.items():
        avg_data[key] = {n: float(np.mean(v)) for n, v in rec.items()}
    return avg_data, cand_names, unmatched


def main():
    print("=" * 62)
    print("  1994 臺灣省省長選舉 → 標準得票率格式")
    print("=" * 62)

    county_code2name, corr_idx = load_correspondence()
    print(f"  對照表鄉鎮市區     : {len(corr_idx)} 個（{len(county_code2name)} 縣市）")

    data, cand_names, unmatched = parse_1994_votes()
    print(f"  1994 選舉資料       : {len(data)} 個鄉鎮市區 key")
    print(f"  候選人             : {cand_names}")

    if unmatched:
        print("  ※ 無法解析的地區：")
        for u in unmatched:
            print(f"      {u}")

    # 以對照表順序輸出（確保完整涵蓋且順序一致）
    rows = []
    missing = 0
    for (county, core), corr_name in corr_idx.items():
        rec = data.get((county, core))
        if rec is None:
            missing += 1
            continue
        rate_vals = [round(rec.get(n, 0.0), 2) for n in cand_names]
        rows.append([county, corr_name, ""] + rate_vals)

    # 反向檢查：資料中有、但對照表沒有的 key（理論上為空）
    orphan_keys = set(data.keys()) - set(corr_idx.keys())
    if orphan_keys:
        print("  ※ 資料有但對照表未配對的 key：")
        for k in sorted(orphan_keys):
            print(f"      {k}")

    out_df = pd.DataFrame(
        rows,
        columns=["選舉區別", "鄉(鎮、市、區)別", "村里別"]
                + [f"{n}得票率" for n in cand_names],
    )
    os.makedirs(BASE_DIR, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        out_df.to_excel(writer, sheet_name=OUT_SHEET, index=False)

    print(f"  輸出: {OUT_XLSX}")
    print(f"      工作表「{OUT_SHEET}」，{len(rows)} 個鄉鎮市區")
    if missing:
        print(f"  ⚠ 對照表有 {missing} 個鄉鎮市區在 1994 資料中不存在（屬非臺灣省轄區，如臺北市等）。")


if __name__ == "__main__":
    main()