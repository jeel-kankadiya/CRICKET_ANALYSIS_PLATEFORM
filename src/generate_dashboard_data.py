"""
generate_dashboard_data.py
---------------------------
PURPOSE:
    Aggregates all analytical outputs, model metrics, Elo ratings, and pairwise
    predictions into a single precomputed JSON file (`outputs/dashboard_data.json`).

WHAT IT DOES:
    - Generates downsampled Elo rating history over time for line charts.
    - Computes team-level win percentages and venue statistics.
    - Evaluates toss impact (batting vs. fielding win rates).
    - Constructs full pairwise win-probability matrix across all active franchises.
    - Formats player leaderboards (Batting Impact, Bowling Impact, All-Rounder Index).
    - Merges model cross-validation results and feature importances.
    - Bundles analytics from all 5 supplementary datasets.
"""

import os
import json
import itertools
import numpy as np
import pandas as pd

from feature_engineering import build_feature_matrix
from player_analytics import build_player_ratings, MIN_INNINGS_BAT, MIN_INNINGS_BOWL
from match_simulator import MatchSimulator
from dataset_analytics import build_all_analytics

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def elo_history(df: pd.DataFrame) -> list:
    """
    Downsamples match-by-match Elo ratings to end-of-season ratings per franchise.

    Parameters:
        df (pd.DataFrame): Matches DataFrame containing pre-match Elo columns.

    Returns:
        list: List of dictionaries [{'team': ..., 'date': ..., 'elo': ..., 'season': ...}].
    """
    records = []
    for _, row in df.sort_values("match_date").iterrows():
        records.append({
            "team": row["team1_name"], "date": str(row["match_date"].date()),
            "elo": round(row["team1_elo_pre"], 1), "season": str(row["season"])
        })
        records.append({
            "team": row["team2_name"], "date": str(row["match_date"].date()),
            "elo": round(row["team2_elo_pre"], 1), "season": str(row["season"])
        })
    hist = pd.DataFrame(records)
    # Keep only the final match rating for each team in each season to optimize chart size
    season_end = (hist.sort_values("date")
                       .groupby(["team", "season"], as_index=False)
                       .last())
    return season_end.to_dict(orient="records")


def season_wins(df: pd.DataFrame) -> list:
    """
    Computes total match wins per team per IPL season.

    Returns:
        list: List of dictionaries [{'season': ..., 'team': ..., 'wins': ...}].
    """
    decisive = df[df["is_decisive"]]
    wins = decisive.groupby(["season", "match_winner_name"]).size().reset_index(name="wins")
    wins = wins.rename(columns={"match_winner_name": "team"})
    return wins.to_dict(orient="records")


def team_summary(df: pd.DataFrame) -> list:
    """
    Computes all-time match wins, matches played, and overall win percentage per team.

    Returns:
        list: List of dictionaries sorted by win percentage descending.
    """
    decisive = df[df["is_decisive"]]
    rows = []
    teams = pd.unique(pd.concat([df["team1_name"], df["team2_name"]]))
    for team in teams:
        played = decisive[(decisive["team1_name"] == team) | (decisive["team2_name"] == team)]
        won = decisive[decisive["match_winner_name"] == team]
        rows.append({
            "team": team,
            "matches_played": int(len(played)),
            "matches_won": int(len(won)),
            "win_pct": round(100.0 * len(won) / len(played), 1) if len(played) else 0.0,
        })
    return sorted(rows, key=lambda r: -r["win_pct"])


def venue_stats(df: pd.DataFrame) -> list:
    """
    Identifies the top 15 most frequently used IPL venues and match counts.

    Returns:
        list: List of dictionaries [{'venue': ..., 'matches': ...}].
    """
    decisive = df[df["is_decisive"]]
    grp = decisive.groupby("venue").size().reset_index(name="matches")
    grp = grp.sort_values("matches", ascending=False).head(15)
    return grp.to_dict(orient="records")


def toss_impact(df: pd.DataFrame) -> dict:
    """
    Calculates overall toss-win conversion rate and decision breakdown (bat vs field).

    Returns:
        dict: Overall toss win % and decision breakdown list.
    """
    decisive = df[df["is_decisive"]].copy()
    decisive["toss_winner_won"] = decisive["toss_winner"] == decisive["match_winner"]
    by_decision = decisive.groupby("toss_decision")["toss_winner_won"].mean().reset_index()
    by_decision["toss_winner_won_pct"] = (by_decision["toss_winner_won"] * 100.0).round(1)
    overall_rate = round(float(decisive["toss_winner_won"].mean()) * 100.0, 1)
    return {
        "overall_toss_winner_win_pct": overall_rate,
        "by_decision": by_decision[["toss_decision", "toss_winner_won_pct"]].to_dict(orient="records"),
    }


def win_probability_matrix(sim: MatchSimulator, teams: list) -> list:
    """
    Generates win probabilities for every possible pairwise match permutation among active teams.

    Returns:
        list: List of dicts [{'team1': ..., 'team2': ..., 'team1_win_prob': ...}].
    """
    matrix = []
    for t1, t2 in itertools.permutations(teams, 2):
        res = sim.predict(t1, t2)
        matrix.append({
            "team1": t1, "team2": t2,
            "team1_win_prob": res["team1_win_probability"],
        })
    return matrix


