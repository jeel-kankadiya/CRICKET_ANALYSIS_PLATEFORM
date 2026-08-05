"""
run_advanced_pipeline.py
--------------------------
Runs the ADVANCED extensions to the Cricket Intelligence Platform end-to-end,
on top of (does not replace) the original run_pipeline.py:

  1. Squad strength + availability features   (src/team_strength.py)
  2. Improved pre-match feature matrix v2      (src/feature_engineering_v2.py)
  3. Train + evaluate 4 pre-match models v2    (src/train_models_v2.py)
  4. Build in-match (live) feature matrix      (src/live_features.py)
  5. Train + evaluate the live win-prob model  (src/train_live_model.py)

Run from the project root, AFTER running the original pipeline at least once
(this reuses outputs/model_metrics.json for the v1-vs-v2 comparison):

    pip install -r requirements.txt
    python run_pipeline.py            # original pipeline (if not already run)
    python run_advanced_pipeline.py   # this script

New output files produced:
    outputs/model_metrics_v2.json
    outputs/cv_results_v2.json
    outputs/feature_importance_v2.csv
    outputs/model_comparison.json
    outputs/live_model_metrics.json
    outputs/live_feature_importance.csv
    models_v2/*.pkl
    models/live_win_probability.pkl
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main():
    print("=" * 60)
    print("CRICKET INTELLIGENCE PLATFORM — advanced pipeline run")
    print("=" * 60)

    print("\n[1/3] Building squad strength + availability features...")
    import team_strength
    strength = team_strength.build_strength_features()
    print(f"  -> strength features built for {len(strength)} match rows")

    print("\n[2/3] Training improved pre-match models (v2)...")
    import train_models_v2
    train_models_v2.main()

    print("\n[3/3] Building live in-match features and training live win-probability model...")
    import train_live_model
    train_live_model.main()

    print("\n" + "=" * 60)
    print("DONE. See outputs/model_comparison.json for v1 vs v2, and")
    print("outputs/live_model_metrics.json for the in-match model's accuracy.")
    print("=" * 60)


if __name__ == "__main__":
    main()
