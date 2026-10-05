# -*- coding: utf-8 -*-
"""一次性工具：為 1994-2014 臺北市長選舉建立看板目錄（meta.json + index.html + source/）。

素材（地圖 / 圖例 / 市徽 / 國徽 / 當選標誌 / 黨徽）一律從
NewSolution/png/ 與 processed/ 複製進 source/，讓 build_board.py 的
check_sources() 能通過。data.xlsx 由 NewSolution/data/ 對應檔複製。

執行： py tools/_gen_taipei_boards.py
"""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

VIDEO = r"D:\Windows\TaiwanElection\Video"
BOARDS = os.path.join(VIDEO, "boards")
DATA = os.path.join(VIDEO, "NewSolution", "data")
PNG = os.path.join(VIDEO, "NewSolution", "png")
PROC = os.path.join(PNG, "processed")

TOWNFULL = {
    "松山": "松山區", "信義": "信義區", "大安": "大安區", "中山": "中山區",
    "中正": "中正區", "大同": "大同區", "萬華": "萬華區", "文山": "文山區",
    "南港": "南港區", "內湖": "內湖區", "士林": "士林區", "北投": "北投區",
}


def cand(key, name, party, short, en, number, votes, elected=False, color=None):
    c = {
        "key": key, "name": name, "party": party,
        "partyShort": short, "partyEn": en,
        "number": number, "votes": votes, "elected": elected,
    }
    if color:
        c["color"] = color
    return c


# ---------------------------------------------------------------- 各年設定
YEARS = [
    {
        "id": "1994-taipei-mayor",
        "election": "第一屆臺北市市長選舉",
        "year": 1994, "date": "12月3日", "dateEn": "3 Dec",
        "excel": "1994台北市长.xlsx",
        "electorate": 1801992, "turnout": 78.77,
        "validVotes": 1408554, "invalidVotes": 13795, "castVotes": 1422349,
        "headerRole": "當選人",
        "candidates": [
            cand("ji", "紀榮治", "無黨籍", "IND", "Independent", 1, 3941),
            cand("chao", "趙少康", "新黨", "NSC", "New Party", 2, 424905),
            cand("chen", "陳水扁", "民主進步黨", "DPP",
                 "Democratic Progressive Party", 3, 615090, elected=True),
            cand("huang", "黃大洲", "中國國民黨", "KMT", "Kuomintang", 4, 364618),
        ],
    },
    {
        "id": "1998-taipei-mayor",
        "election": "第二屆臺北市市長選舉",
        "year": 1998, "date": "12月5日", "dateEn": "5 Dec",
        "excel": "1998台北市长.xlsx",
        "electorate": 1893792, "turnout": 79.16,
        "validVotes": 1498901, "invalidVotes": 11310, "castVotes": 1510211,
        "headerRole": "當選人",
        "candidates": [
            cand("ma", "馬英九", "中國國民黨", "KMT", "Kuomintang", 1,
                 766377, elected=True),
            cand("chen", "陳水扁", "民主進步黨", "DPP",
                 "Democratic Progressive Party", 2, 688072),
            # 資料欄位用異體字「王建火宣」，對外顯示正字「王建煊」
            cand("wang", "王建煊", "新黨", "NSC", "New Party", 3, 44452),
        ],
    },
    {
        "id": "2002-taipei-mayor",
        "election": "第三屆臺北市市長選舉",
        "year": 2002, "date": "12月7日", "dateEn": "7 Dec",
        "excel": "2002台北市長_選舉得票資料.xlsx",
        "electorate": 1944026, "turnout": 70.06,
        "validVotes": 1361913, "invalidVotes": 11561, "castVotes": 1373474,
        "headerRole": "當選人",
        "candidates": [
            cand("lee", "李應元", "民主進步黨", "DPP",
                 "Democratic Progressive Party", 1, 488811),
            cand("ma", "馬英九", "中國國民黨", "KMT", "Kuomintang", 2,
                 873102, elected=True),
        ],
    },
    {
        "id": "2006-taipei-mayor",
        "election": "第四屆臺北市市長選舉",
        "year": 2006, "date": "12月9日", "dateEn": "9 Dec",
        "excel": "2006台北市長_選舉得票資料.xlsx",
        "electorate": 2007385, "turnout": 64.31,
        "validVotes": 1286089, "invalidVotes": 7643, "castVotes": 1293732,
        "headerRole": "當選人",
        "candidates": [
            cand("li", "李敖", "無黨籍", "IND", "Independent", 1, 7795),
            cand("chou", "周玉蔻", "台灣團結聯盟", "TSU", "Taiwan Solidarity Union",
                 2, 3372),
            cand("hsieh", "謝長廷", "民主進步黨", "DPP",
                 "Democratic Progressive Party", 3, 525869),
            cand("soong", "宋楚瑜", "親民黨", "PFP", "People First Party", 4, 53281),
            cand("hao", "郝龍斌", "中國國民黨", "KMT", "Kuomintang", 5,
                 692085, elected=True),
            cand("ko", "柯賜海", "無黨籍", "IND", "Independent", 6, 3687),
        ],
    },
    {
        "id": "2010-taipei-mayor",
        "election": "第五屆臺北市市長選舉",
        "year": 2010, "date": "11月27日", "dateEn": "27 Nov",
        "excel": "2010台北市長_選舉得票資料.xlsx",
        "electorate": 2020751, "turnout": 70.96,
        "validVotes": 1433736, "invalidVotes": 8307, "castVotes": 1442043,
        "headerRole": "當選人",
        "candidates": [
            cand("wu1", "吳炎成", "無黨籍", "IND", "Independent", 1, 1832),
            cand("hao", "郝龍斌", "中國國民黨", "KMT", "Kuomintang", 2,
                 797865, elected=True),
            cand("hsiao", "蕭淑華", "無黨籍", "IND", "Independent", 3, 2238),
            cand("wu2", "吳武明", "無黨籍", "IND", "Independent", 4, 3672),
            cand("su", "蘇貞昌", "民主進步黨", "DPP",
                 "Democratic Progressive Party", 5, 628129),
        ],
    },
    {
        "id": "2014-taipei-mayor",
        "election": "第六屆臺北市市長選舉",
        "year": 2014, "date": "11月29日", "dateEn": "29 Nov",
        "excel": "2014台北市长选举_各里得票.xlsx",
        "electorate": 2146939, "turnout": 70.46,
        "validVotes": 1494046, "invalidVotes": 1833, "castVotes": 1495879,
        "headerRole": "當選人",
        "candidates": [
            cand("chen", "陳汝斌", "三等國民公義人權自救黨", "IND", "Independent",
                 1, 1624),
            cand("chao", "趙衍慶", "無黨籍", "IND", "Independent", 2, 15898),
            cand("li", "李宏信", "無黨籍", "IND", "Independent", 3, 2621),
            cand("chenyc", "陳永昌", "無黨籍", "IND", "Independent", 4, 1908),
            cand("feng", "馮光遠", "無黨籍", "IND", "Independent", 5, 8080),
            cand("lien", "連勝文", "中國國民黨", "KMT", "Kuomintang", 6, 609932),
            cand("ko", "柯文哲", "無黨籍", "IND", "Independent", 7,
                 853983, elected=True),
        ],
    },
]

