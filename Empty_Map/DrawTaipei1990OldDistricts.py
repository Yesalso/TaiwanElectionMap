# -*- coding: utf-8 -*-
"""
臺北市 1990 年（區調整前）舊行政區重建圖
========================================
依使用者提供的清單，以「現行（111 年）村里界」回推 1990 年調整前之舊區。
★ 專案內沒有 1990 年的舊區/舊里圖資（JSON2 twTown1982、twVillage_pre2010
  之臺北市都已是現行 12 區；106/108/111 亦同），因此：
    - 以現行里著色，不畫舊區外框；
    - 舊里名（1990 廢除者）列於表格，因無幾何無法繪製。

收錄的舊區（10 個）：
  龍山區、城中區、雙園區、古亭區、
  延平區、建成區、大同區（1990 前，不含延平、建成）、
  大安區（1990 前，不含古亭併入部分）、
  松山區（1990 前＝今松山 30 里＋今信義 41 里）、
  中山區（1990 前＝今中山主體＋劃出士林 3 里、松山 3 里）

重疊：以「先搶先贏」處理；本版各區原則上互斥（大同已扣除延平、建成；
      大安已扣除古亭部分；松山已扣除改隸中山的民福/民有/松基）。

輸出：
  D:\\Windows\\TaiwanElection\\Empty_Map\\Taipei\\Taipei1990_OldDistricts.png
  D:\\Windows\\TaiwanElection\\Empty_Map\\Taipei\\Taipei1990_OldDistricts.md

用法：
  python DrawTaipei1990OldDistricts.py
"""
import os
import math
import collections

import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.font_manager import FontProperties
import matplotlib.patheffects as pe

# ---------------------- 設定 ----------------------
SHP = (r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111"
       r"\VILLAGE_MOI_1111118.shp")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Taipei")
OUT_PNG = os.path.join(OUT_DIR, "Taipei1990_OldDistricts.png")
OUT_MD = os.path.join(OUT_DIR, "Taipei1990_OldDistricts.md")
TARGET_COUNTY = "臺北市"
TARGET_CRS = "EPSG:3826"
FONT_PATH = "C:/Users/Windows/AppData/Local/Microsoft/Windows/Fonts/mingliu.TTF"
TARGET_MAP_PX = 6500     # 長邊像素

COLORS = {
    "龍山區":   "#e8a0a0",
    "城中區":   "#f4c98a",
    "雙園區":   "#f7e59b",
    "古亭區":   "#a9d6a9",
    "延平區":   "#e6b98f",
    "建成區":   "#bfa8e0",
    "大同區":   "#f0aecb",
    "大安區":   "#8fd0c0",
    "松山區":   "#c3a9e0",
    "中山區":   "#93c5e8",
}

# 舊里名（1990 廢除；無現行幾何，僅列於表格）
OLD_NAMES = {
    "延平區": ["千秋里", "六館里", "劍窗里", "得勝里", "平樂里", "延登里",
             "舊市里", "普安里", "長興里", "民和里"],
    "建成區": ["光輝里", "復壽里", "星華里", "光智里", "文明里", "建和里",
             "興東里"],
    "大同區": ["福境里", "俗安里", "瞻聖里", "保生里", "龍塘里", "福環里",
             "明倫里", "民族里", "近聖里", "仰聖里", "星耀里", "樹德里",
             "昌吉里", "國昌里", "金城里", "福澤里", "德鄰里", "聚英里",
             "成連里", "田寮里"],
}

# 處理順序＝搶位順序
ORDER = ["龍山區", "城中區", "雙園區", "古亭區", "延平區", "建成區",
         "大同區", "大安區", "松山區", "中山區"]

