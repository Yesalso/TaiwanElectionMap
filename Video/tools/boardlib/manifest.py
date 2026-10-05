# -*- coding: utf-8 -*-
"""manifest.py —— 讀 meta.json、驗欄位、解析路徑。

meta.json 是唯一的人工設定來源；xlsx 只提供「哪一欄是誰、多少票」，
候選人名單、號次、政黨、官方總票與選舉資訊一律在此宣告。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import naming

# meta.json 中 image / source 檔名合法的副檔名
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")

# 必填欄位：候選人至少要有一個，且要有 key
REQUIRED_TOP = ("id", "meta", "candidates", "region")
REQUIRED_META = ("election", "year", "date", "office")
REQUIRED_CANDIDATE = ("key", "name", "party", "partyShort", "number")
REQUIRED_REGION = ("county", "unitLevel")


class ManifestError(Exception):
    """meta.json 內容或路徑有問題。"""


@dataclass
class Board:
    board_dir: str
    source_dir: str
    assets_dir: str
    out_dir: str
    meta: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    region: Dict[str, Any]

    # ---------------------------------------------------------------- 屬性
    @property
    def id(self) -> str:
        return self.meta["id"]

    @property
    def unit_level(self) -> str:
        """'village' 或 'town'；決定 xlsx 逐列的聚合層級。"""
        return self.region["unitLevel"]

    @property
    def county(self) -> str:
        """SHP 的 COUNTYNAME，用來過濾行政區邊界。"""
        return self.region["county"]

    @property
    def year(self) -> int:
        """選舉年；決定 geojson 由哪一版村里界圖資 dissolve 出來。

        < 2019 走村里界歷史圖資 106（VILLAGE_MOI_1070205），
        >= 2019 走現行圖資 111（VILLAGE_MOI_1111118）。
        例外情況可在 region 宣告覆寫：
            region.geoSource  圖資 id（見 boardlib.geo.SOURCES）
            region.shp        直接指定 SHP 路徑（優先於 geoSource / year）
        """
        try:
            return int(self.meta["year"])
        except (TypeError, ValueError):
            raise ManifestError("meta.year 必須是西元年數字，現為 %r"
                                % self.meta.get("year"))

    @property
    def geo_source(self) -> Optional[str]:
        """region.geoSource：強制指定圖資版本（少用，例：補選沿用舊界）。"""
        return self.region.get("geoSource")

    @property
    def geo_shp(self) -> Optional[str]:
        """region.shp：直接指定 SHP 路徑（少用）。"""
        return self.region.get("shp")

    @property
    def map_variant(self) -> str:
        """region.mapVariant：得票率地圖用哪一版。

        預設 "map"（村里版）；"map2" = 區級版（只畫區、不畫里，同畫布同範圍）。
        建置時據此到 NewSolution/png/processed/map/<year>/<variant>.png 找圖，
        其餘版面完全不變 —— 同一場資料可以出「村里版」與「區級版」兩張看板。
        """
        v = self.region.get("mapVariant") or "map"
        if v not in ("map", "map2"):
            raise ManifestError("region.mapVariant 只能是 'map' 或 'map2'，"
                                "現為 %r" % v)
        return v

    @property
    def candidate_keys(self) -> List[str]:
        return [c["key"] for c in self.candidates]

    @property
    def layout(self) -> Dict[str, Any]:
        """版面微調覆寫值，無則空 dict。"""
        return self.meta.get("layout", {}) or {}

    @property
    def party_themes(self) -> Dict[str, str]:
        """政黨 key -> 十六進位色碼。"""
        return self.meta.get("partyThemes", {}) or {}

    @property
    def assets_cfg(self) -> Dict[str, Any]:
        return self.meta.get("assets", {}) or {}

    @property
    def title(self) -> str:
        return "%s %s" % (self.meta["year"], self.meta["election"])

    # ---------------------------------------------------------------- 路徑
    def source_file(self, name: str) -> str:
        """source/ 下的資料檔（xlsx）。"""
        return os.path.join(self.source_dir, name)

    def source_image(self, name: str) -> str:
        """source/ 下的圖檔；副檔名不存在時自動補 .png。"""
        if not name:
            raise ManifestError("圖檔名稱為空字串")
        if not name.lower().endswith(IMAGE_EXT):
            name += ".png"
        return os.path.join(self.source_dir, name)

    def out_asset(self, name: str) -> str:
        """assets/ 下的產出路徑（目錄會自動建立）。"""
        p = os.path.join(self.assets_dir, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p


def _require(obj: Dict[str, Any], keys, where: str) -> None:
    missing = [k for k in keys if obj.get(k) in (None, "", [])]
    if missing:
        raise ManifestError("%s 缺少必填欄位：%s" % (where, "、".join(missing)))


def load_meta(board_dir: str) -> Dict[str, Any]:
    path = os.path.join(board_dir, "meta.json")
    if not os.path.isfile(path):
        raise ManifestError("找不到 meta.json：%s" % path)
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestError("meta.json 格式錯誤：%s（行 %d 欄 %d）"
                                % (e.msg, e.lineno, e.colno))


def _normalise_candidates(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """統一欄位名，並驗 key 唯一、votes 為非負整數。"""
    out: List[Dict[str, Any]] = []
    seen = set()
    for i, c in enumerate(raw):
        _require(c, REQUIRED_CANDIDATE, "candidates[%d]" % i)
        key = c["key"]
        if key in seen:
            raise ManifestError("候選人 key 重複：%s" % key)
        seen.add(key)
        votes = c.get("votes")
        if votes is not None and (not isinstance(votes, int) or votes < 0):
            raise ManifestError("candidates[%d].votes 必須是非負整數，現為 %r"
                                % (i, votes))
        out.append({
            "key": key,
            "name": c["name"],
            "nameEn": c.get("nameEn", ""),
            "party": c["party"],
            "partyShort": c["partyShort"],
            "partyEn": c.get("partyEn", ""),
            "number": c["number"],
            "votes": votes,
            "elected": bool(c.get("elected", False)),
            # 選用欄位：引擎端據此覆寫政黨色 / 指定卡片分槽，
            # 未宣告時保持 undefined，不影響既有看板的輸出。
            "color": c.get("color"),
            "slot": c.get("slot"),
        })
    return out


def resolve(board_dir: str) -> Board:
    """讀取並驗證 board 目錄，回傳 Board 物件。"""
    board_dir = os.path.abspath(board_dir)
    if not os.path.isdir(board_dir):
        raise ManifestError("board 目錄不存在：%s" % board_dir)

    raw = load_meta(board_dir)
    _require(raw, REQUIRED_TOP, "meta.json")

    meta = dict(raw["meta"])
    _require(meta, REQUIRED_META, "meta")
    meta.setdefault("id", raw["id"])
    meta["id"] = raw["id"]

    candidates = _normalise_candidates(raw["candidates"])
    region = dict(raw["region"])
    _require(region, REQUIRED_REGION, "region")
    if region["unitLevel"] not in ("village", "town"):
        raise ManifestError("region.unitLevel 只能是 'village' 或 'town'，"
                            "現為 %r" % region["unitLevel"])

    return Board(
        board_dir=board_dir,
        source_dir=os.path.join(board_dir, "source"),
        assets_dir=os.path.join(board_dir, "assets"),
        out_dir=board_dir,
        meta=meta,
        candidates=candidates,
        region=region,
    )


def check_sources(board: Board) -> List[str]:
    """檢查 source/ 必備檔案，回傳缺少的檔名清單（空 = 齊備）。

    必備：data.xlsx（unitLevel 為 village 時）、naming 宣告的每張圖。
    候選人照片不在清單內 —— 看板不畫照片，建置端不需要它。
    """
    missing: List[str] = []

    if board.unit_level == "village":
        if not os.path.isfile(board.source_file("data.xlsx")):
            missing.append("data.xlsx")

    for name in naming.required_filenames(board.candidates):
        if not os.path.isfile(board.source_image(name)):
            missing.append(name)

    return sorted(set(missing))


def describe(board: Board) -> str:
    """一行摘要，給 build 開頭印出來。"""
    return "%s | %s | 候選人 %d 位 | 單位 %s | 縣市 %s" % (
        board.id, board.title, len(board.candidates), board.unit_level, board.county)