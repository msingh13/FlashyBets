"""Champions League 90-minute markets; never settle from extra-time or penalties."""
import asyncio,math,os
from datetime import datetime,timezone
import httpx
from . import providers,store
CACHE={}

class SoccerModel:
    def predict(self,home_rate,away_rate,line,ot_home=.5):
        if not all(math.isfinite(x) for x in (home_rate,away_rate,line)) or not (0<home_rate<=10 and 0<away_rate<=10 and 0<=line<=30):
            raise ValueError('Invalid soccer inputs')
        def pmf(rate):return [math.exp(-rate)*rate**k/math.factorial(k) for k in range(61)]
        home=away=draw=over=under=push=0.
        for h,ph in enumerate(pmf(home_rate)):
            for a,pa in enumerate(pmf(away_rate)):
                mass=ph*pa
                home+=mass if h>a else 0;away+=mass if a>h else 0;draw+=mass if a==h else 0
                over+=mass if h+a>line else 0;under+=mass if h+a<line else 0;push+=mass if h+a==line else 0
        yes=(1-math.exp(-home_rate))*(1-math.exp(-away_rate))
        return dict(home=home,away=away,draw=draw,tie=draw,ml_push=0,over=over,under=under,push=push,
            btts_yes=yes,btts_no=1-yes,expected_total=home_rate+away_rate,home_rate=home_rate,away_rate=away_rate,
            distribution=[],version='ucl-90min-poisson-v1',assumptions='Independent 90-minute Poisson goals, including stoppage time. Draw is a losing result for team ML. Extra time and penalties excluded. Uncalibrated baseline.')

def regular_score(match):
    score=match.get('score',{})
    value=score.get('regularTime') if score.get('duration') in ('EXTRA_TIME','PENALTY_SHOOTOUT') else score.get('fullTime')
    if not value or value.get('home') is None or value.get('away') is None:return None
    return int(value['home']),int(value['away'])

async def live_games(day):
    token=os.getenv('FOOTBALL_DATA_TOKEN')
    if not token:return await espn_games(day)
    year=int(day[:4])-(int(day[5:7])<7)
    cached=CACHE.get(year)
    if cached and (datetime.now(timezone.utc)-cached[0]).total_seconds()<600:matches=cached[1]
    else:
        async with httpx.AsyncClient(timeout=25) as client:
            body=await providers.get(client,'https://api.football-data.org/v4/competitions/CL/matches',{'season':year},headers={'X-Auth-Token':token})
        matches=body.get('matches',[]);CACHE[year]=(datetime.now(timezone.utc),matches)
    return rows_from_matches(matches,day,'football-data.org · Champions League','https://www.football-data.org/')

