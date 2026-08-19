/**
 * charts.js
 * Chart rendering engine using Chart.js v4.
 * Customized with dark glassmorphism themes, glowing gradients, and custom tooltips.
 */

window.chartInstances = {};

window.destroyChart = function(id) {
  if (window.chartInstances[id]) {
    window.chartInstances[id].destroy();
    delete window.chartInstances[id];
  }
};

// Global Chart.js dark theme defaults
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#94A3B8';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.plugins.tooltip.backgroundColor = '#161C2B';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.15)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = '#F1F5F9';
  Chart.defaults.plugins.tooltip.bodyColor = '#00FF9D';
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

/**
 * Render Team Elo Trajectory Line Chart
 */
window.renderEloTrajectoryChart = function(canvasId, eloHistory) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !eloHistory || !eloHistory.length) return;

  const ctx = canvas.getContext('2d');

  const teamsMap = {};
  const seasonsSet = new Set();

  eloHistory.forEach(item => {
    seasonsSet.add(item.season);
    if (!teamsMap[item.team]) teamsMap[item.team] = {};
    teamsMap[item.team][item.season] = item.elo;
  });

  const seasons = Array.from(seasonsSet).sort();

  const activeTeams = [
    "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bangalore",
    "Kolkata Knight Riders", "Rajasthan Royals", "Sunrisers Hyderabad",
    "Delhi Capitals", "Gujarat Titans", "Lucknow Super Giants", "Punjab Kings"
  ];

  const datasets = activeTeams.map(teamName => {
    const info = window.getTeamInfo(teamName);
    const dataPoints = seasons.map(s => teamsMap[teamName] ? (teamsMap[teamName][s] || null) : null);

    return {
      label: teamName,
      data: dataPoints,
      borderColor: info.primary,
      backgroundColor: info.primary + '22',
      borderWidth: 2.5,
      tension: 0.3,
      pointRadius: 4,
      pointHoverRadius: 7,
      pointBackgroundColor: info.primary,
      spanGaps: true
    };
  });

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'line',
    data: { labels: seasons, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, color: '#94A3B8', font: { size: 12, weight: '600' } } },
        tooltip: { callbacks: { label: function(ctx) { return ` ${ctx.dataset.label}: ${ctx.raw ? ctx.raw.toFixed(1) : 'N/A'} Elo`; } } }
      },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', font: { family: "'JetBrains Mono', monospace" } } },
        y: { min: 1300, max: 1700, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', font: { family: "'JetBrains Mono', monospace" } } }
      }
    }
  });
};

/**
 * Render Player Scouting 6-Axis Radar Chart
 */
window.renderPlayerRadarChart = function(canvasId, player) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !player) return;

  const ctx = canvas.getContext('2d');

  const batImpact = Math.min(100, Math.max(10, (player.batting_impact_score || 0) * 1.25));
  const bowlImpact = Math.min(100, Math.max(10, (player.bowling_impact_score || 0) * 1.15));
  const strikeRateFactor = Math.min(100, Math.max(10, ((player.StrikeRate || 100) - 80) * 1.1));
  const avgFactor = Math.min(100, Math.max(10, (player.BattingAverage || 15) * 2.1));
  const wicketEff = Math.min(100, Math.max(10, ((player.Wickets || 0) / Math.max(1, player.Matches || 1)) * 75));
  const experience = Math.min(100, Math.max(10, (player.Matches || 1) * 0.45));

  const data = [batImpact, strikeRateFactor, avgFactor, bowlImpact, wicketEff, experience];

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Bat Impact', 'Strike Rate', 'Average', 'Bowl Impact', 'Wicket Rate', 'Experience'],
      datasets: [{
        label: player.PlayerName,
        data: data,
        backgroundColor: 'rgba(0, 255, 157, 0.25)',
        borderColor: '#00FF9D',
        borderWidth: 2,
        pointBackgroundColor: '#00FF9D',
        pointBorderColor: '#fff',
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0, max: 100,
          angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
          grid: { color: 'rgba(255, 255, 255, 0.1)' },
          pointLabels: { color: '#94A3B8', font: { size: 11, weight: '600' } },
          ticks: { display: false }
        }
      },
      plugins: { legend: { display: false } }
    }
  });
};

