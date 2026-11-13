# 台灣選舉得票率地圖

把歷屆選舉的官方開票資料，整理成**村里 → 鄉鎮市區 → 縣市**三層的得票率表，再依「領先候選人／政黨」填色，輸出可直接引用的得票率地圖；同一批資料也會做成 4K 開票看板與配樂影片。

專案成品多為維基百科未收錄的原創內容，尤其是**村里層級**的總統票、政黨票與區域立委選區地圖。

<p align="center">
  <img src="Precident/2024Precident/maps/%E5%85%A8%E8%87%BA%E7%81%A32024%E5%B9%B4%E7%B8%BD%E7%B5%B1%E5%89%AF%E7%B8%BD%E7%B5%B1%E9%81%B8%E8%88%89_%E5%BE%97%E7%A5%A8%E7%8E%87%E5%9C%B0%E5%9C%96.png" width="30%" alt="2024 總統副總統選舉得票率地圖">
  <img src="maps/County/2024%E5%B9%B4%E7%AB%8B%E6%B3%95%E5%A7%94%E5%93%A1%E9%81%B8%E8%88%89_%E5%BE%97%E7%A5%A8%E7%8E%87%E5%9C%B0%E5%9C%96.png" width="30%" alt="2024 立法委員選舉得票率地圖">
  <img src="Mayors/2022NineInOne/map/2022%E7%B8%A3%E5%B8%82%E9%95%B7%E9%81%B8%E8%88%89_%E9%84%89%E9%8E%AE%E5%B8%82%E5%8D%80%E5%BE%97%E7%A5%A8%E7%8E%87.png" width="30%" alt="2022 縣市長選舉鄉鎮市區得票率地圖">
</p>

## English Summary

This project turns official Taiwan election results into vote-share tables and renders them as high-resolution choropleth maps at village, township and county resolution, using Ministry of the Interior boundary data. The same data feeds a board/video pipeline that produces 4K result boards and music-synced MP4s. Most outputs — especially village-level party-list and legislator maps — are original content not found on Wikipedia.

Coverage: presidential elections 1996–2024; Taipei County / New Taipei City mayors 1989–2022; Kaohsiung mayors 2018–2022; the 2022 nine-in-one local elections (22 counties/cities, village and township maps + 4K boards); legislator at-large party vote 2008–2024; regional legislator races (2008 Kaohsiung/Taichung, 2024 across 11 counties/cities); the 1994 Taiwan provincial governor election; and Taipei City mayor boards 1994–2022. A single-page spectrum-weighted forecast for the 2026 Keelung mayoral race lives in `predict/`.

## 這個專案產出什麼

| 產出 | 內容 | 位置 |
|---|---|---|
| 得票率地圖 | 村里／鄉鎮市區／縣市三種解析度，含圖例、比例尺與離島附圖 | `Precident/*/maps/`、`Mayors/*/maps/`、`LegislationYuan/maps/`、`maps/County/` |
| 跨屆比較圖 | 兩屆得票率並列（1994vs2000、2000vs2024、2008vs2020、2012vs2016、2020vs2024） | `maps/County/` |
| 統計與稽核文件 | 村里領先政黨統計、無資料與未匹配村里清單、縣市／鄉鎮版稽核報告 | 各專案 `maps/`、`LegislationYuan/2012-2024/map/` |
| 4K 開票看板 | 3840×2160，資料套版現畫（非拼圖），33 場選舉版面 | `Video/src/boards/`、`Mayors/2022NineInOne/board/` |
| 配樂影片 | 看板 → 交叉淡化 → 音畫同源時間軸 → MP4 | `Video/src/tools/make_video.py` |
| 互動預測頁 | 基隆市長選舉的政治光譜加權推估（單檔 HTML） | `predict/index.html` |

目前約有 240 支 Python 腳本、35 支 JS/MJS、380 多張 PNG 成品；`git clone` 約 300 MB（含高解析度地圖）。

## 涵蓋的選舉

