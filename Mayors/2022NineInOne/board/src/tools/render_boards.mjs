#!/usr/bin/env node
/**
 * render_boards.mjs —— 零依赖无头渲染器（Node 内建 WebSocket + fetch + CDP）
 * ---------------------------------------------------------------------------
 * 一次启动 Edge，循环渲染**多场**看板 → 写 PNG 落盘 → 记 SHA256 到 manifest.json。
 *
 * 用法：
 *   node src/tools/render_boards.mjs --all                 # 默认 1.5×＝3840×2160
 *   node src/tools/render_boards.mjs --boards 2022-taipei --scale 1
 *   node src/tools/render_boards.mjs --all --scales 1.5,2 --out ../out
 *
 * 产物分三个出口，互不混放：
 *   PNG        → dist/dist_png/2022/<县市>.png     （22 张全在同一个年份文件夹）
 *   layout.json→ dist/boards/<id>/layout.json    （报告，跟看板产物放一起）
 *   manifest   → dist/manifest.json              （清单，增量合并）
 *
 * 参数：
 *   --boards <name...>   指定场次目录名（可多个，相对 boards/）
 *   --all                渲染 boards/ 下所有含 meta.json 的场次
 *   --scale <n>          单一倍率（等价 --scales n）；默认 1.5
 *   --scales <1.5,2>     多倍率（逗号分隔）
 *   --out <dir>          PNG 输出目录，默认 dist/dist_png。
 *                        **按年份分文件夹、县市名做文件名、只有 PNG**：
 *                        <out>/<meta.year>/<meta.county>.png。
 *                        例：2022/臺北市.png … 2022/連江縣.png。
 *                        多倍率时首个倍率不带后缀、其余加 _<n>x。
 *                        不跟 board.js / index.html 混放。
 *   --manifest <file>    渲染清单落点，默认固定 Video/dist/manifest.json
 *                        （不随 --out 漂移）。清单不是图片，永不进 dist_png。
 *   --layout-root <dir>  版面报告（layout.json）落点，默认 Video/dist/boards，
 *                        写到 <dir>/<id>/layout.json（跟看板产物放一起，
 *                        供 verify_layout.py 扫描）。
 *   --boards-root <dir>  覆盖 boards/ 根目录
 *   --root <dir>         静态服务器根目录，默认 Video/。
 *                        必须是 Video/ 而不是 boards/ —— 透明化成品集中在
 *                        dist/assets/，看板的 board.files.js
 *                        用 ../../src/mapgen/... 引它，根设在 boards/ 会 404。
 *                        场次目录若含 .skip 标记文件，--all 会跳过它。
 *   --report             额外导出每场的版面报告（<layout-root>/<id>/layout.json），
 *                        给 tools/verify_layout.py 验「图例不得压到地图／其他元素」。
 *                        默认开启（渲染后顺手量一次，成本约 0.1 s）；--no-report 关闭。
 *   --keep-open          渲染完不关 Edge（调试用）
 *   --no-merge           清单整份重写（默认是增量合并：只渲几场就只替换那几笔，
 *                        不会把 dist/manifest.json 压成只剩本次的场次）
 *
 * 退出码：0 = 全部成功；1 = 有任一场/倍率失败。
 */

