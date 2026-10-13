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


def espn_event(id='1',day='2026-10-13',state='pre',name='STATUS_SCHEDULED',period=0):
    return {'id':id,'date':day+'T19:00Z','competitions':[{'status':{'period':period,'type':{'name':name,'state':state,'completed':state=='post'}},'competitors':[
        {'homeAway':'home','score':'2','team':{'id':'h','displayName':'Home','abbreviation':'H'}},
        {'homeAway':'away','score':'1','team':{'id':'a','displayName':'Away','abbreviation':'A'}}]}]}


def test_espn_never_settles_extra_time_or_penalty_final():
    from app.soccer import espn_match
    assert regular_score(espn_match(espn_event(state='post',name='STATUS_FULL_TIME',period=2)))==(2,1)
    e=espn_event(state='post',name='STATUS_FULL_TIME',period=2)
    for t in e['competitions'][0]['competitors']:t['score']={'value':int(t['score'])}
    assert regular_score(espn_match(e))==(2,1)
    for name,period in [('STATUS_FINAL_PEN',5),('STATUS_FULL_TIME',4),('STATUS_FINAL_ET',4)]:
        m=espn_match(espn_event(state='post',name=name,period=period))
        assert m['status']=='UNAVAILABLE' and regular_score(m) is None


def test_keyless_soccer_uses_real_history_without_future_leakage(monkeypatch):
    from app import soccer
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False);soccer.ESPN_CACHE.clear()
    async def get(client,url,params=None,headers=None):
        if url.endswith('scoreboard'):return {'events':[espn_event()]}
        return {'events':[espn_event('old','2026-09-08','post','STATUS_FULL_TIME',2),espn_event('future','2026-10-20','post','STATUS_FULL_TIME',2)]}
    monkeypatch.setattr(soccer.providers,'get',get)
    rows=asyncio.run(soccer.live_games('2026-10-13'));g=rows[0]
    assert len(rows)==1 and g['id']=='espn-1' and g['state']=='pre'
    assert g['sample_sizes']=={'home':1,'away':1}
    assert g['home_rate']==pytest.approx(17/11+.1)
    assert g['domestic_form']['home']['samples']==0
    assert g['source']=='ESPN public Champions League feed'
    assert g['home_odds'] is None and not g['injuries_checked']


def test_keyless_empty_day_and_provider_failure(monkeypatch):
    from app import soccer
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    async def empty(*args,**kwargs):return {'events':[]}
    monkeypatch.setattr(soccer.providers,'get',empty)
    assert asyncio.run(soccer.live_games('2026-10-15'))==[]
    async def failed(*args,**kwargs):raise ValueError('Unavailable')
    monkeypatch.setattr(soccer.providers,'get',failed)
    with pytest.raises(ValueError):asyncio.run(soccer.live_games('2026-10-15'))


def test_lineups_require_event_team_and_eleven_unique_starters():
    from app.soccer import attach_lineups
    g={'id':'espn-1','home_id':'h','away_id':'a','home_starters':[],'away_starters':[]}
    roster={'homeAway':'home','team':{'id':'h'},'roster':[{'starter':True,'athlete':{'id':str(i),'displayName':str(i)}} for i in range(11)]}
    attach_lineups(g,{'header':{'id':'wrong'},'rosters':[roster]});assert not g['home_starters']
    attach_lineups(g,{'header':{'id':'1'},'rosters':[roster]});assert len(g['home_starters'])==11
    g['home_starters']=[];roster['roster'][0]['athlete']['id']='1'
    attach_lineups(g,{'header':{'id':'1'},'rosters':[roster]});assert not g['home_starters']


def test_live_clock_and_score_do_not_settle_regulation():
    from app.soccer import espn_match,rows_from_matches
    e=espn_event(state='in',name='STATUS_SECOND_HALF',period=2)
    e['competitions'][0]['status']['displayClock']="74'"
    e['competitions'][0]['status']['type']['description']='Second Half'
    m=espn_match(e)
    assert regular_score(m) is None
    g=rows_from_matches([m],'2026-10-13','ESPN','https://www.espn.com/')[0]
    assert g['state']=='in' and g['clock']=="74'" and g['display_home_score']==2 and g['display_away_score']==1
    assert g['home_score'] is None and g['away_score'] is None