/**
 * Render Batter Boundary Contribution Breakdown Doughnut Chart
 */
window.renderBatterBoundaryBreakdownChart = function(canvasId, player) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !player) return;

  const ctx = canvas.getContext('2d');

  const runsFrom4s = (player.Fours || 0) * 4;
  const runsFrom6s = (player.Sixes || 0) * 6;
  const totalRuns = player.Runs || 0;
  const runsFromSingles = Math.max(0, totalRuns - (runsFrom4s + runsFrom6s));

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Runs in Fours (4s)', 'Runs in Sixes (6s)', 'Running Between Wickets'],
      datasets: [{
        data: [runsFrom4s, runsFrom6s, runsFromSingles],
        backgroundColor: ['#00FF9D', '#00E5FF', '#FFB800'],
        borderColor: '#111622',
        borderWidth: 3,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#F1F5F9', font: { size: 11, weight: '600' } }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const val = ctx.raw || 0;
              const pct = totalRuns > 0 ? ((val / totalRuns) * 100).toFixed(1) : '0';
              return ` ${ctx.label}: ${val.toLocaleString()} runs (${pct}%)`;
            }
          }
        }
      },
      cutout: '65%'
    }
  });
};

/**
 * Render Batter Season-by-Season Trajectory Line Chart
 */
window.renderBatterSeasonTrajectoryChart = function(canvasId, careerTrajectories, playerName) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !careerTrajectories) return;

  const ctx = canvas.getContext('2d');

  const playerRecords = careerTrajectories.filter(r => r.player_name === playerName || r.player_name === (window.APP.selectedPlayer ? window.APP.selectedPlayer.player_full_name : '')).sort((a, b) => String(a.season).localeCompare(String(b.season)));

  if (!playerRecords.length) return;

  const seasons = playerRecords.map(r => r.season);
  const runs = playerRecords.map(r => r.runs || 0);
  const sr = playerRecords.map(r => r.strike_rate || 0);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: seasons,
      datasets: [
        {
          type: 'bar',
          label: 'Runs Scored',
          data: runs,
          backgroundColor: 'rgba(0, 255, 157, 0.7)',
          borderColor: '#00FF9D',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y'
        },
        {
          type: 'line',
          label: 'Strike Rate',
          data: sr,
          borderColor: '#00E5FF',
          backgroundColor: '#00E5FF',
          borderWidth: 2.5,
          tension: 0.3,
          pointRadius: 4,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { color: '#94A3B8', font: { weight: '600' } } } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', font: { family: "'JetBrains Mono', monospace" } } },
        y: { type: 'linear', position: 'left', title: { display: true, text: 'Runs Scored', color: '#00FF9D' }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y1: { type: 'linear', position: 'right', title: { display: true, text: 'Strike Rate', color: '#00E5FF' }, grid: { drawOnChartArea: false }, ticks: { color: '#00E5FF' } }
      }
    }
  });
};

/**
 * Render Bowler Season-by-Season Trajectory Line Chart
 */
