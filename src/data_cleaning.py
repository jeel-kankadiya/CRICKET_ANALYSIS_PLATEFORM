"""
============================================================================================
  IPL Cricket Analytics Platform — Data Cleaning & Preprocessing Pipeline
============================================================================================
  Handles:
    1. ipl.csv           -> Ball-by-ball match data with match-level context
    2. ball_by_ball_data.csv -> Granular delivery-level data with player type info

  Output (saved to data/processed/):
    - ipl_cleaned.csv
    - ball_by_ball_cleaned.csv
    - match_level.csv          (one row per match, for match-outcome ML)
    - player_batting_stats.csv (per-player batting features)
    - player_bowling_stats.csv (per-player bowling features)
    - team_performance.csv     (per-team per-season aggregates)
============================================================================================
"""

import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")

# ────────────────────────────────────────────────────────────────────────────────
# PATHS
# ────────────────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
DATA_DIR  = BASE_DIR / "data"
PROC_DIR  = DATA_DIR / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

IPL_RAW   = DATA_DIR / "ipl.csv"
BBB_RAW   = DATA_DIR / "ball_by_ball_data.csv"

# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _log(section, msg):
    print(f"[{section}] {msg}")


def _build_team_canonical_map():
    return {
        "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
        "RCB":                         "Royal Challengers Bengaluru",
        "Banglore":                    "Royal Challengers Bengaluru",
        "Bengaluru":                   "Royal Challengers Bengaluru",
        "Delhi Daredevils":            "Delhi Capitals",
        "DD":                          "Delhi Capitals",
        "Delhi":                       "Delhi Capitals",
        "DC":                          "Delhi Capitals",
        "Kings XI Punjab":             "Punjab Kings",
        "KXIP":                        "Punjab Kings",
        "Punjab":                      "Punjab Kings",
        "Deccan Chargers":             "Sunrisers Hyderabad",
        "SRH":                         "Sunrisers Hyderabad",
        "Hyderabad":                   "Sunrisers Hyderabad",
        "Rising Pune Supergiant":      "Rising Pune Supergiants",
        "RPS":                         "Rising Pune Supergiants",
        "Pune":                        "Rising Pune Supergiants",
        "MI":  "Mumbai Indians",
        "CSK": "Chennai Super Kings",
        "KKR": "Kolkata Knight Riders",
        "RR":  "Rajasthan Royals",
        "GT":  "Gujarat Titans",
        "GL":  "Gujarat Lions",
        "LSG": "Lucknow Super Giants",
        "KTK": "Kochi Tuskers Kerala",
        "PWI": "Pune Warriors",
        "Kolkatta":  "Kolkata Knight Riders",
        "Chennai":   "Chennai Super Kings",
        "Rajasthan": "Rajasthan Royals",
        "Mumbai":    "Mumbai Indians",
        "Lucknow":   "Lucknow Super Giants",
        "Kerala":    "Kochi Tuskers Kerala",
    }


def _normalise_season(s):
    s = str(s).strip()
    if "/" in s:
        parts = s.split("/")
        return f"{parts[0]}-{parts[1]}"
    return s


def _season_start_year(season):
    return int(str(season).split("-")[0])


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CLEAN ipl.csv
# ════════════════════════════════════════════════════════════════════════════════

