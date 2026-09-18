# 台湾历届选举得票率地图绘制 / Taiwan Election Vote-Rate Maps

> **中文**：基于政府公开信息平台提供的 **SHP 村里界图资** 与 **中选会（CEC）／政大选举研究中心** 的选举资料，
> 用 Python 将各级选举在乡镇市区、村里的得票率绘制成地图。
>
> **English**: This project draws vote-percentage (得票率) choropleth maps for Taiwan elections,
> using **Ministry of Interior village-boundary SHP data** together with **CEC / NCCU election data**.
>
> 本项目由 AI 生成。/ _This project was generated entirely by AI._
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
| 立法委员「区域／县市」/ Legislators (regional) | 2024（第 11 届/11th）各县市区域立委图：基隆、新北、台北、桃园、新竹、苗栗、台中、云林、台南、高雄、台东 / per-county district-legislator maps: Keelung, New Taipei, Taipei, Taoyuan, Hsinchu, Miaoli, Taichung, Yunlin, Tainan, Kaohsiung, Taitung |
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

**注意 / Beginner tip**：整个流程其实只有两步——① 把原始开票数字整理成「每个村里的得票率」表格；
② 把表格数值转成颜色、涂到地图的每个村里。下面两种制图方式（Ａ／Ｂ）的差别，只在「怎么取得村里边界」。
_At its core the pipeline has just two steps: (1) turn raw tallies into a per-village vote-rate table, then
(2) map those rates to colors on each village. The two drawing methods (A/B) differ only in how they obtain
village boundaries._

### 制图方式Ａ：SHP 村里级地图 / Method A: SHP village-level maps
### (geopandas + matplotlib + OpenCV + Pillow)

**中文**：用内政部村里界 SHP 直接绘制，一里一色，适用于全台或单县市：

**English**: Draws directly from the village-boundary SHP; one color per village, for the whole island or a
single county/city:

1. **读取与投影**：`geopandas.read_file` 读 `VILLAGE_MOI_1111118.shp`（缺 CRS 视为 `EPSG:4326`），统一
   `to_crs(3826)`（TWD97 / TM2，米制）；单县市图再按 `縣市` 栏裁出目标范围。
   / Read with geopandas (missing CRS treated as `EPSG:4326`), reproject to `EPSG:3826`; clip to the target
   county for single-city maps.
2. **名称配对**：以 `(县市, 乡镇, 村里)` 规范化 key 精确匹配，失败时同乡镇内用 `difflib.SequenceMatcher`
   模糊比对（等长、仅一字之差、且落在异体组如 峯/峰、舘/館），并统计精确／异体／模糊／无资料数量。
   / Match by a normalized `(county, township, village)` key; on failure use `SequenceMatcher` fuzzy matching
   (equal length, one char apart, allowed variant group such as 峯/峰, 舘/館), reporting match-type counts.
3. **填色**：取各村里**领先者**，依其政党／候选人色阶（`10/` 约 10% 起、`20/` 35% 起 5% 距）填色；
   未达色阶起点或无资料则留白／灰。
   / Fill each village by the **winning candidate's** ramp (`10/` from ~10%, `20/` 5% steps from 35%);
   below-start or no-data stays white/gray.
4. **边界与图层**：村里填色关闭抗锯齿防色晕；村界 1px、乡镇界 `dissolve().boundary` 后 `buffer()` 成
   2–4px 黑带、县市界 3–6px 外轮廓；金门／连江／澎湖只画内部乡镇界（`difference(县市界)`）以免糊图。
   / Village fills with AA off; 1px village lines, 2–4px township black bands via dissolve+buffer,
   3–6px county outlines; small counties draw only internal township boundaries.
5. **全台插图与过滤**：金门、马祖以 1:1（`ISLAND_SCALE=1.0`）平移至左上角成插图盒（6px 外框），
   乌坵塞入金门框内空余角落；基隆／宜兰按距离、高雄按 `VILLNAME` 空值过滤离岸岛。
   / Kinmen & Matsu as 1:1 inset boxes top-left (6px frame), Wuqiu tucked into a free corner; offshore
   islands filtered by distance (Keelung/Yilan) or empty `VILLNAME` (Kaohsiung).
6. **量化与合成**：绘图存 PNG 后，用 OpenCV 逐块（每块 50 万像素）把每像素量化到最近调色盘色；
   再用 Pillow 贴入右侧标题＋图例面板（图例起点自动取最低领先率下取整），文字由 `Print_word` 透明图渲染。
   / OpenCV quantizes each pixel to the nearest palette color in 500k-pixel chunks; Pillow composites the
   right-side title + legend panel (auto start tier), text rendered via `Print_word` transparent PNGs.

