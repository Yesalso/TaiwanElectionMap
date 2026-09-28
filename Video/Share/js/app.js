/* ==========================================================================
   app.js — 應用控制器
   --------------------------------------------------------------------------
   負責：建立模型 / 看板、渲染到主畫布、縮放與符合視窗、工具列、快捷鍵、
   以及左側投影片清單（架構上支援多年份，目前只放 2014）。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;
  var L = NT.Layout;

  function App() {
    this.canvas = document.getElementById('slideCanvas');
    this.stage = document.getElementById('stage');
    this.scaler = document.getElementById('stageScaler');
    this.slides = [];
    this.activeIndex = 0;
    this.zoom = 1;
    this._bindUi();
  }

  /* ------------------------------ 啟動 ------------------------------ */
  App.prototype.boot = function () {
    var self = this;
    try {
      var raw = global.ELECTION_2014;
      if (!raw) throw new Error('找不到 ELECTION_2014 資料，請確認 data/election-2014.js 是否存在。');

      var model = new NT.ElectionModel(raw);
      /* 架構上 slides 是「多張看板」的清單，目前僅放入 2014 這張 */
      this.slides = [new NT.Slide(model, {
        name: '第二屆新北市長選舉',
        year: 2014,
        subtitle: '2014 年直轄市長選舉'
      })];

      return this.slides[0].load().then(function () {
        self.render();
        self.buildRail();
        self.fit();
        self.setStatus('就緒', model.summary());
        self.syncMap();          // 讓工具列的地圖滑桿反映 Layout.map.scale
        document.getElementById('hintText').textContent =
          model.districtTally.kmt + ' : ' + model.districtTally.dpp +
          ' 個行政區 · 差距 ' + U.voteWan(model.marginVotes) + ' 票';
        document.getElementById('railMeta').textContent =
          '共 ' + self.slides.length + ' 張 · 每張 ' + L.W + ' × ' + L.H + ' px';
      });
    } catch (err) {
      this.setStatus('載入失敗', err.message);
      document.getElementById('hintText').textContent = err.message;
      console.error(err);
      return Promise.reject(err);
    }
  };

  /* ------------------------------ 渲染 ------------------------------ */
  App.prototype.render = function () {
    var slide = this.cur();
    if (!slide) return;
    this.canvas.width = L.W;
    this.canvas.height = L.H;
    var ctx = this.canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    slide.render(ctx, 1);
  };

  App.prototype.cur = function () {
    return this.slides[this.activeIndex];
  };

  /* ------------------------------ 縮放 ------------------------------ */
  App.prototype.setZoom = function (k, silent) {
    this.zoom = k;
    this.scaler.style.width = (L.W * k) + 'px';
    this.scaler.style.height = (L.H * k) + 'px';
    this.canvas.style.transform = 'scale(' + k + ')';
    if (!silent) {
      document.getElementById('zoomRange').value =
        Math.round(U.clamp(k, 0.1, 1) * 100);
    }
    document.getElementById('zoomValue').textContent = Math.round(k * 100) + '%';
  };

  App.prototype.fit = function () {
    var pad = 44;
    var k = Math.min(
      (this.stage.clientWidth - pad) / L.W,
      (this.stage.clientHeight - pad) / L.H
    );
    k = Math.min(k, 1.6);
    this.setZoom(Math.max(0.05, k));
  };

  /* ------------------------------ 地圖比例 ------------------------------ */
  /**
   * 縮小／放大看板上的地圖：直接改 Layout.map.scale（1 = 撐滿框）後重繪。
   * 用 requestAnimationFrame 節流，拖動滑桿時不會每個 input 事件都重畫一次。
   */
  App.prototype.setMapScale = function (k) {
    L.map.scale = k;
    document.getElementById('mapValue').textContent = Math.round(k * 100) + '%';
    if (this._mapRaf) return;
    var self = this;
    this._mapRaf = requestAnimationFrame(function () {
      self._mapRaf = 0;
      self.render();
      var r = self.cur().assets.mapRect;
      if (r) {
        self.setStatus('地圖 ' + Math.round(k * 100) + '%',
          '實際繪製 ' + Math.round(r.w) + ' × ' + Math.round(r.h) + ' px');
      }
    });
  };

  /** 把 Layout.map.scale 的現值同步到滑桿與標籤 */
  App.prototype.syncMap = function () {
    var slide = this.cur();
    var k = L.map.scale === undefined ? 1 : L.map.scale;
    var range = document.getElementById('mapRange');
    var pct = Math.round(U.clamp(k, Number(range.min) / 100, Number(range.max) / 100) * 100);
    range.value = pct;
    document.getElementById('mapValue').textContent = pct + '%';
    var src = (L.map.src || '（無）');
    var actual = ({ file: src, embedded: 'data/local-assets.js 內嵌版', none: '無' }[
      slide.assets.mapSource] || slide.assets.mapSource);
    range.title = '地圖來源：' + src + '　·　實際使用：' + actual +
      '　·　' + slide.mapHint();
    /* 狀態列平常留給選舉結果摘要；只有素材有問題（讀不到、沒預處理）才跳出來 */
    var issue = slide.mapIssue();
    if (issue) this.setStatus('地圖素材需要處理', issue);
  };

  /* ------------------------------ 左側清單 ------------------------------ */
  App.prototype.buildRail = function () {
    var list = document.getElementById('slideList');
    list.innerHTML = '';
    var self = this;

    this.slides.forEach(function (slide, i) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'thumb' + (i === self.activeIndex ? ' is-active' : '');

      var frame = document.createElement('div');
      frame.className = 'thumb__frame';
      var img = document.createElement('img');
      img.className = 'thumb__cv';
      img.alt = slide.name + ' 縮圖';
      img.src = slide.thumbnail(240);
      frame.appendChild(img);

      var meta = document.createElement('div');
      meta.className = 'thumb__meta';
      var nm = document.createElement('span');
      nm.className = 'thumb__name';
      nm.textContent = slide.name;
      var yr = document.createElement('span');
      yr.className = 'thumb__year';
      yr.textContent = slide.year;
      meta.appendChild(nm);
      meta.appendChild(yr);

      btn.appendChild(frame);
      btn.appendChild(meta);
      btn.addEventListener('click', function () { self.select(i); });
      list.appendChild(btn);
    });
  };

  App.prototype.select = function (i) {
    this.activeIndex = i;
    this.render();
    var items = document.querySelectorAll('.thumb');
    for (var k = 0; k < items.length; k++) {
      items[k].classList.toggle('is-active', k === i);
    }
    this.setStatus('已切換看板', this.cur().name);
  };

  /* ------------------------------ 狀態列 ------------------------------ */
  App.prototype.setStatus = function (left, right) {
    if (left) document.getElementById('statusLeft').textContent = left;
    if (right) document.getElementById('statusRight').textContent = right;
  };

  /* ------------------------------ 事件 ------------------------------ */
  App.prototype._bindUi = function () {
    var self = this;

    document.getElementById('btnFit').addEventListener('click', function () {
      self.fit();
    });
    document.getElementById('btnActual').addEventListener('click', function () {
      self.setZoom(1);
      self.stage.scrollTo(0, 0);
    });
    document.getElementById('zoomRange').addEventListener('input', function (e) {
      self.setZoom(Number(e.target.value) / 100, true);
    });
    document.getElementById('mapRange').addEventListener('input', function (e) {
      self.setMapScale(Number(e.target.value) / 100);
    });

    document.getElementById('btnPng').addEventListener('click', function () {
      self.export(1);
    });
    document.getElementById('btnPng2x').addEventListener('click', function () {
      self.export(2);
    });

    /* 視窗尺寸改變時重新符合 */
    window.addEventListener('resize', function () {
      if (self._fitLock) self.fit();
    });
    self._fitLock = true;

    /* 快捷鍵：F 符合視窗、1 100%、Ctrl/Cmd+S 匯出 */
    window.addEventListener('keydown', function (e) {
      if (e.ctrlKey || e.metaKey) {
        if (e.key.toLowerCase() === 's') {
          e.preventDefault();
          self.export(1);
        }
        return;
      }
      if (e.key === 'f' || e.key === 'F') self.fit();
      if (e.key === '1') self.setZoom(1);
    });
  };

  /* ------------------------------ 匯出 ------------------------------ */
  App.prototype.export = function (scale) {
    var self = this;
    var btn = document.getElementById(scale === 2 ? 'btnPng2x' : 'btnPng');
    btn.disabled = true;
    this.setStatus('匯出中…', '正在產生 ' + (L.W * scale) + ' × ' + (L.H * scale) + ' PNG');

    /* 讓瀏覽器先把「匯出中」畫出來，再開始同步的繪製工作 */
    setTimeout(function () {
      var base = self.cur().year + self.cur().name;
      NT.Exporter.download(self.cur(), scale, base).then(function (r) {
        self.setStatus('匯出完成', r.filename + '（' + Math.round(r.bytes / 1024) + ' KB）');
      }).catch(function (err) {
        console.error(err);
        self.setStatus('匯出失敗', err.message);
      }).then(function () {
        btn.disabled = false;
      });
    }, 30);
  };

  /* ------------------------------ 啟動 ------------------------------ */
  function start() {
    var app = new App();
    global.__app = app;   // 方便在 console 偵錯
    app.boot().catch(function (err) {
      /* 一定要把錯誤講出來。boot() 裡的 try/catch 只擋得住同步例外；圖片載入、
         縮圖這種非同步失敗會直接落到這裡。默默吞掉的話，畫面只會停在初始文字
         （狀態列「就緒」、提示「載入中…」、滑桿「—」），完全看不出發生什麼事。 */
      app.setStatus('啟動失敗', (err && err.message) || String(err));
      console.error('[App] 啟動失敗', err);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  NT.App = App;

})(window);
