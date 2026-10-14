#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_gen_president_boards.py —— 總統副總統選舉「北北基宜」看板產生器（一次性工具）。

從各屆 Precident/<year>Precident/data/*縣市鄉鎮村里.xlsx 的「鄉鎮市區級別」
工作表（官方得票數）算出：
  * 北北基宜合計：各候選人得票數 / 得票率（= 看板主卡數據）
  * 四縣市（臺北市/新北市/基隆市/宜蘭縣）各自的得票與勝者（= districts，
    供頁尾比例帶與「A : B 個行政區」計數）
副手（vice/viceParty）為網路查證的官方登記搭配。

輸出：boards/<year>-president-north{,-map2}/
      meta.json / board.js / board.files.js / index.html
      （-map2 版用地圖「1」資料夾的鄉鎮級圖；主版用「2」的村里級圖。
        兩版資料完全相同，只差 board.files.js 的 map.png 指向。）

素材（map.png/map2.png/legend.png）請先跑：
    NewSolution/tool/legend_president.py  +  NewSolution/tool/build_assets.py

用法：
    "C:/Users/Windows/AppData/Local/Microsoft/WindowsApps/python.exe" tools/_gen_president_boards.py [年份 ...]
"""
import glob
import json
import os
import shutil
import sys

import pandas as pd

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRECIDENT = r"D:/Windows/TaiwanElection/Precident"
BOARDS = os.path.join(VIDEO, "boards")
ENGINE_INDEX = os.path.join(BOARDS, "2022-taipei-mayor", "index.html")

REGION_COUNTIES = {"台北市", "台北縣", "新北市", "基隆市", "宜蘭縣"}
COUNTY_DISPLAY = {"台北市": "臺北市", "台北縣": "新北市", "新北市": "新北市",
                  "基隆市": "基隆市", "宜蘭縣": "宜蘭縣"}
COUNTY_ORDER = ["臺北市", "新北市", "基隆市", "宜蘭縣"]

# 每屆：任次 / 投票日 / 全國投票率 / 時任總統（頁眉） / 全國當選者 / 候選人
# 候選人：(key, 姓名, 政黨全稱, partyShort, 副手, 副手政黨, color覆寫)
# ★ 當選標記按「全國」官方結果（2004 連宋配在北北基宜贏，但全國由陳水扁當選）
YEAR_META = {
    1996: dict(
        winner="李登輝", ordinal="第九屆", date="3月23日", dateEn="23 Mar", turnout=76.04,
        header=("李登輝", "中國國民黨", "KMT"),
        cands=[
            ("leedeng", "李登輝", "中國國民黨", "KMT", "連戰", "中國國民黨", None),
            ("peng", "彭明敏", "民主進步黨", "DPP", "謝長廷", "民主進步黨", None),
            ("liny", "林洋港", "無黨籍", "IND", "郝柏村", "無黨籍", "#f2b800"),
            ("chenla", "陳履安", "無黨籍", "IND", "王清峰", "無黨籍", None),
        ]),
    2000: dict(
        winner="陳水扁", ordinal="第十屆", date="3月18日", dateEn="18 Mar", turnout=82.69,
        header=("李登輝", "中國國民黨", "KMT"),
        cands=[
            ("chen", "陳水扁", "民主進步黨", "DPP", "呂秀蓮", "民主進步黨", None),
            ("song", "宋楚瑜", "無黨籍", "IND", "張昭雄", "無黨籍", None),
            ("lien", "連戰", "中國國民黨", "KMT", "蕭萬長", "中國國民黨", None),
            (" lee", "李敖", "新黨", "NSC", "馮滬祥", "新黨", None),
            ("hsu", "許信良", "無黨籍", "IND", "朱惠良", "無黨籍", None),
        ]),
    2004: dict(
        winner="陳水扁", ordinal="第十一屆", date="3月20日", dateEn="20 Mar", turnout=80.28,
        header=("陳水扁", "民主進步黨", "DPP"),
        cands=[
            ("chen", "陳水扁", "民主進步黨", "DPP", "呂秀蓮", "民主進步黨", None),
            ("lien", "連戰", "中國國民黨", "KMT", "宋楚瑜", "親民黨", None),
        ]),
    2008: dict(
        winner="馬英九", ordinal="第十二屆", date="3月22日", dateEn="22 Mar", turnout=76.33,
        header=("陳水扁", "民主進步黨", "DPP"),
        cands=[
            ("ma", "馬英九", "中國國民黨", "KMT", "蕭萬長", "中國國民黨", None),
            ("hsieh", "謝長廷", "民主進步黨", "DPP", "蘇貞昌", "民主進步黨", None),
        ]),
    2012: dict(
        winner="馬英九", ordinal="第十三屆", date="1月14日", dateEn="14 Jan", turnout=74.38,
        header=("馬英九", "中國國民黨", "KMT"),
        cands=[
            ("ma", "馬英九", "中國國民黨", "KMT", "吳敦義", "中國國民黨", None),
            ("tsai", "蔡英文", "民主進步黨", "DPP", "蘇嘉全", "民主進步黨", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "林瑞雄", "親民黨", None),
        ]),
    2016: dict(
        winner="蔡英文", ordinal="第十四屆", date="1月16日", dateEn="16 Jan", turnout=66.27,
        header=("馬英九", "中國國民黨", "KMT"),
        cands=[
            ("tsai", "蔡英文", "民主進步黨", "DPP", "陳建仁", "民主進步黨", None),
            ("chu", "朱立倫", "中國國民黨", "KMT", "王如玄", "中國國民黨", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "徐欣瑩", "民國黨", None),
        ]),
    2020: dict(
        winner="蔡英文", ordinal="第十五屆", date="1月11日", dateEn="11 Jan", turnout=74.90,
        header=("蔡英文", "民主進步黨", "DPP"),
        cands=[
            ("tsai", "蔡英文", "民主進步黨", "DPP", "賴清德", "民主進步黨", None),
            ("han", "韓國瑜", "中國國民黨", "KMT", "張善政", "中國國民黨", None),
            ("song", "宋楚瑜", "親民黨", "PFP", "余湘", "親民黨", None),
        ]),
    2024: dict(
        winner="賴清德", ordinal="第十六屆", date="1月13日", dateEn="13 Jan", turnout=71.86,
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

    # 北北基宜合計
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
            "name": disp, "short": disp.replace("臺", "台").rstrip("市縣"),
            "votes": cv, "pct": pct, "valid": tv,
            "winnerKey": top, "margin": round(pct[top] - pct[second], 2),
        })

    # 安全網：全國當選者必須恰好一位
    n_elected = sum(1 for c in cands_out if c["elected"])
    if n_elected != 1:
        raise SystemExit("%d：當選者標記 %d 位（應為 1）" % (year, n_elected))

    meta = {
        "id": "%d-president-north" % year,
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
            "regionLabel": "北北基宜",
            "header": {"role": "時任總統", "name": cfg["header"][0],
                       "party": cfg["header"][1], "partyShort": cfg["header"][2]},
        },
        "candidates": cands_out,
        "districts": districts,
        # 依需求：總統北北基宜看板不畫圖例（右欄讓給第 3 名大卡）
        "layout": {"legend": {"disabled": True}},
    }

    # board.js（canonical）—— 引擎的版面覆寫讀的是 board.meta.layout
    board = {
        "meta": dict(meta["meta"], id=meta["id"],
                     layout={"legend": {"disabled": True}}),
        "candidates": cands_out,
        "districts": districts,
        "geojson": {"type": "FeatureCollection", "features": []},
    }

    for suffix, map_target in (("", "map.png"), ("-map2", "map2.png")):
        bid = meta["id"] + suffix
        bdir = os.path.join(BOARDS, bid)
        os.makedirs(bdir, exist_ok=True)

        m = dict(meta)
        m["id"] = bid
        with open(os.path.join(bdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

        with open(os.path.join(bdir, "board.js"), "w", encoding="utf-8") as f:
            f.write("/* 自動產生，請勿手改。\n"
                    "   來源：Precident/%dPrecident/data 縣市鄉鎮村里 xlsx（鄉鎮市區級別）\n"
                    "   建置：Video/tools/_gen_president_boards.py %d\n*/\n" % (year, year))
            f.write("window.BOARD = " + json.dumps(board, ensure_ascii=False) + ";\n")

        # 邏輯素材 -> processed 成品（黨徽只列該場用到的）
        # map.png  本場的**主地圖**：主版＝村里版、-map2 版＝區級版
        # map2.png **區級版**（always）—— 總統場圖例是關的，地圖右欄空著，
        #          引擎的 Map2Layer 會把這張擺到那一欄（見 layout.js Layout.map2）。
        #          -map2 版看板的 map.png 本來就指到同一張，引擎比對來源相同後
        #          自動跳過，不會同一張圖疊兩遍。
        used_shorts = {c["partyShort"] for c in cands_out}
        files = {
            "city_seal.png": "../../NewSolution/png/processed/share/city_seal.png",
            "emblem.png": "../../NewSolution/png/processed/share/emblem.png",
            "legend.png": "../../NewSolution/png/processed/map/%d/legend.png" % year,
            "map.png": "../../NewSolution/png/processed/map/%d/%s" % (year, map_target),
            "map2.png": "../../NewSolution/png/processed/map/%d/map2.png" % year,
            "mark_elected.png": "../../NewSolution/png/processed/share/mark_elected.png",
            # 全域共享素材（與 build_board.py 的 resolve_assets 同一組落點）
            "roc_flag.png": "../../NewSolution/png/processed/share/roc_flag.png",
            "street_bg.png": "../../NewSolution/png/processed/share/street_bg.png",
        }
        for s in sorted(used_shorts):
            key = s.lower()
            p = "../../NewSolution/png/processed/party/party_%s.png" % key
            if os.path.isfile(os.path.join(VIDEO, "NewSolution", "png",
                                           "processed", "party", "party_%s.png" % key)):
                files["party_%s.png" % key] = p
        with open(os.path.join(bdir, "board.files.js"), "w", encoding="utf-8") as f:
            f.write("/* 自動產生，請勿手改。\n"
                    "   邏輯素材名 -> 實際檔案（透明化成品在 NewSolution/png/processed/）\n"
                    "   建置：Video/tools/_gen_president_boards.py %d\n*/\n" % year)
            f.write("window.BOARD_FILES = " +
                    json.dumps({"files": files}, ensure_ascii=False, indent=2) + ";\n")

        shutil.copyfile(ENGINE_INDEX, os.path.join(bdir, "index.html"))
        print("  ✓", bid)

    # 對照輸出（人眼比對 md）
    print("  %d 北北基宜有效票 %s" % (year, format(valid, ",")))
    for c in cands_out:
        print("    %-4s %10s  %5.2f%%  副:%s" %
              (c["name"], format(c["votes"], ","), c["pct"], c["vice"]))


def main():
    years = [int(a) for a in sys.argv[1:]] or sorted(YEAR_META)
    for y in years:
        print(y)
        build(y)


if __name__ == "__main__":
    main()
