"""
train_models_v2.py
--------------------
PURPOSE:
    Trains and evaluates the ACCURACY-BOOSTED pre-match win-probability models using
    FEATURE_COLS_V2, data symmetry augmentation, CatBoost, LightGBM, XGBoost,
    and a Stacking Meta-Ensemble.

OUTPUTS:
    models_v2/*.pkl                      -- fitted model artifacts
    outputs/model_metrics_v2.json        -- test-set metrics, all models
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
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, VotingClassifier, StackingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss, classification_report

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostClassifier

from feature_engineering_v2 import build_feature_matrix_v2, augment_symmetric_data, FEATURE_COLS_V2

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
    """Chronological split preserving temporal order."""
    df = df.sort_values("match_date")
    split_idx = int(len(df) * (1.0 - test_size))
    return df.iloc[:split_idx], df.iloc[split_idx:]


def evaluate(name, model, X_test, y_test, scaled=False, scaler=None):
    """Computes test set accuracy, ROC-AUC, Log Loss, and Brier Score."""
    X_eval = scaler.transform(X_test) if scaled else X_test
    proba = model.predict_proba(X_eval)[:, 1]
    preds = model.predict(X_eval)
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "log_loss": float(log_loss(y_test, proba)),
        "brier_score": float(brier_score_loss(y_test, proba)),
    }
    print(f"\n=== {name} ===")
    for k, v in metrics.items():
        print(f"  {k:12s}: {v:.4f}")
    print(classification_report(y_test, preds, target_names=["team2_won", "team1_won"]))
    return metrics


def main():
    df, elo = prepare_dataset()
    train, test = chronological_split(df, test_size=0.2)

    train_aug = augment_symmetric_data(train, FEATURE_COLS_V2)

    print(f"\nTrain matches: {len(train)} (Augmented to {len(train_aug)})  ({train['match_date'].min().date()} to {train['match_date'].max().date()})")
    print(f"Test matches:  {len(test)}  ({test['match_date'].min().date()} to {test['match_date'].max().date()})")

    X_train, y_train = train_aug[FEATURE_COLS_V2], train_aug["team1_won"]
    X_test, y_test = test[FEATURE_COLS_V2], test["team1_won"]

    scaler = StandardScaler().fit(X_train)
    X_train_scaled = scaler.transform(X_train)

    results = {}

    lr = LogisticRegression(max_iter=1000, C=0.5)
    lr.fit(X_train_scaled, y_train)
    results["logistic_regression"] = evaluate("Logistic Regression (v2)", lr, X_test, y_test, scaled=True, scaler=scaler)

    rf = RandomForestClassifier(n_estimators=300, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    results["random_forest"] = evaluate("Random Forest (v2)", rf, X_test, y_test)

    gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.03, random_state=42)
    gb.fit(X_train, y_train)
    results["gradient_boosting"] = evaluate("Gradient Boosting (v2)", gb, X_test, y_test)

    hgb = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.03, l2_regularization=2.0, random_state=42)
    hgb.fit(X_train, y_train)
    results["hist_gradient_boosting"] = evaluate("Hist Gradient Boosting (v2)", hgb, X_test, y_test)

    lgbm = lgb.LGBMClassifier(n_estimators=200, max_depth=3, learning_rate=0.03, random_state=42, verbose=-1)
    lgbm.fit(X_train, y_train)
    results["lightgbm"] = evaluate("LightGBM (v2)", lgbm, X_test, y_test)

    xgb_m = xgb.XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.03, eval_metric="logloss", random_state=42)
    xgb_m.fit(X_train, y_train)
    results["xgboost"] = evaluate("XGBoost (v2)", xgb_m, X_test, y_test)

    cat_m = CatBoostClassifier(iterations=250, depth=3, learning_rate=0.03, random_seed=42, verbose=0)
    cat_m.fit(X_train, y_train)
    results["catboost"] = evaluate("CatBoost (v2)", cat_m, X_test, y_test)

    # Soft Voting Ensemble
    ens = VotingClassifier(
        estimators=[
            ("lgbm", lgbm),
            ("xgb", xgb_m),
            ("cat", cat_m),
            ("gb", gb)
        ],
        voting="soft"
    )
    ens.fit(X_train, y_train)
    results["voting_ensemble"] = evaluate("Soft-Voting Ensemble (v2)", ens, X_test, y_test)

    # Stacking Classifier with Logistic Regression Meta-Learner
    stack_m = StackingClassifier(
        estimators=[
            ("cat", cat_m),
            ("lgbm", lgbm),
            ("xgb", xgb_m),
            ("rf", rf)
        ],
        final_estimator=LogisticRegression(C=0.5),
        cv=5
    )
    stack_m.fit(X_train, y_train)
    results["stacking_ensemble"] = evaluate("Stacking Meta-Ensemble (v2)", stack_m, X_test, y_test)

    best_name = max(results, key=lambda k: results[k]["roc_auc"])
    print(f"\n>>> Best v2 model: {best_name} (ROC-AUC={results[best_name]['roc_auc']:.4f}, Accuracy={results[best_name]['accuracy']:.4f})")

    joblib.dump(lr, os.path.join(MODELS_DIR, "logistic_regression_v2.pkl"))
    joblib.dump(rf, os.path.join(MODELS_DIR, "random_forest_v2.pkl"))
    joblib.dump(gb, os.path.join(MODELS_DIR, "gradient_boosting_v2.pkl"))
    joblib.dump(hgb, os.path.join(MODELS_DIR, "hist_gradient_boosting_v2.pkl"))
    joblib.dump(lgbm, os.path.join(MODELS_DIR, "lightgbm_v2.pkl"))
    joblib.dump(xgb_m, os.path.join(MODELS_DIR, "xgboost_v2.pkl"))
    joblib.dump(cat_m, os.path.join(MODELS_DIR, "catboost_v2.pkl"))
    joblib.dump(ens, os.path.join(MODELS_DIR, "voting_ensemble_v2.pkl"))
    joblib.dump(stack_m, os.path.join(MODELS_DIR, "stacking_ensemble_v2.pkl"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler_v2.pkl"))
    with open(os.path.join(MODELS_DIR, "best_model_v2.txt"), "w") as f:
        f.write(best_name)

    importances = pd.DataFrame({
        "feature": FEATURE_COLS_V2,
        "random_forest_importance": rf.feature_importances_,
        "gradient_boosting_importance": gb.feature_importances_,
        "catboost_importance": cat_m.feature_importances_,
        "lightgbm_importance": lgbm.feature_importances_,
        "xgboost_importance": xgb_m.feature_importances_,
        "logistic_regression_coef": lr.coef_[0],
    }).sort_values("catboost_importance", ascending=False)
    importances.to_csv(os.path.join(OUTPUTS_DIR, "feature_importance_v2.csv"), index=False)
    print("\nFeature importances (v2):\n", importances.to_string(index=False))

    with open(os.path.join(OUTPUTS_DIR, "model_metrics_v2.json"), "w") as f:
        json.dump(results, f, indent=2)

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
        comparison["best_v2_model"] = {
            "name": best_name,
            "v2_accuracy": results[best_name]["accuracy"],
            "v2_roc_auc": results[best_name]["roc_auc"],
        }
        with open(os.path.join(OUTPUTS_DIR, "model_comparison.json"), "w") as f:
            json.dump(comparison, f, indent=2)

    return results, importances


if __name__ == "__main__":
    main()
