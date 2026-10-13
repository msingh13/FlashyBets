from datetime import datetime,timedelta,timezone
from .data import demo as nhl_demo
from .store import now,instant

def games(sport,day):
    if sport=='nhl':
        rows=nhl_demo(day)
        extra=dict(rows[0]);extra.update(id=f'demo-nhl-{day}-extra',home='Demo Lightning',away='Demo Kraken',home_abbr='TBL',away_abbr='SEA',home_rate=3.8,away_rate=2.7);rows.append(extra)
    else:
        teams={'nba': [('Boston Celtics','BOS','New York Knicks','NYK',117,111,227.5),('Los Angeles Lakers','LAL','Denver Nuggets','DEN',113,119,231.5),('Toronto Raptors','TOR','Cleveland Cavaliers','CLE',109,116,224.),('Miami Heat','MIA','Chicago Bulls','CHI',116,109,224.5),('Phoenix Suns','PHX','Sacramento Kings','SAC',120,111,229.5)],
               'nfl':[('Buffalo Bills','BUF','Kansas City Chiefs','KC',28,24,48.5),('Baltimore Ravens','BAL','Cincinnati Bengals','CIN',27,23,47.),('Green Bay Packers','GB','Detroit Lions','DET',24,28,49.5),('Philadelphia Eagles','PHI','Dallas Cowboys','DAL',28,22,47.5),('San Francisco 49ers','SF','Seattle Seahawks','SEA',27,21,46.5)]}[sport]
        rows=[]
        for i,(h,ha,a,aa,hr,ar,line) in enumerate(teams):
            rows.append({'id':f'demo-{sport}-{day}-{i}','home':h,'away':a,'home_abbr':ha,'away_abbr':aa,
                'start':(datetime.fromisoformat(day+'T23:00:00+00:00')+timedelta(minutes=i*30)).isoformat(),
                'home_rate':hr,'away_rate':ar,'line':line,'home_odds':-120,'away_odds':100,'over_odds':-110,'under_odds':-110,
                'source':'Synthetic demo','odds_source':'Illustrative odds','odds_updated':None,'rates_source':'Synthetic scoring averages'})
    for i,g in enumerate(rows):
        g.update({'sport':sport,'mode':'demo','state':'pre','status':'Scheduled · demo','season_type':2,'venue':'Demo arena' if sport!='nfl' else 'Demo stadium',
          'city':'Demo city','indoor':sport!='nfl','home_score':None,'away_score':None,'rates_asof':day,'provider_errors':[],
          'home_starters':[{'name':'Demo starter A','confirmed':False,'status':'Illustrative only'}],
          'away_starters':[{'name':'Demo starter B','confirmed':False,'status':'Illustrative only'}],
          'lineup_source':'Synthetic fixture, not real players','injuries_checked':True,'injuries_asof':now(),'injuries_source':'Synthetic fixture',
          'injuries':{'home':[{'name':'Demo player','status':'Questionable','report':'Synthetic report, not a real injury.','reported_at':now(),'url':None}], 'away':[]},
          'travel':{'home':{'km':230+i*130,'rest_hours':48,'from':'Demo city A','previous_start':None,'method':'Synthetic'},
                    'away':{'km':870+i*270,'rest_hours':72,'from':'Demo city B','previous_start':None,'method':'Synthetic'}},
          'weather':{'status':'Indoor venue' if sport!='nfl' else 'Synthetic weather','temperature_c':None if sport!='nfl' else 12,
                     'wind_kmh':None if sport!='nfl' else 15,'source':'Synthetic fixture'},'source_url':None})
        if instant(g['start'])+timedelta(hours=4)<datetime.now(timezone.utc):
            g['state']='post';g['status']='Final · synthetic'
            g['home_score']={'nhl':4,'nba':118,'nfl':27}[sport]+i
            g['away_score']={'nhl':3,'nba':111,'nfl':24}[sport]+(i%2)*3
    return rows
