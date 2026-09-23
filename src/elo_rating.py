"""
elo_rating.py
--------------
PURPOSE:
    Implements a Chess-style Elo rating system adapted for T20 cricket matches.
    Tracks relative team strength dynamically across all historical IPL seasons.

HOW IT WORKS:
    1. Every team starts with a baseline Elo rating of 1500.
    2. Before each match, win probabilities are calculated based on rating differences.
    3. After each decisive match, ratings update using expected vs. actual outcomes:
       New_Rating = Old_Rating + K * (Actual_Result - Expected_Result)
    4. Ratings are calculated in strictly chronological order to prevent data leakage.
"""

import pandas as pd
import numpy as np
from collections import defaultdict

# Global constants for Elo calculation
BASE_RATING = 1500  # Default initial rating for any team appearing for the first time
K_FACTOR = 32       # Weight/sensitivity factor controlling rating update size after a match


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Computes the expected win probability for Team A playing against Team B.

    Mathematical Formula:
        E_A = 1 / (1 + 10^((Rating_B - Rating_A) / 400))

    Parameters:
        rating_a (float): Current pre-match Elo rating of Team A.
        rating_b (float): Current pre-match Elo rating of Team B.

    Returns:
        float: Expected outcome for Team A between 0.0 (certain loss) and 1.0 (certain win).
               If ratings are equal (1500 vs 1500), returns 0.5 (50% chance).
    """
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def compute_elo_ratings(matches: pd.DataFrame, mean_reversion_rate: float = 0.25):
    """
    Walks through all matches in strict chronological order and calculates
    pre-match Elo ratings for both teams before updating ratings post-match.

    Enhancements for maximum accuracy:
        1. Season-to-Season Mean Reversion: At the start of a new season, ratings
           are pulled 25% back toward 1500 to account for player auctions/roster changes.
        2. Margin-of-Victory Scaling: Dominant wins (large run/wicket margin) adjust
           ratings slightly more than 1-run / 1-wicket nail-biters.

    Returns:
        tuple: (matches_df, final_ratings_dict)
    """
    ratings = defaultdict(lambda: BASE_RATING)
    team1_elo_pre = []
    team2_elo_pre = []
    current_season = None

    for _, row in matches.iterrows():
        t1, t2 = row["team1_name"], row["team2_name"]
        season = str(row.get("season", ""))

        # Season transition: apply mean reversion to all active team ratings
        if current_season is not None and season != current_season:
            for team in list(ratings.keys()):
                ratings[team] = ratings[team] * (1.0 - mean_reversion_rate) + BASE_RATING * mean_reversion_rate
        current_season = season

        r1, r2 = ratings[t1], ratings[t2]
        
        # Record pre-match ratings BEFORE applying match outcome
        team1_elo_pre.append(r1)
        team2_elo_pre.append(r2)

        # Skip rating updates for non-decisive (tied/abandoned) or invalid matches
        if not row["is_decisive"] or pd.isna(t1) or pd.isna(t2):
            continue

        # Calculate expected probabilities for both teams
        exp1 = expected_score(r1, r2)
        exp2 = 1.0 - exp1
        
        # Binary outcome: 1 if team1 won, 0 if team2 won
        actual1 = 1 if row["team1_won"] == 1 else 0
        actual2 = 1 - actual1

        # Margin-of-victory multiplier
        runs_m = row.get("win_by_runs", 0)
        wkts_m = row.get("win_by_wickets", 0)
        margin_scale = 1.0
        if not pd.isna(runs_m) and runs_m > 0:
            margin_scale = np.log(1.0 + runs_m / 10.0) + 0.8
        elif not pd.isna(wkts_m) and wkts_m > 0:
            margin_scale = np.log(1.0 + wkts_m / 2.0) + 0.8
        margin_scale = float(np.clip(margin_scale, 0.8, 2.0))

        k_eff = K_FACTOR * margin_scale

        # Update Elo ratings based on outcome error
        ratings[t1] = r1 + k_eff * (actual1 - exp1)
        ratings[t2] = r2 + k_eff * (actual2 - exp2)

    # Attach calculated features to DataFrame
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