# 每個舊區的定義：
#   groups          : [(現行區提示 or None, [里名])] 逐一比對
#   include_current : [現行區] 全部納入（再以 exclude_names 扣除）
#   exclude_names   : 從 include_current 扣除的里名
#   partial         : 標「部分併入」的里名
DISTRICTS = [
    dict(name="龍山區", note="1990 併入 萬華區",
         groups=[("萬華區", ["西門里", "新起里", "菜園里", "仁德里",
                           "福音里", "富民里", "富福里", "青山里"])]),
    dict(name="城中區", note="1990 併入 中正區、萬華區",
         groups=[("中正區", ["東門里", "文北里", "文祥里", "幸市里",
                           "明光里", "光復里", "黎明里", "建國里"]),
                 ("萬華區", ["福星里", "慈壽里", "萬壽里"]),
                 ("中正區", ["三愛里", "幸福里", "梅花里"])]),
    dict(name="雙園區", note="1990 併入 萬華區、中正區",
         groups=[("萬華區", ["頂碩里", "雙園里", "和平里", "糖廍里", "柳鄉里",
                           "綠堤里", "華江里", "和德里", "錦德里", "忠德里",
                           "孝德里", "保德里", "銘德里", "華中里", "興德里",
                           "壽德里", "全德里", "日善里"]),
                 ("中正區", ["廈安里"]),
                 ("萬華區", ["榮德里", "青山里", "富民里", "富福里"])],
         partial=["榮德里", "青山里", "富民里", "富福里"]),
    dict(name="古亭區", note="1990 併入 中正區、萬華區、大安區",
         groups=[("中正區", ["南門里", "愛國里", "華林里", "龍福里", "龍津里",
                           "南福里", "自治里", "向營里", "新營里", "龍光里",
                           "龍興里", "永功里", "螢雪里", "忠勤里", "新安里",
                           "新和里", "凌宵里", "永昌里", "忠貞里", "螢圃里",
                           "螢塘里", "網溪里", "河堤里", "板溪里", "頂東里",
                           "大學里", "林興里", "富水里", "水源里", "文盛里",
                           "學府里"]),
                 ("萬華區", ["騰雲里", "日祥里", "新忠里"]),
                 ("大安區", ["古莊里", "古風里"])],
         partial=["新忠里"]),
    dict(name="延平區", note="1990 廢除，併入 大同區（大稻埕一帶）",
         groups=[("大同區", ["南芳里", "大有里", "永樂里", "延平里",
                           "朝陽里", "玉泉里"])]),
    dict(name="建成區", note="1990 廢除，併入 大同區（後車站一帶）",
         groups=[("大同區", ["建明里", "建功里", "建泰里", "星明里",
                           "光能里", "雙連里"])]),
    dict(name="大同區", note="1990 前之大同區（不含 延平、建成）",
         include_current=["大同區"],
         exclude_names=["南芳里", "大有里", "永樂里", "延平里", "朝陽里",
                        "玉泉里", "建明里", "建功里", "建泰里", "星明里",
                        "光能里", "雙連里"]),
    dict(name="大安區", note="1990 前之大安區（不含古亭併入部分）",
         include_current=["大安區"],
         exclude_names=["古莊里", "古風里", "大學里", "學府里"],
         groups=[("信義區", ["黎安里", "黎忠里", "黎平里", "黎順里"])]),
    dict(name="松山區", note="1990 前之松山區（今松山 30 里＋今信義 41 里）",
         groups=[("松山區", ["三民里", "中正里", "中崙里", "中華里", "介壽里",
                            "吉仁里", "吉祥里", "安平里", "自強里", "東光里",
                            "東昌里", "東勢里", "東榮里", "美仁里", "莊敬里",
                            "富泰里", "富錦里", "復建里", "復盛里", "復勢里",
                            "復源里", "敦化里", "慈祐里", "新東里", "新益里",
                            "新聚里", "福成里", "精忠里", "龍田里", "鵬程里"]),
                 ("信義區", ["西村里", "正和里", "興隆里", "中興里", "新仁里",
                            "興雅里", "敦厚里", "廣居里", "安康里", "六藝里",
                            "雅祥里", "五常里", "五全里", "永吉里", "長春里",
                            "四育里", "四維里", "永春里", "富台里", "國業里",
                            "松隆里", "松友里", "松光里", "中坡里", "中行里",
                            "大道里", "大仁里", "景新里", "惠安里", "三張里",
                            "三犁里", "六合里", "泰和里", "景聯里", "景勤里",
                            "雙和里", "嘉興里"]),
                 ("中山區", ["成功里", "金泰里"])]),
    dict(name="中山區", note="1990 前之中山區（主體＋劃出士林、松山部分）",
         include_current=["中山區"],
         exclude_names=["成功里", "金泰里"],
         groups=[(None, ["明勝里", "福樂里", "康寧里", "民福里", "民有里",
                        "松基里"])]),
]

