# Verification — October 13, 2026

- Backend: 30 tests passed, including sport probability mass, settlement, immutable forecasts/cards, no postgame backfill, model-only API, missing context, provider matching and synthetic-data exclusion from learning.
- Frontend: TypeScript checking passed. Static demo and production builds passed.
- Live public feeds were checked for NHL/NBA/NFL schedules, prior results, injuries, travel and NFL weather. Missing sportsbook credentials leave prices and EV blank. ESPN endpoints are undocumented and have no SLA.
- Paid odds and confirmed-starter providers have no supplied credentials and remain unverified against subscribed accounts. Canadian Bet365 coverage is not claimed.
- Daily temperature-calibration code is implemented; no real-data improvement or historical accuracy is claimed. Default replay and demo results are synthetic.
- Browser: favorites, four-leg daily card, model records and synthetic settlement verified. Phone layout visually checked at 390px.
- Browser: favorites, four-leg daily card, model records and synthetic settlement verified. Phone layout visually checked at 390px.
- Browser: favorites, four-leg daily card, model records and synthetic settlement verified. Phone layout visually checked at 390px.
- Docker configuration supplied but not executed here.

Local preview servers are used for verification only. Follow README.md to start the full application. No GitHub upload or public deployment has been performed.
