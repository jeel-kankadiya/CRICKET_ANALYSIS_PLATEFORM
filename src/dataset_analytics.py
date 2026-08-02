"""
dataset_analytics.py
---------------------
Computes analytics from the 5 new datasets:

  1. Auction trends     — most expensive buys, value-for-money index
  2. Venue intelligence — pitch-type win%, bat-first vs chase analysis
  3. Points table       — season champions, closest races, NRR bands
  4. Player season      — career run/wicket trajectories per player
  5. Availability       — team win-rate when key players are absent

All functions return serialization-ready Python dicts/lists (JSON-safe).
"""

# pyrefly: ignore [missing-import]
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
# Helper
# ─────────────────────────────────────────────────────────

def _safe(val):
    """Convert numpy scalars / NaN to JSON-safe Python types."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def _clean_records(df, cols):
    records = []
    for row in df[cols].to_dict(orient="records"):
        records.append({k: _safe(v) for k, v in row.items()})
    return records


# ─────────────────────────────────────────────────────────
# 1. Auction Analytics
# ─────────────────────────────────────────────────────────

def auction_analytics():
    """
    Returns:
      - top_buys_per_season  : 5 most expensive sold players per season
      - most_expensive_ever  : top 20 all-time auction buys
      - avg_price_by_role    : average sold price broken down by player role
      - season_spend_trend   : total auction spend per season
    """
    df = load_auction_data()
    sold = df[df["sold"] == "Yes"].copy()
    sold["sold_price_lakhs"] = pd.to_numeric(sold["sold_price_lakhs"], errors="coerce")

    # Top 5 buys per season
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

    # Top 20 all-time buys
    top20 = sold.sort_values("sold_price_lakhs", ascending=False).head(20)
    most_expensive_ever = _clean_records(
        top20,
        ["season", "player_name", "role", "team_name", "sold_price_lakhs"]
    )

    # Average price by role
    role_avg = (
        sold.groupby("role")["sold_price_lakhs"]
            .agg(["mean", "median", "max", "count"])
            .reset_index()
    )
    role_avg.columns = ["role", "avg_price", "median_price", "max_price", "total_sold"]
    role_avg["avg_price"]    = role_avg["avg_price"].round(1)
    role_avg["median_price"] = role_avg["median_price"].round(1)
    avg_price_by_role = _clean_records(role_avg, role_avg.columns.tolist())

    # Season spend trend
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
# 2. Venue Intelligence
# ─────────────────────────────────────────────────────────

def venue_intelligence():
    """
    Returns:
      - venue_profiles      : all venue attributes sorted by matches hosted
      - pitch_type_summary  : avg bat_first_win_pct & avg first-innings score by pitch type
      - top_batting_venues  : highest average first-innings score venues
      - top_chasing_venues  : venues most favourable to chasing teams
    """
    df = load_venue_details()

    # All venues sorted by activity
    all_venues = df.sort_values("total_matches_hosted", ascending=False)
    venue_profiles = _clean_records(all_venues, [
        "venue", "city", "capacity", "pitch_type",
        "avg_first_innings_score", "bat_first_win_pct",
        "dew_factor", "boundary_size_m", "total_matches_hosted"
    ])

    # Pitch type summary
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

    # Top batting venues
    top_bat = df.nlargest(10, "avg_first_innings_score")
    top_batting_venues = _clean_records(top_bat, ["venue", "city", "avg_first_innings_score", "pitch_type"])

    # Top chasing venues (low bat-first win pct = good for chasing)
    top_chase = df.nsmallest(10, "bat_first_win_pct")
    top_chasing_venues = _clean_records(top_chase, ["venue", "city", "bat_first_win_pct", "dew_factor"])

    return {
        "venue_profiles":      venue_profiles,
        "pitch_type_summary":  pitch_type_summary,
        "top_batting_venues":  top_batting_venues,
        "top_chasing_venues":  top_chasing_venues,
    }


# ─────────────────────────────────────────────────────────
# 3. Points Table Analytics
# ─────────────────────────────────────────────────────────

def points_table_analytics():
    """
    Returns:
      - full_points_table    : all records (season × team)
      - season_champions     : champion per season with their stats
      - qualification_stats  : how often each team has qualified for playoffs
      - closest_title_races  : seasons where top-2 teams had smallest points gap
    """
    df = load_points_table()

    # Full table sorted by season then points desc
    full = df.sort_values(["season", "points"], ascending=[True, False])
    full_points_table = _clean_records(full, full.columns.tolist())

    # Season champions
    champs = df[df["champion"] == 1].sort_values("season")
    season_champions = _clean_records(champs, [
        "season", "team_name", "matches_played", "wins", "losses", "points", "nrr"
    ])

    # Qualification frequency per team
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
    qual["qual_rate"] = (qual["times_qualified"] / qual["seasons_played"] * 100).round(1)
    qual_sorted = qual.sort_values("times_champion", ascending=False)
    qualification_stats = _clean_records(qual_sorted, qual_sorted.columns.tolist())

    # Closest title races: smallest gap between 1st and 2nd place points in group stage
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
# 4. Player Season Trends
# ─────────────────────────────────────────────────────────

def player_season_trends():
    """
    Returns:
      - top_run_scorers_by_season  : top 5 run-scorers per season
      - top_wicket_takers_by_season: top 5 wicket-takers per season
      - career_trajectories        : per-season stats for top 20 career run-scorers
      - season_batting_leaders     : top 10 batters per season (for leaderboard)
    """
    df = load_player_season_stats()

    # Top 5 run-scorers per season
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

    # Top 5 wicket-takers per season
    wkts_top = (
        df.sort_values("wickets", ascending=False)
          .groupby("season")
          .head(5)
          .reset_index(drop=True)
    )
    top_wicket_takers_by_season = _clean_records(
        wkts_top, ["season", "player_name", "team_name", "matches", "wickets", "economy", "bowling_avg"]
    )

    # Career trajectories: top 20 overall run-scorers
    career_totals = df.groupby("player_name")["runs"].sum().nlargest(20).index.tolist()
    traj_df = df[df["player_name"].isin(career_totals)].sort_values(["player_name", "season"])
    career_trajectories = _clean_records(
        traj_df, ["season", "player_name", "team_name", "matches", "runs",
                  "batting_avg", "strike_rate", "wickets", "economy"]
    )

    # Batting leaders (top 10 per season — for dashboard leaderboard table)
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
# 5. Player Availability Analytics
# ─────────────────────────────────────────────────────────

def availability_analytics():
    """
    Returns:
      - most_absent_players   : players with highest absence rates
      - absence_by_reason     : breakdown of absences by reason
      - team_absence_rate     : average absences per match per team
      - season_injury_trend   : total absences per season
    """
    df = load_player_availability()

    absent = df[~df["is_available"]].copy()

    # Most absent players
    absent_counts = (
        absent.groupby("player_name").size().reset_index(name="absences")
    )
    total_counts = (
        df.groupby("player_name").size().reset_index(name="total_records")
    )
    ab_rate = absent_counts.merge(total_counts, on="player_name")
    ab_rate["absence_pct"] = (ab_rate["absences"] / ab_rate["total_records"] * 100).round(1)
    ab_rate = ab_rate.sort_values("absences", ascending=False).head(20)
    most_absent_players = _clean_records(ab_rate, ["player_name", "absences", "absence_pct"])

    # Absence breakdown by reason
    reason_counts = (
        absent[absent["reason"] != "Fit"]
              .groupby("reason").size()
              .reset_index(name="count")
              .sort_values("count", ascending=False)
    )
    absence_by_reason = _clean_records(reason_counts, ["reason", "count"])

    # Team absence rate
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

    # Season injury trend
    season_trend = (
        absent.groupby("season").size().reset_index(name="total_absences")
    )
    season_injury_trend = _clean_records(season_trend, ["season", "total_absences"])

    return {
        "most_absent_players":  most_absent_players,
        "absence_by_reason":    absence_by_reason,
        "team_absence_rate":    team_absence_rate,
        "season_injury_trend":  season_injury_trend,
    }


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def build_all_analytics():
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
