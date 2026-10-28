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
def prepare(state,feed,now):
    local=now.astimezone(TORONTO);day=local.date().isoformat();sync(state,feed)
    if local.hour==6:
        key='slip:'+day
        if key in state['sent']:return None
        # Stale snapshots cannot create a new prospective slip.
        updated=feed.get('updated')
        if not updated or not 0<=(now-instant(updated)).total_seconds()<=7200:raise RuntimeError('AI snapshot is stale; no picks sent')
        card=next((c for c in feed.get('days',[]) if c['day']==day),None)
        legs=[];seen=set()
        for p in (card or {}).get('legs',[]):
            if p['game_key'] in seen or p.get('current_warning') or p.get('outcome') or instant(p['start'])<=now:continue
            if p.get('conditional',p.get('probability',0))<.60:continue
            seen.add(p['game_key']);legs.append(dict(p,outcome=None))
            if len(legs)==3:break
        content=slip(legs) if legs else 'No AI play today.'
        return key,content,{'day':day,'legs':legs}
    if local.hour==3:
        key='results:'+day
        if key in state['sent']:return None
        previous=(local.date()-timedelta(days=1)).isoformat();slate=state['slates'].get(previous)
        lines=[f"AI Play results — {previous}"]
        if slate and slate['legs']:
            for p in slate['legs']:lines.append(label(p)+' — '+(p.get('outcome') or 'pending').upper())
        else:lines.append('No tracked plays.')
        record=state['record'];lines.append(f"AI Play {record['wins']}-{record['losses']}")
        if record['pushes']:lines.append(f"Pushes: {record['pushes']}")
        if record['pending']:lines.append(f"Pending: {record['pending']}")
        return key,'\n'.join(lines),None
    return None

def send(url,content):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('discord.com','discordapp.com') or not p.path.startswith('/api/webhooks/'):raise RuntimeError('Invalid webhook configuration; value not logged')
    if 'http' in content.lower() or '@' in content or '/betslip' in content:raise RuntimeError('Discord message contains prohibited source or command text')
    body=json.dumps({'content':content,'allowed_mentions':{'parse':[]},'username':'FlashyBets'}).encode()
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
    now=datetime.now(timezone.utc);job=prepare(state,feed,now)
    if job:
        url=os.getenv('DISCORD_WEBHOOK_URL','')
        if not url:raise RuntimeError('DISCORD_WEBHOOK_URL is not configured')
        key,content,slate=job;send(url,content)
        if slate is not None:state['slates'][slate['day']]=slate
        state['sent'][key]=now.isoformat();sync(state,feed)
        print('Discord accepted the scheduled message. No source link or mention was included.')
    else:print('Tracker refreshed; no scheduled message due, or already delivered.')
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
