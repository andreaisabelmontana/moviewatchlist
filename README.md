# MovieWatchlist — Interactive Showcase

An interactive static showcase for **MovieWatchlist**, a Flask app for tracking the movies you've
watched and want to watch, searching a film catalog, and getting simple recommendations.

🔗 **Live site:** https://andreaisabelmontana.github.io/moviewatchlist/

## What it does
- **Watchlist** — save films you want to watch.
- **Watched history** — mark what you've seen and build a viewing history.
- **Catalog search** — search a film catalog (TMDB) to find titles to add.
- **Recommendations** — simple suggestions based on what you've watched.
- **Accounts** — private per-user lists.
- **Production-ready** — pytest with coverage, Docker, Prometheus `/metrics`, deployed on Azure.

**Stack:** Flask (Python) · PostgreSQL (Azure) · TMDB API · pytest + coverage · Docker · Prometheus · Azure Web App.

## About this repo
An original, hand-built static site (single `index.html`, no framework) presenting the project,
with a scripted interactive watchlist demo (search → mark to-watch/watched → adaptive recommendations).
Built from scratch; catalog data in the demo is sample data.
