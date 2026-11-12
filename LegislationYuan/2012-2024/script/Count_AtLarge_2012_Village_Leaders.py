# -*- coding: utf-8 -*-
"""2012 第八屆不分區立委（政黨票）：各縣市「村里領先政黨」村里數統計。

讀取 `data/2012不分区` 的 22 個中選會原始 xls，逐投開票所累加到村里，
判定每個村里得票最高的政黨，輸出各縣市 × 11 政黨的領先村里數 Markdown。
輸出：map/全臺灣2012_村里領先政黨統計.md
執行：py script/Count_AtLarge_2012_Village_Leaders.py
"""
import glob
import os
import re
import collections
import time
import xlrd

XLS_DIR = r"D:\Windows\TaiwanElection\LegislationYuan\2012-2024\data\2012不分区"
OUT = r"D:\Windows\TaiwanElection\LegislationYuan\2012-2024\map\全臺灣2012_村里領先政黨統計.md"
FILENAME_COUNTY_RE = re.compile(r"[（(](.+?)[）)]\s*$")
PARTIES = ["台灣國民會議", "人民最大黨", "民主進步黨", "台灣團結聯盟", "中國國民黨", "新黨",
           "健保免費連線", "綠黨", "親民黨", "中華民國臺灣基本法連線", "台灣主義黨"]
OFFICIAL_ORDER = ["臺北市", "新北市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "新竹縣",
                  "桃園縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣",
                  "臺東縣", "花蓮縣", "宜蘭縣", "澎湖縣", "金門縣", "連江縣"]

def party_name(cell):
    lines = [s.strip() for s in str(cell).split("\n") if s.strip()]
    return lines[1] if len(lines) > 1 else (lines[0] if lines else "")

county_units = {}
for path in sorted(glob.glob(os.path.join(XLS_DIR, "*.xls"))):
    stem = os.path.splitext(os.path.basename(path))[0]
    county = FILENAME_COUNTY_RE.search(stem).group(1)
    wb = xlrd.open_workbook(path)
    acc = {}
    for sh in wb.sheets():
        hdr = next((r for r in range(min(6, sh.nrows))
                    if "鄉(鎮、市、區)別" in str(sh.cell_value(r, 0))), None)
        if hdr is None: continue
        valid_col = next(c for c in range(sh.ncols)
                         if "有效票數" in str(sh.cell_value(hdr, c)).replace("\n", ""))
        pcols = [(c, party_name(sh.cell_value(hdr+1, c))) for c in range(3, valid_col)]
        pcols = [(c, nm) for c, nm in pcols if nm]
        assert [nm for _, nm in pcols] == PARTIES, (stem, [nm for _, nm in pcols])
        town = ""
        for r in range(hdr+4, sh.nrows):
            c0 = str(sh.cell_value(r,0)).strip(); c1 = str(sh.cell_value(r,1)).strip()
            if c0 and not c1:
                if "總" not in c0: town = c0.replace("\u3000","")
                continue
            if not c1: continue
            try:
                counts = [float(sh.cell_value(r,c) or 0) for c,_ in pcols]
                valid = float(sh.cell_value(r, valid_col) or 0)
            except (TypeError, ValueError): continue
            if not town or valid <= 0: continue
            k = (town, c1)
            if k not in acc: acc[k] = counts + [valid]
            else:
                for i,v in enumerate(counts): acc[k][i]+=v
                acc[k][-1]+=valid
    # 村里層級整併：
    #   1) 單一村里列（該村里自己的投開票所）優先；
    #   2) 同一投開票所涵蓋多村里（「、」分隔）時，只補給「沒有自己投開票所」的村里。
    # 這樣每個村里只算一次，且不會把共用票所的票重複灌給已有自己票所的村里。
    direct, shared = {}, collections.defaultdict(list)
    for (town, raw), a in acc.items():
        names = [p.strip() for p in re.split(r"[、，,]", raw) if p.strip()]
        if len(names) == 1:
            direct[(town, names[0])] = a
        else:
            for nm in names:
                shared[(town, nm)].append(a)
    villages = {k: list(a) for k, a in direct.items()}
    for k, alist in shared.items():
        if k in villages:
            continue
        villages[k] = [sum(a[i] for a in alist) for i in range(len(alist[0]))]
    units = [(t, v, a) for (t, v), a in villages.items()]
    county_units[county] = units

rows = []
grand = collections.Counter(); grand_n = 0; grand_tie = 0
ties = []
for c in OFFICIAL_ORDER:
    units = county_units[c]
    cnt = collections.Counter(); tie_cnt = 0
    for town, vill, a in units:
        votes = a[:-1]; mx = max(votes)
        leaders = [i for i,v in enumerate(votes) if v == mx]
        if len(leaders) > 1:
            tie_cnt += 1
            ties.append((c, town, vill, [PARTIES[i] for i in leaders], int(mx), int(a[-1])))
        else:
            cnt[PARTIES[leaders[0]]] += 1
    top = max(PARTIES, key=lambda p: cnt[p])
    rows.append((c, len(units), cnt, tie_cnt, top, cnt[top]))
    grand_n += len(units); grand_tie += tie_cnt
    for p in PARTIES: grand[p]+=cnt[p]
print("total", grand_n, "ties", grand_tie, "sum", sum(grand.values())+grand_tie)
for r in rows: print(r[0], r[1], r[3], r[4], r[5], [r[2][p] for p in PARTIES])
print("grand", [grand[p] for p in PARTIES])

