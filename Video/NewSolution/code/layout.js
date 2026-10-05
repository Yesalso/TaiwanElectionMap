/* ==========================================================================
   layout.js — 版面座標與幾何常數（2560×1440 基準）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  var W = 2560, H = 1440;

  NT.Layout = {
    // 畫布
    W: W, H: H,

    // 邊界
    pad: 48,

    // 頁眉區（上方標題、日期、市徽）
    header: {
      h: 180,
      titleY: 56,
      titleSize: 56,
      dateY: 112,
      dateSize: 32,
      seal: { x: 48, y: 24, size: 132 }
    },

    // 候選人卡片區（左右兩側）
    card: {
      leftX: 48,
      rightX: W - 48 - 760,
      y: 260,
      w: 760,
      h: 1040,
      photo: { x: 40, y: 40, w: 680, h: 680 },
      nameY: 760,
      nameSize: 48,
      partyY: 820,
      partySize: 36,
      votesY: 880,
      votesSize: 56,
      pctY: 950,
      pctSize: 40
    },

    // 地圖區（中間）
    map: {
      x: 856,
      y: 260,
      w: 848,
      h: 1040
    },

    // 底部票數帶
    ribbon: {
      y: 1340,
      h: 60,
      segH: 48,
      labelSize: 20
    },

    // 行政區列表（右側）
    districtList: {
      x: 1752,
      y: 260,
      w: 760,
      h: 1040,
      itemH: 36,
      nameSize: 22,
      votesSize: 20
    },

    // 小候選人區（底部票數帶上方）
    minorRow: {
      y: 1280,
      h: 48,
      itemW: 200,
      gap: 16
    },

    // 顏色
    color: {
      cardGradTop: 'rgba(255,255,255,0.08)',
      cardGradBottom: 'rgba(0,0,0,0.6)',
      cardBorder: 'rgba(255,255,255,0.18)',
      textMain: '#ffffff',
      textDim: 'rgba(255,255,255,0.66)',
      textFaint: 'rgba(255,255,255,0.40)',
      elected: '#ffd400'
    }
  };

  // 由比例計算實際座標（支援任意倍率縮放）
  NT.Layout.atScale = function (scale) {
    var L = NT.Utils.deepClone(NT.Layout);
    var keys = ['pad', 'header', 'card', 'map', 'ribbon', 'districtList', 'minorRow'];
    function scaleObj(obj) {
      for (var k in obj) {
        var v = obj[k];
        if (typeof v === 'number') obj[k] = v * scale;
        else if (v && typeof v === 'object') scaleObj(v);
      }
    }
    keys.forEach(function (k) { scaleObj(L[k]); });
    L.W = W * scale;
    L.H = H * scale;
    return L;
  };

})(window);