# 複製到 source/ 的素材：來源 -> 目的檔名
ASSET_COPIES = [
    (os.path.join(PROC, "share", "city_seal.png"), "city_seal.png"),
    (os.path.join(PROC, "share", "emblem.png"), "emblem.png"),
    (os.path.join(PROC, "share", "mark_elected.png"), "mark_elected.png"),
    (os.path.join(PROC, "party", "party_kmt.png"), "party_kmt.png"),
    (os.path.join(PROC, "party", "party_dpp.png"), "party_dpp.png"),
    (os.path.join(PROC, "party", "party_nsc.png"), "party_nsc.png"),
    (os.path.join(PROC, "party", "party_pfp.png"), "party_pfp.png"),
]


def build_one(y, variant):
    """建一個場次目錄。variant='map' 是村里版；'map2' 是區級版（鏡像場次）。

    兩版只有兩處不同：id 後綴（-map2）與 region.mapVariant（決定 build 時
    到 processed/map/<year>/ 拿 map.png 還是 map2.png）。其餘 meta / 資料 /
    素材完全相同，所以同一場選舉可以並存「村里版」與「區級版」兩張看板。
    """
    bid = y["id"] + ("-map2" if variant == "map2" else "")
    bdir = os.path.join(BOARDS, bid)
    srcdir = os.path.join(bdir, "source")
    os.makedirs(srcdir, exist_ok=True)

    # ---- meta.json ----
    meta = {
        "id": bid,
        "meta": {
            "election": y["election"],
            "electionEn": "Taipei City Mayoral Election",
            "year": y["year"],
            "date": y["date"],
            "dateEn": y["dateEn"],
            "country": "中華民國（台灣）",
            "countryEn": "Republic of China (Taiwan)",
            "office": "臺北市市長",
            "officeEn": "Mayor of Taipei City",
            "electorate": y["electorate"],
            "turnout": y["turnout"],
            "validVotes": y["validVotes"],
            "invalidVotes": y["invalidVotes"],
            "castVotes": y["castVotes"],
            "headerRole": y["headerRole"],
        },
        "candidates": y["candidates"],
        "region": {
            "county": "臺北市",
            "unitLevel": "village",
            "sheet": "村里層級明細",
            "simplify": 60,
            "townFull": TOWNFULL,
            "mapVariant": variant,
        },
        "assets": {"voteMapAspectTolerance": 0.2},
        "partyThemes": {},
        "layout": {},
    }
    with open(os.path.join(bdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("meta.json  ", bid)

    # ---- index.html（複製模板）----
    shutil.copyfile(os.path.join(BOARDS, "_template", "index.html"),
                    os.path.join(bdir, "index.html"))

    # ---- source/data.xlsx ----
    shutil.copyfile(os.path.join(DATA, y["excel"]),
                    os.path.join(srcdir, "data.xlsx"))

    # ---- source/ 素材 ----
    for src, dstname in ASSET_COPIES:
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(srcdir, dstname))
        else:
            print("  [警告] 缺素材", os.path.relpath(src, VIDEO))

    # ---- source/map.png（該年、該版本）+ legend.png ----
    year = str(y["year"])
    mapname = "map2.png" if variant == "map2" else "map.png"
    for srcname, dstname in ((mapname, "map.png"), ("legend.png", "legend.png")):
        s = os.path.join(PROC, "map", year, srcname)
        if os.path.isfile(s):
            shutil.copyfile(s, os.path.join(srcdir, dstname))
        else:
            print("  [警告] 缺", os.path.relpath(s, VIDEO))


def main():
    for y in YEARS:
        build_one(y, "map")
        build_one(y, "map2")

    print("\n完成。")


if __name__ == "__main__":
    main()
