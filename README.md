# FlashyBets

A daily NHL, NBA and NFL scorebook with transparent model probabilities, game context, an automatic model record and daily favorite cards. Next.js / TypeScript / Tailwind, FastAPI / Python, SQLite. Champions League adds 90-minute home/draw/away, totals and BTTS baselines. MLB remains deferred.

## GitHub deployment (current default)
Read [GITHUB-PAGES.md](GITHUB-PAGES.md). The scheduled Pages version needs no running server. Python runs in GitHub Actions; the model-data branch preserves forecasts and results. The earlier static-demo/Render instructions below are alternative configurations.

## Start locally
Node 22 and Python 3.9+ (3.12 recommended). Use two terminals:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. API docs: http://localhost:8000/docs. Defaults: demo board in browser; server refreshes **live** data for all sports every 600 seconds. That means public feed requests occur even if the page is closed. Set AUTO_REFRESH=0 to disable the worker, or DATA_MODE=demo for a fully synthetic tracker. REFRESH_SECONDS has a 60-second minimum.

`docker compose up --build` from this directory runs both services and keeps SQLite in a Docker volume. Containers bind only to local loopback in this local-development compose file. For a hosted deployment, configure TLS, origins and read access separately.

## Automatic tracker
The running backend refreshes all three sports, records the **first observed pregame forecast** and settles it against final scores. Fetches after a game begins do not create retroactive forecasts. The first forecast is immutable; snapshot history records later board updates separately. The tracker is a record of these baseline outputs, not a claim of a profitable strategy. A game missed while the backend was offline stays unrecorded.

The main record selects the higher-probability ML side and totals side per game. Wins, losses, pushes, pending results, hit rates, conditional Brier scores and priced flat one-unit ROI are reported separately. Full four-side diagnostics remain available in the API. Prices are saved only when a configured bookmaker supplies them. Reference totals have no priced ROI.

Daily ML cards freeze four or five highest model win probabilities, one leg per game, above 52% conditional probability. Fewer eligible games means no card, not padded selections. Each leg and the complete card settle automatically; the record shows e.g. 4/5 correct. Product probabilities assume independence and are not validated sportsbook parlay probabilities. Favorites are experimental probability rankings, not positive-EV recommendations. Cards do not place wagers. Canceled games remain pending; correction and void rules are future work.

The worker checks probability calibration daily using **real prospective results only**. At least 100 settled non-push games across ten dates are required per sport/market. Older 70% of dates fit a temperature candidate; newest dates compare it with the current model. Promotion requires improvements in both Brier score and log loss, with chronological checks. New versions affect future forecasts only. This is an initial calibration layer, not a full player-impact retraining system or guaranteed daily improvement. Repeated promotion checks are not an independent final accuracy evaluation.

Demo mode seeds a few **synthetic** prior-day results to demonstrate settlement. Those are always identified as demo data. No real historical accuracy is claimed.

For production, run **one** background worker with persistent storage. Avoid multiple API workers running duplicate schedulers. To use a real external scheduler instead, set AUTO_REFRESH=0 and schedule `python -m app.refresh` every ten minutes against the same database. Back up the database and add formal migrations before production growth. SQLite is pragmatic for a single-instance MVP; move to PostgreSQL for multiple instances.

## Providers and credentials
Copy .env.example to .env for Docker Compose. Bare Python/uvicorn does not load .env automatically: export variables in your backend terminal or launch with your process manager's environment configuration. Do not commit actual keys.

- **Schedules / results / injury reports / probable NHL goalies:** ESPN public scoreboard and injuries endpoints. These are public but undocumented, with no SLA. NBA preseason is labeled. NFL has no games on many weekdays; an empty board is not an error.
- **NHL scoring inputs:** prior-day NHL public standings where available, otherwise prior completed ESPN games. ESPN team schedules are cached for one hour, and only the current fixture's season type and dates before the selected day are used for scoring samples (up to 20 games per team). Sparse samples are explicitly shrunk toward assumed league means. Prior venue travel can use the most recent completed game across season types.
- **Sportsbook odds:** The Odds API v4 (`icehockey_nhl`, `basketball_nba`, `americanfootball_nfl`, markets h2h/totals). Set ODDS_API_KEY. Select ODDS_BOOKMAKER, default draftkings, and ODDS_REGION. Matching checks normalized team names and kickoff within five minutes. No key or unmatched prices means blank prices/EV; no fake live odds. Three-way moneyline markets are not treated as two-way markets. Quotas and commercial terms apply.
- **Bet365 preference:** Bet365 is the user’s reference book. The current adapter has no verified Canadian Bet365 feed. The Odds API lists bet365_au on paid plans; do not label other-book odds as Bet365. Until a licensed regional feed is verified, compare actual Bet365 prices separately. No credentials or sportsbook account were accessed.
- **Confirmed NHL goalies / NBA starters:** SportsDataIO licensed projections feeds, enabled with SPORTSDATAIO_KEY. Projected is not confirmed. NBA lineup parsing selects actual starters only. Paid subscription/entitlement is required; account access has not been verified here. NFL depth charts are descriptive, not confirmed gameday inactives.
- **Outdoor NFL weather / city coordinates:** Open-Meteo kickoff-hour temperature and wind; geocoded city locations are approximate. Ambiguous cities leave distances blank. Indoor venues skip outdoor weather. Weather outside the provider horizon stays unavailable. Review Open-Meteo's commercial license before a monetized deployment.

