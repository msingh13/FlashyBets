"""Public ESPN adapters, The Odds API, and an optional licensed SportsDataIO adapter.
Public feeds have no SLA. Provider failures remain visible; live never falls back to demo.
"""
import asyncio,os,math,unicodedata
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import httpx
from .store import instant
PATHS={'nhl':'hockey/nhl','nba':'basketball/nba','nfl':'football/nfl'}
ODDS_SPORT={'nhl':'icehockey_nhl','nba':'basketball_nba','nfl':'americanfootball_nfl'}
BASE='https://site.api.espn.com/apis/site/v2/sports/'
CITY_CACHE={};GEO_LOCKS={};TEAM_CACHE={}
def normalize(name):
    return ''.join(c for c in unicodedata.normalize('NFKD',name).casefold() if not unicodedata.combining(c)).strip().replace('la clippers','los angeles clippers')
async def get(client,url,params=None,headers=None):
    r=await client.get(url,params=params,headers=headers);r.raise_for_status();return r.json()
async def optional(client,url,params=None,headers=None):
    try:return await get(client,url,params,headers),None
    except (httpx.HTTPError,ValueError):return None,'Provider unavailable'
def localday(start): return instant(start).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
def abbr(value,sport):
    return {"NJ":"NJD","TB":"TBL","SJ":"SJS","LA":"LAK","WSH":"WSH","WAS":"WSH","NAS":"NSH"}.get(value,value) if sport=="nhl" else value

def game_from_event(e,sport):
    c=e['competitions'][0];teams={t['homeAway']:t for t in c['competitors']}
    h,a=teams['home'],teams['away'];v=c.get('venue',{});state=c['status']['type']['state']
    if state=='post' and not c['status']['type'].get('completed'):state='unavailable'
    def probable(t):
        return [{'name':p.get('athlete',{}).get('displayName','Unknown'),
            'status':p.get('status',{}).get('name','Expected'),'confirmed':p.get('status',{}).get('type','').lower()=='confirmed'} for p in t.get('probables',[])]
    return {'id':e['id'],'sport':sport,'mode':'live','home':h['team']['displayName'],'away':a['team']['displayName'],
      'home_abbr':abbr(h['team']['abbreviation'],sport),'away_abbr':abbr(a['team']['abbreviation'],sport),'home_id':h['id'],'away_id':a['id'],
      'start':e['date'],'state':state,'status':c['status']['type']['description'],
      'clock':c['status'].get('displayClock'),'period':c['status'].get('period'),
      'display_home_score':float(h['score'].get('value',0) if isinstance(h['score'],dict) else h['score']) if state in ('in','post') else None,
      'display_away_score':float(a['score'].get('value',0) if isinstance(a['score'],dict) else a['score']) if state in ('in','post') else None,'score_updated':datetime.now(timezone.utc).isoformat(),
      'home_score':int(float(h['score'].get('value',0) if isinstance(h['score'],dict) else h['score'])) if state=='post' else None,'away_score':int(float(a['score'].get('value',0) if isinstance(a['score'],dict) else a['score'])) if state=='post' else None,
      'season_type':e.get('season',{}).get('type',e.get('seasonType',{}).get('type')),'season_year':e.get('season',{}).get('year'), 'venue':v.get('fullName','Unknown venue'),
      'city':v.get('address',{}).get('city'),'region':v.get('address',{}).get('state'),
      'country':v.get('address',{}).get('country','USA'),'indoor':v.get('indoor'),
      'neutral':c.get('neutralSite',False),'week':e.get('week',{}).get('number'),
      'source':'ESPN public scoreboard','home_starters':probable(h),'away_starters':probable(a),
      'line':None,'home_odds':None,'away_odds':None,'over_odds':None,'under_odds':None,
      'odds_source':None,'odds_updated':None,'provider_errors':[],
      'source_url':e.get('links',[{}])[0].get('href',f'https://www.espn.com/{sport}/scoreboard')}

def haversine(a,b):
    la,lo,lb,lob=map(math.radians,[a[0],a[1],b[0],b[1]])
    x=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin((lob-lo)/2)**2
    return 6371*2*math.atan2(math.sqrt(x),math.sqrt(max(0,1-x)))
