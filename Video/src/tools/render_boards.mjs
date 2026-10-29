#!/usr/bin/env node
/**
 * render_boards.mjs —— 零依赖无头渲染器（Node 内建 WebSocket + fetch + CDP）
 * ---------------------------------------------------------------------------
 * 一次启动 Edge，循环渲染**多场**看板 → 写 PNG 落盘 → 记 SHA256 到 manifest.json。
 *
 * 用法：
 *   node src/tools/render_boards.mjs --all --scale 1
 *   node src/tools/render_boards.mjs --boards 2018-taipei-mayor 2022-taipei-mayor --scales 1,2
 *   node src/tools/render_boards.mjs --all --scales 1,2 --out ../out
 *
 * 产物分三个出口，互不混放：
 *   PNG        → dist/dist_png/<项目>/<年份>.png   （同项目所有年份同一个文件夹）
 *   layout.json→ dist/boards/<id>/layout.json    （报告，跟看板产物放一起）
 *   manifest   → dist/manifest.json              （清单，增量合并）
 *
 * 参数：
 *   --boards <name...>   指定场次目录名（可多个，相对 boards/）
 *   --all                渲染 boards/ 下所有含 meta.json 的场次
 *   --scale <n>          单一倍率（等价 --scales n）
 *   --scales <1,2>       多倍率（逗号分隔）
 *   --out <dir>          PNG 输出目录，默认 Video/dist/dist_png。
 *                        **按选举项目分文件夹、同项目所有年份同框、只有图片**：
 *                        <out>/<项目>/<年份>[-map2].<ext>（2x 加 _2x 后缀）。
 *                        例：taipei-mayor/1994.png … president-tzmm/2024.png。
 *                        不跟 board.js / index.html 混放。
 *   --format <png|webp>  图片格式，默认 png（与改造前完全一致）。
 *                        webp = 有损压缩，4.6MB → 0.47MB（q95），看板底色是大面积
 *                        渐变 + 街景照片，PNG 无损编码 90% 体积是格式浪费。
 *   --quality <0-1>      webp 质量，默认 0.95。png 忽略。
 *   --variants <a,b>     同一场次渲多种地图版式，默认 map。
 *                        map2 = 区级版（只画区不画里）：URL 带 &mapVariant=map2，
 *                        引擎把 Layout.map.src 换成 assets/map2.png，
 *                        交付文件名仍是 <年份>-map2.<ext>。
 *                        用来取代「同一年开两场、board.js 完全相同」的旧做法。
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
 * 场次 id → 图片落点（相对 --out，按「选举项目」分文件夹，同项目所有年份同框）。
 *
 *   taipei-mayor/1994.png        ← 1994-taipei-mayor
 *   taipei-mayor/2022.png        ← 2022-taipei-mayor
 *   president-north/1996.png     ← 1996-president-north
 *   president-north/1996-map2.png← 1996-president-north-map2（同项目，另一种地图版式）
 *   president-tzmm/2024.png      ← 2024-president-tzmm
 *
 * 拆分规则（唯一的真相，Python 侧 naming.split_board_id() 必须一致）：
 *   ① 去掉开头的 `<四位年份>-` → 剩下的就是项目名（组文件夹名）
 *   ② 项目名尾巴若是 `-map2`（区级版地图），从项目名里摘掉、改成文件名的
 *      后缀 `-map2` —— 它和村里版是同一场选举，不该另开一个项目文件夹
 *   ③ 文件名 = `<年份>[-map2].png`，2 倍图 = `<年份>[-map2]_2x.png`
 *
 * 不合 `<年份>-<项目>` 格式的 id 原样当项目名、原样当文件名，不猜。
 *
 * ★ 倍率后缀用 `_2x` 不用 `@2x`：/__save 的檔名逐段消毒只留
 *   [A-Za-z0-9._-]，`@` 会被换成 `_`，于是「POST 用的名字」跟
 *   「Node 端 readFileSync 的名字」对不上，2 倍图必炸（旧版的坑）。
 */
function splitBoardId(boardId) {
  const m = /^(\d{4})-(.+)$/.exec(boardId);
  if (!m) return { group: boardId, stem: boardId };
  let group = m[2];
  let variant = '';
  const mv = /^(.*)-map2$/.exec(group);
  if (mv) { group = mv[1]; variant = '-map2'; }
  return { group, stem: m[1] + variant };
}

