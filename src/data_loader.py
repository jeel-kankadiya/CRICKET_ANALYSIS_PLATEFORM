"""
data_loader.py
--------------
PURPOSE:
    Central data-access layer for the IPL Analytics Platform.
    All other modules import from here — nothing reads CSVs directly.

WHAT IT DOES:
    - Loads every raw CSV from the /data directory
    - Resolves integer team IDs to human-readable franchise names
    - Handles edge cases like dash-separated missing values, trailing
      asterisks on not-out scores, and string-encoded booleans
    - Returns clean, typed DataFrames that downstream code can use
      without any further wrangling
"""

import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
import os

# Build the path to /data from wherever this script lives
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ─────────────────────────────────────────────────────────────────────────────
# BASIC TABLE LOADERS
# These functions just read a single CSV and return it as-is.
# They are used internally by the higher-level loaders below.
# ─────────────────────────────────────────────────────────────────────────────

def load_teams():
    """
    Load teams_data.csv — the master list of IPL franchises.

    Returns a DataFrame with columns:
        team_id (int), team_name (str)

    This file maps integer team IDs to their canonical franchise name.
    It is used by build_team_id_to_name_map() to convert raw IDs found
    in ball_by_ball_data.csv into readable names.
    """
    teams = pd.read_csv(os.path.join(DATA_DIR, "teams_data.csv"))
    return teams


def load_team_aliases():
    """
    Load team_aliases.csv — all known historical name variants per team.

    Returns a DataFrame with columns:
        alias_id, team_id, alias_name

    Example: 'Delhi Daredevils', 'DD', 'Delhi' all map to team_id 252
    (Delhi Capitals). Used to standardise name references across datasets.
    """
    aliases = pd.read_csv(os.path.join(DATA_DIR, "team_aliases.csv"))
    return aliases


def build_team_id_to_name_map():
    """
    Build a lookup dictionary: team_id (int) -> canonical team_name (str).

    Reads teams_data.csv and returns a plain Python dict so callers can
    use .map() on a DataFrame column of integer IDs.

    Example output:
        {1: 'Royal Challengers Bengaluru', 6: 'Kolkata Knight Riders', ...}
    """
    teams = load_teams()
    return dict(zip(teams["team_id"], teams["team_name"]))


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def load_players():
    """
    Load players_data_updated.csv — biographical and style info per player.

    Returns a DataFrame containing at minimum:
        player_name, bat_style, bowl_style, field_pos, player_full_name

    Used by player_analytics.py to enrich career stats with handedness
    and playing role information.
    """
    players = pd.read_csv(os.path.join(DATA_DIR, "players_data_updated.csv"))
    return players


