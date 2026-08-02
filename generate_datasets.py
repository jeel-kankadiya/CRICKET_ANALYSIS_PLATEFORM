"""
generate_datasets.py
---------------------
Generates 5 new realistic CSV datasets for the Cricket Intelligence Platform.
Uses only Python stdlib so it works even without pandas/numpy installed.

Run from the project root:
    python generate_datasets.py
"""

import csv
import random
import os
import math
from collections import defaultdict

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# ─────────────────────────────────────────────
# Reference data parsed from existing CSVs
# ─────────────────────────────────────────────

def read_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_csv_raw(filename):
    path = os.path.join(DATA_DIR, filename)
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(filename, fieldnames, rows):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ Wrote {len(rows):,} rows → data/{filename}")


# ─────────────────────────────────────────────
# Load reference data
# ─────────────────────────────────────────────

print("Loading reference data...")
allround_rows = read_csv("ipl_allround.csv")
match_rows    = read_csv("ipl_matches_data.csv")
team_rows     = read_csv("teams_data.csv")
player_rows   = read_csv("players_data_updated.csv")

ALL_PLAYERS = [r["PlayerName"] for r in allround_rows]
TEAM_ID_MAP = {r["team_id"]: r["team_name"] for r in team_rows}
CURRENT_TEAMS = [
    "Mumbai Indians", "Chennai Super Kings", "Royal Challengers Bangalore",
    "Kolkata Knight Riders", "Delhi Capitals", "Punjab Kings",
    "Rajasthan Royals", "Sunrisers Hyderabad", "Gujarat Titans",
    "Lucknow Super Giants",
]
SEASONS = [
    "2008","2009","2010","2011","2012","2013","2014","2015","2016",
    "2017","2018","2019","2020/21","2021","2022","2023","2024","2025","2026"
]

TEAM_BY_SEASON = {
    "2008": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Deccan Chargers"],
    "2009": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Deccan Chargers"],
    "2010": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Deccan Chargers"],
    "2011": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Deccan Chargers","Kochi Tuskers Kerala","Pune Warriors"],
    "2012": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Deccan Chargers","Pune Warriors"],
    "2013": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Pune Warriors"],
    "2014": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad"],
    "2015": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad"],
    "2016": ["Mumbai Indians","Rising Pune Supergiant","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Gujarat Lions","Sunrisers Hyderabad"],
    "2017": ["Mumbai Indians","Rising Pune Supergiant","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Gujarat Lions","Sunrisers Hyderabad"],
    "2018": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad"],
    "2019": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad"],
    "2020/21": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
                "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
                "Rajasthan Royals","Sunrisers Hyderabad"],
    "2021": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad"],
    "2022": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Gujarat Titans","Lucknow Super Giants"],
    "2023": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Gujarat Titans","Lucknow Super Giants"],
    "2024": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Gujarat Titans","Lucknow Super Giants"],
    "2025": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Gujarat Titans","Lucknow Super Giants"],
    "2026": ["Mumbai Indians","Chennai Super Kings","Royal Challengers Bangalore",
             "Kolkata Knight Riders","Delhi Capitals","Punjab Kings",
             "Rajasthan Royals","Sunrisers Hyderabad","Gujarat Titans","Lucknow Super Giants"],
}

# Build player→role map from allround stats
PLAYER_ROLE = {}
for r in allround_rows:
    name = r["PlayerName"]
    runs  = float(r["Runs"]) if r["Runs"] and r["Runs"] != "-" else 0
    wkts  = float(r["Wickets"]) if r["Wickets"] and r["Wickets"] != "-" else 0
    if wkts >= 30 and runs < 500:
        PLAYER_ROLE[name] = "Bowler"
    elif runs >= 1000 and wkts < 20:
        PLAYER_ROLE[name] = "Batter"
    elif runs >= 500 and wkts >= 20:
        PLAYER_ROLE[name] = "All-rounder"
    else:
        PLAYER_ROLE[name] = random.choice(["Batter","Bowler","All-rounder","Wicketkeeper"])

# Build player span info
PLAYER_SPAN = {}
for r in allround_rows:
    span = r["Span"]
    name = r["PlayerName"]
    try:
        start_yr = int(span.split("-")[0])
        end_yr   = int(span.split("-")[1])
    except Exception:
        start_yr, end_yr = 2008, 2024
    PLAYER_SPAN[name] = (start_yr, end_yr)

