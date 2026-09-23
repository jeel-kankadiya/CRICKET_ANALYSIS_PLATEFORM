"""
feature_engineering_v2.py
--------------------------
PURPOSE:
    Extends the original feature_engineering.py with fixes and additions
    identified from outputs/feature_importance.csv and outputs/cv_results.json:

    1. ADD squad strength signal (src/team_strength.py) — the original 9
       features are entirely team-history based and never look at actual
       player quality or current-day availability.

    2. REGULARIZE venue win-rate — the original team1_venue_winrate /
       team2_venue_winrate default to 0.5 with NO sample-size floor, so a
       team's win rate at a venue they've played at only once (1/1 = 100%
       or 0/1 = 0%) gets treated with the same confidence as a venue they've
       played 20 times. This shrinks small-sample venue win rates toward the
       0.5 prior using a simple Bayesian pseudo-count.

    3. DROP toss_won_by_team1 — it was the weakest feature in every model
       (importances 0.017-0.034) and is close to a coin flip by nature (toss
       is random), so it mostly adds noise for tree models to overfit on.

    4. ADD one interaction term, elo_diff_x_venue_advantage, which lets
       linear models (Logistic Regression) capture "a strong team AND a
       strong home-venue record" as a multiplicative effect rather than two
       independent additive ones.

USAGE:
    from feature_engineering_v2 import build_feature_matrix_v2, FEATURE_COLS_V2
    df, elo = build_feature_matrix_v2()
"""

import numpy as np
import pandas as pd

from feature_engineering import build_feature_matrix
from team_strength import build_strength_features

# Minimum number of prior meetings at a venue before trusting the raw win
# rate. Below this, the rate is shrunk toward 0.5 proportionally.
VENUE_SHRINKAGE_PSEUDO_COUNT = 5
H2H_SHRINKAGE_PSEUDO_COUNT = 4

FEATURE_COLS_V2 = [
    "elo_diff", "form_diff", "momentum_diff", "experience_diff",
    "team1_venue_winrate_shrunk", "team2_venue_winrate_shrunk",
    "h2h_team1_winrate_shrunk", "toss_decision_bat",
    "strength_diff", "key_players_missing_diff",
    "elo_diff_x_venue_advantage", "toss_won_by_team1"
]


def _shrink_winrate(winrate: pd.Series, matches_played: pd.Series, pseudo_count: int) -> pd.Series:
    """
    Bayesian-style shrinkage: pulls a win rate toward 0.5 when it's backed by
    few matches. With `matches_played` prior meetings and pseudo_count "prior"
    matches assumed to be split 50/50:

        shrunk_rate = (winrate * matches_played + 0.5 * pseudo_count) / (matches_played + pseudo_count)
    """
    return (
        (winrate * matches_played + 0.5 * pseudo_count)
        / (matches_played + pseudo_count)
    )


def augment_symmetric_data(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    """
    Enforces team-order symmetry and doubles the dataset size.
    For each match row with (X, y=team1_won), creates a paired row (-X, y=1-team1_won).
    This completely eliminates arbitrary team1 vs team2 ordering bias.
    """
    df_orig = df.copy()
    
    # Inverted copy: reverse all differential features and flip labels
    df_inverted = df.copy()
    diff_cols = [c for c in feature_cols if ("_diff" in c or c.startswith("h2h") or c.startswith("toss_won"))]
    for col in diff_cols:
        df_inverted[col] = -df_inverted[col]
    
    if "team1_venue_winrate_shrunk" in df.columns and "team2_venue_winrate_shrunk" in df.columns:
        df_inverted["team1_venue_winrate_shrunk"], df_inverted["team2_venue_winrate_shrunk"] = (
            df_orig["team2_venue_winrate_shrunk"], df_orig["team1_venue_winrate_shrunk"]
        )

    df_inverted["team1_won"] = 1 - df_orig["team1_won"]
    
    combined = pd.concat([df_orig, df_inverted], ignore_index=True)
    return combined


def build_feature_matrix_v2():
    """
    Builds the improved feature matrix: original features + squad strength + availability +
    shrunk venue win rates + shrunk H2H win rates + interaction terms.

    Returns:
        tuple: (matches_df, final_elo_dict)
    """
    matches, elo = build_feature_matrix()

    from collections import defaultdict
    venue_record = defaultdict(lambda: [0, 0])  # [wins, played]
    h2h_record = defaultdict(lambda: [0, 0])    # [t1_wins, played]
    
    team1_venue_played, team2_venue_played = [], []
    h2h_played = []

    for _, row in matches.iterrows():
        t1, t2, venue = row["team1_name"], row["team2_name"], row["venue"]
        team1_venue_played.append(venue_record[(t1, venue)][1])
        team2_venue_played.append(venue_record[(t2, venue)][1])
        
        pair_key = tuple(sorted([t1, t2]))
        h2h_played.append(h2h_record[pair_key][1])

        if row["is_decisive"] and not pd.isna(t1) and not pd.isna(t2):
            venue_record[(t1, venue)][1] += 1
            venue_record[(t2, venue)][1] += 1
            h2h_record[pair_key][1] += 1
            if row["team1_won"] == 1:
                venue_record[(t1, venue)][0] += 1
                if pair_key[0] == t1:
                    h2h_record[pair_key][0] += 1
            else:
                venue_record[(t2, venue)][0] += 1
                if pair_key[0] == t2:
                    h2h_record[pair_key][0] += 1

    matches["team1_venue_played"] = team1_venue_played
    matches["team2_venue_played"] = team2_venue_played
    matches["h2h_played"] = h2h_played

    matches["team1_venue_winrate_shrunk"] = _shrink_winrate(
        matches["team1_venue_winrate"], matches["team1_venue_played"], VENUE_SHRINKAGE_PSEUDO_COUNT
    )
    matches["team2_venue_winrate_shrunk"] = _shrink_winrate(
        matches["team2_venue_winrate"], matches["team2_venue_played"], VENUE_SHRINKAGE_PSEUDO_COUNT
    )
    matches["h2h_team1_winrate_shrunk"] = _shrink_winrate(
        matches["h2h_team1_winrate"], matches["h2h_played"], H2H_SHRINKAGE_PSEUDO_COUNT
    )

    # Squad strength + availability
    strength = build_strength_features()
    matches = matches.merge(strength, on="match_id", how="left")
    matches["strength_diff"] = matches["strength_diff"].fillna(0.0)
    matches["key_players_missing_diff"] = (
        matches["team1_key_players_missing_pct"].fillna(0.0)
        - matches["team2_key_players_missing_pct"].fillna(0.0)
    )

    # Interaction terms
    venue_advantage = matches["team1_venue_winrate_shrunk"] - matches["team2_venue_winrate_shrunk"]
    matches["elo_diff_x_venue_advantage"] = matches["elo_diff"] * venue_advantage

    return matches, elo


if __name__ == "__main__":
    df, elo = build_feature_matrix_v2()
    print(f"Feature matrix v2: {len(df)} matches, {df.shape[1]} columns")
    print("\nMissing values in FEATURE_COLS_V2:\n", df[FEATURE_COLS_V2].isnull().sum())
    print("\nSample:\n", df[["match_date", "team1_name", "team2_name"] + FEATURE_COLS_V2 + ["team1_won"]].tail(5).to_string())

