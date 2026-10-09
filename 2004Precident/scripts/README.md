# 2004 總統副總統選舉 得票率地圖 —— 由 2000 版就地改造（暨改造經驗總結）

> 本目錄的六支區域腳本，是由 **`2000Precident/scripts/`**（2000 第十屆版）**就地複製改造**而來：
> 換**得票資料（2004 第十一屆）**、**候選人（兩強）**與**配色**；並且依需求，
> **臺中底圖由民國85年 SHP 改回 `twvillage2012.json`**、**嘉義市維持現行 pre2010 作法**。
>
> 繪圖管線、村名修補、沿革合併、匹配稽核、四項自檢等機制的完整說明，見
> **`1996Precident/scripts/README.md`**（§2～§14）與 **`2000Precident/scripts/README.md`**，本文不再重複。
>
> 共用模組：`2020Precident/scripts/Draw_National_President_2020.py`（簡稱 `nat`）

---

## 0. 本次改造的四項使用者需求（原文對照）

| # | 需求 | 落實 |
|---|---|---|
| 1 | 「臺中的部分改成**原本的 `.json`**，不要目前代碼的 1996 的地圖」 | 中彰投 `TCN3` 底圖模式 `json_shp` → **`json`**（純 `twvillage2012.json`），移除民國85年臺中市 SHP |
| 2 | 「**嘉義市還是保留原本的嘉義市**」 | `YCT4` 嘉義市村里層**續用** `twVillage_pre2010.geo.json`（108 里）＋ `CITY_VILL_REPAIR`，**不動** |
| 3 | 「目前項目是 2000 年的，希望改成 **2004 年**，資料改為 `2004總統副總統選舉_得票率.xlsx`」 | 全域年份 `2000`→`2004`、`第十屆`→`第十一屆`、資料路徑改 2004 |
| 4 | 「閱讀 `2000Precident/scripts/README.md`，不要多餘讀取」 | 以 2000 README 為唯一改造藍本，未做無關探索 |

---

## 1. 檔案與成品一覽

| 檔案 | 區域 | 底圖 |
|---|---|---|
| `Draw_North4_President_2004.py` | 北北基宜 | `twvillage2012.json` |
| `Draw_TCM4_President_2004.py` | 桃竹苗 | 同上 |
| `Draw_YCT4_President_2004.py` | 雲嘉南 | 同上 ＋ **嘉義市村里層用 pre2010（不改）** |
| `Draw_South2_President_2004.py` | 高屏 | 同上 |
| `Draw_TCN3_President_2004.py` | 中彰投 | 同上（**本次由「＋民國85年 SHP」改回純 json**） |
| `Draw_TaichungCity_President_2004.py` | 臺中舊市區 | `twvillage2012.json` 之**臺中舊市區 8 區**（**新建 `json_oldcity` 模式，不用 SHP**） |
| `_gen_2004.py` | 生成器 | 產生 TCM4／YCT4／South2／TCN3／TaichungCity 五支 |
| `village_name_repair.py` | 共用 | 村名修補（PUA／■／誤植／更名） |
| `village_lineage_north4.py` | 共用 | 北北基宜村里沿革表 |

`Draw_North4_President_2016.py` 為 2016 版原始檔，**保留不動**。

**選舉資料**：`data/2004總統副總統選舉_得票率.xlsx`（工作表「各里彙總」）；
跨里合併另用 `data/2004總統副總統選舉_縣市鄉鎮村里.xlsx`（「村里層級明細」得票數）。

---

## 2. 與 2000 版的差異（本次全部改動）

### 2.1 候選人：3 組 → 2 組（兩強對決）

2004 第十一屆登記**兩組**：陳水扁／呂秀蓮(01,民主進步黨)、連戰／宋楚瑜(02,中國國民黨)。
2000 版的三強（連／扁／宋）收斂為兩強，**刪去宋楚瑜一組**。

```python
CAND_NAMES = ["連戰", "陳水扁"]     # 順序＝ RATE_COLOR_STOPS 順序，非 Excel 欄位順序
CAND_RATE_COLS = [f"{n}得票率" for n in CAND_NAMES]
```

### 2.2 配色（沿用 2000 版前兩組，刪去第三組灰階）

| 組 | 候選人 | 政黨 | 色階（35% 起，5% 一階） |
|---|---|---|---|
| 1 | 連戰 | 中國國民黨 | 藍 `#A6E9FF → #010D29`（35~100%，**12 階**） |
| 2 | 陳水扁 | 民主進步黨 | 綠 `#E8FFE0 → #071A09`（35~100%，**12 階**） |
| ~~3~~ | ~~宋楚瑜~~ | — | **刪除**（2004 宋為連戰副手，不獨立成組） |

