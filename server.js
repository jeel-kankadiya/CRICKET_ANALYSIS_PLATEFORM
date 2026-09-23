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

  // ─── Playing XI Generator API ────────────────────────────────────────
  if (pathname === '/api/playing-xi') {
    const data = getDataset();
    if (!data || !data.playing_xi_data || !data.player_venue_stats) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Playing XI data not available. Re-run the pipeline.' }));
      return;
    }

    const team1 = reqUrl.searchParams.get('team1') || '';
    const team2 = reqUrl.searchParams.get('team2') || '';
    const venue = reqUrl.searchParams.get('venue') || '';

    if (!team1 || !team2 || !venue) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing required parameters: team1, team2, venue' }));
      return;
    }

    const { team_rosters, player_roles } = data.playing_xi_data;
    const pvs = data.player_venue_stats;
    const pcs = data.player_career_stats || {};

    // ── Scoring helpers ──────────────────────────────────────────────
    function computeBatScore(s) {
      // Weighted: runs (25%), avg (25%), SR (20%), innings experience (15%), milestones (15%)
      const milestones = (s.fifties || 0) * 15 + (s.hundreds || 0) * 30;
      return (s.runs * 0.25) + (s.avg * 0.25) + (s.sr * 0.20)
           + ((s.innings || 0) * 8 * 0.15) + (milestones * 0.15);
    }

    function computeBowlScore(s) {
      // Weighted: wickets (35%), economy (30%), experience (20%), impact (15%)
      const econScore = s.economy > 0 ? (12.0 / s.economy) * 15 : 0;
      const impact = s.wickets > 0 && (s.bowl_innings || 0) > 0
        ? (s.wickets / s.bowl_innings) * 20 : 0;
      return (s.wickets * 12 * 0.35) + (econScore * 0.30)
           + ((s.bowl_innings || 0) * 8 * 0.20) + (impact * 0.15);
    }

    function computeScore(role, stats) {
      if (role === 'Batsman' || role === 'Wicketkeeper') {
        return computeBatScore(stats);
      } else if (role === 'Bowler') {
        return computeBowlScore(stats);
      } else if (role === 'All-Rounder') {
        const batScore = computeBatScore(stats);
        const bowlScore = computeBowlScore(stats);
        // Versatility bonus: reward players contributing in both disciplines
        const versatility = (stats.runs > 0 && stats.wickets > 0) ? 10 : 0;
        return batScore * 0.45 + bowlScore * 0.45 + versatility * 0.10;
      }
      return 0;
    }

    function buildXI(teamName) {
      const roster = team_rosters[teamName] || [];
      if (roster.length === 0) return { team: teamName, error: 'No roster found', players: [] };

      const vl = venue.toLowerCase();

      // Score each player using venue-specific stats with career fallback
      const scored = roster.map(pName => {
        const role = player_roles[pName] || 'Batsman';
        const venueList = pvs[pName] || [];
        const venueData = venueList.find(v => v.venue && v.venue.toLowerCase() === vl)
                       || venueList.find(v => v.venue && v.venue.toLowerCase().includes(vl.split('(')[0].trim().toLowerCase()));

        const careerData = pcs[pName] || null;
        const hasVenueData = !!venueData && (
          (venueData.runs > 0 || venueData.innings > 0 || venueData.wickets > 0 || venueData.bowl_innings > 0)
        );

        // Build stats objects
        const zeroStats = { runs: 0, innings: 0, avg: 0, sr: 0, wickets: 0, economy: 0,
                            hs: 0, fours: 0, sixes: 0, bowl_innings: 0, fifties: 0, hundreds: 0 };

        const venueStats = hasVenueData ? {
          runs: venueData.runs || 0, innings: venueData.innings || 0,
          avg: venueData.avg || 0, sr: venueData.sr || 0,
          wickets: venueData.wickets || 0, economy: venueData.economy || 0,
          hs: venueData.hs || 0, fours: venueData.fours || 0,
          sixes: venueData.sixes || 0, fifties: venueData.fifties || 0,
          hundreds: venueData.hundreds || 0, bowl_innings: venueData.bowl_innings || 0,
        } : { ...zeroStats };

        const careerStats = careerData ? {
          runs: careerData.runs || 0, innings: careerData.innings || 0,
          avg: careerData.avg || 0, sr: careerData.sr || 0,
          wickets: careerData.wickets || 0, economy: careerData.economy || 0,
          hs: careerData.hs || 0, fours: careerData.fours || 0,
          sixes: careerData.sixes || 0, fifties: careerData.fifties || 0,
          hundreds: careerData.hundreds || 0, bowl_innings: careerData.bowl_innings || 0,
          venues_played: careerData.venues_played || 0,
        } : { ...zeroStats, venues_played: 0 };

        let score = 0;

        if (hasVenueData) {
          // Venue data exists: 70% venue + 30% career
          const venueScore = computeScore(role, venueStats);
          const careerScore = computeScore(role, careerStats);
          // Venue experience bonus: more innings at venue = more reliable data
          const venueInnings = Math.max(venueStats.innings, venueStats.bowl_innings);
          const experienceBonus = Math.min(venueInnings * 2, 20); // cap at 20 bonus points
          score = venueScore * 0.70 + careerScore * 0.30 + experienceBonus;
        } else if (careerData) {
          // No venue data but has career stats: use career with a small penalty
          const careerScore = computeScore(role, careerStats);
          score = careerScore * 0.85; // 15% penalty for lack of venue experience
        }
        // else: no data at all => score stays 0

        return {
          name: pName,
          role,
          score: Math.round(score * 10) / 10,
          venue_stats: venueStats,
          career_stats: careerStats,
          has_venue_data: hasVenueData,
          matches_at_venue: hasVenueData ? Math.max(venueStats.innings, venueStats.bowl_innings) : 0,
        };
      });

      // Group by role
      const batsmen = scored.filter(p => p.role === 'Batsman').sort((a, b) => b.score - a.score);
      const keepers = scored.filter(p => p.role === 'Wicketkeeper').sort((a, b) => b.score - a.score);
      const allrounders = scored.filter(p => p.role === 'All-Rounder').sort((a, b) => b.score - a.score);
      const bowlers = scored.filter(p => p.role === 'Bowler').sort((a, b) => b.score - a.score);

      // Select: 4 Batsmen, 1 WK, 1 All-Rounder, 5 Bowlers
      const selected = [];
      const needs = { Batsman: 4, Wicketkeeper: 1, 'All-Rounder': 1, Bowler: 5 };
      const pools = { Batsman: batsmen, Wicketkeeper: keepers, 'All-Rounder': allrounders, Bowler: bowlers };

      for (const [role, count] of Object.entries(needs)) {
        const pool = pools[role];
        const picked = pool.slice(0, count);
        selected.push(...picked);

        // If not enough players in this role, fill from remaining scored players
        if (picked.length < count) {
          const remaining = count - picked.length;
          const pickedNames = new Set(selected.map(p => p.name));
          const fallbacks = scored
            .filter(p => !pickedNames.has(p.name))
            .sort((a, b) => b.score - a.score)
            .slice(0, remaining)
            .map(p => ({ ...p, role: role + ' (Fallback)' }));
          selected.push(...fallbacks);
        }
      }

      return { team: teamName, players: selected.slice(0, 11) };
    }

    const result = {
      venue,
      team1_xi: buildXI(team1),
      team2_xi: buildXI(team2),
    };

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result));
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
