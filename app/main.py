"""FastAPI application for the AI & Adjacent Markets Stock Index Dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.market_data import market_service

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="AI & Adjacent Markets Index", version="1.0.0")


class AddTickerRequest(BaseModel):
    symbol: str
    sector: str


@app.get("/api/health")
def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}


@app.get("/api/market/overview")
def market_overview(
    range_key: str = Query("YTD", alias="range"),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    """Return full AI & adjacent market overview, indices, sectors, and tickers."""
    return market_service.get_overview(range_key=range_key, force_refresh=refresh)


@app.get("/api/market/ticker/{symbol}")
def ticker_detail(
    symbol: str,
    range_key: str = Query("3M", alias="range"),
) -> dict[str, Any]:
    """Return historical or intraday chart + metrics for a single ticker."""
    valid = {"1D", "1W", "1M", "3M", "YTD", "1Y"}
    if range_key not in valid:
        range_key = "3M"
    return market_service.get_ticker_detail(symbol=symbol, range_key=range_key)


@app.post("/api/refresh")
def force_refresh() -> dict[str, str]:
    """Invalidate live cache so next poll fetches fresh prices."""
    market_service.invalidate_cache(include_daily=False)
    return {"status": "refreshed"}


@app.post("/api/watchlist")
def add_watchlist_ticker(payload: AddTickerRequest) -> dict[str, Any]:
    """Add a new ticker to the watchlist."""
    try:
        entry = market_service.add_ticker(symbol=payload.symbol, sector=payload.sector)
        return {"added": entry}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/watchlist/{symbol}")
def remove_watchlist_ticker(symbol: str) -> dict[str, Any]:
    """Remove a ticker from the watchlist."""
    try:
        updated = market_service.remove_ticker(symbol=symbol)
        return {"count": len(updated)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/watchlist/reset")
def reset_watchlist_tickers() -> dict[str, Any]:
    """Reset the watchlist to default AI & adjacent tickers."""
    updated = market_service.reset_default_watchlist()
    return {"count": len(updated)}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    """Serve the single-page dashboard."""
    return FileResponse(STATIC_DIR / "index.html")
