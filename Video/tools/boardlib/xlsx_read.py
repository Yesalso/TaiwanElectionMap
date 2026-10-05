# -*- coding: utf-8 -*-
"""xlsx_read.py —— 村里得票 xlsx 版面適配器。

資料分工約定：xlsx 只回答「哪一欄是誰、多少票」，候選人名單一律來自
meta.json。适配器因此不需要「發現候選人」的能力，只要能把欄位對到 key。

已支援的版面（依 sheet 名與表頭自動偵測）：

A  10 欄雙候選，無表頭。每 5 欄一組：里名、候選人、號次、票數、得票率。
   坑：第 3/8 欄是「號次」不是票數，票數在第 4/9 欄。
   出現：2010/2014/2018 新北、台北縣 2001。
B  各里彙總標準檔，有表頭，欄名為「<候選人>得票數」。
   出現：2014_得票數、2022、2010_高雄格式。
C  鄉鎮市區彙總 + 村里層級明細，欄名「<候選人>（NN）_得票數」，值為字串。
   出現：1993 / 1997。使用舊行政名，需 historical_areas 做映射。
D  各里彙總純得票率，只有「得票率」沒有「得票數」。
   出現：1993 / 1997 / 2010 / 2014 / 2018 的「_得票率」檔。
E  候選人即欄名，第 2 行為表頭，含「縣市/鄉鎮市區/區里」。
   出現：2005。
F  鄉鎮層單表，含「鄉鎮市」與「有效票數」。出現：1989。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

# 版面 A 每組候選人的欄數
A_GROUP = 5
A_VOTE_OFFSET = 3        # 組內第 4 欄（0 起算）是票數，不是第 3 欄的號次

# 行政區欄名的正規化：去掉「區/縣/市/鄉/鎮」以外的雜訊
_DISTRICT_TAIL = "區縣市鄉鎮"


class XlsxError(Exception):
    """xlsx 內容無法解析。"""


def _clean(value: Any) -> Any:
    """去掉字串前後空白與全形空白；數字字串轉 int；空值回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip().replace("\u3000", "").replace("\xa0", "")
    if not s or s in ("-", "--", "—"):
        return None
    try:
        f = float(s.replace(",", ""))
    except ValueError:
        return s
    return int(f) if f == int(f) else f


def _rows(ws, limit: Optional[int] = None):
    n = 0
    for row in ws.iter_rows(values_only=True):
        yield [_clean(v) for v in row]
        n += 1
        if limit and n >= limit:
            return


# 表頭必須含這些字樣才算數；單純出現「里」不足以判斷，
# 因為版面 A 的資料列本身就寫著「新北市板橋區留侯里」。
_HEADER_KEYWORDS = ("選舉區", "鄉(鎮", "鄉鎮", "候選人", "得票", "區里", "里名", "村里")


def _is_header(value: Any) -> bool:
    return isinstance(value, str) and any(kw in value for kw in _HEADER_KEYWORDS)


def _looks_like_layout_a(rows, width: int) -> bool:
    """版面 A 的特徵：欄數為 5 的倍數，且每組第 3 欄是 1~99 的小整數（號次）、
    第 4 欄是更大的整數（票數）。沒有任何表頭列。"""
    if width % A_GROUP or width < A_GROUP:
        return False
    groups = width // A_GROUP
    for g in range(groups):
        number_col = g * A_GROUP + 2      # 組內第 3 欄
        vote_col = g * A_GROUP + A_VOTE_OFFSET
        nums = [r[number_col] for r in rows[:20]
                if len(r) > vote_col and isinstance(r[number_col], int)]
        votes = [r[vote_col] for r in rows[:20] if len(r) > vote_col
                 and isinstance(r[vote_col], int)]
        if not nums or not votes:
            return False
        if not (1 <= min(nums) <= 99):
            return False
        if max(nums) >= max(votes):
            return False
    return True