def clean_ipl(path):
    _log("IPL", "Loading raw file ...")
    df = pd.read_csv(path, low_memory=False)
    _log("IPL", f"Raw shape: {df.shape}")

    # 1.1 Fix mixed-type columns
    df["result_margin"] = pd.to_numeric(df["result_margin"], errors="coerce")
    df["season"]        = df["season"].astype(str).str.strip()

    # 1.2 Normalise season labels
    df["season"]      = df["season"].apply(_normalise_season)
    df["season_year"] = df["season"].apply(_season_start_year).astype(int)
    _log("IPL", f"Seasons: {sorted(df['season'].unique())}")

    # 1.3 Parse dates
    df["date"] = pd.to_datetime(df["date"], dayfirst=False, errors="coerce")

    # 1.4 Standardise team names
    canon = _build_team_canonical_map()
    for col in ["team1", "team2", "toss_winner", "winner", "batting_team", "bowling_team"]:
        df[col] = df[col].map(lambda x: canon.get(x, x) if pd.notna(x) else x)
    _log("IPL", "Team names standardised")

    # 1.5 Fill null city (UAE venues)
    venue_city_map = {
        "Sharjah Cricket Stadium":               "Sharjah",
        "Dubai International Cricket Stadium":   "Dubai",
        "Sheikh Zayed Stadium":                  "Abu Dhabi",
        "Zayed Cricket Stadium":                 "Abu Dhabi",
    }
    null_city_mask = df["city"].isnull()
    df.loc[null_city_mask, "city"] = df.loc[null_city_mask, "venue"].map(venue_city_map)
    if df["city"].isnull().any():
        df["city"] = df["city"].fillna(df["venue"].str.split(",").str[-1].str.strip())
    _log("IPL", f"City nulls remaining: {df['city'].isnull().sum()}")

    # 1.6 Handle null winner (tie rows)
    tie_mask = df["result_margin"].isnull() & df["winner"].isnull()
    df.loc[tie_mask, "winner"]        = "Tie"
    df.loc[tie_mask, "result_margin"] = 0
    _log("IPL", f"Winner nulls remaining: {df['winner'].isnull().sum()}")

    # 1.7 Fill player_of_match
    df["player_of_match"] = df["player_of_match"].fillna("Unknown")

    # 1.8 Fix required_run_rate
    df["required_run_rate"] = df["required_run_rate"].replace([np.inf, -np.inf], np.nan)
    df.loc[df["required_run_rate"] > 36,  "required_run_rate"] = 36.0
    df.loc[df["required_run_rate"] < 0,   "required_run_rate"] = 0.0
    _log("IPL", "required_run_rate: inf->NaN, outliers capped [0, 36]")

    # 1.9 Fix current_run_rate outliers
    mask_crr   = df["current_run_rate"] > 36
    balls_faced = df["over"] * 6 + df["ball"]
    recomputed  = np.where(
        balls_faced > 0,
        (df["current_score"] / balls_faced * 6).round(2),
        df["current_run_rate"],
    )
    df.loc[mask_crr, "current_run_rate"] = pd.Series(recomputed, index=df.index)[mask_crr]
    _log("IPL", f"CRR outliers fixed: {mask_crr.sum()} rows")

    # 1.10 Wicket columns
    df["wicket_kind"] = df["wicket_kind"].fillna("not_out")
    df["player_out"]  = df["player_out"].fillna("none")
    df["fielder"]     = df["fielder"].fillna("none")

    # 1.11 Encode categorical targets
    df["toss_decision_enc"] = (df["toss_decision"] == "bat").astype(int)
    df["result_enc"]        = (df["result"] == "wickets").astype(int)

    # 1.12 Toss-winner also match-winner
    df["toss_winner_won"] = (
        (df["toss_winner"] == df["winner"]) & (df["winner"] != "Tie")
    ).astype(int)

    # 1.13 Over-phase flags
    df["is_powerplay"]   = (df["over"] < 6).astype(int)
    df["is_death_over"]  = (df["over"] >= 16).astype(int)
    df["is_middle_over"] = ((df["over"] >= 6) & (df["over"] < 16)).astype(int)

    # 1.14 Extra-only delivery flag
    df["is_extra_only"] = ((df["extras"] > 0) & (df["runs_scored"] == 0)).astype(int)

    # 1.15 Drop duplicates & sort
    before = len(df)
    df.drop_duplicates(inplace=True)
    _log("IPL", f"Duplicates removed: {before - len(df)}")
    df.sort_values(["match_id","inning","over","ball"], inplace=True, ignore_index=True)

    _log("IPL", f"Cleaned shape: {df.shape}")
    nulls = df.isnull().sum()
    _log("IPL", f"Remaining nulls:\n{nulls[nulls > 0]}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CLEAN ball_by_ball_data.csv
# ════════════════════════════════════════════════════════════════════════════════

def _build_team_id_to_name():
    return {
        1:    "Royal Challengers Bengaluru",
        2:    "Sunrisers Hyderabad",
        3:    "Mumbai Indians",
        4:    "Rising Pune Supergiants",
        5:    "Gujarat Lions",
        6:    "Kolkata Knight Riders",
        129:  "Chennai Super Kings",
        134:  "Rajasthan Royals",
        252:  "Delhi Capitals",
        494:  "Punjab Kings",
        614:  "Lucknow Super Giants",
        615:  "Gujarat Titans",
        1068: "Sunrisers Hyderabad",
        1414: "Kochi Tuskers Kerala",
        1419: "Pune Warriors",
        3604: "Rising Pune Supergiants",
    }


def _clean_bowler_type(val):
    if pd.isna(val) or str(val).strip() == "":
        return "Unknown"
    primary = str(val).split(",")[0].strip()
    return primary if primary else "Unknown"


def clean_ball_by_ball(path):
    _log("BBB", "Loading raw file ...")
    df = pd.read_csv(path)
    _log("BBB", f"Raw shape: {df.shape}")

    # 2.1 Map team IDs to names
    id_map = _build_team_id_to_name()
    df["team_batting_name"] = df["team_batting"].map(id_map).fillna("Unknown")
    df["team_bowling_name"] = df["team_bowling"].map(id_map).fillna("Unknown")

    # 2.2 Normalise season
    season_map = {2008: "2007-08", 2010: "2009-10", 2021: "2020-21"}
    df["season"] = df["season_id"].map(lambda s: season_map.get(s, str(s)))

    # 2.3 Super-over flag
    df["is_super_over"]    = df["is_super_over"].astype(bool)
    df["super_over_inning"] = (df["innings"] > 2).astype(int)

    # 2.4 Clean batsman_type
    df["batsman_type"] = df["batsman_type"].fillna("Unknown")

    # 2.5 Normalise bowler_type
    df["bowler_type"] = df["bowler_type"].apply(_clean_bowler_type)

    # 2.6 Wicket/fielder nulls
    df["player_out"]        = df["player_out"].fillna("none")
    df["fielders_involved"] = df["fielders_involved"].fillna("none")
    df["wicket_kind"]       = df["wicket_kind"].fillna("not_out")

    # 2.7 Extended over flag
    df["is_extended_over"] = (df["ball_number"] > 5).astype(int)

    # 2.8 Boolean dtype guarantee
    for c in ["is_wicket","is_wide_ball","is_no_ball","is_leg_bye","is_bye","is_penalty","is_super_over"]:
        df[c] = df[c].astype(bool)

    # 2.9 Derived features
    df["is_boundary"]    = df["batter_runs"].isin([4, 6]).astype(int)
    df["is_six"]         = (df["batter_runs"] == 6).astype(int)
    df["is_four"]        = (df["batter_runs"] == 4).astype(int)
    df["is_dot_ball"]    = (
        (df["batter_runs"] == 0) & (~df["is_wide_ball"]) & (~df["is_no_ball"])
    ).astype(int)
    df["is_powerplay"]   = (df["over_number"] < 6).astype(int)
    df["is_death_over"]  = (df["over_number"] >= 16).astype(int)
    df["is_middle_over"] = ((df["over_number"] >= 6) & (df["over_number"] < 16)).astype(int)
    df["ball_id"]        = (
        df["match_id"].astype(str) + "_"
        + df["innings"].astype(str) + "_"
        + df["over_number"].astype(str) + "."
        + df["ball_number"].astype(str)
    )

    # 2.10 Dedup & sort
    before = len(df)
    df.drop_duplicates(inplace=True)
    _log("BBB", f"Duplicates removed: {before - len(df)}")
    df.sort_values(["match_id","innings","over_number","ball_number"], inplace=True, ignore_index=True)

    _log("BBB", f"Cleaned shape: {df.shape}")
    nulls = df.isnull().sum()
    _log("BBB", f"Remaining nulls:\n{nulls[nulls > 0]}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MATCH-LEVEL FEATURE TABLE
# ════════════════════════════════════════════════════════════════════════════════

def build_match_level(ipl_clean):
    _log("MATCH", "Building match-level feature table ...")

    meta_cols = [
        "match_id","season","season_year","date","city","venue",
        "team1","team2","toss_winner","toss_decision","toss_decision_enc",
        "winner","result","result_margin","player_of_match","toss_winner_won",
    ]
    match_meta = (
        ipl_clean[meta_cols]
        .drop_duplicates(subset="match_id")
        .reset_index(drop=True)
    )

    inn_agg = (
        ipl_clean.groupby(["match_id","inning"])
        .agg(
            total_runs    = ("runs_scored", "sum"),
            total_extras  = ("extras",      "sum"),
            total_wickets = ("wicket_kind", lambda x: (x != "not_out").sum()),
            balls_bowled  = ("ball",        "count"),
            sixes         = ("runs_scored", lambda x: (x == 6).sum()),
            fours         = ("runs_scored", lambda x: (x == 4).sum()),
        )
        .reset_index()
    )

    inn1 = inn_agg[inn_agg["inning"] == 1].add_suffix("_inn1").rename(columns={"match_id_inn1": "match_id"})
    inn2 = inn_agg[inn_agg["inning"] == 2].add_suffix("_inn2").rename(columns={"match_id_inn2": "match_id"})

    match_df = (
        match_meta
        .merge(inn1.drop(columns="inning_inn1"), on="match_id", how="left")
        .merge(inn2.drop(columns="inning_inn2"), on="match_id", how="left")
    )

    match_df["win_by_runs"]    = np.where(match_df["result"] == "runs",    match_df["result_margin"], 0)
    match_df["win_by_wickets"] = np.where(match_df["result"] == "wickets", match_df["result_margin"], 0)
    match_df["team1_won"]      = (match_df["winner"] == match_df["team1"]).astype(int)

    _log("MATCH", f"Match table shape: {match_df.shape}")
    return match_df


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PLAYER BATTING & BOWLING STATS
# ════════════════════════════════════════════════════════════════════════════════

def build_player_batting_stats(bbb_clean):
    _log("BATTING", "Aggregating player batting stats ...")
    legal = bbb_clean[~bbb_clean["is_wide_ball"]].copy()

    agg = (
        legal.groupby(["batter","season"])
        .agg(
            matches     = ("match_id",    "nunique"),
            runs        = ("batter_runs", "sum"),
            balls_faced = ("batter_runs", "count"),
            fours       = ("is_four",     "sum"),
            sixes       = ("is_six",      "sum"),
            dot_balls   = ("is_dot_ball", "sum"),
            boundaries  = ("is_boundary", "sum"),
            dismissals  = ("is_wicket",   "sum"),
        )
        .reset_index()
    )

    agg["strike_rate"]   = (agg["runs"] / agg["balls_faced"] * 100).round(2)
    agg["average"]       = np.where(
        agg["dismissals"] > 0,
        (agg["runs"] / agg["dismissals"]).round(2),
        agg["runs"],
    )
    agg["boundary_pct"] = (agg["boundaries"] / agg["balls_faced"] * 100).round(2)
    agg["dot_ball_pct"] = (agg["dot_balls"]  / agg["balls_faced"] * 100).round(2)

    _log("BATTING", f"Shape: {agg.shape}")
    return agg


def build_player_bowling_stats(bbb_clean):
    _log("BOWLING", "Aggregating player bowling stats ...")
    bowler_wicket_kinds = {
        "caught","bowled","lbw","caught and bowled",
        "stumped","hit wicket","obstructing the field",
    }
    legal = bbb_clean[~bbb_clean["is_wide_ball"] & ~bbb_clean["is_no_ball"]].copy()

    agg = (
        legal.groupby(["bowler","season"])
        .agg(
            matches       = ("match_id",    "nunique"),
            balls         = ("total_runs",  "count"),
            runs_conceded = ("total_runs",  "sum"),
            dot_balls     = ("is_dot_ball", "sum"),
            fours         = ("is_four",     "sum"),
            sixes         = ("is_six",      "sum"),
            wickets       = ("wicket_kind", lambda x: x[x.isin(bowler_wicket_kinds)].count()),
        )
        .reset_index()
    )

    agg["overs"]       = (agg["balls"] / 6).round(1)
    agg["economy"]     = np.where(agg["overs"] > 0, (agg["runs_conceded"] / agg["overs"]).round(2), 0.0)
    agg["bowling_avg"] = np.where(agg["wickets"] > 0, (agg["runs_conceded"] / agg["wickets"]).round(2), np.nan)
    agg["bowling_sr"]  = np.where(agg["wickets"] > 0, (agg["balls"] / agg["wickets"]).round(2), np.nan)
    agg["dot_ball_pct"]= (agg["dot_balls"] / agg["balls"] * 100).round(2)

    _log("BOWLING", f"Shape: {agg.shape}")
    return agg


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 5 — TEAM PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════════

def build_team_performance(match_level):
    _log("TEAM", "Building team performance table ...")
    records = []
    for _, row in match_level.iterrows():
        for team in [row["team1"], row["team2"]]:
            won  = (row["winner"] == team)
            lost = (row["winner"] != team) and (row["winner"] != "Tie") and pd.notna(row["winner"])
            tied = (row["winner"] == "Tie")
            records.append({
                "season":       row["season"],
                "season_year":  row["season_year"],
                "team":         team,
                "match_id":     row["match_id"],
                "won":          int(won),
                "lost":         int(lost),
                "tied":         int(tied),
                "toss_won":     int(row["toss_winner"] == team),
                "toss_won_match": int((row["toss_winner"] == team) and won),
            })

    df = pd.DataFrame(records)
    team_season = (
        df.groupby(["team","season","season_year"])
        .agg(
            matches    = ("match_id", "nunique"),
            wins       = ("won",      "sum"),
            losses     = ("lost",     "sum"),
            ties       = ("tied",     "sum"),
            tosses_won = ("toss_won", "sum"),
            toss_to_win= ("toss_won_match","sum"),
        )
        .reset_index()
    )
    team_season["win_pct"]            = (team_season["wins"] / team_season["matches"] * 100).round(2)
    team_season["toss_win_conversion"]= np.where(
        team_season["tosses_won"] > 0,
        (team_season["toss_to_win"] / team_season["tosses_won"] * 100).round(2),
        0.0,
    )
    _log("TEAM", f"Shape: {team_season.shape}")
    return team_season


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  IPL Analytics Platform — Data Cleaning & Preprocessing")
    print("=" * 70)

    ipl_clean      = clean_ipl(IPL_RAW)
    bbb_clean      = clean_ball_by_ball(BBB_RAW)
    match_level    = build_match_level(ipl_clean)
    batting_stats  = build_player_batting_stats(bbb_clean)
    bowling_stats  = build_player_bowling_stats(bbb_clean)
    team_perf      = build_team_performance(match_level)

    outputs = {
        "ipl_cleaned.csv":           ipl_clean,
        "ball_by_ball_cleaned.csv":  bbb_clean,
        "match_level.csv":           match_level,
        "player_batting_stats.csv":  batting_stats,
        "player_bowling_stats.csv":  bowling_stats,
        "team_performance.csv":      team_perf,
    }

    print("\n" + "=" * 70)
    print("  Saving processed files to:", PROC_DIR)
    print("=" * 70)
    for fname, df in outputs.items():
        out_path = PROC_DIR / fname
        df.to_csv(out_path, index=False)
        size_mb = out_path.stat().st_size / 1_048_576
        print(f"  [OK]  {fname:<40} shape={df.shape}  ({size_mb:.2f} MB)")

    print("\n  Preprocessing complete!")


if __name__ == "__main__":
    main()
