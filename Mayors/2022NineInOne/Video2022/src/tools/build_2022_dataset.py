#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_2022_dataset.py —— 從 22 份 xlsx ＋ 簡報 併出看板要用的資料集。

輸出：data/nine2022.json（唯一資料來源，gen_boards.py 只讀這一份）

資料怎麼併的
------------
* 得票數 / 得票率 / 號次 / 姓名（繁體）  ← data/2022*選舉_<縣市>.xlsx 的「縣市級別」
* 黨籍                                   ← docs/2022县市长选举简报.md 各縣市候選人表
                                            （簡報是簡體，用 PARTY_S2T 逐字對回繁體）
* 選舉人數 / 投票數 / 有效票 / 無效票 / 投票率
                                          ← 同一份簡報各縣市「选举人数 …」那行
* 鄉鎮市區得票（給 districts）            ← xlsx 的「鄉鎮市區級別」

為什麼姓名不用簡報的：簡報是簡體，看板要繁體；xlsx 的欄名本來就是繁體，
而且號次（01、02…）兩邊一致，用號次 join 最穩。

用法：
    python src/tools/build_2022_dataset.py            # 產生並自我檢查
    python src/tools/build_2022_dataset.py --print    # 只印表格，不寫檔
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
BRIEF = os.path.join(ROOT, "docs", "2022县市长选举简报.md")
OUT = os.path.join(DATA, "nine2022.json")

# ---------------------------------------------------------------- 22 縣市
# name   正規繁體名（對齊 xlsx 內容與地圖檔名）
# brief  簡報章節標題用的（簡體）名稱
# slug   ASCII 場次尾碼（render_boards.mjs 會拿它當輸出資料夾）
# seal   assets/share/徽章/ 下的原圖檔名
CO = [
    # 直轄市（第四屆）
    ("臺北市", "台北市", "taipei", "台北市市徽.png", 4, "市長"),
    ("新北市", "新北市", "newtaipei", "新北市徽.png", 4, "市長"),
    ("桃園市", "桃园市", "taoyuan", "桃园.png", 4, "市長"),
    ("臺中市", "台中市", "taichung", "台中.png", 4, "市長"),
    ("臺南市", "台南市", "tainan", "台南.png", 4, "市長"),
    ("高雄市", "高雄市", "kaohsiung", "高雄.png", 4, "市長"),
    # 縣市（第十九屆）
    ("基隆市", "基隆市", "keelung", "基隆.png", 19, "市長"),
    ("新竹市", "新竹市", "hsinchu-city", "新竹市.png", 19, "市長"),
    ("新竹縣", "新竹县", "hsinchu-county", "新竹县.png", 19, "縣長"),
    ("苗栗縣", "苗栗县", "miaoli", "苗栗.png", 19, "縣長"),
    ("彰化縣", "彰化县", "changhua", "彰化.png", 19, "縣長"),
    ("南投縣", "南投县", "nantou", "南投.png", 19, "縣長"),
    ("雲林縣", "云林县", "yunlin", "云林.png", 19, "縣長"),
    ("嘉義市", "嘉义市", "chiayi-city", "嘉义市.png", 19, "市長"),
    ("嘉義縣", "嘉义县", "chiayi-county", "嘉义县.png", 19, "縣長"),
    ("屏東縣", "屏东县", "pingtung", "屏东.png", 19, "縣長"),
    ("宜蘭縣", "宜兰县", "yilan", "宜兰.png", 19, "縣長"),
    ("花蓮縣", "花莲县", "hualien", "花莲.png", 19, "縣長"),
    ("臺東縣", "台东县", "taitung", "台东.png", 19, "縣長"),
    ("澎湖縣", "澎湖县", "penghu", "澎湖.png", 19, "縣長"),
    ("金門縣", "金门县", "kinmen", "金门.png", 19, "縣長"),
    ("連江縣", "连江县", "lienchiang", "马祖.png", 19, "縣長"),
]

