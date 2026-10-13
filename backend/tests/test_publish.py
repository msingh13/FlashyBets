import asyncio,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from app import service,store,providers
from app.demo import games
from publish import publish,restore,save

def test_static_publication_and_durable_history(tmp_path,monkeypatch):
    day=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
    monkeypatch.setattr(service,'today',lambda:day)
    async def fetch(sport,selected):
        rows=games(sport,selected)
        for g in rows:g['mode']='live'
        return rows
    monkeypatch.setattr(providers,'live_games',fetch)
    out=tmp_path/'data';state=tmp_path/'state.json';db=str(tmp_path/'one.db')
    asyncio.run(publish(out,state,db))
    first=store.ledger('nhl','live',db)
    second=str(tmp_path/'two.db');restore(state,second)
    assert store.ledger('nhl','live',second)['forecasts']==first['forecasts']
    assert len(json.loads((out/'manifest.json').read_text())['dates']['nfl'])==7
    board=json.loads((out/'nhl'/(day+'.json')).read_text())
    assert board['mode']=='live' and 'distribution' not in board['games'][0]['prediction']
    assert set(json.loads(state.read_text())['tables'])=={'forecasts','cards','model_versions','model_checks','updates'}
    async def fail(*args):raise ValueError('provider failed')
    monkeypatch.setattr(providers,'live_games',fail)
    asyncio.run(publish(out,state,second))
    assert len(json.loads((out/'manifest.json').read_text())['errors'])==28
    assert json.loads((out/'nhl'/(day+'.json')).read_text())==board
    assert store.ledger('nhl','live',second)['forecasts']==first['forecasts']

def test_invalid_state_refuses_silent_reset(tmp_path):
    state=tmp_path/'bad.json';state.write_text('{"schema":2}')
    with pytest.raises(ValueError):restore(state,str(tmp_path/'db'))
