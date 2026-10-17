# 把「地圖」批量做成看板 —— 現況與操作手冊

> 本文只**描述**現有管線，不動任何既有程式碼。
> 對象：想把 `NewSolution/png/map/<年份>/` 底下的一批得票率地圖，
> 批量做成 `boards/<id>/` 看板並輸出 PNG 的人。
>
> 撰寫時間：2026-10-04。基於當時的程式碼與目錄實況。

---

## 0. 先釐清一件事：「地圖」不是看板的輸入，是看板的**素材**

看板（2560×1440 的開票看板）**不是**由一張 PNG「拼」出來的，
而是由**得票資料（xlsx）+ 素材（地圖／圖例／市徽／黨徽）**在前端 Canvas 上現畫的。

所以「把地圖批量做成看板」這句話，在現有架構下真正的意思是：

> **把一批「各年得票率地圖」連同它們的資料與圖例，批量灌進看板管線，一次輸出多張看板 PNG。**

其中「地圖」只扮演一個角色：看板右側那塊**上色的得票率底圖**。
一張地圖 ↔ 一場選舉 ↔ 一個看板目錄。批量 = 對每個年份目錄各跑一次這條鏈。

---

## 1. 資料從哪來、成品到哪去（一張圖看懂）

```
  NewSolution/data/<年>台北市長.xlsx        逐里得票（唯一資料源）
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ A. 產地圖   NewSolution/Converge_to_map_taipei.py            │
  │    讀 xlsx + 村里界 SHP → 上色 → 白底三張圖                   │
  │    輸出：NewSolution/png/map/<year>/{map,map2,legend}.png    │
  └─────────────────────────────────────────────────────────────┘
            │  （白底 RGB / 透明底 RGBA）
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ B. 素材透明化   NewSolution/tool/build_assets.py             │
  │    依配方 assets.map.json：地圖白→透明、圖例原樣搬、黨徽去背   │
  │    輸出：NewSolution/png/processed/  ← 全專案唯一成品落點     │
  └─────────────────────────────────────────────────────────────┘
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ C. 建看板   tools/build_board.py boards/<id>                 │
  │    讀 meta.json + source/data.xlsx + SHP → 聚合成行政區       │
  │    只「找圖」不「做圖」→ 寫 board.js / board.files.js         │
  └─────────────────────────────────────────────────────────────┘
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ D. 渲染   node tools/render_boards.mjs --all --scale 1       │
  │    啟動 Edge（CDP）逐場截圖 → out/<id>_2560x1440.png          │
  │    + out/manifest.json（SHA256 可回歸）                       │
  └─────────────────────────────────────────────────────────────┘
```

**關鍵約定（踩過雷，別改）**

| 約定 | 內容 | 原因 |
|---|---|---|
| 地圖檔名固定 | `map.png`（村里版）／`map2.png`（區級版）／`legend.png` | JS 端按名字取圖，不查 JSON |
| 成品唯一落點 | `NewSolution/png/processed/` | 不回寫原圖、不寫 `boards/<id>/assets/` |
| 靜態伺服器根 | 必須是 `Video/`，不是 `boards/` | `board.files.js` 用 `../../NewSolution/...` 引素材 |
| 圖例不轉透明 | `legend.png` 走 `how=copy` | 它本身就是透明底白字，再轉會被吃掉 |

---

## 2. `map/` 資料夾的真相（你問的那個）

專案根目錄有個 **空的 `map/`**，`Code/` 也是空的。它們是早期規劃留下的空殼，
**目前整條管線完全不讀不寫它們**，可以直接忽略。

真正放地圖的是 **`NewSolution/png/map/<年份>/`**：

```
NewSolution/png/map/
  1994/  map.png  map2.png  legend.png   ( + 1996.png 舊檔，無消費者 )
  1998/  map.png  map2.png  legend.png
  2002/  map.png  map2.png  legend.png
  2006/  map.png  map2.png  legend.png
  2010/  map.png  map2.png  legend.png
  2014/  map.png  map2.png  legend.png
  2018/  map.png  map2.png  legend.png
  2022/  map.png  map2.png  legend.png
  1990/  map.png                          ( 舊行政區界線圖，實驗產物 )
```

