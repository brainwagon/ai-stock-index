# AI & Adjacent Markets Index

A web dashboard for monitoring live and historical performance across AI and adjacent sectors, built with FastAPI, `yfinance`, and zero-dependency Vanilla JS / Canvas 2D charts. It supports both **live local execution** and **automated static deployment on GitHub Pages**.

- **Live GitHub Pages Site**: [http://mvandewettering.com/ai-stock-index/](http://mvandewettering.com/ai-stock-index/)
- **Repository**: [https://github.com/brainwagon/ai-stock-index](https://github.com/brainwagon/ai-stock-index)

## Tracked Sectors

- **Core AI & Hyperscalers**: `NVDA`, `MSFT`, `GOOGL`, `META`, `AMZN`, `PLTR`
- **Semiconductors & Equipment**: `AMD`, `AVGO`, `TSM`, `ASML`, `MU`, `ARM`
- **Data Center Infra & Power**: `VRT`, `ETN`, `EQIX`, `VST`, `CEG`, `DLR`
- **AI Software, Cloud & Robotics**: `SNOW`, `DDOG`, `CRM`, `NOW`, `TSLA`, `ISRG`
- **Benchmarks & Sector ETFs**: `^GSPC` (S&P 500), `^NDX` (NASDAQ 100), `SPY`, `QQQ`, `SMH`, `SOXX`, `BOTZ`, `AIQ`

## Features

- **Experimental Disclaimer**: Prominent top-of-page notice clarifying that the dashboard is an experimental learning tool, has not been audited for accuracy, and does not constitute financial advice.
- **Custom AI Composite Index**: Equal-weighted and market-cap-weighted composite performance vs `S&P 500 (^GSPC)`, `NASDAQ 100 (^NDX)`, `SPY`, `QQQ`, and `SMH`.
- **AI Bubble & Regime Monitor**: Prominent dual-gauge monitor with a plain-English summary and hover/focus `?` explanatory tooltips across gauges and all 10 signals, scoring **Bubble / Froth** (1Y spread vs `S&P 500`, cross-sector crowding correlation, speculative spread, realized volatility, median Forward P/E) and **Unwind / Pop Risk** (52W peak drawdown, `50D`/`200D` SMA breadth, `1M`/`3M` relative breakdown, full-stack contagion, down-day volume pressure).
- **Single-Stock Signal & Risk Checklist (Defaults to `NVDA`)**: Informational, balanced evaluation of any tracked AI stock (valuation multiples vs AI peer median, `50D`/`200D` SMA position, 52W drawdown, `1M` relative return vs `NASDAQ 100`/`SMH`, and 30D volatility) split into **Supportive Signals**, **Risk & Caution Factors**, and **Verify Before Deciding** (not financial advice).
- **Multi-Timeframe Analysis**: `1D` (5-minute intraday), `1W`, `1M`, `3M`, `YTD`, and `1Y` returns.
- **Unusual Moves & Volume Radar**: Flags equities with `|1D %| >= 3%`, `|Z-Score| >= 2.0σ`, or `Volume / 20D Avg >= 1.5x`.
- **Sector Breakdown & Correlation Matrix**: Compare equal-weighted vs cap-weighted sector performance and daily return correlations against `NDX` and `S&P 500`.
- **Interactive Screener & Ticker Detail Modal**: Sort, search, filter by sector, inspect 52W range and 30D sparklines, click any ticker for a price/volume chart, or customize the watchlist (in live mode).

## Project Structure

- `app/main.py` — FastAPI server and REST API (`/api/health`, `/api/market/overview`, `/api/market/ticker/{symbol}`, `/api/watchlist`, `/api/refresh`)
- `app/market_data.py` — `yfinance` batch loader with multi-tier TTL caching (`45s` live, `900s` daily, plus forward P/E and price-to-sales valuation metadata)
- `app/analytics.py` — Return, composite index, intraday, unusual move, correlation, regime monitor, and single-stock checklist calculations
- `app/sectors.py` — Sector definitions and `data/watchlist.json` persistence
- `static/` — Vanilla JS (`app.js`, `charts.js`), CSS (`styles.css`), and HTML (`index.html`) frontend with auto-detection for live vs static mode
- `scripts/export_static.py` — Exports a self-contained static bundle (`dist/`) with precomputed JSON snapshots
- `.github/workflows/deploy-pages.yml` — Scheduled GitHub Actions workflow deploying `dist/` to GitHub Pages

## Quick Start (Live Mode)

Install dependencies (if not already present) and start the local server:

```bash
pip install -r requirements.txt
./run.sh
```

Open [http://127.0.0.1:8090](http://127.0.0.1:8090) in your browser. Set `PORT=9000 ./run.sh` to use a custom port.

## Hosting on GitHub Pages (Static Snapshot Mode)

The GitHub Actions workflow ([.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml)) builds and deploys the static bundle automatically:

- **Triggers**: Push to `main`/`master`, manual `workflow_dispatch`, and scheduled runs every 2 hours on weekdays during US market hours (`30 14,16,18,20 * * 1-5` UTC).
- **Mode Auto-Detection**: The frontend probes `api/health` on startup. When served statically (or via `?mode=static`), it loads precomputed JSON from `data/overview-*.json` and `data/tickers/*.json` and hides live-only watchlist/polling controls.

To build the static bundle locally into `dist/`:

```bash
python3 scripts/export_static.py --out dist
```

## Tests

```bash
python3 -m pytest
```
