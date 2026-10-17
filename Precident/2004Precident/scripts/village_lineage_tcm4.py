# -*- coding: utf-8 -*-
"""桃竹苗四縣市（桃園縣・新竹縣・新竹市・苗栗縣）村里沿革（母里對照）。

資料來源＝使用者查證後提供的 `村里对应关系.md`
（表格欄位：`# | 縣市 | 鄉鎮市區 | 村里 | 1995年時所屬村里 | 備註`）。
每一列＝ 2012 圖資（twvillage2012.json）有該村里、但選舉當年尚不存在，
繪圖時須併入其當時所屬的「母里」（同底色、其間不畫界線），
使地圖不因行政沿革而出現留白——語意同 `village_lineage_north4.py`。

對照表為跨屆共用（同一份母里關係），本模組優先讀取本屆 `maps/村里对应关系.md`，
不存在時回溯讀取 `1996Precident/maps/村里对应关系.md`（單一來源，免重複維護）。

解析規則：
  - 「村里」＝子村里（2012 圖資側）；「1995年時所屬村里」＝母里（選舉當年側）。
    母里欄可能含多個母村（如「大崗村、公西村」）→ 全數收錄，比對時任取
    於當年得票資料中存在者。
  - 分割年＝「備註」欄第一個西元年（如「1997年由曲溪里分割」→ 1997）。
    **本屆政策**：只要底圖有該里、而當年得票資料沒有，就一律往沿革母里
    追溯（不因「分割年 <= 選舉年」而留白）；底圖有、得票資料亦有者一律用
    自身（見 resolve_unit_name 第一步）。母里亦查無資料者才維持自身留白。
    （與 1996 屆不同：1996 屆把「分割年 <= 1996」視為當年已設里之資料缺漏、不併入。）
  - 全表以 (縣市, 鄉鎮市區) 為鍵——桃竹苗四縣市鄉鎮名不重複，但沿用
    北北基宜的 (縣市,鄉鎮,村里) 三元組索引，日後擴區不需改結構。

模組於 import 時解析 MD；日後修改 `村里对应关系.md` 內容即會生效。
"""
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PRECIDENT_DIR = os.path.dirname(os.path.dirname(_SCRIPT_DIR))   # ...\Precident

# 母里對照表（跨屆共用）：本屆優先，無則回溯 1996 屆
MD_CANDIDATES = [
    os.path.join(os.path.dirname(_SCRIPT_DIR), "maps", "村里对应关系.md"),
    os.path.join(_PRECIDENT_DIR, "1996Precident", "maps", "村里对应关系.md"),
]
MD_PATH = next((p for p in MD_CANDIDATES if os.path.exists(p)), MD_CANDIDATES[0])

# (縣市, 鄉鎮市區) → [(母里, 子里), ...]（用字＝MD 原文，含「村/里」尾綴）
VILLAGE_SPLITS = {}
# (縣市, 鄉鎮市區, 子里) → 分割年（int；自備註欄擷取）
VILLAGE_SPLIT_YEARS = {}


def _parse_split_year(note):
    """自備註欄擷取「分割年」（第一個西元年），回傳 int 或 None。

    略過否定語脈絡者（如「非1995年」「原誤記為1995年分割」等，
    其前一個非空白字元為 非/誤/記/為/原），避免把「不是該年分割」誤讀成該年。
    備註若完全無西元年者（如「二戰後即分設」）→ None（不套用分割年判斷）。
    """
    for m in re.finditer(r"(\d{4})\s*年", note):
        pre = note[:m.start()].rstrip()
        if pre and pre[-1] in "非誤記為原":
            continue
        return int(m.group(1))
    return None


def _load_md(path=MD_PATH):
    """解析 `村里对应关系.md`，回填 VILLAGE_SPLITS / VILLAGE_SPLIT_YEARS。"""
    if not os.path.exists(path):
        print(f"  ⚠️ 母里對照表不存在：{path}（沿革合併停用）")
        return
    n_rows = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.replace("**", "").strip()
                     for c in line.strip("|").split("|")]
            if len(cells) < 6 or not cells[0].isdigit():
                continue        # 表頭 / 分隔列
            _, county, town, vill, parent, note = cells[:6]
            if not county or not town or not vill or not parent:
                continue
            parents = [p.strip() for p in re.split(r"[、，,]", parent) if p.strip()]
            if not parents:
                continue
            pairs = VILLAGE_SPLITS.setdefault((county, town), [])
            for p in parents:
                if (p, vill) not in pairs:
                    pairs.append((p, vill))
            ym = _parse_split_year(note)
            if ym:
                VILLAGE_SPLIT_YEARS[(county, town, vill)] = ym
            n_rows += 1
    print(f"  母里對照表：{n_rows} 列（{len(VILLAGE_SPLITS)} 鄉鎮市區、"
          f"{sum(len(v) for v in VILLAGE_SPLITS.values())} 組子→母里、"
          f"分割年 {len(VILLAGE_SPLIT_YEARS)} 筆）← {os.path.basename(os.path.dirname(os.path.dirname(path)))}/"
          f"maps/{os.path.basename(path)}")


