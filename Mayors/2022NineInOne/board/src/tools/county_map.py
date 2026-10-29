# -*- coding: utf-8 -*-
"""county_map.py —— 2022 九合一縣市長選舉 22 縣市的統一配置表。

★ 唯一真值來源：縣市繁簡對照、地圖/徽章/資料檔對應、政黨色階、候選人黨籍。
  建置器（_gen_boards.py）與去背器（build_assets.py）都讀這裡，不要各自寫一份。

縣市 key 一律用「繁體全稱」（臺北市 / 新北市 / 連江縣 …），與 map/ 地圖檔名、
Wikipedia.txt、SHP 圖資同一套用字。徽章檔名是簡體/簡稱，在這裡逐一對應。
"""
import os

# ---------------------------------------------------------------- 路徑
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# board/ 專案根
DATA_DIR = os.path.join(os.path.dirname(ROOT), "data")          # 22 縣市 xlsx + Wikipedia.txt
MAP_VILLAGE = os.path.join(os.path.dirname(ROOT), "map", "village")
MAP_TOWN = os.path.join(os.path.dirname(ROOT), "map", "town")
SEAL_SRC = r"D:\Windows\TaiwanElection\Video\assets\share\徽章"  # 縣徽原圖（簡體/簡稱檔名）
COLOR_TXT = r"D:\Windows\TaiwanElection\Precident\color.txt"
# 低得票率候選人的圖片框占位圖（灰階人形剪影，810×1080）：
# 排名 ≥ 3 且得票率 < 3% 的人一律用它，見 election-model.js#usesLowPctPhoto。
# build_assets.py 原樣複製到 dist/assets/share/low_pct.png（邏輯名 assets/low_pct.png）。
PHOTO_LOW_PCT = r"D:\Windows\TaiwanElection\Video\assets\candidate\得票率过低.png"

# 政黨色階組別（color.txt 由上而下）：0 無黨籍灰 / 1 KMT 藍 / 2 DPP 綠
#   3 新黨黃 / 4 宋橘 / 5 TPP 青綠 / 6 時代力量黃。小黨一律 0（灰）。
PARTY_GROUP = {
    "中國國民黨": 1, "民主進步黨": 2, "台灣民眾黨": 5,
    "新黨": 3, "親民黨": 4, "無黨籍": 0,
    "時代力量": 6,
}
# 候選人 → 政黨（簡稱 key，用於找色階與政黨全稱）。
# ★ 與 script/Draw_CountyMayor_2022.py 的 CAND_PARTY 同源（組別索引一致）。
PARTY_SHORT_BY_GROUP = {0: "無黨籍", 1: "中國國民黨", 2: "民主進步黨",
                         3: "新黨", 4: "親民黨", 5: "台灣民眾黨",
                         6: "時代力量"}

# 沒有預設政黨色（Theme.parties 裡沒有對應 key）的政黨，在這裡給主色。
# 建置器會把它寫成 candidates[].color，引擎用 Theme.fromColor 推導亮暗階與地圖色階；
# 沒列在這裡的政黨完全不變（走原政黨色表或無黨籍灰）。
#   時代力量：黨識別色 #FFBE00（亮黃）。★ 這黨沒有黨徽素材，故意不進
#   build_party_marks.MARKS / slide.js 的 PARTIES_WITH_MARK，主卡位置退回純色塊。
PARTY_COLOR = {
    "時代力量": "#FFBE00",
}

