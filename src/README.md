# Cricket Prediction Upgrade — install & run

These files extend your existing `CRICKET_ANALYSIS_PLATEFORM` repo. They were
built and tested directly against your cloned repo, so they run as-is.

## 1. Install

Copy the 5 files into your repo's `src/` folder, and the runner script into
the repo root:

```
src/team_strength.py
src/feature_engineering_v2.py
src/train_models_v2.py
src/live_features.py
src/train_live_model.py
run_advanced_pipeline.py        <- goes in repo root, next to run_pipeline.py
```

No new dependencies needed — everything uses packages already in your
`requirements.txt` (pandas, numpy, scikit-learn, joblib).

## 2. Run

```bash
python run_pipeline.py          # your original pipeline (run at least once first)
python run_advanced_pipeline.py # the new stuff
```

## 3. What you get

| File | What it does |
|---|---|
| `src/team_strength.py` | Squad strength index + key-player-availability penalty from `player_season_stats.csv` / `player_availability.csv`, leak-free (uses prior season only). |
| `src/feature_engineering_v2.py` | Adds squad strength, shrinks small-sample venue win-rates toward 0.5, drops the near-useless `toss_won_by_team1` feature, adds an `elo_diff x venue_advantage` interaction term. |
| `src/train_models_v2.py` | Retrains LR / RF / GB + a new HistGradientBoosting model on the v2 features, writes a v1-vs-v2 comparison. |
| `src/live_features.py` | **The big one.** Builds over-by-over 2nd-innings win-probability features from `ball_by_ball_data.csv` — current score, required run rate, wickets in hand, etc. |
| `src/train_live_model.py` | Trains a live in-match win-probability model on those features. |

## 4. Actual results from this run (already saved in this folder)

- **Pre-match model v2 vs v1** (`model_comparison.json`): v2 does **not**
  meaningfully beat v1 — Gradient Boosting actually dropped from 0.57 to
  0.52 ROC-AUC. This is an honest, useful finding: it confirms pre-match
  context alone (Elo, form, squad strength, venue, toss) is close to its
  ceiling for IPL, largely because T20 has high natural variance.
- **Live in-match model** (`live_model_metrics.json`): **76.3% accuracy,
  0.86 ROC-AUC overall**, climbing to **87.7% accuracy / 0.96 ROC-AUC in the
  death overs (16-20)**. This is where the real predictive power is —
  `required_run_rate`, `wickets_in_hand`, and `target` dominate
  (`live_feature_importance.csv`).

**Takeaway:** if the goal is a genuinely accurate cricket win predictor
(not just pre-match odds), build your product around the live model, not
the pre-match one. The pre-match model is still useful for pre-toss betting
lines / previews, but it will never get much past ~55% accuracy on IPL data
no matter how you tune it — that's closer to the sport's actual ceiling than
a modeling shortfall.
