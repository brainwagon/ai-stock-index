# AI & Adjacent Markets Index

A local web dashboard for monitoring live and historical performance across AI and adjacent sectors, built with FastAPI, `yfinance`, and zero-dependency Vanilla JS / Canvas 2D charts.

## Tracked Sectors

- **Core AI & Hyperscalers**: `NVDA`, `MSFT`, `GOOGL`, `META`, `AMZN`, `PLTR`
- **Semiconductors & Equipment**: `AMD`, `AVGO`, `TSM`, `ASML`, `MU`, `ARM`
- **Data Center Infra & Power**: `VRT`, `ETN`, `EQIX`, `VST`, `CEG`, `DLR`
- **AI Software, Cloud & Robotics**: `SNOW`, `DDOG`, `CRM`, `NOW`, `TSLA`, `ISRG`
- **Benchmarks & Sector ETFs**: `^GSPC` (S&P 500), `^NDX` (NASDAQ 100), `SPY`, `QQQ`, `SMH`, `SOXX`, `BOTZ`, `AIQ`

## Features

- **Custom AI Composite Index**: Equal-weighted and market-cap-weighted composite performance vs `SPY`, `QQQ`, and `SMH`.
- **Multi-Timeframe Analysis**: `1D` (5-minute intraday), `1W`, `1M`, `3M`, `YTD`, and `1Y` returns.
- **Unusual Moves & Volume Radar**: Flags tickers with `|1D %| >= 3%`, `|Z-Score| >= 2.0σ`, or `Volume / 20D Avg >= 1.5x`.
- **Sector Breakdown & Correlation Matrix**: Compare equal-weighted vs cap-weighted sector performance and daily return correlations.
- **Interactive Screener & Ticker Detail Modal**: Sort, search, filter by sector, inspect 52W range and 30D sparklines, click any ticker for a price/volume chart, or customize the watchlist.

## Quick Start (Live Mode)

```bash
./run.sh
```

Then open [http://127.0.0.1:8090](http://127.0.0.1:8090) in your browser. Set `PORT=9000 ./run.sh` to use a custom port.

## Hosting on GitHub Pages (Static Snapshot Mode)

This project includes a static exporter ([scripts/export_static.py](scripts/export_static.py)) and a GitHub Actions workflow ([.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml)).

1. Push this repository to GitHub (default branch `main` or `master`).
2. In your GitHub repository go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
3. The workflow runs on push, manually via **Actions → workflow_dispatch**, and every 30 minutes on weekdays during US market hours (`13:00–21:59 UTC`) to refresh snapshots automatically.

You can also build the static bundle locally into `dist/`:

```bash
python3 scripts/export_static.py --out dist
```

The frontend automatically detects whether the live FastAPI backend (`/api/health`) is running: locally it uses live polling and watchlist editing; on GitHub Pages it seamlessly switches to the precomputed static snapshots.

## Tests

```bash
python3 -m pytest
```