def _find_header_row(rows, limit: int = 6) -> Optional[int]:
    """回傳第一列看起來像表頭的索引，找不到回 None。"""
    for i, r in enumerate(rows[:limit]):
        if sum(1 for v in r if _is_header(v)) >= 2:
            return i
    return None


def split_district(full_name: str) -> Tuple[str, str]:
    """把「新北市板橋區留侯里」拆成 (「板橋區」, 「留侯里」)。

    回傳的全名沿用來源寫法（可能是「板橋區」也可能是舊的「板橋市」），
    交由呼叫端決定要不要套 historical_areas 映射。
    """
    s = str(full_name)
    for city in ("新北市", "臺北市", "台北市", "高雄市", "桃園市", "臺中市", "台中市"):
        if s.startswith(city):
            s = s[len(city):]
            break
    m = re.match(r"^(.+?[" + _DISTRICT_TAIL + r"])(.*)$", s)
    if m:
        return m.group(1), m.group(2)
    return "", s


def short_name(district: str) -> str:
    """行政區簡稱：去掉結尾的「區/市/鎮/鄉」，留 2~3 字。"""
    s = str(district)
    if s and s[-1] in _DISTRICT_TAIL:
        s = s[:-1]
    return s or str(district)


# ---------------------------------------------------------------- 版面 A
def _read_layout_a(ws, name_to_key, meta_by_name):
    """10 欄、每 5 欄一組的無表頭版面。回傳 {里全名: {key: votes}}。"""
    rows = list(_rows(ws))
    if not rows:
        return {}
    width = max(len(r) for r in rows)
    groups = width // A_GROUP
    if groups < 1:
        raise XlsxError("Sheet「%s」欄數 %d 不足，無法解析為版面 A"
                        % (ws.title, width))

    # 逐一組別確認第 2 欄是候選人姓名，並對到 key
    key_by_group: Dict[int, str] = {}
    for g in range(groups):
        col = g * A_GROUP + 1          # 組內第 2 欄（0 起算 index 1）
        probe = next((r[col] for r in rows[:20]
                      if len(r) > col and isinstance(r[col], str)), None)
        if probe is None:
            raise XlsxError("版面 A 第 %d 組找不到候選人姓名欄" % (g + 1))
        key = _lookup_key(probe, name_to_key, meta_by_name)
        if key is None:
            raise XlsxError(
                "版面 A 第 %d 組的候選人「%s」不在 meta.json 的候選人名單中"
                % (g + 1, probe))
        key_by_group[g] = key

    out: Dict[str, Dict[str, int]] = {}
    for r in rows:
        name = r[0] if r else None
        if not isinstance(name, str) or not name:
            continue
        votes = out.setdefault(name, {})
        for g, key in key_by_group.items():
            i = g * A_GROUP + A_VOTE_OFFSET
            if len(r) > i and isinstance(r[i], (int, float)):
                votes[key] = votes.get(key, 0) + int(r[i])
    return out


# ---------------------------------------------------------------- 版面 B / C / E
_NAME_COL_RE = re.compile(r"^(?P<name>.+?)(?:（\s*(?P<num>\d+)\s*）|\((?P<num2>\d+)\))?[_]?得票數$")


def _match_vote_header(text: str, name_to_key, meta_by_name):
    """表頭「游錫堃得票數」/「游錫堃（1）_得票數」/「張家豪（01，台灣動物保護黨）_得票數」-> key。

    最後一種是 GetData.py 產的逐里檔（2022 等）常見寫法：括號裡同時放了號次與政黨，
    所以要把括號內容拆開，人名只取括號之前的部分，號次從括號裡撈。
    """
    m = _NAME_COL_RE.match(str(text).strip())
    if not m:
        return None
    name = m.group("name").strip()
    num = m.group("num") or m.group("num2")

    # 「張家豪（01，台灣動物保護黨）」→ name=張家豪, num=01
    pm = re.match(r"^(?P<n>.+?)\s*[（(](?P<inner>[^）)]*)[）)]\s*$", name)
    if pm:
        name = pm.group("n").strip()
        inner = pm.group("inner")
        dm = re.search(r"\d+", inner)
        if num is None and dm:
            num = dm.group(0)

    key = _lookup_key(name, name_to_key, meta_by_name)
    if key is None and num:
        for c in meta_by_name.values():
            if str(c.get("number")) == str(num).lstrip("0") or str(c.get("number")) == num:
                key = c["key"]
                break
    return key