# Build player→team map from allround (first team in list)
PLAYER_TEAM = {}
for r in allround_rows:
    teams_str = r["Teams"].strip('"').strip()
    first_team = teams_str.split(",")[0].strip()
    PLAYER_TEAM[r["PlayerName"]] = first_team

# Unique venues from match data (cleaned)
venue_set = set()
for r in match_rows:
    v = r.get("venue","").strip().strip('"')
    if v:
        venue_set.add(v)
VENUES = sorted(venue_set)

# Build match_id→winner map from match data
MATCH_WINNER = {}
for r in match_rows:
    mid = r.get("match_id","")
    winner_id = r.get("match_winner","")
    season    = r.get("season","")
    MATCH_WINNER[mid] = {
        "winner_id": winner_id,
        "season": season,
        "t1": r.get("team1",""),
        "t2": r.get("team2",""),
        "result": r.get("result",""),
    }


# ─────────────────────────────────────────────
# 1.  IPL Auction Data
# ─────────────────────────────────────────────

print("\n[1/5] Generating ipl_auction_data.csv ...")

BASE_PRICES = [20, 30, 40, 50, 75, 100, 150, 200]  # in lakhs

auction_rows = []
# Auction happens before each season (from 2009 for retention/auction cycles)
auction_seasons = [s for s in SEASONS if s != "2008"]

for season in auction_seasons:
    teams_this_season = TEAM_BY_SEASON.get(season, CURRENT_TEAMS)
    n_teams = len(teams_this_season)
    # Each team nominally buys ~12-14 players per season in auction
    # We simulate ~70-90 auction lots per season
    lots_per_season = random.randint(70, 100)
    players_pool = random.sample(ALL_PLAYERS, min(lots_per_season, len(ALL_PLAYERS)))

    for player in players_pool:
        base = random.choice(BASE_PRICES)
        role = PLAYER_ROLE.get(player, "Batter")
        team = random.choice(teams_this_season)

        # Stars command higher prices
        sold = random.random() < 0.75
        if sold:
            multiplier = random.uniform(1.0, 8.0)
            if role == "All-rounder":
                multiplier *= 1.3
            sold_price = round(base * multiplier / 5) * 5   # round to 5
            sold_price = max(base, sold_price)
        else:
            sold_price = None
            team = None

        auction_rows.append({
            "season":          season,
            "player_name":     player,
            "role":            role,
            "base_price_lakhs": base,
            "sold":            "Yes" if sold else "No",
            "sold_price_lakhs": sold_price if sold_price is not None else "",
            "team_name":       team if team else "",
        })

write_csv("ipl_auction_data.csv",
          ["season","player_name","role","base_price_lakhs","sold","sold_price_lakhs","team_name"],
          auction_rows)


# ─────────────────────────────────────────────
# 2.  Player Season Stats
# ─────────────────────────────────────────────

print("\n[2/5] Generating player_season_stats.csv ...")

season_stats_rows = []

