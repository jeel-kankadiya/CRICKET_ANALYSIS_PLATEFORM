"""
player_analytics.py
---------------------
PURPOSE:
    Computes custom impact scores and ratings for IPL players using historical career data.

METRICS CALCULATED:
    1. Batting Impact Score: Composite index combining Batting Average (40%), Strike Rate (35%), and Total Runs (25%).
    2. Bowling Impact Score: Composite index combining Economy Rate (35%), Bowling Average (35%), and Wickets (30%).
    3. All-Rounder Index: Dual-contribution metric defined as min(Batting Impact, Bowling Impact).
"""

import pandas as pd
import numpy as np
import os

from data_loader import load_allrounder_stats, load_players

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Minimum qualification thresholds to filter out small sample sizes
MIN_INNINGS_BAT = 10
MIN_INNINGS_BOWL = 10


def _minmax(series: pd.Series) -> pd.Series:
    """
    Normalizes a numerical Pandas Series onto a [0.0, 1.0] scale.

    Formula:
        (x - min) / (max - min)

    Parameters:
        series (pd.Series): Input column of numeric stats.

    Returns:
        pd.Series: Normalized values between 0.0 and 1.0. Returns 0.5 if min == max.
    """
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def build_player_ratings() -> pd.DataFrame:
    """
    Calculates Batting Impact, Bowling Impact, and All-Rounder Index for all IPL players.

    Steps:
        1. Load all-rounder statistics and merge player metadata (bat style, bowl style, field position).
        2. Apply minimum qualification filters (min 10 innings).
        3. Compute percentile ranks using Min-Max scaling.
        4. Calculate weighted composite impact scores (0 to 100).
        5. For bowlers, invert Economy and Average scales (lower is better).
        6. Calculate All-Rounder Index using min(Batting Impact, Bowling Impact) to reward genuine dual capability.

    Returns:
        pd.DataFrame: Merged DataFrame containing player metadata and computed impact scores.
    """
    df = load_allrounder_stats()
    players = load_players()

    # Join player metadata on player name
    df = df.merge(
        players[["player_name", "bat_style", "bowl_style", "field_pos", "player_full_name"]],
        left_on="PlayerName", right_on="player_name", how="left"
    )

    # 1. Batting Impact Score Calculation
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

    # 2. Bowling Impact Score Calculation (Inverting Economy & Average since lower is better)
    bowl_qual = df["BowlInnings"] >= MIN_INNINGS_BOWL
    df["bowl_econ_pctile"] = np.nan
    df["bowl_avg_pctile"] = np.nan
    df["bowl_wkt_pctile"] = np.nan

    df.loc[bowl_qual, "bowl_econ_pctile"] = 1.0 - _minmax(df.loc[bowl_qual, "Economy"].fillna(df["Economy"].max()))
    df.loc[bowl_qual, "bowl_avg_pctile"] = 1.0 - _minmax(df.loc[bowl_qual, "BowlingAverage"].fillna(df["BowlingAverage"].max()))
    df.loc[bowl_qual, "bowl_wkt_pctile"] = _minmax(df.loc[bowl_qual, "Wickets"].fillna(0))

    df["bowling_impact_score"] = (
        0.35 * df["bowl_econ_pctile"] + 0.35 * df["bowl_avg_pctile"] + 0.3 * df["bowl_wkt_pctile"]
    ) * 100

    # 3. All-Rounder Index Calculation
    # Taking the minimum ensures a player must excel in BOTH disciplines to rank high as an all-rounder
    df["allrounder_index"] = df[["batting_impact_score", "bowling_impact_score"]].min(axis=1)
    df.loc[df["batting_impact_score"].isna() | df["bowling_impact_score"].isna(), "allrounder_index"] = np.nan

    return df


def top_n(df: pd.DataFrame, col: str, n: int = 15, qualifier_col: str = None, min_val: float = None) -> pd.DataFrame:
    """
    Utility function to retrieve the top N players based on a given metric column.

    Parameters:
        df (pd.DataFrame): DataFrame containing player ratings.
        col (str): Metric column to rank players by (e.g., 'batting_impact_score').
        n (int): Number of top players to return (default 15).
        qualifier_col (str, optional): Qualification column name (e.g., 'Innings').
        min_val (float, optional): Minimum required threshold for qualifier column.

    Returns:
        pd.DataFrame: Top N player rows sorted in descending order of the metric.
    """
    d = df.copy()
    if qualifier_col is not None and min_val is not None:
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