# 候選人 → 政黨組別（94 人，繁簡名以 Excel 列名為準）。
CAND_PARTY = {
    "侯友宜": 1, "劉建國": 2, "劉復嵐": 0, "劉櫂豪": 2,
    "吳炳輝": 0, "吳盛聖": 0, "周春米": 2, "周江杰": 2,
    # 苗栗縣宋國鼎：2022 代表時代力量參選（原記 0 無黨籍，誤；6 ＝ 時代力量）
    "唐新民": 0, "宋國鼎": 6, "張善政": 1, "張家豪": 0,
    "張麗善": 1, "徐定禎": 2, "徐榛蔚": 1, "施奉先": 0,
    "曹爾元": 1, "曾國民": 0, "曾尹儷": 0, "朱振東": 0,
    "朱紀瑋": 0, "李俊俋": 2, "李問": 2, "李應文": 0,
    "李驥羣": 0, "林佳瑜": 0, "林佳龍": 2, "林姿妙": 1,
    "林志錦": 0, "林義豐": 0, "林耕仁": 1, "柯志恩": 1,
    "楊文科": 1, "楊鎮浯": 1, "江聰淵": 2, "沈慧虹": 2,
    "洪志恒": 0, "王忠銘": 1, "王惠美": 1, "王文娟": 0,
    "王永慶": 0, "王育敏": 1, "盧秀燕": 1, "童文薰": 0,
    "翁章梁": 2, "范振揆": 0, "葉竹林": 0, "蔡其昌": 2,
    "蔡培慧": 2, "蔡適應": 2, "蔣萬安": 1, "蕭仁正": 0,
    "蘇清泉": 1, "蘇煥智": 0, "許忠信": 0, "許淑華": 1,
    # 屏東縣詹智鈞：2022 代表時代力量參選（原記 0 無黨籍，誤；6 ＝ 時代力量）
    "許鋐哲": 0, "詹智鈞": 6, "謝國樑": 1, "謝福弘": 1,
    "謝立康": 0, "謝龍介": 1, "谷辣斯．尤達卡": 2,
    "賴峰偉": 1, "賴香伶": 5, "鄭凱升": 0, "鄭匡宇": 0,
    "鄭宇翔": 0, "鄭寶清": 0, "鄭運鵬": 2, "鍾東錦": 0,
    "陳光復": 2, "陳其邁": 2, "陳時中": 2, "陳泰山": 0,
    "陳琬惠": 5, "陳福海": 0, "陳秋境": 0, "陳美妃": 0,
    # 基隆市陳薇仲：2022 代表時代力量參選（原記 0 無黨籍，誤；6 ＝ 時代力量）
    "陳薇仲": 6, "陳長宏": 0, "饒慶鈴": 1, "高虹安": 5,
    "黃偉哲": 2, "黃宏成台灣阿成世界偉人財神總統": 0, "黃希賢": 0,
    "黃敏惠": 1, "黃源甫": 0, "黃珊珊": 0, "黃秀芳": 2,
    "黃秀龍": 0, "黃聖峰": 0, "黄師鵬": 0, "龔偉綸": 0,
}

# ---------------------------------------------------------------- 22 縣市配置
# 每縣市：xlsx 檔名（data/）、村里級地圖、鄉鎮級地圖、縣徽原圖（簡體/簡稱檔名）。
# 縣市 key 用繁體全稱；徽章名單見 assets/share/徽章/ 實際檔名。
COUNTIES = {
    "臺北市": dict(xlsx="2022直轄市長選舉_台北市.xlsx", seal="台北市市徽.png"),
    "新北市": dict(xlsx="2022直轄市長選舉_新北市.xlsx", seal="新北市徽.png"),
    "桃園市": dict(xlsx="2022直轄市長選舉_桃園市.xlsx", seal="桃园.png"),
    "臺中市": dict(xlsx="2022直轄市長選舉_臺中市.xlsx", seal="台中.png"),
    "臺南市": dict(xlsx="2022直轄市長選舉_臺南市.xlsx", seal="台南.png"),
    "高雄市": dict(xlsx="2022直轄市長選舉_高雄市.xlsx", seal="高雄.png"),
    "南投縣": dict(xlsx="2022縣市長選舉_南投縣.xlsx", seal="南投.png"),
    "嘉義市": dict(xlsx="2022縣市長選舉_嘉義市.xlsx", seal="嘉义市.png"),
    "嘉義縣": dict(xlsx="2022縣市長選舉_嘉義縣.xlsx", seal="嘉义县.png"),
    "基隆市": dict(xlsx="2022縣市長選舉_基隆市.xlsx", seal="基隆.png"),
    "宜蘭縣": dict(xlsx="2022縣市長選舉_宜蘭縣.xlsx", seal="宜兰.png"),
    "屏東縣": dict(xlsx="2022縣市長選舉_屏東縣.xlsx", seal="屏东.png"),
    "彰化縣": dict(xlsx="2022縣市長選舉_彰化縣.xlsx", seal="彰化.png"),
    "新竹市": dict(xlsx="2022縣市長選舉_新竹市.xlsx", seal="新竹市.png"),
    "新竹縣": dict(xlsx="2022縣市長選舉_新竹縣.xlsx", seal="新竹县.png"),
    "澎湖縣": dict(xlsx="2022縣市長選舉_澎湖縣.xlsx", seal="澎湖.png"),
    "臺東縣": dict(xlsx="2022縣市長選舉_臺東縣.xlsx", seal="台东.png"),
    "花蓮縣": dict(xlsx="2022縣市長選舉_花蓮縣.xlsx", seal="花莲.png"),
    "苗栗縣": dict(xlsx="2022縣市長選舉_苗栗縣.xlsx", seal="苗栗.png"),
    "連江縣": dict(xlsx="2022縣市長選舉_連江縣.xlsx", seal="马祖.png"),
    "金門縣": dict(xlsx="2022縣市長選舉_金門縣.xlsx", seal="金门.png"),
    "雲林縣": dict(xlsx="2022縣市長選舉_雲林縣.xlsx", seal="云林.png"),
}

