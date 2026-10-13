import asyncio,os,json
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
from . import providers,store
from .demo import games as demo_games
from .models import MODELS
from .model import market
from .context import context_for
from . import learning,picks
CACHE={};LOCKS={};TTL=max(60,int(os.getenv('REFRESH_SECONDS','600')))

def today():return datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
def enrich(g,path=None):
    g['updated']=store.now();g['context']=context_for(g)
    if g['sport']=='nfl' and g.get('season_type')!=2:
        g.update(prediction=None,markets={},reference_line=g['line'],recommendations=[],explanation='NFL preseason/playoff modeling is not supported by the regular-season adapter. No forecast is issued.')
        return g
    adj=g['context']['adjustments'];hr=g['home_rate']+adj['home'];ar=g['away_rate']+adj['away']
    line=g['line'] if g['line'] is not None else {'nhl':6.5,'nba':228.5,'nfl':44.5}[g['sport']]
    g['reference_line']=line
    p=MODELS[g['sport']].predict(hr,ar,line);p.setdefault('ml_push',0);g['prediction']=p
    learning.apply(g,path)
    markets={}
    for n in ('home','away','over','under'):
        odds=g.get(n+'_odds');push=p['ml_push'] if n in ('home','away') else p['push']
        markets[n]=market(p[n],push,odds) if odds is not None else None
    for sides in [('home','away'),('over','under')]:
        if all(markets[n] for n in sides):
            vig=sum(markets[n]['implied'] for n in sides)
            for n in sides:markets[n]['no_vig']=markets[n]['implied']/vig;markets[n]['conditional']=markets[n]['probability']/(1-markets[n]['push'])
    g['markets']=markets
    g['explanation']={'nhl':'Independent Poisson regulation goals; ties split 50/50, with one OT/shootout settlement goal added.',
      'nba':'Final-score Gaussian model: shrunk scoring/conceding means, 15-point margin and 20-point total standard deviations. Historical inputs include overtime.',
      'nfl':'Possession scoring model: eleven possessions with 0/3/7-point outcomes; explicit approximate overtime/tie settlement. Regular season only.'}[g['sport']]
    g['recommendations']=[]
    odds_fresh=False
    if g.get('odds_updated'):
        try:odds_fresh=abs((datetime.now(timezone.utc)-store.instant(g['odds_updated'])).total_seconds())<=TTL*2
        except ValueError:pass
    if g['context']['ready'] and g['state']=='pre' and odds_fresh:
        g['recommendations']=[n for n,m in markets.items() if m and m['ev']>0]
    return g

async def board(sport,day,mode,force=False,path=None):
    if sport not in MODELS:raise ValueError('Supported sports: NHL, NBA, NFL')
    if mode not in ('demo','live'):raise ValueError('mode must be demo or live')
    date.fromisoformat(day);cache_key=(sport,day,mode)
    lock=LOCKS.setdefault(cache_key,asyncio.Lock())
    async with lock:
        old=CACHE.get(cache_key)
        if old and not force and (datetime.now(timezone.utc)-old[0]).total_seconds()<TTL:
            return old[1]
        rows=demo_games(sport,day) if mode=='demo' else await providers.live_games(sport,day)
        for g in rows:
            g['mode']=mode;g['sport']=sport
            if g['state']=='pre' and store.instant(g['start'])>datetime.now(timezone.utc):
                enrich(g,path);store.capture(g,path)
            else:
                saved=store.previous(g,path)
                g['prediction']=saved['prediction'] if saved else None
                g['markets']=saved['markets'] if saved else {}
                g['context']=saved['context'] if saved else context_for(g)
                g['reference_line']=saved['reference_line'] if saved else g['line']
                g['explanation']='Stored pregame forecast.' if saved else 'No pregame forecast was recorded. Results will not be backfilled into predictions.'
                g['updated']=store.now();g['recommendations']=[]
                store.settle(g,path)
            with store.connect(path) as c:c.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?)',(g['id'],g['updated'],json.dumps(g)))
        picks.build(sport,day,mode,path)
        result={'games':rows,'mode':mode,'sport':sport,'updated':store.now(),'date':day,'refresh_seconds':TTL,
            'warning':'Baseline forecasts, not calibrated recommendations. Missing context remains visible.'}
        CACHE[cache_key]=(datetime.now(timezone.utc),result)
        return result

async def tick(mode=None,path=None):
    mode=mode or os.getenv('DATA_MODE','live')
    for sport in MODELS:
        try:
            await board(sport,today(),mode,force=True,path=path)
            # Settle outstanding games on their original dates; never manufacture missed forecasts.
            with store.connect(path) as c:
                days={store.instant(r['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat() for r in c.execute(
                  'SELECT start FROM forecasts WHERE sport=? AND mode=? AND result IS NULL',(sport,mode))}
            for d in sorted(days):
                if d<today():await board(sport,d,mode,force=True,path=path)
            if mode=='live':learning.audit(sport,today(),path)
            with store.connect(path) as c:c.execute('INSERT OR REPLACE INTO updates VALUES(?,?,NULL)',(sport,store.now()))
        except Exception:
            if mode=='live':learning.audit(sport,today(),path)
            with store.connect(path) as c:c.execute('INSERT OR REPLACE INTO updates VALUES(?,?,?)',(sport,store.now(),'Update failed; check data providers'))
async def worker():
    while True:
        await tick()
        await asyncio.sleep(TTL)


def seed_demo(sport,path=None):
    """Clearly synthetic past fixtures so the demo can show settled tracker behavior."""
    day=(date.fromisoformat(today())-timedelta(days=1)).isoformat()
    for g in demo_games(sport,day):
        final={'home_score':g['home_score'],'away_score':g['away_score']}
        if g['state']!='post':continue
        g['state']='pre';g['home_score']=None;g['away_score']=None
        enrich(g,path)
        captured=(store.instant(g['start'])-timedelta(hours=2)).isoformat()
        store.capture(g,path,at=captured)
        g.update(final);g['state']='post';store.settle(g,path)
    picks.build(sport,day,'demo',path,at=day+'T14:00:00Z')
