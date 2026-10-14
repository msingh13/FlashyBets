"""Scheduled static publishing with durable, public model state (no server required)."""
import asyncio,json,os,tempfile
from datetime import date,timedelta
from pathlib import Path
from app import service,store,picks,learning,validation
TABLES=('forecasts','cards','model_versions','model_checks','updates')

def restore(path,db):
    if not path.exists():return
    data=json.loads(path.read_text())
    if data.get('schema')!=1:raise ValueError('Unsupported model state; refusing to reset history')
    with store.connect(db) as c:
        for table in TABLES:
            columns=[row['name'] for row in c.execute(f'PRAGMA table_info({table})')]
            for row in data['tables'].get(table,[]):
                if set(row)!=set(columns):raise ValueError('Invalid state columns')
                if table in ('forecasts','cards') and row['mode']!='live':continue
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

async def publish(out,state,db):
    restore(state,db);service.CACHE.clear();service.LOCKS.clear()
    await service.tick('live',db)
    current=service.today();days=[(date.fromisoformat(current)+timedelta(days=i)).isoformat() for i in range(7)]
    errors=[];available={s:[] for s in service.MODELS}
    for sport in service.MODELS:
        for day in days:
            try:
                board=await service.board(sport,day,'live',path=db)
                write(out/sport/(day+'.json'),public_board(board))
                write(out/sport/(day+'-favorites.json'),picks.favorites(sport,day,'live',db))
                available[sport].append(day)
            except Exception:
                errors.append({'sport':sport,'day':day,'message':'Provider update failed; any prior published snapshot remains unchanged.'})
                if (out/sport/(day+'.json')).exists():available[sport].append(day)
                elif sport=='ucl':
                    reason='Champions League live data is not connected or is unavailable. No real fixtures or predictions have been fabricated.'
                    write(out/sport/(day+'.json'),{'games':[],'updated':None,'refresh_seconds':600,'warning':reason})
                    write(out/sport/(day+'-favorites.json'),{'moneylines':[],'totals':[],'btts':[],'card':None,'reason':reason})
                    available[sport].append(day)
        ledger=store.ledger(sport,'live',db);ledger['cards']=picks.settled_cards(sport,'live',db);ledger['learning']=learning.status(sport,'live',db);ledger['validation']=validation.report(sport,'live',db)
        write(out/(sport+'-tracker.json'),ledger)
    save(state,db)
    write(out/'manifest.json',{'generated':store.now(),'today':current,'dates':available,'errors':errors,'cadence_minutes':10})
    print(f'Published scheduled snapshots; {len(errors)} provider updates failed.')

if __name__=='__main__':
    out=Path(os.getenv('PUBLISH_DIR','../frontend/public/data'));state=Path(os.getenv('MODEL_STATE','../work/model-state.json'))
    with tempfile.TemporaryDirectory() as tmp:asyncio.run(publish(out,state,str(Path(tmp)/'model.db')))
