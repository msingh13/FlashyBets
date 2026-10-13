import asyncio,math
from datetime import datetime,timedelta,timezone
import pytest
from app.soccer import SoccerModel,regular_score
from app import store,service,picks

def test_three_way_and_btts_probabilities():
    p=SoccerModel().predict(1.5,1.5,2.5)
    assert p['home']==pytest.approx(p['away'])
    assert p['home']+p['draw']+p['away']==pytest.approx(1)
    assert p['btts_yes']==pytest.approx((1-math.exp(-1.5))**2)
    assert p['over']+p['under']==pytest.approx(1)
    assert p['expected_total']==3 and p['ml_push']==0
    with pytest.raises(ValueError):SoccerModel().predict(float('nan'),1,2.5)

def test_regulation_settlement_excludes_extra_time_and_penalties():
    m={'score':{'duration':'PENALTY_SHOOTOUT','fullTime':{'home':6,'away':5},'regularTime':{'home':1,'away':1}}}
    assert regular_score(m)==(1,1)
    assert store.outcome('soccer_home',1,1)=='loss'
    assert store.outcome('soccer_away',1,1)=='loss'
    assert store.outcome('draw',1,1)=='win'
    assert store.outcome('btts_yes',1,1)=='win'
    assert store.outcome('btts_no',0,0)=='win'
    del m['score']['regularTime']
    assert regular_score(m) is None

def test_soccer_record_tracks_draw_btts_and_favorites(tmp_path):
    path=str(tmp_path/'soccer.db');service.CACHE.clear();service.LOCKS.clear()
    day=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
    b=asyncio.run(service.board('ucl',day,'demo',path=path));g=b['games'][0]
    g.update(state='post',home_score=1,away_score=1);store.settle(g,path)
    record=store.ledger('ucl','demo',path)
    row=next(r for r in record['forecasts'] if r['id']==g['id'])
    assert {m['name']:m['outcome'] for m in row['markets']}['draw']=='win'
    assert {m['name']:m['outcome'] for m in row['markets']}['home']=='loss'
    assert record['metrics']['btts']['pending']==4
    favorites=picks.favorites('ucl',day,'demo',path)
    assert len(favorites['btts'])==5
    assert 'Projected' in favorites['moneylines'][0]['summary']
