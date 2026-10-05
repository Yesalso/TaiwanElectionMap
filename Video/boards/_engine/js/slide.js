/* ==========================================================================
   slide.js — Slide：把資料 + 資源 + 一組圖層組成「一張看板」
   --------------------------------------------------------------------------
   使用方式：
     var slide = new NT.Slide(model, {name: '2014 新北市長選舉', year: 2014});
     await slide.load();
     slide.render(canvas.getContext('2d'), 1);
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;
  var L = NT.Layout;

  /**
   * @param {NT.ElectionModel} model
   * @param {object} opt {name, year, subtitle}
   */
  function Slide(model, opt) {
    opt = opt || {};
    this.model = model;
    this.name = opt.name || model.meta.election;
    this.year = opt.year || model.meta.year;
    this.subtitle = opt.subtitle || '';
    this.assets = {};          // 影像與投影器
    this.layers = [];          // 依繪製順序排列
    this._loaded = false;
    this._buildLayers();
  }

  /** 建立圖層（順序即疊放順序，後蓋前） */
  Slide.prototype._buildLayers = function () {
    this.layers = [
      new NT.BackgroundLayer(this),
      new NT.HeaderLayer(this),
      new NT.MapLayer(this),
      new NT.LegendLayer(this),
      new NT.CandidateLayer(this),
      new NT.MinorCandidateLayer(this),
      new NT.RibbonLayer(this)
    ];
  };

  /**
   * file:// 下要不要改用內嵌的 data URI？
   *
   * 要。file:// 的每個檔案都是不透明來源，只要把本機圖檔畫上 canvas，canvas 就
   * 會變成「畫得出來、讀不回去」：縮圖的 toDataURL 與匯出的 toBlob 一律拋
   * SecurityError。http(s) 下則相反——實體檔才對，換檔重新整理就生效，實體檔
   * 讀不到才退回內嵌。
   */
  function useEmbeddedUnderFile() {
    return !!(global.location && global.location.protocol === 'file:');
  }

  /** 1×1 透明 PNG：畫布被汙染時的縮圖替身 */
  var BLANK_THUMB =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

  /**
   * 載入得票率地圖。
   *
   * ★ 來源分兩種環境：
   *   http(s)：一律以 Layout.map.src（預設 assets/vote_map.png）這個「實體檔」為準，
   *     使用者換掉檔案、重新整理就是最新版，絕不回頭吃 data/local-assets.js 裡
   *     過時的內嵌副本（那種「改了圖頁面沒變」的坑踩過一次就夠了），並附加時間戳
   *     避免快取。
   *   file://：改用內嵌副本，否則 canvas 被汙染，左側縮圖與「下載 PNG」直接壞掉
   *     （見 useEmbeddedUnderFile）。此時要更新內嵌副本請重跑
   *     python tools/build_assets.py。
   *   兩種環境下，檔案真的讀不到都會再退回內嵌，頁面不會開天窗，並在
   *   assets.mapSource 標記來源，工具列滑桿的提示會顯示實際用的是哪個。
   *
   * @returns {Promise<HTMLImageElement|null>}
   */
  Slide.prototype._loadVoteMap = function () {
    var self = this;
    var A = global.NT_ASSETS || {};
    var src = U.resolveAsset((L.map && L.map.src) || '');

    function useEmbedded(reason) {
      if (!A.voteMap) {
        console.warn('[Slide] 地圖不可用：' + reason + '，且沒有內嵌備援。');
        self.assets.mapSource = 'none';
        return Promise.resolve(null);
      }
      console.warn('[Slide] ' + reason + '，暫用內嵌地圖（可能是舊版，' +
        '請確認 ' + src + ' 存在，或重跑 python tools/build_assets.py 更新內嵌）。');
      self.assets.mapSource = 'embedded';
      return U.loadImage(A.voteMap);
    }

    if (!src) return useEmbedded('未設定 Layout.map.src');

    if (useEmbeddedUnderFile()) {
      if (!A.voteMap) return useEmbedded('file:// 下需要內嵌地圖，但 data/local-assets.js 沒有');
      self.assets.mapSource = 'embedded';
      return U.loadImage(A.voteMap).catch(function () {
        return useEmbedded('內嵌地圖解碼失敗');
      });
    }

    /* http(s) 下加時間戳，避免換了圖還看到快取 */
    var url = src;
    if (src.indexOf('?') < 0) {
      url += '?t=' + Date.now();
    }

    return U.loadImage(url).then(function (img) {
      self.assets.mapSource = 'file';
      return img;
    }).catch(function () {
      return useEmbedded('讀不到 ' + src);
    });
  };

  /**
   * 載入頁眉左上角的「新北市市徽」（已去白底的透明 PNG）。
   *
   * 和地圖同一套規則：http(s) 下以實體檔（Layout.header.seal.src）為準並加時間戳，
   * file:// 下改用內嵌副本（否則同樣會汙染 canvas）。兩邊都讀不到時回 null，
   * 由 HeaderLayer 退回原本的藍底圈勾方塊，頁面不會開天窗。
   *
   * @returns {Promise<HTMLImageElement|null>}
   */
  Slide.prototype._loadCitySeal = function () {
    var self = this;
    var A = global.NT_ASSETS || {};
    var src = U.resolveAsset((L.header.seal && L.header.seal.src) || '');

    function giveUp(reason) {
      if (src) console.warn('[Slide] 讀不到市徽（' + reason + '），左上角改用預設圈勾方塊。');
      self.assets.sealSource = 'none';
      return null;
    }

    if (useEmbeddedUnderFile()) {
      if (!A.citySeal) return Promise.resolve(giveUp('data/local-assets.js 沒有內嵌市徽'));
      return U.loadImage(A.citySeal).then(function (img) {
        self.assets.sealSource = 'embedded';
        return img;
      }).catch(function () { return giveUp('內嵌市徽解碼失敗'); });
    }

    if (!src) return Promise.resolve(giveUp('未設定 Layout.header.seal.src'));

    /* http(s) 下加時間戳，避免換了圖還看到快取 */
    var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;

    return U.loadImage(url).then(function (img) {
      self.assets.sealSource = 'file';
      return img;
    }).catch(function () { return giveUp('讀不到 ' + src); });
  };

  /**
   * 載入日期塊的圓徽底圖（assets/emblem.png，已去背成透明 PNG）。
   *
   * 和地圖／市徽同一套規則：http(s) 下以實體檔（Layout.header.dateBlock.disc.src）
   * 為準並加時間戳，file:// 下改用內嵌副本（否則同樣會汙染 canvas）。
   * 兩邊都讀不到時回 null，由 HeaderLayer 退回原本的暗絳紅圓盤，頁面不會開天窗。
   *
   * @returns {Promise<HTMLImageElement|null>}
   */
  Slide.prototype._loadEmblem = function () {
    var self = this;
    var A = global.NT_ASSETS || {};
    var src = U.resolveAsset((L.header.dateBlock.disc && L.header.dateBlock.disc.src) || '');

    function giveUp(reason) {
      if (src) console.warn('[Slide] 讀不到日期圓徽（' + reason + '），日期底色改用暗紅圓盤。');
      self.assets.emblemSource = 'none';
      return null;
    }

    if (useEmbeddedUnderFile()) {
      if (!A.emblem) return Promise.resolve(giveUp('data/local-assets.js 沒有內嵌圓徽'));
      return U.loadImage(A.emblem).then(function (img) {
        self.assets.emblemSource = 'embedded';
        return img;
      }).catch(function () { return giveUp('內嵌圓徽解碼失敗'); });
    }

    if (!src) return Promise.resolve(giveUp('未設定 Layout.header.dateBlock.disc.src'));

    /* http(s) 下加時間戳，避免換了圖還看到快取 */
    var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;

    return U.loadImage(url).then(function (img) {
      self.assets.emblemSource = 'file';
      return img;
    }).catch(function () { return giveUp('讀不到 ' + src); });
  };

  /**
   * 載入政黨徽章（assets/party_<key>.png，已去背成圓形透明 PNG）。
   *
   * 與市徽／圓徽同一套規則：http(s) 下以實體檔為準並加時間戳，
   * file:// 下改用內嵌副本（同樣的理由：實體檔會汙染 canvas）。
   * 這是「依政黨 key 對應的一組圖」，回傳 {kmt: img, dpp: img, nsc: img, …}；
   * 單一政黨讀不到時那一格給 null，由 CandidateLayer 退回原本的抽象色塊，
   * 其他政黨不受影響。
   *
   * ★ 要載哪些 key（2026-10-04 起）：
   *   1. Layout.chip.marks 有宣告的先用（目前 kmt / dpp）；
   *   2. 再把「這場看板候選人實際出現、且政黨本身有標章」的 key 補齊，
   *      檔名依慣例 assets/party_<key>.png。
   *      有標章的政黨表對齊 tools/boardlib/naming.py 的 PARTIES_WITH_MARK
   *      （kmt / dpp / tpp / nsc / pfp）—— 無黨籍、小黨沒有標準標章，
   *      不找圖、直接用抽象色塊。以前只載 marks 寫死的兩張，
   *      1994 趙少康（新黨）／2006 宋楚瑜（親民黨）因此一直顯示回退色塊。
   *
   * 注意：左右兩張候選人卡共用同一個 chip 設定物件（layout.js 的 candidateBlock
   * 以 Object.assign 淺拷貝給 Layout.left / Layout.right），所以取 L.left.chip 即可。
   *
   * @returns {Promise<Object>} {<partyKey>: HTMLImageElement|null, ...}
   */
  Slide.prototype._loadPartyMarks = function () {
    var self = this;
    var A = global.NT_ASSETS || {};
    var conf = (L.left && L.left.chip && L.left.chip.marks) || {};
    /* 政黨本身有標章的 key（對齊 tools/boardlib/naming.py 的 PARTIES_WITH_MARK）*/
    var PARTIES_WITH_MARK = ['kmt', 'dpp', 'tpp', 'nsc', 'pfp'];
    var keys = Object.keys(conf);
    (this.model.candidates || []).forEach(function (c) {
      var k = c.partyKey;
      if (k && PARTIES_WITH_MARK.indexOf(k) >= 0 && keys.indexOf(k) < 0) {
        keys.push(k);
      }
    });
    /* 內嵌副本的欄位名（board.assets.js 的 window.NT_ASSETS），
       命名規則對齊 tools/boardlib/naming.py 的 party_engine_field()：
       kmt -> partyKmt、nsc -> partyNsc、pfp -> partyPfp… */
    function embedField(key) {
      return 'party' + key.charAt(0).toUpperCase() + key.slice(1);
    }
    var underFile = useEmbeddedUnderFile();
    self.assets.partyMarkSource = {};

    function fromEmbedded(key) {
      var field = embedField(key);
      if (!field || !A[field]) {
        self.assets.partyMarkSource[key] = 'none';
        return Promise.resolve(null);
      }
      return U.loadImage(A[field]).then(function (img) {
        self.assets.partyMarkSource[key] = 'embedded';
        return img;
      }).catch(function () {
        self.assets.partyMarkSource[key] = 'none';
        return null;
      });
    }

    return Promise.all(keys.map(function (key) {
      var src = U.resolveAsset(conf[key] || ('assets/party_' + key + '.png'));
      if (!src || underFile) return fromEmbedded(key);

      var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;
      return U.loadImage(url).then(function (img) {
        self.assets.partyMarkSource[key] = 'file';
        return img;
      }).catch(function () {
        console.warn('[Slide] 讀不到政黨徽章 ' + src + '（' + key +
          '），該格退回抽象色塊；請確認檔案存在，或重跑 '
          + 'python tools/build_board.py <board> --force-assets。');
        return fromEmbedded(key);
      });
    })).then(function (imgs) {
      var out = {};
      keys.forEach(function (key, i) { out[key] = imgs[i]; });
      return out;
    });
  };

  /**
   * 載入得票率圖例（assets/legend.png，已去背的透明 PNG）。
   *
   * 和地圖／市徽／圓徽／黨徽同一套規則：http(s) 下以實體檔（Layout.legend.src）
   * 為準並加時間戳，file:// 下改用內嵌副本（否則同樣會汙染 canvas）。
   * 兩邊都讀不到時回 null，由 LegendLayer 整個跳過不畫（看板上少一塊圖例，
   * 但不會留下一個空底板或開天窗）。
   *
   * @returns {Promise<HTMLImageElement|null>}
   */
  Slide.prototype._loadLegend = function () {
    var self = this;
    var A = global.NT_ASSETS || {};
    var src = U.resolveAsset((L.legend && L.legend.src) || '');

    function giveUp(reason) {
      if (src) console.warn('[Slide] 讀不到圖例（' + reason + '），看板不畫圖例區。');
      self.assets.legendSource = 'none';
      return null;
    }

    if (useEmbeddedUnderFile()) {
      if (!A.legend) return Promise.resolve(giveUp('data/local-assets.js 沒有內嵌圖例'));
      return U.loadImage(A.legend).then(function (img) {
        self.assets.legendSource = 'embedded';
        return img;
      }).catch(function () { return giveUp('內嵌圖例解碼失敗'); });
    }

    if (!src) return Promise.resolve(giveUp('未設定 Layout.legend.src'));

    /* http(s) 下加時間戳，避免換了圖還看到快取 */
    var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;

    return U.loadImage(url).then(function (img) {
      self.assets.legendSource = 'file';
      return img;
    }).catch(function () { return giveUp('讀不到 ' + src); });
  };

  /** 非同步載入影像、建立投影器 */
  Slide.prototype.load = function () {
    if (this._loaded) return Promise.resolve(this);
    var self = this;
    var m = this.model;
    /* 使用者提供的素材（當選標誌、得票率地圖），由 data/local-assets.js 內嵌 */
    var A = global.NT_ASSETS || {};

    /* ★ 不載入候選人照片：看板不畫照片，卡面只填政黨純色
         （見 render/layers.js 的 CandidateLayer / MinorCandidateLayer）。 */
    return Promise.all([
      /* 當選印記：優先吃內嵌（file:// 用），其次吃實體檔 mark_elected.png */
      U.loadImage(A.electedMark
        || U.resolveAsset((L.electedMark && L.electedMark.src))),
      this._loadVoteMap(),
      this._loadCitySeal(),
      this._loadEmblem(),
      this._loadPartyMarks(),
      this._loadLegend()
    ]).then(function (res) {
      /* 當選印記 ＋ 得票率地圖 + 左上角市徽 + 日期圓徽 + 政黨徽章 + 圖例 */
      self.assets.electedMark = res[0];
      self.assets.voteMap = res[1];
      self.assets.citySeal = res[2];
      self.assets.emblem = res[3];
      self.assets.partyMarks = res[4];
      self.assets.legend = res[5];

      /* 地圖若帶海報自帶的標題／圖例（Layout.map.crop），擦掉並裁到地圖本體；
         正常情況下不會有 crop —— 素材已由 imagelab / build_vote_map 預處理成
         「只剩地圖本體」的透明 PNG，這裡只是留一個硬要塞原始海報圖的逃生門。 */
      if (self.assets.voteMap && L.map.crop) {
        var cleaned = U.eraseAndCrop(self.assets.voteMap, L.map.crop);
        if (cleaned) self.assets.voteMap = cleaned;
      }

      /* 記下素材尺寸：狀態列要顯示「實際用的是哪一張、多大」，
         未預處理的海報原圖也能一眼認出來（見 Slide.prototype.mapHint）。 */
      self.assets.mapInfo = self.assets.voteMap ? {
        w: self.assets.voteMap.width, h: self.assets.voteMap.height, source: self.assets.mapSource
      } : null;

      /* 背景浮水印用的大投影器（刻意超出畫布，讓輪廓看起來是「切」出來的） */
      self.assets.projectorBackdrop = new NT.GeoProjector(m.geojson, {
        x: L.W * 0.5 - 1900, y: -180, w: 3800, h: 1900
      }, { pad: 0 });

      self._loaded = true;
      return self;
    });
  };

  /**
   * 素材有問題時回傳一句話，沒問題回傳 null。
   * 判斷：預處理後的地圖本體接近正方（寬高比 ≈ 1.05），未處理的海報是 4:3（≈ 1.33），
   * 所以「丟了整張海報進來」是看得出來的，不靠猜。
   */
  Slide.prototype.mapIssue = function () {
    var m = this.assets.mapInfo;
    if (!m) {
      return '地圖未載入（' + (L.map.src || '未設定') +
        '），請執行 python tools/build_vote_map.py';
    }
    if (!L.map.crop && m.w / m.h > 1.2) {
      return '地圖是未預處理的海報原圖 ' + m.w + ' × ' + m.h +
        ' px（含標題／圖例），請執行 python tools/build_vote_map.py';
    }
    return null;
  };

  /** 關於「地圖素材」的一句話，給工具列的 title／狀態列顯示 */
  Slide.prototype.mapHint = function () {
    var m = this.assets.mapInfo;
    var issue = this.mapIssue();
    if (issue) return issue;
    if (!m) return '無地圖';
    var from = {
      file: 'assets/vote_map.png',
      /* file:// 下內嵌版才是主要來源（用實體檔會汙染 canvas），
         這裡別再稱它「後備」，會讓人以為換檔沒生效是 bug */
      embedded: 'local-assets.js 內嵌版（file:// 必要）',
      none: '無'
    };
    return '地圖 ' + m.w + ' × ' + m.h + ' px（' + (from[m.source] || m.source) + '）';
  };

  /**
   * 繪製整張看板
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} scale  1 = 2560×1440；2 = 5120×2880
   */
  Slide.prototype.render = function (ctx, scale) {
    var s = scale || 1;
    ctx.save();
    ctx.setTransform(s, 0, 0, s, 0, 0);
    ctx.clearRect(0, 0, L.W, L.H);
    ctx.textBaseline = 'alphabetic';

    for (var i = 0; i < this.layers.length; i++) {
      var layer = this.layers[i];
      ctx.save();
      if (layer instanceof NT.CandidateLayer) {
        /* 主要候選人圖層負責左右兩位 */
        layer.draw(ctx, this.model.left, L.left);
        layer.draw(ctx, this.model.right, L.right);
      } else {
        layer.draw(ctx);
      }
      ctx.restore();
    }
    ctx.restore();
    return this;
  };

  /** 直接渲染到 canvas 元素 */
  Slide.prototype.renderTo = function (canvas, scale) {
    var s = scale || 1;
    canvas.width = L.W * s;
    canvas.height = L.H * s;
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    this.render(ctx, s);
    return canvas;
  };

  /** 產生縮圖 dataURL（用於左側清單） */
  Slide.prototype.thumbnail = function (width) {
    var cv = document.createElement('canvas');
    var ratio = L.H / L.W;
    cv.width = width;
    cv.height = Math.round(width * ratio);
    var ctx = cv.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    this.render(ctx, width / L.W);
    /* 畫布若被跨來源圖檔汙染，toDataURL 會拋 SecurityError。這裡一定要自己收掉：
       thumbnail() 是 buildRail() 的一環，例外往上冒會讓整個開機流程中斷，
       結果就是左側清單空白、狀態列永遠停在「載入中…」，而且沒有任何錯誤訊息。 */
    try {
      return cv.toDataURL('image/png');
    } catch (e) {
      console.warn('[Slide] 縮圖輸出失敗（canvas 被汙染）：' + (e && e.name));
      return BLANK_THUMB;
    }
  };

  NT.Slide = Slide;

})(window);