def _read_by_header(ws, name_to_key, meta_by_name, valid_markers=None):
    """有表頭、候選人寫在欄名的版面（B / C / E 通用）。"""
    rows = list(_rows(ws))
    hi = _find_header_row(rows)
    if hi is None:
        raise XlsxError("Sheet「%s」找不到表頭列" % ws.title)
    header = rows[hi]

    col_key: Dict[int, str] = {}
    valid_col: List[int] = []
    rate_cols: set = set()
    for i, v in enumerate(header):
        if not isinstance(v, str):
            continue
        if "得票率" in v:
            # 得票率欄的值是 "42.29%" 這種字串，必須排除，
            # 否則會被當成「村名」（掃最後一個字串欄時會誤中）
            rate_cols.add(i)
            continue
        key = _match_vote_header(v, name_to_key, meta_by_name)
        if key:
            col_key[i] = key
            continue
        if valid_markers and any(mk in v for mk in valid_markers):
            valid_col.append(i)

    if not col_key:
        raise XlsxError("Sheet「%s」的表頭找不到任何候選人得票欄；"
                        "meta.json 的候選人名單對不上嗎？" % ws.title)

    # 地區欄：優先「鄉鎮市區」（要拆得出行政區），其次選舉區/區里，最後才是縣市
    district_col = None
    for pref in ("鄉鎮", "選舉區", "區里", "村里", "縣市"):
        for i, v in enumerate(header):
            if i in col_key or i in valid_col or i in rate_cols:
                continue
            if isinstance(v, str) and pref in v:
                district_col = i
                break
        if district_col is not None:
            break

    out: Dict[str, Dict[str, int]] = {}
    for r in rows[hi + 1:]:
        if not r:
            continue
        first = next((v for v in r if v is not None), None)
        if first is None:
            continue
        if isinstance(first, str) and ("合計" in first or "總計" in first):
            continue
        # 村名：取最後一個字串欄（排除候選人欄、有效票欄、得票率欄與行政區欄）
        village = None
        for i in range(len(r) - 1, -1, -1):
            if i in col_key or i in rate_cols or i == district_col:
                continue
            if valid_col and i in valid_col:
                continue
            if isinstance(r[i], str):
                village = r[i]
                break
        if village is None:
            continue
        district = r[district_col] if district_col is not None and district_col < len(r) else None
        label = "%s%s" % (district, village) if isinstance(district, str) else village
        votes = out.setdefault(label, {})
        for i, key in col_key.items():
            if i < len(r) and isinstance(r[i], (int, float)):
                votes[key] = votes.get(key, 0) + int(r[i])
        if valid_col:
            for i in valid_col:
                if i < len(r) and isinstance(r[i], (int, float)):
                    votes.setdefault("__valid__", 0)
                    votes["__valid__"] += int(r[i])
    return out