代表脚本 / Key scripts:
- `MayoralElections/scripts/Converge_to_map.py`
- `KaohsiungMayorlElections/scripts/Converge_to_map_kaohsiung.py`
- `2024Precident/scripts/Draw_National_President_2024.py`（全台 2024 总统 / national 2024 president）
- `2024DistrictLegislator/scripts/Tainan_legislative_map.py`（台南区域立委 A/B 版 / Tainan regional A/B）
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

> 本节按「数据转换 → 名称配对 → 绘图 → 量化 → 文字 → 图例 → 爬虫 → 辅助工具」的顺序，
> 介绍脚本内部的关键实现细节，方便阅读与修改代码。
> _This section walks through the key implementation details inside the scripts._

### 1. 数据转换（得票率计算）/ Data conversion (vote-rate math)

各届原始资料格式不一，转换器（`convert_*.py`）都遵循「读原始开票档 → 以村里为单位汇总 → 输出标准 3 工作表」的流程：

**English**: Raw files differ from year to year, but every converter (`convert_*.py`) follows the same flow:
read the raw polling-station workbook → aggregate to the village level → write the standard 3-sheet output.

- **读取方式**：一律用 `pd.read_excel(header=None)`（无表头）整块读入，不依赖文件名（政府档案常有乱码名），
  县市名改从**档内标题列**以正则提取，如 `選舉(.+?)各政黨`（2008/2012/2016）或
  `選舉各政黨在(.+?)各投開票所`（2024 立委）。
  / Read the whole sheet with `pd.read_excel(header=None)` (no header row) and take the county name from an
  in-file title cell via regex (e.g. `選舉(.+?)各政黨` for 2008/2012/2016), instead of trusting the filename.
- **版面自动检测**：2024 立委混用新旧两种版面，程序以「第 1 列第 0 栏是否等于 `縣市`」判断：
  - 新格式 → 政党自第 4 栏起，乡镇 = 第 1 栏、村里 = 第 2 栏；
  - 旧格式（A05-6，如云林县）→ 政党自第 3 栏起，乡镇 = 第 0 栏、村里 = 第 1 栏。
  / Auto-detect the layout: if row 1 / column 0 equals `縣市`, it is the new format (parties from column 4,
  township = column 1, village = column 2); otherwise the old A05-6 format (parties from column 3,
  township = column 0, village = column 1).
- **政党栏位浮动**：政党数量每届不同（2008 固定 12 党、2016 有 18 党、2024 有 16 党），
  政党名由「政党名行」（第 2 或第 4 列）逐栏读取到空栏为止；有效票数、无效票数、投票数紧接在政党之后，
  故其列号按 `有效票数列 = 政党起始栏 + 政党数` 推算，而非写死。
  / Party columns shift every year (2008: 12 parties, 2016: 18, 2024: 16). Party names are read from the
  party-name row until a blank cell; valid/invalid/turnout columns follow the parties, so their index is
  derived as `valid_col = party_start + party_count` instead of being hard-coded.
- **村里汇总**：2012 起同一「乡镇 × 村里」可能对应多个投开票所，先把**得票数加总**再算
  `得票率(%) = 得票數 ÷ 有效票數 × 100`（避免先算比率再加权的误差）；2008 则多为已汇总的村里列。
  / From 2012 on a single village may map to several polling stations: sum the votes first, then compute
  `rate(%) = votes ÷ valid votes × 100` (avoids the error of averaging ratios); 2008 rows are usually
  already village-level.
- **行结构解析**：乡镇小计列的村里栏为空 → 更新「现行乡镇」；县市总计列含「总」字 → 作为资料起点；
  无村里的列一律跳过。
  / Row parsing: a subtotal row with a blank village cell updates the "current township"; the county total row
  (containing 總) marks the data start; rows without a village are skipped.
- **特殊格式**：
  / Special formats:
  - `convert_1994_to_rates.py`：原始档为「4 位候选人并排、每块 5 栏（地区/姓名/号次/得票数/得票率）」，
    得票率是 0–1 小数需 ×100；并做历史行政区映射（见第 8 节）与同 key 多列取平均。
    / 1994: four candidates sit side by side in 5-column blocks (region/name/number/votes/rate); the rate is a
    0–1 decimal (×100), and the script applies historical district mapping (see §8) and averages duplicate keys.
  - `convert_2024_president_percent.py`：原始档为固定列结构（C=柯文哲、D=赖清德、E=侯友宜、F=有效票数A），
    用 `openpyxl` 逐格读取，村里栏为空时更新现行乡镇，跳过无有效票的区域小计列，只输出 `各里彙總` 单工作表。
    / 2024 president: fixed columns (C=Ko Wen-je, D=Lai Ching-te, E=Hou Yu-ih, F=valid votes A), read cell by
    cell with `openpyxl`; a blank village updates the current township; subtotal rows with no valid votes are
    skipped; only the single `各里彙總` sheet is written.
