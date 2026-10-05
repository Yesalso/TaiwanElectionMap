# -*- coding: utf-8 -*-
"""
將「村里界歷史圖資_111」SHP 與「高雄格式」得票 Excel 結合，
繪製各村里候選人得票率地圖。

資料格式（各里彙總 工作表）：
    選舉區別 | 鄉(鎮、市、區)別 | 村里別 | <候選人>得票數 ... | 有效票數A
得票率(%) = 候選人得票數 ÷ 有效票數A × 100

色階從 0% 起（10% 間距）。
候選人數量由 Excel 自動偵測，圖例欄數隨之調整。

舊年份（1993、1997）資料為選舉當年的村里，與民國111年村里界 SHP 不同：
啟用 "village_merges" 後，會依 VILLAGE_SPLITS（母里 → 分出之里）把「當年尚未分出」
的里與母里合併為同一單元（同一底色、去除其間界線）；沿革未查得者維持無資料（未知）。

執行：
    py Converge_to_map.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import numpy as np
import re
import cv2
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from difflib import SequenceMatcher
import unicodedata
import warnings

# 字型鏈回退時，缺少的符號會由後備字型補上，這個警告可忽略
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")

# ===================== 字体设置 =====================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Microsoft JhengHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = r"D:\Windows\TaiwanElection\MayoralElections\data"
MAPS_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "maps")

# ===================== 配置区 =====================
SHP_CANDIDATE_PATHS = [
    r"D:\Windows\Documents\村里界歷史圖資_111\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
    r"D:\Windows\Documents\村里界歷史圖資_111\VILLAGE_MOI_1111118.shp",
]

# 要生成的地圖（兩張新北市長選舉）
DATASETS = [
    {
        "excel": os.path.join(EXCEL_DIR, "2010新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2010年市長選舉_得票率地圖.png"),
        "tag": "2010 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：蔡英文）",
        "title_lines": ["第一屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "蔡英文"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2014新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2014年市長選舉_得票率地圖.png"),
        "tag": "2014 新北市長選舉（中國國民黨：朱立倫 / 民主進步黨：游錫堃）",
        "title_lines": ["第二屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["朱立倫", "游錫堃"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2018新北_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2018年市長選舉_得票率地圖.png"),
        "tag": "2018 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第三屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "蘇貞昌"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "新北县市首长_2022.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "新北市2022年市長選舉_得票率地圖.png"),
        "tag": "2022 新北市長選舉（中國國民黨：侯友宜 / 民主進步黨：林佳龍）",
        "title_lines": ["第四屆新北市市長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["侯友宜", "林佳龍"],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "2005台北县.xlsx"),
        "sheet": "Sheet1",
        "header": 1,
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2005年縣長選舉_得票率地圖.png"),
        "tag": "2005 臺北縣長選舉（中國國民黨：周錫瑋 / 民主進步黨：羅文嘉）",
        "title_lines": ["第十五屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["周錫瑋", "羅文嘉"],
        "cand_columns": ["周錫偉", "羅文佳"],
        "col_city": "縣市",
        "col_town": "鄉鎮市區",
        "col_vill": "區里",
    },
    {
        "excel": os.path.join(EXCEL_DIR, "台北县2001_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣2001年縣長選舉_得票率地圖.png"),
        "tag": "2001 臺北縣長選舉（新黨：王建煊 / 民主進步黨：蘇貞昌）",
        "title_lines": ["第十四屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["王建煊", "蘇貞昌"],
        "color_schemes": [
            [(0,   "#FFFFEB"), (35,  "#FFFFEB"), (40, "#FFF8CC"),
             (45, "#FFF0A8"), (50, "#FFE780"), (55, "#FFDD55"),
             (60, "#FFF200"), (65, "#E6DA00"), (70, "#BFB500"),
             (75, "#999100"), (80, "#736D00"), (85, "#4D4900"),
             (100, "#383502")],
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "1993台北縣_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "year": 1993,
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣1993年縣長選舉_得票率地圖.png"),
        "tag": "1993 臺北縣長選舉（民主進步黨：尤清 / 中國國民黨：蔡勝邦）",
        "title_lines": ["第十二屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["尤清", "蔡勝邦"],
        "village_merges": True,
        "color_schemes": [
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
            [(35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"),
             (50, "#40C8FF"), (55, "#00C0F4"), (60, "#00A2E8"),
             (65, "#0080B8"), (70, "#006591"), (75, "#004B6B"),
             (80, "#003247"), (85, "#001F2E"), (100, "#010D29")],
        ],
    },
    {
        "excel": os.path.join(EXCEL_DIR, "1997台北縣_得票率.xlsx"),
        "sheet": "各里彙總",
        "city": "新北市",
        "year": 1997,
        "out": os.path.join(MAPS_DIR, os.path.basename(BASE_DIR), "臺北縣1997年縣長選舉_得票率地圖.png"),
        "tag": "1997 臺北縣長選舉（民主進步黨：蘇貞昌 / 中國國民黨：謝深山）",
        "title_lines": ["第十三屆臺北縣縣長選舉", "在各村（里）得票領先之候選人得票比例圖"],
        "legend_names": ["蘇貞昌", "謝深山"],
        "village_merges": True,
        "color_schemes": [
            [(35, "#E8FFE0"), (40, "#CEFFC2"), (45, "#C0FFB1"),
             (50, "#A4FF90"), (55, "#78FF4F"), (60, "#68DE45"),
             (65, "#54B337"), (70, "#3C8027"), (75, "#2B5C1C"),
             (80, "#1D3D13"), (85, "#0F210A"), (100, "#071A09")],
            [(35, "#D9F6FF"), (40, "#A6E9FF"), (45, "#73D9FF"),
             (50, "#40C8FF"), (55, "#00C0F4"), (60, "#00A2E8"),
             (65, "#0080B8"), (70, "#006591"), (75, "#004B6B"),
             (80, "#003247"), (85, "#001F2E"), (100, "#010D29")],
        ],
    },
]

# ===================== 村里沿革合併表 =====================
# 「母里」→「由該里劃分出的子里」。
# 用途：SHP 為民國111年村里界，若某里在選舉當年尚未由母里分出，則該里與母里
#       在當年是同一個行政單元 → 於地圖上合併為一塊（同一底色），並去除其間界線。
#       判斷方式為「該里名在該年 Excel 中查無資料」時才合併，故本表不必標註劃分年份。
#
# 來源：
#   [縣志] scripts/pages_69_87.txt（《臺北縣志》地理志 村里沿革，記載民國40～84年
#           各鄉鎮市之劃分、合併、改名）—— 本表主要依據。
#   [xlsx]  scripts/History.xlsx（1993～2010 年村里調整紀錄）。僅採用縣志未載、
#           且與縣志記載無牴觸者；已剔除經縣志證實之錯誤条目，例：
#             新莊 中信→中原/中隆（應為中港→中原/中信/中隆）、中華→中誠（應為中港→中誠）、
#             四維→南港（應為南港→四維）、龍福→龍安（應為萬安→龍安）、
#             西盛→光明/萬安（光明出自光華）、民安→建安（建安出自後港）、
#             新店 公崙→吉祥（應為玫瑰→吉祥）、公崙→德安（德安民國59年已析出）、
#             鶯歌 鳳祥→鳳鳴（應為鳳鳴→鳳祥）、土城 貨饒→日和（應為日新→日和）、
#             樹林 三多→大同（應為彭厝→大同）、泰山 明志→義仁/義學（應為義學→義仁）、
#             黎明→同榮/同興（應為同榮→同興）、汐止 東勢→橫科/宜興（應為橫科→福山/宜興）、
#             土城 瑞興→復興（縣志已載，非埤林）、八里 米倉→龍源（龍源為獅尾村改名）。
#   [查證]  區公所／戶政史料：汐止 建成 2010-03-01、湖興 1998；金山 金美 2005-06-01。
#
# 格式為 (母里, 子里)。合併事件（A、B 合併為 C）記為 (C, A)、(C, B)；改名事件記為
# (原名, 新名)。同一子里可能有複數母里（如新莊八德、瑞芳金山），由 build_split_index
# 以清單保存，解析時取當年資料中確實存在之祖先。
VILLAGE_SPLITS = {
    # ================= 板橋區 =================
    "板橋": [
        ("社後", "中正"), ("浮州", "復興"), ("浮州", "中山"), ("社後", "國光"), ("社後", "自強"), ("廣福", "仁愛"),
        ("廣福", "和平"), ("廣福", "福德"), ("湳興", "新興"), ("景星", "福星"), ("新埔", "公館"), ("新埔", "新民"),
        ("港嘴", "振興"), ("港嘴", "光復"), ("深丘", "香丘"), ("埔墘", "雙玉"), ("埔墘", "福壽"), ("埔墘", "玉光"),
        ("社後", "港尾"), ("社後", "民權"), ("社後", "建國"), ("新埔", "百壽"), ("新埔", "忠誠"), ("新埔", "幸福"),
        ("公館", "漢生"), ("江翠", "聯翠"), ("江翠", "宏翠"), ("松翠", "華翠"), ("嵐翠", "福翠"), ("福壽", "九如"),
        ("玉光", "埤墘"), ("雙玉", "廣興"), ("深丘", "福丘"), ("廣福", "廣德"), ("福德", "福祿"), ("湳興", "華興"),
        ("浮洲", "聚安"), ("社後", "香社"), ("自強", "自立"), ("自強", "光華"), ("港尾", "港德"), ("江翠", "溪頭"),
        ("宏翠", "新翠"), ("宏翠", "滿翠"), ("宏翠", "明翠"), ("松翠", "柏翠"), ("松翠", "龍翠"), ("華翠", "忠翠"),
        ("嵐翠", "文翠"), ("嵐翠", "青翠"), ("香丘", "東丘"), ("廣福", "重慶"), ("福德", "國泰"), ("華興", "華德"),
        ("聚安", "大安"), ("香社", "香雅"), ("港尾", "新生"), ("民權", "民安"), ("光華", "光榮"), ("幸福", "文德"),
        ("忠誠", "陽明"), ("聯翠", "文化"), ("新翠", "朝陽"), ("德翠", "新海"), ("龍翠", "松柏"), ("華翠", "莒光"),
        ("嵐翠", "文聖"), ("東丘", "民生"), ("長安", "東安"), ("埔墘", "富貴"), ("埤墘", "莊敬"), ("福壽", "居仁"),
        ("九如", "正泰"), ("華貴", "華福"), ("廣福", "五權"), ("國泰", "後埔"),
        ("嵐翠", "仁翠"),                      # [xlsx]
    ],
    # ================= 三重市 =================
    "三重": [
        ("共榮", "光榮"), ("共榮", "仁德"), ("長泰", "長安"), ("長泰", "長生"), ("同安", "光明"), ("菜寮", "大同"),
        ("長泰", "長元"), ("六合", "介壽"), ("六合", "三安"), ("大園", "文化"), ("大園", "正義"), ("菜寮", "中正"),
        ("仁德", "仁義"), ("長元", "長江"), ("介壽", "錦江"), ("介壽", "龍門"), ("光明", "光正"), ("大同", "大安"),
        ("正義", "重新"), ("大園", "中山"), ("大園", "國隆"), ("大園", "重陽"), ("大園", "民生"), ("六合", "安慶"),
        ("六合", "福安"), ("六合", "信安"), ("六合", "幸福"), ("厚德", "順德"), ("厚德", "瑞德"), ("厚德", "承德"),
        ("厚德", "崇德"), ("厚德", "尚德"), ("厚德", "培德"), ("二重", "頂崁"), ("二重", "大有"), ("五谷", "谷王"),
        ("五谷", "中興"), ("德厚", "成功"), ("過田", "重明"), ("過田", "光田"), ("過田", "田心"), ("同安", "同慶"),
        ("菜寮", "永春"), ("中正", "吉利"), ("大同", "中民"), ("大安", "平和"), ("仁義", "忠孝"), ("光榮", "光輝"),
        ("福利", "福星"), ("正義", "正德"), ("正義", "自強"), ("正義", "正安"), ("文化", "中央"), ("文化", "雙園"),
        ("錦通", "錦安"), ("長泰", "長福"), ("介壽", "萬壽"), ("介壽", "奕壽"), ("龍門", "秀江"), ("龍門", "龍濱"),
        ("永安", "永德"), ("永安", "永福"), ("溪美", "福隆"), ("溪美", "五常"), ("慈化", "慈生"), ("慈化", "碧華"),
        ("田心", "田安"), ("永德", "永盛"), ("五常", "五福"), ("慈化", "富華"), ("慈生", "慈福"), ("慈生", "慈惠"),
        ("慈生", "慈愛"),                      # [xlsx]
    ],
    # ================= 永和市 =================
    "永和": [
        ("店街", "水源"), ("上溪", "後溪"), ("網溪", "復興"), ("網溪", "中興"), ("網溪", "竹林"), ("下溪", "永成"),
        ("下溪", "大同"), ("竹林", "上林"), ("中溪", "和平"), ("上溪", "仁愛"), ("後溪", "前溪"), ("店街", "永安"),
        ("水源", "雙和"), ("秀朗", "得和"), ("中興", "永興"), ("店街", "大新"), ("後溪", "信義"), ("頂溪", "河堤"),
        ("網溪", "光復"), ("竹林", "桂林"), ("豫溪", "光明"), ("大同", "新生"), ("永成", "忠義"), ("中興", "正興"),
        ("復興", "勵行"), ("秀朗", "秀和"), ("福和", "永貞"), ("竹林", "福林"), ("潭墘", "民治"), ("潭墘", "治光"),
        ("潭墘", "潭安"), ("秀和", "民權"), ("秀朗", "民生"), ("雙和", "安和"), ("仁愛", "文化"),
        ("永成", "大安"),                      # [xlsx]
    ],
    # ================= 中和市 =================
    "中和": [
        ("積穗", "瑞穗"), ("潭墘", "安樂"), ("頂溪", "上溪"), ("頂溪", "網溪"), ("外南", "景平"), ("積穗", "嘉穗"),
        ("安樂", "安平"), ("積穗", "員山"), ("平河", "連和"), ("枋寮", "漳和"), ("秀山", "秀明"), ("頂南", "東南"),
        ("頂南", "崇南"), ("瑞穗", "壽德"), ("外南", "新南"), ("景平", "景安"), ("安樂", "安和"), ("安平", "中平"),
        ("安平", "泰安"), ("連和", "連合"), ("連和", "連城"), ("廟美", "福美"), ("秀明", "秀峰"), ("秀明", "秀水"),
        ("東南", "華南"), ("崇南", "景南"), ("瑞穗", "清穗"), ("外南", "復興"), ("新南", "和興"), ("新南", "南山"),
        ("景平", "景新"), ("景平", "景福"), ("清穗", "嘉新"), ("平河", "建和"), ("平河", "仁和"), ("瓦", "佳和"),
        ("秀山", "秀景"), ("秀水", "秀仁"), ("積穗", "民享"), ("德穗", "民生"), ("德穗", "國光"), ("壽德", "明德"),
        ("瓦", "福和"), ("仁和", "中正"), ("福美", "福真"), ("福美", "福善"), ("秀山", "秀成"), ("秀山", "秀福"),
        ("內南", "壽南"), ("華南", "忠孝"), ("頂南", "華新"), ("嘉穗", "文元"), ("建和", "碧河"), ("力行", "正行"),
        ("力行", "德行"), ("秀峰", "秀士"), ("崇南", "興南"), ("景南", "景本"), ("外南", "中興"), ("外南", "吉興"),
        ("錦和", "錦中"), ("民享", "民有"), ("員山", "員富"), ("嘉穗", "嘉慶"), ("中正", "中山"), ("錦昌", "錦盛"),
        ("壽南", "福南"), ("頂南", "正南"), ("國光", "國華"), ("安和", "安順"), ("安樂", "宜安"), ("秀成", "秀義"),
        ("瑞穗", "冠穗"),
    ],
    # ================= 新莊市 =================
    "新莊": [
        ("頭前", "思源"), ("頭前", "化成"), ("頭前", "福巷"), ("中港", "立人"), ("中港", "恆安"), ("營盤", "國泰"),
        ("中港", "中美"), ("中港", "中泰"), ("中港", "中和"), ("立人", "立德"), ("立人", "立言"), ("立人", "立功"),
        ("思源", "思賢"), ("國泰", "豐年"), ("海山", "忠孝"), ("思源", "仁愛"), ("思源", "信義"), ("思賢", "自強"),
        ("思賢", "自立"), ("思賢", "幸福"), ("中港", "中誠"), ("立功", "立志"), ("丹鳳", "龍鳳"), ("龍鳳", "富國"),
        ("龍鳳", "裕民"), ("後港", "南港"), ("後港", "西港"), ("西盛", "民安"), ("西盛", "光華"), ("丹鳳", "雙鳳"),
        ("丹鳳", "合鳳"),         ("信義", "和平"), ("民安", "民本"), ("光華", "光明"), ("幸福", "自信"),
        ("港後", "後港"), ("中港", "中隆"), ("中港", "中原"), ("中港", "中信"), ("南港", "四維"),
        ("後港", "建福"), ("中誠", "中宏"), ("中誠", "中全"), ("立言", "立泰"), ("全安", "全泰"), ("和平", "昌明"),
        ("幸福", "昌平"), ("文衡", "文聖"), ("西港", "萬安"), ("萬安", "龍安"), ("營盤", "福營"),
        ("後港", "後德"), ("後港", "建安"),
        # 八德里民國76年由港後分出、82年再由成德分出，母里以最近之成德優先
        ("成德", "八德"), ("港後", "八德"),
        ("丹鳳", "祥鳳"),                      # [xlsx]
        ("福基", "福興"),                      # [xlsx]
        # 牡丹由丹鳳、合鳳兩里各劃一部份新設（民國93，History.xlsx）
        ("丹鳳", "牡丹"), ("合鳳", "牡丹"),
    ],
    # ================= 新店市 =================
    "新店": [
        ("張北", "廣明"), ("頂城", "下成"), ("張南", "國校"), ("張南", "文中"), ("廣明", "文明"), ("張北", "新生"),
        ("張北", "中興"), ("張北", "新安"), ("百忍", "仁愛"), ("百忍", "中正"), ("寶斗", "寶興"), ("寶斗", "寶安"),
        ("公崙", "德安"), ("青潭", "美潭"), ("頂城", "太平"),         ("江陵", "忠孝"), ("江陵", "大鵬"),
        ("江陵", "和平"), ("江陵", "中山"), ("江陵", "信義"), ("江陵", "明德"), ("江陵", "大豐"), ("中山", "中央"),
        ("新生", "新德"), ("張北", "五峰"), ("明德", "國豐"), ("百忍", "福德"), ("百忍", "百福"), ("百忍", "福安"),
        ("百忍", "百和"), ("中正", "中華"),         ("新安", "忠誠"), ("柴埕", "永安"), ("德安", "明城"), ("柴埕", "安和"),
        ("玫瑰", "吉祥"), ("寶興", "寶福"),
        # 香坡由柴埕、雙城兩里各劃一部份新設（民國82，History.xlsx）
        ("柴埕", "香坡"), ("雙城", "香坡"),
        ("大鵬", "復興"),                      # [xlsx]
    ],
    # ================= 土城市 =================
    "土城": [
        ("頂埔", "頂新"), ("員林", "長風"), ("頂埔", "頂福"), ("埤林", "瑞興"), ("貨饒", "日新"), ("員林", "員仁"),
        ("清水", "清溪"), ("日新", "日和"), ("蜂廷", "平和"), ("員林", "員福"), ("員仁", "員信"), ("瑞興", "復興"),
        ("埤林", "廣福"), ("埤林", "學府"), ("埤林", "樂利"), ("貨饒", "裕生"), ("平和", "延壽"), ("平和", "安和"),
        ("蜂廷", "延吉"), ("清水", "清和"), ("清水", "永豐"), ("清水", "青雲"), ("埤林", "學成"), ("廷寮", "延和"),
        ("學府", "學士"),                      # [xlsx]
        ("廣福", "明德"),                      # [xlsx]
        ("廣福", "廣興"),                      # [xlsx]
        ("清水", "清化"),                      # [xlsx]
        ("青雲", "青山"),                      # [xlsx]
        ("員信", "員慶"),                      # [xlsx]
    ],
    # ================= 樹林市 =================
    "樹林": [
        ("樹西", "樹南"), ("樹西", "樹人"), ("樹西", "樹德"), ("潭底", "保安"), ("三多", "三福"), ("三多", "三興"),
        ("彭厝", "大同"), ("圳安", "圳福"), ("樹人", "樹興"), ("大同", "育英"),                      # [xlsx]
        ("中山", "樂山"),                      # [xlsx]
    ],
    # ================= 三峽鎮 =================
    "三峽": [
        ("嘉添", "添福"), ("圳頭", "五寮"), ("溪北", "溪東"), ("大埔", "二里"),
        # 金敏里與圳頭里於民國67年合併為金圳里（金圳為存續里，故金敏之母里以金圳優先）
        ("金圳", "金敏"), ("金圳", "圳頭"), ("插角", "金敏"), ("礁溪", "弘宇"),                      # [xlsx]
    ],
    # ================= 鶯歌鎮 =================
    "鶯歌": [
        ("鳳鳴", "永昌"), ("中湖", "永昌"), ("尖山", "永昌"), ("鳳鳴", "鳳福"), ("鳳鳴", "大湖"), ("南鶯", "建國"),
        ("鳳鳴", "鳳祥"), ("鳳祥", "永吉"),                      # [xlsx]
        ("建國", "同慶"),                      # [xlsx]
    ],
    # ================= 汐止區 =================
    "汐止": [
        ("街后", "秀峰"), ("街后", "新昌"), ("街后", "復興"), ("保安", "長安"), ("橫科", "福山"), ("橫科", "宜興"),
        ("北峰", "中興"), ("北峰", "湖光"),         ("社后", "金龍"),                      # [xlsx]
        ("社后", "湖前"),                      # [xlsx]
        ("保長", "保新"),                      # [xlsx]
        ("橋東", "建成"),                      # [查證]
        ("湖光", "湖興"),                      # [查證]
    ],
    # ================= 瑞芳區 =================
    "瑞芳": [
        ("福佳", "集賢"), ("崇文", "長樂"), ("頌德", "慶平"), ("永慶", "永德"), ("瓜山", "金山"), ("瓜山", "銅山"),
        ("吉慶", "角亭"), ("吉慶", "上天"), ("石山", "三安"), ("弓橋", "大山"), ("濂新", "長仁"),
    ],
    # ================= 淡水區 =================
    "淡水": [
        ("文化", "新生"), ("鄧公", "中興"), ("光明", "水源"), ("竹圍", "民生"), ("水里", "新興"),
        ("新興", "新義"),                      # [xlsx]
        ("新興", "新民"),                      # [xlsx]
        ("新興", "新春"),                      # [xlsx]
        ("鄧公", "學府"),                      # [xlsx]
        ("鄧公", "幸福"),                      # [xlsx]
        ("水碓", "正德"),                      # [xlsx]
        ("水碓", "北新"),                      # [xlsx]
        ("竹圍", "民權"),                      # [xlsx]
        ("沙崙", "大庄"),                      # [xlsx]
    ],
    # ================= 蘆洲市 =================
    "蘆洲": [
        ("溪墘", "樹德"), ("中路", "中原"), ("水湳", "水河"),
        ("永安", "正義"),                      # [xlsx]
        ("永安", "永康"),                      # [xlsx]
        ("永樂", "成功"),                      # [xlsx]
        ("永康", "永德"),                      # [xlsx]
        ("溪墘", "玉清"),                      # [xlsx]
        ("恆佳", "常陽"),                      # [xlsx]
        ("保佑", "保新"),                      # [xlsx]
        ("復興", "信義"),                      # [xlsx]
    ],
    # ================= 五股區 =================
    "五股": [
        ("五股", "陸一"), ("德音", "貿商"), ("更寮", "竹華"),
    ],
    # ================= 八里區 =================
    "八里": [
        ("埤頭", "大崁"),                      # [xlsx]
    ],
    # ================= 林口區 =================
    "林口": [
        ("東林", "林口"), ("東林", "西林"), ("菁湖", "湖北"), ("湖南", "南勢"),
        ("瑞平", "太平"), ("菁湖", "中湖"), ("南勢", "東勢"),
        # 民國67年 寶斗、嘉寶、瑞平三村合併為嘉寶、瑞平二村（寶斗為複數母里）
        ("瑞平", "寶斗"),
    ],
    # ================= 深坑區 =================
    "深坑": [
        ("深坑", "埔新"),                      # [xlsx]
    ],
    # ================= 石碇區 =================
    "石碇": [
        ("豐田", "彭山"), ("隆盛", "豐林"),
    ],
    # ================= 坪林區 =================
    "坪林": [
        ("漁光", "新昇"), ("漁光", "闊瀨"), ("粗窟", "金溪"), ("新昇", "上德"),
    ],
    # ================= 三芝區 =================
    "三芝": [
        ("錫板", "小坑"), ("錫板", "海尾"), ("後厝", "北勢"), ("後厝", "陽住"), ("興華", "田心"), ("興華", "車埕"),
        ("圓山", "二坪"), ("圓山", "濱海"), ("福德", "埔尾"), ("福德", "濱海"),
    ],
    # ================= 石門區 =================
    "石門": [
        ("老梅", "七股"), ("石門", "重門"), ("乾華", "竹里"),
    ],
    # ================= 平溪區 =================
    "平溪": [
        ("東勢", "紫來"),
    ],
    # ================= 貢寮區 =================
    "貢寮": [
        ("雙玉", "雙龍"), ("雙玉", "穗玉"), ("美豐", "五美"), ("美豐", "豐珠"),
    ],
    # ================= 金山區 =================
    "金山": [
        ("三和", "重光"), ("山海", "西湖"), ("山海", "萬壽"),
        ("五南", "五福"), ("五南", "南湖"), ("重和", "三和"),
        ("美田", "金美"),                      # [查證]
        # 永樂、民興民國42年由石水分出，67年再合併為永興里，故母里以永興優先
        ("永興", "永樂"), ("永興", "民興"), ("石水", "永樂"), ("石水", "民興"),
    ],
    # ================= 萬里區 =================
    "萬里": [
        ("雙興", "雙溪"), ("雙興", "太平"), ("溪底", "雙溪"), ("野柳", "國聖"), ("萬里", "北基"),
    ],
}

# 已查證「於 1993／1997 選舉前即已存在、卻在某年度 Excel 中缺漏」的里。
# 此類缺漏為選舉資料本身漏列，原設計排除於合併之外（維持白底）。
# 依需求「不要留白」，現已不再保留白底，全部改為併入母里上色，故此表留空。
SPLIT_GAP_HOLDOUT = set()

# 依 scripts/20/核实.txt 逐一查證後補入的「子里 → 母里」沿革。
# 格式：(鄉鎮市區, 母里, 子里)；母里與子里均已去除「鄉鎮市區/村里」後綴。
# 核实.txt 已於 2026-10 更新，本表為其完整轉錄（第一輪 41 條、第二輪 39 條）。
VILLAGE_SPLITS_EXTRA = [
    # ---------- 第一輪：沿革表／公開資料可查者 ----------
    ("三峽", "大埔", "二鬮"),
    ("三峽", "龍埔", "龍學"),
    ("三峽", "龍埔", "龍恩"),
    ("五股", "五福", "六福"),
    ("五股", "五股", "民義"),
    ("五股", "德音", "水碓"),
    ("五股", "德泰", "福德"),
    ("五股", "集福", "集賢"),
    ("土城", "延壽", "延祿"),
    ("土城", "永豐", "永富"),
    ("新店", "德安", "安昌"),
    ("新店", "明城", "小城"),
    ("新店", "仁愛", "建國"),
    ("新店", "永安", "新和"),
    ("新店", "永安", "永平"),
    ("新店", "太平", "美城"),
    ("新店", "塗潭", "華城"),
    ("新店", "德安", "達觀"),
    ("新店", "五峯", "長春"),
    ("新莊", "光榮", "光和"),
    ("板橋", "溪洲", "溪福"),
    ("林口", "南勢", "仁愛"),
    ("林口", "東勢", "麗園"),
    ("林口", "南勢", "麗林"),
    ("樹林", "三多", "三龍"),
    ("樹林", "西山", "中山"),
    ("樹林", "大同", "中華"),
    ("樹林", "獇寮", "光興"),
    ("樹林", "圳安", "圳民"),
    ("樹林", "圳安", "圳生"),
    ("樹林", "大同", "太順"),
    ("樹林", "西山", "山佳"),
    ("樹林", "彭厝", "彭興"),
    ("樹林", "潭底", "文林"),
    ("樹林", "樹德", "樹福"),
    ("樹林", "獇寮", "金寮"),
    ("汐止", "智慧", "大同"),
    ("汐止", "中興", "康福"),
    ("汐止", "中興", "福德"),
    ("深坑", "萬順", "萬福"),
    ("瑞芳", "爪峰", "新峰"),
    # ---------- 第二輪：核实.txt 更新後新增（1993／1997 兩年度皆缺列者）----------
    # 三重：五常、碧華、福隆皆為民國111年 SHP 中仍存在之里，故併入後可得母里底色。
    ("三重", "五常", "五順"),
    ("三重", "碧華", "仁華"),
    ("三重", "福隆", "福樂"),
    ("五股", "成功", "成泰"),
    ("土城", "柑林", "中正"),
    ("土城", "廷寮", "金城"),
    ("新莊", "中信", "中平"),
    ("新莊", "光榮", "光正"),      # 縣志「光明→光正」係三重市之光正，非新莊
    ("新莊", "富國", "富民"),
    ("新莊", "昌明", "昌信"),
    ("新莊", "昌平", "昌隆"),
    ("新莊", "民安", "民全"),
    ("新莊", "民本", "民有"),
    ("新莊", "豐年", "泰豐"),
    ("新莊", "立基", "立廷"),
    ("新莊", "龍鳳", "龍福"),
    # 板橋：浮洲、崑崙一帶於民國71年重劃，據里界推定大觀／成和／歡園三里之母里。
    ("板橋", "浮洲", "大觀"),
    ("板橋", "崑崙", "成和"),
    ("板橋", "浮洲", "歡園"),
    ("永和", "保安", "保順"),
    ("永和", "民本", "民富"),
    ("永和", "永安", "永樂"),      # 縣志載「永樂→成功」；惟成功於該二年皆無資料，解析時自然取永安
    ("永和", "秀得", "秀元"),
    # 汐止：與縣志「社后→金龍」並存；社后於該二年皆無資料，故實際併入北峰。
    ("汐止", "北峰", "金龍"),
    ("汐止", "橋東", "城中"),
    ("汐止", "厚德", "山光"),
    ("汐止", "茄苳", "崇德"),
    ("汐止", "北山", "忠山"),
    ("汐止", "宜興", "東勢"),
    ("汐止", "湖光", "湖蓮"),
    ("汐止", "北山", "環河"),
    ("汐止", "新昌", "福安"),
    ("汐止", "秀峰", "秀山"),
    ("汐止", "中興", "興福"),
    ("汐止", "八連", "長青"),
    ("泰山", "同興", "全興"),
    ("泰山", "福泰", "福興"),
    ("蘆洲", "水湳", "忠孝"),
    ("蘆洲", "樹德", "民和"),
    # ---------- 第三輪：核实.txt 二度更新後補入（原維持未知者）----------
    ("三重", "培德", "立德"),      # 1994 年自培德里劃分
    ("板橋", "溪北", "堂春"),      # 溪北里分出堂春里
    ("深坑", "土庫", "賴仲"),      # 賴仲原屬土庫大字
    ("蘆洲", "中路", "延平"),      # 與永安、長安同屬中路區
    ("蘆洲", "中路", "永安"),
    ("蘆洲", "中路", "長安"),
    ("蘆洲", "樓厝", "福安"),      # 與復興等同屬樓子厝區
]

# (鄉鎮市區, 子里) → 該里成立之西元年。用於判斷「選舉年是否已存在」：
#   選舉年 >= 成立年 → 該里當年已設，若 Excel 缺列屬資料缺漏，不併入母里。
#   選舉年 <  成立年 → 該里當年尚未分出，併入母里。
VILLAGE_SPLIT_YEARS = {
    # 依 核实.txt 查證之成立年（民國年 + 1911）
    ("三重", "立德"): 1994,
    ("三峽", "二鬮"): 1998,
    ("三峽", "龍學"): 2010,
    ("三峽", "龍恩"): 2010,
    ("五股", "六福"): 1998,
    ("五股", "水碓"): 1998,
    ("五股", "福德"): 2006,
    ("土城", "延祿"): 2001,
    ("土城", "永富"): 1994,
    ("新店", "安昌"): 1998,
    ("新店", "小城"): 1998,
    ("新店", "建國"): 1998,
    ("新店", "新和"): 1998,
    ("新店", "永平"): 1998,
    ("新店", "美城"): 1998,
    ("新店", "華城"): 2002,
    ("新店", "達觀"): 2002,
    ("板橋", "溪福"): 1994,
    ("林口", "仁愛"): 2002,
    ("林口", "麗園"): 2002,
    ("林口", "麗林"): 2002,
    ("樹林", "三龍"): 1998,
    ("樹林", "中山"): 1994,
    ("樹林", "中華"): 1998,
    ("樹林", "光興"): 1995,
    ("樹林", "圳民"): 1998,
    ("樹林", "圳生"): 1998,
    ("樹林", "太順"): 1998,
    ("樹林", "山佳"): 1994,
    ("樹林", "彭興"): 1994,
    ("樹林", "文林"): 1994,
    ("樹林", "樹福"): 1994,
    ("樹林", "金寮"): 1995,
    ("汐止", "大同"): 1998,
    ("深坑", "萬福"): 1998,
    ("瑞芳", "新峰"): 1998,
    # 第二輪新增之查證年
    ("汐止", "城中"): 2010,
    ("汐止", "湖蓮"): 2010,
    ("泰山", "全興"): 2006,
    ("泰山", "福興"): 2006,
    ("蘆洲", "民和"): 1994,
}

# 將查證後補入的沿革併入主表（略過主表已有的同一子里，避免重複）
for _t, _p, _c in VILLAGE_SPLITS_EXTRA:
    _key = (_t, _c)
    _existing = {parent for town, pairs in VILLAGE_SPLITS.items() for parent, child in pairs
                 if town == _t and child == _c}
    if _p in _existing:
        continue
    VILLAGE_SPLITS.setdefault(_t, [])
    if (_p, _c) not in VILLAGE_SPLITS[_t]:
        VILLAGE_SPLITS[_t].append((_p, _c))


_ALL_YEAR_EXISTS = {}


def all_year_exists_towns():
    """回傳 {鄉鎮市區: {里, ...}}，涵蓋各目標年度選舉資料中出現過的村里。

    用於跨年資料缺漏判斷：某里若在其他年度有資料、唯獨本年度沒有，
    多半是該年度 Excel 缺漏，而非該里當年尚未分出，不可直接併入母里。
    """
    if _ALL_YEAR_EXISTS:
        return _ALL_YEAR_EXISTS
    for cfg in DATASETS:
        if not cfg.get("village_merges", False):
            continue
        try:
            df, _, _ = load_rates(cfg)
        except Exception as exc:
            print(f"  [沿革] 無法讀取 {cfg.get('tag')} 之資料（跨年比對略過）：{exc}")
            continue
        excel_city = cfg.get("excel_city", cfg["city"])
        mask = df["縣市"].str.contains(excel_city, case=False, na=False)
        mask = mask | df["縣市"].str.strip().eq("")
        for _, r in df[mask].iterrows():
            vill = str(r["vill_core"]).strip()
            if vill:
                _ALL_YEAR_EXISTS.setdefault(r["town_core"], set()).add(vill)
    return _ALL_YEAR_EXISTS


def cross_year_gap_candidates(exists_keys, split_index):
    """回傳「沿革表中為子里、但本年度缺、其他年度有」的所有鍵（含已查證與未查證）。"""
    candidates = set()
    for town, vills in all_year_exists_towns().items():
        for vill in vills:
            if (town, vill) in exists_keys:
                continue
            if (town, vill) in split_index:
                candidates.add((town, vill))
    return candidates


def cross_year_gap_keys(exists_keys, split_index):
    """回傳應排除合併的跨年資料缺漏里（限已查證的 SPLIT_GAP_HOLDOUT）。

    其餘同型候選仍照常併入母里（不確定時沿用原行為），僅於 log 提示供人工複核。
    """
    return cross_year_gap_candidates(exists_keys, split_index) & set(SPLIT_GAP_HOLDOUT)


def build_split_index(enabled=True):
    """建立 (鄉鎮市區, 子里) → [母里, ...] 的查表；enabled=False 時回傳空表。

    同一子里可能有多個母里（例：民國67年寶斗、嘉寶、瑞平三村合併為嘉寶、瑞平，
    寶斗即有嘉寶與瑞平兩個母里），故值為清單；解析時取該年資料中確實存在的祖先。
    """
    idx = {}
    if not enabled:
        return idx
    for town, pairs in VILLAGE_SPLITS.items():
        for parent, child in pairs:
            idx.setdefault((normalize_text(town), normalize_text(child)), []).append(
                normalize_text(parent))
    return idx


def resolve_unit_name(town, vill, exists_keys, split_index, gap_keys=None,
                      year=None, split_years=None):
    """回傳該里在選舉當年所對應的行政單元名稱。

    自身名稱於當年資料中存在 → 用自身；
    不存在且為已知「由母里分出」之里 → 往上追溯母里（可連續追溯）；
    母里亦查無資料 → 回傳該里自身（視為無資料／未知）。

    複數母里時，取清單中第一個存在於當年資料者（清單已依沿革先後排序，
    合併案以存續里優先）；若皆無資料則續往上溯，並以 seen 防呆避免循環。
    gap_keys 為跨年資料缺漏之里，不予合併（維持未知）。
    year/split_years：若該里成立年 <= 選舉年，表示當年已設里、只是 Excel 缺列，
    屬資料缺漏，不予併入母里（維持未知）。
    """
    if (town, vill) in exists_keys:
        return vill
    if gap_keys and (town, vill) in gap_keys:
        return vill
    parents = split_index.get((town, vill))
    if not parents:
        return vill
    cy = (split_years or {}).get((town, vill))
    if year is not None and cy is not None and year >= cy:
        return vill
    fallback = parents[0]
    for parent in parents:
        if (town, parent) in exists_keys:
            return parent
    # 一級母里皆無資料 → 逐層上溯（多數情況僅一條鏈）
    cur, seen = fallback, {vill}
    while cur and (town, cur) not in exists_keys and cur not in seen:
        seen.add(cur)
        nxt = split_index.get((town, cur))
        if not nxt:
            break
        cur = nxt[0]
    return cur

# ===================== 繪圖參數 =====================
METERS_PER_PIXEL, MAX_SAFE_PX = 10, 32000   # 1px = 10m
VILL_LINE_PX = 1              # 村里界线宽
TOWN_LINE_PX = 4              # 乡镇市区界线宽（黑）
OUTER_LINE_PX = 6             # 市外轮廓线宽（黑）
BUF_RES, BUF_JOIN, BUF_CAP = 1, 2, 2

GRAY_COLOR = "#CCCCCC"

# ===================== 色階（35% 起，5% 間距）=====================
RATE_COLOR_STOPS = [
    [   # 第 1 组：中国国民党候选人
        (35, "#D9F6FF"),
        (40, "#A6E9FF"),
        (45, "#73D9FF"),
        (50, "#40C8FF"),
        (55, "#00C0F4"),
        (60, "#00A2E8"),
        (65, "#0080B8"),
        (70, "#006591"),
        (75, "#004B6B"),
        (80, "#003247"),
        (85, "#001F2E"),
        (100, "#010D29"),
    ],
    [   # 第 2 组：民主进步党候选人
        (35, "#E8FFE0"),
        (40, "#CEFFC2"),
        (45, "#C0FFB1"),
        (50, "#A4FF90"),
        (55, "#78FF4F"),
        (60, "#68DE45"),
        (65, "#54B337"),
        (70, "#3C8027"),
        (75, "#2B5C1C"),
        (80, "#1D3D13"),
        (85, "#0F210A"),
        (100, "#071A09"),
    ],
    [   # 第 3 组：台湾民众党候选人（图中未出现）
        (35, "#B3FFF0"),
        (40, "#00EBD1"),
        (45, "#00D9CA"),
        (50, "#00BFB2"),
        (55, "#00A89C"),
        (60, "#008080"),
        (65, "#006666"),
        (70, "#004C4C"),
        (75, "#003838"),
        (80, "#003030"),
        (85, "#002626"),
        (100, "#021F1F"),
    ],
    [   # 第 4 组：黄新党王建煊
        (0,   "#FFFFEB"),
        (35,  "#FFFFEB"),
        (40,  "#FFF8CC"),
        (45,  "#FFF0A8"),
        (50,  "#FFE780"),
        (55,  "#FFDD55"),
        (60,  "#FFF200"),
        (65,  "#E6DA00"),
        (70,  "#BFB500"),
        (75,  "#999100"),
        (80,  "#736D00"),
        (85,  "#4D4900"),
        (100, "#383502"),
    ],
]

BLOCK_WIDTH, BLOCK_HEIGHT = 170, 105
V_SPACING, H_SPACING = 38, 150
LEGEND_PADDING = 60
MAP_LEGEND_GAP = 125      # 圖例與地圖之間距
COLUMN_TITLE_GAP = 100      # 圖例欄標題（候選人）與第一個色塊的間距

# ---- 所有文字皆以 Print_word.py 方式輸出，以下字級可依需求適度調整 ----
TITLE_FONT_SIZE = 100        # 標題字級
CAND_NAME_FONT_SIZE = 84     # 圖例候選人名稱字級
LEGEND_LABEL_FONT_SIZE = 56  # 圖例數值標籤（≤45%、45~50%…）字級
NO_DATA_FONT_SIZE = 44       # 無資料說明字級

# ===================== 工具函数 =====================
# 異體字/音同字異 正規化對照（表格資料 vs 圖資用字不同，需先統一）
VARIANT_CHAR_MAP = str.maketrans({
    '濓': '濂',
    '曹': '槽',     # 坪林區石[曹] / 石槽
    '\U00025562': '槽',   # 坪林區石𕢥里（2024 源資料） / 石槽
    '磘': '窯',     # 中和區瓦[磘]・灰[磘]
    '嗂': '窯',     # 中和區灰嗂（Excel 用字）/ 灰[磘]（圖資）
    '獇': '羌',     # 樹林區[獇]寮 / 羌寮
    '舘': '館',     # 板橋區公舘 / 三峽區永舘
    '廍': '部',     # 永和區新廍 / 新部
    '峯': '峰',     # 土城區峯廷 / 新店區五峯 / 瑞芳區爪峯
    '脚': '腳',     # 萬里區崁脚 / 崁腳
})

def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'M')
    s = re.sub(r'[\uFE00-\uFE0F\U000E0100-\U000E01EF]', '', s)
    s = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', s)
    # 圖資以方括號標註疑難字（如 瓦[磘]里），括號本身非地名一部分，去除
    s = s.replace("[", "").replace("]", "")
    s = s.translate(VARIANT_CHAR_MAP)
    return s

def strip_town_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[鄉鎮市區]$", "", normalize_text(s))

def strip_village_suffix(s):
    return "" if pd.isna(s) else re.sub(r"[村里]$", "", normalize_text(s))

def get_color_by_value(val, stops):
    if val is None or np.isnan(val):
        return None
    if val < 0:
        return None
    for upper, hx in stops:
        if val <= upper:
            return hx
    return stops[-1][1]

def hex2rgb(hx):
    h = hx.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)

def text_width(font, txt):
    try:
        bbox = font.getbbox(txt)
    except AttributeError:
        bbox = font.getmask(txt).getbbox()
    return (bbox[2] - bbox[0]) if bbox else 0

def resolve_shp():
    for p in SHP_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("找不到村里界 SHP：" + "、".join(SHP_CANDIDATE_PATHS))

# ===================== 文字圖片生成（仿 Print_word.py） =====================
def render_text_image(text_lines, font_size=64, dpi=100):
    """以 Print_word.py 方式：Matplotlib 繪字 → OpenCV 二值化 → 透明背景。

    回傳 PIL RGBA（文字不透明黑、背景透明），可直接 paste 到地圖。
    """
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    font_name = None
    for n in ["PMingLiU", "MingLiU", "新細明體", "Microsoft JhengHei", "SimHei", "SimSun"]:
        if n in names:
            font_name = n
            break
    # 用字型鏈回退：中文字用 CJK 字型，缺少的符號（如 ≤ U+2264）由 DejaVu Sans 補
    font_family = [font_name, "DejaVu Sans"] if font_name else "DejaVu Sans"

    # 測量文字尺寸
    fig_temp = plt.figure(figsize=(1, 1), dpi=dpi)
    ax_temp = fig_temp.add_subplot(111)
    ax_temp.axis("off")
    fig_temp.canvas.draw()
    renderer = fig_temp.canvas.get_renderer()
    line_widths = []
    line_heights = []
    for line in text_lines:
        t = ax_temp.text(0, 0, line, fontsize=font_size, fontfamily=font_family)
        bbox = t.get_window_extent(renderer=renderer)
        line_widths.append(bbox.width)
        line_heights.append(bbox.height)
    plt.close(fig_temp)

    line_spacing = font_size * 1.5
    total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing
    max_width = max(line_widths)
    PAD = 20
    fig_w_pt = max_width + 2 * PAD
    fig_h_pt = total_height + 2 * PAD

    fig = plt.figure(figsize=(fig_w_pt / dpi, fig_h_pt / dpi), dpi=dpi, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w_pt)
    ax.set_ylim(0, fig_h_pt)
    ax.set_facecolor("white")
    ax.axis("off")

    y = PAD + total_height
    for i, line in enumerate(text_lines):
        x = (fig_w_pt - line_widths[i]) / 2
        y -= line_heights[i]
        ax.text(x, y, line, fontsize=font_size, ha="left", va="bottom",
                fontfamily=font_family, color="black")
        y -= line_spacing

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, facecolor="white", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    _, bin_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    h, w = bin_img.shape
    result = np.zeros((h, w, 4), dtype=np.uint8)   # B,G,R = 0（黑字）
    result[:, :, 3] = np.where(bin_img == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))

_TEXT_IMG_CACHE = {}

def render_text_image_cached(text_lines, font_size):
    """快取版 render_text_image：相同文字與字級只渲染一次（Print_word.py 方式）。"""
    key = (tuple(text_lines), font_size)
    if key not in _TEXT_IMG_CACHE:
        _TEXT_IMG_CACHE[key] = render_text_image(text_lines, font_size=font_size)
    return _TEXT_IMG_CACHE[key]

def blit_rgba(base_img, rgba_img, xy):
    """將透明底 RGBA 文字圖以 alpha 為遮罩貼到 base_img 的 (x, y)。"""
    base_img.paste(rgba_img, (int(xy[0]), int(xy[1])), rgba_img.getchannel("A"))

# ===================== 读 SHP =====================
SHP_PATH = resolve_shp()
gdf_all = gpd.read_file(SHP_PATH, encoding="UTF-8")
if gdf_all.crs is None:
    gdf_all.crs = "EPSG:4326"
if gdf_all.crs.is_geographic:
    gdf_all = gdf_all.to_crs(epsg=3826)

for c in ["COUNTYNAME", "TOWNNAME", "VILLNAME"]:
    if c not in gdf_all.columns:
        raise ValueError(f"SHP缺失必要字段：{c}")

# ===================== 读取高雄格式得票 Excel，计算得票率 =====================
def _norm_text(v):
    """正規化：NaN / 'nan'(不區分大小寫) 一律視為空字串（缺失）。"""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s

def load_rates(cfg):
    excel_path = cfg["excel"]
    df = pd.read_excel(excel_path, sheet_name=cfg["sheet"], header=cfg.get("header", 0))
    df.columns = [str(c) for c in df.columns]

    # 模式 ④：地名在單列完整路徑（如「臺北縣板橋市留侯里」），得票率為小數
    if cfg.get("loc_col") is not None and (cfg.get("rate_col") is not None or cfg.get("rate_cols")):
        loc_idx = str(cfg["loc_col"])
        rate_mult = cfg.get("rate_multiplier", 100)
        cand_names = cfg.get("legend_names", [""])
        rc_list = cfg.get("rate_cols") or [cfg["rate_col"]]
        rnames = []
        for i, rc in enumerate(rc_list):
            rname = f"rate_{cand_names[i]}" if i < len(cand_names) else f"rate{i + 1}"
            rnames.append(rname)
            df[rname] = pd.to_numeric(df[str(rc)], errors="coerce") * rate_mult

        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.+)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""

        parsed = df[loc_idx].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_names, rnames

    # 支援三種來源（原有邏輯）：
    #  ① 得票率專用檔：欄位直接是「<政黨>得票率」
    #  ② 高雄格式全量檔：<候選人>得票數 ＋ 有效票數A，再除以 A×100 得得票率
    #  ③ 指定候選人欄位（cfg["cand_columns"]）：欄名即候選人、值為得票率(%)
    #  ⑤ 鄉鎮市區層級檔（cfg["full_loc_col"]）：單一欄含完整路徑（如「臺北縣板橋市」），無村里資料
    pct_cols = [c for c in df.columns if c.endswith("得票率")]
    vote_cols = [c for c in df.columns if c.endswith("得票數")]
    given_cands = cfg.get("cand_columns")

    # 字串百分比（如 "51.54%"）→ 數值
    def _to_pct_numeric(v):
        if v is None:
            return np.nan
        s = str(v).strip()
        if s.endswith("%"):
            s = s[:-1]
        return pd.to_numeric(s, errors="coerce")

    if cfg.get("full_loc_col"):
        cand_cols = list(cfg.get("cand_columns") or pct_cols or vote_cols)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            df[c] = df[c].apply(_to_pct_numeric)
        import re as _re
        def _parse_loc(val):
            s = _norm_text(val)
            m = _re.match(r'^(.*?[縣市])(.*?[鄉鎮市區])(.*)$', s)
            if m:
                return _norm_text(m.group(1)), _norm_text(m.group(2)), _norm_text(m.group(3))
            return "", "", ""
        parsed = df[cfg["full_loc_col"]].apply(_parse_loc)
        df["縣市"] = parsed.apply(lambda t: t[0])
        df["鄉鎮市區"] = parsed.apply(lambda t: t[1])
        df["區里"] = parsed.apply(lambda t: t[2])
        df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
        df["vill_core"] = df["區里"].apply(strip_village_suffix)
        return df, cand_cols, rate_cols

    if given_cands:
        cand_cols = list(given_cands)
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    elif pct_cols:
        cand_cols = pct_cols
        rate_cols = []
        for c in cand_cols:
            rate_cols.append(c)
            # 支援字串百分比（如 "51.54%"）：先去 % 再轉數值
            sample = df[c].dropna().head(5).astype(str)
            if sample.str.contains("%").any():
                df[c] = pd.to_numeric(
                    df[c].astype(str).str.replace("%", "", regex=False),
                    errors="coerce")
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    elif vote_cols:
        if "有效票數A" not in df.columns:
            raise ValueError(f"{excel_path} 缺少『有效票數A』欄位")
        cand_cols = vote_cols
        A = pd.to_numeric(df["有效票數A"], errors="coerce")
        rate_cols = []
        for i, c0 in enumerate(cand_cols):
            rname = f"rate{i + 1}"
            rate_cols.append(rname)
            df[rname] = pd.to_numeric(df[c0], errors="coerce") / A * 100.0
    else:
        raise ValueError(f"{excel_path} 找不到『得票率』或『得票數』欄位")

    df["縣市"] = df[cfg.get("col_city", "選舉區別")].apply(_norm_text)
    df["鄉鎮市區"] = df[cfg.get("col_town", "鄉(鎮、市、區)別")].apply(_norm_text)
    df["區里"] = df[cfg.get("col_vill", "村里別")].apply(_norm_text)

    df["town_core"] = df["鄉鎮市區"].apply(strip_town_suffix)
    df["vill_core"] = df["區里"].apply(strip_village_suffix)
    return df, cand_cols, rate_cols

# ===================== 精确 + 同乡镇最相似模糊匹配 =====================
MIN_SIMILARITY = 0.5

def _char_pairs(a, b):
    """回傳逐字對應 (a字, b字)；長度不同時補上長度差異標記。"""
    pairs = []
    la, lb = len(a), len(b)
    if la != lb:
        return None  # 長度不同：不視為異體字匹配
    for ca, cb in zip(a, b):
        pairs.append((ca, cb))
    return pairs

# 異體字模糊匹配表（模糊候選彼此間「單字異體」的許可字對）
# 格式：同一組內的字互為異體；用於 fuzzy（相似度≥50% 且逐字僅一案異體）
VARIANT_FUZZY_GROUPS = [
    {"峯", "峰"},   # 瑞芳區爪峯/爪峰
    {"舘", "館"},   # 板橋區公舘/公館、三峽區永舘/永館
    {"磘", "窯"},   # 中和區瓦磘/瓦窯
    {"獇", "羌"},   # 樹林區獇寮/羌寮
    {"曹", "槽"},   # 坪林區石曹/石槽
    {"脚", "腳"},
]


def is_variant_fuzzy(a, b):
    """判斷兩個（core）里名是否屬『異體字模糊匹配』：
    相似度 ≥ MIN_SIMILARITY，且逐字比較中『最多一個字不相等，且該字對落在異體字組』。
    """
    if SequenceMatcher(None, a, b).ratio() < MIN_SIMILARITY:
        return False
    pairs = _char_pairs(a, b)
    if pairs is None:
        return False  # 長度不同（字數差）不視為異體字模糊
    diffs = [(ca, cb) for ca, cb in pairs if ca != cb]
    if len(diffs) != 1:
        return False
    ca, cb = diffs[0]
    for group in VARIANT_FUZZY_GROUPS:
        if ca in group and cb in group:
            return True
    return False

def fuzzy_lookup(town, vill, by_key, by_town):
    if not town or not vill:
        return None, None, "none"
    key = (town, vill)
    if key in by_key:
        return vill, by_key[key], "exact"
    best_v, best_val, best_ratio = None, None, -1.0
    for cand_v, val in by_town.get(town, []):
        ratio = SequenceMatcher(None, vill, cand_v).ratio()
        if ratio > best_ratio:
            best_ratio, best_v, best_val = ratio, cand_v, val
    if best_val is None or best_ratio < MIN_SIMILARITY:
        return None, None, "none"
    # 只有逐字差異恰好一個字且該字對屬異體字組，才接受模糊匹配；
    # 其餘「雖然相似度達 50% 但並非異體字」的情形，視為無資料（白底）。
    if not is_variant_fuzzy(vill, best_v):
        return None, None, "none"
    return best_v, best_val, f"fuzzy:{best_v}({best_ratio:.2f})"

# ===================== 逐張地圖繪製 =====================
def draw_legend_on(final_img, x0, y0, cand_names, stops_list, col_width, max_label_w, start_tier=0):
    """圖例：色塊用 ImageDraw 繪製；所有文字以 Print_word.py 方式（render_text_image）貼上。"""
    draw_obj = ImageDraw.Draw(final_img)
    n = len(cand_names)
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(n)]
    name_h = max(
        (render_text_image_cached([nm], CAND_NAME_FONT_SIZE).height for nm in cand_names),
        default=0,
    )
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_text_image_cached([cand_names[col_idx]], CAND_NAME_FONT_SIZE)
            blit_rgba(final_img, nm_img, (x_start + (BLOCK_WIDTH - nm_img.width) / 2, y0))
        for i, (upper, color_hex) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 8,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))

def get_label_text(upper, prev=None, is_first=False, is_last=False):
    if is_last:
        return f"≥{prev}%"
    if is_first and prev <= 35:
        return f"≤{upper}%"
    if prev is None:
        return f"≤{upper}%"
    return f"{prev}~{upper}%"

def make_map(cfg):
    print("=" * 62)
    print(f"  組別：{cfg['tag']}")
    print("=" * 62)

    gdf_nt = gdf_all[gdf_all["COUNTYNAME"].astype(str).str.contains(cfg["city"], na=False)].copy()
    if len(gdf_nt) == 0:
        raise ValueError(f"SHP 中未找到 {cfg['city']} 數據")

    gdf_nt["town_core"] = gdf_nt["TOWNNAME"].apply(strip_town_suffix)
    gdf_nt["vill_core"] = gdf_nt["VILLNAME"].apply(strip_village_suffix)

    df_vote, cand_cols, rate_cols = load_rates(cfg)
    # 納入 {city} 資料；縣市欄缺失(NaN / 'nan' 不區分大小寫)者視為同屬該縣市，一併納入
    # Excel 中的縣市名稱可能與 SHP 不同（如 SHP 為新北市、舊檔為臺北縣），用 excel_city 指定
    excel_city = cfg.get("excel_city", cfg["city"])
    city_mask = df_vote["縣市"].str.contains(excel_city, case=False, na=False)
    missing_mask = df_vote["縣市"].str.strip().eq("")
    df_vote = df_vote[city_mask | missing_mask].copy()

    n_cand = len(cand_cols)
    cand_names = cfg.get("legend_names", [c[:-3] for c in cand_cols])   # 圖例欄名稱＝候選人
    if cfg.get("color_schemes"):
        stops_list = cfg["color_schemes"]
    else:
        stops_list = [RATE_COLOR_STOPS[i % len(RATE_COLOR_STOPS)] for i in range(n_cand)]

    vote_dict = {
        (r["town_core"], r["vill_core"]): tuple(r[c] for c in rate_cols)
        for _, r in df_vote.iterrows()
    }
    vote_by_town = {}
    raw_vote_by_town = {}
    for (t, v), vals in vote_dict.items():
        vote_by_town.setdefault(t, []).append((v, vals))
    for _, r in df_vote.iterrows():
        raw_vote_by_town.setdefault(r["town_core"], {})[r["vill_core"]] = r["區里"]

    # 鄉鎮市區層級資料：村里界無對應（Excel 僅到鄉鎮層級），以鄉鎮數值套用全鄉鎮村里
    town_level_only = bool(df_vote["vill_core"].str.strip().eq("").all())
    town_level_dict = {
        t: vals for (t, v), vals in vote_dict.items() if not v
    }

    # 村里沿革合併：某里在選舉當年尚未由母里分出者 → 該里與母里視為同一行政單元
    split_index = build_split_index(cfg.get("village_merges", False))
    if split_index:
        exists_keys = {k for k in vote_dict if k[1]}
        year = cfg.get("year")
        candidates = cross_year_gap_candidates(exists_keys, split_index)
        year_gaps = {
            k for k in candidates
            if year is not None and VILLAGE_SPLIT_YEARS.get(k) is not None
            and year >= VILLAGE_SPLIT_YEARS[k]
        }
        gap_keys = (candidates & set(SPLIT_GAP_HOLDOUT)) | year_gaps
        merge_keys = sorted(candidates - gap_keys)
        if merge_keys:
            print(f"  ◇ 跨年缺漏候選（已查證當年尚未設里，併入母里）{len(merge_keys)} 里："
                  + "、".join(f"{t}{v}" for t, v in merge_keys))
        if gap_keys:
            print(f"  ⚠ 資料缺漏（當年已設里卻缺列，維持未知不合併）{len(gap_keys)} 里：")
            for town, vill in sorted(gap_keys):
                print(f"    - {town} {vill}（母里：{'、'.join(split_index[(town, vill)])}）")
        gdf_nt["unit_core"] = [
            resolve_unit_name(t, v, exists_keys, split_index, gap_keys,
                              year=year, split_years=VILLAGE_SPLIT_YEARS)
            for t, v in zip(gdf_nt["town_core"], gdf_nt["vill_core"])
        ]
        gdf_nt["merged_into"] = np.where(
            gdf_nt["unit_core"] != gdf_nt["vill_core"], gdf_nt["unit_core"], "")
    else:
        gdf_nt["unit_core"] = gdf_nt["vill_core"]
        gdf_nt["merged_into"] = ""

    def process_row(r):
        town, vill, unit = r["town_core"], r["vill_core"], r["unit_core"]
        matched_vill, vals, excel_mt = fuzzy_lookup(town, unit, vote_dict, vote_by_town)
        if vals is None and town in town_level_dict:
            vals = town_level_dict[town]
            excel_mt = f"town:{town}"
        if vals is None:
            vals = tuple(np.nan for _ in range(n_cand))
            return pd.Series(list(vals) + ["none"])
        if unit != vill:
            excel_mt = f"merged:{unit}"
        elif excel_mt == "exact":
            raw_excel = raw_vote_by_town.get(town, {}).get(matched_vill)
            raw_shp = str(r["VILLNAME"])
            if raw_shp != raw_excel:
                excel_mt = f"variant:{raw_excel}"
        return pd.Series(list(vals) + [excel_mt])

    assign_cols = rate_cols + ["match_type"]
    gdf_nt[assign_cols] = gdf_nt.apply(process_row, axis=1)

    # 有任一候選人得票率可計算，即納入（NaN 以 0 計，不影響其餘候選人） 
    has_data = gdf_nt[rate_cols].notna().any(axis=1)
    gdf_with_data = gdf_nt[has_data].copy()
    gdf_no_data = gdf_nt[~has_data].copy()

    if len(gdf_with_data) == 0:
        raise ValueError(f"{cfg['excel']} 沒有任一村里資料匹配成功。")

    def pick_fill_color(row):
        vals = [row[c] if not np.isnan(row[c]) else 0.0 for c in rate_cols]
        i = int(np.argmax(vals))
        return get_color_by_value(vals[i], stops_list[i])

    gdf_with_data["fill_hex"] = gdf_with_data.apply(pick_fill_color, axis=1)
    gdf_with_data["fill_hex"] = gdf_with_data["fill_hex"].fillna(GRAY_COLOR)

    # ---- 計算圖例起點（所有村里中最低的領先者得票率，向下取整到 10 的倍數） ----
    all_win_rates = []
    for _, row in gdf_with_data.iterrows():
        vals = [row[c] for c in rate_cols if not np.isnan(row[c])]
        if vals:
            all_win_rates.append(max(vals))
    min_win_rate = min(all_win_rates) if all_win_rates else 0
    legend_start_tier = int(min_win_rate // 5) * 5

    # ---- 統計報告 ----
    exact_cnt = int((gdf_nt["match_type"] == "exact").sum())
    variant_cnt = int(gdf_nt["match_type"].str.startswith("variant", na=False).sum())
    fuzzy_cnt = int(gdf_nt["match_type"].str.startswith("fuzzy", na=False).sum())
    merged_cnt = int(gdf_nt["match_type"].str.startswith("merged", na=False).sum())
    none_cnt = int((gdf_nt["match_type"] == "none").sum())
    cnt_valid = int(has_data.sum())
    no_data_cnt = int((~has_data).sum())
    # 合併後實際行政單元數（同鄉鎮內合併為一單元者只算一次）
    unit_cnt = int(gdf_nt.loc[has_data, ["town_core", "unit_core"]].drop_duplicates().shape[0])

    print(f"  SHP 村里要素     : {len(gdf_nt)}")
    print(f"  Excel 有效記錄   : {len(df_vote)}   (候選人/政黨 {n_cand} 位)")
    print(f"  精確匹配         : {exact_cnt}")
    print(f"  異體字匹配       : {variant_cnt}")
    print(f"  模糊匹配         : {fuzzy_cnt}")
    if split_index:
        print(f"  沿革合併         : {merged_cnt}（該里當年尚未由母里分出）")
    print(f"  無候選(無匹配)   : {none_cnt}")
    print(f"  有資料           : {cnt_valid}")
    print(f"  無資料/部分缺失  : {no_data_cnt}")
    if split_index:
        print(f"  當年行政單元(里) : {unit_cnt} 個（合併後）")

    # 簡要說明異體字 / 模糊匹配情形
    for key, label in [("variant", "異體字匹配（SHP 用字與 Excel 不同，經正規化後配對）"),
                       ("fuzzy", "模糊匹配（同鄉鎮內字串相似度達 50% 以上）"),
                       ("merged", "沿革合併（該里當年尚未由母里分出，與母里同一單元）")]:
        sub = gdf_nt[gdf_nt["match_type"].str.startswith(key, na=False)]
        if len(sub) == 0:
            continue
        print(f"  ■ {label}：共 {len(sub)} 個")
        for _, r in sub.head(8).iterrows():
            if key == "variant":
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type'].split(':', 1)[1]}")
            else:
                print(f"      {r['TOWNNAME']} {r['VILLNAME']}  <->  {r['match_type']}")
        if len(sub) > 8:
            print(f"      ... 其餘 {len(sub) - 8} 個略")

    # 合併後仍無資料者：母里沿革未查到 → 未知
    no_data_by_town = gdf_no_data.groupby("TOWNNAME").size().sort_values(ascending=False)
    if len(no_data_by_town):
        print("【無資料區域統計】（母里沿革未查得，暫列為未知）")
        for town, cnt2 in no_data_by_town.items():
            names = [("<無名>" if pd.isna(v) else str(v)) for v in gdf_no_data[gdf_no_data["TOWNNAME"] == town]["VILLNAME"]]
            print(f"  {town}: {cnt2} 個村里 — {'、'.join(names)}")
        nan_cnt = int(gdf_no_data["VILLNAME"].isna().sum())
        if nan_cnt:
            print(f"  ※ 其中 {nan_cnt} 個 SHP 村里名稱為空值(NaN)，無從比對，以灰色顯示")

    # ===================== 繪圖 =====================
    # 無資料村里著色規則：
    #   SHP 有、Excel 沒有 —— 有具體地名者（當時因行政沿革尚未設立）→ 白色
    #   VILLNAME 為 NaN（無名，多為荒島）→ 灰色
    named_missing = gdf_no_data["VILLNAME"].apply(
        lambda v: (not pd.isna(v)) and (str(v).strip() != "")
    )
    gdf_no_data["fill_hex"] = np.where(named_missing, "#FFFFFF", GRAY_COLOR)

    # 將無資料/NaN 村里也納入地圖，新北市全境皆繪製
    gdf_plot = pd.concat([gdf_with_data, gdf_no_data])
    gdf_plot["fill_hex"] = gdf_plot["fill_hex"].fillna(GRAY_COLOR)

    minx, miny, maxx, maxy = gdf_plot.total_bounds
    MAP_PAD_FRAC = 0.03
    pad_x = (maxx - minx) * MAP_PAD_FRAC
    pad_y = (maxy - miny) * MAP_PAD_FRAC
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    w_px = int(np.ceil((xlim[1] - xlim[0]) / METERS_PER_PIXEL))
    h_px = int(np.ceil((ylim[1] - ylim[0]) / METERS_PER_PIXEL))
    if w_px > MAX_SAFE_PX or h_px > MAX_SAFE_PX:
        raise Exception(f"圖像尺寸超限 {w_px}×{h_px}，請調大 METERS_PER_PIXEL")

    DPI = 100
    PX2PT = 72.0 / DPI

    fig = plt.figure(figsize=(w_px / DPI, h_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("#FFFFFF")

    town_half_m = TOWN_LINE_PX * METERS_PER_PIXEL / 2
    outer_half_m = OUTER_LINE_PX * METERS_PER_PIXEL / 2
    city_geom = gdf_plot.geometry.union_all()

    # ① 村里填色（無邊）
    gdf_plot.plot(
        ax=ax, facecolor=gdf_plot["fill_hex"].tolist(),
        edgecolor='none', linewidth=0, antialiased=False, legend=False
    )

    # ② 村里黑線（1px）：沿「當年行政單元」畫線，合併為同一單元者其間不畫界線
    village_lines = gdf_plot.dissolve(by=["town_core", "unit_core"]).boundary.union_all()
    if not village_lines.is_empty:
        gpd.GeoSeries([village_lines]).plot(
            ax=ax, edgecolor='black', facecolor='none',
            linewidth=VILL_LINE_PX * PX2PT, antialiased=False, zorder=5
        )

    # ③ 鄉鎮市區黑線（4px 黑帶）
    town_lines = gdf_plot.dissolve(by="town_core").boundary.union_all()
    if not town_lines.is_empty:
        town_band = town_lines.buffer(
            town_half_m, resolution=BUF_RES,
            join_style=BUF_JOIN, cap_style=BUF_CAP
        ).intersection(city_geom)
        if not town_band.is_empty:
            gpd.GeoSeries([town_band]).plot(
                ax=ax, facecolor='black', edgecolor='none',
                linewidth=0, antialiased=False, zorder=9
            )

    # ④ 市外輪廓（6px 黑帶）
    outer = city_geom.boundary.buffer(
        outer_half_m, resolution=BUF_RES,
        join_style=BUF_JOIN, cap_style=BUF_CAP
    )
    if not outer.is_empty:
        gpd.GeoSeries([outer]).plot(
            ax=ax, facecolor='black', edgecolor='none',
            linewidth=0, antialiased=False, zorder=11
        )

    ax.axis("off")
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, pad_inches=0, bbox_inches=None, facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)

    img_bgr = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # ===================== 顏色量化（分塊處理）=====================
    allowed_hex = {"#FFFFFF", "#000000", GRAY_COLOR}
    for stops in stops_list:
        allowed_hex.update(hx for _, hx in stops)
    allowed_rgb_255 = np.array([hex2rgb(hx) for hx in allowed_hex]).astype(np.float32) * 255

    pixels = img_rgb.reshape(-1, 3).astype(np.float32)
    n_pixels = pixels.shape[0]
    CHUNK_SIZE = 500_000
    quantized_flat = np.empty((n_pixels, 3), dtype=np.uint8)

    for start in range(0, n_pixels, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, n_pixels)
        chunk = pixels[start:end]
        min_dist = np.full(chunk.shape[0], np.inf, dtype=np.float32)
        min_idx = np.zeros(chunk.shape[0], dtype=np.int32)
        for i in range(allowed_rgb_255.shape[0]):
            diff = chunk - allowed_rgb_255[i]
            d = np.sqrt((diff * diff).sum(axis=1))
            mask = d < min_dist
            min_dist[mask] = d[mask]
            min_idx[mask] = i
        quantized_flat[start:end] = allowed_rgb_255[min_idx].astype(np.uint8)

    quantized = quantized_flat.reshape(img_rgb.shape)

    # ===================== 文字圖像（全部以 Print_word.py 方式產生） =====================
    pil_img = Image.fromarray(quantized)
    W, H = pil_img.size

    title_img = render_text_image_cached(cfg["title_lines"], TITLE_FONT_SIZE) if cfg.get("title_lines") else None

    # ---- 圖例只顯示從最低領先得票率色階起的色塊 ----
    legend_stops_list = [
        [(u, c) for u, c in stops if u > legend_start_tier]
        for stops in stops_list
    ]

    # 圖例欄標題（候選人名稱）
    name_imgs = [render_text_image_cached([nm], CAND_NAME_FONT_SIZE) for nm in cand_names]
    name_h = max((im.height for im in name_imgs), default=0)

    # 各候選人欄的色階標籤
    label_img_cols = []
    for stops in legend_stops_list:
        col_imgs = []
        for i, (u, _) in enumerate(stops):
            txt = get_label_text(u, stops[i - 1][0] if i > 0 else legend_start_tier, is_first=(i == 0), is_last=(i == len(stops) - 1))
            col_imgs.append(render_text_image_cached([txt], LEGEND_LABEL_FONT_SIZE))
        label_img_cols.append(col_imgs)
    max_label_w = max([im.width for col in label_img_cols for im in col] or [0])

    col_width = BLOCK_WIDTH + 8 + max_label_w
    n_cols = len(legend_stops_list)
    total_legend_w = col_width * n_cols + H_SPACING * (n_cols - 1)
    max_n = max((len(s) for s in legend_stops_list), default=0)
    legend_h = name_h + COLUMN_TITLE_GAP + max_n * (BLOCK_HEIGHT + V_SPACING) - V_SPACING

    # ===================== 畫布佈局（右側面板：標題 → 圖例） =====================
    group_w = (n_cols - 1) * (col_width + H_SPACING) + BLOCK_WIDTH
    legend_x = W + 115   # 圖例第一欄從地圖右緣 115px 處開始
    TITLE_GAP = 70
    panel_content_h = ((title_img.height + TITLE_GAP) if title_img else 0) + legend_h

    # 標題以圖例群組中心為準置中
    title_x = legend_x + (group_w - title_img.width) / 2 if title_img else legend_x
    title_right = title_x + (title_img.width if title_img else group_w)

    # 畫布右界以「標題最右端 + 225px」為基準，並確保圖例完整放入
    new_W = int(max(title_right + 225, legend_x + group_w + LEGEND_PADDING))
    right_panel_w = new_W - W
    new_H = max(H, panel_content_h + 2 * LEGEND_PADDING)

    final_img = Image.new("RGB", (new_W, new_H), (255, 255, 255))
    final_img.paste(pil_img, (0, (new_H - H) // 2))

    # 右側面板：標題對齊圖例區域（以圖例群組中心為準）置中
    py = LEGEND_PADDING
    if title_img:
        blit_rgba(final_img, title_img, (title_x, py))
        py += title_img.height + TITLE_GAP

    draw_legend_on(final_img, legend_x, py, cand_names, legend_stops_list, col_width, max_label_w, start_tier=legend_start_tier)

    final_img.save(cfg["out"])
    print(f"  輸出: {cfg['out']}  ({final_img.width}×{final_img.height}px)")
    print(f"     主圖基於 {len(gdf_with_data)} 個有資料村里繪製；色階從 {legend_start_tier}% 起\n")

# ===================== 主程式 =====================
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None   # 可指定關鍵字只生成部分地圖，如：py Converge_to_map.py 2005
    for cfg in DATASETS:
        if key and (key not in cfg["excel"]) and (key not in cfg["tag"]):
            continue
        make_map(cfg)
    print("全部完成。")