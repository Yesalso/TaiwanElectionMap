# NewSolution —— 開票看板的批次化生產方案

> 目標：把「一次做一張看板」變成「一條命令出一批看板」。
> 產出：<code>python tools/build_all.py --all --render</code>
> 這份文件是**設計與實作規格**。實作做到哪，看最上面的〈現況快照〉。

---

## 現況快照（2026-10-04）

> 規格說「要做什麼」，這一節說「做到哪」。下方 §0 以後仍是設計規格，內容未改。

**一句話**：五層架構的 **L1–L4 已全部落地並跑通 3 場**，L5（批次編排與量產）**尚未動工**。
規格那句「一條命令出一批」目前是「**建置逐場、渲染已可批次**」。

### 已落地

| 層 | 現況 | 落點 |
|---|---|---|
| L1 建置 | `meta.json` + xlsx → `board.js`，3 場跑通 | `tools/build_board.py`、`tools/boardlib/` |
| L2 素材 | 靜態素材透明化改走配方，逐位元組可復現 | `tools/boardlib/assets.py` |
| L3 引擎 | **已泛化**：讀 `window.BOARD`，無 2014 硬編碼 | `boards/_engine/js/` |
| L4 渲染 | 零依賴 CDP，一次啟動連跑多場 + 版面報告 | `tools/render_boards.mjs` |
| L5 批次 | ❌ `build_all.py` / `verify_all.py` 不存在 | — |

**L3 對照原 §4.3 清單**：`election-model` 分槽（`slot` 宣告優先，否則依票取前 2 進主卡）；
`theme` 已有 5 個政黨色（kmt/dpp/tpp/nsc/ind）；
`index.html` 的 39 行 `ELECTION_2014` 轉接層**已刪除**，三個場次都直接掛 `window.BOARD`。

**規格之外、實作時新增的**：

- **村里界圖資按「選舉年」自動切換**（<2019 用 106 / cp950，≥2019 用 111 / UTF-8），
  geojson 快取自帶 `_source` 溯源，來源不符自動重建。
- **圖例改置右欄、地圖框收窄**（`core/layout.js`），並加上可執行的版面斷言
  `tools/verify_layout.py`（L1–L5，FAIL 退出碼 1）。
- **圖例直接產出「透明底 + 白字 + 色塊」**（不再白底轉透明、不再墊淺色底板），
  色階只保留「真的有里落進來」的檔位（例：領先率都 >35% 時不畫「≤35%」）。
- **圖例色階固定綁政黨三組 + 其他灰**；無黨籍看板只印「無黨籍」不畫英文縮寫；黨徽透明化。

### 已產出

`node tools/render_boards.mjs --all --scale 1` → 3 張 2560×1440 PNG + `out/manifest.json`
（每場記 SHA256 / bytes / 尺寸 / Edge、Node 版本）：

| 場次 | bytes | SHA256（前 16） |
|---|---|---|
| `2014-newtpei-mayor` | 4,251,254 | `c3c5469308f03d45` |
| `2018-taipei-mayor` | 3,656,139 | `f0fe604658a348c6` |
| `2022-taipei-mayor` | 3,694,241 | `399f9503c34beffe` |

二次建置 + 二次渲染 SHA256 完全一致（可重現）；`verify_layout.py` 3 份報告 0 份未通過。

### 與規格的偏離

| 規格 | 實作 |
|---|---|
| 引擎選型 D0 | 選 **A**：原地泛化真引擎（`_engine/js/{core,model,render}`，`layout.js` 17 KB）。`NewSolution/code/` 那份簡版原型**未被採用**，可刪 |
| 新增 `boardlib/imagelab.py` | 併入 `tools/boardlib/assets.py`，未另立檔案 |
| `geo.py` 路徑搜索序 | 已建成 `SOURCES` 註冊表，但**路徑仍是絕對值**；環境變數 / 常見路徑回退未做 |

### 尚未完成

- ❌ **L5**：`tools/build_all.py`、`tools/verify_all.py`（規格 §4.5 / §5 的整批入口）
- ❌ `boards/_defaults/` 的 `extends` 繼承、`pool/` 跨場素材池
- ❌ `build_board.py --embed`：`board.assets.js` 仍每場產（2014 **2.2 MB** / 2018 1.0 MB / 2022 1.0 MB；
  2026-10-04 移除內嵌候選人照片後大幅縮小，先前是 4.3 / 5.4 / 5.4 MB）
- ❌ 小卡仍只畫 1 位（`model.hiddenMinorCount` 已算但無人消費，未印警告）→ 2022 的 12 位候選人只呈現前 3
- ✅ 看板不畫候選人照片（2026-10-04 定案）：主卡 / 小卡 / 頁眉現任者頭像
  一律只填政黨純色，照片由使用者自行後製合成。`png/candidate/` 的原圖與
  `png/processed/candidate/` 的舊成品都留著當素材，但已無任何消費者
- ❌ 量產：現 3 場（目標 24 場）；`Video/{boards,tools,out,NewSolution}` 全未納入 git（`??`）

### 素材透明化的落點（2026-10-04 定案）

**規則：透明化成品只放 `NewSolution/png/processed/`，不寫回原圖、也不進 `boards/<id>/assets/`。**

```
NewSolution/png/                     原始素材
  candidate/<year>/<中文名>.png      候選人照片（使用者提供）
  map/<year>/map.png                 得票率地圖（白底，Converge_to_map_taipei.py 產生）
  map/<year>/legend.png              圖例（**已是透明底 RGBA + 白字 + 色塊**）
  party/<政黨名>.png                 政黨徽章
  share/<素材名>.png                 市徽 / 國徽 / 當選標誌

NewSolution/png/processed/           ★ 透明化成品（唯一落點）
  map/<year>/map.png                 白底轉透明
  map/<year>/legend.png              原樣沿用（how=copy，見下）
  party/party_<key>.png              內切圓去背
  share/{city_seal,emblem,mark_elected}.png
```

★ **圖例不走「白底轉透明」**（2026-10-04 起）：`Converge_to_map_taipei.py` 直接
把 `legend.png` 畫成「透明底 + 白字 + 色塊」的 RGBA，白字本身就是
RGB(255,255,255)，再過一次白底轉透明會被整片吃掉。所以 `assets.map.json`
裡 `legend.png` 寫成 `{"to": "legend.png", "how": "copy"}`，`build_assets.py`
只搬檔不轉換。圖例的色階也只保留「真的有里落進來」的檔位。

