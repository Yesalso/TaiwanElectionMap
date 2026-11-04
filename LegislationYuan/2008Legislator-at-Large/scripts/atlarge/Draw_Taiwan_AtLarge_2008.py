# -*- coding: utf-8 -*-
"""
全臺灣（本島＋澎湖＋金門＋馬祖）
2008 第七屆立法委員全國不分區及僑居國外國民選舉
各村（里）得票領先政黨得票比例圖 —— **單張全島圖**

資料來源：Data/2008不分区/2008不分区/{縣市}.xls（中選會原始「各政黨得票情形」表）
    欄位：鄉(鎮、市、區)別 | 村里別 | 投票所別 | 12 個政黨得票數 | 有效票數A | …
    ⚠️ 同一村里有多個投開票所 → 佔多列：得票數與有效票數必須「逐列累加」。
    ⚠️ 離島（如連江縣「復興村、福沃村」）把多村里併為一列 → 拆成各村，共用同一組
       得票數（各村得票率相同；僅影響全國總計，不影響配色）。
    得票率 = 該政黨得票數 ÷ 有效票數A × 100。

底圖（沿用本目錄五支分區腳本的底圖規則，金馬另行拼接）：
    臺北市…高雄市等 **20 個縣市** → Base_JSON/twvillage2012.json
        （民國101年村里界；欄位 county/town/village 小寫 → 正規化為
          COUNTYNAME/TOWNNAME/VILLNAME；無內建 CRS → 視為 EPSG:4326 再投影 3826）
    **金門縣／連江縣** → `VILLAGE_MOI_1070205.shp`（民國106年村里界，全臺同一套圖資）
        （2012 json 的金馬村里層偏粗：連江僅 21 個有名村里、其餘無名圖斑剔除後
          島形殘缺，且整份缺烏坵鄉；106 年版村里完整並含烏坵鄉，故金馬改用它拼接）
    **嘉義市** → Base_JSON/twVillage_pre2010.geo.json（民國99年前村里界，108 里）
        （與 Draw_YCT4 相同做法：外緣與東/西區區界仍用 2012，只有村里細分線換 pre2010；
          逐里裁剪到 2012 市界內 → 市界補塊 → 按 2012 區界硬切 → 區內貼合，
          使市側聯集恰等於 2012 市界；村名以 CITY_VILL_REPAIR 對齊 2008 用字）
    **宜蘭縣頭城鎮龜山里之龜山島**（2026-11-03 補漏）→ 106 年村里界 SHP（SHP_106）：
        2012 json 的龜山里只有本島沿岸部分，缺外海約 11 km 的龜山島
        （有村里編制、2008 有投票資料；106 年版龜山里為 本島沿岸＋龜山島 MultiPolygon，
          只取距宜蘭本體 >2 km 的部件補入，見 add_gueishan_island）。
        加 `--gueishan` 可先輸出「龜山島補漏測試圖」（宜蘭一帶＋龜山島高亮）供核對。
    縣市界依 **2008 年行政區**還原（2010 五都升格前的 25 個縣市）：
        臺中市／臺中縣、臺南市／臺南縣、高雄市／高雄縣 以鄉鎮市區切分，
        新北市（2010 前為臺北縣）以 2008 名繪製。

版面（2026-11-03 使用者指定：改為版面測試圖同款嵌合佈局）：
    臺灣本島＋澎湖依真實位置為主圖；**連江框在主圖左上角，金門框嵌在連江框
    右下角（金門框右緣、底緣與連江框共邊，L 形嵌合）**，取代原本
    「連江框在上、金門框在下、右緣對齊」的堆疊式。
    放大倍率以 `ISLAND_SCALE`（1.6×）為上限，**並自動往下降**直到兩個框都不壓到
    其他縣市（本島／澎湖，淨空 250m）——連江含東引與 134 塊無名礁石，實際範圍達
    60.4×49.1 km，1.6 倍時寬 96.6 km 會蓋到臺灣西北海岸，故實際輸出為 **1.50×**
    （連江 90.6×73.7 km、金門框 68.0×28.4 km）。
    1:1 時離島在全島圖上只有幾十像素、框內大片留白看不清；附圖比例尺與主圖不同屬
    正常製圖慣例（附圖＝局部放大），**主圖比例尺不變、圖不會變小**。
    金門附圖剔除距主島群過遠的島嶼部件（東碇島等，`KM_ISLET_FAR_KM`＝26 km，
    與版面測試圖同規則）：東碇會把金門附圖外接矩形撐高，嵌入連江框右下角時壓到
    南北竿；剔除後金門框僅佔連江框右側約 72%、底部約 37%，自檢壓到連江圖斑 0 塊。
    金門框內：金門內容貼**左下**、**烏坵鄉**（距金門本島約 120 km）以 2px 虛線
    小方框嵌在**右下角**（框寬＝金門內容＋烏坵框＋留白，兩者幾何分離），
    均不依實際距離擺放。
    命令列加 `--test` 可只畫澎湖／金門／連江（三框由上而下堆疊）供快速核對線寬；
    加 `--boundaries` 可只輸出「縣市界 6px ＋ 海岸線 1px」單獨測試圖（無村里、無填色），
    並列印每段縣市界的兩側縣市稽核表，核對縣市界段「不多選、不少選」。

線色（使用者指定，2026-11-03）：
    所有界線（村里界／鄉鎮市區界／縣市界／海岸線）一律 **#FCFCFC**（近白）；
    **金門／連江／烏坵的附圖外框一律黑線**（2026-11-03 使用者指定，與其他界線區隔）。
    作法：線稿仍以純黑產生遮罩（二值化可靠），最後才 `arr[lines_mask] = LINE_RGB` 上色，
    再把「附圖外框專用遮罩」的像素改回純黑（`render_inset_box_mask` 與 ② 層同一
    matplotlib 畫法，保證像素對齊），故線寬、連通性、油漆桶堤壩都不受顏色影響；
    自檢改以 `ignore_mask=lines_mask` 排除線像素（近白線既非填色、也不算「村外非白」）。

繪圖管線（沿用 Draw_North4／South2／TCN3／TCM4／YCT4 的「線稿兩層 + 油漆桶填色」）：
    ① 線稿（兩層畫法）
       - 村里界 1px：PIL Bresenham 逐段 1px 直繪 → skimage.morphology.thin 取中心線
       - 區界 2px + **縣市界 6px**（只取兩縣市共有段；**加嚴：不丟任何小段、
         linemerge 接合成最長線 → 6px 均勻連續無碎段**）：
         matplotlib(Agg, DPI=100) 繪線，以 THRESHOLD_VAL 二值化切掉抗鋸齒灰邊 →
         黑線遮罩（最後統一上色為 #FCFCFC）
       - **海岸線 1px（2026-11-03 使用者指定：參考金馬的 1px 設計）**：
         本島縣市聯集的外輪廓改用與金馬完全同一畫法 —— 1px 直繪 → thin 取中心線，
         不再以 matplotlib 粗線描邊（全圖所有海岸線統一 1px）
       - 小面積離島縣市（澎湖、金門、連江）：**海岸線與無名礁石一律 1px**，
         且畫法與村里界完全相同（1px 直繪 → thin 取中心線）；② 層只畫「內部鄉鎮界」，
         **不對外緣描邊**（若描邊會以 2px 覆蓋掉 1px，海岸線就變粗）
       - 無名礁石（金門 11 塊、連江 134 塊）與偏遠島礁（東碇島等）**全數保留**：
         不做任何「距主島距離」剔除，島礁圖斑有幾塊就畫幾塊（各自 1px 描邊）。
         舊版整組剔除 → 連江少畫 73 塊無名礁石、金門少 7 塊
       - 附圖外框 6px（金門／連江）
       - 迴針清理（remove_ring_slits）折疊 dissolve「去而復返」的退化迴針，
         微孔洞清理（clean_tiny_holes）避免浮點誤差造成的散點
       - 兩層同一像素網格約定（像素 i 中心 = minx+(i+0.5)/sx），疊加不錯開 1px
    ② 填色：線稿為封閉堤壩，堤壩以外每一塊 4-連通區域整塊填單色，
       顏色取「區域內像素幾何所屬村里」的眾數 → 顏色永不跨越任何一條線
       （線稿最後一步才上色成 #FCFCFC：堤壩是布林遮罩，與線的顏色無關）
    ③ 自檢：油漆桶不變式、逐像素幾何參考（GDAL/rasterio 獨立方法）、允許色、
       ② 層覆蓋、② 層連通分量、村里層 2x2 粗塊
    版面：不畫標題、不畫圖例，只輸出純地圖。
    畫布：長寬上限 **10000 × 12500 px**（超出則自動放大比例尺）。

填色補充（2026-11-03 使用者指定）：
    **金門／連江／澎湖的空白島嶼**（無村里名礁石、或劃入某村但 2008 無投票資料
    的無人島，共 156 塊）**填入所屬鄉鎮市區的得票率顏色** —— 鄉鎮得票率＝
    轄內各村得票數合計後重算，取領先政黨依得票率選色階深淺（見
    `fill_blank_islets_town_colors`）；其餘 19 縣市無資料仍留白。

平票（2026-11-04 使用者指定，規格見 Precident/平票斜線紋_通用程式碼片段.txt）：
    村里（或金馬澎島嶼所屬鄉鎮）第 1、2 名得票率同至小數 3 位、或得票數相同
    → 底色仍填第 1 名（`np.argmax`；同票時取 PARTIES 表頭順序在前者），另存
    `tie_hex`＝第 2 名顏色，由 `nat.apply_tie_stripes(..., lines_mask=lines_mask)`
    在「油漆桶單色不變式」自檢之後疊 45° 斜線紋（寬 8px）。界線像素一律不畫
    斜線（用權威 lines_mask 排除，不靠 arr.any(axis=2) 顏色反推），並印出
    「平票後線稿：X/Y 線像素仍為原線色」核對界線完整性。
    2008 政黨票實測有 15 個村里第 1、2 名同票（皆為 中國國民黨＝民主進步黨）。

村里名比對（沿革 → 合併 → 字元 → 模糊）：
    ⓪ 村里沿革合併（village_lineage_north4 北北基宜、village_lineage_tcm4 桃竹苗）：
       2012 圖資有、2008 尚未設立的里
       → 併入 2008 年母里（同底色、其間不畫村界線）。＝分區腳本「沿革合併」的作法
    ① 精確（臺/台、峯/峰、嗂/窯、部/廍、褔/福、穀/谷 … 先經異體字收斂）
    ② 跨里合併（village_lineage_north4.VILLAGE_VOTE_MERGES）：多個 2008 里 → 一 2012 里，
       以「得票數加總後重算得票率」（故另存各里得票數）
    ③ 萬用字元：來源 xls 少數字元存成 U+FFFD（�）、底圖少數存成「■」/PUA 碼位
       → 同鄉鎮、同長度、非萬用字元全等即視為同一村里；整串都是 � 時採「消去法」
       （同鄉鎮同長度僅唯一候選才接受）
    ④ nat.fuzzy_lookup 的單字異體模糊（峯/峰、舘/館、磘/窯、獇/羌、曹/槽、脚/腳）
    另修掉來源表殘留的編號前綴（中壢「2龍德里」→ 龍德里、大林「0內林里」→ 內林里）。
    仍對不上者留白，並逐筆寫入 Markdown 稽核報告。

輸出：LegislationYuan/maps/全臺灣2008年立法委員不分區選舉_政黨票得票率地圖.png
      LegislationYuan/maps/全臺灣2008_無資料與未匹配村里.md
執行：py scripts/atlarge/Draw_Taiwan_AtLarge_2008.py            # 全臺正式圖
      py scripts/atlarge/Draw_Taiwan_AtLarge_2008.py --test     # 只畫澎湖／金門／連江
      py scripts/atlarge/Draw_Taiwan_AtLarge_2008.py --stats    # 純統計，不出圖（→ STATS_MD）
"""
import os
import re
import sys
import math
import time
import glob
import itertools
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import xlrd
from shapely.ops import unary_union, linemerge
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, MultiLineString
from PIL import Image, ImageDraw
from skimage.morphology import thin
from scipy import ndimage

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import cv2
from io import BytesIO

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))   # …\2008Legislator-at-Large
ROOT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))     # …\TaiwanElection
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
# 共用模組（文字正規化 / 模糊匹配 / 洪水填充 / 幾何自檢）位於 2020Precident/scripts
SHARED_SCRIPTS = os.path.join(ROOT_DIR, "Precident", "2020Precident", "scripts")
if SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, SHARED_SCRIPTS)
import Draw_National_President_2020 as nat
# twvillage2012.json 村里名修補（PUA 碼位／■ 佔位符還原）＋ 2008→2012 村里更名表
REPAIR_SCRIPTS = os.path.join(ROOT_DIR, "Precident", "2008Precident", "scripts")
if REPAIR_SCRIPTS not in sys.path:
    sys.path.insert(0, REPAIR_SCRIPTS)
import village_name_repair as nr
import village_lineage_north4 as lin
# 桃竹苗四縣市村里沿革（母里對照）：同 Draw_TCM4 的做法，以 importlib 指定路徑載入，
# 該模組於 import 時自行解析 `Precident/1996Precident/maps/村里对应关系.md`。
import importlib.util as _ilu
_LIN_TCM_SRC = os.path.join(ROOT_DIR, "Precident", "2000Precident", "scripts",
                            "village_lineage_tcm4.py")
_spec = _ilu.spec_from_file_location("village_lineage_tcm4", _LIN_TCM_SRC)
lin4 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(lin4)

# ===================== 配置 =====================
# 2008 第七屆不分區政黨票的 12 個政黨（欄位順序沿用中選會表頭）
PARTIES = ["公民黨", "制憲聯盟", "台灣團結聯盟", "第三社會黨", "民主進步黨", "新黨",
           "綠黨", "台灣農民黨", "無黨團結聯盟", "中國國民黨", "紅黨", "客家黨"]

# 政黨 → color.txt 色階組別（0 無黨籍灰 / 1 國民黨藍 / 2 民進黨綠 / 3 新黨黃 /
#                        4 橘 / 5 民眾黨青綠）；未列者一律用第 0 組（灰）
PARTY_COLOR_GROUP = {
    "中國國民黨": 1, "民主進步黨": 2, "新黨": 3,
    "無黨團結聯盟": 0, "台灣團結聯盟": 0, "綠黨": 0, "紅黨": 0,
    "客家黨": 0, "台灣農民黨": 0, "公民黨": 0, "制憲聯盟": 0, "第三社會黨": 0,
}

COLOR_TXT = os.path.join(ROOT_DIR, "LegislationYuan", "color.txt")
_ALL_STOPS = nat.load_color_stops(COLOR_TXT)
PARTY_STOPS = {p: _ALL_STOPS[g] for p, g in PARTY_COLOR_GROUP.items()}

# 中選會原始 xls（每個縣市一檔）——支援 Data/2008不分区 下的多層目錄
XLS_DIR = os.path.join(PROJECT_DIR, "Data", "2008不分区")
XLS_GLOB = os.path.join(XLS_DIR, "**", "*.xls")

# 檔名（簡體）→ 底圖縣市名
FILENAME_COUNTY = {
    "台北市": "臺北市", "台北县": "新北市", "桃园县": "桃園縣",
    "台中市": "臺中市", "台中县": "臺中市",
    "台南市": "臺南市", "台南县": "臺南市",
    "高雄市": "高雄市", "高雄县": "高雄市",
    "基隆市": "基隆市", "新竹市": "新竹市", "新竹县": "新竹縣", "苗栗县": "苗栗縣",
    "彰化县": "彰化縣", "南投县": "南投縣", "云林县": "雲林縣",
    "嘉义市": "嘉義市", "嘉义县": "嘉義縣", "屏东县": "屏東縣", "宜兰县": "宜蘭縣",
    "花莲县": "花蓮縣", "台东县": "臺東縣", "澎湖县": "澎湖縣",
    "金门县": "金門縣", "连江县": "連江縣",
}
# 舊鄉鎮市名 → 現地名（資料側更名一律走 village_name_repair.TOWN_VILL_RENAME_2008；
# 這裡只留「整個鄉鎮改名、村里名不變」的特例）
TOWN_ALIAS_BY_SRC = {}

# 底圖：全臺 2012 村里界 + 嘉義市改用 pre2010 村里層（同 Draw_YCT4）
MAP_JSON = os.path.join(ROOT_DIR, "Base_JSON", "twvillage2012.json")
# 跨縣市重疊仲裁用的權威縣市範圍（民國111年村里界，拓撲無重疊）
SHP_COUNTY = os.path.join(r"D:\Windows\Documents\村里界歷史圖資_111",
                          "村里界歷史圖資_111", "VILLAGE_MOI_1111118.shp")
# 民國106年村里界（檔名 1070205）：金門／連江 的拼接來源，也是鄉鎮市區版的底圖
SHP_106 = os.path.join(r"D:\Windows\Documents\村里界歷史圖資_111",
                       "村里界歷史圖資_106", "村里界歷史圖資_106",
                       "VILLAGE_MOI_1070205.shp")
KINMEN_MATSU = ("金門縣", "連江縣")
# 「村里名為 NaN」的圖斑：這些縣市保留（多為離島礁石或跨島里的多邊形部件），
# 其餘縣市一律剔除（多為港區/水域等無意義碎塊）
NAN_KEEP_COUNTIES = {"新北市", "金門縣", "連江縣", "澎湖縣", "新竹市"}
CITY_GEOJSON = os.path.join(ROOT_DIR, "Base_JSON", "twVillage_pre2010.geo.json")
CITY_GEOJSON_COUNTY = "嘉義市"
CITY_VILL_REPAIR = {("西區", "磚嗂里"): "磚窯里"}   # pre2010 用字 → 2008 得票資料用字

OUT_DIR = os.path.join(ROOT_DIR, "LegislationYuan", "maps")
OUT_PNG = os.path.join(OUT_DIR, "全臺灣2008年立法委員不分區選舉_政黨票得票率地圖.png")
MISSING_MD = os.path.join(OUT_DIR, "全臺灣2008_無資料與未匹配村里.md")
STATS_MD = os.path.join(OUT_DIR, "全臺灣2008_村里比對統計_測試.md")   # --stats 純統計報告
layer_name = "layer_taiwan_atlarge_2008_county_6px_coast_1px.png"   # 線稿層單獨輸出（核對用）
# 測試模式（命令列加 --test）：只畫 澎湖／金門／連江，快速核對「海岸線 1px」與礁石，
# 其餘流程（底圖、比對、填色、自檢）完全照正式模式跑，輸出另存以免蓋掉全臺大圖。
TEST_COUNTIES = ("澎湖縣", "金門縣", "連江縣")
TEST_OUT_PNG = os.path.join(OUT_DIR, "全臺灣2008_離島測試_澎湖金門馬祖.png")
TEST_MISS_MD = os.path.join(OUT_DIR, "全臺灣2008_離島測試_無資料與未匹配村里.md")
# 邊界測試模式（命令列加 --boundaries）：只輸出「縣市界 6px＋海岸線 1px」測試圖，
# 不畫村里、不填色，並列印縣市界段稽核表（每段兩側縣市），核對「不多選不少選」。
BOUNDARY_TEST_OUT = os.path.join(OUT_DIR, "全臺灣2008_縣市界海岸線測試圖.png")

TARGET_CRS = "EPSG:3826"