- **统一输出**：`各里彙總`／`各鄉鎮(市、區)彙總`／`縣市彙總` 3 个工作表，字段与
  `County/README_立委不分區資料整理與地圖製作.md` 一致，供制图脚本直接读取。
  / Standard output: three sheets `各里彙總` / `各鄉鎮(市、區)彙總` / `縣市彙總`, matching the fields documented
  in `County/README_立委不分區資料整理與地圖製作.md`, ready for the drawing scripts.

**注意 / Beginner tip**：这里的「得票率」= 某候选人在该村的得票数 ÷ 该村有效票数 × 100%。
把每个村的领先者涂上颜色，就得到一张「谁在哪里赢、赢多少」的地图。
_A "vote rate" here means a candidate's votes in a village divided by that village's valid votes (as a %)._

### 2. 名称规范化与配对 / Name normalization & matching

选举资料（表格）与内政部图资（SHP）对同一村里的用字常不同，所有制图脚本共用同一套规范化函数：

**English**: Election tables and the Ministry of Interior SHP often spell the same village differently, so all
drawing scripts share one normalization routine (shown below):

```text
normalize_text(s)
  ├─ str.strip()
  ├─ unicodedata.normalize("NFKC")                 # 全角/半角、兼容字形统一
  ├─ 去除组合用记号（unicodedata.category 首字母为 M）
  ├─ 去除变体选择符（\uFE00-\uFE0F、\U000E0100-\U000E01EF）
  ├─ 去除零宽/控制字符（\u200B-\u200F、\u202A-\u202E、\u2060-\u206F、\uFEFF）
  ├─ 去除图资标注疑难字的方括号 [ ]（如 瓦[磘]里 → 瓦磘里）
  └─ VARIANT_CHAR_MAP.translate                    # 异体字对照（峯→峰、舘→館、磘→窯、獇→羌…）
```

- **去后缀**：`strip_town_suffix` 去 `[鄉鎮市區]$`、`strip_village_suffix` 去 `[村里]$`，取「核心名」比对。
  / Drop suffixes: `strip_town_suffix` removes `[鄉鎮市區]$`, `strip_village_suffix` removes `[村里]$`, and the
  "core name" is used for comparison.
- **精确配对**：以 `(县市, 乡镇核心名, 村里核心名)` 为 key 建字典，O(1) 查找。
  / Exact match: build a dict keyed by `(county, township core, village core)` for O(1) lookup.
- **模糊配对**（SHP 有、精确查不到时）：在同一乡镇范围内用 `difflib.SequenceMatcher` 找相似度最高者，
  且必须同时满足：
  / Fuzzy match (when the SHP village has no exact hit): within the same township, use
  `difflib.SequenceMatcher` to find the best candidate, but only if all of these hold:
  - 相似度 ≥ `MIN_SIMILARITY`（0.5）；
    / similarity ≥ `MIN_SIMILARITY` (0.5);
  - 字串**等长**且只有**一个**字符不同；
    / the strings are **equal length** with exactly **one** differing character;
  - 该差异字符对必须落在允许的异体组 `VARIANT_FUZZY_GROUPS` 内（如 `{峯,峰}`、`{磘,窯}`）。
    / that differing pair belongs to an allowed variant group `VARIANT_FUZZY_GROUPS` (e.g. `{峯,峰}`, `{磘,窯}`).
- **合并村里拆分**：总统转换器对「复兴村、福沃村」这类以 `、，,` 合并的村里，拆成多笔共用同一组得票率，
  使连江等多村合并地区也能上色。
  / Split merged villages: for entries like "復興村、福沃村" joined by `、，,`, the president converter splits
  them into several rows sharing one rate, so merged areas such as Lienchiang can still be colored.
- **政党名统一**：2024 立委把「眾 U+773E」一律换成「衆 U+8846」（台湾民衆党），确保与对照表一致。
  / Party-name unification: the 2024 legislator converter rewrites 眾 (U+773E) to 衆 (U+8846) so it matches the
  lookup table.
