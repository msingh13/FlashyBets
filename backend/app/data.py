from datetime import datetime, timezone, timedelta
import os
import unicodedata
import httpx

TEAMS=[("Toronto Maple Leafs","TOR",3.4,3.05),("Montreal Canadiens","MTL",2.9,3.4),
("New Jersey Devils","NJD",3.35,2.8),("Carolina Hurricanes","CAR",3.3,2.7),
("Boston Bruins","BOS",2.8,2.9),("Florida Panthers","FLA",3.4,2.8),
("Edmonton Oilers","EDM",3.65,3.0),("Los Angeles Kings","LAK",3.0,2.65)]

def demo(day):
    games=[]
    for i in range(4):
        h,a=TEAMS[2*i:2*i+2]
        games.append({"id":f"demo-{day}-{i}","home":h[0],"away":a[0],"home_abbr":h[1],"away_abbr":a[1],
        "start":(datetime.fromisoformat(day+'T23:00:00+00:00')+timedelta(hours=i//2)).isoformat(),"home_rate":(h[2]+a[3])/2*1.04,"away_rate":(a[2]+h[3])/2*.96,
        "goalie_status":"Unconfirmed · demo","source":"demo","odds_source":"Illustrative sportsbook",
        "odds_updated":None,"home_odds":[-145,-110,130,-150][i],"away_odds":[125,-110,-150,130][i],
        "line":[6.5,5.5,6.,6.5][i],"over_odds":-110,"under_odds":-110,"rates_source":"Synthetic team averages"})
    return games

def normalize(name):
    return "".join(c for c in unicodedata.normalize("NFKD",name).casefold() if not unicodedata.combining(c)).strip()

async def live(day):
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.get(f"https://api-web.nhle.com/v1/schedule/{day}");r.raise_for_status()
        schedule=r.json()
        r=await client.get(f"https://api-web.nhle.com/v1/standings/{day}");r.raise_for_status()
        standings={t['teamAbbrev']['default']:t for t in r.json()['standings']}
        odds=[]
        if os.getenv('ODDS_API_KEY'):
            r=await client.get('https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds',params={
            'apiKey':os.environ['ODDS_API_KEY'],'regions':os.getenv('ODDS_REGION','us'),'markets':'h2h,totals','oddsFormat':'american'})
            if r.status_code!=200: raise ValueError(f"Odds provider returned HTTP {r.status_code}")
            odds=r.json()
    games=[]
    for block in schedule.get('gameWeek',[]):
        if block['date']!=day: continue
        for g in block['games']:
            if g.get('gameType')!=2: continue
            h,a=g['homeTeam'],g['awayTeam'];hs,as_=standings.get(h['abbrev']),standings.get(a['abbrev'])
            if not hs or not as_: continue
            # Shrink season averages to a 3.0 goal baseline with 20 prior games.
            def avg(t,key): return (t[key]+60)/(t['gamesPlayed']+20)
            item={"id":str(g['id']),"home":hs['teamName']['default'],"away":as_['teamName']['default'],
            "home_abbr":h['abbrev'],"away_abbr":a['abbrev'],"start":g['startTimeUTC'],
            "home_rate":(avg(hs,'goalFor')+avg(as_,'goalAgainst'))/2*1.04,
            "away_rate":(avg(as_,'goalFor')+avg(hs,'goalAgainst'))/2*.96,"source":"NHL public feed",
            "rates_source":"Season final-score averages; shrunk with 20 prior games (approximation)",
            "goalie_status":"Unconfirmed · no goalie feed configured","odds_source":None,"odds_updated":None,
            "home_odds":None,"away_odds":None,"line":6.5,"over_odds":None,"under_odds":None}
            match=next((o for o in odds if normalize(o['home_team'])==normalize(item['home']) and normalize(o['away_team'])==normalize(item['away']) and o['commence_time'][:10]==g['startTimeUTC'][:10]),None)
            if match:
                book=next((b for b in match['bookmakers'] if b['key']==os.getenv('ODDS_BOOKMAKER','draftkings')),None)
                if book:
                    item['odds_source']=book['title'];item['odds_updated']=book['last_update']
                    for m in book['markets']:
                        outcomes={normalize(o['name']):o for o in m['outcomes']}
                        if m['key']=='h2h' and normalize(item['home']) in outcomes and normalize(item['away']) in outcomes:
                            item['home_odds']=outcomes[normalize(item['home'])]['price'];item['away_odds']=outcomes[normalize(item['away'])]['price']
                        if m['key']=='totals' and 'over' in outcomes and 'under' in outcomes and outcomes['over']['point']==outcomes['under']['point']:
                            item['line']=outcomes['over']['point'];item['over_odds']=outcomes['over']['price'];item['under_odds']=outcomes['under']['price']
            games.append(item)
    return games
