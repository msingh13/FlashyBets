"""Scheduled static publishing with durable, public model state (no server required)."""
import asyncio,json,os,tempfile
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from app import service,store,picks,learning,validation
from pregame import add_changes, read_json, refresh_targets

TABLES=('forecasts','cards','model_versions','model_checks','updates','daily_plays')

def restore(path,db):
    if not path.exists():return
    data=json.loads(path.read_text())
    if data.get('schema')!=1:raise ValueError('Unsupported model state; refusing to reset history')
    with store.connect(db) as c:
        for table in TABLES:
            columns=[row['name'] for row in c.execute(f'PRAGMA table_info({table})')]
            for row in data['tables'].get(table,[]):
                if set(row)!=set(columns):raise ValueError('Invalid state columns')
                if table in ('forecasts','cards','daily_plays') and row['mode']!='live':continue
                c.execute(f'INSERT OR IGNORE INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',[row[x] for x in columns])

def save(path,db):
    with store.connect(db) as c:
        tables={t:[dict(row) for row in c.execute(f'SELECT * FROM {t}'+(" WHERE mode='live'" if t in ('forecasts','cards') else ''))] for t in TABLES}
    write(path,{'schema':1,'tables':tables})

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,separators=(',',':'),allow_nan=False));tmp.replace(path)

def public_board(board):
    # Distribution arrays are unnecessary on the static dashboard.
    for g in board['games']:
        if g.get('prediction'):g['prediction']={k:v for k,v in g['prediction'].items() if k!='distribution'}
    board['refresh_seconds']=600
    return board

async def publish(out,state,db,scheduled=False):
    current=service.today();days=[(date.fromisoformat(current)+timedelta(days=i)).isoformat() for i in range(7)]
    now=datetime.now(timezone.utc)
    targets=refresh_targets(out,service.MODELS,days,now) if scheduled else None
    if targets == []:
        print('All boards are within their refresh windows.')
        return False
    restore(state,db);service.CACHE.clear();service.LOCKS.clear()
    if targets is not None:
        updated=False
        for sport,day in targets:
            try:
                await publish_board(out,sport,day,db)
                updated=True
            except Exception:
                print(f'{sport} {day}: pregame refresh failed; preserving previous data.')
        if updated:save(state,db)
        return updated
    await service.tick('live',db)
    errors=[];available={s:[] for s in service.MODELS}
    for sport in service.MODELS:
        for day in days:
            try:
                await publish_board(out,sport,day,db)
                available[sport].append(day)
            except Exception:
                errors.append({'sport':sport,'day':day,'message':'Provider update failed; any prior published snapshot remains unchanged.'})
                if (out/sport/(day+'.json')).exists():available[sport].append(day)
                else:
                    reason=sport.upper()+' live data is unavailable. No fixtures or predictions have been fabricated.'
                    write(out/sport/(day+'.json'),{'games':[],'updated':None,'refresh_seconds':600,'warning':reason})
                    write(out/sport/(day+'-favorites.json'),{'moneylines':[],'totals':[],'btts':[],'card':None,'reason':reason})
                    available[sport].append(day)
        from app import news
        try:write(out/(sport+'-news.json'),await news.fetch(sport))
        except Exception:
            if not (out/(sport+'-news.json')).exists():write(out/(sport+'-news.json'),{'articles':[],'injuries':[],'fetched':None,'status':'News provider unavailable'})
        ledger=store.ledger(sport,'live',db);ledger['cards']=picks.settled_cards(sport,'live',db);ledger['learning']=learning.status(sport,'live',db);ledger['validation']=validation.report(sport,'live',db)
        write(out/(sport+'-tracker.json'),ledger)
    from app import spotlight
    spotlight.build(current,'live',db)
    write(out/'flashy-ai.json',spotlight.record('live',db))
    save(state,db)
    write(out/'manifest.json',{'generated':store.now(),'today':current,'dates':available,'errors':errors,'cadence_minutes':120,'near_kickoff_minutes':90,'near_cadence_minutes':10,'full_refresh_at':now.isoformat()})
    print(f'Published scheduled snapshots; {len(errors)} provider updates failed.')
    return True

async def publish_board(out,sport,day,db):
    path=out/sport/(day+'.json')
    board=await service.board(sport,day,'live',path=db)
    add_changes(board,read_json(path))
    favorites=picks.favorites(sport,day,'live',db)
    write(path,public_board(board))
    write(out/sport/(day+'-favorites.json'),favorites)

if __name__=='__main__':
    out=Path(os.getenv('PUBLISH_DIR','../frontend/public/data'));state=Path(os.getenv('MODEL_STATE','../work/model-state.json'))
    with tempfile.TemporaryDirectory() as tmp:
        changed=asyncio.run(publish(out,state,str(Path(tmp)/'model.db'),scheduled=os.getenv('GITHUB_EVENT_NAME')=='schedule' and os.getenv('FORCE_FULL_REFRESH')!='true'))
    if output:=os.getenv('GITHUB_OUTPUT'):
        with open(output,'a') as f:f.write(f'changed={str(changed).lower()}\n')