- **自检统计**：脚本会打印 `精確匹配 / 異體字匹配 / 模糊匹配 / 無資料` 数量，并在孤儿 key（资料有、对照表无）
  非空时中止输出，避免静默漏配。
  / Self-check: the script prints `精確匹配 / 異體字匹配 / 模糊匹配 / 無資料` counts and aborts if any orphan key
  (present in the data but missing from the lookup) remains, so mismatches never pass silently.

**注意 / Beginner tip**：例如同一个里，政府资料写「瓦磘里」，图资可能写成「瓦[磘]里」或「瓦窯里」。
规范化先把两边转成同一写法再比对，才能把正确的颜色涂到正确的村里。
_Example: one village may appear as 瓦磘里, 瓦[磘]里, or 瓦窯里 across sources; normalization maps them to one
form before matching._

### 3. 投影与图层绘制 / Projection & map rendering

**中文**：把 SHP 投影到统一的米制坐标系后，逐层叠上村里填色与各级界线，最后输出图片。

**English**: Reproject the SHP into one metric coordinate system, then stack village fills and boundary lines
layer by layer and export the image.

- **坐标系统一**：SHP 若无 CRS 则视为 `EPSG:4326`，一律重投影到 `EPSG:3826`（TWD97 / TM2，米制）。
  / One coordinate system: if the SHP has no CRS it is treated as `EPSG:4326`, then reprojected to `EPSG:3826`
  (TWD97 / TM2, metric).
- **画布与比例尺**：强制 `Agg` 后端、`DPI=100`；比例尺
  `scale = max(宽/MAX_PX, 高/MAX_PX, METERS_PER_PIXEL) / SCALE_UP`，
  再取 `画布像素 = ceil(地理尺寸 / scale)`（全台约 12m/px，单县市默认 10m/px，长宽上限 11000–32000px）。
  线宽以 `PX2PT = 72 / DPI` 由像素换算为点。
  / Canvas & scale: force the `Agg` backend and `DPI=100`; the scale is
  `scale = max(w/MAX_PX, h/MAX_PX, METERS_PER_PIXEL) / SCALE_UP`, then
  `canvas px = ceil(geo size / scale)` (~12 m/px for the whole island, 10 m/px default per county, max
  11000–32000 px). Line widths are converted from px to points via `PX2PT = 72 / DPI`.
- **图层顺序**（`zorder` 由低到高）：
  / Layer order (`zorder`, low to high):
  1. 村里填色（`edgecolor='none'`、`antialiased=False`，关闭抗锯齿以免色晕）；
     / village fills (`edgecolor='none'`, `antialiased=False` to avoid color fringing);
  2. 村里界线 1px（zorder 5）；
     / 1px village lines (zorder 5);
  3. 乡镇界：`dissolve(by=TOWNNAME).boundary` 后以 `buffer()` 画成**黑带**（zorder 7–9）；
     / township borders: `dissolve(by=TOWNNAME).boundary`, then `buffer()` into **black bands** (zorder 7–9);
  4. 县市界线 3px（zorder 9）；
     / 3px county/city lines (zorder 9);
  5. 外轮廓黑带（zorder 10–11）。
     / outer-boundary black band (zorder 10–11).
- **两种画线法**：
  / Two ways of drawing lines:
  - 全台图（如 `Draw_National_President_2024.py`）直接用 `dissolve().boundary` 画线；
    / national maps (e.g. `Draw_National_President_2024.py`) draw lines directly from `dissolve().boundary`;
  - 单县市图（`Converge_to_map*.py`）用 `buffer(线宽/2)` 生成黑带，并与市界 `intersection` 裁切，
    避免黑带溢出到邻县。
    / single-city maps (`Converge_to_map*.py`) build black bands via `buffer(width/2)` and clip them with the
    city boundary (`intersection`) so bands do not spill into neighbouring counties.
- **小县市特例**：金门、连江、澎湖的海岸线用 1px，且只画「内部乡镇界」——即
  `乡镇界.difference(县市界)`，以免 2–4px 的粗黑带把细碎岛屿糊成一团。
  / Small-county special case: Kinmen, Lienchiang and Penghu use a 1px coastline and draw only internal
  township boundaries (`township.difference(county)`), so thick 2–4px bands do not smudge the small islands.
- **离岸岛屿过滤**：基隆市剔除距形心 > 25km 的彭佳屿等；宜兰县 `drop_offshore_parts` 剔除 > 60km 的钓鱼台列屿；
  高雄市 `VILLNAME` 为空的未编制村里/代管区不绘制；`TOWNNAME` 为空的要素一律跳过。
  / Offshore-island filtering: Keelung drops Pengjia Islet etc. > 25 km from the centroid; Yilan's
  `drop_offshore_parts` drops the Diaoyutai islets > 60 km away; Kaohsiung skips unorganized/trustee areas
  with empty `VILLNAME`; any feature with empty `TOWNNAME` is skipped.
