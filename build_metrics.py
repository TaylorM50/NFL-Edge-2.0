#!/usr/bin/env python3
"""Build NFL Edge team/player metrics from nflverse play-by-play CSV.
Only uses observed data fields. Unavailable charting metrics are not imputed.
"""
import csv, gzip, io, json, os, sys, urllib.request
from datetime import datetime, timezone
from collections import defaultdict

YEAR=int(os.getenv('NFL_SEASON', datetime.now(timezone.utc).year))
URL=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{YEAR}.csv.gz'
OUT='data/data.json'

def num(row, key):
    try:
        v=row.get(key,'')
        if v in ('',None,'NA','NaN','nan'): return None
        return float(v)
    except (ValueError,TypeError): return None

def truth(v): return str(v).strip().lower() in ('1','true','t','yes')

def main():
    print('Downloading',URL,flush=True)
    req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Edge-Analytics/1.0'})
    with urllib.request.urlopen(req,timeout=120) as resp: raw=resp.read()
    if raw[:2]==b'\x1f\x8b': raw=gzip.decompress(raw)
    text=io.TextIOWrapper(io.BytesIO(raw),encoding='utf-8',newline='')
    reader=csv.DictReader(text)
    teams=defaultdict(lambda:defaultdict(float)); players=defaultdict(lambda:defaultdict(float))
    weeks=[]; games=set(); row_count=0
    required={'posteam','defteam','epa','season','week'}
    if not required.issubset(set(reader.fieldnames or [])):
        raise RuntimeError('Unexpected play-by-play schema: required fields missing')
    for r in reader:
        row_count+=1
        season=num(r,'season'); week=num(r,'week')
        if season is not None and int(season)!=YEAR: continue
        if str(r.get('season_type','REG')).upper() not in ('REG','POST'): continue
        if week is not None: weeks.append(int(week))
        if r.get('game_id'): games.add(r['game_id'])
        off=(r.get('posteam') or '').strip(); deff=(r.get('defteam') or '').strip()
        epa=num(r,'epa'); play_type=(r.get('play_type') or '').lower()
        if epa is None or not off or not deff or truth(r.get('no_play','0')): continue
        # Count ordinary offensive scrimmage plays; exclude kickoffs, punts, field goals.
        if play_type not in ('pass','run'): continue
        yds=num(r,'yards_gained') or 0
        is_pass=play_type=='pass'; explosive=yds >= (20 if is_pass else 10)
        for key,val in [('plays',1),('epa_sum',epa),('success',1 if epa>0 else 0),('explosive',1 if explosive else 0)]:
            teams[off][key]+=val
        teams[off]['off_pass_plays']+=1 if is_pass else 0
        teams[deff]['def_plays']+=1; teams[deff]['def_epa_sum']+=epa
        teams[deff]['def_success_allowed']+=1 if epa>0 else 0
        # Player attribution: use official play-by-play player names and IDs where present.
        passer=(r.get('passer_player_name') or '').strip(); passer_id=(r.get('passer_player_id') or '').strip()
        rusher=(r.get('rusher_player_name') or '').strip(); rusher_id=(r.get('rusher_player_id') or '').strip()
        receiver=(r.get('receiver_player_name') or '').strip(); receiver_id=(r.get('receiver_player_id') or '').strip()
        if is_pass and passer and passer_id and not truth(r.get('sack','0')):
            p=players[passer_id];p['name']=passer;p['team']=off;p['position']='QB';p['pass_plays']+=1;p['epa_total']+=epa
            p['pass_yds']+=num(r,'passing_yards') or 0;p['pass_td']+=1 if truth(r.get('pass_touchdown','0')) else 0
        if play_type=='run' and rusher and rusher_id:
            p=players[rusher_id];p['name']=rusher;p['team']=off;p.setdefault('position','RB');p['rush_yds']+=num(r,'rushing_yards') or yds;p['rush_td']+=1 if truth(r.get('rush_touchdown','0')) else 0;p['epa_total']+=epa;p['rush_plays']+=1
        if is_pass and receiver and receiver_id and not truth(r.get('sack','0')) and not truth(r.get('interception','0')):
            p=players[receiver_id];p['name']=receiver;p['team']=off;p.setdefault('position','WR/TE');p['rec_yds']+=num(r,'receiving_yards') or 0;p['rec_td']+=1 if truth(r.get('pass_touchdown','0')) else 0;p['rec_targets']+=1
    output=[]
    for abbr,s in teams.items():
        plays=s['plays']; dp=s['def_plays']
        if plays<1: continue
        output.append({'team':abbr,'name':abbr,'off_epa':s['epa_sum']/plays,'def_epa':s['def_epa_sum']/dp if dp else None,'success_rate':s['success']/plays,'def_success_rate':s['def_success_allowed']/dp if dp else None,'explosive_rate':s['explosive']/plays,'plays':int(plays),'def_plays':int(dp)})
    output.sort(key=lambda x:x['off_epa'],reverse=True)
    plist=[]
    for pid,p in players.items():
        plist.append({'player_id':pid,'name':p.get('name','Unknown'),'team':p.get('team','—'),'position':p.get('position','—'),'pass_yds':p.get('pass_yds',0),'pass_td':p.get('pass_td',0),'rush_yds':p.get('rush_yds',0),'rush_td':p.get('rush_td',0),'rec_yds':p.get('rec_yds',0),'rec_td':p.get('rec_td',0),'epa_total':p.get('epa_total',0),'pass_plays':p.get('pass_plays',0),'rush_plays':p.get('rush_plays',0),'rec_targets':p.get('rec_targets',0)})
    plist.sort(key=lambda p:p['pass_yds']+p['rush_yds']+p['rec_yds'],reverse=True)
    if not output: raise RuntimeError('No team metrics produced; refusing to overwrite published data')
    payload={'season':YEAR,'generated_at':datetime.now(timezone.utc).isoformat(),'source':'nflverse/nflfastR play-by-play','source_url':URL,'rows_read':row_count,'games':len(games),'latest_week':max(weeks) if weeks else None,'metric_notes':{'off_epa':'Mean nflfastR EPA on run/pass plays by offense','def_epa':'Mean opponent EPA on run/pass plays against defense; lower is better','success_rate':'Share of eligible run/pass plays with EPA > 0','explosive_rate':'Share of run plays gaining >=10 yards or pass plays gaining >=20 yards','risk_worthy_throws':'Not calculated: requires validated charting labels not reliably present in basic play-by-play'} ,'teams':output,'players':plist}
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT+'.tmp','w',encoding='utf-8') as f: json.dump(payload,f,separators=(',',':'))
    os.replace(OUT+'.tmp',OUT)
    print(f"Wrote {OUT}: {len(output)} teams, {len(plist)} players, {len(games)} games; week {payload['latest_week']}",flush=True)
if __name__=='__main__': main()
