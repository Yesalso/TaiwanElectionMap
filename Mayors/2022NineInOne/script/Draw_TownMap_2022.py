# -*- coding: utf-8 -*-
"""
2022 年地方公職人員選舉（九合一）—— 縣市長選舉
全台「鄉鎮市區」級別得票率地圖（單張全圖，不畫圖例、不畫標題）

資料來源：..\\data\\2022{直轄市|縣市}長選舉_{縣市}.xlsx
    工作表「鄉鎮市區級別」：縣市 | 鄉鎮市區 | <候選人（NN）>_得票數 | ... | 當選人
    各鄉鎮得票率＝該鄉鎮候選人得票數 ÷ 該鄉鎮候選人得票數合計（由得票數重新加總計算）

填色邏輯（沿用 2012LegislatorParty.py）：
    ① 以鄉鎮市區內「得票率最高」的候選人為勝選者
    ② 勝選者所屬政黨 → 決定色階組別（color.txt 由上而下：
       0 無黨籍(灰) / 1 中國國民黨(藍) / 2 民主進步黨(綠) / 3 新黨(黃)
       4 宋楚瑜(橘) / 5 台灣民眾黨(青綠)）
    ③ 勝選者本人的得票率 → 決定該組色階的深淺（35% 起，5% 一階）
    ④ 無資料的鄉鎮市區 → 填畫布底色（#323232），與背景融為一體

底圖：以全台「唯一色」底圖 Colorful.png 直接重著色，無需 SHP
    - Colorful.png 中每個鄉鎮市區填以單一辨識色（畫布底色 #323232）
    - Name_Color_Correspondence.xlsx：顏色(HEX) ↔ 鄉鎮市區 對照表（現行 368 個鄉鎮市區）

輸出：
    Mayors/2022NineInOne/map/2022縣市長選舉_鄉鎮市區得票率.png

執行：
    py Draw_TownMap_2022.py
"""
import ast
import glob
import os
import re
import warnings

import numpy as np
import pandas as pd
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")

# ===================== 路徑 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)                        # ...\2022NineInOne
DATA_DIR = os.path.join(ROOT_DIR, "data")
OUT_PNG = os.path.join(ROOT_DIR, "map", "2022縣市長選舉_鄉鎮市區得票率.png")

# 全台鄉鎮市區唯一色底圖 + 顏色對照表（沿用 County 既有資產）
BASE_PNG = r"D:\Windows\TaiwanElection\County\Colorful.png"
CORR_XLSX = r"D:\Windows\TaiwanElection\County\Name_Color_Correspondence.xlsx"
# 政黨色階（沿用總統線配色，6 組）
COLOR_TXT = r"D:\Windows\TaiwanElection\Precident\color.txt"

CANVAS_COLOR = "#323232"    # 畫布底色；亦為無資料鄉鎮市區的填色

# ===================== 22 縣市 → 資料檔 =====================
COUNTY_FILES = {
    "臺北市": "2022直轄市長選舉_台北市.xlsx",
    "新北市": "2022直轄市長選舉_新北市.xlsx",
    "桃園市": "2022直轄市長選舉_桃園市.xlsx",
    "臺中市": "2022直轄市長選舉_臺中市.xlsx",
    "臺南市": "2022直轄市長選舉_臺南市.xlsx",
    "高雄市": "2022直轄市長選舉_高雄市.xlsx",
    "基隆市": "2022縣市長選舉_基隆市.xlsx",
    "新竹市": "2022縣市長選舉_新竹市.xlsx",
    "嘉義市": "2022縣市長選舉_嘉義市.xlsx",
    "新竹縣": "2022縣市長選舉_新竹縣.xlsx",
    "苗栗縣": "2022縣市長選舉_苗栗縣.xlsx",
    "彰化縣": "2022縣市長選舉_彰化縣.xlsx",
    "南投縣": "2022縣市長選舉_南投縣.xlsx",
    "雲林縣": "2022縣市長選舉_雲林縣.xlsx",
    "嘉義縣": "2022縣市長選舉_嘉義縣.xlsx",
    "屏東縣": "2022縣市長選舉_屏東縣.xlsx",
    "宜蘭縣": "2022縣市長選舉_宜蘭縣.xlsx",
    "花蓮縣": "2022縣市長選舉_花蓮縣.xlsx",
    "臺東縣": "2022縣市長選舉_臺東縣.xlsx",
    "澎湖縣": "2022縣市長選舉_澎湖縣.xlsx",
    "金門縣": "2022縣市長選舉_金門縣.xlsx",
    "連江縣": "2022縣市長選舉_連江縣.xlsx",
}

