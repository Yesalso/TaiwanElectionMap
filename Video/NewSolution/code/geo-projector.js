/* ==========================================================================
   geo-projector.js — GeoJSON 投影與簡化（Canvas 2D 繪製用）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  function GeoProjector(geojson, bounds, padding) {
    this.geojson = geojson;
    this.bounds = bounds || this._calcBounds(geojson);
    this.padding = padding || 0.02;
    this._initTransform();
  }

  GeoProjector.prototype._calcBounds = function (gj) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    gj.features.forEach(function (f) {
      this._expandBounds(f.geometry, minX, minY, maxX, maxY);
    }, this);
    return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
  };

  GeoProjector.prototype._expandBounds = function (geom, minX, minY, maxX, maxY) {
    if (!geom) return;
    if (geom.type === 'Point') {
      this._upd(geom.coordinates[0], geom.coordinates[1]);
    } else if (geom.type === 'MultiPoint') {
      geom.coordinates.forEach(this._upd, this);
    } else if (geom.type === 'LineString') {
      geom.coordinates.forEach(this._upd, this);
    } else if (geom.type === 'MultiLineString') {
      geom.coordinates.forEach(function (ls) { ls.forEach(this._upd, this); }, this);
    } else if (geom.type === 'Polygon') {
      geom.coordinates.forEach(function (ring) { ring.forEach(this._upd, this); }, this);
    } else if (geom.type === 'MultiPolygon') {
      geom.coordinates.forEach(function (poly) { poly.forEach(function (ring) { ring.forEach(this._upd, this); }, this); }, this);
    } else if (geom.type === 'GeometryCollection') {
      geom.geometries.forEach(this._expandBounds, this);
    }
    function _upd(x, y) { if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; }
  };

  GeoProjector.prototype._initTransform = function () {
    var b = this.bounds;
    var w = b.maxX - b.minX;
    var h = b.maxY - b.minY;
    var padX = w * this.padding;
    var padY = h * this.padding;
    this.xScale = 1 / (w + 2 * padX);
    this.yScale = 1 / (h + 2 * padY);
    this.xOff = -(b.minX - padX);
    this.yOff = -(b.minY - padY);
  };

  /** 將經緯度投影為 0~1 正規化座標 */
  GeoProjector.prototype.project = function (lon, lat) {
    return {
      x: (lon + this.xOff) * this.xScale,
      y: 1 - (lat + this.yOff) * this.yScale  // Y 軸翻轉
    };
  };

  /** 繪製單一 feature 到 Canvas */
  GeoProjector.prototype.drawFeature = function (ctx, feature, scale, styleFn) {
    var geom = feature.geometry;
    if (!geom) return;
    var style = styleFn ? styleFn(feature) : {};
    ctx.fillStyle = style.fill || '#333';
    ctx.strokeStyle = style.stroke || '#000';
    ctx.lineWidth = (style.lineWidth || 1) * scale;

    var drawRing = function (ring) {
      ctx.beginPath();
      var first = true;
      ring.forEach(function (coord) {
        var p = this.project(coord[0], coord[1]);
        var x = p.x * ctx.canvas.width;
        var y = p.y * ctx.canvas.height;
        if (first) { ctx.moveTo(x, y); first = false; }
        else { ctx.lineTo(x, y); }
      }, this);
      ctx.closePath();
    }.bind(this);

    if (geom.type === 'Polygon') {
      geom.coordinates.forEach(drawRing);
      if (style.fill) ctx.fill();
      if (style.stroke) ctx.stroke();
    } else if (geom.type === 'MultiPolygon') {
      geom.coordinates.forEach(function (poly) { poly.forEach(drawRing); });
      if (style.fill) ctx.fill();
      if (style.stroke) ctx.stroke();
    }
  };

  /** 批次繪製所有 features */
  GeoProjector.prototype.drawAll = function (ctx, scale, styleFn) {
    this.geojson.features.forEach(function (f) {
      this.drawFeature(ctx, f, scale, styleFn);
    }, this);
  };

  NT.GeoProjector = GeoProjector;

})(window);