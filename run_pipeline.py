"""
run_pipeline.py
-----------------
Runs the full Cricket Intelligence Platform pipeline end-to-end:

  1. Load & clean raw data                 (src/data_loader.py)
  2. Compute Elo team ratings               (src/elo_rating.py)
  3. Engineer leak-free match features      (src/feature_engineering.py)
  4. Train & evaluate 3 ML models           (src/train_models.py)
  5. Compute player performance ratings     (src/player_analytics.py)
  6. Compute new-dataset analytics          (src/dataset_analytics.py)
  7. Precompute all dashboard data          (src/generate_dashboard_data.py)

Run from the project root:
    pip install -r requirements.txt
    python run_pipeline.py

Then open dashboard/index.html in any browser to explore results.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def main():
    print("=" * 60)
    print("CRICKET INTELLIGENCE PLATFORM — full pipeline run")
    print("=" * 60)

    print("\n[1/5] Computing Elo ratings...")
    import elo_rating
    from data_loader import load_matches
    m = load_matches()
    m, ratings = elo_rating.compute_elo_ratings(m)
    print(f"  -> {len(ratings)} teams rated, top team: "
          f"{max(ratings, key=ratings.get)} ({max(ratings.values()):.1f})")

    print("\n[2/5] Building feature matrix (Elo + form + venue + h2h + toss)...")
    from feature_engineering import build_feature_matrix
    df, elo = build_feature_matrix()
    print(f"  -> {len(df)} matches, {df.shape[1]} columns")

    print("\n[3/5] Training win-probability models (LR / RF / GB)...")
    import train_models
    train_models.main()

    print("\n[4/5] Computing player performance ratings...")
    import player_analytics
    player_ratings = player_analytics.build_player_ratings()
    player_ratings.to_csv(
        os.path.join(os.path.dirname(__file__), "outputs", "player_ratings.csv"),
        index=False
    )
    print(f"  -> {len(player_ratings)} players rated")

    print("\n[5/6] Computing new-dataset analytics (auction / venue / points / trends / availability)...")
    import dataset_analytics
    analytics = dataset_analytics.build_all_analytics()
    import json
    analytics_path = os.path.join(os.path.dirname(__file__), "outputs", "dataset_analytics.json")
    with open(analytics_path, "w") as f:
        json.dump(analytics, f, default=str)
    print(f"  -> Analytics saved: {analytics_path}")

    print("\n[6/6] Precomputing dashboard data bundle...")
    import generate_dashboard_data
    generate_dashboard_data.main()

    print("\n" + "=" * 60)
    print("DONE. Open dashboard/index.html in a browser to explore results.")
    print("=" * 60)


if __name__ == "__main__":
    main()