import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import {
  readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync,
} from 'node:fs';
import { resolve, join, extname, dirname, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VIDEO_ROOT = resolve(__dirname, '..', '..');   // 本檔在 src/tools/
const DIST_ROOT = join(VIDEO_ROOT, 'dist');

const BASE_W = 2560;
const BASE_H = 1440;

/**
 * 默认倍率 1.5 —— 版面坐标仍是 2560×1440（Layout 不动），画布与绘制变换乘 1.5，
 * 出图 3840×2160（4K）。因为是同一套矢量/位图绘制再整体放大，1.5× 与 1× 的构图
 * 逐坐标同构，只多出像素密度。要别的尺寸用 --scale 覆盖。
 */
const DEFAULT_SCALE = 1.5;

/**
 * 年份 + 县市（取自 meta.json）→ 图片落点。
 *
 * ★ 2022 九合一县市长：**所有 22 张同一个年份文件夹**，文件名用县市全称：
 *     dist/dist_png/2022/臺北市.png
 *     dist/dist_png/2022/新北市.png …
 *   年份取 meta.meta.year、文件名取 meta.meta.county（建置器已写在 meta.json），
 *   不靠 id 猜。多倍率时首个倍率不带后缀，其余加 `_<n>x`（`臺北市_2x.png`）。
 *
 * ★ 文件名消毒必须**写入与读回用同一支**（safeRelPath）：/__save 端点是
 *   「页面 POST 名字 → Node 消毒后写档」，主流程再按名字 readFileSync 读回来。
 *   两边只要有一边消毒规则不同，名字就对不上（旧版 `@2x` 就是在这里炸的）。
 *   县市名是汉字，所以消毒白名单要放行 Han，不能一律打成下划线。
 */
function pngNameOf(year, county, scale, primary) {
  const stem = primary ? String(county) : `${county}_${scale}x`;
  return `${year}/${stem}.png`;
}

/** 单段路径消毒：保留汉字 / 字母数字 / . _ -，其余换成 _ */
function sanitizeSeg(s) {
  return String(s).replace(/[^\p{Script=Han}A-Za-z0-9._-]/gu, '_');
}

/** 相对路径消毒（逐段），拒绝 . 与 .. 穿越；写入与读回都走这一支 */
function safeRelPath(raw) {
  const segs = String(raw || '').split('/').map(sanitizeSeg)
    .filter((s) => s && s !== '.' && s !== '..');
  return segs.join('/') || 'out.png';
}

/**
 * 递归列出 dir 下所有非 .png 的文件（相对 dir）。
 * 用来守着「dist_png 里只有 png」这条契约 —— 每场一个子目录，所以要往里走。
 */
function listNonPng(dir, base = dir) {
  const out = [];
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, ent.name);
    if (ent.isDirectory()) out.push(...listNonPng(p, base));
    else if (!ent.name.toLowerCase().endsWith('.png')) out.push(relative(base, p));
  }
  return out;
}

// ---------------------------------------------------------------- args
function parseArgs(argv) {
  const opts = {
    boards: [], all: false, scales: [],
    out: join(DIST_ROOT, 'dist_png'),          // 图片唯一出口：dist/dist_png（只有 png）
    manifest: join(DIST_ROOT, 'manifest.json'), // 清单不进 dist_png
    layoutRoot: join(DIST_ROOT, 'boards'),      // layout.json 跟看板产物放一起
    boardsRoot: join(VIDEO_ROOT, 'src', 'boards'), root: VIDEO_ROOT,
    keepOpen: false, report: true, merge: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--boards' || a === '--board') {
      while (argv[i + 1] && !argv[i + 1].startsWith('--')) opts.boards.push(argv[++i]);
    } else if (a === '--all') opts.all = true;
    else if (a === '--scale') opts.scales.push(parseInt(argv[++i], 10));
    else if (a === '--scales') opts.scales.push(...String(argv[++i]).split(',').map(Number));
    else if (a === '--out') opts.out = resolve(argv[++i]);
    else if (a === '--manifest') opts.manifest = resolve(argv[++i]);
    else if (a === '--layout-root') opts.layoutRoot = resolve(argv[++i]);
    else if (a === '--boards-root') opts.boardsRoot = resolve(argv[++i]);
    else if (a === '--root') opts.root = resolve(argv[++i]);
    else if (a === '--report') opts.report = true;
    else if (a === '--no-report') opts.report = false;
    else if (a === '--no-merge') opts.merge = false;
    else if (a === '--keep-open') opts.keepOpen = true;
    else throw new Error('未知参数：' + a);
  }
  if (!opts.scales.length) opts.scales = [DEFAULT_SCALE];
  opts.scales = [...new Set(opts.scales)].filter((n) => Number.isFinite(n) && n > 0);
  if (!opts.scales.length) throw new Error('--scales 没给有效倍率');
  return opts;
}

