"""
train_live_model.py
---------------------
PURPOSE:
    Trains the IN-MATCH ("live") win-probability model using the over-by-over
    2nd-innings snapshots from live_features.py. This is expected to
    outperform every pre-match model in outputs/model_metrics.json /
    model_metrics_v2.json by a wide margin, because live game-state (how far
    behind/ahead of the required run rate the chasing team is, wickets in
    hand) is a vastly stronger signal than any pre-match context can be in a
    sport this volatile.

VALIDATION STRATEGY:
    Chronological match-level split (NOT row-level) — all snapshots from a
    given match go entirely into either train or test, so the model is never
    tested on a different over of a match it partially trained on.

OUTPUTS:
    models/live_win_probability.pkl       -- fitted HistGradientBoosting model
    outputs/live_model_metrics.json       -- overall + phase-of-innings metrics
    outputs/live_feature_importance.csv
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss

from live_features import build_live_feature_matrix, LIVE_FEATURE_COLS

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(ROOT, "models")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def match_level_split(df: pd.DataFrame, test_size: float = 0.2):
    """
    Splits by MATCH, chronologically, so every over-by-over row from a given
    match stays together in either train or test. Ordering matches by their
    earliest snapshot keeps the split time-consistent with the rest of the
    pipeline (train on older matches, test on the most recent ones).
    """
    match_order = df.groupby("match_id")["over_completed"].count().index  # arbitrary stable order
    # Use match_id as a proxy for chronology isn't reliable on its own, so
    # instead order by the row order already present (build_live_feature_matrix
    # preserves ball_by_ball_data's chronological match ordering via match_id
    # merge order); safer to sort by match_id's first appearance index.
    first_seen = df.reset_index().groupby("match_id")["index"].min().sort_values()
    ordered_match_ids = first_seen.index.tolist()

    split_idx = int(len(ordered_match_ids) * (1.0 - test_size))
    train_ids = set(ordered_match_ids[:split_idx])
    test_ids = set(ordered_match_ids[split_idx:])

    train = df[df["match_id"].isin(train_ids)].copy()
    test = df[df["match_id"].isin(test_ids)].copy()
    return train, test


def evaluate_by_phase(model, df: pd.DataFrame):
    """
    Reports accuracy/ROC-AUC broken out by innings phase (early / middle /
    death overs), since a live model's usefulness is precisely that it should
    get MORE confident as the chase progresses — this confirms that's happening.
    """
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

    model = HistGradientBoostingClassifier(
        max_iter=300, max_depth=5, learning_rate=0.05,
        l2_regularization=1.0, random_state=42,
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
    print("\n=== Live Win-Probability Model (overall, held-out matches) ===")
    for k, v in overall_metrics.items():
        print(f"  {k:12s}: {v:.4f}")

    phase_metrics = evaluate_by_phase(model, test)
    print("\n=== Accuracy by innings phase ===")
    for phase, m in phase_metrics.items():
        print(f"  {phase:22s} n={m['n_snapshots']:5d}  accuracy={m['accuracy']:.4f}  roc_auc={m['roc_auc']:.4f}")

    # Permutation importance (HistGradientBoostingClassifier has no native
    # .feature_importances_, unlike RandomForest/GradientBoosting).
    perm = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42, n_jobs=-1)
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
