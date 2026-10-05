/* ==========================================================================
   app.js — 應用程式入口（瀏覽器模式）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  // 簡單的載入管理
  NT.App = {
    init: function (boardData) {
      return NT.BoardFactory.create(boardData).then(function (slide) {
        var canvas = document.getElementById('canvas');
        if (!canvas) throw new Error('找不到 #canvas 元素');
        var ctx = canvas.getContext('2d');
        slide.render(ctx, 1);
        return slide;
      });
    }
  };

  // 全域暴露給 index.html 使用
  global.NT = NT;

})(window);