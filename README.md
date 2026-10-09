# 台灣選舉得票率地圖

用 Python 將中選會與政大選舉研究中心的歷屆選舉開票資料，整理為「得票率」資料表，再依得票率高低為各鄉鎮市區或村里填色，製作得票率地圖，並將開票結果製作成看板與影片。

產出多為維基百科未收錄之原創內容，包含村里／鄉鎮市區層級的得票率地圖與統計圖表。

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

- `Precident/`：歷屆總統圖。`1996Precident/` 至 `2024Precident/` 各含 `data/`（得票率資料表）、`scripts/`（資料轉換與繪圖程式）、`maps/`（成品地圖）。近年屆次另含全台村里圖與跨屆比較圖。
- `Mayors/`：縣市長圖。`MayoralElections/`（臺北縣／新北市長，1989–2022）、`KaohsiungMayorlElections/`（高雄市長，2018/2022）。
- `LegislationYuan/`：立委。`2008/2012/2016Legislator-at-Large`（不分區資料與轉換程式）、`2024Legislator-at-Large`（全台不分區政黨票圖）、`2024DistrictLegislator`（區域立委圖，含臺南市）。
- `maps/County/`：全台鄉鎮市區層級之成品圖，含跨屆比較圖（1994vs2000、2000vs2024、2008vs2020、2012vs2016、2020vs2024）。
- `County/`：全台鄉鎮底圖換色之繪圖程式，附 `Colorful.png` 底圖與 `Name_Color_Correspondence.xlsx` 政黨—顏色對照表。
- `Empty_Map/`：縣市輪廓空圖之繪製程式與產物。
- `Base_JSON/`：底圖 JSON 圖資（外部資料，排除於版控之外）。
- `Get_data/`：逐屆總統資料蒐集程式（1996–2020）。
- `Shared/`：共用模組，含 `Color.txt` 政黨色票與 `Print_word.py` 文字渲染。
- `Video/`：開票看板與合成影片。`boards/` 為各版面、`final/` 為看板 PNG 與配樂 MP3、`out_video/` 為完成之影片。

## 資料蒐集：開票資料之取得

開票資料取自中選會公開之選舉結果頁面，並以政大選舉研究中心之存檔網頁為輔助來源。選舉結果以「全國 → 縣市 → 鄉鎮市區 → 村里」四個層級逐級列示，各層級頁面記載選舉區別、投開票所或村里名稱，及每一位候選人（或政黨）之得票數。

蒐集程式依上述層級順序逐頁下載資料，並將得票數換算為得票率，即「候選人得票數 ÷ 有效票數」。整理完成之結果寫入一本 Excel 工作簿，內含三張工作表，分別對應縣市、鄉鎮市區、村里三個層級；每個候選人或政黨佔一欄，儲存其得票率（單位為百分比）。

部分年度（例如 2008、2012、2016 年之不分區立委）中選會已提供完整之原始檔案，此類資料毋須上網抓取，僅需將其格式轉換為統一的「得票率」表，供後續繪圖程式讀取。各屆資料統一存放於所屬年度之 `data` 目錄。

以 2016 年總統選舉為例，產生「縣市／鄉鎮／村里」三層級得票率表之指令：

    python Get_data\scrape_president_2016_rates.py

## 地圖繪製：得票率地圖之製作

地圖製作之核心工作，在於將得票率資料與地理圖資進行對應，再依得票率高低填色。製作流程分述如下：

（一）地理圖資：依目標解析度選用兩種底圖。鄉鎮市區層級使用全台鄉鎮輪廓圖（存放於 `Base_JSON`）；村里層級使用內政部提供之村里界圖檔。區域型地圖另依行政區選取特定範圍之多邊形繪製。

（二）地名對應：資料表中記載之行政區名稱，須與底圖上之多邊形逐一比對。比對過程涉及名稱正規化與異體字校正（例如「濓／濂」等寫法差異）；經校正仍無法對應之行政區，另產出檢核清單（如「無資料與未匹配村里」檔案）標記，以供確認。

（三）色彩編碼：政黨採用固定之代表色，色票整理於 `Shared\Color.txt`；無黨籍候選人另行配色。每個行政區塗以「最高票候選人／最高票政黨」之代表色，並以顏色深淺表示得票率高低，形成連續色階。

（四）版面構成：填色完成後，再補上標題、圖例、縣市界線與地名標註，輸出為 PNG 圖片。區域及單一縣市之地圖存放於各屆 `maps` 目錄；全台範圍之地圖集中存放於 `maps\County`，跨屆比較圖亦置於該目錄。

以 2024 年為例，繪製全台總統得票率圖之指令：

    python Precident\2024Precident\scripts\Draw_National_President_2024.py

繪製全台不分區立委政黨票圖之指令：

    python County\2024LegislatorParty.py

各屆縣市長與區域立委之繪圖程式，位於該屆之 `scripts` 目錄。

## 看板與影片產出

開票看板將單一選舉之開票結果套入設計版面，逐屆輸出為看板圖片；再依配樂節拍將各看板依序組成影片。版面設計、素材需求與執行步驟，參見 `Video\README_批量做看板.md` 及 `Video\README_合成视频.md`。

## 需要的外部檔案

- 村里層級地圖需要內政部村里界圖檔：
  `D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp`
- 鄉鎮層級繪圖需要 `Base_JSON\` 內之底圖 JSON。

## 依賴

Python 3 與下列套件：pandas、geopandas、matplotlib、openpyxl、Pillow、requests、beautifulsoup4。