"""
elo_rating.py
--------------
Chess-style Elo rating system adapted for T20 cricket. Every team starts at
1500. After each decisive match, ratings are updated based on the expected
vs actual result, with a K-factor and a small home/neutral adjustment left
out (venue effects are captured separately as a feature).

We also track a "form" Elo delta (change over last N matches) which is a
useful predictive signal independent of the absolute rating.
"""

import pandas as pd
import numpy as np
from collections import defaultdict

BASE_RATING = 1500
K_FACTOR = 32


def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def compute_elo_ratings(matches: pd.DataFrame):
    """
    Walks through matches in chronological order and computes pre-match Elo
    ratings for team1 and team2 (i.e. the rating BEFORE that match's result
    is applied -- this avoids leakage when used as a model feature).

    Returns the matches DataFrame with two new columns:
        team1_elo_pre, team2_elo_pre
    and a dict of final ratings {team_name: rating}.
    """
    ratings = defaultdict(lambda: BASE_RATING)
    team1_elo_pre = []
    team2_elo_pre = []

    for _, row in matches.iterrows():
        t1, t2 = row["team1_name"], row["team2_name"]
        r1, r2 = ratings[t1], ratings[t2]
        team1_elo_pre.append(r1)
        team2_elo_pre.append(r2)

        if not row["is_decisive"] or pd.isna(t1) or pd.isna(t2):
            continue

        exp1 = expected_score(r1, r2)
        exp2 = 1 - exp1
        actual1 = 1 if row["team1_won"] == 1 else 0
        actual2 = 1 - actual1

        ratings[t1] = r1 + K_FACTOR * (actual1 - exp1)
        ratings[t2] = r2 + K_FACTOR * (actual2 - exp2)

    matches = matches.copy()
    matches["team1_elo_pre"] = team1_elo_pre
    matches["team2_elo_pre"] = team2_elo_pre
    matches["elo_diff"] = matches["team1_elo_pre"] - matches["team2_elo_pre"]

    return matches, dict(ratings)


if __name__ == "__main__":
    from data_loader import load_matches

    m = load_matches()
    m, final_ratings = compute_elo_ratings(m)
    print("Final Elo ratings (current team strength):\n")
    for team, rating in sorted(final_ratings.items(), key=lambda x: -x[1]):
        print(f"  {team:35s} {rating:7.1f}")
