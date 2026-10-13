"""Champions League 90-minute markets; never settle from extra-time or penalties."""
import math,os
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
    if not token:raise ValueError('Champions League needs FOOTBALL_DATA_TOKEN from football-data.org; no live forecasts are fabricated.')
    year=int(day[:4])-(int(day[5:7])<7)
    cached=CACHE.get(year)
    if cached and (datetime.now(timezone.utc)-cached[0]).total_seconds()<600:matches=cached[1]
    else:
        async with httpx.AsyncClient(timeout=25) as client:
            body=await providers.get(client,'https://api.football-data.org/v4/competitions/CL/matches',{'season':year},headers={'X-Auth-Token':token})
        matches=body.get('matches',[]);CACHE[year]=(datetime.now(timezone.utc),matches)
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
            home_id=h['id'],away_id=a['id'],start=m['utcDate'],state=state,status=m['status'],season_type=2,venue=m.get('venue') or 'Venue not supplied',
            home_score=score[0] if state=='post' else None,away_score=score[1] if state=='post' else None,
            home_rate=(hf+aa)/2+.10,away_rate=max(.1,(af+ha)/2-.10),sample_sizes={'home':hn,'away':an},
            line=None,home_odds=None,away_odds=None,draw_odds=None,over_odds=None,under_odds=None,btts_yes_odds=None,btts_no_odds=None,
            source='football-data.org · Champions League',source_url='https://www.football-data.org/',odds_source=None,odds_updated=None,
            rates_source='Prior completed Champions League 90-minute scores; 10-match prior at 1.5 goals per team',rates_asof=store.now(),
            home_starters=[],away_starters=[],lineup_source='Confirmed starting XIs unavailable',injuries={'home':[],'away':[]},injuries_checked=False,injuries_asof=None,
            injuries_source='Injury coverage unavailable',travel={'home':{'km':None,'rest_hours':None,'from':None,'method':'Unavailable'},'away':{'km':None,'rest_hours':None,'from':None,'method':'Unavailable'}},
            indoor=False,weather={'status':'Weather unavailable','temperature_c':None,'wind_kmh':None,'source':None},
            provider_errors=['Starting XIs, injuries, domestic form, travel and weather are not supplied by this adapter. Baseline only.'])
        rows.append(g)
    return rows