| 類別 | 年份 | 備註 |
|---|---|---|
| 總統副總統 | 1996、2000、2004、2008、2012、2016、2020、2024 | 每屆 6 個區域村里圖；2020、2024 另有全台圖 |
| 臺北縣／新北市長 | 1989、1993、1997、2001、2005、2010、2014、2018、2022 | 村里／鄉鎮級與跨屆比較 |
| 高雄市長 | 2018、2022 | 村里級 |
| 縣市長（九合一） | 2022（22 縣市） | 村里＋鄉鎮地圖、22 張縣市看板＋全國政黨版圖看板 |
| 立委不分區（政黨票） | 2008、2012、2016、2020、2024 | 全台村里／鄉鎮／縣市三種版本、村里領先政黨統計 |
| 立委區域 | 2008（高雄市／縣、臺中市／縣）、2024（臺北、新北、基隆、桃園、新竹、苗栗、臺中、雲林、臺南、高雄、臺東等） | 以村里 dissolve 出選區，選區界畫白線 |
| 立委（2001 鄉鎮級） | 2001 | 政黨得票率地圖 |
| 臺灣省長 | 1994 | 全台鄉鎮級 |
| 臺北市長 | 1994–2022（8 屆） | 開票看板與配樂影片 |
| 基隆市長（預測） | 2026 | 光譜分群加權互動頁 |

## 專案結構

```
TaiwanElection/
├── Get_data/            開票資料爬蟲（1994–2022）、轉換工具與爬蟲經驗文件
├── Precident/           總統副總統 1996–2024；每屆 data/ + scripts/ + maps/
├── Mayors/              縣市長：臺北縣／新北、高雄、2022 九合一（地圖＋看板＋影片）
├── LegislationYuan/     立委：不分區政黨票、區域立委、村里領先政黨統計
├── County/              「唯一色底圖換色」繪圖程式、全台鄉鎮底圖、跨屆比較圖
├── Script/              早期村里級繪圖核心（SHP / GeoJSON 兩種圖資）
├── Empty_Map/           縣市輪廓與村里界空白底圖、智慧標註程式
├── Base_JSON/           GeoJSON 圖資＋drawcore 引擎（本機資料，不入版控）
├── maps/County/         全台鄉鎮級成品圖與跨屆比較圖
├── Shared/              共用色票（Color.txt）與文字渲染模組
├── Video/               開票看板與配樂影片產線（src/ 入庫，素材與產物不入庫）
├── predict/             基隆市長光譜加權預測互動頁
├── txt/                 各縣市繪圖腳本原型（.txt 內容實為 Python）
└── 子项目技能总结.md     各子專案可複用技能與工程經驗總覽
```

## 資料流

```
官方開票頁（中選會／政大選研中心存檔）
        │  Get_data/scrape_*.py：SHA1 磁碟快取、平行抓取、三層交叉驗算
        ▼
Excel：縣市 / 鄉鎮市區 / 村里 三層得票數
        │  convert_*_to_rates.py：先加總票數、再算得票率（絕不平均百分比）
        ▼
統一「各里彙總」表（選舉區別｜鄉鎮市區｜村里｜各候選人／政黨得票率）
        │  geopandas 讀村里界 → 名稱正規化 → 精確＋模糊比對
        ▼
線稿三層（1px 村里界、3px 鄉鎮界、5px 縣市界／海岸線）
        │  洪水填充（以黑線為堤壩，顏色不跨越任何一條線）＋圖例＋標題
        ▼
得票率地圖 PNG
        │  Video/src/tools：meta.json＋xlsx＋素材 → 前端 Canvas 現畫
        ▼
4K 開票看板 PNG（3840×2160）
        │  make_video.py：畫面 xfade 與音訊 acrossfade 共用同一組轉場中點
        ▼
配樂 MP4（+faststart，可邊下邊播）
```

## 快速開始

### 1. 環境

Python 3.11 以上（實測 3.13），主要依賴：

```powershell
python -m pip install pandas openpyxl xlrd numpy pillow `
  geopandas shapely matplotlib rasterio scikit-image opencv-python scipy `
  requests beautifulsoup4 opencc-python-reimplemented fonttools imageio-ffmpeg
```

看板渲染需要 Node.js 22+ 與 Microsoft Edge（`render_boards.mjs` 走 Node 內建 WebSocket 直接驅動 Edge CDP，**零 npm 依賴**）。影片合成用 `imageio-ffmpeg` 內附的靜態 ffmpeg，不需另裝。

Windows 主控台輸出中文建議先設：

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### 2. 外部圖資

以下資料**不在版控內**，需自行準備：