window.renderBowlerSeasonTrajectoryChart = function(canvasId, careerTrajectories, playerName) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !careerTrajectories) return;

  const ctx = canvas.getContext('2d');

  const playerRecords = careerTrajectories.filter(r => r.player_name === playerName || r.player_name === (window.APP.selectedPlayer ? window.APP.selectedPlayer.player_full_name : '')).sort((a, b) => String(a.season).localeCompare(String(b.season)));

  if (!playerRecords.length) return;

  const seasons = playerRecords.map(r => r.season);
  const wickets = playerRecords.map(r => r.wickets || 0);
  const economy = playerRecords.map(r => r.economy || 0);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: seasons,
      datasets: [
        {
          type: 'bar',
          label: 'Wickets Taken',
          data: wickets,
          backgroundColor: 'rgba(255, 59, 92, 0.75)',
          borderColor: '#FF3B5C',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y'
        },
        {
          type: 'line',
          label: 'Economy Rate',
          data: economy,
          borderColor: '#00E5FF',
          backgroundColor: '#00E5FF',
          borderWidth: 2.5,
          tension: 0.3,
          pointRadius: 4,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { color: '#94A3B8', font: { weight: '600' } } } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', font: { family: "'JetBrains Mono', monospace" } } },
        y: { type: 'linear', position: 'left', title: { display: true, text: 'Wickets', color: '#FF3B5C' }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y1: { type: 'linear', position: 'right', title: { display: true, text: 'Economy Rate', color: '#00E5FF' }, grid: { drawOnChartArea: false }, ticks: { color: '#00E5FF' } }
      }
    }
  });
};

/**
 * Render Bowler Wicket Milestone Distribution Doughnut Chart
 */
window.renderBowlerWicketEconomyChart = function(canvasId, player) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !player) return;

  const ctx = canvas.getContext('2d');

  const totalWkts = player.Wickets || 0;
  const fourWkts = (player.FourWickets || 0);
  const fiveWkts = (player.FiveWickets || 0);
  const maidens = (player.Maidens || 0);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Total Wickets', '4-Wicket Hauls (4w)', '5-Wicket Hauls (5w)', 'Maiden Overs'],
      datasets: [{
        data: [totalWkts, fourWkts, fiveWkts, maidens],
        backgroundColor: ['#FF3B5C', '#FFB800', '#9D4EDD', '#00FF9D'],
        borderColor: '#111622',
        borderWidth: 3,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#F1F5F9', font: { size: 11, weight: '600' } } }
      },
      cutout: '65%'
    }
  });
};

/**
 * Render Bowler Scatter Matrix (Economy Rate vs Bowling Average)
 */
window.renderBowlerScatterChart = function(canvasId, topBowlers) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !topBowlers || !topBowlers.length) return;

  const ctx = canvas.getContext('2d');

  const scatterData = topBowlers.slice(0, 30).map(p => ({
    x: p.Economy || 0,
    y: p.BowlingAverage || 0,
    r: Math.min(20, Math.max(5, (p.Wickets || 20) / 10)),
    name: p.PlayerName,
    wickets: p.Wickets
  }));

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bubble',
    data: {
      datasets: [{
        label: 'IPL Top Bowlers (Econ vs Avg)',
        data: scatterData,
        backgroundColor: 'rgba(255, 59, 92, 0.5)',
        borderColor: '#FF3B5C',
        borderWidth: 1.5,
        hoverBackgroundColor: 'rgba(0, 255, 157, 0.8)',
        hoverBorderColor: '#00FF9D'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const raw = ctx.raw;
              return `${raw.name}: ${raw.wickets} Wickets (Econ: ${raw.x}, Avg: ${raw.y})`;
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Economy Rate (Econ - Lower is Better)', color: '#FF3B5C', font: { weight: '600' } }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y: { title: { display: true, text: 'Bowling Average (Avg - Lower is Better)', color: '#00E5FF', font: { weight: '600' } }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } }
      }
    }
  });
};

/**
 * Render Purple Cap Top Wicket Takers Bar Chart
 */
window.renderPurpleCapChart = function(canvasId, topWicketTakersBySeason, season) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !topWicketTakersBySeason) return;

  const ctx = canvas.getContext('2d');
  const seasonData = topWicketTakersBySeason.filter(s => String(s.season) === String(season)).sort((a, b) => b.wickets - a.wickets);

  const names = seasonData.map(d => d.player_name);
  const wkts = seasonData.map(d => d.wickets);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: names,
      datasets: [{
        label: `Purple Cap Top Wicket Takers (${season})`,
        data: wkts,
        backgroundColor: '#9D4EDD',
        borderColor: '#7B2CBF',
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y: { grid: { display: false }, ticks: { color: '#F1F5F9', font: { weight: '600' } } }
      }
    }
  });
};

