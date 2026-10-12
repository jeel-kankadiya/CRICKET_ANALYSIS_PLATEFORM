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
    const team2 = reqUrl.searchParams.get('team2') || '';
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
    let venueAvgScore = 175;
    let tossBatFirstWinRate = 50;

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
        if (matchingProfiles[0].avg_first_innings_score) {
          venueAvgScore = Math.round(matchingProfiles[0].avg_first_innings_score);
        }
        if (matchingProfiles[0].bat_first_win_pct) {
          tossBatFirstWinRate = Math.round(matchingProfiles[0].bat_first_win_pct);
        }
      }
    }

    const pitchCompositions = {
      'Seam Friendly':    { pace: 4, spin: 1, arPref: 'pace', pitchBatMod: 0.92, paceMod: 1.25, spinMod: 0.85 },
      'Batting Paradise': { pace: 3, spin: 2, arPref: 'pace', pitchBatMod: 1.15, paceMod: 0.95, spinMod: 1.05 },
      'Balanced':         { pace: 3, spin: 2, arPref: 'pace', pitchBatMod: 1.00, paceMod: 1.05, spinMod: 1.05 },
      'Spin Friendly':    { pace: 2, spin: 3, arPref: 'spin', pitchBatMod: 0.90, paceMod: 0.85, spinMod: 1.30 },
      'Slow & Low':       { pace: 2, spin: 3, arPref: 'spin', pitchBatMod: 0.85, paceMod: 0.90, spinMod: 1.25 },
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

    function scoreRoster(playerNames) {
      const vl = venue.toLowerCase();
      return playerNames.map(pName => {
        const role = player_roles[pName] || 'Batsman';
        const venueList = pvs[pName] || [];
        const venueData = !isAllVenues
          ? (venueList.find(v => v.venue && v.venue.toLowerCase() === vl)
             || venueList.find(v => v.venue && v.venue.toLowerCase().includes(vl.split('(')[0].trim().toLowerCase())))
          : null;

        const careerData = pcs[pName] || null;
        const hasVenueData = !isAllVenues && !!venueData && (
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
        if (isAllVenues && careerData) {
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
          const experienceBonus = Math.min(venueInnings * 3, 25);
          score = venueScore * 0.70 + careerScore * 0.30 + experienceBonus;
        } else if (careerData) {
          const careerScore = computeScore(role, careerStats);
          score = careerScore * 0.85;
        }

        // ── AI Venue Prediction: Projected Runs & Projected Wickets ────
        const bType = bowlTypes[pName] || 'pace';
        const isBattingRole = (role === 'Batsman' || role === 'Wicketkeeper' || role === 'All-Rounder');
        const isBowlingRole = (role === 'Bowler' || role === 'All-Rounder');

        let predRunsVal = 0, predRunsMin = 0, predRunsMax = 0, runConf = 60;
        if (isBattingRole) {
          const baseAvg = (hasVenueData && venueStats.innings >= 2 && venueStats.avg > 0)
            ? venueStats.avg
            : (careerStats.avg > 0 ? careerStats.avg : 22);
          const pMod = comp.pitchBatMod || 1.0;
          predRunsVal = Math.round(baseAvg * pMod);
          predRunsMin = Math.max(4, Math.round(predRunsVal * 0.65));
          predRunsMax = Math.round(predRunsVal * 1.35 + 8);
          runConf = hasVenueData ? Math.min(95, 65 + venueStats.innings * 3) : 55;
        } else {
          predRunsVal = Math.min(12, Math.round((careerStats.avg || 6) * 0.6));
          predRunsMin = 0; predRunsMax = Math.max(8, predRunsVal * 2);
          runConf = 45;
        }

        let predWktsVal = 0, predWktsMin = 0, predWktsMax = 0;
        if (isBowlingRole) {
          const bMod = bType === 'spin' ? (comp.spinMod || 1.0) : (comp.paceMod || 1.0);
          const baseRate = (hasVenueData && venueStats.bowl_innings >= 2 && venueStats.wickets > 0)
            ? (venueStats.wickets / venueStats.bowl_innings)
            : (careerStats.bowl_innings > 0 ? (careerStats.wickets / careerStats.bowl_innings) : 0.8);
          predWktsVal = Math.round(baseRate * bMod * 10) / 10;
          predWktsMin = Math.max(0, Math.floor(predWktsVal - 0.4));
          predWktsMax = Math.ceil(predWktsVal + 0.8);
        }

        // Venue vs Career comparison
        let venueBoostPct = 0;
        if (hasVenueData && careerStats.avg > 0 && venueStats.avg > 0) {
          venueBoostPct = Math.round(((venueStats.avg - careerStats.avg) / careerStats.avg) * 100);
        }

        // Venue Tag Badge
        let venueBadge = 'Key Squad Player';
        if (hasVenueData && venueStats.runs >= 400) venueBadge = '🏟️ Stadium Fortress';
        else if (hasVenueData && venueStats.wickets >= 15) venueBadge = '🎯 Venue Strike Master';
        else if (hasVenueData && venueBoostPct >= 18) venueBadge = '🔥 Venue Specialist';
        else if (role === 'Wicketkeeper') venueBadge = '🧤 Elite Gloveman';
        else if (role === 'Bowler' && bType === 'spin') venueBadge = '🌀 Spin Wizard';
        else if (role === 'Bowler') venueBadge = '⚡ Pace Spearhead';
        else if (role === 'All-Rounder') venueBadge = '⚡ Dynamic All-Rounder';
        else if (careerStats.runs > 3000) venueBadge = '👑 IPL Legend';

        return {
          name: pName,
          role,
          bowl_type: bType,
          score: Math.round(score * 10) / 10,
          venue_stats: venueStats,
          career_stats: careerStats,
          has_venue_data: hasVenueData,
          matches_at_venue: hasVenueData ? Math.max(venueStats.innings, venueStats.bowl_innings) : 0,
          predicted_runs: { value: predRunsVal, min: predRunsMin, max: predRunsMax, confidence: runConf },
          predicted_wickets: { value: predWktsVal, min: predWktsMin, max: predWktsMax },
          venue_boost_pct: venueBoostPct,
          venue_badge: venueBadge,
        };
      });
    }

    function buildXIFromScored(scoredList, teamName) {
      if (!scoredList || scoredList.length === 0) return { team: teamName, error: 'No players found', players: [] };

      const batsmen = scoredList.filter(p => p.role === 'Batsman').sort((a, b) => b.score - a.score);
      const keepers = scoredList.filter(p => p.role === 'Wicketkeeper').sort((a, b) => b.score - a.score);

      const paceBowlers = scoredList
        .filter(p => p.role === 'Bowler' && p.bowl_type === 'pace' && p.career_stats.wickets > 0)
        .sort((a, b) => b.score - a.score);
      const spinBowlers = scoredList
        .filter(p => p.role === 'Bowler' && p.bowl_type === 'spin' && p.career_stats.wickets > 0)
        .sort((a, b) => b.score - a.score);

      const paceARs = scoredList.filter(p => p.role === 'All-Rounder' && p.bowl_type === 'pace').sort((a, b) => b.score - a.score);
      const spinARs = scoredList.filter(p => p.role === 'All-Rounder' && p.bowl_type === 'spin').sort((a, b) => b.score - a.score);

      const selected = [];

      // 1. Pick 4 Batsmen
      const pickedBatsmen = batsmen.slice(0, 4);
      selected.push(...pickedBatsmen);

      // 2. Pick 1 Wicketkeeper
      if (keepers.length > 0) {
        selected.push(keepers[0]);
      } else {
        const pickedNames = new Set(selected.map(p => p.name));
        const wkFb = batsmen.filter(p => !pickedNames.has(p.name)).slice(0, 1)
          .map(p => ({ ...p, role: 'Wicketkeeper (Fallback)' }));
        selected.push(...wkFb);
      }

      // 3. Pick 1 All-Rounder (prefer pitch match)
      const prefARs = comp.arPref === 'spin' ? spinARs : paceARs;
      const altARs = comp.arPref === 'spin' ? paceARs : spinARs;
      if (prefARs.length > 0) {
        selected.push(prefARs[0]);
      } else if (altARs.length > 0) {
        selected.push(altARs[0]);
      } else {
        const pickedNames = new Set(selected.map(p => p.name));
        const arFb = scoredList.filter(p => !pickedNames.has(p.name)).sort((a, b) => b.score - a.score).slice(0, 1)
          .map(p => ({ ...p, role: 'All-Rounder (Fallback)' }));
        selected.push(...arFb);
      }

      // 4. Pick 5 Bowlers with pitch-type composition
      const bowlerNames = new Set(selected.map(p => p.name));
      const availPace = paceBowlers.filter(p => !bowlerNames.has(p.name));
      const availSpin = spinBowlers.filter(p => !bowlerNames.has(p.name));

      const pickedPace = availPace.slice(0, comp.pace);
      const pickedSpin = availSpin.slice(0, comp.spin);
      selected.push(...pickedPace, ...pickedSpin);

      // Fill shortfall
      const totalBowlers = pickedPace.length + pickedSpin.length;
      if (totalBowlers < 5) {
        const allNames = new Set(selected.map(p => p.name));
        const remaining = scoredList
          .filter(p => p.role === 'Bowler' && p.career_stats.wickets > 0 && !allNames.has(p.name))
          .sort((a, b) => b.score - a.score);
        selected.push(...remaining.slice(0, 5 - totalBowlers));
      }

      // Final fallback if still under 11
      if (selected.length < 11) {
        const currentNames = new Set(selected.map(p => p.name));
        const extra = scoredList.filter(p => !currentNames.has(p.name)).sort((a, b) => b.score - a.score);
        selected.push(...extra.slice(0, 11 - selected.length));
      }

      const eleven = selected.slice(0, 11);

      // ── Batting Order Organization (#1 to #11) ──────────────────────
      const batOrderNames = [
        'Opening Batsman', 'Opening Batsman', 'Top-Order Anchor',
        'Middle-Order Power', 'Wicketkeeper / Finisher', 'Finisher / All-Rounder',
        'Bowling All-Rounder', 'Strike Bowler / Spinner', 'Frontline Pacer',
        'Fast Bowler', 'Tailend Bowler'
      ];

      // Sort eleven into a realistic cricket batting lineup:
      // Keepers & Batsmen first, All-rounders middle, Bowlers last
      eleven.sort((a, b) => {
        const rank = (role) => {
          if (role === 'Batsman') return 1;
          if (role.includes('Wicketkeeper')) return 2;
          if (role.includes('All-Rounder')) return 3;
          return 4;
        };
        const rA = rank(a.role);
        const rB = rank(b.role);
        if (rA !== rB) return rA - rB;
        return b.score - a.score;
      });

      // Assign Captain & Vice Captain
      const topScorers = [...eleven].sort((a, b) => b.score - a.score);
      const capName = topScorers[0] ? topScorers[0].name : '';
      const vcName = topScorers[1] ? topScorers[1].name : '';

      const finalEleven = eleven.map((p, idx) => ({
        ...p,
        batting_order: idx + 1,
        order_title: batOrderNames[idx] || `Player #${idx + 1}`,
        is_captain: p.name === capName,
        is_vice_captain: p.name === vcName,
      }));

      // Find Impact Player / 12th Man (next best player)
      const elevenNames = new Set(finalEleven.map(p => p.name));
      const impactCandidate = scoredList.filter(p => !elevenNames.has(p.name)).sort((a, b) => b.score - a.score)[0] || null;

      // Projected team score calculation
      let teamProjectedRuns = finalEleven.slice(0, 7).reduce((acc, p) => acc + (p.predicted_runs.value || 20), 0) + 24;
      teamProjectedRuns = Math.round(teamProjectedRuns * 0.92);

      return {
        team: teamName,
        players: finalEleven,
        captain: capName,
        vice_captain: vcName,
        impact_player: impactCandidate ? {
          name: impactCandidate.name,
          role: impactCandidate.role,
          score: impactCandidate.score,
          venue_stats: impactCandidate.venue_stats,
          predicted_runs: impactCandidate.predicted_runs,
          predicted_wickets: impactCandidate.predicted_wickets,
          reason: 'Tactical replacement based on match state and pitch condition.'
        } : null,
        projected_total: {
          predicted: teamProjectedRuns,
          min: Math.max(120, teamProjectedRuns - 16),
          max: teamProjectedRuns + 18,
        }
      };
    }

    function buildXIForTeam(teamName) {
      let roster = team_rosters[teamName] || [];
      const isAllTime = teamName.includes('All-Time') || teamName === 'All-Time XI';
      if (isAllTime) {
        const allPlayersSet = new Set();
        Object.values(team_rosters).forEach(rList => rList.forEach(p => allPlayersSet.add(p)));
        roster = Array.from(allPlayersSet);
      }
      const scored = scoreRoster(roster);
      return buildXIFromScored(scored, teamName);
    }

    // Single Team or H2H Clash
    const primaryXI = buildXIForTeam(team);
    let secondaryXI = null;
    let dreamXI = null;

    if (team2 && team2 !== team && team_rosters[team2]) {
      secondaryXI = buildXIForTeam(team2);

      // Build Combined Dream XI across both teams for this venue
      const roster1 = team_rosters[team] || [];
      const roster2 = team_rosters[team2] || [];
      const combinedRoster = Array.from(new Set([...roster1, ...roster2]));
      const scoredCombined = scoreRoster(combinedRoster);
      dreamXI = buildXIFromScored(scoredCombined, `${team} vs ${team2} Combined Dream XI`);
    }

    const result = {
      team,
      team2: team2 || null,
      venue: isAllVenues ? 'All Venues (Career)' : venue,
      pitch_type: pitchType,
      venue_avg_score: venueAvgScore,
      toss_bat_first_win_rate: tossBatFirstWinRate,
      bowling_composition: comp,
      xi: primaryXI,
      xi_team2: secondaryXI,
      dream_xi: dreamXI,
    };

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result));
    return;
  }

  // ─── Live Match Prediction Simulator API ──────────────────────────────
  if (pathname === '/api/live-simulate') {
    const chasingTeam = reqUrl.searchParams.get('chasing_team') || 'Royal Challengers Bangalore';
    const defendingTeam = reqUrl.searchParams.get('defending_team') || 'Chennai Super Kings';
    const venue = reqUrl.searchParams.get('venue') || 'M Chinnaswamy Stadium (Bengaluru)';
    const target = parseInt(reqUrl.searchParams.get('target') || '185', 10);
    const score = parseInt(reqUrl.searchParams.get('current_score') || '112', 10);
    const wickets = parseInt(reqUrl.searchParams.get('wickets_lost') || '3', 10);
    const oversInput = parseFloat(reqUrl.searchParams.get('overs_completed') || '12.0');

    // Parse overs (e.g. 12.4 means 12 overs + 4 balls)
    const wholeOvers = Math.floor(oversInput);
    const ballsInOver = Math.min(5, Math.round((oversInput - wholeOvers) * 10));
    const totalLegalBalls = wholeOvers * 6 + ballsInOver;
    const ballsRemaining = Math.max(0, 120 - totalLegalBalls);
    const completedOversDec = totalLegalBalls / 6.0;

    const runsNeeded = Math.max(0, target - score);
    const wicketsInHand = Math.max(0, 10 - wickets);

    const crr = completedOversDec > 0 ? (score / completedOversDec) : 0;
    const rrr = ballsRemaining > 0 ? (runsNeeded / (ballsRemaining / 6.0)) : (runsNeeded === 0 ? 0 : 36);
    const rrrMinusCrr = rrr - crr;

    // Phase identification
    let phase = 'middle';
    if (completedOversDec <= 6) phase = 'powerplay';
    else if (completedOversDec >= 15) phase = 'death';

    // Model Accuracy Benchmark from live_model_metrics.json
    const phaseAccuracy = {
      powerplay: { accuracy: 69.7, roc_auc: 0.804 },
      middle:    { accuracy: 78.5, roc_auc: 0.873 },
      death:     { accuracy: 89.3, roc_auc: 0.964 }
    }[phase];

    // Elo difference
    const dataset = getDataset();
    const eloRatings = (dataset && dataset.current_elo_ratings) || {};
    const eloChasing = eloRatings[chasingTeam] || 1500;
    const eloDefending = eloRatings[defendingTeam] || 1500;
    const eloDiff = eloChasing - eloDefending;

    // Pressure Index
    const chasePressure = Math.max(0, Math.min(100, Math.round(
      (rrr * 5.5) + (wickets * 4.2) - (completedOversDec * 2.0) + (rrrMinusCrr * 3.0)
    )));

    let pressureLevel = 'Moderate';
    if (chasePressure < 35) pressureLevel = 'Low Pressure (Cruising)';
    else if (chasePressure < 65) pressureLevel = 'Moderate Pressure';
    else if (chasePressure < 85) pressureLevel = 'High Pressure (Tight)';
    else pressureLevel = 'Extreme Pressure (Critical)';

    // Live Win Probability Calculation:
    // Calibrated against live_win_probability ensemble model
    let chaseProb = 50.0;

    if (score >= target) {
      chaseProb = 100.0;
    } else if (wickets >= 10 || (ballsRemaining <= 0 && runsNeeded > 0)) {
      chaseProb = 0.0;
    } else if (runsNeeded > ballsRemaining * 6) {
      chaseProb = 0.0;
    } else {
      // Base logit formula derived from trained live features
      let logit = (wicketsInHand - 4.5) * 0.42
                - (rrr - 8.2) * 0.38
                + (crr - 7.5) * 0.16
                - (rrrMinusCrr) * 0.22
                + (eloDiff * 0.0015);

      if (phase === 'powerplay') {
        logit = logit * 0.65; // High uncertainty early
      } else if (phase === 'death') {
        // In death overs, runs remaining per ball and wickets dominate
        const runsPerBall = runsNeeded / Math.max(1, ballsRemaining);
        if (runsPerBall > 2.5 && wicketsInHand < 4) logit -= 2.0;
        else if (runsPerBall <= 1.0 && wicketsInHand >= 3) logit += 2.2;
      }

      chaseProb = 100.0 / (1.0 + Math.exp(-logit));
      chaseProb = Math.min(99.5, Math.max(0.5, chaseProb));
    }

    const defendProb = Math.round((100.0 - chaseProb) * 10) / 10;
    chaseProb = Math.round(chaseProb * 10) / 10;

    // Projected Final Score
    const projectedRuns = Math.round(score + (crr * (ballsRemaining / 6.0)));

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      chasing_team: chasingTeam,
      defending_team: defendingTeam,
      venue,
      target,
      current_score: score,
      wickets_lost: wickets,
      overs_completed: oversInput,
      balls_bowled: totalLegalBalls,
      balls_remaining: ballsRemaining,
      runs_needed: runsNeeded,
      wickets_in_hand: wicketsInHand,
      crr: Math.round(crr * 100) / 100,
      rrr: Math.round(rrr * 100) / 100,
      rrr_minus_crr: Math.round(rrrMinusCrr * 100) / 100,
      chase_win_prob: chaseProb,
      defend_win_prob: defendProb,
      pressure_index: chasePressure,
      pressure_level: pressureLevel,
      phase,
      model_benchmark: phaseAccuracy,
      projected_final_score: projectedRuns,
      elo_ratings: { chasing: eloChasing, defending: eloDefending, diff: eloDiff }
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
