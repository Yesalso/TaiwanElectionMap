# 台湾历届选举得票率地图绘制 / Taiwan Election Vote-Rate Maps

> **中文**：基于政府公开信息平台提供的 **SHP 村里界图资** 与 **中选会（CEC）／政大选举研究中心** 的选举资料，
> 用 Python 将各级选举在乡镇市区、村里的得票率绘制成地图。
>
> **English**: This project draws vote-percentage (得票率) choropleth maps for Taiwan elections,
> using **Ministry of Interior village-boundary SHP data** together with **CEC / NCCU election data**.
>
> 本项目由 AI 生成，AI 率百分之百。/ _This project was generated entirely by AI._
>
> ⭐ 大部分地图与图表皆为**维基百科上所没有的原创内容**（各村里、乡镇市区级得票率地图与统计图表）。
> _Most maps and charts herein are **original content not found on Wikipedia** (village/township-level
> vote-rate maps and statistics charts)._

---

## 目录 / Table of Contents

- [项目简介 / Overview](#项目简介--overview)
- [数据来源 / Data Sources](#数据来源--data-sources)
- [核心流程 / Core Pipeline](#核心流程--core-pipeline)
- [代码实现 / Implementation Details](#代码实现--implementation-details)
- [目录结构 / Directory Structure](#目录结构--directory-structure)
- [依赖与安装 / Dependencies & Setup](#依赖与安装--dependencies--setup)
- [使用示例 / Usage Examples](#使用示例--usage-examples)
- [地图输出 / Map Outputs](#地图输出--map-outputs)
- [扩展指南 / Extending the Project](#扩展指南--extending-the-project)
- [历史行政区变迁 / Administrative Boundary History](#历史行政区变迁--administrative-boundary-history)

---

## 项目简介 / Overview

**中文**：将历年选举开票资料（投开票所／村里层级）整理为「得票率」数据表，再依候选人或政党
以不同色阶填图，产出全台或是单一县市的**得票率披彩地图（choropleth）**。

**English**: Raw election results are cleaned at the polling-station / village level and converted into
vote-rate tables, then each village or township is filled with a color from the winning candidate's ramp,
producing **vote-rate choropleth maps** for the whole island or a single county/city.

本项目涵盖的选举 / Elections covered:

| 选举类型 Election | 届次／年份 Terms / Years |
|---|---|
| 立法委员「全国不分区及侨居国外国民」/ Legislators (at-large, party list) | 2008（第 7 届/7th）、2012（第 8 届/8th）、2016（第 9 届/9th）、2024（第 11 届/11th）|
| 立法委员「区域／县市」/ Legislators (regional) | 2024（第 11 届/11th，多县市比较图 multi-county comparison maps）|
| 总统副总统 / President & Vice President | 1996、2000、2024（第 16 届/16th）|
| 台湾省省长 / Taiwan Provincial Governor | 1994 |
| 台北县／新北市长 / Taipei County / New Taipei City mayors | 1993、1997、2001、2005、2010、2014、2018、2022 |
| 高雄市长 / Kaohsiung City mayors | 2018、2022 |
| 其他 / Others | 2001 立委政党票（2001 legislator party votes）、空图（blank map）产出 |

涵盖层级：**村里（village）** 与 **乡镇市区（township）** 两种分辨率。
_Resolution: **village (村里)** and **township (乡镇市区)** level._

---

## 数据来源 / Data Sources

**中文**：
- **边界图资（SHP）**：内政部「村里界历史图资」`VILLAGE_MOI_1111118.shp`（坐标系 TWD97 / EPSG:3826）。
  此文件位于项目外（默认路径 `D:\Windows\Documents\村里界歷史圖資_111\...`）。
- **选举资料**：中央选举委员会投票结果页面（经国立政治大学选举研究中心 `vote.nccu.edu.tw` 存档），
  由 `Get_data/` 爬虫下载，或直接放入各选举文件夹的 `Data/`、`data/` 中。
- `.gitignore` 排除 `*.xlsx / *.xls / *.pdf / *.jpg / *.jpeg`，原始数据文件不入库；PNG 地图则纳入版本管理。

**English**:
- **Boundary data (SHP)**: Ministry of Interior historical village boundaries, `VILLAGE_MOI_1111118.shp`
  (CRS: TWD97 / EPSG:3826). This file lives **outside the repo** (default path
  `D:\Windows\Documents\村里界歷史圖資_111\...`).
- **Election data**: Central Election Commission result pages (archived by the NCCU Election Study Center,
  `vote.nccu.edu.tw`), downloaded via the `Get_data/` scrapers or placed manually into each election
  folder's `Data/` / `data/` directory.
- `.gitignore` excludes `*.xlsx / *.xls / *.pdf / *.jpg / *.jpeg`: raw data files are **not** committed,
  while PNG maps are version-controlled.

---

## 核心流程 / Core Pipeline

**中文**：整体数据流为一个两阶段管道：

**English**: The pipeline has two stages:

```text
原始开票档（xls/xlsx，投开票所级）
Raw results (xls/xlsx, polling-station level)
        │  convert_{year}_*.py        ① 转换 convert
        ▼
{年份}{縣市}_得票率.xlsx  （3 工作表：各里彙總／各鄉鎮彙總／縣市彙總）
                                      (3 sheets: village / township / county summaries)
        │  {Converge_to_map / DrawMap / {year}*Party}.py  ② 制图 draw
        ▼
得票率地图 PNG / Vote-rate map PNG
```

### 制图方式Ａ：SHP 村里级地图 / Method A: SHP village-level maps
### (geopandas + matplotlib + OpenCV + Pillow)

**中文**：用内政部村里界 SHP 直接绘制，一里一色，适用于全台或单县市：

**English**: Draws directly from the village-boundary SHP; one color per village, for the whole island or a
single county/city:

1. 读取 SHP（`EPSG:4326` → 转 `EPSG:3826`）/ Load SHP and reproject to `EPSG:3826`;
2. 依「村里名称」配对得票率数据（`normalize_text` 规范化 + `SequenceMatcher` 模糊比对处理异体字，如 峯/峰、舘/館）
   / Match villages to rate data by name (`normalize_text` normalization + `SequenceMatcher` fuzzy matching for
   variant characters, e.g. 峯/峰, 舘/館);
3. 取各村里**领先者**依该候选人色阶填色；村界 1px、乡镇界 2–4px、县市界 3–6px 黑色边线
   / Fill each village by the **winning candidate's** color ramp; 1px village lines, 2–4px township bands,
   3–6px county/city outlines;
4. 全台图把金门、马祖以 1:1 放大**插图（inset）** 放在左上角
   / National maps place Kinmen & Matsu as 1:1 inset boxes in the top-left corner;
5. 用 OpenCV 将每个像素**量化**到最接近的调色盘颜色，再用 Pillow 合成右侧标题＋图例面板
   / OpenCV **quantizes** each pixel to the nearest palette color, then Pillow composites the right-side
   title + legend panel.

代表脚本 / Key scripts:
- `MayoralElections/scripts/Converge_to_map.py`
- `KaohsiungMayorlElections/scripts/Converge_to_map_kaohsiung.py`
- `2024Precident/scripts/Draw_National_President_2024.py`（全台 2024 总统 / national 2024 president）
- `Empty_Map/DrawMap.py`（空白轮廓图 / blank outline maps）

### 制图方式Ｂ：Colorful 底色图替换 / Method B: Colorful base-map recoloring
### (County 全台乡镇级 / national township level)

**中文**：不需 SHP 即可产出**全台 368 乡镇市区**地图：

**English**: Produces maps for all **368 townships** without needing the SHP at draw time:

1. 事先把彩版底图 `Colorful.png` 每个乡镇填上**唯一 ID 色** / Pre-fill each township in `Colorful.png`
   with a **unique ID color**;
2. `Name_Color_Correspondence.xlsx` 记录「乡镇名 ↔ 颜色」对照 / holds the township↔color lookup;
3. 制图时用 numpy 一次做「唯一色 → 得票率色阶」的全图查表替换 / at draw time, numpy performs a whole-image
   lookup mapping unique colors → rate-ramp colors;
4. Pillow 加上标题、图例；文字一律用 `Shared/scripts/Print_word.py` 的透明背景图渲染
   / Pillow adds title & legend; text is always rendered by `Shared/scripts/Print_word.py`.

代表脚本 / Key scripts: `County/{1996President, 2000President, 2001Legislator, {2008,2012,2016,2024}LegislatorParty}.py`。

### 两种颜色图例风格：`10/` 与 `20/` / Two legend styles: `10/` and `20/`

**中文**：多数制图脚本都有两个子文件夹的变体。**English**: Most map scripts ship a `10/` and a `20/` variant.

| 风格 Style | 色阶起点 Ramp start | 色阶间距 Step | 用途 Purpose |
|---|---|---|---|
| `10/` | 约 10% / ~10% | 10% | 对比度较低、细分领先者 / fainter, distinguishes the leader |
| `20/` | 35%（取领先最小值下取整）/ 35% (floored to min. leading rate) | 5% | 强调「领先幅度」的深浅 / emphasizes margin of victory |

政党／候选人配色惯例 / Party & candidate color conventions（见 `Shared/Color.txt`）:

| 政党 / 候选人 Party / Candidate | 代表色 Color |
|---|---|
| 中国国民党（侯友宜）/ KMT (Hou Yu-ih) | 蓝 / blue |
| 民主进步党（赖清德）/ DPP (Lai Ching-te) | 绿 / green |
| 台湾民众党（柯文哲）/ TPP (Ko Wen-je) | 青／水蓝 / cyan / teal |
| 新党（王建煊）/ New Party (Wang Chien-shien) | 黄／金 / yellow / gold |
| 无党团结联盟（2016）/ Non-Partisan Solidarity Union | 粉红 / pink |
| 无党籍（台南区域立委）/ Independents (Tainan regional) | 灰阶 / gray |

---

## 代码实现 / Implementation Details

> 本节介绍脚本内部的关键实现细节，方便阅读与修改代码。
> _This section explains the key implementation details inside the scripts._

### 1. 数据转换（得票率计算）/ Data conversion (vote-rate math)

- **通用转换器**（`convert_2008/2012/2016_to_rates.py`、`convert_2024_to_rates.py`）：
  用 `pd.read_excel(header=None)` 读取原始投票所级 `xls/xlsx`，不依赖乱码文件名，而是**从档内标题取县市名**
  （正则如 `選舉(.+?)各政黨`）。政党的列位置随届别浮动，故代码按「政党政名行 + 政党数 n」推算：
  `有效票数列 = 3 + n`，其后依次为无效票数、投票数。
- **合并以村里为单位**：2012 起把同一「乡镇×村里」的各投开票所得票数加总，再算
  `得票率(%) = 得票數 ÷ 有效票數 × 100`，四舍五入保留 2 位小数。
- **2024 总统转换器**（`convert_2024_president_percent.py`）较特殊：原始档为固定列结构
  （C=柯文哲、D=赖清德、E=侯友宜、F=有效票数A），用 `openpyxl` 逐列读取，跳过无资料的区域小计列，
  输出 `各里彙總` 单工作表。
- 统一输出**3 工作表**格式：`各里彙總`／`各鄉鎮彙總`／`縣市彙總`，供制图脚本直接读取。
  具体字段见 `County/README_立委不分區資料整理與地圖製作.md`。

### 2. 名称规范化与配对 / Name normalization & matching

村里名称在政大资料（表格）与内政部图资（SHP）间常用字不同，所有制图脚本共用同一套规范化函数：

```text
normalize_text(s)
  ├─ str.strip()
  ├─ unicodedata.normalize("NFKC")           # 全角/半角、兼容文件字形统一
  ├─ 去除 Unicode 组合用记号（部首 M 类）
  ├─ 去除零宽/不可见字符（\u200B–\u206F、\uFEFF 等）
  ├─ 去除图资中标注疑难字的方括号 [ ]（如 瓦[磘]里 → 瓦磘里）
  └─ VARIANT_CHAR_MAP.translate             # 异体字对照（峯→峰、舘→館、磘→窯、獇→羌…）
```

- **精确配对**：以 `(县市, 乡镇核心名, 村里核心名)` 为 key 做字典 O(1) 查找；
  `strip_town_suffix` / `strip_village_suffix` 去掉「鄉鎮市區」「村里」后缀。
- **模糊配对**：同乡镇内用 `difflib.SequenceMatcher` 找相似度最高者，且要求：
  - 相似度 ≥ `MIN_SIMILARITY`（0.5），
  - 字符串等长、且只有**一个**字符不同，
  - 该字符对必须是 `VARIANT_FUZZY_GROUPS` 内允许的异体组（如 {峯,峰}、{磘,窯}）。
- 脚本会打印 `精確匹配/異體字匹配/模糊匹配/無資料` 统计，用于自检。

### 3. 投影与图层绘制 / Projection & map rendering

- SHP 若缺 CRS 则视为 `EPSG:4326`，统一转 `EPSG:3826`（TWD97／TWD TM2 台湾）。
- matplotlib 强制 `Agg` 后端（`matplotlib.use("Agg")`，每脚本开头），`DPI=100`；
  画布大小由 `包围框总长 ÷ 米/像素` 决定（单县市默认 1px≈10m，全台约 12m，长宽上限 32000px）。
- 图层顺序（`zorder` 由低到高）：
  1. 村里填色（`facecolor=fill_hex, edgecolor='none'`，关闭抗锯齿防色晕）
  2. 村里黑线 1px
  3. 乡镇界：`dissolve(by=TOWNNAME).boundary` 生成线，再 `buffer(2px)` 成**黑带**用面绘制
  4. 县市界线：全台图 3px、金门/连江/澎湖等小县市 1px 海岸线
  5. 金门、连江附图为 1:1 平移至主图左上角的**插图盒**（6px 外框、乌坵放金门框内空余角落）
- 装饰过滤：宜兰钓岛等离岸岛屿按「距县市形心 > km 阈值的部件」剔除；高雄市 `VILLNAME` 为空的未编制村里、基隆离岸岛也跳过。

### 4. 颜色量化 / Color quantization

matplotlib 反锯齿会产出大量中间色，故绘图后统一**量化**到允许的调色盘：

```python
pixels = img_rgb.reshape(-1, 3).astype(np.float32)        # 全部像素
for start in range(0, n_pixels, CHUNK_SIZE):              # 500_000 一区块
    d = np.sqrt(((chunk - allowed_rgb) ** 2).sum(axis=1)) # 欧氏距离
    min_idx = np.argmin(d, axis=0)                        # 最近色
```

- County 底图法则更进一步：把 24-bit 颜色打包成 `uint32`，构造**全色域 LUT**
  （`lut = np.arange(0x1000000)`，只把「唯一色→填色」的槽位覆盖），
  用 fancy-index 一次处理约 1900 万像素的整图替换。

### 5. 地图文字渲染（Print_word 模式）/ Text rendering (Print_word pattern)

所有标题、图例文字都通过「Shard 的 `Print_word.py` 方式」生成透明背景图，保证中文与 `≤ ~ ≥` 符号都能正常显示：

```text
matplotlib 于 1×1 画布写黑字（CJK：PMingLiU/MingLiU/新細明體/微軟正黑體/SimHei…，符号由 DejaVu Sans 回退）
  → 先量测每行文字的 bbox 尺寸，再按实测尺寸建画布居中绘制
  → plt.savefig 到 BytesIO → cv2.imdecode 灰度 → cv2.threshold(200) 二值化
  → 背景(白)像素 alpha=0、文字像素 alpha=255，得到 RGBA 透明文字图
  → base_img.paste(rgba, xy, mask=rgba.getchannel("A")) 贴回地图
```

- **双层缓存**：进程内 `_TEXT_IMG_CACHE` 以 `(lines, font_size)` 为 key；County 脚本另存
  `maps/_text_cache/<sha256>.png` 磁盘缓存，跨次运行免重渲染。

### 6. 图例自动起点 / Auto legend start tier

- 依「全台最低领先得票率」动态决定图例起点：`start = int(min_win_rate // 5) * 5`；
- 每个色阶标签格式：`≤x%`（首档）、`y~z%`（中档）、`≥w%`（末档）；
- 只显示有领先乡镇的政党/候选人（如 2016 澎湖七美乡的无党团结联盟）。

### 7. 爬虫 GetData.py / Web scraper

- 三种入口页自动识别：`vote3.asp`（全国/县市）→ `vote31.asp`（乡镇）→ `vote32.asp`（村里），
  依网域 URL 判断层级并自动下钻，每次都附带请求间隔与失败重试。
- 页面以 `big5` 解码，`BeautifulSoup` 解析 `<table>`；`--region` 支持 `\u` 转义，避免命令行编码问题。
- 输出交叉表 xlsx：`鄉鎮市區彙總`（每候选人两栏：得票数/得票率）、`村里層級明細`，并附加「总计」行。
  命令行参数：`--region`（只抓某县市）、`--delay`（每页间隔秒）、`--retry`（失败重试次数）。

---

## 目录结构 / Directory Structure

**中文**：**English**：

```text
TaiwanElection/
├── 2008Legislator-at-Large/   7th-term at-large legislators (Data/ raw xls, scripts/convert_2008_to_rates.py)
├── 2012Legislator-at-Large/   8th-term at-large legislators (scripts/convert_2012_to_rates.py)
├── 2016Legislator-at-Large/   9th-term at-large legislators (scripts/convert_2016_to_rates.py)
├── 2024Legislator-at-Large/   11th-term at-large legislators (data/ rate xlsx, maps/10-20, scripts/convert_2024_to_rates.py)
├── 2024DistrictLegislator/    11th-term regional legislators (mainly Tainan + multi-county Compare maps)
├── 2024Precident/             16th-term president (data/, maps/, scripts/Draw_National_President_2024.py)
├── County/                    National township-level drawing (Colorful.png base-map method)
│   ├── {year}*President.py / {year}LegislatorParty.py
│   ├── color_map_from_rates.py / convert_1994_to_rates.py
│   └── README_立委不分區資料整理與地圖製作.md   ← detailed at-large pipeline guide
├── Empty_Map/                 Blank outline maps (DrawMap.py, Taiwan.png, per-county blanks)
├── Get_data/                  Scrapers (vote.nccu.edu.tw): GetData.py, scrape_*.py, Convert.py
├── KaohsiungMayorlElections/  Kaohsiung mayors 2018/2022 (scripts/, data/, maps/10-20)
├── MayoralElections/          Taipei County / New Taipei City mayors 1993-2022 (scripts/, data/, maps/10-20)
├── Shared/                    Shared utilities
│   ├── scripts/Print_word.py  Chinese text renderer (transparent PNG)
│   └── Color.txt              Shared color-ramp definitions
├── maps/
│   ├── County/                National township vote-rate map PNGs (1994→2024)
│   └── _text_cache/           On-disk cache of rendered text PNGs
└── txt/                       Older / backup drawing scripts (.py files with .txt extension)
```

各选举文件夹内部惯例 / Per-election folder convention:

```text
{Year}{Election}/
├── data/ 或 Data/    raw results / converted {Year}{County}_得票率.xlsx
├── scripts/          converter & drawing scripts (+ 10/, 20/ variants)
└── maps/             output PNGs (root, 10/, 20/)
```

---

## 依赖与安装 / Dependencies & Setup

**中文**：Python ≥ 3.10（已在 CPython 3.14 验证执行）。需要下列套件：
**English**: Requires Python ≥ 3.10 (verified on CPython 3.14) and the following packages:

| 套件 Package | 用途 Purpose |
|---|---|
| pandas, numpy | 数据整理 / data wrangling |
| geopandas, shapely | SHP 读取、几何运算 / SHP I/O & geometry ops |
| matplotlib | 绘图、中文文字渲染 / drawing & CJK text rendering |
| Pillow (PIL) | 影像合成 / image composition |
| opencv-python (cv2) | 影像二值化、色彩量化 / binarization & color quantization |
| openpyxl | 读写 xlsx / xlsx read-write |
| requests, beautifulsoup4 | 爬虫 / scraping |

```bash
pip install pandas numpy geopandas shapely matplotlib pillow opencv-python openpyxl requests beautifulsoup4
```

> **注/Note**：geopandas 在 Windows 上如安装失败，可改用 conda：`conda install geopandas`。

---

## 使用示例 / Usage Examples

### 1. 总统选举（2024）数据转换 / Convert 2024 president data

```powershell
python "2024Precident\scripts\convert_2024_president_percent.py"
```

**中文**：自动扫描 `2024Precident\data\` 中所有「第16任…在{縣市}各村(里)得票數一覽表.xlsx」
并输出 `2024{縣市}_得票率.xlsx`。
**English**: Scans all `第16任…在{縣市}各村(里)得票數一覽表.xlsx` files in `2024Precident\data\`
and outputs `2024{縣市}_得票率.xlsx` for each county.

### 2. 绘制全台 2024 总统村里级地图 / Draw the national 2024 president village-level map

```powershell
python "2024Precident\scripts\Draw_National_President_2024.py"
```

输出 / Output：`2024Precident\maps\全臺灣2024年總統副總統選舉_得票率地圖.png`

### 3. 绘制单一县市（新北市长）地图 / Draw single-city mayor maps (New Taipei)

```powershell
python "MayoralElections\scripts\Converge_to_map.py"
python "MayoralElections\scripts\10\Converge_to_map.py"   # 10% 色阶 / 10% ramp
python "MayoralElections\scripts\20\Converge_to_map.py"   # 35% 起 5% 色阶 / 5% ramp from 35%
```

### 4. 全台乡镇级立委不分区地图（底图法）/ National township-level at-large legislator maps

```powershell
python "County\2016LegislatorParty.py"
python "County\2024LegislatorParty.py"
```

输出 / Output：`maps\County\{年份}年立法委員選舉_得票率地圖.png`

### 5. 爬取中选会／政大开票资料 / Scrape CEC/NCCU result data

```powershell
python "Get_data\GetData.py" <election-results-url> [--region] [-o out.xlsx]
```

### 6. 产出空白轮廓地图 / Generate blank outline maps

```powershell
python "Empty_Map\DrawMap.py"
```

---

## 地图输出 / Map Outputs

**中文**：各类地图产出的位置。**English**: Where generated maps end up.

| 位置 Location | 内容 Contents |
|---|---|
| `maps\County\` | 全台乡镇级：1994 省长、1996/2000 总统、2001/2008/2012/2016/2024 立委 / National township: 1994 governorship, 1996/2000 president, 2001/2008/2012/2016/2024 legislators |
| `MayoralElections\maps\10\`、`maps\20\` | 各年份新北县市长（含 2001 个别候选人：王建煊／苏贞昌）/ New Taipei mayors by year (incl. 2001 per-candidate: Wang Chien-shien / Su Tseng-chang) |
| `KaohsiungMayorlElections\maps\` | 高雄市长 2018、2022 / Kaohsiung mayors 2018, 2022 |
| `2024Precident\maps\` | 全台 2024 总统 + 台北／台中／新竹比较图 / National 2024 president + Taipei/Taichung/Hsinchu comparisons |
| `2024DistrictLegislator\maps\` | 台南区域立委（A/B 版）及多县市 Compare 图 / Tainan regional legislators (A/B) + multi-county Compare maps |
| `2024Legislator-at-Large\maps\` | 新北不分区政党票 / New Taipei at-large party votes |
| `Empty_Map\` | 全台及各县市空白轮廓图 / National & per-county blank outline maps |

---

## 扩展指南 / Extending the Project

**中文**：新增一个选举年份／类别，大致四步（详见 `County\README_立委不分區資料整理與地圖製作.md`）。

**English**: To add a new election year/category, roughly four steps
(see `County\README_立委不分區資料整理與地圖製作.md` for the full guide):

1. **新增转换器 Write a converter**：依原始档格式写 `convert_{year}_to_rates.py`，输出
   `{年份}{縣市}_得票率.xlsx`（3 工作表）/ based on the raw layout, output a `{Year}{County}_得票率.xlsx`
   (3 sheets).
2. **复制制图模板 Copy a drawing template**：
   ```powershell
   Copy-Item County\2016LegislatorParty.py County\{year}LegislatorParty.py
   ```
3. **修改 5 处常量 Edit 5 constants**：
   `DATA_DIR` / `OUT_PNG`、`OLD_COUNTY_MAP`（县市名对应 / county-name mapping）、
   `RATE_COLOR_STOPS`＋`CANDIDATES`、`TITLE_LINES`（届次与日期 / term & date）、
   `VARIANT_CHAR_MAP`（异体字 / variant characters）。
4. **验证 Verify**：脚本自我检查输出应符合「乡镇市区 368、有数据 368、无数据 0」；
   因 AI 无法直接看图，以像素统计（蓝／绿／其他色 pixel 数）验证配色正确
   / the self-check should report 368 townships, 368 with data, 0 without; since AI cannot literally
   view images, verify colors by pixel statistics (blue/green/other pixel counts).

---

## 历史行政区变迁 / Administrative Boundary History

**中文**：影响 `OLD_COUNTY_MAP`／`SPECIAL_TOWN` 的改制。
**English**: Boundary changes affecting `OLD_COUNTY_MAP` / `SPECIAL_TOWN`.

| 日期 Date | 变迁 Change |
|---|---|
| 2008-01-01 | 高雄县三民乡 → 那玛夏乡 / Sanmin → Namasia, Kaohsiung County |
| 2010-12-25 | 五都改制：新北市；台中／台南／高雄县市合并升格 / Five municipalities reform: Taipei County→New Taipei City; Taichung/Tainan/Kaohsiung county-city mergers |
| 2014-12-25 | 桃园县 → 桃园市 / Taoyuan County → Taoyuan City |
| ~2010 | 台南市西区＋中区 → 中西区 / West + Central districts merged into West-Central, Tainan City |

---

## 授权 / License

**中文**：未指定授权。数据来源为政府公开信息（中选会、内政部）与政大选举研究中心，
使用时请注意各自著作权与引用规定。

**English**: No license specified. Data originates from government open information (CEC, Ministry of
Interior) and the NCCU Election Study Center; please respect the respective copyright and citation rules
when reusing it.