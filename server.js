const http = require('http');
const fs   = require('fs');
const path = require('path');

const PORT = 5000;
const DASHBOARD = path.join(__dirname, 'dashboard', 'index.html');
const OUTPUTS_DIR = path.join(__dirname, 'outputs');
const DATASET_FILE = path.join(OUTPUTS_DIR, 'dashboard_data.json');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
  '.png':  'image/png',
  '.ico':  'image/x-icon',
  '.svg':  'image/svg+xml',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
};

// Cache dataset in memory for fast API responses
let cachedData = null;
function getDataset() {
  try {
    const raw = fs.readFileSync(DATASET_FILE, 'utf-8');
    cachedData = JSON.parse(raw);
  } catch (err) {
    console.error('Error reading dashboard_data.json:', err.message);
  }
  return cachedData;
}
getDataset(); // Initial load

http.createServer((req, res) => {
  const reqUrl = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = reqUrl.pathname;

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // API Endpoints
  if (pathname === '/api/data' || pathname === '/outputs/dashboard_data.json') {
    const data = getDataset();
    if (!data) { res.writeHead(500); res.end(JSON.stringify({ error: 'Failed to load dataset' })); return; }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    return;
  }

  if (pathname === '/api/players') {
    const data = getDataset();
    const players = data ? data.all_players || [] : [];
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ total: players.length, players }));
    return;
  }

  if (pathname.startsWith('/api/player')) {
    const q = (reqUrl.searchParams.get('q') || pathname.replace('/api/player/', '') || '').trim().toLowerCase();
    const data = getDataset();
    const players = data ? data.all_players || [] : [];
    if (!q) {
      res.writeHead(400); res.end(JSON.stringify({ error: 'Query parameter q is required' })); return;
    }
    const matches = players.filter(p => 
      (p.PlayerName && p.PlayerName.toLowerCase().includes(q)) ||
      (p.player_full_name && p.player_full_name.toLowerCase().includes(q)) ||
      (p.Teams && p.Teams.toLowerCase().includes(q))
    );
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ query: q, count: matches.length, players: matches }));
    return;
  }

  // Serve static files from outputs/ if requested
  if (pathname.startsWith('/outputs/')) {
    const targetFile = path.join(__dirname, pathname);
    if (targetFile.startsWith(OUTPUTS_DIR) && fs.existsSync(targetFile)) {
      const ext = path.extname(targetFile);
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
      fs.createReadStream(targetFile).pipe(res);
      return;
    }
  }

  // Static Dashboard files
  const url = pathname === '/' ? '/index.html' : pathname;
  const filePath = path.join(__dirname, 'dashboard', url);
  const ext = path.extname(filePath);
  const contentType = MIME[ext] || 'text/plain';

  if (!filePath.startsWith(path.join(__dirname, 'dashboard'))) {
    res.writeHead(403); res.end('Forbidden'); return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      fs.readFile(DASHBOARD, (err2, html) => {
        if (err2) { res.writeHead(404); res.end('Not found'); return; }
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
      });
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });

  const ts = new Date().toISOString();
  console.log(`${req.method} ${pathname} - ${ts}`);
}).listen(PORT, () => {
  console.log(`\n🏏  Cricket Intelligence Platform`);
  console.log(`    Dashboard → http://localhost:${PORT}`);
  console.log(`    API Data  → http://localhost:${PORT}/api/data`);
  console.log(`    API Player → http://localhost:${PORT}/api/player?q=virat\n`);
});