# ===================== 候選人 → 政黨色階組別 =====================
# 組別索引＝ color.txt 由上而下：0 無黨籍(灰) / 1 國民黨(藍) / 2 民進黨(綠)
#   3 新黨(黃) / 4 宋楚瑜(橘) / 5 民眾黨(青綠)
CAND_PARTY = {
    "侯友宜": 1, "劉建國": 2, "劉復嵐": 0, "劉櫂豪": 2,
    "吳炳輝": 0, "吳盛聖": 0, "周春米": 2, "周江杰": 2,
    "唐新民": 0, "宋國鼎": 0, "張善政": 1, "張家豪": 0,
    "張麗善": 1, "徐定禎": 2, "徐榛蔚": 1, "施奉先": 0,
    "曹爾元": 1, "曾國民": 0, "曾尹儷": 0, "朱振東": 0,
    "朱紀瑋": 0, "李俊俋": 2, "李問": 2, "李應文": 0,
    "李驥羣": 0, "林佳瑜": 0, "林佳龍": 2, "林姿妙": 1,
    "林志錦": 0, "林義豐": 0, "林耕仁": 1, "柯志恩": 1,
    "楊文科": 1, "楊鎮浯": 1, "江聰淵": 2, "沈慧虹": 2,
    "洪志恒": 0, "王忠銘": 1, "王惠美": 1, "王文娟": 0,
    "王永慶": 0, "王育敏": 1, "盧秀燕": 1, "童文薰": 0,
    "翁章梁": 2, "范振揆": 0, "葉竹林": 0, "蔡其昌": 2,
    "蔡培慧": 2, "蔡適應": 2, "蔣萬安": 1, "蕭仁正": 0,
    "蘇清泉": 1, "蘇煥智": 0, "許忠信": 0, "許淑華": 1,
    "許鋐哲": 0, "詹智鈞": 0, "謝國樑": 1, "謝福弘": 1,
    "謝立康": 0, "謝龍介": 1, "谷辣斯．尤達卡 Kolas Yotaka": 2,
    "賴峰偉": 1, "賴香伶": 5, "鄭凱升": 0, "鄭匡宇": 0,
    "鄭宇翔": 0, "鄭寶清": 0, "鄭運鵬": 2, "鍾東錦": 0,
    "陳光復": 2, "陳其邁": 2, "陳時中": 2, "陳泰山": 0,
    "陳琬惠": 5, "陳福海": 0, "陳秋境": 0, "陳美妃": 0,
    "陳薇仲": 0, "陳長宏": 0, "饒慶鈴": 1, "高虹安": 5,
    "黃偉哲": 2, "黃宏成台灣阿成世界偉人財神總統": 0, "黃希賢": 0,
    "黃敏惠": 1, "黃源甫": 0, "黃珊珊": 0, "黃秀芳": 2,
    "黃秀龍": 0, "黃聖峰": 0, "黄師鵬": 0, "龔偉綸": 0,
}
PARTY_NAMES = ["無黨籍", "中國國民黨", "民主進步黨", "新黨", "宋楚瑜", "台灣民眾黨"]

# ===================== 異體字／用字差異正規化 =====================
# 方向：把資料側與對照表側統一為同一個字，兩邊即可精確比對
VARIANT_CHAR_MAP = str.maketrans({
    "臺": "台", "裡": "里", "侖": "崙", "穀": "谷", "樸": "朴", "恒": "恆",
    "莊": "庄", "鬥": "斗",   # 雲林鬥六/斗六、鬥南/斗南
    "褔": "福",               # 彰化福興鄉（史料常寫作「褔」）
})
VARIANT_WORD_MAP = {
    "後里": "后里",   # 臺中市后里區 ↔ 對照表後裡區
    "滿洲": "滿州",   # 屏東縣滿州鄉 ↔ 對照表滿洲鄉
}


