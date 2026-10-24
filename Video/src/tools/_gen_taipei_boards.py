# -*- coding: utf-8 -*-
"""一次性工具：為臺北市長選舉建立場次目錄（meta.json + source/）。

素材（地圖 / 圖例 / 市徽 / 國徽 / 當選標誌 / 黨徽）一律從 dist/assets/ 複製
進 source/，讓 build_board.py 的 check_sources() 能通過。data.xlsx 由 data/
對應檔複製。

★ 2026-10-24 起預設**不再產生 `-map2` 區級鏡像場次**（`<id>-map2`）：
  那批場次每次批次建置都會多吐一份 dist/boards/<id>-map2/board.files.js，
  卻沒有成品在用。預設只建村里版（region.mapVariant = "map"）。
  要恢復舊行為：加 `--with-map2`。

用法：
  python src/tools/_gen_taipei_boards.py                # 只建村里版（預設）
  python src/tools/_gen_taipei_boards.py --with-map2    # 連區級鏡像場次一起建
  python src/tools/_gen_taipei_boards.py --retire-map2  # 只清掉既有 -map2 場次，不動 meta

★ 注意：本檔是「一次性建場器」，會覆寫 meta.json。若現有 meta.json 已手改
  （例如 meta.header 時任市長區塊），跑之前先確認不會被蓋掉。
"""
import argparse
import datetime
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from boardlib import naming

sys.stdout.reconfigure(encoding="utf-8")

VIDEO = naming.VIDEO_ROOT
BOARDS = os.path.join(VIDEO, naming.BOARDS_DIR)          # src/boards
DATA = os.path.join(VIDEO, naming.DATA_ROOT)             # data/
PROC = os.path.join(VIDEO, naming.PROCESSED_ROOT)        # dist/assets
DIST_BOARDS = os.path.join(VIDEO, naming.DIST_BOARDS_ROOT)  # dist/boards
ARCHIVE = os.path.join(VIDEO, "invaild", "obsolete-taipei-map2")

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


def build_one(y, variant="map"):
    """建一個場次目錄。

    variant='map' 是村里版（預設、唯一會產生的版本）；'map2' 是區級鏡像場次，
    只在 `--with-map2` 時才會建，已於 2026-10-24 停用（不要再產）。

    兩版只有兩處不同：id 後綴（-map2）與 region.mapVariant（決定 build 時
    到 dist/assets/map/<year>/ 拿 map.png 還是 map2.png）。
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


# ------------------------------------------------------------ 退役 -map2
def find_map2_boards():
    """掃出臺北市長線既有的 `-map2` 鏡像場次 id（不論年份、含 2018/2022）。"""
    ids = []
    for root in (BOARDS, DIST_BOARDS):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if not name.endswith("-map2"):
                continue
            base = name[: -len("-map2")]
            if "taipei-mayor" not in base:
                continue
            if os.path.isdir(os.path.join(root, name)) and name not in ids:
                ids.append(name)
    return ids


def prune_manifest(ids):
    """從 dist/manifest.json 移除已退役場次的紀錄（先備份）。"""
    path = os.path.join(VIDEO, "dist", "manifest.json")
    if not os.path.isfile(path) or not ids:
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results") or []
    keep = [r for r in results if r.get("board") not in ids]
    if len(keep) == len(results):
        print("manifest：無需變更")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(VIDEO, "dist", "manifest.backup-%s.json" % stamp)
    shutil.copyfile(path, backup)
    data["results"] = keep
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("manifest：移除 %d 筆（%d -> %d），備份 %s"
          % (len(results) - len(keep), len(results), len(keep),
             os.path.relpath(backup, VIDEO)))


def retire_map2(dry_run=False):
    """把臺北市長線的 `-map2` 場次（src + dist）移到 invaild/ 歸檔。

    直接刪掉也不影響重建（dist/boards 是可再生產物、src 的 source/ 是複製品），
    但歸檔可以隨時還原，成本只是幾個 MB。
    """
    ids = find_map2_boards()
    if not ids:
        print("沒有需要退役的 -map2 場次。")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for bid in ids:
        for root, tag in ((BOARDS, "src"), (DIST_BOARDS, "dist")):
            s = os.path.join(root, bid)
            if not os.path.isdir(s):
                continue
            d = os.path.join(ARCHIVE, stamp, tag, bid)
            if dry_run:
                print("[dry-run] %s -> %s" % (os.path.relpath(s, VIDEO),
                                              os.path.relpath(d, VIDEO)))
                continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.move(s, d)
            print("歸檔", os.path.relpath(s, VIDEO), "->", os.path.relpath(d, VIDEO))
    if not dry_run:
        prune_manifest(ids)
    print("\n退役 %d 場 -map2：%s" % (len(ids), "、".join(ids)))


def main():
    ap = argparse.ArgumentParser(
        description="臺北市長看板一次性建場器（預設不再產生 -map2 區級鏡像場次）")
    ap.add_argument("--with-map2", action="store_true",
                    help="同時建 -map2 區級鏡像場次（舊行為，預設關閉）")
    ap.add_argument("--retire-map2", action="store_true",
                    help="只把既有 -map2 場次歸檔到 invaild/，不重建 meta")
    ap.add_argument("--dry-run", action="store_true", help="只印動作，不動檔案")
    ap.add_argument("--only", nargs="*", default=None,
                    help="只處理指定年份，例如 --only 1994 2014")
    args = ap.parse_args()

    if args.retire_map2:
        retire_map2(dry_run=args.dry_run)
        return

    years = YEARS
    if args.only:
        want = {str(v) for v in args.only}
        years = [y for y in YEARS if str(y["year"]) in want]
        if not years:
            print("沒有符合 --only 的年份：", " ".join(args.only))
            return 1

    for y in years:
        build_one(y, "map")
        if args.with_map2:
            build_one(y, "map2")

    if not args.with_map2:
        print("\n完成（只建村里版）。下一步：")
        print("  逐場建置： python src/tools/build_board.py src/boards/<id>")
        print("  一次渲染： node src/tools/render_boards.mjs --all --scale 1")
        print("  既有 -map2 場次若還在，跑 --retire-map2 歸檔掉。")
    else:
        print("\n完成（村里版 + 區級鏡像版）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