| 資料 | 用途 | 預期位置 |
|---|---|---|
| 內政部村里界歷史圖資（106、108、111 年版） | 村里級繪圖 | `D:\Windows\Documents\村里界歷史圖資_111\...`（路徑寫在腳本檔頭） |
| `Base_JSON/`（GeoJSON＋`drawcore.py`） | 鄉鎮底圖、空白底圖 | 專案根目錄 |
| `Video/assets/`、`Video/data/`、`Video/dist/` | 看板素材、原始 xlsx、產物 | `Video/` 下（僅 `src/`、`docs/` 入庫） |

各版本 SHP 的 `.dbf` 編碼不同：106 年版為 `cp950`，108、111 年版為 UTF-8；舊檔 `crs` 可能是 `None`，需先 `set_crs("EPSG:4326")` 再投影 `EPSG:3826`。

### 3. 跑一張圖

```powershell
# 抓 2016 總統三層得票率（寫入 Get_data/*.xlsx）
python Get_data\scrape_president_2016_rates.py

# 畫 2016 桃竹苗村里級地圖（腳本檔頭有 SHP 絕對路徑，換機器要先改）
python Precident\2016Precident\scripts\Draw_TCM4_President_2016.py

# 2024 立委不分區政黨票（鄉鎮市區版，免 SHP，用 Colorful.png 換色）
python County\2024LegislatorParty.py

# 2024 區域立委：臺南市 A 版（20m/px）或 B 版（10m/px）
python LegislationYuan\2024DistrictLegislator\scripts\Tainan_legislative_map.py A

# 2008 立委不分區：全台村里版
python LegislationYuan\2008Legislator-at-Large\scripts\atlarge\Draw_Taiwan_AtLarge_2008.py
```

### 4. 看板與影片

```powershell
cd Video

# 單場看板：建置資料 → 無頭渲染（素材需先備妥於 dist/assets/）
python src\tools\build_board.py src\boards\2018-taipei-mayor
node src\tools\render_boards.mjs --boards 2018-taipei-mayor

# 總統場建置器：一次重建某年份的村里版／區級版／桃竹苗版
python src\tools\_gen_president_boards.py 2024
node src\tools\render_boards.mjs --boards 2024-president-north

# 全量渲染 + 版面驗證（PASS/FAIL 逐場輸出）
node src\tools\render_boards.mjs --all
python src\tools\verify_layout.py

# 影片：先出草稿，確認後再正式合成
python src\tools\make_video.py --draft
python src\tools\make_video.py
```

2022 九合一 22 縣市看板有獨立產線（素材去背 → 建置 → 渲染 → 版面驗證），完整指令與版面參數見 [`Mayors/2022NineInOne/board/README.md`](Mayors/2022NineInOne/board/README.md)。

## 子專案說明

### `Get_data/` —— 開票資料爬蟲

`GetData.py` 是通用多層入口，會自動辨識 `vote3 / vote312 / vote313 / vote31 / vote32` 五種頁面層級；`scrape_president_1996~2020.py` 是各屆專用版。核心手法：手動指定 `big5` 解碼、以 `sha1(url)` 做磁碟快取斷點續抓、全國→縣市→鄉鎮→村里逐級下鑽、三層加總與官方公告票數對帳。方法論見 [`Get_data/经验总结_爬虫与环境.md`](Get_data/经验总结_爬虫与环境.md)。

### `Precident/` —— 總統選舉（1996–2024）

每屆固定 `data/ + scripts/ + maps/`，繪圖依地理分區拆成 `North4 / South2 / TCM4 / TCN3 / YCT4` 等腳本，共用的 `President20xx_Common.py` 提供讀色票、地名正規化、洪水填充、平票斜紋與自檢。新增縣市組合的完整檢查清單見 [`Precident/2016Precident/scripts/README.md`](Precident/2016Precident/scripts/README.md)。

### `Mayors/` —— 縣市長選舉

- `MayoralElections/`：臺北縣／新北市 1989–2022，配置驅動（`DATASETS` 描述每屆差異），保留 `scripts/10`、`20`、`35` 等色階演進版本。
- `KaohsiungMayorlElections/`：高雄市 2018、2022。
- `2022NineInOne/`：22 縣市村里／鄉鎮地圖、22 張 4K 看板與全國政黨版圖看板、配樂影片。

### `LegislationYuan/` —— 立法委員