for r in allround_rows:
    name = r["PlayerName"]
    span = r["Span"]
    teams_str = r["Teams"].strip('"').strip()
    team_list = [t.strip() for t in teams_str.split(",")]

    try:
        start_yr = int(span.split("-")[0])
        end_yr   = int(span.split("-")[1])
    except Exception:
        start_yr, end_yr = 2008, 2024

    # Career totals to derive per-season averages
    try:
        total_matches = int(r["Matches"]) if r["Matches"] else 0
        total_innings = int(r["Innings"]) if r["Innings"] and r["Innings"] != "-" else 0
        total_runs    = float(r["Runs"]) if r["Runs"] and r["Runs"] != "-" else 0
        bat_avg       = float(r["BattingAverage"]) if r["BattingAverage"] and r["BattingAverage"] not in ["-",""] else 20
        strike_rate   = float(r["StrikeRate"]) if r["StrikeRate"] and r["StrikeRate"] not in ["-",""] else 120
        total_wkts    = float(r["Wickets"]) if r["Wickets"] and r["Wickets"] not in ["-",""] else 0
        economy       = float(r["Economy"]) if r["Economy"] and r["Economy"] not in ["-",""] else 8.5
        bowl_avg      = float(r["BowlingAverage"]) if r["BowlingAverage"] and r["BowlingAverage"] not in ["-",""] else 30
        fours         = int(r["Fours"]) if r["Fours"] and r["Fours"] not in ["-",""] else 0
        sixes         = int(r["Sixes"]) if r["Sixes"] and r["Sixes"] not in ["-",""] else 0
    except Exception:
        total_matches = 10; total_runs = 200; bat_avg = 20; strike_rate = 120
        total_wkts = 5; economy = 8.5; bowl_avg = 30; fours = 10; sixes = 5
        total_innings = 10

    # Map season strings to years for span filtering
    def season_year(s):
        return int(s.split("/")[0].split("-")[0])

    active_seasons = [s for s in SEASONS if start_yr <= season_year(s) <= end_yr]
    if not active_seasons:
        active_seasons = [SEASONS[-1]]

    n_seasons = len(active_seasons)
    for i, season in enumerate(active_seasons):
        team_idx = min(i, len(team_list) - 1)
        team = team_list[team_idx]

        # Jitter career averages per season
        jitter = random.uniform(0.7, 1.3)
        s_matches = max(1, round((total_matches / n_seasons) * random.uniform(0.5, 1.5)))
        s_matches = min(s_matches, 16)
        s_innings = min(s_matches, max(1, round(s_matches * (total_innings / max(total_matches, 1)))))
        s_runs    = round(total_runs / n_seasons * random.uniform(0.4, 1.6))
        s_bat_avg = round(bat_avg * random.uniform(0.6, 1.4), 2)
        s_sr      = round(strike_rate * random.uniform(0.85, 1.15), 2)
        s_wkts    = round(total_wkts / n_seasons * random.uniform(0.3, 1.7))
        s_econ    = round(economy * random.uniform(0.9, 1.1), 2)
        s_bavg    = round(bowl_avg * random.uniform(0.8, 1.2), 2)
        s_fours   = round(fours / n_seasons * random.uniform(0.5, 1.5))
        s_sixes   = round(sixes / n_seasons * random.uniform(0.5, 1.5))
        s_fifties = max(0, round(s_runs / 50 * random.uniform(0, 0.8)))
        s_hundreds= 1 if s_runs >= 100 and random.random() < 0.1 else 0

        season_stats_rows.append({
            "season":          season,
            "player_name":     name,
            "team_name":       team,
            "matches":         s_matches,
            "innings":         s_innings,
            "runs":            max(0, s_runs),
            "batting_avg":     max(0, s_bat_avg),
            "strike_rate":     max(0, s_sr),
            "fours":           max(0, s_fours),
            "sixes":           max(0, s_sixes),
            "fifties":         s_fifties,
            "hundreds":        s_hundreds,
            "wickets":         max(0, s_wkts),
            "economy":         max(0, s_econ),
            "bowling_avg":     max(0, s_bavg),
        })

write_csv("player_season_stats.csv",
          ["season","player_name","team_name","matches","innings","runs",
           "batting_avg","strike_rate","fours","sixes","fifties","hundreds",
           "wickets","economy","bowling_avg"],
          season_stats_rows)


# ─────────────────────────────────────────────
# 3.  Venue Details
# ─────────────────────────────────────────────

print("\n[3/5] Generating venue_details.csv ...")

PITCH_TYPES = ["Batting Paradise", "Balanced", "Spin Friendly", "Seam Friendly", "Slow & Low"]
CITY_MAP = {
    "M Chinnaswamy Stadium":           ("Bangalore", 35000),
    "MA Chidambaram Stadium":          ("Chennai", 38000),
    "Eden Gardens":                    ("Kolkata", 66000),
    "Wankhede Stadium":                ("Mumbai", 33000),
    "Narendra Modi Stadium":           ("Ahmedabad", 132000),
    "Arun Jaitley Stadium":            ("Delhi", 41842),
    "Sawai Mansingh Stadium":          ("Jaipur", 30000),
    "Rajiv Gandhi International Stadium": ("Hyderabad", 55000),
    "Punjab Cricket Association IS Bindra Stadium": ("Mohali", 26950),
    "Brabourne Stadium":               ("Mumbai", 20000),
    "Dr DY Patil Sports Academy":      ("Navi Mumbai", 55000),
    "Maharashtra Cricket Association Stadium": ("Pune", 37406),
    "Barsapara Cricket Stadium":       ("Guwahati", 40000),
    "Himachal Pradesh Cricket Association Stadium": ("Dharamsala", 23000),
    "Vidarbha Cricket Association Stadium": ("Nagpur", 45000),
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium": ("Visakhapatnam", 27000),
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium": ("Lucknow", 50000),
    "Maharaja Yadavindra Singh International Cricket Stadium": ("Mullanpur", 35000),
    "Sardar Patel Stadium":            ("Ahmedabad", 54000),
    "Dubai International Cricket Stadium": ("Dubai", 25000),
    "Zayed Cricket Stadium":           ("Abu Dhabi", 20000),
}

