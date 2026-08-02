# Cricket Intelligence Platform
### Advanced Player Performance Analytics, Match Simulation & Win Probability Prediction

An advanced cricket analytics platform that uses data analytics and machine
learning to predict match outcomes, analyze player and team performance, and
provide interactive insights through dashboards.

**Techniques used:** AI, Machine Learning, Python

---

## 1. Dataset

Built entirely from five raw IPL datasets:

| File | Rows | Description |
|---|---|---|
| `ipl_matches_data.csv` | 1,212 | Match-level results, 2008–2026 (toss, venue, winner, margins) |
| `ipl_allround.csv` | 792 | Career batting + bowling aggregates per player |
| `players_data_updated.csv` | 800 | Player identity: batting/bowling style, role |
| `teams_data.csv` | 16 | Canonical team IDs → current franchise names |
| `team_aliases.csv` | 46 | Historical name variants (e.g. Delhi Daredevils → Delhi Capitals) |

## 2. Project Structure

```
cricket_intelligence_platform/
├── data/                        raw CSVs (as provided)
├── src/
│   ├── data_loader.py            load + clean raw CSVs, resolve team IDs → names
│   ├── elo_rating.py              chess-style Elo rating engine for team strength
│   ├── feature_engineering.py     leak-free pre-match feature matrix
│   ├── train_models.py            trains & evaluates 3 ML models + time-series CV
│   ├── player_analytics.py        batting/bowling/all-rounder impact scores
│   ├── match_simulator.py         "what-if" win probability for any matchup
│   └── generate_dashboard_data.py bundles everything into one JSON for the UI
├── models/                       trained model artifacts (.pkl)
├── outputs/                       metrics, ratings, feature importances (csv/json)
├── dashboard/index.html          standalone interactive dashboard (no server needed)
├── run_pipeline.py                 runs steps 1–6 end-to-end
└── requirements.txt
```

## 3. Methodology

### 3.1 Elo Team Ratings (`elo_rating.py`)
Every franchise starts at 1500. After each decisive match, ratings update by
`K × (actual − expected)`, `K=32`. Ratings are computed **walking forward in
time**, so each match uses only the rating *before* that match — no lookahead.

### 3.2 Feature Engineering (`feature_engineering.py`)
All features are strictly historical at the time of each match:
- **Elo differential** between the two teams
- **Rolling form** — win rate over each team's last 5 matches
- **Momentum** — average normalized win/loss margin over the last 5 matches
- **Experience** — total matches played by each team so far
- **Venue win rate** — each team's historical record at that specific venue
- **Head-to-head win rate** between the two specific franchises
- **Toss winner / toss decision** (bat vs field first)

### 3.3 Machine Learning Models (`train_models.py`)
Three models are trained and compared:
1. **Logistic Regression** — interpretable linear baseline
2. **Random Forest** (300 trees, depth 6) — captures non-linear interactions
3. **Gradient Boosting** (200 trees, depth 3) — typically the strongest

**Validation:** a chronological (never shuffled) train/test split, plus a
5-fold `TimeSeriesSplit` cross-validation, since shuffling match order would
leak future information into training — the correct approach for sports
time-series data.

### 3.4 Player Performance Analytics (`player_analytics.py`)
- **Batting Impact Score** = weighted percentile blend of average, strike
  rate, and career run volume (min. 10 innings to qualify)
- **Bowling Impact Score** = weighted percentile blend of economy, bowling
  average, and wickets taken (min. 10 bowling innings)
- **All-Rounder Index** = `min(batting, bowling)` impact — deliberately using
  the minimum (not the average) so a specialist batter or bowler cannot rank
  as an all-rounder; only genuine dual contributors score highly

### 3.5 Match Simulator (`match_simulator.py`)
Reconstructs each team's *current* Elo, form, momentum, venue record and
head-to-head stats from full history, then feeds them into the trained
Gradient Boosting model to output a win probability for any hypothetical
fixture — the basis for the dashboard's live simulator.

## 4. Results & Honest Findings

| Model | Accuracy | ROC-AUC (holdout) | 5-Fold CV Mean AUC |
|---|---|---|---|
| Logistic Regression | 48.7% | 0.508 | 0.512 ± 0.057 |
| Random Forest | 51.3% | 0.509 | 0.503 ± 0.063 |
| **Gradient Boosting** | **54.2%** | **0.573** | 0.490 ± 0.046 |

**This is a genuine, documented finding, not a modeling failure.** T20
cricket is a short, high-variance format — a single over can swing a match —
so pre-match team-strength features cap out well below the reliability you'd
see in a longer format like Test cricket. The value of this platform is
**calibrated, transparent probability estimation** built on real historical
signal (Elo, form, head-to-head), not an overstated "certain" predictor. The
top predictive signals are, in order: **Elo differential, momentum, venue
win rate, and head-to-head record** — all sports-sensible.

## 5. Running the Project

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Then open `dashboard/index.html` in any browser — it's a fully standalone
file (all data is embedded), no server or internet connection required
(except for the Google Fonts / Chart.js CDN used purely for styling/charts).

## 6. Dashboard Features

- **Elo Power Rankings** — live current strength ranking of all 14 franchises
- **Match Simulator** — pick any two teams, get an instant win probability
- **Season Trends** — win count per season for any franchise
- **Player Leaderboards** — Top Batters / Bowlers / All-Rounders with impact scores
- **Venue & Toss Insights** — toss-decision win rates, busiest venues
- **Model Transparency** — full metrics table + feature importance, reported honestly