- **金门/马祖插图（inset）**：两县以 1:1（`ISLAND_SCALE=1.0`）平移到主图左上角，外框 6px；
  金门框在上、连江框在下紧贴；乌坵乡再以同比例尺塞进金门框内 4 个候选角落中「不与金门本体重叠」的一个，外框 1px。
  / Kinmen/Matsu insets: both counties are translated to the top-left corner at 1:1 (`ISLAND_SCALE=1.0`) with a
  6px frame; Kinmen sits above Lienchiang; Wuqiu is placed at the same scale into whichever of the four corner
  slots does not overlap the Kinmen mainland, with a 1px frame.
- **Method B（Colorful 底图）**：不读 SHP，直接对预制的「每乡镇一唯一色」底图 `Colorful.png` 做颜色替换
  （详见第 4、8 节）。
  / Method B (Colorful base map): does not read the SHP; instead it recolors the pre-made `Colorful.png` base
  map in which every township has a unique color (see §4 and §8).

**注意 / Beginner tip**：`EPSG:3826` 是台湾常用的 TWD97 投影坐标系（单位：米）；原始 SHP 多为
经纬度（`EPSG:4326`）。两者直接混用会让图形扭曲、比例失真，所以先统一投影再画。
_`EPSG:3826` is Taiwan's TWD97 metric CRS; the raw SHP is usually geographic (`EPSG:4326`). Mixing them
would distort the shapes, so everything is reprojected first._

### 4. 颜色量化 / Color quantization

matplotlib 反锯齿会生成大量中间色，绘图后统一**量化**到允许的调色盘（含白、黑、灰与所有色阶色）：

**English**: matplotlib's antialiasing creates many in-between colors; after drawing, every pixel is
**quantized** to the nearest color in an allowed palette (white, black, gray, and all ramp colors):

```python
pixels = img_rgb.reshape(-1, 3).astype(np.float32)
for start in range(0, n_pixels, CHUNK_SIZE):               # 每块 500_000 像素
    chunk = pixels[start:start + CHUNK_SIZE]
    d = np.sqrt(((chunk - allowed_rgb) ** 2).sum(axis=1))  # 到每个允许色的欧氏距离
    min_idx = np.argmin(d, axis=0)                         # 取最近色
```

- **分块处理**：避免一次性对全图 × 全调色盘做距离运算造成内存峰值。
  / Chunking: avoids a memory spike from computing the whole-image × whole-palette distance in one shot.
- **County 底图法加速**：把 24-bit RGB 打包成 `uint32`，构造 `0x1000000` 长的**全色域 LUT**
  （`lut = np.arange(0x1000000)`，只覆盖「唯一色 → 填色」的槽位），用 `lut[pack]` 一次 fancy-index
  完成约 1900 万像素的整图替换，取代 `np.unique + argsort` 的旧流程。
  / County base-map speedup: pack 24-bit RGB into `uint32`, build a full-domain LUT of length `0x1000000`
  (`lut = np.arange(0x1000000)`, overriding only the "unique color → fill color" slots) and recolor ~19M pixels
  in one `lut[pack]` fancy-index, replacing the old `np.unique + argsort` flow.
- **对照表自我校正**（`color_map_from_rates.derive_base_color`）：`Name_Color_Correspondence.xlsx`
  少数列的色栏/中心坐标可能错误（如台北信义 vs 基隆信义色栏互换、鹿野乡中心坐标落在高雄茄萣）。
  程序以 `Colorful.png` 像素为准逐一验证：形心邻域（半径 20）能找到对照色则采用，否则取邻域内「属于对照色之众数」重绑，
  并对显式 `TOWN_BASE_COLOR_OVERRIDE` 例外处理；最后检查底图色是否**一对一**，冲突则中止。
  / Lookup self-correction (`color_map_from_rates.derive_base_color`): a few rows in
  `Name_Color_Correspondence.xlsx` have wrong color slots / centroids (e.g. Taipei Xinyi vs Keelung Xinyi slots
  swapped, Luye centroid landing on Qieding, Kaohsiung). The script validates each row against `Colorful.png`
  pixels: accept the lookup color if found in a centroid neighbourhood (radius 20), otherwise rebind to the
  dominant color of that neighbourhood; explicit `TOWN_BASE_COLOR_OVERRIDE` entries are honoured; finally it
  checks that base-map colors are **one-to-one** and aborts on conflict.
