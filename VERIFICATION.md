# Verification — October 13, 2026

- Backend: 35 tests pass, including immutable capture, durable state, settlement, provider failure retention, sport probability mass and soccer draw/BTTS/90-minute score handling.
- Production static export and TypeScript checks pass.
- Public GitHub Pages deployment succeeded twice. The second run preserved all 51 original NHL forecast timestamps and model versions.
- ShawnLabs remains the portfolio homepage; its FlashyBets project now links to /FlashyBets/.
- NHL/NBA/NFL public data integrations verified. No paid sportsbook or confirmed-starter credentials are configured. Bet365 coverage and EV are not claimed.
- Champions League football-data.org adapter, model and tracker are implemented and tested with controlled fixtures. No football-data token is supplied; real UCL integration has not been verified. Live page reports unavailable rather than fabricated data.
- Soccer excludes extra time and penalties. Missing regularTime scores for extended games remain unsettled. Three-way calibration is disabled pending separate chronological validation.
- Higher probabilities are highlighted yellow, with ties unhighlighted. Favorite explanations derive from stored scoring rates and disclose missing context.
- Demo/replay results are synthetic. No accuracy or daily improvement claims.
- Docker supplied, not executed here.
