# -*- coding: utf-8 -*-
"""naming.py —— 素材檔名的單一來源。

所有看板共用同一組檔名，source/ 放原始素材、assets/ 放處理後的成品，
兩邊檔名一致。JS 端因此可以直接按名字取，不用查 meta.json。

固定對應：

  map.png              得票率地圖（source 為原始海報，assets 為擦除標題圖例後的成品）
  legend.png           得票率圖例
  city_seal.png        市徽
  emblem.png           日期塊底色的圓徽
  mark_elected.png     當選標誌
  party_<key>.png      政黨徽章，key 對齊 _engine/js/core/theme.js 的政黨 key

★ 沒有候選人照片這一項。看板不畫候選人照片（卡面只填政黨純色），
  所以建置端不找、也不要求任何 candidate/<key>.png。
  照片怎麼合成由使用者自行後製決定，見 _engine/js/render/layers.js。

檔名與 JS 的對應由本檔決定，不要在 layout.js / slide.js / meta.json 另寫一份。

engine_field 是 board.assets.js 內嵌備援 window.NT_ASSETS 的欄位名，
由 _engine/js/slide.js 讀取。
"""

from __future__ import annotations

import os
from typing import Dict, List, NamedTuple, Optional

# 透明化成品的統一落點（相對 Video/）。由 NewSolution/tool/build_assets.py 產生，
# 依「類別 / 年份」分層，見下面的 processed_relpath()。
PROCESSED_ROOT = os.path.join("NewSolution", "png", "processed")

# Video/ 根目錄（本檔在 Video/tools/boardlib/ 底下）
VIDEO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


class AssetSpec(NamedTuple):
    role: str            # 用途說明
    filename: str        # source/ 與 assets/ 共用的檔名
    engine_field: str    # window.NT_ASSETS 的欄位名
    required: bool       # 缺了會不會讓看板開天窗


# 順序即為 _template/meta.json 的 assets.required 順序
ASSETS = (
    AssetSpec("得票率地圖", "map.png", "voteMap", True),
    AssetSpec("得票率圖例", "legend.png", "legend", True),
    AssetSpec("市徽", "city_seal.png", "citySeal", True),
    AssetSpec("日期圓徽", "emblem.png", "emblem", True),
    AssetSpec("當選標誌", "mark_elected.png", "electedMark", True),
)

# 政黨徽章是動態的，格式另訂
PARTY_PATTERN = "party_%s.png"          # %s = 政黨 key（小寫）

DATA_FILENAME = "data.xlsx"


def by_role() -> Dict[str, AssetSpec]:
    return {a.role: a for a in ASSETS}


def by_filename() -> Dict[str, AssetSpec]:
    return {a.filename: a for a in ASSETS}


def engine_field(filename: str) -> Optional[str]:
    spec = by_filename().get(filename)
    return spec.engine_field if spec else None


def party_filename(party_key: str) -> str:
    return PARTY_PATTERN % party_key.lower()


def party_engine_field(party_key: str) -> str:
    """政黨 key -> window.NT_ASSETS 欄位名（kmt -> partyKmt）。"""
    return "party" + party_key.lower().capitalize()


def processed_relpath(filename: str, year=None, map_variant: str = "map") -> Optional[str]:
    """邏輯素材名 -> NewSolution/png/processed/ 下的相對路徑。

    這條約定就是「透明化成品放哪裡」的唯一來源，和 build_assets.py 的
    assets.map.json 一體兩面（那邊決定成品檔名，這邊決定它落在哪一層）。

        map.png / legend.png      map/<year>/map.png
        party_<key>.png           party/party_<key>.png
        city_seal.png 等靜態素材   share/<name>.png

    map_variant：得票率地圖的版本。預設 "map"（村里版）；"map2" 是區級版
    （只畫區、不畫里，同畫布同範圍）。兩者都是白底轉透明的成品，只是
    來源檔名不同，落點同在 map/<year>/ 下。由 meta.region.mapVariant 指定。

    沒有 year 就回 None —— 這些素材依年份分層，缺年份無法定位。
    """
    name = filename.replace("\\", "/")
    if name == "map.png":
        return "map/%s/%s.png" % (year, map_variant) if year else None
    if name == "legend.png":
        return "map/%s/legend.png" % year if year else None
    if name.startswith("party_"):
        return "party/" + name
    return "share/" + name


def processed_path(filename: str, year=None, map_variant: str = "map") -> Optional[str]:
    """邏輯素材名 -> 透明化成品在磁碟上的絕對路徑（不存在也照樣回傳）。"""
    rel = processed_relpath(filename, year, map_variant=map_variant)
    if rel is None:
        return None
    return os.path.join(VIDEO_ROOT, PROCESSED_ROOT, rel.replace("/", os.sep))


# 這些政黨是政黨本身有標章的，沒有徽章的政黨（如無黨籍）走預設色塊
PARTIES_WITH_MARK = ("kmt", "dpp", "tpp", "pfp", "nsc")


def party_needs_mark(candidates) -> List[str]:
    """回傳需要徽章的政黨 key（依出現順序，同政黨只列一次）。

    partyShort 不在 PARTIES_WITH_MARK 的一律不要求徽章 —— 無黨籍、
    聯盟、各國小黨沒有公開的標準標章，強行要求會擋住建置。
    """
    out = []
    for c in candidates:
        key = c["partyShort"].lower()
        if key in PARTIES_WITH_MARK and key not in out:
            out.append(key)
    return out


def required_filenames(candidates) -> List[str]:
    """給定候選人清單，回傳 source/ 必備檔名。"""
    names = [a.filename for a in ASSETS if a.required]
    names += [party_filename(k) for k in party_needs_mark(candidates)]
    return names


def describe_all(candidates) -> List[str]:
    """列出這個看板的完整素材清單，供 --list-assets 印出。"""
    lines = []
    for a in ASSETS:
        lines.append("%-22s %-22s %s"
                     % (a.filename, "engine_field=" + a.engine_field, a.role))
    for key in party_needs_mark(candidates):
        party = next(c["party"] for c in candidates
                     if c["partyShort"].lower() == key)
        lines.append("%-22s %-22s %s"
                     % (party_filename(key),
                        "engine_field=" + party_engine_field(key),
                        party + " 徽章"))
    return lines