# ---------------------------------------------------------------- 版面 F
def _read_layout_f(ws, name_to_key, meta_by_name):
    """鄉鎮層單表：欄名含「鄉鎮市」，逐欄為候選人得票。"""
    rows = list(_rows(ws))
    hi = _find_header_row(rows)
    if hi is None:
        raise XlsxError("Sheet「%s」找不到表頭列" % ws.title)
    header = rows[hi]

    col_key: Dict[int, str] = {}
    for i, v in enumerate(header):
        if not isinstance(v, str):
            continue
        if "得票" not in v and "票數" not in v:
            continue
        name = re.sub(r"[(（].*?[)）]", "", v).replace("_", "").replace("得票數", "").replace("得票", "").strip()
        key = _lookup_key(name, name_to_key, meta_by_name)
        if key:
            col_key[i] = key
    if not col_key:
        raise XlsxError("Sheet「%s」找不到候選人得票欄" % ws.title)

    out: Dict[str, Dict[str, int]] = {}
    for r in rows[hi + 1:]:
        if not r:
            continue
        first = next((v for v in r if v is not None), None)
        if isinstance(first, str) and ("合計" in first or "總計" in first):
            continue
        town = next((v for v in r if isinstance(v, str) and "鄉" in v or
                     isinstance(v, str) and ("鎮" in v or "市" in v)), None)
        if town is None:
            continue
        votes = out.setdefault(town, {})
        for i, key in col_key.items():
            if i < len(r) and isinstance(r[i], (int, float)):
                votes[key] = votes.get(key, 0) + int(r[i])
    return out


def _lookup_key(name: str, name_to_key, meta_by_name):
    if not name:
        return None
    name = str(name).strip()
    if name in name_to_key:
        return name_to_key[name]
    if name in meta_by_name:
        return meta_by_name[name]["key"]
    # 去掉前後空白与全形空白后再试一次
    n2 = name.replace("\u3000", "").replace("\xa0", "")
    if n2 in name_to_key:
        return name_to_key[n2]
    # 以「姓」比對：同姓不同字（立倫/立伦）
    if len(n2) >= 2:
        for full, key in name_to_key.items():
            if full[:1] == n2[:1] and abs(len(full) - len(n2)) <= 1:
                return key
    return None


# ---------------------------------------------------------------- 偵測
def detect_layout(ws, name_to_key, meta_by_name) -> str:
    rows = list(_rows(ws, limit=8))
    if not rows:
        raise XlsxError("Sheet「%s」是空的" % ws.title)
    width = max(len(r) for r in rows)

    first = next((v for r in rows for v in r if v is not None), None)
    title = ws.title or ""

    if "鄉" in title and "鄉" in str(first):
        return "F"
    # 版面 A 優先於表頭判斷：它的資料列本身就長得像表頭
    if _looks_like_layout_a(rows, width):
        return "A"
    hi = _find_header_row(rows)
    if hi is not None:
        header = rows[hi]
        if any(isinstance(v, str) and ("區里" in v or "里名" in v or "村里" in v)
               for v in header):
            return "E"
        if any(isinstance(v, str) and "得票數" in v for v in header):
            return "B"
        if any(isinstance(v, str) and "得票率" in v for v in header):
            return "D"
        return "B"
    return "A"


