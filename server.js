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

    const team = reqUrl.searchParams.get('team') || '';
    const venue = reqUrl.searchParams.get('venue') || '';
    const isAllVenues = !venue || venue === 'all';

    if (!team) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing required parameter: team' }));
      return;
    }

    const { team_rosters, player_roles, player_bowl_types } = data.playing_xi_data;
    const bowlTypes = player_bowl_types || {};
    const pvs = data.player_venue_stats;
    const pcs = data.player_career_stats || {};

    // ── Determine venue pitch type ──────────────────────────────────
    let pitchType = 'Balanced';
    if (!isAllVenues && data.venue_intelligence && data.venue_intelligence.venue_profiles) {
      const vLower = venue.toLowerCase().split('(')[0].split(',')[0].trim();
      const matchingProfiles = data.venue_intelligence.venue_profiles.filter(
        v => v.venue && v.venue.toLowerCase().includes(vLower)
      );
      if (matchingProfiles.length > 0) {
        matchingProfiles.sort((a, b) => (b.total_matches_hosted || 0) - (a.total_matches_hosted || 0));
        if (matchingProfiles[0].pitch_type) {
          pitchType = matchingProfiles[0].pitch_type;
        }
      }
    }

    // ── Bowling composition based on pitch type ─────────────────────
    const pitchCompositions = {
      'Seam Friendly':    { pace: 4, spin: 1, arPref: 'pace' },
      'Batting Paradise': { pace: 3, spin: 2, arPref: 'pace' },
      'Balanced':         { pace: 3, spin: 2, arPref: 'pace' },
      'Spin Friendly':    { pace: 2, spin: 3, arPref: 'spin' },
      'Slow & Low':       { pace: 2, spin: 3, arPref: 'spin' },
    };
    const comp = pitchCompositions[pitchType] || pitchCompositions['Balanced'];

    // ── Scoring helpers ──────────────────────────────────────────────
    function computeBatScore(s) {
      if (!s || (s.runs <= 0 && s.innings <= 0)) return 0;
      const cappedAvg = Math.min(s.avg || 0, 65);
      const milestones = (s.fifties || 0) * 15 + (s.hundreds || 0) * 35;
      return (s.runs * 0.25) + (cappedAvg * 0.25) + ((s.sr || 0) * 0.20)
           + ((s.innings || 0) * 5 * 0.15) + (milestones * 0.15);
    }

    function computeBowlScore(s) {
      // ZERO-WICKETS RULE: If a bowler has 0 wickets, bowling score is STRICTLY ZERO.
      if (!s || s.wickets <= 0) return 0;
      const econScore = (s.economy > 0 && s.economy <= 15) ? (12.0 / s.economy) * 15 : 0;
      const impact = (s.bowl_innings || 0) > 0 ? (s.wickets / s.bowl_innings) * 20 : 0;
      return (s.wickets * 12 * 0.35) + (econScore * 0.30)
           + ((s.bowl_innings || 0) * 5 * 0.20) + (impact * 0.15);
    }

    function computeScore(role, stats) {
      if (role === 'Batsman' || role === 'Wicketkeeper') {
        return computeBatScore(stats);
      } else if (role === 'Bowler') {
        return computeBowlScore(stats);
      } else if (role === 'All-Rounder') {
        const batScore = computeBatScore(stats);
        const bowlScore = computeBowlScore(stats);
        const versatility = (stats.runs > 0 && stats.wickets > 0) ? 10 : 0;
        return batScore * 0.45 + bowlScore * 0.45 + versatility * 0.10;
      }
      return 0;
    }

    function buildXI(teamName) {
      let roster = team_rosters[teamName] || [];
      const isAllTime = teamName.includes('All-Time') || teamName === 'All-Time XI';

      if (isAllTime) {
        const allPlayersSet = new Set();
        Object.values(team_rosters).forEach(rList => rList.forEach(p => allPlayersSet.add(p)));
        roster = Array.from(allPlayersSet);
      }

      if (roster.length === 0) return { team: teamName, error: 'No roster found', players: [] };

      const vl = venue.toLowerCase();

      // Score each player using venue-specific stats with career fallback
      const scored = roster.map(pName => {
        const role = player_roles[pName] || 'Batsman';
        const venueList = pvs[pName] || [];
        const venueData = !isAllVenues
          ? (venueList.find(v => v.venue && v.venue.toLowerCase() === vl)
             || venueList.find(v => v.venue && v.venue.toLowerCase().includes(vl.split('(')[0].trim().toLowerCase())))
          : null;

        const careerData = pcs[pName] || null;
        const hasVenueData = !isAllVenues && !isAllTime && !!venueData && (
          (venueData.runs > 0 || venueData.innings > 0 || venueData.wickets > 0 || venueData.bowl_innings > 0)
        );

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

        if ((isAllTime || isAllVenues) && careerData) {
          // Career-based scoring (All Venues or All-Time)
          if (role === 'Batsman' || role === 'Wicketkeeper') {
            score = (careerStats.runs * 0.5) + (Math.min(careerStats.avg, 50) * 2.0) + (careerStats.fifties * 10) + (careerStats.hundreds * 25);
          } else if (role === 'Bowler') {
            score = careerStats.wickets > 0 ? (careerStats.wickets * 15.0) + ((12.0 / (careerStats.economy || 8.0)) * 10) : 0;
          } else if (role === 'All-Rounder') {
            score = (careerStats.runs * 0.30) + (careerStats.wickets > 0 ? careerStats.wickets * 12.0 : 0);
          }
        } else if (hasVenueData) {
          const venueScore = computeScore(role, venueStats);
          const careerScore = computeScore(role, careerStats);
          const venueInnings = Math.max(venueStats.innings, venueStats.bowl_innings);
          const experienceBonus = Math.min(venueInnings * 2, 20);
          score = venueScore * 0.70 + careerScore * 0.30 + experienceBonus;
        } else if (careerData) {
          const careerScore = computeScore(role, careerStats);
          score = careerScore * 0.85;
        }

        return {
          name: pName,
          role,
          bowl_type: bowlTypes[pName] || 'pace',
          score: Math.round(score * 10) / 10,
          venue_stats: venueStats,
          career_stats: careerStats,
          has_venue_data: hasVenueData,
          matches_at_venue: hasVenueData ? Math.max(venueStats.innings, venueStats.bowl_innings) : 0,
        };
      });

      // ── Pitch-type-aware team composition ─────────────────────────
      const batsmen = scored.filter(p => p.role === 'Batsman').sort((a, b) => b.score - a.score);
      const keepers = scored.filter(p => p.role === 'Wicketkeeper').sort((a, b) => b.score - a.score);

      // Split bowlers into pace and spin
      const paceBowlers = scored
        .filter(p => p.role === 'Bowler' && p.bowl_type === 'pace' && p.career_stats.wickets > 0)
        .sort((a, b) => b.score - a.score);
      const spinBowlers = scored
        .filter(p => p.role === 'Bowler' && p.bowl_type === 'spin' && p.career_stats.wickets > 0)
        .sort((a, b) => b.score - a.score);

      // Split all-rounders by bowl type
      const paceARs = scored.filter(p => p.role === 'All-Rounder' && p.bowl_type === 'pace').sort((a, b) => b.score - a.score);
      const spinARs = scored.filter(p => p.role === 'All-Rounder' && p.bowl_type === 'spin').sort((a, b) => b.score - a.score);

      const selected = [];

      // 1. Pick 4 batsmen
      selected.push(...batsmen.slice(0, 4));

      // 2. Pick 1 wicketkeeper
      if (keepers.length > 0) {
        selected.push(keepers[0]);
      } else {
        const pickedNames = new Set(selected.map(p => p.name));
        const wkFb = batsmen.filter(p => !pickedNames.has(p.name)).slice(0, 1)
          .map(p => ({ ...p, role: 'Wicketkeeper (Fallback)' }));
        selected.push(...wkFb);
      }

      // 3. Pick 1 all-rounder (prefer pitch-matching bowl type)
      const prefARs = comp.arPref === 'spin' ? spinARs : paceARs;
      const altARs = comp.arPref === 'spin' ? paceARs : spinARs;
      if (prefARs.length > 0) {
        selected.push(prefARs[0]);
      } else if (altARs.length > 0) {
        selected.push(altARs[0]);
      } else {
        const pickedNames = new Set(selected.map(p => p.name));
        const arFb = scored.filter(p => !pickedNames.has(p.name)).sort((a, b) => b.score - a.score).slice(0, 1)
          .map(p => ({ ...p, role: 'All-Rounder (Fallback)' }));
        selected.push(...arFb);
      }

      // 4. Pick 5 bowlers with pitch-type composition
      const bowlerNames = new Set(selected.map(p => p.name));
      const availPace = paceBowlers.filter(p => !bowlerNames.has(p.name));
      const availSpin = spinBowlers.filter(p => !bowlerNames.has(p.name));

      const pickedPace = availPace.slice(0, comp.pace);
      const pickedSpin = availSpin.slice(0, comp.spin);
      selected.push(...pickedPace, ...pickedSpin);

      // Fill shortfall from any remaining bowlers
      const totalBowlers = pickedPace.length + pickedSpin.length;
      if (totalBowlers < 5) {
        const allNames = new Set(selected.map(p => p.name));
        const remaining = scored
          .filter(p => p.role === 'Bowler' && p.career_stats.wickets > 0 && !allNames.has(p.name))
          .sort((a, b) => b.score - a.score);
        selected.push(...remaining.slice(0, 5 - totalBowlers));
      }

      return { team: teamName, players: selected.slice(0, 11) };
    }

    const result = {
      team,
      venue: isAllVenues ? 'All Venues (Career)' : venue,
      pitch_type: pitchType,
      bowling_composition: comp,
      xi: buildXI(team),
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
