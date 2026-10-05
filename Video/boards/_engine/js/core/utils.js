/* ==========================================================================
   utils.js — 全域命名空間與靜態工具
   --------------------------------------------------------------------------
   全站以 NT（New Taipei）命名空間掛載，使用傳統 <script> 載入，
   不用 ES Module，這樣直接用 file:// 雙擊 index.html 也能正常執行。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};

  /* ---------------------------------------------------------------------
     Utils：與繪圖、數字、顏色相關的無狀態工具
     --------------------------------------------------------------------- */
  function Utils() {}

  /* ------------------------------ 數字 ------------------------------ */

  /** 1450 -> "1,450" */
  Utils.group = function (n) {
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

  /**
   * 票數的中文「萬」制寫法（看板統一使用）：
   *   959302 -> "95萬9302"、22207 -> "2萬2207"、770000 -> "77萬"
   * 一萬票（含）以下維持純數字。
   */
  Utils.voteWan = function (n) {
    var v = Math.round(n);
    if (Math.abs(v) <= 10000) return String(v);
    var wan = Math.trunc(v / 10000);
    var rest = Math.abs(v % 10000);
    if (rest === 0) return wan + '萬';
    return wan + '萬' + ('000' + rest).slice(-4);
  };

  /**
   * 把票數切成「數字 / 非數字」的片段，讓圖層可以給兩者不同字級
   * （例如數字用大字、萬與票用小字）。
   *   959302 -> [{text:"95",num:true},{text:"萬",num:false},
   *              {text:"9302",num:true},{text:"票",num:false}]
   */
  Utils.voteParts = function (n, unit) {
    var s = Utils.voteWan(n) + (unit === undefined ? '票' : unit);
    var parts = [];
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      var isNum = ch >= '0' && ch <= '9';
      var last = parts[parts.length - 1];
      if (last && last.num === isNum) last.text += ch;
      else parts.push({ text: ch, num: isNum });
    }
    return parts;
  };

  /** 0.5006 -> "50.06"（保留小數，回傳字串） */
  Utils.pct = function (v, digits) {
    return (v * 100).toFixed(digits === undefined ? 2 : digits);
  };

  Utils.clamp = function (v, lo, hi) {
    return v < lo ? lo : (v > hi ? hi : v);
  };

  /** 線性內插：t=0 回 a，t=1 回 b */
  Utils.lerp = function (a, b, t) {
    return a + (b - a) * t;
  };

  /* ------------------------------ 顏色 ------------------------------ */

  /** "#2f6bd8" -> [47,107,216] */
  Utils.hexToRgb = function (hex) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  };

  Utils.rgbToHex = function (rgb) {
    function p(v) {
      var s = Math.max(0, Math.min(255, Math.round(v))).toString(16);
      return s.length === 1 ? '0' + s : s;
    }
    return '#' + p(rgb[0]) + p(rgb[1]) + p(rgb[2]);
  };

  /** 兩色線性混合，t=0 -> a，t=1 -> b */
  Utils.mix = function (a, b, t) {
    var ca = Utils.hexToRgb(a), cb = Utils.hexToRgb(b);
    return Utils.rgbToHex([
      Utils.lerp(ca[0], cb[0], t),
      Utils.lerp(ca[1], cb[1], t),
      Utils.lerp(ca[2], cb[2], t)
    ]);
  };

  /** hex -> "rgba(r,g,b,a)" */
  Utils.alpha = function (hex, a) {
    var c = Utils.hexToRgb(hex);
    return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')';
  };

  Utils.lighten = function (hex, t) { return Utils.mix(hex, '#ffffff', t); };
  Utils.darken = function (hex, t) { return Utils.mix(hex, '#000000', t); };

  /* ------------------------------ 幾何 ------------------------------ */

  /** 圓角矩形路徑（只建立路徑，不填色） */
  Utils.roundRectPath = function (ctx, x, y, w, h, r) {
    var rr = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.lineTo(x + w - rr, y);
    ctx.arcTo(x + w, y, x + w, y + rr, rr);
    ctx.lineTo(x + w, y + h - rr);
    ctx.arcTo(x + w, y + h, x + w - rr, y + h, rr);
    ctx.lineTo(x + rr, y + h);
    ctx.arcTo(x, y + h, x, y + h - rr, rr);
    ctx.lineTo(x, y + rr);
    ctx.arcTo(x, y, x + rr, y, rr);
    ctx.closePath();
  };

  Utils.fillRoundRect = function (ctx, x, y, w, h, r, fill) {
    Utils.roundRectPath(ctx, x, y, w, h, r);
    ctx.fillStyle = fill;
    ctx.fill();
  };

  Utils.strokeRoundRect = function (ctx, x, y, w, h, r, stroke, lw) {
    Utils.roundRectPath(ctx, x, y, w, h, r);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lw || 1;
    ctx.stroke();
  };

  /* ------------------------------ 文字 ------------------------------ */

  /** 組字串 font：size(px) / weight / 字族 */
  Utils.font = function (size, weight, family) {
    return (weight || 400) + ' ' + size + 'px ' + (family || NT.FONT_STACK);
  };

  /**
   * 逐字繪製以支援字距（canvas 的 letterSpacing 支援度不一）。
   * align: 'left' | 'center' | 'right'
   */
  Utils.drawSpacedText = function (ctx, text, x, y, spacing, align) {
    if (!spacing) {
      ctx.fillText(text, x, y);
      return ctx.measureText(text).width;
    }
    var chars = String(text).split('');
    var widths = chars.map(function (c) { return ctx.measureText(c).width; });
    var total = widths.reduce(function (s, w) { return s + w; }, 0)
      + spacing * (chars.length - 1);
    var cursor = x;
    if (align === 'center') cursor = x - total / 2;
    else if (align === 'right') cursor = x - total;
    ctx.textAlign = 'left';
    for (var i = 0; i < chars.length; i++) {
      ctx.fillText(chars[i], cursor, y);
      cursor += widths[i] + spacing;
    }
    ctx.textAlign = align || 'left';
    return total;
  };

  /** 量測（含字距）後的寬度 */
  Utils.measureSpaced = function (ctx, text, spacing) {
    var chars = String(text).split('');
    var w = chars.reduce(function (s, c) { return s + ctx.measureText(c).width; }, 0);
    return w + (spacing || 0) * Math.max(0, chars.length - 1);
  };

  /**
   * 把一段文字裁到指定寬度內，超出時逐字刪去並補上「…」。
   * 呼叫前請自行設定好 ctx.font。maxWidth 為 null/undefined 或
   * 文字本來就塞得下時，原字串原封不動回傳。
   */
  Utils.fitText = function (ctx, text, maxWidth, spacing) {
    var s = String(text);
    if (maxWidth === null || maxWidth === undefined) return s;
    if (Utils.measureSpaced(ctx, s, spacing) <= maxWidth) return s;
    var cut = s;
    while (cut.length > 1 &&
           Utils.measureSpaced(ctx, cut + '…', spacing) > maxWidth) {
      cut = cut.slice(0, -1);
    }
    return cut + '…';
  };

  /**
   * 一次畫好一段文字。
   * opt: {x, y, size, weight, family, color, align, baseline, spacing, shadow}
   * shadow: {color, blur, x, y}
   */
  Utils.text = function (ctx, str, opt) {
    ctx.save();
    ctx.font = Utils.font(opt.size, opt.weight, opt.family);
    ctx.fillStyle = opt.color || '#fff';
    ctx.textAlign = opt.align || 'left';
    ctx.textBaseline = opt.baseline || 'alphabetic';
    if (opt.shadow) {
      ctx.shadowColor = opt.shadow.color;
      ctx.shadowBlur = opt.shadow.blur || 0;
      ctx.shadowOffsetX = opt.shadow.x || 0;
      ctx.shadowOffsetY = opt.shadow.y || 0;
    }
    ctx.globalAlpha = opt.alpha === undefined ? 1 : opt.alpha;
    var w = Utils.drawSpacedText(ctx, str, opt.x, opt.y, opt.spacing || 0, opt.align || 'left');
    ctx.restore();
    return w;
  };

  /**
   * 同一行混用不同字級的富文字（共用同一條基線）。
   * segments: [{text, size, weight, family, color, spacing}, ...]
   * opt: {x, y, align:'left'|'center'|'right', baseline, shadow}
   * 回傳整行寬度。
   */
  Utils.richText = function (ctx, segments, opt) {
    opt = opt || {};
    var align = opt.align || 'left';
    var i, seg, widths = [], total = 0;

    for (i = 0; i < segments.length; i++) {
      seg = segments[i];
      ctx.save();
      ctx.font = Utils.font(seg.size || opt.size, seg.weight || opt.weight,
        seg.family || opt.family);
      var w = Utils.measureSpaced(ctx, seg.text, seg.spacing || 0);
      ctx.restore();
      widths.push(w);
      total += w;
    }

    var cursor = opt.x;
    if (align === 'center') cursor = opt.x - total / 2;
    else if (align === 'right') cursor = opt.x - total;

    for (i = 0; i < segments.length; i++) {
      seg = segments[i];
      Utils.text(ctx, seg.text, {
        x: cursor, y: opt.y,
        size: seg.size || opt.size,
        weight: seg.weight || opt.weight,
        family: seg.family || opt.family,
        color: seg.color || opt.color,
        align: 'left',
        baseline: opt.baseline || 'alphabetic',
        spacing: seg.spacing || 0,
        shadow: opt.shadow
      });
      cursor += widths[i];
    }
    return total;
  };

  /* ------------------------------ 線性漸層 ------------------------------ */

  /**
   * 建立線性漸層。
   * stops: [[offset, color], ...]
   */
  Utils.gradient = function (ctx, x0, y0, x1, y1, stops) {
    var g = ctx.createLinearGradient(x0, y0, x1, y1);
    for (var i = 0; i < stops.length; i++) g.addColorStop(stops[i][0], stops[i][1]);
    return g;
  };

  Utils.radial = function (ctx, x0, y0, r0, x1, y1, r1, stops) {
    var g = ctx.createRadialGradient(x0, y0, r0, x1, y1, r1);
    for (var i = 0; i < stops.length; i++) g.addColorStop(stops[i][0], stops[i][1]);
    return g;
  };

  /* ------------------------------ 素材路徑 ------------------------------ */

  /**
   * 把「邏輯素材路徑」換成實際 URL。
   *
   * 引擎內部一律用邏輯檔名（`assets/map.png`、`candidate/ko.png`…），
   * 實際檔案在哪由 `board.files.js`（tools/build_board.py 產生）決定 ——
   * 透明化成品集中在 `NewSolution/png/processed/`，不散落到各場的 assets/。
   *
   * 沒掛 BOARD_FILES 時原樣回傳（沿用 assets/ 相對路徑，舊場次照樣能跑）。
   */
  Utils.resolveAsset = function (p) {
    if (!p) return p;
    if (/^(data:|blob:|https?:|\/\/|\/)/i.test(p)) return p;
    var files = global.BOARD_FILES && global.BOARD_FILES.files;
    if (!files) return p;
    var key = String(p).replace(/^\.?\//, '').replace(/^assets\//, '');
    return files[key] || p;
  };

  /* ------------------------------ 影像 ------------------------------ */

  /**
   * 把 data URI / URL 載入成 HTMLImageElement（回傳 Promise）。
   */
  Utils.loadImage = function (src) {
    return new Promise(function (resolve, reject) {
      if (!src) return resolve(null);
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { reject(new Error('圖片載入失敗：' + src.slice(0, 48))); };
      img.src = src;
    });
  };

  /**
   * 把圖裡「海報自帶的標題／圖例」等雜區擦掉，再裁掉外圍透明邊，
   * 回傳一張新的 canvas（可直接當 drawImage 的來源用，用法與 Image 相同）。
   *
   * opt:
   *   width   工作寬度，預設 3600（低於原圖可省記憶體，仍足夠 2× 匯出用）
   *   erase   [{x, y, w, h}]——以「圖寬高的比例」描述的擦除矩形，可給多個
   *   content {x, y, w, h}——擦完後內容外框的「比例」。
   *            有給就用它直接裁，「不讀像素」：這樣在 file:// 下
   *            （canvas 被污染、讀不到像素）也能照樣裁出乾淨的地圖本體。
   *            沒給才掃 alpha 外框（需要 canvas 可讀）。
   *   pad     掃描模式裁切時四周額外保留的邊（占寬的比例，預設 0）
   *
   * 任何一步失敗都回傳 null，呼叫端應退回原圖。
   */
  Utils.eraseAndCrop = function (img, opt) {
    try {
      if (!img || !img.width) return null;
      var W = opt.width || 3600;
      var s = W / img.width;
      var H = Math.round(img.height * s);
      var work = document.createElement('canvas');
      work.width = W;
      work.height = H;
      var c = work.getContext('2d');
      c.drawImage(img, 0, 0, W, H);

      var erase = opt.erase || [];
      for (var i = 0; i < erase.length; i++) {
        var r = erase[i];
        c.clearRect(r.x * W, r.y * H, r.w * W, r.h * H);
      }

      /* 內容外框：優先用事先量好的比例（免讀像素），否則現場掃 alpha */
      var box = opt.content;
      if (!box) {
        var d = c.getImageData(0, 0, W, H).data;
        var A = 8, x0 = W, y0 = H, x1 = -1, y1 = -1;
        for (var y = 0; y < H; y++) {
          var row = y * W;
          for (var x = 0; x < W; x++) {
            if (d[(row + x) * 4 + 3] > A) {
              if (x < x0) x0 = x;
              if (x > x1) x1 = x;
              if (y < y0) y0 = y;
              if (y > y1) y1 = y;
            }
          }
        }
        if (x1 < 0) return null;   // 全被擦光了
        var pad = (opt.pad || 0) * W;
        x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
        x1 = Math.min(W - 1, x1 + pad); y1 = Math.min(H - 1, y1 + pad);
        box = { x: x0 / W, y: y0 / H, w: (x1 - x0 + 1) / W, h: (y1 - y0 + 1) / H };
      }

      var bw = Math.max(1, Math.round(box.w * W));
      var bh = Math.max(1, Math.round(box.h * H));
      var out = document.createElement('canvas');
      out.width = bw;
      out.height = bh;
      out.getContext('2d').drawImage(work,
        box.x * W, box.y * H, box.w * W, box.h * H, 0, 0, bw, bh);
      return out;
    } catch (e) {
      return null;
    }
  };

  /* drawImageCover() 已移除：它唯一的用途是把候選人照片以 cover 方式填進
     照片框，而看板已不再畫候選人照片（見 layers.js 的 CandidateLayer）。
     要恢復照片的話，把上面那段「保持比例填滿 + anchorY/zoom/dx」的算法
     重新加回來即可。 */

  /** 在指定矩形內切圓角並執行繪製（自動 save/restore） */
  Utils.clipRoundRect = function (ctx, x, y, w, h, r, fn) {
    ctx.save();
    Utils.roundRectPath(ctx, x, y, w, h, r);
    ctx.clip();
    fn(ctx);
    ctx.restore();
  };

  NT.Utils = Utils;

})(window);
