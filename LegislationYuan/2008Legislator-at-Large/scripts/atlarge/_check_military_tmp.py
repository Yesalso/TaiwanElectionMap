# -*- coding: utf-8 -*-
"""纯 Python 解析 DBF：查 106 年村里界的军事图斑归属与台中/高雄乡镇列表（用后可删）"""
import struct

DBF = (r"D:\Windows\Documents\村里界歷史圖資_111"
       r"\村里界歷史圖資_106\村里界歷史圖資_106\VILLAGE_MOI_1070205.dbf")

with open(DBF, "rb") as f:
    data = f.read()

nrec = struct.unpack("<I", data[4:8])[0]
nhead = struct.unpack("<H", data[8:10])[0]
nlen = struct.unpack("<H", data[10:12])[0]

# 字段定义
fields, off = [], 32
while data[off] != 0x0D:
    name = data[off:off + 11].split(b"\x00")[0].decode("ascii", "replace")
    ftype = chr(data[off + 11])
    flen = data[off + 16]
    fields.append((name, ftype, flen))
    off += 32
print(f"记录数 {nrec}，字段 {fields}")

# 编码：尝试 cp950（台湾 Big5 常用）
enc = "cp950"

def decode(b):
    return b.decode(enc, "replace").strip()

records = []
for i in range(nrec):
    base = nhead + i * nlen
    rec = data[base:base + nlen]
    pos, row = 1, {}
    for name, ftype, flen in fields:
        raw = rec[pos:pos + flen]
        row[name] = decode(raw)
        pos += flen
    records.append(row)

cols = list(records[0].keys())
print("字段列表:", cols)
cn_col = next(c for c in cols if c == "COUNTYNAME")
tn_col = next(c for c in cols if c == "TOWNNAME")
vl_col = next(c for c in cols if c == "VILLNAME")
print(f"县/乡/村 列: {cn_col}, {tn_col}, {vl_col}")

# 1) 军事图斑
print("--- 含「軍事」字样的图斑 ---")
seen = set()
for r in records:
    key = (r[cn_col], r[tn_col], r[vl_col])
    if key in seen:
        continue
    if "軍事" in r[tn_col] or "軍事" in r[vl_col] or "基地" in r[vl_col]:
        seen.add(key)
        print(key)

# 2) 台中/高雄乡镇列表
for c in ("臺中市", "高雄市"):
    towns = sorted({r[tn_col] for r in records if r[cn_col] == c})
    print(f"--- {c}: {len(towns)} 个乡镇市区 ---")
    print("、".join(towns))

# 3) 全图乡镇组数
groups = {(r[cn_col], r[tn_col]) for r in records}
print("全图 (县,乡镇) 组数:", len(groups))

# 4) 乡镇名为空的记录的县分布
blank = {}
for r in records:
    if r[tn_col] in ("", "nan", "None"):
        blank[r[cn_col]] = blank.get(r[cn_col], 0) + 1
print("乡镇名为空的图斑（按县）:", blank)