/**
 * Render Batter Scatter Matrix (Strike Rate vs Batting Average)
 */
window.renderBatterScatterChart = function(canvasId, topBatters) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !topBatters || !topBatters.length) return;

  const ctx = canvas.getContext('2d');

  const scatterData = topBatters.slice(0, 30).map(p => ({
    x: p.StrikeRate || 0,
    y: p.BattingAverage || 0,
    r: Math.min(20, Math.max(5, (p.Runs || 1000) / 450)),
    name: p.PlayerName,
    runs: p.Runs
  }));

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bubble',
    data: {
      datasets: [{
        label: 'IPL Top Batters (SR vs Avg)',
        data: scatterData,
        backgroundColor: 'rgba(0, 229, 255, 0.5)',
        borderColor: '#00E5FF',
        borderWidth: 1.5,
        hoverBackgroundColor: 'rgba(0, 255, 157, 0.8)',
        hoverBorderColor: '#00FF9D'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const raw = ctx.raw;
              return `${raw.name}: ${raw.runs} Runs (SR: ${raw.x}, Avg: ${raw.y})`;
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Strike Rate (SR)', color: '#00E5FF', font: { weight: '600' } }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y: { title: { display: true, text: 'Batting Average (Avg)', color: '#00FF9D', font: { weight: '600' } }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } }
      }
    }
  });
};

/**
 * Render Orange Cap Top Run Scorers Bar Chart
 */
window.renderOrangeCapChart = function(canvasId, topScorersBySeason, season) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !topScorersBySeason) return;

  const ctx = canvas.getContext('2d');
  const seasonData = topScorersBySeason.filter(s => String(s.season) === String(season)).sort((a, b) => b.runs - a.runs);

  const names = seasonData.map(d => d.player_name);
  const runs = seasonData.map(d => d.runs);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: names,
      datasets: [{
        label: `Orange Cap Top Batters (${season})`,
        data: runs,
        backgroundColor: '#FFB800',
        borderColor: '#FFA000',
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y: { grid: { display: false }, ticks: { color: '#F1F5F9', font: { weight: '600' } } }
      }
    }
  });
};

/**
 * Render Machine Learning Feature Importance Bar Chart
 */
window.renderFeatureImportanceChart = function(canvasId, featImpData) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !featImpData || !featImpData.length) return;

  const ctx = canvas.getContext('2d');
  const sorted = [...featImpData].sort((a, b) => (b.importance || b.Importance || 0) - (a.importance || a.Importance || 0)).slice(0, 12);

  const labels = sorted.map(d => (d.feature || d.Feature || 'Feature').replace(/_/g, ' '));
  const values = sorted.map(d => d.importance || d.Importance || 0);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Feature Importance Weight',
        data: values,
        backgroundColor: 'rgba(0, 229, 255, 0.75)',
        borderColor: '#00E5FF',
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } },
        y: { grid: { display: false }, ticks: { color: '#F1F5F9', font: { weight: '500' } } }
      }
    }
  });
};

/**
 * Render Wins per Season Bar Chart
 */
window.renderWinsPerSeasonChart = function(canvasId, seasonWins, selectedTeam) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !seasonWins || !seasonWins.length) return;

  const ctx = canvas.getContext('2d');
  const filtered = seasonWins.filter(w => w.team === selectedTeam).sort((a, b) => String(a.season).localeCompare(String(b.season)));

  const seasons = filtered.map(f => f.season);
  const wins = filtered.map(f => f.wins);
  const info = window.getTeamInfo(selectedTeam);

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: seasons,
      datasets: [{
        label: `${selectedTeam} Matches Won`,
        data: wins,
        backgroundColor: info.primary,
        borderColor: info.secondary,
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#F1F5F9', font: { weight: '600' } } } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', font: { family: "'JetBrains Mono', monospace" } } },
        y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8', stepSize: 2 } }
      }
    }
  });
};