- **无资料区块**（County）：先填白垫底，再以 `#323232` 覆盖内部，并保留外缘一圈白色（以膨胀/集合运算求得 rim），
  使无资料乡镇仍能看出区界。
  / No-data areas (County): fill white underneath, overlay `#323232` inside, and keep a white rim around the
  edge (via dilation/set operations) so township borders remain visible.
- **白带保护**（台南区域立委）：立委选区白带另渲一张遮罩图 `protect_mask`，量化后调用
  `fill_small_white_blobs`（`connectedComponentsWithStats`）把面积 ≤ 2000px、不在影像边缘、且邻域多数非白的小白点
  填成邻域主色，消除抗锯齿残留的白点，同时不破坏选区白带。
  / White-band protection (Tainan regional legislators): the constituency white bands are rendered into a
  separate `protect_mask`; after quantization, `fill_small_white_blobs` (`connectedComponentsWithStats`) fills
  tiny white specks (area ≤ 2000 px, not on the image edge, surrounded mostly by non-white) with the local
  majority color, removing antialiasing leftovers without harming the bands.

**注意 / Beginner tip**：「抗锯齿」让线条平滑，但会在边缘混出很多过渡色。量化就是把过渡色强制归回
最近的「正统色」，成品更干净、颜色可数，也方便程序自动检查配色是否正确。
_Quantization snaps antialiased edge colors back to the nearest palette color, keeping the output clean and
machine-checkable._

### 5. 地图文字渲染（Print_word 模式）/ Text rendering (Print_word pattern)

所有标题、图例文字都通过「`Shared/scripts/Print_word.py` 方式」生成透明背景图，保证中文与 `≤ ~ ≥` 符号都能正常显示：

**English**: All titles and legend text are rendered as transparent PNGs via the `Shared/scripts/Print_word.py`
approach, so Chinese characters and symbols like `≤ ~ ≥` always display correctly:

```text
matplotlib 在 1×1 画布上写黑字（CJK：PMingLiU/MingLiU/新細明體/Microsoft JhengHei/SimHei/SimSun，
                                        缺字符号 ≤ ≥ 由 DejaVu Sans 回退）
  → 逐行量测 get_window_extent 尺寸，按实测尺寸建立画布并居中绘制
  → plt.savefig 到 BytesIO → cv2.imdecode 灰度 → cv2.threshold(200) 二值化
  → 背景(白) alpha=0、文字 alpha=255（可指定黑字或白字），得到 RGBA 透明文字图
  → base_img.paste(rgba, xy, mask=rgba.getchannel("A")) 贴回地图
```

- **字体链回退**：先找系统可用的 CJK 字体，再串接 `DejaVu Sans` 补 `≤ ~ ≥` 等符号，避免缺字方框。
  / Font fallback chain: pick an available system CJK font, then chain `DejaVu Sans` for symbols like `≤ ~ ≥`,
  avoiding tofu boxes.
- **双层缓存**：进程内 `_TEXT_IMG_CACHE` 以 `(行内容, 字号[, 颜色])` 为 key；County 脚本另写
  `maps/_text_cache/<sha256>.png` 磁盘缓存，跨次运行免重渲染。
  / Two-level cache: an in-process `_TEXT_IMG_CACHE` keyed by `(lines, font_size[, color])`, plus a disk cache
  `maps/_text_cache/<sha256>.png` in the County scripts so repeated runs skip re-rendering.
- **效能优化**（`color_map_from_rates.py`）：量测用的 figure 只建一次（`_MEASURE_FIG` 复用），
  字体清单一并缓存（`_FONT_FAMILY`），避免每次渲染都重建。
  / Performance (`color_map_from_rates.py`): the measuring figure is created once (`_MEASURE_FIG` reused) and
  the font list is cached (`_FONT_FAMILY`) instead of rebuilding on every render.
- **长名换行**：政党名过长（如「無黨團結聯盟」）时缩小字号并折成两行（`render_cand_name_img`）。
  / Long-name wrapping: overly long party names (e.g. 無黨團結聯盟) are shrunk and wrapped onto two lines
  (`render_cand_name_img`).

**注意 / Beginner tip**：直接用绘图库写中文字，常遇到缺字、字体不对或贴图没有透明背景等问题。
这里改成「先用 matplotlib 把字画成一张图片，再把图片贴到地图上」，可避开这些坑。
_Instead of drawing CJK text directly, the text is first rendered to an image, then pasted onto the map._

### 6. 图例与版面 / Legend & layout

**中文**：图例不用手动设定，程序会依实际得票率自动决定起点与分级。

**English**: The legend is computed automatically from the actual vote rates instead of being hard-coded.