> 兩組色階**逐字沿用** 2000 版（`RATE_COLOR_STOPS` 前兩組原樣搬移），僅移除第三組。

### 2.3 資料路徑與識別字全量替換

`2000總統副總統選舉_*.xlsx` → `2004總統副總統選舉_*.xlsx`；
輸出檔名／報告標題／`layer_name`／識別字（`VARIANT_CHAR_MAP_2004`、`TOWN_VILL_RENAME_2004`、
`rename_town_vill_2004`…）一併更名；檔名 `_2000.py` → `_2004.py`。

### 2.4 臺中底圖：民國85年 SHP → `twvillage2012.json`（本次最大結構改動）

| 腳本 | 2000 版 | 2004 版 |
|---|---|---|
| `Draw_TCN3_*`（中彰投） | `json_shp`：2012 json ＋ 民國85年臺中市 8 區 SHP | **`json`**：純 `twvillage2012.json`（不再用 SHP） |
| `Draw_TaichungCity_*`（舊市區單圖） | `shp`：只用民國85年 SHP | **`json_oldcity`**：2012 json 篩「臺中舊市區 8 區」 |

- 生成器 `_gen_2004.py` 的 `REGIONS` 同步改：TCN3 `base="json"`、TaichungCity `base="json_oldcity"`。
- 新增底圖模式字典 `BASEMAP_*["json_oldcity"]`（`METERS_PER_PIXEL=4.0`、`SCALE_UP=1.10`，
  同 2000 版舊市區的高解析度設定），並讓 `load_base_map` 在讀入 2012 json 後**篩 `TARGET_TOWNS` 8 區**：

  ```python
  TARGET_TOWNS = ['中區', '東區', '西區', '南區', '北區', '西屯區', '南屯區', '北屯區']
  gdf = gdf[gdf["TOWNNAME"].astype(str).str.strip().isin(TARGET_TOWNS)].copy()
  ```

- 舊市區 8 區在 2012 圖資實測為 **214 個里圖斑**、bbox 約 23.2 × 12.7 km → 圖幅 6512×3565 px。

### 2.5 嘉義市：維持 pre2010（依需求不動）

`YCT4` 的嘉義市村里層**繼續**採 `twVillage_pre2010.geo.json`（108 里）＋
`CITY_VILL_REPAIR {("西區","磚嗂里"):"磚窑里"}`；外緣與區界仍沿用 2012 界，**只換村里細分線**。
本次**未做任何改動**。

---

## 3. 改造方法論（可複用經驗，核心）

> 以下是把「某一屆總統得票率地圖」複製改造為「下一屆」的通用步驟，
> 已在 **1996→2000** 與 **2000→2004** 兩次改造中驗證。

### 3.1 六階段流水線

```
① 讀上一屆 README（唯一藍本，避免無關探索）
② 勘驗：資料表結構 + 底圖圖資範圍（寫成 _inspect_*.py，跑一次即丟）
③ 機械替換：年份/屆次/檔名（_convert.py，正則守衛）
④ 定向替換：候選人/色階/文案/底圖模式（_convert2.py + 手改生成器）
⑤ 校驗：roundtrip 還原比對（_verify_convert.py）
⑥ 執行：先跑 1 支代表腳本 → 全跑 6 支 → 四項自檢
```

> 步驟 ②③④⑤ 的一次性工具（`_inspect_*.py`、`_convert*.py`、`_verify_convert.py`）
> 屬改造過程產物，**用畢已刪除**（備份見 `.workbuddy/backup/2004scripts_*`）；
> 下表保留其用途說明，供下屆改造照做即可。

### 3.2 機械替換的「三重保護」

1. **正則守衛**：`2000` 會出現在 `20000`、`2000.0`（`REMOTE_MAX_DIST_M`）、`12000` 等常量中，
   必須用邊界鎖定：
   ```python
   RE_2000 = re.compile(r"(?<!\d)2000(?!\d)(?!\.0)")
   ```
2. **roundtrip 校驗**：把新檔的 `2004→2000`、`第十一屆→第十屆` **還原**後，
   須與原檔**逐字元相同**（`_verify_convert.py`）；不一致即機械替換誤傷。
3. **殘留掃描**：替換後 grep 舊標記（`宋楚瑜`、`三強`、`（3 組）`…）確認歸零。

> 檔案為 **UTF-8**，讀寫務必 `encoding="utf-8"`，且保持原換行；替換後再跑一次 roundtrip 最保險。

### 3.3 定向替換用「精確字串配對」，不要用正則

