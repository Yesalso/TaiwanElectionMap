# -*- coding: utf-8 -*-
"""boardlib —— 選舉看板建置工具庫。

模組分工：
  manifest.py   讀 meta.json、驗欄位、解析路徑
  canonical.py  定義唯一中間格式（Python / JS 共用）
  xlsx_read.py  村里得票 xlsx 版面適配器
  geo.py        由村里界 SHP dissolve 出行政區 GeoJSON
  assets.py     素材處理（地圖 / 圖例 / 市徽 / 圓徽 / 政黨徽 / 候選人去背）
"""

__all__ = ["manifest", "canonical", "xlsx_read", "geo", "assets"]