# Count bat-first wins per venue from match data
venue_match_counts = defaultdict(int)
venue_batfirst_wins = defaultdict(int)
for r in match_rows:
    v = r.get("venue","").strip().strip('"')
    if not v or r.get("result","") != "win":
        continue
    venue_match_counts[v] += 1
    toss_dec = r.get("toss_decision","").strip()
    toss_win = r.get("toss_winner","").strip()
    match_win = r.get("match_winner","").strip()
    if toss_dec == "bat" and toss_win == match_win:
        venue_batfirst_wins[v] += 1
    elif toss_dec == "field" and toss_win != match_win:
        venue_batfirst_wins[v] += 1

venue_rows = []
for venue in VENUES:
    city, capacity = CITY_MAP.get(venue, ("India", random.randint(15000, 50000)))
    pitch = random.choice(PITCH_TYPES)
    dew_factor = round(random.uniform(0.1, 0.9), 2)  # 0=no dew, 1=heavy dew
    boundary_m = random.randint(60, 76)
    total = venue_match_counts.get(venue, random.randint(5, 30))
    bf_wins = venue_batfirst_wins.get(venue, round(total * random.uniform(0.35, 0.65)))
    avg_first_innings = random.randint(140, 195)
    bat_first_win_pct = round(100 * bf_wins / total, 1) if total > 0 else 50.0
    venue_rows.append({
        "venue":                 venue,
        "city":                  city,
        "capacity":              capacity,
        "pitch_type":            pitch,
        "avg_first_innings_score": avg_first_innings,
        "bat_first_win_pct":     bat_first_win_pct,
        "dew_factor":            dew_factor,
        "boundary_size_m":       boundary_m,
        "total_matches_hosted":  total,
    })

write_csv("venue_details.csv",
          ["venue","city","capacity","pitch_type","avg_first_innings_score",
           "bat_first_win_pct","dew_factor","boundary_size_m","total_matches_hosted"],
          venue_rows)


# ─────────────────────────────────────────────
# 4.  IPL Points Table
# ─────────────────────────────────────────────

print("\n[4/5] Generating ipl_points_table.csv ...")

# Compute real win/loss counts from match data per season per team
season_team_wins = defaultdict(lambda: defaultdict(int))
season_team_played = defaultdict(lambda: defaultdict(int))
season_team_losses = defaultdict(lambda: defaultdict(int))
season_team_nr = defaultdict(lambda: defaultdict(int))

for r in match_rows:
    season = r.get("season","")
    t1_id  = r.get("team1","")
    t2_id  = r.get("team2","")
    winner = r.get("match_winner","")
    result = r.get("result","")

    t1 = TEAM_ID_MAP.get(t1_id, "")
    t2 = TEAM_ID_MAP.get(t2_id, "")
    if not t1 or not t2:
        continue

    if result == "win":
        winner_name = TEAM_ID_MAP.get(winner, "")
        loser_name  = t2 if winner_name == t1 else t1
        season_team_wins[season][winner_name]   += 1
        season_team_losses[season][loser_name]  += 1
        season_team_played[season][t1] += 1
        season_team_played[season][t2] += 1
    elif result in ("no result","tie"):
        season_team_nr[season][t1] += 1
        season_team_nr[season][t2] += 1
        season_team_played[season][t1] += 1
        season_team_played[season][t2] += 1

