/* ==========================================================================
   layers.js — 繪圖圖層（地圖、候選人卡、票數帶、行政區列表）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  // ===================== 地圖圖層 =====================
  function MapLayer(model, layout) {
    this.model = model;
    this.layout = layout;
    this.projector = new NT.GeoProjector(model.geojson);
    this.cache = null;
  }

  MapLayer.prototype.render = function (ctx, scale) {
    var L = this.layout;
    var map = L.map;
    var x = map.x, y = map.y, w = map.w, h = map.h;

    ctx.save();
    ctx.translate(x, y);

    // 背景
    ctx.fillStyle = NT.Theme.BG.panel;
    ctx.fillRect(0, 0, w, h);

    // 繪製各行政區
    var self = this;
    this.model.districts.forEach(function (d) {
      var feat = self.model.geojson.features.find(function (f) { return f.properties.name === d.name; });
      if (!feat) return;

      self.projector.drawFeature(ctx, feat, 1, function () {
        return { fill: d.color, stroke: 'rgba(0,0,0,0.3)', lineWidth: 1 };
      });
    });

    ctx.restore();
  };

  // ===================== 候選人卡片圖層 =====================
  function CandidateCardLayer(model, layout, side) {
    this.model = model;
    this.layout = layout;
    this.side = side; // 'left' 或 'right'
    this.candidate = side === 'left' ? model.left : model.right;
    this.photos = null;
  }

  CandidateCardLayer.prototype.setPhotos = function (photos) { this.photos = photos; };

  CandidateCardLayer.prototype.render = function (ctx, scale) {
    var L = this.layout;
    var card = L.card;
    var c = this.candidate;
    var x = this.side === 'left' ? card.leftX : card.rightX;
    var y = card.y;
    var w = card.w, h = card.h;

    ctx.save();
    ctx.translate(x, y);

    // 卡片背景漸層
    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, c.theme.light + '40');
    grad.addColorStop(1, c.theme.dark);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // 邊框
    ctx.strokeStyle = c.theme.main;
    ctx.lineWidth = 3 * scale;
    ctx.strokeRect(1.5 * scale, 1.5 * scale, w - 3 * scale, h - 3 * scale);

    // 當選標記
    if (c.elected) {
      ctx.fillStyle = NT.Layout.color.elected;
      ctx.font = 'bold ' + (28 * scale) + 'px ' + NT.FONT_STACK;
      ctx.fillText('當選', w - 100 * scale, 50 * scale);
    }

    // 照片
    if (this.photos && this.photos[c.key]) {
      var ph = card.photo;
      var img = this.photos[c.key];
      ctx.drawImage(img, ph.x, ph.y, ph.w, ph.h);
    }

    // 姓名
    ctx.fillStyle = NT.Layout.color.textMain;
    ctx.font = 'bold ' + (card.nameSize * scale) + 'px ' + NT.FONT_STACK;
    ctx.textAlign = 'center';
    ctx.fillText(c.name, w / 2, card.nameY);

    // 號次與政黨
    ctx.font = (card.partySize * scale) + 'px ' + NT.FONT_STACK;
    ctx.fillStyle = NT.Layout.color.textDim;
    ctx.fillText(c.number + '號  ' + c.party, w / 2, card.partyY);

    // 得票數
    ctx.fillStyle = NT.Layout.color.textMain;
    ctx.font = 'bold ' + (card.votesSize * scale) + 'px ' + NT.FONT_DISPLAY_NUM;
    ctx.fillText(c.votesLabel(), w / 2, card.votesY);

    // 得票率
    ctx.fillStyle = c.theme.main;
    ctx.font = 'bold ' + (card.pctSize * scale) + 'px ' + NT.FONT_DISPLAY_NUM;
    ctx.fillText(c.pctText() + '%', w / 2, card.pctY);

    ctx.restore();
  };

  // ===================== 底部票數帶 =====================
  function RibbonLayer(model, layout) {
    this.model = model;
    this.layout = layout;
  }

  RibbonLayer.prototype.render = function (ctx, scale) {
    var L = this.layout;
    var r = L.ribbon;
    var x = L.pad, y = r.y, w = L.W - 2 * L.pad, h = r.h;

    ctx.save();
    ctx.translate(x, y);

    var segs = this.model.ribbonSegments();
    var curX = 0;
    segs.forEach(function (seg) {
      var segW = w * seg.ratio;
      ctx.fillStyle = seg.color;
      ctx.fillRect(curX, r.h - r.segH, segW, r.segH);
      // 標籤
      ctx.fillStyle = '#fff';
      ctx.font = (r.labelSize * scale) + 'px ' + NT.FONT_STACK;
      ctx.textAlign = 'left';
      ctx.fillText(seg.label + ' ' + (seg.ratio * 100).toFixed(1) + '%', curX + 8 * scale, r.h - 8 * scale);
      curX += segW;
    });

    ctx.restore();
  };

  // ===================== 行政區列表 =====================
  function DistrictListLayer(model, layout) {
    this.model = model;
    this.layout = layout;
  }

  DistrictListLayer.prototype.render = function (ctx, scale) {
    var L = this.layout;
    var dl = L.districtList;
    var x = dl.x, y = dl.y, w = dl.w, h = dl.h;

    ctx.save();
    ctx.translate(x, y);

    // 背景
    ctx.fillStyle = NT.Theme.BG.panel;
    ctx.fillRect(0, 0, w, h);

    // 標題
    ctx.fillStyle = NT.Layout.color.textMain;
    ctx.font = 'bold ' + (24 * scale) + 'px ' + NT.FONT_STACK;
    ctx.fillText('行政區得票', 16 * scale, 36 * scale);

    // 列表
    var itemH = dl.itemH * scale;
    var nameSize = dl.nameSize * scale;
    var votesSize = dl.votesSize * scale;
    var maxItems = Math.floor((h - 50 * scale) / itemH);

    this.model.districts.slice(0, maxItems).forEach(function (d, i) {
      var iy = 50 * scale + i * itemH;
      // 底色
      ctx.fillStyle = d.color + '40';
      ctx.fillRect(0, iy, w, itemH - 2 * scale);
      // 勝方色條
      ctx.fillStyle = d.color;
      ctx.fillRect(0, iy, 6 * scale, itemH - 2 * scale);
      // 行政區名
      ctx.fillStyle = NT.Layout.color.textMain;
      ctx.font = nameSize + 'px ' + NT.FONT_STACK;
      ctx.textAlign = 'left';
      ctx.fillText(d.short, 20 * scale, iy + itemH * 0.65);
      // 得票數
      var winner = d.votes[d.winnerKey] || 0;
      ctx.fillStyle = NT.Layout.color.textDim;
      ctx.font = votesSize + 'px ' + NT.FONT_NUM;
      ctx.textAlign = 'right';
      ctx.fillText(NT.Utils.voteComma(winner), w - 16 * scale, iy + itemH * 0.65);
    });

    ctx.restore();
  };

  // ===================== 小候選人列 =====================
  function MinorRowLayer(model, layout) {
    this.model = model;
    this.layout = layout;
    this.photos = null;
  }

  MinorRowLayer.prototype.setPhotos = function (photos) { this.photos = photos; };

  MinorRowLayer.prototype.render = function (ctx, scale) {
    if (!this.model.minors.length) return;
    var L = this.layout;
    var mr = L.minorRow;
    var y = mr.y;
    var totalW = this.model.minors.length * mr.itemW + (this.model.minors.length - 1) * mr.gap;
    var startX = (L.W - totalW) / 2;

    ctx.save();
    ctx.translate(startX, y);

    this.model.minors.forEach(function (c, i) {
      var x = i * (mr.itemW + mr.gap);
      // 背景
      ctx.fillStyle = c.theme.main + '30';
      ctx.fillRect(x, 0, mr.itemW, mr.h);
      // 照片
      if (this.photos && this.photos[c.key]) {
        var img = this.photos[c.key];
        ctx.drawImage(img, x + 8, 4, 40, 40);
      }
      // 姓名
      ctx.fillStyle = NT.Layout.color.textMain;
      ctx.font = 'bold 18px ' + NT.FONT_STACK;
      ctx.textAlign = 'center';
      ctx.fillText(c.name, x + mr.itemW / 2, mr.h - 8);
    }, this);

    ctx.restore();
  };

  // ===================== 頁眉 =====================
  function HeaderLayer(model, layout) {
    this.model = model;
    this.layout = layout;
  }

  HeaderLayer.prototype.render = function (ctx, scale) {
    var L = this.layout;
    var h = L.header;
    var meta = this.model.meta;

    ctx.save();

    // 背景漸層
    var grad = ctx.createLinearGradient(0, 0, 0, h.h);
    grad.addColorStop(0, NT.Theme.BG.top);
    grad.addColorStop(0.5, NT.Theme.BG.mid);
    grad.addColorStop(1, NT.Theme.BG.bottom);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, L.W, h.h);

    // 標題
    ctx.fillStyle = NT.Layout.color.textMain;
    ctx.font = 'bold ' + (h.titleSize * scale) + 'px ' + NT.FONT_STACK;
    ctx.textAlign = 'left';
    ctx.fillText(meta.election, h.seal.x + h.seal.size + 24 * scale, h.titleY);

    // 日期
    ctx.font = (h.dateSize * scale) + 'px ' + NT.FONT_DISPLAY_NUM;
    ctx.fillStyle = NT.Layout.color.textDim;
    ctx.fillText(meta.date + '  投票日', h.seal.x + h.seal.size + 24 * scale, h.dateY);

    // 市徽
    if (this.sealImg) {
      ctx.drawImage(this.sealImg, h.seal.x, h.seal.y, h.seal.size, h.seal.size);
    }

    ctx.restore();
  };

  HeaderLayer.prototype.setSeal = function (img) { this.sealImg = img; };

  NT.MapLayer = MapLayer;
  NT.CandidateCardLayer = CandidateCardLayer;
  NT.RibbonLayer = RibbonLayer;
  NT.DistrictListLayer = DistrictListLayer;
  NT.MinorRowLayer = MinorRowLayer;
  NT.HeaderLayer = HeaderLayer;

})(window);