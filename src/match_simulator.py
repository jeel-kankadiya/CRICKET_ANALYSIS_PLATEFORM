"""
match_simulator.py
--------------------
Given two team names (+ optional venue / toss info), reconstructs the same
pre-match features used in training (current Elo, current form, current
head-to-head, venue record) from the full match history, feeds them into
the trained Gradient Boosting model, and returns a win-probability estimate
for a hypothetical / upcoming fixture.

This is the "Match Simulation" component of the platform: it lets a user
ask "what if Team A played Team B at Venue X tomorrow?" without needing an
actual played match row.
"""

import os
import joblib
import numpy as np
import pandas as pd

from feature_engineering import build_feature_matrix, FEATURE_COLS

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(ROOT, "models")


class MatchSimulator:
    def __init__(self):
        self.df, self.elo = build_feature_matrix()
        self.model = joblib.load(os.path.join(MODELS_DIR, "gradient_boosting.pkl"))
        self._build_current_state()

    def _build_current_state(self):
        """Snapshot each team's latest known form/elo/venue stats from full history."""
        df = self.df
        self.current_elo = self.elo  # final ratings after all matches

        # latest rolling form per team = form value going INTO their most recent match,
        # updated one more step using their most recent result
        last_form = {}
        for _, row in df.sort_values("match_date").iterrows():
            last_form[row["team1_name"]] = row["team1_form"]
            last_form[row["team2_name"]] = row["team2_form"]
        self.current_form = last_form

        last_momentum = {}
        for _, row in df.sort_values("match_date").iterrows():
            last_momentum[row["team1_name"]] = row["team1_momentum"]
            last_momentum[row["team2_name"]] = row["team2_momentum"]
        self.current_momentum = last_momentum

        experience = {}
        for _, row in df.sort_values("match_date").iterrows():
            experience[row["team1_name"]] = row["team1_experience"]
            experience[row["team2_name"]] = row["team2_experience"]
        self.current_experience = experience

        # venue win rates: aggregate across ALL history (not just pre-match snapshot)
        venue_stats = {}
        for _, row in df[df["is_decisive"]].iterrows():
            for team, venue, won in [
                (row["team1_name"], row["venue"], row["team1_won"] == 1),
                (row["team2_name"], row["venue"], row["team1_won"] == 0),
            ]:
                key = (team, venue)
                w, p = venue_stats.get(key, (0, 0))
                venue_stats[key] = (w + int(won), p + 1)
        self.venue_stats = venue_stats

        # head-to-head across all history
        h2h = {}
        for _, row in df[df["is_decisive"]].iterrows():
            t1, t2 = row["team1_name"], row["team2_name"]
            key = tuple(sorted([t1, t2]))
            w, p = h2h.get(key, (0, 0))
            t1_won = row["team1_won"] == 1
            win_for_key0 = (key[0] == t1 and t1_won) or (key[0] == t2 and not t1_won)
            h2h[key] = (w + int(win_for_key0), p + 1)
        self.h2h_stats = h2h

    def venue_winrate(self, team, venue):
        w, p = self.venue_stats.get((team, venue), (0, 0))
        return w / p if p > 0 else 0.5

    def h2h_winrate(self, team_a, team_b):
        key = tuple(sorted([team_a, team_b]))
        w, p = self.h2h_stats.get(key, (0, 0))
        if p == 0:
            return 0.5
        wr = w / p
        return wr if key[0] == team_a else 1 - wr

    def predict(self, team1, team2, venue=None, toss_winner=None, toss_decision="bat"):
        """
        Returns dict with win probabilities for team1 and team2.
        venue: venue name string (optional -- uses neutral 0.5 if unknown/omitted)
        toss_winner: 'team1' or 'team2' (optional)
        toss_decision: 'bat' or 'field'
        """
        elo1 = self.current_elo.get(team1, 1500)
        elo2 = self.current_elo.get(team2, 1500)
        form1 = self.current_form.get(team1, 0.5)
        form2 = self.current_form.get(team2, 0.5)
        mom1 = self.current_momentum.get(team1, 0.0)
        mom2 = self.current_momentum.get(team2, 0.0)
        exp1 = self.current_experience.get(team1, 0)
        exp2 = self.current_experience.get(team2, 0)

        venue_wr1 = self.venue_winrate(team1, venue) if venue else 0.5
        venue_wr2 = self.venue_winrate(team2, venue) if venue else 0.5
        h2h_wr1 = self.h2h_winrate(team1, team2)

        toss_won_by_team1 = 1 if toss_winner == "team1" else 0
        toss_decision_bat = 1 if toss_decision == "bat" else 0

        feats = pd.DataFrame([{
            "elo_diff": elo1 - elo2,
            "form_diff": form1 - form2,
            "momentum_diff": mom1 - mom2,
            "experience_diff": exp1 - exp2,
            "team1_venue_winrate": venue_wr1,
            "team2_venue_winrate": venue_wr2,
            "h2h_team1_winrate": h2h_wr1,
            "toss_won_by_team1": toss_won_by_team1,
            "toss_decision_bat": toss_decision_bat,
        }])[FEATURE_COLS]

        proba_team1 = self.model.predict_proba(feats)[0, 1]

        return {
            "team1": team1, "team2": team2,
            "team1_win_probability": round(float(proba_team1) * 100, 1),
            "team2_win_probability": round(float(1 - proba_team1) * 100, 1),
            "team1_current_elo": round(elo1, 1),
            "team2_current_elo": round(elo2, 1),
            "head_to_head_team1_winrate": round(h2h_wr1 * 100, 1),
        }


if __name__ == "__main__":
    sim = MatchSimulator()
    matchups = [
        ("Mumbai Indians", "Chennai Super Kings", "Wankhede Stadium"),
        ("Royal Challengers Bangalore", "Gujarat Titans", None),
        ("Kolkata Knight Riders", "Sunrisers Hyderabad", None),
    ]
    for t1, t2, venue in matchups:
        result = sim.predict(t1, t2, venue=venue, toss_winner="team1", toss_decision="bat")
        print(result)
