import io
from openpyxl import load_workbook

p = r"D:\Windows\TaiwanElection\Get_data\2008總統副總統選舉_縣市鄉鎮村里.xlsx"
wb = load_workbook(p)


def rows(name):
    ws = wb[name]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] in (None, "總計"):
            continue
        out.append(r)
    return out


def iv(x):
    try:
        return int(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return 0


co = rows("縣市級別")
tw = rows("鄉鎮市區級別")
vl = rows("村里層級明細")
out = []

# 1) 先以縣市為單位：村里合計 vs 縣市
cmap = {r[0]: (iv(r[1]), iv(r[3])) for r in co}
agg_county = {}
for r in vl:
    a = agg_county.setdefault(r[0], [0, 0])
    a[0] += iv(r[3])
    a[1] += iv(r[5])

# 2) 鄉鎮對照表
twmap = {(r[0], r[1]): (iv(r[2]), iv(r[4])) for r in tw}
bad_town = []
for real, (cm, cx) in sorted(cmap.items()):
    a = agg_county.get(real, [0, 0])
    if a[0] == cm and a[1] == cx:
        continue  # 縣市層對，跳過
    # 縣市層不對 → 按鄉鎮求和比對
    agg_town = {}
    for r in vl:
        if r[0] != real:
            continue
        t = agg_town.setdefault((r[0], r[1]), [0, 0])
        t[0] += iv(r[3])
        t[1] += iv(r[5])
    for k, (tm, tx) in sorted(twmap.items()):
        if k[0] != real:
            continue
        t = agg_town.get(k, [0, 0])
        if t[0] != tm or t[1] != tx:
            bad_town.append((k[0], k[1], t[0], t[1], tm, tx, t[0] - tm, t[1] - tx))

out.append("== 縣市層核對：25 縣市 ==")
for real, (cm, cx) in sorted(cmap.items()):
    a = agg_county.get(real, [0, 0])
    mark = "對" if a[0] == cm and a[1] == cx else "不對"
    out.append("{} 村里合計 馬{} 謝{} vs 縣市 馬{} 謝{} -> {}".format(real, a[0], a[1], cm, cx, mark))
out.append("")
out.append("== 縣市層不對的縣市，其村里 vs 鄉鎮比對（不符者報告，找到第一個即結束） ==")
if bad_town:
    for b in bad_town:
        out.append("不符 鄉鎮：{} {}  村里合計 馬{} 謝{} vs 鄉鎮 馬{} 謝{}  差 馬{} 謝{}".format(*b))
    out.append("AVERAGE_BAD_TOWN: {}".format(bad_town[0][0], bad_town[0][1]))
else:
    out.append("（縣市層不對的縣市，其鄉鎮層全部對上，無不符鄉鎮）")

io.open(r"D:\Windows\TaiwanElection\Get_data\_check.txt", "w", encoding="utf-8").write("\n".join(out))
print("done -> _check.txt")
