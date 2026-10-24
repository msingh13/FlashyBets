"""Public lineup/goalie facts and optional authenticated X news. No sentiment inputs."""
import json,re,os
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .store import instant
CACHE={}
def nba_abbr(s):return {'SA':'SAS','GS':'GSW','NO':'NOP','NY':'NYK','PHO':'PHX'}.get(s,s)

def rotowire(html,day):
    soup=BeautifulSoup(html,'html.parser');main=soup.select_one('main[data-gamedate]')
    if not main or main.get('data-gamedate')!=day:raise ValueError('RotoWire date mismatch')
    rows=[]
    for card in main.select('.lineup.is-nba'):
        row={}
        for side,cls in [('home','is-home'),('away','is-visit')]:
            team=card.select_one('.lineup__team.'+cls+' .lineup__abbr');ul=card.select_one('ul.lineup__list.'+cls)
            if not team or not ul:break
            status=ul.select_one('.lineup__status');confirmed=bool(status and 'is-confirmed' in status.get('class',[]))
            players=ul.select('li.lineup__player');starters=[];injuries=[]
            for index,li in enumerate(players):
                a=li.select_one('a[title]');pos=li.select_one('.lineup__pos');inj=li.select_one('.lineup__inj')
                if not a:continue
                name=a['title'];position=pos.get_text(strip=True) if pos else None
                if index<5:
                    starters.append({'name':name,'position':position,'confirmed':confirmed,'status':'Confirmed' if confirmed else 'Expected'})
                elif inj:injuries.append({'name':name,'position':position,'status':{'Doubt':'Doubtful','Ques':'Questionable'}.get(inj.get_text(strip=True),inj.get_text(strip=True)),'report':'RotoWire availability listing','reported_at':None,'url':'https://www.rotowire.com'+a.get('href','')})
            # Only complete, unique five-player units can establish a lineup.
            if len(starters)!=5 or len({p['name'] for p in starters})!=5:starters=[]
            row[side]={'abbr':nba_abbr(team.get_text(strip=True)),'starters':starters,'injuries':injuries}
        if len(row)==2:rows.append(row)
    return rows

def faceoff(html,day):
    soup=BeautifulSoup(html,'html.parser');script=soup.find('script',id='__NEXT_DATA__')
    if not script:raise ValueError('Daily Faceoff structured page unavailable')
    data=json.loads(script.string or script.get_text())['props']['pageProps'];rows=data.get('data',[])
    return [r for r in rows if r.get('date')==day and r.get('dateGmt')]

async def page(client,url):
    old=CACHE.get(url);now=datetime.now(timezone.utc)
    if old and (now-old[0]).total_seconds()<300:return old[1]
    r=await client.get(url,headers={'User-Agent':'FlashyBets/1.0 (+https://msingh13.github.io/FlashyBets/)'});r.raise_for_status()
    if len(r.content)>2500000:raise ValueError('Unexpected page size')
    CACHE[url]=(now,r.text);return r.text

async def attach(client,games,sport,day):
    current=datetime.now(timezone.utc).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    if sport not in ('nba','nhl') or day!=current:return
    url='https://www.rotowire.com/basketball/nba-lineups.php' if sport=='nba' else 'https://www.dailyfaceoff.com/starting-goalies/'+datetime.fromisoformat(day).strftime('%m-%d-%Y')
    source='RotoWire' if sport=='nba' else 'Daily Faceoff';fetched=datetime.now(timezone.utc).isoformat()
    try:rows=(rotowire if sport=='nba' else faceoff)(await page(client,url),day);error=None
    except Exception:rows=[];error=source+' unavailable or page format changed'
    for g in games:
        g['personnel_sources']=[{'name':source,'url':url,'fetched':fetched,'status':error or 'No matching report'}]
        g['news_connection']='X / Underdog not connected · API credentials required'
        if g['state']!='pre':
            g['personnel_sources'][0]['status']='Post-start fixture · not used for a new forecast'
            continue
        if error:continue
        if sport=='nba':
            match=next((r for r in rows if r['home']['abbr']==nba_abbr(g['home_abbr']) and r['away']['abbr']==nba_abbr(g['away_abbr'])),None)
        else:
            from .providers import abbr
            match=next((r for r in rows if abbr(r.get('homeTeamAbbreviation'),'nhl')==g['home_abbr'] and abbr(r.get('awayTeamAbbreviation'),'nhl')==g['away_abbr'] and abs((instant(r['dateGmt'])-instant(g['start'])).total_seconds())<300),None)
        if not match:continue
        for side in ('home','away'):
            if sport=='nba':
                starters=match[side]['starters']
                known={p['name'].casefold() for p in g['injuries'].get(side,[])}
                g['injuries'][side].extend(p for p in match[side]['injuries'] if p['name'].casefold() not in known)
            else:
                name=match.get(side+'GoalieName');status=match.get(side+'NewsStrengthName') or 'Unconfirmed'
                reported=match.get(side+'NewsCreatedAt');valid=bool(reported and instant(reported)<=datetime.now(timezone.utc) and 0<=(instant(g['start'])-instant(reported)).total_seconds()<=172800)
                starters=[{'name':name,'confirmed':status=='Confirmed' and valid,'status':status if status!='Confirmed' or valid else 'Stale / invalid confirmation','reported_at':reported,'source_url':match.get(side+'NewsSourceUrl'),'source':match.get(side+'NewsSourceName')}] if name else []
                previous=g.get(side+'_starters',[])
                if starters and starters[0]['confirmed'] and any(p.get('confirmed') and p['name'].casefold()!=name.casefold() for p in previous):
                    starters[0].update(confirmed=False,status='Conflicting reports · Daily Faceoff '+status)
            if starters:g[side+'_starters']=starters
        g['lineup_source']=source+' public lineup report · Expected/Likely is not Confirmed'
        g['personnel_sources'][0]['status']='Report matched to fixture'
    await x_news(client,games)

async def x_news(client,games):
    token=os.getenv('X_BEARER_TOKEN')
    if not token:return
    accounts=[s for s in os.getenv('X_NEWS_ACCOUNTS','Underdog__NBA').split(',') if re.fullmatch(r'[A-Za-z0-9_]{1,15}',s)]
    if not accounts:return
    query='('+' OR '.join('from:'+s for s in accounts)+') -is:retweet'
    try:
        r=await client.get('https://api.x.com/2/tweets/search/recent',params={'query':query,'max_results':20,'tweet.fields':'created_at'},headers={'Authorization':'Bearer '+token});r.raise_for_status();posts=r.json().get('data',[])
        for g in games:
            names={g['home'].split()[-1].lower(),g['away'].split()[-1].lower()}
            names.update(p['name'].lower() for side in ('home','away') for p in g.get('injuries',{}).get(side,[]))
            g['news_links']=[{'url':'https://x.com/i/web/status/'+p['id'],'reported_at':p.get('created_at'),'label':'Source update · verify lineup report'} for p in posts if any(n in p.get('text','').lower() for n in names)][:4]
            g['news_connection']='Authenticated X feed · news context only; no sentiment or automatic player penalties'
    except Exception:
        for g in games:g['news_connection']='X feed unavailable · no news was inferred'
