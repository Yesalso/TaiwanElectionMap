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
  Layout.header = {
    h: 236,
    /* 左：新北市市徽（固定貼齊左邊界）
       x 直接指定、不依賴日期塊算出來，所以市徽落點固定好驗證。
       hRatio = 市徽高度 ÷ 日期塊高度；寬度依原圖比例換算（市徽原圖 480 × 716）。
       市徽右緣到選舉名稱的距離就是 gap，選舉名稱的實際 x 由市徽寬度推出來。 */
    seal: { src: 'assets/city_seal.png', x: 72, gap: 34, hRatio: 1.0 },
    /* 左：選舉名稱（單行）
       早先這裡還有一行小字「TAIWAN, CHINA」，已移除；選舉名稱因此成為左側
       唯一的錨點，直接視覺置中於日期塊的水平軸上（y 由 layers.js 用實際
       墨跡範圍回推，不在這裡寫死）。 */
    leftText: { x: 72, size: 66, weight: 900, spacing: 8 },
    /* 中：深紅圓盤 + 屆次年份 + 投票日
       原本是一塊藍色圓角底版裝兩行；改用者提供的樣板（「2009 / August 30」）
       之後改成：一個深紅圓盤墊在年份後面，年份數字極大、幾乎壓滿圓盤，
       投票日降一級字、換細字重排在圓盤下緣。沒有底版、沒有外框，
       整組只靠圓盤與兩行字自己成形。
       參考圖量到的比例（圖寬 198px，圓盤 x 66–141 / y 10–82）：
         年份數字墨跡高 38.5px、圓盤直徑 76px  → dRatio = 76 / 38.5 ≈ 1.95
         圓心在數字墨跡高度的 70% 處            → cyRatio = 0.70
         日期行墨跡高 13.5px = 年份的 0.35 倍
         兩行淨空隙 12px = 年份數字高的 0.31 倍
         圓盤底緣 ≈ 日期行的基線
       這些比例全部寫成「相對年份數字墨跡」的係數，實際像素由 layers.js
       用 measureRich 量出來（換年份、改字級都不會走掉）：
         dRatio   圓直徑 ÷ 年份數字墨跡高度
         cyRatio  圓心落在「年份墨跡高度」的幾成處（0 = 頂、1 = 底）
         y        區塊上緣＝圓盤上緣
         lineGap  「年那行墨跡底 → 日期那行墨跡頂」的淨空隙
       兩行共用同一支數字字型 NT.FONT_DISPLAY_NUM（Noto Sans UI Black），
       主次只靠字級大小區分（96 → 36），筆調完全一致；
       中文單位（年／月／日）走 FONT_STACK，因為那支字型沒有中文字身，
       瀏覽器會逐字往下一個字型找。 */
    dateBlock: {
      cx: 1320, y: 28,
      disc: {
        /* 底色改用使用者提供的圓徽圖（assets/emblem.png，由 tools/build_assets.py
           從 2014NewTaipei/国徽.png 產出：原圖 1280×1280、白底、圓盤剛好是內切圓，
           這裡只留內切圓、圓外透明）。原圖本身是正方形＋內切圓，
           所以繪製時「畫滿外接正方形再切圓」就會完全貼合，不必另外調比例。 */
        src: 'assets/emblem.png',
        /* 壓暗罩：圓徽很亮（純藍 + 白太陽），而年份是白字——不壓暗的話
           「2014」會直接糊在太陽上。用「由中心往外遞減」的徑向暗罩：
           中心（太陽所在、也正是數字壓過去的地方）壓最重，
           圓盤外緣（藍底與光芒尖）留得比較亮，圓徽的形狀才看得出來。
           寫成 [offset, color] 陣列就用徑向漸層，寫成單一顏色字串就是平塗。 */
        scrim: [
          [0, 'rgba(3,7,22,0.62)'],
          [0.58, 'rgba(3,7,22,0.38)'],
          [1, 'rgba(3,7,22,0.12)']
        ],
        scrimRadius: 0.62,        /* 暗罩半徑 ÷ 圓盤直徑：1 = 罩到圓周 */
        dRatio: 1.95, cyRatio: 0.70,
        /* 讀不到圓徽圖時的後備：原本的暗絳紅平塗
           （參考樣板量到的實色是 RGB ≈ 62,4,17 = #3e0411）。 */
        inner: '#4d0716', outer: '#360310'
      },
      lineGap: 21,
      /* 年份與投票日兩行刻意「同字型、同字重」，只降字級：
         原本日期行想用細一級的字重做出參考圖那種對比，但系統上找不到
         夠細又有中文字身的黑體（源石黑體 H 只有 heavy、Noto Sans UI Black
         只有 900、微軟正黑指定 700 會落到 Bold），結果兩支粗黑體並排，
         看起來反而像「同一支字卻沒對齊」，不如直接統一。
         family 兩行都指向 NT.FONT_DISPLAY_NUM，要換字型改這一處即可。 */
      year: { size: 96, cjkSize: 32, weight: 900, cjkWeight: 700, gap: 6, gapAfter: 0 },
      day: { size: 36, cjkSize: 23, weight: 900, cjkWeight: 700, gap: 5, gapAfter: 0,
        family: NT.FONT_DISPLAY_NUM }
    },
    /* 投票率 / 有效票：接在日期塊「右側」、與日期塊垂直置中
       gap 為日期塊右緣到這行字的距離，size／weight 為字級與粗細。 */
    stats: { gap: 34, size: 26, weight: 600 },
    /* 右：現任者（與日期塊同樣上移，保持和左側名稱同一水平帶） */
    incumbent: {
      photo: { w: 112, h: 132, radius: 20, right: 2488, y: 34 },
      textRight: 2348, line1Y: 76, line2Y: 126, line3Y: 164,
      line1Size: 28, line2Size: 52, line3Size: 30
    }
  };

  /* ------------------------- 主要候選人區塊 ------------------------- */
  /* cx 為區塊中心；兩個區塊共用同一組 y 與尺寸。
     刻意貼齊左右兩側，把中間全部讓給地圖。
     「行距」= 姓名 / 得票率 / 得票數 三條基線之間的距離，由 lead 值控制：
     兩個區塊共用同一組值，之後想整體調鬆或收緊，改這裡就好。 */
  var candidateBlock = {
    cx: 310,
    /* dx：照片水平微調（像素，正數往右）。cover 只會把「圖框」置中，
       兩張照片的裁切不對稱程度不同：朱立倫幾乎居中，游錫堃的人偏在圖框左側
       （貼齊左邊、右邊留白），所以右邊那張要往右推才會看起來置中。 */
    photo: { w: 452, h: 620, y: 274, radius: 40, dx: 0 },
    /* 政黨標籤（照片卡下方）：[政黨徽章] 政黨全名  英文縮寫
       marks 依政黨 key（見 theme.js 的 parties）對應到徽章圖，
       由 tools/build_assets.py 從 2014NewTaipei/*.png 產出（只留內切圓、圓外透明）。
       讀不到圖時該位置退回原本的抽象色塊（Marks.partyChip），不會開天窗。
       markRatio 是徽章邊長相對「標籤高度」的比例（不需可調時保持 0.42）。 */
    chip: {
      w: 452, h: 76, y: 910, radius: 38, nameSize: 40, enSize: 23,
      markRatio: 0.42,
      marks: { kmt: 'assets/party_kmt.png', dpp: 'assets/party_dpp.png' }
    },
    /* 姓名右側（當選者左側）貼當選標誌：markRatio 為標誌相對姓名字級的比例 */
    name: { y: 1096, size: 104, spacing: 6, markRatio: 0.94, markGap: 34 },
    /* 姓名 → 得票率 的基線距離（行距） */
    lead: { nameToPct: 186, pctToVotes: 104 },
    pct: { size: 150 },
    /* 得票數：阿拉伯數字大、萬/票等漢字小 */
    votes: { size: 56, cjkSize: 30 }
  };
  /* 由 name.y 與 lead 推導出得票率、得票數的基線位置 */
  candidateBlock.pct.y = candidateBlock.name.y + candidateBlock.lead.nameToPct;
  candidateBlock.votes.y = candidateBlock.pct.y + candidateBlock.lead.pctToVotes;

  /* Object.assign 是淺拷貝，photo 物件會被左右共用；
     要左右給不同的 photo.dx，必須各自再拷貝一層 photo。 */
  Layout.left = Object.assign({}, candidateBlock, {
    cx: 310,
    photo: Object.assign({}, candidateBlock.photo, { dx: 0 })
  });
  Layout.right = Object.assign({}, candidateBlock, {
    cx: 2250,
    /* 實測：未調整時人物頭部重心在卡片中心左邊約 21px、右側多留 39px 空白 */
    photo: Object.assign({}, candidateBlock.photo, { dx: 22 })
  });

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
        scale    地圖再乘上的比例：1 = 撐滿框，0.9 = 整體縮到九成。
                 工具列的「地圖」滑桿即時改的就是這個值。
        anchorX/Y  縮小後在框內的貼齊位置：0 = 靠左/上、0.5 = 置中、1 = 靠右/下。
        dx/dy    額外的像素位移，用來微調。
        crop     已不需要（原本在執行期擦海報標題／圖例，搬到建置腳本了）。
                 只有「硬要塞原始海報圖」時才填 {width, erase[], content{}}，
                 見 js/core/utils.js 的 Utils.eraseAndCrop。 */
  Layout.map = {
    src: 'assets/vote_map.png',
    x: 520, y: 196, w: 1520, h: 1034,
    scale: 1.0,
    anchorX: 0.5, anchorY: 0.5,
    dx: 0, dy: 0
  };

  /* ------------------------------ 圖例 ------------------------------ */
  /* 得票率圖例（assets/legend.png，由 tools/build_assets.py 從
     2014NewTaipei/map/图例.png 裁邊、縮到 LEGEND_WIDTH 寬、切掉頂端標題而來）。
     素材本身是「透明底 + 深藍近黑文字 + 藍綠九階色塊」，直接貼在深色看板上
     文字會整個糊掉，所以這裡多一層「淺色底板」把對比撐起來——
     底板不是裝飾，是這張圖看得見的必要條件（見 layers.js 的 LegendLayer）。

     ★ 圖上原本還有「標題／副標／人名」三行字，已由建置腳本切掉：
       那些是海報的標題層級，跟看板自己的頁眉打架，貼上去只會搶戲。
       現在這張圖純粹是「哪個顏色代表幾 %」的量尺，看的人看色塊就夠了，
       說明交給底板的小標題（title，預設不畫，見下）。

     落點：地圖框（Layout.map 520,196,1520×1034）中央那塊「沒有村里的台北盆地」。
     實測該處色塊分布：盆地的乾淨區大約是 x 1560–1960 / y 700–1220，
     整組放到這個矩形裡，四周都還留著地圖自己的深藍底，完全不會蓋到村里色塊；
     右緣 1960 也還在右側候選人照片卡（x 從 2024 起）之外，
     下緣 1220 則讓開底部小卡（y 從 1240 起）與底部票數帶（y 1396 起），收乾淨。
     （純色塊版圖例比原圖矮胖，這裡改用 420×520 的直式底板裝，
       圖 contain 進去約 384 寬，2× 匯出仍近 770 寬，夠銳利。）

       x/y/w/h  底板矩形（也是圖例圖片的 contain 框）。
                切掉標題後圖例本體變成「高瘦」的一塊（原素材比例約 0.72 高/寬，
                含 9 列的兩欄），所以底板也跟著拉高，讓圖能吃滿、字才不會太小。
       pad      底板相對圖例內縮的邊距（含在 w/h 內，不是往外加）
       radius   底板圓角
       bg       底板顏色：比看板底色（#0d1738）亮好幾階的冷灰藍，
                讓「這一塊是圖例區」一眼看得出來，又不搶候選人的政黨色。
       border   底板描邊（微微一圈亮線，邊界更清楚）
       title*   底板左上角的小標題，預設不畫（title 為空字串就整段跳過）：
                圖上自己的標題已經切掉了，這塊只需要「量尺」功能，
                再加一行字反而讓本來就緊的框更擠。
                要恢復的話把 title 填成 '候選人得票率' 即可。
       inner    圖例圖片的內距（圖片 contain 進 x+inner .. x+w-inner）
       opacity  整組（底板 + 圖片）的透明度，1 = 完全不透明 */
  Layout.legend = {
    src: 'assets/legend.png',
    x: 1540, y: 700, w: 420, h: 520,
    radius: 20,
    bg: 'rgba(226,233,246,0.94)',
    border: 'rgba(255,255,255,0.34)',
    shadow: 'rgba(0,0,0,0.55)',
    /* 底板的小標題：預設不畫（空字串），切成量尺後就不需要這行字了 */
    title: '',
    titleSize: 24, titleWeight: 900, titleColor: '#1b2740',
    titleGap: 12,
    /* 圖例圖片：contain 進「扣掉標題與內距」的區域 */
    inner: 18,
    opacity: 1
  };

  /* --------------------------- 其他候選人 --------------------------- */
  /* 第三候選人（李進順）刻意做小，避免與兩位主要候選人搶版面 */
  Layout.minor = {
    cx: 1280, y: 1240, w: 520, h: 138, radius: 22,
    photo: { w: 96, h: 106, radius: 15, offsetX: 22 },
    nameX: 140, nameY: 56, nameSize: 40,
    partyY: 94, partySize: 24,
    pctRight: -30, pctY: 56, pctSize: 40,
    votesY: 112, votesSize: 28, votesCjkSize: 16
  };

  /* --------------------------- 底部票數帶 --------------------------- */
  Layout.ribbon = { y: 1396, h: 44, gap: 4 };

  /* --------------------------- 背景裝飾 --------------------------- */
  Layout.decor = {
    glowLeft: { x: 420, y: 620, r: 1180, color: 'kmt' },
    glowRight: { x: 2140, y: 600, r: 1180, color: 'dpp' },
    vignette: 0.55
  };

  NT.Layout = Layout;

})(window);
