"""Up to three global daily model plays, frozen prospectively and scored separately."""
import json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from . import store,picks
RULE='flashy-ai-v1'

def build(day,mode,path=None,at=None):
    at=at or store.now();moment=store.instant(at)
    if moment.astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=day:return None
    key=f'{mode}:{day}'
    with store.connect(path) as c:
        old=c.execute('SELECT payload FROM daily_plays WHERE play_key=?',(key,)).fetchone()
        if old:return json.loads(old['payload'])
        recorded={r['game_key'] for r in c.execute('SELECT game_key FROM forecasts WHERE mode=?',(mode,))}
        rows=c.execute('SELECT payload,created FROM snapshots ORDER BY created DESC').fetchall()
    candidates=[];seen=set()
    for row in rows:
        g=json.loads(row['payload']);game_key=store.key(g)
        if g['mode']!=mode or game_key in seen or game_key not in recorded:continue
        seen.add(game_key)
        if not g.get('prediction') or g['state']!='pre' or store.instant(g['start'])<=moment:continue
        if store.instant(g['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=day:continue
        if not 0<=(moment-store.instant(row['created'])).total_seconds()<=1200:continue
        if g['sport']=='nfl' and g.get('season_type')!=2:continue
        options=[picks.chosen(g,k) for k in (('ml','total','btts') if g['sport']=='ucl' else ('ml','total'))]
        for p in options:
            if p['conditional']<.58:continue
            fresh=False
            if g.get('odds_updated'):
                fresh=0<=(moment-store.instant(g['odds_updated'])).total_seconds()<=1200
            verified=bool(p['context_ready'] and fresh and p['ev'] is not None and p['ev']>0 and (p['side'] in ('home','away','draw','btts_yes','btts_no') or p['market_line']))
            p.update(sport=g['sport'],captured=at,tier='Priced model edge' if verified else 'Research pick · not verified value',verified_value=verified,
                summary=picks.explain(g,p['side']),outcome=None)
            candidates.append(p)
    candidates.sort(key=lambda p:(not p['verified_value'],-(p['ev'] if p['verified_value'] else p['conditional']),p['start'],p['game_key'],p['side']))
    legs=[];used=set()
    for p in candidates:
        if p['game_key'] in used:continue
        legs.append(p);used.add(p['game_key'])
        if len(legs)==3:break
    if not legs:return None
    card={'key':key,'day':day,'mode':mode,'created':at,'rule':RULE,'legs':legs,
          'note':'Maximum three individual plays across all sports per Toronto day, one per game. Frozen when selected; not a parlay. Ranked by verified positive EV when eligible, otherwise by conditional model probability ≥58%. Research selections are not verified betting value; no LLM invents probabilities.'}
    with store.connect(path) as c:
        c.execute('INSERT OR IGNORE INTO daily_plays VALUES(?,?,?,?,?)',(key,mode,day,at,json.dumps(card)))
        saved=c.execute('SELECT payload FROM daily_plays WHERE play_key=?',(key,)).fetchone()
    return json.loads(saved['payload'])

def record(mode,path=None):
    with store.connect(path) as c:
        rows=c.execute('SELECT payload FROM daily_plays WHERE mode=? ORDER BY day DESC',(mode,)).fetchall()
        results={r['game_key']:json.loads(r['result']) for r in c.execute('SELECT game_key,result FROM forecasts WHERE mode=? AND result IS NOT NULL',(mode,))}
    cards=[];wins=losses=pushes=pending=priced=0;profit=0.
    for row in rows:
        card=json.loads(row['payload'])
        for p in card['legs']:
            r=results.get(p['game_key']);side='soccer_'+p['side'] if p['sport']=='ucl' and p['side'] in ('home','away') else p['side']
            p['outcome']=store.outcome(side,r['home_score'],r['away_score'],p['line']) if r else None
            p['final']=r
            if p['outcome']=='win':wins+=1
            elif p['outcome']=='loss':losses+=1
            elif p['outcome']=='push':pushes+=1
            else:pending+=1
            if r and p['odds'] is not None:priced+=1;profit+=store.profit(p['outcome'],p['odds'])
        cards.append(card)
    return {'days':cards,'metrics':{'wins':wins,'losses':losses,'pushes':pushes,'pending':pending,'priced':priced,
        'hit_rate':wins/(wins+losses) if wins+losses else None,'roi':profit/priced if priced else None},
        'updated':store.now(),'note':'Separate prospective Flashy AI record. No historical selections are backfilled. A day with no eligible pregame games can have zero plays; canceled games remain pending until supported settlement is available.'}