NAME_VARIANT = str.maketrans({"宵": "霄", "莊": "庄"})


def norm(s):
    return str(s).strip().translate(NAME_VARIANT)


# ---------------------- 讀取村里界 ----------------------
gdf = gpd.read_file(SHP, encoding="UTF-8")
if gdf.crs is None:
    gdf.crs = "EPSG:4326"
gdf = gdf.to_crs(TARGET_CRS)
tv = gdf[gdf["COUNTYNAME"] == TARGET_COUNTY].copy()
tv["VILLNAME"] = tv["VILLNAME"].astype(str).str.strip()
tv["TOWNNAME"] = tv["TOWNNAME"].astype(str).str.strip()
tv = tv[["TOWNNAME", "VILLNAME", "geometry"]].reset_index(drop=True)
print(f"{TARGET_COUNTY}：{len(tv)} 里")

_by_key = {}
_by_name = collections.defaultdict(list)
for i, r in tv.iterrows():
    _by_key[(r["TOWNNAME"], norm(r["VILLNAME"]))] = i
    _by_name[norm(r["VILLNAME"])].append(i)


def match(hint, nm):
    n = norm(nm)
    if hint is not None and (hint, n) in _by_key:
        return _by_key[(hint, n)]
    cands = _by_name.get(n, [])
    if not cands:
        return None
    if hint is not None:
        pref = [c for c in cands if tv.loc[c, "TOWNNAME"] == hint]
        if pref:
            return pref[0]
    return cands[0]


# ---------------------- 匹配與指派 ----------------------
assigned = {}                                # index -> old district
entries = collections.defaultdict(list)      # old district -> [entry]
unmatched = []
hint_mismatch = []

for d in DISTRICTS:
    old = d["name"]
    done = set()
    # 1) include_current：整個現行區（扣 exclude）
    for cur in d.get("include_current", []):
        excl = {norm(x) for x in d.get("exclude_names", [])}
        for i, r in tv[tv["TOWNNAME"] == cur].iterrows():
            if norm(r["VILLNAME"]) in excl:
                continue
            e = {"old": old, "hint": cur, "name": r["VILLNAME"],
                 "partial": False, "idx": i, "cur_town": cur}
            entries[old].append(e)
            if i not in assigned:
                assigned[i] = old
    # 2) 逐一比對 groups
    for hint, names in d.get("groups", []):
        for nm in names:
            if nm in done:
                continue
            done.add(nm)
            i = match(hint, nm)
            e = {"old": old, "hint": hint, "name": nm,
                 "partial": nm in d.get("partial", []), "idx": i}
            if i is None:
                e["cur_town"] = None
                unmatched.append(e)
            else:
                e["cur_town"] = tv.loc[i, "TOWNNAME"]
                if hint is not None and e["cur_town"] != hint:
                    hint_mismatch.append((old, nm, hint, e["cur_town"]))
            entries[old].append(e)
            if i is not None and i not in assigned:
                assigned[i] = old

# 重建 entry 的 assigned_to / 標記重疊
for old, es in entries.items():
    for e in es:
        if e["idx"] is None:
            e["assigned_to"] = None
        else:
            e["assigned_to"] = assigned[e["idx"]]

overlaps = [(e["old"], e["assigned_to"], e["name"])
            for old, es in entries.items() for e in es
            if e["idx"] is not None and e.get("assigned_to") != old]

print(f"\n指派成功 {len(assigned)} 里（去重後）")
for old in ORDER:
    n = sum(1 for e in entries[old]
            if e["idx"] is not None and e["assigned_to"] == old)
    print(f"  {old}：{n} 里")
if overlaps:
    print(f"重疊（歸主要舊區）{len(overlaps)} 筆：" +
          "、".join(f"{o}的{a}→{w}" for o, w, a in overlaps))