# 版面：連江、金門放大後平移到主圖左上角作附圖（2026-11-03 使用者指定：
#       連江框在上、金門框**嵌在連江框右下角**（右緣底緣共邊，版面測試圖同款嵌合佈局））
EXCLUDE_INSET = ["金門縣", "連江縣"]      # 抽出來當附圖的縣市
INSET_ORDER = ("連江縣", "金門縣")        # 附圖順序（連江在上；金門嵌其右下角）
ISLAND_SCALE = 1.6                        # 附圖比例尺上限＝主圖 × 1.6（放不進空白海域時自動遞減）
INSET_MIN_SCALE = 0.8                     # 自動避讓時的最低倍率
INSET_BOX_PAD = 0.02                      # 連江附圖內容與外框的留白（佔框寬/高比例）
INSET_MARGIN_FRAC = 0.02                  # 附圖距主圖左上角的邊距（佔主圖寬/高比例）
INSET_CLEARANCE_M = 250.0                 # 附圖框與其他縣市（本島／澎湖）的最小淨空（米）
# 2012 底圖缺漏的鄉鎮市區（由 111 年村里界 SHP 補）：金門縣烏坵鄉
EXTRA_TOWNS = {("金門縣", "烏坵鄉")}
# 需放進「金門框」小方框的小離島鄉鎮（不依實際距離擺放，使用者指定）
EXTRA_ISLET_TOWNS = {("金門縣", "烏坵鄉")}
EXTRA_ISLET_BOX_PX = 2                    # 烏坵小方框 2px（與金門框 6px 區別）
EXTRA_ISLET_MARGIN = 0.06                 # 烏坵小方框距金門框邊緣的留白（佔框寬/高比例）
EXTRA_ISLET_CORNER = "右下"               # 烏坵小方框在父框中的位置：左上／右上／左下／右下
                                          # （2026-11-03 使用者指定：改放金門框右下角）
KM_ISLET_FAR_KM = 26000.0                 # 金門附圖剔除遠島部件的距離門檻（東碇島等，
                                          #     與版面測試圖同規則；主圖其他縣市不受影響）
KM_BOX_GAP_FRAC = 0.05                    # 金門框內留白（佔金門內容高）：
                                          #     金門框寬＝內容＋烏坵框＋3×留白（內容貼左下、
                                          #     烏坵框貼右下，互不重疊；版面測試圖同款）

# 2012 底圖缺漏的村里（由 106 年村里界 SHP 補）：宜蘭縣頭城鎮龜山里之**龜山島**
#   twvillage2012.json 的「頭城鎮龜山里」只有本島沿岸部分，缺外海約 11 km 的龜山島
#   （106 年＝1070205 村里界的龜山里為 MultiPolygon：本島沿岸＋龜山島，
#     與 2020/2024 總統北四縣市腳本「龜山島有村里編制、須保留」同一認定）。
GUEISHAN_KEY = ("宜蘭縣", "頭城鎮", "龜山里")
GUEISHAN_MIN_OFFSHORE_M = 2000.0          # 距宜蘭縣本體 >2 km 的部件才視為龜山島
                                          #     （本島沿岸部分 2012 json 已有，不重複補）
GUEISHAN_TEST_OUT = os.path.join(OUT_DIR, "全臺灣2008_龜山島補漏測試圖.png")

# 縣市界依 2008 年行政區還原（2010 五都升格前的臺中/臺南/高雄縣市）
SPLIT_COUNTY = {"臺中市": ("臺中市", "臺中縣"),
                "臺南市": ("臺南市", "臺南縣"),
                "高雄市": ("高雄市", "高雄縣")}
CITY_TOWNS = {   # 2010 前「市」部分的鄉鎮市區（去「區」尾綴後）
    "臺中市": {"中", "東", "西", "南", "北", "西屯", "南屯", "北屯"},
    "臺南市": {"中西", "東", "南", "北", "安平", "安南"},
    "高雄市": {"楠梓", "左營", "鼓山", "鹽埕", "旗津", "三民",
              "前金", "新興", "苓雅", "前鎮", "小港"},
}
RENAME_2008 = {"新北市": "臺北縣"}        # 2010 升格前的縣名

# 比例尺與畫布（長寬硬上限 10000 × 12500 px，超出則自動放大比例尺）
METERS_PER_PIXEL = 12.0
MAX_W_PX = 10000
MAX_H_PX = 12500
PAD_FRAC = 0.01
SIMPLIFY_TOL_M = 0.0          # 0 = 不簡化

# 線寬（依使用者指定：村里界 1px、鄉鎮市區界 2px、縣市界 6px、海岸線 1px）
LINE_VILLAGE_PX = 1           # 村里界（＝澎湖／金門／連江的海岸線與礁石，同一畫法）
LINE_TOWNSHIP_PX = 2          # 鄉鎮市區界
LINE_COUNTY_INNER_PX = 6      # 縣市界（兩縣市共有段，只畫內陸交界，不含海岸線）
LINE_COAST_PX = 1             # 海岸線（本島各縣市聯集外輪廓）：金馬同款 1px 畫法（1px 直繪 → thin）
THIN_COUNTIES = {"澎湖縣", "金門縣", "連江縣"}   # 小島縣市：海岸線／礁石一律 1px（同村里界畫法）
LINE_INSET_BOX_PX = 6         # 金門／連江附圖外框
# 線色（使用者指定）：村里界／鄉鎮市區界／縣市界／海岸線／附圖外框 一律 #FCFCFC
# 線稿仍以純黑成像取遮罩（二值化才可靠），最後一步才把 lines_mask 上色 → 線寬不變
LINE_COLOR = "#FCFCFC"
LINE_RGB = tuple(int(round(v * 255)) for v in nat.hex2rgb(LINE_COLOR))
THRESHOLD_VAL = 40            # 線稿二值化閾值
HOLE_MIN_AREA_M2 = 10000.0    # 小於此面積的內環視為 dissolve 雜訊，填平
FAR_PART_MAX_KM = 100.0       # 距本島超過此距離的圖資碎塊不畫（東沙/南沙/釣魚台等）

DPI = nat.DPI
PX2PT = 72.0 / DPI
NO_DATA_COLOR = nat.NO_DATA_COLOR
SAVE_LAYER = False

# 平票規則（規格同 Precident/平票斜線紋_通用程式碼片段.txt）：
# 某村里第 1 名與第 2 名得票率差 ≤ TIE_RATE_EPS（或同至小數 3 位、或得票數相同）
# → 底色仍填第 1 名，另以「第 2 名顏色」疊 45° 斜線紋（寬 TIE_STRIPE_PX px）。
TIE_RATE_EPS = nat.TIE_RATE_EPS        # 1e-9
TIE_STRIPE_PX = nat.TIE_STRIPE_PX      # 8（與 full_geom_check 的期望圖同一週期）
# ==================================================

os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------- 異體字收斂 ----------------------
# 底圖與得票資料用字不同（臺/台、峯/峰、嗂/窯、褔/福 …），兩側都先收斂到同一形再比對。
VARIANT_CHAR_MAP = str.maketrans({
    "台": "臺", "峯": "峰", "舘": "館", "磘": "窯", "嗂": "窯", "廍": "部",
    "獇": "羌", "曹": "槽", "脚": "腳", "塩": "鹽", "槺": "糠", "菓": "果",
    "双": "雙", "坂": "板", "厦": "廈", "壳": "殼", "哢": "弄", "壠": "壟",
    "蜣": "羌", "𦰡": "那", "欍": "春", "褔": "福", "穀": "谷", "榖": "谷",
})
# 萬用字元：來源 xls 的 U+FFFD(�)、底圖的「■」與私用區(PUA)碼位
WILDCARD_CHARS = {"\ufffd", "■"} | {chr(c) for c in range(0xE000, 0xF900)}


def _is_wild(ch):
    return ch in WILDCARD_CHARS


def norm_county(s):
    return nat.normalize_text(s).translate(VARIANT_CHAR_MAP)


def norm_town(s):
    return nat.strip_town_suffix(s).translate(VARIANT_CHAR_MAP)


def norm_vill(s):
    return nat.strip_village_suffix(nat.normalize_text(s)).translate(VARIANT_CHAR_MAP)


def wildcard_equal(a, b, allow_no_solid=False):
    """同長度、非萬用字元全等即視為同一名稱。

    allow_no_solid=False（嚴格）：至少要對到一個實字；
    allow_no_solid=True（消去法）：資料側整個村名都存成 U+FFFD 時仍可比對，
    由呼叫端確保「同鄉鎮同長度只有唯一候選」才採用。
    """
    if len(a) != len(b):
        return False
    solid = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            if not _is_wild(ca):
                solid += 1
            continue
        if _is_wild(ca) or _is_wild(cb):
            continue
        return False
    return True if allow_no_solid else solid > 0


# ---------------------- 投票資料側的村名修補 ----------------------
RE_LEAD_NO = re.compile(r"^[0-9０-９]+")


def repair_vote_name(name):
    """修掉中選會原始表殘留的編號前綴（誤植）。

    例：桃園中壢「2龍德里」「7舊明里」「6內定里」、嘉義大林「0內林里」
        → 龍德里／舊明里／內定里／內林里（不修就整里對不上、圖上留白）。
    """
    return RE_LEAD_NO.sub("", str(name).strip())


# ---------------------- ① 讀中選會原始 xls ----------------------
def load_party_votes():
    """解析 25 個縣市原始 xls，聚合到村里層級。

    回傳 (by_key, by_town, display, cnt_by_key, n_total)：
      by_key     : (縣市, 鄉鎮市區, 村里) → 12 個政黨得票率 tuple
      by_town    : (縣市, 鄉鎮市區) → [(村里, rates), ...]（萬用字元/模糊匹配用）
      display    : 同鍵 → (縣市, 鄉鎮, 村里) 原始字樣（報告用）
      cnt_by_key : 同鍵 → (12 個政黨得票數…, 有效票數)
                   （跨里合併重算；鄉鎮版腳本亦由此逐里累加成鄉鎮合計）
      n_total    : xls 實際讀到的村里列數（拆分前）
    """
    files = sorted(glob.glob(XLS_GLOB, recursive=True))
    if not files:
        raise FileNotFoundError(f"找不到中選會原始 xls：{XLS_GLOB}")
    by_key, by_town, display, cnt_by_key = {}, {}, {}, {}
    n_total = 0
    parties_ref = None
    skipped = []

    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        county = FILENAME_COUNTY.get(stem)
        if county is None:
            skipped.append(stem)
            continue
        wb = xlrd.open_workbook(path)
        acc = {}      # (鄉鎮, 村里原文) → [counts..., valid]
        for sh in wb.sheets():
            hdr = None
            for r in range(min(6, sh.nrows)):
                if "鄉(鎮、市、區)別" in str(sh.cell_value(r, 0)):
                    hdr = r
                    break
            if hdr is None:
                continue
            valid_col = None
            for c in range(sh.ncols):
                if "有效票數" in str(sh.cell_value(hdr, c)).replace("\n", ""):
                    valid_col = c
                    break
            if valid_col is None:
                raise ValueError(f"{stem} 找不到「有效票數」欄")
            # 政黨名在第 hdr+3 列（hdr=1 時即第 4 列）
            pcols = [(c, str(sh.cell_value(hdr + 3, c)).strip())
                     for c in range(3, valid_col)]
            pcols = [(c, nm) for c, nm in pcols if nm]
            names = [nm for _, nm in pcols]
            if parties_ref is None:
                parties_ref = names
            elif names != parties_ref:
                raise ValueError(f"{stem} 政黨欄位與其他檔不一致：{names}")

            town = ""
            for r in range(hdr + 4, sh.nrows):
                c0 = str(sh.cell_value(r, 0)).strip()
                c1 = str(sh.cell_value(r, 1)).strip()
                if c0 and not c1:
                    if c0 != "總計":        # 總計列不更新鄉鎮
                        town = c0
                    continue
                if not c1:
                    continue
                try:
                    counts = [float(sh.cell_value(r, c) or 0) for c, _ in pcols]
                    valid = float(sh.cell_value(r, valid_col) or 0)
                except (TypeError, ValueError):
                    continue
                if not town or valid <= 0:
                    continue
                n_total += 1
                k = (town, c1)
                a = acc.get(k)
                if a is None:
                    acc[k] = counts + [valid]
                else:
                    for i, v in enumerate(counts):
                        a[i] += v
                    a[-1] += valid

        # 逐村里換算得票率（多村里併列者拆開，共用同一組得票數）
        for (town_raw, vill_raw), a in acc.items():
            counts, valid = a[:-1], a[-1]
            rates = tuple(v / valid * 100.0 for v in counts)
            town_core = TOWN_ALIAS_BY_SRC.get((stem, norm_town(town_raw)), norm_town(town_raw))
            for part in [p for p in re.split(r"[、，,]", vill_raw) if p.strip()]:
                vk = norm_vill(repair_vote_name(part))
                if not vk:
                    continue
                # 2008→2012 改名（同單元改名，非拆併）：如 高雄縣三民鄉民族村 →
                # 高雄市那瑪夏區南沙魯里、桃源鄉梅蘭村 → 桃源區拉芙蘭里
                t2, v2 = nr.rename_town_vill_2008(county, town_core, vk)
                key = (county, t2, v2)
                if key in by_key:
                    continue
                by_key[key] = rates
                cnt_by_key[key] = tuple(counts) + (valid,)
                by_town.setdefault((county, t2), []).append((v2, rates))
                display[key] = (county, town_raw.strip(), part.strip())
    if skipped:
        print(f"  ⚠️ 略過無法對應縣市的檔案：{skipped}")
    return by_key, by_town, display, cnt_by_key, n_total


# ---------------------- ② 讀底圖（2012 ＋ 嘉義市 pre2010） ----------------------
def _norm_geo_columns(gdf, path):
    """欄位正規化 → 統一欄名 COUNTYNAME／TOWNNAME／VILLNAME。

    2012 底圖同時有小寫短欄（county/town/village，值正確）與長欄
    （countyname/townname，多為空值），故**短欄優先**；pre2010 底圖為
    COUNTYNAME/TOWNNAME/VILLAGENAM 大寫長欄。
    """
    ren = {}
    lower = {str(c).lower(): c for c in gdf.columns}
    for cands, dst in ((("county", "countyname"), "COUNTYNAME"),
                       (("town", "townname"), "TOWNNAME"),
                       (("village", "villagenam"), "VILLNAME")):
        if dst in gdf.columns:
            continue
        for src in cands:
            if src in lower:
                ren[lower[src]] = dst
                break
    if ren:
        gdf = gdf.rename(columns=ren)
    lack = [c for c in ("COUNTYNAME", "TOWNNAME", "VILLNAME") if c not in gdf.columns]
    if lack:
        raise ValueError(f"{os.path.basename(path)} 缺少欄位：{'、'.join(lack)}"
                         f"（現有：{gdf.columns.tolist()}）")
    return gdf


def _load_city_geojson(path=CITY_GEOJSON):
    """讀入民國99年前村里界 twVillage_pre2010.geo.json 的嘉義市子集（同 Draw_YCT4）。"""
    g = _norm_geo_columns(gpd.read_file(path), path)
    g["COUNTYNAME"] = g["COUNTYNAME"].astype(str).str.strip()
    g = g[g["COUNTYNAME"].eq(CITY_GEOJSON_COUNTY)].copy()
    if g.crs is None:
        g.crs = "EPSG:4326"
    g = g.to_crs(TARGET_CRS)
    g["TOWNNAME"] = g["TOWNNAME"].astype(str).str.strip()
    g["VILLNAME"] = g["VILLNAME"].astype(str).str.strip()
    g["geometry"] = g.geometry.buffer(0)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    t, v = g["TOWNNAME"].tolist(), g["VILLNAME"].tolist()
    nv = [CITY_VILL_REPAIR.get((a, b), b) for a, b in zip(t, v)]
    if sum(1 for a, b in zip(v, nv) if a != b):
        print(f"  pre2010 村名對齊 2008 用字（CITY_VILL_REPAIR）："
              f"{sum(1 for a, b in zip(v, nv) if a != b)} 筆")
    g["VILLNAME"] = nv
    return g[["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry"]].reset_index(drop=True)


def _apply_city_geojson(gdf, path=CITY_GEOJSON):
    """把嘉義市的村里層換成民國99年前村里界（pre2010）——同 Draw_YCT4 的四步機制。

    外緣（市界）與東/西區區界仍以 twvillage2012.json 為準，只有村里細分線換 pre2010：
      ① 逐里裁剪：pre2010 里 ∩ 2012 市界 → 村里線不越出市界；
      ② 市界補塊：市界內未被任何 pre2010 里涵蓋的碎屑，逐塊併入最近的里；
      ③ 區界硬切：每里再按 2012 區界裁剪，區界不因 pre2010 里跨區而畫歪；
      ④ 區內貼合：把「2012 區面 − 區內各里聯集」的殘餘補進最近的里，
         使各區的里聯集精確等於 2012 區面（避免共邊處出現亞像素縫、被誤畫成粗黑線）。
    """
    city = _load_city_geojson(path)
    if not len(city):
        print("  pre2010 底圖置換：無有效要素，維持 JSON 底圖")
        return gdf
    CITY = CITY_GEOJSON_COUNTY
    is12 = gdf["COUNTYNAME"].eq(CITY)
    json_city, rest = gdf[is12].copy(), gdf[~is12].copy()
    if not len(json_city):
        print(f"  pre2010 底圖置換：底圖無「{CITY}」，維持 JSON 底圖")
        return gdf

    S_12 = unary_union(json_city.geometry.tolist())
    S_pre = unary_union(city.geometry.tolist())
    town_geoms = {}
    for _t, _g in zip(json_city["TOWNNAME"], json_city["geometry"]):
        town_geoms.setdefault(_t, []).append(_g)
    town_geoms = {k: unary_union(v) for k, v in town_geoms.items()}

    # ① 逐里裁剪
    city["geometry"] = [g.intersection(S_12) for g in city.geometry]
    city = city[~city.geometry.isna() & ~city.geometry.is_empty].copy().reset_index(drop=True)
    if not len(city):
        print("  pre2010 底圖置換：裁剪後無有效要素，維持 JSON 底圖")
        return gdf

    # ② 市界補塊
    _geoms = list(city["geometry"])
    _resid = S_12.difference(unary_union(_geoms))
    _n_patch = 0
    if not _resid.is_empty:
        for _c in (list(_resid.geoms) if hasattr(_resid, "geoms") else [_resid]):
            _k = int(np.argmin([g.distance(_c) for g in _geoms]))
            _geoms[_k] = _geoms[_k].union(_c)
            _n_patch += 1
    city["geometry"] = _geoms

    # ③ 區界硬切
    def _cut_row(r):
        g = r["geometry"]
        tg = town_geoms.get(r["TOWNNAME"])
        return g.intersection(tg) if tg is not None else g

    city["geometry"] = city.apply(_cut_row, axis=1)
    city = city[~city.geometry.isna() & ~city.geometry.is_empty].copy().reset_index(drop=True)

    # ④ 區內貼合
    _n_fill = 0
    for _t, _sub in city.groupby("TOWNNAME"):
        tg = town_geoms.get(_t)
        if tg is None:
            continue
        idxs = list(_sub.index)
        gs = [city.at[i, "geometry"] for i in idxs]
        _r = tg.difference(unary_union(gs))
        if _r.is_empty:
            continue
        for _c in (list(_r.geoms) if hasattr(_r, "geoms") else [_r]):
            _k = int(np.argmin([g.distance(_c) for g in gs]))
            gs[_k] = gs[_k].union(_c)
            _n_fill += 1
        for i, g in zip(idxs, gs):
            city.at[i, "geometry"] = g
    city = city[~city.geometry.isna() & ~city.geometry.is_empty].copy().reset_index(drop=True)
    city["VILLNAME_RAW"] = city["VILLNAME"]
    city["NAME_REPAIR"] = ""

    out = pd.concat([rest, city], ignore_index=True)
    out = out[~out.geometry.isna() & ~out.geometry.is_empty].reset_index(drop=True)
    _u = unary_union(city.geometry.tolist())
    _parts = len(_u.geoms) if hasattr(_u, "geoms") else 1
    print(f"  pre2010 底圖置換：{CITY} 村里層改用民國99年前村里界"
          f"（原 JSON {len(json_city)} 筆 → pre2010 {len(city)} 里）")
    print(f"    S_12 {S_12.area / 1e6:.2f} km²、S_pre {S_pre.area / 1e6:.2f} km²、"
          f"互有出入 {S_pre.symmetric_difference(S_12).area / 1e6:.3f} km²；"
          f"市界補塊 {_n_patch}、區內貼合 {_n_fill}；市側聯集 {_parts} 塊（應 1）")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def resolve_cross_county_overlaps(gdf, min_piece_m2=2000.0):
    """清理跨縣市多邊形重疊，使相鄰縣市的界線重合為單一條（不出現平行雙線）。

    問題：twvillage2012.json 在少數縣市交界兩側的村里多邊形互相重疊
    （最嚴重是 **臺中市／苗栗縣 大甲—苑裡**：合計 34.9 ha，其中 33.5 ha 集中一塊，
    臺中的大甲 幸福里 與 苗栗的苑裡 山柑/玉田/新復 互相咬進對方）。
    重疊會讓縣市界畫成「兩條平行粗線夾著一條色帶」，填色也會出現滲透色。

    仲裁：以「民國111年村里界」SHP 的縣市範圍為準（單一來源、拓撲無重疊）。
    對每一對相鄰縣市取其「整條重疊帶」，比較兩縣市 SHP 範圍各佔多少面積，
    面積大者為歸屬方，再從另一縣市（非歸屬方）的村里多邊形整條減去 ——
    因該帶本來就在歸屬方境內，減去後不會產生破洞，兩縣市界線自然重合為單線。
    （重疊帶總面積 < min_piece_m2＝0.2 ha 者不處理：在 30.7 m/px 下 <0.2 px，肉眼不可見）
    """
    if not os.path.exists(SHP_COUNTY):
        print(f"  跨縣市重疊清理：略過（找不到 {os.path.basename(SHP_COUNTY)}）")
        return gdf
    shp = gpd.read_file(SHP_COUNTY, encoding="utf-8")
    if shp.crs is None:
        shp = shp.set_crs("EPSG:4326")
    shp = shp.to_crs(TARGET_CRS)
    SHP_ALIAS = {"桃園市": "桃園縣", "臺中縣": "臺中市", "臺南縣": "臺南市",
                 "高雄縣": "高雄市", "臺北縣": "新北市"}
    shp["_c"] = shp["COUNTYNAME"].astype(str).str.strip().replace(SHP_ALIAS)
    shp_u = {c: unary_union(sub.geometry.tolist()) for c, sub in shp.groupby("_c")}

    counties = sorted(gdf["COUNTYNAME"].unique())
    uni = {c: unary_union(gdf.loc[gdf["COUNTYNAME"] == c, "geometry"].tolist())
           for c in counties}
    drop_by_county = {}          # 縣市 → 需從其村里減去的幾何
    n_pair = 0
    for a, b in itertools.combinations(counties, 2):
        A, B = uni[a], uni[b]
        if A.distance(B) > 1.0:
            continue
        C = A.intersection(B)
        if C.is_empty or C.area <= min_piece_m2:
            continue
        # 以 SHP 縣市範圍與整條重疊帶的重疊面積多寡仲裁：面積大者為歸屬方
        ar_a = C.intersection(shp_u[a]).area if a in shp_u else 0.0
        ar_b = C.intersection(shp_u[b]).area if b in shp_u else 0.0
        if abs(ar_a - ar_b) < 1e-9:
            print(f"    （{a}／{b} 重疊 {C.area / 1e4:.2f} ha，SHP 難判歸屬 → 略過）")
            continue
        loser = b if ar_a > ar_b else a
        drop_by_county.setdefault(loser, []).append((f"{a}／{b}", C))
        n_pair += 1

    if not n_pair:
        print(f"  跨縣市重疊清理：無需處理（門檻 {min_piece_m2:.0f} m²）")
        return gdf

    out = gdf.copy()
    for c, items in drop_by_county.items():
        cut = unary_union([g for _n, g in items])
        m = out["COUNTYNAME"] == c
        idx = out.index[m]
        newg = [out.at[i, "geometry"].difference(cut)
                if out.at[i, "geometry"].intersects(cut) else out.at[i, "geometry"]
                for i in idx]
        out.loc[idx, "geometry"] = newg
    out = out[~out.geometry.isna() & ~out.geometry.is_empty].copy()
    out["geometry"] = out.geometry.buffer(0)
    out = out.reset_index(drop=True)
    _desc = "、".join(f"{c} 讓出 {len(v)} 條帶"
                     for c, v in drop_by_county.items())
    _ar = "、".join(f"{n} {g.area / 1e4:.2f} ha" for c, v in drop_by_county.items()
                   for n, g in v)
    print(f"  跨縣市重疊清理：{n_pair} 對縣市 → {_desc}")
    print(f"    重疊帶：{_ar}（以 111 年村里界縣市範圍仲裁，使縣市界重合為單線）")
    return out