★ **沒有 candidate 這一類**（2026-10-04 起）：看板不畫候選人照片
（`_engine/js/render/layers.js` 的 `CandidateLayer` 只填政黨純色），
所以這條管線不處理候選人圖檔。`png/candidate/<year>/` 的原圖與
`png/processed/candidate/` 的舊成品都留著當素材，但已無任何消費者。

| 角色 | 落點 |
|---|---|
| 產生（唯一入口） | `NewSolution/tool/build_assets.py`（配方表 `tool/assets.map.json`） |
| 透明化實作 | `NewSolution/tool/make_transparent.py` 的 `white_to_transparent()`（白底→透明，只給**地圖**用；被 build_assets 呼叫，無 CLI，要整批轉檔用 `build_assets.py`）。圖例不需去背，走 `how=copy` |
| 消費 | `tools/build_board.py` 只「找圖」不做圖，寫出 `boards/<id>/board.files.js` |
| 引擎 | `Utils.resolveAsset()` 把邏輯名（`assets/map.png`）換成 `BOARD_FILES` 裡的實際 URL |
| 路徑約定 | `tools/boardlib/naming.py` 的 `processed_relpath()` |

原圖與成品靠 `assets.map.json` 對應（中文檔名 -> 看板要用的 ASCII key）。
新增一場 = 在 `png/` 放原圖 + 在 JSON 補一段，程式零改動。

**看板的靜態伺服器根因此改成 `Video/`**（不是 `boards/`）—— `board.files.js`
用 `../../NewSolution/png/processed/` 指素材，根設在 `boards/` 會 404。
`tools/render_boards.mjs` 已照此設定（`--root`，預設 `Video/`）。

**批次範圍**：`boards/<id>/.skip` 存在時 `--all` 會跳過該場。
`2014-newtpei-mayor` 已標記 —— 本階段**只生成台北（2018 / 2022）**，不做新北。
`Converge_to_map_taipei.py` 也在主程式擋掉 `city != 臺北市` 的資料集。

`boards/<id>/assets/` 保留為**舊場次的回退來源**，
新場次不會再往那裡寫任何東西。（裡面舊的 `assets/candidate/*.png` 已無消費者，
看板不畫照片。）

---

## 0. 一句話

現況是「引擎 + 一份 <code>meta.json</code> + 一個資料夾 = 一場選舉」，
而且引擎裡寫死了 2014 新北市的候選人與政黨，PNG 只能靠人開瀏覽器點按鈕。
方案把它拆成**五層**：場次描述（純 JSON）／資產池（跨場共用素材）／泛化引擎／
無頭渲染器／批次編排，並補上回歸驗證，之後新增一場選舉的成本從「改程式碼」降到「填一個 JSON」。

---

## 1. 施工前盤點（2026-10-03 的狀態）

> ⚠️ 這一節記錄的是**動工之前**的實況。其中「引擎寫死 2014」「轉接層仍在」等項目，
> L3 泛化後**多數已修**——請以最上方〈現況快照〉為準，本節僅保留作為問題背景。

### 1.1 專案是兩層，不是一層

| 層 | 位置 | 產出 | 技術 |
|---|---|---|---|
| 根專案 | <code>TaiwanElection/</code> | 得票率地圖 PNG | Python：geopandas + matplotlib + OpenCV + Pillow |
| 子專案 | <code>Video/</code> | 開票看板 PNG（2560×1440 / 5120×2880） | Python 建置 + 純前端 Canvas 繪製 |

根專案的管線是兩段式（見根 <code>README.md</code>）：

```
中選會原始 xls/xlsx  →  convert_*.py  →  {年份}{縣市}_得票數.xlsx  →  Converge_to_map*.py  →  得票率地圖 PNG
```

<code>Video/</code> 是**獨立的看板專案**，消費的是前者的產物。
它沒有自己的繪圖管線，只有一條「資料 → 資料夾 → 一個 HTML 頁 → 手動點 PNG」的路。

### 1.2 <code>Video/boards/</code> 的資料流

```
source/data.xlsx（逐里得票）  ┐
source/*.png（原始素材）      ├→ tools/build_board.py → board.js（canonical 資料）
meta.json（★ 人工維護）       ┘        │
                                     ├→ .cache/geojson.json（SHP dissolve，快取）
                                     └→ assets/* + board.assets.js（內嵌備援）
                                              ↓
              boards/<id>/index.html（薄殼，引 ../_engine/…）
                                              ↓
                        Canvas 2D 繪製（Slide.render(ctx, scale)）
                                              ↓
                              ★ 只能靠瀏覽器手動「下載 PNG」
```

<code>build_board.py</code> 六步（<code>tools/build_board.py:262</code>）：

