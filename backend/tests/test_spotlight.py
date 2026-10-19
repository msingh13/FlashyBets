import json
from app import spotlight,store,service
from app.demo import games

def seed(db):
    at='2026-10-19T12:00:00Z'
    for sport in ('nhl','nba','nfl'):
        for i,g in enumerate(games(sport,'2026-10-19')[:3]):
            g.update(mode='live',state='pre',start='2026-10-19T23:00:00Z')
            service.enrich(g,db)
            g['prediction'].update(home=.65,away=.35,over=.7,under=.3,push=0.,ml_push=0.)
            store.capture(g,db,at=at)
            with store.connect(db) as c:c.execute('INSERT INTO snapshots VALUES(?,?,?)',(g['id'],at,json.dumps(g)))
    return at

def test_three_global_unique_frozen_and_settled(tmp_path):
    db=str(tmp_path/'db');at=seed(db)
    card=spotlight.build('2026-10-19','live',db,at)
    assert len(card['legs'])==3 and len({p['game_key'] for p in card['legs']})==3
    assert all(not p['verified_value'] for p in card['legs'])
    assert spotlight.build('2026-10-19','live',db,'2026-10-19T13:00:00Z')==card
    leg=card['legs'][0]
    with store.connect(db) as c:c.execute('UPDATE forecasts SET result=? WHERE game_key=?',(json.dumps({'home_score':100,'away_score':100}),leg['game_key']))
    record=spotlight.record('live',db)
    assert record['metrics']['wins']+record['metrics']['losses']+record['metrics']['pushes']==1
    assert record['metrics']['pending']==2 and record['metrics']['roi'] is not None # synthetic test odds exist
    assert spotlight.record('demo',db)['days']==[]
    from publish import save,restore
    state=tmp_path/'state.json';save(state,db)
    restored=str(tmp_path/'restored.db');restore(state,restored)
    assert spotlight.record('live',restored)['days']==record['days']

def test_never_backfills_or_selects_stale_or_started_games(tmp_path):
    db=str(tmp_path/'db');seed(db)
    assert spotlight.build('2026-10-18','live',db,'2026-10-19T12:00:00Z') is None
    assert spotlight.build('2026-10-19','live',db,'2026-10-19T13:00:00Z') is None
    with store.connect(db) as c:c.execute('UPDATE snapshots SET created=?',('2026-10-19T23:01:00Z',))
    assert spotlight.build('2026-10-19','live',db,'2026-10-19T23:01:00Z') is None
