"""
train_models_v2.py
--------------------
PURPOSE:
    Trains and evaluates the IMPROVED pre-match win-probability models using
    FEATURE_COLS_V2 (squad strength, availability, shrunk venue win-rate,
    elo x venue interaction, toss_won_by_team1 dropped) and compares them
    directly against the original 9-feature results.

MODELS TRAINED:
    1. Logistic Regression       (linear baseline)
    2. Random Forest              (non-linear ensemble)
    3. Gradient Boosting          (sequential boosting ensemble)
    4. Hist Gradient Boosting     (sklearn's XGBoost-style histogram-based
                                    booster — usually the strongest of the four
                                    on tabular data like this, and a good
                                    stand-in when xgboost/lightgbm aren't
                                    installed)

VALIDATION STRATEGY: identical to train_models.py — chronological 80/20
split plus 5-fold TimeSeriesSplit cross-validation, so results are directly
comparable to outputs/model_metrics.json and outputs/cv_results.json.

OUTPUTS:
    models_v2/*.pkl                      -- fitted model artifacts
    outputs/model_metrics_v2.json        -- test-set metrics, all 4 models
    outputs/cv_results_v2.json           -- 5-fold TimeSeriesSplit ROC-AUC
    outputs/feature_importance_v2.csv    -- importances for FEATURE_COLS_V2
    outputs/model_comparison.json        -- v1 vs v2 metrics side by side
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss, classification_report

from feature_engineering_v2 import build_feature_matrix_v2, FEATURE_COLS_V2

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(ROOT, "models_v2")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def prepare_dataset():
    """Loads the v2 feature matrix and drops non-decisive / incomplete rows."""
    df, elo = build_feature_matrix_v2()
    df = df[df["is_decisive"]].copy()
    df = df.dropna(subset=FEATURE_COLS_V2 + ["team1_won"])
    return df, elo


def chronological_split(df: pd.DataFrame, test_size: float = 0.2):
    """Same chronological (non-shuffled) split used by train_models.py."""
    df = df.sort_values("match_date")
    split_idx = int(len(df) * (1.0 - test_size))
    return df.iloc[:split_idx], df.iloc[split_idx:]


def evaluate(name, model, X_test, y_test, scaled=False, scaler=None):
    """Same metric set as train_models.py: accuracy, ROC-AUC, log loss, Brier score."""
    X_eval = scaler.transform(X_test) if scaled else X_test
    proba = model.predict_proba(X_eval)[:, 1]
    preds = model.predict(X_eval)
    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "roc_auc": roc_auc_score(y_test, proba),
        "log_loss": log_loss(y_test, proba),
        "brier_score": brier_score_loss(y_test, proba),
    }
    print(f"\n=== {name} ===")
    for k, v in metrics.items():
        print(f"  {k:12s}: {v:.4f}")
    print(classification_report(y_test, preds, target_names=["team2_won", "team1_won"]))
    return metrics


def cross_validate_report(df: pd.DataFrame):
    """5-fold TimeSeriesSplit ROC-AUC across all 4 models, same protocol as v1."""
    df = df.sort_values("match_date").reset_index(drop=True)
    X, y = df[FEATURE_COLS_V2].values, df["team1_won"].values
    tscv = TimeSeriesSplit(n_splits=5)

    cv_results = {"logistic_regression": [], "random_forest": [], "gradient_boosting": [], "hist_gradient_boosting": []}

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        scaler = StandardScaler().fit(X_train)
        lr = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), y_train)
        rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=10,
                                     random_state=42, n_jobs=-1).fit(X_train, y_train)
        gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                         random_state=42).fit(X_train, y_train)
        hgb = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05,
                                              l2_regularization=1.0, random_state=42).fit(X_train, y_train)

        cv_results["logistic_regression"].append(roc_auc_score(y_test, lr.predict_proba(scaler.transform(X_test))[:, 1]))
        cv_results["random_forest"].append(roc_auc_score(y_test, rf.predict_proba(X_test)[:, 1]))
        cv_results["gradient_boosting"].append(roc_auc_score(y_test, gb.predict_proba(X_test)[:, 1]))
        cv_results["hist_gradient_boosting"].append(roc_auc_score(y_test, hgb.predict_proba(X_test)[:, 1]))

    print("\n=== 5-fold Time-Series Cross-Validation (ROC-AUC), v2 features ===")
    summary = {}
    for name, scores in cv_results.items():
        summary[name] = {
            "mean_roc_auc": float(np.mean(scores)),
            "std_roc_auc": float(np.std(scores)),
            "fold_scores": [round(s, 4) for s in scores],
        }
        print(f"  {name:24s} mean={np.mean(scores):.4f}  std={np.std(scores):.4f}  folds={[round(s,3) for s in scores]}")

    with open(os.path.join(OUTPUTS_DIR, "cv_results_v2.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    df, elo = prepare_dataset()
    cross_validate_report(df)
    train, test = chronological_split(df, test_size=0.2)

    print(f"\nTrain matches: {len(train)}  ({train['match_date'].min().date()} to {train['match_date'].max().date()})")
    print(f"Test matches:  {len(test)}  ({test['match_date'].min().date()} to {test['match_date'].max().date()})")

    X_train, y_train = train[FEATURE_COLS_V2], train["team1_won"]
    X_test, y_test = test[FEATURE_COLS_V2], test["team1_won"]

    scaler = StandardScaler().fit(X_train)
    X_train_scaled = scaler.transform(X_train)

    results = {}

    lr = LogisticRegression(max_iter=1000, C=1.0)
    lr.fit(X_train_scaled, y_train)
    results["logistic_regression"] = evaluate("Logistic Regression (v2)", lr, X_test, y_test, scaled=True, scaler=scaler)

    rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=10, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    results["random_forest"] = evaluate("Random Forest (v2)", rf, X_test, y_test)

    gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
    gb.fit(X_train, y_train)
    results["gradient_boosting"] = evaluate("Gradient Boosting (v2)", gb, X_test, y_test)

    hgb = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05, l2_regularization=1.0, random_state=42)
    hgb.fit(X_train, y_train)
    results["hist_gradient_boosting"] = evaluate("Hist Gradient Boosting (v2)", hgb, X_test, y_test)

    best_name = max(results, key=lambda k: results[k]["roc_auc"])
    print(f"\n>>> Best v2 model: {best_name} (ROC-AUC={results[best_name]['roc_auc']:.4f})")

    joblib.dump(lr, os.path.join(MODELS_DIR, "logistic_regression_v2.pkl"))
    joblib.dump(rf, os.path.join(MODELS_DIR, "random_forest_v2.pkl"))
    joblib.dump(gb, os.path.join(MODELS_DIR, "gradient_boosting_v2.pkl"))
    joblib.dump(hgb, os.path.join(MODELS_DIR, "hist_gradient_boosting_v2.pkl"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler_v2.pkl"))
    with open(os.path.join(MODELS_DIR, "best_model_v2.txt"), "w") as f:
        f.write(best_name)

    importances = pd.DataFrame({
        "feature": FEATURE_COLS_V2,
        "random_forest_importance": rf.feature_importances_,
        "gradient_boosting_importance": gb.feature_importances_,
        "logistic_regression_coef": lr.coef_[0],
    }).sort_values("random_forest_importance", ascending=False)
    importances.to_csv(os.path.join(OUTPUTS_DIR, "feature_importance_v2.csv"), index=False)
    print("\nFeature importances (v2):\n", importances.to_string(index=False))

    with open(os.path.join(OUTPUTS_DIR, "model_metrics_v2.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Side-by-side comparison against the original v1 metrics, if present.
    v1_path = os.path.join(OUTPUTS_DIR, "model_metrics.json")
    if os.path.exists(v1_path):
        with open(v1_path) as f:
            v1_results = json.load(f)
        comparison = {}
        for model_name in ["logistic_regression", "random_forest", "gradient_boosting"]:
            if model_name in v1_results:
                comparison[model_name] = {
                    "v1_accuracy": v1_results[model_name]["accuracy"],
                    "v2_accuracy": results[model_name]["accuracy"],
                    "v1_roc_auc": v1_results[model_name]["roc_auc"],
                    "v2_roc_auc": results[model_name]["roc_auc"],
                    "roc_auc_delta": results[model_name]["roc_auc"] - v1_results[model_name]["roc_auc"],
                }
        comparison["hist_gradient_boosting_v2_only"] = {
            "v2_accuracy": results["hist_gradient_boosting"]["accuracy"],
            "v2_roc_auc": results["hist_gradient_boosting"]["roc_auc"],
        }
        with open(os.path.join(OUTPUTS_DIR, "model_comparison.json"), "w") as f:
            json.dump(comparison, f, indent=2)
        print("\n=== v1 vs v2 comparison ===")
        for model_name, c in comparison.items():
            print(f"  {model_name}: {json.dumps(c)}")

    return results, importances


if __name__ == "__main__":
    main()
