const http = require('http');
const fs   = require('fs');
const path = require('path');

let PORT = parseInt(process.env.PORT, 10) || 5000;
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

const server = http.createServer((req, res) => {
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
    if (!data) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Dataset not available' }));
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    return;
  }

  if (pathname === '/api/player') {
    const query = reqUrl.searchParams.get('q') || '';
    const data = getDataset();
    if (!data || !data.players) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Dataset not available' }));
      return;
    }
    const qLower = query.toLowerCase();
    const matched = Object.entries(data.players)
      .filter(([name]) => name.toLowerCase().includes(qLower))
      .slice(0, 10)
      .map(([name, stats]) => ({ name, ...stats }));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ query, count: matched.length, players: matched }));
    return;
  }

  if (pathname === '/api/venues') {
    const data = getDataset();
    if (!data || !data.venues) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Dataset not available' }));
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data.venues));
    return;
  }

  if (pathname === '/api/stats') {
    const data = getDataset();
    if (!data) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Dataset not available' }));
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      totalMatches: data.generated_from_matches,
      seasons: data.seasons,
      playersCount: Object.keys(data.players || {}).length,
      venuesCount: Object.keys(data.venues || {}).length,
      topBatsmenCount: (data.top_batsmen || []).length,
      topBowlersCount: (data.top_bowlers || []).length
    }));
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
});

function listen(port) {
  server.listen(port, () => {
    console.log(`\n🏏  Cricket Intelligence Platform`);
    console.log(`    Dashboard → http://localhost:${port}`);
    console.log(`    API Data  → http://localhost:${port}/api/data`);
    console.log(`    API Player → http://localhost:${port}/api/player?q=virat\n`);
  });
}

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.warn(`⚠️  Port ${PORT} is in use. Trying port ${PORT + 1}...`);
    PORT++;
    listen(PORT);
  } else {
    console.error('Server error:', err);
  }
});

listen(PORT);
