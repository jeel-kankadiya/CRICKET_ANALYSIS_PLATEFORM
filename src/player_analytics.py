"""
player_analytics.py
---------------------
Computes derived performance metrics for every player using their IPL career
aggregate stats (ipl_allround.csv), enriched with identity/style info from
players_data_updated.csv.

Metrics computed:
  - Batting Impact Score   : blends average, strike rate & volume of runs
  - Bowling Impact Score    : blends economy, average & wickets taken
  - All-Rounder Index       : rewards players who contribute meaningfully with
                              both bat and ball (min-based, not additive, so a
                              pure batter/bowler doesn't rank as an all-rounder)
  - Percentile ranks for each metric, for easy leaderboard building
"""

import pandas as pd
import numpy as np
import os

from data_loader import load_allrounder_stats, load_players

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

MIN_INNINGS_BAT = 10   # qualification thresholds so small samples don't dominate rankings
MIN_INNINGS_BOWL = 10


def _minmax(series):
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def build_player_ratings():
    df = load_allrounder_stats()
    players = load_players()

    df = df.merge(
        players[["player_name", "bat_style", "bowl_style", "field_pos", "player_full_name"]],
        left_on="PlayerName", right_on="player_name", how="left"
    )

    # ---- Batting Impact Score ----
    bat_qual = df["Innings"] >= MIN_INNINGS_BAT
    df["bat_avg_pctile"] = np.nan
    df["bat_sr_pctile"] = np.nan
    df["bat_vol_pctile"] = np.nan

    df.loc[bat_qual, "bat_avg_pctile"] = _minmax(df.loc[bat_qual, "BattingAverage"].fillna(0))
    df.loc[bat_qual, "bat_sr_pctile"] = _minmax(df.loc[bat_qual, "StrikeRate"].fillna(0))
    df.loc[bat_qual, "bat_vol_pctile"] = _minmax(df.loc[bat_qual, "Runs"].fillna(0))

    df["batting_impact_score"] = (
        0.4 * df["bat_avg_pctile"] + 0.35 * df["bat_sr_pctile"] + 0.25 * df["bat_vol_pctile"]
    ) * 100

    # ---- Bowling Impact Score (lower economy/average is better -> invert) ----
    bowl_qual = df["BowlInnings"] >= MIN_INNINGS_BOWL
    df["bowl_econ_pctile"] = np.nan
    df["bowl_avg_pctile"] = np.nan
    df["bowl_wkt_pctile"] = np.nan

    df.loc[bowl_qual, "bowl_econ_pctile"] = 1 - _minmax(df.loc[bowl_qual, "Economy"].fillna(df["Economy"].max()))
    df.loc[bowl_qual, "bowl_avg_pctile"] = 1 - _minmax(df.loc[bowl_qual, "BowlingAverage"].fillna(df["BowlingAverage"].max()))
    df.loc[bowl_qual, "bowl_wkt_pctile"] = _minmax(df.loc[bowl_qual, "Wickets"].fillna(0))

    df["bowling_impact_score"] = (
        0.35 * df["bowl_econ_pctile"] + 0.35 * df["bowl_avg_pctile"] + 0.3 * df["bowl_wkt_pctile"]
    ) * 100

    # ---- All-Rounder Index: min() rewards genuine dual contribution ----
    df["allrounder_index"] = df[["batting_impact_score", "bowling_impact_score"]].min(axis=1)
    df.loc[df["batting_impact_score"].isna() | df["bowling_impact_score"].isna(), "allrounder_index"] = np.nan

    return df


def top_n(df, col, n=15, qualifier_col=None, min_val=None):
    d = df.copy()
    if qualifier_col is not None:
        d = d[d[qualifier_col] >= min_val]
    return d.dropna(subset=[col]).sort_values(col, ascending=False).head(n)[
        ["PlayerName", "Teams", col, "Matches", "Runs", "Wickets"]
    ]


if __name__ == "__main__":
    ratings = build_player_ratings()
    ratings.to_csv(os.path.join(OUTPUTS_DIR, "player_ratings.csv"), index=False)

    print("Top 15 Batters (Batting Impact Score, min 10 innings):")
    print(top_n(ratings, "batting_impact_score", 15, "Innings", MIN_INNINGS_BAT).to_string(index=False))

    print("\nTop 15 Bowlers (Bowling Impact Score, min 10 bowling innings):")
    print(top_n(ratings, "bowling_impact_score", 15, "BowlInnings", MIN_INNINGS_BOWL).to_string(index=False))

    print("\nTop 15 All-Rounders (All-Rounder Index):")
    print(top_n(ratings, "allrounder_index", 15).to_string(index=False))
