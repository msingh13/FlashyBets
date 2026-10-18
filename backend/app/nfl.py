"""Observed NFL personnel context. Depth order is not a confirmed gameday lineup."""
import asyncio
from datetime import datetime,timezone
from . import providers
from .store import instant
CACHE={}
UNAVAILABLE={'out','injured reserve','ir','suspended','reserve/injured'}

def parse_depth(body,team_id,year):
    if str(body.get('team',{}).get('id'))!=str(team_id) or body.get('season',{}).get('year')!=year:
        return []
    rows=[]
    for chart in body.get('depthchart',[]):
        for position,slot in chart.get('positions',{}).items():
            for rank,athlete in enumerate(slot.get('athletes',[]),1):
                if not athlete.get('displayName'):continue
                rows.append({'name':athlete['displayName'],'id':str(athlete.get('id','')),'position':position.upper(),
                    'rank':rank,'formation':chart.get('name',''),'status':'Depth chart · not confirmed','confirmed':False})
    return rows

async def attach(client,games):
    # Current availability must never be presented as a historical pregame input.
    today=datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).date().isoformat()
    eligible=[g for g in games if providers.localday(g['start'])>=today]
    semaphore=asyncio.Semaphore(6)
    async def team(team_id,year):
        key=(str(team_id),year);old=CACHE.get(key)
        if old and (datetime.now(timezone.utc)-old[0]).total_seconds()<600:return old[1]
        async with semaphore:
            depth,error=await providers.optional(client,providers.BASE+providers.PATHS['nfl']+f'/teams/{team_id}/depthcharts')
        rows=parse_depth(depth or {},team_id,year)
        value={'rows':rows,'asof':(depth or {}).get('timestamp'),'error':error or (None if rows else 'Depth chart unavailable')}
        if not value['error']:CACHE[key]=(datetime.now(timezone.utc),value)
        return value
    keys={(g[s+'_id'],g.get('season_year')) for g in eligible for s in ('home','away')}
    values=await asyncio.gather(*(team(*key) for key in keys));teams=dict(zip(keys,values))
    for g in eligible:
        g['nfl_depth']={};g['lineup_source']='ESPN team depth charts; projected order, not confirmed gameday starters'
        for side in ('home','away'):
            item=teams[(g[side+'_id'],g.get('season_year'))]
            g['nfl_depth'][side]={'players':item['rows'],'asof':item['asof'],
                'url':f"https://www.espn.com/nfl/team/depth/_/name/{g[side+'_abbr'].lower()}",
                'status':'Depth order only; final inactives not verified'}
            if item['error']:g['provider_errors'].append(f'{side} NFL depth chart unavailable')
        # Do not promote a depth chart into confirmed starters.
        g['nfl_context_asof']=datetime.now(timezone.utc).isoformat()

def summary(g):
    p=g.get('prediction')
    if not p:return 'No pregame forecast was recorded, so there is no model favorite to explain.'
    if abs(p['home']-p['away'])<1e-8:
        reason='The model has no clear moneyline favorite because its scoring projections are level.'
    else:
        side='home' if p['home']>p['away'] else 'away';other='away' if side=='home' else 'home'
        reason=f"{g[side]} leads at {p[side]:.0%}: the possession model projects {p[side+'_rate']:.1f} versus {p[other+'_rate']:.1f} points from shrunk prior-game scoring and conceding rates"+(' plus home-field advantage.' if side=='home' and not g.get('neutral') else '.')
    if not g.get('nfl_depth'):
        return reason+' Personnel context for this game is unavailable; this is a baseline forecast.'
    flags=[]
    for side in ('away','home'):
        injuries=g.get('injuries',{}).get(side,[])
        ranked=sorted(injuries,key=lambda x:(x.get('position')!='QB',x.get('status','').lower() not in UNAVAILABLE,x.get('name','')))
        absent=[x for x in ranked if x.get('status','').lower() in UNAVAILABLE or x.get('status','').lower() in ('questionable','doubtful')]
        qb=next((r for r in g['nfl_depth'][side]['players'] if r['position']=='QB' and r['rank']==1),None)
        if absent:
            r=absent[0];flags.append(f"{g[side+'_abbr']}: {r['name']} {r['status']}"+(f", {qb['name']} atop the QB depth chart" if r.get('position')=='QB' and qb else ''))
    caution='; '.join(flags) if flags else 'Depth charts remain projected and final inactives are unverified'
    return reason+' '+caution+' — current personnel reports are context, not fitted probability adjustments.'
