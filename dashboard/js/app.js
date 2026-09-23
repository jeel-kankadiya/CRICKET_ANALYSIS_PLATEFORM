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
    // 1. Try to use inline window.DATA if pre-embedded and complete with all_players
    if (window.DATA && window.DATA.generated_from_matches && window.DATA.all_players && window.DATA.all_players.length > 0) {
      console.log("Found complete embedded DATA bundle.");
      this.data = window.DATA;
      return;
    }

    if (typeof DATA !== 'undefined' && DATA && DATA.generated_from_matches && DATA.all_players && DATA.all_players.length > 0) {
      console.log("Found complete inline const DATA bundle.");
      this.data = DATA;
      window.DATA = DATA;
      return;
    }

    // 2. Fetch from API endpoint /api/data
    try {
      const res = await fetch('/api/data');
      if (res.ok) {
        const json = await res.json();
        if (json && json.all_players && json.all_players.length > 0) {
          this.data = json;
          window.DATA = json;
          console.log("Loaded full dataset bundle via /api/data:", json.all_players.length, "players");
          return;
        }
      }
    } catch (e) {
      console.warn("Could not fetch /api/data:", e);
    }

    // 3. Fallback to direct static JSON file fetch /outputs/dashboard_data.json
    try {
      const res = await fetch('/outputs/dashboard_data.json');
      if (res.ok) {
        const json = await res.json();
        this.data = json;
        window.DATA = json;
        console.log("Loaded full dataset bundle via /outputs/dashboard_data.json:", json.all_players.length, "players");
        return;
      }
    } catch (e) {
      console.error("Could not fetch /outputs/dashboard_data.json fallback:", e);
    }
  },

  // Track which sections have been rendered to avoid duplicate renders
  _renderedSections: {},

  renderAll: function() {
    if (!this.data) return;

    this.renderHeaderMetrics();
    this.renderOverviewSection();

    // Only render the currently visible section's charts immediately.
    // Other sections are rendered lazily when navigated to,
    // because Chart.js cannot size canvases inside display:none containers.
    this._renderedSections['overview-section'] = true;

    // Pre-render non-chart data (dropdowns, tables, event listeners)
    this.renderSimulatorSection();
    this.renderPlayerScoutSection();
    this.renderLeaderboardsTable();
    this.renderVenueSection();
    this.renderAuctionSection();
    this.renderPlayingXISection();
  },

  renderSectionCharts: function(sectionId) {
    if (!this.data) return;
    if (this._renderedSections[sectionId]) {
      // Section already rendered — just resize existing charts
      this.resizeAllChartsInSection(sectionId);
      return;
    }
    this._renderedSections[sectionId] = true;

    switch(sectionId) {
      case 'elo-section':
        this.renderEloSection();
        break;
      case 'player-section':
        this.reRenderPlayerCharts();
        break;
      case 'venue-section':
        if (window.renderPitchTypeComparisonChart && this.data.venue_intelligence) {
          window.renderPitchTypeComparisonChart('pitchTypeChartCanvas', this.data.venue_intelligence.pitch_type_summary || []);
        }
        break;
      case 'model-section':
        this.renderMLSection();
        break;
    }
  },

  resizeAllChartsInSection: function(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    const canvases = section.querySelectorAll('canvas');
    canvases.forEach(canvas => {
      const chartInstance = window.chartInstances[canvas.id];
      if (chartInstance) {
        chartInstance.resize();
      }
    });
  },

  reRenderPlayerCharts: function() {
    if (this.selectedPlayer) {
      this.selectPlayerProfile(this.selectedPlayer);
    }
    // Re-render league benchmark charts
    if (window.renderBatterScatterChart && this.data.leaderboards) {
      window.renderBatterScatterChart('batterScatterCanvas', this.data.leaderboards.top_batters || []);
    }
    if (window.renderBowlerScatterChart && this.data.leaderboards) {
      window.renderBowlerScatterChart('bowlerScatterCanvas', this.data.leaderboards.top_bowlers || []);
    }
    // Re-render Orange/Purple cap charts
    const orangeSelect = document.getElementById('orangeCapSeasonSelect');
    if (orangeSelect && window.renderOrangeCapChart && this.data.player_season_trends) {
      window.renderOrangeCapChart('orangeCapChartCanvas', this.data.player_season_trends.top_run_scorers_by_season, orangeSelect.value);
    }
    const purpleSelect = document.getElementById('purpleCapSeasonSelect');
    if (purpleSelect && window.renderPurpleCapChart && this.data.player_season_trends) {
      window.renderPurpleCapChart('purpleCapChartCanvas', this.data.player_season_trends.top_wicket_takers_by_season, purpleSelect.value);
    }
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

          // Render charts for the newly visible section
          // (Chart.js needs the container to be visible to calculate dimensions)
          requestAnimationFrame(() => {
            this.renderSectionCharts(targetId);
          });
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
          <div style="font-family:var(--font-mono); font-size:22px; font-weight:800; color:var(--accent-teal);">
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
    if (!d || !document.getElementById('simTeamASelect')) return;

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
      if (masterSelect.options.length === 0) {
        masterSelect.innerHTML = '';
        const sortedPlayers = [...d.all_players].sort((a, b) => (a.PlayerName || '').localeCompare(b.PlayerName || ''));
        sortedPlayers.forEach(p => {
          const teamShort = p.Teams ? p.Teams.split(',')[0] : '';
          const opt = new Option(`${p.PlayerName} (${teamShort})`, p.PlayerName);
          masterSelect.add(opt);
        });
      }

      if (!masterSelect.hasAttribute('data-init')) {
        masterSelect.setAttribute('data-init', 'true');
        masterSelect.addEventListener('change', (e) => {
          const target = d.all_players.find(p => p.PlayerName === e.target.value);
          if (target) this.selectPlayerProfile(target);
        });
      }
    }

    // 2. Quick Player Preset Pills Click Listeners
    const quickBtns = document.querySelectorAll('.quick-player-btn');
    quickBtns.forEach(btn => {
      if (!btn.hasAttribute('data-init')) {
        btn.setAttribute('data-init', 'true');
        btn.addEventListener('click', () => {
          quickBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const pName = btn.getAttribute('data-player');
          const target = d.all_players.find(p => p.PlayerName === pName || (p.PlayerName && p.PlayerName.includes(pName)));
          if (target) this.selectPlayerProfile(target);
        });
      }
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
            <td><strong style="color:var(--accent-amber); font-family:var(--font-mono);">${row.season}</strong></td>
            <td><span style="color:var(--accent-sky);">${row.team_name || 'Franchise'}</span></td>
            <td>${row.matches || 0}</td>
            <td style="color:var(--accent-teal); font-weight:700;">${row.runs || 0}</td>
            <td>${row.batting_avg ? row.batting_avg.toFixed(2) : '—'}</td>
            <td>${row.strike_rate ? row.strike_rate.toFixed(1) : '—'}</td>
            <td style="color:var(--accent-rose); font-weight:700;">${row.wickets || 0}</td>
            <td>${row.economy ? row.economy.toFixed(2) : '—'}</td>
          `;
          personalTbody.appendChild(tr);
        });
      } else {
        personalTbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-dim); padding:20px;">No individual season records found for ${player.PlayerName}.</td></tr>`;
      }
    }

    // Render Personal Stadium-by-Stadium Performance Table
    this.renderPlayerVenueTable(player.PlayerName);
  },

  renderPlayerVenueTable: function(playerName) {
    const titleName = document.getElementById('scoutVenueTablePlayerName');
    if (titleName) titleName.innerText = playerName;

    const tbody = document.getElementById('scoutPersonalVenueTbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const d = this.data;
    if (!d || !d.player_venue_stats) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:20px;">No stadium statistics available.</td></tr>`;
      return;
    }

    let stats = d.player_venue_stats[playerName] || [];
    if (!stats.length) {
      const key = Object.keys(d.player_venue_stats).find(k => k.toLowerCase() === playerName.toLowerCase());
      if (key) stats = d.player_venue_stats[key];
    }

    const searchInput = document.getElementById('scoutVenueSearchInput');
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    if (query) {
      stats = stats.filter(s => s.venue.toLowerCase().includes(query));
    }

    if (!stats.length) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:20px;">No matching venue stats for "${playerName}".</td></tr>`;
      return;
    }

    stats.forEach(row => {
      const tr = document.createElement('tr');
      const hsHighlight = row.hs >= 100 ? 'color:var(--accent-amber); font-weight:800;' : row.hs >= 50 ? 'color:var(--accent-teal); font-weight:700;' : '';
      tr.innerHTML = `
        <td><strong style="color:var(--text-main); font-family:var(--font-title);">${row.venue}</strong></td>
        <td>${row.innings || 0}</td>
        <td style="color:var(--accent-teal); font-weight:800; font-family:var(--font-mono); font-size:14px;">${(row.runs || 0).toLocaleString()}</td>
        <td><strong>${row.avg ? row.avg.toFixed(1) : '—'}</strong></td>
        <td>${row.sr ? row.sr.toFixed(1) : '—'}</td>
        <td><span style="${hsHighlight}">${row.hs || 0}</span></td>
        <td><span style="color:var(--accent-amber); font-weight:700;">${row.hundreds || 0}</span> / <span style="font-weight:600;">${row.fifties || 0}</span></td>
        <td><span>${row.fours || 0}</span> / <span style="color:var(--accent-rose); font-weight:700;">${row.sixes || 0}</span></td>
        <td style="color:var(--accent-rose); font-weight:700;">${row.wickets > 0 ? row.wickets : '—'}</td>
      `;
      tbody.appendChild(tr);
    });
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
        <td><span style="font-size:12px; color:var(--accent-teal);">${(p.Teams || '').split(',')[0]}</span></td>
        <td><strong>${p.Matches || 0}</strong></td>
        <td style="color:var(--accent-teal); font-weight:700;">${p.Runs || 0}</td>
        <td>${p.BattingAverage ? p.BattingAverage.toFixed(2) : '—'}</td>
        <td>${p.StrikeRate ? p.StrikeRate.toFixed(1) : '—'}</td>
        <td style="color:var(--accent-rose); font-weight:700;">${p.Wickets || 0}</td>
        <td>${p.Economy ? p.Economy.toFixed(2) : '—'}</td>
        <td style="font-family:var(--font-mono); font-weight:800; color:var(--accent-amber);">
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
    if (!d) return;

    // Use venue_intelligence data (richer) with fallback to venue_stats
    const vi = d.venue_intelligence || {};
    const venueProfiles = vi.venue_profiles || [];
    const pitchTypeSummary = vi.pitch_type_summary || [];
    const topBattingVenues = vi.top_batting_venues || [];
    const topChasingVenues = vi.top_chasing_venues || [];

    // Store for filtering
    this.venueProfiles = venueProfiles;
    this.venueActiveFilter = 'all';
    this.venueSearchQuery = '';
    this.selectedVenue = null;

    // Render venue cards
    this.renderVenueCards();

    // Setup search & filter
    this.setupVenueFilters();

    // Setup interactive Player vs Specific Stadium analyzer tool
    this.initPlayerVenueAnalyzer();

    // Render pitch type analysis
    this.renderPitchTypeAnalysis(pitchTypeSummary);

    // Render top venues leaderboards
    this.renderTopVenuesLeaderboards(topBattingVenues, topChasingVenues);

    // Render pitch type chart
    if (window.renderPitchTypeComparisonChart && pitchTypeSummary.length) {
      window.renderPitchTypeComparisonChart('pitchTypeChartCanvas', pitchTypeSummary);
    }

    // Close button for detail panel
    const closeBtn = document.getElementById('venueDetailClose');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.closeVenueDetail();
      });
    }
  },

  getPitchBadgeClass: function(pitchType) {
    if (!pitchType) return 'pitch-badge--balanced';
    const pt = pitchType.toLowerCase();
    if (pt.includes('batting') || pt.includes('paradise')) return 'pitch-badge--batting';
    if (pt.includes('seam')) return 'pitch-badge--seam';
    if (pt.includes('spin')) return 'pitch-badge--spin';
    if (pt.includes('slow') || pt.includes('low')) return 'pitch-badge--slow';
    return 'pitch-badge--balanced';
  },

  renderVenueCards: function() {
    const grid = document.getElementById('venueCardsGrid');
    if (!grid) return;

    grid.innerHTML = '';
    const profiles = this.getFilteredVenues();

    if (!profiles.length) {
      grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-dim); font-size:14px;">No venues match your search criteria.</div>`;
      return;
    }

    profiles.forEach(v => {
      const card = document.createElement('div');
      card.className = 'venue-card' + (this.selectedVenue && this.selectedVenue.venue === v.venue ? ' selected' : '');

      const batWinPct = v.bat_first_win_pct || 50;
      const avgScore = v.avg_first_innings_score || 0;
      const capacity = v.capacity || 0;
      const dewFactor = v.dew_factor || 0;
      const boundarySize = v.boundary_size_m || 0;
      const matches = v.total_matches_hosted || 0;

      card.innerHTML = `
        <div class="venue-card-header">
          <div>
            <div class="venue-card-title">${v.venue}</div>
            <div class="venue-card-city">${v.city || 'India'}</div>
          </div>
          <div class="venue-card-matches">${matches} Matches</div>
        </div>
        <span class="pitch-badge ${this.getPitchBadgeClass(v.pitch_type)}">${v.pitch_type || 'Unknown'}</span>
        <div class="venue-card-stats">
          <div class="venue-card-stat">
            <span class="venue-card-stat-label">Avg 1st Inn.</span>
            <span class="venue-card-stat-value" style="color:var(--accent-teal)">${avgScore}</span>
          </div>
          <div class="venue-card-stat">
            <span class="venue-card-stat-label">Bat 1st Win%</span>
            <span class="venue-card-stat-value" style="color:var(--accent-amber)">${batWinPct}%</span>
          </div>
          <div class="venue-card-stat">
            <span class="venue-card-stat-label">Dew Factor</span>
            <span class="venue-card-stat-value" style="color:var(--accent-sky)">${dewFactor}</span>
          </div>
          <div class="venue-card-stat">
            <span class="venue-card-stat-label">Boundary</span>
            <span class="venue-card-stat-value">${boundarySize}m</span>
          </div>
        </div>
      `;

      card.addEventListener('click', () => {
        this.openVenueDetail(v);
        // Mark selected card
        document.querySelectorAll('.venue-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
      });

      grid.appendChild(card);
    });
  },

  getFilteredVenues: function() {
    let profiles = this.venueProfiles || [];
    const filter = this.venueActiveFilter || 'all';
    const query = (this.venueSearchQuery || '').toLowerCase().trim();

    if (filter !== 'all') {
      profiles = profiles.filter(v => v.pitch_type === filter);
    }

    if (query) {
      profiles = profiles.filter(v =>
        (v.venue && v.venue.toLowerCase().includes(query)) ||
        (v.city && v.city.toLowerCase().includes(query))
      );
    }

    return profiles;
  },

  setupVenueFilters: function() {
    // Search input
    const searchInput = document.getElementById('venueSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.venueSearchQuery = e.target.value;
        this.renderVenueCards();
      });
    }

    // Filter pills
    const pills = document.querySelectorAll('.venue-filter-pill');
    pills.forEach(pill => {
      pill.addEventListener('click', () => {
        pills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        this.venueActiveFilter = pill.getAttribute('data-filter');
        this.renderVenueCards();
      });
    });
  },

  openVenueDetail: function(venue) {
    this.selectedVenue = venue;
    const panel = document.getElementById('venueDetailPanel');
    if (!panel) return;

    // Show panel
    panel.classList.add('visible');

    // Name & City
    const nameEl = document.getElementById('venueDetailName');
    const cityEl = document.getElementById('venueDetailCity');
    if (nameEl) nameEl.innerText = venue.venue;
    if (cityEl) cityEl.innerText = `${venue.city || 'India'} • Capacity: ${(venue.capacity || 0).toLocaleString()} • ${venue.pitch_type || 'Unknown'} Pitch`;

    // Metrics strip
    const metricsGrid = document.getElementById('venueDetailMetrics');
    if (metricsGrid) {
      const metrics = [
        { icon: '🏟️', value: (venue.capacity || 0).toLocaleString(), label: 'Capacity' },
        { icon: '🏏', value: venue.avg_first_innings_score || '—', label: 'Avg 1st Inn Score' },
        { icon: '📊', value: `${venue.bat_first_win_pct || 0}%`, label: 'Bat First Win %' },
        { icon: '💧', value: venue.dew_factor || 0, label: 'Dew Factor' },
        { icon: '📏', value: `${venue.boundary_size_m || 0}m`, label: 'Boundary Size' },
      ];
      metricsGrid.innerHTML = metrics.map(m => `
        <div class="venue-metric-card">
          <div class="venue-metric-icon">${m.icon}</div>
          <div class="venue-metric-value">${m.value}</div>
          <div class="venue-metric-label">${m.label}</div>
        </div>
      `).join('');
    }

    // Win split bar
    const batPct = venue.bat_first_win_pct || 50;
    const chasePct = (100 - batPct).toFixed(1);
    const batBar = document.getElementById('venueWinSplitBat');
    const chaseBar = document.getElementById('venueWinSplitChase');
    const batLabel = document.getElementById('venueWinBatLabel');
    const chaseLabel = document.getElementById('venueWinChaseLabel');

    if (batBar) batBar.style.width = `${batPct}%`;
    if (chaseBar) chaseBar.style.width = `${chasePct}%`;
    if (batLabel) batLabel.innerText = `🏏 Bat First: ${batPct}%`;
    if (chaseLabel) chaseLabel.innerText = `🎯 Chase: ${chasePct}%`;

    // Dew factor meter
    const dewFill = document.getElementById('venueDetailDewFill');
    const dewValue = document.getElementById('venueDetailDewValue');
    const dewPct = ((venue.dew_factor || 0) * 100);
    if (dewFill) dewFill.style.width = `${dewPct}%`;
    if (dewValue) dewValue.innerText = (venue.dew_factor || 0).toFixed(2);

    // Boundary size meter (scale: 55m-80m)
    const bFill = document.getElementById('venueDetailBoundaryFill');
    const bValue = document.getElementById('venueDetailBoundaryValue');
    const boundary = venue.boundary_size_m || 65;
    const bPct = Math.min(100, Math.max(0, ((boundary - 55) / 25) * 100));
    if (bFill) bFill.style.width = `${bPct}%`;
    if (bValue) bValue.innerText = `${boundary}m`;

    // Render All-Time Top Scored Players at this Stadium
    const topTbody = document.getElementById('venueDetailTopBattersTbody');
    if (topTbody && this.data && this.data.player_venue_stats) {
      topTbody.innerHTML = '';
      const vName = venue.venue ? venue.venue.toLowerCase().trim() : '';
      const vCity = venue.city ? venue.city.toLowerCase().trim() : '';

      const allVenueStats = [];
      Object.entries(this.data.player_venue_stats).forEach(([pName, vList]) => {
        vList.forEach(vEntry => {
          const vEntryName = vEntry.venue.toLowerCase();
          if (vEntryName.includes(vName) || (vCity && vEntryName.includes(vCity))) {
            allVenueStats.push({
              playerName: pName,
              ...vEntry
            });
          }
        });
      });

      // Sort by runs descending
      allVenueStats.sort((a, b) => b.runs - a.runs);

      // Deduplicate by player name
      const uniqueBatters = [];
      const seenPlayers = new Set();
      for (const s of allVenueStats) {
        if (!seenPlayers.has(s.playerName)) {
          seenPlayers.add(s.playerName);
          uniqueBatters.push(s);
        }
      }

      const topBatters = uniqueBatters.slice(0, 8);

      if (topBatters.length) {
        topBatters.forEach((row, idx) => {
          const tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          const rankBadge = idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : '';
          tr.innerHTML = `
            <td><span class="rank-badge ${rankBadge}">${idx + 1}</span></td>
            <td><strong style="color:var(--text-main); font-family:var(--font-title);">${row.playerName}</strong></td>
            <td>${row.innings || 0}</td>
            <td style="color:var(--accent-teal); font-weight:800; font-family:var(--font-mono); font-size:14px;">${(row.runs || 0).toLocaleString()}</td>
            <td><strong>${row.avg ? row.avg.toFixed(1) : '—'}</strong></td>
            <td>${row.sr ? row.sr.toFixed(1) : '—'}</td>
            <td><span style="color:var(--accent-amber); font-weight:700;">${row.hs || 0}</span></td>
            <td><span style="color:var(--accent-amber); font-weight:700;">${row.hundreds || 0}</span> / <span>${row.fifties || 0}</span></td>
          `;
          tr.addEventListener('click', () => {
            const pObj = (this.data.all_players || []).find(p => p.PlayerName === row.playerName);
            if (pObj) {
              this.selectPlayerProfile(pObj);
              const scoutNav = document.querySelector('[data-target="player-section"]');
              if (scoutNav) scoutNav.click();
            }
          });
          topTbody.appendChild(tr);
        });
      } else {
        topTbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:16px;">No batter records found for this stadium.</td></tr>`;
      }
    }

    // Scroll to panel
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  closeVenueDetail: function() {
    this.selectedVenue = null;
    const panel = document.getElementById('venueDetailPanel');
    if (panel) panel.classList.remove('visible');
    document.querySelectorAll('.venue-card').forEach(c => c.classList.remove('selected'));
  },

  initPlayerVenueAnalyzer: function() {
    const playerSelect = document.getElementById('pvVenuePlayerSelect');
    const stadiumSelect = document.getElementById('pvVenueStadiumSelect');
    if (!playerSelect || !stadiumSelect || !this.data) return;

    // Populate Players dropdown if empty
    if (playerSelect.options.length === 0 && this.data.all_players) {
      const players = [...this.data.all_players].sort((a, b) => (b.Runs || 0) - (a.Runs || 0));
      players.forEach(p => {
        playerSelect.add(new Option(`${p.PlayerName} (${(p.Teams || '').split(',')[0]})`, p.PlayerName, false, p.PlayerName === 'V Kohli'));
      });
    }

    // Attach listeners once
    if (!playerSelect.hasAttribute('data-pv-init')) {
      playerSelect.setAttribute('data-pv-init', 'true');
      playerSelect.addEventListener('change', () => {
        this.updateStadiumOptionsForSelectedPlayer();
        this.renderPlayerVenueAnalysisOutput();
      });
      stadiumSelect.addEventListener('change', () => this.renderPlayerVenueAnalysisOutput());
    }

    this.updateStadiumOptionsForSelectedPlayer();
    this.renderPlayerVenueAnalysisOutput();
  },

  updateStadiumOptionsForSelectedPlayer: function() {
    const playerSelect = document.getElementById('pvVenuePlayerSelect');
    const stadiumSelect = document.getElementById('pvVenueStadiumSelect');
    if (!playerSelect || !stadiumSelect || !this.data) return;

    const pName = playerSelect.value || 'V Kohli';
    const currentVal = stadiumSelect.value;
    stadiumSelect.innerHTML = '';

    const pVenueList = (this.data.player_venue_stats && this.data.player_venue_stats[pName]) || [];

    if (pVenueList.length > 0) {
      pVenueList.forEach((v, idx) => {
        const label = `${v.venue} (${v.runs.toLocaleString()} runs${v.wickets > 0 ? ', ' + v.wickets + ' wkts' : ''})`;
        const opt = new Option(label, v.venue);
        stadiumSelect.add(opt);
      });
      // Try to preserve currentVal if it exists in list, else pick first
      const exists = pVenueList.some(v => v.venue === currentVal);
      if (exists) {
        stadiumSelect.value = currentVal;
      } else {
        stadiumSelect.selectedIndex = 0;
      }
    } else {
      // Fallback: list all venues
      const allStadiumsSet = new Set();
      if (this.data.player_venue_stats) {
        Object.values(this.data.player_venue_stats).forEach(vList => {
          vList.forEach(v => allStadiumsSet.add(v.venue));
        });
      }
      Array.from(allStadiumsSet).sort().forEach(s => {
        stadiumSelect.add(new Option(s, s));
      });
    }
  },

  renderPlayerVenueAnalysisOutput: function() {
    const outputContainer = document.getElementById('pvVenueAnalysisOutput');
    const playerSelect = document.getElementById('pvVenuePlayerSelect');
    const stadiumSelect = document.getElementById('pvVenueStadiumSelect');
    if (!outputContainer || !playerSelect || !stadiumSelect || !this.data) return;

    const pName = playerSelect.value || 'V Kohli';
    const sName = stadiumSelect.value || (stadiumSelect.options[0] ? stadiumSelect.options[0].value : 'Eden Gardens (Kolkata)');

    const pObj = (this.data.all_players || []).find(p => p.PlayerName === pName) || { PlayerName: pName };
    const pVenueList = (this.data.player_venue_stats && this.data.player_venue_stats[pName]) || [];
    
    // Find record for selected stadium
    const stat = pVenueList.find(v => v.venue === sName || v.venue.toLowerCase().includes(sName.toLowerCase())) || null;

    if (!stat) {
      outputContainer.innerHTML = `
        <div style="padding:24px; text-align:center; background:var(--bg-card); border:1px dashed var(--border-color); border-radius:var(--radius-md);">
          <span style="font-size:32px; display:block; margin-bottom:8px;">🏟️</span>
          <h4 style="font-family:var(--font-title); font-size:16px; font-weight:700; color:var(--text-main); margin:0;">No Recorded Matches at ${sName} for ${pName}</h4>
          <p style="font-size:12px; color:var(--text-muted); margin-top:6px;">Select another stadium or player to inspect head-to-head performance.</p>
        </div>
      `;
      return;
    }

    // Calculations & Comparisons vs Career
    const careerBatAvg = pObj.BattingAverage || 0;
    const careerSR = pObj.StrikeRate || 0;
    const avgDiff = stat.avg - careerBatAvg;
    const avgDiffPct = careerBatAvg > 0 ? ((avgDiff / careerBatAvg) * 100).toFixed(1) : '0';
    const avgBadgeClass = avgDiff >= 0 ? 'color:var(--accent-teal); background:rgba(13,148,136,0.1); border:1px solid rgba(13,148,136,0.25);' : 'color:var(--accent-rose); background:rgba(225,29,72,0.1); border:1px solid rgba(225,29,72,0.25);';
    const avgSign = avgDiff >= 0 ? '+' : '';

    const srDiff = stat.sr - careerSR;
    const srSign = srDiff >= 0 ? '+' : '';

    // Dominance Verdict Tag
    let verdictTag = '⚖️ Steady Surface Performance';
    if (stat.runs >= 400 || (stat.avg >= 45 && stat.innings >= 5)) {
      verdictTag = '🔥 Prime Fortress & Hunting Ground';
    } else if (avgDiff >= 5.0) {
      verdictTag = '📈 High Efficiency Ground (+Above Career Avg)';
    } else if (stat.wickets >= 10) {
      verdictTag = '⚡ Bowling Stronghold';
    }

    outputContainer.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-md); padding:20px; box-shadow:var(--shadow-sm);">
        
        <!-- Header Strip -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid var(--border-color);">
          <div style="display:flex; align-items:center; gap:12px;">
            <div style="width:48px; height:48px; border-radius:50%; background:var(--accent-teal); color:#fff; display:flex; align-items:center; justify-content:center; font-family:var(--font-title); font-weight:900; font-size:18px;">
              ${pName.split(' ').map(n=>n[0]).join('')}
            </div>
            <div>
              <h3 style="font-family:var(--font-title); font-size:20px; font-weight:800; color:var(--text-main); margin:0;">${pName} <span style="font-size:14px; color:var(--text-muted); font-weight:400;">at</span> ${sName}</h3>
              <span style="font-size:12px; color:var(--text-muted); font-family:var(--font-mono);">${stat.innings} Batting Innings • ${stat.balls} Balls Faced • ${(pObj.Teams || '').split(',')[0]}</span>
            </div>
          </div>

          <div style="padding:6px 14px; border-radius:20px; font-family:var(--font-mono); font-size:12px; font-weight:800; ${avgBadgeClass}">
            ${verdictTag}
          </div>
        </div>

        <!-- 4 Stat Widgets Grid -->
        <div class="grid-4" style="margin-bottom:20px;">
          <div class="stat-widget" style="padding:14px 16px;">
            <div class="stat-info">
              <span class="stat-label">Runs Scored</span>
              <span class="stat-value" style="color:var(--accent-teal); font-size:24px;">${stat.runs.toLocaleString()}</span>
              <span class="stat-sub">Highest Score: <strong style="color:var(--accent-amber);">${stat.hs}</strong></span>
            </div>
          </div>

          <div class="stat-widget cyan" style="padding:14px 16px;">
            <div class="stat-info">
              <span class="stat-label">Batting Average</span>
              <span class="stat-value" style="font-size:22px;">${stat.avg.toFixed(1)}</span>
              <span class="stat-sub">Career Avg: <strong>${careerBatAvg.toFixed(1)}</strong> (${avgSign}${avgDiff.toFixed(1)})</span>
            </div>
          </div>

          <div class="stat-widget gold" style="padding:14px 16px;">
            <div class="stat-info">
              <span class="stat-label">Strike Rate & Milestones</span>
              <span class="stat-value" style="color:var(--accent-amber); font-size:22px;">${stat.sr.toFixed(1)}</span>
              <span class="stat-sub">100s: <strong>${stat.hundreds}</strong> | 50s: <strong>${stat.fifties}</strong></span>
            </div>
          </div>

          <div class="stat-widget crimson" style="padding:14px 16px;">
            <div class="stat-info">
              <span class="stat-label">Boundaries & Bowling</span>
              <span class="stat-value" style="color:var(--accent-rose); font-size:22px;">${stat.fours} 4s / ${stat.sixes} 6s</span>
              <span class="stat-sub">Wickets: <strong style="color:var(--accent-rose);">${stat.wickets > 0 ? stat.wickets : '—'}</strong> (${stat.economy > 0 ? stat.economy.toFixed(2) + ' Econ' : '—'})</span>
            </div>
          </div>
        </div>

        <!-- Side-by-Side Comparison Row -->
        <div style="background:var(--bg-panel); border:1px solid var(--border-color); border-radius:var(--radius-md); padding:14px 18px;">
          <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:10px;">
            📊 Head-to-Head Delta: ${pName} at ${sName} vs Overall Career Average
          </div>
          <div style="display:flex; justify-content:space-around; align-items:center; flex-wrap:wrap; gap:16px;">
            <div style="text-align:center;">
              <span style="font-size:11px; color:var(--text-muted); display:block;">Batting Average Delta</span>
              <strong style="font-size:16px; font-family:var(--font-mono); color:${avgDiff >= 0 ? 'var(--accent-teal)' : 'var(--accent-rose)'};">${stat.avg.toFixed(1)} vs ${careerBatAvg.toFixed(1)}</strong>
              <span style="font-size:10px; display:block; font-weight:700; color:${avgDiff >= 0 ? 'var(--accent-teal)' : 'var(--accent-rose)'};">${avgSign}${avgDiffPct}% Difference</span>
            </div>

            <div style="height:30px; width:1px; background:var(--border-color);"></div>

            <div style="text-align:center;">
              <span style="font-size:11px; color:var(--text-muted); display:block;">Strike Rate Delta</span>
              <strong style="font-size:16px; font-family:var(--font-mono); color:var(--accent-sky);">${stat.sr.toFixed(1)} vs ${careerSR.toFixed(1)}</strong>
              <span style="font-size:10px; display:block; color:${srDiff >= 0 ? 'var(--accent-sky)' : 'var(--text-muted)'};">${srSign}${srDiff.toFixed(1)} SR Points</span>
            </div>

            <div style="height:30px; width:1px; background:var(--border-color);"></div>

            <div style="text-align:center;">
              <span style="font-size:11px; color:var(--text-muted); display:block;">Boundary Ball %</span>
              <strong style="font-size:16px; font-family:var(--font-mono); color:var(--accent-amber);">${stat.balls > 0 ? (((stat.fours + stat.sixes)/stat.balls)*100).toFixed(1) : 0}%</strong>
              <span style="font-size:10px; display:block; color:var(--text-muted);">${stat.fours + stat.sixes} boundaries in ${stat.balls} balls</span>
            </div>
          </div>
        </div>

      </div>
    `;
  },

  renderPitchTypeAnalysis: function(pitchTypeSummary) {
    // Avg Score rows
    const scoreContainer = document.getElementById('pitchTypeScoreRows');
    if (scoreContainer && pitchTypeSummary.length) {
      const maxScore = Math.max(...pitchTypeSummary.map(p => p.avg_first_innings_score || 0));
      const pitchColors = {
        'Balanced': '#0EA5E9',
        'Batting Paradise': '#D97706',
        'Seam Friendly': '#0D9488',
        'Spin Friendly': '#8B5CF6',
        'Slow & Low': '#E11D48'
      };

      scoreContainer.innerHTML = pitchTypeSummary.map(p => {
        const pct = maxScore > 0 ? ((p.avg_first_innings_score || 0) / maxScore * 100) : 0;
        const color = pitchColors[p.pitch_type] || '#00E5FF';
        return `
          <div class="pitch-type-row">
            <span class="pitch-type-name">${p.pitch_type}</span>
            <div class="pitch-type-bar-container">
              <div class="pitch-type-bar-fill" style="width:${pct}%; background:${color}"></div>
            </div>
            <span class="pitch-type-value" style="color:${color}">${p.avg_first_innings_score || 0}</span>
          </div>
        `;
      }).join('');
    }

    // Win % rows
    const winContainer = document.getElementById('pitchTypeWinRows');
    if (winContainer && pitchTypeSummary.length) {
      const pitchColors = {
        'Balanced': '#00E5FF',
        'Batting Paradise': '#FFB800',
        'Seam Friendly': '#00FF9D',
        'Spin Friendly': '#A855F7',
        'Slow & Low': '#FF3B5C'
      };

      winContainer.innerHTML = pitchTypeSummary.map(p => {
        const pct = p.avg_bat_first_win_pct || 0;
        const color = pitchColors[p.pitch_type] || '#00E5FF';
        return `
          <div class="pitch-type-row">
            <span class="pitch-type-name">${p.pitch_type}</span>
            <div class="pitch-type-bar-container">
              <div class="pitch-type-bar-fill" style="width:${pct}%; background:${color}"></div>
            </div>
            <span class="pitch-type-value" style="color:${color}">${pct}%</span>
          </div>
        `;
      }).join('');
    }
  },

  renderTopVenuesLeaderboards: function(topBatting, topChasing) {
    // Top Batting Venues
    const batList = document.getElementById('topBattingVenuesList');
    if (batList && topBatting.length) {
      batList.innerHTML = topBatting.map((v, i) => {
        const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
        return `
          <div class="venue-leaderboard-row">
            <span class="venue-lb-rank ${rankClass}">${i + 1}</span>
            <span class="venue-lb-name">${v.venue}</span>
            <span class="venue-lb-value" style="color:var(--accent-teal)">${v.avg_first_innings_score}</span>
          </div>
        `;
      }).join('');
    }

    // Top Chasing Venues
    const chaseList = document.getElementById('topChasingVenuesList');
    if (chaseList && topChasing.length) {
      chaseList.innerHTML = topChasing.map((v, i) => {
        const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
        const chasePct = (100 - (v.bat_first_win_pct || 50)).toFixed(1);
        return `
          <div class="venue-leaderboard-row">
            <span class="venue-lb-rank ${rankClass}">${i + 1}</span>
            <span class="venue-lb-name">${v.venue}</span>
            <span class="venue-lb-value" style="color:var(--accent-sky)">${chasePct}%</span>
          </div>
        `;
      }).join('');
    }
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
          <div class="stat-value" style="color:var(--accent-amber); font-size:22px;">${buy.player}</div>
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

    const renderSearchList = (query = '') => {
      if (!modalResults || !this.data || !this.data.all_players) return;
      modalResults.innerHTML = '';
      const q = query.toLowerCase().trim();
      let matches = [];
      if (!q) {
        matches = this.data.all_players.slice(0, 15);
      } else {
        matches = this.data.all_players.filter(p => p.PlayerName && p.PlayerName.toLowerCase().includes(q)).slice(0, 15);
      }

      matches.forEach(p => {
        const div = document.createElement('div');
        div.className = 'autocomplete-item';
        div.innerHTML = `
          <div>
            <strong style="color:var(--text-main); font-size:14px;">${p.PlayerName}</strong>
            <div style="font-size:12px; color:var(--text-muted);">${p.Teams || 'IPL Franchise'} | Span: ${p.Span || 'N/A'}</div>
          </div>
          <div style="font-family:var(--font-mono); font-size:12px; color:var(--accent-teal); font-weight:700;">
            Runs: ${(p.Runs || 0).toLocaleString()} | Wkts: ${p.Wkts || 0}
          </div>
        `;
        div.addEventListener('click', () => {
          closeSearch();
          this.switchSection('player-section');
          this.selectPlayerProfile(p);
        });
        modalResults.appendChild(div);
      });
    };

    const openSearch = () => {
      if (searchModal) searchModal.style.display = 'flex';
      renderSearchList(modalInput ? modalInput.value : '');
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

    if (modalInput) {
      modalInput.addEventListener('input', (e) => {
        renderSearchList(e.target.value);
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

    // Player venue breakdown search filter
    const vSearch = document.getElementById('scoutVenueSearchInput');
    if (vSearch) {
      vSearch.addEventListener('input', () => {
        const curPlayer = this.selectedPlayer ? this.selectedPlayer.PlayerName : 'V Kohli';
        this.renderPlayerVenueTable(curPlayer);
      });
    }
  },

  // ─── BEST PLAYING XI SECTION ─────────────────────────────────────────
  renderPlayingXISection: function() {
    const d = this.data;
    if (!d) return;

    const sel1 = document.getElementById('xiTeam1Select');
    const sel2 = document.getElementById('xiTeam2Select');
    const selV = document.getElementById('xiVenueSelect');
    const genBtn = document.getElementById('xiGenerateBtn');

    if (!sel1 || !sel2 || !selV) return;

    // Populate team dropdowns from current_elo_ratings or playing_xi_data
    const teams = d.playing_xi_data && d.playing_xi_data.team_rosters
      ? Object.keys(d.playing_xi_data.team_rosters).sort()
      : Object.keys(d.current_elo_ratings || {}).sort();

    sel1.innerHTML = '';
    sel2.innerHTML = '';
    teams.forEach((t, i) => {
      sel1.add(new Option(t, t, false, i === 0));
      sel2.add(new Option(t, t, false, i === 1));
    });

    // Populate venue dropdown
    const venues = (d.playing_xi_data && d.playing_xi_data.venues_list) || [];
    selV.innerHTML = '';
    if (venues.length > 0) {
      venues.forEach(v => selV.add(new Option(v, v)));
    } else if (d.venue_stats) {
      d.venue_stats.forEach(v => selV.add(new Option(v.venue, v.venue)));
    }

    // Generate button click handler
    if (genBtn) {
      genBtn.addEventListener('click', () => this.generatePlayingXI());
    }
  },

  generatePlayingXI: async function() {
    const team1 = document.getElementById('xiTeam1Select').value;
    const team2 = document.getElementById('xiTeam2Select').value;
    const venue = document.getElementById('xiVenueSelect').value;
    const btn = document.getElementById('xiGenerateBtn');
    const output = document.getElementById('xiResultsOutput');

    if (!team1 || !team2 || !venue) return;

    // Show loading
    btn.disabled = true;
    btn.innerHTML = '<span class="xi-spinner"></span> Generating...';

    // Try API first, then fallback to client-side computation
    let result = null;
    try {
      const url = `/api/playing-xi?team1=${encodeURIComponent(team1)}&team2=${encodeURIComponent(team2)}&venue=${encodeURIComponent(venue)}`;
      const res = await fetch(url);
      if (res.ok) {
        result = await res.json();
      }
    } catch (e) {
      console.warn('API call failed, using client-side fallback:', e);
    }

    // Client-side fallback
    if (!result) {
      result = this._computePlayingXIClientSide(team1, team2, venue);
    }

    // Restore button
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
      </svg>
      Generate Best Playing XI
    `;

    // Render results
    if (result) {
      this.renderPlayingXIResults(result, output);
    }
  },

  _computePlayingXIClientSide: function(team1, team2, venue) {
    const d = this.data;
    if (!d || !d.playing_xi_data) return null;

    const { team_rosters, player_roles } = d.playing_xi_data;
    const pvs = d.player_venue_stats || {};
    const pcs = d.player_career_stats || {};

    // ── Scoring helpers (mirror server logic) ────────────────────────
    function computeBatScore(s) {
      if (!s || (s.runs <= 0 && s.innings <= 0)) return 0;
      const cappedAvg = Math.min(s.avg || 0, 65);
      const milestones = (s.fifties || 0) * 15 + (s.hundreds || 0) * 35;
      return (s.runs * 0.25) + (cappedAvg * 0.25) + ((s.sr || 0) * 0.20)
           + ((s.innings || 0) * 5 * 0.15) + (milestones * 0.15);
    }

    function computeBowlScore(s) {
      if (!s || s.wickets <= 0) return 0; // STRICT ZERO WICKETS EXCLUSION
      const econScore = (s.economy > 0 && s.economy <= 15) ? (12.0 / s.economy) * 15 : 0;
      const impact = (s.bowl_innings || 0) > 0 ? (s.wickets / s.bowl_innings) * 20 : 0;
      return (s.wickets * 12 * 0.35) + (econScore * 0.30)
           + ((s.bowl_innings || 0) * 5 * 0.20) + (impact * 0.15);
    }

    function computeRoleScore(role, stats) {
      if (role === 'Batsman' || role === 'Wicketkeeper') return computeBatScore(stats);
      if (role === 'Bowler') return computeBowlScore(stats);
      if (role === 'All-Rounder') {
        const bat = computeBatScore(stats);
        const bowl = computeBowlScore(stats);
        const versatility = (stats.runs > 0 && stats.wickets > 0) ? 10 : 0;
        return bat * 0.45 + bowl * 0.45 + versatility * 0.10;
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

      const scored = roster.map(pName => {
        const role = player_roles[pName] || 'Batsman';
        const venueList = pvs[pName] || [];
        const venueData = venueList.find(v => v.venue && v.venue.toLowerCase() === vl)
          || venueList.find(v => v.venue && v.venue.toLowerCase().includes(vl.split('(')[0].trim().toLowerCase()));

        const careerData = pcs[pName] || null;
        const hasVenueData = !isAllTime && !!venueData && (
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
        if (isAllTime && careerData) {
          if (role === 'Batsman' || role === 'Wicketkeeper') {
            score = (careerStats.runs * 0.5) + (Math.min(careerStats.avg, 50) * 2.0) + (careerStats.fifties * 10) + (careerStats.hundreds * 25);
          } else if (role === 'Bowler') {
            score = careerStats.wickets > 0 ? (careerStats.wickets * 15.0) + ((12.0 / (careerStats.economy || 8.0)) * 10) : 0;
          } else if (role === 'All-Rounder') {
            score = (careerStats.runs * 0.30) + (careerStats.wickets > 0 ? careerStats.wickets * 12.0 : 0);
          }
        } else if (hasVenueData) {
          const venueScore = computeRoleScore(role, venueStats);
          const careerScore = computeRoleScore(role, careerStats);
          const venueInnings = Math.max(venueStats.innings, venueStats.bowl_innings);
          const experienceBonus = Math.min(venueInnings * 2, 20);
          score = venueScore * 0.70 + careerScore * 0.30 + experienceBonus;
        } else if (careerData) {
          score = computeRoleScore(role, careerStats) * 0.85;
        }

        return {
          name: pName, role,
          score: Math.round(score * 10) / 10,
          venue_stats: venueStats,
          career_stats: careerStats,
          has_venue_data: hasVenueData,
          matches_at_venue: hasVenueData ? Math.max(venueStats.innings, venueStats.bowl_innings) : 0,
        };
      });

      // Filter out zero-wicket bowlers
      const batsmen = scored.filter(p => p.role === 'Batsman').sort((a, b) => b.score - a.score);
      const keepers = scored.filter(p => p.role === 'Wicketkeeper').sort((a, b) => b.score - a.score);
      const allrounders = scored.filter(p => p.role === 'All-Rounder').sort((a, b) => b.score - a.score);
      const bowlers = scored
        .filter(p => p.role === 'Bowler' && p.career_stats.wickets > 0)
        .sort((a, b) => b.score - a.score);

      const selected = [];
      const needs = { Batsman: 4, Wicketkeeper: 1, 'All-Rounder': 1, Bowler: 5 };
      const pools = { Batsman: batsmen, Wicketkeeper: keepers, 'All-Rounder': allrounders, Bowler: bowlers };

      for (const [role, count] of Object.entries(needs)) {
        const pool = pools[role];
        const picked = pool.slice(0, count);
        selected.push(...picked);
        if (picked.length < count) {
          const remaining = count - picked.length;
          const pickedNames = new Set(selected.map(p => p.name));
          const fallbacks = scored
            .filter(p => !pickedNames.has(p.name) && (role !== 'Bowler' || p.career_stats.wickets > 0))
            .sort((a, b) => b.score - a.score)
            .slice(0, remaining)
            .map(p => ({ ...p, role: role + ' (Fallback)' }));
          selected.push(...fallbacks);
        }
      }

      return { team: teamName, players: selected.slice(0, 11) };
    }

    return { venue, team1_xi: buildXI(team1), team2_xi: buildXI(team2) };
  },

  renderPlayingXIResults: function(result, container) {
    if (!container) return;

    const getTeamColor = (teamName) => {
      const info = window.getTeamInfo ? window.getTeamInfo(teamName) : null;
      return info ? info.primary : '#3A4D6B';
    };

    const getTeamShort = (teamName) => {
      const info = window.getTeamInfo ? window.getTeamInfo(teamName) : null;
      return info ? info.short : teamName.split(' ').map(w => w[0]).join('').substring(0, 3);
    };

    const getRoleBadgeClass = (role) => {
      const r = role.toLowerCase().replace(/\s*\(fallback\)/, '');
      if (r.includes('wicketkeeper')) return 'wicketkeeper';
      if (r.includes('all-rounder')) return 'allrounder';
      if (r.includes('bowler')) return 'bowler';
      return 'batsman';
    };

    const getRoleDisplayName = (role) => {
      const clean = role.replace(/\s*\(Fallback\)/, '');
      if (clean === 'Wicketkeeper') return 'WK';
      if (clean === 'All-Rounder') return 'AR';
      if (clean === 'Bowler') return 'BWL';
      return 'BAT';
    };

    const getInitials = (name) => {
      const parts = name.split(' ');
      if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      return name.substring(0, 2).toUpperCase();
    };

    const renderTeamPanel = (xi, teamColor) => {
      if (!xi || !xi.players || xi.players.length === 0) {
        return `<div class="xi-team-panel">
          <div class="xi-empty-state">
            <div class="xi-empty-state-icon">⚠️</div>
            <div class="xi-empty-state-text">${xi.error || 'No players found for this team'}</div>
          </div>
        </div>`;
      }

      // Find best performer (highest score)
      const bestIdx = xi.players.reduce((maxI, p, i, arr) => p.score > arr[maxI].score ? i : maxI, 0);

      // Group players by role for display
      const roleOrder = ['Batsman', 'Wicketkeeper', 'All-Rounder', 'Bowler'];
      const grouped = {};
      xi.players.forEach((p, idx) => {
        const baseRole = p.role.replace(/\s*\(Fallback\)/, '');
        if (!grouped[baseRole]) grouped[baseRole] = [];
        grouped[baseRole].push({ ...p, originalIdx: idx });
      });

      let playerCards = '';
      let playerNum = 1;

      roleOrder.forEach(role => {
        const players = grouped[role];
        if (!players || players.length === 0) return;

        const roleClass = getRoleBadgeClass(role);
        const roleTitles = { 'Batsman': '🏏 BATSMEN', 'Wicketkeeper': '🧤 WICKETKEEPER', 'All-Rounder': '⚡ ALL-ROUNDER', 'Bowler': '🎯 BOWLERS' };

        playerCards += `<div class="xi-role-group">
          <div class="xi-role-group-title ${roleClass}">${roleTitles[role] || role}</div>`;

        players.forEach(p => {
          const isBest = p.originalIdx === bestIdx;
          const hasVenue = p.has_venue_data !== undefined ? p.has_venue_data : true;
          const s = hasVenue ? p.venue_stats : (p.career_stats || p.venue_stats);
          const isBatting = (role === 'Batsman' || role === 'Wicketkeeper' || role === 'All-Rounder');
          const isBowling = (role === 'Bowler' || role === 'All-Rounder');

          // Data source indicator
          const dataSourceBadge = hasVenue
            ? `<span class="xi-data-source venue" title="Stats from this venue">📍 Venue Stats (${p.matches_at_venue || s.innings || 0} inn)</span>`
            : `<span class="xi-data-source career" title="No venue data — showing career stats">📊 Career Stats</span>`;

          let statsHTML = '<div class="xi-player-venue-stats">';
          if (isBatting) {
            statsHTML += `
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.innings || 0}</span><span class="xi-venue-stat-label">Inn</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.runs}</span><span class="xi-venue-stat-label">Runs</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.avg}</span><span class="xi-venue-stat-label">Avg</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.sr}</span><span class="xi-venue-stat-label">SR</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.hs || 0}</span><span class="xi-venue-stat-label">HS</span></div>
            `;
            if ((s.fifties || 0) > 0 || (s.hundreds || 0) > 0) {
              statsHTML += `
                <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.fifties || 0}/${s.hundreds || 0}</span><span class="xi-venue-stat-label">50s/100s</span></div>
              `;
            }
          }
          if (isBowling) {
            statsHTML += `
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.bowl_innings || 0}</span><span class="xi-venue-stat-label">B.Inn</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.wickets}</span><span class="xi-venue-stat-label">Wkts</span></div>
              <div class="xi-venue-stat"><span class="xi-venue-stat-value">${s.economy}</span><span class="xi-venue-stat-label">Econ</span></div>
            `;
          }
          statsHTML += '</div>';

          playerCards += `
            <div class="xi-player-card ${isBest ? 'best-performer' : ''} ${!hasVenue ? 'career-fallback' : ''}">
              <span class="xi-player-number">${playerNum}</span>
              <div class="xi-player-avatar" style="background:${teamColor}">${getInitials(p.name)}</div>
              <div class="xi-player-info">
                <div class="xi-player-name">${p.name}</div>
                <div class="xi-player-meta">
                  <span class="xi-role-badge ${roleClass}">${getRoleDisplayName(p.role)}</span>
                  ${dataSourceBadge}
                </div>
              </div>
              ${statsHTML}
            </div>`;
          playerNum++;
        });

        playerCards += '</div>';
      });

      return `<div class="xi-team-panel">
        <div class="xi-team-panel-header">
          <div class="xi-team-badge" style="background:${teamColor}">${getTeamShort(xi.team)}</div>
          <div>
            <div class="xi-team-name">${xi.team}</div>
            <div class="xi-venue-label">📍 ${result.venue}</div>
          </div>
        </div>
        ${playerCards}
      </div>`;
    };

    const team1Color = getTeamColor(result.team1_xi.team);
    const team2Color = getTeamColor(result.team2_xi.team);

    container.innerHTML = `
      <div class="xi-results-container">
        ${renderTeamPanel(result.team1_xi, team1Color)}
        ${renderTeamPanel(result.team2_xi, team2Color)}
      </div>
    `;
  }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.APP.init();
});
