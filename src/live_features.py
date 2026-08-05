"""
live_features.py
-----------------
PURPOSE:
    Builds an IN-MATCH ("live") win-probability feature matrix from
    ball_by_ball_data.csv. This is the single highest-impact addition to the
    platform: the existing feature_engineering.py only ever looks at PRE-match
    context (Elo, form, venue, toss), which caps predictive power at ~50-55%
    accuracy in cricket, a sport where the game state changes enormously over
    20 overs.

SCOPE:
    This module models the SECOND INNINGS chase specifically — i.e. "given the
    current state of the chase, what is the chasing team's win probability?"
    This is the standard framing used by broadcast win predictors (e.g.
    ESPNcricinfo's Forecaster, CricViz WinViz) because a first-innings score
    has no target yet, so there's no "required run rate" signal to exploit.

WHAT IT COMPUTES, per completed over of the 2nd innings, for every match:
    - balls_bowled / balls_remaining
    - current_score, wickets_in_hand
    - current_run_rate (CRR)
    - target, runs_needed, required_run_rate (RRR)
    - rrr_minus_crr  (the single most telling live cricket stat: how far
      behind/ahead of the required pace the batting team currently is)
    - phase (powerplay / middle / death, one-hot)
    - pre_match_elo_diff (carried over from feature_engineering.py, so the
      live model still has pre-match team-strength context, not just the
      chase state)

LABEL:
    chasing_team_won (1/0) — taken from the match's actual result.

LEAKAGE GUARD:
    Every snapshot only uses information available AT THAT POINT in the
    chase (cumulative runs/wickets up to and including the over just
    completed). The label is the FINAL match outcome, which is correct for
    supervised learning (we're predicting the eventual winner from the
    current state), not for feature construction.

USAGE:
    from live_features import build_live_feature_matrix
    df = build_live_feature_matrix()
"""

import os
import numpy as np
import pandas as pd

from data_loader import load_matches, build_team_id_to_name_map

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BALLS_PER_OVER = 6

LIVE_FEATURE_COLS = [
    "over_completed", "balls_remaining", "current_score", "wickets_in_hand",
    "current_run_rate", "target", "runs_needed", "required_run_rate",
    "rrr_minus_crr", "is_powerplay", "is_death_overs", "pre_match_elo_diff",
]


def _load_ball_by_ball() -> pd.DataFrame:
    """Loads ball_by_ball_data.csv and attaches human-readable team names."""
    df = pd.read_csv(os.path.join(DATA_DIR, "ball_by_ball_data.csv"))
    id_to_name = build_team_id_to_name_map()
    df["team_batting_name"] = df["team_batting"].map(id_to_name)
    df["team_bowling_name"] = df["team_bowling"].map(id_to_name)
    return df