def drop_nan_village_parts(gdf, keep=None):
    """剔除「村里名為 NaN」的圖斑 —— 除新北／金門／連江／澎湖／新竹市外。

    這些圖斑雖掛在某鄉鎮市區下，實際是港區、水域或無名碎塊（高雄港、臺中港…），
    畫出來只會多出無意義的白色缺口；金馬澎的無名圖斑則是礁石，必須保留
    （無資料 → 留白，界線以 1px 畫法描邊）。
    """
    keep = keep or NAN_KEEP_COUNTIES
    bad = gdf["VILLNAME"].eq("") & ~gdf["COUNTYNAME"].isin(keep)
    if int(bad.sum()):
        print(f"  剔除無村里名圖斑（{len(NAN_KEEP_COUNTIES)} 個縣市除外）："
              f"{int(bad.sum())} 筆 → {gdf.loc[bad, 'COUNTYNAME'].value_counts().to_dict()}")
    return gdf[~bad].copy().reset_index(drop=True)


def count_islet_parts(gdf, counties=KINMEN_MATSU):
    """統計附圖縣市的島礁部件數 —— 只統計、不剔除。

    106 年村里界把金門／連江的礁石（東碇島、亮島、中柱島等）併進村里的 multipolygon，
    舊版為避免附圖框被撐大而依「距主島距離」整組剔除，結果連無名礁石一起被砍掉
    （金門 7 塊、連江 73 塊）。**使用者要求無名礁石全部畫出來**，故改為全數保留，
    由 ① 層（村里界 1px 直繪 → thin）逐塊描邊。
    """
    for c in counties:
        sub = gdf[gdf["COUNTYNAME"] == c]
        if not len(sub):
            continue
        n_all = n_unnamed = 0
        for v, g in zip(sub["VILLNAME"], sub["geometry"]):
            ps = list(g.geoms) if hasattr(g, "geoms") else [g]
            n_all += len(ps)
            if not str(v).strip():
                n_unnamed += len(ps)
        print(f"  島礁部件（{c}）：{n_all} 塊（其中無村里名礁石 {n_unnamed} 塊，全數保留）")


def _read_shp_base(path, drop_nan=True):
    """讀村里界 SHP 為統一格式（COUNTYNAME/TOWNNAME/VILLNAME、EPSG:3826）。

    SHP 無內建 CRS（與 108／111 年版相同）→ 視為 EPSG:4326 再投影 3826。
    .dbf 編碼各年版不同（108／111 為 UTF-8、**106 版為 Big5**）→ 依序嘗試。
    VILLNAME 允許為空（離島礁石常無村里名），由呼叫端決定是否剔除。
    """
    g, err = None, None
    for enc in ("utf-8", "cp950"):
        try:
            g = gpd.read_file(path, encoding=enc)
            break
        except UnicodeDecodeError as e:      # .dbf 為 Big5 時 utf-8 會失敗
            err = e
    if g is None:
        raise err
    g = _norm_geo_columns(g, path)
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    g = g.to_crs(TARGET_CRS)
    for c in ("COUNTYNAME", "TOWNNAME", "VILLNAME"):
        g[c] = g[c].apply(lambda x: "" if pd.isna(x) else str(x).strip())
    g["geometry"] = g.geometry.buffer(0)
    g = g[~g.geometry.isna() & ~g.geometry.is_empty].copy()
    g = g.reset_index(drop=True)
    if drop_nan:
        g = drop_nan_village_parts(g)
    return g


def replace_counties_from_shp(gdf, counties=KINMEN_MATSU, path=SHP_106):
    """把指定縣市（金門、連江）換成 106 年村里界（1070205）圖資 —— 底圖拼接。

    2012 json 的金馬村里層偏粗（連江僅 21 個有名村里、其餘 168 個無名圖斑被剔除，
    且整份缺烏坵鄉）；106 年版村里界同為全臺同一套圖資、村里更完整並含烏坵鄉，
    故金馬改用它拼接，其餘 20 個縣市仍用 2012 json（與分區腳本一致）。
    """
    if not os.path.exists(path):
        print(f"  ⚠️ 找不到 {os.path.basename(path)}，金門／連江 維持 2012 json")
        return gdf
    shp = _read_shp_base(path)
    shp = shp[shp["COUNTYNAME"].isin(counties)].copy()
    count_islet_parts(shp)          # 只統計、不剔除：島礁圖斑全部保留（含無名礁石）
    if not len(shp):
        print(f"  ⚠️ {os.path.basename(path)} 無 {'、'.join(counties)}，維持 2012 json")
        return gdf
    cols = ["COUNTYNAME", "TOWNNAME", "VILLNAME", "geometry"]
    keep = gdf[~gdf["COUNTYNAME"].isin(counties)][cols].copy()
    out = gpd.GeoDataFrame(pd.concat([keep, shp[cols]], ignore_index=True),
                           geometry="geometry", crs=TARGET_CRS)
    _n = shp.groupby("COUNTYNAME").size().to_dict()
    print(f"  金門／連江 底圖拼接：改用 106 年村里界（1070205）"
          f"→ {'、'.join(f'{c} {n} 村里' for c, n in _n.items())}"
          f"（原 2012 json 為 "
          f"{'、'.join(f'{c} {int((gdf.COUNTYNAME == c).sum())}' for c in counties)}）")
    return out


def load_shp_base(path=SHP_106):
    """以村里界 SHP（106 年／1070205）直接作全臺底圖 —— 鄉鎮市區版使用。

    - 保留「無村里名」圖斑：多為離島礁石，鄉鎮層 dissolve 仍需要它撐面積（全數保留）
    - 縣市名對齊得票資料：桃園市（2014 升格）→ 桃園縣
    """
    g = _read_shp_base(path)
    count_islet_parts(g)            # 只統計、不剔除：島礁圖斑全部保留（含無名礁石）
    g["COUNTYNAME"] = g["COUNTYNAME"].replace({"桃園市": "桃園縣"})
    print(f"  底圖：106 年村里界（1070205）→ {len(g)} 個村里圖斑、"
          f"{g.groupby(['COUNTYNAME', 'TOWNNAME']).ngroups} 個鄉鎮市區")
    return g


