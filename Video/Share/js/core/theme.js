/* ==========================================================================
   theme.js — 主題：色彩、字型、政黨識別
   --------------------------------------------------------------------------
   看板上所有顏色與字型都集中在這裡，改一個地方全站生效。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  /* 字型堆疊：指定 源石黑體 TW H（GenSekiGothic TW H，重量 900），
     其餘為同家族的其他命名與各平台常見黑體，避免換機器時掉字型。 */
  NT.FONT_STACK = '"GenSekiGothic TW H","源石黑體 H","GenSekiGothic TW",' +
    '"源石黑體","GenSekiGothic TW TTF Heavy","GenSekiGothic TW TTF",' +
    '"Microsoft JhengHei","Noto Sans TC","PingFang TC",' +
    '"Heiti TC",system-ui,Arial,sans-serif';
  /* 數字沿用同一套字型，讓中英文與數字筆調一致 */
  NT.FONT_NUM = NT.FONT_STACK;
  /* 標題級阿拉伯數字：Noto Sans UI Black（單一字重 900 的西文黑體，
     數字又寬又重，適合「2014 / 11 / 29」這種要一眼看清楚的場合。
     日期塊的年份與投票日兩行都走這一支，主次只靠字級大小分（96 / 36）。
     這支字型沒有中文字身，瀏覽器會逐字往下一個字型找，
     所以只拿來畫數字，中文（年／月／日）仍然走 FONT_STACK。

     註：曾經為了讓日期行「細一級」另外開過一份 FONT_NUM_LIGHT
     （把微軟正黑排在最前面取 Bold），但機器上找不到夠細、又有中文字身
     的黑體可選（源石黑體 H 只有 heavy、這支只有 900、正黑指定 700 會落到
     Bold），結果只是兩支粗黑體並排、看起來像同一支沒對齊，已移除。 */
  NT.FONT_DISPLAY_NUM = '"Noto Sans UI Black",' + NT.FONT_STACK;

  /**
   * Theme —— 色彩 / 尺寸 / 政黨樣式
   */
  function Theme() {}

  /* --------------------------- 看板底色系 --------------------------- */
  Theme.BG = {
    top: '#0d1738',
    mid: '#0a1128',
    bottom: '#05080f',
    deep: '#03060d',
    panel: 'rgba(255,255,255,0.045)',
    line: 'rgba(255,255,255,0.14)',
    text: '#ffffff',
    textDim: 'rgba(255,255,255,0.66)',
    textFaint: 'rgba(255,255,255,0.40)'
  };

  /* --------------------------- 政黨色 --------------------------- */
  /* 每個政黨定義：
     main  主色
     light 亮階（照片卡上緣、卡片漸層起點）
     dark  暗階（漸層終點、地圖深色端）
     map   地圖五段色階（淺 → 深，票差越大越深）
  */
  Theme.parties = {
    kmt: {
      key: 'kmt',
      main: '#2f6bd8',
      light: '#5f96ea',
      dark: '#123a86',
      accent: '#7fb0ff',
      map: ['#6ea3ef', '#4a83e4', '#2f6bd8', '#1d4ba6', '#102f74']
    },
    dpp: {
      key: 'dpp',
      main: '#23a455',
      light: '#4fc47c',
      dark: '#0d5c2c',
      accent: '#78e0a0',
      map: ['#63cf8c', '#35ae62', '#23a455', '#157a3b', '#0a4c23']
    },
    ind: {
      key: 'ind',
      main: '#8d93a6',
      light: '#b6bccb',
      dark: '#4c5164',
      accent: '#c8cedb',
      map: ['#b6bccb']
    }
  };

  Theme.party = function (key) {
    return Theme.parties[key] || Theme.parties.ind;
  };

  /**
   * 依「票差」取得地圖色階。
   * margin 為勝負差距百分點（0~100）：差距越大顏色越深。
   */
  Theme.mapShade = function (partyKey, marginPct) {
    var p = Theme.party(partyKey);
    var steps = p.map;
    var t = NT.Utils.clamp(marginPct / 22, 0, 1);   // 22 個百分點以上為最深
    var idx = Math.min(steps.length - 1, Math.floor(t * steps.length));
    return steps[idx];
  };

  /* --------------------------- 版面尺寸 --------------------------- */
  Theme.metrics = {
    space: 8,
    radiusLg: 44,
    radiusMd: 22,
    radiusSm: 14
  };

  NT.Theme = Theme;

})(window);
