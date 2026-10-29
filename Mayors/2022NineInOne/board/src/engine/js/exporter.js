/* ==========================================================================
   exporter.js — 匯出 PNG
   --------------------------------------------------------------------------
   地圖現在以實體檔（assets/vote_map.png）載入：http:// 下一切正常；
   但 file:// 下本機圖檔會把 canvas 汙染成「畫得出來、讀不回去」，
   toBlob／toDataURL 會拋 SecurityError。這裡在匯出前先探測，
   失敗時給出明確原因與兩條解法，而不是丟一個 SecurityError 給使用者。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var L = NT.Layout;

  function Exporter() {}

  /**
   * 產生指定倍率的畫布
   * @param {NT.Slide} slide
   * @param {number} scale 1 → 2560×1440，2 → 5120×2880
   */
  Exporter.renderToCanvas = function (slide, scale) {
    var s = scale || 1;
    var cv = document.createElement('canvas');
    cv.width = Math.round(L.W * s);
    cv.height = Math.round(L.H * s);
    var ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    slide.render(ctx, s);
    return cv;
  };

  /**
   * 畫布讀得到像素嗎？被跨來源圖檔污染的畫布會在 getImageData 拋 SecurityError。
   */
  Exporter.canvasReadable = function (ctx) {
    try {
      ctx.getImageData(0, 0, 1, 1);
      return true;
    } catch (e) {
      return false;
    }
  };

  /**
   * 轉成 Blob
   */
  Exporter.toBlob = function (canvas) {
    return new Promise(function (resolve, reject) {
      if (canvas.toBlob) {
        canvas.toBlob(function (b) {
          b ? resolve(b) : reject(new Error('產生 PNG 失敗'));
        }, 'image/png');
      } else {
        try {
          var data = canvas.toDataURL('image/png');
          var bin = atob(data.split(',')[1]);
          var arr = new Uint8Array(bin.length);
          for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
          resolve(new Blob([arr], { type: 'image/png' }));
        } catch (e) { reject(e); }
      }
    });
  };

  /** 觸發瀏覽器下載 */
  Exporter.saveBlob = function (blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  };

  /**
   * 一次完成：渲染 → 轉檔 → 下載
   * @returns {Promise<{filename:string, bytes:number}>}
   */
  Exporter.download = function (slide, scale, baseName) {
    var s = scale || 1;
    var canvas = Exporter.renderToCanvas(slide, s);
    var name = (baseName || '看板') + '_' + (L.W * s) + 'x' + (L.H * s) + '.png';

    if (!Exporter.canvasReadable(canvas.getContext('2d'))) {
      return Promise.reject(new Error(
        'file:// 模式下瀏覽器禁止匯出含本機圖檔的看板。' +
        '解法一：用 http:// 開啟（node tools/_server.js 8622 後開 http://127.0.0.1:8622/index.html）；' +
        '解法二：重跑 python tools/build_assets.py 把最新地圖重新內嵌。'));
    }

    return Exporter.toBlob(canvas).then(function (blob) {
      Exporter.saveBlob(blob, name);
      return { filename: name, bytes: blob.size };
    });
  };

  NT.Exporter = Exporter;

})(window);
