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

    /* 1. 主底色 */
    ctx.fillStyle = U.gradient(ctx, 0, 0, 0, H, [
      [0, T.BG.top], [0.42, T.BG.mid], [1, T.BG.bottom]
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

    /* ---------------- 左：新北市市徽（固定貼齊左邊界） ----------------
       重要：只畫「一次」。早先的寫法是先畫在 x=0 再用 clearRect 擦掉重畫，
       那一擦連同一區的選舉名稱和頂部漸層帶一起擦掉了（選舉名稱整行消失）。
       現在先用寬高比算出寬度、決定最終 x，再一次畫到位。 */
    var sealConf = H.seal;
    var sealGap = sealConf.gap || 0;
    var sealH = boxH * (sealConf.hRatio === undefined ? 1 : sealConf.hRatio);
    var sealY = db.y + (boxH - sealH) / 2;
    var seal = this.assets.citySeal;
    var sealBox = null;
    if (seal && seal.width) {
      sealBox = Marks.imageByHeight(ctx, seal, sealConf.x, sealY, sealH);
    } else {
      /* 讀不到市徽時退回原本的圈選記號，不讓這一格開天窗 */
      var r = sealH * 0.30;
      sealBox = { x: sealConf.x, y: sealY, w: sealH, h: sealH };
      Marks.voteMark(ctx, sealBox.x + sealH / 2, sealY + sealH / 2,
        r, 'rgba(255,255,255,0.9)', 6);
    }
    /* 記下實際落點，供自動化驗證量測 */
    this.assets.sealRect = sealBox;

    /* ---------------- 左：選舉名稱（單行，讓開市徽） ----------------
       早先這裡上面還有一行小字「TAIWAN, CHINA」，依需求移除。
       名稱是左側唯一的錨點，用「實際墨跡」視覺置中於日期塊的水平軸，
       讓左／中／右三塊共用同一條中心線。 */
    var ltX = sealBox ? (sealBox.x + sealBox.w + sealGap) : H.leftText.x;
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
       斷開距離與原本的觀感接近（約 2em），但不會再多一個圓點搶眼。 */
    var st = H.stats;
    U_.text(ctx, '投票率 ' + meta.turnout.toFixed(2) + '%\u3000\u3000有效票 ' +
      U_.voteWan(meta.validVotes), {
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
     MinorCandidateLayer —— 第三位候選人（小卡）
     ===================================================================== */
  function MinorCandidateLayer(slide) { Layer.call(this, slide); }
  MinorCandidateLayer.prototype = Object.create(Layer.prototype);
  MinorCandidateLayer.prototype.constructor = MinorCandidateLayer;

  MinorCandidateLayer.prototype.draw = function (ctx) {
    var c = this.model.minor, m = L.minor;
    /* 只有兩位候選人的選舉（例：2002 馬英九 vs 李應元）沒有第三位小卡，
       直接不畫這一層 —— 泛化後任何候選人數都要能渲染。 */
    if (!c) return;
    var x = m.cx - m.w / 2, y = m.y;
    var th = c.theme;

    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.55)';
    ctx.shadowBlur = 26;
    ctx.shadowOffsetY = 10;
    ctx.fillStyle = 'rgba(6,12,26,0.78)';
    U.roundRectPath(ctx, x, y, m.w, m.h, m.radius);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.16)';
    ctx.lineWidth = 2;
    U.roundRectPath(ctx, x, y, m.w, m.h, m.radius);
    ctx.stroke();
    ctx.restore();

    /* 頭像框：與主卡同一條規則 —— 不畫照片，只填政黨純色底（見 CandidateLayer） */
    var px = x + m.card.offsetX;
    var py = y + (m.h - m.card.h) / 2;
    ctx.save();
    ctx.fillStyle = th.main;
    U.roundRectPath(ctx, px, py, m.card.w, m.card.h, m.card.radius);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.28)';
    ctx.lineWidth = 2;
    U.roundRectPath(ctx, px, py, m.card.w, m.card.h, m.card.radius);
    ctx.stroke();
    ctx.restore();

    var tx = x + m.nameX;
    var rx = x + m.w + m.pctRight;
    U.text(ctx, c.name, {
      x: tx, y: y + m.nameY, size: m.nameSize, weight: 900,
      color: '#fff', baseline: 'middle', spacing: 3
    });
    /* 政黨名：先換成短名（無黨籍及未經政黨推薦 -> 無黨籍），
       再依實際可用寬度（左側文字起點 → 右側票數區）裁切，
       免得長黨名壓到右邊的得票數。 */
    var partyLabel = c.partyDisplay();
    ctx.save();
    ctx.font = U.font(m.partySize, 700);
    partyLabel = U.fitText(ctx, partyLabel, rx - tx - 210, 2);
    ctx.restore();
    U.text(ctx, partyLabel, {
      x: tx, y: y + m.partyY, size: m.partySize, weight: 700,
      color: T.BG.textFaint, baseline: 'middle', spacing: 2
    });

    U.text(ctx, c.pctText() + '%', {
      x: rx, y: y + m.pctY, size: m.pctSize, weight: 900, family: NT.FONT_NUM,
      color: th.light, align: 'right', baseline: 'middle'
    });
    drawVotes(ctx, c, rx, { y: y + m.votesY, size: m.votesSize, cjkSize: m.votesCjkSize },
      'right', { color: T.BG.textDim });
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
  NT.LegendLayer = LegendLayer;
  NT.CandidateLayer = CandidateLayer;
  NT.MinorCandidateLayer = MinorCandidateLayer;
  NT.RibbonLayer = RibbonLayer;

})(window);
