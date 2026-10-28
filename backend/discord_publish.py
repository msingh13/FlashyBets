"""Publish prospective model selections and settlement updates to Discord.
Secrets remain in Actions; only non-secret delivery IDs are persisted.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

SITE='https://msingh13.github.io/FlashyBets/'
def read(path, default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default

def instant(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
def label(p):
    probability=p.get('conditional',p.get('probability',0))
    price=f" | odds {p['odds']:+g}" if p.get('odds') is not None else ' | price unavailable'
    return f"{p.get('away','?')} @ {p.get('home','?')} — **{p.get('label','Selection')}** | model {probability:.1%}{price}"

def plans(data,state,now):
    result=[];today=read(data/'manifest.json',{}).get('today');ai=read(data/'flashy-ai.json',{})
    cards=[]
    for c in ai.get('days',[]):cards.append(('ai',c))
    for path in sorted(data.glob('*-tracker.json')):
        tracker=read(path,{})
        for c in tracker.get('cards',[]):cards.append(('favorites',c))
    # Current favorites also carry the immutable card, with settled outcomes.
    if today:
        for path in sorted(data.glob(f'*/{today}-favorites.json')):
            c=read(path,{}).get('card')
            if c:cards.append(('favorites',c))
    known={}
    for kind,c in cards:
        key=f"{kind}:{c['key']}";known[key]=c
    for key,c in known.items():
        kind=key.split(':',1)[0]
        if c.get('day')!=today:continue
        legs=[p for p in c.get('legs',[]) if not p.get('current_warning') and not c.get('current_warning') and not p.get('outcome') and instant(p['start'])>now]
        if key not in state['posted'] and legs:
            title='Flashy AI · Play of the Day' if kind=='ai' else f"{c.get('sport','').upper()} · Model Favorites"
            body='\n'.join(label(p) for p in legs)
            content=f"**{title} — {today}**\n{body}\n\nExperimental model selections. Prices and lineups can change; these are not guaranteed wins.\n{SITE}"
            result.append((key,content,{'legs':[p['game_key']+'|'+p['side'] for p in legs]}))
    for key,posted in state['posted'].items():
        if key not in known or key.startswith('result:'):continue
        c=known[key]
        for p in c.get('legs',[]):
            leg=p['game_key']+'|'+p['side'];outcome=p.get('outcome')
            identity='result:'+key+':'+leg
            if leg not in posted.get('legs',[]) or outcome not in ('win','loss','push') or identity in state['posted']:continue
            title='Flashy AI result' if key.startswith('ai:') else 'Model Favorites result'
            result.append((identity,f"**{title} · {outcome.upper()}**\n{label(p)}\nOriginal selection: {c['day']}\n{SITE}",{}))
    return result

def send(url,content):
    # Do not echo request objects or errors: they can contain the secret webhook URL.
    body=json.dumps({'content':content[:1990],'allowed_mentions':{'parse':[]},'username':'FlashyBets'}).encode()
    for attempt in range(3):
        req=Request(url,data=body,headers={'Content-Type':'application/json','User-Agent':'FlashyBets-Discord/1.0'},method='POST')
        try:
            with urlopen(req,timeout=20) as response:
                if response.status not in (200,204):raise RuntimeError('Discord rejected the message')
            return
        except HTTPError as e:
            if e.code==429 and attempt<2:
                try:delay=min(30,max(1,float(json.loads(e.read()).get('retry_after',2))))
                except Exception:delay=2
                time.sleep(delay);continue
            raise RuntimeError(f'Discord delivery failed (HTTP {e.code}); no secret was logged') from None
        except URLError:raise RuntimeError('Discord connection failed; no secret was logged') from None
    raise RuntimeError('Discord rate limit persisted')

def main():
    url=os.getenv('DISCORD_WEBHOOK_URL','')
    if not url:print('Discord skipped: repository secret is not configured.');return
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('discord.com','discordapp.com') or not parsed.path.startswith('/api/webhooks/'):
        raise RuntimeError('Invalid Discord webhook configuration; value not logged')
    data=Path(os.getenv('PUBLISH_DIR','../frontend/public/data'));path=Path(os.environ['DISCORD_STATE'])
    state=read(path,{'posted':{}})
    jobs=plans(data,state,datetime.now(timezone.utc))
    # Initial delivery proves the configured channel works, even without eligible picks.
    if 'connected:v1' not in state['posted']:
        jobs.insert(0,('connected:v1',f'**FlashyBets is connected.**\nUpcoming Play of the Day and Model Favorites selections, followed by their results, will post here automatically when available. Updates follow the website refresh cycle.\n{SITE}',{}))
    for key,content,record in jobs:
        send(url,content);state['posted'][key]=record
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
        time.sleep(.5)
    print(f'Discord delivery complete: {len(jobs)} new messages. Existing posts were not repeated.')
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
