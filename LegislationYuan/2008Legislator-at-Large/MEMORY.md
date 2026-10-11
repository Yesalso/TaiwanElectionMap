# 2008 立委地圖項目 —— 長期記憶（繪圖管線與鐵律）

## 專案定位
- 腳本 A `scripts/Draw_Kaohsiung_Legislator_2008.py`：高雄**市**（舊 11 區、5 選區）；輸出 `LegislationYuan/maps/高雄市2008年立法委員選舉_政黨色塊地圖.png`（1588×2945px）。
- 腳本 B `scripts/Draw_KaohsiungCounty_Legislator_2008.py`：高雄**縣**（27 鄉鎮市、4 選區，2026-10-11 新增）；輸出 `LegislationYuan/maps/高雄縣2008年立法委員選舉_得票率地圖.png`（9327×11542px）。
- 腳本 C `scripts/Draw_Taichung_Legislator_2008.py`：臺中**市**（舊 8 區、3 選區，2026-10-11 新增）；輸出 `LegislationYuan/maps/臺中市2008年立法委員選舉_得票率地圖.png`（2414×1321px）。
- 腳本 D `scripts/Draw_TaichungCounty_Legislator_2008.py`：臺中**縣**（21 鄉鎮市、5 選區，2026-10-11 新增）；輸出 `LegislationYuan/maps/臺中縣2008年立法委員選舉_得票率地圖.png`（10511×5104px）。
- 資料：市 `Data/区域/p07_T1_200.xls`（5 sheet）；高縣 `Data/区域/p07_T1_312.xls`（4 sheet）；中市 `Data/区域/p07_T1_319.xls`（3 sheet）；中縣 `Data/区域/p07_T1_306.xls`（5 sheet）。
- **四份 xls 同構**：行0標題、行1欄名（有效票數 A 欄位置隨候選人數變動→以「有效票數」字樣自動定位）、行3候選人、行4政黨、行5總計、行6+ 鄉鎮市(col0有值col1空)/村里(col1有值)。sheet 名尾號＝選區號。
- 執行環境 `C:\Users\Windows\PyCharmMiscProject\.venv`（geopandas/shapely/rasterio/skimage/cv2/xlrd 齊全）。

## 繪圖管線（沿用 Draw_South2_President_2020 風格）
- 共用模組：`Precident/2024Precident/scripts/20/Draw_National_President_2024.py`（flood_fill_layer / check_region_single_color / full_geom_check / strip_town_suffix / strip_village_suffix / normalize_text / hex2rgb / DPI=100）。
- ① 線稿兩層：村里界 1px（PIL Bresenham + skimage.thin 取中心線）；區界 3px、縣市界/海岸線 5px（matplotlib Agg + 閾值二值化）。
- ② 洪水填充：lines_mask 作封閉堤壩，4-連通區域整塊填單色（顏色取區域內像素「幾何所屬村里」的眾數）。
- ③ 立委選區界 5px：與縣市界/海岸線重合的段剔除（幾何法），其餘段成像。**顏色：高雄兩圖＝純白 (255,255,255)；臺中兩圖＝#FCFCFC (252,252,252)**（使用者指定）。
- ④ 先 `arr[lines_mask]=0` 畫黑線，再 `arr[立委線]=線色`。


## 鐵律（踩過坑的經驗，新增圖層/改規則前必讀）
1. **粗白線/擦除帶一律用幾何 difference/intersection**，禁止「兩個獨立渲染的像素遮罩相減」——抗鋸齒實心填充 vs 描邊線的寬度不守恆，必留 ~1px 殘邊（表現為縣市界/海岸線外圈的「白暈圈」）。
2. **`.boundary` 當「外輪廓/海岸線」用之前，必須先剔除退化內環**（`drop_degenerate_holes`）：村里圖資相鄰里的亞像素細縫（<1m）會被 union 成面積≈0 的內環，被當成海岸線 → 憑空多畫粗黑線 ＋ difference 在白線中段打洞（白線冒黑點）。鹽埕區育仁里/前金區博孝里僅差 0.8m，即為此例（全圖 33 個退化內環）。
3. **自檢必須回查最終渲染像素**，不能只查派生遮罩：白線被打洞後，該處像素已不屬 band_layer，查「band_layer 內黑像素」恆為 0（假陰性）。正解＝把剔除碎片光柵化後查最終圖是否變黑。
4. **線寬量測用 skeletonize + distance_transform_edt（骨架處距離×2）**；列掃描連續黑段長度會被斜線投影撐長而失真。
5. **粗白線必須用 buffer 成像，禁用「線稿 extract + 逐段畫線」**（退化迴針會被放大成肉眼可見死線）。
6. 輸出 PNG 可能被預覽器占用 → `OSError [Errno 22]`，需重試兜底。

