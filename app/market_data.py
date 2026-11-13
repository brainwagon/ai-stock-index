"""Market data fetching and TTL caching via yfinance."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from app.analytics import (
    build_historical_chart_data,
    build_intraday_chart_data,
    compute_composite_summary,
    compute_regime_monitor,
    compute_sector_correlation,
    compute_sector_summaries,
    compute_stock_checklists,
    compute_ticker_snapshot,
    safe_float,
)
from app.sectors import (
    SECTOR_META,
    load_watchlist,
    reset_watchlist,
    save_watchlist,
)


def _extract_field_frame(raw: pd.DataFrame, field: str, symbols: list[str]) -> pd.DataFrame:
    """Extract a single OHLCV field (e.g. 'Close' or 'Volume') as DataFrame[columns=symbols]."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=symbols)

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.get_level_values(0)
        if field in level0:
            sub = raw[field].copy()
            if isinstance(sub, pd.Series):
                sub = sub.to_frame(name=symbols[0])
            return sub
        return pd.DataFrame(columns=symbols)

    # Single-ticker flat DataFrame
    if field in raw.columns and len(symbols) == 1:
        return raw[[field]].rename(columns={field: symbols[0]}).copy()
    return pd.DataFrame(columns=symbols)


def _fetch_fast_quote(symbol: str) -> tuple[str, dict[str, Any]]:
    """Fetch fast_info quote fields for a single symbol."""
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        return symbol, {
            "last_price": safe_float(getattr(fi, "last_price", None)),
            "previous_close": safe_float(getattr(fi, "previous_close", None)),
            "market_cap": safe_float(getattr(fi, "market_cap", None)),
            "last_volume": safe_float(getattr(fi, "last_volume", None)),
        }
    except Exception:
        return symbol, {}


def _fetch_valuation(symbol: str) -> tuple[str, dict[str, Any]]:
    """Fetch forward P/E and P/S valuation multiples for a single equity."""
    try:
        info = yf.Ticker(symbol).info or {}
        return symbol, {
            "forward_pe": safe_float(info.get("forwardPE")),
            "price_to_sales": safe_float(info.get("priceToSalesTrailing12Months")),
        }
    except Exception:
        return symbol, {}


