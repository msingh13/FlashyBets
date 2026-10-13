# Add FlashyBets to Shawn Labs

Your published portfolio is https://msingh13.github.io/. It renders project cards from `content.js`; there is already a `Flashy Sports Analytics` item. The upload package replaces that item with **FlashyBets** while preserving the other projects.

## Option A — upload the portfolio demo now
This is the simplest way to put the project on your portfolio without backend hosting or credentials.

1. Unzip **flashybets-portfolio-upload.zip** from the deliverables. It contains `content.js`, `app.js`, `.nojekyll`, and a `flashybets/` folder with the prebuilt static dashboard.
2. Open the GitHub repository that publishes your portfolio. For a user Pages site this is normally `msingh13.github.io`, but check your repository's Settings → Pages publishing source. Use the same branch/folder you originally uploaded to.
3. Back up your existing `content.js` and `app.js`. The supplied files were prepared from the public version retrieved October 13, 2026. If you have edited them since then, merge the FlashyBets card and the status-aware labels rather than overwriting newer work.
4. Upload `content.js`, `app.js` and `.nojekyll` to the publishing root, and put **the contents** of the supplied `flashybets/` folder at `<publishing root>/flashybets/`. Preserve your existing root `index.html` and `style.css`.
5. Commit the upload. Wait for the GitHub Pages build/deployment to finish. The card's demo link is configured for `https://msingh13.github.io/flashybets/`. That URL is a planned destination, not an already verified deployment.
6. Open your portfolio, find FlashyBets, and select View project → Live demo. The demo is explicitly labeled as a frozen synthetic snapshot; it cannot run live scheduled updates or settle real games.

The root `.nojekyll` keeps `_next/` static assets from being filtered by Jekyll. If your Pages publishing process is a custom framework build, merge the demo into that build's output instead of uploading to a source directory that the build ignores.

## Option B — publish the full automatic app
The portfolio stays where it is. Publish the **Python backend** separately on an always-on container/Python host with durable storage. Publish the Next.js frontend as either a Next.js app or static export configured to call that backend, then link it from the portfolio.

Backend settings:

- Service root: `backend/`; install with `python -m pip install -r requirements.txt`.
- Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`, one worker.
- `DATABASE_PATH`: a persistent mounted directory, for example `/data/flashybets.db`.
- `FRONTEND_ORIGIN`: your exact frontend origin, e.g. `https://msingh13.github.io` (no /flashybets path), or your hosted frontend URL. Multiple allowed origins are comma-separated.
- Set subscribed provider credentials in the host's secret settings.
- `AUTO_REFRESH=1`, `DATA_MODE=live`, `REFRESH_SECONDS=600`.
- Use an always-on plan or a separate real scheduler; a service that sleeps will miss forecasts. Hosting and data-provider subscriptions may cost money; no account, purchase or deployment was created here.

Frontend settings:

- Root: `frontend/`; build `npm ci && npm run build`; start `npm start` for a Next.js host.
- `NEXT_PUBLIC_API_URL=https://YOUR-ACTUAL-BACKEND-URL` at **build time**. Do not use localhost on a public site.
- For static GitHub Pages at /flashybets/, build with `STATIC_EXPORT=1 NEXT_PUBLIC_OFFLINE_DEMO=0 NEXT_PUBLIC_BASE_PATH=/flashybets NEXT_PUBLIC_API_URL=https://YOUR-ACTUAL-BACKEND-URL npm run build`, then copy `out/` to the portfolio `flashybets/` folder.
- Use HTTPS on both services. Configure the backend origin before using the page.

## Source repository
Unzip flashybets-source.zip into a new project repository and push source only. .gitignore excludes generated dependencies, databases and credentials. Set the portfolio card's `github` URL after you have created the actual repository; the supplied card deliberately leaves it empty.

## Sharing later
Post the public app/demo link to your Discord or profiles after deployment. Result graphics should clearly identify baseline versus calibrated models, timestamp, bookmaker line and actual settled record. Automated Discord/IG/TikTok posting has not been implemented or authorized; we can choose that workflow once the live record is established.

Official references:
- GitHub Pages setup: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- Next.js static export: https://nextjs.org/docs/app/guides/static-exports
- The Odds API: https://the-odds-api.com/liveapi/guides/v4/index.html
- SportsDataIO: https://sportsdata.io/developers/available-data-feeds
- Open-Meteo API/license: https://open-meteo.com/en/docs and https://open-meteo.com/en/terms
