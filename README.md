# 台灣選舉得票率地圖

用 Python 把中選會與政大選舉研究中心的歷屆選舉開票資料，整理成「得票率」資料表，再套上內政部的村里界地理圖資，畫成村里與鄉鎮市區兩種解析度的披彩地圖（choropleth），並把開票結果做成看板、合成影片。

產出大多是維基百科上沒有的原創內容：村里／鄉鎮市區級的得票率地圖與統計圖表。

## English Summary

This project turns official Taiwan election results (Central Election Commission / NCCU Election Study Center) into vote-rate tables, then renders them as choropleth maps at township and village resolution using Ministry of the Interior boundary data. It also produces election-result boards and videos. Most map outputs are original content not found on Wikipedia.

Elections covered: presidential elections 1996–2024; Taipei County / New Taipei City mayors 1989–2022; Kaohsiung City mayors 2018/2022; legislators (at-large party-list 2008/2012/2016/2024 and 2024 regional districts, including Tainan villages); the 1994 Taiwan provincial governor election; and Taipei City mayor result boards for 1994–2022.

## 涵蓋的選舉

| 類別 | 年份 |
|---|---|
| 總統副總統 | 1996、2000、2004、2008、2012、2016、2020、2024 |
| 台北縣／新北市長 | 1989、1993、1997、2001、2005、2010、2014、2018、2022 |
| 高雄市長 | 2018、2022 |
| 立法委員（全國不分區政黨票） | 2008、2012、2016、2024 |
| 立法委員（區域立委） | 2024 各縣市（含臺南市村里圖） |
| 臺灣省省長 | 1994 |
| 臺北市長 | 1994–2022 開票看板（見 `Video/`） |

## 目錄結構

- `Precident/`：歷屆總統圖。`1996Precident/` 到 `2024Precident/` 各有 `data/`（得票率資料表）、`scripts/`（資料轉換與繪圖）、`maps/`（成品）。每一屆都附資料、腳本與成品；近年屆次另含全台村裡圖與跨屆比較圖。
- `Mayors/`：縣市長圖。`MayoralElections/`（臺北縣／新北 1989–2022）、`KaohsiungMayorlElections/`（高雄 2018/2022）。
- `LegislationYuan/`：立委。`2008/2012/2016Legislator-at-Large`（資料與轉換腳本）、`2024Legislator-at-Large`（全台不分區政黨票圖）、`2024DistrictLegislator`（區域立委圖，含臺南市）。
- `maps/County/`：全台鄉鎮市區層級的成品圖，含跨屆比較圖（1994vs2000、2000vs2024、2008vs2020、2012vs2016、2020vs2024）。
- `County/`：全台鄉鎮底圖換色的繪圖腳本，附 `Colorful.png` 底圖與 `Name_Color_Correspondence.xlsx` 政黨－顏色對照表。
- `Empty_Map/`：縣市輪廓空圖的繪製腳本與產物。
- `Base_JSON/`：底圖 JSON 圖資（外部資料，已排除於版控外）。
- `Get_data/`：逐屆總統資料爬蟲（1996–2020）。
- `Shared/`：共用模組。`Color.txt` 政黨色票、`Print_word.py` 文字渲染。
- `Video/`：開票看板與合成影片。`boards/` 各版面、`final/` 看板 PNG 與配樂 MP3、`out_video/` 完成的影片。

## 需要的外部檔案

- 村里級地圖需要內政部村里界 SHP 圖資：
  `D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp`
- 鄉鎮級繪圖需要 `Base_JSON\` 內的底圖 JSON。

## 依賴

Python 3 與下列套件：pandas、geopandas、matplotlib、openpyxl、Pillow、requests、beautifulsoup4。

## 常用指令

爬 2016 總統得票率（縣市／鄉鎮／村里三層級），輸出至 `Precident\2016Precident\data\`：

    python Get_data\scrape_president_2016_rates.py

畫 2024 全台總統得票率圖，輸出至 `Precident\2024Precident\maps\`：

    python Precident\2024Precident\scripts\Draw_National_President_2024.py

畫 2024 不分區立委政黨票全台鄉鎮圖，輸出至 `maps\County\`：

    python County\2024LegislatorParty.py

各屆縣市長與區域立委的繪圖腳本，都放在該屆的 `scripts\` 目錄裡；看板與影片的製作流程見 `Video\README_批量做看板.md` 與 `Video\README_合成视频.md`。