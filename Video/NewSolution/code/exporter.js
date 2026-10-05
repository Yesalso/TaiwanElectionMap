/* ==========================================================================
   exporter.js — 匯出功能（瀏覽器下載 PNG）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  NT.Exporter = {
    download: function (slide, scale, filename) {
      scale = scale || 1;
      var dataUrl = slide.renderToCanvas(scale);
      var link = document.createElement('a');
      link.href = dataUrl;
      link.download = filename || 'board_' + (2560 * scale) + 'x' + (1440 * scale) + '.png';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },

    downloadAll: function (slide, filenamePrefix) {
      this.download(slide, 1, (filenamePrefix || 'board') + '_2560x1440.png');
      this.download(slide, 2, (filenamePrefix || 'board') + '_5120x2880.png');
    }
  };

})(window);