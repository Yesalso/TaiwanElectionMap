# -*- coding: utf-8 -*-
"""
build_map_assets.py — 把海報地圖轉成看板可用的透明底 PNG

★ 依使用者指示：**只去海色、只等比例縮放，不做任何剪裁**。
  金馬離島面板、右上角圖例小方框、大陸輪廓、標題圖例 —— 海報裡有什麼就保留什麼，
  空間上一律不挖不切（先前挖大陸、切方框、抽離島的邏輯全部移除）。
  縮放由渲染器的 contain()（等比例 contain 進框）完成，素材本身保持原尺寸。

★ 2026-11-20：地圖來源改為 `map/` 支線新產出的 party_lead 系列（四張，均 3203×4404）：
    主圖 1  ← legislative_district_2024_party_lead_map.png    （選區級）
    主圖 2  ← legislative_township_2024_party_lead_map.png    （鄉鎮市區級）
    輔圖 1  ← legislative_election_2024_party_lead_map.png    （選舉得票級）
    輔圖 2  ← legislative_county_2024_party_lead_map.png      （縣市級）
  舊的 `video/2024.png`（鄉鎮）/ `video/2024-2.png`（縣市）不再使用。
"""

import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")

# 1992-2024/map（同層）與 2008-2024/map（上兩層）
MAP_1992 = os.path.join(HERE, os.pardir, "map")
MAP_2008 = os.path.join(HERE, os.pardir, os.pardir, "2008-2024", "map")

JOBS = [
    # (來源, 輸出, 角色)
    (os.path.join(MAP_1992, "legislative_district_2024_party_lead_map.png"),
     "tw2024_district.png", "主圖 1 · 選區級"),
    (os.path.join(MAP_2008, "legislative_township_2024_party_lead_map.png"),
     "tw2024_township.png", "主圖 2 · 鄉鎮市區級"),
    (os.path.join(MAP_1992, "legislative_election_2024_party_lead_map.png"),
     "tw2024_election.png", "輔圖 1 · 選舉得票級"),
    (os.path.join(MAP_2008, "legislative_county_2024_party_lead_map.png"),
     "tw2024_county.png", "輔圖 2 · 縣市級"),
]

SEA = np.array([50, 50, 50])             # 海報底色 #323232


def build(src, dst, role="", tol=14):
    """整張海報 → 透明底 PNG：只有「海色 → alpha 0」這一步，其餘原樣保留。"""
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w = a.shape[:2]

    fg = np.abs(a - SEA).max(axis=2) > tol

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = a.astype(np.uint8)
    rgba[..., 3] = (fg * 255).astype(np.uint8)

    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, dst)
    Image.fromarray(rgba, "RGBA").save(out)
    print(f"{role}：{os.path.basename(src)} → {dst}  {w}×{h}  整張保留（僅去海色，無剪裁）")
    return out


if __name__ == "__main__":
    for s, d, r in JOBS:
        build(s, d, r)
