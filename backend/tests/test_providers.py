import asyncio
import httpx
import pytest
from app import providers,service
from app.main import app
from fastapi.testclient import TestClient

def test_live_failure_never_falls_back(monkeypatch,tmp_path):
    async def failed(sport,day):raise httpx.ConnectError('offline')
    monkeypatch.setattr(providers,'live_games',failed)
    monkeypatch.setattr('app.main.DB',str(tmp_path/'test.db'));service.CACHE.clear()
    r=TestClient(app).get('/api/games?mode=live&day=2026-10-13')
    assert r.status_code==502 and 'No demo fallback' in r.json()['detail']

def test_provider_team_accents():
    assert providers.normalize('Montréal Canadiens')==providers.normalize('Montreal Canadiens')

def test_city_distance_and_local_day():
    assert providers.haversine((45,0),(45,0))==0
    assert providers.haversine((0,0),(0,1))==pytest.approx(111.195,rel=.001)
    assert providers.localday('2026-10-14T01:00:00Z')=='2026-10-13'

def test_odds_same_event_and_missing_provider(monkeypatch):
    class Client:
        async def get(self,url,**kwargs):
            return httpx.Response(200,json=[{'home_team':'Montréal Canadiens','away_team':'Toronto Maple Leafs',
                'commence_time':'2026-10-13T23:00:00Z','bookmakers':[{'key':'draftkings','title':'DraftKings','last_update':'2026-10-13T22:00:00Z',
                'markets':[{'key':'h2h','outcomes':[{'name':'Montreal Canadiens','price':-120},{'name':'Toronto Maple Leafs','price':100}]},
                {'key':'totals','outcomes':[{'name':'Over','point':6.5,'price':-110},{'name':'Under','point':6.5,'price':-110}]}]}]}],request=httpx.Request('GET',url))
    monkeypatch.setenv('ODDS_API_KEY','mock');monkeypatch.delenv('ODDS_BOOKMAKER',raising=False)
    g={'home':'Montreal Canadiens','away':'Toronto Maple Leafs','start':'2026-10-13T23:00:00Z','provider_errors':[]}
    asyncio.run(providers.attach_odds(Client(),[g],'nhl'))
    assert g['home_odds']==-120 and g['line']==6.5 and g['odds_updated']
    g2={'home':g['home'],'away':g['away'],'start':'2026-10-14T23:00:00Z','provider_errors':[]}
    asyncio.run(providers.attach_odds(Client(),[g2],'nhl'))
    assert 'home_odds' not in g2