- `map.png` —— 村里版，每一里按「領先候選人」上色（看板預設用這張）。
- `map2.png` —— 區級版，只畫區不畫里；畫布與 `map.png` **完全同尺寸同範圍**，可疊合。
- `legend.png` —— 圖例，透明底白字；直接畫好，不需再處理。

> **年份 = 一場選舉 = 一個看板候選**。所以「批量」就是「把這些年份一次跑完」。

---

## 3. 批量做看板：三條命令（現行可用的最短路徑）

現況**還沒有**一鍵批次腳本（`tools/build_all.py` 尚未實作）。
但每一步本身都支援「一次處理多場」，把它們順序串起來即是批量。
以下全部在 `Video/` 目錄下執行。

### 步驟 A — 一次產出全部年份的地圖

```bash
# 用有感 Python（裝了 geopandas / matplotlib / cv2 / PIL 的那個）
"C:\Users\Windows\AppData\Local\Microsoft\WindowsApps\python.exe" \
  NewSolution/Converge_to_map_taipei.py
```

- 不帶參數 → 依 `DATASETS` 表**全部年份**跑一遍（1994…2022）。
- 只做某一年 → 加關鍵字：`... Converge_to_map_taipei.py 2002`。
- 輸出到 `NewSolution/png/map/<year>/`。
- 這步最慢（顏色量化是瓶頸），跑一次約數十秒～數分鐘，視年份數。

> ⚠️ 只產**臺北市**。主程式會擋掉 `city != 臺北市` 的資料集；1990 舊區圖另有
> `Converge_to_map_taipei_1990.py`。

### 步驟 B — 一次把所有地圖／素材透明化

```bash
"C:\Users\Windows\AppData\Local\Microsoft\WindowsApps\python.exe" \
  NewSolution/tool/build_assets.py
```

- 依 `NewSolution/tool/assets.map.json` 的配方，處理 `map` / `party` / `share` 三類。
- 成品統一寫到 `NewSolution/png/processed/`。已存在的成品會跳過（要重做加 `--force`）。
- 只想檢查齊備：`--check`（缺件退出碼 1）。
- 常用：`--year 2018`、`--kind map`、`--dry-run`。

### 步驟 C — 批次建看板 + 批次渲染

```bash
# C1. 逐場建置（現階段建置仍是逐場，因為要指定目錄）
for id in 1994-taipei-mayor 1998-taipei-mayor 2002-taipei-mayor \
          2006-taipei-mayor 2010-taipei-mayor 2014-taipei-mayor \
          2018-taipei-mayor 2022-taipei-mayor; do
  "C:\Users\Windows\AppData\Local\Microsoft\WindowsApps\python.exe" \
    tools/build_board.py "boards/$id"
done

# C2. 一次渲染全部（引擎一次啟動 Edge，逐場截圖）
"C:\Users\Windows\.workbuddy\binaries\node\versions\22.22.2-5\node.exe" \
  tools/render_boards.mjs --all --scale 1 --out ./out
```

- `build_board.py` 每場寫出 `board.js` / `board.files.js` / `board.assets.js`。
- `render_boards.mjs --all` 掃 `boards/` 下所有含 `meta.json` 的目錄；
  有 `.skip` 標記的會**自動跳過**（`2014-newtpei-mayor` 就是這樣被排除的）。
- 多倍率：`--scales 1,2`（1× = 2560×1440，2× = 5120×2880）。
- 產物在 `out/`：`<id>_2560x1440.png` + `manifest.json`（含 SHA256／bytes／尺寸）。
- 渲染後會順手輸出 `out/layout/<id>.json`，可再跑：
  ```bash
  "...python.exe" tools/verify_layout.py     # 版面斷言，FAIL 退出碼 1
  ```

> **「新增一場」= 加一個 `boards/<id>/` 目錄（`meta.json` + `source/`），JS／Python 零改動。**
> 批次腳本會自動撿到它。

