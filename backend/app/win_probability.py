"""Ridge-regularized Bradley–Terry adjustment to frozen moneyline forecasts."""
import json
import math
from collections import defaultdict
from zoneinfo import ZoneInfo

from . import store

LEAGUES = {'nhl', 'nba', 'nfl', 'ncaaf'}
KIND = 'ml_rating'
MIN_TRAIN = 80
MIN_TEST = 30
MIN_TEST_DATES = 5
TORONTO = ZoneInfo('America/Toronto')


def logistic(value):
    value = max(-35.0, min(35.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def logit(probability):
    probability = min(1 - 1e-9, max(1e-9, probability))
    return math.log(probability / (1 - probability))


def features(game):
    terms = {}
    if not game.get('neutral'):
        terms['home_advantage'] = 1.0
    home, away = game.get('home_id'), game.get('away_id')
    if home and away and home != away:
        terms[f'team:{home}'] = 1.0
        terms[f'team:{away}'] = -1.0
    if game.get('context', {}).get('checks', {}).get('travel'):
        home_travel = game.get('travel', {}).get('home', {})
        away_travel = game.get('travel', {}).get('away', {})
        for name, key, scale in [('rest', 'rest_hours', 48), ('travel', 'km', 2000)]:
            h, a = home_travel.get(key), away_travel.get(key)
            if h is not None and a is not None:
                terms[name] = max(-1.0, min(1.0, (h - a) / scale))
    return terms


def fit(rows):
    """Maximize penalized Bernoulli likelihood by coordinate Newton updates."""
    columns = defaultdict(list)
    predictors = []
    for i, row in enumerate(rows):
        predictors.append(row['offset'])
        for term, value in row['terms'].items():
            if value:
                columns[term].append((i, value))
    weights = dict.fromkeys(columns, 0.0)
    for _ in range(80):
        largest_change = 0.0
        for term, entries in sorted(columns.items()):
            penalty = 5.0 if term.startswith('team:') else 10.0
            gradient = -penalty * weights[term]
            curvature = penalty
            for i, value in entries:
                probability = logistic(predictors[i])
                gradient += value * (rows[i]['won'] - probability)
                curvature += value * value * probability * (1 - probability)
            change = max(-0.5, min(0.5, gradient / curvature))
            weights[term] += change
            largest_change = max(largest_change, abs(change))
            for i, value in entries:
                predictors[i] += change * value
        if largest_change < 1e-6:
            break
    return weights


def estimate(offset, terms, weights):
    return logistic(offset + sum(value * weights.get(term, 0.0) for term, value in terms.items()))


def scores(rows, weights=None):
    brier = loss = 0.0
    for row in rows:
        probability = row['posted'] if weights is None else estimate(row['offset'], row['terms'], weights)
        brier += (probability - row['won']) ** 2
        observed = probability if row['won'] else 1 - probability
        loss -= math.log(max(1e-12, observed))
    return {'brier': brier / len(rows), 'log_loss': loss / len(rows)}


def training_rows(forecasts, day):
    rows = []
    for forecast in forecasts:
        if not forecast['settled_at']:
            continue
        captured = store.instant(forecast['captured'])
        start = store.instant(forecast['start'])
        settled = store.instant(forecast['settled_at'])
        game_day = start.astimezone(TORONTO).date().isoformat()
        if game_day >= day or not captured < start <= settled:
            continue
        result = json.loads(forecast['result'])
        if result['home_score'] == result['away_score']:
            continue
        game = json.loads(forecast['payload'])
        prediction = game['prediction']
        mass = 1.0 - prediction.get('ml_push', 0.0)
        if mass <= 0:
            continue
        raw = prediction.get('raw', prediction)['home'] / mass
        rows.append({'captured': captured, 'settled': settled, 'day': game_day,
                     'offset': logit(raw), 'posted': prediction['home'] / mass,
                     'won': int(result['home_score'] > result['away_score']),
                     'terms': features(game)})
    return rows


def choose_split(rows, watermark=None, active_since=None):
    """Embargo games whose results were unavailable at first test capture."""
    if len(rows) < MIN_TRAIN + MIN_TEST:
        return None
    test_pool = [r for r in rows if (watermark is None or r['captured'] > watermark)
                 and (active_since is None or r['captured'] >= active_since)]
    if len(test_pool) < MIN_TEST or len({r['day'] for r in test_pool}) < MIN_TEST_DATES:
        return None
    for cutoff in sorted({r['captured'] for r in test_pool}, reverse=True):
        holdout = [r for r in test_pool if r['captured'] >= cutoff]
        if len(holdout) < MIN_TEST or len({r['day'] for r in holdout}) < MIN_TEST_DATES:
            continue
        training = [r for r in rows if r['settled'] < cutoff]
        return (training, holdout) if len(training) >= MIN_TRAIN else None
    return None


def audit(sport, day, path=None):
    if sport not in LEAGUES:
        return
    with store.connect(path) as c:
        forecasts = c.execute(
            "SELECT * FROM forecasts WHERE sport=? AND mode='live' AND result IS NOT NULL", (sport,)
        ).fetchall()
        previous = c.execute(
            "SELECT payload FROM model_checks WHERE sport=? AND kind=? ORDER BY day DESC LIMIT 1", (sport, KIND)
        ).fetchone()
        incumbent = c.execute(
            "SELECT created FROM model_versions WHERE sport=? AND kind=? AND active=1", (sport, KIND)
        ).fetchone()
    old = json.loads(previous['payload']) if previous else {}
    rows = training_rows(forecasts, day)
    latest_test = old.get('latest_test')
    watermark = store.instant(latest_test['holdout_capture_through']) if latest_test else None
    since = store.instant(incumbent['created']) if incumbent else None
    split = choose_split(rows, watermark, since)
    report = {'kind': KIND, 'day': day, 'samples': len(rows), 'status': 'Active · waiting for fresh test games' if incumbent else 'Waiting for dated validation',
              'latest_test': latest_test}
    with store.connect(path) as c:
        if split:
            training, holdout = split
            weights = fit(training)
            candidate, current = scores(holdout, weights), scores(holdout)
            promoted = (candidate['brier'] <= current['brier'] - .002
                        and candidate['log_loss'] <= current['log_loss'] - .005)
            tested = {'training_count': len(training), 'holdout_count': len(holdout),
                      'candidate': candidate, 'champion': current, 'promoted': promoted,
                      'holdout_capture_from': min(r['captured'] for r in holdout).isoformat(),
                      'holdout_capture_through': max(r['captured'] for r in holdout).isoformat()}
            report.update(latest_test=tested, status='Promoted rating model' if promoted else 'Current model retained')
            if promoted:
                version = f'{sport}-ml-ratings-{day}'
                c.execute('UPDATE model_versions SET active=0 WHERE sport=? AND kind=?', (sport, KIND))
                c.execute('INSERT OR REPLACE INTO model_versions VALUES(?,?,?,?,?,?,?,1)',
                          (version, sport, KIND, 1.0, store.now(),
                           max(r['settled'] for r in training).isoformat(), json.dumps({'weights': weights, **tested})))
        c.execute('INSERT OR REPLACE INTO model_checks VALUES(?,?,?,?)', (sport, day, KIND, json.dumps(report)))
    return report


def apply(game, path=None):
    if game.get('mode') != 'live' or game.get('sport') not in LEAGUES:
        return
    with store.connect(path) as c:
        row = c.execute('SELECT version,created,evaluation FROM model_versions WHERE sport=? AND kind=? AND active=1',
                        (game['sport'], KIND)).fetchone()
    if not row or store.instant(row['created']) >= store.instant(game['start']):
        return
    prediction = game['prediction']
    mass = 1.0 - prediction.get('ml_push', 0.0)
    if mass <= 0:
        return
    weights = json.loads(row['evaluation'])['weights']
    home = estimate(logit(prediction['raw']['home'] / mass), features(game), weights)
    prediction['home'] = home * mass
    prediction['away'] = mass - prediction['home']
    prediction['calibration_versions']['ml'] = row['version']
    prediction['version'] += ' / opponent-adjusted ML'
