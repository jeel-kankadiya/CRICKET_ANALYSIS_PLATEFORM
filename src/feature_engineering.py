"""
feature_engineering.py
-----------------------
Builds the full feature matrix used by the win-probability models:

  - Elo ratings (pre-match, leak-free)                 -> elo_rating.py
  - Rolling form (win rate over last N matches)
  - Head-to-head win rate between the two teams
  - Venue-specific win rate for each team
  - Toss winner / toss decision effects
  - Rest days since each team's previous match

All rolling/aggregate features are computed using only matches STRICTLY
BEFORE the current one, so there is no data leakage from the future.
"""

import pandas as pd
import numpy as np
from collections import defaultdict, deque

from data_loader import load_matches
from elo_rating import compute_elo_ratings

FORM_WINDOW = 5


def build_feature_matrix():
    matches = load_matches()
    matches, final_elo = compute_elo_ratings(matches)

    last_results = defaultdict(lambda: deque(maxlen=FORM_WINDOW))
    last_margins = defaultdict(lambda: deque(maxlen=FORM_WINDOW))  # normalized win/loss margin
    last_match_date = {}
    venue_record = defaultdict(lambda: [0, 0])
    h2h_record = defaultdict(lambda: [0, 0])
    matches_played = defaultdict(int)

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

        def form_rate(team):
            hist = last_results[team]
            return np.mean(hist) if len(hist) > 0 else 0.5

        def rest_days(team):
            if team in last_match_date:
                return (date - last_match_date[team]).days
            return np.nan

        def venue_wr(team):
            w, p = venue_record[(team, venue)]
            return w / p if p > 0 else 0.5

        def momentum(team):
            hist = last_margins[team]
            return np.mean(hist) if len(hist) > 0 else 0.0

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

        key = tuple(sorted([t1, t2]))
        w, p = h2h_record[key]
        if p > 0:
            teamA_wr = w / p
            h2h_team1_wr.append(teamA_wr if key[0] == t1 else 1 - teamA_wr)
        else:
            h2h_team1_wr.append(0.5)

        if row["is_decisive"] and not pd.isna(t1) and not pd.isna(t2):
            t1_won = row["team1_won"] == 1
            last_results[t1].append(1 if t1_won else 0)
            last_results[t2].append(0 if t1_won else 1)

            # normalized margin: runs margin / 20, wickets margin / 10 (rough T20 scale),
            # signed positive for the winner, negative for the loser
            runs_m = row["win_by_runs"] if not pd.isna(row["win_by_runs"]) else None
            wkts_m = row["win_by_wickets"] if not pd.isna(row["win_by_wickets"]) else None
            if runs_m is not None:
                norm_margin = min(runs_m / 20.0, 3.0)
            elif wkts_m is not None:
                norm_margin = min(wkts_m / 10.0, 3.0)
            else:
                norm_margin = 0.5
            last_margins[t1 if t1_won else t2].append(norm_margin)
            last_margins[t2 if t1_won else t1].append(-norm_margin)

            matches_played[t1] += 1
            matches_played[t2] += 1

            venue_record[(t1, venue)][1] += 1
            venue_record[(t2, venue)][1] += 1
            if t1_won:
                venue_record[(t1, venue)][0] += 1
            else:
                venue_record[(t2, venue)][0] += 1

            h2h_record[key][1] += 1
            if (key[0] == t1 and t1_won) or (key[0] == t2 and not t1_won):
                h2h_record[key][0] += 1

        last_match_date[t1] = date
        last_match_date[t2] = date

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


FEATURE_COLS = [
    "elo_diff", "form_diff", "momentum_diff", "experience_diff",
    "team1_venue_winrate", "team2_venue_winrate",
    "h2h_team1_winrate", "toss_won_by_team1", "toss_decision_bat",
]


if __name__ == "__main__":
    df, elo = build_feature_matrix()
    print(df[["match_date", "team1_name", "team2_name"] + FEATURE_COLS + ["team1_won"]].tail(10).to_string())
    print("\nFeature matrix shape:", df.shape)
    print("\nMissing values in feature cols:\n", df[FEATURE_COLS].isnull().sum())