1. <code>manifest.resolve()</code> 讀 <code>meta.json</code>、驗欄位（<code>boardlib/manifest.py:157</code>）
2. <code>xlsx_read.read_units()</code> 逐里得票 → 自動偵測版面 A～F（<code>boardlib/xlsx_read.py:318</code>）
3. <code>reconcile()</code> 對帳：Σ 各區票 vs <code>meta.json</code> 官方總票
4. <code>geo.build()</code> 由村里界 SHP dissolve 出行政區 GeoJSON（<code>boardlib/geo.py:33</code>）
5. 素材只找圖不做圖：靜態素材由 <code>NewSolution/tool/build_assets.py</code> 處理（地圖／徽章去背，圖例已是透明底 RGBA 只搬檔）；<strong>候選人照片不在其中</strong> —— 看板不畫照片
6. 寫 <code>board.js</code> / <code>board.assets.js</code> / <code>assets/*</code>

### 1.3 現有解決思路 —— 確認成立，且方向正確

| # | 做法 | 出處 | 評價 |
|---|---|---|---|
| 1 | **設定與資料分離**：<code>meta.json</code> 是唯一人工來源；xlsx 只回答「哪一欄是誰、多少票」 | <code>boardlib/manifest.py</code> docstring | 好。缺的是「設定本身的重複」沒解（見 §4.1） |
| 2 | **素材檔名固定、不查設定**：<code>naming.py</code> 是唯一來源，JS 直接按名字取 | <code>boardlib/naming.py:36</code> | 很好。這是整個設計裡最值得保留的一條 |
| 3 | **唯一中間格式 canonical**：<code>{meta, candidates[], districts[], geojson}</code> 同時是 Python 產出與 JS 消費 | <code>boardlib/canonical.py</code> | 很好。契約清楚，可測試 |
| 4 | **畫布渲染、可任意倍率重繪**：2× 是真重繪不是放大 | <code>_engine/js/slide.js:395</code> | 很好。是能出 4K 的前提 |
| 5 | **逐場隔離、一份引擎**：開新場就複製 <code>_template/</code> | <code>boards/README.md</code> | 方向對，但「複製」本身在 N 大時會爆炸（見 §1.4-C） |
| 6 | **多版面 xlsx 適配器**：A～F 六種版面自動偵測 | <code>boardlib/xlsx_read.py:318</code> | 很好。已涵蓋 1993～2022，是批次化的最大既有資產 |

**結論：資料層的抽象層級是對的，不需要推倒重來。**
問題全部集中在「引擎泛化」與「產出出口」兩端。

### 1.4 通往「批次」的三道牆

#### 牆 A —— 引擎寫死 2014 新北市

| 位置 | 寫死什麼 | 後果 |
|---|---|---|
| <code>_engine/js/model/election-model.js:83-87</code> | <code>build('zhu') / build('you') / build('lee')</code> | 換場必壞 |
| <code>_engine/js/model/election-model.js:97-112</code> | <code>votes: { zhu: d.zhu, you: d.you }</code>、<code>winnerKey==='zhu'?'kmt':'dpp'</code> | 同上 |
| <code>_engine/js/core/theme.js:56</code> | 只有 <code>kmt / dpp / ind</code> 三個政黨色 | 遇到民眾黨/台灣民基黨無色可用 |
| <code>_engine/js/slide.js:319</code> | <code>photoByKey = { zhu: imgs[0], you: imgs[1], lee: imgs[2] }</code> | 第三候選人照片取不到 |
| <code>_engine/js/app.js:28,33-37</code> | <code>global.ELECTION_2014</code>、<code>name: '第二屆新北市長選舉'</code> | 單場專用 |
| <code>boards/_template/index.html:75-113</code> | canonical → <code>ELECTION_2014</code> 轉接層 | 多一層要維護的格式 |
| <code>_engine/js/render/layers.js</code> 的 <code>MinorCandidateLayer</code> | 單一第三人 | 直轄市長 2018 起常見 4～5 人 |

#### 牆 B —— 沒有無頭出口，PNG 產出全靠人手

* <code>_engine/js/exporter.js:83</code> 只有 <code>Exporter.download()</code>（觸發瀏覽器下載）。
* 唯一的寫檔路徑是 <code>Share/tools/_server.js:26</code> 的 <code>POST /__save</code>，
  檔頭註解明寫「僅供開發驗證，不屬於專案功能」。
* 驗證流程寫在 <code>.workbuddy/memory/2026-09-29.md</code>：起 http:8622 → Edge headless + CDP → 手動 <code>Runtime.evaluate</code>。
  **這是每次都重做一遍的腳本，沒有落檔。**
* 後果：無 CLI、無批次、無回歸、無法回答「這批 24 張有沒有被改壞」。

#### 牆 C —— 素材處理沒參數化，且逐場複製

| 位置 | 寫死什麼 |
|---|---|
| <code>tools/_legacy_build_assets.py:87-117</code> | <code>SHARE</code>/<code>ASSET_DIR</code>/<code>SRC_SEAL</code>/<code>SRC_EMBLEM</code>… 全是絕對路徑且指向 2014 新北 |
| <code>tools/_legacy_build_assets.py:135,140</code> | <code>EMBLEM_BLUE = (0,0,149)</code>、<code>PARTY_BLUE</code> —— 直接寫死「青天白日圓徽的藍」 |
| <code>tools/_legacy_build_assets.py:156</code> | <code>LEGEND_KEEP_TOP = 343</code> —— 2014 那張圖例的裁切值 |
| <code>tools/_legacy_build_vote_map.py</code> | 擦標題／圖例的比例寫死（0.685/0/0.315/0.304） |
| <code>tools/boardlib/geo.py:16</code> | <code>DEFAULT_SHP</code> 是 <code>D:\Windows\Documents\…</code> 絕對路徑 |
| <code>tools/verify_board.py:4-5</code> | 路徑寫死 2014 + Share |

另外：<code>boards/2014-newtpei-mayor/board.assets.js</code> 是 **4.3 MB**（整包 base64）。
24 場 × 4.3 MB ≈ 100 MB 的重複位元組，而批次渲染其實走 http，根本不需要內嵌。

### 1.5 現成的資料規模

* 根專案已有 **277 個 xlsx**（<code>git status</code> 排除不到，因為 <code>.gitignore</code> 擋掉 <code>*.xlsx</code>）。
* <code>MayoralElections/data/</code> 有 1989～2022 直轄市長／縣市長逐里得票。
* <code>MayoralElections/scripts/*/Converge_to_map1.py</code> 已有 <code>DATASETS</code> 設定清單
  → **地圖這一側已經接近可批次**，看板缺的只是把它接上。

**v1 的合理批次目標：6 縣市 × 4 屆次 ≈ 24 張直轄市長看板。**
（總統／立委是全國型，版面需求不同，放 v2。）

---

## 2. 目標與不變量

### 目標

1. **一條命令出圖**：<code>python tools/build_all.py --all --render --scales 1,2</code>
2. **新增一場 = 填一份 JSON + 放素材**，不改任何 JS／Python
3. **可回歸**：改了引擎後，能用像素斷言證明「除指定區塊外逐像素相同」
4. **可重現**：同樣輸入 → 同樣 SHA256

### 不變量（改版不得破壞）

* <code>canonical</code> 格式的四個鍵不變（<code>meta / candidates / districts / geojson</code>）
* <code>naming.py</code> 的素材檔名不變（<code>map.png</code>、<code>legend.png</code>、<code>party_&lt;key&gt;.png</code>…；沒有候選人照片）
* <code>Slide.render(ctx, scale)</code> 簽名不變，2× 必須是真重繪
* 2560×1440 版面座標不變（<code>layout.js</code> 只在「要支援更多變化時」才動）
* 2014 新北那張圖**逐像素零差異**（作為整個方案的回歸基準）

---

## 3. 方案總覽

