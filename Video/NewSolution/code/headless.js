/* ==========================================================================
   headless.js — 無頭渲染 Hook（Node + Edge CDP 用）
   只有在 ?headless=1 時才會被載入
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  function renderBoard(scale) {
    return NT.BoardFactory.create(global.BOARD)
      .then(function (slide) {
        // 等待所有圖片解碼完成
        return Promise.all(slide.pendingImages.map(function (img) {
          return img.decode ? img.decode() : Promise.resolve();
        }))
        .then(function () { return document.fonts.ready; })
        .then(function () { return slide.renderToCanvas(scale); });
      });
  }

  function boardReady() {
    return NT.BoardFactory.create(global.BOARD)
      .then(function (slide) {
        return Promise.all(slide.pendingImages.map(function (img) {
          return img.decode ? img.decode() : Promise.resolve();
        }))
        .then(function () { return document.fonts.ready; });
      });
  }

  global.__renderBoard = function (scale) { return renderBoard(scale); };
  global.__boardReady = function () { return boardReady(); };

})(window);