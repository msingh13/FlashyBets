import json
from datetime import datetime, timedelta, timezone

from app import store, win_probability as ratings


def test_holdout_excludes_games_settled_after_its_first_forecast():
    anchor = datetime(2026, 10, 20, tzinfo=timezone.utc)
    early = [
        dict(captured=anchor - timedelta(days=10), settled=anchor - timedelta(days=8),
             day='2026-10-11')
        for _ in range(ratings.MIN_TRAIN)
    ]
    holdout = [
        dict(captured=anchor + timedelta(days=i), settled=anchor + timedelta(days=i + 1),
             day=(anchor + timedelta(days=i)).date().isoformat())
        for i in range(5) for _ in range(6)
    ]
    unavailable = dict(captured=anchor - timedelta(hours=1),
                       settled=anchor + timedelta(hours=1), day='2026-10-20')
    train, test = ratings.choose_split(early + [unavailable] + holdout)
    assert test == holdout
    assert train == early
    assert ratings.choose_split(early + holdout, watermark=holdout[-1]['captured']) is None


def test_active_rating_changes_only_decisive_moneyline_mass(tmp_path):
    db = tmp_path / 'test.db'
    with store.connect(db) as c:
        c.execute('INSERT INTO model_versions VALUES(?,?,?,?,?,?,?,1)',
                  ('test-rating', 'nfl', ratings.KIND, 1, '2026-10-01T00:00Z',
                   '2026-09-30T00:00Z', json.dumps({'weights': {'team:A': .5}})))
    game = {'mode': 'live', 'sport': 'nfl', 'home_id': 'A', 'away_id': 'B',
            'start': '2026-10-20T00:00Z', 'prediction': {
                'raw': {'home': .49}, 'home': .49, 'away': .49, 'ml_push': .02,
                'over': .6, 'under': .4, 'version': 'test', 'calibration_versions': {}}}
    ratings.apply(game, db)
    p = game['prediction']
    assert p['home'] > .49
    assert abs(p['home'] + p['away'] + p['ml_push'] - 1) < 1e-12
    assert p['over'] == .6 and p['under'] == .4
    assert p['calibration_versions']['ml'] == 'test-rating'