async def geocode(client,city,region=None,country=None):
    if not city:return None
    cache_key=(city,region,country)
    async with GEO_LOCKS.setdefault(asyncio.get_running_loop(),asyncio.Lock()):
        if cache_key in CITY_CACHE:return CITY_CACHE[cache_key]
        body,err=await optional(client,'https://geocoding-api.open-meteo.com/v1/search',{'name':city,'count':10,'language':'en','format':'json'})
        matches=(body or {}).get('results',[])
        # Only use unambiguous city candidates. US state abbreviations map explicitly.
        states={'AZ':'Arizona','CA':'California','CO':'Colorado','CT':'Connecticut','DC':'District of Columbia','FL':'Florida','GA':'Georgia','IL':'Illinois','IN':'Indiana','LA':'Louisiana','MA':'Massachusetts','MD':'Maryland','MI':'Michigan','MN':'Minnesota','MO':'Missouri','NC':'North Carolina','NJ':'New Jersey','NV':'Nevada','NY':'New York','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','TN':'Tennessee','TX':'Texas','UT':'Utah','WA':'Washington','WI':'Wisconsin','ON':'Ontario','QC':'Quebec','AB':'Alberta','BC':'British Columbia','MB':'Manitoba'}
        wanted=states.get(region,region)
        country_code={'USA':'US','United States':'US','Canada':'CA','England':'GB','UK':'GB','United Kingdom':'GB','Germany':'DE','Spain':'ES','Mexico':'MX','Brazil':'BR','Ireland':'IE','Australia':'AU'}.get(country,country)
        candidates=[m for m in matches if normalize(m['name'])==normalize(city) and (not wanted or normalize(m.get('admin1',''))==normalize(wanted)) and (not country_code or m.get('country_code')==country_code)]
        match=candidates[0] if len(candidates)==1 else None
        point=(match['latitude'],match['longitude']) if match else None
        if not err:CITY_CACHE[cache_key]=point
        return point

async def attach_odds(client,games,sport):
    if not games or not os.getenv('ODDS_API_KEY'):return
    body,err=await optional(client,f'https://api.the-odds-api.com/v4/sports/{ODDS_SPORT[sport]}/odds',
      {'apiKey':os.environ['ODDS_API_KEY'],'regions':os.getenv('ODDS_REGION','us'),'markets':'h2h,totals','oddsFormat':'american'})
    if err:
        for g in games:g['provider_errors'].append('Sportsbook provider unavailable')
        return
    for g in games:
        match=next((o for o in body if normalize(o['home_team'])==normalize(g['home']) and normalize(o['away_team'])==normalize(g['away']) and abs((instant(o['commence_time'])-instant(g['start'])).total_seconds())<300),None)
        if not match:continue
        book=next((b for b in match['bookmakers'] if b['key']==os.getenv('ODDS_BOOKMAKER','draftkings')),None)
        if not book:continue
        g['odds_source']=book['title'];g['odds_updated']=book['last_update']
        for m in book['markets']:
            outcomes={normalize(o['name']):o for o in m['outcomes']}
            if m['key']=='h2h' and len(outcomes)==2 and normalize(g['home']) in outcomes and normalize(g['away']) in outcomes:
                g['home_odds']=outcomes[normalize(g['home'])]['price'];g['away_odds']=outcomes[normalize(g['away'])]['price']
            if m['key']=='totals' and 'over' in outcomes and 'under' in outcomes and outcomes['over']['point']==outcomes['under']['point']:
                g['line']=outcomes['over']['point'];g['over_odds']=outcomes['over']['price'];g['under_odds']=outcomes['under']['price']