Fetch times, injury-feed timestamps, report dates and bookmaker updates are shown separately. A fresh fetch does not guarantee an individual injury report is fresh. Missing feeds produce visible warnings and pending context; schedule-provider failure never silently loads demo data.

## Model logic and context
**NHL:** independent regulation Poisson goals, 50/50 tie winner, and one extra final-score goal in OT/shootout. Season final-score averages approximate regulation rates and need refinement. Home advantage ±0.12 goals is assumed, not fitted. Sportsbook settlement must include the shootout goal for this adapter.

**NBA:** final-score margin and total Gaussian baselines, assumed margin SD 15 and total SD 20. Inputs contain final-score overtime; this is not a separate regulation/OT simulation. Integer total lines use continuity-corrected push probability. Preseason minutes and rotations are not modeled.

**NFL:** eleven assumed possessions per team with 0, 3 or 7 points; a fixed 32/68 field-goal/touchdown scoring mix. Tied regulation uses an explicitly approximate OT branch: 10% remain tied; the other 90% split the winner evenly and add one 3/7-point score. Two-way ML ties return the stake. Safeties, two-point conversions, overtime possession rules and score-driven drive counts need a richer model. Regular-season model only; no playoff recommendations.

League means, priors and home advantages are visible assumptions. **These models have not been calibrated or validated for betting.** Public opinion, consensus picks and betting percentages never enter the model. Odds are comparison prices only.

Injuries, starters, travel, rest and weather are checked and displayed. They only adjust rates if MODEL_CONFIG_PATH supplies sourced coefficients, player/starter effects and a temporal evaluation declaration. Do not supply arbitrary penalties or mark an unevaluated config validated. NHL starter effects change the opponent's scoring rate (goalie impact); NBA/NFL starter effects change their own scoring mean. Out/IR/suspended players with known impacts are counted; questionable players are not assumed absent. Bench and rotation-specific minutes are future work.

Recommendations are withheld unless inputs, timestamps, starter confirmation, supported season type and external evaluation metadata are present, no missing required player effects remain, and bookmaker odds are recent. The default app is **watch only**. Configuration metadata is not proof of calibration; independently audit the evaluation.

EV = P(win) × (decimal odds − 1) − P(loss). A push returns stake. Raw implied = 1/decimal. Proportional no-vig is shown for two-side markets; compare against model probability conditional on no push for integer totals and NFL ML.

## Historical replay
The original NHL CSV replay remains available at `/api/history`. Set BACKTEST_CSV to a file using backend/fixtures/history.csv's schema. Features and odds require timezone-aware timestamps before game start; final scores must include settlement goals. It reports ML-favorite flat-stake ROI, Brier score and log loss. The default four-game fixture is synthetic. NBA/NFL historical replay and large-sample evaluation remain future work; the new tracker records prospective forecasts separately.

## Portfolio / GitHub Pages
Read DEPLOYMENT.md. A ready-to-upload static demo and patched portfolio card are packaged separately. GitHub Pages serves static files; Python ingestion and settlement need an always-running backend. Do not upload .env, SQLite files, .venv, node_modules or .next.

## Checks
```sh
cd backend
python -m pytest -q
```
```sh
cd frontend
npm run typecheck
npm run build
```
For a GitHub Pages demo under /flashybets/:
```sh
cd backend
python export_demo.py
cd ../frontend
npm run demo:build
```
The generated `out/` is a clearly labeled frozen demo. Only copy the contents into your portfolio's `flashybets/` folder. Do not run `next start` against a static export; rebuild without STATIC_EXPORT for the full API-connected app.

## Next phase
1. License reliable confirmed lineups, gameday inactives and player minutes; verify starter-provider IDs and price settlement rules with paid account fixtures.
2. Fit player, goalie, rest, travel and weather effects from time-stamped data. Compare sport models to market and naive baselines using rolling holdout seasons; report calibration and uncertainty, not just hit rate.
3. Replace NFL approximate OT and drive model; add NFL playoffs separately. Improve NHL regulation-only rates and correlated scoring; model NBA possessions and confirmed minutes.
4. Add event correction/void settlement, backfill actual results for recorded forecasts, cancellation review, database migrations, quotas and alerting.
5. Improve rolling evaluation and model governance; add uncertainty estimates, promotion logs and independent final holdouts.
6. Create branded result cards for Discord/IG/TikTok; show market, price, prediction time, model version, source and settled result. No auto-posting is configured or authorized.
7. Add MLB with pitcher/lineup/run models later. Expand soccer only after validating the Champions League baseline.

## Champions League setup
Add FOOTBALL_DATA_TOKEN to the backend environment or GitHub Actions repository secrets. Obtain a token from football-data.org and check coverage/terms. Without it, the live UCL tab explicitly reports unavailable data. Use local demo mode for synthetic UCL fixtures. Soccer prices/EV remain unavailable until a licensed three-way and BTTS odds adapter is added. Regulation scoring is kept separate from extra time and penalties. Current UCL baseline uses prior Champions League results only; domestic form, confirmed lineups, injury effects and three-way calibration are next-phase work. Favorite summaries are generated directly from stored model inputs, with missing checks disclosed.
