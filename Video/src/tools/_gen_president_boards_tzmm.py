#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_gen_president_boards_tzmm.py —— 總統副總統選舉「桃竹苗」看板產生器（一次性工具）。

★ 與 _gen_president_boards.py（北北基宜）是**兩條獨立的線**：
  本檔只產桃竹苗（桃園市／新竹市／新竹縣／苗栗縣）場次，不去碰北北基宜的
  任何產物；要重生北北基宜請跑那個檔。候選人、政黨、副手搭配與北北基宜
  完全相同（同一屆選舉、同一份候選人名單），只有「分區範圍」不同。

從各屆 Precident/<year>Precident/data/*縣市鄉鎮村里.xlsx 的「鄉鎮市區級別」
工作表（官方得票數）算出：
  * 桃竹苗合計：各候選人得票數 / 得票率（= 看板主卡數據）
  * 四縣市（桃園市／新竹市／新竹縣／苗栗縣）各自的得票與勝者（= districts，
    供頁尾比例帶與「A : B 個行政區」計數）

輸出：boards/<year>-president-tzmm/
      meta.json / board.js / board.files.js / index.html
      ★ 2026-10-19 晚八（需求）：只出「村里圖＋鄉鎮圖合併」的主版一張，
        **不再出 -map2 變體**（主圖＝鄉鎮級那張的版本）。
        主版：主圖＝村里級（map_tzmm.png）、右欄＝區級（map2_tzmm.png）。

素材（map_tzmm.png/map2_tzmm.png/legend.png）請先跑：
    src/mapgen/tool/build_assets.py --kind map
    （源圖：src/president/maps/<year>/{2,1}/桃竹苗*.png → assets/map/<year>/）

版面差異（vs 北北基宜）：
  * regionLabel = 桃竹苗；board id 尾碼用 -tzmm。
  * 地圖是**近方形**（4433×4716，ratio 0.94），contain 進預設框（560–1580）
    後墨跡右緣會到 x≈1546 —— 會壓到第 3 名高卡（左緣 ≥1478）與 map2 欄
    （x1440）。故用 meta.layout.map 把主圖框收窄成 {x:560, w:880}：
    實測墨跡右緣 1432、底部 1172，全部讓開（verify_layout L9/L10 把關）。

用法：
    "C:/Users/Windows/AppData/Local/Microsoft/WindowsApps/python.exe" tools/_gen_president_boards_tzmm.py [年份 ...]
"""
import glob
import json
import os
import shutil
import sys

import pandas as pd

VIDEO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRECIDENT = r"D:/Windows/TaiwanElection/Precident"
BOARDS = os.path.join(VIDEO, "src", "boards")        # 源碼場次目錄（meta.json）
DIST_BOARDS = os.path.join(VIDEO, "dist", "boards")  # 產物（board.js / index.html / PNG）
ENGINE_INDEX = os.path.join(VIDEO, "src", "templates", "index.html")

REGION_LABEL = "桃竹苗"
REGION_COUNTIES = {"桃園縣", "桃園市", "新竹市", "新竹縣", "苗栗縣"}
COUNTY_DISPLAY = {"桃園縣": "桃園市", "桃園市": "桃園市",
                  "新竹市": "新竹市", "新竹縣": "新竹縣", "苗栗縣": "苗栗縣"}
# 顯示順序：由北而南
COUNTY_ORDER = ["桃園市", "新竹市", "新竹縣", "苗栗縣"]
# 短名（新竹市／新竹縣同音，保留市／縣後綴以免混；此欄目前不渲染，僅模型用）
COUNTY_SHORT = {"桃園市": "桃園", "新竹市": "新竹市", "新竹縣": "新竹縣", "苗栗縣": "苗栗"}

# 每屆：任次 / 投票日 / 時任總統（頁眉） / 全國當選者 / 候選人
# 候選人：(key, 姓名, 政黨全稱, partyShort, 副手, 副手政黨, color覆寫)
# ★ 與北北基宜看板同一份名單（同一屆選舉）；當選標記按「全國」官方結果。
# ★ 2000 宋楚瑜＝無黨籍走灰（color.txt 第 0 組），與北北基宜一致。
YEAR_META = {
    1996: dict(
        winner="李登輝", ordinal="第九屆", date="3月23日", dateEn="23 Mar",
        header=("李登輝", "中國國民黨", "KMT"),
        cands=[
            ("leedeng", "李登輝", "中國國民黨", "KMT", "連戰", "中國國民黨", None),
            ("peng", "彭明敏", "民主進步黨", "DPP", "謝長廷", "民主進步黨", None),
            ("liny", "林洋港", "無黨籍", "IND", "郝柏村", "無黨籍", "#f2b800"),
            ("chenla", "陳履安", "無黨籍", "IND", "王清峰", "無黨籍", None),
        ]),
    2000: dict(
        winner="陳水扁", ordinal="第十屆", date="3月18日", dateEn="18 Mar",
        header=("李登輝", "中國國民黨", "KMT"),
        cands=[
            ("chen", "陳水扁", "民主進步黨", "DPP", "呂秀蓮", "民主進步黨", None),
            ("song", "宋楚瑜", "無黨籍", "IND", "張昭雄", "無黨籍", None),
            ("lien", "連戰", "中國國民黨", "KMT", "蕭萬長", "中國國民黨", None),
            (" lee", "李敖", "新黨", "NSC", "馮滬祥", "新黨", None),
            ("hsu", "許信良", "無黨籍", "IND", "朱惠良", "無黨籍", None),
        ]),
    2004: dict(
        winner="陳水扁", ordinal="第十一屆", date="3月20日", dateEn="20 Mar",
        header=("陳水扁", "民主進步黨", "DPP"),
        cands=[
            ("chen", "陳水扁", "民主進步黨", "DPP", "呂秀蓮", "民主進步黨", None),
            ("lien", "連戰", "中國國民黨", "KMT", "宋楚瑜", "親民黨", None),
        ]),
    2008: dict(
        winner="馬英九", ordinal="第十二屆", date="3月22日", dateEn="22 Mar",
        header=("陳水扁", "民主進步黨", "DPP"),
        cands=[
            ("ma", "馬英九", "中國國民黨", "KMT", "蕭萬長", "中國國民黨", None),
            ("hsieh", "謝長廷", "民主進步黨", "DPP", "蘇貞昌", "民主進步黨", None),
        ]),
    2012: dict(
        winner="馬英九", ordinal="第十三屆", date="1月14日", dateEn="14 Jan",
        header=("馬英九", "中國國民黨", "KMT"),
        cands=[
            ("ma", "馬英九", "中國國民黨", "KMT", "吳敦義", "中國國民黨", None),
            ("tsai", "蔡英文", "民主進步黨", "DPP", "蘇嘉全", "民主進步黨", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "林瑞雄", "親民黨", None),
        ]),
    2016: dict(
        winner="蔡英文", ordinal="第十四屆", date="1月16日", dateEn="16 Jan",
        header=("馬英九", "中國國民黨", "KMT"),
        cands=[
            ("tsai", "蔡英文", "民主進步黨", "DPP", "陳建仁", "無黨籍", None),
            ("chu", "朱立倫", "中國國民黨", "KMT", "王如玄", "無黨籍", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "徐欣瑩", "民國黨", None),
        ]),
    2020: dict(
        winner="蔡英文", ordinal="第十五屆", date="1月11日", dateEn="11 Jan",
        header=("蔡英文", "民主進步黨", "DPP"),
        cands=[
            ("tsai", "蔡英文", "民主進步黨", "DPP", "賴清德", "民主進步黨", None),
            ("han", "韓國瑜", "中國國民黨", "KMT", "張善政", "無黨籍", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "余湘", "親民黨", None),
        ]),
    2024: dict(
        winner="賴清德", ordinal="第十六屆", date="1月13日", dateEn="13 Jan",
        header=("蔡英文", "民主進步黨", "DPP"),
        cands=[
            ("lai", "賴清德", "民主進步黨", "DPP", "蕭美琴", "民主進步黨", None),
            ("hou", "侯友宜", "中國國民黨", "KMT", "趙少康", "中國國民黨", None),
            ("ko", "柯文哲", "台灣民眾黨", "TPP", "吳欣盈", "台灣民眾黨", None),
        ]),
}

PARTY_EN = {"KMT": "Kuomintang", "DPP": "Democratic Progressive Party",
            "NSC": "New Party", "PFP": "People First Party",
            "TPP": "Taiwan People's Party", "IND": "Independent"}

# ★ 2026-10-19 個案：推薦政黨（候選人本身是無黨籍、但由某政黨推薦）。
# 值＝推薦政黨的 partyShort（引擎據此找徽章 + 在主卡政黨標籤追加「推薦」段）。
# 目前只有 1996 林洋港＝新黨推薦（中選會登記為「無黨籍」但由新黨背書）。
RECOMMENDED_BY = {
    1996: {"liny": "NSC"},
}

# 桃竹苗主圖框覆寫：見模組 docstring 的「版面差異」
MAP_OVERRIDE = {"x": 560, "w": 880}


def town_table(year):
    paths = glob.glob(os.path.join(PRECIDENT, "%dPrecident" % year,
                                   "data", "*縣市鄉鎮村里*.xlsx"))
    if not paths:
        raise SystemExit("%d：找不到縣市鄉鎮村里 xlsx" % year)
    df = pd.read_excel(paths[0], sheet_name="鄉鎮市區級別")
    return df[df["縣市"].str.replace("臺", "台", regex=False).isin(REGION_COUNTIES)].copy()


def votes_col(df, name):
    pref = [c for c in df.columns
            if c.startswith(name) and c.endswith("_得票數")]
    if not pref:
        raise SystemExit("找不到 %s 的得票數欄" % name)
    return pref[0]


def build(year):
    cfg = YEAR_META[year]
    df = town_table(year)
    cands = cfg["cands"]

    # 欄位：每候選人得票數
    cols = {c[1]: votes_col(df, c[1]) for c in cands}

    # 桃竹苗合計
    totals = {n: int(df[col].fillna(0).sum()) for n, col in cols.items()}
    valid = sum(totals.values())

    # 四縣市
    counties = {}
    for county, g in df.groupby("縣市"):
        disp = COUNTY_DISPLAY.get(county, county)
        cv = {n: int(g[col].fillna(0).sum()) for n, col in cols.items()}
        counties[disp] = cv

    # 組 candidates
    cands_out = []
    for i, (key, name, party, short, vice, viceParty, color) in enumerate(cands, 1):
        c = {
            "key": key.strip(), "name": name, "nameEn": "",
            "party": party, "partyShort": short, "partyEn": PARTY_EN[short],
            "number": i, "votes": totals[name],
            "pct": round(totals[name] / valid * 100, 2),
            "elected": name == cfg["winner"],
            "vice": vice, "viceParty": viceParty,
        }
        if color:
            c["color"] = color
        # 推薦政黨（無黨籍候選人由某政黨背書，如 1996 林洋港＝新黨推薦）
        rec = (RECOMMENDED_BY.get(year) or {}).get(key.strip())
        if rec:
            c["recommendedBy"] = rec
        cands_out.append(c)

    # districts（四縣市）
    districts = []
    for disp in COUNTY_ORDER:
        if disp not in counties:
            continue
        cv = counties[disp]
        order = sorted(cv, key=lambda k: -cv[k])
        top, second = order[0], order[1]
        tv = sum(cv.values())
        pct = {k: round(v / tv * 100, 2) for k, v in cv.items()}
        districts.append({
            "name": disp, "short": COUNTY_SHORT[disp],
            "votes": cv, "pct": pct, "valid": tv,
            "winnerKey": top, "margin": round(pct[top] - pct[second], 2),
        })

    # 安全網：全國當選者必須恰好一位
    n_elected = sum(1 for c in cands_out if c["elected"])
    if n_elected != 1:
        raise SystemExit("%d：當選者標記 %d 位（應為 1）" % (year, n_elected))

    meta = {
        "id": "%d-president-tzmm" % year,
        "meta": {
            "election": "%s總統副總統選舉" % cfg["ordinal"],
            "electionEn": "%d Presidential Election" % year,
            "year": year,
            "date": cfg["date"], "dateEn": cfg["dateEn"],
            "country": "中華民國（台灣）",
            "countryEn": "Republic of China (Taiwan)",
            "office": "總統副總統",
            "officeEn": "President & Vice President",
            "turnout": None,                    # 分區無選舉人數，不印投票率
            "validVotes": valid,
            "regionLabel": REGION_LABEL,
            "header": {"role": "時任總統", "name": cfg["header"][0],
                       "party": cfg["header"][1], "partyShort": cfg["header"][2]},
        },
        "candidates": cands_out,
        "districts": districts,
        # 依需求：總統桃竹苗看板不畫圖例（右欄讓給區級圖／第 3 名大卡）
        # map 框收窄：近方形地圖的墨跡右緣要讓開第 3 名高卡與 map2 欄
        "layout": {"legend": {"disabled": True}, "map": dict(MAP_OVERRIDE)},
    }

    # board.js（canonical）—— 引擎的版面覆寫讀的是 board.meta.layout
    board = {
        "meta": dict(meta["meta"], id=meta["id"],
                     layout={"legend": {"disabled": True}, "map": dict(MAP_OVERRIDE)}),
        "candidates": cands_out,
        "districts": districts,
        "geojson": {"type": "FeatureCollection", "features": []},
    }

    # ★ 2026-10-19 晚八（需求）：只出主版（村里主圖＋右欄鄉鎮圖合併），
    #   不再出 -map2 變體。要恢復兩版輸出時，把這行換回：
    #   for suffix, map_target in (("", "map_tzmm.png"), ("-map2", "map2_tzmm.png")):
    for suffix, map_target in (("", "map_tzmm.png"),):
        bid = meta["id"] + suffix
        src_dir = os.path.join(BOARDS, bid)        # src/boards/<id>（meta.json）
        out_dir = os.path.join(DIST_BOARDS, bid)   # dist/boards/<id>（產物）
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        m = dict(meta)
        m["id"] = bid
        with open(os.path.join(src_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

        with open(os.path.join(out_dir, "board.js"), "w", encoding="utf-8") as f:
            f.write("/* 自動產生，請勿手改。\n"
                    "   來源：Precident/%dPrecident/data 縣市鄉鎮村里 xlsx（鄉鎮市區級別）\n"
                    "   建置：Video/src/tools/_gen_president_boards_tzmm.py %d（桃竹苗）\n*/\n" % (year, year))
            f.write("window.BOARD = " + json.dumps(board, ensure_ascii=False) + ";\n")

        # 邏輯素材 -> 透明化成品的相對路徑（相對 index.html = dist/boards/<id>/）。
        # map.png  本場的**主地圖**：主版＝村里版、-map2 版＝區級版（皆為桃竹苗）
        # map2.png **區級版**（always）—— 總統場圖例是關的，地圖右欄空著，
        #          引擎的 Map2Layer 會把這張擺到那一欄（見 layout.js Layout.map2）。
        used_shorts = {c["partyShort"] for c in cands_out}
        # 推薦政黨的徽章也要一起掛進 files（否則引擎退回抽象色塊）
        used_shorts |= {c["recommendedBy"] for c in cands_out
                        if c.get("recommendedBy")}
        files = {
            "city_seal.png": "../../assets/share/city_seal.png",
            "emblem.png": "../../assets/share/emblem.png",
            "legend.png": "../../assets/map/%d/legend.png" % year,
            "map.png": "../../assets/map/%d/%s" % (year, map_target),
            "map2.png": "../../assets/map/%d/map2_tzmm.png" % year,
            "mark_elected.png": "../../assets/share/mark_elected.png",
            # 全域共享素材（與 build_board.py 的 resolve_assets 同一組落點）
            "roc_flag.png": "../../assets/share/roc_flag.png",
            "street_bg.png": "../../assets/share/street_bg.png",
        }
        for s in sorted(used_shorts):
            key = s.lower()
            p = "../../assets/party/party_%s.png" % key
            if os.path.isfile(os.path.join(VIDEO, "dist", "assets",
                                           "party", "party_%s.png" % key)):
                files["party_%s.png" % key] = p
        with open(os.path.join(out_dir, "board.files.js"), "w", encoding="utf-8") as f:
            f.write("/* 自動產生，請勿手改。\n"
                    "   邏輯素材名 -> 實際檔案（透明化成品在 dist/assets/）\n"
                    "   建置：Video/src/tools/_gen_president_boards_tzmm.py %d（桃竹苗）\n*/\n" % year)
            f.write("window.BOARD_FILES = " +
                    json.dumps({"files": files}, ensure_ascii=False, indent=2) + ";\n")

        shutil.copyfile(ENGINE_INDEX, os.path.join(out_dir, "index.html"))
        print("  ✓", bid)

    # 對照輸出（人眼比對 src/president/maps/<year>/*五大分區得票統計.md）
    print("  %d 桃竹苗有效票 %s" % (year, format(valid, ",")))
    for c in cands_out:
        print("    %-4s %10s  %5.2f%%  副:%s" %
              (c["name"], format(c["votes"], ","), c["pct"], c["vice"]))
    for d in districts:
        print("    [%s] 勝:%s 領先%.2f%%" % (d["name"], d["winnerKey"], d["margin"]))


def main():
    years = [int(a) for a in sys.argv[1:]] or sorted(YEAR_META)
    for y in years:
        print(y)
        build(y)


if __name__ == "__main__":
    main()