def leaderboards(ratings: pd.DataFrame) -> dict:
    """
    Extracts top 20 Batters, Bowlers, and All-Rounders for dashboard leaderboards.

    Parameters:
        ratings (pd.DataFrame): DataFrame returned by player_analytics.build_player_ratings().

    Returns:
        dict: Three lists of clean dictionaries ('top_batters', 'top_bowlers', 'top_allrounders').
    """
    def clean(sub, cols):
        return sub[cols].replace({np.nan: None}).to_dict(orient="records")

    bat = ratings[ratings["Innings"] >= MIN_INNINGS_BAT].dropna(subset=["batting_impact_score"])
    bat = bat.sort_values("batting_impact_score", ascending=False).head(20)

    bowl = ratings[ratings["BowlInnings"] >= MIN_INNINGS_BOWL].dropna(subset=["bowling_impact_score"])
    bowl = bowl.sort_values("bowling_impact_score", ascending=False).head(20)

    allr = ratings.dropna(subset=["allrounder_index"]).sort_values("allrounder_index", ascending=False).head(20)

    return {
        "top_batters": clean(bat, ["PlayerName", "Teams", "Matches", "Runs", "BattingAverage",
                                    "StrikeRate", "Hundreds", "Fifties", "batting_impact_score"]),
        "top_bowlers": clean(bowl, ["PlayerName", "Teams", "Matches", "Wickets", "BowlingAverage",
                                     "Economy", "FourWickets", "FiveWickets", "bowling_impact_score"]),
        "top_allrounders": clean(allr, ["PlayerName", "Teams", "Matches", "Runs", "Wickets",
                                          "batting_impact_score", "bowling_impact_score", "allrounder_index"]),
    }


def all_players_data(ratings: pd.DataFrame) -> list:
    """
    Returns clean, serialized dictionary of ALL 792 players with full career stats,
    handedness, style info, and calculated impact scores.
    """
    cols = [
        "PlayerName", "player_full_name", "Teams", "Span", "Matches",
        "Innings", "NotOuts", "Runs", "HighestScore", "BattingAverage",
        "BallsFaced", "StrikeRate", "Hundreds", "Fifties", "Ducks",
        "Fours", "Sixes", "BowlInnings", "Overs", "Maidens",
        "RunsConceded", "Wickets", "BestBowlingInnings", "BowlingAverage",
        "Economy", "BowlingStrikeRate", "FourWickets", "FiveWickets",
        "bat_style", "bowl_style", "field_pos",
        "batting_impact_score", "bowling_impact_score", "allrounder_index"
    ]
    sub = ratings[cols].replace({np.nan: None})
    return sub.to_dict(orient="records")


def main():
    """
    Main pipeline entrypoint to build and dump `outputs/dashboard_data.json`.
    """
    df, elo = build_feature_matrix()
    ratings = build_player_ratings()
    sim = MatchSimulator()

    # Load model performance reports
    with open(os.path.join(OUTPUTS_DIR, "model_metrics.json")) as f:
        model_metrics = json.load(f)
    with open(os.path.join(OUTPUTS_DIR, "cv_results.json")) as f:
        cv_results = json.load(f)
    feat_imp = pd.read_csv(os.path.join(OUTPUTS_DIR, "feature_importance.csv")).to_dict(orient="records")

    current_teams = sorted([t for t in elo.keys()])

    print("  Building new-dataset analytics (auction / venue / points / trends / availability)...")
    new_analytics = build_all_analytics()

    # Bundle all analytics into a single master dictionary
    bundle = {
        "generated_from_matches": int(len(df)),
        "seasons": sorted(df["season"].astype(str).unique().tolist()),
        "current_elo_ratings": {k: round(v, 1) for k, v in sorted(elo.items(), key=lambda x: -x[1])},
        "elo_history": elo_history(df),
        "season_wins": season_wins(df),
        "team_summary": team_summary(df),
        "venue_stats": venue_stats(df),
        "toss_impact": toss_impact(df),
        "win_probability_matrix": win_probability_matrix(sim, current_teams),
        "leaderboards": leaderboards(ratings),
        "all_players": all_players_data(ratings),
        "model_metrics": model_metrics,
        "cv_results": cv_results,
        "feature_importance": feat_imp,
        "auction_trends":       new_analytics["auction"],
        "venue_intelligence":   new_analytics["venue_intel"],
        "points_table_history": new_analytics["points_table"],
        "player_season_trends": new_analytics["player_trends"],
        "availability_summary": new_analytics["availability"],
    }

    out_path = os.path.join(OUTPUTS_DIR, "dashboard_data.json")
    with open(out_path, "w") as f:
        json.dump(bundle, f, default=str)
    print(f"Wrote dashboard bundle -> {out_path}")
    print(f"  Teams: {len(current_teams)}, Matches: {len(df)}, "
          f"Win-prob matrix entries: {len(bundle['win_probability_matrix'])}")


if __name__ == "__main__":
    main()
