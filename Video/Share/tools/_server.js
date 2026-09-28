// tools/_server.js —— 驗證用的極簡靜態伺服器（不參與專案運行）
// 用法：node tools/_server.js 8622
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.argv[2] || 8622);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml'
};

const OUT = path.join(ROOT, 'tools', '_out');

http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);

  // 驗證用：把瀏覽器端產生的圖檔寫回磁碟（僅供開發驗證，不屬於專案功能）
  if (req.method === 'POST' && url === '/__save') {
    const name = (new URL(req.url, 'http://x').searchParams.get('name') || 'out.png')
      .replace(/[^\w.\-]/g, '_');
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      fs.mkdirSync(OUT, { recursive: true });
      const buf = Buffer.concat(chunks);
      fs.writeFileSync(path.join(OUT, name), buf);
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(String(buf.length));
    });
    return;
  }

  const file = path.join(ROOT, url === '/' ? 'index.html' : url);
  if (!file.startsWith(ROOT)) {
    res.writeHead(403).end('forbidden');
    return;
  }
  fs.readFile(file, (err, buf) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' }).end('not found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store'
    });
    res.end(buf);
  });
}).listen(PORT, '127.0.0.1', () => {
  console.log('serving ' + ROOT + ' on http://127.0.0.1:' + PORT);
});
