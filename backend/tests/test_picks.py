from app import store,service,picks,learning
from app.demo import games
from datetime import datetime,timedelta,timezone

def test_cards_freeze_and_settle(tmp_path):
    db=str(tmp_path/'db');day=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
    gs=games('nba',day)
    for g in gs:service.enrich(g,db);store.capture(g,db)
    card=picks.build('nba',day,'demo',db)
    assert card and len({l['game_key'] for l in card['legs']})==5
    assert 0<card['joint_probability']<min(l['probability'] for l in card['legs'])
    assert picks.build('nba',day,'demo',db)==card
    for g in gs:g.update(state='post',home_score=120,away_score=110);store.settle(g,db)
    settled=picks.settled_cards('nba','demo',db)[0]
    assert settled['pending']==0 and settled['wins']+settled['losses']==5
    assert settled['result']=='loss'
    reports=learning.audit('nba',(datetime.now(timezone.utc)+timedelta(days=3)).date().isoformat(),db)
    assert all(r['samples']==0 and not r['promoted'] for r in reports)

def test_too_few_favorites_no_padding(tmp_path):
    db=str(tmp_path/'db');day=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
    g=games('nhl',day)[0];service.enrich(g,db);store.capture(g,db)
    assert picks.build('nhl',day,'demo',db) is None

def test_calibration_preserves_mass(tmp_path):
    db=str(tmp_path/'db');day=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()
    g=games('nfl',day)[0];g['mode']='live';service.enrich(g,db)
    p=g['prediction']
    assert abs(p['home']+p['away']+p['ml_push']-1)<1e-9
    assert abs(p['over']+p['under']+p['push']-1)<1e-9

def test_chronological_promotion_and_refresh_does_not_reuse_holdout(tmp_path):
    db=str(tmp_path/'db');first=datetime(2026,1,1,tzinfo=timezone.utc)
    for i in range(120):
        start=first+timedelta(days=i//10,hours=18,minutes=i%10)
        g=games('nba',start.date().isoformat())[0]
        g.update(id=f'learning-{i}',mode='live',state='pre',start=start.isoformat())
        service.enrich(g,db)
        g['prediction'].update(home=.9,away=.1,raw={'home':.9,'away':.1,'over':g['prediction']['over'],'under':g['prediction']['under']})
        store.capture(g,db,at=(start-timedelta(hours=1)).isoformat())
        g.update(state='post',home_score=120 if i%10<6 else 100,away_score=110)
        store.settle(g,db)
    report=learning.audit('nba','2026-02-01',db)
    ml=next(r for r in report if r['kind']=='ml')
    assert ml['promoted'] and ml['training_through']<ml['holdout_from']
    assert ml['candidate']['brier']<ml['champion']['brier']
    again=learning.audit('nba','2026-02-01',db)
    assert all(not r['promoted'] for r in again)
    assert next(r for r in again if r['kind']=='ml')['status']=='Waiting for fresh holdout'
    assert learning.active('nba','ml',db)['version']==ml['version']
    assert learning.active('nba','ml',db)['temperature']!=1

def test_champion_not_applied_before_creation(tmp_path):
    import json
    db=str(tmp_path/'db')
    with store.connect(db) as c:
        c.execute('INSERT INTO model_versions VALUES(?,?,?,?,?,?,?,1)',('future','nba','ml',2.,'2099-01-01T00:00:00Z','2025-01-01T00:00:00Z',json.dumps({})))
    g=games('nba','2026-01-01')[0];g['mode']='live';service.enrich(g,db)
    assert g['prediction']['calibration_versions']['ml']=='baseline'

def test_new_day_does_not_reuse_old_holdout(tmp_path):
    db=str(tmp_path/'db');first=datetime(2026,1,1,tzinfo=timezone.utc)
    for i in range(120):
        start=first+timedelta(days=i//10,hours=18,minutes=i%10)
        g=games('nba',start.date().isoformat())[0];g.update(id=f'fresh-{i}',mode='live',state='pre',start=start.isoformat())
        service.enrich(g,db);store.capture(g,db,at=(start-timedelta(hours=1)).isoformat())
        g.update(state='post',home_score=120,away_score=110);store.settle(g,db)
    first_report=learning.audit('nba','2026-02-01',db)
    assert all(r.get('holdout_through') for r in first_report)
    again=learning.audit('nba','2026-02-02',db)
    assert all(r['status']=='Waiting for fresh holdout' and not r['promoted'] for r in again)
