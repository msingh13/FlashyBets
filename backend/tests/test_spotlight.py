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


def test_college_basketball_never_enters_play_of_the_day(tmp_path):
    from datetime import datetime, timezone
    from discord_publish import fresh_state, prepare

    db = tmp_path / 'ncaab.db'
    day, at = '2026-11-10', '2026-11-10T08:00:00Z'
    game = games('ncaab', day)[0]
    game.update(mode='live', state='pre', start='2026-11-10T23:00:00Z')
    service.enrich(game, db)
    game['prediction'].update(home=.8, away=.2, over=.8, under=.2)
    store.capture(game, db, at=at)
    with store.connect(db) as c:
        c.execute('INSERT INTO snapshots VALUES(?,?,?)', (game['id'], at, json.dumps(game)))
    assert spotlight.build(day, 'live', db, at=at) is None

    state = fresh_state()
    state['sent']['results:' + day] = at
    candidate = dict(game_key=store.key(game), sport='ncaab', side='home',
                     label='C1 ML', probability=.8, start=game['start'])
    feed = {'updated': at, 'days': [{'day': day, 'legs': [candidate]}]}
    assert prepare(state, feed, datetime(2026, 11, 10, 8, tzinfo=timezone.utc)) is None
