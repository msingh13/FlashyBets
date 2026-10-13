# Host the FlashyBets backend

The included render.yaml defines one paid Python web service and a 1 GB persistent disk. It runs one worker, refreshes live NHL/NBA/NFL data every ten minutes, and saves model records under /data/flashybets.db. No service has been created, no hosting payment authorized, and no public backend URL exists yet.

## Deploy

1. Put the contents of the FlashyBets source folder into a GitHub repository, with render.yaml, backend/ and frontend/ at its root. Do not upload local databases, .env files or dependencies.
2. Connect the Render integration to your account if you want deployment managed from this chat. Otherwise open Render → New → Blueprint and select that repository.
3. Review the paid service and persistent-disk estimate shown by Render before creating it. Render's free web services sleep and cannot attach this persistent disk, so they are unsuitable for this automatic SQLite tracker. Data subscriptions cost separately.
4. Deploy the blueprint. The start command uses Render's assigned port; one process owns the refresh loop. There is no separate worker bill in this configuration.
5. Verify the assigned HTTPS address at /health, /docs and /api/tracker?sport=nhl&mode=live. Check worker logs and the latest tracker update time. Verify records survive a restart before sharing the app.
6. Add any licensed provider keys in Render's environment settings: ODDS_API_KEY, ODDS_REGION, ODDS_BOOKMAKER, SPORTSDATAIO_KEY. Keys are optional; absent keys leave sportsbook prices/EV and confirmed-starter feeds unavailable. Canadian Bet365 coverage is not currently verified.
7. Rebuild the frontend for your portfolio with the actual backend address:

```sh
cd frontend
STATIC_EXPORT=1 NEXT_PUBLIC_OFFLINE_DEMO=0 NEXT_PUBLIC_BASE_PATH=/flashybets NEXT_PUBLIC_API_URL=https://YOUR-ASSIGNED-RENDER-ADDRESS npm run build
```

Replace the portfolio's flashybets/ directory with out/'s contents. Keep your root portfolio files. This switches from frozen demo files to the hosted API. The API permits the https://msingh13.github.io origin; update FRONTEND_ORIGIN if you host the frontend elsewhere.

## Operation

Keep the paid service running. Deployments briefly interrupt a service with a disk; missed pregame forecasts remain unrecorded. Back up SQLite using a consistent SQLite backup, not a lone copy of a live WAL database file. Retain one API worker and one instance until the storage and refresh loop are redesigned for PostgreSQL/multiple workers. Monitor disk usage, refresh failures and provider quotas. Public API reads may trigger provider fetches; add rate limits before promoting the link to a large audience.

References: [Render blueprint format](https://render.com/docs/blueprint-spec), [free plan limitations](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks), [pricing](https://render.com/pricing).