- `2008Legislator-at-Large/`：2008 區域立委（高雄、臺中）＋不分區；README 把「立委選區界白線、與縣市界重合處讓位黑線」的規則寫死，可直接當新選區模板。
- `2012Legislator-at-Large/`、`2016Legislator-at-Large/`：早期不分區資料與轉換程式。
- `2012-2024/`：2012–2024 不分區政黨票批次繪圖（村里／鄉鎮／縣市）＋村里領先政黨統計。
- `2024Legislator-at-Large/`、`2024DistrictLegislator/`：2024 政黨票與區域立委（含臺南 A/B 兩版色階、`verify_tainan.py` 像素驗證）。
- `Atlarge2008-2024/`、`maps/`：整理後的全台成品與稽核文件。

### `County/`、`Script/`、`Empty_Map/`、`Base_JSON/` —— 底圖與繪圖引擎

- `County/`：以「**底圖色＝身份證**」的方式換色——`Colorful.png` 每個鄉鎮一種唯一純色，`Name_Color_Correspondence.xlsx` 做顏色↔地名對照；用 `np.unique(..., return_inverse=True)` 一次映射，完全不需 SHP。適合快速產出鄉鎮級與跨屆比較圖。
- `Script/`：早期村里級核心，含 `normalize_text()` 名稱正規化、精確＋`difflib` 模糊匹配、1px 線寬控制與邊界擦除。
- `Empty_Map/`：空白底圖與智慧標註（質心→代表點→16 方向避線→字級分檔→小面編號）。
- `Base_JSON/`：GeoJSON 圖資與 `drawcore.py` 光柵化引擎（三層疊線、微孔洞填平、安全寫盤），**本機資料，不進版控**。

### `Video/` —— 開票看板與配樂影片

`src/engine/` 是所有場次共用的 Canvas 引擎，`src/boards/<id>/meta.json` 是一場選舉的唯一人工設定；新增一場＝加一個 `meta.json`＋素材，程式零改動。產物統一落 `dist/`，可整包刪除重建。目錄規範以 [`Video/.workbuddy/DIRECTORY_CONVENTION.md`](Video/.workbuddy/DIRECTORY_CONVENTION.md) 為唯一真相，操作手冊見 [`Video/docs/`](Video/docs/)。

### `predict/` —— 光譜加權預測

`Keelong.md` 是資料（8 個政治光譜群 × 各候選人滲透率），`index.html` 直接解析 Markdown 表格，用純 SVG 畫環形扇形；改數字不必改程式。

## 繪圖與工程慣例

這些規則是全專案共通、也是改圖前必讀的紅線：

1. **三層線稿**：村里界 1px、鄉鎮市區界 3px、縣市界／海岸線 5px；立委選區界另畫白線（與縣市界重合段讓位給黑線）。
2. **色階固定**：政黨代表色集中在 `Shared/Color.txt`（各子專案另有 `color.txt`）；得票率自 35% 起、5% 一檔，領先政黨決定色系、得票率決定深淺，跨圖可比。
3. **洪水填充**：以線稿為封閉堤壩，每一塊 4-連通區域填單色，顏色取區域內像素所屬村里的眾數，保證顏色永不跨越黑線。
4. **名稱匹配三件套**：NFKC → 異體字／PUA 映射（如「濓→濂」）→ 去「鄉鎮市區村里」後綴；先精確後模糊，未匹配一律輸出清單並拒絕出圖。
5. **聚合順序**：同一個村里有多個投開票所時，**先加總票數、再算得票率**，不平均百分比。
6. **每一環都要自檢**：資料層三層加總對帳；圖層「油漆桶單色不變式＋獨立幾何逐像素比對＋允許色檢查」；看板 `verify_layout.py` 逐場斷言；影片用波形 MAE 驗音畫對位；渲染器以 SHA256 manifest 做逐位元組回歸。
7. **禁 simplify**：邊界幾何不做簡化，只做 `make_valid`、去零面積碎片與填平微小孔洞（孔洞是光柵化散點的元凶）。

## 新增一屆選舉的 SOP

1. **抓資料**：複製對應的 `scrape_*.py`，改入口 URL、年份、輸出檔名；跑 `_check.py` 做三層對帳。
2. **轉得票率**：寫 `convert_*_to_rates.py`，輸出「各里彙總」標準表（先加票數再算率）。
3. **選圖資與比例尺**：依選舉年挑最接近的村里界版本；先估 `bbox/比例尺` 是否小於 `MAX_PX`，過大就從 20m 放寬到 30m。
4. **複製繪圖腳本**：只改 5 處常數（資料檔、SHP、`TARGET_COUNTIES`、輸出檔名、圖例起點），跑完確認四項自檢全綠。
5. **補文件**：在該屆 `maps/` 留下「無資料與未匹配村里」報告；需要看板時在 `Video/src/boards/` 新增 `meta.json` 與素材。

