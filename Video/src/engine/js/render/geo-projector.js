/* ==========================================================================
   geo-projector.js — 地理座標 → 畫面座標 的投影器
   --------------------------------------------------------------------------
   新北市範圍不大，採等距圓柱投影加上緯度的 cos 修正即可，
   不需要引入 d3-geo 之類的函式庫。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  /**
   * GeoProjector
   * @param {object} geojson   FeatureCollection（WGS84）
   * @param {object} rect      {x, y, w, h} 目標框
   * @param {object} opt       {pad: number, fit: 'contain'}
   */
  function GeoProjector(geojson, rect, opt) {
    this.geojson = geojson;
    this.rect = rect;
    this.opt = opt || {};
    this.pad = this.opt.pad || 0;
    this._prepare();
  }

  GeoProjector.prototype._prepare = function () {
    var feats = this.geojson.features || [];

    /* 以整體的緯度中位數做 cos 修正，讓東西向不被拉長 */
    var latSum = 0, latN = 0;
    var minLon = Infinity, maxLon = -Infinity;
    var minLat = Infinity, maxLat = -Infinity;

    function scanRing(ring) {
      for (var i = 0; i < ring.length; i++) {
        var lon = ring[i][0], lat = ring[i][1];
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        latSum += lat; latN++;
      }
    }

    function scanGeom(g) {
      if (!g) return;
      if (g.type === 'Polygon') {
        for (var i = 0; i < g.coordinates.length; i++) scanRing(g.coordinates[i]);
      } else if (g.type === 'MultiPolygon') {
        for (var j = 0; j < g.coordinates.length; j++) {
          for (var k = 0; k < g.coordinates[j].length; k++) scanRing(g.coordinates[j][k]);
        }
      }
    }

    for (var f = 0; f < feats.length; f++) scanGeom(feats[f].geometry);

    this.lat0 = latSum / Math.max(1, latN);
    this.kx = Math.cos(this.lat0 * Math.PI / 180);

    var x0 = minLon * this.kx, x1 = maxLon * this.kx;
    var y0 = minLat, y1 = maxLat;

    var boxW = Math.max(1e-9, x1 - x0);
    var boxH = Math.max(1e-9, y1 - y0);

    var availW = this.rect.w - this.pad * 2;
    var availH = this.rect.h - this.pad * 2;

    this.scale = Math.min(availW / boxW, availH / boxH);
    this.offX = this.rect.x + (this.rect.w - boxW * this.scale) / 2 - x0 * this.scale;
    this.offY = this.rect.y + (this.rect.h - boxH * this.scale) / 2 + y1 * this.scale;

    /* 投影後的實際佔用範圍（供描邊、加光暈用） */
    this.painted = {
      x: this.rect.x + (this.rect.w - boxW * this.scale) / 2,
      y: this.rect.y + (this.rect.h - boxH * this.scale) / 2,
      w: boxW * this.scale,
      h: boxH * this.scale
    };
  };

  /** lon/lat -> {x, y} */
  GeoProjector.prototype.project = function (lon, lat) {
    return {
      x: this.offX + lon * this.kx * this.scale,
      y: this.offY - lat * this.scale
    };
  };

  /** 把一段 ring 加進目前路徑 */
  GeoProjector.prototype._ring = function (ctx, ring) {
    for (var i = 0; i < ring.length; i++) {
      var p = this.project(ring[i][0], ring[i][1]);
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
  };

  /** 建立單一 feature 的路徑（不 fill / stroke） */
  GeoProjector.prototype.path = function (ctx, geometry) {
    ctx.beginPath();
    if (!geometry) return;
    if (geometry.type === 'Polygon') {
      for (var i = 0; i < geometry.coordinates.length; i++) {
        this._ring(ctx, geometry.coordinates[i]);
      }
    } else if (geometry.type === 'MultiPolygon') {
      for (var j = 0; j < geometry.coordinates.length; j++) {
        for (var k = 0; k < geometry.coordinates[j].length; k++) {
          this._ring(ctx, geometry.coordinates[j][k]);
        }
      }
    }
  };

  /** 建立所有 feature 的路徑（用於描外框） */
  GeoProjector.prototype.pathAll = function (ctx) {
    ctx.beginPath();
    var feats = this.geojson.features || [];
    for (var f = 0; f < feats.length; f++) {
      var g = feats[f].geometry;
      if (!g) continue;
      if (g.type === 'Polygon') {
        for (var i = 0; i < g.coordinates.length; i++) this._ring(ctx, g.coordinates[i]);
      } else if (g.type === 'MultiPolygon') {
        for (var j = 0; j < g.coordinates.length; j++) {
          for (var k = 0; k < g.coordinates[j].length; k++) {
            this._ring(ctx, g.coordinates[j][k]);
          }
        }
      }
    }
  };

  NT.GeoProjector = GeoProjector;

})(window);