- **自动起点**：依「全台/全县市最低领先得票率」动态决定图例起点 `start = int(min_win_rate // 5) * 5`；
  标签格式首档 `≤x%`、中档 `y~z%`、末档 `≥w%`。
  / Auto start: derive the legend start from the lowest leading rate (national or per county) as
  `start = int(min_win_rate // 5) * 5`; labels are `≤x%` for the first tier, `y~z%` in the middle, `≥w%` last.
- **只列领先者**：仅显示至少领先一个乡镇市区的政党/候选人（如 2016 澎湖七美乡的无党团结联盟）。
  / Leaders only: show only parties/candidates that lead in at least one township (e.g. the Non-Partisan
  Solidarity Union in Qimei, Penghu in 2016).
- **布局计算**：图例每栏宽 = 色块宽 + 间距 + 最长标签宽；右侧面板宽高由标题图与图例群组算出，
  地图本体垂直居中贴入，标题对齐图例群组中心。台南区域立委 A/B 两版采用不同的图例起始留白与标签规则。
  / Layout: each legend column width = swatch width + gap + longest label width; the right panel is sized from
  the title image and legend group, the map is pasted vertically centered, and the title is aligned to the
  legend group center. The Tainan regional A/B versions use different legend padding and label rules.

### 7. 爬虫 GetData.py 与专用脚本 / Web scraper

**中文**：`Get_data/` 提供一支通用爬虫与数支针对特定选举的专用脚本，把中选会／政大网页转成 Excel。

**English**: `Get_data/` provides one generic scraper plus several election-specific scripts that turn
CEC/NCCU web pages into Excel files.

- **通用爬虫 `GetData.py`**：三入口自动识别（`vote3.asp` 全国／县市 → `vote31.asp` 乡镇 → `vote32.asp` 村里），
  以 `requests`（带浏览器 UA）+ `big5` 解码 + `BeautifulSoup` 解析 `<table>`；失败时以 `delay × 2` 退避重试。
  / Generic scraper `GetData.py`: recognizes three entry pages (`vote3.asp` national/county → `vote31.asp`
  township → `vote32.asp` village), fetches with `requests` (browser UA), decodes as `big5`, parses `<table>`
  with `BeautifulSoup`, and retries with `delay × 2` backoff on failure.
- **三层下钻**：`vote3` 列出候选人，逐位下钻 `vote31`，有连结者再下钻 `vote32`；`vote31`／`vote32` 也可直接当入口。
  / Three-level drill-down: `vote3` lists candidates, drill into `vote31` per candidate, then into `vote32`
  where a link exists; `vote31`/`vote32` may also be used as the entry directly.
- **村里切分**：`vote32` 的「地区」栏是「县市+乡镇+村里」合并字串，用已知乡镇清单（按长度排序）做前缀匹配切出乡镇／村里。
  / Village splitting: the "area" column of `vote32` is a combined "county+township+village" string; a known
  township list (sorted by length) is used for longest-prefix matching to split township/village.
- **输出**：`鄉鎮市區彙總`（每候选人两栏：得票数／得票率）与 `村里層級明細` 两个工作表，附「总计」列，并冻结首列、套用样式。
  / Output: two sheets `鄉鎮市區彙總` (two columns per candidate: votes / rate) and `村里層級明細`, with a total
  row, frozen first column, and styled headers.
- **CLI**：`--region`（只取某县市，支援 `\u` 转义避免命令列编码问题）、`--delay`、`--retry`、`-o`；
  输出档被占用时自动改存 `*_新.xlsx`。
  / CLI: `--region` (one county only; supports `\u` escapes to avoid console encoding issues), `--delay`,
  `--retry`, `-o`; if the output file is locked it is saved as `*_新.xlsx` instead.
- **专用脚本**（`Get_data/`，固定某场选举、输出单一 xlsx）：
  / Dedicated scripts (`Get_data/`, fixed election, single xlsx output):
  - `scrape_president_1996.py`：1996 总统，把「总统行（10 栏）+ 副总统行（4 栏）」合并成单列扁平表。
    / 1996 president: merges the "president row (10 cells) + vice-president row (4 cells)" into one flat table.
  - `scrape_president_1996_levels.py`：1996 总统，下钻 `vote312`（县市）／`vote313`（乡镇），输出「縣市級別」「鄉鎮市區級別」两表。
    / 1996 president: drills into `vote312` (county) / `vote313` (township), outputting the `縣市級別` and
    `鄉鎮市區級別` sheets.
  - `scrape_legislator_2001_party.py`：2001 立委，将同政党在同乡镇的多位候选人得票**加总**，输出「政党 × 乡镇市区」交叉表。
    / 2001 legislators: **sums** the votes of same-party candidates within a township and outputs a
    "party × township" cross table.

