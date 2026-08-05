"""
feature_engineering.py
-----------------------
PURPOSE:
    Constructs the master feature matrix used to train and evaluate match outcome models.

WHAT IT DOES:
    Computes 9 key predictive features for every match using STRICTLY historical data:
    1. Pre-match Elo rating difference (team1_elo - team2_elo)
    2. Short-term rolling form difference (win rate over last 5 matches)
    3. Momentum difference (average win margin over last 5 matches)
    4. Experience difference (total matches played prior to this match)
    5. Team 1 venue win rate at the specific stadium
    6. Team 2 venue win rate at the specific stadium
    7. Head-to-head win rate between the two teams prior to this match
    8. Toss victory flag (did team 1 win the toss?)
    9. Toss decision choice (did toss winner choose to bat?)

GUARANTEE AGAINST DATA LEAKAGE:
    All features for match N are computed using only matches 1 to N-1.
"""

import pandas as pd
import numpy as np
from collections import defaultdict, deque

from data_loader import load_matches
from elo_rating import compute_elo_ratings

# Number of past matches to consider for short-term form and momentum calculation
FORM_WINDOW = 5

# Master list of feature column names used across model training and simulation
FEATURE_COLS = [
    "elo_diff", "form_diff", "momentum_diff", "experience_diff",
    "team1_venue_winrate", "team2_venue_winrate",
    "h2h_team1_winrate", "toss_won_by_team1", "toss_decision_bat",
]


