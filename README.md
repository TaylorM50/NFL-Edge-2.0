# NFL Edge — real-data analytics starter

A static dashboard designed for Netlify/GitHub Pages with a scheduled GitHub Actions data pipeline.

## What is real in this project?
- **Live/upcoming scoreboard:** reads ESPN's public scoreboard endpoint in the browser and refreshes every 30 seconds while open. It is a public, unofficial endpoint, not a service-level-guaranteed API.
- **Team advanced metrics:** generated from nflverse/nflfastR play-by-play CSV, including mean offensive EPA/play, mean defensive EPA allowed/play, EPA-positive success rate, and an explicitly defined explosive-play rate.
- **Player production:** passing/rushing/receiving yardage and touchdowns attributed where available in play-by-play fields. Some players may be absent or stats incomplete until upstream data is updated.
- **Automated refresh:** GitHub Actions attempts to refresh the metrics file every six hours and on manual dispatch. nflverse itself typically updates play-by-play on its own schedule, so a run cannot create newer source data than the provider has published.

## Important metric limits
- “Risk-worthy throws” is **not** fabricated or approximated as a real charting metric. The dashboard says it is unavailable until a validated charting source/labels are configured.
- Pressure rate, player separation, tracking metrics and Next Gen Stats are not calculated without their relevant source fields.
- This is an independent project and is not affiliated with the NFL or ESPN. Respect upstream data terms and attribution requirements.

## Publish on Netlify (current GitHub-connected workflow)
1. Upload the contents of this folder into the root of your existing `NFL-Edge` GitHub repository, including `.github/workflows/update-data.yml`.
2. In GitHub, open **Actions** → **Update NFL Edge data** → **Run workflow**.
3. Wait for the workflow to complete successfully. It should commit `data/data.json` to the repository.
4. Netlify should redeploy automatically after the commit. Open your Netlify site and refresh.
5. In GitHub Actions, check the run log if the data build fails. If GitHub Actions are disabled for the repository, enable them in the repository's Actions tab/settings.

## Local preview
Open `index.html` directly for the dashboard shell. Browser security may block local JSON fetches; use a local static server for full functionality, e.g. `python -m http.server 8000` from the project folder and open `http://localhost:8000`.

## Data pipeline
The workflow uses the current calendar year by default (`NFL_SEASON` can override it). The script downloads `play_by_play_<year>.csv.gz` from the nflverse-data `pbp` release, aggregates eligible run/pass plays, and writes `data/data.json`.
