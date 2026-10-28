from .sports import SOCCER
"""Immutable pregame model forecasts and settlements."""
import json,sqlite3,os,math,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from .model import decimal

DB=os.getenv('DATABASE_PATH','flashybets.db')
def now(): return datetime.now(timezone.utc).isoformat()
def instant(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Timestamp must be timezone-aware')
    return d
@contextmanager
def connect(path=None):
    c=sqlite3.connect(path or DB,timeout=20);c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""
    CREATE TABLE IF NOT EXISTS forecasts (
      game_key TEXT PRIMARY KEY, sport TEXT, mode TEXT, start TEXT, captured TEXT,
      payload TEXT, result TEXT, settled_at TEXT);
    CREATE TABLE IF NOT EXISTS cards (
      card_key TEXT PRIMARY KEY,sport TEXT,mode TEXT,day TEXT,created TEXT,payload TEXT);
    CREATE TABLE IF NOT EXISTS model_versions (
      version TEXT PRIMARY KEY,sport TEXT,kind TEXT,temperature REAL,created TEXT,
      training_through TEXT,evaluation TEXT,active INTEGER);
    CREATE TABLE IF NOT EXISTS model_checks (
      sport TEXT,day TEXT,kind TEXT,payload TEXT,PRIMARY KEY(sport,day,kind));
    CREATE TABLE IF NOT EXISTS updates (sport TEXT PRIMARY KEY, updated TEXT, error TEXT);
    CREATE TABLE IF NOT EXISTS daily_plays (play_key TEXT PRIMARY KEY,mode TEXT,day TEXT,created TEXT,payload TEXT);
    CREATE TABLE IF NOT EXISTS snapshots (id TEXT,created TEXT,payload TEXT,PRIMARY KEY(id,created));
    """)
    try: yield c;c.commit()
    except BaseException: c.rollback();raise
    finally: c.close()

def key(g): return f"{g['mode']}:{g['sport']}:{g['id']}"
def capture(g,path=None,at=None):
    t=at or now()
    if g.get('state')!='pre' or not g.get('prediction') or instant(t)>=instant(g['start']): return False
    with connect(path) as c:
        r=c.execute('INSERT OR IGNORE INTO forecasts(game_key,sport,mode,start,captured,payload) VALUES(?,?,?,?,?,?)',
        (key(g),g['sport'],g['mode'],g['start'],t,json.dumps(g)))
        return r.rowcount==1

def previous(g,path=None):
    with connect(path) as c: r=c.execute('SELECT payload FROM forecasts WHERE game_key=?',(key(g),)).fetchone()
    return json.loads(r['payload']) if r else None

def outcome(market,h,a,line=None):
    if market in ('draw','soccer_home','soccer_away','btts_yes','btts_no'):
        won=(h==a) if market=='draw' else (h>0 and a>0)==(market=='btts_yes') if market.startswith('btts') else (h>a if market=='soccer_home' else a>h)
        return 'win' if won else 'loss'
    if market in ('home','away'):
        if h==a:return 'push'
        return 'win' if (h>a)==(market=='home') else 'loss'
    if line is None: raise ValueError('Totals require a line')
    if h+a==line: return 'push'
    return 'win' if ((h+a)>line)==(market=='over') else 'loss'

def profit(result,odds,stake=1):
    return stake*(decimal(odds)-1) if result=='win' else -stake if result=='loss' else 0

def settle(g,path=None):
    if g.get('state')!='post' or g.get('home_score') is None or g.get('away_score') is None:return
    h,a=g['home_score'],g['away_score']
    if min(h,a)<0 or (h==a and g['sport'] not in ('nfl',*SOCCER)):return
    with connect(path) as c:
        c.execute('UPDATE forecasts SET result=?,settled_at=? WHERE game_key=? AND result IS NULL',
            (json.dumps({'home_score':h,'away_score':a,'source':g['source']}),now(),key(g)))

def ledger(sport,mode,path=None):
    with connect(path) as c:
        fs=c.execute('SELECT * FROM forecasts WHERE sport=? AND mode=? ORDER BY start DESC',(sport,mode)).fetchall()
        health=c.execute('SELECT * FROM updates WHERE sport=?',(sport,)).fetchone()
    payloads={f['game_key']:json.loads(f['payload']) for f in fs}
    rows=[];metrics={n:{'settled':0,'wins':0,'pushes':0,'priced':0,'profit':0,'brier_sum':0,'brier_count':0} for n in (['home','away','draw','over','under','btts_yes','btts_no'] if sport in SOCCER else ['home','away','over','under'])}
    for f in fs:
        g=payloads[f['game_key']];r=json.loads(f['result']) if f['result'] else None
        row={'game_key':f['game_key'],'id':g['id'],'home':g['home_abbr'],'away':g['away_abbr'],'start':f['start'],
             'captured':f['captured'],'model':g['prediction']['version'],'line':g['reference_line'],'result':r,'markets':[]}
        for n in metrics:
            p=g['prediction'][n];odds=g['markets'].get(n);result=outcome('soccer_'+n if sport in SOCCER and n in ('home','away') else n,r['home_score'],r['away_score'],g['reference_line']) if r else None
            row['markets'].append({'name':n,'probability':p,'odds':odds['odds'] if odds else None,'outcome':result})
            if r:
                m=metrics[n];m['settled']+=1;m['wins']+=result=='win';m['pushes']+=result=='push'
                if result!='push':
                    push=g['prediction'].get('ml_push',0) if n in ('home','away') else 0 if n.startswith('btts') or n=='draw' else g['prediction']['push']
                    cp=p/(1-push);m['brier_sum']+=(cp-int(result=='win'))**2;m['brier_count']+=1
                if odds: m['priced']+=1;m['profit']+=profit(result,odds['odds'])
        rows.append(row)
    for m in metrics.values():
        m['roi']=m['profit']/m['priced'] if m['priced'] else None
        m['brier']=m.pop('brier_sum')/m['brier_count'] if m['brier_count'] else None
    selection_metrics={kind:{'wins':0,'losses':0,'pushes':0,'pending':0,'priced':0,'profit':0.,'brier_sum':0.,'brier_count':0} for kind in (('ml','total','btts') if sport in SOCCER else ('ml','total'))}
    for row in rows:
        row['picks']={}
        for kind,sides in ([('ml',('home','away','draw')),('total',('over','under')),('btts',('btts_yes','btts_no'))] if sport in SOCCER else [('ml',('home','away')),('total',('over','under'))]):
            picked=max((m for m in row['markets'] if m['name'] in sides),key=lambda m:m['probability'])
            picked=dict(picked)
            picked['label']=('Draw' if picked['name']=='draw' else row[picked['name']]) if kind=='ml' else picked['name'].replace('_',' ').upper() if kind=='btts' else picked['name'].title()+' '+str(row['line'])
            row['picks'][kind]=picked
            sm=selection_metrics[kind];result=picked['outcome']
            sm[{'win':'wins','loss':'losses','push':'pushes',None:'pending'}[result]]+=1
            if result and picked['odds']:
                sm['priced']+=1;sm['profit']+=profit(result,picked['odds'])
            if result in ('win','loss'):
                # Use the original forecast's push probability, not current market lines.
                original=payloads[row['game_key']]
                pp=original['prediction'].get('ml_push',0) if kind=='ml' else 0 if kind=='btts' else original['prediction']['push']
                sm['brier_sum']+=(picked['probability']/(1-pp)-int(result=='win'))**2;sm['brier_count']+=1
    for sm in selection_metrics.values():
        sm['hit_rate']=sm['wins']/(sm['wins']+sm['losses']) if sm['wins']+sm['losses'] else None
        sm['roi']=sm['profit']/sm['priced'] if sm['priced'] else None
        sm['brier']=sm.pop('brier_sum')/sm['brier_count'] if sm['brier_count'] else None
    return {'forecasts':rows,'metrics':selection_metrics,'all_side_metrics':metrics,
        'health':dict(health) if health else None,
        'source':'Synthetic demo model record' if mode=='demo' else 'Immutable pregame model picks; automatic final-score settlement'}
