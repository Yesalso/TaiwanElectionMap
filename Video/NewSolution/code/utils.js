/* ==========================================================================
   utils.js — 共用工具函式
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  NT.Utils = {
    /** 萬單位格式化：959302 -> "95萬9302" */
    voteWan: function (v) {
      if (v >= 10000) {
        var wan = Math.floor(v / 10000);
        var rest = v % 10000;
        return wan + '萬' + (rest ? String(rest).padStart(4, '0') : '');
      }
      return String(v);
    },

    /** 數字千分位：959302 -> "959,302" */
    voteComma: function (v) {
      return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },

    /** 限制數值在範圍內 */
    clamp: function (v, min, max) {
      return Math.max(min, Math.min(max, v));
    },

    /** 線性插值 */
    lerp: function (a, b, t) {
      return a + (b - a) * t;
    },

    /** 等待所有圖片解碼完成 */
    waitImages: function (imgs) {
      return Promise.all(imgs.map(function (img) {
        if (img.complete) return Promise.resolve();
        return new Promise(function (resolve) {
          img.onload = img.onerror = resolve;
        });
      }));
    },

    /** 等待字型載入 */
    waitFonts: function () {
      return document.fonts.ready;
    },

    /** 格式化百分比：50.06 -> "50.06%" */
    pct: function (v) {
      return v.toFixed(2) + '%';
    },

    /** 簡單的深拷貝 */
    deepClone: function (obj) {
      return JSON.parse(JSON.stringify(obj));
    }
  };

})(window);