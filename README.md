# 台灣歷屆選舉得票率地圖繪製 / Taiwan Election Vote-Rate Maps

> 基於政府公開資訊平台提供的 **SHP 村里界圖資** 與 **中選會（CEC）／政大選舉研究中心** 之選舉資料，
> 用 Python 將各級選舉在鄉鎮市區、村里層級的得票率繪製成地圖。
>
> This project draws vote-percentage (得票率) choropleth maps for Taiwan elections,
> based on **Ministry of Interior village-boundary SHP data** and **CEC / NCCU election data**.
>
> 本專案由 AI 生成，AI 率百分之百。_This project was generated entirely by AI._

---

## 目錄 / Table of Contents

- [專案簡介 / Overview](#專案簡介--overview)
- [資料來源 / Data Sources](#資料來源--data-sources)
- [核心流程 / Core Pipeline](#核心流程--core-pipeline)
- [目錄結構 / Directory Structure](#目錄結構--directory-structure)
- [依賴與安裝 / Dependencies & Setup](#依賴與安裝--dependencies--setup)
- [使用範例 / Usage Examples](#使用範例--usage-examples)
- [地圖輸出 / Map Outputs](#地圖輸出--map-outputs)
- [擴充指南 / Extending the Project](#擴充指南--extending-the-project)
- [歷史行政區變遷 / Administrative Boundary History](#歷史行政區變遷--administrative-boundary-history)

---

## 專案簡介 / Overview

將歷年選舉開票資料（投開票所／村里層級）整理為「得票率」資料表，再依候選人或政黨
以不同色階填圖，產出全台或是單一縣市的**得票率披彩地圖（choropleth）**。

本專案涵蓋的選舉：

| 選舉類型 | 屆次／年份 |
|---|---|
| 立法委員「全國不分區及僑居國外國民」| 2008（第 7 屆）、2012（第 8 屆）、2016（第 9 屆）、2024（第 11 屆）|
| 立法委員「區域／縣市」| 2024（第 11 屆，多縣市比較圖）|
| 總統副總統 | 1996、2000、2024（第 16 屆）|
| 臺灣省省長 | 1994 |
| 台北縣／新北市長 | 1993、1997、2001、2005、2010、2014、2018、2022 |
| 高雄市長 | 2018、2022 |
| 其他 | 2001 立委政黨票、空圖（Empty Map）產出 |

涵蓋層級：**村里（village）** 與 **鄉鎮市區（township）** 兩種解析度。

---

## 資料來源 / Data Sources

- **邊界圖資（SHP）**：內政部「村里界歷史圖資」`VILLAGE_MOI_1111118.shp`（座標系統 TWD97 / EPSG:3826）。
  此檔位於專案外（預設路徑 `D:\Windows\Documents\村里界歷史圖資_111\...`）。
- **選舉資料**：中央選舉委員會投票結果頁面（經國立政治大學選舉研究中心 `vote.nccu.edu.tw` 存檔），
  由 `Get_data/` 爬蟲下載，或直接放入各選舉資料夾的 `Data/`、`data/` 中。
- `.gitignore` 排除 `*.xlsx / *.xls / *.pdf / *.jpg / *.jpeg`，原始資料檔不入庫；PNG 地圖則納入版本控管。

---

## 核心流程 / Core Pipeline

整體資料流為一個兩階段管線：

```text
原始開票檔（xls/xlsx，投開票所級）
        │  convert_{year}_*.py        ① 轉換
        ▼
{年份}{縣市}_得票率.xlsx  （3 工作表：各里彙總／各鄉鎮彙總／縣市彙總）
        │  {Converge_to_map / DrawMap / {year}*Party}.py  ② 製圖
        ▼
得票率地圖 PNG
```

### 製圖方式Ａ：SHP 村里級地圖（geopandas + matplotlib + OpenCV + Pillow）

用內政部村里界 SHP 直接繪製，一里一色，適用全台或單縣市：

1. 讀入 SHP（`EPSG:4326` → 轉 `EPSG:3826`）；
2. 依「村里名稱」配對得票率資料（`normalize_text` 正規化 + `SequenceMatcher` 模糊比對處理異體字，如 峯/峰、舘/館）；
3. 取各村里**領先者**依該候選人色階填色；村界 1px、鄉鎮界 2–4px、縣市界 3–6px 黑色邊線；
4. 全台圖把金門、馬祖以 1:1 放大**插圖（inset）** 放在左上角；
5. 用 OpenCV 將每個像素**量化**到最接近的調色盤顏色，再用 Pillow 合成右側標題＋圖例面板。

代表腳本：
- `MayoralElections/scripts/Converge_to_map.py`
- `KaohsiungMayorlElections/scripts/Converge_to_map_kaohsiung.py`
- `2024Precident/scripts/Draw_National_President_2024.py`（全台 2024 總統）
- `Empty_Map/DrawMap.py`（空白輪廓圖）

### 製圖方式Ｂ：Colorful 底色圖替換（County 全台鄉鎮級）

不需 SHP 即可產出**全台 368 鄉鎮市區**地圖：

1. 事先把彩版底圖 `Colorful.png` 每個鄉鎮填上**唯一 ID 色**；
2. `Name_Color_Correspondence.xlsx` 記錄「鄉鎮名 ↔ 顏色」對照；
3. 製圖時以 numpy 一次做「唯一色 → 得票率色階」的全圖查表替換；
4. Pillow 加上標題、圖例。文字一律用 `Shared/scripts/Print_word.py` 的透明背景圖渲染。

代表腳本：`County/{1996President, 2000President, 2001Legislator, {2008,2012,2016,2024}LegislatorParty}.py`。

### 兩種顏色圖例風格：`10/` 與 `20/`

多數製圖腳本都有兩個子資料夾的變體：

| 風格 | 色階起點 | 色階間距 | 用途 |
|---|---|---|---|
| `10/` | 約 10% | 10% | 對比度較低、細分領先者 |
| `20/` | 35%（取領先最小值下取整）| 5% | 強調「領先幅度」的深淺 |

政黨／候選人配色慣例（見 `Shared/Color.txt`）：

| 政黨 / 候選人 | 代表色 |
|---|---|
| 中國國民黨（侯友宜）| 藍 |
| 民主進步黨（賴清德）| 綠 |
| 台灣民眾黨（柯文哲）| 青／水藍 |
| 新黨（王建煊）| 黃／金 |
| 無黨團結聯盟（2016）| 粉紅 |
| 無黨籍（台南區域立委）| 灰階 |

---

## 目錄結構 / Directory Structure

```text
TaiwanElection/
├── 2008Legislator-at-Large/   第 7 屆立委不分區（Data/ 原始 xls、scripts/convert_2008_to_rates.py）
├── 2012Legislator-at-Large/   第 8 屆立委不分區（scripts/convert_2012_to_rates.py）
├── 2016Legislator-at-Large/   第 9 屆立委不分區（scripts/convert_2016_to_rates.py）
├── 2024Legislator-at-Large/   第 11 屆立委不分區（data/ 得票率 xlsx、maps/10–20、scripts/convert_2024_to_rates.py）
├── 2024DistrictLegislator/    第 11 屆區域立委（Tainan/ 台南為主、多縣市 Compare 比較圖）
├── 2024Precident/             第 16 屆總統（data/、maps/、scripts/Draw_National_President_2024.py）
├── County/                    全台鄉鎮級製圖（Colorful.png 底圖法）
│   ├── {year}*President.py / {year}LegislatorParty.py
│   ├── color_map_from_rates.py / convert_1994_to_rates.py
│   └── README_立委不分區資料整理與地圖製作.md   ← 不分區流程詳盡指南
├── Empty_Map/                 空白輪廓圖（DrawMap.py、Taiwan.png、各縣市空白圖）
├── Get_data/                  爬蟲（vote.nccu.edu.tw）：GetData.py、scrape_*.py、Convert.py
├── KaohsiungMayorlElections/  高雄市長 2018/2022（scripts/、data/、maps/10–20）
├── MayoralElections/          台北縣／新北市長 1993–2022（scripts/、data/、maps/10–20）
├── Shared/                    共用工具
│   ├── scripts/Print_word.py  中文字元渲染（透明背景 PNG）
│   └── Color.txt              共用色階定義
├── maps/
│   ├── County/                全台鄉鎮級得票率地圖 PNG（1994→2024）
│   └── _text_cache/           圖內文字 PNG 磁碟快取
└── txt/                       舊版／備份繪圖腳本（副檔名為 .txt 的 .py）
```

各選舉資料夾內部慣例：

```text
{Year}{Election}/
├── data/ 或 Data/     原始開票檔／轉換後的 {年份}{縣市}_得票率.xlsx
├── scripts/           轉換與製圖腳本（+ 10/、20/ 變體）
└── maps/              產出的 PNG（根目錄、10/、20/）
```

---

## 依賴與安裝 / Dependencies & Setup

Python ≥ 3.10（已在 CPython 3.14 驗證執行）。需要下列套件：

| 套件 | 用途 |
|---|---|
| pandas, numpy | 資料整理 |
| geopandas, shapely | SHP 讀取、幾何運算 |
| matplotlib | 繪圖、中文文字渲染 |
| Pillow (PIL) | 影像合成 |
| opencv-python (cv2) | 影像二值化、色彩量化 |
| openpyxl | 讀寫 xlsx |
| requests, beautifulsoup4 | 爬蟲 |

```bash
pip install pandas numpy geopandas shapely matplotlib pillow opencv-python openpyxl requests beautifulsoup4
```

> 註：geopandas 在 Windows 上如安裝失敗，可改用 conda：`conda install geopandas`。

---

## 使用範例 / Usage Examples

### 1. 總統選舉（2024）資料轉換

```powershell
python "2024Precident\scripts\convert_2024_president_percent.py"
```

會自動掃描 `2024Precident\data\` 中所有「第16任…在{縣市}各村(里)得票數一覽表.xlsx」
並輸出 `2024{縣市}_得票率.xlsx`。

### 2. 繪製全台 2024 總統村里級地圖

```powershell
python "2024Precident\scripts\Draw_National_President_2024.py"
```

輸出：`2024Precident\maps\全臺灣2024年總統副總統選舉_得票率地圖.png`

### 3. 繪製單一縣市（新北市長）地圖

```powershell
python "MayoralElections\scripts\Converge_to_map.py"
python "MayoralElections\scripts\10\Converge_to_map.py"   # 10% 色階
python "MayoralElections\scripts\20\Converge_to_map.py"   # 35% 起 5% 色階
```

### 4. 全台鄉鎮級立委不分區地圖（底圖法）

```powershell
python "County\2016LegislatorParty.py"
python "County\2024LegislatorParty.py"
```

輸出：`maps\County\{年份}年立法委員選舉_得票率地圖.png`

### 5. 爬取中選會／政大開票資料

```powershell
python "Get_data\GetData.py" <選舉結果網址> [--region] [-o out.xlsx]
```

### 6. 產出空白輪廓地圖

```powershell
python "Empty_Map\DrawMap.py"
```

---

## 地圖輸出 / Map Outputs

| 位置 | 內容 |
|---|---|
| `maps\County\` | 全台鄉鎮級：1994 省長、1996/2000 總統、2001/2008/2012/2016/2024 立委 |
| `MayoralElections\maps\10\`、`maps\20\` | 各年份新北縣市長（含 2001 個別候選人：王建煊／蘇貞昌）|
| `KaohsiungMayorlElections\maps\` | 高雄市長 2018、2022 |
| `2024Precident\maps\` | 全台 2024 總統 + 台北／台中／新竹比較圖 |
| `2024DistrictLegislator\maps\` | 台南區域立委（A/B 版）及多縣市 Compare 圖 |
| `2024Legislator-at-Large\maps\` | 新北不分區政黨票 |
| `Empty_Map\` | 全台及各縣市空白輪廓圖 |

---

## 擴充指南 / Extending the Project

新增一個選舉年份／類別，大致四步（詳見 `County\README_立委不分區資料整理與地圖製作.md`）：

1. **新增轉換器**：依原始檔格式寫 `convert_{year}_to_rates.py`，輸出 `{年份}{縣市}_得票率.xlsx`（3 工作表）。
2. **複製製圖模板**：
   ```powershell
   Copy-Item County\2016LegislatorParty.py County\{year}LegislatorParty.py
   ```
3. **修改 5 處常數**：
   `DATA_DIR` / `OUT_PNG`、`OLD_COUNTY_MAP`（縣市名對應）、`RATE_COLOR_STOPS`＋`CANDIDATES`、
   `TITLE_LINES`（屆次與日期）、`VARIANT_CHAR_MAP`（異體字）。
4. **驗證**：腳本自我檢查輸出應符合「鄉鎮市區 368、有資料 368、無資料 0」；
   因 AI 無法直接看圖，以像素統計（藍／綠／其他色 pixel 數）驗證配色正確。

---

## 歷史行政區變遷 / Administrative Boundary History

影響 `OLD_COUNTY_MAP`／`SPECIAL_TOWN` 的改制：

| 日期 | 變遷 |
|---|---|
| 2008-01-01 | 高雄縣三民鄉 → 那瑪夏鄉 |
| 2010-12-25 | 五都改制：臺北縣→新北市；臺中／臺南／高雄縣市合併升格 |
| 2014-12-25 | 桃園縣 → 桃園市 |
| 2010 前後 | 臺南市西區＋中區 → 中西區 |

---

## 授權 / License

未指定授權。資料來源為政府公開資訊（中選會、內政部）與政大選舉研究中心，
使用時請注意各自著作權與引用規定。