# 檔名前綴（直轄市長／縣市長）與 臺/台 用字都不一致，用「掃目錄＋正規化」對，
# 不寫死檔名：臺→台 之後「台北市」「臺中市」都會落在同一個 key。
def _norm(s):
    return s.replace("臺", "台").replace(" ", "")


def xlsx_index():
    idx = {}
    for fn in os.listdir(DATA):
        m = re.match(r"^2022.*選舉_(.+)\.xlsx$", fn)
        if m:
            idx[_norm(m.group(1))] = os.path.join(DATA, fn)
    return idx


XLSX = xlsx_index()


def xlsx_name(name):
    p = XLSX.get(_norm(name))
    if not p:
        raise SystemExit("找不到 %s 的 xlsx（data/ 下沒有對應檔）" % name)
    return p


# 簡報（簡體）黨籍 → (繁體黨名, partyShort)
PARTY_S2T = {
    "中国国民党": ("中國國民黨", "KMT"),
    "民主进步党": ("民主進步黨", "DPP"),
    "台湾民众党": ("台灣民眾黨", "TPP"),
    "无党籍": ("無黨籍", "IND"),
    "时代力量": ("時代力量", "IND"),
    "台湾动物保护党": ("台灣動物保護黨", "IND"),
    "台湾维新": ("台灣維新", "IND"),
    "共和党": ("共和黨", "IND"),
    "天一党": ("天一黨", "IND"),
    "台澎党": ("台澎國際法法理建國黨", "IND"),
    "龙党": ("龍黨", "IND"),
}

PARTY_EN = {"KMT": "Kuomintang", "DPP": "Democratic Progressive Party",
            "TPP": "Taiwan People's Party", "IND": "Independent"}

CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九",
          10: "十", 11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五",
          16: "十六", 17: "十七", 18: "十八", 19: "十九", 20: "二十"}

# 嘉義市因候選人死亡，投票日延期
DATE_OVERRIDE = {"嘉義市": ("12月18日", "18 Dec")}
DATE_DEFAULT = ("11月26日", "26 Nov")

# 英文機關名（看板不顯示，只留給 meta 完整性）
OFFICE_EN = {
    "臺北市": "Mayor of Taipei City", "新北市": "Mayor of New Taipei City",
    "桃園市": "Mayor of Taoyuan City", "臺中市": "Mayor of Taichung City",
    "臺南市": "Mayor of Tainan City", "高雄市": "Mayor of Kaohsiung City",
    "基隆市": "Mayor of Keelung City", "新竹市": "Mayor of Hsinchu City",
    "新竹縣": "Magistrate of Hsinchu County", "苗栗縣": "Magistrate of Miaoli County",
    "彰化縣": "Magistrate of Changhua County", "南投縣": "Magistrate of Nantou County",
    "雲林縣": "Magistrate of Yunlin County", "嘉義市": "Mayor of Chiayi City",
    "嘉義縣": "Magistrate of Chiayi County", "屏東縣": "Magistrate of Pingtung County",
    "宜蘭縣": "Magistrate of Yilan County", "花蓮縣": "Magistrate of Hualien County",
    "臺東縣": "Magistrate of Taitung County", "澎湖縣": "Magistrate of Penghu County",
    "金門縣": "Magistrate of Kinmen County", "連江縣": "Magistrate of Lienchiang County",
}


