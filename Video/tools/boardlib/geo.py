# -*- coding: utf-8 -*-
"""geo.py —— 由村里界 SHP dissolve 出行政區 GeoJSON。

取代 build_data.py 裡寫死的 COUNTYNAME == "新北市"，改由
meta.json 的 region.county 與 region.simplify 決定。

圖資版本隨「選舉年」切換
------------------------
內政部每次選舉前會公告當年度有效的村里界，村里界會調整（合併、分割、界線微調）。
看板畫的是「那場選舉當下的行政區」，所以不能一律用最新的一版圖資：

    year <  2019  ->  村里界歷史圖資_106（VILLAGE_MOI_1070205）
    year >= 2019  ->  現行村里界圖資_111（VILLAGE_MOI_1111118）

兩版圖資的欄位相同（COUNTYNAME / TOWNNAME / VILLNAME），但**編碼不同**：
106 版是 Big5（cp950），111 版是 UTF-8。強制用 UTF-8 讀 106 版會直接
`UnicodeDecodeError`，所以讀檔時逐一嘗試候選編碼，並用「這份圖資裡到不到得了
meta 指定的縣市」當作解碼是否正確的判準 —— 編碼錯了 COUNTYNAME 一定是亂碼，
縣市必然對不上，比只看有沒有丟例外可靠。

純代碼邊界測試不需要圖資檔時，可設環境變數 BOARD_GEO_SKIP=1。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd

# --------------------------------------------------------------------- 圖資來源
# 「2019 年以前」的分界。要調整年份分界（例如加入 108 年圖資）只需改這一個數字，
# 並在 SOURCES 補一筆對應區間。
HISTORICAL_CUTOFF_YEAR = 2019

# 歷史圖資根目錄（106 年版藏在 111 目錄底下，與 NewSolution 的取法一致）
_HIST_ROOT = r"D:\Windows\Documents\村里界歷史圖資_111"


@dataclass(frozen=True)
class Source:
    """一份村里界圖資，以及它適用的選舉年份區間（閉區間）。"""
    id: str
    label: str
    path: str
    encoding: str            # 首選編碼；讀不到會自動退回其他候選
    year_min: int
    year_max: Optional[int]  # None = 無上限

    def covers(self, year: int) -> bool:
        if year < self.year_min:
            return False
        return self.year_max is None or year <= self.year_max

    def as_provenance(self) -> Dict[str, Any]:
        """寫進快取、用來判斷快取是否過期的最小資訊集。"""
        return {
            "id": self.id,
            "label": self.label,
            "shp": os.path.basename(self.path),
            "encoding": self.encoding,
        }


SOURCES: Tuple[Source, ...] = (
    Source(
        id="moi106",
        label="村里界歷史圖資_106（VILLAGE_MOI_1070205）",
        path=os.path.join(_HIST_ROOT, "村里界歷史圖資_106",
                          "村里界歷史圖資_106", "VILLAGE_MOI_1070205.shp"),
        encoding="cp950",
        year_min=0,
        year_max=HISTORICAL_CUTOFF_YEAR - 1,      # 2018 與更早
    ),
    Source(
        id="moi111",
        label="現行村里界圖資_111（VILLAGE_MOI_1111118）",
        path=os.path.join(_HIST_ROOT, "村里界歷史圖資_111",
                          "VILLAGE_MOI_1111118.shp"),
        encoding="utf-8",
        year_min=HISTORICAL_CUTOFF_YEAR,          # 2019 與之後
        year_max=None,
    ),
)

# 未宣告年份時用哪一份（＝現行圖資）
DEFAULT_SOURCE_ID = "moi111"
DEFAULT_SHP = SOURCES[-1].path
# SHP_CANDIDATE_PATHS 相容舊名：外部若還有人 import 這兩個常數不會壞
SHP_CANDIDATE_PATHS = [s.path for s in SOURCES]

DEFAULT_SIMPLIFY = 60      # 公尺（epsg:3826 投影座標單位）
DEFAULT_ROUND = 5          # WGS84 座標小數位


def resolve_source(year: Optional[int] = None,
                   source_id: Optional[str] = None) -> Source:
    """依選舉年挑圖資；year 為 None 時回傳現行圖資。"""
    if source_id:
        for s in SOURCES:
            if s.id == source_id:
                return s
        raise ValueError("未知的圖資 id：%r（可用：%s）"
                         % (source_id, "、".join(s.id for s in SOURCES)))
    if year is None:
        return _by_id(DEFAULT_SOURCE_ID)
    for s in SOURCES:
        if s.covers(int(year)):
            return s
    raise ValueError("沒有任何圖資涵蓋 %r 年" % year)


def _by_id(sid: str) -> Source:
    for s in SOURCES:
        if s.id == sid:
            return s
    raise ValueError("未知的圖資 id：%r" % sid)


def describe_source(src: Source) -> str:
    """一行摘要，給 build 印出來。"""
    span = ("%d–" % src.year_min if src.year_max is None
            else "%d–%d" % (src.year_min, src.year_max))
    return "%s（%s，%s）" % (src.label, span, src.encoding)


# --------------------------------------------------------------------- 讀檔
def _candidate_encodings(preferred: Optional[str]) -> List[str]:
    """首選編碼優先，其餘候選依序補上（去重）。"""
    out: List[str] = []
    for enc in (preferred, "utf-8", "cp950", "big5"):
        if enc and enc not in out:
            out.append(enc)
    return out


def _read_county(src: Source,
                 county: str,
                 encoding: Optional[str] = None
                 ) -> Tuple["gpd.GeoDataFrame", str]:
    """讀 SHP 並確認解碼正確（縣市名對得上）。

    回傳 (GeoDataFrame, 實際用到的編碼)。
    """
    path = src.path
    if not os.path.isfile(path):
        raise FileNotFoundError("找不到村里界 shapefile：%s" % path)

    tried: List[str] = []
    county_err: Optional[Exception] = None
    enc_err: Optional[Exception] = None

    for enc in _candidate_encodings(encoding or src.encoding):
        try:
            gdf = gpd.read_file(path, encoding=enc)
        except Exception as e:                       # 編碼錯 / 檔案壞
            enc_err = enc_err or e
            tried.append("%s×（%s）" % (enc, e.__class__.__name__))
            continue

        if "COUNTYNAME" not in gdf.columns:
            enc_err = enc_err or KeyError("shapefile 沒有 COUNTYNAME 欄位")
            tried.append("%s×（無 COUNTYNAME）" % enc)
            continue

        names = gdf["COUNTYNAME"].dropna().unique().tolist()
        if not county or county in names:
            return gdf, enc

        county_err = ValueError(
            "shapefile 中找不到 COUNTYNAME == %r（讀到 %d 個縣市：%s）"
            % (county, len(names), "、".join(sorted(str(n) for n in names)[:6]) + "…"))
        tried.append("%s×（縣市對不上）" % enc)

    # 所有編碼都試過：若不是縣市名問題，就是編碼／檔案問題，把兩者都講清楚
    if county_err is not None:
        raise county_err
    raise RuntimeError("讀取 shapefile 失敗：%s（試過 %s）"
                       % (path, "、".join(tried))) from enc_err


def _round_geom(geom: Dict[str, Any], nd: int) -> Dict[str, Any]:
    def ring(r):
        return [[round(x, nd), round(y, nd)] for x, y in r]

    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [ring(c) for c in geom["coordinates"]]}
    return {"type": "MultiPolygon",
            "coordinates": [[ring(c) for c in poly] for poly in geom["coordinates"]]}


def build(county: str,
          shp: Optional[str] = None,
          simplify: float = DEFAULT_SIMPLIFY,
          nd: int = DEFAULT_ROUND,
          prop_key: str = "name",
          year: Optional[int] = None,
          source_id: Optional[str] = None,
          encoding: Optional[str] = None,
          source: Optional[Source] = None) -> Dict[str, Any]:
    """回傳 {county: FeatureCollection} 的 FeatureCollection。

    year        選舉年；<2019 走歷史圖資 106，否則走現行圖資 111。
    shp         直接指定 SHP 路徑（覆寫 year/source_id 的選擇）。
    encoding    直接指定編碼（覆寫來源預設；錯了仍會自動退回其他候選）。
    prop_key    決定 features[].properties 的欄位名（canonical 格式用 "name"）。
    """
    if source is None:
        if shp:
            source = Source(id="custom", label="自訂 SHP", path=shp,
                            encoding=encoding or "utf-8",
                            year_min=0, year_max=None)
        else:
            source = resolve_source(year, source_id)

    gdf, used_enc = _read_county(source, county, encoding)
    gdf = gdf[gdf["COUNTYNAME"] == county].copy()
    gdf = gdf[gdf["TOWNNAME"].notna() & gdf.geometry.notna()].copy()
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()
    if gdf.empty:
        raise ValueError("shapefile 中找不到 COUNTYNAME == %r 的图" % county)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    gdf = gdf.to_crs(epsg=3826)
    town = gdf.dissolve(by="TOWNNAME").reset_index()
    town["geometry"] = town["geometry"].simplify(simplify, preserve_topology=True)
    town = town.to_crs(epsg=4326)

    features = []
    for _, row in town.iterrows():
        geom = json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"]
        features.append({
            "type": "Feature",
            "properties": {prop_key: row["TOWNNAME"]},
            "geometry": _round_geom(geom, nd),
        })

    # 供呼叫端寫入快取；放在套件層函式回傳太囉唆，這裡掛在回傳物件上
    fc = {"type": "FeatureCollection", "features": features}
    fc["_source"] = dict(source.as_provenance(),
                         encoding=used_enc,
                         county=county,
                         simplify=float(simplify),
                         round=int(nd))
    return fc


def provenance_of(geojson: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """取出 build() 寫進去的來源資訊；舊快取沒有這個鍵就回 None。"""
    src = geojson.get("_source")
    return src if isinstance(src, dict) else None


# 判斷快取新舊時要比對的欄位。encoding 刻意不比 —— 它記的是「實際讀成功的那個」，
# 換來源時 shp 已經不同，不需要靠 encoding 間接推斷。
PROVENANCE_KEYS = ("id", "shp", "county", "simplify", "round")


def expected_provenance(county: str,
                        year: Optional[int] = None,
                        source_id: Optional[str] = None,
                        shp: Optional[str] = None,
                        simplify: float = DEFAULT_SIMPLIFY,
                        nd: int = DEFAULT_ROUND) -> Dict[str, Any]:
    """不讀檔，只算出「這次建置應該用哪份圖資」的來源資訊。

    與 build() 寫入 geojson["_source"] 的欄位對齊，用來判斷快取是否還有效。
    """
    if shp:
        src = Source(id="custom", label="自訂 SHP", path=shp,
                     encoding="utf-8", year_min=0, year_max=None)
    else:
        src = resolve_source(year, source_id)
    return dict(src.as_provenance(),
                county=county,
                simplify=float(simplify),
                round=int(nd))


def provenance_matches(cached: Optional[Dict[str, Any]],
                       want: Dict[str, Any]) -> bool:
    """快取裡的來源資訊是否與這次要用的相符。舊快取（None）一律視為過期。"""
    if not cached:
        return False
    return all(cached.get(k) == want.get(k) for k in PROVENANCE_KEYS)