class MarketDataService:
    """Thread-safe market data loader with multi-tier TTL caching."""

    def __init__(self, daily_ttl: float = 900.0, live_ttl: float = 45.0) -> None:
        self._lock = threading.RLock()
        self._daily_ttl = daily_ttl
        self._live_ttl = live_ttl
        self._daily_cache: dict[str, Any] = {"ts": 0.0, "symbols": (), "close": pd.DataFrame(), "volume": pd.DataFrame()}
        self._val_cache: dict[str, Any] = {"ts": 0.0, "symbols": (), "valuations": {}}
        self._live_cache: dict[str, Any] = {"ts": 0.0, "symbols": (), "quotes": {}, "intra_close": pd.DataFrame()}

    def invalidate_cache(self, include_daily: bool = False) -> None:
        """Clear cached live data (and optionally daily history)."""
        with self._lock:
            self._live_cache["ts"] = 0.0
            if include_daily:
                self._daily_cache["ts"] = 0.0
                self._val_cache["ts"] = 0.0

    def _get_daily_frames(self, symbols: list[str], force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
        key = tuple(symbols)
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._daily_cache["symbols"] == key
                and (now - self._daily_cache["ts"]) < self._daily_ttl
                and not self._daily_cache["close"].empty
            ):
                return self._daily_cache["close"], self._daily_cache["volume"]

        raw = yf.download(
            symbols,
            period="2y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        close_df = _extract_field_frame(raw, "Close", symbols)
        vol_df = _extract_field_frame(raw, "Volume", symbols)

        with self._lock:
            self._daily_cache = {
                "ts": time.monotonic(),
                "symbols": key,
                "close": close_df,
                "volume": vol_df,
            }
        return close_df, vol_df

    def _get_valuations(self, symbols: list[str], force: bool = False) -> dict[str, dict[str, Any]]:
        key = tuple(symbols)
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._val_cache["symbols"] == key
                and (now - self._val_cache["ts"]) < self._daily_ttl
                and self._val_cache["valuations"]
            ):
                return self._val_cache["valuations"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(_fetch_valuation, symbols))
        valuations = dict(results)

        with self._lock:
            self._val_cache = {
                "ts": time.monotonic(),
                "symbols": key,
                "valuations": valuations,
            }
        return valuations

    def _get_live_data(self, symbols: list[str], force: bool = False) -> tuple[dict[str, dict[str, Any]], pd.DataFrame]:
        key = tuple(symbols)
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._live_cache["symbols"] == key
                and (now - self._live_cache["ts"]) < self._live_ttl
                and self._live_cache["quotes"]
            ):
                return self._live_cache["quotes"], self._live_cache["intra_close"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            quote_results = list(pool.map(_fetch_fast_quote, symbols))
        quotes = dict(quote_results)

        intra_raw = yf.download(
            symbols,
            period="1d",
            interval="5m",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        intra_close = _extract_field_frame(intra_raw, "Close", symbols)

        with self._lock:
            self._live_cache = {
                "ts": time.monotonic(),
                "symbols": key,
                "quotes": quotes,
                "intra_close": intra_close,
            }
        return quotes, intra_close

    def get_overview(self, range_key: str = "YTD", force_refresh: bool = False) -> dict[str, Any]:
        """Return full dashboard payload: composite index, sectors, tickers, charts, correlations."""
        valid_ranges = {"1W", "1M", "3M", "YTD", "1Y"}
        if range_key not in valid_ranges:
            range_key = "YTD"

        watchlist = load_watchlist()
        symbols = [item["symbol"] for item in watchlist]
        stock_symbols = [
            item["symbol"]
            for item in watchlist
            if not SECTOR_META.get(item["sector"], {}).get("is_benchmark", False)
        ]

        close_df, vol_df = self._get_daily_frames(symbols, force=force_refresh)
        valuations = self._get_valuations(stock_symbols, force=False)
        quotes, intra_close = self._get_live_data(symbols, force=force_refresh)

        snapshots: list[dict[str, Any]] = []
        live_prices: dict[str, float] = {}
        for item in watchlist:
            sym = item["symbol"]
            c_series = close_df[sym] if sym in close_df.columns else pd.Series(dtype=float)
            v_series = vol_df[sym] if sym in vol_df.columns else pd.Series(dtype=float)
            merged_quote = {**quotes.get(sym, {}), **valuations.get(sym, {})}
            snap = compute_ticker_snapshot(
                ticker_cfg=item,
                sector_meta=SECTOR_META,
                close_series=c_series,
                volume_series=v_series,
                fast_quote=merged_quote,
            )
            snapshots.append(snap)
            if snap["price"] is not None:
                live_prices[sym] = snap["price"]

        composite = compute_composite_summary(snapshots)
        sectors = compute_sector_summaries(snapshots, SECTOR_META)
        regime = compute_regime_monitor(
            close_df=close_df,
            vol_df=vol_df,
            snapshots=snapshots,
            composite=composite,
            sector_summaries=sectors,
            sector_meta=SECTOR_META,
            live_prices=live_prices,
        )
        stock_checklists = compute_stock_checklists(
            close_df=close_df,
            snapshots=snapshots,
            composite=composite,
            regime=regime,
            live_prices=live_prices,
        )
        chart = build_historical_chart_data(
            close_df=close_df,
            snapshots=snapshots,
            sector_meta=SECTOR_META,
            range_key=range_key,
            live_prices=live_prices,
        )
        intraday_chart = build_intraday_chart_data(
            intra_df=intra_close,
            snapshots=snapshots,
            sector_meta=SECTOR_META,
        )
        correlations = compute_sector_correlation(
            close_df=close_df,
            snapshots=snapshots,
            sector_meta=SECTOR_META,
            range_key=range_key,
        )

        unusual_moves = sorted(
            [s for s in snapshots if s["is_unusual"] and not s["is_benchmark"]],
            key=lambda s: abs(s["ret_1d"] or 0.0),
            reverse=True,
        )

        last_intra_ts = None
        if not intra_close.empty:
            idx = pd.to_datetime(intra_close.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/New_York")
            last_intra_ts = idx[-1].strftime("%Y-%m-%d %H:%M ET")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_timestamp": last_intra_ts,
            "range": range_key,
            "sector_meta": list(SECTOR_META.values()),
            "composite": composite,
            "regime": regime,
            "stock_checklists": stock_checklists,
            "sectors": sectors,
            "tickers": snapshots,
            "unusual_moves": unusual_moves,
            "chart": chart,
            "intraday_chart": intraday_chart,
            "correlations": correlations,
        }

    def get_ticker_detail(self, symbol: str, range_key: str = "3M") -> dict[str, Any]:
        """Return detailed historical & intraday series plus stats for one ticker."""
        sym = symbol.strip().upper()
        watchlist = load_watchlist()
        item = next((w for w in watchlist if w["symbol"] == sym), None)
        if item is None:
            item = {"symbol": sym, "name": sym, "sector": "core_ai"}

        symbols = [w["symbol"] for w in watchlist]
        if sym in symbols:
            stock_symbols = [
                w["symbol"]
                for w in watchlist
                if not SECTOR_META.get(w["sector"], {}).get("is_benchmark", False)
            ]
            close_df, vol_df = self._get_daily_frames(symbols)
            valuations = self._get_valuations(stock_symbols)
            quotes, intra_close = self._get_live_data(symbols)
            c_series = close_df[sym] if sym in close_df.columns else pd.Series(dtype=float)
            v_series = vol_df[sym] if sym in vol_df.columns else pd.Series(dtype=float)
            quote = {**quotes.get(sym, {}), **valuations.get(sym, {})}
            intra_series = intra_close[sym] if sym in intra_close.columns else pd.Series(dtype=float)
        else:
            raw = yf.download([sym], period="2y", interval="1d", auto_adjust=True, progress=False)
            c_series = _extract_field_frame(raw, "Close", [sym]).get(sym, pd.Series(dtype=float))
            v_series = _extract_field_frame(raw, "Volume", [sym]).get(sym, pd.Series(dtype=float))
            _, quote = _fetch_fast_quote(sym)
            intra_raw = yf.download([sym], period="1d", interval="5m", auto_adjust=True, progress=False)
            intra_series = _extract_field_frame(intra_raw, "Close", [sym]).get(sym, pd.Series(dtype=float))

        snap = compute_ticker_snapshot(item, SECTOR_META, c_series, v_series, quote)

        # Build chart points for requested range
        if range_key == "1D":
            clean_intra = pd.to_numeric(intra_series, errors="coerce").dropna()
            idx = pd.to_datetime(clean_intra.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/New_York")
            labels = [ts.strftime("%H:%M") for ts in idx]
            prices = [round(float(v), 2) for v in clean_intra.tolist()]
            vols = []
        else:
            clean_c = pd.to_numeric(c_series, errors="coerce").dropna()
            clean_v = pd.to_numeric(v_series, errors="coerce").dropna()
            if not clean_c.empty:
                idx = pd.to_datetime(clean_c.index)
                if idx.tz is not None:
                    idx = idx.tz_convert("America/New_York").tz_localize(None)
                clean_c.index = idx.normalize()
                clean_c = clean_c[~clean_c.index.duplicated(keep="last")].sort_index()
                if snap["price"] is not None:
                    clean_c.iloc[-1] = snap["price"]

                from app.analytics import get_anchor_date

                anchor = get_anchor_date(clean_c.index, range_key)
                if anchor is not None:
                    clean_c = clean_c.loc[clean_c.index >= anchor]

                labels = [d.strftime("%Y-%m-%d") for d in clean_c.index]
                prices = [round(float(v), 2) for v in clean_c.tolist()]

                # Align volumes
                if not clean_v.empty:
                    v_idx = pd.to_datetime(clean_v.index)
                    if v_idx.tz is not None:
                        v_idx = v_idx.tz_convert("America/New_York").tz_localize(None)
                    clean_v.index = v_idx.normalize()
                    clean_v = clean_v[~clean_v.index.duplicated(keep="last")]
                    vols = [int(clean_v.get(d, 0) or 0) for d in clean_c.index]
                else:
                    vols = []
            else:
                labels, prices, vols = [], [], []

        return {
            "snapshot": snap,
            "range": range_key,
            "series": {
                "labels": labels,
                "prices": prices,
                "volumes": vols,
            },
        }

    def add_ticker(self, symbol: str, sector: str) -> dict[str, Any]:
        """Validate a symbol via yfinance and add it to the watchlist."""
        sym = symbol.strip().upper()
        if not sym or len(sym) > 12:
            raise ValueError("Invalid ticker symbol.")
        if sector not in SECTOR_META:
            raise ValueError(f"Unknown sector '{sector}'.")

        watchlist = load_watchlist()
        if any(item["symbol"] == sym for item in watchlist):
            raise ValueError(f"{sym} is already in the watchlist.")

        ticker = yf.Ticker(sym)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty:
            raise ValueError(f"Could not find market price data for '{sym}'.")

        name = sym
        try:
            info = ticker.info or {}
            name = info.get("shortName") or info.get("longName") or sym
        except Exception:
            pass

        entry = {"symbol": sym, "name": str(name), "sector": sector}
        watchlist.append(entry)
        save_watchlist(watchlist)
        self.invalidate_cache(include_daily=True)
        return entry

    def remove_ticker(self, symbol: str) -> list[dict[str, str]]:
        """Remove a symbol from the watchlist."""
        sym = symbol.strip().upper()
        watchlist = load_watchlist()
        updated = [w for w in watchlist if w["symbol"] != sym]
        if len(updated) == len(watchlist):
            raise ValueError(f"{sym} is not in the watchlist.")
        if not updated:
            raise ValueError("Cannot remove the last ticker from the watchlist.")
        save_watchlist(updated)
        self.invalidate_cache(include_daily=True)
        return updated

    def reset_default_watchlist(self) -> list[dict[str, str]]:
        """Restore the default watchlist."""
        updated = reset_watchlist()
        self.invalidate_cache(include_daily=True)
        return updated


market_service = MarketDataService()
