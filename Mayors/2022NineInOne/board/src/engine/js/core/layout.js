/* ==========================================================================
   layout.js — 看板版式（2560 × 1440 的絕對座標）
   --------------------------------------------------------------------------
   把「哪裡放什麼、多大、什麼顏色」全部集中在這個檔案。
   要調整版面只要改這裡，不需要動任何繪製邏輯。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  /**
   * Layout —— 單一畫面的版式定義
   */
  function Layout() {}

  Layout.W = 2560;
  Layout.H = 1440;
  Layout.margin = 72;

  /* ------------------------------ 頁眉 ------------------------------ */
  /* ★ 2022 九合一縣市長看板頁眉（沿用總統看板風格，從左到右）：
       國旗 → 標題「2022年九合一選舉」 → 年份圓盤 2022＋日期 →
       縣徽白卡 → 四行數據（投票率/有效票/無效票/選舉人數） → 現任縣市長 */
  Layout.header = {
    h: 236,
    seal: {
      src: 'assets/city_seal.png',
      srcPresident: 'assets/roc_flag.png',
      x: 72, gap: 34, hRatio: 1.0,
      card: { pad: 16, radius: 24 }
    },
    leftText: { x: 72, size: 56, weight: 900, spacing: 6 },
    dateBlock: {
      cx: 1140, y: 28,
      disc: {
        src: 'assets/emblem.png',
        scrim: [
          [0, 'rgba(3,7,22,0.62)'],
          [0.58, 'rgba(3,7,22,0.38)'],
          [1, 'rgba(3,7,22,0.12)']
        ],
        scrimRadius: 0.62,
        dRatio: 1.95, cyRatio: 0.70,
        inner: '#4d0716', outer: '#360310'
      },
      lineGap: 21,
      year: { size: 96, cjkSize: 32, weight: 900, cjkWeight: 700, gap: 6, gapAfter: 0 },
      day: { size: 36, cjkSize: 23, weight: 900, cjkWeight: 700, gap: 5, gapAfter: 0,
        family: NT.FONT_DISPLAY_NUM }
    },
    /* 縣徽白卡：年份圓盤右側（單枚）。gap 為日期塊右緣到縣徽的距離。 */
    countySeal: {
      gap: 26, y: 40, h: 150,
      card: { pad: 12, radius: 22 }
    },
    /* 四行數據（投票率／有效票／無效票／選舉人數）：縣徽右側、小字豎排。 */
    stats: { gap: 26, size: 20, weight: 600, rowH: 32, labelGap: 12,
             labelColor: 'rgba(255,255,255,0.55)', valueColor: '#ffffff' },
    /* 最右：現任縣市長（色卡＋角色標籤＋姓名＋政黨），沿用總統看板樣式。 */
    incumbent: {
      card: { w: 112, h: 132, radius: 20, right: 2488, y: 34 },
      textRight: 2348, line1Y: 76, line2Y: 126, line3Y: 164,
      line1Size: 26, line2Size: 44, line3Size: 26
    }
  };

  /* ------------------------- 主要候選人區塊 ------------------------- */
  /* cx 為區塊中心；兩個區塊共用同一組 y 與尺寸。
     刻意貼齊左右兩側，把中間全部讓給地圖。
     「行距」= 姓名 / 得票率 / 得票數 三條基線之間的距離，由 lead 值控制：
     兩個區塊共用同一組值，之後想整體調鬆或收緊，改這裡就好。 */
  var candidateBlock = {
    cx: 310,
    /* card 是候選人色卡的框。
       ★ 看板不畫候選人照片（需求：照片由使用者自行後製），框裡只畫
         政黨純色底 + 一圈亮線，位置與尺寸沿用原本的照片框，構圖不變。
         見 layers.js 的 CandidateLayer。 */
    card: { w: 452, h: 620, y: 274, radius: 40 },
    /* 政黨標籤（色卡下方）：[政黨徽章] 政黨名。
       刻意不再放英文縮寫（原本是「[徽章] 中國國民黨 KMT」）——
       中文名已足夠，加上英文會讓最長的「無黨籍及未經政黨推薦 INDEPENDENT」
       撐爆膠囊。政黨名走 partyDisplay()，無黨籍一律只印「無黨籍」。
       marks 依政黨 key（見 theme.js 的 parties）對應到徽章圖，
       由 tools/build_board.py 的靜態素材透明化產出（只留內切圓、圓外透明；
       配方見 boardlib/assets.py 的 STATIC_RECIPES）。
       讀不到圖時該位置退回原本的抽象色塊（Marks.partyChip），不會開天窗。
       markRatio 是徽章邊長相對「標籤高度」的比例。
       ★ 2026-10-19 晚五：標籤加高、徽章放大（需求：第 1／2 名的政黨徽章
         「適度大一點」）—— h 76→84、radius 38→42、markRatio 0.42→0.54
         （徽章邊長 31.9 → 45.4px，約 1.42 倍）；黨名可用的寬度會少一點，
         labelMax 由 cp.w 扣掉內距與徽章寬自己算出來，不會溢出膠囊。
       ★ 2026-10-19 晚七（需求）：政黨欄底板方框移除（見 layers.js），徽章
         再放大一級 markRatio 0.54→0.75（邊長 45.4 → 63px）。
       ★ 2026-10-19 晚八（需求）：主卡政黨色卡移除後徽章再放大一級
         0.75→0.95（邊長 63 → 79.8px，幾乎占滿 chip 高）。 */
    chip: {
      w: 452, h: 84, y: 910, radius: 42, nameSize: 40,
      markRatio: 0.95,
      marks: { kmt: 'assets/party_kmt.png', dpp: 'assets/party_dpp.png' },
      /* 政黨徽章檔名規則：party_<政黨 key>.png（kmt -> assets/party_kmt.png） */
    },
    /* 姓名右側（當選者左側）貼當選標誌：markRatio 為標誌相對姓名字級的比例 */
    name: { y: 1096, size: 104, spacing: 6, markRatio: 0.94, markGap: 34 },
    /* 副手行（總統／副總統選舉用，參考巴西看板的「Vice: 姓名（政黨）」）：
       夾在姓名與得票率之間。「副手：」標籤用 dim 色、姓名白字、政黨跟主色。
       候選人沒有 vice 資料時整行不畫（市長選舉），y 不佔位、版面不變。
       maxW 為整行可用寬度（超過就 fitText 截斷）。 */
    vice: { y: 1152, size: 38, labelSize: 30, maxW: 470, gap: 14 },
    /* 姓名 → 得票率 的基線距離（行距） */
    lead: { nameToPct: 186, pctToVotes: 104 },
    /* ★ 得票率降一級（150 → 128）：％ 是配角，數字才是主角。
       （需求：前兩名的得票率字級小一點、得票數大一點） */
    pct: { size: 128 },
    /* 得票數：阿拉伯數字大、萬/票等漢字小。
       ★ 升一級（56 → 80）：票數是選民最想看的絕對數字，給它最大的字。
       漢字（萬／票）按同一個比例放大（30 → 43，維持 0.54 的比值）。 */
    votes: { size: 80, cjkSize: 43 }
  };
  /* 由 name.y 與 lead 推導出得票率、得票數的基線位置 */
  candidateBlock.pct.y = candidateBlock.name.y + candidateBlock.lead.nameToPct;
  candidateBlock.votes.y = candidateBlock.pct.y + candidateBlock.lead.pctToVotes;

  /* 主卡色卡（也就是第 1／2 名的照片框）的長寬比 = 452 : 620 ≈ 0.729。
     ★ 第 3 名高卡的「照片占位框」吃同一個比例（需求：第 3 名照片長寬比
       要和第 1、2 名相同）—— 後製合成照片時同一組裁切比例就能通用。
       只有這一個來源，改主卡尺寸時第 3 名會自己跟著變，不會走鐘。 */
  var CARD_ASPECT = candidateBlock.card.w / candidateBlock.card.h;

  /* 左右只差 cx；card 是純幾何，左右共用同一份（不需要再拷貝一層）。 */
  Layout.left = Object.assign({}, candidateBlock, { cx: 310 });
  Layout.right = Object.assign({}, candidateBlock, { cx: 2250 });

  /* ------------------ 低得票率候選人：圖片框改用占位圖 ------------------
     ★ 2026-10-28（需求）：候選人「得票排名 ≥ 3」且「得票率 < 3%」時，
       他的圖片框**一律**改畫 assets/low_pct.png（灰階人形剪影占位圖），
       不再是政黨純色塊 —— 這批人幾乎都沒有照片，後製時也不必再補一格。
       判斷式只有一處：model/election-model.js 的 Candidate#usesLowPctPhoto()
       （門檻 LOW_PCT_RANK = 3、LOW_PCT_LIMIT = 3 也在那裡）。
       這裡只放素材路徑，走「邏輯名 → board.files.js 對照」那一套，
       實際檔由 build_assets.py 複製到 dist/assets/share/low_pct.png。
       讀不到時自動退回政黨純色塊（見 layers.js 的 minorBlock），不會開天窗。 */
  Layout.photoFallback = {
    src: 'assets/low_pct.png'
  };

  /* --------------------------- 背景照片 --------------------------- */
  /* 街景照鋪滿整個畫布（cover：等比例放大到蓋滿、超出部分裁掉），
     上面再罩一層暗色（dim = 遮罩不透明度），讓前景的白字與色卡一樣讀得清楚。
     原本的漸層底色、光暈、細格線仍然畫在照片之上（半透明疊加），
     所以「換掉 src」或「讀不到照片」時畫面會退回純漸層底，不會開天窗。
     素材：邏輯名 street_bg.png，實際檔由 _gen_boards 逐場指向
           dist/assets/bg/<key>.png（2026-10-28 起按區域分三張：
           north＝街景1、hsinchu＝新竹、kaohsiung＝高雄；同組共用一張）。
           （原樣複製、不做任何透明化轉換，配方見 build_assets.py 的 build_bg。） */
  Layout.background = {
    src: 'assets/street_bg.png',
    dim: 0.50
  };

  /* ------------------------------ 地圖 ------------------------------ */
  /* src      地圖圖檔（已預處理好的透明 PNG，預設 assets/vote_map.png）。
             直接換掉那個檔就會生效，不必重建 data/local-assets.js。
             素材由 tools/build_vote_map.py 產生：把 9824×7365 的海報擦掉右上角
             自帶的「標題＋圖例」、裁到地圖本體、縮成 2400 × 2278 的透明圖。
             ★ 換素材請重跑那支腳本，不要丟整張海報進來：
               檔案會變成 3/4 空白 + 重複標題，見 tools/build_vote_map.py 檔頭。
             （在 file:// 下本機圖檔會污染 canvas、害「下載 PNG」壞掉，
               此時 js/slide.js 會自動退回內嵌版本，見該檔說明。）
             （那份內嵌副本要用 python tools/build_vote_map.py --embed 一起更新。）
        x/y/w/h  contain 進來的框；實際大小依原圖比例置中，不加底板。
        ★ 這個框只佔中段偏左（560 → 1580），右邊 1600–2008 整條留給圖例。
          早先框開到 2040（w 1520），地圖置中後會一路吃到右側，
          圖例只能「疊在地圖上」——2018／2022 的台北市地圖是直式滿版，
          疊上去正好蓋住內湖／南港／信義一帶的村里色塊，這是設計缺陷。
          收窄成 w 1020 之後：地圖仍取高度撐滿（k 由框高決定），
          直式地圖尺寸完全不變、只是整體左移；橫式地圖（新北）也只縮 1%。
          右緣 1580 與圖例左緣 1600 之間留 20px，兩者絕不接觸。
        scale    地圖再乘上的比例：1 = 撐滿框，0.9 = 整體縮到九成。
                 工具列的「地圖」滑桿即時改的就是這個值。
        anchorX/Y  縮小後在框內的貼齊位置：0 = 靠左/上、0.5 = 置中、1 = 靠右/下。
        dx/dy    額外的像素位移，用來微調。
        crop     已不需要（原本在執行期擦海報標題／圖例，搬到建置腳本了）。
                 只有「硬要塞原始海報圖」時才填 {width, erase[], content{}}，
                 見 js/core/utils.js 的 Utils.eraseAndCrop。 */
  Layout.map = {
    src: 'assets/map.png',
    x: 560, y: 196, w: 1020, h: 1034,
    scale: 1.0,
    anchorX: 0.5, anchorY: 0.5,
    dx: 0, dy: 0,
    /* plate：地圖底下的暗色圓角板（可選，預設不畫）。
       ★ 2026-10-29 全國看板：兩張高密度國地圖貼在街景照片上，海面／留白
         會透出照片，加一塊暗板把地圖托起來（見 layers.js 的 drawPlate）。
         22 場縣市長看板沒有這一項，輸出完全不變。 */
    plate: null
  };

  /* --------------------------- 區級圖（第二張圖） ---------------------------
     ★ 2026-10-14 晚六（需求：總統場把兩張圖放到同一張看板上）。
     村里的地圖（Layout.map，assets/map.png）仍然是**主要地圖**，
     尺寸與位置完全不動；這裡放的是**區級版**（assets/map2.png，
     Converge_to_map_taipei.py 的「只畫區、不畫里」版，同畫布同範圍），
     補進地圖右側那一整欄空位，讓看板左右不再「左重右空」。

     ★ 什麼時候畫：只有「圖例關掉」的場次（見 layers.js 的 Map2Layer）。
       市長場的圖例正好佔著這一欄（Layout.legend 1626–1978 × 493–933），
       硬畫會整張疊上去；總統「北北基宜」場圖例是關的（meta.layout.legend
       .disabled），那一欄本來就空著，正好拿來放第二張圖。
       素材不存在（或主圖與區級圖是同一張，例如 -map2 變體看板）時整層跳過，
       不會開天窗。

     x/y/w/h  contain 進來的框；實際大小依原圖比例置中，不加底板
              （與 Layout.map 同一套規則）。
              框刻意不貼齊右主卡：右緣 2004，右主卡左緣 2024，留 20px 淨空；
              左緣 1440 也避開地圖墨跡（實測右緣 x≈1408）；
              下緣 1076 在地圖下方那條「沒有墨跡」的帶裡，
              也在第 3 名高卡上緣（y1102）之上 —— 這三條由
              tools/verify_layout.py 的 L10–L12 把關。
     scale / anchorX / anchorY / dx / dy  與 Layout.map 同義，方便微調。 */
  Layout.map2 = {
    src: 'assets/map2.png',
    enabled: true,
    x: 1440, y: 360, w: 564, h: 700,
    scale: 1.0,
    anchorX: 0.5, anchorY: 0.5,
    dx: 0, dy: 0,
    /* 圖例開著時，第二張圖預設不畫（那一欄是圖例的）。
       ★ allowWithLegend = true 由 meta.layout.map2 逐場放行 —— 全國看板把圖例
         擺在頁眉右側、與地圖框不重疊，兩者可以並存（2026-10-29）。 */
    allowWithLegend: false,
    plate: null
  };

  /* --------------------------- 當選印記 --------------------------- */
  /* 「當選」印章（assets/mark_elected.png，circle_asset 去背後留內切圓）。
     以前只從 NT_ASSETS（board.assets.js 內嵌）拿，http 下不載內嵌就沒有章；
     現在給一個實體檔路徑，slide.js 讀不到內嵌才退回這裡。 */
  Layout.electedMark = {
    src: 'assets/mark_elected.png'
  };

  /* ------------------------------ 圖例 ------------------------------ */
  /* 得票率圖例（assets/legend.png）。兩個來源，版面吃法相同：
       2014 新北：海報截圖（2014NewTaipei/map/图例.png）裁邊、切掉頂端標題。
       2018／2022 台北：src/mapgen/Converge_to_map_taipei.py 現畫的 ——
         它依「哪個候選人在這一里領先」上色，圖例就是那組色階的量尺。
         色階固定綁政黨：藍=國民黨、綠=民進黨、青=民眾黨（柯文哲／黃珊珊）、
         灰=其他，同一個政黨在任何選舉都拿到同一組顏色。
         柵格產出後不再做任何去背 —— 這張圖**直接就是透明底 RGBA**：
         色塊不透明、文字純白，交給 tool/build_assets.py 時是原樣沿用（how=copy）。
         ★ 白字不能過「白底轉透明」：白字 RGB 就是 (255,255,255)，過一次會整片被吃掉。
         ★ 色階只畫「真的有里落進來」的檔位（全部領先里的得票率區間之外的檔不畫）。

     ★ 沒有底板了。以前圖例是「透明底 + 深色文字 + 色階色塊」，貼在看板底色
       （#0d1738）上文字會整個糊掉，所以在底下鋪一塊淺色圓角底板撐對比。
       現在文字改白字，底板反而跟白字糊成一片，所以整塊拿掉 —— 圖例直接貼在
       看板上，與地圖的處理一致（MapLayer 同樣不加任何底板）。

     ★ 圖上原本還有「標題／副標／人名」三行字（海報那張有，腳本畫的本來就沒有），
       海報那張已由建置腳本切掉：那些是海報的標題層級，跟看板自己的頁眉打架，
       貼上去只會搶戲。現在這張圖純粹是「哪個顏色代表幾 %」的量尺，
       說明交給小標題（title，預設不畫，見下）。

     落點：地圖框「右側」那一整條空欄，與地圖、與所有元素都不重疊。
     ★ 這裡原本擺在地圖框內（1540,700,420×520），靠著「新北市地圖中間那塊
       沒有村里的台北盆地」蒙混過去；換成台北市（2018／2022）之後，
       那塊位置正好是內湖／南港／信義／文山的村里色塊，圖例直接蓋掉地圖。
       現在改成：地圖框收窄到 560–1580（見 Layout.map），圖例獨佔右欄。
     ★ 右欄不是無限寬：左邊是地圖框緣 1580，右邊是右側候選人色卡左緣 2024
       （主卡 cx 2250、色卡寬 452），可用寬只有 444px。
       這一區從 408px 收到 352px 並置中於這一欄：左右各留 46px 淨空，
       與色卡的距離變成原本的近 3 倍。
       上下方向 y 493–933 落在頁眉（h 236）之下、底部小卡（y 1230 起）
       與票數帶（y 1396 起）之上，四周都是真正沒東西的區域。
       垂直位置取地圖框的垂直中心（框 196–1230，中心 713 → y = 713 − 440/2）。
       ★ 這條「不重疊」不是靠目測：tools/verify_layout.py 會用
         render_boards.mjs --report 匯出的實際矩形 + 地圖 PNG 的 alpha 邊界
         逐一比對，任何一格相交就讓建置失敗。

       x/y/w/h  圖例的 contain 框（也是「這一欄是圖例區」的範圍）。
                ★ 現在只是一個框，不再畫任何底板：圖例直接貼在看板底色上，
                  實際被畫到的只有 contain 出來的 image 矩形。
                圖例本體是一塊「高瘦」的量尺，框要夠高圖才吃得滿。
                三張圖例素材（新北 433×523、2018、2022）寬高比都不同，
                但都吃得住這個框：contain 後圖寬 263–332px，
                2× 匯出 526–664px，字仍然讀得清楚。
       title*   選用的小標題，畫在框的左上角，預設不畫（title 為空字串就整段
                跳過）。底色是深藍，所以預設白字。要加的話把 title 填成
                '候選人得票率' 即可。
       inner    圖例圖片的內距（圖片 contain 進 x+inner .. x+w-inner）
       opacity  圖例圖片的透明度，1 = 完全不透明 */
  Layout.legend = {
    src: 'assets/legend.png',
    /* disabled: true → 整個圖例不畫（總統「北北基宜」看板用 meta.layout 覆寫關掉；
       市長看板維持預設 false）。verify_layout 看到 legendDisabled 會略過 L1–L5。 */
    disabled: false,
    /* 右欄 1580–2024 置中：1580 + (444 − 352) / 2 = 1626
       ★ 高度可用 meta.layout.legend 逐場覆寫（見檔尾的套用程式碼）：
         總統「北北基宜」看板的圖例最多 4 位候選人直排、圖很瘦高，
         覆寫 h=717（到小卡上方為止）contain 後字才看得清；
         市長圖例是「寬度受限」，維持 440 不變、輸出不受影響。 */
    x: 1626, y: 493, w: 352, h: 440,
    title: '',
    titleSize: 24, titleWeight: 900, titleColor: '#ffffff',
    titleGap: 12,
    /* 圖例圖片：contain 進「扣掉標題與內距」的區域 */
    inner: 18,
    opacity: 1,
    /* allowInHeader：圖例擺在頁眉帶（y < header.h）之內時要明說。
       ★ 2026-10-29 全國看板：圖例放在頁眉右側（四行數據與「應選席次」之間），
         與地圖框完全不重疊。verify_layout 的 L3 原本把「整個頁眉」當障礙物，
         任何落在頁眉裡的圖例都會被判壓到；宣告這個旗標後 L3 會跳過頁眉
         （其他元素照驗）。市長／總統看板沒有這一項，判定完全不變。 */
    allowInHeader: false
  };

  /* --------------------------- 其他候選人（第 3 名起） ---------------------------
     ★ 2026-10-14 五版規則（需求：1 第 3 名照片比例要和第 1／2 名一樣、
                              2「其他候選人」改成一行一位、3 第 4 名起靠左排）：
       1. 第 3 名高卡的**照片占位框比例 = 主卡色卡的 452 : 620**（`CARD_ASPECT`，
          由 candidateBlock.card 推得，只有一個來源）。
       2. 「其他候選人」不再是「共 N 位 / 合計票數 / 合計得票率」的摘要格，
          改成**一行一位候選人的清單**：`- 姓名    1,851票`
          （★ 不印政黨、不印得票率）。列數多時卡片往上長（上限 = 高卡高度），
          字級由每列可用高度推得 —— 詳見下面的 others 設定。
       3. 左群（第 4 名起）改為**從第 3 名高卡的左緣往左排**：
          第 4 名緊貼高卡左側、第 5 名在其左、清單格在最左。
          （舊版是從 x0 往右排，第 3 名卡靠右 → 中間留一大段空；而且卡片
            排得越少空得越多。現在空的是最左邊，貼著地圖下方的那片暗底。）

     ★ 四版規則（第 3 名「長度太長、寬度太窄」）—— 仍然有效：
       1. 第 3 名＝獨立一張**高卡**（不是橫條）：有自己的高度 big.h（288），
          **底部與左群同一條線**（m.y + m.h = 1390），往**上**長到 y1102。
          ── 為什麼可以往上長：地圖框雖然開到 y1230，但地圖圖片是「置中的
             直式圖」，墨跡右緣只到 x≈1444（2000 總統／2022 市長實測都一樣，
             見 verify_layout 報告的 map.content）。第 3 名卡右緣貼 x1=1990、
             寬約 470–500 → 左緣 ≥1478，永遠落在地圖墨跡的**右邊**，
             所以「往上長」不會壓到地圖（這條由 verify_layout 的 L9 把關）。
       2. 卡內改成**單欄直排**（照片占位框 + 右側一欄：
          姓名／副手（或政黨）／得票率／票數）—— 舊版是「姓名群 ↔ 得票群」
          兩欄並排，卡片被撐成 670–720 長、160 高的橫條（4.2 : 1），
          看起來又長又扁；收成單欄後約 470–500 × 288（1.7 : 1）。
          照片面積 ≈ 175×240 = 42,000 px² ≈ 第 4 名以後小卡（92×118）的 3.9 倍。
       3. **卡寬 = 內容自然寬**（占位框 + 最寬那一行 + 內距 padL/padR），
          卡內不留多餘空位；空隙只留在「卡與卡之間」（gap / groupGap）。
       4. 字級動態：堆疊總高由 layers.js 的 bigScale 求係數 k，讓五行
          **剛好填滿卡內高度**（沒有副手行的場次 k 略大）；塞不下時再由
          fit 迴圈整條等比縮（下限 minTextScale），不截字、不溢出。
       ── 排列：第 4、5 名（160 高的窄卡）與「其他候選人」清單格，
          一律**從 x1 往左排**（右緣貼 bigX − groupGap）；
          第 3 名高卡右緣貼齊 x1。
          x1 = 1990：右主卡得票率文字最左約 2008（2022 實測），留約 18px 淨空
          （舊版 solo 對齊到主卡右緣 2476，會整張疊上去、票數變雙重曝光亂碼）。
       候選人不足時左群自然消失：只有 3 位候選人 → 第 3 名一張高卡靠右（solo）。
       每格左側都有圖片占位框（政黨純色 + 亮線，照片由使用者後製）。 */
  Layout.minors = {
    y: 1230, h: 160, radius: 16,   /* 左群（第 4 名起）的帶：維持 160 高 */
    x0: 560, x1: 1990,
    gap: 12,                 /* 左群「卡與卡」之間的固定空隙 */
    groupGap: 64,            /* 左群 ↔ 第 3 名高卡 之間的最小淨空 */
    minGap: 8,               /* 空間不足時 gap 的下限 */
    padL: 14, padR: 16,      /* 卡內左右留白（固定值，不隨內容變動） */
    blockGap: 14,            /* 占位框 ↔ 文字列 的間距 */
    minTextScale: 0.62,      /* 等比縮字級的下限（超過就交給 fitText 收尾） */

    /* 第 4 名以後：小卡（照片區 92×118，文字四行上下堆疊在同一列） */
    block: { w: 92, h: 118, radius: 10 },
    /* 每場最多放幾張「窄卡」，超過的進「其他候選人」清單格。
       ★ 預設不設（undefined）→ 沿用舊規則：5 位以上才開清單格、最多 2 張窄卡。
       ★ 2026-10-29 全國看板：候選人是政黨，指定 smallMax = 2（只留 2 張窄卡），
         其餘（其他政黨）走清單格 —— 也就是台北市底部那一套。 */
    smallMax: undefined,
    /* 「其他候選人」清單格的文字寬上限（可選；undefined → 用 others.maxTextW）。
       ★ 2026-10-29 全國看板：其他政黨逐黨列出後，長黨名（台澎國際法法理建國黨）
         讓清單字級被壓到 19px；主卡／高卡的席次條空出寬度後多出約 100px，
         逐場把上限提到 370 → 字級回到 ~23px。
       ★ 注意不能直接覆寫 minors.others（淺層併會把 rowH／dash 等一起蓋掉）。 */
    othersMaxTextW: undefined,
    nameSize: 27, subSize: 17,
    /* 副行的顏色（可選）。undefined / null → 沿用舊行為：
       有副手 textDim(0.66)、沒有副手 textFaint(0.40)。
       ★ 2026-10-29 全國看板：副行印的是**黨主席姓名**，重要性僅次於黨名，
         而底色是街景照片（不是純色面板），0.40 白幾乎看不見 → 逐場提到 0.86。 */
    subInk: null,
    pctSize: 32, votesSize: 23, votesCjkSize: 13,
    maxTextW: 250,           /* 文字列自然寬上限 */
    /* 卡內絕對 Y（name/sub 走 middle 基線、pct/votes 走 alphabetic 基線） */
    nameCy: 42, subCy: 78, pctBase: 126, votesBase: 152,

    /* 第 3 名：高卡（單欄直排；底部與左群同線，往上長）
       ★ 占位框完全由卡片內距與比例推得：高 = h − 2×padV = 240、
         寬 = 高 × blockAspect（= CARD_ASPECT，與第 1／2 名主卡色卡同比例）。
         改 h / padV / blockAspect 都會自己跟著長，不必另外維護一組數字。 */
    big: {
      h: 288, radius: 18,
      padL: 18, padR: 22, padV: 24,
      blockAspect: CARD_ASPECT,           /* 452 : 620 —— 與主卡同比例 */
      blockRadius: 13,
      blockGap: 22,                       /* 占位框 ↔ 文字欄 */
      nameSize: 50, subSize: 22, partySize: 18,
      lineGap1: 12, lineGap2: 8,          /* 姓名↔副手、副手↔政黨 的行距 */
      stackGap: 20,                       /* 姓名群 ↔ 得票率 */
      votesGap: 6,                        /* 得票率 ↔ 票數 */
      pctSize: 62, votesSize: 38, votesCjkSize: 22,
      capRatio: 0.72,                     /* alphabetic 基線 = 行頂 + 字級 × 此值 */
      maxTextW: 300,                      /* 文字欄自然寬上限（超過就整欄縮字級） */
      scaleMin: 0.8, scaleMax: 1.15       /* 「填滿卡高」的字級係數上下限 */
    },
    /* 「其他候選人」清單格（★ 2026-10-14 五版：一行一位，不再合計）
       ── 內容：`- 姓名 ＋ 票數`（票數右對齊成一欄，像表格）。
          ★ 依需求**不印政黨、不印得票率**，也沒有照片占位框。
       ── 高度：由列數自己長（底部與左群同線、往上長），
          `h = 標題高 + n×rowH + 2×padV`，但**上限 m.big.h**（= 288）——
          列數多時把每一列壓矮（rowH 下限 minRowH），字級按 rowH 比例縮，
          整張卡永遠不會長得比第 3 名高卡還高（否則會撞到地圖，見 L9）。
       ── 寬度：`padL + colW + padR`，colW 由「最寬的姓名 + 最寬的票數」推得
          （票數欄右緣對齊 → 每列看起來是一張表）。 */
    others: {
      /* 2026-10-14 晚五：標題「其他候選人（N 位）」依需求移除 ——
         清單格直接列候選人（`- 姓名 票數`），不再頂一行標題。
         空字串 = 不畫（titleH 記 0，卡片高度全部讓給列、每列因此更高）。 */
      title: '',
      titleSize: 22,
      padV: 16, padL: 18, padR: 18,
      rowH: 36, minRowH: 22,               /* 每一列的首選高／下限 */
      maxH: 268,                           /* 清單格高度上限（< big.h，避免往上長壓地圖墨跡） */
      size: 26,                            /* 姓名與票數的字級（再用 rowH 比例縮放） */
      dash: '-',                           /* 行首符號：`- 姓名` */
      dashGap: 12, colGap: 22,             /* 符號↔姓名、姓名↔票數 */
      rule: true,                          /* 列與列之間畫一條極淡的細線 */
      ruleColor: 'rgba(255,255,255,0.07)',
      maxTextW: 300                        /* colW 上限（超過就整張縮字級） */
    }
  };

  /* --------------------------- 底部票數帶 --------------------------- */
  /* disabled: true → 整條得票比例帶不畫（可由 meta.layout.ribbon 逐場覆寫；
     縣市長看板維持預設 false）。 */
  Layout.ribbon = { y: 1396, h: 44, gap: 4, disabled: false };

  /* --------------------------- 背景裝飾 --------------------------- */
  Layout.decor = {
    glowLeft: { x: 420, y: 620, r: 1180, color: 'kmt' },
    glowRight: { x: 2140, y: 600, r: 1180, color: 'dpp' },
    vignette: 0.55
  };

  NT.Layout = Layout;

  /* --------------------- 逐場版面覆寫（meta.layout） ---------------------
     board.js 比 layout.js 先載入（見 index.html），所以在這裡可以把
     window.BOARD.meta.layout 的欄位淺層併進對應的 Layout 區塊。
     目前開放 legend（總統北北基宜看板把 h 覆寫成 717）、map2，
     以及 map（2026-10-19 桃竹苗看板：地圖是近方形，contain 進預設框
     560–1580 後墨跡右緣會到 x≈1546，壓到第 3 名高卡與 map2 欄，
     故把主圖框收窄成 w=880 → 墨跡右緣 1432，見 verify_layout L9/L10）；
     ★ 2026-10-29 再加 minors（全國看板把「小卡色塊」由 92×118 的頭像框
       改成 124×118 的席次牌 —— candidates 是政黨，牌子上要放三位數以內的
       席次與打勾記號，寬一點才擺得下）。
     ★ 注意是**淺層**併：覆寫 minors.block 要把整個物件寫齊（w/h/radius），
       只寫 w 會讓 h、radius 一起變成 undefined。
     要開放其他區塊時照樣加進 LAYOUT_OVERRIDABLE 即可。 */
  var LAYOUT_OVERRIDABLE = ['legend', 'map2', 'map', 'ribbon', 'minors'];
  try {
    var overrides = (global.BOARD && global.BOARD.meta &&
                     global.BOARD.meta.layout) || null;
    if (overrides) {
      LAYOUT_OVERRIDABLE.forEach(function (k) {
        if (overrides[k] && Layout[k]) {
          Object.assign(Layout[k], overrides[k]);
        }
      });
    }
  } catch (e) { /* 版面覆寫失敗不該毀掉整塊看板 */ }

})(window);
