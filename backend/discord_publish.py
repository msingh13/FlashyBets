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
    start=instant(p['start']).strftime('%Y-%m-%d %H:%M UTC')
    sport=p.get('sport','').upper()
    return f"{sport} {p.get('away','?')} at {p.get('home','?')} ({start}): {p.get('label','Selection')}"

def slip(legs,bot_id,parlay=False):
    if not bot_id.isdigit():raise ValueError('GAMBLY_BOT_USER_ID must be a numeric Discord user ID')
    action='Create a bet365 parlay with these selections:' if parlay else 'Create bet365 straight-bet slips for these selections:'
    return f"<@{bot_id}> {action}\n"+'\n'.join(label(p) for p in legs)

def plans(data,state,now,bot_id=""):
    state.setdefault("tracker",{})
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
            prepared=[dict(p,sport=p.get('sport',c.get('sport',''))) for p in legs]
            content=slip(prepared,bot_id,parlay=kind=='favorites')
            result.append((key,content,{'legs':[p['game_key']+'|'+p['side'] for p in legs],
                                      'day':c['day'],'selections':prepared}))
    # Track outcomes silently. Discord receives only mention + slip messages.
    for key,posted in state['posted'].items():
        if key not in known or key.startswith('result:'):continue
        c=known[key];selected=set(posted.get('legs',[]))
        tracked=[]
        for p in c.get('legs',[]):
            if p['game_key']+'|'+p['side'] not in selected:continue
            tracked.append({'game_key':p['game_key'],'side':p['side'],'label':p.get('label'),
                            'outcome':p.get('outcome'),'final':p.get('final')})
        state['tracker'][key]={'day':c['day'],'legs':tracked,
          'wins':sum(p['outcome']=='win' for p in tracked),
          'losses':sum(p['outcome']=='loss' for p in tracked),
          'pushes':sum(p['outcome']=='push' for p in tracked),
          'pending':sum(p['outcome'] is None for p in tracked)}
    return result

def send(url,content):
    # Do not echo request objects or errors: they can contain the secret webhook URL.
    body=json.dumps({'content':content[:1990],'allowed_mentions':{'parse':[],'users':[os.environ['GAMBLY_BOT_USER_ID']] if os.getenv('GAMBLY_BOT_USER_ID','').isdigit() else []},'username':'FlashyBets'}).encode()
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
    bot_id=os.getenv('GAMBLY_BOT_USER_ID','')
    if not bot_id.isdigit():print('Discord skipped: configure GAMBLY_BOT_USER_ID before posting.');return
    data=Path(os.getenv('PUBLISH_DIR','../frontend/public/data'));path=Path(os.environ['DISCORD_STATE'])
    state=read(path,{'posted':{}})
    jobs=plans(data,state,datetime.now(timezone.utc),bot_id)
    for key,content,record in jobs:
        send(url,content);state['posted'][key]=record
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
        time.sleep(.5)
    # Save tracker changes even when there are no new announcements.
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,sort_keys=True));temp.replace(path)
    print(f'Discord delivery complete: {len(jobs)} new messages. Existing posts were not repeated.')
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