# ---------------------------------------------------------------- 工具
def to_int(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def to_pct(v):
    if v is None:
        return 0.0
    s = str(v).strip().replace("%", "").replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def wan(n):
    """與引擎 U.voteWan 同一個規則：>=1 萬 → 「136萬0951」，否則原數字。"""
    n = int(n)
    if n < 10000:
        return str(n)
    return "%d萬%04d" % (n // 10000, n % 10000)


# ---------------------------------------------------------------- 簡報
def parse_brief():
    """回傳 {縣市簡體名: {'cands': {號次: {...}}, 'stats': {...}}}"""
    text = open(BRIEF, encoding="utf-8").read()
    blocks = re.split(r"^#### ", text, flags=re.M)[1:]
    out = {}
    for b in blocks:
        head = b.splitlines()[0]
        cname = head.split("\u3000")[0].strip()
        cands = {}
        for ln in b.splitlines():
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) != 6 or not re.match(r"^\d{2}$", cells[0]):
                continue
            no = int(cells[0])
            cands[no] = {
                "nameS": cells[1],
                "partyS": cells[2],
                "votes": to_int(cells[3]),
                "pct": to_pct(cells[4]),
                "elected": "当选" in cells[5],
            }
        stats = None
        for ln in b.splitlines():
            # 只吃「本節開頭那一行」（行首就是選舉人數）；後面的第 6 章、
            # 註腳也含「选举人数」字樣，取第一個就停，否則會被蓋成 0。
            if stats is not None or not ln.strip().startswith("选举人数"):
                continue
            m = dict(re.findall(r"(选举人数|投票数|有效票|无效票)\s*\*{0,2}([\d,]+)",
                                ln.replace("**", "")))
            mt = re.search(r"投票率\s*([\d.]+)%", ln)
            stats = {
                "electorate": to_int(m.get("选举人数")),
                "cast": to_int(m.get("投票数")),
                "valid": to_int(m.get("有效票")),
                "invalid": to_int(m.get("无效票")),
                "turnout": round(float(mt.group(1)), 2) if mt else None,
            }
        if not cands:
            raise SystemExit("簡報解析失敗：%s 沒有候選人表" % cname)
        out[cname] = {"cands": cands, "stats": stats}
    return out


# ---------------------------------------------------------------- xlsx
VOTE_COL = re.compile(r"^(.+?)（(\d{2})）_得票數$")


def read_xlsx(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    # --- 縣市級別：欄名 -> (姓名, 號次)
    ws = wb["縣市級別"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(c) if c is not None else "" for c in rows[0]]
    row = rows[1]
    cols = []            # [(號次, 姓名, 票數, 得票率)]
    for i, h in enumerate(hdr):
        m = VOTE_COL.match(h)
        if m:
            cols.append((int(m.group(2)), m.group(1), to_int(row[i]),
                         to_pct(row[i + 1]) if i + 1 < len(row) else 0.0))
    elected_name = str(row[-1]).strip() if row[-1] else ""

    # --- 鄉鎮市區級別
    ws2 = wb["鄉鎮市區級別"]
    r2 = list(ws2.iter_rows(values_only=True))
    hdr2 = [str(c) if c is not None else "" for c in r2[0]]
    idx = {}
    for i, h in enumerate(hdr2):
        m = VOTE_COL.match(h)
        if m:
            idx[int(m.group(2))] = i
    towns = []
    for r in r2[1:]:
        if not r or not r[1]:
            continue
        towns.append({"name": str(r[1]).strip(),
                      "votes": {no: to_int(r[i]) for no, i in idx.items()}})
    return cols, elected_name, towns


# ---------------------------------------------------------------- 組裝
def build_county(name, brief_name, slug, seal, ordinal, office, brief):
    b = brief[brief_name]
    cols, elected_name, towns = read_xlsx(xlsx_name(name))

    cands = []
    warn = []
    for no, cname, votes, pct in sorted(cols):
        src = b["cands"].get(no)
        if not src:
            raise SystemExit("%s：簡報沒有號次 %02d（%s）" % (name, no, cname))
        if src["votes"] != votes:
            warn.append("號次 %02d %s 票數 xlsx=%d 簡報=%d（採 xlsx）"
                        % (no, cname, votes, src["votes"]))
        party, short = PARTY_S2T[src["partyS"]]
        cands.append({
            "key": "c%02d" % no,
            "number": no,
            "name": cname,
            "nameEn": "",
            "party": party,
            "partyShort": short,
            "partyEn": PARTY_EN[short],
            "votes": votes,
            "pct": pct,
            "elected": (cname == elected_name),
        })

    valid = sum(c["votes"] for c in cands)
    st = b["stats"]
    if st["valid"] != valid:
        warn.append("有效票：候選人加總 %d ≠ 簡報 %d" % (valid, st["valid"]))
    if st["valid"] + st["invalid"] != st["cast"]:
        warn.append("有效票＋無效票 %d ≠ 投票數 %d" % (st["valid"] + st["invalid"], st["cast"]))

    # districts：鄉鎮市區領先者與差距（看板目前不畫，但資料留著給後續用）
    districts = []
    for t in towns:
        tv = {k: v for k, v in t["votes"].items() if v > 0}
        if not tv:
            continue
        total = sum(t["votes"].values())
        order = sorted(tv, key=lambda k: -tv[k])
        top = order[0]
        second = order[1] if len(order) > 1 else None
        pctv = {k: round(t["votes"][k] / total * 100, 2) for k in t["votes"]}
        districts.append({
            "name": t["name"],
            "votes": {"c%02d" % k: v for k, v in sorted(t["votes"].items())},
            "pct": {"c%02d" % k: v for k, v in sorted(pctv.items())},
            "valid": total,
            "winnerKey": "c%02d" % top,
            "margin": round(pctv[top] - pctv[second], 2) if second else round(pctv[top], 2),
        })

    winner = next(c for c in cands if c["elected"])
    date, dateEn = DATE_OVERRIDE.get(name, DATE_DEFAULT)
    stats_rows = [
        {"label": "選舉人數", "value": wan(st["electorate"]) + " 人"},
        {"label": "投票數", "value": wan(st["cast"]) + " 票"},
        {"label": "有效票", "value": wan(st["valid"]) + " 票"},
        {"label": "無效票", "value": wan(st["invalid"]) + " 票"},
        {"label": "投票率", "value": "%.2f%%" % st["turnout"]},
    ]

    return {
        "name": name,
        "slug": slug,
        "id": "2022-" + slug,
        "sealSrc": seal,
        "mapVillage": name + "_村里級.png",
        "mapTown": name + "_鄉鎮級.png",
        "election": "2022年九合一選舉",
        "electionEn": "2022 Local Elections",
        "subtitle": "%s · 第%s屆%s選舉" % (name, CN_NUM[ordinal], office),
        "office": name + office,
        "officeEn": OFFICE_EN[name],
        "date": date,
        "dateEn": dateEn,
        "ordinal": ordinal,
        "stats": st,
        "statsRows": stats_rows,
        "winner": {"name": winner["name"], "party": winner["party"],
                   "partyShort": winner["partyShort"]},
        "candidates": cands,
        "districts": districts,
        "warn": warn,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="只印表格，不寫檔")
    args = ap.parse_args()

    brief = parse_brief()
    counties = []
    problems = 0
    for name, bname, slug, seal, ordinal, office in CO:
        c = build_county(name, bname, slug, seal, ordinal, office, brief)
        counties.append(c)
        elected = [x for x in c["candidates"] if x["elected"]]
        st = c["stats"]
        flag = "" if len(elected) == 1 else "  ⚠ 當選人數=%d" % len(elected)
        print("%-5s %-14s 候選%2d  有效%9s  投票率%6.2f%%  當選 %s（%s）%s"
              % (name, c["subtitle"], len(c["candidates"]),
                 format(st["valid"], ","), st["turnout"],
                 c["winner"]["name"], c["winner"]["partyShort"], flag))
        for w in c["warn"]:
            problems += 1
            print("    [核對]", w)
        if len(elected) != 1:
            problems += 1

    print("\n合計：%d 縣市、%d 位候選人、有效票 %s、問題 %d 項"
          % (len(counties), sum(len(c["candidates"]) for c in counties),
             format(sum(c["stats"]["valid"] for c in counties), ","), problems))

    if not args.print:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"generatedAt": "2022", "counties": counties},
                      f, ensure_ascii=False, indent=1)
        print("寫出", os.path.relpath(OUT, ROOT))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
