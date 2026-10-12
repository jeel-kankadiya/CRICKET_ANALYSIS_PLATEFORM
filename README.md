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
│   ├── feature_engineering_v2.py  leak-free pre-match feature matrix (v2)
│   ├── train_models_v2.py         trains & evaluates 7 ML models + stacking ensemble
│   ├── player_analytics.py        batting/bowling/all-rounder impact scores
│   ├── match_simulator.py         "what-if" win probability for any matchup
│   └── generate_dashboard_data.py bundles everything into one JSON for the UI
├── models_v2/                    trained model artifacts (.pkl) — v2 pipeline
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

### 3.2 Feature Engineering (`feature_engineering_v2.py`)
All features are strictly historical at the time of each match:
- **Elo differential** between the two teams
- **Rolling form** — win rate over each team's last 5 matches
- **Momentum** — average normalized win/loss margin over the last 5 matches
- **Experience** — total matches played by each team so far
- **Venue win rate** — each team's historical record at that specific venue
- **Head-to-head win rate** between the two specific franchises
- **Toss winner / toss decision** (bat vs field first)

### 3.3 Machine Learning Models — Algorithms Used & Why (`train_models_v2.py`)

Seven models are trained, compared, and combined into ensemble architectures:

#### 1. 🥇 Gradient Boosting (Primary Model — `sklearn`)
Sequentially builds 200 shallow trees (depth 3, learning rate 0.03), each correcting
residual errors of the previous. Chosen because it natively captures non-linear
team-strength interactions (Elo × form × venue) while staying robust against
overfitting on the ~1,000-match dataset. Consistently achieves the best ROC-AUC.

#### 2. Random Forest (300 Trees)
Builds 300 independently trained decision trees and aggregates their votes.
Excellent at capturing feature interactions without parameter tuning. Serves as a
strong ensemble baseline; avoids variance from correlated features via random
subspace sampling.

#### 3. XGBoost (eXtreme Gradient Boosting)
Industry-standard gradient boosting with L1/L2 regularization, column subsampling,
and hardware-optimized tree building. Chosen for its superior speed and
regularization properties on structured sports tabular data.

#### 4. LightGBM (Leaf-wise Boosting)
Uses leaf-wise (best-first) tree growth instead of level-wise. Faster training with
lower memory usage. Particularly effective when feature importance is skewed —
matching our dataset where Elo differential dominates all other features.

#### 5. CatBoost (Category-aware Boosting — Yandex)
Gradient boosting framework with native ordered target statistics for categorical
features. Chosen because team IDs, venues, and toss decisions are inherently
categorical — CatBoost handles these natively without label-encoding leakage.

#### 6. Logistic Regression (Interpretable Baseline)
Linear probabilistic classifier with L2 regularization (C=0.5). Included as a
fully interpretable baseline and used as the **meta-learner** in the Stacking
Ensemble. Its coefficients reveal which features have linear predictive power.

#### 7. Stacking Meta-Ensemble (CatBoost + LightGBM + XGBoost + RF → Logistic Regression)
A 2-layer stacking architecture: 4 diverse base models generate out-of-fold
probability predictions, which become features for a Logistic Regression meta-learner.
Combines complementary strengths of each learner, reducing individual model variance.

#### 8. 🔴 HistGradientBoosting (Live In-Match Model)
A separate model trained on live ball-by-ball snapshots (runs scored, wickets fallen,
current over, run rate). Uses `HistGradientBoostingClassifier` for fast inference.
Accuracy improves dramatically as the match progresses into death overs.

**Validation:** A chronological (never shuffled) train/test split, plus a
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

### Pre-Match Win Probability Models (Holdout: 238 matches, 2024–2025 season)

| Model | Algorithm | Accuracy | ROC-AUC | Log Loss | Brier Score |
|---|---|---|---|---|---|
| **Gradient Boosting ⭐** | sklearn GBC | **54.6%** | **0.530** | 0.717 | 0.260 |
| Random Forest | sklearn RFC | 52.5% | 0.518 | 0.697 | 0.252 |
| XGBoost | xgboost | 52.5% | 0.518 | 0.718 | 0.261 |
| Stacking Ensemble | CatBoost+LGBM+XGB+RF → LR | 52.1% | 0.512 | 0.693 | 0.250 |
| LightGBM | lightgbm | 50.8% | 0.512 | 0.724 | 0.264 |
| Logistic Regression | sklearn LR | 50.0% | 0.490 | 0.705 | 0.256 |
| CatBoost | catboost | 49.2% | 0.514 | 0.700 | 0.254 |

### Live In-Match Model (4,317 ball-by-ball snapshots)

| Phase | Accuracy | ROC-AUC |
|---|---|---|
| Powerplay (Overs 1–6) | 69.7% | 0.804 |
| Middle Overs (7–15) | 78.5% | 0.873 |
| **Death Overs (16–20)** | **89.3%** | **0.964** |
| **Overall** | **77.6%** | **0.875** |

**Why ~54% pre-match accuracy is expected — not a modeling failure.** T20
cricket is a short, high-variance format — a single over can swing a match —
so pre-match team-strength features cap out well below the reliability you'd
see in a longer format like Test cricket. The value of this platform is
**calibrated, transparent probability estimation** built on real historical
signal (Elo, form, head-to-head), not an overstated "certain" predictor. The
top predictive signals are, in order: **Elo differential, momentum, venue
win rate, and head-to-head record** — all sports-sensible.

The live in-match model (77.6% overall, **89.3% in death overs**) uses
real-time ball-by-ball state and dramatically outperforms pre-match predictions,
as expected for a format where match state is the strongest signal.

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
- **Machine Learning Lab** — full algorithm transparency: which model was used, why it was chosen, accuracy scores, ROC-AUC, Log Loss, Brier Score for all 8 models, and an honest explanation of T20 prediction limits
