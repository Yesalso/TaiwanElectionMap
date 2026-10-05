/* ==========================================================================
   theme.js — 主題：色彩、字型、政黨識別
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  NT.FONT_STACK = '"GenSekiGothic TW H","源石黑體 H","GenSekiGothic TW",' +
    '"源石黑體","GenSekiGothic TW TTF Heavy","GenSekiGothic TW TTF",' +
    '"Microsoft JhengHei","Noto Sans TC","PingFang TC",' +
    '"Heiti TC",system-ui,Arial,sans-serif';
  NT.FONT_NUM = NT.FONT_STACK;
  NT.FONT_DISPLAY_NUM = '"Noto Sans UI Black",' + NT.FONT_STACK;

  function Theme() {}

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

  Theme.parties = {
    kmt: { key: 'kmt', main: '#2f6bd8', light: '#5f96ea', dark: '#123a86', accent: '#7fb0ff',
      map: ['#6ea3ef','#4a83e4','#2f6bd8','#1d4ba6','#102f74'] },
    dpp: { key: 'dpp', main: '#23a455', light: '#4fc47c', dark: '#0d5c2c', accent: '#78e0a0',
      map: ['#63cf8c','#35ae62','#23a455','#157a3b','#0a4c23'] },
    tpp: { key: 'tpp', main: '#ff7f27', light: '#ffa45c', dark: '#a84600', accent: '#ffc08f',
      map: ['#ffc08f','#ffa264','#ff8a3d','#c25a08','#8a3f04'] },
    nsc: { key: 'nsc', main: '#7b4ea8', light: '#a983c8', dark: '#4a2a68', accent: '#d5c2e6',
      map: ['#d5c2e6','#b294ce','#8f68ad','#6a4a86','#4a3060'] },
    ind: { key: 'ind', main: '#8d93a6', light: '#b6bccb', dark: '#4c5164', accent: '#c8cedb',
      map: ['#b6bccb'] }
  };

  Theme.party = function (key) {
    return Theme.parties[key] || Theme.parties.ind;
  };

  Theme.mapShade = function (partyKey, marginPct) {
    var p = Theme.party(partyKey);
    var steps = p.map;
    var t = NT.Utils.clamp(marginPct / 22, 0, 1);
    var idx = Math.min(steps.length - 1, Math.floor(t * steps.length));
    return steps[idx];
  };

  Theme.metrics = {
    space: 8,
    radiusLg: 44,
    radiusMd: 22,
    radiusSm: 14
  };

  NT.Theme = Theme;

})(window);