"""Toronto morning AI slips and results, tracked separately from legacy records."""
import json,os,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
SITE='https://msingh13.github.io/FlashyBets/'
TORONTO=ZoneInfo('America/Toronto')
def instant(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def read(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default
def fresh_state():return {'version':3,'slates':{},'sent':{},'record':{'wins':0,'losses':0,'pushes':0,'pending':0}}
def label(p):
    name=p['label'].replace('**','').strip()
    return name if p['side'] in ('home','away','draw') else f"{p['away']} vs {p['home']} {name}"
def slip(legs,bot_id='',parlay=False):return '\n'.join(label(p) for p in legs)
def sync(state,feed):
    actual={(p['game_key'],p['side']):p for c in feed.get('days',[]) for p in c.get('legs',[])}
    for slate in state['slates'].values():
        for p in slate['legs']:
            latest=actual.get((p['game_key'],p['side']))
            if latest and latest.get('outcome') in ('win','loss','push'):
                p['outcome']=latest['outcome'];p['final']=latest.get('final')
    all_legs=[p for s in state['slates'].values() for p in s['legs']]
    state['record']={key:sum(p.get('outcome')==outcome for p in all_legs) for key,outcome in [('wins','win'),('losses','loss'),('pushes','push'),('pending',None)]}
def prepare(state,feed,now,force=False):
    local=now.astimezone(TORONTO);day=local.date().isoformat();sync(state,feed)
    if local.hour==3 or force:
        key='slip:'+day
        if key in state['sent']:return None
        # Stale snapshots cannot create a new prospective slip.
        updated=feed.get('updated')
        if not updated or not 0<=(now-instant(updated)).total_seconds()<=7200:raise RuntimeError('AI snapshot is stale; no picks sent')
        card=state['slates'].get(day) or next((c for c in feed.get('days',[]) if c['day']==day),None)
        legs=[];seen=set()
        for p in (card or {}).get('legs',[]):
            if p['game_key'] in seen or p.get('current_warning') or p.get('outcome') or instant(p['start'])<=now:continue
            if p.get('conditional',p.get('probability',0))<.60:continue
            if p['side'] in ('home','away','draw') and p.get('probability',0)<=.536:continue
            seen.add(p['game_key']);legs.append(dict(p,outcome=None))
            if len(legs)==3:break
        content=slip(legs) if legs else 'No AI play today.'
        return key,content,{'day':day,'legs':legs}
    if local.hour==2:
        key='results:'+day
        if key in state['sent']:return None
        previous=(local.date()-timedelta(days=1)).isoformat();slate=state['slates'].get(previous)
        lines=[f"AI Play results — {previous}"]
        legs=(slate or {}).get('legs',[])
        if legs:
            lines += [MARKS.get(p.get('outcome'),'⏳')+' '+label(p) for p in legs]
            lines += ['',result_summary(legs)]
        else:lines.append('No tracked plays.')
        record=state['record'];lines.append(f"Running AI Play {record['wins']}-{record['losses']}")
        if record['pushes']:lines.append(f"Pushes: {record['pushes']}")
        if record['pending']:lines.append(f"Pending: {record['pending']}")
        return key,'\n'.join(lines),None
    return None

SOCCER=('ucl','epl','laliga','ligue1','bundesliga','seriea')
def top_plans(state,feeds,now,force=False,football=''):
    local=now.astimezone(TORONTO)
    if local.hour!=3 and not force:return []
    day=local.date().isoformat();jobs=[]
    groups=[('NBA',('nba',)),('NHL',('nhl',)),('NFL',('nfl',)),('SOCCER',SOCCER)]
    if football=='ncaaf':groups.insert(3,('CFB',('ncaaf',)))
    for title,leagues in groups:
        key='top:'+title+':'+day
        if key in state['sent']:continue
        options=[];seen=set()
        for league in leagues:
            for p in feeds.get(league,{}).get('moneylines',[]):
                if p.get('current_warning') or p.get('outcome') or instant(p['start'])<=now:continue
                if p['game_key'] in seen or p.get('probability',0)<=.536:continue
                seen.add(p['game_key']);options.append(dict(p,sport=league))
        options.sort(key=lambda p:-p.get('probability',0))
        legs=options[:5]
        if not legs:continue
        text=title+' TOP ML\n'+(slip(legs) if legs else 'No upcoming selections today.' if any(league in feeds for league in leagues) else 'Selections currently unavailable.')
        jobs.append((key,text,{'day':day,'sport':title,'legs':legs}))
    return jobs

THEMES={'NBA':('🏀',0xF59E0B),'NHL':('🏒',0x38BDF8),'NFL':('🏈',0x22C55E),
        'CFB':('🏟️',0xA78BFA),'SOCCER':('⚽',0x14B8A6)}
def card_message(key,content,slate,record):
    if key.startswith('recap:'):
        sport=slate['sport'];icon,color=THEMES.get(sport,('🏁',0xE5E7EB))
        return {'embeds':[{'title':f'{icon} '+('GRAND TOTAL' if sport=='TOTAL' else sport+' • RESULTS'),'description':slate['day']+'\n\n'+content,'color':color}]}
    if key.startswith('results:'):
        return {'embeds':[{'title':'⚡ FLASHYBET • RESULTS','description':content,
                          'color':0xF5C542,'footer':{'text':'Only announced AI plays count toward this record'}}]}
    ai=key.startswith('slip:');sport=(slate or {}).get('sport','')
    icon,color=('⚡',0xF5C542) if ai else THEMES[sport]
    title='⚡ FLASHYBET PLAY OF THE DAY' if ai else f'{icon} {sport} • TOP MONEYLINES'
    legs=(slate or {}).get('legs',[]);fields=[]
    for i,p in enumerate(legs,1):
        pct=p.get('probability',0)*100
        start=instant(p['start']).astimezone(TORONTO).strftime('%I:%M %p').lstrip('0')
        fields.append({'name':f"{i:02d}  {label(p)}",'value':f"{p['away']} vs {p['home']}\n**Model: {pct:.1f}%**  ·  {start} ET",'inline':False})
    embed={'title':title,'color':color,'description':(slate or {}).get('day',''),
           'fields':fields,'footer':{'text':f"TRACKER  {record['wins']} W · {record['losses']} L · {record['pushes']} push · {record['pending']} pending" if ai else 'Moneylines above 53.6% model win probability'}}
    if not legs:embed['description']='No qualifying AI play today.'
    return {'embeds':[embed]}

MARKS={'win':'✅','loss':'❌','push':'↔️',None:'⏳'}
def result_summary(legs):
    w=sum(p.get('outcome')=='win' for p in legs);l=sum(p.get('outcome')=='loss' for p in legs)
    pushes=sum(p.get('outcome')=='push' for p in legs);pending=sum(p.get('outcome') is None for p in legs)
    rate=f'{w/(w+l):.0%}' if w+l else '—'
    text=f'**{w} ✅ / {l} ❌ | {rate} Win Rate**'
    if pushes:text+=f' · {pushes} push'
    if pending:text+=f' · {pending} pending'
    return text

def sync_top(state,trackers):
    actual={}
    for tracker in trackers.values():
        for g in tracker.get('forecasts',[]):
            for m in g.get('markets',[]):
                if m.get('outcome') in ('win','loss','push'):actual[(g['game_key'],m['name'])]=(m['outcome'],g.get('result'))
    for slate in state.get('top_slates',{}).values():
        for p in slate['legs']:
            result=actual.get((p['game_key'],p['side']))
            if result:p['outcome'],p['final']=result

def recap_jobs(state,now):
    local=now.astimezone(TORONTO)
    if local.hour!=2:return []
    day=local.date().isoformat();previous=(local.date()-timedelta(days=1)).isoformat();jobs=[];all_legs=[]
    for title in ('NBA','NHL','NFL','CFB','SOCCER'):
        slate=next((v for v in state.get('top_slates',{}).values() if v['day']==previous and v['sport']==title),None)
        if not slate or not slate['legs']:continue
        legs=slate['legs'];all_legs+=legs;key='recap:'+title+':'+day
        if key in state['sent']:continue
        text='\n'.join(MARKS.get(p.get('outcome'),'⏳')+' '+label(p) for p in legs)+'\n\n'+result_summary(legs)
        jobs.append((key,text,{'sport':title,'day':previous,'legs':[]}))
    ai=state['slates'].get(previous,{}).get('legs',[]);all_legs+=ai
    unique={}
    for p in all_legs:
        identity=(p['game_key'],p['side'],p.get('line') if p['side'] in ('over','under') else None)
        if identity not in unique or p.get('outcome') is not None:unique[identity]=p
    key='recap:TOTAL:'+day
    if key not in state['sent']:
        legs=list(unique.values());text=result_summary(legs)+'\n'+f"{len(legs)} unique selections · AI + sport lists"
        jobs.append((key,text,{'sport':'TOTAL','day':previous,'legs':[]}))
    return jobs

def send(url,content):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('discord.com','discordapp.com') or not p.path.startswith('/api/webhooks/'):raise RuntimeError('Invalid webhook configuration; value not logged')
    payload=dict(content) if isinstance(content,dict) else {'content':content}
    serialized=json.dumps(payload).lower()
    if 'http' in serialized or '<@' in serialized or '/betslip' in serialized:raise RuntimeError('Discord message contains prohibited source or command text')
    payload.update(allowed_mentions={'parse':[]},username='FlashyBets')
    body=json.dumps(payload).encode()
    for attempt in range(3):
        try:
            req=Request(url,data=body,headers={'Content-Type':'application/json','User-Agent':'FlashyBets-Discord/1.0'},method='POST')
            with urlopen(req,timeout=20) as r:
                if r.status not in (200,204):raise RuntimeError('Discord rejected delivery')
            return
        except HTTPError as e:
            if e.code==429 and attempt<2:
                try:delay=min(30,max(1,float(json.loads(e.read()).get('retry_after',2))))
                except Exception:delay=2
                time.sleep(delay);continue
            raise RuntimeError(f'Discord delivery failed (HTTP {e.code}); secret not logged') from None
        except URLError:raise RuntimeError('Discord connection failed; secret not logged') from None
    raise RuntimeError('Discord rate limit persisted')
def main():
    path=Path(os.environ['DISCORD_STATE']);state=read(path,fresh_state())
    if state.get('version')!=3:raise RuntimeError('Use a new tracker state file for the new AI series')
    with urlopen(SITE+'data/flashy-ai.json',timeout=30) as r:feed=json.load(r)
    now=datetime.now(timezone.utc);force=os.getenv('POST_NOW','false').lower()=='true'
    if os.getenv('REPLACE_POSTS','false').lower()=='true':
        today=now.astimezone(TORONTO).date().isoformat()
        state['sent']={k:v for k,v in state['sent'].items() if not (k=='slip:'+today or k.startswith('top:') and k.endswith(':'+today))}
        state['top_slates']={k:v for k,v in state.get('top_slates',{}).items() if v['day']!=today}
    job=prepare(state,feed,now,force);jobs=[job] if job else []
    if now.astimezone(TORONTO).hour==3 or force:
        # One freshness check gates all pick lists.
        if not feed.get('updated') or not 0<=(now-instant(feed['updated'])).total_seconds()<=7200:
            raise RuntimeError('Snapshot is stale; no pick lists sent')
        day=now.astimezone(TORONTO).date().isoformat();feeds={}
        for sport in ('nba','nhl','nfl','ncaaf')+SOCCER:
            try:
                with urlopen(SITE+f'data/{sport}/{day}-favorites.json',timeout=20) as r:feeds[sport]=json.load(r)
            except (HTTPError,URLError):print(f'{sport}: current favorites unavailable; no fabricated selections')
        jobs+=top_plans(state,feeds,now,force,os.getenv('FOOTBALL_LEAGUE',''))
    if now.astimezone(TORONTO).hour==2 and not force:
        trackers={}
        sports={p.get('sport') for v in state.get('top_slates',{}).values() for p in v['legs'] if p.get('sport')}
        for sport in sports:
            try:
                with urlopen(SITE+f'data/{sport}-tracker.json',timeout=20) as r:trackers[sport]=json.load(r)
            except (HTTPError,URLError):print(f'{sport}: results unavailable; keeping pending')
        sync_top(state,trackers);jobs+=recap_jobs(state,now)
    for key,content,slate in jobs:
        url=os.getenv('DISCORD_WEBHOOK_URL','')
        if not url:raise RuntimeError('DISCORD_WEBHOOK_URL is not configured')
        if key.startswith('slip:'):content='AI PLAY OF THE DAY\n'+content
        send(url,card_message(key,content,slate,state['record']))
        if slate is not None:
            if key.startswith('slip:'):state['slates'].setdefault(slate['day'],slate)
            elif key.startswith('top:'):state.setdefault('top_slates',{})[key]=slate
        state['sent'][key]=now.isoformat();sync(state,feed)
        print('Discord accepted a plain selection message. No link, mention or command included.')
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
        time.sleep(.5)
    if not jobs:print('Tracker refreshed; no new message due.')
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
