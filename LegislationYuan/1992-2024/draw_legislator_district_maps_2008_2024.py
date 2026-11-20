#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2008-2024 五屆立法委員選舉 — 各「選舉區」得票領先政黨得票率地圖（無圖例）
================================================================
粒度改為「區域立法委員選舉區」（每屆 73 個選舉區，每區一色塊），
以 County/Legislative/ 下的「73 色唯一色底圖」直接重著色，無需 SHP。

底圖與對照表（依屆別選用，三份對照表的選區劃分不同）：
    2008（第七屆）        : Colorful73_2007.png + Name_Color_Correspondence_73_2007.xlsx
                            25 縣市時期畫法；新竹縣單一選區、臺南市 2 + 臺南縣 3、高雄市 5 + 高雄縣 4、屏東縣 3
    2012/2016（第八、九屆）: Colorful73_2010.png + Name_Color_Correspondence_73_2010.xlsx
                            五都改制後畫法；新竹縣單一選區、臺南市 5、高雄市 9、屏東縣 3
    2020/2024（第十、十一屆）: Colorful73.png + Name_Color_Correspondence_73.xlsx
                            現行畫法；新竹縣 2、臺南市 6、高雄市 8、屏東縣 2

得票資料：本目錄 data/{year}立法委員_選舉區得票.xlsx（選舉區級別）
    政黨欄位＝「{政黨}得票率」；無黨籍為「無黨籍-{姓名}得票率」（逐人，不合併）。
    每列一個選舉區，取「得票率最高者」為該區領先者，以其政黨色階＋得票率上色。

選舉區名比對：資料端 2008 為「臺北市第1選舉區」、2012+ 為「臺北市第一選區」，
    統一正規化為 (縣市, 選區序號) 後再與對照表配對；單一選區（新竹縣、金門縣…）
    序號記 0，可同時匹配「新竹縣」與「新竹縣選舉區」。

無圖例：本版不畫圖例、不畫外框，輸出純地圖（年份見檔名）。
    若需要把標題燒進圖裡，把 DRAW_TITLE 改成 True。

色階：固定基準 35%，每 5 個百分點一檔（35/40/…/85），末檔「85%以上」；
      顏色沿用本專案 color.txt 體系（與鄉鎮市區版一致）。

輸出：map/legislative_district_{year}_party_lead_map.png

執行：
    python draw_legislator_district_maps_2008_2024.py           # 全部五屆
    python draw_legislator_district_maps_2008_2024.py 2020      # 只畫某屆