IPL_CHAMPIONS = {
    "2008": "Rajasthan Royals", "2009": "Deccan Chargers",
    "2010": "Chennai Super Kings", "2011": "Chennai Super Kings",
    "2012": "Kolkata Knight Riders", "2013": "Mumbai Indians",
    "2014": "Kolkata Knight Riders", "2015": "Mumbai Indians",
    "2016": "Sunrisers Hyderabad", "2017": "Mumbai Indians",
    "2018": "Chennai Super Kings", "2019": "Mumbai Indians",
    "2020/21": "Mumbai Indians", "2021": "Chennai Super Kings",
    "2022": "Gujarat Titans", "2023": "Chennai Super Kings",
    "2024": "Kolkata Knight Riders", "2025": "Royal Challengers Bangalore"
}

points_rows = []
for season in SEASONS:
    teams = TEAM_BY_SEASON.get(season, CURRENT_TEAMS)
    champion = IPL_CHAMPIONS.get(season, teams[0])
    for i, team in enumerate(teams):
        w  = season_team_wins[season].get(team, 0)
        l  = season_team_losses[season].get(team, 0)
        nr = season_team_nr[season].get(team, 0)
        mp = season_team_played[season].get(team, w + l + nr)
        if mp == 0:
            # Simulate data for teams not well represented
            mp = 14
            w  = random.randint(3, 12)
            l  = mp - w
            nr = 0

        pts = w * 2 + nr
        nrr = round(random.uniform(-1.5, 1.5), 3)
        # Top 4 teams qualify for playoffs
        all_pts = sorted([random.randint(6, 20) for _ in teams], reverse=True)
        qualified = 1 if i < 4 else 0
        # Champion always qualifies
        if team == champion:
            qualified = 1

        points_rows.append({
            "season":         season,
            "team_name":      team,
            "matches_played": mp,
            "wins":           w,
            "losses":         l,
            "no_result":      nr,
            "points":         pts,
            "nrr":            nrr,
            "qualified":      qualified,
            "champion":       1 if team == champion else 0,
        })

write_csv("ipl_points_table.csv",
          ["season","team_name","matches_played","wins","losses","no_result","points","nrr","qualified","champion"],
          points_rows)


# ─────────────────────────────────────────────
# 5.  Player Availability
# ─────────────────────────────────────────────

print("\n[5/5] Generating player_availability.csv ...")

INJURY_REASONS = [
    "Hamstring strain", "Back spasm", "Shoulder injury", "Fever",
    "Personal reasons", "Knee injury", "Finger fracture", "Quad strain",
    "Travel delay", "Suspension", "Covid protocol", "Calf injury", "Fit",
]

availability_rows = []
# Sample top ~50 players per season to keep file manageable
def _safe_float(val):
    try:
        return float(val) if val and val != "-" else 0.0
    except (ValueError, TypeError):
        return 0.0

TOP_PLAYERS_BY_ROLE = sorted(ALL_PLAYERS, key=lambda p: (
    _safe_float([r["Runs"] for r in allround_rows if r["PlayerName"]==p][0])
    + _safe_float([r["Wickets"] for r in allround_rows if r["PlayerName"]==p][0]) * 20
    if any(r["PlayerName"]==p for r in allround_rows) else 0
), reverse=True)[:150]

for r in match_rows[:500]:  # first 500 matches to keep file size reasonable
    mid     = r.get("match_id","")
    season  = r.get("season","")
    t1_id   = r.get("team1","")
    t2_id   = r.get("team2","")
    t1 = TEAM_ID_MAP.get(t1_id, t1_id)
    t2 = TEAM_ID_MAP.get(t2_id, t2_id)

    # ~20 players per match (11 playing + squad), ~5% chance of absence
    squad = random.sample(TOP_PLAYERS_BY_ROLE, min(20, len(TOP_PLAYERS_BY_ROLE)))
    for player in squad:
        available = random.random() > 0.05
        reason = "Fit" if available else random.choice(INJURY_REASONS[:-1])
        team = random.choice([t1, t2])
        availability_rows.append({
            "match_id":    mid,
            "season":      season,
            "player_name": player,
            "team_name":   team,
            "available":   "Yes" if available else "No",
            "reason":      reason,
        })

write_csv("player_availability.csv",
          ["match_id","season","player_name","team_name","available","reason"],
          availability_rows)

print(f"\n{'='*55}")
print("All 5 datasets generated successfully in data/")
print("="*55)