---

## 4. 一場看板由哪些檔案組成（批次前要準備的東西）

```
boards/<id>/
  meta.json          ★ 人工維護：選舉名稱／年份／候選人（key/姓名/政黨/號次/總票/當選）
                      + region.county=臺北市, unitLevel=village, mapVariant=map|map2
  index.html         薄殼，複製 boards/_template/index.html
  source/
    data.xlsx        逐里得票（從 NewSolution/data/ 複製對應檔）
    map.png          得票率地圖 = processed/map/<year>/map.png（或 map2）
    legend.png       圖例      = processed/map/<year>/legend.png
    city_seal.png    市徽      = processed/share/city_seal.png
    emblem.png       國徽      = processed/share/emblem.png
    mark_elected.png 當選標誌  = processed/share/mark_elected.png
    party_<key>.png  黨徽      = processed/party/party_<key>.png
  board.js / board.files.js / board.assets.js   ← build 產生，別手改
  .cache/geojson.json                            ← SHP dissolve 快取，可刪
```

- **建置前的齊備檢查**由 `manifest.check_sources()` 負責；缺檔會直接報錯並列出。
- `boards/<id>/assets/` 只作舊場次的回退來源，新場次不再往寫。
- **沒有候選人照片**這一項：看板卡面只填政黨純色，照片由使用者後製合成。

現成的 8 場台北市長看板目錄，是 `tools/_gen_taipei_boards.py`（一次性工具）生出來的；
它同時產生「村里版」與「區級版」兩套（`<id>` 與 `<id>-map2`），差別只在 `mapVariant`。

---

## 5. 常見坑（照著避開）

| 症狀 | 原因 | 解法 |
|---|---|---|
| 渲染時素材 404 | 靜態根設成 `boards/` | 必須 `--root Video/`（`render_boards.mjs` 預設已是 `Video/`） |
| 地圖邊緣一圈白邊 | 地圖沒過白→透明，或容差變了 | 跑 `build_assets.py`；容差固定 `threshold=12` |
| 圖例整片不見 | 把 `legend.png` 也做了白→透明 | 它 `how=copy`，原樣搬即可 |
| 看板整場變灰 | 早年資料欄位只有人名、無政黨 | 見 `Converge_to_map_taipei.py` 的 `PARTY_COLOR_GROUPS`；姓名要能對到政黨 |
| 村里對不到、留白 | 早年里界與圖資不符 | 圖資按年份切：`<2019` 用 106（cp950）、`≥2019` 用 111（UTF-8） |
| 單場渲染後其他場消失 | `--boards` 會把 `manifest.json` 覆寫成只有該場 | 要全量就重跑 `--all` |

---

## 6. 現況與未完成（別期待不存在的東西）

**已可用**：步驟 A–D 全部跑通，8 場台北市長看板（村里版 + 區級版）已產出於 `out/`。

**尚未實作**（README 設計規格裡有、程式碼還沒有）：

- ❌ `tools/build_all.py` —— 「一條命令建置+渲染整批」的總入口（現需自己寫 for 迴圈，見 §3-C1）。
- ❌ `tools/verify_all.py` —— 三層批次驗證。
- ❌ `boards/_defaults/` 的 `extends` 繼承、`pool/` 跨場素材池。
- ❌ `build_board.py --embed`：`board.assets.js` 目前每場都產（file:// 直接開才需要）。

> 也就是說：**「批量」現在是「三個步驟各自支援多場 + 自己串」，不是「單一指令」。**
> 想再往前一步，缺的就是 `build_all.py` 那層薄薄的編排。

---

## 7. 一句話總結

> 把每一年當「一場」，三條命令依序跑：
> **產地圖（`Converge_to_map_taipei.py`）→ 透明化（`build_assets.py`）→ 建置+渲染（`build_board.py` ×N ＋ `render_boards.mjs --all`）**。
> 「新增一場」永遠只是加一個 `meta.json` + `source/`，程式零改動。