def read_units(xlsx_path: str, candidates, sheet: Optional[str] = None):
    """讀村里（或鄉鎮）得票。

    回傳 (units, layout, sheet_title)：
      units 為 {單位全名: {key: 票數}}，可能含 '__valid__' 有效票欄
      layout 為偵測到的版面代號 A/B/C/D/E/F
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    name_to_key = {c["name"]: c["key"] for c in candidates}
    meta_by_name = {c["name"]: c for c in candidates}

    if sheet:
        if sheet not in wb.sheetnames:
            raise XlsxError("找不到 sheet「%s」，现有：%s"
                            % (sheet, "、".join(wb.sheetnames)))
        ws = wb[sheet]
        layout = detect_layout(ws, name_to_key, meta_by_name)
        return _dispatch(ws, layout, name_to_key, meta_by_name), layout, ws.title

    # 未指定 sheet：依版面分派挑第一个读得动的
    errors = []
    for ws in wb.worksheets:
        try:
            layout = detect_layout(ws, name_to_key, meta_by_name)
            units = _dispatch(ws, layout, name_to_key, meta_by_name)
            if units:
                return units, layout, ws.title
        except XlsxError as e:
            errors.append("%s: %s" % (ws.title, e))
    raise XlsxError("所有 sheet 都無法解析出逐里得票：\n  " + "\n  ".join(errors))


def _dispatch(ws, layout, name_to_key, meta_by_name):
    if layout == "A":
        return _read_layout_a(ws, name_to_key, meta_by_name)
    if layout == "F":
        return _read_layout_f(ws, name_to_key, meta_by_name)
    if layout == "D":
        raise XlsxError(
            "Sheet「%s」是純得票率版面（D），沒有逐里票數。"
            "source/data.xlsx 請改用「_得票數」或含票數的檔案。" % ws.title)
    return _read_by_header(ws, name_to_key, meta_by_name,
                           valid_markers=("有效票",))


def read_official_totals(xlsx_path: str):
    """讀「新北市」那種合計 sheet，取有效票 / 無效票 / 投票數 / 選舉人數。

    回傳 dict，欄位為 vote_cast、valid、invalid、electorate、turnout，
    缺什麼就少什麼，不會補 0。
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        rows = list(_rows(ws, limit=4))
        if not rows:
            continue
        header = rows[0]
        joined = " ".join(str(v) for v in header if isinstance(v, str))
        if not any(k in joined for k in ("無效票", "投票數", "選舉人數", "投票率")):
            continue
        total_row = None
        for r in rows[1:]:
            first = next((v for v in r if v is not None), None)
            if isinstance(first, str) and ("合計" in first or "總計" in first):
                total_row = r
                break
        if total_row is None:
            continue
        out = {}
        for i, v in enumerate(header):
            if not isinstance(v, str) or i >= len(total_row):
                continue
            val = total_row[i]
            if not isinstance(val, (int, float)):
                continue
            if "無效票" in v:
                out["invalid"] = int(val)
            elif "投票數" in v and "率" not in v:
                out["vote_cast"] = int(val)
            elif "選舉人數" in v:
                out["electorate"] = int(val)
            elif "投票率" in v:
                out["turnout"] = round(float(val), 2)
        if out:
            return out
    return {}


def read_rates(xlsx_path: str, candidates, sheet: Optional[str] = None):
    """讀純得票率檔（D 版面），回傳 {單位全名: {key: pct}}。"""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    name_to_key = {c["name"]: c["key"] for c in candidates}
    meta_by_name = {c["name"]: c for c in candidates}

    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows = list(_rows(ws))
    hi = _find_header(rows)
    if hi is None:
        raise XlsxError("得票率檔找不到表頭列")

    col_key: Dict[int, str] = {}
    for i, v in enumerate(rows[hi]):
        if not isinstance(v, str) or "得票率" not in v:
            continue
        name = re.sub(r"得票率.*$", "", v).strip()
        key = _lookup_key(name, name_to_key, meta_by_name)
        if key is None:
            # 退而求其次：以「中國國民黨得票率」-> 依 meta 順序配對
            keys = [c["key"] for c in candidates]
            if len(keys) >= 1:
                key = keys[0] if "國民" in name else (keys[1] if len(keys) > 1 else None)
        if key:
            col_key[i] = key

    out: Dict[str, Dict[str, float]] = {}
    for r in rows[hi + 1:]:
        village = None
        for i in range(len(r) - 1, -1, -1):
            if i in col_key:
                continue
            if isinstance(r[i], str):
                village = r[i]
                break
        if village is None:
            continue
        district = next((v for v in r if isinstance(v, str) and v[-1:] in _DISTRICT_TAIL), "")
        label = "%s%s" % (district, village) if district else village
        vals = {}
        for i, key in col_key.items():
            if i < len(r) and isinstance(r[i], (int, float)):
                vals[key] = round(float(r[i]) / 100, 5)
        if vals:
            out[label] = vals
    return out