```
                      ┌──────────────────────────────────────┐
   中選會 xlsx ──────►│ L1 build：meta.json + xlsx → board.js  │
   （根專案 277 檔）  │      SHP → geojson  素材 → 透明化     │
                      └───────────────┬──────────────────────┘
                                      │
   原始素材 PNG ──────►┌───────────────▼──────────────────────┐
   （市徽/黨徽/國徽/   │ L2 assets：跨場共用的資產池 +         │
     圖例/地圖）       │      參數化的圖像處理 imagelab         │
                      └───────────────┬──────────────────────┘
                                      │
                      ┌───────────────▼──────────────────────┐
                      │ L3 engine：泛化，零硬編碼              │
                      │      讀 window.BOARD（單一資料源）     │
                      └───────────────┬──────────────────────┘
                                      │
                      ┌───────────────▼──────────────────────┐
                      │ L4 render：Edge headless + CDP        │
                      │      零 npm 依賴 → PNG 落盤            │
                      └───────────────┬──────────────────────┘
                                      │
                      ┌───────────────▼──────────────────────┐
                      │ L5 batch：build_all / verify_all       │
                      │      對帳 + 像素斷言 + manifest.json    │
                      └──────────────────────────────────────┘
```

**關鍵設計選擇**：渲染走 `http://` 而非 `file://`。
因為 <code>slide.js:53</code> 的 <code>useEmbeddedUnderFile()</code> 已經把兩條路分開了——
走 http 就用實體檔 + 時間戳，於是 **`board.assets.js` 的 4.3 MB 內嵌從「必需品」降級成「選用項」**。
這不是順手做，是刻意的：省體積只是收穫，真正的好處是**檔案換掉刷新就生效**，批次流程才不會吃到舊圖。

---

## 4. 各層設計

### 4.1 L0 — 場次描述：讓 <code>meta.json</code> 學會「繼承」

**問題**：現在開新一場，<code>meta.json</code> 要重抄縣市徽、黨徽、版面微調…
24 場就是 24 份重複。

**做法**：新增 <code>extends</code>（單層即可，不要搞成深鏈）＋ 資產池引用。

```jsonc
// boards/_defaults/tw-mayor.json  ← 縣市層級的共用設定
{
  "meta": { "country": "中華民國（台灣）", "countryEn": "Republic of China (Taiwan)" },
  "assets": {
    "pool": {
      "city_seal":  "pool/seal/newtpei.png",
      "emblem":     "pool/emblem/roc.png",
      "mark_elected": "pool/marks/elected.png",
      "party": { "kmt": "pool/party/kmt.png", "dpp": "pool/party/dpp.png",
                 "tpp": "pool/party/tpp.png", "nsc": "pool/party/nsc.png" }
    }
  }
}
```

```jsonc
// boards/2018-newtpei-mayor/meta.json  ← 只寫差異
{
  "id": "2018-newtpei-mayor",
  "extends": "../_defaults/tw-mayor.json",
  "meta": { "election": "第三屆新北市市長選舉", "year": 2018, "date": "11月24日" },
  "candidates": [
    { "key": "hou", "name": "侯友宜", "party": "中國國民黨", "partyShort": "KMT",
      "number": 1, "votes": 4564740, "elected": true },
    ...
  ],
  "region": { "county": "新北市", "unitLevel": "village" }
}
```

**合併規則（寫死在 <code>boardlib/manifest.py</code>，不給設定檔）**：

| 類型 | 行為 |
|---|---|
| dict | 逐鍵深合併 |
| list | **子集取代**（<code>candidates</code> / <code>partyThemes</code> 一律整份換掉，不做合併） |
| scalar | 子集覆蓋 |
| 陣列內元素 | 以 <code>key</code> 欄位比對做 key-wise 合併（讓 <code>partyThemes</code> 能只調一個政黨） |

**不做的事**：不做多層鏈、不做條件繼承、不做變數插值。
一旦這三樣出現，設定就變成了一門語言，除錯成本會超過它省下的重複。

**<code>partyThemes</code> 補完**（<code>theme.js:56</code> 現在只有三個）：

```js
tpp: { main: '#ff7f27', light: '#ffa45c', dark: '#a84600',
       map: ['#ffc08f','#ffa264','#ff8a3d','#c25a08','#8a3f04'] },   // 橘
nsc: { main: '#7b4ea8', light: '#a983c8', dark: '#4a2a68',
       map: ['#d5c2e6','#b294ce','#8f68ad','#6a4a86','#4a3060'] },   // 紫
pfp: { main: '#c9a227', ... },
ind: { /* 保留現有灰 */ }
```

---

### 4.2 L1 — 資產池 + 參數化的圖像處理

把 <code>_legacy_build_vote_map.py</code> 與 <code>_legacy_build_assets.py</code> 裡**已經驗證過
但還沒參數化**的實作搬進 <code>boardlib/imagelab.py</code>。這一步是純搬家 + 去硬編碼，
演算法不動，因為 <code>.workbuddy/memory/2026-09-29.md</code> 已經量過它好在哪：

| 功能 | 搬進 | 參數化什麼 | 已驗證的效能 |
|---|---|---|---|
| 預乘 alpha 面積平均縮圖 | <code>resize_rgba()</code> | 目標寬度 | 過渡帶 0.256%、邊緣色誤差中位 +0.0、PNG 從 1346 KB → 602 KB |
| 擦標題／圖例 | <code>erase_bands()</code> | **比例改由 <code>meta.json</code> 給或自動偵測** | 原本寫死 0.685/0/0.315/0.304 |
| 幾何切圓去背 | <code>circle_asset()</code> | <code>edge_fill</code> 由「偵測圓周單一色」決定 | 圓外 alpha max = 0，無白暈 |
| <code>edge_report()</code> 自檢 | 原樣 | — | 抓針孔／鋸齒／跑色 |

**關鍵改進 —— 擦標題比例改成自動偵測**：
現在是寫死的四個比例。批次後會有 24 張不同來源的圖，寫死一定會錯。
做法：偵測右上角的「深色像素密度最高的矩形區塊」當標題帶，
右下角「有規則色階方塊」當圖例帶；偵測失敗就落到 <code>meta.json</code> 的手動值，再失敗就**報錯不要猜**。

**<code>geo.py</code> 的 <code>DEFAULT_SHP</code> 絕對路徑**：改成
<code>路徑搜尋序</code> = <code>meta.json region.shp</code> → 環境變數 <code>MOI_SHP</code> → 常見預設路徑清單 → 報錯並印出所有試過的路徑。