def supplement_missing_towns(gdf, extra=EXTRA_TOWNS):
    """補上 2012 底圖缺漏的鄉鎮市區（金門縣烏坵鄉）——取自 111 年村里界 SHP。

    twvillage2012.json 不含烏坵鄉（大坵村、小坵村），少一個鄉鎮市區
    （全臺應為 368 個，只用 json 會變 367）。2008 不分區選舉烏坵有投票所，
    故以同一套圖資（民國111年村里界）補入，村里名保留「村」尾綴與其他鄉鎮一致，
    後續比對／繪圖邏輯不需特例。
    """
    have = set(zip(gdf["COUNTYNAME"], gdf["TOWNNAME"]))
    need = [k for k in extra if k not in have]
    if not need:
        return gdf
    if not os.path.exists(SHP_COUNTY):
        print(f"  ⚠️ 缺 {need}，且找不到 111 年村里界 SHP，無法補漏")
        return gdf
    shp = gpd.read_file(SHP_COUNTY, encoding="utf-8")
    if shp.crs is None:
        shp = shp.set_crs("EPSG:4326")
    shp = shp.to_crs(TARGET_CRS)
    c = shp["COUNTYNAME"].astype(str).str.strip()
    t = shp["TOWNNAME"].astype(str).str.strip()
    m = pd.Series(False, index=shp.index)
    for cn, tn in need:
        m |= (c == cn) & (t == tn)
    pick = shp[m]
    if not len(pick):
        print(f"  ⚠️ 111 年村里界 SHP 亦無 {need}")
        return gdf
    add = gpd.GeoDataFrame({
        "COUNTYNAME": c[m].values,
        "TOWNNAME": t[m].values,
        "VILLNAME": pick["VILLNAME"].astype(str).str.strip().values,
        "geometry": pick.geometry.values,
    }, geometry="geometry", crs=TARGET_CRS)
    out = gpd.GeoDataFrame(pd.concat([gdf, add], ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    print(f"  補漏鄉鎮市區：{'、'.join(f'{cn}{tn}（{len(add)} 村里）' for cn, tn in need)}"
          f" ← 取自 111 年村里界 SHP")
    return out


def add_gueishan_island(gdf, key=GUEISHAN_KEY, min_offshore_m=GUEISHAN_MIN_OFFSHORE_M):
    """補上 2012 底圖缺漏的宜蘭縣頭城鎮龜山里之**龜山島** —— 取自 106 年村里界 SHP。

    twvillage2012.json 的「頭城鎮龜山里」只有本島沿岸部分，缺外海約 11 km 的
    龜山島（約 0.32 km²，有村里編制、2008 有投票資料）；106 年（1070205）村里界
    的龜山里為 MultiPolygon（本島沿岸＋龜山島）。
    作法：取 106 年 SHP 龜山里的所有部件，**只挑距宜蘭縣本體 > 2 km 的部件**
    （即龜山島；本島沿岸部分 2012 json 已有，不重複補），以同名
    （宜蘭縣／頭城鎮／龜山里）追加為新村里圖斑 → 比對、填色、繪線全走既有流程
    （龜山島外緣＝村里界 1px 層＋② 屬頭城鎮 2px 邊，與全圖海岸線慣例一致）。
    """
    cn, tn, vn = key
    have = gdf[(gdf["COUNTYNAME"] == cn) & (gdf["TOWNNAME"] == tn)
               & (gdf["VILLNAME"] == vn)]
    if not len(have):
        print(f"  ⚠️ 底圖無 {cn}{tn}{vn}，無法對位補龜山島")
        return gdf
    # 宜蘭本體＝縣內最大連通塊（即使底圖已含離岸島，也不會把島算進「本體」）
    _yilan_u = unary_union(gdf[gdf["COUNTYNAME"] == cn].geometry.tolist())
    _comps = list(_yilan_u.geoms) if _yilan_u.geom_type == "MultiPolygon" else [_yilan_u]
    mainland = max(_comps, key=lambda z: z.area)
    for gg in have.geometry:                     # 已有離岸部件（重跑／換底圖）→ 不重複補
        for pp in (list(gg.geoms) if gg.geom_type == "MultiPolygon" else [gg]):
            if mainland.distance(pp) > min_offshore_m:
                print("  龜山島：底圖已有離岸圖斑，略過補漏")
                return gdf
    if not os.path.exists(SHP_106):
        print("  ⚠️ 找不到 106 年村里界 SHP，無法補龜山島")
        return gdf
    shp = _read_shp_base(SHP_106)
    src = shp[(shp["COUNTYNAME"] == cn) & (shp["TOWNNAME"] == tn)
              & (shp["VILLNAME"] == vn)]
    if not len(src):
        print("  ⚠️ 106 年村里界 SHP 無 頭城鎮龜山里，無法補龜山島")
        return gdf
    islets = []
    for gg in src.geometry:
        for pp in (list(gg.geoms) if gg.geom_type == "MultiPolygon" else [gg]):
            if mainland.distance(pp) > min_offshore_m:
                islets.append(pp)
    if not islets:
        print("  ⚠️ 106 年 SHP 龜山里無離岸部件，無法補龜山島")
        return gdf
    add = gpd.GeoDataFrame({
        "COUNTYNAME": [cn] * len(islets),
        "TOWNNAME": [tn] * len(islets),
        "VILLNAME": [vn] * len(islets),
    }, geometry=islets, crs=gdf.crs)
    out = gpd.GeoDataFrame(pd.concat([gdf, add], ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    _a = sum(p.area for p in islets) / 1e6
    _d = min(mainland.distance(p) for p in islets) / 1000.0
    print(f"  補 2012 底圖缺漏：宜蘭縣頭城鎮龜山里之龜山島 ← 取自 106 年村里界 SHP"
          f"（{len(islets)} 塊、{_a:.2f} km²、距宜蘭本體 {_d:.1f} km）")
    return out


def load_base_map(path=MAP_JSON):
    """讀入 2012 村里界底圖（全臺 22 縣市），再把嘉義市換成 pre2010 村里層。

    欄位 county/town/village（小寫）正規化為 COUNTYNAME/TOWNNAME/VILLNAME；
    檔案無內建 CRS → 視為 EPSG:4326 再投影 EPSG:3826（同 Base_JSON/draw_json_map.py）。
    """
    gdf = _norm_geo_columns(gpd.read_file(path), path)
    if gdf.crs is None:
        gdf.crs = "EPSG:4326"
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = gdf[gdf["COUNTYNAME"].notna()].copy()
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    for c in ("COUNTYNAME", "TOWNNAME", "VILLNAME"):
        gdf[c] = gdf[c].astype(str).str.strip()
    gdf = gdf[~gdf["TOWNNAME"].isin(["", "nan", "None"])].copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf.reset_index(drop=True)

    # 海域圖斑（鄉鎮名帶「(海)」）一律剔除；無村里名者依 NAN_KEEP_COUNTIES 規則處理
    gdf["VILLNAME"] = gdf["VILLNAME"].replace({"NULL": "", "nan": "", "None": ""})
    sea = gdf["TOWNNAME"].str.contains(r"[（(]海[）)]", regex=True, na=False)
    if int(sea.sum()):
        print(f"  剔除海域圖斑：{int(sea.sum())} 筆")
        gdf = gdf[~sea].copy().reset_index(drop=True)
    gdf = drop_nan_village_parts(gdf)

    gdf = replace_counties_from_shp(gdf, KINMEN_MATSU, SHP_106)
    gdf = supplement_missing_towns(gdf)
    gdf = add_gueishan_island(gdf)
    gdf = _apply_city_geojson(gdf, CITY_GEOJSON)
    gdf = repair_base_names(gdf)
    return gdf


def repair_base_names(gdf):
    """還原 twvillage2012.json 的村里名正字（私用區 PUA 碼位／「■」佔位符）。

    就地改寫 VILLNAME；另存 VILLNAME_RAW（原名）與 NAME_REPAIR
    （非空者＝該列曾修補，值為「原名 → 正名」），供稽核報告逐筆核對。
    規則見 village_name_repair.repair_json_vill_name（PUA→正字、■ 逐名指定）。
    """
    raw = gdf["VILLNAME"].tolist()
    fixed, notes = [], []
    for c, t, v in zip(gdf["COUNTYNAME"], gdf["TOWNNAME"], raw):
        fv, _chg, note = nr.repair_json_vill_name(str(c), str(t), v)
        fixed.append(fv)
        notes.append(note)
    out = gdf.copy()
    out["VILLNAME_RAW"] = raw
    out["VILLNAME"] = fixed
    out["NAME_REPAIR"] = notes
    _n = int((out["NAME_REPAIR"].astype(str).str.len() > 0).sum())
    if _n:
        print(f"  ② 底圖村名修補（PUA 碼位／■ 還原）：{_n} 筆")
    return out


def add_old_county(gdf):
    """補「2008 年縣市」欄（2010 五都升格前的 25 個縣市），供縣市界與統計使用。"""
    def _old(r):
        c = r["COUNTYNAME"]
        if c in SPLIT_COUNTY:
            city, cty = SPLIT_COUNTY[c]
            return city if norm_town(r["TOWNNAME"]) in CITY_TOWNS[c] else cty
        return RENAME_2008.get(c, c)

    gdf = gdf.copy()
    gdf["OLD_COUNTY"] = gdf.apply(_old, axis=1)
    return gdf


def strip_far_parts(gdf, max_km=FAR_PART_MAX_KM):
    """剔除離本島過遠的圖資碎塊（東沙／南沙／釣魚台等），保留澎湖（約 50 km）。

    金門、連江要當附圖，故不參與此判斷（呼叫前已排除）。
    """
    cover = ~gdf["COUNTYNAME"].isin(EXCLUDE_INSET)
    sub = gdf[cover]
    parts, owner = [], []
    for i, geom in enumerate(sub.geometry):
        for pp in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            parts.append(pp)
            owner.append(sub.index[i])
    if len(parts) <= 1:
        return gdf
    merged = unary_union(parts)
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    main = max(comps, key=lambda z: z.area)
    far_owner = set()
    n_drop = 0
    for j, pp in enumerate(parts):
        if main.distance(pp) / 1000.0 > max_km:
            far_owner.add(owner[j])
            n_drop += 1
    if far_owner:
        print(f"  離島碎塊清理：剔除 {n_drop} 塊（距本島 > {max_km:.0f} km）"
              f"→ {gdf.loc[list(far_owner), 'OLD_COUNTY'].value_counts().to_dict()}")
        gdf = gdf.drop(index=list(far_owner)).reset_index(drop=True)
    else:
        print(f"  離島碎塊清理：無需剔除（門檻 {max_km:.0f} km）")
    return gdf


# ---------------------- ③ 村里名比對 ----------------------
# 有村里沿革表的縣市（北北基宜 village_lineage_north4；桃竹苗 village_lineage_tcm4），
# 這些縣市 2012 圖資多出、但 2008 尚未設立的里 → 併入 2008 年的母里
# （同底色、其間不畫界線）＝分區腳本的「沿革合併」。
NORTH4_COUNTIES = {"臺北市", "新北市", "基隆市", "宜蘭縣"}
TCM4_COUNTIES = {"桃園縣", "新竹縣", "新竹市", "苗栗縣"}


def build_lineage_index(by_key):
    """建立北北基宜＋桃竹苗的沿革索引（母里／子里、2008→2012 跨里合併）。"""
    norm = lambda s: str(s).translate(VARIANT_CHAR_MAP)
    return {
        "norm": norm,
        "exists_all": set(by_key.keys()),
        "exists_nc": {(t, v) for (c, t, v) in by_key if c == "新北市"},
        "split_index": lin.build_split_index(norm, enabled=True),
        "split_index_n4": lin.build_split_index_north4(norm, enabled=True),
        "split_index_tcm": lin4.build_split_index(norm, enabled=True),
        "vote_merge_index": lin.build_vote_merge_index(norm, enabled=True),
    }


def add_unit_core(gdf, idx):
    """補「2008 年行政單元」欄：沿革合併者指向母里，其餘同村里名。"""
    def _unit(r):
        c, t, v = norm_county(r["COUNTYNAME"]), norm_town(r["TOWNNAME"]), r["vill_core"]
        if c in NORTH4_COUNTIES:
            if c == "新北市":
                return lin.resolve_unit_name(t, v, idx["exists_nc"], idx["split_index"],
                                             year=2008,
                                             split_years=lin.VILLAGE_SPLIT_YEARS)
            return lin.resolve_unit_name_north4(c, t, v, idx["exists_all"],
                                                idx["split_index_n4"], year=2008)
        if c in TCM4_COUNTIES:
            # 同 Draw_TCM4：底圖有、得票資料沒有 → 一律往沿革母里追溯（可連續追溯）
            return lin4.resolve_unit_name(c, t, v, idx["exists_all"],
                                          idx["split_index_tcm"])
        return v

    out = gdf.copy()
    out["unit_core"] = out.apply(_unit, axis=1)
    out["merged_into"] = np.where(out["unit_core"] != out["vill_core"],
                                  out["unit_core"], "")
    _n = int((out["merged_into"] != "").sum())
    _by = out.loc[out["merged_into"] != "", "OLD_COUNTY"].value_counts().to_dict()
    print(f"  村里沿革合併（北北基宜＋桃竹苗）：{_n} 個 2012 里併入 2008 母里 {_by}")
    return out


def match_votes(gdf, by_key, by_town, cnt_by_key, idx):
    """四層比對：沿革合併／本身 → 跨里合併 → 萬用字元 → 單字異體模糊。"""
    rate_cols = [f"rate{i}" for i in range(len(PARTIES))]
    gdf = gdf.copy()
    gdf["vill_core"] = gdf["VILLNAME"].map(norm_vill)
    gdf = add_unit_core(gdf, idx)
    merge_idx = idx["vote_merge_index"]

    def _merged_rates(ck, tk, vk):
        """2012 里 ← 多個 2008 里：以得票數加總後重算得票率。"""
        srcs = merge_idx.get((ck, tk, vk))
        if not srcs:
            return None, []
        tot = [0.0] * len(PARTIES)
        used = []
        for s in srcs:
            c = cnt_by_key.get((ck, tk, s))
            if c is None:
                continue
            for i in range(len(PARTIES)):
                tot[i] += c[i]
            used.append(s)
        if not used or sum(tot) <= 0:
            return None, []
        ssum = sum(tot)
        return [v / ssum * 100.0 for v in tot], used

    def _one(r):
        ck, tk = norm_county(r["COUNTYNAME"]), norm_town(r["TOWNNAME"])
        vk, unit = r["vill_core"], r["unit_core"]
        if not vk:
            return [np.nan] * len(PARTIES) + ["none", ""]
        # ① 沿革合併後的行政單元（＝母里）或村里本身
        for key_v in ([unit] if unit and unit != vk else [vk]):
            rates = by_key.get((ck, tk, key_v))
            if rates is not None:
                mt = "exact" if key_v == vk else f"merged:{key_v}"
                return list(rates) + [mt, key_v]
        # ② 跨里合併（多個 2008 里 → 一 2012 里，得票數加總重算）
        rates, srcs = _merged_rates(ck, tk, unit or vk)
        if rates is not None:
            return rates + [f"mergevote:{'+'.join(srcs)}", "+".join(srcs)]
        # ③ 萬用字元（資料側 U+FFFD、底圖 ■/PUA）
        for cand, val in by_town.get((ck, tk), []):
            if cand != vk and wildcard_equal(vk, cand):
                return list(val) + [f"wildcard:{cand}", cand]
        # ③b 消去法：資料側村名整串都是 U+FFFD，同鄉鎮同長度只有唯一候選才採用
        loose = [cand for cand, _v in by_town.get((ck, tk), [])
                 if cand != vk and wildcard_equal(vk, cand, allow_no_solid=True)]
        if len(loose) == 1:
            val = dict(by_town[(ck, tk)])[loose[0]]
            return list(val) + [f"elimination:{loose[0]}", loose[0]]
        # ④ 單字異體模糊（nat.fuzzy_lookup）
        best, vals, mt = nat.fuzzy_lookup(ck, tk, vk, by_key, by_town)
        if vals is None:
            return [np.nan] * len(PARTIES) + ["none", ""]
        return list(vals) + [mt, best]

    res = gdf.apply(_one, axis=1, result_type="expand")
    gdf[rate_cols] = res.iloc[:, :len(PARTIES)].to_numpy()
    gdf["match_type"] = res.iloc[:, len(PARTIES)].astype(str)
    gdf["matched_vill"] = res.iloc[:, len(PARTIES) + 1].astype(str)

    # 自檢：任何比對（沿革／合併／萬用字元／消去法／模糊）都必須落在
    # 「同縣市＋同鄉鎮」的候選集合內 —— 絕不可跨縣市／跨鄉鎮亂配。
    allowed = {(c, t): {v for v, _ in lst} for (c, t), lst in by_town.items()}
    bad = []
    for c, t, mt_, mv in zip(gdf["COUNTYNAME"], gdf["TOWNNAME"],
                             gdf["match_type"], gdf["matched_vill"]):
        if mt_ in ("exact", "none") or not mv:
            continue
        pool = allowed.get((norm_county(c), norm_town(t)), set())
        cands = mv.split("+") if mt_.startswith("mergevote") else [mv]
        if any(x not in pool for x in cands):
            bad.append((c, t, mt_, mv))
    print(f"  跨鄉鎮誤配自檢：{len(bad)} 筆（應為 0；比對範圍限同縣市同鄉鎮）")
    if bad:
        print(f"    ⚠️ {bad[:5]}")
    return gdf, rate_cols


def pick_colors(gdf, rate_cols, cnt_by_key=None):
    """取各村里得票率最高的政黨，以其政黨色階（依得票率選深淺）填色。

    平票不改底色：底色仍由 `np.argmax` 決定（同票時取 PARTIES 表頭順序在前者），
    但另存 `tie_hex`＝第 2 名顏色，供 `nat.apply_tie_stripes` 疊 45° 斜線紋
    （規格同 Precident/平票斜線紋_通用程式碼片段.txt）。
    判定：第 1、2 名得票率同至小數 3 位、或得票數相同、或差 ≤ TIE_RATE_EPS。
    """
    has_data = gdf[rate_cols].notna().any(axis=1)
    gdf = gdf.copy()

    def _fill(row):
        vals = [row[c] if not np.isnan(row[c]) else -1.0 for c in rate_cols]
        i = int(np.argmax(vals))
        if vals[i] < 0:
            return NO_DATA_COLOR
        return nat.get_color_by_value(vals[i], PARTY_STOPS[PARTIES[i]]) or NO_DATA_COLOR

    gdf["fill_hex"] = np.where(has_data, gdf.apply(_fill, axis=1), NO_DATA_COLOR)
    gdf["fill_hex"] = gdf["fill_hex"].fillna(NO_DATA_COLOR)

    win = np.argmax(gdf.loc[has_data, rate_cols].fillna(-1).to_numpy(dtype=float), axis=1)
    gdf["win_party"] = ""
    gdf.loc[has_data, "win_party"] = [PARTIES[i] for i in win]
    min_win = float(np.nanmin(gdf.loc[has_data, rate_cols].max(axis=1))) if has_data.any() else 0.0

    # ---- 平票偵測：第 1、2 名同票 → tie_hex＝第 2 名顏色（不覆蓋底色） ----
    def _tie(row):
        vals = [row[c] if not np.isnan(row[c]) else -1.0 for c in rate_cols]
        order = sorted(range(len(vals)), key=lambda i: vals[i], reverse=True)
        if len(order) < 2 or vals[order[0]] < 0:
            return (np.nan, "")
        a, b = order[0], order[1]
        cnts = cnt_by_key.get((norm_county(row["COUNTYNAME"]), norm_town(row["TOWNNAME"]),
                               str(row["matched_vill"]))) if cnt_by_key else None
        tied = (round(vals[a], 3) == round(vals[b], 3)) or (
            cnts is not None and float(cnts[a]) == float(cnts[b]))
        tied = tied or (vals[a] - vals[b] <= TIE_RATE_EPS)
        if not tied:
            return (np.nan, "")
        c1 = nat.get_color_by_value(vals[a], PARTY_STOPS[PARTIES[a]])
        c2 = nat.get_color_by_value(vals[b], PARTY_STOPS[PARTIES[b]])
        # 兩黨同屬一個色階組（例如都落在第 0 組灰）時顏色相同，疊了也看不出來 → 不疊
        if c1 and c2 and c1.upper() != c2.upper():
            return (c2, PARTIES[b])
        return (np.nan, "")

    gdf["tie_hex"] = pd.Series(np.nan, index=gdf.index, dtype=object)
    gdf["tie_party"] = ""
    if has_data.any():
        _t = gdf[has_data].apply(_tie, axis=1, result_type="expand")
        gdf.loc[has_data, "tie_hex"] = _t[0].to_numpy()
        gdf.loc[has_data, "tie_party"] = _t[1].to_numpy()
    return gdf, has_data, min_win


def fill_blank_islets_town_colors(gdf, has_data, cnt_by_key, rate_cols):
    """金馬澎的空白島嶼 → 填入所屬鄉鎮市區的得票率顏色（2026-11-03 使用者指定）。

    適用範圍**僅限金門縣／連江縣／澎湖縣**：這些縣市裡比對不到得票資料的
    島嶼圖斑（無村里名的礁石、或劃入某村但 2008 無投票資料的無人島），
    改以「所屬鄉鎮市區」的得票率顏色填色 —— 鄉鎮得票率＝轄內各村得票數
    逐黨合計後重算（與跨里合併同一算法），取領先政黨依得票率選色階深淺。
    其餘 19 個縣市不受影響（無資料仍留白）。已填色者 match_type 標為
    "town"，不再計入「無資料」統計與稽核報告。
    """
    gdf = gdf.copy()
    blank = (~has_data) & gdf["COUNTYNAME"].isin(("金門縣", "連江縣", "澎湖縣"))
    if not blank.any():
        return gdf, has_data, 0

    # 鄉鎮合計：轄內各村得票數逐黨累加（末位為有效票數）
    town_tot = {}
    for (c, t, _v), a in cnt_by_key.items():
        cur = town_tot.get((c, t))
        if cur is None:
            town_tot[(c, t)] = list(a)
        else:
            for i in range(len(a)):
                cur[i] += a[i]

    filled = 0
    for i in gdf.index[blank]:
        key = (norm_county(gdf.at[i, "COUNTYNAME"]), norm_town(gdf.at[i, "TOWNNAME"]))
        tot = town_tot.get(key)
        if tot is None or tot[-1] <= 0:
            continue
        rates = [v / tot[-1] * 100.0 for v in tot[:-1]]
        j = int(np.argmax(rates))
        col = nat.get_color_by_value(rates[j], PARTY_STOPS[PARTIES[j]])
        if not col:
            continue
        # 平票（鄉鎮合計第 1、2 名同票）→ 同村里層規則：另存 tie_hex 疊斜線紋
        _order = sorted(range(len(rates)), key=lambda k: rates[k], reverse=True)
        tie_hex, tie_party = np.nan, ""
        if len(_order) > 1:
            a2, b2 = _order[0], _order[1]
            if (tot[a2] == tot[b2]) or (round(rates[a2], 3) == round(rates[b2], 3)) \
                    or (rates[a2] - rates[b2] <= TIE_RATE_EPS):
                c2 = nat.get_color_by_value(rates[b2], PARTY_STOPS[PARTIES[b2]])
                if c2 and c2.upper() != col.upper():
                    tie_hex, tie_party = c2, PARTIES[b2]
        gdf.at[i, "fill_hex"] = col
        gdf.at[i, "win_party"] = PARTIES[j]
        gdf.at[i, "tie_hex"] = tie_hex
        gdf.at[i, "tie_party"] = tie_party
        for k, rc in enumerate(rate_cols):
            gdf.at[i, rc] = rates[k]
        gdf.at[i, "match_type"] = "town"
        has_data.at[i] = True
        filled += 1

    _by = gdf.loc[gdf["match_type"] == "town", "COUNTYNAME"].value_counts().to_dict()
    print(f"  金馬澎空白島嶼填鄉鎮色：{filled} 塊 {_by}"
          f"（{('、'.join(sorted({gdf.at[i, 'TOWNNAME'] for i in gdf.index[gdf['match_type'] == 'town']})))}）")
    return gdf, has_data, filled


# ---------------------- ④ 版面：金門／連江 1:1 附圖 ----------------------
def _place_islet_in_corner(islet_gdf, box_bounds, box_pad=0.12, scale=1.0):
    """把小離島（烏坵鄉）放進父框（金門框）角落的小方框 —— 不依實際距離擺放。

    角落由 `EXTRA_ISLET_CORNER` 指定（預設左上，與參考圖一致）。
    烏坵距金門本島約 120 km，若按真實位置擺會把金門框撐成 137×91 km。
    scale 與父框用同一個 `ISLAND_SCALE`（否則同一面板上會有兩種比例尺）。
    """
    bx0, by0, bx1, by1 = box_bounds
    x0, y0, x1, y1 = islet_gdf.total_bounds
    iw, ih = (x1 - x0) * scale, (y1 - y0) * scale
    mx = EXTRA_ISLET_MARGIN * (bx1 - bx0)
    my = EXTRA_ISLET_MARGIN * (by1 - by0)
    if EXTRA_ISLET_CORNER == "右下":
        cx, cy = bx1 - mx - iw, by0 + my
    elif EXTRA_ISLET_CORNER == "右上":
        cx, cy = bx1 - mx - iw, by1 - my - ih
    elif EXTRA_ISLET_CORNER == "左下":
        cx, cy = bx0 + mx, by0 + my
    else:                                     # 左上（預設）
        cx, cy = bx0 + mx, by1 - my - ih
    g = islet_gdf.copy()
    if scale != 1.0:
        g.geometry = g.geometry.scale(xfact=scale, yfact=scale, origin=(x0, y0))
    g.geometry = g.geometry.translate(xoff=cx - x0, yoff=cy - y0)
    rect = (cx - box_pad * iw, cy - box_pad * ih,
            cx + (1.0 + box_pad) * iw, cy + (1.0 + box_pad) * ih)
    return g, rect


def _place_insets(isl, islets, scale, left_x, top_y):
    """在指定倍率下排出附圖框（測試圖同款嵌合佈局，2026-11-03 使用者指定）。

    連江框在上（位置由 `left_x`／`top_y` 指定）；金門框**嵌在連江框右下角**——
    金門框的右緣、底緣與連江框共邊（L 形嵌合，取代原本「上下堆疊＋右緣對齊」）。
    金門框內：金門內容貼**左下**、烏坵虛線框貼**右下**（框寬＝金門內容＋烏坵框
    ＋3×留白，兩者幾何上分離）。
    回傳 (parts, boxes, rects)：parts＝平移縮放後的 GeoDataFrame 片段、
    boxes＝(名稱, 矩形, 線寬)、rects＝各框外接多邊形（避讓自檢）。
    """
    items = {cn: isl[isl["COUNTYNAME"] == cn] for cn in INSET_ORDER}
    matsu, kinmen = items.get("連江縣"), items.get("金門縣")
    if matsu is None or not len(matsu):
        return [], [], []
    parts, boxes, rects = [], [], []

    # 連江框（在上）
    x0, y0, x1, y1 = matsu.total_bounds
    cw, ch = (x1 - x0) * scale, (y1 - y0) * scale
    xp, yp = INSET_BOX_PAD * cw, INSET_BOX_PAD * ch
    fx0, fy1 = left_x, top_y
    fx1, fy0 = left_x + cw + 2 * xp, top_y - ch - 2 * yp
    g = matsu.copy()
    # 縮放後左緣／下緣仍在 (x0, y0)、尺寸變成 cw×ch → 以「框內留白」定位
    g.geometry = matsu.geometry.scale(xfact=scale, yfact=scale, origin=(x0, y0)).translate(
        xoff=(fx0 + xp) - x0, yoff=(fy0 + yp) - y0)
    parts.append(g)
    boxes.append(("連江縣", (fx0, fy0, fx1, fy1), LINE_INSET_BOX_PX))
    rects.append(Polygon([(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]))

    # 金門框：嵌在連江框右下角，右緣、底緣與連江框共邊（測試圖同款）；
    # 框內左下放金門內容、右下放烏坵虛線框（與烏坵框之間、四周各留 KM_BOX_GAP_FRAC）
    if kinmen is not None and len(kinmen):
        x0, y0, x1, y1 = kinmen.total_bounds
        cw, ch = (x1 - x0) * scale, (y1 - y0) * scale
        g_gap = KM_BOX_GAP_FRAC * ch
        if islets is not None and len(islets):
            wx0, wy0, wx1, wy1 = islets.total_bounds
            uw_rect = (wx1 - wx0) * scale + 2 * g_gap
            uh_rect = (wy1 - wy0) * scale + 2 * g_gap
        else:
            uw_rect = uh_rect = 0.0
        jw = cw + uw_rect + 3 * g_gap
        jh = max(ch, uh_rect) + 2 * g_gap
        jx1, jy0 = fx1, fy0
        jx0, jy1 = jx1 - jw, jy0 + jh
        g = kinmen.copy()
        g.geometry = kinmen.geometry.scale(xfact=scale, yfact=scale, origin=(x0, y0)).translate(
            xoff=(jx0 + g_gap) - x0, yoff=(jy0 + g_gap) - y0)
        parts.append(g)
        boxes.append(("金門縣", (jx0, jy0, jx1, jy1), LINE_INSET_BOX_PX))
        rects.append(Polygon([(jx0, jy0), (jx1, jy0), (jx1, jy1), (jx0, jy1)]))
    return parts, boxes, rects


def layout_insets(gdf):
    """把連江、金門放大後平移到主圖左上角；金門框嵌在連江框右下角（測試圖同款）。

    使用者指定（2026-11-03）：附圖佈局改為版面測試圖同款 —— 連江框在上、
    **金門框嵌在連江框右下角（右緣、底緣與連江框共邊，L 形嵌合）**，
    取代原本「連江在上、金門在下、右緣對齊」的堆疊式；烏坵另立小框嵌在金門框右下角。

    **不得壓到其他縣市**：附圖框必須落在左上角的空白海域內，不可與本島／澎湖重疊。
    連江縣的圖斑含東引與 134 塊無名礁石，實際範圍達 60.4×49.1 km，1.6 倍時
    寬 96.6 km 會壓到臺灣西北海岸 → 這裡以 `INSET_CLEARANCE_M` 淨空逐級試倍率
    （`ISLAND_SCALE` 起、每 0.05 一階往下降到 `INSET_MIN_SCALE`），取「放得進空白海域
    的最大倍率」。故實際倍率可能小於 `ISLAND_SCALE`，執行訊息會印出採用的倍率。

    金門附圖另**剔除距金門主島群過遠的島嶼部件**（東碇島等，`KM_ISLET_FAR_KM`）：
    東碇距本島約 30 km，會把金門附圖外接矩形撐高到連江框的 84%、嵌入右下角時
    壓到南北竿；剔除後金門框僅佔連江框右側 62%、底部 35%，自檢壓到連江圖斑 0 塊
    （與版面測試圖同一規則；主圖其他縣市不受影響）。

    烏坵鄉（金門縣）距金門本島約 120 km，若跟著金門一起平移會把框撐爆，
    故以同倍率放進金門框的空餘角落（右下角），另加 2px 小外框。
    """
    is_inset = gdf["COUNTYNAME"].isin(EXCLUDE_INSET)
    main, isl = gdf[~is_inset].copy(), gdf[is_inset].copy()
    boxes = []
    if not len(isl):
        return gdf, boxes

    # 先挑出小金門（烏坵），不隨金門一起平移
    is_islet = pd.Series([(c, t) in EXTRA_ISLET_TOWNS
                          for c, t in zip(isl["COUNTYNAME"], isl["TOWNNAME"])],
                         index=isl.index)
    islets = isl[is_islet].copy()
    isl = isl[~is_islet].copy()

    # 金門附圖剔除遠島部件（東碇島等）——explode 到單一多邊形部件再按距離判斷，
    # 以免烈嶼鄉上岐村（大膽＋二膽＋東碇同一筆 MultiPolygon）整筆被誤刪
    _km = isl["COUNTYNAME"] == "金門縣"
    if int(_km.sum()):
        km = isl[_km].explode(index_parts=False).reset_index(drop=True)
        _c = km.geometry.centroid
        _med = (float(_c.x.median()), float(_c.y.median()))
        _d = ((km.geometry.centroid.x - _med[0]) ** 2
              + (km.geometry.centroid.y - _med[1]) ** 2).pow(0.5)
        _far = _d > KM_ISLET_FAR_KM
        if int(_far.sum()):
            _names = (km.loc[_far, "TOWNNAME"].astype(str) + "／"
                      + km.loc[_far, "VILLNAME"].astype(str)).value_counts().to_dict()
            print(f"  金門附圖剔除遠島部件 {int(_far.sum())} 塊"
                  f"（距主島群 > {KM_ISLET_FAR_KM / 1000:.0f} km，與版面測試圖同規則）：{_names}")
            isl = pd.concat([isl[~_km], km[~_far]], ignore_index=True)

    m_minx, m_miny, m_maxx, m_maxy = main.total_bounds
    m_w, m_h = m_maxx - m_minx, m_maxy - m_miny
    tgt_left = m_minx + INSET_MARGIN_FRAC * m_w
    tgt_top = m_maxy - INSET_MARGIN_FRAC * m_h

    # 避讓基準：其他縣市（本島＋澎湖）聯集，外加 250m 淨空
    keep_out = unary_union(main.geometry.tolist()).buffer(INSET_CLEARANCE_M)
    scale, parts, box_list, rect_list = ISLAND_SCALE, None, None, None
    s = ISLAND_SCALE
    while s >= INSET_MIN_SCALE - 1e-9:
        _parts, _boxes, _rects = _place_insets(isl, islets, s, tgt_left, tgt_top)
        hit = [b[0] for b, r in zip(_boxes, _rects) if r.intersects(keep_out)]
        if _parts and not hit:
            scale, parts, box_list, rect_list = s, _parts, _boxes, _rects
            break
        if _parts:
            print(f"    附圖倍率 {s:.2f}× 會壓到其他縣市（{('、'.join(hit))}），往下試…")
        s = round(s - 0.05, 4)
    if parts is None:                       # 已到最低倍率仍放不進 → 仍以最低倍率輸出
        scale = max(INSET_MIN_SCALE, 0.1)
        parts, box_list, rect_list = _place_insets(isl, islets, scale, tgt_left, tgt_top)
        print(f"    ⚠️ 附圖已降到 {scale:.2f}× 仍與其他縣市重疊，請檢查底圖範圍")
    boxes.extend(box_list)

    # 自檢：嵌合佈局下金門框不得壓到連江島礁（放大後）
    _kin_rect = next((r for (cn, _b, _l), r in zip(box_list, rect_list)
                      if cn == "金門縣"), None)
    _matsu_part = next((p for p, (cn, _b, _l) in zip(parts, box_list)
                        if cn == "連江縣"), None)
    if _kin_rect is not None and _matsu_part is not None:
        _n_hit = int(_matsu_part.geometry.intersects(_kin_rect).sum())
        print(f"  自檢：金門框（嵌連江框右下角）壓到連江圖斑 {_n_hit} 塊（應為 0）")

    report = []
    for cn, (bx0, by0, bx1, by1), _lw in box_list:
        sub = isl[isl["COUNTYNAME"] == cn]
        x0, y0, x1, y1 = sub.total_bounds
        report.append(f"{cn} {(x1 - x0) / 1000:.1f}×{(y1 - y0) / 1000:.1f}km"
                      f"（放大後 {(x1 - x0) * scale / 1000:.1f}×{(y1 - y0) * scale / 1000:.1f}km）")

    # 烏坵：嵌在金門框右下角的虛線小方框（框已在 `_place_insets` 中與金門內容
    # 幾何分離：金門框＝內容＋烏坵框＋留白；烏坵內容在框內置中，不依實際距離）
    jm_box = next((b[1] for b in box_list if b[0] == "金門縣"), None)
    if len(islets) and jm_box is not None:
        jx0, jy0, jx1, jy1 = jm_box
        kx0, ky0, kx1, ky1 = isl[isl["COUNTYNAME"] == "金門縣"].total_bounds
        g_gap = KM_BOX_GAP_FRAC * (ky1 - ky0) * scale
        wx0, wy0, wx1, wy1 = islets.total_bounds
        iw, ih = (wx1 - wx0) * scale, (wy1 - wy0) * scale
        ux1, uy0 = jx1 - g_gap, jy0 + g_gap
        ux0, uy1 = ux1 - iw - 2 * g_gap, uy0 + ih + 2 * g_gap
        moved = islets.geometry.scale(xfact=scale, yfact=scale, origin=(wx0, wy0)).translate(
            xoff=(ux0 + ux1) / 2.0 - (wx0 + wx1) / 2.0,   # 虛線框內水平置中
            yoff=(uy0 + uy1) / 2.0 - (wy0 + wy1) / 2.0)   # 虛線框內垂直置中
        parts.append(islets.assign(geometry=moved))
        boxes.append(("烏坵鄉", (ux0, uy0, ux1, uy1), EXTRA_ISLET_BOX_PX))
        report.append(f"烏坵 {iw / 1000:.1f}×{ih / 1000:.1f}km"
                      f"（嵌於金門框{EXTRA_ISLET_CORNER}）")
        # 自檢：烏坵虛線框不得壓到金門圖斑（放大後）
        _kin_part = next((p for p, (cn, _b, _l) in zip(parts, box_list)
                          if cn == "金門縣"), None)
        _urect = Polygon([(ux0, uy0), (ux1, uy0), (ux1, uy1), (ux0, uy1)])
        if _kin_part is not None:
            _n_hit = int(_kin_part.geometry.intersects(_urect).sum())
            print(f"  自檢：烏坵虛線框壓到金門圖斑 {_n_hit} 塊（應為 0）")
    elif len(islets):                        # 無金門框時仍給它一個獨立小框
        x0, y0, x1, y1 = islets.total_bounds
        iw, ih = (x1 - x0) * scale, (y1 - y0) * scale
        xp, yp = INSET_BOX_PAD * iw, INSET_BOX_PAD * ih
        moved = islets.geometry.scale(xfact=scale, yfact=scale,
                                      origin=(x0, y0)).translate(
            xoff=(tgt_left + xp) - x0, yoff=(tgt_top - yp - ih) - y0)
        parts.append(islets.assign(geometry=moved))
        boxes.append(("烏坵鄉", (tgt_left, tgt_top - ih - 2 * yp,
                               tgt_left + iw + 2 * xp, tgt_top),
                      EXTRA_ISLET_BOX_PX))
        report.append(f"烏坵 {iw / 1000:.1f}×{ih / 1000:.1f}km（另立小框）")

    print(f"  附圖（倍率 {scale:.2f}×、連江框在上、金門框嵌連江框右下角共邊、"
          f"烏坵嵌金門框{EXTRA_ISLET_CORNER}）：{'、'.join(report)}")
    out = gpd.GeoDataFrame(pd.concat([main] + parts, ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    return out, boxes


def layout_stack_all(gdf, counties=TEST_COUNTIES, islets=EXTRA_ISLET_TOWNS):
    """測試模式版面：把指定縣市全部當附圖、由上而下 1:1 堆疊（左緣對齊、各加外框）。

    正式版的 `layout_insets` 以「主圖」為基準把金馬放到左上角；測試模式只留離島，
    沒有臺灣本島可當主圖，若照原邏輯擺位會與澎湖圖斑重疊，故改用純堆疊版面。
    烏坵鄉（距金門約 120 km）比照正式版：**嵌在金門框右下方的小方框**，
    否則金門框會被它撐成 137×91 km。
    """
    islet_mask = pd.Series([(c, t) in islets for c, t in
                            zip(gdf["COUNTYNAME"], gdf["TOWNNAME"])], index=gdf.index)
    rows = [(cn, gdf[(gdf["COUNTYNAME"] == cn) & ~islet_mask]) for cn in counties]
    rows = [(cn, s) for cn, s in rows if len(s)]
    if not rows:
        return gdf, []
    parts, boxes, top, report = [], [], 0.0, []
    placed = {}
    for cn, sub in rows:
        x0, y0, x1, y1 = sub.total_bounds
        cw, ch = (x1 - x0) * ISLAND_SCALE, (y1 - y0) * ISLAND_SCALE
        xp, yp = INSET_BOX_PAD * cw, INSET_BOX_PAD * ch
        g = sub.copy()
        g.geometry = g.geometry.scale(xfact=ISLAND_SCALE, yfact=ISLAND_SCALE,
                                      origin=(x0, y0)).translate(
            xoff=xp - x0, yoff=(top - yp - ch) - y0)
        parts.append(g)
        rect = (0.0, top - ch - 2 * yp, cw + 2 * xp, top)     # 貼著內容的框
        boxes.append((cn, rect, LINE_INSET_BOX_PX))
        placed[cn] = (xp, top - yp - ch, xp + cw, top - yp)   # 內容實際佔位
        report.append(f"{cn} {cw / 1000:.1f}×{ch / 1000:.1f}km")
        top -= ch + 2 * yp

    for ic, it in islets:
        s = gdf[islet_mask & (gdf["COUNTYNAME"] == ic) & (gdf["TOWNNAME"] == it)]
        if not len(s) or ic not in placed:
            continue
        iw = (s.total_bounds[2] - s.total_bounds[0]) * ISLAND_SCALE
        ih = (s.total_bounds[3] - s.total_bounds[1]) * ISLAND_SCALE
        g_islet, rect = _place_islet_in_corner(s, placed[ic], scale=ISLAND_SCALE)
        parts.append(g_islet)
        boxes.append((f"{ic}{it}", rect, EXTRA_ISLET_BOX_PX))
        report.append(f"{it} {iw / 1000:.1f}×{ih / 1000:.1f}km（嵌於{ic}框{EXTRA_ISLET_CORNER}）")

    print(f"  測試版面（放大 {ISLAND_SCALE}×、由上而下堆疊）：{'、'.join(report)}")
    out = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True),
                           geometry="geometry", crs=gdf.crs)
    return out, boxes


# ---------------------- ⑤ 線稿 ----------------------
def _despike_ring(coords, tol=5.0, area_thr=5000.0, min_path=100.0):
    """折疊單一線環中的「迴針／零寬裂縫」退化子路徑（同 Draw_North4）。"""
    P = np.asarray(coords, dtype=float)
    n = len(P)
    if n < 5:
        return P
    dead = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        if dead[i]:
            i += 1
            continue
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        d[:i + 2] = np.inf
        if i == 0:
            d[n - 1] = np.inf
        j = int(np.argmin(d))
        if d[j] <= tol:
            seg = P[i:j + 1]
            path_len = float(np.hypot(np.diff(seg[:, 0]), np.diff(seg[:, 1])).sum())
            _x, _y = seg[:, 0], seg[:, 1]
            area = 0.5 * abs(np.dot(_x[:-1], _y[1:]) - np.dot(_x[1:], _y[:-1]))
            if path_len > min_path and area < area_thr:
                dead[i + 1:j] = True
        i += 1
    return P[~dead]


def remove_ring_slits(gdf, tol=5.0, area_thr=5000.0, min_path=100.0):
    """移除 dissolve 後區／縣市層外環與內環的退化迴針（避免憑空冒出的死線）。"""
    n_ring = n_vert = 0

    def _fix(geom):
        nonlocal n_ring, n_vert
        if geom is None or geom.is_empty:
            return geom
        out = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            ext = _despike_ring(poly.exterior.coords, tol, area_thr, min_path)
            if len(ext) != len(poly.exterior.coords):
                n_ring += 1
                n_vert += len(poly.exterior.coords) - len(ext)
            holes = []
            for r in poly.interiors:
                h = _despike_ring(r.coords, tol, area_thr, min_path)
                if len(h) != len(r.coords):
                    n_ring += 1
                    n_vert += len(r.coords) - len(h)
                if len(h) >= 4:
                    holes.append(h)
            out.append(Polygon(ext, holes).buffer(0))
        if not out:
            return geom
        return out[0] if len(out) == 1 else MultiPolygon(out)

    o = gdf.copy()
    o["geometry"] = o.geometry.apply(_fix)
    o = o[~o.geometry.isna() & ~o.geometry.is_empty].copy().reset_index(drop=True)
    if n_ring:
        print(f"  迴針清理：修正 {n_ring} 個線環、折疊 {n_vert} 個頂點")
    return o


def clean_tiny_holes(gdf, min_area=HOLE_MIN_AREA_M2):
    """移除面積 < min_area 的內環（dissolve 浮點誤差造成的微孔）與過小碎片。"""
    def _fix(geom):
        if geom is None or geom.is_empty:
            return geom
        kept = []
        for poly in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            if poly.geom_type != "Polygon" or poly.area < min_area:
                continue
            holes = [r for r in poly.interiors if Polygon(r).area >= min_area]
            kept.append(Polygon(poly.exterior, holes))
        if not kept:
            return geom
        return kept[0] if len(kept) == 1 else MultiPolygon(kept)

    out = gdf.copy()
    out["geometry"] = out.geometry.apply(_fix)
    return out


def to_px(coords, minx, maxy, sx, sy):
    """像素網格約定：像素 i 中心 = minx+(i+0.5)/sx（floor，與 matplotlib 渲染網格一致）"""
    return [(int(math.floor((x - minx) * sx)), int(math.floor((maxy - y) * sy)))
            for x, y in coords]


def extract_lines(gs):
    """把（Multi）LineString／GeometryCollection 攤平成座標序列清單。"""
    parts = list(gs.geoms) if hasattr(gs, "geoms") else [gs]
    out = []
    for g in parts:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(list(g.coords))
        elif g.geom_type == "MultiLineString":
            out.extend(list(ls.coords) for ls in g.geoms)
        elif g.geom_type == "GeometryCollection":
            out.extend(extract_lines(g))
    return out


def draw_layer(lines, width, w_px, h_px, minx, maxy, sx, sy):
    """Bresenham 逐段描繪 width 像素寬的純黑白線，返回 bool 陣列。"""
    im = Image.new("L", (w_px, h_px), 255)
    d = ImageDraw.Draw(im)
    for coords in lines:
        pts = to_px(coords, minx, maxy, sx, sy)
        if len(pts) >= 2:
            d.line(pts, fill=0, width=width)
    arr = np.asarray(im) < 128
    del im
    return arr


def render_village_layer(villages, w_px, h_px, minx, maxy, sx, sy):
    """① 村里界 1px：1px 直繪 → thin 取中心線（分區腳本同一作法）。"""
    lines = extract_lines(unary_union(villages.geometry.boundary.tolist()))
    village_arr = draw_layer(lines, LINE_VILLAGE_PX, w_px, h_px, minx, maxy, sx, sy)
    skel = thin(village_arr)
    del village_arr
    return skel


def render_thin_coast_layer(counties, w_px, h_px, minx, maxy, sx, sy):
    """澎湖／金門／連江的海岸線：**與村里界同一個畫法**（1px 直繪 → thin 取中心線）。

    鄉鎮市區版沒有村里界層，故另建這一層；村里版的村里界層本身就含海岸線
    （最外圈村里的多邊形邊界就是海岸線），不需重複繪製。
    """
    sub = counties[counties["OLD_COUNTY"].isin(THIN_COUNTIES)]
    if not len(sub):
        return None
    lines = extract_lines(unary_union(sub.geometry.tolist()).boundary)
    arr = draw_layer(lines, LINE_VILLAGE_PX, w_px, h_px, minx, maxy, sx, sy)
    skel = thin(arr)
    del arr
    return skel


def compute_county_boundary(counties):
    """本島（非澎湖金馬）的「海岸線」與「縣市界內陸段」幾何（正式圖與測試圖共用）。

    海岸線＝本島縣市聯集的外輪廓（1px 金馬畫法負責）；
    縣市界＝各縣市邊界「扣掉海岸線緩衝」後的內陸段（6px matplotlib 負責）。
      用全域聯集一次算完（不做 231 對兩兩求交），並以 6m 緩衝吸收
      `resolve_cross_county_overlaps` 清理後的亞米級落差，避免出現斷線。
    **2026-11-03 加嚴：縣市界必須均勻連續、不留碎段**——
      舊版「>30m 才畫」的長度過濾會把 unary_union 節點化產生的 4.6 萬個
      ≤30m 小段整批丟掉（實測佔邊界總長 29%）→ 縣市界呈虛線狀碎段。
      這些小段全部落在真實縣市界上（difference 後每個點距海岸 ≥6m），
      故改為**全數保留**，再以 `linemerge` 把端點相接的段接合成最長線：
      畫出的 6px 線均勻連續，不丟任何真實邊界。
    **2026-11-03 二次修正（缺口的真正根因）**：海岸線只取聯集各部件的
      **外環**（`polygon.exterior`），絕不能把整個 `.boundary` 當海岸線 ——
      本島 20 縣市的聯集內部有 **7251 個內環**（村里圖資跨縣市的細縫，
      總長 1403 km），舊版把內環也當海岸線 → `difference(coast.buffer(6m))`
      把沿細縫的縣市界**整段誤刪**（3524 km 被刪到只剩 2035 km，宜蘭／雲林／
      屏東／臺北等地縣界大量缺段）。改用外環後（真海岸線 1792 km），
      縣市界全長 3524 km 一段不缺；細縫兩側的縣界各自成像，
      6px 線在細縫（遠窄於 6px）兩側自然疊合成一條連續粗線。
    回傳 (thick_cty, coast, segs)；segs 為接合後的 LineString 清單。
    """
    thick_cty = counties[~counties["OLD_COUNTY"].isin(THIN_COUNTIES)]
    if not len(thick_cty):          # --test 離島模式：本島縣市不存在
        return thick_cty, None, []
    union = unary_union(thick_cty.geometry.tolist())
    parts = list(union.geoms) if hasattr(union, "geoms") else [union]
    coast = unary_union([p.exterior for p in parts])   # 只取外環＝真海岸線
    allb = unary_union([unary_union(sub.geometry).buffer(0).boundary
                        for _c, sub in thick_cty.groupby("OLD_COUNTY")])
    rem = allb.difference(coast.buffer(6.0))
    pieces = [g for g in (rem.geoms if hasattr(rem, "geoms") else [rem])
              if g.geom_type == "LineString" and g.length > 0.0]
    if not pieces:
        return thick_cty, coast, []
    merged = linemerge(pieces)
    if merged.is_empty:
        segs = []
    elif merged.geom_type == "LineString":
        segs = [merged]
    else:
        segs = [g for g in merged.geoms if g.geom_type == "LineString"]
    return thick_cty, coast, segs


def audit_county_segments(counties, segs):
    """縣市界自檢：每段以中點找出兩側縣市，核對縣市界段「不多選、不少選」。

    判定：與段中點距離 < 30 m 的縣市應「恰好 2 個」（該段兩側）。
      跨縣市圖資細縫（>60m）兩側的段，對側縣市在 30m 外 → 放寬至 150m
      仍恰好 2 縣者視為正常（縫隙兩側各有一段，畫出後疊合）。
      - 只命中 1 個（150m 內也沒有第 2 縣）→ 海岸殘段或孤立碎線
      - 命中 ≥3 個 → 中點太靠近三縣市交會點（或冗餘重疊段）
    列印「縣市對 → 段數、總長」一覽表，可與 2008 年行政區逐一核對；
    異常段逐條列 ⚠️。回傳異常段數。
    """
    thick_cty = counties[~counties["OLD_COUNTY"].isin(THIN_COUNTIES)]
    if not segs or not len(thick_cty):
        print("    縣市界稽核：無本島縣市（離島測試模式），略過")
        return 0
    geoms = list(zip(thick_cty["OLD_COUNTY"],
                     [g.buffer(0) if not g.is_valid else g for g in thick_cty.geometry]))
    pairs, problems = {}, []
    for g in segs:
        for ls in (g.geoms if hasattr(g, "geoms") else [g]):
            mid = ls.interpolate(0.5, normalized=True)
            near = sorted(c for c, cg in geoms if cg.distance(mid) < 30.0)
            if len(near) == 1:
                # 寬縫隙兩側段：跨縣市圖資細縫（>60m）使對側縣市在 30m 外。
                # 150m 內恰好 2 縣 → 仍屬正常縣市界（縫隙另一側有對應段）。
                wide = sorted(c for c, cg in geoms if cg.distance(mid) < 150.0)
                if len(wide) == 2:
                    near = wide
            key = tuple(near)
            if key not in pairs:
                pairs[key] = [0, 0.0]
            pairs[key][0] += 1
            pairs[key][1] += ls.length / 1000.0     # 統一累加 km（length 單位＝米）
            if len(near) != 2:
                problems.append((near, ls.length / 1000.0,
                                 (round(mid.x), round(mid.y))))
    tot_km = sum(v[1] for v in pairs.values())
    ok_pairs = {k: v for k, v in pairs.items() if len(k) == 2}
    print(f"    縣市界稽核：共 {len(segs)} 段、{tot_km:.0f} km、"
          f"相鄰縣市對 {len(ok_pairs)} 組")
    for k in sorted(ok_pairs):
        n, ln = ok_pairs[k]
        print(f"      {k[0]}–{k[1]}：{n} 段 {ln:.1f} km")
    if problems:
        print(f"    ⚠️ 兩側縣市不是恰好 2 個的段（{len(problems)} 條，請人工核對）：")
        for near, ln, xy in problems[:20]:
            print(f"      {'/'.join(near) if near else '（無）'}：{ln:.2f} km @ {xy}")
    return len(problems)


def render_main_coast_layer(coast, w_px, h_px, minx, maxy, sx, sy):
    """本島海岸線 1px：**與金馬完全同一畫法**（1px 直繪 → thin 取中心線）。

    舊版在 ② 層以 matplotlib 3px 描本島海岸線 → 2026-11-03 使用者指定改為
    參考金馬的 1px 設計，全圖所有海岸線統一 1px。
    """
    if coast is None:               # --test 離島模式：本島海岸線不存在
        return np.zeros((h_px, w_px), dtype=bool)
    arr = draw_layer(extract_lines(coast), LINE_COAST_PX, w_px, h_px, minx, maxy, sx, sy)
    skel = thin(arr)
    del arr
    return skel


def render_county_segments_mask(segs, crs, w_px, h_px, minx, maxx, miny, maxy):
    """只把縣市界段（6px）畫成遮罩：matplotlib 繪線 → 閾值二值化（同 ② 層畫法）。"""
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    if segs:
        gpd.GeoSeries(list(segs), crs=crs).plot(
            ax=ax, edgecolor="black", facecolor="none",
            linewidth=LINE_COUNTY_INNER_PX * PX2PT, antialiased=False)
    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None,
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, mask = cv2.threshold(gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
    del gray
    return mask > 0


    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, mask = cv2.threshold(gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
    del gray
    return mask > 0


def render_inset_box_mask(boxes, w_px, h_px, minx, maxx, miny, maxy):
    """只把附圖外框（金門／連江／烏坵框）畫成獨立遮罩：與 ② 層同一 matplotlib
    畫法（同 DPI／線寬／閾值），保證與 lines_mask 中的外框像素完全對齊。

    用途：主流程填色後先 `arr[lines_mask] = LINE_RGB`（全部界線近白），
    再 `arr[box_mask] = 0` 把外框像素改回**純黑**（2026-11-03 使用者指定：
    金門／馬祖附圖方框改黑線，與其他界線區隔）。
    """
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor("white")
    px2pt = 72.0 / DPI
    for _cn, (bx0, by0, bx1, by1), lw in boxes:
        ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False,
                               edgecolor="black", linewidth=lw * px2pt, zorder=5))
    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None,
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, mask = cv2.threshold(gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
    del gray
    return mask > 0


def render_boundary_layer(towns, counties, segs, boxes, w_px, h_px, minx, maxx, miny, maxy):
    """② 區界＋縣市界＋附圖外框：matplotlib 繪線 → 閾值二值化。

    區界 2px；縣市界（兩縣市共有段的內陸交界）6px。
    **海岸線不在本層**：2026-11-03 使用者指定參考金馬的 1px 設計，
    本島海岸線改由 render_main_coast_layer 以「1px 直繪 → thin 中心線」繪製。
    **澎湖／金門／連江（小面積離島縣市）不在本層描邊**：其海岸線與無名礁石
    一律由 ① 層以「1px 直繪 → thin 取中心線」繪製（與村里界同一畫法）。
    本層對這些縣市只畫「內部鄉鎮界」（相鄰鄉鎮之間的段），絕不碰外緣 ——
    舊版在 `towns.plot()` 時對每個鄉鎮面都描了 2px 邊，等於把 1px 海岸線
    整個覆蓋成 2px（使用者反映的「離島海岸線太粗」即此）。
    """
    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_facecolor(NO_DATA_COLOR)
    px2pt = 72.0 / DPI
    town_lw = LINE_TOWNSHIP_PX * px2pt
    cty_inner_lw = LINE_COUNTY_INNER_PX * px2pt     # 縣市界 6px

    # 區層先鋪底（只填白、**不描邊**），村里線之後再疊（兩層同一像素網格）
    towns.plot(ax=ax, edgecolor="none", facecolor="white", linewidth=0.0,
               antialiased=False, zorder=1)
    thick_town = towns[~towns["OLD_COUNTY"].isin(THIN_COUNTIES)]
    thick_town.boundary.plot(ax=ax, edgecolor="black", facecolor="none",
                             linewidth=town_lw, antialiased=False, zorder=2)
    inner = []
    for cn in THIN_COUNTIES:
        csub = counties[counties["OLD_COUNTY"] == cn]
        tsub = towns[towns["OLD_COUNTY"] == cn]
        if not len(csub) or not len(tsub):
            continue
        cb = unary_union(csub.geometry.tolist()).boundary
        for tg in tsub.geometry:
            seg = tg.boundary.difference(cb)
            if not seg.is_empty and getattr(seg, "length", 0) > 0:
                inner.append(seg)
    if inner:
        gpd.GeoSeries(inner, crs=towns.crs).plot(
            ax=ax, edgecolor="black", facecolor="none",
            linewidth=town_lw, antialiased=False, zorder=2)
    # 縣市界：只畫內陸交界段（6px）；海岸線不在本層（改由金馬同款 1px 畫法負責）
    #   縣市界＝各縣市邊界「扣掉海岸線緩衝」後的內陸段，由 compute_county_boundary
    #   在 main 流程一次算好（全域聯集，6m 緩衝吸收亞米級落差，避免斷線）
    if segs:      # 一次繪多段（逐段 plot 會在 1 億像素畫布上反覆重建集合，慢數十倍）
        gpd.GeoSeries(list(segs), crs=towns.crs).plot(
            ax=ax, edgecolor="black", facecolor="none",
            linewidth=cty_inner_lw, antialiased=False, zorder=4)
    print(f"    縣市界 {LINE_COUNTY_INNER_PX}px：{len(segs)} 段內陸交界"
          f"（{sum(g.length for g in segs) / 1000:.0f} km）；"
          f"海岸線改由 {LINE_COAST_PX}px 金馬同款畫法負責（不在本層）")
    # 附圖外框
    for _cn, (bx0, by0, bx1, by1), lw in boxes:
        ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False,
                               edgecolor="black", linewidth=lw * px2pt, zorder=5))
    ax.axis("off")

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None,
                facecolor=NO_DATA_COLOR)
    plt.close(fig)
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    del img
    _, mask = cv2.threshold(gray, THRESHOLD_VAL, 255, cv2.THRESH_BINARY_INV)
    del gray
    return mask > 0


# ---------------------- ⑥ 稽核報告 ----------------------
def write_missing_report(gdf, vote_display, stats, md_path=MISSING_MD):
    mt = gdf["match_type"].astype(str)
    _none_all = gdf[mt == "none"]
    # 無村里名的礁石（金馬澎）不算「村里」，另計；其餘才是真正的無資料村里
    _rock = _none_all[_none_all["VILLNAME"].astype(str).str.strip().eq("")]
    none_df = _none_all[~_none_all["VILLNAME"].astype(str).str.strip().eq("")] \
        .sort_values(["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    wild_df = gdf[mt.str.startswith(("wildcard", "elimination"), na=False)].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    fuzzy_df = gdf[mt.str.startswith("fuzzy", na=False)].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    used = {(norm_county(r["COUNTYNAME"]), norm_town(r["TOWNNAME"]), r["matched_vill"])
            for _, r in gdf[mt != "none"].iterrows() if r["matched_vill"]}
    orphan = sorted(k for k in vote_display if k not in used)

    L = ["# 全臺灣 2008 立法委員不分區（政黨票）得票率地圖 — 匹配稽核", ""]
    L += [f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
          "- 底圖：`twvillage2012.json`（民國101年村里界）＋ **嘉義市改用 "
          "`twVillage_pre2010.geo.json`**（民國99年前村里界 108 里）"
          f" → 本圖 {len(gdf)} 個村里圖斑",
          f"- 得票資料：`Data/2008不分区`（中選會原始 xls，12 個政黨）→ "
          f"{len(vote_display)} 個村里（多村里併列者已拆開）",
          f"- 匹配結果：精確 **{stats['exact']}**、沿革合併 **{stats['merged']}**、"
          f"跨里合併 **{stats['mergevote']}**、萬用字元 **{stats['wildcard']}**、"
          f"消去法 **{stats['elimination']}**、模糊 **{stats['fuzzy']}**、"
          f"無資料 **{stats['none']}**（圖上留白）", ""]

    L += [f"## 1. 地圖上有村里圖斑、但對不上得票資料（{len(none_df)} 筆 → 留白）", ""]
    if len(_rock):
        L += [f"> 另有 **{len(_rock)}** 個「無村里名」礁石圖斑（金門、連江、澎湖等）"
              f"本就無村里編制、無得票資料，圖上留白並以 1px 描邊，不計入下表。", ""]
    if len(none_df):
        L += ["| # | 縣市（2008） | 鄉鎮市區 | 村里 |", "|---:|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} |"
              for i, (_, r) in enumerate(none_df.iterrows(), 1)]
        L += ["", "### 依縣市統計", "", "| 縣市（2008） | 無資料村里數 |", "|---|---:|"]
        L += [f"| {c} | {int(n)} |" for c, n in none_df.groupby("OLD_COUNTY").size().items()]
    else:
        L.append("（無）")
    L.append("")

    L += [f"## 2. 村里沿革合併（北北基宜＋桃竹苗，{stats['merged']} 筆）", ""]
    L += ["> 2012 圖資中存在、但 2008 年尚未設立的里 → 併入 2008 年時的母里",
          "> （同底色，且其間不畫村里界線）。規則見 `village_lineage_north4`。", ""]
    merged_df = gdf[gdf["merged_into"].astype(str) != ""].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "merged_into", "VILLNAME"])
    if len(merged_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 子里（2012 圖資） | 併入 2008 母里 |",
              "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['merged_into']} |"
              for i, (_, r) in enumerate(merged_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    L += [f"## 3. 跨里合併（多個 2008 里 → 一 2012 里，得票數加總重算；"
          f"{stats['mergevote']} 筆）", ""]
    vote_df = gdf[gdf["match_type"].astype(str).str.startswith("mergevote")]
    if len(vote_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 2012 里 | 承接的 2008 里 |", "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill']} |"
              for i, (_, r) in enumerate(vote_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    L += [f"## 4. 萬用字元／消去法匹配（來源資料 U+FFFD 或底圖 ■/PUA；{len(wild_df)} 筆）", ""]
    if len(wild_df):
        L += ["| # | 縣市（2008） | 鄉鎮市區 | 底圖村里 | 對應得票資料 |",
              "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill']} |"
              for i, (_, r) in enumerate(wild_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    L += [f"## 5. 異體字模糊匹配（{len(fuzzy_df)} 筆）", ""]
    if len(fuzzy_df):
        L += ["| # | 縣市（2008） | 鄉鎮市區 | 底圖村里 | 對應得票資料 | 匹配方式 |",
              "|---:|---|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill']} | {r['match_type']} |"
              for i, (_, r) in enumerate(fuzzy_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    repair_df = gdf[gdf["NAME_REPAIR"].astype(str).str.len() > 0].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"]) if "NAME_REPAIR" in gdf.columns else gdf.iloc[:0]

    L += [f"## 6. 底圖村名修補（twvillage2012.json 罕見字還原；{len(repair_df)} 筆）", ""]
    L += ["> JSON 以私用區(PUA)碼位或「■」代替罕見字，先還原成正字再與 2008 資料比對。",
          "> 規則見 `village_name_repair.repair_json_vill_name`。", ""]
    if len(repair_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 圖資原名 | 修補後 |", "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | "
              f"{r['VILLNAME_RAW']} | {r['VILLNAME']} |"
              for i, (_, r) in enumerate(repair_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    L += [f"## 7. 得票資料有、底圖卻無對應村里圖斑（{len(orphan)} 筆）", ""]
    L += ["> 多為村里改名／重編（2008 資料與 2012 圖資不同步），"
          "其得票已由同鄉鎮其他村里承接，或該里已不存在。", ""]
    if orphan:
        L += ["| # | 縣市 | 鄉鎮市區 | 村里（得票資料） |", "|---:|---|---|---|"]
        L += [f"| {i} | {vote_display[k][0]} | {vote_display[k][1]} | {vote_display[k][2]} |"
              for i, k in enumerate(orphan, 1)]
    else:
        L.append("（無）")
    L.append("")

    L += ["## 8. 各縣市比對統計（2008 行政區）", "",
          "| 縣市 | 村里圖斑 | 精確 | 沿革合併 | 萬用字元/消去 | 模糊 | 無資料 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for c, sub in gdf.groupby("OLD_COUNTY"):
        smt = sub["match_type"].astype(str)
        L.append(f"| {c} | {len(sub)} | {int((smt == 'exact').sum())} | "
                 f"{int(smt.str.startswith('merge').sum())} | "
                 f"{int(smt.str.startswith(('wildcard', 'elimination')).sum())} | "
                 f"{int(smt.str.startswith('fuzzy').sum())} | "
                 f"{int((smt == 'none').sum())} |")
    L.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  ③ 匹配稽核報告：{md_path}")


def save_png(img, path, retries=3):
    """輸出 PNG（檔案被預覽器占用時重試）。"""
    for i in range(retries):
        try:
            img.save(path)
            return
        except OSError as e:
            if i == retries - 1:
                raise
            print(f"  ⚠️ 存檔失敗（{e}），{i + 1}s 後重試…")
            time.sleep(1.0)


def check_reef_drawn(gdf_plot, lines_mask, w_px, h_px, minx, maxy, sx, sy, pad=2):
    """自檢：金門／連江的「無村里名礁石」是否真的被畫出來。

    對每一塊礁石取其外接矩形（像素座標外擴 pad），統計該框內的線稿像素；
    0 表示這塊礁石整塊漏畫（底圖有、圖上沒有），必須為 0。
    """
    sub = gdf_plot[gdf_plot["VILLNAME"].astype(str).str.strip().eq("")
                   & gdf_plot["COUNTYNAME"].isin(KINMEN_MATSU)]
    n_part = n_miss = 0
    miss = []
    for c, t, geom in zip(sub["COUNTYNAME"], sub["TOWNNAME"], sub.geometry):
        for p in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            if p.is_empty:
                continue
            n_part += 1
            x0, y0, x1, y1 = p.bounds
            c0 = max(int(math.floor((x0 - minx) * sx)) - pad, 0)
            c1 = min(int(math.ceil((x1 - minx) * sx)) + pad, w_px)
            r0 = max(int(math.floor((maxy - y1) * sy)) - pad, 0)
            r1 = min(int(math.ceil((maxy - y0) * sy)) + pad, h_px)
            n = int(lines_mask[r0:r1, c0:c1].sum()) if (r1 > r0 and c1 > c0) else 0
            if n == 0:
                n_miss += 1
                miss.append((c, t, round(p.area / 1e4, 4)))
    print(f"  礁石自檢（金門／連江無村里名礁石）：{n_part} 塊，"
          f"完全未畫出 {n_miss} 塊（應為 0）")
    if miss:
        print(f"    ⚠️ 未畫出：{miss[:8]}{' …' if len(miss) > 8 else ''}")
    return n_miss


# ---------------------- 邊界測試模式（--boundaries） ----------------------
def _boundary_test(argv):
    """命令列含 --boundaries／--boundary-test／-b → 只輸出縣市界＋海岸線測試圖。"""
    return any(str(a).lower() in ("--boundaries", "--boundary-test", "-b")
               for a in argv[1:])


def run_boundary_test():
    """輸出「縣市界 6px ＋ 海岸線 1px」單獨測試圖（不畫村里、不填色）。

    目的：核對縣市界段「不多選、不少選」——
      ① 每段以中點判定兩側縣市，列印「縣市對 → 段數、總長」稽核表
        （應恰好 2 個縣市；不足或超過者列 ⚠️）；
      ② 純界線圖可逐段目視：6px 縣市界只出現在陸地交界，1px 海岸線不應有粗細不一。
    """
    t0 = time.time()
    print("=" * 66)
    print("  縣市界／海岸線 測試圖（僅界線：縣市界 6px、海岸線 1px，無村里無填色）")
    print("=" * 66)
    gdf = load_base_map()
    gdf = add_old_county(gdf)
    gdf = resolve_cross_county_overlaps(gdf)
    gdf = strip_far_parts(gdf)
    counties = gdf.dissolve(by=["OLD_COUNTY"]).reset_index()
    counties = remove_ring_slits(counties)
    counties = clean_tiny_holes(counties)
    print(f"  縣市（2008）：{len(counties)}")
    _thick_cty, coast, segs = compute_county_boundary(counties)
    n_bad = audit_county_segments(counties, segs)

    # 離島三縣市（澎湖／金門／連江）的外緣也是海岸線：1px 同款畫法
    thin_sub = counties[counties["OLD_COUNTY"].isin(THIN_COUNTIES)]
    thin_lines = (extract_lines(unary_union(thin_sub.geometry.tolist()).boundary)
                  if len(thin_sub) else [])

    minx, miny, maxx, maxy = counties.total_bounds
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w, geo_h = maxx - minx, maxy - miny
    scale = max(geo_w / MAX_W_PX, geo_h / MAX_H_PX, METERS_PER_PIXEL)
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  圖片尺寸：{w_px} × {h_px} px；1 像素 = {geo_w / w_px:.3f} 米")

    print(f"  海岸線 {LINE_COAST_PX}px（1px 直繪 → thin；含本島與澎湖金馬）…")
    mask = render_main_coast_layer(coast, w_px, h_px, minx, maxy, sx, sy)
    if thin_lines:
        mask |= render_main_coast_layer(
            _lines_to_geometry(thin_lines), w_px, h_px, minx, maxy, sx, sy)
    print(f"  縣市界 {LINE_COUNTY_INNER_PX}px（matplotlib → 閾值二值化，同正式圖）…")
    mask |= render_county_segments_mask(segs, counties.crs,
                                        w_px, h_px, minx, maxx, miny, maxy)
    print(f"  界線像素：{int(mask.sum())}")

    out = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
    out[mask] = (0, 0, 0)
    del mask
    save_png(Image.fromarray(out, mode="RGB"), BOUNDARY_TEST_OUT)
    del out
    print(f"\n  Saved: {BOUNDARY_TEST_OUT}  ({w_px}×{h_px}px)")
    print(f"  異常段（兩側縣市 ≠ 2）：{n_bad} 條（應為 0）")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== Boundary test finished ====")


def _lines_to_geometry(lines):
    """座標序列清單 → shapely MultiLineString（供 render_main_coast_layer 使用）。"""
    return MultiLineString([list(c) for c in lines if len(c) >= 2])


# ---------------------- 龜山島補漏測試模式（--gueishan） ----------------------
def _gueishan_test(argv):
    """命令列含 --gueishan → 只輸出「龜山島補漏測試圖」，驗證後再跑全圖。"""
    return any(str(a).lower() in ("--gueishan", "-g") for a in argv[1:])


def run_gueishan_test():
    """龜山島補漏測試圖：畫宜蘭縣一帶（含龜山島），核對島嶼已補在正確相對位置。

    輸出 GUEISHAN_TEST_OUT；同時列印幾何自檢（面積／距宜蘭本體距離／相對方位／
    與鄰縣最短距離），供與 106 年圖資核對。
    """
    from shapely.geometry import box as _box
    print("  讀取底圖（含龜山島補漏）…")
    gdf = load_base_map()
    cn, tn, vn = GUEISHAN_KEY
    isl_rows = gdf[(gdf["COUNTYNAME"] == cn) & (gdf["TOWNNAME"] == tn)
                   & (gdf["VILLNAME"] == vn)]
    yilan = gdf[gdf["COUNTYNAME"] == cn]
    # 宜蘭本體＝縣內最大連通塊（補漏後的龜山島也在 gdf 裡，不能直接用全縣聯集）
    _yilan_u = unary_union(yilan.geometry.tolist())
    _comps = list(_yilan_u.geoms) if _yilan_u.geom_type == "MultiPolygon" else [_yilan_u]
    mainland = max(_comps, key=lambda z: z.area)
    islets, d_near = [], None
    for gg in isl_rows.geometry:
        for pp in (list(gg.geoms) if gg.geom_type == "MultiPolygon" else [gg]):
            if mainland.distance(pp) > GUEISHAN_MIN_OFFSHORE_M:
                islets.append(pp)
                d = mainland.distance(pp) / 1000.0
                d_near = d if d_near is None else min(d_near, d)
    if not islets:
        raise RuntimeError("測試失敗：底圖補漏後仍無龜山島離岸圖斑")
    isl_union = unary_union(islets)
    cx, cy = isl_union.centroid.x, isl_union.centroid.y
    dx, dy = cx - mainland.centroid.x, cy - mainland.centroid.y
    # 鄰縣最短距離（不應與任何其他縣市接觸）
    others = gdf[gdf["COUNTYNAME"] != cn]
    other_union = unary_union(others.geometry.tolist())
    d_other = other_union.distance(isl_union) / 1000.0
    a_km2 = isl_union.area / 1e6
    bx0, by0, bx1, by1 = isl_union.bounds
    print("  ── 龜山島幾何自檢 ──")
    print(f"  面積 {a_km2:.3f} km²、外接矩形 {(bx1 - bx0) / 1000:.2f} × "
          f"{(by1 - by0) / 1000:.2f} km、{len(islets)} 塊")
    print(f"  距宜蘭本體最近 {d_near:.1f} km；島中心相對宜蘭圖形中心："
          f"dx={dx / 1000:+.1f} km、dy={dy / 1000:+.1f} km（東北外海為正確位）")
    print(f"  距其他縣市最近 {d_other:.1f} km（應 > 5 km，島不應碰鄰縣）")
    # 畫測試圖：宜蘭縣一帶村里界（淺灰）＋ 龜山島（橘色高亮）
    pad = 4000.0
    minx, miny, maxx, maxy = mainland.bounds
    minx, miny = minx - pad, miny - pad
    maxx, maxy = max(maxx, bx1) + pad, max(maxy, by1) + pad
    region = _box(minx, miny, maxx, maxy)
    sub = gdf[gdf.intersects(region)]
    fig, ax = plt.subplots(figsize=(14, 14), dpi=100)
    sub.plot(ax=ax, edgecolor="#909090", facecolor="white", linewidth=0.6)
    gpd.GeoSeries(islets, crs=gdf.crs).plot(
        ax=ax, facecolor="#E8734A", edgecolor="black", linewidth=1.2)
    nx, ny = (bx0 + bx1) / 2, by1 + 1500.0
    ax.annotate(f"龜山島 {a_km2:.2f} km²\n距宜蘭本體 {d_near:.1f} km",
                (nx, ny), ha="center", fontsize=12, color="#B04000")
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0.5)
    fig.savefig(GUEISHAN_TEST_OUT, dpi=100)
    plt.close(fig)
    print(f"  Saved: {GUEISHAN_TEST_OUT}")


# ---------------------- 純統計模式（--stats，不出圖）---------------------
def _stats_only(argv):
    """命令列含 --stats／--stats-only／-s → 只統計並輸出 MD，不畫任何圖。"""
    return any(str(a).lower() in ("--stats", "--stats-only", "-s") for a in argv[1:])


def run_stats_only():
    """只跑「讀票 → 讀底圖 → 比對 → 填色 → 平票判定」，不排版、不填色成像、不出 PNG。

    輸出 STATS_MD（`全臺灣2008_村里比對統計_測試.md`），內容：
      摘要數字、各縣市彙總、非精確比對逐筆（沿革／跨里／萬用字元／消去／模糊）、
      無資料圖斑逐筆、**有得票資料但底圖無圖斑**逐筆（含票數）、平票逐筆、
      附錄：全部圖斑的比對結果清單。
    純資料側統計（不經底圖）請另跑 `stats/analyze_village_party_leads.py`。
    """
    t0 = time.time()
    print("=" * 66)
    print("  全臺灣 2008 立法委員不分區（政黨票）村里比對統計"
          "　【純統計模式：不產生圖片】")
    print("=" * 66)

    # ---- ① 得票資料 ----
    by_key, by_town, vote_display, cnt_by_key, n_total = load_party_votes()
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(vote_display)} 個村里、"
          f"{len(PARTIES)} 個政黨")

    # ---- ② 底圖 ----
    gdf = load_base_map()
    gdf = add_old_county(gdf)
    gdf = resolve_cross_county_overlaps(gdf)
    gdf = strip_far_parts(gdf)
    print(f"  底圖村里圖斑：{len(gdf)}；2008 縣市：{gdf['OLD_COUNTY'].nunique()}")

    # ---- ③ 比對 ----
    gdf, rate_cols = match_votes(gdf, by_key, by_town, cnt_by_key,
                                 build_lineage_index(by_key))

    # ---- ④ 填色 + 平票 ----
    gdf, has_data, min_win = pick_colors(gdf, rate_cols, cnt_by_key)
    gdf, has_data, n_town_fill = fill_blank_islets_town_colors(
        gdf, has_data, cnt_by_key, rate_cols)

    # 注意：`match_type` 的快照必須在「金馬澎島嶼填鄉鎮色」之後才取 ——
    # 該步驟會把 156 塊 none 改標為 "town"，提前取會出現「無資料 160 vs 留白 4」的矛盾。
    mt = gdf["match_type"].astype(str)
    stats = {
        "exact": int((mt == "exact").sum()),
        "merged": int(mt.str.startswith("merged").sum()),
        "mergevote": int(mt.str.startswith("mergevote").sum()),
        "wildcard": int(mt.str.startswith("wildcard").sum()),
        "elimination": int(mt.str.startswith("elimination").sum()),
        "fuzzy": int(mt.str.startswith("fuzzy").sum()),
        "town": int((mt == "town").sum()),
        "none": int((~has_data).sum()),
    }

    # ---- 有票無圖（孤兒票）----
    used = {(norm_county(r["COUNTYNAME"]), norm_town(r["TOWNNAME"]), r["matched_vill"])
            for _, r in gdf[has_data].iterrows() if r["matched_vill"]}
    orphan = sorted(k for k in vote_display if k not in used)
    orphan_votes = sum(cnt_by_key[k][-1] for k in orphan)

    # ---- 各項清單 ----
    none_all = gdf[~has_data]
    rock_df = none_all[none_all["VILLNAME"].astype(str).str.strip().eq("")]
    none_df = none_all[~none_all["VILLNAME"].astype(str).str.strip().eq("")] \
        .sort_values(["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    merged_df = gdf[gdf["merged_into"].astype(str) != ""].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "merged_into", "VILLNAME"])
    vote_df = gdf[mt.str.startswith("mergevote")].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    wild_df = gdf[mt.str.startswith(("wildcard", "elimination"))].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    fuzzy_df = gdf[mt.str.startswith("fuzzy")].sort_values(
        ["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
    tie_df = gdf[gdf["tie_hex"].notna()].sort_values(["OLD_COUNTY", "TOWNNAME", "VILLNAME"])

    n_plot = int(has_data.sum())
    n_blank = int((~has_data).sum())
    print(f"  圖斑 {len(gdf)}｜有資料 {n_plot}｜無資料 {n_blank}"
          f"（其中無村里名礁石 {len(rock_df)}）｜以鄉鎮色填補 {n_town_fill}")
    print(f"  比對：精確 {stats['exact']}、沿革合併 {stats['merged']}、跨里合併 "
          f"{stats['mergevote']}、萬用字元 {stats['wildcard']}、消去法 "
          f"{stats['elimination']}、模糊 {stats['fuzzy']}、"
          f"鄉鎮色填補 {stats['town']}、無資料 {stats['none']}")
    print(f"  有票無圖（孤兒票）：{len(orphan)} 個村里、合計 {int(orphan_votes)} 票")
    print(f"  平票圖斑：{len(tie_df)} 個")

    def _top2(key):
        """回傳 (有效票, 第1名(票), 第2名(票))；用於孤兒票／平票明細。"""
        c = cnt_by_key.get(key)
        if c is None:
            return None
        cnts = [float(v) for v in c[:-1]]
        order = sorted(range(len(cnts)), key=lambda i: cnts[i], reverse=True)
        return int(c[-1]), f"{PARTIES[order[0]]} {int(cnts[order[0]])}", \
            f"{PARTIES[order[1]]} {int(cnts[order[1]])}"

    def _is_vote_tie(key):
        """資料側是否有兩黨以上同為最高票（＝純資料側統計的「並列」）。"""
        c = cnt_by_key.get(key)
        if c is None:
            return False
        v = sorted((float(x) for x in c[:-1]), reverse=True)
        return len(v) > 1 and v[0] > 0 and v[0] == v[1]

    orphan_ties = [k for k in orphan if _is_vote_tie(k)]

    L = ["# 全臺灣 2008 立法委員不分區（政黨票）— 村里比對統計（純統計模式）", "",
         f"- 產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         "- 產生指令：`py scripts/atlarge/Draw_Taiwan_AtLarge_2008.py --stats`"
         "（只統計，**不產生任何圖片**）",
         "- 底圖：`twvillage2012.json`（民國 101 年村里界）＋ 嘉義市改用 "
         "`twVillage_pre2010.geo.json`（民國 99 年前 108 里）；"
         "金門／連江改用 106 年村里界拼接",
         "- 得票資料：`Data/2008不分区`（中選會原始 xls，12 個政黨；多村里併列的投開票所已拆開）",
         "",
         "> **兩種統計單位不同**：本報告的「村里圖斑」＝底圖多邊形（畫得出來的），"
         "「得票村里」＝xls 里的村里列。2008 有票、2012 圖資已無此里的"
         "（見第 4 節）不會出現在地圖上，因此地圖的領先村里統計會比純資料側少幾個。",
         ""]

    # ---- 0 摘要 ----
    L += ["## 0. 摘要", "", "| 項目 | 數量 | 說明 |", "|---|---:|---|",
          f"| 村里圖斑（底圖） | {len(gdf)} | 有對應多邊形、可上圖 |",
          f"| 得票村里（資料側） | {len(vote_display)} | xls 村里列，含底圖沒有的里 |",
          f"| 已上圖（有資料） | {n_plot} | 含以鄉鎮得票率填色的島嶼 {n_town_fill} 塊 |",
          f"| 精確比對 | {stats['exact']} | 村里名（異體字收斂後）完全相同 |",
          f"| 沿革合併 | {stats['merged']} | 2012 里併入 2008 母里 |",
          f"| 跨里合併 | {stats['mergevote']} | 多個 2008 里 → 一 2012 里，票數加總重算 |",
          f"| 萬用字元 | {stats['wildcard']} | 來源 U+FFFD／底圖 ■、PUA 佔位符 |",
          f"| 消去法 | {stats['elimination']} | 村名整串是佔位符，同鄉鎮同長度唯一候選 |",
          f"| 異體字模糊 | {stats['fuzzy']} | 峯/峰、舘/館 … 單字異體 |",
          f"| 鄉鎮色填補 | {stats['town']} | 金門／連江／澎湖的空白島嶼 → 取所屬鄉鎮得票率 |",
          f"| 無資料（留白） | {n_blank} | 其中無村里名礁石 {len(rock_df)} 塊、"
          f"真正的無資料村里 {len(none_df)} 塊 |",
          f"| **有票無圖（孤兒票）** | **{len(orphan)}** | 見第 4 節；合計 {int(orphan_votes)} 票未上圖 |",
          f"| 平票圖斑 | {len(tie_df)} | 第 1、2 名同票 → 疊 45° 斜線紋 |",
          "",
          f"> 「被統計上」＝圖斑成功取得得票率（{n_plot} 塊）；"
          f"其中 **非精確**（沿革／跨里／萬用字元／消去／模糊）共 "
          f"**{stats['merged'] + stats['mergevote'] + stats['wildcard'] + stats['elimination'] + stats['fuzzy']}** 塊，"
          f"逐筆列於第 2 節。完整清單見附錄。", ""]

    # ---- 1 各縣市彙總 ----
    L += ["## 1. 各縣市彙總（2008 行政區）", "",
          "| 縣市 | 圖斑 | 精確 | 沿革合併 | 跨里合併 | 萬用字元/消去 | 模糊 | 鄉鎮色 | 無資料 | 平票 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c, sub in gdf.groupby("OLD_COUNTY"):
        smt = sub["match_type"].astype(str)
        L.append(f"| {c} | {len(sub)} | {int((smt == 'exact').sum())} | "
                 f"{int(smt.str.startswith('merged').sum())} | "
                 f"{int(smt.str.startswith('mergevote').sum())} | "
                 f"{int(smt.str.startswith(('wildcard', 'elimination')).sum())} | "
                 f"{int(smt.str.startswith('fuzzy').sum())} | "
                 f"{int((smt == 'town').sum())} | "
                 f"{int((~has_data[sub.index]).sum())} | "
                 f"{int(sub['tie_hex'].notna().sum())} |")
    L.append("")

    # ---- 2 非精確比對 ----
    L += [f"## 2. 非精確比對逐筆（模糊統計；共 "
          f"{stats['merged'] + stats['mergevote'] + stats['wildcard'] + stats['elimination'] + stats['fuzzy']} 塊）",
          "",
          "### 2.1 村里沿革合併（2012 里 → 2008 母里；同底色、其間不畫村界線）", ""]
    if len(merged_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 子里（2012 圖資） | 併入 2008 母里 |",
              "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['merged_into']} |"
              for i, (_, r) in enumerate(merged_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L += ["", "### 2.2 跨里合併（多個 2008 里 → 一 2012 里，得票數加總重算）", ""]
    if len(vote_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 2012 里 | 承接的 2008 里 |", "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill'].replace('+', '＋')} |"
              for i, (_, r) in enumerate(vote_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L += ["", "### 2.3 萬用字元／消去法（來源資料 U+FFFD 或底圖 ■、PUA 佔位符）", ""]
    if len(wild_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 底圖村里 | 對應得票資料 | 方式 |",
              "|---:|---|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill']} | {r['match_type']} |"
              for i, (_, r) in enumerate(wild_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L += ["", "### 2.4 異體字模糊（單字異體：峯/峰、舘/館、磘/窯 …）", ""]
    if len(fuzzy_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 底圖村里 | 對應得票資料 |", "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{r['matched_vill']} |"
              for i, (_, r) in enumerate(fuzzy_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    # ---- 3 無資料 ----
    L += [f"## 3. 有圖斑、無得票資料（最終留白 {n_blank} 塊）", ""]
    L += [f"> 原始比對有 **{n_blank + n_town_fill}** 塊對不上得票資料，其中 **{n_town_fill}** 塊"
          f"屬金門／連江／澎湖的無名礁石與無人島，已改以**所屬鄉鎮得票率**填色"
          f"（`match_type=town`，不計入留白）；下面 **{n_blank}** 塊仍然留白。",
          f"> 這 {n_blank} 塊裡，無村里名的礁石 {len(rock_df)} 塊、有名有姓卻查無得票的村里 "
          f"{len(none_df)} 塊。", ""]
    if len(none_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 村里 | 村里名空值 |", "|---:|---|---|---|---|"]
        L += [f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
              f"{'是' if not str(r['VILLNAME']).strip() else '否'} |"
              for i, (_, r) in enumerate(none_df.iterrows(), 1)]
    else:
        L.append("（無）")
    L.append("")

    # ---- 4 有票無圖 ----
    L += [f"## 4. 有得票資料、但底圖沒有對應村里的圖斑（孤兒票；{len(orphan)} 筆、"
          f"合計 {int(orphan_votes)} 票）", "",
          "> 這批票**不會**被加到同鄉鎮的其他里（比對是「圖斑找票」的單向流程，"
          "且跨鄉鎮誤配自檢為 0），因此地圖上等於不存在；純資料側統計仍會計入。",
          ""]
    if orphan:
        L += ["| # | 縣市 | 鄉鎮市區 | 村里（得票資料） | 有效票 | 最高票 | 次高票 |",
              "|---:|---|---|---|---:|---|---|"]
        for i, k in enumerate(orphan, 1):
            c, t, v = vote_display[k]
            tt = _top2(k)
            if tt is None:
                L.append(f"| {i} | {c} | {t} | {v} | — | — | — |")
            else:
                L.append(f"| {i} | {c} | {t} | {v} | {tt[0]} | {tt[1]} | {tt[2]} |")
        L += ["", f"**孤兒票合計：{int(orphan_votes)} 票**"
                  f"（佔全國有效票 9,780,573 的 {orphan_votes / 9780573 * 100:.5f}%）"]
        if orphan_ties:
            L += ["",
                  f"> 其中 **{len(orphan_ties)}** 筆在純資料側統計屬「**並列**」（最高票相同），"
                  f"但因底圖沒有對應圖斑而不會出現在地圖上 —— 這正是"
                  f"「資料側並列數（{len(tie_df) + len(orphan_ties)}）> 地圖平票圖斑數（{len(tie_df)}）」的差額：",
                  "> " + "、".join(
                      f"{vote_display[k][0]}{vote_display[k][1]}{vote_display[k][2]}"
                      f"（有效票 {int(cnt_by_key[k][-1])}）" for k in orphan_ties)]
    else:
        L.append("（無）")
    L.append("")

    # ---- 5 平票 ----
    L += [f"## 5. 平票圖斑（第 1、2 名同票 → 疊 45° 斜線紋；{len(tie_df)} 個）", "",
          "> 判定：得票率同至小數 3 位／得票數相同／差 ≤ `TIE_RATE_EPS`。"
          "底色＝第 1 名，斜線＝第 2 名顏色；兩黨同屬一個色階組時不疊（看不出差異）。", ""]
    if len(tie_df):
        L += ["| # | 縣市 | 鄉鎮市區 | 村里 | 有效票 | 底色（第 1 名） | 斜線（第 2 名） | 比對方式 |",
              "|---:|---|---|---|---:|---|---|---|"]
        for i, (_, r) in enumerate(tie_df.iterrows(), 1):
            k = (norm_county(r["COUNTYNAME"]), norm_town(r["TOWNNAME"]),
                 str(r["matched_vill"]))
            c = cnt_by_key.get(k)
            vtxt = int(c[-1]) if c is not None else "（合併）"
            L.append(f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
                     f"{vtxt} | {r['win_party']} | {r['tie_party']} | {r['match_type']} |")
    else:
        L.append("（無）")
    L.append("")

    # ---- 6 附錄：全量清單 ----
    L += ["## 6. 附錄：全部圖斑比對結果", "",
          f"共 {len(gdf)} 塊；`比對方式`＝exact（精確）／merged:母里（沿革合併）／"
          "mergevote:來源（跨里合併）／wildcard:…／elimination:…／fuzzy:…／"
          "town（以鄉鎮得票率填補的島嶼）／none（無資料、留白）。", "",
          "| # | 縣市 | 鄉鎮市區 | 村里 | 比對方式 | 領先政黨 | 領先得票率(%) |",
          "|---:|---|---|---|---|---|---:|"]
    for i, (_, r) in enumerate(gdf.sort_values(["OLD_COUNTY", "TOWNNAME", "VILLNAME"])
                                .iterrows(), 1):
        mtype = str(r["match_type"])
        wp = str(r["win_party"]) if str(r["win_party"]) else "—"
        try:
            rate = f"{float(np.nanmax([r[c] for c in rate_cols])):.2f}"
        except (ValueError, TypeError):
            rate = "—"
        if mtype == "none" or wp == "—":
            rate = "—"
        L.append(f"| {i} | {r['OLD_COUNTY']} | {r['TOWNNAME']} | {r['VILLNAME']} | "
                 f"{mtype} | {wp} | {rate} |")
    L.append("")

    with open(STATS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  統計報告：{STATS_MD}（{len(L)} 行）")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== 統計完成（未產生任何圖片） ====")


# ---------------------- 主流程 ----------------------
def _test_only(argv):
    """命令列含 --test／--only-islands → 只畫離島三縣市（快速核對線寬與礁石）。"""
    return any(str(a).lower() in ("--test", "--only-islands", "-t") for a in argv[1:])


def main():
    t0 = time.time()
    stats_only = _stats_only(sys.argv)
    test_only = _test_only(sys.argv)
    boundary_test = _boundary_test(sys.argv)
    gueishan_test = _gueishan_test(sys.argv)
    # 純統計模式：先分流，完全不進繪圖管線（不排版、不填色成像、不存 PNG）
    if stats_only:
        run_stats_only()
        return
    print("=" * 66)
    print("  全臺灣 2008 立法委員不分區（政黨票）村里得票率地圖"
          + ("　【測試模式：只畫澎湖／金門／連江】" if test_only else "")
          + ("　【邊界測試：縣市界＋海岸線】" if boundary_test else "")
          + ("　【龜山島補漏測試】" if gueishan_test else ""))
    print("=" * 66)
    if gueishan_test:
        run_gueishan_test()
        return
    if boundary_test:
        run_boundary_test()
        return

    # ---- ① 得票資料 ----
    by_key, by_town, vote_display, cnt_by_key, n_total = load_party_votes()
    print(f"  得票資料：{n_total} 列（投票所層級）→ {len(by_key)} 個村里、"
          f"{len(PARTIES)} 個政黨")

    # ---- ② 底圖 ----
    gdf = load_base_map()
    gdf = add_old_county(gdf)
    print(f"  底圖村里圖斑：{len(gdf)}；2008 縣市：{gdf['OLD_COUNTY'].nunique()}")
    if test_only:
        # 離島三縣市彼此不相鄰，跨縣市重疊仲裁必然無事可做 → 跳過（省一次 111 年 SHP 讀取）
        print("  跨縣市重疊清理：測試模式略過（離島三縣市互不相鄰）")
    else:
        gdf = resolve_cross_county_overlaps(gdf)
    gdf = strip_far_parts(gdf)
    if test_only:
        _m = gdf["COUNTYNAME"].isin(TEST_COUNTIES)
        print(f"  測試模式：只保留 {'、'.join(TEST_COUNTIES)} → "
              f"{int(_m.sum())} 個村里圖斑（原 {len(gdf)}）")
        gdf = gdf[_m].copy().reset_index(drop=True)

    # ---- ③ 比對（沿革合併 → 跨里合併 → 萬用字元 → 異體模糊） ----
    lin_idx = build_lineage_index(by_key)
    gdf, rate_cols = match_votes(gdf, by_key, by_town, cnt_by_key, lin_idx)
    mt = gdf["match_type"].astype(str)
    stats = {
        "exact": int((mt == "exact").sum()),
        "merged": int(mt.str.startswith("merged").sum()),
        "mergevote": int(mt.str.startswith("mergevote").sum()),
        "wildcard": int(mt.str.startswith("wildcard").sum()),
        "elimination": int(mt.str.startswith("elimination").sum()),
        "fuzzy": int(mt.str.startswith("fuzzy").sum()),
        "none": int((mt == "none").sum()),
    }
    print(f"  精確 {stats['exact']}、沿革合併 {stats['merged']}、跨里合併 "
          f"{stats['mergevote']}、萬用字元 {stats['wildcard']}、消去法 "
          f"{stats['elimination']}、模糊 {stats['fuzzy']}、無資料 {stats['none']}")

    # ---- ④ 填色 ----
    gdf, has_data, min_win = pick_colors(gdf, rate_cols, cnt_by_key)
    gdf, has_data, n_town_fill = fill_blank_islets_town_colors(
        gdf, has_data, cnt_by_key, rate_cols)
    print(f"  有資料填色 {int(has_data.sum())}／{len(gdf)}"
          f"（含金馬澎空白島嶼填鄉鎮色 {n_town_fill} 塊）；"
          f"全臺最低領先得票率 {min_win:.2f}%")
    for p, n in gdf.loc[has_data, "win_party"].value_counts().items():
        print(f"    領先村里：{p} {int(n)}")

    # 平票：底色＝第 1 名，另疊第 2 名顏色的 45° 斜線紋（不影響領先村里統計）
    _tie_rows = gdf[gdf["tie_hex"].notna()]
    print(f"  平票村里（第 1、2 名同票 → 疊 45° 斜線紋）：{len(_tie_rows)} 個")
    if len(_tie_rows):
        _pairs = (_tie_rows["win_party"].astype(str) + "／" + _tie_rows["tie_party"].astype(str))
        print(f"    平票組合：{_pairs.value_counts().to_dict()}")
        _names = [f"{r.COUNTYNAME}{r.TOWNNAME}{r.VILLNAME}"
                  for r in _tie_rows.itertuples()]
        print(f"    明細（{len(_names)}）：{'、'.join(_names[:20])}"
              + ("…" if len(_names) > 20 else ""))

    write_missing_report(gdf, vote_display, stats,
                         md_path=(TEST_MISS_MD if test_only else MISSING_MD))

    # ---- ⑤ 版面 ----
    if test_only:
        gdf, boxes = layout_stack_all(gdf)
    else:
        gdf, boxes = layout_insets(gdf)
    records = gpd.GeoDataFrame(
        gdf[["COUNTYNAME", "TOWNNAME", "VILLNAME", "OLD_COUNTY", "unit_core",
             "merged_into", "fill_hex", "tie_hex", "match_type"] + rate_cols].copy(),
        geometry=gdf.geometry, crs=gdf.crs)

    # ---- 畫布（長寬硬上限 10000 × 12500 px） ----
    minx, miny, maxx, maxy = records.total_bounds
    # 附圖外框也要完整落在畫布內（框線比內容外擴 INSET_BOX_PAD，不能只依內容取界）
    for _cn, (_bx0, _by0, _bx1, _by1), _lw in boxes:
        minx, miny = min(minx, _bx0), min(miny, _by0)
        maxx, maxy = max(maxx, _bx1), max(maxy, _by1)
    pad_x, pad_y = PAD_FRAC * (maxx - minx), PAD_FRAC * (maxy - miny)
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    geo_w, geo_h = maxx - minx, maxy - miny

    scale = max(geo_w / MAX_W_PX, geo_h / MAX_H_PX, METERS_PER_PIXEL)
    w_px = int(math.ceil(geo_w / scale))
    h_px = int(math.ceil(geo_h / scale))
    sx, sy = w_px / geo_w, h_px / geo_h
    print(f"  統一比例尺：1 像素 = {geo_w / w_px:.3f} 米")
    print(f"  圖片尺寸：{w_px} × {h_px} px（上限 {MAX_W_PX}×{MAX_H_PX}，"
          f"{w_px * h_px / 1e6:.0f} 百萬像素）")

    # ---- 區／縣市層（dissolve 後清理退化迴針與微孔） ----
    gdf_plot = gpd.GeoDataFrame(records, geometry="geometry", crs=records.crs)
    townships = gdf_plot.dissolve(by=["OLD_COUNTY", "TOWNNAME"]).reset_index()
    counties = gdf_plot.dissolve(by=["OLD_COUNTY"]).reset_index()
    townships = remove_ring_slits(townships)
    townships = clean_tiny_holes(townships)
    counties = remove_ring_slits(counties)
    counties = clean_tiny_holes(counties)
    print(f"  縣市（2008）：{len(counties)}、鄉鎮市區：{len(townships)}、村里：{len(gdf_plot)}")

    # ---- ② 區界 + 縣市界 + 附圖外框（海岸線另以 1px 金馬畫法繪製） ----
    print(f"  ② 區界 {LINE_TOWNSHIP_PX}px + 縣市界 {LINE_COUNTY_INNER_PX}px"
          f" ＋ 附圖外框 {LINE_INSET_BOX_PX}px（matplotlib + 閾值二值化）；"
          f"澎湖／金門／連江本層不描外緣，海岸線全圖統一 {LINE_COAST_PX}px"
          f"（金馬同款：1px 直繪 → thin 中心線）…")
    _thick_cty, coast_geom, county_segs = compute_county_boundary(counties)
    print(f"  縣市界幾何：{len(county_segs)} 段"
          f"（{sum(g.length for g in county_segs) / 1000:.0f} km）")
    audit_county_segments(counties, county_segs)
    # ② 層不畫附圖外框（boxes 傳空）——外框只由 render_inset_box_mask 單一成像，
    # 並在洪水填充前併入堤壩，最後改上黑線（避免兩處成像的亞像素錯位）
    town_layer = render_boundary_layer(townships, counties, county_segs, [],
                                       w_px, h_px, minx, maxx, miny, maxy)
    print(f"  區/縣市界層：{int(town_layer.sum())} px"
          f"（區界 {LINE_TOWNSHIP_PX}px、縣市界 {LINE_COUNTY_INNER_PX}px，"
          f"閾值 {THRESHOLD_VAL}；海岸線不在本層）")

    # ---- 附圖外框專用遮罩（最後改上黑線） ----
    print(f"  附圖外框遮罩（金門／連江／烏坵框，最後改上黑線；"
          f"其餘界線維持 {LINE_COLOR}）…")
    box_mask = render_inset_box_mask(boxes, w_px, h_px, minx, maxx, miny, maxy)
    print(f"  附圖外框遮罩：{int(box_mask.sum())} px")

    # ---- ① 村里界 1px ----
    print("  ① 村里界 1px（1px 直繪 → thin 中心線；沿革合併單元其間不畫線）…")
    villages = gdf_plot if not SIMPLIFY_TOL_M else (
        gdf_plot.set_geometry(gdf_plot.geometry.simplify(SIMPLIFY_TOL_M, True)))
    # 村里界以「當年行政單元」為單位：沿革合併者與母里同屬一單元，其間不畫界線
    _ukey = (villages["COUNTYNAME"].astype(str) + "|" + villages["TOWNNAME"].astype(str)
             + "|" + villages["unit_core"].astype(str))
    _blank = villages["unit_core"].astype(str).str.strip().eq("")
    _ukey = _ukey.where(~_blank, _ukey + "#" + villages.index.astype(str))
    unit_polys = villages.assign(_unit_key=_ukey).dissolve(by="_unit_key").reset_index()
    print(f"  沿革合併後行政單元：{len(unit_polys)}（村里圖斑 {len(villages)}）")
    village_skel = render_village_layer(unit_polys, w_px, h_px, minx, maxy, sx, sy)
    del unit_polys
    print(f"  村里層 1px 中心線：{int(village_skel.sum())} px")

    # ---- 海岸線 1px（本島，金馬同款畫法） ----
    print(f"  海岸線 {LINE_COAST_PX}px（本島縣市聯集外輪廓；"
          f"1px 直繪 → thin 中心線，與金門／馬祖同一畫法）…")
    coast_skel = render_main_coast_layer(coast_geom, w_px, h_px, minx, maxy, sx, sy)
    print(f"  海岸線層 1px 中心線：{int(coast_skel.sum())} px")

    lines_mask = village_skel | town_layer | coast_skel | box_mask
    del village_skel, coast_skel

    check_reef_drawn(gdf_plot, lines_mask, w_px, h_px, minx, maxy, sx, sy)

    # 對齊自檢：所有區界/縣市界/小島海岸線的 1px 原始線都必須被線稿覆蓋
    S3 = np.ones((3, 3), dtype=bool)
    _town_1px = draw_layer(extract_lines(unary_union(townships.geometry.boundary.tolist())),
                           1, w_px, h_px, minx, maxy, sx, sy)
    _miss = int((_town_1px & ~ndimage.binary_dilation(lines_mask, structure=S3)).sum())
    print(f"  區/縣市界 1px 原始線 {int(_town_1px.sum())} px，"
          f"未被線稿覆蓋 {_miss} px（應 ≈0）")
    del _town_1px

    # 散點自檢：② 層連通分量（本島＋澎湖＋金馬附圖，不應有其他散塊）
    _cc_n, _, _cc_st, _ = cv2.connectedComponentsWithStats(
        town_layer.astype(np.uint8), connectivity=8)
    _cc_area = _cc_st[1:, cv2.CC_STAT_AREA]
    print(f"  ② 層連通分量：{_cc_n - 1} 個；<=40px 小分量 {int((_cc_area <= 40).sum())} 個（應為 0）")

    # 村里線自檢：扣掉 ② 層後不應出現 2x2 粗塊
    _v_only = lines_mask & ~town_layer
    _2x2 = ndimage.binary_erosion(_v_only, structure=np.ones((2, 2), dtype=bool))
    print(f"  村里層 1px 像素：{int(_v_only.sum())}，2x2 粗塊（應≈0）：{int(_2x2.sum())}")
    del _v_only, _2x2

    if SAVE_LAYER:
        _la = np.full((h_px, w_px, 3), 255, dtype=np.uint8)
        _la[lines_mask] = LINE_RGB
        save_png(Image.fromarray(_la, mode="RGB"), os.path.join(OUT_DIR, layer_name))

    # ---- 填色（洪水填充） ----
    print("  填色（洪水填充／油漆桶規則，4-連通區域整塊上色）…")
    arr, ncomp, comp = nat.flood_fill_layer(records, lines_mask, w_px, h_px,
                                            minx, maxy, sx, sy)
    # 線稿上色：遮罩本身即堤壩（線寬不變），只是把純黑換成使用者指定的線色；
    # 附圖外框（金門／連江／烏坵框）再改回純黑（使用者指定 2026-11-03）
    arr[lines_mask] = np.array(LINE_RGB, dtype=np.uint8)
    arr[box_mask] = 0
    print(f"  非線連通區域：{ncomp - 1} 塊；線色 {LINE_COLOR}、"
          f"附圖外框 黑 (0,0,0)")
    _n_line = int(lines_mask.sum())
    _uniq_l = np.unique(arr[lines_mask].reshape(-1, 3), axis=0)
    print(f"  線稿像素 {_n_line}，線色種類 {len(_uniq_l)}（應為 2＝"
          f"{LINE_COLOR} 近白＋黑框："
          f"{[tuple(int(x) for x in c) for c in _uniq_l]}）")

    # 自檢 A：油漆桶不變式
    _nc, _nbad = nat.check_region_single_color(arr, ncomp, comp)
    print(f"  油漆桶不變式：非線區域 {_nc} 塊，非單色區域 {_nbad} 塊（應為 0）")
    del comp

    # 平票斜線紋（規格同 Precident/平票斜線紋_通用程式碼片段.txt）：
    # 必須在「線稿上色 arr[lines_mask]=LINE_RGB」與「單色不變式」自檢之後才疊 ——
    # 斜線紋會刻意讓平票圖斑出現兩色。界線一律以權威 lines_mask 排除，
    # 不用 arr.any(axis=2) 顏色反推（線色是 #FCFCFC 近白，反推會失效）。
    _line_before = arr[lines_mask].copy()
    _n_tie = nat.apply_tie_stripes(arr, records, w_px, h_px, minx, maxy, sx, sy,
                                   lines_mask=lines_mask, stripe_px=TIE_STRIPE_PX)
    _n_line = int(lines_mask.sum())
    _line_kept = int((arr[lines_mask] == _line_before).all(axis=1).sum())
    print(f"  平票後線稿：{_line_kept}/{_n_line} 線像素仍為原線色"
          f"（應相等＝界線完整；斜線紋 {_n_tie} 個村里圖斑）")
    if _line_kept != _n_line:
        print("  ⚠️ 斜線紋侵占界線 —— 檢查 lines_mask 是否正確傳入／與 arr 同尺寸")
    del _line_before

    # 自檢 B：逐像素幾何參考（獨立方法；線像素以 ignore_mask 排除，
    # 因線色非純黑、不是填色，也不該算「村外非白」）
    _nw, _nout = nat.full_geom_check(arr, records, w_px, h_px, minx, maxy, sx, sy,
                                     lines_mask=lines_mask, ignore_mask=lines_mask)
    _tot = w_px * h_px
    print(f"  與逐像素幾何參考差異：{_nw} px（{_nw / _tot * 100:.4f}%）；"
          f"村外非白 {_nout} px（皆應 ≈0）")

    # 自檢 C：全圖只含允許色
    allowed = {(255, 255, 255), (0, 0, 0), tuple(int(v) for v in LINE_RGB)}
    for stops in PARTY_STOPS.values():
        for _, hx in stops:
            allowed.add(tuple(int(round(v * 255)) for v in nat.hex2rgb(hx)))
    _uniq, _cnt = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    _bad = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_uniq, _cnt)
            if tuple(int(x) for x in c) not in allowed]
    print(f"  全圖顏色 {len(_uniq)} 種（允許 {len(allowed)}）；"
          f"非允許色像素 {sum(n for _, n in _bad)}（應為 0）")
    if _bad:
        print(f"  ⚠️ 非允許色：{_bad[:5]}")

    pil_img = Image.fromarray(arr, mode="RGB")
    del arr
    out_png = TEST_OUT_PNG if test_only else OUT_PNG
    save_png(pil_img, out_png)
    W, H = pil_img.size
    del pil_img

    # ---- 存檔後自檢 ----
    _re = np.asarray(Image.open(out_png).convert("RGB"))
    _u2, _c2 = np.unique(_re.reshape(-1, 3), axis=0, return_counts=True)
    _bad2 = [(tuple(int(x) for x in c), int(n)) for c, n in zip(_u2, _c2)
             if tuple(int(x) for x in c) not in allowed]
    _nw2, _nout2 = nat.full_geom_check(_re, records, w_px, h_px, minx, maxy, sx, sy,
                                       lines_mask=lines_mask, ignore_mask=lines_mask)
    _tol2 = 0.0002 * w_px * h_px
    print(f"  存檔自檢：非允許色 {sum(n for _, n in _bad2)} px、幾何參考差異 {_nw2} px"
          f"（容差 {_tol2:.0f}）、村外非白 {_nout2} px（皆應 ≈0）")
    print(f"\n  Saved: {out_png}  ({W}×{H}px)")
    print(f"  總耗時 {time.time() - t0:.1f}s")
    print("==== All finished ====")


if __name__ == "__main__":
    main()