def build_live_feature_matrix() -> pd.DataFrame:
    """
    Builds the over-by-over 2nd-innings live feature matrix.

    Returns:
        pd.DataFrame with one row per (match_id, over_completed) and columns
        LIVE_FEATURE_COLS + ["match_id", "chasing_team_won"].
    """
    balls = _load_ball_by_ball()

    # Only regular 2-innings matches (drop rare super-over rows, innings 3+).
    balls = balls[(balls["innings"].isin([1, 2])) & (~balls["is_super_over"])].copy()

    matches = load_matches()
    matches = matches[matches["is_decisive"]].copy()

    # Pull elo_diff (team1 - team2) computed by the existing pipeline so the
    # live model retains pre-match team-strength context.
    from elo_rating import compute_elo_ratings
    matches, _ = compute_elo_ratings(matches)

    match_ctx = matches[[
        "match_id", "team1_name", "team2_name", "team1_won", "team1_elo_pre", "team2_elo_pre"
    ]]

    balls = balls.merge(match_ctx, on="match_id", how="inner")
    balls = balls.sort_values(["match_id", "innings", "over_number", "ball_number"])

    # Legal deliveries only count toward the 6-ball over (wides/no-balls don't).
    balls["is_legal_ball"] = ~(balls["is_wide_ball"] | balls["is_no_ball"])

    grp_cols = ["match_id", "innings"]
    balls["cum_runs"] = balls.groupby(grp_cols)["total_runs"].cumsum()
    balls["cum_wickets"] = balls.groupby(grp_cols)["is_wicket"].cumsum()
    balls["legal_ball_count"] = balls.groupby(grp_cols)["is_legal_ball"].cumsum()

    # First-innings final score -> the target the 2nd innings is chasing.
    innings1_final = (
        balls[balls["innings"] == 1]
        .groupby("match_id")["cum_runs"].max()
        .rename("innings1_total")
    )

    # Snapshot at the END of each completed over (legal_ball_count is a
    # multiple of 6): this reduces ~140K deliveries/innings to ~20
    # snapshots/innings and matches how commentators report "score after over N".
    innings2 = balls[balls["innings"] == 2].copy()
    innings2 = innings2[
        (innings2["legal_ball_count"] % BALLS_PER_OVER == 0) & (innings2["legal_ball_count"] > 0)
    ]
    # If multiple rows share the same legal_ball_count (extras on the 6th
    # ball), keep the LAST one so cum_runs/cum_wickets reflect the full over.
    innings2 = innings2.sort_values(["match_id", "legal_ball_count"])
    innings2 = innings2.groupby(["match_id", "legal_ball_count"], as_index=False).last()

    innings2 = innings2.merge(innings1_final, on="match_id", how="inner")

    innings2["over_completed"] = innings2["legal_ball_count"] // BALLS_PER_OVER
    innings2["balls_remaining"] = (20 * BALLS_PER_OVER) - innings2["legal_ball_count"]
    innings2["current_score"] = innings2["cum_runs"]
    innings2["wickets_in_hand"] = 10 - innings2["cum_wickets"]

    overs_played = innings2["legal_ball_count"] / BALLS_PER_OVER
    innings2["current_run_rate"] = innings2["current_score"] / overs_played.replace(0, np.nan)
    innings2["current_run_rate"] = innings2["current_run_rate"].fillna(0.0)

    innings2["target"] = innings2["innings1_total"] + 1
    innings2["runs_needed"] = (innings2["target"] - innings2["current_score"]).clip(lower=0)

    overs_remaining = innings2["balls_remaining"] / BALLS_PER_OVER
    innings2["required_run_rate"] = (
        innings2["runs_needed"] / overs_remaining.replace(0, np.nan)
    )
    # Match already effectively decided (last ball, or already chased down):
    # cap RRR rather than leaving inf/NaN, so the model sees "very high pressure"
    # instead of a broken value.
    innings2["required_run_rate"] = innings2["required_run_rate"].fillna(
        innings2["runs_needed"].clip(lower=0) * 6.0
    ).clip(upper=36.0)

    innings2["rrr_minus_crr"] = innings2["required_run_rate"] - innings2["current_run_rate"]

    innings2["is_powerplay"] = (innings2["over_completed"] <= 6).astype(int)
    innings2["is_death_overs"] = (innings2["over_completed"] >= 16).astype(int)

    # Pre-match elo_diff, reoriented to be from the CHASING team's perspective
    # (team_batting_name), not fixed to team1/team2.
    innings2["pre_match_elo_diff"] = np.where(
        innings2["team_batting_name"] == innings2["team1_name"],
        innings2["team1_elo_pre"] - innings2["team2_elo_pre"],
        innings2["team2_elo_pre"] - innings2["team1_elo_pre"],
    )

    # Label: did the chasing team (team_batting_name) go on to win?
    winner_name = np.where(innings2["team1_won"] == 1, innings2["team1_name"], innings2["team2_name"])
    innings2["chasing_team_won"] = (innings2["team_batting_name"] == winner_name).astype(int)

    out_cols = ["match_id", "team_batting_name", "team_bowling_name"] + LIVE_FEATURE_COLS + ["chasing_team_won"]
    return innings2[out_cols].reset_index(drop=True)


if __name__ == "__main__":
    df = build_live_feature_matrix()
    print(f"Live feature matrix: {len(df)} over-by-over snapshots from "
          f"{df['match_id'].nunique()} matches")
    print(df[LIVE_FEATURE_COLS + ["chasing_team_won"]].describe())
    print("\nSample (a single close chase):")
    sample_match = df["match_id"].iloc[0]
    print(df[df["match_id"] == sample_match][
        ["over_completed", "current_score", "wickets_in_hand", "current_run_rate",
         "required_run_rate", "rrr_minus_crr", "chasing_team_won"]
    ].to_string(index=False))