# ===================== 通用工具 =====================
def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def norm_name(s):
    """縣市／鄉鎮名 → 正規化鍵（去頭尾空白、統一字形）。"""
    return str(s).strip().translate(VARIANT_CHAR_MAP)


def norm_town(s):
    """鄉鎮市區名 → 去掉「鄉鎮市區」尾字後的正規化核心字。"""
    core = re.sub(r"[鄉鎮市區]$", "", str(s).strip())
    core = core.translate(VARIANT_CHAR_MAP)
    return VARIANT_WORD_MAP.get(core, core)


def get_color_by_value(val, stops):
    """得票率 → 色階色碼（低於第一階者取第一階；高於末階者取末階）。"""
    if val is None or (isinstance(val, float) and np.isnan(val)) or val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def load_color_stops(path):
    """讀 color.txt（Python 串列字面）。忽略整行註解，取 '=' 之後做 literal_eval。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    rhs = "\n".join(lines).split("=", 1)[1]
    return ast.literal_eval(rhs)


RATE_COLOR_STOPS = load_color_stops(COLOR_TXT)


# ===================== 讀顏色對照表 =====================
def load_correspondence():
    """回傳 towns: [{code, county, name, core, color_hex}]（368 個鄉鎮市區）。"""
    df = pd.read_excel(CORR_XLSX, header=None, dtype=str)

    # 右側縣市碼表：col12 = 縣市編碼, col13 = 縣市名
    county_code2name = {}
    for i in range(1, min(len(df), 30)):
        c, nm = df.iloc[i, 12], df.iloc[i, 13]
        if pd.isna(c) or pd.isna(nm):
            continue
        try:
            county_code2name[int(float(c))] = norm_name(nm)
        except (TypeError, ValueError):
            continue

    towns = []
    for i in range(1, len(df)):
        if pd.isna(df.iloc[i, 0]) or pd.isna(df.iloc[i, 5]):
            continue
        try:
            code = int(float(df.iloc[i, 5]))
        except (TypeError, ValueError):
            continue
        name = str(df.iloc[i, 8]).strip()
        towns.append({
            "code": code,
            "county": county_code2name.get(code, ""),
            "name": name,
            "core": norm_town(name),
            "color_hex": str(df.iloc[i, 1]).strip().upper(),
        })
    return towns


# ===================== 讀 2022 得票資料 =====================
def _cand_from_col(col):
    """「蔣萬安（06）_得票數」→ 候選人名「蔣萬安」（先去尾碼，再去號次）。"""
    c = re.sub(r"_得票[數率]$", "", str(col).strip())
    return re.sub(r"[（(]\d+[）)]$", "", c).strip()


def _to_num(v):
    if pd.isna(v):
        return 0.0
    s = str(v).strip().replace(",", "").replace("\u00a0", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_votes():
    """讀 22 個縣市 xlsx 的「鄉鎮市區級別」工作表。

    回傳 data: {(county_key, town_core): {候選人: 得票率%}}，得票率由得票數重新加總計算。
    """
    data = {}
    missing_files = []
    for county, fname in COUNTY_FILES.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            missing_files.append(fname)
            continue
        df = pd.read_excel(path, sheet_name="鄉鎮市區級別", dtype=str)
        cols = [str(c) for c in df.columns]
        vote_cols = {_cand_from_col(c): c for c in cols if c.endswith("得票數")}
        cands = list(vote_cols.keys())

        for _, row in df.iterrows():
            county_key = norm_name(row.get("縣市", county))
            town = norm_town(row.get("鄉鎮市區"))
            if not town:
                continue
            votes = {n: _to_num(row[vote_cols[n]]) for n in cands}
            total = sum(votes.values())
            if total <= 0:
                continue
            data[(county_key, town)] = {n: v / total * 100.0 for n, v in votes.items()}

    if missing_files:
        print("  ※ 缺少資料檔：" + "、".join(missing_files))
    return data


# ===================== 主程式 =====================
def main():
    print("=" * 62)
    print("  2022 縣市長選舉 —— 全台鄉鎮市區得票率地圖（無圖例）")
    print("=" * 62)

    towns = load_correspondence()
    print(f"  顏色對照表鄉鎮市區 : {len(towns)} 個")

    data = load_votes()
    print(f"  選舉資料鄉鎮市區   : {len(data)} 個")

    # ---- 指派每個鄉鎮市區的填色 ----
    no_data, unknown_cand, ties = [], set(), []
    win_cnt = {i: 0 for i in range(len(RATE_COLOR_STOPS))}
    win_rates = []

    for t in towns:
        rec = data.get((t["county"], t["core"]))
        if not rec:
            t["fill_hex"] = CANVAS_COLOR
            no_data.append(f"{t['county']}{t['name']}")
            continue

        ranked = sorted(rec.items(), key=lambda kv: kv[1], reverse=True)
        name, rate = ranked[0]
        if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) < 1e-9:
            ties.append((t["county"], t["name"]))

        gi = CAND_PARTY.get(name)
        if gi is None:
            unknown_cand.add(name)
            gi = 0                       # 未收錄候選人一律視為無黨籍（灰）
        t["fill_hex"] = get_color_by_value(rate, RATE_COLOR_STOPS[gi])
        win_cnt[gi] += 1
        win_rates.append(rate)

    print(f"  有資料(填色)       : {len(towns) - len(no_data)}")
    print(f"  無資料(填底色)     : {len(no_data)}"
          + ("：" + "、".join(no_data[:15]) + ("…" if len(no_data) > 15 else "") if no_data else ""))
    if unknown_cand:
        print("  ※ 未收錄於 CAND_PARTY 的候選人（暫按無黨籍著色）：" + "、".join(sorted(unknown_cand)))
    if ties:
        print("  ※ 得票率完全相同（並列第一）：" + "、".join(f"{c}{n}" for c, n in ties))

    print("  各政黨領先鄉鎮市區數：")
    for gi, cnt in win_cnt.items():
        if cnt:
            print(f"      {PARTY_NAMES[gi] if gi < len(PARTY_NAMES) else gi}: {cnt}")
    if win_rates:
        print(f"  勝選得票率範圍     : {min(win_rates):.2f}% ~ {max(win_rates):.2f}%")

    # ---- 重著色底圖 ----
    img = Image.open(BASE_PNG).convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3]
    uniq, inv = np.unique(rgb.reshape(-1, 3), axis=0, return_inverse=True)
    print(f"  底圖              : {img.width}×{img.height}px，辨識色 {len(uniq)} 種")

    color2fill = {}
    for t in towns:
        if t["fill_hex"]:
            color2fill[hex2rgb(t["color_hex"])] = hex2rgb(t["fill_hex"])

    new_uniq = uniq.copy()
    hit = 0
    for i, u in enumerate(uniq):
        f = color2fill.get(tuple(int(x) for x in u))
        if f is not None:
            new_uniq[i] = f
            hit += 1
    recolored = new_uniq[inv].reshape(rgb.shape)
    print(f"  對照命中           : {hit} / {len(uniq)} 種辨識色"
          f"（對照表 {len(color2fill)} 色）")

    out_arr = arr.copy()
    out_arr[..., :3] = recolored
    rgba = Image.fromarray(out_arr)
    bg = Image.new("RGB", rgba.size, hex2rgb(CANVAS_COLOR))
    bg.paste(rgba, mask=rgba.getchannel("A"))

    # ---- 輸出（純地圖：不畫圖例、不畫標題）----
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    bg.save(OUT_PNG)
    print(f"  輸出              : {OUT_PNG}  ({bg.width}×{bg.height}px)\n")


if __name__ == "__main__":
    main()