## 填色方案（2026-10-11 起：按得票率配色）
- 原為「按政黨固定色」（KMT #004E9E / DPP #1B9431 / 其他 #9E9E9E），已改為**按得票率配色**。
- 色階來源外部檔 `D:\Windows\TaiwanElection\LegislationYuan\color.txt` 的 `RATE_COLOR_STOPS`（6 組，順序：0 無黨籍灰 / 1 中國國民黨藍 / 2 民主進步黨綠 / 3 新黨黃 / 4 宋楚瑜橘 / 5 台灣民眾黨青）。腳本以 `exec` 讀入該檔（單一來源，勿在腳本內硬編色表）。
- 每里取「得票最高候選人」→ 以其**政黨**選色階組、以其**得票率**（= 得票數 ÷ 有效票數A × 100）選深淺；`PARTY_STOPS_INDEX` 做政黨→組別映射，未列出政黨 fallback 至 0（灰）。
- **專屬色階 `EXTRA_PARTY_STOPS`（2026-10-11 臺中縣新增）**：政黨→自訂 stops，在 `pick_rate_color` 中**優先於** `RATE_COLOR_STOPS` 檢查。目前僅「**無黨團結聯盟**」（顏清標，臺中縣第2選區）→ 粉色 11 階：(35,#FAC6D8) (40,#F8A8C5) (45,#F68AB2) (50,#F46C9F) (55,#F24E8C) (60,#F03772) (65,#D01058) (70,#B30D4B) (75,#950B3F) (80,#770932) (85,#590726)。
- 允許色驗證統一由 `all_allowed_colors()` 匯集：純白 + 純黑 + 立委線色 + 全部 RATE_COLOR_STOPS 色 + 全部 EXTRA_PARTY_STOPS 色。
- 有效票數欄位置非固定：以表頭含「有效票數」自動定位，找不到則取「候選人欄之後一欄」（= 3+n_cand）。
- 2008 舊高雄市實際只有 KMT/DPP 曾領先任一里（DPP 261、KMT 189），領先得票率 41.03%~98.29%；輸出 20 色，全在允許集內。
- 臺中市：KMT 187 / DPP 27（44.41%~97.37%）。臺中縣：KMT 262 / 無黨團結聯盟 91 / DPP 57 / 台聯 1（43.98%~91.51%）；顏清標 91 里落到粉色 8 階。

## 資料關鍵
- 選區 xls `Data/区域/p07_T1_200.xls`：5 sheet=5 選區；三民區拆第2/3、前鎮區拆第4/5 → 選區邊界須以「里」為單位 dissolve。
- 選區 xls `Data/区域/p07_T1_312.xls`（高雄縣）：4 sheet=4 選區（第1區14鄉鎮、第2區8鄉鎮、第3區4鄉鎮、第4區鳳山市）；各鄉鎮市只屬單一選區，選區界可直接 dissolve。SHP 108 版 COUNTYNAME 一律「高雄市」→ 以 TOWNNAME 篩 27 鄉鎮市區。
- 選區 xls `Data/区域/p07_T1_319.xls`（臺中市）：3 sheet=3 選區；8 區全部只屬單一選區（第1區 西屯+南屯；第2區 北屯+北；第3區 西+中+東+南）。
- 選區 xls `Data/区域/p07_T1_306.xls`（臺中縣）：5 sheet=5 選區；**大里市拆第2/3 選區**（第2區僅東湖、西湖 2 里）→ 以「里」為單位 dissolve；其餘 20 鄉鎮市只屬單一選區。
- 圖資 108 版 `VILLAGE_MOI_1081121.shp`：COUNTYNAME 臺中＝「臺中市」（合併後 29 區），高雄＝「高雄市」（合併後大高雄 38 區），皆須以 COUNTYNAME+TOWNNAME 篩舊範圍。
- **⚠️ 「一列一所」鐵律（四份 xls 皆同，踩過大坑）**：同一村里有多個投開票所就佔**多列**（楠梓清豐里 9 列、仁武八卦村 8 列），故 votes 與 `有效票數A` 必須**逐列累加**；`if key not in vote_by_vill` 只取第一列 → 得票數/得票率嚴重低估、勝者會錯（市：累加前 KMT231/DPP199，累加後 KMT256/DPP173）。有效票數欄以表頭含「有效票數」定位，兜底 3+n_cand。
- **⚠️ 「一列兩里」（臺中市首次遇到）**：同一投開票所跨兩里時，村里別欄寫成「甲里、乙里」→ `v1.split("、")`，把該列 votes 與 valid **平均分配**給兩里。臺中市共 2 例（北區「樂英里、金華里」、西屯區「福恩里、協和里」）。兩里同屬一選區故勝者不受影響。
- **名稱對照**：鄉/鎮/市→區同名（`strip_town_suffix`）可直接匹配；**三民鄉 → 那瑪夏區**（`TOWN_ALIAS`，僅高雄縣）。村里級：異體字統一 `臺/台、峯/峰、舘/館、脚/腳`（`VILL_VARIANT_MAP`；臺中縣另有 霧峰 丁臺→丁台）；舊村名 `VILLAGE_ALIAS`＝桃源 梅蘭→拉芙蘭、那瑪夏 民族→南沙魯/民權→瑪雅/民生→達卡努瓦。來源 xls 有少數字元解不開（存成 U+FFFD）→ 用「同鄉鎮、同長度、非 U+FFFD 字元全等」的萬用字元比對（`_fffd_match`，注意 U+FFFD 在**資料側**）。已知案例：高縣 坔埔→「�埔」、公館→「公�」、峰山→「�山」；中市 部子→「�子」(北屯)、双龍→「�龍」(西區)；中縣 龜壳→「龜�」(大安)、部子→「�子」(外埔)、槺榔→「�榔」(清水)、蔗部→「蔗�」(大肚)。**驗證法**＝「該鄉鎮資料側集合去 FFFD 項」與「圖資側集合去對應名」必須完全相等。杉林 大愛里為 2009 八八風災後新設，2008 無資料屬正常。
- 圖資碎塊：高雄市圖旗津區夾帶東沙/南沙碎塊需 DROP_NAN_COUNTIES 剔除；高雄縣圖僅岡山區 1 筆無名碎塊；臺中市無；臺中縣 5 筆 VILLNAME=NaN 亞微碎塊（清水×3/梧棲/龍井，面積 ~1e-8 ha，無害，不需剔除）。
- 非退化內環（真實水域鏤空，保留、黑線描邊、內部填白）：高雄縣 阿公店水庫 3.13 km²（岡山區）；臺中縣 161.48 km²（1 個）。`drop_degenerate_holes` 的「剩餘應為 0」只針對 <1ha 亞像素細縫。