**<code>board.assets.js</code> 的處置**：改成**選用**。
新增 <code>--embed</code> 開關，預設不產生；只有真的要雙擊 <code>index.html</code> 用 <code>file://</code> 時才開。
檔名改叫 <code>board.assets.embedded.js</code>（讓人一眼看出它是後備），
且 <code>index.html</code> 改用 <code>document.write</code> 條件載入或直接給一個人工步驟說明。

---

### 4.3 L3 — 引擎泛化（去硬編碼）

這是**唯一必須動 JS 的一層**，也是最需要小心的。原則：**只改資料流，不改版面座標。**

#### 4.3.1 <code>election-model.js</code> 改成通用分槽

```js
// 現在：var zhu = build('zhu','left'); var you = build('you','right'); this.minor = build('lee','minor');
// 改成：以 meta.json 的宣告優先，其次依得票排序

function ElectionModel(raw) {
  var list = (raw.candidates || []).map(function (c) { return new Candidate(c); });

  /* 分槽：candidates[].slot 宣告優先 → 否則前 N 名進主卡（左右依得票），
     其餘進小卡。N 由 meta.slots.main 決定，預設 2。 */
  var nMain = (raw.slots && raw.slots.main) || 2;
  var declared = list.filter(function (c) { return c.slot; });
  var sorted  = list.slice().sort(function (a, b) { return b.votes - a.votes; });

  this.main  = declared.length ? declared.slice(0, nMain) : sorted.slice(0, nMain);
  this.minors = list.filter(function (c) { return this.main.indexOf(c) < 0; }, this);
  this.left  = this.main[0];      /* 得票高者固定在左，沿用現有版面慣例 */
  this.right = this.main[1] || this.main[0];

  /* 勝負差距對「得票前二」，與現有畫面一致 */
  this.winner = this.left.votes >= this.right.votes ? this.left : this.right;
  this.loser  = this.winner === this.left ? this.right : this.left;

  this.candidates = this.main.concat(this.minors);
  this.marginVotes = Math.abs(this.left.votes - this.right.votes);
}
```

<strong>向後相容</strong>：<code>2014-newtpei-mayor/meta.json</code> 加上
<code>"candidates": [{"slot": "left"}, {"slot": "right"}, {"slot": "minor"}]</code>
之後，輸出必須與改動前**逐像素相同**。這是第一號驗收項。

#### 4.3.2 行政區資料改成任意 key

```js
// 現在：votes: { zhu: d.zhu, you: d.you }，winnerKey === 'zhu' ? 'kmt' : 'dpp'
// 改成：直接吃 canonical 的 votes 物件，政黨色由「勝者的政黨」推出

this.districts = (raw.districts || []).map(function (d) {
  var winnerKey = d.winnerKey;
  var winner = candByKey[winnerKey];
  var partyKey = winner ? winner.partyKey : 'ind';
  return {
    name: d.name, short: d.short, villages: d.villages,
    votes: d.votes,              /* 任意 key，不再寫死 zhu/you */
    pct: d.pct,
    valid: d.valid, winnerKey: winnerKey,
    partyKey: partyKey,          /* 由候選人的政黨推出，不是 === 'zhu' */
    margin: d.margin,
    color: NT.Theme.mapShade(partyKey, d.margin)
  };
});
```

#### 4.3.3 <code>slide.js</code> 的 <code>photoByKey</code> 動態化

```js
// 現在：photoByKey = { zhu: imgs[0], you: imgs[1], lee: imgs[2] }
// 改成：照 canonical 的候選人順序建，並把 5 個 _loadXxx 收斂成一個 _loadAssets()

var keys = Object.keys(self.model.photoByKey);   /* 由 model 依候選人順序給 */
self.assets.photoByKey = {};
Promise.all(self.model.candidates.map(loadOnePhoto))
  .then(function (list) {
    list.forEach(function (v, i) { self.assets.photoByKey[self.model.candidates[i].key] = v; });
  });
```

#### 4.3.4 <code>MinorCandidateLayer</code> 支援多位

現在只有一張小卡。2022 直轄市長常見 4～5 位。
<strong>做法</strong>：保留 <code>minors[0]</code> 用現有那張小卡（版面零變動），
第 2 位以後畫進「底部票數帶」上方的縮圖列（<code>layout.js</code> 已有 <code>Layout.ribbon</code>，
上方 <code>y 1396</code> 之前有 18px 空間 → 需要新增 <code>Layout.minorRow</code> 區段）。

<strong>保守做法（v1 先做這個）</strong>：超過 <code>slots.minor</code> 上限時
只畫前 N 位，並在狀態列／建置輸出印出「另有 X 位候選人未呈現」。
<em>寧可少畫，不要版面跑掉</em>——這是整份文件反覆出現的取捨。

#### 4.3.5 刪掉轉接層

<code>_engine</code> 全面改讀 <code>window.BOARD</code> 之後，
<code>index.html:75-113</code> 那 39 行轉接腳本整段刪除，
<code>app.js</code> 的 <code>global.ELECTION_2014</code> 改成 <code>global.BOARD</code>。
<strong>收益不只是少一段程式碼</strong>：現在 Python 的 canonical 與 JS 的
<code>ELECTION_2014</code> 是兩份格式，中間靠一段 39 行的 JS 手工轉換，
欄位改名時會**靜默失效**。刪掉之後只剩一份契約。

#### 4.3.6 <code>layout.js</code> 的 <code>src</code> 改絕對化

<code>layout.js:26</code> 的 <code>seal.src = 'assets/city_seal.png'</code> 是相對於 board 目錄的，
<em>由 <code>index.html</code> 的所在位置決定</em>。批次渲染若從別的目錄載入就會指錯。
<strong>做法</strong>：<code>build_board.py</code> 產生 <code>window.BOARD_PATHS</code>
（<code>{assetsRoot: 'assets/', poolRoot: '../pool/'}</code>），<code>slide.js</code> 用它組出實際 URL。

---

### 4.4 L4 — 無頭渲染器（零依賴）

#### 4.4.1 為什麼不用 Puppeteer / Playwright

| 選項 | 判斷 |
|---|---|
| <code>npm i puppeteer</code> | ✗ 本機 <code>npm</code> 指向 <code>D:\npm.ps1</code>，被 PowerShell 執行策略擋掉；且要下載 ~150 MB Chromium；離線環境高風險 |
| <code>npx playwright</code> | ✗ 同上，且會自動裝一份 Chromium（本機只有 Edge） |
| <strong>內建 <code>WebSocket</code> + CDP</strong> | ✓ 已實測：Node v24.18.0 有 <code>globalThis.WebSocket</code> 與 <code>fetch</code>；Edge 154 的 <code>--headless=new --remote-debugging-port</code> 回 <code>/json/version</code> 正常 |

