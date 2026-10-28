import asyncio,json
import pytest
from app import soccer,service,store,spotlight
from app.models import CollegeFootballModel
from app.sports import SOCCER
from app.demo import games

@pytest.mark.parametrize('sport',list(SOCCER))
def test_soccer_mass_draw_settlement_and_league_identity(tmp_path,sport):
    db=str(tmp_path/'db');g=games(sport,'2099-10-27')[0];g.update(sport=sport,mode='live',state='pre')
    service.enrich(g,db)
    p=g['prediction'];assert p['home']+p['away']+p['draw']==pytest.approx(1)
    assert p['ml_push']==0 and 'draw' in g['markets'] and 'btts_yes' in g['markets']
    store.capture(g,db,at='2099-10-26T12:00Z');g.update(state='post',home_score=1,away_score=1);store.settle(g,db)
    rows=store.ledger(sport,'live',db)['forecasts'];assert len(rows)==1
    home=next(m for m in rows[0]['markets'] if m['name']=='home');assert home['outcome']=='loss'


def test_college_overtime_has_no_final_tie_or_ml_push():
    p=CollegeFootballModel().predict(28,28,56)
    assert p['home']==pytest.approx(.5) and p['away']==pytest.approx(.5)
    assert p['ml_push']==0 and p['tie']==0 and p['over']+p['under']+p['push']==pytest.approx(1)


def test_soccer_provider_routes_correct_league(monkeypatch):
    urls=[]
    async def get(client,url,params=None,headers=None):urls.append(url);return {'events':[]}
    monkeypatch.setattr(soccer.providers,'get',get);monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    for league,(_,slug,_) in SOCCER.items():
        assert asyncio.run(soccer.live_games('2026-10-31',league))==[]
        assert any('/soccer/'+slug+'/scoreboard' in u for u in urls)


def test_spotlight_passes_on_thin_sample_and_large_market_gap(tmp_path):
    db=str(tmp_path/'db');g=games('nba','2026-10-27')[0];g.update(mode='live',state='pre',start='2026-10-27T23:00Z',sample_sizes={'home':1,'away':1})
    service.enrich(g,db);g['prediction'].update(home=.8,away=.2)
    at='2026-10-27T12:00Z';store.capture(g,db,at=at)
    with store.connect(db) as c:c.execute('INSERT INTO snapshots VALUES(?,?,?)',(g['id'],at,json.dumps(g)))
    assert spotlight.build('2026-10-27','live',db,at) is None
