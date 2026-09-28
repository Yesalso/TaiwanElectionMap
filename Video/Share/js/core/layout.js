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
    /* 中：屆次年份 + 投票日
       日期塊是一塊藍色圓角底，裝兩行：
         第一行  「2014年」   年份數字大、年字小並靠基線
         第二行  「11月29日」 月／日在同一行，日期數字大、月日兩字小
       數字用 NT.FONT_DISPLAY_NUM（Noto Sans UI Black），中文單位走 FONT_STACK。
       兩行的間距與底板上下留白都由「實際墨跡」推導（見 layers.js measureRich），
       所以這裡的 size 只決定字級大小，padY 是額外的視覺留白。 */
    dateBlock: {
      cx: 1320, y: 28, w: 236, radius: 26,
      /* 藍底：年份在上、日期在下，共用同一塊底。w 只是最小寬度，
         內容更寬時由實際量測撐開，換年份／換字級都不會被切到。 */
      padX: 30, padY: 11,
      /* 兩行之間的視覺間距（像素）。數字沒有下伸部，所以這裡是
         「年那行墨跡底 到 日期那行墨跡頂」的淨空隙。 */
      lineGap: 20,
      year: { size: 62, cjkSize: 27, weight: 900, cjkWeight: 700, gap: 5, gapAfter: 0 },
      day: { size: 44, cjkSize: 23, weight: 900, cjkWeight: 700, gap: 5, gapAfter: 0 }
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
    chip: { w: 452, h: 76, y: 910, radius: 38, nameSize: 40, enSize: 23 },
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
