# -*- coding: utf-8 -*-
"""canonical.py —— 唯一中間格式定義。

build 流程的中間產物固定為這份結構；它同時是 board.js 的內容來源
（只多包一層 window.BOARD = 與 assets 宣告），所以 Python 端算出來的
欄位名必須與 JS 端一致。

{
  "meta": {...},                 # 選舉資訊 + 補算的 pct / turnout
  "candidates": [                # 陣列，依 meta.candidates 順序
    {key, name, nameEn, party, partyShort, partyEn,
     number, votes, pct, share, elected}
  ],
  "districts": [                 # 依 valid 由大到小
    {name, short, villages,
     votes: {key: int},
     pct:   {key: float},
     valid, winnerKey, margin}
  ],
  "geojson": {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"name": "板橋區"}, "geometry": {...}}
  ]}
}
"""

from __future__ import annotations

# 沒有 photo：看板不畫候選人照片（見 render/layers.js 的 CandidateLayer）。
CANDIDATE_FIELDS = (
    "key", "name", "nameEn", "party", "partyShort", "partyEn",
    "number", "votes", "pct", "share", "elected",
)

DISTRICT_FIELDS = (
    "name", "short", "villages", "votes", "pct", "valid", "winnerKey", "margin",
)


def pct_of(votes: int, base: int) -> float:
    """佔有效票的百分比，兩位小數。base 為 0 時回 0.0。"""
    if not base:
        return 0.0
    return round(votes / base * 100, 2)


def share_of(votes: int, base: int) -> float:
    """佔實際投票數的百分比（含無效票為分母），兩位小數。"""
    if not base:
        return 0.0
    return round(votes / base * 100, 2)


def build_district(name, short, villages, votes, valid):
    """由逐里加總結果產生一個行政區物件。

    votes 為 {key: int}；winnerKey 取票數最高者（平手時依 key 排序取前者）。
    margin 為勝敗差距佔有效票的百分比。
    """
    pct = {k: pct_of(v, valid) for k, v in votes.items()}
    winner = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
    total_voted = sum(votes.values())
    top = votes[winner[0]]
    runner = max((v for k, v in votes.items() if k != winner[0]), default=0)
    return {
        "name": name,
        "short": short,
        "villages": villages,
        "votes": votes,
        "pct": pct,
        "valid": valid if valid else total_voted,
        "winnerKey": winner[0],
        "margin": pct_of(abs(top - runner), valid),
    }


def sort_districts(districts):
    """有效票由大到小；同票數時依名稱排序，確保輸出穩定可重現。"""
    return sorted(districts, key=lambda d: (-d["valid"], d["name"]))