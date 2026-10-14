/* ==========================================================================
   layers.js — 圖層（Layer）家族
   --------------------------------------------------------------------------
   每個圖層只負責「把一部分畫面畫到 canvas 上」，彼此不知道對方存在。
   Slide 負責依序呼叫它們。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;
  var T = NT.Theme;
  var L = NT.Layout;

  /* =====================================================================
     Layer —— 抽象基底
     ===================================================================== */
  function Layer(slide) {
    this.slide = slide;
    this.model = slide.model;
    this.assets = slide.assets;
  }
  /** 子類別覆寫 */
  Layer.prototype.draw = function () {};

  /* =====================================================================
     共用小工具
     ===================================================================== */
  var Marks = {
    /** 「圈選」記號：一個圈加一個勾（選票蓋章的意象） */
    voteMark: function (ctx, cx, cy, r, color, lw) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = lw || r * 0.2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - r * 0.44, cy + r * 0.04);
      ctx.lineTo(cx - r * 0.10, cy + r * 0.36);
      ctx.lineTo(cx + r * 0.48, cy - r * 0.34);
      ctx.stroke();
      ctx.restore();
    },

    /**
     * 當選印記：直接貼使用者提供的標誌圖（已先去白底成透明 PNG）。
     * 以中心點 + 邊長擺放，維持正方形比例。
     */
    stamp: function (ctx, img, cx, cy, size) {
      if (!img) return;
      ctx.save();
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, cx - size / 2, cy - size / 2, size, size);
      ctx.restore();
    },

    /**
     * 依「高度」貼一張透明 PNG：寬度照原圖比例換算，左上角對齊 (x, y)。
     * 市徽這類「主體不填滿畫布」的圖不適合用正方形外框，用高度最直覺。
     */
    imageByHeight: function (ctx, img, x, y, h) {
      if (!img || !img.width) return null;
      var w = h * (img.width / img.height);
      ctx.save();
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, x, y, w, h);
      ctx.restore();
      return { x: x, y: y, w: w, h: h };
    },

    /** 抽象政黨色塊（小圓角方塊 + 白點） */
    partyChip: function (ctx, x, y, size, theme) {
      var r = size * 0.28;
      ctx.save();
      ctx.fillStyle = U.gradient(ctx, x, y, x + size, y + size,
        [[0, theme.light], [1, theme.dark]]);
      U.roundRectPath(ctx, x, y, size, size, r);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.55)';
      ctx.lineWidth = 2;
      U.roundRectPath(ctx, x, y, size, size, r);
      ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.95)';
      ctx.beginPath();
      ctx.arc(x + size / 2, y + size / 2, size * 0.17, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  };
  NT.Marks = Marks;

  /* =====================================================================
     頁眉用的小工具：混字級單行（rich line）與日期字串拆解
     ===================================================================== */

  /**
   * 取某一段文字「後面」的間距。segs[i].gapAfter 有指定就用它，
   * 否則用整行共用的 gap。這樣同一行裡可以做出不同粗細的間距
   * （例如「11月│29日」：數字貼單位要緊，單位到下一組要鬆）。
   */
  function segGap(segs, i, gap) {
    var g = segs[i] && segs[i].gapAfter;
    return (g === undefined || g === null) ? (gap || 0) : g;
  }

  /**
   * 量一行混字級文字的「實際墨跡」範圍。
   * 除了寬度，也回傳 ascent／descent（真正的上下緣），
   * 因為數字沒有下伸部，若用 font size 當行高，底板上下會留白不均、
   * 行距看起來也比實際空隙小很多。日期塊與選舉名稱都靠這個做視覺置中。
   */
  function measureRich(ctx, segs, gap, gapAfter) {
    ctx.save();
    var total = 0, ascent = 0, descent = 0;
    for (var i = 0; i < segs.length; i++) {
      var s = segs[i];
      ctx.font = U.font(s.size, s.weight, s.family);
      var m = ctx.measureText(s.text);
      if (m.actualBoundingBoxAscent > ascent) ascent = m.actualBoundingBoxAscent;
      if (m.actualBoundingBoxDescent > descent) descent = m.actualBoundingBoxDescent;
      total += m.width;
      if (i < segs.length - 1) total += segGap(segs, i, gap);
    }
    ctx.restore();
    return { width: total + (gapAfter || 0), ascent: ascent, descent: descent };
  }

  /**
   * 畫一行混字級文字，整行以 x 為中心置中。
   * segs 的 size 已在建立時指定，這裡只負責定位與繪製。
   */
  function drawRichLine(ctx, segs, x, y, gap, gapAfter, style) {
    var widths = [], total = 0, i;
    ctx.save();
    for (i = 0; i < segs.length; i++) {
      ctx.font = U.font(segs[i].size, segs[i].weight, segs[i].family);
      var w = ctx.measureText(segs[i].text).width;
      widths.push(w);
      total += w + (i < segs.length - 1 ? segGap(segs, i, gap) : 0);
    }
    ctx.restore();

    var cursor = x - (total + (gapAfter || 0)) / 2;
    for (i = 0; i < segs.length; i++) {
      U.text(ctx, segs[i].text, {
        x: cursor, y: y, size: segs[i].size, weight: segs[i].weight,
        family: segs[i].family, color: segs[i].color || (style && style.color) || '#fff',
        align: 'left', baseline: (style && style.baseline) || 'alphabetic',
        spacing: segs[i].spacing || 0,
        shadow: style && style.shadow
      });
      cursor += widths[i] + (i < segs.length - 1 ? segGap(segs, i, gap) : 0);
    }
    return total;
  }

  /**
   * 把 meta.date（"11月29日"）拆成 {m:"11", d:"29"}。
   * 資料是 build_data.py 產的固定格式，但這裡仍然容忍空白與全形數字，
   * 拆不出來就整段丟給 d，至少不會少字。
   */
  function splitDate(s) {
    var t = String(s == null ? '' : s)
      .replace(/[\uff10-\uff19]/g, function (c) {          /* 全形數字轉半形 */
        return String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
      })
      .replace(/\s+/g, '');
    var m = t.match(/^(\d+)\s*月\s*(\d+)\s*日?$/);
    if (m) return { m: m[1], d: m[2] };
    var m2 = t.match(/^(\d+)\s*月?/);
    var d2 = t.match(/(\d+)\s*日/);
    if (m2 && d2) return { m: m2[1], d: d2[1] };
    return { m: t.replace(/月/g, ''), d: '' };
  }

  /* =====================================================================
     BackgroundLayer —— 底色、光暈、浮水印地圖、暗角
     ===================================================================== */
  function BackgroundLayer(slide) { Layer.call(this, slide); }
  BackgroundLayer.prototype = Object.create(Layer.prototype);
  BackgroundLayer.prototype.constructor = BackgroundLayer;

  BackgroundLayer.prototype.draw = function (ctx) {
    var W = L.W, H = L.H;

    /* 0. 街景背景照（2026-10-14 起）：cover 鋪滿畫布 + 暗色遮罩。
          cover = 等比例放大到「寬、高都蓋滿」，置中後超出畫布的部分裁掉
          （素材 4:3、畫布 16:9 → 以寬為準放大，上下各裁一截）。
          讀不到照片時整段跳過，畫面退回下面的純漸層底，不會開天窗。 */
    var bgConf = L.background || {};
    var bg = this.assets.streetBg;
    if (bg && bg.width) {
      var k = Math.max(W / bg.width, H / bg.height);
      var dw = bg.width * k, dh = bg.height * k;
      ctx.drawImage(bg, (W - dw) / 2, (H - dh) / 2, dw, dh);
      if (bgConf.dim) {
        ctx.fillStyle = 'rgba(4,7,16,' + bgConf.dim + ')';
        ctx.fillRect(0, 0, W, H);
      }
    }

    /* 1. 主底色。有照片時整條降不透明度（alpha 0.55 起），讓街景透出來、
          又保住深藍色調；沒有照片時維持原本的不透明漸層。 */
    var bgAlpha = (bg && bg.width) ? 0.45 : 1.0;
    ctx.fillStyle = U.gradient(ctx, 0, 0, 0, H, [
      [0, U.alpha(T.BG.top, bgAlpha)],
      [0.42, U.alpha(T.BG.mid, bgAlpha)],
      [1, U.alpha(T.BG.bottom, bgAlpha)]
    ]);
    ctx.fillRect(0, 0, W, H);

    /* 2. 左右兩側的政黨色光暈 */
    var glows = [L.decor.glowLeft, L.decor.glowRight];
    for (var i = 0; i < glows.length; i++) {
      var g = glows[i];
      var hex = T.party(g.color).main;
      ctx.fillStyle = U.radial(ctx, g.x, g.y, 0, g.x, g.y, g.r, [
        [0, U.alpha(hex, 0.30)],
        [0.55, U.alpha(hex, 0.10)],
        [1, U.alpha(hex, 0)]
      ]);
      ctx.fillRect(0, 0, W, H);
    }

    /* 3. 細格線：讓大面積底色有質感 */
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.028)';
    ctx.lineWidth = 1;
    var step = 128;
    ctx.beginPath();
    for (var gx = 0; gx <= W; gx += step) {
      ctx.moveTo(gx + 0.5, 0);
      ctx.lineTo(gx + 0.5, H);
    }
    for (var gy = 0; gy <= H; gy += step) {
      ctx.moveTo(0, gy + 0.5);
      ctx.lineTo(W, gy + 0.5);
    }
    ctx.stroke();
    ctx.restore();

    /* 4. 浮水印：新北市輪廓淡淡地鋪在背景。
          現在前景已經是「真實地圖」，浮水印壓得很淡，只當作底紋。 */
    if (this.assets.projectorBackdrop) {
      ctx.save();
      ctx.globalAlpha = 0.05;
      ctx.strokeStyle = 'rgba(255,255,255,0.55)';
      ctx.lineWidth = 6;
      this.assets.projectorBackdrop.pathAll(ctx);
      ctx.stroke();
      ctx.globalAlpha = 0.022;
      ctx.fillStyle = '#8fb4ff';
      this.assets.projectorBackdrop.pathAll(ctx);
      ctx.fill();
      ctx.restore();
    }

    /* 5. 由左上斜射的光帶 */
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    ctx.fillStyle = U.gradient(ctx, W * 0.1, 0, W * 0.62, H, [
      [0, 'rgba(120,170,255,0.055)'],
      [0.45, 'rgba(120,170,255,0.012)'],
      [1, 'rgba(120,170,255,0)']
    ]);
    ctx.beginPath();
    ctx.moveTo(W * 0.12, 0);
    ctx.lineTo(W * 0.46, 0);
    ctx.lineTo(W * 0.66, H);
    ctx.lineTo(W * 0.20, H);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    /* 6. 暗角 */
    ctx.fillStyle = U.radial(ctx, W / 2, H * 0.46, H * 0.28, W / 2, H * 0.46, H * 0.95, [
      [0, 'rgba(0,0,0,0)'],
      [0.62, 'rgba(0,0,0,0.24)'],
      [1, 'rgba(0,0,0,' + L.decor.vignette + ')']
    ]);
    ctx.fillRect(0, 0, W, H);
  };

  /* =====================================================================
     HeaderLayer —— 頁眉：選舉名稱 / 屆次年份 / 現任者
     ===================================================================== */
  function HeaderLayer(slide) { Layer.call(this, slide); }
  HeaderLayer.prototype = Object.create(Layer.prototype);
  HeaderLayer.prototype.constructor = HeaderLayer;

  HeaderLayer.prototype.draw = function (ctx) {
    var H = L.header, meta = this.model.meta;
    var U_ = U;

    /* 頂部漸層帶 */
    ctx.fillStyle = U_.gradient(ctx, 0, 0, 0, H.h, [
      [0, 'rgba(4,7,16,0.92)'],
      [0.72, 'rgba(4,7,16,0.62)'],
      [1, 'rgba(4,7,16,0)']
    ]);
    ctx.fillRect(0, 0, L.W, H.h);
    ctx.fillStyle = T.BG.line;
    ctx.fillRect(0, H.h - 1, L.W, 1);

    /* ---------------- 日期塊版面（純計算，先算完才能排左側市徽與名稱） ----------------
       深紅圓盤墊在年份後面，年份數字極大，投票日降一級字、換細字重排在圓盤下緣
       （參考使用者提供的樣板；比例係數與出處寫在 layout.js 的 dateBlock）。
       阿拉伯數字兩行共用 NT.FONT_DISPLAY_NUM（Noto Sans UI Black），
       主次只靠字級（96 / 36）區分；年／月／日 是中文、該字型沒有中文字身，
       瀏覽器會逐字往下一個字型找。 */
    var db = H.dateBlock;
    var dateParts = splitDate(meta.date);          /* {m:'11', d:'29'} */
    var dayFamily = db.day.family || NT.FONT_DISPLAY_NUM;
    var yearSegs = [
      { text: String(meta.year), size: db.year.size, weight: db.year.weight,
        family: NT.FONT_DISPLAY_NUM, color: '#fff', gapAfter: db.year.gap },
      { text: '年', size: db.year.cjkSize, weight: db.year.cjkWeight, color: '#fff' }
    ];
    /* 「11月29日」全部用 gapAfter 排版，不要塞真的空白字元：
       空白字元在 Noto Sans UI Black 裡又寬又不對齊，會讓「月│29」的距離
       比「11│月」大上一倍。數字貼單位緊、單位到下一組鬆，「29日」才是一組。 */
    var daySegs = [
      { text: dateParts.m, size: db.day.size, weight: db.day.weight,
        family: dayFamily, color: '#fff', gapAfter: db.day.gap },
      { text: '月', size: db.day.cjkSize, weight: db.day.cjkWeight,
        color: '#fff', gapAfter: db.day.gap * 2.0 },
      { text: dateParts.d, size: db.day.size, weight: db.day.weight,
        family: dayFamily, color: '#fff', gapAfter: db.day.gap },
      { text: '日', size: db.day.cjkSize, weight: db.day.cjkWeight, color: '#fff' }
    ];

    /* 先量兩行的實際墨跡，再量「年份數字自己」的墨跡：
       圓盤的直徑與圓心只看後者，所以換年份、改字級，圓和數字永遠同一組比例。 */
    var yM = measureRich(ctx, yearSegs, db.year.gap, db.year.gapAfter);
    var dM = measureRich(ctx, daySegs, db.day.gap, db.day.gapAfter);
    var digitM = measureRich(ctx, [{
      text: String(meta.year), size: db.year.size,
      weight: db.year.weight, family: NT.FONT_DISPLAY_NUM
    }], 0, 0);
    var disc = db.disc || {};
    var digitH = digitM.ascent || yM.ascent;                 /* 年份數字墨跡高 */
    var discD = digitH * (disc.dRatio === undefined ? 1.95 : disc.dRatio);
    var discCY = db.y + discD / 2;
    /* 年份行基線：讓它的墨跡頂落在圓心的上方 cyRatio × 數字高 處 */
    var baseY = discCY - (disc.cyRatio === undefined ? 0.70 : disc.cyRatio) * digitH
      + yM.ascent;
    var dayBaseY = baseY + yM.descent + db.lineGap + dM.ascent;   /* 日期行基線 */
    /* 區塊＝圓盤的外接框；左右寬度取兩行內容較寬者（供右側小字定位與驗證量測） */
    var boxW = Math.max(yM.width, dM.width);
    var boxX = db.cx - boxW / 2;
    var boxH = discD;

    /* ---------------- 左：頁眉徽章（白底圓角卡片） ----------------
       2026-10-14 起：徽章不再直接貼在看板上，先畫一塊白底圓角卡片，
       徽章放在卡片裡 —— 市長選舉放臺北市市徽、總統選舉放國旗
       （meta.office 含「總統」時改用 seal.srcPresident 的 roc_flag.png）。
       卡片 = 徽章矩形向外擴 card.pad、圓角 card.radius，帶一點投影；
       選舉名稱接在「卡片右緣 + gap」之後（原本是徽章右緣，語意一致）。
       讀不到徽章時退回原本的圈選記號，卡片照畫（不讓這一格開天窗）。 */
    var sealConf = H.seal;
    var sealGap = sealConf.gap || 0;
    var sealH = boxH * (sealConf.hRatio === undefined ? 1 : sealConf.hRatio);
    var sealY = db.y + (boxH - sealH) / 2;
    var isPresident = (meta.office || '').indexOf('總統') >= 0;
    /* 總統場讀不到國旗時退回市徽（通常不會發生；city_seal 一直都在） */
    var seal = isPresident ? (this.assets.rocFlag || this.assets.citySeal)
                           : this.assets.citySeal;
    var sealBox = null;
    if (seal && seal.width) {
      /* 先算徽章矩形（等比例、高 = sealH），畫白卡，再把徽章畫進去。
         ★ 總統選舉的國旗要「填滿卡片」：卡片內不留白，國旗鋪滿整張卡
          （pad 壓到 0、圓角就是國旗的外框）。市徽是不規則透明圖，留一點
          pad 讓它透氣、白底才看得出來。 */
      var sealW = sealH * seal.width / seal.height;
      sealBox = { x: sealConf.x, y: sealY, w: sealW, h: sealH };
      var card = sealConf.card || {};
      var pad = card.pad === undefined ? 16 : card.pad;
      if (isPresident) pad = 0;                 /* 國旗填滿卡片 */
      var rad = card.radius === undefined ? 24 : card.radius;
      if (pad === 0) {
        /* 國旗直接畫滿卡片矩形，卡片就是國旗 + 圓角裁切 */
        ctx.save();
        ctx.shadowColor = 'rgba(0,0,0,0.45)';
        ctx.shadowBlur = 18;
        ctx.shadowOffsetY = 6;
        U_.roundRectPath(ctx, sealBox.x, sealBox.y, sealBox.w, sealBox.h, rad);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.clip();
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(seal, sealBox.x, sealBox.y, sealBox.w, sealBox.h);
        ctx.restore();
      } else {
        ctx.save();
        ctx.shadowColor = 'rgba(0,0,0,0.45)';
        ctx.shadowBlur = 18;
        ctx.shadowOffsetY = 6;
        ctx.fillStyle = '#ffffff';
        U_.roundRectPath(ctx, sealBox.x - pad, sealBox.y - pad,
          sealBox.w + pad * 2, sealBox.h + pad * 2, rad);
        ctx.fill();
        ctx.restore();
        ctx.save();
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(seal, sealBox.x, sealBox.y, sealBox.w, sealBox.h);
        ctx.restore();
      }
    } else {
      /* 讀不到徽章時退回原本的圈選記號，不讓這一格開天窗 */
      var r = sealH * 0.30;
      sealBox = { x: sealConf.x, y: sealY, w: sealH, h: sealH };
      Marks.voteMark(ctx, sealBox.x + sealH / 2, sealY + sealH / 2,
        r, 'rgba(255,255,255,0.9)', 6);
    }
    /* 記下實際落點（含白卡的徽章矩形），供自動化驗證量測 */
    this.assets.sealRect = sealBox;

    /* ---------------- 左：選舉名稱（單行，讓開市徽） ----------------
       早先這裡上面還有一行小字「TAIWAN, CHINA」，依需求移除。
       名稱是左側唯一的錨點，用「實際墨跡」視覺置中於日期塊的水平軸，
       讓左／中／右三塊共用同一條中心線。 */
    /* 名稱讓開的是「卡片右緣」：徽章矩形 + pad。總統場國旗填滿卡片（pad=0），
       市長場徽章有 pad。讀不到徽章、沒畫卡時 pad 記 0，行為與舊版一致。 */
    var sealCardPad = (!isPresident && seal && seal.width &&
      sealConf.card && sealConf.card.pad) || 0;
    var ltX = sealBox ? (sealBox.x + sealBox.w + sealCardPad + sealGap) : H.leftText.x;
    var nameM = measureRich(ctx, [{
      text: meta.election, size: H.leftText.size, weight: H.leftText.weight
    }], 0, 0);
    /* baseline 要讓墨跡中心對齊 blockCY：(ascent - descent)/2 是墨跡中心在基線上方的距離 */
    var blockCY = db.y + boxH / 2;
    U_.text(ctx, meta.election, {
      x: ltX, y: blockCY + (nameM.ascent - nameM.descent) / 2,
      size: H.leftText.size, weight: H.leftText.weight,
      color: T.BG.text, baseline: 'alphabetic',
      spacing: H.leftText.spacing,
      shadow: { color: 'rgba(0,0,0,0.5)', blur: 14, y: 4 }
    });

    /* ---------------- 中：圓盤底 + 年份 + 投票日 ----------------
       圓盤底色＝使用者提供的圓徽圖（assets/emblem.png）。
       原圖是「正方形 + 內切圓」，所以畫滿外接正方形再切圓就完全貼合，
       不必另外調比例；圓徽很亮、太陽又是白的，上面再罩一層暗色
       （disc.scrim），白字才離得開、圓徽也才融得進看板的深藍色系。
       讀不到圓徽圖時退回原本的暗絳紅平塗，畫面不會開天窗。 */
    var emblem = this.assets.emblem;
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur = 36;
    ctx.shadowOffsetY = 10;
    ctx.beginPath();
    ctx.arc(db.cx, discCY, discD / 2, 0, Math.PI * 2);
    ctx.fillStyle = disc.inner || '#4d0716';
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    ctx.arc(db.cx, discCY, discD / 2, 0, Math.PI * 2);
    ctx.clip();
    if (emblem) {
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(emblem, db.cx - discD / 2, discCY - discD / 2, discD, discD);
      /* disc.scrim 給 [offset,color] 陣列 → 徑向暗罩（中心重、外緣輕）；
         給單一顏色字串 → 平塗。 */
      if (disc.scrim) {
        var sr = discD * (disc.scrimRadius === undefined ? 0.62 : disc.scrimRadius);
        ctx.fillStyle = (disc.scrim instanceof Array)
          ? U_.radial(ctx, db.cx, discCY, 0, db.cx, discCY, sr, disc.scrim)
          : disc.scrim;
        ctx.fillRect(db.cx - discD / 2, discCY - discD / 2, discD, discD);
      }
    } else {
      ctx.fillStyle = U_.radial(ctx, db.cx, discCY - discD * 0.14, 0,
        db.cx, discCY, discD * 0.56, [
        [0, disc.inner || '#4d0716'],
        [1, disc.outer || '#360310']
      ]);
      ctx.fillRect(db.cx - discD / 2, discCY - discD / 2, discD, discD);
    }
    ctx.restore();

    var dateStyle = {
      color: '#fff', baseline: 'alphabetic',
      shadow: { color: 'rgba(0,0,0,0.5)', blur: 16, y: 5 }
    };
    drawRichLine(ctx, yearSegs, db.cx, baseY, db.year.gap, db.year.gapAfter, dateStyle);
    drawRichLine(ctx, daySegs, db.cx, dayBaseY, db.day.gap, 0, dateStyle);

    /* 記下日期塊實際落點，供自動化驗證量測 */
    this.assets.dateRect = {
      x: boxX, y: db.y, w: boxW, h: boxH,
      disc: { cx: db.cx, cy: discCY, d: discD },
      yearTop: baseY - yM.ascent, yearBaseY: baseY, dayBaseY: dayBaseY
    };

    /* ---------------- 投票率 / 有效票：日期塊右側、垂直置中 ----------------
       兩項之間**不放間隔號**（原本是「　·　」），只用兩個全角空格分開；
       斷開距離與原本的觀感接近（約 2em），但不會再多一個圓點搶眼。
       ★ meta.turnout 為 null（總統選舉：分區沒有官方選舉人數，算不出分區
         投票率）時只印有效票。
       ★ 2026-10-14 起「（北北基宜）」分區標註依需求移除 —— meta.regionLabel
         保留在 meta.json 裡不再上板。
       ★ 有效票後綴補一個「票」字（需求：`有效票 409萬3732 票`）——
         數字與單位之間留一個半形空格，唸起來才不會黏在一起。 */
    var st = H.stats;
    var statsText = (meta.turnout == null)
      ? '有效票 ' + U_.voteWan(meta.validVotes) + ' 票'
      : '投票率 ' + meta.turnout.toFixed(2) + '%\u3000\u3000有效票 ' +
        U_.voteWan(meta.validVotes) + ' 票';
    U_.text(ctx, statsText, {
      x: boxX + boxW + (st.gap || 0), y: db.y + boxH / 2, size: st.size,
      weight: st.weight, color: T.BG.textDim, align: 'left', baseline: 'middle'
    });


    /* ---------------- 右：時任市長 ----------------
       這格在原始版面是「現任者」徽章：頭像沿用主候選人（左卡）的照片。
       泛化後改成 meta.headerRole 可覆寫標籤；
       2026-10-04 起再支援 meta.header 把整格人物寫死在 meta.json：
           "header": { "role": "時任市長", "name": "黃大洲",
                        "party": "中國國民黨", "partyShort": "KMT" }
       ★ 時任市長不一定在這場的候選人名單裡（2014 的郝龍斌、2022 的柯文哲
         都已卸任且未參選），而且色票要跟著人走 —— 1998 的頁眉是陳水扁（綠），
         不是該場勝者馬英九（藍）。所以人物／政黨／色票都改由 header 宣告，
         partyShort 經 Candidate.partyKeyOf 換算政黨色（header.color 可再覆寫）。
       沒宣告 header 時維持舊行為：標籤吃 meta.headerRole（無則「現任市長」）、
       人物吃主卡左卡（得票最高者），舊場次輸出不變；
       role 宣告成 null / false / "" 則整格不畫（純候選人頁面用）。 */
    var hdr = meta.header || null;
    var roleLabel = (hdr && hdr.role !== undefined) ? hdr.role
      : (meta.headerRole === undefined ? '現任市長' : meta.headerRole);
    if (roleLabel) {
    /* 頁眉人物與色票：meta.header 優先，否則沿用左卡（原本行為）。 */
    var incTheme, incName, incParty;
    if (hdr && hdr.name) {
      var hdrPartyKey = NT.Candidate.partyKeyOf(hdr.partyShort);
      incTheme = hdr.color ? T.fromColor(hdr.color, hdrPartyKey)
                           : T.party(hdrPartyKey);
      incName = hdr.name;
      incParty = hdr.party || '';
    } else {
      incTheme = this.model.left.theme;
      incName = this.model.left.name;
      incParty = this.model.left.partyDisplay();
    }
    var inc = H.incumbent;
    var px = inc.card.right - inc.card.w;
    /* 頭像框：看板一律不畫候選人照片（需求：照片由使用者自行後製），
       框裡只填一塊政黨純色底 + 一圈亮線，位置與尺寸維持原樣。 */
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur = 16;
    ctx.fillStyle = incTheme.main;
    U_.roundRectPath(ctx, px, inc.card.y, inc.card.w, inc.card.h, inc.card.radius);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.strokeStyle = U_.alpha(incTheme.light, 0.9);
    ctx.lineWidth = 2.5;
    U_.roundRectPath(ctx, px, inc.card.y, inc.card.w, inc.card.h, inc.card.radius);
    ctx.stroke();
    ctx.restore();

    U_.text(ctx, roleLabel, {
      x: inc.textRight, y: inc.line1Y, size: inc.line1Size, weight: 700,
      color: T.BG.textFaint, align: 'right', baseline: 'middle', spacing: 8
    });
    U_.text(ctx, incName, {
      x: inc.textRight, y: inc.line2Y, size: inc.line2Size, weight: 900,
      color: '#fff', align: 'right', baseline: 'middle'
    });
    /* 政黨名：meta.header.party 直接印宣告值（寫的時候就用顯示短名，
       例如「無黨籍」）；沿用左卡時才走 partyDisplay()——
       「無黨籍及未經政黨推薦」在頁眉只印「無黨籍」，否則這一格靠右對齊、
       會一路頂到頁眉最左邊壓到標題。 */
    U_.text(ctx, incParty, {
      x: inc.textRight, y: inc.line3Y, size: inc.line3Size, weight: 700,
      color: U_.alpha(incTheme.light, 0.95), align: 'right', baseline: 'middle'
    });
    }
  };

  /* =====================================================================
     MapLayer —— 行政區得票地圖
     ===================================================================== */
  function MapLayer(slide) { Layer.call(this, slide); }
  MapLayer.prototype = Object.create(Layer.prototype);
  MapLayer.prototype.constructor = MapLayer;

  /**
   * 直接採用使用者提供的「新北市 2014 得票率地圖」（村里等級、含圖例）。
   * 圖檔來源與載入策略見 js/slide.js（預設 Share/assets/vote_map.png）。
   *
   * 畫法：依原圖比例 contain 進 Layout.map 的框 → 乘上 Layout.map.scale（縮小用）
   *       → 依 anchorX / anchorY 貼齊框內位置 → 不加任何底板。
   */
  MapLayer.prototype.draw = function (ctx) {
    var img = this.assets.voteMap;
    if (!img) return;

    var box = L.map;
    var k = box.scale === undefined ? 1 : box.scale;
    var s = Math.min(box.w / img.width, box.h / img.height) * k;
    var w = img.width * s;
    var h = img.height * s;

    /* 縮小後多出來的空間往哪裡擺：0.5 置中（預設），0 貼左上 */
    var ax = box.anchorX === undefined ? 0.5 : box.anchorX;
    var ay = box.anchorY === undefined ? 0.5 : box.anchorY;
    var x = box.x + (box.w - w) * ax + (box.dx || 0);
    var y = box.y + (box.h - h) * ay + (box.dy || 0);

    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, x, y, w, h);
    ctx.restore();

    /* 記下地圖實際落下的矩形，供除錯與自動化驗證量測 */
    this.assets.mapRect = { x: x, y: y, w: w, h: h, scale: k };
  };

  /* =====================================================================
     Map2Layer —— 區級得票地圖（第二張圖，補進地圖右側的空欄）
     ===================================================================== */
  function Map2Layer(slide) { Layer.call(this, slide); }
  Map2Layer.prototype = Object.create(Layer.prototype);
  Map2Layer.prototype.constructor = Map2Layer;

  /**
   * 把「區級版地圖」（assets/map2.png，只畫區、不畫里，與村里版同畫布同範圍）
   * 擺到地圖右邊那一整條獨立空欄（Layout.map2 的座標）。
   *
   * ★ 為什麼要這張圖（2026-10-14 晚六，需求：總統場把兩張圖放到同一張看板）：
   *   村里的地圖（MapLayer，assets/map.png）仍是主要地圖，尺寸位置完全不動；
   *   但總統「北北基宜」場把圖例關掉了，地圖右側那一欄（1580–2024）本來整片
   *   空著，看板看起來「左重右空」。區級圖正好補上那一欄 —— 兩張圖同源同範圍，
   *   一張看村里、一張看區，擺在一起互相對照。
   *
   * ★ 只在「圖例關掉」的場次畫：市長場的圖例就佔著這一欄
   *   （Layout.legend 1626–1978 × 493–933），硬畫會整張疊上去。
   *   素材讀不到（或主圖就是這張，例如 -map2 變體看板）時整個跳過，不開天窗。
   *
   * 畫法：與 MapLayer 同一套 —— contain 進框 → 乘 scale → 依 anchorX / anchorY
   *       貼齊 → 不加任何底板（跟主地圖一致）。
   */
  Map2Layer.prototype.draw = function (ctx) {
    var img = this.assets.map2;
    if (!img) return;                              /* 沒有區級圖就什麼都不畫 */
    var bx = L.map2;
    if (!bx || bx.enabled === false) return;       /* 逐場可關（meta.layout.map2） */
    if (L.legend && !L.legend.disabled) return;    /* 圖例還開著＝這一欄是圖例的 */

    var k = bx.scale === undefined ? 1 : bx.scale;
    var s = Math.min(bx.w / img.width, bx.h / img.height) * k;
    var w = img.width * s;
    var h = img.height * s;

    var ax = bx.anchorX === undefined ? 0.5 : bx.anchorX;
    var ay = bx.anchorY === undefined ? 0.5 : bx.anchorY;
    var x = bx.x + (bx.w - w) * ax + (bx.dx || 0);
    var y = bx.y + (bx.h - h) * ay + (bx.dy || 0);

    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, x, y, w, h);
    ctx.restore();

    /* 記下實際落點，供除錯與自動化驗證量測（verify_layout 的 L10–L12） */
    this.assets.map2Rect = { x: x, y: y, w: w, h: h, scale: k };
  };

  /* =====================================================================
     LegendLayer —— 得票率圖例（地圖右側空欄，直接貼在看板底色上）
     ===================================================================== */
  function LegendLayer(slide) { Layer.call(this, slide); }
  LegendLayer.prototype = Object.create(Layer.prototype);
  LegendLayer.prototype.constructor = LegendLayer;

  /**
   * 把得票率圖例擺到地圖「右邊」那一整條獨立空欄（Layout.legend 的座標）。
   *
   * ★ 曾經擺在地圖框內側、靠著「新北市地圖中間那塊台北盆地空洞」——
   *   2014 新北看起來沒事，換成台北市（2018／2022）之後同一個座標
   *   正好落在內湖／南港／信義／文山的村里色塊上，圖例直接把地圖蓋掉。
   *   現在地圖框收窄（Layout.map 560–1580），圖例整個移到框外，
   *   幾何上不可能再壓到地圖；tools/verify_layout.py 會把這條規則跑成斷言。
   *
   * ★ 沒有底板了：
   *   以前圖例是「透明底 + 深色文字」，貼在看板底色（#0d1738）上文字會整個消失，
   *   所以在底下鋪一塊淺色圓角底板（舊的 Layout.legend.bg）把對比撐起來。
   *   現在圖例改由 NewSolution/Converge_to_map_taipei.py 直接畫成
   *   「透明底 + 白字 + 色塊」，白字本來就是給深色底用的 —— 底板反而多出一塊
   *   亮底、跟白字糊在一起，所以整塊拿掉，圖例直接貼在看板上。
   *   （地圖本來就是這樣貼的：MapLayer 也不加任何底板。）
   *
   * 畫法：圖例圖片 contain 進 Layout.legend 的框，保持原圖比例、不變形，
   *       水平／垂直都置中；讀不到圖片就整個跳過。
   */
  LegendLayer.prototype.draw = function (ctx) {
    var img = this.assets.legend;
    if (!img) return;                       /* 沒有圖例就什麼都不畫 */
    if (L.legend && L.legend.disabled) return;   /* 逐場關閉（總統北北基宜看板） */

    var g = L.legend;
    var x = g.x, y = g.y, w = g.w, h = g.h;
    var inner = g.inner === undefined ? 16 : g.inner;

    ctx.save();
    ctx.globalAlpha = g.opacity === undefined ? 1 : g.opacity;

    /* 選用的小標題（title 為空字串就整段跳過）。底色是深藍，預設白字 */
    var contentX = x + inner, contentY = y + inner;
    var contentW = w - inner * 2, contentH = h - inner * 2;
    if (g.title) {
      var tSize = g.titleSize || 24;
      U.text(ctx, g.title, {
        x: contentX, y: contentY + tSize * 0.82,
        size: tSize, weight: g.titleWeight || 900,
        color: g.titleColor || '#ffffff',
        align: 'left', baseline: 'alphabetic', spacing: 2
      });
      contentY += tSize * 1.18 + (g.titleGap === undefined ? 12 : g.titleGap);
      contentH = y + h - inner - contentY;
    }
    if (contentH <= 8 || contentW <= 8) { ctx.restore(); return; }

    /* 圖例圖片：contain 進剩餘區域（保持原圖比例） */
    var k = Math.min(contentW / img.width, contentH / img.height);
    var iw = img.width * k;
    var ih = img.height * k;
    var ix = contentX + (contentW - iw) / 2;      /* 水平置中 */
    var iy = contentY + (contentH - ih) / 2;      /* 垂直置中 */
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, ix, iy, iw, ih);

    ctx.restore();

    /* 記下落點，供自動化驗證量測 */
    this.assets.legendRect = {
      box: { x: x, y: y, w: w, h: h },
      image: { x: ix, y: iy, w: iw, h: ih },
      source: this.assets.legendSource
    };
  };

  /* =====================================================================
     CandidateLayer —— 主要候選人區塊（照片卡 + 黨徽 + 姓名 + 得票率）
     ===================================================================== */
  function CandidateLayer(slide) { Layer.call(this, slide); }
  CandidateLayer.prototype = Object.create(Layer.prototype);
  CandidateLayer.prototype.constructor = CandidateLayer;

  /**
   * @param {object} ctx
   * @param {NT.Candidate} c    候選人
   * @param {object} conf       Layout.left / Layout.right
   */
  CandidateLayer.prototype.draw = function (ctx, c, conf) {
    var th = c.theme;
    var cx = conf.cx;

    /* ------------------------- 1. 政黨色卡 -------------------------
       ★ 看板不畫候選人照片：照片怎麼合成由使用者自己後製決定，
         看板端只留「一塊政黨純色底 + 一圈亮線」標出位置。
         幾何沿用原本的照片框（Layout 的 card），構圖不會因為拿掉照片而跑掉。
         底色刻意是單一顏色（不用漸層、不疊柔光、不做底部壓暗）：
         使用者若在後製時把去背照片疊上來，透出來的就是這一色。 */
    var ph = conf.card;
    var px = cx - ph.w / 2;
    var py = ph.y;

    ctx.save();
    ctx.shadowColor = U.alpha(th.main, 0.5);
    ctx.shadowBlur = 56;
    ctx.shadowOffsetY = 18;
    ctx.fillStyle = th.main;
    U.roundRectPath(ctx, px, py, ph.w, ph.h, ph.radius);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = U.alpha(th.light, 0.95);
    ctx.lineWidth = 6;
    U.roundRectPath(ctx, px, py, ph.w, ph.h, ph.radius);
    ctx.stroke();
    ctx.restore();

    /* ------------------------- 2. 政黨標籤 -------------------------
       標籤內容就是兩樣：[政黨徽章] 政黨名。

       ★ 不再畫英文縮寫（原本是「[徽章] 中國國民黨 KMT」）：
         中文名已經把政黨講完，英文只是同義重複；而且最長的
         「無黨籍及未經政黨推薦 INDEPENDENT」會把標籤撐爆、溢出膠囊邊界
         （2018 柯文哲那張就是這樣）。
       ★ 政黨名走 partyDisplay()：「無黨籍及未經政黨推薦」只印「無黨籍」。
       fitText 是最後一道保險 —— 真的遇到超長黨名就截斷補「…」，
       不會再讓文字壓出膠囊外。 */
    var cp = conf.chip;
    var chipX = cx - cp.w / 2;
    ctx.save();
    ctx.fillStyle = 'rgba(6,12,26,0.66)';
    U.roundRectPath(ctx, chipX, cp.y, cp.w, cp.h, cp.radius);
    ctx.fill();
    ctx.strokeStyle = U.alpha(th.main, 0.75);
    ctx.lineWidth = 2.5;
    U.roundRectPath(ctx, chipX, cp.y, cp.w, cp.h, cp.radius);
    ctx.stroke();
    ctx.restore();

    var markW = cp.h * (cp.markRatio === undefined ? 0.42 : cp.markRatio);
    var gap1 = 20;
    /* 膠囊左右各留 24px 內距，扣掉徽章與間隔，才是黨名真正可用的寬度 */
    var labelMax = cp.w - 48 - markW - gap1;
    var partyLabel = c.partyDisplay();
    ctx.save();
    ctx.font = U.font(cp.nameSize, 900);
    partyLabel = U.fitText(ctx, partyLabel, labelMax, 0);
    var nameW = ctx.measureText(partyLabel).width;
    ctx.restore();

    var total = markW + gap1 + nameW;
    var sx = chipX + (cp.w - total) / 2;

    /* 徽章：使用者提供的政黨圖（assets/party_*.png）。
       ★ 圓外已經透明 —— 由 tools/build_board.py 的靜態素材透明化處理
         （boardlib/assets.py 的 STATIC_RECIPES），不是直接複製白底原圖；
         不然圓徽在深藍底上會多出一個白色方塊。
       原圖是「圓形主體內切於正方形」，所以圓的直徑就等於 markW，
       與原本抽象色塊的佔位完全一致，不需要另外調比例。
       圖讀不到時退回抽象色塊，標籤不會開天窗。 */
    var markY = cp.y + (cp.h - markW) / 2;
    var partyMark = (this.assets.partyMarks || {})[c.partyKey];
    if (partyMark) {
      ctx.save();
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(partyMark, sx, markY, markW, markW);
      ctx.restore();
    } else {
      Marks.partyChip(ctx, sx, markY, markW, th);
    }
    /* 記下徽章實際落點與來源，供自動化驗證量測 */
    if (!this.assets.partyMarkRects) this.assets.partyMarkRects = {};
    this.assets.partyMarkRects[c.key] = {
      x: sx, y: markY, w: markW, h: markW,
      source: (this.assets.partyMarkSource || {})[c.partyKey] || 'fallback'
    };
    U.text(ctx, partyLabel, {
      x: sx + markW + gap1, y: cp.y + cp.h / 2, size: cp.nameSize, weight: 900,
      color: '#fff', baseline: 'middle'
    });

    /* ------------------------- 3. 當選標誌 + 姓名 -------------------------
       當選者在姓名左側貼上當選標誌（使用者提供的圖，不是打勾），
       並且把「標誌 + 姓名」整組置中，避免偏一邊。 */
    var nm = conf.name;
    ctx.save();
    ctx.font = U.font(nm.size, 900);
    var nameW = U.measureSpaced(ctx, c.name, nm.spacing || 0);
    ctx.restore();

    var markSize = c.elected ? nm.size * (nm.markRatio || 0.9) : 0;
    var gap = c.elected ? (nm.markGap || 30) : 0;
    var groupW = nameW + markSize + gap;
    var gx = cx - groupW / 2;

    if (c.elected && this.assets.electedMark) {
      /* 對齊 CJK 字身框的視覺中心（baseline 往上約 0.38em） */
      Marks.stamp(ctx, this.assets.electedMark,
        gx + markSize / 2, nm.y - nm.size * 0.38, markSize);
    }

    U.text(ctx, c.name, {
      x: gx + markSize + gap, y: nm.y, size: nm.size, weight: 900,
      color: '#fff', align: 'left', baseline: 'alphabetic',
      spacing: nm.spacing,
      shadow: { color: 'rgba(0,0,0,0.65)', blur: 22, y: 6 }
    });

    /* ------------------------- 3.5 副手行（有宣告才畫） -------------------------
       參考樣板的「Vice: 姓名（政黨）」：「副手：」小一級用暗色、姓名白字、
       政黨跟候選人主色。整組置中於卡片中線，超寬截斷。
       市長選舉（無 vice 資料）整行跳過，版面與既有輸出完全不變。 */
    if (c.vice) drawViceLine(ctx, c, cx, conf.vice);

    /* ------------------------- 4. 得票率 ------------------------- */
    ctx.save();
    ctx.shadowColor = U.alpha(th.light, 0.5);
    ctx.shadowBlur = 36;
    ctx.shadowOffsetY = 7;
    U.text(ctx, c.pctText() + '%', {
      x: cx, y: conf.pct.y, size: conf.pct.size, weight: 900,
      family: NT.FONT_NUM, color: th.light, align: 'center', baseline: 'alphabetic'
    });
    ctx.restore();

    /* ------------------------- 5. 得票數（數字大、萬/票小） ------------------------- */
    drawVotes(ctx, c, cx, conf.votes, 'center',
      { color: 'rgba(255,255,255,0.92)' });
  };

  /**
   * 副手行：「副手：」標籤（暗色、小一級）＋ 副手姓名（白字）＋（政黨）（主色）。
   * 整行以 cx 置中；政黨省略時跟候選人同一政黨顯示；超過 conf.maxW 截斷。
   * conf: {y, size, labelSize, maxW, gap}
   */
  function drawViceLine(ctx, c, cx, conf) {
    var party = c.viceParty || c.partyDisplay();
    var partySeg = party ? '（' + party + '）' : '';
    var segs = [
      { text: '副手：', size: conf.labelSize, weight: 700,
        color: T.BG.textFaint, family: NT.FONT_STACK },
      { text: c.vice, size: conf.size, weight: 900,
        color: '#fff', family: NT.FONT_STACK }
    ];
    if (partySeg) {
      segs.push({ text: partySeg, size: conf.labelSize, weight: 700,
        color: U.alpha(c.theme.light, 0.95), family: NT.FONT_STACK });
    }

    /* 量總寬，超過 maxW 就從後段截（先保姓名，政黨名最後犧牲） */
    var total = 0, i;
    ctx.save();
    for (i = 0; i < segs.length; i++) {
      ctx.font = U.font(segs[i].size, segs[i].weight, segs[i].family);
      total += ctx.measureText(segs[i].text).width +
        (i < segs.length - 1 ? conf.gap : 0);
    }
    ctx.restore();
    if (total > conf.maxW && partySeg) {
      ctx.save();
      ctx.font = U.font(segs[2].size, segs[2].weight, segs[2].family);
      var avail = conf.maxW - (total - ctx.measureText(partySeg).width);
      var trimmed = U.fitText(ctx, partySeg, Math.max(avail, 0), 0);
      segs[2].text = trimmed;
      ctx.restore();
    }

    /* 置中：先量最終總寬，再逐段畫 */
    total = 0;
    ctx.save();
    for (i = 0; i < segs.length; i++) {
      ctx.font = U.font(segs[i].size, segs[i].weight, segs[i].family);
      total += ctx.measureText(segs[i].text).width +
        (i < segs.length - 1 ? conf.gap : 0);
    }
    ctx.restore();

    var cursor = cx - total / 2;
    for (i = 0; i < segs.length; i++) {
      U.text(ctx, segs[i].text, {
        x: cursor, y: conf.y, size: segs[i].size, weight: segs[i].weight,
        family: segs[i].family, color: segs[i].color,
        align: 'left', baseline: 'alphabetic',
        shadow: { color: 'rgba(0,0,0,0.5)', blur: 12, y: 3 }
      });
      ctx.save();
      ctx.font = U.font(segs[i].size, segs[i].weight, segs[i].family);
      cursor += ctx.measureText(segs[i].text).width + conf.gap;
      ctx.restore();
    }
  }

  /**
   * 得票數：阿拉伯數字用大級、漢字（萬、票）用小級，共用同一條基線。
   * 「其他候選人」小卡也共用這個畫法。
   * @param {number} x      對齊點
   * @param {object} conf   {y, size, cjkSize}
   * @param {string} align  'left' | 'center' | 'right'
   */
  function drawVotes(ctx, c, x, conf, align, style) {
    var parts = U.voteParts(c.votes);
    var segs = parts.map(function (p) {
      return {
        text: p.text,
        size: p.num ? conf.size : (conf.cjkSize || conf.size * 0.55),
        weight: p.num ? 900 : 700
      };
    });
    U.richText(ctx, segs, {
      x: x, y: conf.y, align: align, baseline: 'alphabetic',
      family: NT.FONT_NUM, color: (style && style.color) || '#fff',
      shadow: { color: 'rgba(0,0,0,0.55)', blur: 14, y: 4 }
    });
  }

  /* =====================================================================
     MinorCandidateLayer —— 其他候選人（第 3 名起）
     -------------------------------------------------------------------------
     規則（見 layout.js 的 Layout.minors）：
       1. 第 3 名＝獨立一張**高卡**：有自己的高度 big.h，底部與左群同線、
          往上長（地圖墨跡右緣到不了那一欄，所以不會壓到地圖，L9 把關）；
          卡內是**單欄直排**（照片占位框 + 姓名／副手／政黨／得票率／票數），
          不再「姓名群 ↔ 得票群」兩欄並排，卡就不會被撐成長橫條。
          照片占位框的比例 = 主卡色卡（452 : 620，layout.js 的 CARD_ASPECT）。
       2. 第 4、5 名＝窄卡（160 高）；第 6 名起併成**「其他候選人」清單格**：
          一行一位（`- 姓名  票數`，票數右對齊成一欄），不印政黨與得票率，
          列數多時整格往上長（上限 = 高卡高度）。
       3. 排列：第 3 名高卡右緣貼齊 x1；其餘一律**從高卡左緣往左排** ——
          第 4 名緊貼高卡左側、第 5 名在其左、清單格在最左。
       4. **卡寬 = 內容自然寬**：先量好每張卡「占位框 + 文字欄（含字距）+ 內距」，
          再照這個寬度畫卡 —— 卡內不會有多餘空位；空隙只留在「卡與卡之間」。
       5. 字級動態：窄卡超過 maxTextW 就整張縮字級；第 3 名高卡的 k 由
          bigScale 求（五行堆疊剛好填滿卡內高度）；清單格的 k 由每列高度推得；
          真的還塞不下才整條縮。
     畫完把每張卡的實際矩形記到 assets.minorCards，供 verify_layout 的
     L7/L8/L9 比對。
     ===================================================================== */
  function MinorCandidateLayer(slide) { Layer.call(this, slide); }
  MinorCandidateLayer.prototype = Object.create(Layer.prototype);
  MinorCandidateLayer.prototype.constructor = MinorCandidateLayer;

  /** 量「一行文字」在某字級下的寬度（含字距）。 */
  function lineWidth(ctx, text, size, weight, spacing, family) {
    ctx.save();
    ctx.font = U.font(size, weight, family);
    var w = U.measureSpaced(ctx, text, spacing || 0);
    ctx.restore();
    return w;
  }

  /** 得票數那一行的寬度（大級數字 + 小級漢字，與 drawVotes 同一種組法）。 */
  function votesLineWidth(ctx, c, size, cjkSize) {
    var parts = U.voteParts(c.votes), w = 0, i;
    ctx.save();
    for (i = 0; i < parts.length; i++) {
      var num = parts[i].num;
      ctx.font = U.font(num ? size : (cjkSize || size * 0.55),
                        num ? 900 : 700, NT.FONT_NUM);
      w += ctx.measureText(parts[i].text).width;
    }
    ctx.restore();
    return w;
  }

  /** 把一行字塞進 maxW：塞得下原樣回傳，塞不下才逐字刪（極端情況的保險）。 */
  function fitLine(ctx, text, size, weight, spacing, maxW) {
    ctx.save();
    ctx.font = U.font(size, weight);
    var s = (maxW === null || maxW === undefined
             || U.measureSpaced(ctx, text, spacing || 0) <= maxW)
      ? String(text) : U.fitText(ctx, text, maxW, spacing || 0);
    ctx.restore();
    return s;
  }

  /**
   * 上限係數：一張卡「最寬那一行」的**自然寬**（還原成 fit=1）超過 maxTextW 時，
   * 回傳要再乘上去的字級係數（下限 0.7）。
   * 這是「字級動態調整」的第二道閥：不是把長文字截掉，而是整張卡縮字級塞進去。
   */
  function capFactor(widest, maxW, fit) {
    var natural = widest / (fit || 1);
    if (!maxW || natural <= maxW) return 1;
    return Math.max(0.7, maxW / natural);
  }

  /** 圖片占位框：不畫照片，只填政黨純色 + 亮線（照片由使用者後製合成）。 */
  function minorBlock(ctx, x, y, m, th) {
    ctx.save();
    ctx.fillStyle = th.main;
    U.roundRectPath(ctx, x, y, m.w, m.h, m.radius);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.28)';
    ctx.lineWidth = 2;
    U.roundRectPath(ctx, x, y, m.w, m.h, m.radius);
    ctx.stroke();
    ctx.restore();
  }

  /** 量一張小卡（第 4 名以後）：占位框 + 單一文字列（四行上下堆疊）。 */
  MinorCandidateLayer.prototype.specSmall = function (ctx, c, m, fit, depth) {
    var nS = m.nameSize * fit, sS = m.subSize * fit,
        pS = m.pctSize * fit, vS = m.votesSize * fit, vC = m.votesCjkSize * fit;
    var name = c.name;
    var sub = c.vice ? ('副手：' + c.vice) : c.partyDisplay();
    var pct = c.pctText() + '%';
    var wName = lineWidth(ctx, name, nS, 900, 2 * fit);
    var wSub = lineWidth(ctx, sub, sS, 700, 1 * fit);
    var wPct = lineWidth(ctx, pct, pS, 900, 0, NT.FONT_NUM);
    var wVotes = votesLineWidth(ctx, c, vS, vC);
    var colW = Math.max(wName, wSub, wPct, wVotes);
    /* 文字自然寬超過上限 → 整張卡縮字級（不截字） */
    var cap = capFactor(colW, m.maxTextW, fit);
    if (cap < 1 && (depth || 0) < 3) {
      return this.specSmall(ctx, c, m, fit * cap, (depth || 0) + 1);
    }
    return {
      kind: 'small', c: c, fit: fit, colW: colW,
      w: m.padL + m.block.w + m.blockGap + colW + m.padR,
      name: name, sub: sub, pct: pct,
      nS: nS, sS: sS, pS: pS, vS: vS, vC: vC,
      wName: wName, wSub: wSub, wPct: wPct, wVotes: wVotes
    };
  };

  /** 第 3 名高卡的字級堆疊總高（k = 1 的基準值；實際乘上 fit）。
      五行：姓名 / 副手 / 政黨（有副手才有）/ 得票率 / 票數 —— 全部直排，
      所以「堆疊總高」只跟字級與行距有關，跟卡片寬度無關。 */
  function bigStackHeight(b, k, showParty) {
    return k * (b.nameSize + b.lineGap1 + b.subSize
                + (showParty ? b.lineGap2 + b.partySize : 0)
                + b.stackGap + b.pctSize + b.votesGap + b.votesSize);
  }

  /** 第 3 名高卡的字級係數 k：讓五行堆疊**剛好填滿卡內高度**（h − 2×padV）。
      沒有副手行（市長選舉）的場次堆疊較矮 → k 略大，字就自動大一點；
      夾在 scaleMin..scaleMax 之間，避免某場特別空或特別擠。 */
  MinorCandidateLayer.prototype.bigScale = function (c, m) {
    var b = m.big;
    var inner = b.h - 2 * b.padV;
    var base = Math.max(1, bigStackHeight(b, 1, !!c.vice));
    return Math.max(b.scaleMin, Math.min(b.scaleMax, inner / base));
  };

  /** 量第 3 名高卡：占位框（(h − 2×padV) × blockAspect）+ **單欄**直排文字。
      fit 為全域縮放係數（整條塞不下才會 < 1）；字級係數 k 由 bigScale 另計。 */
  MinorCandidateLayer.prototype.specBig = function (ctx, c, m, fit, depth) {
    var b = m.big;
    var blkH = b.h - 2 * b.padV, blkW = blkH * b.blockAspect;
    var nS = b.nameSize * fit, sS = b.subSize * fit, ptS = b.partySize * fit,
        pS = b.pctSize * fit, vS = b.votesSize * fit, vC = b.votesCjkSize * fit;
    var sub = c.vice ? ('副手：' + c.vice) : c.partyDisplay();
    var party = c.partyDisplay();
    var showParty = !!c.vice;
    var pct = c.pctText() + '%';
    var wName = lineWidth(ctx, c.name, nS, 900, 2 * fit);
    var wSub = lineWidth(ctx, sub, sS, 700, 1 * fit);
    var wParty = showParty ? lineWidth(ctx, party, ptS, 700, 1 * fit) : 0;
    var wPct = lineWidth(ctx, pct, pS, 900, 0, NT.FONT_NUM);
    var wVotes = votesLineWidth(ctx, c, vS, vC);
    var colW = Math.max(wName, wSub, wParty, wPct, wVotes);
    var cap = capFactor(colW, b.maxTextW, fit);
    if (cap < 1 && (depth || 0) < 3) {
      return this.specBig(ctx, c, m, fit * cap, (depth || 0) + 1);
    }
    return {
      kind: 'big', c: c, fit: fit, colW: colW,
      blockH: blkH, blockW: blkW,
      stackH: bigStackHeight(b, fit, showParty),
      w: b.padL + blkW + b.blockGap + colW + b.padR,
      name: c.name, sub: sub, party: party, showParty: showParty, pct: pct,
      nS: nS, sS: sS, ptS: ptS, pS: pS, vS: vS, vC: vC,
      gap1: b.lineGap1 * fit, gap2: b.lineGap2 * fit,
      stackGap: b.stackGap * fit, votesGap: b.votesGap * fit,
      wName: wName, wSub: wSub, wParty: wParty, wPct: wPct, wVotes: wVotes
    };
  };

  /** 量「其他候選人」清單格（★ 五版：一行一位候選人，不再合計）。
      內容＝`- 姓名    1,851票`（票數右對齊成一欄），**不印政黨、不印得票率**。
      高度由列數自己長（底部與左群同線、往上長），上限 = 第 3 名高卡的 h；
      列數多時每一列壓矮、字級按 rowH 比例縮，整張卡不會高過高卡（見 L9）。
      寬度 = padL + colW + padR，colW 由「最寬姓名 + 最寬票數」推得。 */
  MinorCandidateLayer.prototype.specOthers = function (ctx, list, m, fit, depth) {
    var o = m.others, i;
    var n = list.length;
    if (!n) return null;

    var titleSize = o.titleSize * fit;
    var titleH = o.title ? titleSize * 1.7 : 0;
    var want = titleH + n * o.rowH + 2 * o.padV;
    var h = Math.min(want, m.big.h);             /* 上限 = 第 3 名高卡 */
    var rowH = (h - titleH - 2 * o.padV) / n;    /* 一定 ≤ o.rowH */
    h = titleH + rowH * n + 2 * o.padV;          /* 列少 → 卡片自然變矮 */

    var k = rowH / o.rowH;                       /* 字級係數（列多 → < 1） */
    var size = o.size * fit * k;
    var dashW = o.dash ? lineWidth(ctx, o.dash, size, 700, 0) : 0;

    var rows = [], maxNameW = 0, maxVotesW = 0;
    for (i = 0; i < n; i++) {
      var c = list[i];
      var votes = U.voteWan(c.votes) + '票';
      var nw = lineWidth(ctx, c.name, size, 900, 1 * fit);
      var vw = lineWidth(ctx, votes, size, 700, 0, NT.FONT_NUM);
      if (nw > maxNameW) maxNameW = nw;
      if (vw > maxVotesW) maxVotesW = vw;
      rows.push({ name: c.name, votes: votes });
    }
    var colW = dashW + (o.dash ? o.dashGap * fit : 0)
             + maxNameW + o.colGap * fit + maxVotesW;
    var cap = capFactor(colW, o.maxTextW, fit);
    if (cap < 1 && (depth || 0) < 3) {
      return this.specOthers(ctx, list, m, fit * cap, (depth || 0) + 1);
    }
    return {
      kind: 'others', list: list, fit: fit, rows: rows, n: n,
      h: h, rowH: rowH, size: size,
      titleSize: titleSize, titleH: titleH,
      dashW: dashW, maxNameW: maxNameW, maxVotesW: maxVotesW, colW: colW,
      w: o.padL + colW + o.padR
    };
  };

  MinorCandidateLayer.prototype.draw = function (ctx) {
    var minors = this.model.minors || [];
    if (!minors.length) return;            /* 只有兩位候選人：整區不畫 */
    var m = L.minors;
    var b = m.big;
    var y = m.y, i;
    /* 第 3 名高卡：底部與左群同一條線（m.y + m.h），往上長 b.h */
    var bigY = m.y + m.h - b.h;

    /* 分群：第 4、5 名（窄卡）＋「其他候選人」清單格；右邊是第 3 名高卡 */
    var hasOthers = minors.length >= 5;
    var fixed = minors.slice(1, hasOthers ? 3 : 4);   /* 最多 2 張窄卡 */
    var hidden = hasOthers ? minors.slice(3) : [];    /* 第 6 名以後 */

    /* ---- 量寬 →（塞不下才）整條等比縮字級 ----
       窄卡：字級固定（fit=1）；第 3 名高卡：字級係數 k 由「五行剛好填滿卡高」
       決定（見 bigScale），卡片寬度永遠等於內容自然寬 —— 放大的是字級，不是留白。 */
    var kBig = this.bigScale(minors[0], m);
    var fit = 1, specs, big, gap, groupGap, leftW, need, avail = m.x1 - m.x0;
    for (var pass = 0; pass < 4; pass++) {
      gap = Math.max(m.minGap, m.gap * fit);
      groupGap = Math.max(m.minGap * 2, m.groupGap * fit);
      specs = [];
      for (i = 0; i < fixed.length; i++) specs.push(this.specSmall(ctx, fixed[i], m, fit));
      if (hasOthers) {
        var so = this.specOthers(ctx, hidden, m, fit);
        if (so) specs.push(so);
      }
      leftW = specs.reduce(function (s, x) { return s + x.w; }, 0)
            + gap * Math.max(0, specs.length - 1);

      big = this.specBig(ctx, minors[0], m, Math.min(fit, 1) * kBig);

      var gapsW = specs.length ? groupGap : 0;      /* 左群內部的 gap 已含在 leftW */
      need = leftW + gapsW + big.w;
      if (need <= avail || fit <= m.minTextScale) break;
      /* 字級與寬度近似線性 → 用「可用內容寬 / 需要內容寬」直接估下一個 fit
         （leftW 內含的 gap 隨 fit 一起縮，所以比較時只挑出 groupGap） */
      fit = Math.max(m.minTextScale, fit * ((avail - groupGap) / (leftW + big.w)));
    }

    /* ---- 畫：第 3 名高卡右緣貼 x1；左群「從它的左緣往左排」 ----
       順序由近而遠＝第 4 名 → 第 5 名 →（其他候選人清單，最左）。
       所以由右往左擺：游標先放在 bigX − groupGap，再一張一張往左扣。 */
    var bigX = Math.max(m.x0, m.x1 - big.w);
    var rects = [];
    var x = bigX - (specs.length ? groupGap : 0);
    for (i = 0; i < specs.length; i++) {
      var sp = specs[i];
      x -= sp.w;
      if (sp.kind === 'small') this.drawSmall(ctx, sp, x, y, m);
      else this.drawOthers(ctx, sp, x, y, m);
      rects.push({
        name: sp.kind === 'others' ? 'others' : 'small:' + sp.c.name,
        rect: { x: x, y: (sp.kind === 'others' ? y + m.h - sp.h : y),
                w: sp.w, h: (sp.kind === 'others' ? sp.h : m.h) },
        scale: sp.fit
      });
      x -= gap;
    }
    this.drawBig(ctx, big, bigX, bigY, m);
    rects.push({ name: 'big:' + minors[0].name,
                 rect: { x: bigX, y: bigY, w: big.w, h: b.h }, scale: big.fit });

    /* 供 verify_layout 用：每張卡的實際矩形（L7 互不相交、L8 都在帶內、L9 不壓地圖） */
    this.assets.minorCards = rects;
  };

  /** 畫一張小卡。 */
  MinorCandidateLayer.prototype.drawSmall = function (ctx, s, x, y, m) {
    var c = s.c, fit = s.fit;
    minorBlock(ctx, x + m.padL, y + (m.h - m.block.h) / 2, m.block, c.theme);

    var tx = x + m.padL + m.block.w + m.blockGap;
    U.text(ctx, fitLine(ctx, s.name, s.nS, 900, 2 * fit, s.colW), {
      x: tx, y: y + m.nameCy, size: s.nS, weight: 900,
      color: '#fff', baseline: 'middle', spacing: 2 * fit
    });
    U.text(ctx, fitLine(ctx, s.sub, s.sS, 700, 1 * fit, s.colW), {
      x: tx, y: y + m.subCy, size: s.sS, weight: 700,
      color: c.vice ? T.BG.textDim : T.BG.textFaint, baseline: 'middle', spacing: 1 * fit
    });
    U.text(ctx, s.pct, {
      x: tx, y: y + m.pctBase, size: s.pS, weight: 900, family: NT.FONT_NUM,
      color: c.theme.light, align: 'left', baseline: 'alphabetic'
    });
    drawVotes(ctx, c, tx, { y: y + m.votesBase, size: s.vS, cjkSize: s.vC },
      'left', { color: T.BG.textDim });
  };

  /** 畫第 3 名高卡：占位框（吃滿卡高）+ **單欄**直排（姓名／副手／政黨／得票率／
      票數）。整欄由 s.stackH 推到卡內垂直置中，行距由字級推導 → 任何字級都不疊字。
      得票率／票數右對齊到文字欄右緣（寬度＝最寬那一行），不另外撐寬卡片。 */
  MinorCandidateLayer.prototype.drawBig = function (ctx, s, x, y, m) {
    var b = m.big, c = s.c;
    minorBlock(ctx, x + b.padL, y + b.padV,
               { w: s.blockW, h: s.blockH, radius: b.blockRadius }, c.theme);

    var tx = x + b.padL + s.blockW + b.blockGap;
    var right = x + s.w - b.padR;                 /* 文字欄右緣 = 卡片右緣 − padR */
    var top = y + (b.h - s.stackH) / 2;           /* 整欄垂直置中 */

    U.text(ctx, fitLine(ctx, s.name, s.nS, 900, 2 * s.fit, s.colW), {
      x: tx, y: top + s.nS / 2, size: s.nS, weight: 900,
      color: '#fff', baseline: 'middle', spacing: 2 * s.fit
    });
    top += s.nS + s.gap1;

    U.text(ctx, fitLine(ctx, s.sub, s.sS, 700, 1 * s.fit, s.colW), {
      x: tx, y: top + s.sS / 2, size: s.sS, weight: 700,
      color: c.vice ? T.BG.textDim : T.BG.textFaint, baseline: 'middle',
      spacing: 1 * s.fit
    });
    top += s.sS;

    if (s.showParty) {
      top += s.gap2;
      U.text(ctx, s.party, {
        x: tx, y: top + s.ptS / 2, size: s.ptS, weight: 700,
        color: T.BG.textFaint, baseline: 'middle', spacing: 1 * s.fit
      });
      top += s.ptS;
    }

    top += s.stackGap;
    U.text(ctx, s.pct, {
      x: right, y: top + s.pS * b.capRatio, size: s.pS, weight: 900,
      family: NT.FONT_NUM, color: c.theme.light, align: 'right', baseline: 'alphabetic'
    });
    top += s.pS + s.votesGap;
    drawVotes(ctx, c, right, {
      y: top + s.vS * b.capRatio, size: s.vS, cjkSize: s.vC
    }, 'right', { color: T.BG.textDim });
  };

  /** 畫「其他候選人」清單格：標題 + **一行一位**（`- 姓名    1,851票`）。
      票數右對齊成一欄（看起來是一張表）；不畫照片區、不印政黨與得票率。
      卡片底部與左群同一條線、往上長（s.h），列與列之間一條極淡細線。 */
  MinorCandidateLayer.prototype.drawOthers = function (ctx, s, x, y, m) {
    var o = m.others, fit = s.fit, i;
    var top = y + m.h - s.h;                   /* 底部同線、往上長 */

    var tx = x + o.padL;
    var ty = top + o.padV;
    if (o.title) {
      U.text(ctx, o.title + '（' + s.n + ' 位）', {
        x: tx, y: ty + s.titleSize / 2, size: s.titleSize, weight: 900,
        color: '#fff', baseline: 'middle', spacing: 2 * fit
      });
      ty += s.titleH;
    }

    var lx = tx + (o.dash ? s.dashW + o.dashGap * fit : 0);
    var rx = tx + s.colW;                      /* 票數欄右緣（表格式對齊） */
    for (i = 0; i < s.rows.length; i++) {
      var r = s.rows[i];
      var cy = ty + s.rowH * (i + 0.5);
      if (o.dash) {
        U.text(ctx, o.dash, {
          x: tx, y: cy, size: s.size, weight: 700,
          color: T.BG.textFaint, baseline: 'middle'
        });
      }
      U.text(ctx, fitLine(ctx, r.name, s.size, 900, 1 * fit, s.colW), {
        x: lx, y: cy, size: s.size, weight: 900,
        color: '#fff', baseline: 'middle', spacing: 1 * fit
      });
      U.text(ctx, r.votes, {
        x: rx, y: cy, size: s.size, weight: 700, family: NT.FONT_NUM,
        color: T.BG.textDim, baseline: 'middle', align: 'right'
      });
      if (o.rule && i < s.rows.length - 1) {
        ctx.save();
        ctx.strokeStyle = o.ruleColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(tx, Math.round(cy + s.rowH / 2) + 0.5);
        ctx.lineTo(x + s.w - o.padR, Math.round(cy + s.rowH / 2) + 0.5);
        ctx.stroke();
        ctx.restore();
      }
    }
  };

  /* =====================================================================
     RibbonLayer —— 底部得票比例帶
     ===================================================================== */
  function RibbonLayer(slide) { Layer.call(this, slide); }
  RibbonLayer.prototype = Object.create(Layer.prototype);
  RibbonLayer.prototype.constructor = RibbonLayer;

  RibbonLayer.prototype.draw = function (ctx) {
    var segs = this.model.ribbonSegments();
    var rb = L.ribbon;
    var x = 0;
    var totalGap = rb.gap * (segs.length - 1);
    var avail = L.W - totalGap;

    for (var i = 0; i < segs.length; i++) {
      var s = segs[i];
      var w = Math.max(6, s.ratio * avail);
      ctx.save();
      ctx.fillStyle = U.gradient(ctx, x, rb.y, x, rb.y + rb.h, [
        [0, U.lighten(s.color, 0.18)], [1, U.darken(s.color, 0.12)]
      ]);
      ctx.fillRect(x, rb.y, w, rb.h);
      ctx.restore();

      if (w > 170) {
        U.text(ctx, (s.ratio * 100).toFixed(2) + '%', {
          x: x + w / 2, y: rb.y + rb.h / 2 + 1, size: 24, weight: 900,
          family: NT.FONT_NUM,
          color: 'rgba(255,255,255,0.92)', align: 'center', baseline: 'middle',
          spacing: 1
        });
      }
      x += w + rb.gap;
    }
  };

  NT.BackgroundLayer = BackgroundLayer;
  NT.HeaderLayer = HeaderLayer;
  NT.MapLayer = MapLayer;
  NT.Map2Layer = Map2Layer;
  NT.LegendLayer = LegendLayer;
  NT.CandidateLayer = CandidateLayer;
  NT.MinorCandidateLayer = MinorCandidateLayer;
  NT.RibbonLayer = RibbonLayer;

})(window);
