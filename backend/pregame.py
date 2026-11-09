"""Track what changed between published pregame forecasts."""
import json
from datetime import timedelta

from app import store

FULL_INTERVAL = timedelta(hours=2)
NEAR_KICKOFF = timedelta(minutes=90)
NEAR_INTERVAL = timedelta(minutes=10)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def refresh_targets(out, sports, days, now):
    """None requests the full refresh; a list selects only near-start boards."""
    manifest = read_json(out / 'manifest.json')
    last = manifest.get('full_refresh_at')
    if not last or manifest.get('today') != days[0] or now - store.instant(last) >= FULL_INTERVAL:
        return None
    targets = []
    for sport in sports:
        for day in days[:2]:
            board = read_json(out / sport / (day + '.json'))
            updated = board.get('updated')
            if updated and now - store.instant(updated) < NEAR_INTERVAL:
                continue
            if any(g.get('state') == 'pre' and timedelta(0) < store.instant(g['start']) - now <= NEAR_KICKOFF
                   for g in board.get('games', [])):
                targets.append((sport, day))
    return targets


def roster(game, side):
    return {
        row.get('name'): (row.get('position'), row.get('status', '').casefold())
        for row in game.get('injuries', {}).get(side, []) if row.get('name')
    }


def starters(game, side):
    return {row['name']: ('confirmed' if row.get('confirmed') else row.get('status', 'expected').casefold())
            for row in game.get(side + '_starters', []) if row.get('name')}


def book_price(game, side):
    market = (game.get('markets') or {}).get(side)
    ref = game.get('market_reference') or {}
    if market and market.get('odds') is not None:
        return market['odds']
    return ref.get(side + '_odds')


def add_changes(board, old_board):
    previous = {g['id']: g for g in old_board.get('games', [])}
    for game in board['games']:
        old = previous.get(game['id'])
        if not old:
            continue
        history = old.get('pregame_changes', [])
        if history:
            game['pregame_changes'] = history
        forecast, prior = game.get('prediction'), old.get('prediction')
        if game.get('state') != 'pre' or old.get('state') != 'pre' or not forecast or not prior:
            continue
        sides = [s for s in ('away', 'home', 'draw') if s in forecast and s in prior]
        changes = []
        for side in ('away', 'home'):
            before, after = roster(old, side), roster(game, side)
            for name, (position, status) in sorted(after.items()):
                if before.get(name) != (position, status):
                    changes.append(f'{name}: {status}')
            if game.get('injuries_checked') and old.get('injuries_checked'):
                for name in sorted(before.keys() - after.keys()):
                    changes.append(f'{name}: removed from injury report')
            old_starters = starters(old, side)
            for name, status in sorted(starters(game, side).items()):
                if old_starters.get(name) != status:
                    changes.append(f'{name}: {status} starter')
            travel = game.get('travel', {}).get(side, {})
            old_travel = old.get('travel', {}).get(side, {})
            if travel.get('previous_start') and travel.get('previous_start') != old_travel.get('previous_start'):
                changes.append(game[side + '_abbr'] + ' rest/travel updated')
        for field, label in (('temperature_c', 'temperature'), ('wind_kmh', 'wind')):
            before = old.get('weather', {}).get(field)
            after = game.get('weather', {}).get(field)
            if before is not None and after is not None and abs(after - before) >= 2:
                changes.append('Kickoff ' + label + ' forecast updated')
        for side in sides:
            before, after = book_price(old, side), book_price(game, side)
            if before is not None and after is not None and before != after:
                team = 'Draw' if side == 'draw' else game[side + '_abbr']
                changes.append(f'{team} book reference {before:+g} → {after:+g}')
        if forecast['version'] != prior['version']:
            changes.append('Model version updated')
        old_ml = {s: prior[s] for s in sides}
        new_ml = {s: forecast[s] for s in sides}
        moved = any(abs(new_ml[s] - old_ml[s]) >= .001 for s in sides)
        if moved or changes:
            entry = {'checked_at': game['updated'], 'previous_at': old['updated'],
                     'previous_ml': old_ml, 'current_ml': new_ml, 'inputs': changes[:12]}
            game['pregame_changes'] = ([entry] + history)[:20]
