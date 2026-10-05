/* ==========================================================================
   slide.js — 看板主類別：協調各圖層、載入素材、統一渲染入口
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  function Slide(board) {
    this.board = board;
    this.model = new NT.ElectionModel(board);
    this.layout = NT.Layout.atScale(1);
    this.assets = { photos: {}, seal: null, map: null };
    this.layers = [];
    this.pendingImages = [];
    this._built = false;
  }

  /** 載入所有圖片素材 */
  Slide.prototype.loadAssets = function () {
    var self = this;
    var promises = [];

    // 候選人照片
    this.model.candidates.forEach(function (c) {
      if (!c.photo) return;
      var p = new Promise(function (resolve) {
        var img = new Image();
        img.crossOrigin = 'anonymous';
        img.src = c.photo + '?v=' + Date.now();
        img.onload = img.onerror = function () {
          self.assets.photos[c.key] = img;
          resolve();
        };
      });
      self.pendingImages.push(img);
      promises.push(p);
    });

    // 市徽
    var sealSrc = 'assets/city_seal.png';
    var sealPromise = new Promise(function (resolve) {
      var img = new Image();
      img.crossOrigin = 'anonymous';
      img.src = sealSrc + '?v=' + Date.now();
      img.onload = img.onerror = function () {
        self.assets.seal = img;
        resolve();
      };
    });
    self.pendingImages.push(sealPromise);
    promises.push(sealPromise);

    return Promise.all(promises);
  };

  /** 建立圖層 */
  Slide.prototype.buildLayers = function () {
    var m = this.model, L = this.layout, a = this.assets;

    this.layers = [
      new NT.HeaderLayer(m, L),
      new NT.MapLayer(m, L),
      new NT.CandidateCardLayer(m, L, 'left'),
      new NT.CandidateCardLayer(m, L, 'right'),
      new NT.RibbonLayer(m, L),
      new NT.DistrictListLayer(m, L),
      new NT.MinorRowLayer(m, L)
    ];

    // 注入素材
    this.layers[0].setSeal(a.seal);
    this.layers[2].setPhotos(a.photos);
    this.layers[3].setPhotos(a.photos);
    this.layers[5].setPhotos(a.photos);
  };

  /** 主渲染入口 */
  Slide.prototype.render = function (ctx, scale) {
    if (!this._built) {
      this.buildLayers();
      this._built = true;
    }

    // 按比例縮放 layout
    var scaledLayout = NT.Layout.atScale(scale);
    this.layers.forEach(function (layer) {
      layer.layout = scaledLayout;
    });

    // 清除畫布
    ctx.fillStyle = NT.Theme.BG.deep;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    // 依序渲染各圖層（後蓋前）
    this.layers.forEach(function (layer) {
      layer.render(ctx, scale);
    });
  };

  /** 無頭模式專用：渲染到新 Canvas 並回傳 dataURL */
  Slide.prototype.renderToCanvas = function (scale) {
    var canvas = document.createElement('canvas');
    canvas.width = 2560 * scale;
    canvas.height = 1440 * scale;
    var ctx = canvas.getContext('2d');
    this.render(ctx, scale);
    return canvas.toDataURL('image/png');
  };

  NT.Slide = Slide;

  // ===================== BoardFactory =====================
  NT.BoardFactory = {
    create: function (boardData) {
      return Promise.resolve().then(function () {
        var slide = new NT.Slide(boardData);
        return slide.loadAssets().then(function () {
          return slide;
        });
      });
    }
  };

})(window);