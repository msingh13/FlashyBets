import asyncio,json
from datetime import datetime,timedelta,timezone
import pytest
from app import store,service,providers
from app.demo import games
from app.models import NBAModel,NFLModel

def future():return (datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
def fixture(sport='nhl'):
    return service.enrich(games(sport,future())[0])
@pytest.mark.parametrize('sport',['nhl','nba','nfl'])
def test_probability_mass(sport):
    p=fixture(sport)['prediction']
    assert p['home']+p['away']+p['ml_push']==pytest.approx(1)
    assert p['over']+p['under']+p['push']==pytest.approx(1)

def test_nba_symmetry_and_integer_push():
    p=NBAModel().predict(114,114,228)
    assert p['home']==pytest.approx(.5)
    assert p['push']>0 and p['tie']==0

def test_nfl_tie_probability_and_drive_support():
    p=NFLModel().predict(22,22,44)
    assert p['home']==pytest.approx(p['away'])
    assert p['ml_push']>0
    assert sum(x['probability'] for x in p['distribution'])==pytest.approx(1)

def test_immutable_forecast_and_settlement(tmp_path):
    db=str(tmp_path/'test.db');g=fixture();old=g['prediction']['home']
    assert store.capture(g,db)
    g['prediction']['home']=.99
    assert not store.capture(g,db)
    assert store.previous(g,db)['prediction']['home']==old
    g.update(state='post',home_score=4,away_score=2)
    store.settle(g,db);store.settle(g,db)
    result=store.ledger('nhl','demo',db)
    assert result['metrics']['ml']['wins']+result['metrics']['ml']['losses']==1
    assert result['metrics']['ml']['priced']==1

def test_no_postgame_forecast(tmp_path):
    g=fixture();g['start']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    assert not store.capture(g,str(tmp_path/'test.db'))
    g['state']='post';assert not store.capture(g,str(tmp_path/'test.db'))

def test_missing_context_never_recommends():
    g=fixture();assert not g['context']['ready'] and not g['recommendations']
    assert g['context']['adjustments']=={'home':0.,'away':0.}

def test_tracker_tick_records_and_settles_without_browser(monkeypatch,tmp_path):
    db=str(tmp_path/'test.db');service.CACHE.clear();service.LOCKS.clear()
    calls=[]
    async def fetched(sport,day):
        calls.append(sport);g=games(sport,future())[0];g['mode']='live'
        return [g]
    monkeypatch.setattr(providers,'live_games',fetched)
    asyncio.run(service.tick('live',db))
    assert set(calls)=={'nhl','nba','nfl'}
    g=games('nhl',future())[0];g['mode']='live';g.update(state='post',home_score=3,away_score=2)
    store.settle(g,db)
    assert store.ledger('nhl','live',db)['forecasts'][0]['result']['home_score']==3

def test_nfl_playoff_adapter_withholds_forecast():
    g=games('nfl',future())[0];g['season_type']=3
    service.enrich(g)
    assert g['prediction'] is None and not g['recommendations']

def test_goalie_effect_changes_opponent_rate(tmp_path,monkeypatch):
    g=games('nhl',future())[0]
    for side in ('home','away'):g[side+'_starters'][0]['confirmed']=True
    config={'nhl':{'validated_out_of_sample':True,'evaluation_source':'test-only held-out fixture',
      'asof':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),'starter_impacts':{'Demo starter A':-.2,'Demo starter B':.1},
      'player_impacts':{},'coefficients':{}}}
    path=tmp_path/'config.json';path.write_text(json.dumps(config));monkeypatch.setenv('MODEL_CONFIG_PATH',str(path))
    service.enrich(g)
    assert g['context']['adjustments']['away']==pytest.approx(-.2)
    assert g['context']['adjustments']['home']==pytest.approx(.1)
