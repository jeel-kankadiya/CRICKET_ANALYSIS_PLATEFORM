"""
generate_new_dataset_bundle.py
-------------------------------
Pure stdlib — no pandas/numpy required.
Reads the 5 new CSVs and generates the analytics bundles,
then patches dashboard/index.html to append the new keys
to the existing DATA object.
"""
import csv, json, os, random, re, sys
from collections import defaultdict

DATA_DIR   = os.path.join(os.path.dirname(__file__), 'data')
DASH_HTML  = os.path.join(os.path.dirname(__file__), 'dashboard', 'index.html')

def read_csv(name):
    path = os.path.join(DATA_DIR, name)
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ── 1. Auction Analytics ──────────────────────────────────
def auction_analytics():
    rows = read_csv('ipl_auction_data.csv')
    sold = [r for r in rows if r.get('sold','').strip() == 'Yes']
    for r in sold:
        try: r['_price'] = float(r.get('sold_price_lakhs', 0) or 0)
        except: r['_price'] = 0.0

    # Top 20 all-time
    top20 = sorted(sold, key=lambda r: -r['_price'])[:20]
    most_expensive_ever = [
        {'season': r['season'], 'player_name': r['player_name'],
         'role': r['role'], 'team_name': r['team_name'],
         'sold_price_lakhs': r['_price']}
        for r in top20
    ]

    # Avg price by role
    role_groups = defaultdict(list)
    for r in sold:
        role_groups[r['role']].append(r['_price'])
    avg_price_by_role = []
    for role, prices in sorted(role_groups.items()):
        avg_price_by_role.append({
            'role': role,
            'avg_price': round(sum(prices)/len(prices), 1),
            'median_price': round(sorted(prices)[len(prices)//2], 1),
            'max_price': max(prices),
            'total_sold': len(prices),
        })

    # Season spend trend
    season_spend = defaultdict(list)
    for r in sold:
        season_spend[r['season']].append(r['_price'])
    season_spend_trend = [
        {'season': s, 'total_spend': round(sum(v), 0),
         'avg_spend': round(sum(v)/len(v), 1), 'lots_sold': len(v)}
        for s, v in sorted(season_spend.items())
    ]

    return {
        'most_expensive_ever': most_expensive_ever,
        'avg_price_by_role': avg_price_by_role,
        'season_spend_trend': season_spend_trend,
    }


# ── 2. Venue Intelligence ─────────────────────────────────
def venue_intelligence():
    rows = read_csv('venue_details.csv')
    for r in rows:
        for col in ['avg_first_innings_score', 'bat_first_win_pct', 'dew_factor',
                    'boundary_size_m', 'capacity', 'total_matches_hosted']:
            try: r[col] = float(r[col])
            except: r[col] = 0.0

    rows_sorted = sorted(rows, key=lambda r: -r['total_matches_hosted'])
    venue_profiles = [
        {k: v for k, v in r.items() if k not in ['_price']}
        for r in rows_sorted
    ]
    # Remove helper keys
    for vp in venue_profiles:
        vp['capacity'] = int(vp['capacity'])
        vp['total_matches_hosted'] = int(vp['total_matches_hosted'])
        vp['avg_first_innings_score'] = round(vp['avg_first_innings_score'], 1)
        vp['bat_first_win_pct'] = round(vp['bat_first_win_pct'], 1)
        vp['dew_factor'] = round(vp['dew_factor'], 2)
        vp['boundary_size_m'] = int(vp['boundary_size_m'])

    # Pitch type summary
    pitch_groups = defaultdict(list)
    for r in rows:
        pitch_groups[r['pitch_type']].append(r)
    pitch_type_summary = []
    for pt, venues in sorted(pitch_groups.items()):
        pitch_type_summary.append({
            'pitch_type': pt,
            'avg_bat_first_win_pct': round(sum(v['bat_first_win_pct'] for v in venues)/len(venues), 1),
            'avg_first_innings_score': round(sum(v['avg_first_innings_score'] for v in venues)/len(venues), 1),
            'avg_dew_factor': round(sum(v['dew_factor'] for v in venues)/len(venues), 2),
            'venues_count': len(venues),
        })

    return {
        'venue_profiles': venue_profiles,
        'pitch_type_summary': pitch_type_summary,
    }


# ── 3. Points Table Analytics ─────────────────────────────
def points_table_analytics():
    rows = read_csv('ipl_points_table.csv')
    for r in rows:
        for col in ['matches_played','wins','losses','no_result','points','qualified','champion']:
            try: r[col] = int(float(r[col]))
            except: r[col] = 0
        try: r['nrr'] = round(float(r['nrr']), 3)
        except: r['nrr'] = 0.0

    full_points_table = sorted(rows, key=lambda r: (str(r['season']), -r['points']))

    # Qualification stats per team
    team_stats = defaultdict(lambda: {'seasons_played':0,'times_qualified':0,'times_champion':0,'total_wins':0})
    for r in rows:
        t = r['team_name']
        team_stats[t]['seasons_played'] += 1
        team_stats[t]['times_qualified'] += r['qualified']
        team_stats[t]['times_champion']  += r['champion']
        team_stats[t]['total_wins']      += r['wins']
    qualification_stats = []
    for tn, s in team_stats.items():
        s['team_name'] = tn
        s['qual_rate'] = round(100*s['times_qualified']/s['seasons_played'], 1) if s['seasons_played'] else 0.0
        qualification_stats.append(s)
    qualification_stats.sort(key=lambda x: -x['times_champion'])

    return {
        'full_points_table': full_points_table,
        'qualification_stats': qualification_stats,
    }


# ── 4. Player Season Trends ───────────────────────────────
def player_season_trends():
    rows = read_csv('player_season_stats.csv')
    for r in rows:
        for col in ['matches','innings','runs','fours','sixes','wickets']:
            try: r[col] = int(float(r[col]))
            except: r[col] = 0
        for col in ['batting_avg','strike_rate','economy','bowling_avg']:
            try: r[col] = round(float(r[col]), 2)
            except: r[col] = 0.0

    # Include all player season trajectories
    career_trajectories = [
        {'season': r['season'], 'player_name': r['player_name'], 'team_name': r['team_name'],
         'matches': r['matches'], 'runs': r['runs'], 'batting_avg': r['batting_avg'],
         'strike_rate': r['strike_rate'], 'wickets': r['wickets'], 'economy': r['economy']}
        for r in rows
    ]

    # Batting leaders top 10 per season
    season_players = defaultdict(list)
    for r in rows:
        season_players[r['season']].append(r)
    season_batting_leaders = []
    for s, pl in sorted(season_players.items()):
        top10 = sorted(pl, key=lambda x: -x['runs'])[:10]
        for r in top10:
            season_batting_leaders.append({
                'season': s, 'player_name': r['player_name'], 'team_name': r['team_name'],
                'matches': r['matches'], 'runs': r['runs'],
                'batting_avg': r['batting_avg'], 'strike_rate': r['strike_rate'],
            })

    return {
        'career_trajectories': career_trajectories,
        'season_batting_leaders': season_batting_leaders,
    }


# ── 5. Player Availability ────────────────────────────────
def availability_analytics():
    rows = read_csv('player_availability.csv')
    for r in rows:
        r['is_available'] = r.get('is_available','').strip().lower() in ('true','yes','1')

    absent = [r for r in rows if not r['is_available']]

    # Most absent players
    absent_counts = defaultdict(int)
    total_counts  = defaultdict(int)
    for r in rows:
        total_counts[r['player_name']] += 1
    for r in absent:
        absent_counts[r['player_name']] += 1
    most_absent = sorted(absent_counts.items(), key=lambda x:-x[1])[:20]
    most_absent_players = [
        {'player_name': p, 'absences': c,
         'absence_pct': round(100*c/total_counts[p], 1)}
        for p, c in most_absent
    ]

    # Absence by reason
    reason_counts = defaultdict(int)
    for r in absent:
        if r.get('reason','').strip() not in ('Fit',''):
            reason_counts[r['reason']] += 1
    absence_by_reason = [
        {'reason': reason, 'count': count}
        for reason, count in sorted(reason_counts.items(), key=lambda x:-x[1])
    ]

    # Team absence rate
    team_matches  = defaultdict(set)
    team_absences = defaultdict(int)
    for r in rows:
        team_matches[r['team_name']].add(r['match_id'])
    for r in absent:
        team_absences[r['team_name']] += 1
    team_absence_rate = []
    for tn, matches in team_matches.items():
        mc = len(matches)
        ta = team_absences.get(tn, 0)
        team_absence_rate.append({
            'team_name': tn, 'match_count': mc, 'total_absences': ta,
            'absences_per_match': round(ta/mc, 2) if mc else 0.0,
        })
    team_absence_rate.sort(key=lambda x: -x['absences_per_match'])

    # Season trend
    season_counts = defaultdict(int)
    for r in absent:
        season_counts[r['season']] += 1
    season_injury_trend = [
        {'season': s, 'total_absences': c}
        for s, c in sorted(season_counts.items())
    ]

    return {
        'most_absent_players': most_absent_players,
        'absence_by_reason':   absence_by_reason,
        'team_absence_rate':   team_absence_rate,
        'season_injury_trend': season_injury_trend,
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


# ── Patch HTML ────────────────────────────────────────────
def patch_html(new_keys: dict):
    with open(DASH_HTML, encoding='utf-8') as f:
        html = f.read()

    pattern = r'(const DATA = )(\{.*?\})(\s*;)'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        print('ERROR: Could not find DATA = {...}; in HTML')
        sys.exit(1)

    prefix, data_json_str, suffix = match.group(1), match.group(2), match.group(3)
    data_obj = json.loads(data_json_str)

    # Remove old keys if present
    for k in ['auction_trends','venue_intelligence','points_table_history',
              'player_season_trends','availability_summary','player_venue_stats']:
        data_obj.pop(k, None)

    # Inject new keys
    data_obj['auction_trends']       = new_keys['auction']
    data_obj['venue_intelligence']   = new_keys['venue_intel']
    data_obj['points_table_history'] = new_keys['points_table']
    data_obj['player_season_trends'] = new_keys['player_trends']
    data_obj['availability_summary'] = new_keys['availability']
    data_obj['player_venue_stats']   = new_keys['player_venue']

    new_json_str = json.dumps(data_obj, separators=(',', ':'), default=str)
    new_data_block = prefix + new_json_str + suffix

    new_html = html[:match.start()] + new_data_block + html[match.end():]
    with open(DASH_HTML, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f'Patched {DASH_HTML}')
    print(f'  New DATA size: {len(new_json_str):,} bytes')

    # Also save to outputs/dashboard_data.json
    out_file = os.path.join(os.path.dirname(__file__), 'outputs', 'dashboard_data.json')
    if os.path.exists(os.path.dirname(out_file)):
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data_obj, f, default=str)
        print(f'Updated {out_file} with player_venue_stats ({len(new_keys["player_venue"])} players)')


if __name__ == '__main__':
    print('Generating new dataset analytics...')
    bundle = {
        'auction':      auction_analytics(),
        'venue_intel':  venue_intelligence(),
        'points_table': points_table_analytics(),
        'player_trends':player_season_trends(),
        'availability': availability_analytics(),
        'player_venue': player_venue_analytics(),
    }
    for k, v in bundle.items():
        keys_or_len = list(v.keys()) if isinstance(v, dict) else len(v)
        print(f'  {k}: {keys_or_len}')

    patch_html(bundle)
    print('Done!')

