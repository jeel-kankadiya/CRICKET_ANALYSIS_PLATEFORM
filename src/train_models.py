"""
train_models.py
----------------
PURPOSE:
    Trains and evaluates Machine Learning classifiers to predict IPL match outcomes.

MODELS TRAINED:
    1. Logistic Regression (Linear Baseline)
    2. Random Forest Classifier (Non-linear Ensemble)
    3. Gradient Boosting Classifier (Sequential Boosting Ensemble)

VALIDATION STRATEGY:
    Uses strict chronological time-series splitting (train on earlier seasons, test on recent ones)
    plus 5-fold TimeSeriesSplit cross-validation to prevent temporal data leakage.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, roc_auc_score, log_loss, brier_score_loss,
    classification_report, confusion_matrix
)

from feature_engineering import build_feature_matrix, FEATURE_COLS

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(ROOT, "models")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def prepare_dataset():
    """
    Loads the master feature matrix and filters out non-decisive matches (ties/no-results)
    and rows with missing values in feature columns.

    Returns:
        tuple: (clean_matches_df, final_elo_dict)
    """
    df, elo = build_feature_matrix()
    df = df[df["is_decisive"]].copy()  # Filter out ties and abandoned matches
    df = df.dropna(subset=FEATURE_COLS + ["team1_won"])
    return df, elo


def chronological_split(df: pd.DataFrame, test_size: float = 0.2):
    """
    Splits data chronologically into train and test sets without shuffling.

    Parameters:
        df (pd.DataFrame): Input matches DataFrame sorted by match_date.
        test_size (float): Proportion of matches allocated to the test set (default 20%).

    Returns:
        tuple: (train_df, test_df)
    """
    df = df.sort_values("match_date")
    split_idx = int(len(df) * (1.0 - test_size))
    train, test = df.iloc[:split_idx], df.iloc[split_idx:]
    return train, test


def evaluate(name: str, model, X_test, y_test, scaled: bool = False, scaler=None):
    """
    Evaluates a trained classifier on the test set using multiple metrics:
    Accuracy, ROC-AUC, Log Loss, and Brier Score Loss.

    Parameters:
        name (str): Model display name (e.g. 'Random Forest').
        model: Trained scikit-learn model object.
        X_test: Test features.
        y_test: True test labels (1 for team1 win, 0 for team2 win).
        scaled (bool): Whether to scale X_test using scaler before predicting.
        scaler: Fitted StandardScaler instance (required if scaled=True).

    Returns:
        tuple: (metrics_dict, predicted_probabilities_array)
    """
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
    return metrics, proba


def cross_validate_report(df: pd.DataFrame):
    """
    Performs 5-fold TimeSeriesSplit cross-validation across all models to compute
    stable, leak-free ROC-AUC estimates across historical seasons.

    Parameters:
        df (pd.DataFrame): Cleaned matches DataFrame.

    Returns:
        dict: Summary dictionary containing mean and std ROC-AUC per model.
    """
    df = df.sort_values("match_date").reset_index(drop=True)
    X, y = df[FEATURE_COLS].values, df["team1_won"].values
    tscv = TimeSeriesSplit(n_splits=5)

    cv_results = {"logistic_regression": [], "random_forest": [], "gradient_boosting": []}

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        scaler = StandardScaler().fit(X_train)
        lr = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), y_train)
        rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=10,
                                     random_state=42, n_jobs=-1).fit(X_train, y_train)
        gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                         random_state=42).fit(X_train, y_train)

        cv_results["logistic_regression"].append(
            roc_auc_score(y_test, lr.predict_proba(scaler.transform(X_test))[:, 1]))
        cv_results["random_forest"].append(
            roc_auc_score(y_test, rf.predict_proba(X_test)[:, 1]))
        cv_results["gradient_boosting"].append(
            roc_auc_score(y_test, gb.predict_proba(X_test)[:, 1]))

    print("\n=== 5-fold Time-Series Cross-Validation (ROC-AUC) ===")
    summary = {}
    for name, scores in cv_results.items():
        summary[name] = {
            "mean_roc_auc": float(np.mean(scores)),
            "std_roc_auc": float(np.std(scores)),
            "fold_scores": [round(s, 4) for s in scores]
        }
        print(f"  {name:20s} mean={np.mean(scores):.4f}  std={np.std(scores):.4f}  folds={[round(s,3) for s in scores]}")

    with open(os.path.join(OUTPUTS_DIR, "cv_results.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    """
    Main training execution function:
    1. Loads dataset and runs 5-fold TimeSeriesSplit cross-validation.
    2. Performs chronological train/test split (80/20).
    3. Fits Logistic Regression, Random Forest, and Gradient Boosting models.
    4. Identifies the best model based on ROC-AUC score.
    5. Saves fitted model artifacts (.pkl) to models/ and metrics/feature importances to outputs/.
    """
    df, elo = prepare_dataset()
    cross_validate_report(df)
    train, test = chronological_split(df, test_size=0.2)

    print(f"Train matches: {len(train)}  ({train['match_date'].min().date()} to {train['match_date'].max().date()})")
    print(f"Test matches:  {len(test)}  ({test['match_date'].min().date()} to {test['match_date'].max().date()})")

    X_train, y_train = train[FEATURE_COLS], train["team1_won"]
    X_test, y_test = test[FEATURE_COLS], test["team1_won"]

    # Scale features for linear model
    scaler = StandardScaler().fit(X_train)
    X_train_scaled = scaler.transform(X_train)

    results = {}

    # 1. Fit Logistic Regression
    lr = LogisticRegression(max_iter=1000, C=1.0)
    lr.fit(X_train_scaled, y_train)
    m, _ = evaluate("Logistic Regression", lr, X_test, y_test, scaled=True, scaler=scaler)
    results["logistic_regression"] = m

    # 2. Fit Random Forest
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_leaf=10,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    m, _ = evaluate("Random Forest", rf, X_test, y_test)
    results["random_forest"] = m

    # 3. Fit Gradient Boosting
    gb = GradientBoostingClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42
    )
    gb.fit(X_train, y_train)
    m, _ = evaluate("Gradient Boosting", gb, X_test, y_test)
    results["gradient_boosting"] = m

    # Select best model by ROC-AUC
    best_name = max(results, key=lambda k: results[k]["roc_auc"])
    print(f"\n>>> Best model: {best_name} (ROC-AUC={results[best_name]['roc_auc']:.4f})")

    # Save models to disk
    joblib.dump(lr, os.path.join(MODELS_DIR, "logistic_regression.pkl"))
    joblib.dump(rf, os.path.join(MODELS_DIR, "random_forest.pkl"))
    joblib.dump(gb, os.path.join(MODELS_DIR, "gradient_boosting.pkl"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))
    with open(os.path.join(MODELS_DIR, "best_model.txt"), "w") as f:
        f.write(best_name)

    # Save feature importances
    importances = pd.DataFrame({
        "feature": FEATURE_COLS,
        "random_forest_importance": rf.feature_importances_,
        "gradient_boosting_importance": gb.feature_importances_,
        "logistic_regression_coef": lr.coef_[0],
    }).sort_values("random_forest_importance", ascending=False)

    importances.to_csv(os.path.join(OUTPUTS_DIR, "feature_importance.csv"), index=False)
    print("\nFeature importances:\n", importances.to_string(index=False))

    with open(os.path.join(OUTPUTS_DIR, "model_metrics.json"), "w") as f:
        json.dump(results, f, indent=2)

    with open(os.path.join(OUTPUTS_DIR, "elo_final_ratings.json"), "w") as f:
        json.dump({k: round(v, 1) for k, v in elo.items()}, f, indent=2)

    return results, importances


if __name__ == "__main__":
    main()