候選人與色階是**多行結構**（`CAND_NAMES`、`RATE_COLOR_STOPS`、docstring 表頭），
用**完整舊字串 → 新字串**的 `str.replace`（`_convert2.py`）最安全；
逐檔列印 `changed=` 與殘留計數，確保**七檔同步**。

### 3.4 生成器與產出腳本「雙寫」陷阱

`_gen_*.py` 內建 **HEADER 模板**（含 `CAND_NAMES`／色階／docstring），
而 6 支產出腳本各自**再帶一份同樣的 header**。改候選人/色階/文案時，
**生成器的模板字典（`BASEMAP_*`、REGIONS）與現有 6 支腳本都要改**，
否則「重生成」會產生 diff，或某支腳本漏改。

### 3.5 底圖模式抽象（`BASEMAP_*` 字典）

生成器以 `base` 欄位選擇模式，每個模式對應一組字典項：
`BASEMAP_DOC / DIFF_DOC / CONFIG / FUNCS / MPP / SCALEUP / BASE_PATH / BASE_LABEL / BASE_KIND …`。
本次新增 `json_oldcity` 即在**所有**這些字典補一項；而 `json_shp`／`shp` 兩個舊模式
在本次改造後（REGIONS 已無區域採用）即成**死代碼**，已連同 `CITY_SHP*`／`BASE_SHP*`／
`_apply_city_shp`／`SHP_NAME_REPAIR` 一併移除（見 §7）。

### 3.6 底圖來源切換的三類做法

| 情境 | 做法 |
|---|---|
| 全區改用同名 json | `base="json"`（REGIONS 一行） |
| 只換某縣市村里層（嘉義市） | 保留 `CITY_GEOJSON`+`_apply_city_pre2010` 機制，**不動** |
| 從大範圍 json 取子集另畫一圖（臺中舊市區） | 新增模式 + `TARGET_TOWNS` 篩選 |

### 3.7 候選人數變化會連鎖影響

`CAND_NAMES` 由 3→2 時，必須同步：`CAND_RATE_COLS`、`RATE_COLOR_STOPS`、
docstring 表頭、報告文案（「三強」→「兩強」）、**明細得票數欄位挑選**。
明細欄位務必**依 `CAND_NAMES` 逐名挑選**，不可「取全部 `_得票數` 欄」：
```python
cnt_cols = [next(c for c in dc.columns if c.endswith("_得票數") and c.startswith(n))
            for n in CAND_NAMES]
```

### 3.8 執行前先勘驗、後全跑

- 先用 `_inspect_data.py` 確認新資料表的**工作表名／欄位名**與舊版一致（本專案均為「各里彙總」）。
- 先用 `_inspect_basemaps.py` 確認新底圖的**縣市名與鄉鎮清單**（`twvillage2012.json` 用小寫
  `county/town/village`；`twVillage_pre2010` 用 `COUNTYNAME/TOWNNAME/VILLAGENAM`），
  避免「縣市名對不上 → 整區全白」。
- 先跑 **1 支代表腳本**（含特殊機制的 YCT4／TCM4 較佳），四項自檢全綠再全跑。

### 3.9 四項自檢＝驗收門檻

② 層覆蓋、② 層連通分量、油漆桶不變式、幾何參考／非允許色／村外非白。
判準：**非單色區域 0、非允許色 0、村外非白 0、幾何參考差異 ≤0.0051%**。

---

## 4. 執行結果（六支全綠）

四項自檢**六支全部通過**：非單色區域 0、非允許色 0、村外非白 0、幾何參考差異 ≤0.0051%。

| 區域 | 腳本 | 精確 | 沿革合併 | 村名修補 | 無資料 | 反向缺漏 | 領先村里 連戰/陳水扁 | 圖幅 px |
|---|---|---:|---:|---:|---:|---:|---|---|
| 北北基宜 | North4 | 1845 | 30 | 14 | 5 | 7 | **1044 / 831** | 3729×5596 |
| 桃竹苗 | TCM4 | 1029 | — | 10 | 36 | 3 | 726 / 303 | 4433×4716 |
| 雲嘉南 | YCT4 | 1587 | — | 31 | 17 | 30 | 154 / **1433** | 5006×5422 |
| 高屏 | South2 | 1339 | — | 11 | 23 | 22 | 242 / 1097 | 4568×8895 |
| 中彰投 | TCN3 | 1449 | — | 15 | 32 | 2 | 599 / 850 | 6384×5685 |
| 臺中舊市區 | TaichungCity | 212 | — | 3 | 2 | 0 | 134 / 78 | 6512×3565 |

