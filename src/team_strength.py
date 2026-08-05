"""
team_strength.py
-----------------
PURPOSE:
    Adds squad-quality signal to the match prediction pipeline, using data
    that the existing feature_engineering.py never touches:
        - player_season_stats.csv  (individual batting/bowling output)
        - player_availability.csv  (who was actually available for a given match)

WHY THIS MATTERS:
    The original 9-feature model only knows about TEAM-level history (Elo, form,
    venue, h2h, toss). It has no idea whether a team's best players are actually
    playing that day. Two teams can have identical Elo but very different chances
    if one is missing 3 of its top-5 run scorers.

WHAT IT COMPUTES:
    1. build_team_season_strength()
       A composite "squad strength index" per (season, team) built from:
         - batting_strength = sum of (runs * strike_rate/100) across the squad
         - bowling_strength = sum of (wickets * economy-adjusted weight)
       Both are averaged by squad size (so a deep bench isn't just "more
       strength") and z-scored WITHIN each season (so a high-scoring era like
       2024 isn't automatically "stronger" than a low-scoring era like 2009).

       LEAKAGE GUARD: the index for season Y is only ever attached to matches
       in season Y+1 via `strength_index_prior` — i.e. a team's strength going
       into a season is based on how their squad performed LAST season, never
       the season being predicted.

    2. build_key_player_index()
       For each (season, team), identifies the "key players" = top 5 run
       scorers + top 5 wicket takers from the PRIOR season.

    3. build_availability_penalty()
       For every match, computes what fraction of a team's key players were
       marked unavailable (player_availability.csv) for that specific match_id.
       This produces team1_key_players_missing / team2_key_players_missing,
       a 0.0-1.0 signal usable directly as a pre-match feature.

USAGE:
    from team_strength import build_strength_features
    strength_df = build_strength_features()
    # columns: season, team_name, strength_index_prior
    #
    # merge onto ipl_matches_data-derived match rows via
    # (match['season'], match['team1_name']) -> strength_index_prior, etc.
"""

import os
import numpy as np
import pandas as pd

from data_loader import load_player_season_stats, load_player_availability, load_matches

TOP_N_KEY_PLAYERS = 5


def _zscore(series: pd.Series) -> pd.Series:
    """Standardize a series to mean 0 / std 1. Returns all-zeros if std is 0."""
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return series * 0.0
    return (series - series.mean()) / std


def build_team_season_strength() -> pd.DataFrame:
    """
    Builds a composite squad strength index per (season, team_name), then
    shifts it forward one season so it can be safely used as a PRE-match
    feature (this season's matches only ever see LAST season's strength).

    Returns:
        DataFrame with columns:
            season, team_name, strength_index, strength_index_prior
    """
    stats = load_player_season_stats().copy()

    # Per-player-season batting output: volume (runs) weighted by tempo (SR).
    stats["batting_score"] = stats["runs"].fillna(0) * (stats["strike_rate"].fillna(0) / 100.0)

    # Per-player-season bowling output: wickets, boosted for a tighter economy.
    # Economy is clipped at a floor of 4.0 so a tiny-sample outlier (e.g. 1 over
    # at 2.0 economy) doesn't produce an absurd multiplier.
    econ = stats["economy"].replace(0, np.nan).fillna(9.0).clip(lower=4.0)
    stats["bowling_score"] = stats["wickets"].fillna(0) * (8.0 / econ)

    team_season = stats.groupby(["season", "team_name"]).agg(
        batting_strength=("batting_score", "sum"),
        bowling_strength=("bowling_score", "sum"),
        squad_size=("player_name", "nunique"),
    ).reset_index()

    # Normalize by squad size so rostering more players isn't rewarded on its own.
    team_season["batting_strength_avg"] = team_season["batting_strength"] / team_season["squad_size"]
    team_season["bowling_strength_avg"] = team_season["bowling_strength"] / team_season["squad_size"]

    # Z-score WITHIN each season: makes strength comparable across scoring eras.
    team_season["batting_z"] = team_season.groupby("season")["batting_strength_avg"].transform(_zscore)
    team_season["bowling_z"] = team_season.groupby("season")["bowling_strength_avg"].transform(_zscore)
    team_season["strength_index"] = team_season["batting_z"] + team_season["bowling_z"]

    # Shift forward one season per team: strength_index_prior for season Y
    # is the strength_index computed from season Y-1's player stats.
    team_season = team_season.sort_values(["team_name", "season"])
    team_season["strength_index_prior"] = (
        team_season.groupby("team_name")["strength_index"].shift(1)
    )

    return team_season[[
        "season", "team_name", "strength_index", "strength_index_prior"
    ]]