"""

import os
import re
import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTY_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "County")
LEG_DIR = os.path.join(COUNTY_DIR, "Legislative")     # 73 選舉區底圖與對照表
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "map")

CANVAS_COLOR = "#323232"     # 底色（與底圖 #323232 一致），亦用於無資料選區

# ===================== 各屆底圖與對照表 =====================
# (年份, 屆別, 選舉日期, 對照表檔名, 底圖檔名)
ELECTIONS = [
    (2008, "第七屆", "2008年1月12日",
     "Name_Color_Correspondence_73_2007.xlsx", "Colorful73_2007.png"),
    (2012, "第八屆", "2012年1月14日",
     "Name_Color_Correspondence_73_2010.xlsx", "Colorful73_2010.png"),
    (2016, "第九屆", "2016年1月16日",
     "Name_Color_Correspondence_73_2010.xlsx", "Colorful73_2010.png"),
    (2020, "第十屆", "2020年1月11日",
     "Name_Color_Correspondence_73.xlsx", "Colorful73.png"),
    (2024, "第十一屆", "2024年1月13日",
     "Name_Color_Correspondence_73.xlsx", "Colorful73.png"),
]

DRAW_TITLE = False           # True = 在地圖左上角燒錄兩行標題（預設純地圖）

# ===================== 色階（固定基準 35%，5% 間距；末檔 100） =====================
_RAW_STOPS = {
    # 無黨籍（灰色系）
    "無黨籍及未經政黨推薦": [
        (35, "#D9D9D9"), (40, "#C9C9C9"), (45, "#B6B6B6"), (50, "#A0A0A0"),
        (55, "#898989"), (60, "#727272"), (65, "#5B5B5B"), (70, "#464646"),
        (75, "#333333"), (80, "#232323"), (85, "#151515"), (100, "#151515"),
    ],
    # 中國國民黨（藍色系）
    "中國國民黨": [
        (35, "#A6E9FF"), (40, "#73D9FF"), (45, "#40C8FF"), (50, "#00C0F4"),
        (55, "#00A2E8"), (60, "#0080B8"), (65, "#006591"), (70, "#004B6B"),
        (75, "#003247"), (80, "#00283A"), (85, "#001F2E"), (100, "#010D29"),
    ],
    # 民主進步黨（綠色系）
    "民主進步黨": [
        (35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"), (50, "#A4FF90"),
        (55, "#78FF4F"), (60, "#68DE45"), (65, "#54B337"), (70, "#3C8027"),
        (75, "#2B5C1C"), (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09"),
    ],
    # 新黨（金黃色系）
    "新黨": [
        (0, "#FFF3C4"), (35, "#FFE89A"), (40, "#FFDD66"), (45, "#FFD133"),
        (50, "#FFC700"), (55, "#F2B800"), (60, "#E0A800"), (65, "#C79200"),
        (70, "#AD7A00"), (75, "#946400"), (80, "#4D4900"), (85, "#2E2A00"),
        (100, "#161400"),
    ],
    # 親民黨（橘色系）
    "親民黨": [
        (35, "#FFC2AA"), (40, "#FFA380"), (45, "#FF8456"), (50, "#FF662B"),
        (55, "#FF4701"), (60, "#D93A00"), (65, "#B33000"), (70, "#8D2500"),
        (75, "#6B1D00"), (80, "#4D1400"), (85, "#3A1000"), (100, "#170500"),
    ],
    # 無黨團結聯盟（粉色系）
    "無黨團結聯盟": [
        (35, "#FAC6D8"), (40, "#F8A8C5"), (45, "#F68AB2"), (50, "#F46C9F"),
        (55, "#F24E8C"), (60, "#F03772"), (65, "#D01058"), (70, "#B30D4B"),
        (75, "#950B3F"), (80, "#770932"), (85, "#590726"), (100, "#590726"),
    ],
    # 時代力量（芥黃色系）
    "時代力量": [
        (40, "#FFE300"), (45, "#E8B70D"), (50, "#CFA30C"), (55, "#997909"),
        (60, "#695207"), (85, "#403104"), (100, "#2A2003"),
    ],
    # 台灣民眾黨（青綠色系）
    "台灣民眾黨": [
        (35, "#00D9CA"), (40, "#00BFB2"), (45, "#00A89C"), (50, "#008080"),
        (55, "#006666"), (60, "#004C4C"), (65, "#003838"), (70, "#003030"),
        (75, "#002626"), (80, "#021F1F"), (85, "#001919"), (100, "#000808"),
    ],
    # 台灣基進（深紅色系）
    "台灣基進": [
        (35, "#FFB3B3"), (40, "#FF8A8A"), (45, "#FF5C5C"), (50, "#F03535"),
        (55, "#D42020"), (60, "#A81414"), (65, "#800D0D"), (70, "#5C0808"),
        (75, "#400505"), (80, "#2A0303"), (85, "#1A0202"), (100, "#0F0101"),
    ],
    # 台灣團結聯盟（咖啡色系）
    "台灣團結聯盟": [
        (35, "#E8CFAF"), (40, "#E0C199"), (45, "#D8AE7B"), (50, "#CB9450"),
        (55, "#A37135"), (85, "#59401E"), (100, "#59401E"),
    ],
    # 以下為備用色階（未出現於領先者時僅作 fallback 配色）
    "建國黨": [
        (35, "#73F9E2"), (40, "#40E8D2"), (45, "#00D4C0"), (50, "#00B8A6"),
        (55, "#009385"), (60, "#007468"), (65, "#00564E"), (70, "#003832"),
        (75, "#002420"), (80, "#011C1B"), (85, "#011511"), (100, "#011511"),
    ],
    "中華社會民主黨": [
        (35, "#CFA0FF"), (40, "#BE80FF"), (45, "#AB5FF9"), (50, "#9A43E8"),
        (55, "#7C34B8"), (60, "#612A91"), (65, "#481F6B"), (70, "#301547"),
        (75, "#1E0D2E"), (80, "#170E2A"), (85, "#100729"), (100, "#100729"),
    ],
    "民主聯盟": [
        (35, "#FF98B8"), (40, "#FF6E9B"), (45, "#FF4079"), (50, "#F41E5E"),
        (55, "#C8164C"), (60, "#9E113C"), (65, "#750C2D"), (70, "#520720"),
        (75, "#380517"), (80, "#2B040F"), (85, "#20030B"), (100, "#20030B"),
    ],
    "工黨": [
        (35, "#D9B98D"), (40, "#C99F66"), (45, "#B98545"), (50, "#A66F2B"),
        (55, "#87571F"), (60, "#6B4418"), (65, "#513411"), (70, "#38230B"),
        (75, "#261707"), (80, "#1D1206"), (85, "#170E04"), (100, "#170E04"),
    ],
    "其他政黨": [
        (35, "#C8E88D"), (40, "#B0D966"), (45, "#96C845"), (50, "#7BB22E"),
        (55, "#628F22"), (60, "#4C6E19"), (65, "#395112"), (70, "#28380C"),
        (75, "#1B2508"), (80, "#161D06"), (85, "#111805"), (100, "#111805"),
    ],
}

_SCHEME_ORDER = ["中國國民黨", "親民黨", "民主進步黨", "台灣團結聯盟", "新黨",
                 "無黨籍及未經政黨推薦", "建國黨", "中華社會民主黨", "民主聯盟",
                 "工黨", "無黨團結聯盟", "其他政黨",
                 "時代力量", "台灣民眾黨", "台灣基進"]
BLANK_RECT = (0, 0, 1065, 1065)

LEGEND_GRID = list(range(35, 86, 5)) + [100]     # 35,40,…,85,100


def _expand_stops(raw, grid):
    """把色階展開到統一邊界 grid：各邊界取「第一個 ≥ 該邊界」的顏色。"""
    out = []
    for g in grid:
        c = raw[-1][1]
        for u, hx in raw:
            if u >= g:
                c = hx
                break
        out.append((g, c))
    if raw[0][0] == 0:                     # 保留 (0,…) 前導檔位（如新黨）
        out.insert(0, raw[0])
    return out


def scale_fixed():
    return [_expand_stops(_RAW_STOPS[p], LEGEND_GRID) for p in _SCHEME_ORDER]


# ===================== 政黨 → 色階組別 =====================
PARTY_SCHEME = {
    "中國國民黨": 0,              # 藍
    "親民黨": 1,                  # 橘
    "民主進步黨": 2,              # 綠
    "台灣團結聯盟": 3,            # 咖啡
    "新黨": 4,                    # 黃
    "無黨籍及未經政黨推薦": 5,    # 灰
    "無黨籍": 5,                  # 灰
    "建國黨": 6,                  # 青
    "中華社會民主黨": 7,          # 紫
    "民主聯盟": 8,                # 粉
    "工黨": 9,                    # 棕
    "無黨團結聯盟": 10,           # 粉
    "時代力量": 12,               # 芥黃
    "台灣民眾黨": 13,             # 青
    "台灣基進": 14,               # 紅
}
SCHEME_FALLBACK = [11, 6, 7, 8, 9, 10, 12, 13, 14, 0, 1, 2, 3, 4, 5]

# ===================== 選舉區名正規化 =====================
VARIANT_CHAR_MAP = str.maketrans({"臺": "台", "裡": "里"})
# 同一塊地在不同年代的縣市名（只放「不會與舊縣市名撞號」的：桃園縣→桃園市、臺北縣→新北市；
# 臺中縣/臺南縣/高雄縣 三者與同名省轄市並存於 2008，不可合併）
COUNTY_ALIAS = {"桃園縣": "桃園市", "臺北縣": "新北市"}
_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    """中文數字（含「十」「十一」…）→ int。"""
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, b = s.split("十", 1)
        return (_CN_DIGIT.get(a, 1) if a else 1) * 10 + (_CN_DIGIT.get(b, 0) if b else 0)
    return _CN_DIGIT.get(s, 0)


def district_key(name):
    """選舉區名 → (縣市, 選區序號)。

    支援「臺北市第1選舉區」「臺南市第一選區」「新竹縣」「金門縣選舉區」等寫法；
    單一選區（全縣一區）序號記 0。縣市名先套用 COUNTY_ALIAS，再統一 臺→台。"""
    s = re.sub(r"\s+", "", str(name).strip())
    m = re.match(r"^(.*?)第([0-9一二三四五六七八九十]+)選(?:舉)?區$", s)
    if m:
        county, num = m.group(1).strip(), cn2int(m.group(2))
    else:
        m = re.match(r"^(.*?)(?:選舉區|選區)$", s)
        county, num = (m.group(1).strip(), 0) if m else (s, 0)
    county = COUNTY_ALIAS.get(county, county)
    return county.translate(VARIANT_CHAR_MAP), num


def hex2rgb(hx):
    h = str(hx).strip().lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_color_by_value(val, stops):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]


def is_independent(name):
    return str(name).startswith("無黨籍")


# ===================== 讀取對照表與得票資料 =====================
def load_correspondence(xlsx_path):
    """回傳 {(縣市, 序號): {name, county, color_hex}}"""
    df = pd.read_excel(xlsx_path)
    col_color = next(c for c in df.columns if "顏色" in str(c))
    recs = OrderedDict()
    for _, row in df.iterrows():
        name = str(row["選舉區"]).strip()
        key = district_key(name)
        recs[key] = {
            "name": name,
            "county": str(row["縣市"]).strip(),
            "color_hex": str(row[col_color]).strip().upper(),
        }
    if len(recs) != len(df):
        print(f"  ※ 對照表選舉區名正規化後有重複，{len(df)} 列 → {len(recs)} 個 key")
    return recs


def parse_votes(xlsx_path):
    """各屆 xlsx（選舉區級別）→ ([{key, name, county, rates, total}], 得票率欄位名)"""
    df = pd.read_excel(xlsx_path, sheet_name="選舉區級別")
    df.columns = [str(c) for c in df.columns]
    rate_cols = OrderedDict()
    for col in df.columns:
        if col.endswith("得票率"):
            rate_cols[col[:-3]] = col
    if not rate_cols:
        raise ValueError(f"{xlsx_path} 未偵測到任何「得票率」欄位")

    rows = []
    for _, row in df.iterrows():
        name = str(row["選舉區"]).strip()
        rates = {}
        for label, col in rate_cols.items():
            try:
                rates[label] = float(str(row[col]).strip().replace("%", ""))
            except (TypeError, ValueError):
                rates[label] = float("nan")
        rows.append({
            "key": district_key(name),
            "name": name,
            "county": str(row["縣市"]).strip(),
            "rates": rates,
        })
    return rows, list(rate_cols.keys())


# ===================== 繪圖 =====================
FONT_CANDIDATES = [
    r"C:\Users\Windows\AppData\Local\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf",
    r"C:\Windows\Fonts\msjhbd.ttc",
]


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return None


def draw_title(img, lines):
    """把標題燒進左上角（DRAW_TITLE=True 時才呼叫）。"""
    f = _font(96)
    if f is None:
        return img
    d = ImageDraw.Draw(img)
    y = 70
    for t in lines:
        d.text((90, y), t, font=f, fill=(255, 255, 255))
        y += int(96 * 1.35)
    return img


def draw_year(year, session_label, date_line, corr_file, base_file):
    print("=" * 62)
    print(f"  {year} {session_label}立法委員選舉 — 各選舉區得票領先政黨")
    print("=" * 62)

    xlsx_path = os.path.join(DATA_DIR, f"{year}立法委員_選舉區得票.xlsx")
    corr_path = os.path.join(LEG_DIR, corr_file)
    base_png = os.path.join(LEG_DIR, base_file)
    for p in (xlsx_path, corr_path, base_png):
        if not os.path.exists(p):
            print(f"  ※ 缺少檔案，略過本屆：{p}")
            return False

    corr = load_correspondence(corr_path)
    rows, labels = parse_votes(xlsx_path)
    print(f"  對照表選舉區       : {len(corr)} 個（{corr_file}）")
    print(f"  資料選舉區         : {len(rows)} 個（{os.path.basename(xlsx_path)}）")
    print(f"  得票率欄位         : {len(labels)} 個")

    data_map = {r["key"]: r for r in rows}
    miss_in_data = [k for k in corr if k not in data_map]
    miss_in_corr = [k for k in data_map if k not in corr]
    if miss_in_data:
        print(f"  ※ 對照表有、資料無（不著色）：{[corr[k]['name'] for k in miss_in_data]}")
    if miss_in_corr:
        print(f"  ※ 資料有、對照表無（未畫入）：{[data_map[k]['name'] for k in miss_in_corr]}")

    # ------------- 政黨 → 色階指派 -------------
    used_schemes = set()
    party_scheme = {}
    ordered = ["民主進步黨", "中國國民黨", "親民黨", "新黨", "時代力量",
               "台灣民眾黨", "台灣基進", "無黨團結聯盟", "台灣團結聯盟"]
    for p in ordered:
        if p in labels and p in PARTY_SCHEME:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
    for p in labels:
        if p in party_scheme:
            continue
        if is_independent(p):                     # 無黨籍-姓名 → 灰色系
            party_scheme[p] = 5
        elif p in PARTY_SCHEME:
            party_scheme[p] = PARTY_SCHEME[p]
            used_schemes.add(PARTY_SCHEME[p])
        else:
            idx = next((s for s in SCHEME_FALLBACK if s not in used_schemes), 11)
            party_scheme[p] = idx
            used_schemes.add(idx)

    stops = scale_fixed()

    # ------------- 逐區取領先者並上色 -------------
    win_cnt = {}
    win_rates = []
    color2fill = {}
    no_data = []
    for key, rec in corr.items():
        row = data_map.get(key)
        if row is None:
            no_data.append(rec["name"])
            color2fill[hex2rgb(rec["color_hex"])] = hex2rgb(CANVAS_COLOR)
            continue
        rates = row["rates"]
        win = max(rates, key=lambda n: (rates[n] if not np.isnan(rates[n]) else -1.0))
        val = rates[win]
        if np.isnan(val):
            no_data.append(rec["name"])
            color2fill[hex2rgb(rec["color_hex"])] = hex2rgb(CANVAS_COLOR)
            continue
        win_cnt[win] = win_cnt.get(win, 0) + 1
        win_rates.append(val)
        fill = get_color_by_value(val, stops[party_scheme[win]])
        color2fill[hex2rgb(rec["color_hex"])] = hex2rgb(fill)

    print("  各政黨領先選舉區數：")
    for n, c in sorted(win_cnt.items(), key=lambda kv: -kv[1]):
        if is_independent(n):
            print(f"      無黨籍（{n}）: {c} 區")
        else:
            print(f"      {n}: {c} 區")
    if win_rates:
        print(f"  領先得票率範圍     : {min(win_rates):.2f}% ~ {max(win_rates):.2f}%"
              f"（<35% 共 {sum(1 for r in win_rates if r < 35)} 區，落入首格）")
    print(f"  無資料(填底色)     : {len(no_data)}" + (f" {no_data}" if no_data else ""))

    # ------------- 以唯一色重著色底圖 -------------
    img = Image.open(base_png).convert("RGB")
    arr = np.array(img)
    uniq, inv = np.unique(arr.reshape(-1, 3), axis=0, return_inverse=True)
    new_uniq = uniq.copy()
    hit = 0
    for i, u in enumerate(uniq):
        f = color2fill.get(tuple(int(x) for x in u))
        if f is not None:
            new_uniq[i] = f
            hit += 1
    out_arr = new_uniq[inv].reshape(arr.shape)
    out_img = Image.fromarray(out_arr.astype(np.uint8)).convert("RGB")

    # 2026-11-21：BLANK_RECT 以前只宣告、沒有任何地方使用 → 等於沒加。
    # 這裡補上實際繪製（與 2008-2024 的 county／township 兩支同一寫法）：
    # 重著色完成後、燒標題之前，把左上角大陸沿海整片蓋成畫布底色。
    if BLANK_RECT:
        ImageDraw.Draw(out_img).rectangle(BLANK_RECT, fill=hex2rgb(CANVAS_COLOR))

    print(f"  底圖               : {base_file} {img.width}×{img.height}px"
          f"（命中 {hit} / {len(color2fill)} 色）")

    if DRAW_TITLE:
        out_img = draw_title(out_img, [f"{session_label}立法委員選舉（{date_line}）",
                                       "各選舉區得票領先政黨得票率"])

    os.makedirs(OUT_DIR, exist_ok=True)
    out_png = os.path.join(OUT_DIR, f"legislative_district_{year}_party_lead_map.png")
    tmp_png = os.path.join(OUT_DIR, f"_tmp_district_{year}.png")
    for attempt in range(5):
        try:
            out_img.save(tmp_png)
            os.replace(tmp_png, out_png)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.8)
    print(f"  輸出               : {out_png}  ({out_img.width}×{out_img.height}px)\n")
    return True


def main():
    only = [int(a) for a in sys.argv[1:] if a.isdigit()] or [e[0] for e in ELECTIONS]
    print("=" * 62)
    print("  2008-2024 五屆立法委員選舉 — 各選舉區得票率地圖（無圖例）")
    print("  底圖／對照表：County/Legislative（73 色唯一色底圖）")
    print("=" * 62)

    done = []
    for year, session_label, date_line, corr_file, base_file in ELECTIONS:
        if year not in only:
            continue
        if draw_year(year, session_label, date_line, corr_file, base_file):
            done.append(year)

    print("#" * 62)
    print(f"完成 {len(done)}/{len(only)} 屆：{done}")


if __name__ == "__main__":
    main()