**結論：<code>tools/render_boards.mjs</code> 用 Node 內建模組直接講 CDP，零 npm 依賴。**
（<code>--experimental-websocket</code> 在舊 Node 才需要；v22+ 已內建。）

#### 4.4.2 渲染流程

```js
// tools/render_boards.mjs —— 零依賸，Node >= 22
// 1. spawn Edge： --headless=new --disable-gpu --hide-scrollbars
//                   --force-color-profile=srgb --font-render-hinting=none
//                   --remote-debugging-port=0 --user-data-dir=<tmp>
// 2. 讀 <user-data-dir>/DevToolsActivePort 拿實際 port
// 3. 啟動零依賴靜態伺服器（node:http），把 boards/ 目錄掛出去
// 4. POST /json/new?<url>  →  webSocketDebuggerUrl
// 5. WebSocket 發 CDP：Page.enable → Runtime.enable
//    → Page.navigate(url + '?headless=1') → 等 Page.loadEventFired
// 6. Runtime.evaluate( awaitPromise, returnByValue ):
//        await window.__boardReady();                 // 圖片 decode + document.fonts.ready
//        return await window.__renderBoard(scale);   // → dataURL
// 7. base64 → 寫檔 → 記 SHA256
// 8. Browser.close，重啟下一場（每場一個 tab 或一個 process，見下）
```

#### 4.4.3 頁面端 hook（<code>_engine/js/headless.js</code>）

<strong>關鍵設計：把渲染邏輯從 <code>App</code>（UI）裡抽出來</strong>，
否則批次就得模擬按鈕點擊。做法是新增一個不依賴 DOM 的純函式：

```js
// _engine/js/headless.js —— 有 headless=1 時才載入
(function (global) {
  var NT = global.NT;

  function renderBoard(scale) {
    return NT.BoardFactory.create(global.BOARD)
      .then(function (slide) {
        /* 關鍵：所有圖片都要 decode 完，否則 drawImage 會畫到空白 */
        return Promise.all(slide.pendingImages.map(function (i) { return i.decode(); }))
          .then(function () { return document.fonts.ready; })
          .then(function () { return slide.renderToCanvas(scale); })
          .then(function (cv) { return cv.toDataURL('image/png'); });
      });
  }

  global.__renderBoard = function (scale) { return renderBoard(scale); };
  global.__boardReady = function () { /* 只等載入，不渲染 */ };
}(window));
```

<strong>所以 <code>index.html</code> 在 <code>?headless=1</code> 時不建立 <code>App</code></strong>（不做 UI、不生縮圖），
只註冊 <code>window.BOARD</code> 與 headless hook。省掉縮圖那 240 px 的重繪，
每場省一次全版渲染。

#### 4.4.4 決定性（determinism）

| 措施 | 理由 |
|---|---|
| <code>--force-color-profile=srgb</code> | 避免不同機器色彩管理差異 |
| <code>--font-render-hinting=none</code> | 關閉字型 hinting，數字墨跡才可重現 |
| <code>document.fonts.ready</code> | 沒等這個，headless 常用 fallback 字型 |
| 固定 <code>DevToolsActivePort</code> 讀取後才送指令 | 否則偶發拿不到 port |
| 每場開新 tab，不用同一頁反覆 navigate | 避免前一個場次的 <code>Layout.*</code> 全域污染下一場 |
| 記錄 Edge 版本 + 字型清單到 manifest | 換了 Edge 版本要能看出來 |

#### 4.4.5 產出

```
out/
  2014-newtpei-mayor_2560x1440.png
  2014-newtpei-mayor_5120x2880.png
  2018-newtpei-mayor_2560x1440.png
  ...
  manifest.json     ← 每場的 SHA256、bytes、尺寸、Edge 版本、警告清單
```

---

### 4.5 L5 — 批次編排與驗證

#### 4.5.1 <code>tools/build_all.py</code>

```powershell
# 全場：建置 → 對帳 → 渲染 → 出圖
python tools/build_all.py --all --render --scales 1,2

# 只建置不渲染（CI 用）
python tools/build_all.py --all

# 開新場：從 _template 骨架 + _defaults 產生
python tools/build_all.py --new 2018-newtpei-mayor

# 只重渲染（引擎改版後）
python tools/build_all.py --all --render-only --scales 1

# 指定幾場
python tools/build_all.py boards/2014-newtpei-mayor boards/2018-newtpei-mayor --render
```

**失敗語意**：單場失敗**不中斷整批**，記為 failed 繼續下一場，最後印摘要
（成功 N / 失敗 M / 跳過 K）並以 exit code 1 結束。
批次流程最怕的是第 3 場掛掉之後前兩場白跑。

#### 4.5.2 <code>tools/verify_all.py</code> —— 回歸的關鍵

這是把 <code>.workbuddy/memory/2026-09-29.md</code> 裡那 12 項手寫像素斷言**制度化**。

**三層驗證**：

| 層 | 檢查 | 失敗代表 |
|---|---|---|
| L-資料 | Σ各區票 vs 官方總票；<code>valid</code> 加總；行政區數 = geojson features 數 | 資料錯 |
| L-版面 | 幾何斷言：市徽有畫上（用同水平帶空白處比亮度，<strong>不要用「純白像素」當判準</strong>）、地圖與頁眉淨間距 ≥ N、地圖不壓左右候選人、票數帶不撞小字區塊 | 版面跑掉 |
| L-像素 | 與 <code>out/</code> 裡的基準 PNG 做指定區塊外的逐像素比對 | 未預期的改動 |

<strong>L-像素的比對策略</strong>：全畫面逐像素比對太脆（字型抗鋸齒）。
做法是每張看板存一份 <code>baseline.masks.json</code>（用矩形區塊描述「允許變動」的範圍，
例如日期塊、候選人卡、票數帶），比對時只比 <strong>區塊外</strong>，
命中差異就印出 bbox 與差異像素數。

這條直接來自記憶裡那條教訓：

> 差異像素 **1875**，bbox <code>x 1246–1392 / y 141–170</code> → 只落在日期行；
> 其餘 9 個區塊（含地圖、兩側候選人、底部票帶）**逐像素 0 差異**。