async def sportsdata_context(client,games,sport,day):
    key=os.getenv('SPORTSDATAIO_KEY')
    if not key or not games:return
    headers={'Ocp-Apim-Subscription-Key':key};base=f'https://api.sportsdata.io/v3/{sport}'
    kind={'nhl':f'StartingGoaltendersByDate/{day}','nba':f'StartingLineupsByDate/{day}','nfl':None}[sport]
    if kind:
        body,err=await optional(client,f'{base}/projections/json/{kind}',headers=headers)
        if err:
            for g in games:g['provider_errors'].append('Licensed lineup provider unavailable')
        else:
            for g in games:
                match=next((r for r in body if abbr(r['HomeTeam'],sport)==g['home_abbr'] and abbr(r['AwayTeam'],sport)==g['away_abbr']),None)
                if match:
                    for side in ('home','away'):
                        raw=match.get(side.title()+('Goaltender' if sport=='nhl' else 'Lineup'))
                        if not raw:continue
                        if isinstance(raw,dict):raw=[raw]
                        if sport=='nba':raw=[r for r in raw if r.get('Starting') is True]
                        g[side+'_starters']=[{'name':((r.get('FirstName') or '')+' '+(r.get('LastName') or '')).strip() or r.get('Name','Unknown'),
                            'confirmed':r.get('Confirmed') is True,'status':'Confirmed' if r.get('Confirmed') is True else 'Projected'} for r in raw]
                    g['lineup_source']='SportsDataIO licensed feed'
    if sport=='nfl':
        depth,err=await optional(client,f'{base}/scores/json/DepthCharts',headers=headers)
        if err:
            for g in games:g['provider_errors'].append('NFL depth chart provider unavailable')
        else:
            # Depth charts do not prove gameday availability. Display, never call confirmed.
            for g in games:
                g['depth_chart']=depth;g['lineup_source']='SportsDataIO depth chart; inactives still required'