print(f"已不存在里名 {len(unmatched)} 筆：" +
      "、".join(f"{u['old']}:{u['name']}" for u in unmatched))
if hint_mismatch:
    print("清單標示與實際落點不同（以實際落點為準）：" +
          "、".join(f"{o}:{a}({h}→{c})" for o, a, h, c in hint_mismatch))

# ---------------------- 繪圖 ----------------------
_covered = tv.loc[sorted(assigned.keys())].geometry.union_all()
minx, miny, maxx, maxy = _covered.bounds
pad_x = (maxx - minx) * 0.05
pad_y = (maxy - miny) * 0.05
minx, maxx = minx - pad_x, maxx + pad_x
miny, maxy = miny - pad_y, maxy + pad_y
gw, gh = maxx - minx, maxy - miny
scale = max(gw, gh) / TARGET_MAP_PX
W, H = int(math.ceil(gw / scale)), int(math.ceil(gh / scale))
DPI = 100

fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
ax = fig.add_axes([0.01, 0.01, 0.98, 0.90])
ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)
ax.set_facecolor("white")
ax.axis("off")

tv.plot(ax=ax, facecolor="white", edgecolor="#e0e0e0", linewidth=0.35)

for old in ORDER:
    idxs = [i for i, o in assigned.items() if o == old]
    if not idxs:
        continue
    tv.loc[idxs].plot(ax=ax, facecolor=COLORS[old],
                      edgecolor="#333333", linewidth=0.6)
    part = [e["idx"] for e in entries[old]
            if e["idx"] is not None and e["partial"]
            and e["assigned_to"] == old]
    if part:
        tv.loc[part].plot(ax=ax, facecolor="none", edgecolor="#333333",
                          linewidth=0.6, hatch="///")

tv.dissolve().boundary.plot(ax=ax, edgecolor="#555555", linewidth=1.0)

# --- 文字 ---
data_per_px = gw / W


def _pt(px):
    return px * 72.0 / DPI


FS_VILLAGE = _pt(0.0026 * W)
FS_OLD = _pt(0.0090 * W)
FS_LEGEND = _pt(0.0062 * W)
FS_TITLE = _pt(0.0115 * W)
FS_SUB = _pt(0.0058 * W)
fp = FontProperties(fname=FONT_PATH) if os.path.exists(FONT_PATH) else None

placed_lbl = []


def try_label(x, y, s, fs_pt, color="#111111"):
    w = len(s) * fs_pt * DPI / 72.0 * data_per_px
    h = fs_pt * DPI / 72.0 * data_per_px * 1.25
    for (x0, y0, x1, y1) in placed_lbl:
        if not (x + w / 2 < x0 or x - w / 2 > x1 or
                y + h / 2 < y0 or y - h / 2 > y1):
            return False
    ax.text(x, y, s, fontsize=fs_pt, color=color, ha="center", va="center",
            fontproperties=fp, zorder=6,
            path_effects=[pe.withStroke(linewidth=max(1.2, fs_pt * 0.30),
                                        foreground="white")])
    placed_lbl.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return True


v_order = sorted(assigned, key=lambda i: -tv.loc[i].geometry.area)
n_lbl = sum(1 for i in v_order
            if try_label(tv.loc[i].geometry.representative_point().x,
                         tv.loc[i].geometry.representative_point().y,
                         tv.loc[i, "VILLNAME"], FS_VILLAGE))
print(f"里名標籤：{n_lbl}/{len(assigned)}")

for old in ORDER:
    idxs = [i for i, o in assigned.items() if o == old]
    if not idxs:
        continue
    rp = tv.loc[idxs].geometry.union_all().representative_point()
    ax.text(rp.x, rp.y, old, fontsize=FS_OLD, color="#111111", ha="center",
            va="center", fontproperties=fp, zorder=7, weight="bold",
            path_effects=[pe.withStroke(linewidth=FS_OLD * 0.16,
                                        foreground="white")])

handles = [Patch(facecolor=COLORS[o], edgecolor="#333333", label=o)
           for o in ORDER if any(v == o for v in assigned.values())]