def rows_from_matches(matches,day,source,source_url):
    rows=[]
    for m in matches:
        if providers.localday(m['utcDate'])!=day:continue
        score=regular_score(m);state='post' if m['status']=='FINISHED' and score else 'pre' if m['status']=='TIMED' else 'unavailable'
        if m['status'] in ('IN_PLAY','PAUSED'):state='in'
        h,a=m['homeTeam'],m['awayTeam']
        past=[x for x in sorted(matches,key=lambda x:x['utcDate']) if x['status']=='FINISHED' and store.instant(x['utcDate'])<store.instant(m['utcDate']) and regular_score(x)]
        def rates(team):
            samples=[x for x in past if team in (x['homeTeam']['id'],x['awayTeam']['id'])][-20:]
            gf=ga=0
            for x in samples:
                hs,aws=regular_score(x);ishome=x['homeTeam']['id']==team
                gf+=hs if ishome else aws;ga+=aws if ishome else hs
            return (gf+15)/(len(samples)+10),(ga+15)/(len(samples)+10),len(samples)
        hf,ha,hn=rates(h['id']);af,aa,an=rates(a['id'])
        g=dict(id=str(m['id']),sport='ucl',mode='live',home=h['name'],away=a['name'],home_abbr=h.get('tla') or h['shortName'],away_abbr=a.get('tla') or a['shortName'],
            home_id=h['id'],away_id=a['id'],start=m['utcDate'],state=state,status=m.get('display_status') or m['status'],
            clock=m.get('clock'),period=m.get('period'),display_home_score=m.get('display_home_score',score[0] if score else None),display_away_score=m.get('display_away_score',score[1] if score else None),score_updated=store.now(),season_type=2,venue=m.get('venue') or 'Venue not supplied',
            home_score=score[0] if state=='post' else None,away_score=score[1] if state=='post' else None,
            home_rate=(hf+aa)/2+.10,away_rate=max(.1,(af+ha)/2-.10),sample_sizes={'home':hn,'away':an},
            line=None,home_odds=None,away_odds=None,draw_odds=None,over_odds=None,under_odds=None,btts_yes_odds=None,btts_no_odds=None,
            source=source,source_url=m.get('source_url') or source_url,odds_source=None,odds_updated=None,
            rates_source='Prior completed Champions League 90-minute scores; 10-match prior at 1.5 goals per team',rates_asof=store.now(),
            home_starters=[],away_starters=[],lineup_source='Confirmed starting XIs unavailable',injuries={'home':[],'away':[]},injuries_checked=False,injuries_asof=None,
            injuries_source='Injury coverage unavailable',travel={'home':{'km':None,'rest_hours':None,'from':None,'method':'Unavailable'},'away':{'km':None,'rest_hours':None,'from':None,'method':'Unavailable'}},
            indoor=False,weather={'status':'Weather unavailable','temperature_c':None,'wind_kmh':None,'source':None},
            provider_errors=['Starting XIs, injuries, domestic form, travel and weather are not supplied by this adapter. Baseline only.'])
        rows.append(g)
    return rows


ESPN_CACHE={}

def espn_match(event):
    """Normalize only unambiguous regulation finals; ET/shootout scores never settle."""
    c=event['competitions'][0];status=c['status']['type']
    teams={t['homeAway']:t for t in c['competitors']};h,a=teams['home'],teams['away']
    final=status.get('completed') and status.get('name')=='STATUS_FULL_TIME' and c['status'].get('period',2)<=2
    state='FINISHED' if final else 'TIMED' if status.get('state')=='pre' else 'IN_PLAY' if status.get('state')=='in' else 'UNAVAILABLE'
    def team(t):
        value=t['team'];return {'id':str(value['id']),'name':value['displayName'],'tla':value.get('abbreviation'),'shortName':value.get('shortDisplayName',value['displayName'])}
    def display(t):
        score=t.get('score');return int(score['value'] if isinstance(score,dict) else score) if score is not None and status.get('state') in ('in','post') else None
    def goals(t):return display(t) if final else None
    return {'id':'espn-'+str(event['id']),'utcDate':event['date'],'status':state,'homeTeam':team(h),'awayTeam':team(a),
        'clock':c['status'].get('displayClock'),'period':c['status'].get('period'),'display_status':status.get('description'),'display_home_score':display(h),'display_away_score':display(a),
        'venue':c.get('venue',{}).get('fullName'),'score':{'duration':'REGULAR','fullTime':{'home':goals(h),'away':goals(a)}},
        'source_url':next((l['href'] for l in event.get('links',[]) if 'desktop' in l.get('rel',[])), 'https://www.espn.com/soccer/scoreboard/_/league/uefa.champions')}