def build_key_player_index() -> pd.DataFrame:
    """
    Identifies each team's "key players" for a given season = the top 5 run
    scorers + top 5 wicket takers from the PRIOR season's player_season_stats.

    Returns:
        DataFrame with columns: season, team_name, player_name
        (one row per key player; a team has up to 10 rows per season, fewer
        if there's overlap between top batters/bowlers)
    """
    stats = load_player_season_stats().copy()
    # season is loaded as a string dtype; coerce to int for +1 arithmetic, then
    # back to string so it matches the string season key used everywhere else.
    stats["next_season"] = (pd.to_numeric(stats["season"], errors="coerce") + 1).astype("Int64").astype(str)

    key_rows = []
    for (season, team), grp in stats.groupby(["next_season", "team_name"]):
        top_bat = grp.nlargest(TOP_N_KEY_PLAYERS, "runs")["player_name"]
        top_bowl = grp.nlargest(TOP_N_KEY_PLAYERS, "wickets")["player_name"]
        for p in pd.concat([top_bat, top_bowl]).unique():
            key_rows.append({"season": season, "team_name": team, "player_name": p})

    return pd.DataFrame(key_rows)


def build_availability_penalty() -> pd.DataFrame:
    """
    For every match_id, computes the fraction of each team's key players who
    were marked unavailable (player_availability.csv) for that match.

    Returns:
        DataFrame with columns: match_id, team_name, key_players_missing_pct
        (0.0 = full-strength squad, 1.0 = every key player unavailable)
    """
    avail = load_player_availability()
    key_players = build_key_player_index()

    merged = avail.merge(
        key_players,
        on=["season", "team_name", "player_name"],
        how="inner",  # only keep availability rows for players who ARE key players
    )

    penalty = merged.groupby(["match_id", "team_name"]).agg(
        key_players_total=("player_name", "nunique"),
        key_players_missing=("is_available", lambda x: (~x).sum()),
    ).reset_index()

    penalty["key_players_missing_pct"] = (
        penalty["key_players_missing"] / penalty["key_players_total"].clip(lower=1)
    )

    return penalty[["match_id", "team_name", "key_players_missing_pct"]]


def build_strength_features() -> pd.DataFrame:
    """
    Convenience wrapper: attaches team_season_strength + availability_penalty
    onto every match in ipl_matches_data.csv, producing a leak-free, per-match,
    per-team pair of columns ready to merge into the main feature matrix.

    Returns:
        DataFrame with columns:
            match_id, team1_strength, team2_strength, strength_diff,
            team1_key_players_missing_pct, team2_key_players_missing_pct
    """
    matches = load_matches()[["match_id", "season", "team1_name", "team2_name"]].copy()

    strength = build_team_season_strength()
    penalty = build_availability_penalty()

    out = matches.copy()
    for side in ["team1", "team2"]:
        team_col = f"{side}_name"
        out = out.merge(
            strength.rename(columns={
                "team_name": team_col,
                "strength_index_prior": f"{side}_strength",
            })[["season", team_col, f"{side}_strength"]],
            on=["season", team_col],
            how="left",
        )
        out = out.merge(
            penalty.rename(columns={
                "team_name": team_col,
                "key_players_missing_pct": f"{side}_key_players_missing_pct",
            }),
            on=["match_id", team_col],
            how="left",
        )

    # A team with no prior-season data (new franchise, or league's first season)
    # gets strength 0.0 (league-average) rather than NaN, so it doesn't get
    # dropped by dropna() downstream in train_models.py.
    out["team1_strength"] = out["team1_strength"].fillna(0.0)
    out["team2_strength"] = out["team2_strength"].fillna(0.0)
    out["team1_key_players_missing_pct"] = out["team1_key_players_missing_pct"].fillna(0.0)
    out["team2_key_players_missing_pct"] = out["team2_key_players_missing_pct"].fillna(0.0)

    out["strength_diff"] = out["team1_strength"] - out["team2_strength"]

    return out[[
        "match_id", "team1_strength", "team2_strength", "strength_diff",
        "team1_key_players_missing_pct", "team2_key_players_missing_pct",
    ]]


if __name__ == "__main__":
    feats = build_strength_features()
    print(feats.describe())
    print("\nSample rows:\n", feats.tail(10).to_string())