async def live_games(sport,day):
    if sport=='ucl':
        from .soccer import live_games as soccer_games
        return await soccer_games(day)
    startdate=date.fromisoformat(day);past=startdate-timedelta(days=120 if sport=='nfl' else 45)
    async with httpx.AsyncClient(timeout=25) as client:
        scheduled=await get(client,BASE+PATHS[sport]+'/scoreboard',{'dates':startdate.strftime('%Y%m%d'),'limit':1000})
        games=[game_from_event(e,sport) for e in scheduled.get('events',[]) if localday(e['date'])==day]
        if not games:return games
        # ESPN's multi-date scoreboard can reject cross-season ranges. Team schedule
        # endpoints are verified and supply complete season-type schedules instead.
        semaphore=asyncio.Semaphore(6)
        async def team_history(team,year,stype):
            cache_key=(sport,team,year,stype);cached=TEAM_CACHE.get(cache_key)
            if cached and (datetime.now(timezone.utc)-cached[0]).total_seconds()<3600:return cached[1],None
            async with semaphore:
                body,error=await optional(client,BASE+PATHS[sport]+f'/teams/{team}/schedule',{'season':year,'seasontype':stype})
            if not error:TEAM_CACHE[cache_key]=(datetime.now(timezone.utc),body)
            return body,error
        requests={(g[side+'_id'],g['season_year'],g['season_type']) for g in games for side in ('home','away')}
        histories=await asyncio.gather(*(team_history(*args) for args in requests))
        err=any(error for _,error in histories);event_map={}
        for body,error in histories:
            for e in (body or {}).get('events',[]):
                if e['competitions'][0]['status']['type'].get('completed') and localday(e['date'])<day:
                    parsed=game_from_event(e,sport)
                    if parsed['state']=='post':event_map[parsed['id']]=parsed
        events=list(event_map.values())
        injuries,ierr=await optional(client,BASE+PATHS[sport]+'/injuries')
        # NHL official standings captured before selected day to prevent same-day result leakage.
        standings={};serr=None
        if sport=='nhl':
            body,serr=await optional(client,f'https://api-web.nhle.com/v1/standings/{(startdate-timedelta(days=1)).isoformat()}')
            standings={r['teamAbbrev']['default']:r for r in (body or {}).get('standings',[])}
        for g in games:
            baseline={'nhl':3.,'nba':114.,'nfl':22.}[sport];prior={'nhl':20,'nba':12,'nfl':6}[sport]
            relevant=[e for e in events if e['season_type']==g['season_type'] and instant(e['start'])<instant(g['start'])]
            def samples(side):return sorted([e for e in relevant if g[side+'_id'] in (e['home_id'],e['away_id'])],key=lambda e:instant(e['start']))[-20:]
            hs,aws=samples('home'),samples('away')
            def rates(rows,team_id):
                gf=sum(r['home_score'] if r['home_id']==team_id else r['away_score'] for r in rows)
                ga=sum(r['away_score'] if r['home_id']==team_id else r['home_score'] for r in rows)
                return (gf+baseline*prior)/(len(rows)+prior),(ga+baseline*prior)/(len(rows)+prior)
            hf,ha=rates(hs,g['home_id']);af,aa=rates(aws,g['away_id'])
            if sport=='nhl' and g['home_abbr'] in standings and g['away_abbr'] in standings:
                def nhlr(abbr):
                    r=standings[abbr];n=r['gamesPlayed']+20
                    return (r['goalFor']+60)/n,(r['goalAgainst']+60)/n
                hf,ha=nhlr(g['home_abbr']);af,aa=nhlr(g['away_abbr'])
            adv=0 if g['neutral'] else {'nhl':.12,'nba':1.5,'nfl':1.}[sport]
            g['home_rate']=(hf+aa)/2+adv;g['away_rate']=(af+ha)/2-adv
            g['sample_sizes']={'home':len(hs),'away':len(aws)}
            g['rates_source']='Prior-day NHL standings' if sport=='nhl' and standings else 'Prior completed ESPN games; shrunk scoring/conceding averages'
            g['rates_asof']=(startdate-timedelta(days=1)).isoformat();g['lineup_source']='ESPN starting-goalie status; Expected and Confirmed remain distinct'
            injury_teams={normalize(t['displayName']):t for t in (injuries or {}).get('injuries',[])}
            g['injuries']={}
            for side in ('home','away'):
                t=injury_teams.get(normalize(g[side]))
                g['injuries'][side]=[{'name':r.get('athlete',{}).get('displayName','Unknown'),
                    'status':r.get('status','Unknown'),'report':r.get('shortComment',''),'reported_at':r.get('date'),
                    'url':next((x['href'] for x in r.get('athlete',{}).get('links',[]) if 'playercard' in x.get('rel',[])),None)} for r in (t or {}).get('injuries',[]) if r.get('status') not in ('Active','Healthy')]
            g['injuries_checked']=not ierr and normalize(g['home']) in injury_teams and normalize(g['away']) in injury_teams
            g['injuries_asof']=(injuries or {}).get('timestamp');g['injuries_source']='ESPN public injuries'
            if ierr:g['provider_errors'].append('Injury feed unavailable')
            if err:g['provider_errors'].append('Prior-game history unavailable; baseline-only rates')
            if serr:g['provider_errors'].append('NHL standings unavailable')
            # Prior game for travel can include a previous season type; use actual last venue.
            g['travel']={};destination=await geocode(client,g['city'],g['region'],g['country'])
            for side in ('home','away'):
                previous=sorted([e for e in events if g[side+'_id'] in (e['home_id'],e['away_id']) and instant(e['start'])<instant(g['start'])],key=lambda e:instant(e['start']))
                last=previous[-1] if previous else None
                origin=await geocode(client,last['city'],last['region'],last['country']) if last else None
                g['travel'][side]={'km':round(haversine(origin,destination)) if origin and destination else None,
                    'rest_hours':round((instant(g['start'])-instant(last['start'])).total_seconds()/3600,1) if last else None,
                    'from':last['city'] if last else None,'previous_start':last['start'] if last else None,
                    'method':'City-to-city great-circle estimate; start-to-start rest, not actual itinerary'}
            g['weather']={'status':'Indoor venue' if g['indoor'] else 'Unavailable','temperature_c':None,'wind_kmh':None,'source':None}
            if sport=='nfl' and g['indoor'] is False and destination and instant(g['start'])>=datetime.now(timezone.utc):
                body,werr=await optional(client,'https://api.open-meteo.com/v1/forecast',{'latitude':destination[0],'longitude':destination[1],
                    'hourly':'temperature_2m,wind_speed_10m','timezone':'UTC','forecast_days':16})
                hourly=(body or {}).get('hourly',{});hour=instant(g['start']).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:00')
                if hour in hourly.get('time',[]):
                    ix=hourly['time'].index(hour)
                    g['weather']={'status':'Kickoff-hour city forecast','temperature_c':hourly['temperature_2m'][ix],
                        'wind_kmh':hourly['wind_speed_10m'][ix],'source':'Open-Meteo forecast; city location, not stadium sensor',
                        'asof':datetime.now(timezone.utc).isoformat()}
        await attach_odds(client,games,sport)
        await sportsdata_context(client,games,sport,day)
    return games