> 幾何參考差異（px／%）：North4 1064/0.0051%、TCM4 675/0.0032%、YCT4 1038/0.0038%、
> South2 813/0.0020%、TCN3 950/0.0026%、TaichungCity 243/0.0010%。

**成品**：`2004Precident/maps/*2004年總統副總統選舉_得票率地圖.png` 6 張
＋ `*2004_無資料與未匹配村里.md` 6 份。

---

## 5. 一鍵重跑

```powershell
$env:PYTHONIOENCODING='utf-8'
py 2004Precident\scripts\Draw_North4_President_2004.py       # 北北基宜（約 1 分鐘）
py 2004Precident\scripts\Draw_TCM4_President_2004.py         # 桃竹苗
py 2004Precident\scripts\Draw_YCT4_President_2004.py         # 雲嘉南
py 2004Precident\scripts\Draw_South2_President_2004.py       # 高屏
py 2004Precident\scripts\Draw_TCN3_President_2004.py         # 中彰投
py 2004Precident\scripts\Draw_TaichungCity_President_2004.py # 臺中舊市區
Get-ChildItem 2004Precident\maps\*2004* | Select Name, @{n='MB';e={[math]::Round($_.Length/1MB,2)}}
```

### 5.1 生成器

`_gen_2004.py` 以 `Draw_North4_President_2004.py` 的「圖資清理」以下段落為共用尾段，
改 `REGIONS` 配置即可再擴充區域。**重生成驗證**：TCM4／TCN3／TaichungCity 三支
與本目錄現有檔案**逐字元相同**；YCT4（嘉義市 pre2010 機制）與 South2（那瑪夏更名機制）
含手工增補邏輯、無法由生成器復現（與 1996／2000 版情況相同）。

---

## 6. 待辦

| 項目 | 說明 |
|---|---|
| 村名修補逐年校驗 | 每屆資料的村里集合不同，`VOTE_NAME_REPAIR`（偉功/武功）、`TOWN_VILL_RENAME_*`（那瑪夏 3 村＋桃源拉芙蘭）、`CITY_VILL_REPAIR`（嘉義磚嗂→磚窑）須以當屆資料實測為準，不可直接沿用 |
| 臺中舊市區 8 區範圍 | `TARGET_TOWNS` 目前硬編 8 區；若改做縣市合併後的行政區須同步調整 |
| README 色階註記 | `2000Precident/scripts/README.md` §2.2 記為連戰藍 `#B0E3F0→#000814`，但 2000 代碼實為 `#A6E9FF→#010D29`（2004 沿用後者）；建議回填 2000 README 使圖文一致 |

---

## 7. 死代碼清理（2026-10-09）

全專案經 AST 靜態掃描（未使用 import／未被引用函式與常量）後，清理如下，
清理後**六支腳本全部重跑、四項自檢全綠**，且 TCM4／TCN3／TaichungCity 重生成後
與清理前**逐字元相同**（證明移除的皆為死代碼，畫面零變化）：

| 類別 | 內容 | 處置 |
|---|---|---|
| ① 一次性腳本／產物 | `_convert.py`、`_convert2.py`、`_verify_convert.py`、`_inspect_basemaps.py`、`_inspect_data.py`、`_diag.py`、`_deadcode.py`、`_run_all.log`、`_thumb_taichung.png` | 已刪（備份於 `.workbuddy/backup/`） |
| ② 生成器死模式（2004 特有） | `_gen_2004.py` 的 `json_shp`／`shp` 兩模式：`_CITY_SHP_WIN`、`CITY_SHP*`、`BASE_SHP*`、`BASEMAP_*_JSONSHP`、`BASEMAP_*_SHP`、`_SHP_REPAIR_CFG`／`_SHP_REPAIR_FUNC`，及所有 `BASEMAP_*` 字典的 `"json_shp"`／`"shp"` 鍵 | 已刪（`_gen_2004.py` 減少 248 行） |
| ③ 死常量 | `TITLE_LINES`、`LINE_VILLAGE_PX`（6 支 Draw ＋ 生成器模板各 2 行）、`Draw_YCT4` 的 `CITY_GEOJSON_TOWN_COL`／`CITY_GEOJSON_VILL_COL` | 已刪 |

> ② 的 `json_shp`／`shp` 在 2000 版**仍被 REGIONS 使用**（TCN3 用 `json_shp`、臺中舊市區用 `shp`），
> 是本次「臺中改用 json」後才變成死代碼，屬 2004 特有冗餘。
> ③ 則是 1996／2000 遺留下來的既有冗餘（各年目錄都有），本次僅 2004 清理；如需一致，可另案同步前三屆。
> `Draw_North4_President_2016.py` 為各年統一的「原始參照檔」，**保留不動**。
