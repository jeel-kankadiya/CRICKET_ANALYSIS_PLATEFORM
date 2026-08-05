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


def compute_elo_ratings(matches: pd.DataFrame):
    """
    Walks through all matches in strict chronological order and calculates
    pre-match Elo ratings for both teams before updating ratings post-match.

    Why Pre-Match Elo?
        Recording pre-match Elo ensures no target leakage when using Elo as an
        explanatory feature in downstream Machine Learning win-prediction models.

    Processing Steps:
        1. Initialize all teams with baseline rating (1500).
        2. Iterate over matches sorted by date.
        3. Record pre-match ratings for team1 and team2.
        4. If match is decisive (not a tie/no-result), compute expected outcome and
           update both teams' ratings using K_FACTOR.
        5. Calculate rating difference: (team1_elo_pre - team2_elo_pre).

    Parameters:
        matches (pd.DataFrame): Sorted matches DataFrame from data_loader.load_matches().

    Returns:
        tuple: (matches_df, final_ratings_dict)
            - matches_df (pd.DataFrame): Matches copy with added 'team1_elo_pre',
              'team2_elo_pre', and 'elo_diff' columns.
            - final_ratings_dict (dict): Latest Elo ratings for all active franchises.
    """
    # Use defaultdict so any newly encountered team automatically starts at 1500
    ratings = defaultdict(lambda: BASE_RATING)
    team1_elo_pre = []
    team2_elo_pre = []

    for _, row in matches.iterrows():
        t1, t2 = row["team1_name"], row["team2_name"]
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

        # Update Elo ratings based on outcome error
        ratings[t1] = r1 + K_FACTOR * (actual1 - exp1)
        ratings[t2] = r2 + K_FACTOR * (actual2 - exp2)

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