/**
 * 列出要渲染的场次。
 *
 * 目录里有 `.skip` 文件就整个跳过 —— 用来把「暂时不生成」的场次留在仓库里
 * 但不进批次（例如只做台北、不做新北）。比直接删掉目录安全，也比在
 * meta.json 塞一个引擎看不懂的旗标干净。`.skip` 里可以写原因，仅作说明。
 */
function listBoards(root) {
  const skipped = [];
  const list = readdirSync(root)
    .filter((n) => {
      const d = join(root, n);
      if (!statSync(d).isDirectory() || n.startsWith('_') || n.startsWith('.')) return false;
      if (!existsSync(join(d, 'meta.json'))) return false;
      if (existsSync(join(d, '.skip'))) { skipped.push(n); return false; }
      return true;
    })
    .sort();
  if (skipped.length) console.log(`[跳过] .skip 标记：${skipped.join('、')}`);
  return list;
}

// ---------------------------------------------------------------- edge
function findEdge() {
  const candidates = [
    process.env.EDGE_PATH,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    'msedge',
  ].filter(Boolean);
  for (const p of candidates) {
    if (p === 'msedge' || existsSync(p)) return p;
  }
  throw new Error('找不到 Edge，可设环境变量 EDGE_PATH 指定路径');
}

function launchEdge(port, userDataDir) {
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--force-color-profile=srgb',
    '--font-render-hinting=none',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ];
  const proc = spawn(findEdge(), args, { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
  proc.stderr.on('data', (d) => {
    const s = d.toString();
    if (/ERROR|FATAL/.test(s)) console.error('[Edge]', s.trim());
  });
  proc.on('error', (e) => { throw e; });
  return proc;
}

/** Edge 會開一票子行程，只 kill 啟動器會留下孤兒；整個行程樹一起收掉 */
function killTree(proc) {
  if (!proc || proc.killed) return;
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], { stdio: 'ignore', windowsHide: true });
    } else {
      proc.kill('SIGKILL');
    }
  } catch { try { proc.kill(); } catch { /* ignore */ } }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchBrowserWs(port) {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      const data = await res.json();
      if (data.webSocketDebuggerUrl) return { browserWs: data.webSocketDebuggerUrl, version: data.Browser };
    } catch { /* 还没起来 */ }
    await sleep(250);
  }
  throw new Error('无法连接 Edge CDP（/json/version 一直不可用）');
}

async function fetchPageWs(port) {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const list = await res.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* retry */ }
    await sleep(250);
  }
  throw new Error('找不到可用的 page target（/json/list）');
}

