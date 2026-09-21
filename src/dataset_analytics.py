"""
dataset_analytics.py
---------------------
PURPOSE:
    Computes domain-specific analytics from the 5 supplementary IPL datasets:
    1. Auction trends (most expensive buys, average spend by role, season trends)
    2. Venue intelligence (pitch characteristics, bat-first vs chase win rates)
    3. Points table history (season champions, playoff qualification rates, close races)
    4. Player season trends (top run scorers, top wicket-takers, career trajectories)
    5. Player availability (absences by reason, team injury rates)

All functions return serialization-ready Python dicts/lists for JSON output.
"""

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
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────

def _safe(val):
    """
    Converts NumPy scalars and NaN/None values into native JSON-safe Python types.

    Parameters:
        val: Any scalar value (int, float, np.int64, np.nan, etc.)

    Returns:
        Native int, float, or None suitable for json.dump().
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def _clean_records(df: pd.DataFrame, cols: list) -> list:
    """
    Converts selected columns of a DataFrame into a list of JSON-safe dictionaries.

    Parameters:
        df (pd.DataFrame): Input DataFrame.
        cols (list): List of column names to extract.

    Returns:
        list: List of row dictionaries with clean primitive Python types.
    """
    records = []
    for row in df[cols].to_dict(orient="records"):
        records.append({k: _safe(v) for k, v in row.items()})
    return records


# ─────────────────────────────────────────────────────────
# 1. AUCTION ANALYTICS
# ─────────────────────────────────────────────────────────

def auction_analytics() -> dict:
    """
    Disabled auction market analytics.
    """
    return {}


# ─────────────────────────────────────────────────────────
# 2. VENUE INTELLIGENCE
# ─────────────────────────────────────────────────────────

def venue_intelligence() -> dict:
    """
    Analyzes stadium attributes and match pitch conditions.

    Calculates:
      - venue_profiles      : Comprehensive physical and statistical profile per ground.
      - pitch_type_summary  : Win % for batting first and avg scores by pitch surface (flat, green, dry, etc.).
      - top_batting_venues  : Grounds with highest average first-innings scores.
      - top_chasing_venues  : Grounds with lowest bat-first win rates (most favorable for chasing).

    Returns:
        dict: Four venue intelligence metrics.
    """
    df = load_venue_details()

    # All venues sorted by match hosting activity
    all_venues = df.sort_values("total_matches_hosted", ascending=False)
    venue_profiles = _clean_records(all_venues, [
        "venue", "city", "capacity", "pitch_type",
        "avg_first_innings_score", "bat_first_win_pct",
        "dew_factor", "boundary_size_m", "total_matches_hosted"
    ])

    # Performance breakdown by pitch type
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

    # Highest scoring grounds
    top_bat = df.nlargest(10, "avg_first_innings_score")
    top_batting_venues = _clean_records(top_bat, ["venue", "city", "avg_first_innings_score", "pitch_type"])

    # Grounds where chasing team wins most frequently
    top_chase = df.nsmallest(10, "bat_first_win_pct")
    top_chasing_venues = _clean_records(top_chase, ["venue", "city", "bat_first_win_pct", "dew_factor"])

    return {
        "venue_profiles":      venue_profiles,
        "pitch_type_summary":  pitch_type_summary,
        "top_batting_venues":  top_batting_venues,
        "top_chasing_venues":  top_chasing_venues,
    }


# ─────────────────────────────────────────────────────────
# 3. POINTS TABLE ANALYTICS
# ─────────────────────────────────────────────────────────

def points_table_analytics() -> dict:
    """
    Analyzes historical IPL league standings and playoff outcomes.

    Calculates:
      - full_points_table    : Complete season-by-season standings.
      - season_champions     : Champion team per season with tournament stats.
      - qualification_stats  : Playoff qualification rate (%) per franchise.
      - closest_title_races  : Seasons with smallest points gap between 1st and 2nd place.

    Returns:
        dict: Four standings metrics.
    """
    df = load_points_table()

    # Full table sorted by season and points
    full = df.sort_values(["season", "points"], ascending=[True, False])
    full_points_table = _clean_records(full, full.columns.tolist())

    # Filter champions per season
    champs = df[df["champion"] == 1].sort_values("season")
    season_champions = _clean_records(champs, [
        "season", "team_name", "matches_played", "wins", "losses", "points", "nrr"
    ])

    # Qualification rate calculation per team
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
    qual["qual_rate"] = (qual["times_qualified"] / qual["seasons_played"] * 100.0).round(1)
    qual_sorted = qual.sort_values("times_champion", ascending=False)
    qualification_stats = _clean_records(qual_sorted, qual_sorted.columns.tolist())

    # Closest title races: minimum gap between 1st and 2nd team points
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
# 4. PLAYER SEASON TRENDS
# ─────────────────────────────────────────────────────────

def player_season_trends() -> dict:
    """
    Analyzes seasonal player performances and multi-year career arcs.

    Calculates:
      - top_run_scorers_by_season   : Orange Cap contenders (top 5 batters per season).
      - top_wicket_takers_by_season : Purple Cap contenders (top 5 bowlers per season).
      - career_trajectories         : Season-by-season progression for top 20 all-time run scorers.
      - season_batting_leaders      : Top 10 batters per season for dashboard leaderboards.

    Returns:
        dict: Four seasonal trend records.
    """
    df = load_player_season_stats()

    # Top 5 run scorers per season
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

    # Top 5 wicket takers per season
    wkts_top = (
        df.sort_values("wickets", ascending=False)
          .groupby("season")
          .head(5)
          .reset_index(drop=True)
    )
    top_wicket_takers_by_season = _clean_records(
        wkts_top, ["season", "player_name", "team_name", "matches", "wickets", "economy", "bowling_avg"]
    )

    # Career trajectory for ALL players
    traj_df = df.sort_values(["player_name", "season"])
    career_trajectories = _clean_records(
        traj_df, ["season", "player_name", "team_name", "matches", "runs",
                  "batting_avg", "strike_rate", "wickets", "economy"]
    )

    # Top 10 batters per season
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
# 5. PLAYER AVAILABILITY ANALYTICS
# ─────────────────────────────────────────────────────────

def availability_analytics() -> dict:
    """
    Analyzes match-level player availability and injury impact.

    Calculates:
      - most_absent_players   : Players missing highest percentage of team matches.
      - absence_by_reason     : Breakdown of absences (Injury, National Duty, Personal, Rest).
      - team_absence_rate     : Average missing player records per match by franchise.
      - season_injury_trend   : Total missing player instances per season over time.

    Returns:
        dict: Four player availability metrics.
    """
    df = load_player_availability()
    absent = df[~df["is_available"]].copy()

    # Most absent players ranking
    absent_counts = absent.groupby("player_name").size().reset_index(name="absences")
    total_counts = df.groupby("player_name").size().reset_index(name="total_records")
    ab_rate = absent_counts.merge(total_counts, on="player_name")
    ab_rate["absence_pct"] = (ab_rate["absences"] / ab_rate["total_records"] * 100.0).round(1)
    ab_rate = ab_rate.sort_values("absences", ascending=False).head(20)
    most_absent_players = _clean_records(ab_rate, ["player_name", "absences", "absence_pct"])

    # Categorized breakdown of reasons for absence
    reason_counts = (
        absent[absent["reason"] != "Fit"]
              .groupby("reason").size()
              .reset_index(name="count")
              .sort_values("count", ascending=False)
    )
    absence_by_reason = _clean_records(reason_counts, ["reason", "count"])

    # Team absence frequency
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

    # Seasonal injury trend
    season_trend = absent.groupby("season").size().reset_index(name="total_absences")
    season_injury_trend = _clean_records(season_trend, ["season", "total_absences"])

    return {
        "most_absent_players":  most_absent_players,
        "absence_by_reason":    absence_by_reason,
        "team_absence_rate":    team_absence_rate,
        "season_injury_trend":  season_injury_trend,
    }


# ── 6. Player Stadium / Venue Analytics ────────────────────
def normalize_venue_name(v):
    if not v: return "Unknown Venue"
    v = v.strip()
    vl = v.lower()
    if 'chinnaswamy' in vl: return 'M Chinnaswamy Stadium (Bengaluru)'
    if 'wankhede' in vl: return 'Wankhede Stadium (Mumbai)'
    if 'eden gardens' in vl: return 'Eden Gardens (Kolkata)'
    if 'chidambaram' in vl or 'chepauk' in vl: return 'MA Chidambaram Stadium (Chennai)'
    if 'feroz shah' in vl or 'arun jaitley' in vl or 'kotla' in vl or ('delhi' in vl and 'stadium' in vl): return 'Arun Jaitley Stadium (Delhi)'
    if 'rajiv gandhi' in vl or 'uppal' in vl: return 'Rajiv Gandhi Intl Stadium (Hyderabad)'
    if 'bindra' in vl or 'mohali' in vl: return 'IS Bindra Stadium (Mohali)'
    if 'sawai mansingh' in vl or 'jaipur' in vl: return 'Sawai Mansingh Stadium (Jaipur)'
    if 'narendra modi' in vl or 'motera' in vl or 'sardar patel' in vl: return 'Narendra Modi Stadium (Ahmedabad)'
    if 'dy patil' in vl: return 'Dr DY Patil Sports Academy (Navi Mumbai)'
    if 'brabourne' in vl: return 'Brabourne Stadium (Mumbai)'
    if 'maharashtra cricket association' in vl or 'mca stadium' in vl or 'subrata roy' in vl or 'pune' in vl: return 'MCA Stadium (Pune)'
    if 'dubai' in vl: return 'Dubai International Stadium'
    if 'zayed' in vl or 'abu dhabi' in vl: return 'Zayed Cricket Stadium (Abu Dhabi)'
    if 'sharjah' in vl: return 'Sharjah Cricket Stadium'
    if 'ekana' in vl or 'lucknow' in vl: return 'Ekana Cricket Stadium (Lucknow)'
    if 'dharamsala' in vl or 'himachal' in vl: return 'HPCA Stadium (Dharamsala)'
    if 'barsapara' in vl or 'guwahati' in vl: return 'Barsapara Stadium (Guwahati)'
    if 'mullanpur' in vl or 'new chandigarh' in vl or 'yadavindra' in vl: return 'Maharaja Yadavindra Stadium (Mullanpur)'
    if 'holkar' in vl or 'indore' in vl: return 'Holkar Stadium (Indore)'
    if 'cuttack' in vl or 'barabati' in vl: return 'Barabati Stadium (Cuttack)'
    if 'visakhapatnam' in vl or 'aca-vdca' in vl: return 'ACA-VDCA Stadium (Visakhapatnam)'
    if 'ranchi' in vl or 'jsca' in vl: return 'JSCA Stadium (Ranchi)'
    if 'raipur' in vl or 'shaheed' in vl: return 'Shaheed Veer Narayan Stadium (Raipur)'
    return v

def player_venue_analytics():
    from collections import defaultdict
    import csv
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    match_venue = {}
    ipl_csv = os.path.join(DATA_DIR, 'ipl.csv')
    if os.path.exists(ipl_csv):
        with open(ipl_csv, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                match_venue[r['match_id']] = normalize_venue_name(r.get('venue'))

    matches_csv = os.path.join(DATA_DIR, 'ipl_matches_data.csv')
    if os.path.exists(matches_csv):
        with open(matches_csv, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r['match_id'] not in match_venue and r.get('city'):
                    match_venue[r['match_id']] = normalize_venue_name(r.get('city') + ' Stadium')

    p_v_match = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'runs': 0, 'balls': 0, 'outs': 0, 'fours': 0, 'sixes': 0})))
    p_v_bowl_match = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'runs': 0, 'balls': 0, 'wickets': 0})))

    bbb_csv = os.path.join(DATA_DIR, 'ball_by_ball_data.csv')
    if os.path.exists(bbb_csv):
        with open(bbb_csv, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                m_id = r['match_id']
                venue = match_venue.get(m_id, 'Other Venues')
                batter = r['batter']
                bowler = r.get('bowler')

                try: runs = int(r['batter_runs'])
                except: runs = 0

                m_bat = p_v_match[batter][venue][m_id]
                m_bat['runs'] += runs
                if r.get('is_wide_ball') != '1':
                    m_bat['balls'] += 1
                if runs == 4: m_bat['fours'] += 1
                elif runs == 6: m_bat['sixes'] += 1

                p_out = r.get('player_out', '').strip()
                if p_out == batter or (r.get('is_wicket') == '1' and p_out == batter):
                    m_bat['outs'] += 1

                if bowler:
                    m_bowl = p_v_bowl_match[bowler][venue][m_id]
                    if r.get('is_wide_ball') != '1' and r.get('is_no_ball') != '1':
                        m_bowl['balls'] += 1
                    noball_r = int(r.get('no_ball_runs', 0) or 0)
                    wide_r = int(r.get('wide_ball_runs', 0) or 0)
                    m_bowl['runs'] += (runs + noball_r + wide_r)
                    w_kind = r.get('wicket_kind', '')
                    if r.get('is_wicket') == '1' and w_kind not in ['run out', 'retired hurt', 'obstructing the field', 'hit double ball']:
                        m_bowl['wickets'] += 1

    player_venue_summary = {}
    all_players = set(p_v_match.keys()) | set(p_v_bowl_match.keys())

    for player in all_players:
        venues_stat = []
        v_dict = p_v_match[player]
        b_dict = p_v_bowl_match[player]
        all_v = set(v_dict.keys()) | set(b_dict.keys())

        for venue in all_v:
            matches_bat = v_dict[venue]
            bat_inn = len(matches_bat)
            total_runs = sum(m['runs'] for m in matches_bat.values())
            total_balls = sum(m['balls'] for m in matches_bat.values())
            total_outs = sum(m['outs'] for m in matches_bat.values())
            total_4s = sum(m['fours'] for m in matches_bat.values())
            total_6s = sum(m['sixes'] for m in matches_bat.values())

            hs = max((m['runs'] for m in matches_bat.values()), default=0)
            fifties = sum(1 for m in matches_bat.values() if 50 <= m['runs'] < 100)
            hundreds = sum(1 for m in matches_bat.values() if m['runs'] >= 100)

            avg = round(total_runs / total_outs, 1) if total_outs > 0 else (float(total_runs) if total_runs > 0 else 0.0)
            sr = round((total_runs / total_balls) * 100, 1) if total_balls > 0 else 0.0

            matches_bowl = b_dict[venue]
            bowl_inn = len(matches_bowl)
            b_runs = sum(m['runs'] for m in matches_bowl.values())
            b_balls = sum(m['balls'] for m in matches_bowl.values())
            b_wkts = sum(m['wickets'] for m in matches_bowl.values())
            b_econ = round(b_runs / (b_balls / 6.0), 2) if b_balls >= 6 else 0.0

            if total_runs > 0 or b_wkts > 0 or bat_inn > 0 or bowl_inn > 0:
                venues_stat.append({
                    'venue': venue,
                    'runs': total_runs,
                    'innings': bat_inn,
                    'balls': total_balls,
                    'avg': avg,
                    'sr': sr,
                    'hs': hs,
                    'fifties': fifties,
                    'hundreds': hundreds,
                    'fours': total_4s,
                    'sixes': total_6s,
                    'wickets': b_wkts,
                    'bowl_innings': bowl_inn,
                    'economy': b_econ
                })

        venues_stat.sort(key=lambda x: -x['runs'])
        player_venue_summary[player] = venues_stat

    return player_venue_summary


# ─────────────────────────────────────────────────────────
# 7. PLAYING XI DATA (Team Rosters + Player Roles)
# ─────────────────────────────────────────────────────────

# Recognised bowling style keywords that indicate a genuine bowler
_BOWL_STYLES = {
    'fast', 'medium', 'offbreak', 'orthodox', 'legbreak', 'chinaman',
    'wrist spin', 'leg break', 'left arm', 'right arm', 'slow',
}


def _is_bowling_style(style_str):
    """Return True if *style_str* looks like a genuine bowling type."""
    if not style_str or not isinstance(style_str, str):
        return False
    sl = style_str.strip().lower()
    if not sl or sl in ('', '-', 'null', 'none', 'nan'):
        return False
    return any(kw in sl for kw in _BOWL_STYLES)


def build_playing_xi_data() -> dict:
    """
    Build data required by the Best Playing XI generator feature.

    Returns dict with:
      - team_rosters : { team_name: [player_name, ...] }  — latest 3 seasons
      - player_roles : { player_name: 'Batsman'|'Bowler'|'Wicketkeeper'|'All-Rounder' }
      - venues_list  : [venue_name, ...]  — unique venues from player_venue_stats
    """
    import csv

    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

    # ── 1. Build team rosters from the latest 3 seasons ────────────────────
    pss_csv = os.path.join(DATA_DIR, "player_season_stats.csv")
    season_team_player = {}  # {season: {team: set(players)}}
    all_seasons = set()

    with open(pss_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            season_str = str(r.get("season", "")).strip()
            try:
                s = int(season_str.split("/")[0])
            except (ValueError, IndexError):
                continue
            all_seasons.add(s)
            team = r["team_name"]
            player = r["player_name"]
            season_team_player.setdefault(s, {}).setdefault(team, set()).add(player)

    # Use the latest 3 seasons to build rosters
    latest_seasons = sorted(all_seasons, reverse=True)[:3]
    team_rosters = {}
    for s in latest_seasons:
        for team, players in season_team_player.get(s, {}).items():
            team_rosters.setdefault(team, set()).update(players)

    # Convert sets to sorted lists
    team_rosters = {t: sorted(list(ps)) for t, ps in team_rosters.items()}

    # ── 2. Classify player roles ───────────────────────────────────────────
    # Load player metadata (field_pos, bowl_style)
    players_csv = os.path.join(DATA_DIR, "players_data_updated.csv")
    player_meta = {}  # {player_name: {field_pos, bowl_style}}
    with open(players_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            player_meta[r["player_name"]] = {
                "field_pos": (r.get("field_pos") or "").strip(),
                "bowl_style": (r.get("bowl_style") or "").strip(),
            }

    # Load career stats from ipl_allround.csv for innings counts
    allround_csv = os.path.join(DATA_DIR, "ipl_allround.csv")
    player_career = {}  # {player_name: {bat_inn, bowl_inn}}
    with open(allround_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["PlayerName"]
            try:
                bat_inn = int(r.get("Innings") or 0)
            except (ValueError, TypeError):
                bat_inn = 0
            try:
                bowl_inn = int(r.get("BowlInnings") or 0)
            except (ValueError, TypeError):
                bowl_inn = 0
            player_career[name] = {"bat_inn": bat_inn, "bowl_inn": bowl_inn}

    # Classify every player in the rosters
    player_roles = {}
    all_roster_players = set()
    for players in team_rosters.values():
        all_roster_players.update(players)

    for p in all_roster_players:
        meta = player_meta.get(p, {})
        career = player_career.get(p, {"bat_inn": 0, "bowl_inn": 0})
        fp = meta.get("field_pos", "").lower()
        bs = meta.get("bowl_style", "")

        # Wicketkeeper
        if "wicketkeeper" in fp:
            player_roles[p] = "Wicketkeeper"
        # All-Rounder: substantial contribution in both batting and bowling
        elif career["bat_inn"] >= 10 and career["bowl_inn"] >= 10:
            player_roles[p] = "All-Rounder"
        # Bowler: has a recognised bowling style and meaningful bowling innings
        elif _is_bowling_style(bs) and career["bowl_inn"] >= 5:
            player_roles[p] = "Bowler"
        # Default: Batsman
        else:
            player_roles[p] = "Batsman"

    # ── 3. Unique venues list ──────────────────────────────────────────────
    # Extracted from ball-by-ball via the same venue normalisation logic
    bbb_csv = os.path.join(DATA_DIR, "ball_by_ball_data.csv")
    ipl_csv = os.path.join(DATA_DIR, "ipl.csv")

    venue_set = set()
    # Pull venues from ipl.csv (match-level data)
    if os.path.exists(ipl_csv):
        with open(ipl_csv, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                v = normalize_venue_name(r.get("venue"))
                if v and v != "Unknown Venue":
                    venue_set.add(v)

    venues_list = sorted(venue_set)

    return {
        "team_rosters": team_rosters,
        "player_roles": player_roles,
        "venues_list": venues_list,
    }


# ─────────────────────────────────────────────────────────
# MAIN AGGREGATOR
# ─────────────────────────────────────────────────────────

def build_all_analytics() -> dict:
    return {
        "auction":      auction_analytics(),
        "venue_intel":  venue_intelligence(),
        "points_table": points_table_analytics(),
        "player_trends":player_season_trends(),
        "availability": availability_analytics(),
        "player_venue": player_venue_analytics(),
        "playing_xi":   build_playing_xi_data(),
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