function pngNameOf(boardId, scale, ext = 'png', variant = '') {
  const { group, stem } = splitBoardId(boardId);
  /* 场次 id 自带 -map2 时 stem 已含后缀；变体方案下的 id 没有后缀，
     由 variant 补上 —— 交付文件名两边一致（<年份>-map2）。 */
  const vs = (variant && variant !== 'map' && !stem.endsWith('-' + variant))
    ? '-' + variant : '';
  const file = scale === 1 ? `${stem}${vs}.${ext}` : `${stem}${vs}_${scale}x.${ext}`;
  return `${group}/${file}`;
}

/** 图片出口目录允许的扩展名。用了 --format webp 后 .webp 也是合法产物。 */
const IMAGE_EXTS = ['.png', '.webp'];

/**
 * 递归列出 dir 下所有「不是图片」的文件（相对 dir）。
 * 用来守着「dist_png 里只有图片」这条契约 —— 每场一个子目录，所以要往里走。
 */
function listNonPng(dir, base = dir) {
  const out = [];
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, ent.name);
    if (ent.isDirectory()) out.push(...listNonPng(p, base));
    else if (!IMAGE_EXTS.some((e) => ent.name.toLowerCase().endsWith(e))) {
      out.push(relative(base, p));
    }
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
    format: 'png', quality: 0.95, variants: ['map'],
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--boards' || a === '--board') {
      while (argv[i + 1] && !argv[i + 1].startsWith('--')) opts.boards.push(argv[++i]);
    } else if (a === '--all') opts.all = true;
    else if (a === '--scale') opts.scales.push(parseInt(argv[++i], 10));
    else if (a === '--scales') opts.scales.push(...String(argv[++i]).split(',').map(Number));
    else if (a === '--out') opts.out = resolve(argv[++i]);
    else if (a === '--format') opts.format = String(argv[++i]).toLowerCase();
    else if (a === '--quality') opts.quality = Number(argv[++i]);
    else if (a === '--variants') opts.variants = String(argv[++i]).split(',').map((s) => s.trim()).filter(Boolean);
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
  if (!opts.scales.length) opts.scales = [1];
  opts.scales = [...new Set(opts.scales)].filter((n) => Number.isFinite(n) && n > 0);
  if (!opts.scales.length) throw new Error('--scales 没给有效倍率');
  if (!['png', 'webp', 'jpeg'].includes(opts.format)) {
    throw new Error('--format 只支持 png / webp / jpeg，收到 ' + opts.format);
  }
  if (!(opts.quality > 0 && opts.quality <= 1)) throw new Error('--quality 要在 (0, 1] 之间');
  opts.variants = [...new Set(opts.variants)];
  for (const v of opts.variants) {
    if (!['map', 'map2'].includes(v)) throw new Error('--variants 只支持 map / map2，收到 ' + v);
  }
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
        /* 允许子目录（场次名/board.png），但逐段消毒、拒绝 . 与 .. 穿越 */
        const segs = raw.split('/').map((s) => s.replace(/[^A-Za-z0-9._-]/g, '_'))
          .filter((s) => s && s !== '.' && s !== '..');
        const name = segs.join('/') || 'out.png';
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

    /* 一次批次一个 runId：素材 URL 的 ?t= 在 headless 下用它（见 utils.js
       stampUrl），同批内固定 → 第二场起 street_bg.png / 地图 / 徽章全部命中
       浏览器 HTTP 缓存。素材真的换了，下一次批次自然是新的 runId。 */
    const runId = Date.now().toString(36);
    console.log(`[批次] runId=${runId}  变体 ${opts.variants.join('+')}  格式 ${opts.format}`
      + (opts.format === 'png' ? '' : ` q${opts.quality}`));

    for (const board of boardNames) {
      const boardDir = join(boardsRoot, board);
      let boardId = board;
      try { boardId = JSON.parse(readFileSync(join(boardDir, 'meta.json'), 'utf8')).id || board; } catch { /* keep */ }

      for (const variant of opts.variants) {
        /* index.html 是產物，在 dist/boards/<id>/（由 src/templates/index.html 复制）。
           场次源码在 src/boards/<name>/，只放 meta.json + source/。
           静态服务器根仍是 Video/，故 URL 直接用 dist/... 这段。 */
        /* 入口页：全場共用 dist/boards/_entry/index.html，用 ?board=<id> 指定场次
           （模板只留一份，不再每场复制 —— 旧版是 32 份 sha256 全同的副本）。
           共用入口存在就用它；不存在（旧产物 / 只 checkout 了一半）时退回
           dist/boards/<id>/index.html，两条路都能跑。 */
        const entryRel = 'dist/boards/_entry/index.html';
        const useSharedEntry = existsSync(join(opts.root, entryRel));
        const urlRel = useSharedEntry ? entryRel : `dist/boards/${boardId}/index.html`;
        let qs = `headless=1&v=${runId}`;
        if (useSharedEntry) qs = `board=${encodeURIComponent(boardId)}&${qs}`;
        if (variant !== 'map') qs += `&mapVariant=${variant}`;
        // 入口不存在就别开浏览器等 25 秒超时了 —— 直接说清楚要跑什么。
        // 踩过的坑：用通配符批量删各场 index.html 时，会把共用入口
        // dist/boards/_entry/index.html 一起删掉（它也在 dist/boards/ 下一层），
        // 症状是「载入完成但 __boardReady 一直没定义」，很难查。
        if (!existsSync(join(opts.root, urlRel))) {
          throw new Error(`入口页不存在：${urlRel}（先跑 python src/tools/build_board.py`
            + ` 或 build_all.py 重建共用入口 dist/boards/_entry/index.html）`);
        }
        const url = `http://127.0.0.1:${httpPort}/${urlRel}?${qs}`;
        const tag = variant === 'map' ? '' : ` [${variant}]`;
        /* 清单里的场次名：变体沿用旧的「-map2 后缀」命名，与改造前可比对。 */
        const resultName = variant === 'map' ? boardId : `${boardId}-${variant}`;
        try {
          console.log(`\n[场次] ${boardId}${tag}  ${BASE_W}x${BASE_H} × ${opts.scales.join(',')}`);
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

          /* ★ 多倍率共用「一次导航 + 一次 ready」：__saveBoard 每次新建 canvas、
             互不干扰，重载页面只会白重下素材、重跑模型（旧版每个倍率导航一遍）。 */
          for (const scale of opts.scales) {
            const W = BASE_W * scale, H = BASE_H * scale;
            /* 按项目分文件夹：dist/dist_png/<项目>/<年份>[-map2].<ext>（2x 加 _2x） */
            const pngName = pngNameOf(boardId, scale, opts.format, variant);
            const info = await cdp.evaluate(
              `window.__saveBoard(${scale}, ${JSON.stringify(pngName)}, `
              + `${JSON.stringify(opts.format)}, ${opts.quality})`, 180000);
            if (!info || !info.ok) throw new Error('保存失败：' + JSON.stringify(info));
            const outFile = join(opts.out, pngName);
            const buffer = readFileSync(outFile);
            const sha = createHash('sha256').update(buffer).digest('hex');
            results.push({
              board: resultName, group: splitBoardId(boardId).group, scale,
              width: W, height: H, format: opts.format, file: outFile,
              bytes: buffer.length, sha256: sha, ok: true,
            });
            console.log(`  ✓ ${outFile}  ${buffer.length.toLocaleString()} bytes  sha256=${sha.slice(0, 16)}…`);
          }

          /* 版面报告：只量一次（首个倍率、主变体），供 verify_layout.py 验证图例不吃到东西。
             报告不是图片，落 dist/boards/<id>/layout.json，别混进 dist_png。
             __layoutReport 会扫地图 PNG 的 alpha 逐像素找墨迹框，约 0.1 s。
             只有主变体写报告：变体共用同一个场次目录，写两次会互相覆盖。 */
          if (opts.report && variant === 'map') {
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
          /* 导航/就绪失败算整组失败：把每个倍率各记一笔，清单统计才和改造前一致。 */
          for (const scale of opts.scales) {
            failures++;
            results.push({
              board: resultName, scale, width: BASE_W * scale, height: BASE_H * scale,
              format: opts.format, ok: false, error: String(err.message || err),
            });
          }
          console.error(`  ✗ ${boardId}${tag} 失败：${err.message || err}`);
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
