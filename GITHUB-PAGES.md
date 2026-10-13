# FlashyBets on GitHub Pages

This version runs scheduled Python jobs in GitHub Actions and hosts the dashboard on GitHub Pages. No Render service or paid API key is required. Sportsbook prices and EV remain blank without a future odds integration. Public feed availability and GitHub schedules are not guaranteed.

## Turn it on

1. Commit the included changes to msingh13/FlashyBets on main, including .github/workflows/pages.yml.
2. Open repository Settings → Pages → Build and deployment → Source → GitHub Actions.
3. Open Actions → Update predictions and publish FlashyBets → Run workflow → main.
4. Wait for all steps to pass. The Deploy step reports the actual public URL. Expected project URL: https://msingh13.github.io/FlashyBets/ (capital F and B).
5. Link that URL from the existing portfolio. The portfolio stays at https://msingh13.github.io/; this workflow deploys only the separate FlashyBets project site.

If Actions is disabled, enable it in repository settings. If model-data pushes fail, check the repository/organization Actions permission policies permit the workflow's contents:write permission. GitHub App writes to .github/workflows also require workflow permission; uploading this workflow through the GitHub website is an alternative.

## Updates and durable history

A single workflow runs at minute 17 and 47 each hour, or manually, and on main pushes. It restores model-state.json from the model-data branch, fetches current results and the next seven days, records only pregame predictions, settles recorded results and checks calibration. It commits updated history and public JSON to model-data before building the dashboard. State survives a failed frontend build. Separate workflow concurrency prevents overlapping history writers; model-data pushes do not trigger another build.

The model-data branch is public and contains only model forecasts, cards, model versions/checks and refresh status. No personal journal, local database or API credentials are published. Do not delete the branch unless you deliberately want to discard history. Keep backups of that branch. SQLite is rebuilt for each job from validated, versioned JSON state.

Failed provider updates retain previous files and their original fetch timestamps. No fake live/demo fallback occurs. The manifest lists failures. A missing/disabled/delayed workflow means the published record may be stale and pregame forecasts may be missed. Public repositories' scheduled Actions can be disabled after inactivity; inspect Actions if freshness stops. The browser polls the published files but cannot itself run a model or fetch API credentials.

## Local verification

From backend/: python -m pytest -q.

To publish real feed snapshots locally (no secrets required): python publish.py. This writes ../frontend/public/data/ and ../work/model-state.json; use MODEL_STATE and PUBLISH_DIR to override.

From frontend/: STATIC_EXPORT=1 NEXT_PUBLIC_PUBLISHED_DATA=1 NEXT_PUBLIC_BASE_PATH=/FlashyBets npm run build.

The normal FastAPI app is still available for local development. Render config remains an optional future deployment, not an active paid service.

References: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages and https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule.