# 顯示順序（由北而南、本島而離島）
COUNTY_ORDER = [
    "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市",
    "基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣",
    "雲林縣", "嘉義市", "嘉義縣", "宜蘭縣", "花蓮縣", "臺東縣",
    "屏東縣", "澎湖縣", "金門縣", "連江縣",
]

# 縣市短名（頁眉小字或右欄用）
COUNTY_SHORT = {
    "臺北市": "臺北", "新北市": "新北", "桃園市": "桃園", "臺中市": "臺中",
    "臺南市": "臺南", "高雄市": "高雄", "基隆市": "基隆", "新竹市": "新竹市",
    "新竹縣": "新竹縣", "苗栗縣": "苗栗", "彰化縣": "彰化", "南投縣": "南投",
    "雲林縣": "雲林", "嘉義市": "嘉義市", "嘉義縣": "嘉義縣", "宜蘭縣": "宜蘭",
    "花蓮縣": "花蓮", "臺東縣": "臺東", "屏東縣": "屏東", "澎湖縣": "澎湖",
    "金門縣": "金門", "連江縣": "連江",
}


def clean_name(name):
    """候選人姓名清理：去掉「英文羅馬拼音」部分（第一個半形空格之後）。

    例：「谷辣斯．尤達卡 Kolas Yotaka」→「谷辣斯．尤達卡」。
    看板只印中文，英文拼音（羅馬字）不放上板。
    """
    if not name:
        return name
    # 全形空格（\u3000）也一併視為分隔
    return name.replace("\u3000", " ").split(" ")[0].strip()


def county_file(county):
    """該縣市 data 目錄的 xlsx 檔名。"""
    return COUNTIES[county]["xlsx"]


def seal_source(county):
    """該縣市徽章原圖（簡體/簡稱檔名）的完整路徑。"""
    return os.path.join(SEAL_SRC, COUNTIES[county]["seal"])


def map_source(county, level):
    """該縣市村里級/鄉鎮級地圖原圖路徑。level: 'village' | 'town'"""
    folder = MAP_VILLAGE if level == "village" else MAP_TOWN
    suffix = "村里級" if level == "village" else "鄉鎮級"
    return os.path.join(folder, "%s_%s.png" % (county, suffix))


def data_path(county):
    return os.path.join(DATA_DIR, COUNTIES[county]["xlsx"])


WIKI_TXT = os.path.join(os.path.dirname(ROOT), "Wikipedia.txt")


# ---------------------------------------------------------------- 背景照分組
# 2026-10-28：背景照由「全台共用一張」改為按區域分三張（同組共用一張原圖，
# 成品 dist/assets/bg/<key>.png 只存一份，不逐縣市複製）。
#   north      北部（中正紀念堂空拍，白天）
#   hsinchu    桃竹苗～嘉南（新竹迎曦門夜景）
#   kaohsiung  高屏～東部～離島（高雄夜景；原 street_bg.png 就是這張）
BG_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(ROOT))),
                      "Video", "assets", "share")
