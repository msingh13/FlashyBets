"""Men's Division I scoreboard and recent completed-game inputs."""
import asyncio
import math
from datetime import date, datetime, timedelta, timezone

import httpx

from . import providers

LEAGUE_PATH = 'basketball/mens-college-basketball'
LOOKBACK_DAYS = 21
PRIOR_POINTS = 72.0
PRIOR_GAMES = 4
HISTORY_CACHE = {}


def book_lines(competition):
    for quote in competition.get('odds') or []:
        spread = quote.get('pointSpread') or {}
        try:
            home = float(spread['home']['close']['line'])
            away = float(spread['away']['close']['line'])
            home_spread = home if math.isfinite(home) and home == -away else None
        except (KeyError, TypeError, ValueError):
            home_spread = None
        try:
            total = float(quote['overUnder'])
            total = total if math.isfinite(total) and total > 0 else None
        except (KeyError, TypeError, ValueError):
            total = None
        if home_spread is not None or total is not None:
            return {'home_spread': home_spread, 'total': total,
                    'source': (quote.get('provider') or {}).get('name', 'Sportsbook') + ' via ESPN'}
    return {}


async def live_games(day):
    selected = date.fromisoformat(day)
    today = date.fromisoformat(providers.localday(datetime.now(timezone.utc).isoformat()))
    cutoff = min(selected, today)
    url = providers.BASE + LEAGUE_PATH + '/scoreboard'

    def params(value):
        return {'dates': value.strftime('%Y%m%d'), 'groups': 50, 'limit': 1000}

    async with httpx.AsyncClient(timeout=15) as client:
        scheduled = await providers.get(client, url, params(selected))
        events = [e for e in scheduled.get('events', []) if providers.localday(e['date']) == day]
        if not events:
            return []
        semaphore = asyncio.Semaphore(6)

        async def history(value):
            cached = HISTORY_CACHE.get(value)
            if cached and datetime.now(timezone.utc) - cached[0] < timedelta(hours=2):
                return cached[1]
            async with semaphore:
                body, error = await providers.optional(client, url, params(value))
            if error:
                return None
            completed = []
            for e in body.get('events', []):
                c = e['competitions'][0]
                if providers.localday(e['date']) != value.isoformat() or not c['status']['type'].get('completed'):
                    continue
                try:
                    g = providers.game_from_event(e, 'ncaab')
                    if g['state'] == 'post' and g['home_score'] != g['away_score']:
                        completed.append(g)
                except (KeyError, ValueError, TypeError):
                    continue
            HISTORY_CACHE[value] = (datetime.now(timezone.utc), completed)
            return completed

        historical = await asyncio.gather(*(history(cutoff - timedelta(days=i))
                                            for i in range(1, LOOKBACK_DAYS + 1)))

    totals = {}
    for completed in historical:
        for g in completed or ():
            for side, opponent in (('home', 'away'), ('away', 'home')):
                points = totals.setdefault(g[side + '_id'], [0, 0, 0])
                points[0] += g[side + '_score']
                points[1] += g[opponent + '_score']
                points[2] += 1

    def team_rates(team):
        scored, allowed, count = totals.get(team, (0, 0, 0))
        return ((scored + PRIOR_POINTS * PRIOR_GAMES) / (count + PRIOR_GAMES),
                (allowed + PRIOR_POINTS * PRIOR_GAMES) / (count + PRIOR_GAMES), count)

    games = []
    for event in events:
        g = providers.game_from_event(event, 'ncaab')
        hf, ha, hn = team_rates(g['home_id'])
        af, aa, an = team_rates(g['away_id'])
        advantage = 0.0 if g['neutral'] else 1.5
        g.update(home_rate=(hf + aa) / 2 + advantage, away_rate=(af + ha) / 2 - advantage,
                 rates_source='Prior 21 days of ESPN completed games with a 72-point prior',
                 rates_asof=(cutoff - timedelta(days=1)).isoformat(),
                 sample_sizes={'home': hn, 'away': an},
                 college_lines=book_lines(event['competitions'][0]),
                 lineup_source='ESPN scoreboard probable players where available',
                 injuries={}, injuries_checked=False, injuries_asof=None, injuries_source='Unavailable',
                 travel={}, weather={'status': 'Indoor baseline', 'temperature_c': None, 'wind_kmh': None, 'source': None})
        if any(rows is None for rows in historical):
            g['provider_errors'].append('Part of the college basketball history feed was unavailable')
        games.append(g)
    return games
