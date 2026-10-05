/* ==========================================================================
   headless.js — 無頭渲染 Hook（Node + Edge CDP 用）
   --------------------------------------------------------------------------
   只有在 index.html 帶 ?headless=1 時才會被載入。
   把「渲染」從 App（UI）裡抽出來，批次流程就不必模擬按鈕點擊：
     await window.__boardReady();                       // 等資料與素材就緒
     var dataURL = await window.__renderBoard(scale);   // 回傳 PNG dataURL
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var slidePromise = null;

  /** 建立並載入本場看板（只做一次，之後重用） */
  function build() {
    if (!slidePromise) {
      slidePromise = Promise.resolve().then(function () {
        if (!global.BOARD) throw new Error('window.BOARD 不存在（board.js 未載入？）');
        console.log('[headless] 建立模型…');
        var model = new NT.ElectionModel(global.BOARD);
        console.log('[headless] 模型就緒，開始載入素材…');
        var slide = new NT.Slide(model, {
          name: model.meta.election,
          year: model.meta.year,
          subtitle: model.meta.office || ''
        });
        return slide.load().then(function () {
          console.log('[headless] 素材載入完成');
          return slide;
        });
      });
    }
    return slidePromise;
  }

  /** 只等就緒，不渲染 */
  global.__boardReady = function () {
    return build().then(function () { return true; });
  };

  /**
   * 渲染到一張 canvas 並回傳（內部用）。
   * 先畫一次觸發字型載入，等 document.fonts.ready 後再畫一次 ——
   * 沒等字型的話 headless 會用 fallback 字型，數字墨跡與正式版不一致。
   * 字型不能無限等（萬一不 settle 會整個卡住），設 3 秒上限。
   */
  function renderToCanvas(scale) {
    var s = scale || 1;
    return build().then(function (slide) {
      var cv = document.createElement('canvas');
      cv.width = NT.Layout.W * s;
      cv.height = NT.Layout.H * s;
      var ctx = cv.getContext('2d');
      ctx.imageSmoothingQuality = 'high';

      console.log('[headless] 開始渲染 ' + cv.width + 'x' + cv.height);
      slide.render(ctx, s);                       // 暖機：觸發字型下載
      console.log('[headless] 暖機完成，等字型');
      return Promise.race([
        document.fonts.ready,
        new Promise(function (r) { setTimeout(r, 3000); })
      ]).then(function () {
        slide.render(ctx, s);                     // 字型到位後重繪
        console.log('[headless] 渲染完成');
        return cv;
      });
    });
  }

  /** 回傳 PNG dataURL（小圖可直接用；大圖請用 __saveBoard，見下） */
  global.__renderBoard = function (scale) {
    return renderToCanvas(scale).then(function (cv) {
      return cv.toDataURL('image/png');
    });
  };

  /**
   * 渲染後直接 POST 給渲染器的 /__save 端點，由 Node 端寫檔。
   *
   * ★ 為什麼不把 dataURL 回傳給 CDP：2560×1440 的 PNG base64 約 5.6 MB，
   *   超過 CDP/WebSocket 的單一訊息上限，訊息會被丟掉、Node 端看起來像「逾時」。
   *   走 HTTP POST 上傳就沒有這個限制。
   *
   * @param {number} scale
   * @param {string} name  輸出檔名（渲染器已消毒）
   * @returns {Promise<{ok:boolean, bytes:number, file:string}>}
   */
  global.__saveBoard = function (scale, name) {
    return renderToCanvas(scale).then(function (cv) {
      return new Promise(function (resolve, reject) {
        cv.toBlob(function (blob) {
          if (!blob) return reject(new Error('toBlob 回傳 null'));
          fetch('/__save?name=' + encodeURIComponent(name), { method: 'POST', body: blob })
            .then(function (r) {
              if (!r.ok) throw new Error('/__save HTTP ' + r.status);
              return r.json();
            })
            .then(resolve)
            .catch(reject);
        }, 'image/png');
      });
    }).catch(function (e) {
      console.log('[headless] 渲染失敗：' + (e && e.message));
      throw e;
    });
  };

  /* =====================================================================
     版面報告 —— 給 tools/verify_layout.py 做「圖例不得壓到地圖／其他元素」
     的自動驗證。

     為什麼要這支：
     「圖例有沒有壓到東西」本來只能靠眼睛看，改一次版面就要人再盯一次，
     遲早會漏。這裡把所有相關矩形的「實際值」（不是設定值）吐出來：
     地圖落點由 MapLayer 記在 assets.mapRect、圖例由 LegendLayer 記在
     assets.legendRect，其餘元素由 Layout 常數 + 真實字型量測推得。
     再搭配地圖 PNG 的 alpha 墨跡外接框，驗證腳本就能逐一比對相交與否。

     回傳：{board, canvas, map:{frame,drawn,content}, legend:{box,image},
            elements:{header,ribbon,minor, cards:[{name,rect}…]}}

     ★ 主卡為什麼拆成一串子矩形（cards），而不是給一顆外接框：
       主卡是「照片 274–894、標籤 910–986、姓名 1096、得票率 1282、得票數 1386」
       疊起來的一整條。只給外接框會得到 274–1403 × 1967–2533 的大框，
       圖例（1600–2008 × 453–973）跟它一比就「相交」——但那個相交區其實整片是空的
       （照片卡從 2024 才起、得票率那行在 y 1170 以下）。
       初版就是這樣誤判的，所以這裡逐塊輸出、驗證腳本逐塊比。
     ===================================================================== */

  /** 掃描圖片實際墨跡（alpha > 16）的外接框；座標是「圖片自身像素」 */
  function alphaBBox(img) {
    var cv = document.createElement('canvas');
    cv.width = img.naturalWidth;
    cv.height = img.naturalHeight;
    var c2 = cv.getContext('2d');
    c2.drawImage(img, 0, 0);
    var d = c2.getImageData(0, 0, cv.width, cv.height).data;
    var w = cv.width, h = cv.height;
    var x0 = w, x1 = -1, y0 = h, y1 = -1;
    for (var y = 0; y < h; y++) {
      var row = y * w * 4;
      for (var x = 0; x < w; x++) {
        if (d[row + x * 4 + 3] > 16) {
          if (x < x0) x0 = x;
          if (x > x1) x1 = x;
          if (y < y0) y0 = y;
          if (y > y1) y1 = y;
        }
      }
    }
    return x1 < 0 ? null : { x0: x0, y0: y0, x1: x1, y1: y1 };
  }

  /** 圖片像素外接框 → 看板座標（依 drawn 的縮放比換算） */
  function toBoardRect(drawn, img, bb) {
    var k = drawn.w / img.naturalWidth;
    return {
      x: drawn.x + bb.x0 * k,
      y: drawn.y + bb.y0 * k,
      w: (bb.x1 - bb.x0 + 1) * k,
      h: (bb.y1 - bb.y0 + 1) * k
    };
  }

  /** 用真的字型量一行文字的墨跡寬度（回傳 U.text 算出來的值） */
  function textWidth(sc, str, size, weight, family, spacing) {
    return NT.Utils.text(sc, str, {
      x: -1e5, y: 0, size: size, weight: weight, family: family,
      spacing: spacing || 0
    });
  }

  /** 得票數是「大字數字 + 小字萬/票」的富文字，寬度要用同一支量 */
  function votesWidth(sc, c, conf) {
    var parts = NT.Utils.voteParts(c.votes);
    var segs = parts.map(function (p) {
      return {
        text: p.text,
        size: p.num ? conf.size : (conf.cjkSize || conf.size * 0.55),
        weight: p.num ? 900 : 700
      };
    });
    return NT.Utils.richText(sc, segs, { x: -1e5, y: 0, align: 'left' });
  }

  global.__layoutReport = function () {
    return build().then(function (slide) {
      var L = NT.Layout, A = slide.assets, m = slide.model;
      var sc = document.createElement('canvas').getContext('2d');

      var out = {
        board: slide.name || null,
        canvas: { w: L.W, h: L.H },
        map: null,
        legend: null,
        elements: { cards: [] }
      };

      /* 地圖：框 + 實際落點 + 墨跡外接框（台北的直式地圖四周留白很多，
         只看「落點矩形」會誤判，一定要用 alpha 墨跡框才算得準） */
      var imgMap = A.voteMap;
      if (imgMap && A.mapRect) {
        var bb = alphaBBox(imgMap);
        out.map = {
          frame: { x: L.map.x, y: L.map.y, w: L.map.w, h: L.map.h },
          drawn: { x: A.mapRect.x, y: A.mapRect.y, w: A.mapRect.w, h: A.mapRect.h },
          content: bb ? toBoardRect(A.mapRect, imgMap, bb) : null
        };
      }

      /* 圖例：contain 框與實際圖片矩形（由 LegendLayer 記下）。
         ★ 沒有底板了：實際被畫到的只有 image，box 只是「這一欄是圖例區」的範圍，
           驗證腳本用 image 比對相交、用 box 確認還在畫布內。 */
      if (A.legendRect) {
        out.legend = { box: A.legendRect.box, image: A.legendRect.image };
      }

      /* 其餘元素：頁眉、底部票數帶、小卡 */
      out.elements.header = { x: 0, y: 0, w: L.W, h: L.header.h };
      out.elements.ribbon = { x: 0, y: L.ribbon.y, w: L.W, h: L.ribbon.h };
      var mn = L.minor;
      out.elements.minor = { x: mn.cx - mn.w / 2, y: mn.y, w: mn.w, h: mn.h };

      /* 左右主卡：逐塊拆開輸出，不給外接框（理由見檔頭 ★）。
         文字寬度一律用真的字型量，不用「大概幾個字」估，
         否則驗證會變成另一種目測。 */
      ['left', 'right'].forEach(function (side) {
        var c = side === 'left' ? m.left : m.right;
        var conf = L[side];
        if (!c || !conf) return;

        function add(what, rect) {
          out.elements.cards.push({ name: side + '/' + what, rect: rect });
        }

        var ph = conf.card;
        add('card', { x: conf.cx - ph.w / 2, y: ph.y, w: ph.w, h: ph.h });

        var cp = conf.chip;
        add('chip', { x: conf.cx - cp.w / 2, y: cp.y, w: cp.w, h: cp.h });

        var nm = conf.name;
        var nameW = textWidth(sc, c.name, nm.size, 900, null, nm.spacing || 0);
        var markSize = c.elected ? nm.size * (nm.markRatio || 0.9) : 0;
        var gap = c.elected ? (nm.markGap || 30) : 0;
        var groupW = nameW + markSize + gap;
        add('name', {
          x: conf.cx - groupW / 2, y: nm.y - nm.size,
          w: groupW, h: nm.size * 1.25
        });

        var pctW = textWidth(sc, c.pctText() + '%', conf.pct.size, 900, NT.FONT_NUM, 0);
        add('pct', {
          x: conf.cx - pctW / 2, y: conf.pct.y - conf.pct.size,
          w: pctW, h: conf.pct.size * 1.3
        });

        var vW = votesWidth(sc, c, conf.votes);
        add('votes', {
          x: conf.cx - vW / 2, y: conf.votes.y - conf.votes.size,
          w: vW, h: conf.votes.size * 1.3
        });
      });

      return out;
    });
  };

})(window);
