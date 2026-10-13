from fastapi.testclient import TestClient
from datetime import datetime,timedelta,timezone
from app.main import app
from app import service
import pytest

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr('app.main.DB',str(tmp_path/'test.db'))
    service.CACHE.clear();service.LOCKS.clear()
    return TestClient(app)

def day():return (datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
def test_dashboard_and_history(client):
    r=client.get('/api/games',params={'day':day()}).json()
    assert r['mode']=='demo' and len(r['games'])==5
    g=r['games'][0]
    assert g['markets']['home']['no_vig']+g['markets']['away']['no_vig']==1
    assert len(client.get('/api/snapshots/'+g['id']).json())==1
    assert client.get('/api/history').json()['count']==4
    assert client.get('/api/games?sport=mlb').status_code==422
    assert client.get('/api/games?mode=bad').status_code==422

@pytest.mark.parametrize('sport',['nhl','nba','nfl'])
def test_model_tracker_and_no_journal(client,sport):
    client.get('/api/games',params={'day':day(),'sport':sport})
    tracker=client.get('/api/tracker',params={'sport':sport}).json()
    assert 'bets' not in tracker and 'bankroll' not in tracker
    assert set(tracker['metrics'])=={'ml','total'}
    assert tracker['learning']['status']=='Demo · learning disabled'
    assert client.post('/api/bets',json={}).status_code==404
    f=client.get('/api/favorites',params={'sport':sport,'day':day()}).json()
    assert len(f['moneylines'])==5
    assert f['card'] and len(f['card']['legs']) in (4,5)
