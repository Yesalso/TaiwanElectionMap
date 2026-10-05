#!/usr/bin/env node
/**
 * render_boards.mjs —— 零依赖无头渲染器（Node 内建 WebSocket + fetch + CDP）
 * ---------------------------------------------------------------------------
 * 一次启动 Edge，循环渲染**多场**看板 → 写 PNG 落盘 → 记 SHA256 到 manifest.json。
 *
 * 用法：
 *   node tools/render_boards.mjs --all --scale 1
 *   node tools/render_boards.mjs --boards 2018-taipei-mayor 2022-taipei-mayor --scales 1,2
 *   node tools/render_boards.mjs --all --scales 1,2 --out ../out
 *
 * 参数：
 *   --boards <name...>   指定场次目录名（可多个，相对 boards/）
 *   --all                渲染 boards/ 下所有含 meta.json 的场次
 *   --scale <n>          单一倍率（等价 --scales n）
 *   --scales <1,2>       多倍率（逗号分隔）
 *   --out <dir>          输出目录，默认 Video/out
 *   --boards-root <dir>  覆盖 boards/ 根目录
 *   --root <dir>         静态服务器根目录，默认 Video/。
 *                        必须是 Video/ 而不是 boards/ —— 透明化成品集中在
 *                        NewSolution/png/processed/，看板的 board.files.js
 *                        用 ../../NewSolution/... 引它，根设在 boards/ 会 404。
 *                        场次目录若含 .skip 标记文件，--all 会跳过它。
 *   --report             额外导出每场的版面报告（out/layout/<id>.json），
 *                        给 tools/verify_layout.py 验「图例不得压到地图／其他元素」。
 *                        默认开启（渲染后顺手量一次，成本约 0.1 s）；--no-report 关闭。
 *   --keep-open          渲染完不关 Edge（调试用）
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
const VIDEO_ROOT = resolve(__dirname, '..');

const BASE_W = 2560;
const BASE_H = 1440;

// ---------------------------------------------------------------- args
function parseArgs(argv) {
  const opts = {
    boards: [], all: false, scales: [], out: join(VIDEO_ROOT, 'out'),
    boardsRoot: join(VIDEO_ROOT, 'boards'), root: VIDEO_ROOT,
    keepOpen: false, report: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--boards' || a === '--board') {
      while (argv[i + 1] && !argv[i + 1].startsWith('--')) opts.boards.push(argv[++i]);
    } else if (a === '--all') opts.all = true;
    else if (a === '--scale') opts.scales.push(parseInt(argv[++i], 10));
    else if (a === '--scales') opts.scales.push(...String(argv[++i]).split(',').map(Number));
    else if (a === '--out') opts.out = resolve(argv[++i]);
    else if (a === '--boards-root') opts.boardsRoot = resolve(argv[++i]);
    else if (a === '--root') opts.root = resolve(argv[++i]);
    else if (a === '--report') opts.report = true;
    else if (a === '--no-report') opts.report = false;
    else if (a === '--keep-open') opts.keepOpen = true;
    else throw new Error('未知参数：' + a);
  }
  if (!opts.scales.length) opts.scales = [1];
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
        const name = raw.replace(/[^A-Za-z0-9._-]/g, '_');
        const dest = join(outDir, name);
        if (!resolve(dest).startsWith(resolve(outDir))) {
          resp.writeHead(403); resp.end('forbidden'); return;
        }
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

  /* 根目录是 Video/（不是 boards/）：看板的素材在 NewSolution/png/processed/ */
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
      let boardId = board;
      try { boardId = JSON.parse(readFileSync(join(boardDir, 'meta.json'), 'utf8')).id || board; } catch { /* keep */ }

      for (const scale of opts.scales) {
        const W = BASE_W * scale, H = BASE_H * scale;
        const boardRel = relative(opts.root, boardDir).split(sep).join('/');
        const url = `http://127.0.0.1:${httpPort}/${boardRel}/index.html?headless=1`;
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

          const outName = `${boardId}_${W}x${H}.png`;
          const info = await cdp.evaluate(
            `window.__saveBoard(${scale}, ${JSON.stringify(outName)})`, 180000);
          if (!info || !info.ok) throw new Error('保存失败：' + JSON.stringify(info));
          const outFile = join(opts.out, outName);
          const buffer = readFileSync(outFile);
          const sha = createHash('sha256').update(buffer).digest('hex');
          results.push({ board: boardId, scale, width: W, height: H, file: outFile, bytes: buffer.length, sha256: sha, ok: true });
          console.log(`  ✓ ${outFile}  ${buffer.length.toLocaleString()} bytes  sha256=${sha.slice(0, 16)}…`);

          /* 版面报告：只量一次（最小倍率那次），供 verify_layout.py 验证图例不吃到东西。
             __layoutReport 会扫地图 PNG 的 alpha 逐像素找墨迹框，约 0.1 s。 */
          if (opts.report && scale === opts.scales[0]) {
            const rep = await cdp.evaluate('window.__layoutReport()', 60000);
            if (rep) {
              const repDir = join(opts.out, 'layout');
              mkdirSync(repDir, { recursive: true });
              writeFileSync(join(repDir, boardId + '.json'),
                JSON.stringify(rep, null, 2), 'utf8');
              console.log(`  · 版面报告 ${join(repDir, boardId + '.json')}`);
            }
          }
        } catch (err) {
          failures++;
          results.push({ board: boardId, scale, width: W, height: H, ok: false, error: String(err.message || err) });
          console.error(`  ✗ ${boardId} @${scale}x 失败：${err.message || err}`);
        }
      }
    }

    // manifest.json
    const manifest = {
      generatedAt: new Date().toISOString(),
      edge: version,
      node: process.version,
      scales: opts.scales,
      results,
      summary: { total: results.length, ok: results.filter((r) => r.ok).length, failed: failures },
    };
    const manifestPath = join(opts.out, 'manifest.json');
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
    console.log(`\n[清单] ${manifestPath}`);
    console.log(`[结果] 成功 ${manifest.summary.ok} / 失败 ${manifest.summary.failed} / 共 ${manifest.summary.total}`);
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
