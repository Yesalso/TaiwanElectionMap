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
          /* 上傳失敗自動重試：全量批次時偶發 /__save 500（寫檔被防毒／
             檔案鎖擋一下），重試 2 次即可，不必讓整批失敗。 */
          var tries = 0;
          function attempt() {
            tries++;
            fetch('/__save?name=' + encodeURIComponent(name),
                  { method: 'POST', body: blob })
              .then(function (r) {
                if (!r.ok) throw new Error('/__save HTTP ' + r.status);
                return r.json();
              })
              .then(resolve)
              .catch(function (e) {
                if (tries < 3) {
                  console.log('[headless] 保存失敗（' + e.message +
                    '），第 ' + (tries + 1) + ' 次重試…');
                  setTimeout(attempt, 400);
                } else {
                  reject(e);
                }
              });
          }
          attempt();
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

     回傳：{board, canvas, map:{frame,drawn,content,profile},
            map2:{frame,drawn,content,profile}(可無), legend:{box,image},
            elements:{header,ribbon,minor,minorCards, cards:[{name,rect}…]}}

     ★ 主卡為什麼拆成一串子矩形（cards），而不是給一顆外接框：
       主卡是「照片 274–894、標籤 910–986、姓名 1096、得票率 1282、得票數 1386」
       疊起來的一整條。只給外接框會得到 274–1403 × 1967–2533 的大框，
       圖例（1600–2008 × 453–973）跟它一比就「相交」——但那個相交區其實整片是空的
       （照片卡從 2024 才起、得票率那行在 y 1170 以下）。
       初版就是這樣誤判的，所以這裡逐塊輸出、驗證腳本逐塊比。
     ===================================================================== */

  /** 掃描圖片實際墨跡（alpha > 16）：外接框 + **分段左右界**。
      ★ 為什麼要分段：地圖是「置中的直式圖」，墨跡下半部其實很窄
        （2022 台北市 y1100 以下只剩 x≈1009–1280），只比外接框
        （x 675–1465）會把「卡片明明在空白處」誤判成壓到地圖 ——
        往上長的第 3 名高卡與「其他候選人」清單都靠這條才驗得準。
      回傳 { bb, bands }：bands 為 INK_BANDS 個等高的橫帶，
      每帶記自己的墨跡外接框（座標是「圖片自身像素」；空帶不列入）。 */
  var INK_BANDS = 48;
  function alphaScan(img) {
    var cv = document.createElement('canvas');
    cv.width = img.naturalWidth;
    cv.height = img.naturalHeight;
    var c2 = cv.getContext('2d');
    c2.drawImage(img, 0, 0);
    var d = c2.getImageData(0, 0, cv.width, cv.height).data;
    var w = cv.width, h = cv.height;
    var x0 = w, x1 = -1, y0 = h, y1 = -1;
    var bands = [], i;
    for (i = 0; i < INK_BANDS; i++) {
      bands.push({ x0: w, y0: h, x1: -1, y1: -1 });
    }
    for (var y = 0; y < h; y++) {
      var row = y * w * 4;
      var b = bands[Math.min(INK_BANDS - 1, Math.floor(y * INK_BANDS / h))];
      for (var x = 0; x < w; x++) {
        if (d[row + x * 4 + 3] > 16) {
          if (x < x0) x0 = x;
          if (x > x1) x1 = x;
          if (y < y0) y0 = y;
          if (y > y1) y1 = y;
          if (x < b.x0) b.x0 = x;
          if (x > b.x1) b.x1 = x;
          if (y < b.y0) b.y0 = y;
          if (y > b.y1) b.y1 = y;
        }
      }
    }
    if (x1 < 0) return null;
    var out = [];
    for (i = 0; i < INK_BANDS; i++) {
      if (bands[i].x1 >= 0) out.push(bands[i]);
    }
    return { bb: { x0: x0, y0: y0, x1: x1, y1: y1 }, bands: out };
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
        /* 區級圖（第二張圖）的落點，只有「圖例關掉」的場次才有值 */
        map2: null,
        legend: null,
        elements: { cards: [] }
      };

      /* 地圖：框 + 實際落點 + 墨跡外接框（台北的直式地圖四周留白很多，
         只看「落點矩形」會誤判，一定要用 alpha 墨跡框才算得準） */
      var imgMap = A.voteMap;
      if (imgMap && A.mapRect) {
        var scan = alphaScan(imgMap);
        out.map = {
          frame: { x: L.map.x, y: L.map.y, w: L.map.w, h: L.map.h },
          drawn: { x: A.mapRect.x, y: A.mapRect.y, w: A.mapRect.w, h: A.mapRect.h },
          content: scan ? toBoardRect(A.mapRect, imgMap, scan.bb) : null,
          /* 分段墨跡（看板座標）：驗證腳本用「卡片 × 重疊到的那幾段」比對，
             而不是拿整張地圖的外接框 —— 見 alphaScan 的說明。 */
          profile: scan ? scan.bands.map(function (b) {
            return toBoardRect(A.mapRect, imgMap, b);
          }) : []
        };
      }

      /* 圖例：contain 框與實際圖片矩形（由 LegendLayer 記下）。
         ★ 沒有底板了：實際被畫到的只有 image，box 只是「這一欄是圖例區」的範圍，
           驗證腳本用 image 比對相交、用 box 確認還在畫布內。 */
      if (A.legendRect && !(L.legend && L.legend.disabled)) {
        out.legend = {
          box: A.legendRect.box,
          image: A.legendRect.image,
          /* 圖例擺在頁眉帶裡（全國看板）→ verify_layout 的 L3 不對頁眉判定 */
          inHeader: !!(L.legend && L.legend.allowInHeader)
        };
      }
      if (L.legend && L.legend.disabled) out.legendDisabled = true;

      /* 區級圖（第二張圖，Layout.map2）：只有「圖例關掉」的場次會畫
         （Map2Layer 把落點記在 assets.map2Rect）。欄位與 map 完全對稱，
         驗證腳本可以用同一套（content 外接框 + profile 分段墨跡）比對。 */
      var imgM2 = A.map2;   /* Slide.load 存在 assets.map2（_loadMap2） */
      if (imgM2 && A.map2Rect && L.map2) {
        var scan2 = alphaScan(imgM2);
        out.map2 = {
          frame: { x: L.map2.x, y: L.map2.y, w: L.map2.w, h: L.map2.h },
          drawn: { x: A.map2Rect.x, y: A.map2Rect.y,
                   w: A.map2Rect.w, h: A.map2Rect.h },
          content: scan2 ? toBoardRect(A.map2Rect, imgM2, scan2.bb) : null,
          profile: scan2 ? scan2.bands.map(function (b) {
            return toBoardRect(A.map2Rect, imgM2, b);
          }) : []
        };
      }

      /* 其餘元素：頁眉、底部票數帶、小卡（第 3 名高卡 + 底部橫排的聯集；
         沒有小黨候選人時整條不算障礙物） */
      out.elements.header = { x: 0, y: 0, w: L.W, h: L.header.h };
      out.elements.ribbon = L.ribbon.disabled ? null
        : { x: 0, y: L.ribbon.y, w: L.W, h: L.ribbon.h };
      if ((m.minors || []).length) {
        /* 底部帶：x0..x1 是「小卡可以出現的範圍」（保守外框，L6 用）。
           ★ 第 3 名高卡與「其他候選人」清單格都比左群高（layout.js big.h /
             others.h，後者上限＝前者），它們的上緣會高於 mm.y，
             所以這條帶的高度要「往上吃掉」多出來的那一段，
             否則 L8（每張卡都要落在帶內）會誤判越界。
           實際每張卡的矩形由 MinorCandidateLayer 記在 assets.minorCards，
           卡寬＝內容自然寬、彼此只留 gap（L7 不相交、L8 都在帶內、L9 不壓地圖）。 */
        var mm = L.minors;
        var bigH = Math.max((mm.big && mm.big.h) || 0,
                            (mm.others && mm.others.h) || 0);
        var top = Math.min(mm.y, mm.y + mm.h - bigH);
        out.elements.minor = { x: mm.x0, y: top, w: mm.x1 - mm.x0,
                               h: (mm.y + mm.h) - top };
        if (A.minorCards && A.minorCards.length) {
          out.elements.minorCards = A.minorCards;
        }
      }

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
        /* 與 CandidateLayer 完全同步：主卡大字＝c.leader（黨主席）優先；
           有 c.seats 時姓名左邊多一塊席次牌，姓名可用寬度要扣掉它。 */
        var dispName = c.leader || c.name;
        var pW = 0, pGap = 0;
        if (c.seats !== null && c.seats !== undefined) {
          var pH = Math.round(nm.size * 0.86);
          pW = Math.round(pH * 1.34);   /* 與 CandidateLayer 同步（去掉「✓」後的牌匾尺寸） */
          pGap = Math.round(nm.size * 0.22);
        }
        var maxNameW = Math.min(nm.maxW || 492, conf.card.w) - (pW ? pW + pGap : 0);
        var sp = nm.spacing || 0;
        sc.font = NT.Utils.font(nm.size, 900);
        var naturalW = NT.Utils.measureSpaced(sc, dispName, sp);
        var nameScale = naturalW <= maxNameW ? 1 : Math.max(0.4, maxNameW / naturalW);
        var nameSize = nm.size * nameScale;
        var nameSpacing = sp * nameScale;
        sc.font = NT.Utils.font(nameSize, 900);
        var nameStr = dispName;
        var nameW = NT.Utils.measureSpaced(sc, nameStr, nameSpacing);
        if (nameW > maxNameW) {
          nameStr = NT.Utils.fitText(sc, nameStr, maxNameW, nameSpacing);
          nameW = NT.Utils.measureSpaced(sc, nameStr, nameSpacing);
        }
        var markSize = c.elected ? nm.size * (nm.markRatio || 0.9) : 0;
        var gap = c.elected ? (nm.markGap || 30) : 0;
        var groupW = pW + (pW ? pGap : 0) + nameW + markSize + gap;
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
