/**
 * app.js
 * Master Application Controller for Cricket Intelligence Platform.
 * Manages state, API fetching, real-time match simulation, search, and dynamic DOM rendering.
 */

window.APP = {
  data: null,
  activeSection: 'overview-section',
  leaderboardTab: 'batters',
  leaderboardPage: 1,
  leaderboardItemsPerPage: 15,
  selectedPlayer: null,
  
  init: async function() {
    console.log("⚡ Initializing IPL Intelligence Platform...");
    this.setupNavigation();
    this.setupGlobalSearch();
    await this.loadData();
    if (this.data) {
      this.renderAll();
      this.setupEventListeners();
    }
  },

  loadData: async function() {
    // 1. Try to use inline window.DATA if pre-embedded
    if (window.DATA && window.DATA.generated_from_matches) {
      console.log("Found embedded DATA bundle.");
      this.data = window.DATA;
      return;
    }

    // 2. Fetch from API endpoint /api/data
    try {
      const res = await fetch('/api/data');
      if (res.ok) {
        this.data = await res.json();
        window.DATA = this.data;
        console.log("Loaded dataset bundle via /api/data.");
        return;
      }
    } catch (e) {
      console.warn("Could not fetch /api/data:", e);
    }
  },

  renderAll: function() {
    if (!this.data) return;

    this.renderHeaderMetrics();
    this.renderOverviewSection();
    this.renderEloSection();
    this.renderSimulatorSection();
    this.renderPlayerScoutSection();
    this.renderLeaderboardsTable();
    this.renderVenueSection();
    this.renderAuctionSection();
    this.renderMLSection();
  },

  setupNavigation: function() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = item.getAttribute('data-target');
        if (!targetId) return;

        // Update active nav link
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        // Hide all sections, show target
        document.querySelectorAll('.app-section').forEach(sec => sec.style.display = 'none');
        const targetSec = document.getElementById(targetId);
        if (targetSec) {
          targetSec.style.display = 'block';
          targetSec.classList.add('animate-fade-in');
          this.activeSection = targetId;
        }

        // Close mobile drawer if open
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) sidebar.classList.remove('mobile-open');
      });
    });

    // Mobile nav toggle button
    const mobileToggle = document.getElementById('mobileNavToggle');
    if (mobileToggle) {
      mobileToggle.addEventListener('click', () => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) sidebar.classList.toggle('mobile-open');
      });
    }
  },

  renderHeaderMetrics: function() {
    const d = this.data;
    if (!d) return;

    const matchesEl = document.getElementById('hdrMatches');
    const seasonsEl = document.getElementById('hdrSeasons');
    const playersEl = document.getElementById('hdrPlayers');

    if (matchesEl) matchesEl.innerText = (d.generated_from_matches || 1212).toLocaleString();
    if (seasonsEl) seasonsEl.innerText = (d.seasons ? d.seasons.length : 19);
    if (playersEl) playersEl.innerText = (d.all_players ? d.all_players.length : 792);
  },

  renderOverviewSection: function() {
    const d = this.data;
    if (!d) return;

    // Stat Cards
    const totalMatchesEl = document.getElementById('statTotalMatches');
    const topEloTeamEl = document.getElementById('statTopEloTeam');
    const topEloRatingEl = document.getElementById('statTopEloRating');

    if (totalMatchesEl) totalMatchesEl.innerText = (d.generated_from_matches || 1212);

    if (d.current_elo_ratings) {
      const topTeam = Object.keys(d.current_elo_ratings)[0];
      const topRating = d.current_elo_ratings[topTeam];
      if (topEloTeamEl) topEloTeamEl.innerText = topTeam;
      if (topEloRatingEl) topEloRatingEl.innerText = `${topRating.toFixed(1)} Elo`;
    }
  },

  renderEloSection: function() {
    const d = this.data;
    if (!d || !d.elo_history) return;

    // Render Trajectory Chart
    if (window.renderEloTrajectoryChart) {
      window.renderEloTrajectoryChart('eloChartCanvas', d.elo_history);
    }

    // Render Standings Grid
    const gridEl = document.getElementById('eloStandingsGrid');
    if (!gridEl || !d.current_elo_ratings) return;

    gridEl.innerHTML = '';
    const ratings = d.current_elo_ratings;
    const summaryMap = {};
    if (d.team_summary) {
      d.team_summary.forEach(t => summaryMap[t.team] = t);
    }

    Object.entries(ratings).forEach(([team, rating], idx) => {
      const info = window.getTeamInfo(team);
      const badgeSVG = window.renderTeamBadgeSVG(team, 36);
      const summ = summaryMap[team] || { matches_played: 0, matches_won: 0, win_pct: 0 };

      const card = document.createElement('div');
      card.className = 'card-panel stat-widget glow-emerald';
      card.innerHTML = `
        <div style="display:flex; align-items:center; gap:14px;">
          <div>${badgeSVG}</div>
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="rank-badge ${idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : ''}">${idx + 1}</span>
              <strong style="font-family:var(--font-title); font-size:16px;">${team}</strong>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
              Played ${summ.matches_played} | Won ${summ.matches_won} (${summ.win_pct}% Win Rate)
            </div>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-family:var(--font-mono); font-size:22px; font-weight:800; color:var(--accent-emerald);">
            ${rating.toFixed(1)}
          </div>
          <div style="font-size:11px; color:var(--text-dim); text-transform:uppercase;">Elo Power Rating</div>
        </div>
      `;
      gridEl.appendChild(card);
    });
  },

  renderSimulatorSection: function() {
    const d = this.data;
    if (!d) return;

    const selectA = document.getElementById('simTeamASelect');
    const selectB = document.getElementById('simTeamBSelect');
    const selectVenue = document.getElementById('simVenueSelect');

    if (!selectA || !selectB) return;

    const teams = Object.keys(d.current_elo_ratings || {});
    selectA.innerHTML = '';
    selectB.innerHTML = '';

    teams.forEach((t, i) => {
      const optA = new Option(t, t, false, i === 0);
      const optB = new Option(t, t, false, i === 1);
      selectA.add(optA);
      selectB.add(optB);
    });

    if (d.venue_stats && selectVenue) {
      selectVenue.innerHTML = '<option value="">All Venues (Neutral)</option>';
      d.venue_stats.forEach(v => {
        selectVenue.add(new Option(`${v.venue} (${v.matches} matches)`, v.venue));
      });
    }

    this.updateSimulation();
  },

  updateSimulation: function() {
    const d = this.data;
    if (!d) return;

    const teamA = document.getElementById('simTeamASelect').value;
    const teamB = document.getElementById('simTeamBSelect').value;
    const tossWinner = document.getElementById('simTossWinnerSelect') ? document.getElementById('simTossWinnerSelect').value : 'Team A';
    const tossDecision = document.getElementById('simTossDecisionSelect') ? document.getElementById('simTossDecisionSelect').value : 'field';

    // Render team badges
    const badgeAContainer = document.getElementById('simBadgeA');
    const badgeBContainer = document.getElementById('simBadgeB');
    if (badgeAContainer) badgeAContainer.innerHTML = window.renderTeamBadgeSVG(teamA, 64);
    if (badgeBContainer) badgeBContainer.innerHTML = window.renderTeamBadgeSVG(teamB, 64);

    // Calculate probabilities based on Elo and toss factor
    const eloA = (d.current_elo_ratings && d.current_elo_ratings[teamA]) || 1500;
    const eloB = (d.current_elo_ratings && d.current_elo_ratings[teamB]) || 1500;

    // Check pairwise matrix
    let matrixEntry = null;
    if (d.win_probability_matrix) {
      matrixEntry = d.win_probability_matrix.find(m => m.team1 === teamA && m.team2 === teamB);
    }

    let probA = matrixEntry ? matrixEntry.team1_win_prob : (100 / (1 + Math.pow(10, (eloB - eloA) / 400)));
    
    // Toss adjustment (~3.5% boost for fielding toss winner)
    const isTossA = (tossWinner === 'Team A');
    if (isTossA) {
      probA += (tossDecision === 'field' ? 3.5 : 1.5);
    } else {
      probA -= (tossDecision === 'field' ? 3.5 : 1.5);
    }

    probA = Math.min(95, Math.max(5, probA));
    const probB = 100 - probA;

    // Update DOM
    const probValA = document.getElementById('simProbValA');
    const probValB = document.getElementById('simProbValB');
    const barA = document.getElementById('simBarFillA');
    const barB = document.getElementById('simBarFillB');

    if (probValA) probValA.innerText = `${probA.toFixed(1)}%`;
    if (probValB) probValB.innerText = `${probB.toFixed(1)}%`;
    if (barA) barA.style.width = `${probA}%`;
    if (barB) barB.style.width = `${probB}%`;

    // Update Meta Details
    const metaEloA = document.getElementById('simMetaEloA');
    const metaEloB = document.getElementById('simMetaEloB');
    if (metaEloA) metaEloA.innerText = eloA.toFixed(1);
    if (metaEloB) metaEloB.innerText = eloB.toFixed(1);
  },

  renderPlayerScoutSection: function() {
    const d = this.data;
    if (!d || !d.all_players || !d.all_players.length) return;

    // 1. Populate Master Dropdown Select Bar (792 Players)
    const masterSelect = document.getElementById('scoutMasterPlayerSelect');
    if (masterSelect) {
      masterSelect.innerHTML = '';
      const sortedPlayers = [...d.all_players].sort((a, b) => (a.PlayerName || '').localeCompare(b.PlayerName || ''));
      sortedPlayers.forEach(p => {
        const teamShort = p.Teams ? p.Teams.split(',')[0] : '';
        const opt = new Option(`${p.PlayerName} (${teamShort})`, p.PlayerName);
        masterSelect.add(opt);
      });

      masterSelect.addEventListener('change', (e) => {
        const target = d.all_players.find(p => p.PlayerName === e.target.value);
        if (target) this.selectPlayerProfile(target);
      });
    }

    // 2. Quick Player Preset Pills Click Listeners
    const quickBtns = document.querySelectorAll('.quick-player-btn');
    quickBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        quickBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const pName = btn.getAttribute('data-player');
        const target = d.all_players.find(p => p.PlayerName === pName || (p.PlayerName && p.PlayerName.includes(pName)));
        if (target) this.selectPlayerProfile(target);
      });
    });

    // 3. Dedicated Player Scouting Search Input Autocomplete
    const scoutInput = document.getElementById('scoutPlayerSearchInput');
    const scoutResults = document.getElementById('scoutSearchAutocomplete');

    if (scoutInput && scoutResults) {
      scoutInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        scoutResults.innerHTML = '';
        if (!q) {
          scoutResults.style.display = 'none';
          return;
        }

        const matches = d.all_players.filter(p => p.PlayerName && p.PlayerName.toLowerCase().includes(q)).slice(0, 10);
        if (!matches.length) {
          scoutResults.style.display = 'none';
          return;
        }

        scoutResults.style.display = 'block';
        matches.forEach(p => {
          const div = document.createElement('div');
          div.className = 'autocomplete-item';
          div.innerHTML = `
            <div>
              <strong style="color:var(--text-main);">${p.PlayerName}</strong>
              <div style="font-size:12px; color:var(--text-muted);">${p.Teams || ''}</div>
            </div>
            <div style="font-family:var(--font-mono); font-size:12px; color:var(--accent-emerald); font-weight:700;">
              ${(p.batting_impact_score || 0).toFixed(1)} Bat Impact
            </div>
          `;
          div.addEventListener('click', () => {
            scoutInput.value = p.PlayerName;
            scoutResults.style.display = 'none';
            this.selectPlayerProfile(p);
          });
          scoutResults.appendChild(div);
        });
      });

      // Hide autocomplete on click outside
      document.addEventListener('click', (e) => {
        if (!scoutInput.contains(e.target) && !scoutResults.contains(e.target)) {
          scoutResults.style.display = 'none';
        }
      });
    }

    // Populate Orange Cap Season Select
    const orangeSelect = document.getElementById('orangeCapSeasonSelect');
    if (orangeSelect && d.seasons) {
      orangeSelect.innerHTML = '';
      [...d.seasons].reverse().forEach(s => {
        orangeSelect.add(new Option(`Season ${s}`, s));
      });
      orangeSelect.addEventListener('change', (e) => {
        if (window.renderOrangeCapChart && d.player_season_trends) {
          window.renderOrangeCapChart('orangeCapChartCanvas', d.player_season_trends.top_run_scorers_by_season, e.target.value);
        }
      });
      const initialSeason = d.seasons[d.seasons.length - 2] || d.seasons[0];
      orangeSelect.value = initialSeason;
      if (window.renderOrangeCapChart && d.player_season_trends) {
        window.renderOrangeCapChart('orangeCapChartCanvas', d.player_season_trends.top_run_scorers_by_season, initialSeason);
      }
    }

    // Populate Purple Cap Season Select
    const purpleSelect = document.getElementById('purpleCapSeasonSelect');
    if (purpleSelect && d.seasons) {
      purpleSelect.innerHTML = '';
      [...d.seasons].reverse().forEach(s => {
        purpleSelect.add(new Option(`Season ${s}`, s));
      });
      purpleSelect.addEventListener('change', (e) => {
        if (window.renderPurpleCapChart && d.player_season_trends) {
          window.renderPurpleCapChart('purpleCapChartCanvas', d.player_season_trends.top_wicket_takers_by_season, e.target.value);
        }
      });
      const initialSeason = d.seasons[d.seasons.length - 2] || d.seasons[0];
      purpleSelect.value = initialSeason;
      if (window.renderPurpleCapChart && d.player_season_trends) {
        window.renderPurpleCapChart('purpleCapChartCanvas', d.player_season_trends.top_wicket_takers_by_season, initialSeason);
      }
    }

    // Render Batter & Bowler Scatter Plots
    if (window.renderBatterScatterChart && d.leaderboards) {
      window.renderBatterScatterChart('batterScatterCanvas', d.leaderboards.top_batters || []);
    }
    if (window.renderBowlerScatterChart && d.leaderboards) {
      window.renderBowlerScatterChart('bowlerScatterCanvas', d.leaderboards.top_bowlers || []);
    }

    // Default select Virat Kohli or first player
    const defaultPlayer = d.all_players.find(p => p.PlayerName === 'V Kohli' || p.PlayerName === 'MS Dhoni') || d.all_players[0];
    this.selectPlayerProfile(defaultPlayer);
  },

  selectPlayerProfile: function(player) {
    if (!player) return;
    this.selectedPlayer = player;

    // Synchronize Master Dropdown Select
    const masterSelect = document.getElementById('scoutMasterPlayerSelect');
    if (masterSelect) masterSelect.value = player.PlayerName;

    // Header info
    const nameEl = document.getElementById('scoutPlayerName');
    const teamsEl = document.getElementById('scoutPlayerTeams');
    const stylesEl = document.getElementById('scoutPlayerStyles');
    const spanEl = document.getElementById('scoutPlayerSpan');
    const avatarEl = document.getElementById('scoutPlayerAvatar');
    const seasonTableTitle = document.getElementById('scoutSeasonTablePlayerName');
    const ovrEl = document.getElementById('scoutPlayerOVR');

    if (nameEl) nameEl.innerText = player.PlayerName;
    if (teamsEl) teamsEl.innerText = player.Teams || 'IPL Franchise';
    if (stylesEl) stylesEl.innerText = `${player.bat_style || 'Batting'} | ${player.bowl_style || 'Bowling'}`;
    if (spanEl) spanEl.innerText = `Career Span: ${player.Span || 'N/A'}`;
    if (seasonTableTitle) seasonTableTitle.innerText = player.PlayerName;

    if (ovrEl) {
      const batImp = player.batting_impact_score || 0;
      const bowlImp = player.bowling_impact_score || 0;
      const allrImp = (player.allrounder_index || 0) * 0.85;
      const maxImp = Math.max(batImp, bowlImp, allrImp);
      const ovr = Math.min(99, Math.max(68, Math.round(68 + (maxImp / 80) * 31)));
      ovrEl.innerText = `${ovr} OVR`;
    }

    if (avatarEl) {
      const initials = player.PlayerName.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
      avatarEl.innerText = initials;
    }

    // Impact Stat Cards
    const batImpactEl = document.getElementById('scoutBatImpact');
    const bowlImpactEl = document.getElementById('scoutBowlImpact');
    const allrIndexEl = document.getElementById('scoutAllrIndex');
    const matchesEl = document.getElementById('scoutMatches');

    if (batImpactEl) batImpactEl.innerText = player.batting_impact_score ? player.batting_impact_score.toFixed(1) : '—';
    if (bowlImpactEl) bowlImpactEl.innerText = player.bowling_impact_score ? player.bowling_impact_score.toFixed(1) : '—';
    if (allrIndexEl) allrIndexEl.innerText = player.allrounder_index ? player.allrounder_index.toFixed(1) : '—';
    if (matchesEl) matchesEl.innerText = player.Matches || 0;

    // Batter Milestone Stats Strip
    const runsEl = document.getElementById('batStatRuns');
    const hsEl = document.getElementById('batStatHS');
    const avgSREl = document.getElementById('batStatAvgSR');
    const innEl = document.getElementById('batStatInnings');
    const milestonesEl = document.getElementById('batStatMilestones');
    const ducksEl = document.getElementById('batStatDucks');
    const boundEl = document.getElementById('batStatBoundaries');
    const boundPctEl = document.getElementById('batStatBoundaryPct');

    const fours = player.Fours || 0;
    const sixes = player.Sixes || 0;
    const runs = player.Runs || 0;
    const boundaryRuns = (fours * 4) + (sixes * 6);
    const bPct = runs > 0 ? ((boundaryRuns / runs) * 100).toFixed(1) : '0';

    if (runsEl) runsEl.innerText = runs.toLocaleString();
    if (hsEl) hsEl.innerText = player.HighestScore || '—';
    if (avgSREl) avgSREl.innerText = `${(player.BattingAverage || 0).toFixed(1)} | ${(player.StrikeRate || 0).toFixed(1)}`;
    if (innEl) innEl.innerText = player.Innings || 0;
    if (milestonesEl) milestonesEl.innerText = `${player.Hundreds || 0} | ${player.Fifties || 0}`;
    if (ducksEl) ducksEl.innerText = player.Ducks || 0;
    if (boundEl) boundEl.innerText = `${fours} | ${sixes}`;
    if (boundPctEl) boundPctEl.innerText = `${bPct}%`;

    // Bowler Milestone Stats Strip
    const wktEl = document.getElementById('bowlStatWickets');
    const bestEl = document.getElementById('bowlStatBest');
    const econAvgEl = document.getElementById('bowlStatEconAvg');
    const bowlInnEl = document.getElementById('bowlStatInnings');
    const haulsEl = document.getElementById('bowlStatHauls');
    const maidensEl = document.getElementById('bowlStatMaidens');
    const srOversEl = document.getElementById('bowlStatSROvers');
    const runsConcEl = document.getElementById('bowlStatRunsConceded');

    if (wktEl) wktEl.innerText = player.Wickets || 0;
    if (bestEl) bestEl.innerText = player.BestBowlingInnings || '—';
    if (econAvgEl) econAvgEl.innerText = `${(player.Economy || 0).toFixed(2)} | ${(player.BowlingAverage || 0).toFixed(1)}`;
    if (bowlInnEl) bowlInnEl.innerText = player.BowlInnings || 0;
    if (haulsEl) haulsEl.innerText = `${player.FourWickets || 0} | ${player.FiveWickets || 0}`;
    if (maidensEl) maidensEl.innerText = player.Maidens || 0;
    if (srOversEl) srOversEl.innerText = `${(player.BowlingStrikeRate || 0).toFixed(1)} | ${(player.Overs || 0).toFixed(1)}`;
    if (runsConcEl) runsConcEl.innerText = (player.RunsConceded || 0).toLocaleString();

    // Render Personal 6-axis Radar Chart
    if (window.renderPlayerRadarChart) {
      window.renderPlayerRadarChart('scoutRadarCanvas', player);
    }

    // Render Personal Boundary Breakdown Chart
    if (window.renderBatterBoundaryBreakdownChart) {
      window.renderBatterBoundaryBreakdownChart('batterBoundaryPieCanvas', player);
    }

    // Render Personal Bowler Wicket Breakdown Chart
    if (window.renderBowlerWicketEconomyChart) {
      window.renderBowlerWicketEconomyChart('bowlerWicketPieCanvas', player);
    }

    // Dynamic Trajectory Chart: Bowler vs Batter
    const trajTitle = document.getElementById('scoutTrajectoryTitle');
    const isBowler = (player.Wickets || 0) > 15 || ((player.bowling_impact_score || 0) > (player.batting_impact_score || 0));

    if (isBowler && window.renderBowlerSeasonTrajectoryChart && this.data && this.data.player_season_trends) {
      if (trajTitle) trajTitle.innerText = "Career Season Form Trajectory (Bowling)";
      window.renderBowlerSeasonTrajectoryChart('batterSeasonTrajectoryCanvas', this.data.player_season_trends.career_trajectories || [], player.PlayerName);
    } else if (window.renderBatterSeasonTrajectoryChart && this.data && this.data.player_season_trends) {
      if (trajTitle) trajTitle.innerText = "Career Season Form Trajectory (Batting)";
      window.renderBatterSeasonTrajectoryChart('batterSeasonTrajectoryCanvas', this.data.player_season_trends.career_trajectories || [], player.PlayerName);
    }

    // Render Personal Season-by-Season Table
    const personalTbody = document.getElementById('scoutPersonalSeasonTbody');
    if (personalTbody && this.data && this.data.player_season_trends) {
      personalTbody.innerHTML = '';
      const trajectories = (this.data.player_season_trends.career_trajectories || [])
        .filter(r => r.player_name === player.PlayerName || r.player_name === player.player_full_name)
        .sort((a, b) => String(a.season).localeCompare(String(b.season)));

      if (trajectories.length) {
        trajectories.forEach(row => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><strong style="color:var(--accent-gold); font-family:var(--font-mono);">${row.season}</strong></td>
            <td><span style="color:var(--accent-cyan);">${row.team_name || 'Franchise'}</span></td>
            <td>${row.matches || 0}</td>
            <td style="color:var(--accent-emerald); font-weight:700;">${row.runs || 0}</td>
            <td>${row.batting_avg ? row.batting_avg.toFixed(2) : '—'}</td>
            <td>${row.strike_rate ? row.strike_rate.toFixed(1) : '—'}</td>
            <td style="color:var(--accent-crimson); font-weight:700;">${row.wickets || 0}</td>
            <td>${row.economy ? row.economy.toFixed(2) : '—'}</td>
          `;
          personalTbody.appendChild(tr);
        });
      } else {
        personalTbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-dim); padding:20px;">No individual season records found for ${player.PlayerName}.</td></tr>`;
      }
    }
  },

  renderLeaderboardsTable: function() {
    const d = this.data;
    if (!d || !d.leaderboards) return;

    const tbody = document.getElementById('leaderboardTbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    let list = [];
    if (this.leaderboardTab === 'batters') list = d.leaderboards.top_batters || [];
    else if (this.leaderboardTab === 'bowlers') list = d.leaderboards.top_bowlers || [];
    else if (this.leaderboardTab === 'allrounders') list = d.leaderboards.top_allrounders || [];
    else list = d.all_players || [];

    // Filter by search
    const filterInput = document.getElementById('leaderboardSearchInput');
    const query = filterInput ? filterInput.value.toLowerCase().trim() : '';
    if (query) {
      list = list.filter(p => p.PlayerName && p.PlayerName.toLowerCase().includes(query));
    }

    // Paginate
    const startIdx = (this.leaderboardPage - 1) * this.leaderboardItemsPerPage;
    const paginated = list.slice(startIdx, startIdx + this.leaderboardItemsPerPage);

    paginated.forEach((p, idx) => {
      const overallRank = startIdx + idx + 1;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="rank-badge ${overallRank === 1 ? 'rank-1' : overallRank === 2 ? 'rank-2' : overallRank === 3 ? 'rank-3' : ''}">${overallRank}</span></td>
        <td><strong style="color:var(--text-main); font-family:var(--font-title);">${p.PlayerName}</strong></td>
        <td><span style="font-size:12px; color:var(--accent-emerald);">${(p.Teams || '').split(',')[0]}</span></td>
        <td><strong>${p.Matches || 0}</strong></td>
        <td style="color:var(--accent-emerald); font-weight:700;">${p.Runs || 0}</td>
        <td>${p.BattingAverage ? p.BattingAverage.toFixed(2) : '—'}</td>
        <td>${p.StrikeRate ? p.StrikeRate.toFixed(1) : '—'}</td>
        <td style="color:var(--accent-crimson); font-weight:700;">${p.Wickets || 0}</td>
        <td>${p.Economy ? p.Economy.toFixed(2) : '—'}</td>
        <td style="font-family:var(--font-mono); font-weight:800; color:var(--accent-gold);">
          ${(p.batting_impact_score || p.bowling_impact_score || p.allrounder_index || 0).toFixed(1)}
        </td>
      `;
      tr.addEventListener('click', () => {
        this.selectPlayerProfile(p);
        // Jump to player scout section
        const scoutNav = document.querySelector('[data-target="player-section"]');
        if (scoutNav) scoutNav.click();
      });
      tbody.appendChild(tr);
    });
  },

  renderVenueSection: function() {
    const d = this.data;
    if (!d || !d.venue_stats) return;

    const grid = document.getElementById('venueCardsGrid');
    if (!grid) return;

    grid.innerHTML = '';

    d.venue_stats.forEach(v => {
      const card = document.createElement('div');
      card.className = 'card-panel glow-cyan';
      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <h4 style="font-family:var(--font-title); font-size:18px; font-weight:800;">${v.venue}</h4>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Official IPL Stadium Profile</div>
          </div>
          <div style="background:rgba(0,229,255,0.1); border:1px solid var(--accent-cyan); color:var(--accent-cyan); padding:4px 10px; border-radius:var(--radius-full); font-family:var(--font-mono); font-size:12px; font-weight:700;">
            ${v.matches} Matches
          </div>
        </div>
      `;
      grid.appendChild(card);
    });
  },

  renderAuctionSection: function() {
    const d = this.data;
    if (!d || !d.auction_trends) return;

    const topBuysGrid = document.getElementById('auctionTopBuysGrid');
    if (!topBuysGrid || !d.auction_trends.top_buys) return;

    topBuysGrid.innerHTML = '';
    d.auction_trends.top_buys.slice(0, 6).forEach(buy => {
      const card = document.createElement('div');
      card.className = 'card-panel stat-widget gold';
      card.innerHTML = `
        <div>
          <div class="stat-label">${buy.team} (${buy.year})</div>
          <div class="stat-value" style="color:var(--accent-gold); font-size:22px;">${buy.player}</div>
          <div class="stat-sub">Price: ₹${buy.price_cr} Cr (${buy.role})</div>
        </div>
      `;
      topBuysGrid.appendChild(card);
    });
  },

  renderMLSection: function() {
    const d = this.data;
    if (!d) return;

    if (window.renderFeatureImportanceChart && d.feature_importance) {
      window.renderFeatureImportanceChart('featureImpCanvas', d.feature_importance);
    }
    if (window.renderModelComparisonChart) {
      window.renderModelComparisonChart('modelCompCanvas', d.cv_results);
    }
  },

  setupGlobalSearch: function() {
    const searchModal = document.getElementById('searchModal');
    const modalInput = document.getElementById('modalSearchInput');
    const searchTrigger = document.getElementById('headerSearchTrigger');
    const modalResults = document.getElementById('modalResultsList');

    const openSearch = () => {
      if (searchModal) searchModal.style.display = 'flex';
      if (modalInput) modalInput.focus();
    };

    const closeSearch = () => {
      if (searchModal) searchModal.style.display = 'none';
    };

    if (searchTrigger) searchTrigger.addEventListener('click', openSearch);

    // Ctrl + K keyboard shortcut
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        openSearch();
      }
      if (e.key === 'Escape') closeSearch();
    });

    if (searchModal) {
      searchModal.addEventListener('click', (e) => {
        if (e.target === searchModal) closeSearch();
      });
    }

    if (modalInput && modalResults) {
      modalInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        modalResults.innerHTML = '';
        if (!q || !this.data || !this.data.all_players) return;

        const matches = this.data.all_players.filter(p => p.PlayerName && p.PlayerName.toLowerCase().includes(q)).slice(0, 10);
        matches.forEach(p => {
          const div = document.createElement('div');
          div.className = 'autocomplete-item';
          div.innerHTML = `
            <div>
              <strong style="color:var(--text-main);">${p.PlayerName}</strong>
              <div style="font-size:12px; color:var(--text-muted);">${p.Teams || ''}</div>
            </div>
            <div style="font-family:var(--font-mono); font-size:12px; color:var(--accent-emerald); font-weight:700;">
              Score: ${(p.batting_impact_score || p.bowling_impact_score || 0).toFixed(1)}
            </div>
          `;
          div.addEventListener('click', () => {
            closeSearch();
            this.selectPlayerProfile(p);
            const scoutNav = document.querySelector('[data-target="player-section"]');
            if (scoutNav) scoutNav.click();
          });
          modalResults.appendChild(div);
        });
      });
    }

    this.setupBattleModal();
  },

  setupBattleModal: function() {
    const battleModal = document.getElementById('battleModal');
    const battleTrigger = document.getElementById('headerBattleTrigger');
    const closeBtn = document.getElementById('closeBattleModalBtn');
    const selectA = document.getElementById('battleSelectA');
    const selectB = document.getElementById('battleSelectB');

    if (!battleModal || !selectA || !selectB) return;

    const openModal = () => {
      battleModal.style.display = 'flex';
      if (!selectA.options.length && this.data && this.data.all_players) {
        const sorted = [...this.data.all_players].sort((a, b) => a.PlayerName.localeCompare(b.PlayerName));
        sorted.forEach(p => {
          selectA.add(new Option(p.PlayerName, p.PlayerName));
          selectB.add(new Option(p.PlayerName, p.PlayerName));
        });
        selectA.value = 'V Kohli';
        selectB.value = 'MS Dhoni';
      }
      this.updateBattleComparison();
    };

    const closeModal = () => {
      battleModal.style.display = 'none';
    };

    if (battleTrigger) battleTrigger.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    battleModal.addEventListener('click', (e) => {
      if (e.target === battleModal) closeModal();
    });

    selectA.addEventListener('change', () => this.updateBattleComparison());
    selectB.addEventListener('change', () => this.updateBattleComparison());
  },

  updateBattleComparison: function() {
    if (!this.data || !this.data.all_players) return;
    const nameA = document.getElementById('battleSelectA').value;
    const nameB = document.getElementById('battleSelectB').value;

    const pA = this.data.all_players.find(p => p.PlayerName === nameA) || this.data.all_players[0];
    const pB = this.data.all_players.find(p => p.PlayerName === nameB) || this.data.all_players[1];

    const nA = document.getElementById('battleNameA');
    const nB = document.getElementById('battleNameB');
    const tA = document.getElementById('battleTeamA');
    const tB = document.getElementById('battleTeamB');

    if (nA) nA.innerText = pA.PlayerName;
    if (nB) nB.innerText = pB.PlayerName;
    if (tA) tA.innerText = pA.Teams || 'Franchise';
    if (tB) tB.innerText = pB.Teams || 'Franchise';

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    setVal('bValBatImpactA', (pA.batting_impact_score || 0).toFixed(1));
    setVal('bValBatImpactB', (pB.batting_impact_score || 0).toFixed(1));

    setVal('bValRunsA', (pA.Runs || 0).toLocaleString());
    setVal('bValRunsB', (pB.Runs || 0).toLocaleString());

    setVal('bValAvgA', (pA.BattingAverage || 0).toFixed(1));
    setVal('bValAvgB', (pB.BattingAverage || 0).toFixed(1));

    setVal('bValSRA', (pA.StrikeRate || 0).toFixed(1));
    setVal('bValSRB', (pB.StrikeRate || 0).toFixed(1));

    setVal('bValWktsA', (pA.Wickets || 0).toString());
    setVal('bValWktsB', (pB.Wickets || 0).toString());
  },

  setupEventListeners: function() {
    // Simulator controls
    const simA = document.getElementById('simTeamASelect');
    const simB = document.getElementById('simTeamBSelect');
    if (simA) simA.addEventListener('change', () => this.updateSimulation());
    if (simB) simB.addEventListener('change', () => this.updateSimulation());

    // Leaderboards search & tabs
    const lbSearch = document.getElementById('leaderboardSearchInput');
    if (lbSearch) {
      lbSearch.addEventListener('input', () => {
        this.leaderboardPage = 1;
        this.renderLeaderboardsTable();
      });
    }

    const tabBtns = document.querySelectorAll('.leaderboard-tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.leaderboardTab = btn.getAttribute('data-tab');
        this.leaderboardPage = 1;
        this.renderLeaderboardsTable();
      });
    });
  }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.APP.init();
});