## 資料來源與聲明

- 開票資料：中央選舉委員會公開選舉結果，透過政治大學選舉研究中心存檔（`vote.nccu.edu.tw/cec/`）逐頁取得；立委部分屆次直接使用中選會投開票所原始檔（`.xls`／`.xlsx`）。
- 邊界圖資：內政部地政司「村里界歷史圖資」（民國 106、108、111 年版）。
- 投票率、選舉人數等行政數據：維基百科與中選會公告，僅作看板頁眉資料。
- 本倉庫的地圖、圖表、看板與影片為專案原創產出；原始資料與圖資的授權依各主管機關規定。引用成品時請註明「資料來源：中選會」與本專案。
- 本倉庫目前未附 `LICENSE` 檔。

## 文件索引

| 文件 | 內容 |
|---|---|
| [`子项目技能总结.md`](子项目技能总结.md) | 各子專案的可複用技能與跨專案工程經驗（最推薦先讀） |
| [`Video/docs/README_批量做看板.md`](Video/docs/README_批量做看板.md) | 看板產線：素材、版面、批次渲染 |
| [`Video/docs/README_合成视频.md`](Video/docs/README_合成视频.md) | 看板 → 配樂 MP4 的合成與質檢 |
| [`Mayors/2022NineInOne/board/README.md`](Mayors/2022NineInOne/board/README.md) | 22 縣市 4K 看板的資料來源、版面設計與 25 條踩坑記錄 |
| [`LegislationYuan/2008Legislator-at-Large/README.md`](LegislationYuan/2008Legislator-at-Large/README.md) | 區域立委繪圖管線、選區白線幾何規則、六項自檢 |
| [`Precident/2016Precident/scripts/README.md`](Precident/2016Precident/scripts/README.md) | 選縣市、挑圖資、迴針修復與出圖檢查清單 |
| [`County/README_立委不分區資料整理與地圖製作.md`](County/README_立委不分區資料整理與地圖製作.md) | 「唯一色底圖換色」的模板複刻流程 |
| [`Get_data/经验总结_爬虫与环境.md`](Get_data/经验总结_爬虫与环境.md) | 老 ASP 網站爬取、編碼與環境問題 |
| [`Video/.workbuddy/DIRECTORY_CONVENTION.md`](Video/.workbuddy/DIRECTORY_CONVENTION.md) | `Video/` 目錄規範（唯一真相來源） |
| [`目录占用分析与删除影响.md`](目录占用分析与删除影响.md)、[`大文件与重复文件分析报告.md`](大文件与重复文件分析报告.md) | 倉庫體積、重複檔與清理建議 |

## 已知限制

- **大量資料不在版控內**：`Base_JSON/`、`Video/assets/`、`Video/data/`、`Video/dist/`、`*.xls(x)`、`*.pdf`、`*.jpg` 皆被 `.gitignore` 排除；新 clone 只會拿到程式與已入庫的 PNG 成品。
- **絕對路徑**：多支繪圖腳本把村里界 SHP、Python 執行檔寫死在 `D:\Windows\...`，換機器需先改檔頭常數。
- **文件簡繁混用**：`Video/docs/` 與部分 README 描述的是重構前的目錄（如 `Video/tools`、`Video/final`），現行結構以 `Video/.workbuddy/DIRECTORY_CONVENTION.md` 為準。
- **資料與圖資的時點差異**：選舉年的村里名稱未必與所選圖資版本一致（改制、合併、改名），已用異體字映射與模糊匹配處理，剩餘案例逐案列在該屆「無資料與未匹配村里」報告，使用成品前建議先讀該報告。
- **比例尺與記憶體**：全台村里圖動輒 6000×12000 px，`MAX_SAFE_PX`／`MAX_PX` 是防爆記憶體的保險，調整前先看該腳本註解。

---

> 本專案以資料正確性與可追溯性為優先：每一張圖背後都有對應的資料表、稽核報告與自檢輸出。若只想快速看成品，從 `maps/County/` 與各屆 `maps/` 開始；若想改圖，請先讀上表的子專案文件。