def load_allrounder_stats():
    """
    Load ipl_allround.csv — career aggregate batting AND bowling stats
    for every player who has appeared in IPL matches.

    Key operations performed here:
    1. Numeric coercion: many stat columns contain '-' (meaning no data)
       instead of NaN, so we force them to numeric with errors='coerce'.
    2. HighestScore parsing: the column stores values like '158*' where
       the '*' means the batter was not out. We:
         - Extract the boolean flag into 'HighestScoreNotOut'
         - Strip the '*' and store the clean integer in 'HighestScoreRuns'

    Returns:
        DataFrame with all original columns plus:
        - HighestScoreNotOut (bool): True if the innings was unbeaten
        - HighestScoreRuns  (int):  The numeric highest score
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_allround.csv"))

    # List of columns that should be numeric but may contain '-' placeholders
    numeric_cols = [
        "Matches", "Innings", "NotOuts", "Runs", "BattingAverage", "BallsFaced",
        "StrikeRate", "Hundreds", "Fifties", "Ducks", "Fours", "Sixes",
        "BowlInnings", "Overs", "Maidens", "RunsConceded", "Wickets",
        "BowlingAverage", "Economy", "BowlingStrikeRate", "FourWickets", "FiveWickets"
    ]
    for col in numeric_cols:
        if col in df.columns:
            # errors='coerce' turns '-' and any non-numeric string into NaN
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # HighestScore has trailing '*' for not-out innings -> extract numeric value + flag
    df["HighestScoreNotOut"] = df["HighestScore"].astype(str).str.contains(r"\*", na=False)
    df["HighestScoreRuns"] = (
        df["HighestScore"].astype(str).str.replace("*", "", regex=False)
    )
    df["HighestScoreRuns"] = pd.to_numeric(df["HighestScoreRuns"], errors="coerce")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# MATCH DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_matches():
    """
    Load ipl_matches_data.csv and enrich it with human-readable team names.

    Raw file stores team1, team2, toss_winner, match_winner as integer IDs.
    This function converts all four to readable names by joining with
    teams_data.csv, then adds two computed helper columns used by all
    downstream ML and analytics code.

    Processing steps:
    1. Map team ID columns -> '<col>_name' string columns
    2. Parse match_date as datetime (needed for chronological splits)
    3. Sort by date (ascending) so iterrows() always walks forward in time
    4. Add 'team1_won' (1/0) — binary label for supervised learning
    5. Add 'is_decisive' (bool) — True only for matches with a clear winner
       (i.e., result == 'win'). Ties and no-results are excluded from win-
       probability modelling but kept in the DataFrame for reference.

    Returns:
        DataFrame sorted chronologically, one row per match.
    """
    matches = pd.read_csv(os.path.join(DATA_DIR, "ipl_matches_data.csv"))
    id_to_name = build_team_id_to_name_map()

    # Create human-readable name columns alongside the original ID columns
    for col in ["team1", "team2", "toss_winner", "match_winner"]:
        matches[col + "_name"] = matches[col].map(id_to_name)

    # Convert date strings to proper datetime objects for sorting and arithmetic
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    matches = matches.sort_values("match_date").reset_index(drop=True)

    # Winner flag relative to team1 (used later for supervised learning)
    matches["team1_won"] = (matches["match_winner"] == matches["team1"]).astype(int)

    # Only keep matches that have a clear winner (drop ties / no-result for the
    # win-probability model; they are retained in a separate frame for reference)
    matches["is_decisive"] = matches["result"] == "win"

    return matches


# ─────────────────────────────────────────────────────────────────────────────
# SUPPLEMENTARY DATASET LOADERS
# Added for the 5-dataset expansion of the platform
# ─────────────────────────────────────────────────────────────────────────────

def load_auction_data():
    """
    Load ipl_auction_data.csv — IPL player auction records.

    Columns: season, player_name, role, base_price_lakhs,
             sold (Yes/No), sold_price_lakhs, team_name

    Numeric columns (prices) are coerced so unsold rows (no price) become NaN
    instead of strings, making arithmetic on sold prices safe.

    Used by dataset_analytics.auction_analytics() for:
        - Season-wise spending trends
        - Most expensive buys of all time
        - Average price by playing role
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_auction_data.csv"))
    df["sold_price_lakhs"] = pd.to_numeric(df["sold_price_lakhs"], errors="coerce")
    df["base_price_lakhs"] = pd.to_numeric(df["base_price_lakhs"], errors="coerce")
    return df


def load_player_season_stats():
    """
    Load player_season_stats.csv — season-wise batting & bowling stats per player.

    Columns: season, player_name, team_name, matches, innings, runs,
             batting_avg, strike_rate, fours, sixes, fifties, hundreds,
             wickets, economy, bowling_avg

    All stat columns are numeric-coerced to handle any '-' placeholders
    or missing entries gracefully.

    Used by dataset_analytics.player_season_trends() for career trajectory
    charts and per-season leaderboards on the dashboard.
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
    Load venue_details.csv — physical and historical attributes of each IPL ground.

    Columns: venue, city, capacity, pitch_type, avg_first_innings_score,
             bat_first_win_pct, dew_factor, boundary_size_m, total_matches_hosted

    Numeric coercion is applied to all quantitative columns.

    Used by dataset_analytics.venue_intelligence() to power:
        - Pitch-type win-rate breakdowns
        - Batting vs. chasing venue comparison
        - Dew-factor analysis for evening matches
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
    Load ipl_points_table.csv — season-wise IPL group-stage standings.

    Columns: season, team_name, matches_played, wins, losses, no_result,
             points, nrr, qualified (1/0), champion (1/0)

    Used by dataset_analytics.points_table_analytics() for:
        - Identifying season champions
        - Computing qualification rates per team
        - Finding the closest points races (smallest 1st–2nd place gap)
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "ipl_points_table.csv"))
    numeric_cols = ["matches_played", "wins", "losses", "no_result", "points", "nrr"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_player_availability():
    """
    Load player_availability.csv — match-level player availability records.

    Columns: match_id, season, player_name, team_name, available (Yes/No), reason

    Adds a derived boolean column 'is_available' (True when available == 'Yes')
    so downstream code doesn't need to do string comparisons.

    Used by dataset_analytics.availability_analytics() for:
        - Identifying injury-prone players
        - Measuring how team win rates change when key players are absent
        - Season-level injury trend analysis
    """
    df = pd.read_csv(os.path.join(DATA_DIR, "player_availability.csv"))
    # Convert the 'Yes'/'No' string column to a proper boolean for easy filtering
    df["is_available"] = df["available"].str.lower() == "yes"
    return df