這就是「改了 A、確定 B 沒變」的標準答案，要把它變成可以重跑的程式。

#### 4.5.3 <code>tools/verify_board.py</code> 的去處

現有這支（<code>verify_board.py</code>）是「新版 vs 舊 <code>Share/</code>」的一次性比對，
路徑寫死。它有價值——它证明了 canonical 化沒有改變任何數字——
但只對 2014 有意義。<strong>保留原樣當遷移憑證，另寫 <code>verify_all.py</code> 走通用路徑。</strong>

---

## 5. CLI 契約

| 指令 | 用途 |
|---|---|
| <code>python tools/build_all.py --new &lt;id&gt;</code> | 從 <code>_template/</code> + <code>_defaults/</code> 開新場 |
| <code>python tools/build_all.py --all [--render] [--scales 1,2]</code> | 建置（+渲染）全部場次 |
| <code>python tools/build_all.py &lt;dir&gt;… [--render]</code> | 建置指定場次 |
| <code>python tools/build_all.py --all --render-only</code> | 跳過建置，只重出圖 |
| <code>python tools/build_all.py --all --refresh-geo</code> | 忽略 geojson 快取重跑 SHP |
| <code>python tools/build_all.py --all --force-photos</code> | 強制重跑去背 |
| <code>python tools/build_all.py --all --embed</code> | 產生 <code>board.assets.embedded.js</code>（file:// 用） |
| <code>node tools/render_boards.mjs --board &lt;id&gt; --scale 2 --out out/</code> | 只渲染，不建置 |
| <code>python tools/verify_all.py --all</code> | 三層驗證 + 更新基準 |
| <code>python tools/verify_all.py --all --check</code> | 只驗不改基準（CI 用） |

<strong>全部回傳 exit code</strong>：0 = 全過，1 = 有失敗。
這是能不能放進排程的唯一條件。

---

## 6. 目錄結構

```
Video/
  boards/
    _engine/                  共用引擎（只有一份）
      js/
        core/     utils theme layout
        model/    election-model.js        ← 泛化
        render/   geo-projector layers
        slide.js exporter.js app.js
        headless.js                         ← 新增：無頭渲染 hook
    _defaults/                新增：縣市／選舉類別層級的共用設定
      tw-mayor.json  tw-county-mayor.json
    _template/                空白模板（開新場複製這個）
    2014-newtpei-mayor/       ← 全域改成讀 BOARD，去掉轉接層
    2018-newtpei-mayor/
    ...
  pool/                       新增：跨場共用的素材（取代逐場複製）
    seal/    newtpei.png taipei.png kaohsiung.png ...
    emblem/  roc.png
    marks/   elected.png
    party/   kmt.png dpp.png tpp.png nsc.png pfp.png
    legend/  （依縣市，因圖例色階不同）
  tools/
    build_board.py            單場建置（保留，改用 manifest 的合併結果）
    build_all.py              新增：批次編排
    verify_all.py             新增：三層驗證
    verify_board.py           保留：遷移憑證（一次性）
    render_boards.mjs         新增：零依賴 CDP 渲染器
    boardlib/
      manifest.py   ← 加 extends 合併
      naming.py     canonical.py   xlsx_read.py
      geo.py        ← SHP 路徑改搜尋序
      assets.py     白底轉透明 / 內切圓（沒有候選人去背）
      imagelab.py   新增：地圖/圖例/圓徽/黨徽的參數化處理
    _legacy_*.py               imagelab.py 驗證後刪除
  out/                        新增：渲染產物 + manifest.json + baseline.masks.json
  NewSolution/                本文件
```

<strong><code>pool/</code> 為什麼值得做</strong>：市徽／國徽／黨徽／選舉章跨全部場次都是同一批圖。
現在每場 <code>assets/</code> 都放一份（2014 一場就 8 張、1.4 MB）。
24 場就是 24 份。池化後這些檔案只存在一份，<code>meta.json</code> 引用路徑即可。

---

## 7. 分階段交付與驗收

| 階段 | 內容 | 產出 | 驗收標準 |
|---|---|---|---|
| **P0**<br>建立回歸基準 | 跑一次現有流程，把 2014 的 2560/2880 兩張 PNG 存成 <code>out/</code> 基準 + 寫 <code>baseline.masks.json</code> | <code>out/2014-newtpei-mayor_*.png</code><br><code>out/baseline.masks.json</code> | 三層驗證在**未改任何程式**時全過 |
| **P1**<br>渲染器落地 | <code>render_boards.mjs</code> + <code>_engine/js/headless.js</code>，不動任何既有程式邏輯 | 兩張 PNG | <strong>與 P0 基準逐像素相同，SHA256 一致</strong> |
| **P2**<br>引擎泛化 | <code>election-model.js</code>／<code>theme.js</code>／<code>slide.js</code>／<code>app.js</code> 去硬編碼，刪轉接層 | — | <strong>2014 逐像素相同</strong>；用一份「假 <code>meta.json</code>」（改名字、改政黨、加第 4 位候選人）跑通 |
| **P3**<br>資產池 + imagelab | <code>imagelab.py</code> 參數化，<code>pool/</code> 落地，<code>DEFAULT_SHP</code> 改搜尋序，<code>--embed</code> 選用化 | — | 重跑 imagelab，<strong>2014 的 map/legend/seal/emblem/party 位元組不變</strong> |
| **P4**<br>批次編排 | <code>build_all.py</code> + <code>verify_all.py</code> + <code>_defaults/</code> 繼承 | — | 用 **3 個假場次**（不真實的選舉）驗證：批次成功、部分失敗不中斷、exit code 正確 |
| **P5**<br>真資料量產 | 補齊 6 縣市 × 4 屆次的 <code>meta.json</code> 與素材 | 24 張看板 | 逐場人工目視；<code>manifest.json</code> 完整；<code>verify_all.py</code> 全過 |

<strong>順序的理由</strong>：P1 必須在 P2 之前。
先有「改了能證明沒改壞」的能力，再去改引擎——
這正是記憶裡那條教訓的應用：
<em>「拿專案裡現成的交付 PNG 當 diff 基線是錯的……正確做法是動手前先自己渲染一份基線。」</em>

<strong>為什麼用假場次驗證 P4</strong>：批次邏輯的 bug 通常在「壞掉的輸入」才會浮現。
先用刻意的爛資料把失敗路徑走完，比用真資料跑 24 場才發現好。

---