// ---------------------------------------------------------------- cdp
class CDP {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener('message', (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (process.env.CDP_DEBUG) {
        console.log('[cdp←]', m.id !== undefined ? ('#' + m.id) : m.method,
          JSON.stringify(m.result !== undefined ? m.result : (m.error || m.params || {})).slice(0, 160));
      }
      if (m.id !== undefined && this.pending.has(m.id)) {
        const { resolve: res, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        if (m.error) reject(new Error(m.error.message));
        else res(m.result);
      } else if (m.method) {
        (this.listeners.get(m.method) || []).forEach((fn) => fn(m.params));
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.seq;
    return new Promise((res, reject) => {
      this.pending.set(id, { resolve: res, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(fn);
  }

  once(method, timeoutMs, what) {
    return new Promise((res, reject) => {
      const timer = setTimeout(() => reject(new Error((what || method) + ' 超时')), timeoutMs);
      const fn = (p) => {
        clearTimeout(timer);
        const arr = this.listeners.get(method) || [];
        const i = arr.indexOf(fn);
        if (i >= 0) arr.splice(i, 1);
        res(p);
      };
      this.on(method, fn);
    });
  }

  async evaluate(expression, timeoutMs) {
    const r = await Promise.race([
      this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('Runtime.evaluate 超时')), timeoutMs)),
    ]);
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error('页面异常：' + (d.exception?.description || d.text));
    }
    return r.result?.value;
  }
}

// ---------------------------------------------------------------- http
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
};

function serveStatic(root, outDir) {
  return new Promise((res) => {
    const server = createServer((req, resp) => {
      const parsed = new URL(req.url || '/', 'http://127.0.0.1');
      let urlPath = decodeURIComponent(parsed.pathname);
      if (urlPath.endsWith('/')) urlPath += 'index.html';

      /* 頁面把渲染好的 PNG POST 回來由 Node 寫檔。
         繞過 CDP 單一訊息大小上限（5.6 MB 的 base64 會被丟掉）。 */
      if (req.method === 'POST' && urlPath === '/__save') {
        const raw = parsed.searchParams.get('name') || 'out.png';
        /* 允许子目录（年份/县市.png），逐段消毒、拒绝 . 与 .. 穿越。
           ★ 与主流程读回用的是同一支 safeRelPath，两边名字必须一致。 */
        const name = safeRelPath(raw);
        const dest = join(outDir, name);
        if (!resolve(dest).startsWith(resolve(outDir))) {
          resp.writeHead(403); resp.end('forbidden'); return;
        }
        mkdirSync(dirname(dest), { recursive: true });
        const chunks = [];
        req.on('data', (c) => chunks.push(c));
        req.on('end', () => {
          try {
            const buf = Buffer.concat(chunks);
            writeFileSync(dest, buf);
            resp.writeHead(200, { 'Content-Type': 'application/json' });
            resp.end(JSON.stringify({ ok: true, bytes: buf.length, file: dest }));
          } catch (e) {
            resp.writeHead(500, { 'Content-Type': 'application/json' });
            resp.end(JSON.stringify({ ok: false, error: String(e.message || e) }));
          }
        });
        return;
      }

      const filePath = join(root, urlPath);
      // 防目录穿越：必须仍在 root 之下
      if (!resolve(filePath).startsWith(resolve(root))) {
        resp.writeHead(403); resp.end('forbidden'); return;
      }
      try {
        const body = readFileSync(filePath);
        resp.writeHead(200, { 'Content-Type': MIME[extname(filePath).toLowerCase()] || 'application/octet-stream' });
        resp.end(body);
      } catch {
        resp.writeHead(404); resp.end('not found: ' + urlPath);
      }
    });
    server.listen(0, '127.0.0.1', () => res(server));
  });
}

// ---------------------------------------------------------------- main
async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const boardsRoot = opts.boardsRoot;
  const boardNames = opts.all ? listBoards(boardsRoot) : opts.boards;
  if (!boardNames.length) throw new Error('没有要渲染的场次（用 --all 或 --boards <name...>）');
  for (const n of boardNames) {
    if (!existsSync(join(boardsRoot, n, 'meta.json'))) throw new Error('场次不存在或缺 meta.json：' + n);
  }
  mkdirSync(opts.out, { recursive: true });

  console.log(`[渲染] 场次 ${boardNames.length} 场 × 倍率 ${opts.scales.join(',')} → ${opts.out}`);

  /* 根目录是 Video/（不是 boards/）：看板的素材在 dist/assets/ */
  const httpServer = await serveStatic(opts.root, opts.out);
  const httpPort = httpServer.address().port;

  const cdpPort = await (async () => {
    const s = createServer(); await new Promise((r) => s.listen(0, '127.0.0.1', r));
    const p = s.address().port; await new Promise((r) => s.close(r)); return p;
  })();

  const userDataDir = join(process.env.TEMP || process.env.TMP || '/tmp', `edge_render_${Date.now()}`);
  mkdirSync(userDataDir, { recursive: true });

  const edgeProc = launchEdge(cdpPort, userDataDir);
  const cleanup = () => killTree(edgeProc);
  process.on('SIGINT', () => { cleanup(); process.exit(130); });
  process.on('SIGTERM', () => { cleanup(); process.exit(143); });
  const results = [];
  let failures = 0;

  try {
    const { browserWs, version } = await fetchBrowserWs(cdpPort);
    console.log(`[Edge] ${version}`);
    void browserWs;
    const pageWs = await fetchPageWs(cdpPort);
    const ws = new WebSocket(pageWs);
    await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
    const cdp = new CDP(ws);
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    cdp.on('Runtime.consoleAPICalled', (p) => {
      const args = (p.args || []).map((a) => (a.value !== undefined ? a.value
        : (a.description || a.type))).join(' ');
      console.log('  [浏览器]', p.type, args);
    });
    cdp.on('Runtime.exceptionThrown', (p) => {
      const d = p.exceptionDetails || {};
      console.log('  [浏览器异常]', (d.exception && d.exception.description) || d.text);
    });

    for (const board of boardNames) {
      const boardDir = join(boardsRoot, board);
      let meta = {};
      try { meta = JSON.parse(readFileSync(join(boardDir, 'meta.json'), 'utf8')); } catch { /* keep */ }
      const boardId = meta.id || board;
      /* 图片落点用 meta 里的年份与县市全称（dist/dist_png/2022/臺北市.png） */
      const year = (meta.meta && meta.meta.year) || Number((boardId.match(/^(\d{4})/) || [])[1]) || '';
      const county = (meta.meta && meta.meta.county) || boardId;

      for (const scale of opts.scales) {
        const W = BASE_W * scale, H = BASE_H * scale;
        /* index.html 是產物，在 dist/boards/<id>/（由 src/templates/index.html 複製）。
           場次源碼在 src/boards/<name>/，只放 meta.json + source/。
           靜態伺服器根仍是 Video/，故 URL 直接用 dist/... 這段。 */
        const urlRel = `dist/boards/${boardId}/index.html`;
        const url = `http://127.0.0.1:${httpPort}/${urlRel}?headless=1`;
        try {
          console.log(`\n[场次] ${boardId}  ${W}x${H}`);
          const loaded = cdp.once('Page.loadEventFired', 60000, '页面加载');
          await cdp.send('Page.navigate', { url });
          await loaded;
          console.log('  · 载入完成，等待看板就绪…');

          await cdp.evaluate(`(async () => {
            for (let i = 0; i < 300; i++) {
              if (typeof window.__boardReady === 'function') break;
              await new Promise(r => setTimeout(r, 100));
            }
            if (typeof window.__boardReady !== 'function') {
              return 'poll-timeout (__boardReady 未定义，headless hook 没载入？)';
            }
            return await Promise.race([
              window.__boardReady().then(() => 'ok').catch(e => 'reject: ' + (e && e.message)),
              new Promise(r => setTimeout(() => r('ready-timeout'), 15000))
            ]);
          })()`, 25000).then((status) => {
            if (status !== 'ok') throw new Error('看板未就绪 → ' + status);
          });

          /* 全部 22 张同一个年份文件夹：dist/dist_png/2022/<县市>.png */
          const pngName = safeRelPath(
            pngNameOf(year, county, scale, scale === opts.scales[0]));
          const info = await cdp.evaluate(
            `window.__saveBoard(${scale}, ${JSON.stringify(pngName)})`, 180000);
          if (!info || !info.ok) throw new Error('保存失败：' + JSON.stringify(info));
          const outFile = join(opts.out, pngName);
          const buffer = readFileSync(outFile);
          const sha = createHash('sha256').update(buffer).digest('hex');
          results.push({ board: boardId, group: String(year), county, scale, width: W, height: H, file: outFile, bytes: buffer.length, sha256: sha, ok: true });
          console.log(`  ✓ ${outFile}  ${buffer.length.toLocaleString()} bytes  sha256=${sha.slice(0, 16)}…`);

          /* 版面报告：只量一次（最小倍率那次），供 verify_layout.py 验证图例不吃到东西。
             报告不是图片，落 dist/boards/<id>/layout.json，别混进 dist_png。
             __layoutReport 会扫地图 PNG 的 alpha 逐像素找墨迹框，约 0.1 s。 */
          if (opts.report && scale === opts.scales[0]) {
            const rep = await cdp.evaluate('window.__layoutReport()', 60000);
            if (rep) {
              const layoutDir = join(opts.layoutRoot, boardId);
              mkdirSync(layoutDir, { recursive: true });
              writeFileSync(join(layoutDir, 'layout.json'),
                JSON.stringify(rep, null, 2), 'utf8');
              console.log(`  · 版面报告 ${join(layoutDir, 'layout.json')}`);
            }
          }
        } catch (err) {
          failures++;
          results.push({ board: boardId, scale, width: W, height: H, ok: false, error: String(err.message || err) });
          console.error(`  ✗ ${boardId} @${scale}x 失败：${err.message || err}`);
        }
      }
    }

    // manifest.json（清单不是图片：固定落 dist/manifest.json，不进 dist_png）
    // ★ 增量合并：--boards 只渲几场时，不再把整份清单压成那几场
    //   （旧版会覆写，得靠手写 python 把 40 笔併回来）。以 board+scale 为键，
    //   本次成功的结果覆盖同键旧记录；本次失败则保留旧的成功记录不清空。
    //   要整份重写用 --no-merge。
    let prevResults = [];
    if (opts.merge && existsSync(opts.manifest)) {
      try {
        const prev = JSON.parse(readFileSync(opts.manifest, 'utf8'));
        prevResults = Array.isArray(prev.results) ? prev.results : [];
      } catch { /* 旧清单坏了就当没有 */ }
    }
    const byKey = new Map();
    for (const r of prevResults) byKey.set(`${r.board}|${r.scale}`, r);
    for (const r of results) {
      const k = `${r.board}|${r.scale}`;
      if (r.ok || !byKey.has(k)) byKey.set(k, r);
    }
    const merged = [...byKey.values()].sort((a, b) =>
      a.board.localeCompare(b.board) || (a.scale - b.scale));

    const manifest = {
      generatedAt: new Date().toISOString(),
      edge: version,
      node: process.version,
      pngDir: relative(VIDEO_ROOT, opts.out).replace(/\\/g, '/'),
      scales: opts.scales,
      results: merged,
      summary: {
        total: merged.length,
        ok: merged.filter((r) => r.ok).length,
        failed: merged.filter((r) => !r.ok).length,
        thisRun: { total: results.length, ok: results.filter((r) => r.ok).length, failed: failures },
      },
    };
    mkdirSync(dirname(opts.manifest), { recursive: true });
    writeFileSync(opts.manifest, JSON.stringify(manifest, null, 2), 'utf8');
    console.log(`\n[清单] ${opts.manifest}（累计 ${manifest.summary.ok}/${manifest.summary.total} 笔）`);
    console.log(`[结果] 本次：成功 ${manifest.summary.thisRun.ok} / 失败 ${manifest.summary.thisRun.failed} / 共 ${manifest.summary.thisRun.total}`);

    /* 契约自检：PNG 出口目录里（含各场次子目录）只准有 .png。混进 json/js
       之类的，说明有别的环节往这里写东西 —— 当场叫出来，免得又变成垃圾堆。 */
    const strays = listNonPng(opts.out);
    if (strays.length) {
      console.warn(`[警告] ${opts.out} 下有非 PNG 文件：${strays.join('、')}`);
    }
  } finally {
    if (!opts.keepOpen) killTree(edgeProc);
    httpServer.close();
  }

  process.exit(failures ? 1 : 0);
}

main().catch((e) => {
  console.error('[错误]', e.message || e);
  process.exit(1);
});