BG_GROUPS = [
    ("街景1.png", "north",
     ["臺北市", "新北市", "基隆市", "宜蘭縣", "桃園市"]),
    ("新竹.png", "hsinchu",
     ["新竹縣", "新竹市", "苗栗縣", "臺中市", "彰化縣",
      "南投縣", "雲林縣", "嘉義縣", "嘉義市", "臺南市"]),
    ("高雄.png", "kaohsiung",
     ["高雄市", "屏東縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]),
]
BG_BY_COUNTY = {c: (fn, key) for fn, key, cs in BG_GROUPS for c in cs}


def bg_source(county):
    """該縣市背景照原圖路徑。"""
    return os.path.join(BG_SRC, BG_BY_COUNTY[county][0])


def bg_key(county):
    """該縣市背景照的成品代號（dist/assets/bg/<key>.png）。"""
    return BG_BY_COUNTY[county][1]

# 2022 縣市長選舉簡報（「四、各县市结果总表」的『时任首长』是頁眉時任首長的唯一來源）
#
# ★ 2026-10-29：上層 ``2022县市长选举简报.md`` 被換成「全國看板專用」的精簡版
#   （只剩總體結果／政黨得票／3.2 縣市一覽），**『時任首長』那一欄已不存在**，
#   `_gen_boards.parse_brief_incumbents()` 因此找不到表頭而整批建置失敗。
#   含「四、各县市结果总表」的詳細版仍在 ``Video2022/docs/`` 下（也是該檔案的
#   權威版），所以縣市看板改讀 BRIEF_DETAIL_MD；BRIEF_MD 保留給全國看板
#   （`_gen_national.py` 只讀 §一／§2.4／§3.1，兩者互不干擾）。
BRIEF_MD = os.path.join(os.path.dirname(ROOT), "2022县市长选举简报.md")
BRIEF_DETAIL_MD = os.path.join(os.path.dirname(ROOT), "Video2022", "docs",
                               "2022县市长选举简报.md")


def brief_md_with_incumbent():
    """含『時任首長』表的簡報路徑：優先詳細版，退回上層簡報（向後相容）。"""
    if os.path.isfile(BRIEF_DETAIL_MD):
        return BRIEF_DETAIL_MD
    return BRIEF_MD

# 時任首長黨籍的逐場修正（簡報照中選會欄位記「無黨籍」，但實際黨籍不同）。
# 只列需要改的場次，其餘 21 縣市一律照簡報原文。
#
#   臺北市 柯文哲：2019 年創立台灣民眾黨並任主席，2022 年投票當下為民眾黨籍
#                  （簡報因中選會「無黨籍及未經政黨推薦」欄記為無黨籍）。
INCUMBENT_PARTY_OVERRIDE = {
    "臺北市": "台灣民眾黨",
}

# 逐場投票日覆寫（預設 11月26日）。嘉義市因市長候選人黃紹聰於投票日前逝世，
# 依公職人員選舉罷免法延後至 12月18日單獨投票。
COUNTY_DATE = {
    "嘉義市": ("12月18日", "18 Dec"),
}

# 超長姓名的看板顯示換行（純顯示用，不影響黨籍／當選判斷）。
# 嘉義市黃宏成：本名＋藝名＋封號太長（15 字），高卡姓名欄塞不下，拆成兩行。
# key 為 clean_name 後的中文全名，value 用 \n 標記斷行處（引擎識別 \n 換行）。
NAME_WRAP = {
    "黃宏成台灣阿成世界偉人財神總統": "黃宏成台灣阿成\n世界偉人財神總統",
}


def map_ink_ratio(county):
    """該縣市村里級地圖的「墨跡寬高比」（白底外框不計）。

    橫向寬圖（如臺中、金門）比值 > 1；直長圖（如連江、花蓮）比值 < 1。
    用於版面判斷：橫向寬圖改上下堆疊（主圖上、鄉鎮圖下）。
    """
    return map_aspect(county, "village")


def map_aspect(county, level="village"):
    """該縣市地圖 PNG 的寬高比（整張畫布，即渲染時 contain 的對象）。

    level: 'village'（村里級，主圖）｜'town'（鄉鎮級，第二張）。
    兩張同源同範圍，比值通常幾乎相同（臺中 2.06、連江 0.34 …），
    擺位時靠這個值算出「不留白邊的框」。
    """
    from PIL import Image
    with Image.open(map_source(county, level)) as im:
        w, h = im.size
    return float(w) / float(h)


def party_group(short_name):
    """政黨全稱 → 色階組別（未知一律 0 無黨籍灰）。"""
    return PARTY_GROUP.get(short_name, 0)


def party_short_by_group(group):
    return PARTY_SHORT_BY_GROUP.get(group, "無黨籍")