async def espn_games(day):
    base=providers.BASE+'soccer/uefa.champions/'
    season=int(day[:4])-(int(day[5:7])<7)
    async with httpx.AsyncClient(timeout=25) as client:
        body=await providers.get(client,base+'scoreboard',{'dates':day.replace('-','')})
        events=body.get('events',[])
        ids={str(t['team']['id']) for e in events for t in e['competitions'][0]['competitors']}
        semaphore=asyncio.Semaphore(4)
        async def history(team):
            key=(season,team);cached=ESPN_CACHE.get(key)
            if cached and (datetime.now(timezone.utc)-cached[0]).total_seconds()<600:return cached[1]
            async with semaphore:
                data=await providers.get(client,providers.BASE+f'soccer/all/teams/{team}/schedule',{'season':season})
            rows=[]
            for e in data.get('events',[]):
                m=espn_match(e);m['league']=e.get('league',{}).get('slug','uefa.champions');m['league_name']=e.get('league',{}).get('name','Champions League');m['is_tournament']=e.get('league',{}).get('isTournament',True);rows.append(m)
            ESPN_CACHE[key]=(datetime.now(timezone.utc),rows);return rows
        # A failed historical fetch fails the update rather than quietly substituting made-up form.
        histories=await asyncio.gather(*(history(t) for t in sorted(ids)))
    matches={m['id']:m for group in histories for m in group}
    matches.update({m['id']:m for m in map(espn_match,events)})
    rows=rows_from_matches([m for m in matches.values() if m.get('league','uefa.champions')=='uefa.champions'],day,'ESPN public Champions League feed','https://www.espn.com/soccer/scoreboard/_/league/uefa.champions')
    async with httpx.AsyncClient(timeout=25) as client:
        async def lineup(g):
            if abs((store.instant(g['start'])-datetime.now(timezone.utc)).total_seconds())>7200:return
            async with semaphore:
                data,error=await providers.optional(client,base+'summary',{'event':g['id'].removeprefix('espn-')})
            if data:attach_lineups(g,data)
            elif error:g['provider_errors'].append('Lineup summary unavailable')
        await asyncio.gather(*(lineup(g) for g in rows))
    # Team schedules can contain other dates; publish only the requested scoreboard's fixtures.
    for g in rows:
        g['domestic_form']={}
        for side in ('home','away'):
            team=g[side+'_id'];past=[m for m in matches.values() if not m.get('is_tournament',True) and m['status']=='FINISHED' and store.instant(m['utcDate'])<store.instant(g['start']) and team in (m['homeTeam']['id'],m['awayTeam']['id'])]
            past=sorted(past,key=lambda m:m['utcDate'])[-10:];gf=ga=0
            for m in past:
                h,a=regular_score(m);ishome=m['homeTeam']['id']==team;gf+=h if ishome else a;ga+=a if ishome else h
            g['domestic_form'][side]={'samples':len(past),'goals_for':gf,'goals_against':ga,'matches':[{'start':m['utcDate'],'league':m.get('league_name'),'home':m['homeTeam']['name'],'away':m['awayTeam']['name'],'score':regular_score(m)} for m in past]}
        g['provider_errors']=['Domestic form is displayed as context; league-strength and player-impact coefficients are not fitted. Confirmed XIs and injury coverage remain unavailable.']
    event_ids={'espn-'+str(e['id']) for e in events}
    return [g for g in rows if g['id'] in event_ids]


def attach_lineups(g,data):
    """Accept explicitly marked starters only, with event and team identity checks."""
    if str(data.get('header',{}).get('id'))!=g['id'].removeprefix('espn-'):return
    for side in ('home','away'):
        roster=next((r for r in data.get('rosters',[]) if r.get('homeAway')==side and str(r.get('team',{}).get('id'))==str(g[side+'_id'])),None)
        starters=[r for r in (roster or {}).get('roster',[]) if r.get('starter') is True and r.get('athlete',{}).get('displayName')]
        if len(starters)==11 and len({r['athlete'].get('id') for r in starters})==11:
            g[side+'_starters']=[{'name':r['athlete']['displayName'],'status':'ESPN listed starter','confirmed':True} for r in starters]
    if g['home_starters'] or g['away_starters']:g['lineup_source']='ESPN match roster · explicitly marked starting XI · fetched '+store.now()
