"""
data_loader.py
--------------
Loads the raw IPL CSV files, resolves team IDs to canonical franchise names
(handling renames/aliases like Delhi Daredevils -> Delhi Capitals), and
returns clean, analysis-ready DataFrames.
"""

import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_teams():
    teams = pd.read_csv(os.path.join(DATA_DIR, "teams_data.csv"))
    return teams


def load_team_aliases():
    aliases = pd.read_csv(os.path.join(DATA_DIR, "team_aliases.csv"))
    return aliases


def build_team_id_to_name_map():
    """team_id -> canonical current team_name (from teams_data.csv)."""
    teams = load_teams()
    return dict(zip(teams["team_id"], teams["team_name"]))


def load_players():
    players = pd.read_csv(os.path.join(DATA_DIR, "players_data_updated.csv"))
    return players


def load_allrounder_stats():
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_allround.csv"))
    # Clean numeric columns that contain '-' for missing values
    numeric_cols = [
        "Matches", "Innings", "NotOuts", "Runs", "BattingAverage", "BallsFaced",
        "StrikeRate", "Hundreds", "Fifties", "Ducks", "Fours", "Sixes",
        "BowlInnings", "Overs", "Maidens", "RunsConceded", "Wickets",
        "BowlingAverage", "Economy", "BowlingStrikeRate", "FourWickets", "FiveWickets"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # HighestScore has trailing '*' for not-out innings -> extract numeric value + flag
    df["HighestScoreNotOut"] = df["HighestScore"].astype(str).str.contains(r"\*", na=False)
    df["HighestScoreRuns"] = (
        df["HighestScore"].astype(str).str.replace("*", "", regex=False)
    )
    df["HighestScoreRuns"] = pd.to_numeric(df["HighestScoreRuns"], errors="coerce")

    return df


def load_matches():
    """
    Loads match-level data and maps team1/team2/toss_winner/match_winner
    (raw team_ids) to canonical franchise names using teams_data.csv.
    """
    matches = pd.read_csv(os.path.join(DATA_DIR, "ipl_matches_data.csv"))
    id_to_name = build_team_id_to_name_map()

    for col in ["team1", "team2", "toss_winner", "match_winner"]:
        matches[col + "_name"] = matches[col].map(id_to_name)

    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    matches = matches.sort_values("match_date").reset_index(drop=True)

    # Winner flag relative to team1 (used later for supervised learning)
    matches["team1_won"] = (matches["match_winner"] == matches["team1"]).astype(int)

    # Only keep matches that have a clear winner (drop ties / no-result for the
    # win-probability model; they are retained in a separate frame for reference)
    matches["is_decisive"] = matches["result"] == "win"

    return matches


if __name__ == "__main__":
    m = load_matches()
    print(m[["match_date", "season", "team1_name", "team2_name",
              "match_winner_name", "result"]].head(10))
    print("\nTotal matches:", len(m))
    print("Decisive matches:", m["is_decisive"].sum())
    print("\nSeasons covered:", sorted(m["season"].unique()))


# ──────────────────────────────────────────────────────────────
# New dataset loaders (added for 5-dataset expansion)
# ──────────────────────────────────────────────────────────────

def load_auction_data():
    """
    Loads ipl_auction_data.csv.
    Columns: season, player_name, role, base_price_lakhs, sold,
             sold_price_lakhs, team_name
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_auction_data.csv"))
    df["sold_price_lakhs"] = pd.to_numeric(df["sold_price_lakhs"], errors="coerce")
    df["base_price_lakhs"] = pd.to_numeric(df["base_price_lakhs"], errors="coerce")
    return df


def load_player_season_stats():
    """
    Loads player_season_stats.csv — season-wise batting & bowling stats per player.
    Columns: season, player_name, team_name, matches, innings, runs,
             batting_avg, strike_rate, fours, sixes, fifties, hundreds,
             wickets, economy, bowling_avg
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "player_season_stats.csv"))
    numeric_cols = [
        "matches", "innings", "runs", "batting_avg", "strike_rate",
        "fours", "sixes", "fifties", "hundreds", "wickets", "economy", "bowling_avg",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_venue_details():
    """
    Loads venue_details.csv — physical & statistical attributes of each IPL ground.
    Columns: venue, city, capacity, pitch_type, avg_first_innings_score,
             bat_first_win_pct, dew_factor, boundary_size_m, total_matches_hosted
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "venue_details.csv"))
    numeric_cols = [
        "capacity", "avg_first_innings_score", "bat_first_win_pct",
        "dew_factor", "boundary_size_m", "total_matches_hosted",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_points_table():
    """
    Loads ipl_points_table.csv — season-wise IPL standings.
    Columns: season, team_name, matches_played, wins, losses, no_result,
             points, nrr, qualified, champion
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_points_table.csv"))
    numeric_cols = ["matches_played", "wins", "losses", "no_result", "points", "nrr"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_player_availability():
    """
    Loads player_availability.csv — match-level player availability & injury records.
    Columns: match_id, season, player_name, team_name, available, reason
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "player_availability.csv"))
    df["is_available"] = df["available"].str.lower() == "yes"
    return df

