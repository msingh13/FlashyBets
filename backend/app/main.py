import os,json,asyncio
from contextlib import asynccontextmanager,suppress
from datetime import date
from pathlib import Path
from typing import Optional,Literal
from fastapi import FastAPI,HTTPException,Query,Request
from fastapi.middleware.cors import CORSMiddleware
from . import store,service
from .history import load
DB=store.DB
@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(service.worker()) if os.getenv('AUTO_REFRESH','1')=='1' else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):await task
app=FastAPI(title='FlashyBets',version='2.0.0',lifespan=lifespan)
origins=set(os.getenv('FRONTEND_ORIGIN','http://localhost:3000').split(','))|{'http://127.0.0.1:3000'}
app.add_middleware(CORSMiddleware,allow_origins=list(origins),allow_methods=['GET'],allow_headers=['Content-Type'])
@app.get('/health')
def health():return {'status':'ok','sports':list(service.MODELS),'auto_refresh':os.getenv('AUTO_REFRESH','1')=='1','interval':service.TTL}
@app.get('/api/games')
async def games(day:Optional[date]=None,mode:Literal['demo','live']='demo',sport:Literal['nhl','nba','nfl']='nhl'):
    try:return await service.board(sport,day.isoformat() if day else service.today(),mode,path=DB)
    except ValueError as e:raise HTTPException(422,str(e))
    except Exception:raise HTTPException(502,'Live provider unavailable. No demo fallback was applied.')
@app.get('/api/history')
def history():
    path=os.getenv('BACKTEST_CSV',str(Path(__file__).parent.parent/'fixtures/history.csv'))
    try:result=load(path)
    except (ValueError,KeyError,OSError) as e:raise HTTPException(422,str(e))
    result['source']='User historical CSV' if os.getenv('BACKTEST_CSV') else 'Synthetic NHL replay · not real historical accuracy'
    return result
@app.get('/api/tracker')
def tracker(sport:Literal['nhl','nba','nfl']='nhl',mode:Literal['demo','live']='demo'):
    from . import picks,learning
    if mode=='demo':service.seed_demo(sport,DB)
    result=store.ledger(sport,mode,DB)
    result['cards']=picks.settled_cards(sport,mode,DB)
    result['learning']=learning.status(sport,mode,DB)
    return result
@app.get('/api/favorites')
def favorites(day:Optional[date]=None,sport:Literal['nhl','nba','nfl']='nhl',mode:Literal['demo','live']='demo'):
    from . import picks
    return picks.favorites(sport,day.isoformat() if day else service.today(),mode,DB)
@app.get('/api/snapshots/{game_id}')
def snapshot(game_id:str):
    with store.connect(DB) as c:rows=c.execute('SELECT payload FROM snapshots WHERE id=? ORDER BY created DESC LIMIT 10',(game_id,)).fetchall()
    return [json.loads(r['payload']) for r in rows]
