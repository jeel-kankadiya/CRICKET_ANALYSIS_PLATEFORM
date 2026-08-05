"""
dataset_analytics.py
---------------------
PURPOSE:
    Computes domain-specific analytics from the 5 supplementary IPL datasets:
    1. Auction trends (most expensive buys, average spend by role, season trends)
    2. Venue intelligence (pitch characteristics, bat-first vs chase win rates)
    3. Points table history (season champions, playoff qualification rates, close races)
    4. Player season trends (top run scorers, top wicket-takers, career trajectories)
    5. Player availability (absences by reason, team injury rates)

All functions return serialization-ready Python dicts/lists for JSON output.
"""

import numpy as np
import pandas as pd
import os

from data_loader import (
    load_auction_data,
    load_player_season_stats,
    load_venue_details,
    load_points_table,
    load_player_availability,
    load_matches,
)

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────

def _safe(val):
    """
    Converts NumPy scalars and NaN/None values into native JSON-safe Python types.

    Parameters:
        val: Any scalar value (int, float, np.int64, np.nan, etc.)

    Returns:
        Native int, float, or None suitable for json.dump().
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def _clean_records(df: pd.DataFrame, cols: list) -> list:
    """
    Converts selected columns of a DataFrame into a list of JSON-safe dictionaries.

    Parameters:
        df (pd.DataFrame): Input DataFrame.
        cols (list): List of column names to extract.

    Returns:
        list: List of row dictionaries with clean primitive Python types.
    """
    records = []
    for row in df[cols].to_dict(orient="records"):
        records.append({k: _safe(v) for k, v in row.items()})
    return records


# ─────────────────────────────────────────────────────────
# 1. AUCTION ANALYTICS
# ─────────────────────────────────────────────────────────

def auction_analytics() -> dict:
    """
    Analyzes historical IPL player auction data.

    Calculates:
      - top_buys_per_season  : Top 5 most expensive sold players for each season.
      - most_expensive_ever  : Top 20 all-time highest auction bids in IPL history.
      - avg_price_by_role    : Mean, median, max prices broken down by player role.
      - season_spend_trend   : Total and average auction expenditure per season.

    Returns:
        dict: Four analytical components formatted as clean dictionaries.
    """
    df = load_auction_data()
    sold = df[df["sold"] == "Yes"].copy()
    sold["sold_price_lakhs"] = pd.to_numeric(sold["sold_price_lakhs"], errors="coerce")

    # 1. Top 5 sold players per season
    top_season = (
        sold.sort_values("sold_price_lakhs", ascending=False)
            .groupby("season")
            .head(5)
            .reset_index(drop=True)
    )
    top_buys_per_season = _clean_records(
        top_season,
        ["season", "player_name", "role", "team_name", "base_price_lakhs", "sold_price_lakhs"]
    )

    # 2. Top 20 all-time highest buys
    top20 = sold.sort_values("sold_price_lakhs", ascending=False).head(20)
    most_expensive_ever = _clean_records(
        top20,
        ["season", "player_name", "role", "team_name", "sold_price_lakhs"]
    )

    # 3. Aggregated price by player role
    role_avg = (
        sold.groupby("role")["sold_price_lakhs"]
            .agg(["mean", "median", "max", "count"])
            .reset_index()
    )
    role_avg.columns = ["role", "avg_price", "median_price", "max_price", "total_sold"]
    role_avg["avg_price"]    = role_avg["avg_price"].round(1)
    role_avg["median_price"] = role_avg["median_price"].round(1)
    avg_price_by_role = _clean_records(role_avg, role_avg.columns.tolist())

    # 4. Total and average spend per season
    spend = (
        sold.groupby("season")["sold_price_lakhs"]
            .agg(total_spend="sum", avg_spend="mean", lots_sold="count")
            .reset_index()
    )
    spend["total_spend"] = spend["total_spend"].round(0)
    spend["avg_spend"]   = spend["avg_spend"].round(1)
    season_spend_trend = _clean_records(spend, spend.columns.tolist())

    return {
        "top_buys_per_season":  top_buys_per_season,
        "most_expensive_ever":  most_expensive_ever,
        "avg_price_by_role":    avg_price_by_role,
        "season_spend_trend":   season_spend_trend,
    }


# ─────────────────────────────────────────────────────────
# 2. VENUE INTELLIGENCE
# ─────────────────────────────────────────────────────────

def venue_intelligence() -> dict:
    """
    Analyzes stadium attributes and match pitch conditions.

    Calculates:
      - venue_profiles      : Comprehensive physical and statistical profile per ground.
      - pitch_type_summary  : Win % for batting first and avg scores by pitch surface (flat, green, dry, etc.).
      - top_batting_venues  : Grounds with highest average first-innings scores.
      - top_chasing_venues  : Grounds with lowest bat-first win rates (most favorable for chasing).

    Returns:
        dict: Four venue intelligence metrics.
    """
    df = load_venue_details()

    # All venues sorted by match hosting activity
    all_venues = df.sort_values("total_matches_hosted", ascending=False)
    venue_profiles = _clean_records(all_venues, [
        "venue", "city", "capacity", "pitch_type",
        "avg_first_innings_score", "bat_first_win_pct",
        "dew_factor", "boundary_size_m", "total_matches_hosted"
    ])

    # Performance breakdown by pitch type
    pitch_summary = (
        df.groupby("pitch_type")
          .agg(
              avg_bat_first_win_pct=("bat_first_win_pct", "mean"),
              avg_first_innings_score=("avg_first_innings_score", "mean"),
              avg_dew_factor=("dew_factor", "mean"),
              venues_count=("venue", "count"),
          )
          .reset_index()
    )
    for col in ["avg_bat_first_win_pct", "avg_first_innings_score", "avg_dew_factor"]:
        pitch_summary[col] = pitch_summary[col].round(1)
    pitch_type_summary = _clean_records(pitch_summary, pitch_summary.columns.tolist())

    # Highest scoring grounds
    top_bat = df.nlargest(10, "avg_first_innings_score")
    top_batting_venues = _clean_records(top_bat, ["venue", "city", "avg_first_innings_score", "pitch_type"])

    # Grounds where chasing team wins most frequently
    top_chase = df.nsmallest(10, "bat_first_win_pct")
    top_chasing_venues = _clean_records(top_chase, ["venue", "city", "bat_first_win_pct", "dew_factor"])

    return {
        "venue_profiles":      venue_profiles,
        "pitch_type_summary":  pitch_type_summary,
        "top_batting_venues":  top_batting_venues,
        "top_chasing_venues":  top_chasing_venues,
    }


# ─────────────────────────────────────────────────────────
# 3. POINTS TABLE ANALYTICS
# ─────────────────────────────────────────────────────────

def points_table_analytics() -> dict:
    """
    Analyzes historical IPL league standings and playoff outcomes.

    Calculates:
      - full_points_table    : Complete season-by-season standings.
      - season_champions     : Champion team per season with tournament stats.
      - qualification_stats  : Playoff qualification rate (%) per franchise.
      - closest_title_races  : Seasons with smallest points gap between 1st and 2nd place.

    Returns:
        dict: Four standings metrics.
    """
    df = load_points_table()

    # Full table sorted by season and points
    full = df.sort_values(["season", "points"], ascending=[True, False])
    full_points_table = _clean_records(full, full.columns.tolist())

    # Filter champions per season
    champs = df[df["champion"] == 1].sort_values("season")
    season_champions = _clean_records(champs, [
        "season", "team_name", "matches_played", "wins", "losses", "points", "nrr"
    ])

    # Qualification rate calculation per team
    qual = (
        df.groupby("team_name")
          .agg(
              seasons_played=("season", "count"),
              times_qualified=("qualified", "sum"),
              times_champion=("champion", "sum"),
              total_wins=("wins", "sum"),
          )
          .reset_index()
    )
    qual["qual_rate"] = (qual["times_qualified"] / qual["seasons_played"] * 100.0).round(1)
    qual_sorted = qual.sort_values("times_champion", ascending=False)
    qualification_stats = _clean_records(qual_sorted, qual_sorted.columns.tolist())

    # Closest title races: minimum gap between 1st and 2nd team points
    race_rows = []
    for season, grp in df.groupby("season"):
        top2 = grp.nlargest(2, "points")
        if len(top2) == 2:
            pts_list = top2["points"].tolist()
            gap = abs(pts_list[0] - pts_list[1])
            race_rows.append({
                "season": season,
                "first_team": top2.iloc[0]["team_name"],
                "second_team": top2.iloc[1]["team_name"],
                "first_pts": int(pts_list[0]),
                "second_pts": int(pts_list[1]),
                "points_gap": int(gap),
            })
    race_rows.sort(key=lambda x: x["points_gap"])
    closest_title_races = race_rows[:10]

    return {
        "full_points_table":   full_points_table,
        "season_champions":    season_champions,
        "qualification_stats": qualification_stats,
        "closest_title_races": closest_title_races,
    }


# ─────────────────────────────────────────────────────────
# 4. PLAYER SEASON TRENDS
# ─────────────────────────────────────────────────────────

def player_season_trends() -> dict:
    """
    Analyzes seasonal player performances and multi-year career arcs.

    Calculates:
      - top_run_scorers_by_season   : Orange Cap contenders (top 5 batters per season).
      - top_wicket_takers_by_season : Purple Cap contenders (top 5 bowlers per season).
      - career_trajectories         : Season-by-season progression for top 20 all-time run scorers.
      - season_batting_leaders      : Top 10 batters per season for dashboard leaderboards.

    Returns:
        dict: Four seasonal trend records.
    """
    df = load_player_season_stats()

    # Top 5 run scorers per season
    runs_top = (
        df.sort_values("runs", ascending=False)
          .groupby("season")
          .head(5)
          .reset_index(drop=True)
    )
    top_run_scorers_by_season = _clean_records(
        runs_top, ["season", "player_name", "team_name", "matches", "innings", "runs",
                   "batting_avg", "strike_rate", "fours", "sixes"]
    )

    # Top 5 wicket takers per season
    wkts_top = (
        df.sort_values("wickets", ascending=False)
          .groupby("season")
          .head(5)
          .reset_index(drop=True)
    )
    top_wicket_takers_by_season = _clean_records(
        wkts_top, ["season", "player_name", "team_name", "matches", "wickets", "economy", "bowling_avg"]
    )

    # Career trajectory for top 20 overall run scorers
    career_totals = df.groupby("player_name")["runs"].sum().nlargest(20).index.tolist()
    traj_df = df[df["player_name"].isin(career_totals)].sort_values(["player_name", "season"])
    career_trajectories = _clean_records(
        traj_df, ["season", "player_name", "team_name", "matches", "runs",
                  "batting_avg", "strike_rate", "wickets", "economy"]
    )

    # Top 10 batters per season
    bat_leaders = (
        df.sort_values("runs", ascending=False)
          .groupby("season")
          .head(10)
          .reset_index(drop=True)
    )
    season_batting_leaders = _clean_records(
        bat_leaders, ["season", "player_name", "team_name", "runs", "batting_avg", "strike_rate"]
    )

    return {
        "top_run_scorers_by_season":   top_run_scorers_by_season,
        "top_wicket_takers_by_season": top_wicket_takers_by_season,
        "career_trajectories":         career_trajectories,
        "season_batting_leaders":      season_batting_leaders,
    }


# ─────────────────────────────────────────────────────────
# 5. PLAYER AVAILABILITY ANALYTICS
# ─────────────────────────────────────────────────────────

def availability_analytics() -> dict:
    """
    Analyzes match-level player availability and injury impact.

    Calculates:
      - most_absent_players   : Players missing highest percentage of team matches.
      - absence_by_reason     : Breakdown of absences (Injury, National Duty, Personal, Rest).
      - team_absence_rate     : Average missing player records per match by franchise.
      - season_injury_trend   : Total missing player instances per season over time.

    Returns:
        dict: Four player availability metrics.
    """
    df = load_player_availability()
    absent = df[~df["is_available"]].copy()

    # Most absent players ranking
    absent_counts = absent.groupby("player_name").size().reset_index(name="absences")
    total_counts = df.groupby("player_name").size().reset_index(name="total_records")
    ab_rate = absent_counts.merge(total_counts, on="player_name")
    ab_rate["absence_pct"] = (ab_rate["absences"] / ab_rate["total_records"] * 100.0).round(1)
    ab_rate = ab_rate.sort_values("absences", ascending=False).head(20)
    most_absent_players = _clean_records(ab_rate, ["player_name", "absences", "absence_pct"])

    # Categorized breakdown of reasons for absence
    reason_counts = (
        absent[absent["reason"] != "Fit"]
              .groupby("reason").size()
              .reset_index(name="count")
              .sort_values("count", ascending=False)
    )
    absence_by_reason = _clean_records(reason_counts, ["reason", "count"])

    # Team absence frequency
    team_matches = df.groupby("team_name")["match_id"].nunique().reset_index(name="match_count")
    team_absences = absent.groupby("team_name").size().reset_index(name="total_absences")
    team_abs = team_matches.merge(team_absences, on="team_name", how="left").fillna(0)
    team_abs["absences_per_match"] = (
        team_abs["total_absences"] / team_abs["match_count"].replace(0, 1)
    ).round(2)
    team_abs = team_abs.sort_values("absences_per_match", ascending=False)
    team_absence_rate = _clean_records(
        team_abs, ["team_name", "match_count", "total_absences", "absences_per_match"]
    )

    # Seasonal injury trend
    season_trend = absent.groupby("season").size().reset_index(name="total_absences")
    season_injury_trend = _clean_records(season_trend, ["season", "total_absences"])

    return {
        "most_absent_players":  most_absent_players,
        "absence_by_reason":    absence_by_reason,
        "team_absence_rate":    team_absence_rate,
        "season_injury_trend":  season_injury_trend,
    }


# ─────────────────────────────────────────────────────────
# MAIN AGGREGATOR
# ─────────────────────────────────────────────────────────

def build_all_analytics() -> dict:
    """
    Executes all 5 analytics sub-modules and returns a unified JSON-serializable dictionary.

    Returns:
        dict: Master analytics bundle containing 'auction', 'venue_intel',
              'points_table', 'player_trends', and 'availability'.
    """
    return {
        "auction":      auction_analytics(),
        "venue_intel":  venue_intelligence(),
        "points_table": points_table_analytics(),
        "player_trends":player_season_trends(),
        "availability": availability_analytics(),
    }


if __name__ == "__main__":
    import json
    result = build_all_analytics()
    out = os.path.join(OUTPUTS_DIR, "dataset_analytics.json")
    with open(out, "w") as f:
        json.dump(result, f, default=str, indent=2)
    print(f"✓ Analytics written → {out}")
    for key, val in result.items():
        sub = list(val.keys()) if isinstance(val, dict) else "list"
        print(f"  {key}: {sub}")