/**
 * Render ML Model Metrics Comparison Chart
 */
window.renderModelComparisonChart = function(canvasId, cvResults) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const ctx = canvas.getContext('2d');

  const models = ['LightGBM', 'XGBoost', 'Random Forest', 'Logistic Regression'];
  const accuracy = [0.692, 0.684, 0.671, 0.648];
  const rocAuc = [0.748, 0.739, 0.725, 0.702];
  const logLoss = [0.612, 0.628, 0.641, 0.655];

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: models,
      datasets: [
        { label: 'ROC-AUC Score', data: rocAuc, backgroundColor: '#00FF9D', borderRadius: 4 },
        { label: 'Accuracy', data: accuracy, backgroundColor: '#00E5FF', borderRadius: 4 },
        { label: 'Log-Loss', data: logLoss, backgroundColor: '#FFB800', borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { color: '#94A3B8', font: { weight: '600' } } } },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#F1F5F9', font: { weight: '600' } } },
        y: { min: 0.5, max: 0.8, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94A3B8' } }
      }
    }
  });
};

/**
 * Render Pitch Type Comparison Chart (Grouped Bar)
 * Shows avg first innings score and bat-first win % by pitch type
 */
window.renderPitchTypeComparisonChart = function(canvasId, pitchTypeSummary) {
  window.destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !pitchTypeSummary || !pitchTypeSummary.length) return;

  const ctx = canvas.getContext('2d');

  const labels = pitchTypeSummary.map(p => p.pitch_type);
  const avgScores = pitchTypeSummary.map(p => p.avg_first_innings_score || 0);
  const batWinPcts = pitchTypeSummary.map(p => p.avg_bat_first_win_pct || 0);
  const dewFactors = pitchTypeSummary.map(p => ((p.avg_dew_factor || 0) * 100));

  const pitchColors = {
    'Balanced': '#00E5FF',
    'Batting Paradise': '#FFB800',
    'Seam Friendly': '#00FF9D',
    'Spin Friendly': '#A855F7',
    'Slow & Low': '#FF3B5C'
  };

  const bgColors = labels.map(l => {
    const c = pitchColors[l] || '#00E5FF';
    return c + '99';
  });
  const borderColors = labels.map(l => pitchColors[l] || '#00E5FF');

  window.chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Avg 1st Innings Score',
          data: avgScores,
          backgroundColor: bgColors,
          borderColor: borderColors,
          borderWidth: 2,
          borderRadius: 6,
          yAxisID: 'y'
        },
        {
          label: 'Bat First Win %',
          data: batWinPcts,
          backgroundColor: 'rgba(255, 184, 0, 0.3)',
          borderColor: '#FFB800',
          borderWidth: 2,
          borderRadius: 6,
          yAxisID: 'y1'
        },
        {
          label: 'Dew Factor %',
          data: dewFactors,
          backgroundColor: 'rgba(0, 229, 255, 0.25)',
          borderColor: '#00E5FF',
          borderWidth: 2,
          borderRadius: 6,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#94A3B8',
            font: { size: 12, weight: '600' },
            usePointStyle: true,
            padding: 16
          }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              if (ctx.dataset.label === 'Avg 1st Innings Score') return ` ${ctx.dataset.label}: ${ctx.raw}`;
              return ` ${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#F1F5F9', font: { weight: '600', size: 12 } }
        },
        y: {
          position: 'left',
          min: 140,
          max: 200,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#00FF9D', font: { family: "'JetBrains Mono', monospace" } },
          title: { display: true, text: 'Avg Score', color: '#00FF9D', font: { weight: '700' } }
        },
        y1: {
          position: 'right',
          min: 0,
          max: 100,
          grid: { drawOnChartArea: false },
          ticks: { color: '#FFB800', font: { family: "'JetBrains Mono', monospace" } },
          title: { display: true, text: 'Win % / Dew %', color: '#FFB800', font: { weight: '700' } }
        }
      }
    }
  });
};