_load_md()


# ============================================================================
# 鍵正規化：與底圖／得票資料同一套 core（去尾綴 + normalize）
# ============================================================================
def _core_vill(name, normalize):
    """去村里尾綴（里/村）後再正規化，使母里表用字與底圖／得票鍵收斂一致。"""
    s = str(name).strip()
    if s.endswith("里") or s.endswith("村"):
        s = s[:-1]
    return normalize(s)


def _core_town(name, normalize):
    """去鄉鎮市區尾綴（區/鎮/鄉/市）後再正規化。"""
    s = str(name).strip()
    if s and s[-1] in "區鎮鄉市":
        s = s[:-1]
    return normalize(s)


def build_split_index(normalize=lambda s: s, enabled=True):
    """(縣市, 鄉鎮市區, 子里) → [母里, ...]；同一子里可能有多個母里（合併案）。

    normalize 由呼叫端注入（與底圖／得票資料同一套正規化），
    使母里表用字與實際查表鍵收斂到一致。
    """
    idx = {}
    if not enabled:
        return idx
    for (county, town), pairs in VILLAGE_SPLITS.items():
        c, t = normalize(county), _core_town(town, normalize)
        for parent, child in pairs:
            idx.setdefault((c, t, _core_vill(child, normalize)), []).append(
                _core_vill(parent, normalize))
    return idx


def build_split_year_index(normalize=lambda s: s, enabled=True):
    """(縣市, 鄉鎮市區, 子里) → 分割年（int）。"""
    idx = {}
    if not enabled:
        return idx
    for (county, town, vill), year in VILLAGE_SPLIT_YEARS.items():
        idx[(normalize(county), _core_town(town, normalize),
             _core_vill(vill, normalize))] = year
    return idx


def resolve_unit_name(county, town, vill, exists_keys, split_index,
                      year=None, split_years=None):
    """回傳該里所對應的行政單元名稱（(縣市,鄉鎮,村里) 版）。

    本屆政策：
      自身名稱於當年資料中存在 → 用自身（底圖有、得票資料亦有，即不套沿革）；
      否則往上追溯沿革母里（可連續追溯）——**不因分割年 <= 選舉年而放棄**；
      母里亦查無資料 → 回傳該里自身（視為無資料留白）。
    （year / split_years 參數保留供相容，本屆不再據以否決併入。）
    """
    if (county, town, vill) in exists_keys:
        return vill
    parents = split_index.get((county, town, vill))
    if not parents:
        return vill
    for parent in parents:
        if (county, town, parent) in exists_keys:
            return parent
    cur, seen = parents[0], {vill}
    while cur and (county, town, cur) not in exists_keys and cur not in seen:
        seen.add(cur)
        nxt = split_index.get((county, town, cur))
        if not nxt:
            break
        cur = nxt[0]
    return cur


def split_note(county, town, vill, normalize=lambda s: s):
    """回傳「村里 vill 於選舉年尚未設立，母里：X+Y」之說明，無則空字串。

    用於缺資料報告第 1 節逐筆標註母里線索（供人工核對）。
    """
    c0, t0, v0 = normalize(county), _core_town(town, normalize), _core_vill(vill, normalize)
    parents = None
    for (c, t), pairs in VILLAGE_SPLITS.items():
        if normalize(c) == c0 and _core_town(t, normalize) == t0:
            ps = [p for p, ch in pairs if _core_vill(ch, normalize) == v0]
            if ps:
                parents = ps
                break
    if not parents:
        return ""
    y = None
    for (c, t, v), yr in VILLAGE_SPLIT_YEARS.items():
        if (normalize(c) == c0 and _core_town(t, normalize) == t0
                and _core_vill(v, normalize) == v0):
            y = yr
            break
    note = "母里：" + "+".join(_core_vill(p, normalize) for p in parents)
    if y is not None:
        note += f"（{y} 年分割）"
    return note
