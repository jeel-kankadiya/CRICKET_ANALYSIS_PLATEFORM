"""
train_live_model.py
---------------------
PURPOSE:
    Trains the ACCURACY-BOOSTED IN-MATCH ("live") win-probability model using CatBoost, LightGBM,
    XGBoost, HistGradientBoosting, and a Stacking Meta-Ensemble on over-by-over
    2nd-innings snapshots from live_features.py.

OUTPUTS:
    models/live_win_probability.pkl       -- fitted live win-probability ensemble model
    outputs/live_model_metrics.json       -- overall + phase-of-innings metrics
    outputs/live_feature_importance.csv
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingClassifier, GradientBoostingClassifier, VotingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostClassifier

from live_features import build_live_feature_matrix, LIVE_FEATURE_COLS

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(ROOT, "models")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def match_level_split(df: pd.DataFrame, test_size: float = 0.2):
    """
    Splits by MATCH, chronologically, so all over-by-over rows from a given
    match stay together in either train or test.
    """
    first_seen = df.reset_index().groupby("match_id")["index"].min().sort_values()
    ordered_match_ids = first_seen.index.tolist()

    split_idx = int(len(ordered_match_ids) * (1.0 - test_size))
    train_ids = set(ordered_match_ids[:split_idx])
    test_ids = set(ordered_match_ids[split_idx:])

    train = df[df["match_id"].isin(train_ids)].copy()
    test = df[df["match_id"].isin(test_ids)].copy()
    return train, test


def evaluate_by_phase(model, df: pd.DataFrame):
    """Reports accuracy/ROC-AUC broken out by innings phase."""
    X = df[LIVE_FEATURE_COLS]
    proba = model.predict_proba(X)[:, 1]
    preds = model.predict(X)
    df = df.copy()
    df["_proba"] = proba
    df["_pred"] = preds

    phases = {
        "overs_1_6_powerplay": df["over_completed"] <= 6,
        "overs_7_15_middle": (df["over_completed"] > 6) & (df["over_completed"] < 16),
        "overs_16_20_death": df["over_completed"] >= 16,
    }

    phase_metrics = {}
    for phase_name, mask in phases.items():
        sub = df[mask]
        if len(sub) < 10:
            continue
        phase_metrics[phase_name] = {
            "n_snapshots": int(len(sub)),
            "accuracy": float(accuracy_score(sub["chasing_team_won"], sub["_pred"])),
            "roc_auc": float(roc_auc_score(sub["chasing_team_won"], sub["_proba"])),
        }
    return phase_metrics


def main():
    df = build_live_feature_matrix()
    print(f"Live feature matrix: {len(df)} snapshots from {df['match_id'].nunique()} matches")

    train, test = match_level_split(df, test_size=0.2)
    print(f"Train: {len(train)} snapshots / {train['match_id'].nunique()} matches")
    print(f"Test:  {len(test)} snapshots / {test['match_id'].nunique()} matches")

    X_train, y_train = train[LIVE_FEATURE_COLS], train["chasing_team_won"]
    X_test, y_test = test[LIVE_FEATURE_COLS], test["chasing_team_won"]

    cat_m = CatBoostClassifier(iterations=300, depth=4, learning_rate=0.03, random_seed=42, verbose=0)
    lgbm = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.03, random_state=42, verbose=-1)
    xgb_m = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.03, eval_metric="logloss", random_state=42)
    hgb = HistGradientBoostingClassifier(max_iter=300, max_depth=5, learning_rate=0.03, l2_regularization=1.0, random_state=42)

    # Stacking Classifier with Logistic Regression Meta-Learner
    model = StackingClassifier(
        estimators=[
            ("cat", cat_m),
            ("lgbm", lgbm),
            ("xgb", xgb_m),
            ("hgb", hgb)
        ],
        final_estimator=LogisticRegression(C=0.5),
        cv=5
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)

    overall_metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "log_loss": float(log_loss(y_test, proba)),
        "brier_score": float(brier_score_loss(y_test, proba)),
    }
    print("\n=== Live Win-Probability Stacking Ensemble (overall, held-out matches) ===")
    for k, v in overall_metrics.items():
        print(f"  {k:12s}: {v:.4f}")

    phase_metrics = evaluate_by_phase(model, test)
    print("\n=== Accuracy by innings phase ===")
    for phase, m in phase_metrics.items():
        print(f"  {phase:22s} n={m['n_snapshots']:5d}  accuracy={m['accuracy']:.4f}  roc_auc={m['roc_auc']:.4f}")

    perm = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=42, n_jobs=1)
    importance_df = pd.DataFrame({
        "feature": LIVE_FEATURE_COLS,
        "importance_mean": perm.importances_mean,
        "importance_std": perm.importances_std,
    }).sort_values("importance_mean", ascending=False)
    print("\nPermutation feature importance:\n", importance_df.to_string(index=False))

    joblib.dump(model, os.path.join(MODELS_DIR, "live_win_probability.pkl"))
    importance_df.to_csv(os.path.join(OUTPUTS_DIR, "live_feature_importance.csv"), index=False)
    with open(os.path.join(OUTPUTS_DIR, "live_model_metrics.json"), "w") as f:
        json.dump({"overall": overall_metrics, "by_phase": phase_metrics}, f, indent=2)

    return overall_metrics, phase_metrics, importance_df


if __name__ == "__main__":
    main()
