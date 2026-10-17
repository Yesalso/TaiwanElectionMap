# boards/ —— 選舉看板

每一場選舉一個目錄，資料與素材只放一份；`_engine/` 是所有場次共用的程式碼。

```
boards/
  _engine/                     共用引擎（css/ + js/），只有一份
  _template/                   空白模板，開新場時複製這個目錄
  2014-newtpei-mayor/          第一場
    index.html                 薄殼：只引 ../_engine/… 與 ./board.js
    meta.json                  ★ 人工維護：選舉資訊、候選人（不含素材檔名）
    board.js                   build 產生：window.BOARD = {…}
    board.assets.js            build 產生：window.BOARD_ASSETS / window.NT_ASSETS
    .cache/geojson.json        由 SHP dissolve 的快取（可安全刪除）
    source/                    ★ 人工放入的原始素材（建置不改這裡）
      data.xlsx
      map.png  legend.png  city_seal.png  emblem.png  mark_elected.png
      party_kmt.png  party_dpp.png
    assets/                    舊場次的回退素材（★ 新場次不再往這裡寫）
      map.png  legend.png  city_seal.png  emblem.png  mark_elected.png
      party_kmt.png  party_dpp.png
```

★ **透明化成品不在 `boards/<id>/assets/`**，全部集中在
`NewSolution/png/processed/`（產生者：`NewSolution/tool/build_assets.py`）。
`assets/` 只剩舊場次的回退來源，見 `NewSolution/README.md`。

## 兩份人工檔的分工

| 檔案 | 放什麼 |
|---|---|
| `meta.json` | 選舉名稱、年份、日期、職位、候選人名單（key／姓名／政黨／號次／官方總票／當選）、縣市、版面微調 |
| `source/data.xlsx` | 只有逐里得票數 |
| `source/*.png` | 原始素材，檔名見下表 |

## 素材檔名（固定，不可改）

`source/` 放原始素材、`assets/` 放處理後的成品，**兩邊檔名相同**。
JS 端因此可以直接按名字取，不必查 meta.json。規則定義在
`tools/boardlib/naming.py`，是唯一來源。

| 檔名 | 用途 | source/ 的內容 | assets/ 的內容 |
|---|---|---|---|
| `map.png` | 得票率地圖 | 原始海報（2014 是 9824 × 7365，含標題與圖例） | 擦除標題圖例、縮到 2400 寬的成品 |
| `legend.png` | 得票率圖例 | 原始圖例 | 裁邊、切掉頂端標題 |
| `city_seal.png` | 頁眉左上角市徽 | 原始市徽 | 去背透明 |
| `emblem.png` | 日期塊底色圓徽 | 原始國徽 | 只留內切圓 |
| `mark_elected.png` | 姓名旁當選標誌 | 原始選舉章 | 去背透明 |
| `party_<key>.png` | 政黨徽章 | 原始黨徽 | 只留內切圓 |

`<key>` 一律小寫，政黨用 theme.js 的政黨 key（`kmt` / `dpp` / `tpp` / `pfp` / `nsc`）。

**沒有候選人照片這一項。** 看板不畫候選人照片 —— 主卡、小卡、頁眉現任者頭像
都只填一塊政黨純色（`_engine/js/render/layers.js`），照片怎麼合成由使用者
自行後製決定。所以 meta.json 不需要 `photo` / `cardSize`，建置端也不找這張圖。

沒有標準標章的政黨（無黨籍、聯盟）不要求徽章，會退回預設色塊 ——
檢查檔名時 `party_needs_mark()` 只認 `PARTIES_WITH_MARK` 裡的政黨。

JS 端的對應（`board.assets.js` 的 `window.NT_ASSETS`）：

| 檔名 | 欄位名 |
|---|---|
| `map.png` | `voteMap` |
| `legend.png` | `legend` |
| `city_seal.png` | `citySeal` |
| `emblem.png` | `emblem` |
| `mark_elected.png` | `electedMark` |
| `party_kmt.png` | `partyKmt` |
| `party_dpp.png` | `partyDpp` |

`window.BOARD_ASSETS` 則以檔名為 key（`map.png`、`party_kmt.png`…），供逐檔取用。

候選人名單**不在** xlsx 裡。2014 新北市的李進順就是這樣：逐里檔只有朱、游兩人，
他的 22,207 票靠 meta.json 宣告。xlsx 適配器只負責「哪一欄是誰、多少票」。

## 建置

```powershell
cd Video
python tools/build_board.py boards/2014-newtpei-mayor
python tools/verify_board.py          # 與 Share/data/election-2014.js 逐欄比對
```

常用選項：

| 選項 | 用途 |
|---|---|
| `--diff <舊檔.js>` | 建置後直接印出差異清單 |
| `--skip-geo` | 完全不碰 SHP，只用 `.cache/geojson.json` |
| `--refresh-geo` | 忽略 `.cache/geojson.json`，重跑 SHP |
| `--geo-cache <檔>` | 沿用指定的 geojson |
| `--shp <檔>` | 強制用這份村里界 SHP（覆寫依選舉年挑圖資的結果） |

（`--skip-photos` / `--force-photos` / `--force-assets` 三個舊旗標已刪除：
素材處理不在這裡做了。）

## 地圖寬高比

`source/map.png` 是原始海報（2014 是 9824 × 7365），看板用的是透明化成品
`NewSolution/png/processed/map/<year>/map.png`。`build_board.py` **只找圖不做圖**，
找到後會印出寬高比離群警告 —— 用原素材蓋掉成品會讓版面跑掉。

## 已知限制

- `boards/<id>/assets/` 的舊檔仍在（只有 2014 新北靠它）；
  新場次的素材一律走 `NewSolution/png/processed/`。
- 看板不畫候選人照片：卡面只有政黨純色，照片由使用者自行後製合成。