def build_feature_matrix():
    """
    Iterates chronologically through IPL match history to construct a leak-free
    feature matrix for match outcome prediction.

    Internal Helper Concepts & State Tracking:
        - last_results: Keeps a deque of last 5 match outcomes (1 for win, 0 for loss) per team.
        - last_margins: Keeps normalized win margins (positive for win, negative for loss).
        - venue_record: Tracks (wins, total_matches) for each (team, venue) pair.
        - h2h_record: Tracks (teamA_wins, total_matches) for every paired matchup.
        - matches_played: Cumulative count of matches played prior to current fixture.

    Returns:
        tuple: (matches_df, final_elo_dict)
            - matches_df (pd.DataFrame): Matches enriched with all FEATURE_COLS.
            - final_elo_dict (dict): Latest Elo ratings for all teams.
    """
    matches = load_matches()
    matches, final_elo = compute_elo_ratings(matches)

    # Deques with fixed max length automatically drop oldest entries as new matches arrive
    last_results = defaultdict(lambda: deque(maxlen=FORM_WINDOW))
    last_margins = defaultdict(lambda: deque(maxlen=FORM_WINDOW))
    last_match_date = {}
    venue_record = defaultdict(lambda: [0, 0])  # [wins, played]
    h2h_record = defaultdict(lambda: [0, 0])    # [teamA_wins, played]
    matches_played = defaultdict(int)

    # Lists to store computed features row by row
    team1_form, team2_form = [], []
    team1_rest, team2_rest = [], []
    team1_venue_wr, team2_venue_wr = [], []
    team1_momentum, team2_momentum = [], []
    team1_experience, team2_experience = [], []
    h2h_team1_wr = []

    for _, row in matches.iterrows():
        t1, t2 = row["team1_name"], row["team2_name"]
        venue = row["venue"]
        date = row["match_date"]

        # Helper 1: Compute rolling win rate over last N matches (default 0.5 if no history)
        def form_rate(team):
            hist = last_results[team]
            return float(np.mean(hist)) if len(hist) > 0 else 0.5

        # Helper 2: Calculate days rest since team's last played match
        def rest_days(team):
            if team in last_match_date:
                return (date - last_match_date[team]).days
            return np.nan

        # Helper 3: Compute team win rate at current venue prior to this match
        def venue_wr(team):
            w, p = venue_record[(team, venue)]
            return w / p if p > 0 else 0.5

        # Helper 4: Compute rolling momentum (mean normalized win margin)
        def momentum(team):
            hist = last_margins[team]
            return float(np.mean(hist)) if len(hist) > 0 else 0.0

        # Step A: Capture pre-match state BEFORE applying current match result
        team1_form.append(form_rate(t1))
        team2_form.append(form_rate(t2))
        team1_rest.append(rest_days(t1))
        team2_rest.append(rest_days(t2))
        team1_venue_wr.append(venue_wr(t1))
        team2_venue_wr.append(venue_wr(t2))
        team1_momentum.append(momentum(t1))
        team2_momentum.append(momentum(t2))
        team1_experience.append(matches_played[t1])
        team2_experience.append(matches_played[t2])

        # Step B: Compute Head-to-Head win rate prior to this match
        key = tuple(sorted([t1, t2]))
        w, p = h2h_record[key]
        if p > 0:
            teamA_wr = w / p
            h2h_team1_wr.append(teamA_wr if key[0] == t1 else 1.0 - teamA_wr)
        else:
            h2h_team1_wr.append(0.5)

        # Step C: Update historical tracking state IF match is decisive
        if row["is_decisive"] and not pd.isna(t1) and not pd.isna(t2):
            t1_won = (row["team1_won"] == 1)
            
            # Update form history
            last_results[t1].append(1 if t1_won else 0)
            last_results[t2].append(0 if t1_won else 1)

            # Calculate normalized win margin (capped at 3.0 to prevent blowout outlier skew)
            runs_m = row["win_by_runs"] if not pd.isna(row["win_by_runs"]) else None
            wkts_m = row["win_by_wickets"] if not pd.isna(row["win_by_wickets"]) else None
            if runs_m is not None:
                norm_margin = min(runs_m / 20.0, 3.0)
            elif wkts_m is not None:
                norm_margin = min(wkts_m / 10.0, 3.0)
            else:
                norm_margin = 0.5

            # Winner gets positive margin; loser gets negative margin
            last_margins[t1 if t1_won else t2].append(norm_margin)
            last_margins[t2 if t1_won else t1].append(-norm_margin)

            # Update match experience counts
            matches_played[t1] += 1
            matches_played[t2] += 1

            # Update venue performance record
            venue_record[(t1, venue)][1] += 1
            venue_record[(t2, venue)][1] += 1
            if t1_won:
                venue_record[(t1, venue)][0] += 1
            else:
                venue_record[(t2, venue)][0] += 1

            # Update head-to-head record
            h2h_record[key][1] += 1
            if (key[0] == t1 and t1_won) or (key[0] == t2 and not t1_won):
                h2h_record[key][0] += 1

        # Update last played date
        last_match_date[t1] = date
        last_match_date[t2] = date

    # Step D: Attach all computed feature columns to the DataFrame
    matches["team1_form"] = team1_form
    matches["team2_form"] = team2_form
    matches["form_diff"] = matches["team1_form"] - matches["team2_form"]
    matches["team1_rest_days"] = team1_rest
    matches["team2_rest_days"] = team2_rest
    matches["team1_venue_winrate"] = team1_venue_wr
    matches["team2_venue_winrate"] = team2_venue_wr
    matches["h2h_team1_winrate"] = h2h_team1_wr
    matches["toss_won_by_team1"] = (matches["toss_winner"] == matches["team1"]).astype(int)
    matches["toss_decision_bat"] = (matches["toss_decision"] == "bat").astype(int)
    matches["team1_momentum"] = team1_momentum
    matches["team2_momentum"] = team2_momentum
    matches["momentum_diff"] = matches["team1_momentum"] - matches["team2_momentum"]
    matches["team1_experience"] = team1_experience
    matches["team2_experience"] = team2_experience
    matches["experience_diff"] = matches["team1_experience"] - matches["team2_experience"]

    return matches, final_elo


if __name__ == "__main__":
    df, elo = build_feature_matrix()
    print(df[["match_date", "team1_name", "team2_name"] + FEATURE_COLS + ["team1_won"]].tail(10).to_string())
    print("\nFeature matrix shape:", df.shape)
    print("\nMissing values in feature cols:\n", df[FEATURE_COLS].isnull().sum())
