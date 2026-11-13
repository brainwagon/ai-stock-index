# Handoff: AI & Adjacent Markets Index

## Current State

- **Repository**: `https://github.com/brainwagon/ai-stock-index` (`main` branch)
- **Prior Commits**:
  - `1013faa`: Initial FastAPI + Vanilla JS dashboard, analytics, static exporter, and GitHub Pages workflow
  - `a755b2a`: Updated GitHub Actions cron schedule to every 2 hours during US market hours (`30 14,16,18,20 * * 1-5`)
- **Live Deployments**:
  - **GitHub Pages**: `http://mvandewettering.com/ai-stock-index/` (built via `actions/deploy-pages`, `build_type: workflow`). Note: `https_enforced` is `false` on the custom domain and `https://` returned `503` when checked; `http://` serves `200`.
  - **Local Server**: `./run.sh` runs `uvicorn` on port `8090` (port `8080` was already occupied on this host).

## Architecture Overview

- **Backend (`app/`)**: FastAPI (`app/main.py`) + `yfinance` batch downloader with `45s`/`900s` TTL cache (`app/market_data.py`) + pure pandas/numpy analytics (`app/analytics.py`) + sector/watchlist config (`app/sectors.py`).
- **Benchmarks**: Includes `^GSPC` (S&P 500), `^NDX` (NASDAQ 100), `SPY`, `QQQ`, `SMH`, `SOXX`, `BOTZ`, `AIQ`. Index symbols starting with `^` are mapped by `safe_symbol_filename()` (`IDX_GSPC.json`, `IDX_NDX.json`) in `scripts/export_static.py` and `static/app.js`.
- **Dual-Mode Frontend (`static/`)**: Uses relative asset paths (`static/...`, `data/...`) so it works both at `/` locally and under `/ai-stock-index/` on GitHub Pages. `detectBackendMode()` probes `api/health` and falls back to static JSON mode (`?mode=static` forces static mode).
- **Tests (`tests/`)**: 9 unit/API/exporter tests (`python3 -m pytest`), plus `node --check` on `static/app.js` and `static/charts.js`.

## Known Gaps & Next Opportunities

- **HTTPS on Custom Domain**: `https://mvandewettering.com/ai-stock-index/` returned `503` (`https_enforced: false` on GitHub Pages API). Enabling HTTPS enforcement in GitHub Pages settings (or DNS/proxy config) is left to the user.
- **Static Mode Watchlist Persistence**: Custom watchlist additions (`POST /api/watchlist`) are disabled in static mode; client-side `localStorage` filtering or custom basket weighting could be added if desired.
- **Uncommitted Local Artifacts**: `dist/` is gitignored and generated locally for verification; do not commit `dist/` to `main`.

## Suggested Skills

- **`tdd`**: When adding new analytics metrics, technical indicators, or watchlist endpoints.
- **`diagnose`**: If `yfinance` upstream schema changes or a scheduled GitHub Actions run fails.
- **`improve-codebase-architecture`**: If expanding into persistent historical storage (e.g., SQLite/DuckDB) or multi-portfolio support.
