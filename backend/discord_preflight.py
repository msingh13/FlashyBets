"""Decide if overdue picks require a data refresh. Never use webhook credentials."""
import json,os
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo
BASE='https://raw.githubusercontent.com/msingh13/FlashyBets/'
def needs_refresh(state,feed,now,force=False):
    local=now.astimezone(ZoneInfo('America/Toronto'))
    if not force and (local.hour<3 or 'slip:'+local.date().isoformat() in state.get('sent',{})):return False
    try:age=(now-datetime.fromisoformat(feed['updated'].replace('Z','+00:00'))).total_seconds()
    except (KeyError,ValueError,TypeError):return True
    return not 0<=age<=7200
if __name__=='__main__':
    def get(path):
        try:
            with urlopen(BASE+path,timeout=20) as r:return json.load(r)
        except Exception:return {}
    state=get('discord-data/ai-play-tracker.json');feed=get('model-data/data/flashy-ai.json')
    value=needs_refresh(state,feed,datetime.now(timezone.utc),os.getenv('POST_NOW')=='true')
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as out:out.write('refresh='+str(value).lower()+'\n')
    print('Fresh model update needed:',value)