## 8. 關鍵決策與取捨

| # | 決策 | 放棄了什麼 | 為什麼 |
|---|---|---|---|
| 1 | 零 npm 依賴，用 Node 內建 <code>WebSocket</code> + CDP | Puppeteer 的便利（自動等待、截圖、profile 管理） | 本機 npm 受 PowerShell 執行策略阻擋、要下載 Chromium、離線風險。而且我們只需要「開頁面 → 跑一段 JS → 拿 base64」這三件事，CDP 直接做更省 |
| 2 | 渲染走 http，不走 file:// | 「雙擊 index.html 就能用」的隨手性 | 換來：內嵌降為選用（每場省 4.3 MB）、換素材刷新即生效、canvas 不會被汙染 |
| 3 | <code>extends</code> 只做單層 | 深層設定繼承 | 24 場只需要「縣市層 + 場次層」兩層。深鏈會讓「這個值從哪來」變成要追鏈的問題 |
| 4 | 少於預設人數時**少畫**並警告 | 硬塞版面 | 版面跑掉是靜默的品質災難；少一位候選人是顯眼的、可接受的 |
| 5 | 刪掉 <code>ELECTION_2014</code> 轉接層 | 相容舊資料檔 | 兩份格式 + 手工轉換 = 欄位改名時靜默失效的溫床。一次性遷移成本遠低於長期代價 |
| 6 | 驗證用「區塊外逐像素相同」而非全畫面 | 簡單的全畫面比對 | 全畫面比對會被字型抗鋪齒打斷，然後團隊就會開始「習慣性忽略失敗」。<strong>驗證一旦被習慣性忽略就等於沒有</strong> |
| 7 | 地圖擦標題比例自動偵測 + 明確失敗 | 沿用寫死值 | 24 張不同來源的圖，寫死一定會錯。猜錯會讓標題糊在地圖上，而那種錯誤在縮圖看不出來 |
| 8 | v1 只做直轄市長（24 場） | 一次做完總統／立委 | 全國型是另一種版面（無單一縣市地圖、需要全國色階）。混在一起做會讓 L3 的版面座標設計失焦 |

---

## 9. 風險

| 風險 | 影響 | 緩解 |
|---|---|---|
| **P2 泛化改壞 2014 的畫面** | 高 | P0 基準 + P1/P2 逐像素驗收；泛化只動資料流不動座標 |
| **字型在別的機器上缺** | 中 | <code>theme.js</code> 已有 font stack 與 fallback；manifest 記錄字型清單；缺字型時 <code>verify_all.py</code> 報警告（不報錯，因為文字寬度改變難以自動判定） |
| **24 場的素材湊不齊**（尤其黨徽、縣市市徽） | 高 | 這是最可能真正卡住的地方。P3 的 <code>pool/</code> 就是為了讓缺件一眼看得出來；<code>build_all.py</code> 開頭就列缺件清單，不要等到渲染才發現 |
| **SHP 只有民國 111 年版本** | 中 | 1993/1997 那幾場的行政區界對不上 → 這幾場本來就不該排進 v1。批次應該**只處理有對應 SHP 年份的場次**，用 <code>region.shp</code> 逐場指定 |
| **Edge 版本更新造成像素差異** | 低 | manifest 記錄版本；基準比對在同版本下有意義，跨版本只做「區塊內」比對 |
| **<code>2×</code> PNG 體積**（5120×2880 約 12 MB × 24 × 2 ≈ 600 MB） | 低 | 產物進 <code>.gitignore</code>；<code>--scales</code> 讓日常只出 1× |

---

## 10. 順手要清的程式債

這些不是本次目標，但會在實作時擋路，先記錄：

| 位置 | 問題 |
|---|---|
| <code>tools/build_board.py:236</code> | <code>for key in payload["candidates"][0]["key"] and [c["key"] for c in ...]</code> —— <code>and</code> 左邊是非空字串（恆真），所以能跑，但這是無意的。應為 <code>and</code> 誤植 |
| <code>boardlib/manifest.py:1-217</code> | <code>from typing import Optional</code> 有被用到，但 <code>_card_size</code> 的註解寫 <code>Tuple</code> 而 import 段沒 <code>Tuple</code>（靠 <code>__future__ annotations</code> 沒炸） |
| <code>tools/verify_board.py:4-5</code> | 路徑寫死，搬去 fixtures |
| <code>.gitignore</code> | <code>Video/boards/</code> 與 <code>Video/tools/</code> 目前都還是 untracked（<code>git status</code> → <code>??</code>）。<strong>方案動工前應先納入版控</strong>——記憶裡已經因此被坑過一次（「素材與程式碼都可能無法還原」） |
| <code>Share/</code> | 舊版單場實作，是 <code>_engine</code> 的來源。P3 完成後可歸檔，保留 <code>data/election-2014.js</code> 作為 <code>verify_board.py</code> 的比對基準 |
| <code>boards/README.md:96-101</code> 「已知限制」兩條 | 正是本方案 P2／P3 的內容，完成後把該節改成指向 NewSolution |

---

## 11. 附錄：環境實測（本機驗證過）

| 項目 | 結果 |
|---|---|
| Node | v24.18.0，<code>globalThis.WebSocket</code> = function，<code>globalThis.fetch</code> = function → **零依賴 CDP 可行** |
| Python | 3.14.7 |
| Python 套件 | PIL 12.3.0、numpy 2.5.3、geopandas 1.1.4、shapely 2.1.2、openpyxl 3.1.5、cv2 5.0.0、matplotlib 3.11.2、pyogrio 0.13.0（<code>fiona</code> 無 → 走 pyogrio，現有 <code>geo.py</code> 正常） |
| Chromium | **只有 Edge 154.0.4258.48**（<code>C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe</code>），沒有 Chrome |
| Edge headless | <code>--headless=new --remote-debugging-port=9333</code> → <code>/json/version</code> 回 <code>Edg/154.0.4258.48</code> + 合法 <code>webSocketDebuggerUrl</code> ✓ |
| npm | <code>npm</code> → <code>D:\npm.ps1</code>，被 PowerShell 執行策略阻擋（<code>npm.cmd</code> 可繞過，但本方案不需要 npm） |
| 資料量 | 277 個 xlsx；<code>MayoralElections/data/</code> 涵蓋 1989～2022 |
| 版控 | <code>Video/</code> 未進 git（<code>?? Video/boards/</code>、<code>?? Video/tools/</code>） |