def pct(a,b): return f"{a/b*100:.2f}" if b else "—"

L = []
L.append("# 全臺灣 2012 立法委員不分區（政黨票）— 各縣市「村里領先政黨」統計")
L.append("")
L.append(f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
L.append("- 資料來源：`data/2012不分区`（中選會原始 xls，22 個縣市各一檔，11 個政黨）")
L.append("- 統計單位：**村里**。同一村里若有多個投開票所，先合併該村里全部得票再判定領先政黨。")
L.append("- 判定方式：以該村里**得票數最高**的政黨為「領先政黨」（同一村里各黨得票率分母相同，故以得票數判定與得票率判定結果一致）。")
L.append("- 同票並列：得票數相同且同為最高票時，**不計入任何政黨**，另列「並列」欄，並在文末列出清單。")
L.append("- 共用投開票所：原表若同一個投開票所對應多個村里（以「、」分隔），優先採用該村里自己的投開票所資料；沒有自己投開票所的村里，才使用共用投開票所的合計得票。")
L.append(f"- 全國合計：**{grand_n:,} 個村里**（含並列 {grand_tie} 個）")
L.append("")
L.append("## 1. 各縣市政黨領先村里數")
L.append("")
head = "| 縣市 | 村里數 | " + " | ".join(PARTIES) + " | 並列 | 領先政黨（村里數） |"
sep = "|---|---:|" + "---:|"*len(PARTIES) + "---:|---|"
L += [head, sep]
for c, n, cnt, tie, top, topn in rows:
    vals = " | ".join(str(cnt[p]) for p in PARTIES)
    L.append(f"| {c} | {n} | {vals} | {tie} | {top}（{topn}） |")
top_grand = max(PARTIES, key=lambda p: grand[p])
L.append(f"| **合計** | **{grand_n:,}** | " + " | ".join(f"**{grand[p]:,}**" for p in PARTIES) + f" | **{grand_tie}** | {top_grand}（{grand[top_grand]:,}） |")
L.append("")
L.append("> 註：各縣市「村里數」為資料表中實際出現的村里數（同一村里只計一次）；共用投開票所依上述規則處理，因此可能與行政區村里總數略有差異。")
L.append("")
L.append("## 2. 全國村里領先政黨合計")
L.append("")
L.append("| 政黨 | 領先村里數 | 佔全部村里 % | 佔有唯一領先村里 % |")
L.append("|---|---:|---:|---:|")
uniq = grand_n - grand_tie
for p in PARTIES:
    if grand[p]:
        L.append(f"| {p} | {grand[p]:,} | {pct(grand[p], grand_n)} | {pct(grand[p], uniq)} |")
L.append(f"| **唯一領先合計** | **{uniq:,}** | **{pct(uniq, grand_n)}** | **100.00** |")
L.append(f"| 並列（無唯一領先） | {grand_tie} | {pct(grand_tie, grand_n)} | — |")
L.append(f"| **村里總數** | **{grand_n:,}** | **100.00** | — |")
L.append("")
L.append("## 3. 各縣市領先政黨佔比")
L.append("")
L.append("| 縣市 | 村里數 | 中國國民黨 | 民主進步黨 | 綠黨 | 並列 | 最大領先政黨 |")
L.append("|---|---:|---:|---:|---:|---:|---|")
for c, n, cnt, tie, top, topn in rows:
    L.append(f"| {c} | {n} | {cnt['中國國民黨']}（{pct(cnt['中國國民黨'], n)}%） | {cnt['民主進步黨']}（{pct(cnt['民主進步黨'], n)}%） | {cnt['綠黨']}（{pct(cnt['綠黨'], n)}%） | {tie}（{pct(tie, n)}%） | {top} |")
L.append("")
if ties:
    L.append("## 4. 同票並列村里清單")
    L.append("")
    L.append("| # | 縣市 | 鄉鎮市區 | 村里 | 並列政黨 | 最高票 | 有效票 |")
    L.append("|---:|---|---|---|---|---:|---:|")
    for i, (c, t, v, ps, mx, valid) in enumerate(ties, 1):
        L.append(f"| {i} | {c} | {t} | {v} | {'、'.join(ps)} | {mx:,} | {valid:,} |")
    L.append("")
L.append("## 5. 處理說明")
L.append("")
L.append("1. 直接讀取 22 個縣市原始 xls 的「各政黨得票數」欄，不經任何地圖對位或村里名稱修補，避免名稱比對造成的遺漏。")
L.append("2. 原表按投開票所逐列登錄，同一村里可能出現多列；本統計以「鄉鎮市區＋村里」為鍵先合併得票，再判定領先政黨。")
L.append("3. 少數投開票所同時對應多個村里（例如連江縣南竿鄉一次涵蓋 6 個村），原表僅提供該組合計得票。本統計對「沒有自己投開票所」的村里使用該組合計得票；若該村里另有自己的投開票所，則只採自己的資料，避免重複計算。")
L.append("4. 並列村里不歸屬任何政黨，以維持「領先村里數」的互斥性；若改以「並列各黨各記 1 村」計算，中國國民黨與民主進步黨各可再加 20 村。")
L.append("5. 本表僅統計「村里數」，不涉及得票率高低或當選席次。")
L.append("")
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))
print("written", OUT, len(L), "lines")