handles.append(Patch(facecolor="#ffffff", edgecolor="#333333",
                     hatch="///", label="標「部分併入」之里"))
ax.legend(handles=handles, loc="upper left", fontsize=FS_LEGEND,
          prop=fp, framealpha=0.95, borderpad=0.8)

ax.text(0.5, 1.055, "臺北市 1990 年（區調整前）舊行政區重建圖",
        transform=ax.transAxes, ha="center", va="bottom",
        fontproperties=fp, fontsize=FS_TITLE)
ax.text(0.5, 1.012, "依現行（111 年）村里界重建，僅含清單提及之里；"
                    "不畫舊區外框（重疊之里歸主要舊區）",
        transform=ax.transAxes, ha="center", va="bottom",
        fontproperties=fp, fontsize=FS_SUB, color="#444444")

os.makedirs(OUT_DIR, exist_ok=True)
try:
    fig.savefig(OUT_PNG, dpi=DPI, facecolor="white")
except OSError as e:
    OUT_PNG = OUT_PNG[:-4] + "_new.png"
    print(f"⚠️ 寫入失敗（{e}），改存 {OUT_PNG}")
    fig.savefig(OUT_PNG, dpi=DPI, facecolor="white")
plt.close(fig)
print(f"已存圖：{OUT_PNG}（{W}×{H}）")

# ---------------------- Markdown 表格 ----------------------
CUR_ORDER = ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區",
             "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"]

lines = []
lines.append("# 臺北市 1990 年（區調整前）舊行政區所轄里對照表\n")
lines.append("> 以「現行（111 年）村里界」回推；只含清單提及之里。舊里名"
             "（1990 廢除）無幾何，僅列於表。")
lines.append("> 重疊之里歸主要舊區（順序：" +
             "→".join(ORDER) + "）。\n")

lines.append("## 摘要\n")
lines.append("| 舊行政區 | 可繪製里數 | 舊里名（1990 廢除） | 已不存在之現行里名 | 說明 |")
lines.append("|---|---:|---:|---:|---|")
for old in ORDER:
    can = sum(1 for e in entries[old]
              if e["idx"] is not None and e["assigned_to"] == old)
    gone = sum(1 for e in entries[old] if e["idx"] is None)
    oldn = len(OLD_NAMES.get(old, []))
    lines.append(f"| {old} | {can} | {oldn} | {gone} | "
                 f"{next(d['note'] for d in DISTRICTS if d['name'] == old)} |")
lines.append("")

for old in ORDER:
    note = next(d["note"] for d in DISTRICTS if d["name"] == old)
    can = [e for e in entries[old]
           if e["idx"] is not None and e["assigned_to"] == old]
    lost = [e for e in entries[old]
            if e["idx"] is not None and e["assigned_to"] != old]
    gone = [e for e in entries[old] if e["idx"] is None]
    lines.append(f"## {old}（{note}）\n")
    lines.append(f"可繪製 {len(can)} 里、已不存在 {len(gone)} 里"
                 f"（另 {len(lost)} 里與其他舊區重疊，歸主要舊區）。\n")
    lines.append("| 現行區 | 里名 | 備註 |")
    lines.append("|---|---|---|")
    for cur in CUR_ORDER:
        for e in sorted([x for x in can if x["cur_town"] == cur],
                        key=lambda x: x["name"]):
            note2 = "部分併入（現行整里算入）" if e["partial"] else ""
            lines.append(f"| {cur} | {e['name']} | {note2} |")
    for e in sorted(lost, key=lambda x: x["name"]):
        lines.append(f"| {e['cur_town']} | {e['name']} | "
                     f"與 {e['assigned_to']} 重疊，歸 {e['assigned_to']} |")
    for e in sorted(gone, key=lambda x: x["name"]):
        lines.append(f"| — | {e['name']} | 已不存在於現行（106/108/111）資料，"
                     f"無法繪製 |")
    lines.append("")
    if OLD_NAMES.get(old):
        lines.append(f"**{old} 1990 年廢除之舊里名（無現行幾何）**："
                     + "、".join(OLD_NAMES[old]) + "\n")

with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"已存表：{OUT_MD}")
print("\n==== All finished ====")