### 8. 辅助脚本与历史行政区 / Helper scripts & boundary history

**中文**：主要制图流程以外的辅助工具与历史行政区对照。

**English**: Helper utilities and historical administrative mappings used alongside the main pipeline.

- **`Empty_Map/DrawMap.py`**：产出全台与各县市**空白轮廓图**；沿用与全台图相同的金马插图布局，
  最后以 `cv2.threshold(40, THRESH_BINARY_INV)` 把绘图结果转成纯黑白轮廓线。
  / Produces **blank outline maps** for the whole island and each county; reuses the same Kinmen/Matsu inset
  layout as the national map, then binarizes the drawing into pure black-and-white outlines with
  `cv2.threshold(40, THRESH_BINARY_INV)`.
- **`Get_data/Convert.py`**：影像清理小工具，把除保留色（`#7F7F7F / #323232 / #0066CC`）外的像素一律涂灰。
  / A small image-cleanup tool that paints every pixel gray except the kept colors
  (`#7F7F7F / #323232 / #0066CC`).
- **历史行政区映射**（`OLD_COUNTY_MAP` / `TOWN_MERGE` / `SPECIAL_TOWN`）：把旧行政区名对到现行对照表，
  例：2008-01-01 高雄县三民乡→那玛夏乡；2010-12-25 五都改制（台北县→新北市，台中/台南/高雄县市合并）；
  2014-12-25 桃园县→桃园市；台南市中区＋西区→中西区（得票取平均）。
  / Historical district mapping (`OLD_COUNTY_MAP` / `TOWN_MERGE` / `SPECIAL_TOWN`) maps old names to the current
  lookup, e.g. Sanmin → Namasia (Kaohsiung County, 2008-01-01); the 2010-12-25 five-municipality reform
  (Taipei County → New Taipei City; Taichung/Tainan/Kaohsiung county-city mergers); Taoyuan County → Taoyuan
  City (2014-12-25); Tainan West + Central districts → West-Central (votes averaged).
- **2016/2024 县市映射**：两届已是现行制，`OLD_COUNTY_MAP` 为恒等映射，仅用于统一走同一套比对逻辑。
  / 2016/2024 mapping: both elections already use the current system, so `OLD_COUNTY_MAP` is the identity map,
  kept only so every election goes through the same matching logic.
- **资料缺口处理**：2024 立委缺云林县原始档，该县 20 个乡镇市区以「无资料」处理（画布底色，不著色）。
  / Data gaps: the 2024 legislator raw file for Yunlin County is missing, so its 20 townships are treated as
  "no data" (canvas background color, uncolored).

---

## 目录结构 / Directory Structure

**中文**：**English**：

```text
TaiwanElection/
├── 2008Legislator-at-Large/   7th-term at-large legislators (Data/ raw xls, scripts/convert_2008_to_rates.py)
├── 2012Legislator-at-Large/   8th-term at-large legislators (scripts/convert_2012_to_rates.py)
├── 2016Legislator-at-Large/   9th-term at-large legislators (scripts/convert_2016_to_rates.py)
├── 2024Legislator-at-Large/   11th-term at-large legislators (data/ rate xlsx, maps/10-20, scripts/convert_2024_to_rates.py)
├── 2024DistrictLegislator/    11th-term regional legislators (Tainan A/B + per-county District2024 maps)
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

通用爬虫（自动下钻到村里层）/ Generic scraper (auto-drills to village level):

```powershell
python "Get_data\GetData.py" <election-results-url> [--region] [--delay] [--retry] [-o out.xlsx]
```

专用脚本（固定某场选举，输出单一 xlsx）/ Dedicated scripts (fixed election, single xlsx):

```powershell
python "Get_data\scrape_president_1996.py"          # 1996 总统扁平表 / flat 1996 president table
python "Get_data\scrape_president_1996_levels.py"   # 1996 总统 县市＋乡镇两层 / county+township levels
python "Get_data\scrape_legislator_2001_party.py"   # 2001 立委 政党×乡镇 / party x township
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
| `2024DistrictLegislator\maps\` | 台南区域立委（A/B 版）+ 各县市区域立委图（`{县市}_District2024*.png`，多版本以 `_1`／`_2`／`_Zone` 等区分）/ Tainan regional legislators (A/B) + per-county district-legislator maps (`{County}_District2024*.png`, variants suffixed `_1`/`_2`/`_Zone` etc.) |
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