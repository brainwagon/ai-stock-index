"""Pure financial analytics for AI & adjacent market monitoring."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

RANGE_DAYS: dict[str, int] = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "1Y": 365,
}

# (symbol, series_id, display_name, color)
BENCHMARK_SERIES_SPEC: list[tuple[str, str, str, str]] = [
    ("^GSPC", "bench_gspc", "S&P 500", "#cbd5e1"),
    ("^NDX", "bench_ndx", "NASDAQ 100", "#60a5fa"),
    ("SPY", "bench_spy", "SPY", "#94a3b8"),
    ("QQQ", "bench_qqq", "QQQ", "#e2e8f0"),
    ("SMH", "bench_smh", "SMH", "#c084fc"),
]


def safe_float(val: Any) -> float | None:
    """Convert value to finite float, returning None if invalid or NaN."""
    if val is None:
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(num):
        return None
    return num


def compute_return_pct(latest_price: float | None, base_price: float | None) -> float | None:
    """Compute percentage return from base_price to latest_price."""
    if latest_price is None or base_price is None or base_price <= 0:
        return None
    return round((latest_price / base_price - 1.0) * 100.0, 2)


def normalize_daily_index(series: pd.Series) -> pd.Series:
    """Normalize a price/volume series to tz-naive sorted daily dates without NaNs."""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return pd.Series(dtype=float)
    idx = pd.to_datetime(clean.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    clean.index = idx.normalize()
    clean = clean[~clean.index.duplicated(keep="last")].sort_index()
    return clean


def get_anchor_date(dates: pd.DatetimeIndex, range_key: str) -> pd.Timestamp | None:
    """Find the anchor trading date for a given lookback range."""
    if dates.empty:
        return None
    latest = dates[-1]
    if range_key == "YTD":
        year_start = pd.Timestamp(year=latest.year, month=1, day=1)
        prior = dates[dates < year_start]
        return prior[-1] if not prior.empty else dates[0]

    days = RANGE_DAYS.get(range_key)
    if days is None:
        return dates[0]
    target = latest - timedelta(days=days)
    prior = dates[dates <= target]
    return prior[-1] if not prior.empty else None


def compute_ticker_snapshot(
    ticker_cfg: dict[str, str],
    sector_meta: dict[str, dict[str, Any]],
    close_series: pd.Series,
    volume_series: pd.Series,
    fast_quote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute multi-timeframe returns, volume ratios, and unusual move flags for one ticker."""
    symbol = ticker_cfg["symbol"]
    sector_id = ticker_cfg["sector"]
    sector_info = sector_meta.get(sector_id, {})
    fast_quote = fast_quote or {}

    closes = normalize_daily_index(close_series)
    volumes = normalize_daily_index(volume_series)

    live_price = safe_float(fast_quote.get("last_price"))
    prev_close_fast = safe_float(fast_quote.get("previous_close"))
    market_cap = safe_float(fast_quote.get("market_cap"))
    live_volume = safe_float(fast_quote.get("last_volume"))
    display_name = fast_quote.get("name") or ticker_cfg.get("name") or symbol

    latest_hist_close = safe_float(closes.iloc[-1]) if not closes.empty else None
    price = live_price if live_price is not None else latest_hist_close

    # Determine previous close cleanly: prefer fast_info previous_close when live_price exists
    if live_price is not None and prev_close_fast is not None and prev_close_fast > 0:
        prev_close = prev_close_fast
    elif len(closes) >= 2:
        prev_close = safe_float(closes.iloc[-2])
    else:
        prev_close = None

    ret_1d = compute_return_pct(price, prev_close)

    # Multi-timeframe returns using historical closes
    ret_1w = ret_1m = ret_3m = ret_ytd = ret_1y = None
    high_52w = low_52w = range_52w_pct = None
    vol_30d_ann = z_score_1d = None
    sparkline: list[float] = []

    if not closes.empty and price is not None:
        # Ensure latest point reflects live price for consistent lookbacks
        effective_closes = closes.copy()
        effective_closes.iloc[-1] = price

        for key, attr_name in [
            ("1W", "ret_1w"),
            ("1M", "ret_1m"),
            ("3M", "ret_3m"),
            ("YTD", "ret_ytd"),
            ("1Y", "ret_1y"),
        ]:
            anchor = get_anchor_date(effective_closes.index, key)
            base_val = safe_float(effective_closes.loc[anchor]) if anchor is not None else None
            val = compute_return_pct(price, base_val)
            if attr_name == "ret_1w":
                ret_1w = val
            elif attr_name == "ret_1m":
                ret_1m = val
            elif attr_name == "ret_3m":
                ret_3m = val
            elif attr_name == "ret_ytd":
                ret_ytd = val
            elif attr_name == "ret_1y":
                ret_1y = val

        # 52W range from last ~252 trading days
        one_year_cut = effective_closes.index[-1] - timedelta(days=365)
        win_1y = effective_closes[effective_closes.index >= one_year_cut]
        if not win_1y.empty:
            high_52w = round(float(win_1y.max()), 2)
            low_52w = round(float(win_1y.min()), 2)
            span = high_52w - low_52w
            if span > 0:
                range_52w_pct = round(max(0.0, min(100.0, (price - low_52w) / span * 100.0)), 1)

        # Daily volatility over trailing 30 trading days (excluding today's partial/live move)
        daily_rets = closes.pct_change().dropna() * 100.0
        if len(daily_rets) >= 15:
            trailing = daily_rets.iloc[-31:-1] if len(daily_rets) > 30 else daily_rets.iloc[:-1]
            if len(trailing) >= 10:
                daily_std = float(trailing.std(ddof=1))
                if daily_std > 0:
                    vol_30d_ann = round(daily_std * np.sqrt(252.0), 1)
                    if ret_1d is not None:
                        z_score_1d = round(ret_1d / daily_std, 2)

        # 30-day sparkline
        tail_closes = effective_closes.iloc[-30:]
        sparkline = [round(float(x), 2) for x in tail_closes.tolist()]

    # Volume vs 20-day average (excluding today's partial session from average)
    latest_hist_vol = safe_float(volumes.iloc[-1]) if not volumes.empty else None
    volume = live_volume if (live_volume is not None and live_volume > 0) else latest_hist_vol
    avg_vol_20d = None
    vol_ratio = None
    if len(volumes) >= 5:
        prior_vols = volumes.iloc[-21:-1] if len(volumes) > 20 else volumes.iloc[:-1]
        if not prior_vols.empty:
            mean_vol = float(prior_vols.mean())
            if mean_vol > 0:
                avg_vol_20d = round(mean_vol)
                if volume is not None:
                    vol_ratio = round(volume / mean_vol, 2)

    unusual_reasons: list[str] = []
    if ret_1d is not None and abs(ret_1d) >= 3.0:
        sign = "+" if ret_1d > 0 else ""
        unusual_reasons.append(f"Move {sign}{ret_1d:.1f}%")
    if z_score_1d is not None and abs(z_score_1d) >= 2.0:
        sign = "+" if z_score_1d > 0 else ""
        unusual_reasons.append(f"Z-Score {sign}{z_score_1d:.1f}σ")
    if vol_ratio is not None and vol_ratio >= 1.5:
        unusual_reasons.append(f"Vol {vol_ratio:.1f}x")

    return {
        "symbol": symbol,
        "name": display_name,
        "sector": sector_id,
        "sector_name": sector_info.get("short_name", sector_id),
        "sector_color": sector_info.get("color", "#94a3b8"),
        "is_benchmark": bool(sector_info.get("is_benchmark", False)),
        "price": round(price, 2) if price is not None else None,
        "prev_close": round(prev_close, 2) if prev_close is not None else None,
        "market_cap": round(market_cap) if market_cap is not None else None,
        "ret_1d": ret_1d,
        "ret_1w": ret_1w,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_ytd": ret_ytd,
        "ret_1y": ret_1y,
        "volume": round(volume) if volume is not None else None,
        "avg_vol_20d": avg_vol_20d,
        "vol_ratio": vol_ratio,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "range_52w_pct": range_52w_pct,
        "vol_30d_ann": vol_30d_ann,
        "z_score_1d": z_score_1d,
        "is_unusual": bool(unusual_reasons),
        "unusual_reasons": unusual_reasons,
        "sparkline": sparkline,
    }


def _weighted_return_series(
    close_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    anchor_date: pd.Timestamp,
) -> tuple[list[str], list[float]]:
    """Build cumulative % return series from anchor_date using daily-rebalanced weights."""
    cols = [s for s in symbols if s in close_df.columns]
    if not cols:
        return [], []

    sub = close_df.loc[close_df.index >= anchor_date, cols].dropna(how="all")
    if len(sub) < 2:
        return [], []

    daily_rets = sub.pct_change()
    # First row is anchor (0.0% return)
    dates = [idx.strftime("%Y-%m-%d") for idx in sub.index]
    cum_values: list[float] = [0.0]

    # Pre-align weights vector
    raw_weights = pd.Series({c: max(0.0, float(weights.get(c, 1.0))) for c in cols})
    if raw_weights.sum() <= 0:
        raw_weights = pd.Series({c: 1.0 for c in cols})

    level = 1.0
    for dt in sub.index[1:]:
        row = daily_rets.loc[dt].dropna()
        if row.empty:
            cum_values.append(round((level - 1.0) * 100.0, 2))
            continue
        active_w = raw_weights[row.index]
        w_sum = float(active_w.sum())
        if w_sum <= 0:
            day_ret = float(row.mean())
        else:
            day_ret = float((row * active_w).sum() / w_sum)
        level *= 1.0 + day_ret
        cum_values.append(round((level - 1.0) * 100.0, 2))

    return dates, cum_values


def build_historical_chart_data(
    close_df: pd.DataFrame,
    snapshots: list[dict[str, Any]],
    sector_meta: dict[str, dict[str, Any]],
    range_key: str = "YTD",
    live_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute composite indices, sector sub-indices, and benchmark curves for range_key."""
    if close_df.empty:
        return {"dates": [], "series": []}

    df = close_df.copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()

    if live_prices and not df.empty:
        last_idx = df.index[-1]
        for sym, px in live_prices.items():
            if sym in df.columns and px is not None:
                df.at[last_idx, sym] = px

    anchor = get_anchor_date(df.index, range_key)
    if anchor is None:
        anchor = df.index[0]

    stock_snaps = [s for s in snapshots if not s["is_benchmark"]]
    stock_symbols = [s["symbol"] for s in stock_snaps]
    equal_weights = {s: 1.0 for s in stock_symbols}
    cap_weights = {
        s["symbol"]: float(s["market_cap"]) if s.get("market_cap") else 1.0 for s in stock_snaps
    }

    series_out: list[dict[str, Any]] = []
    master_dates: list[str] = []

    for label, key_id, w_map, color, dash in [
        ("AI Composite (Equal-Wt)", "ai_equal", equal_weights, "#22d3ee", False),
        ("AI Composite (Cap-Wt)", "ai_cap", cap_weights, "#f43f5e", False),
    ]:
        dates, vals = _weighted_return_series(df, stock_symbols, w_map, anchor)
        if dates:
            master_dates = dates
            series_out.append(
                {
                    "id": key_id,
                    "name": label,
                    "kind": "composite",
                    "color": color,
                    "dashed": dash,
                    "values": vals,
                    "latest": vals[-1],
                }
            )

    # Sector sub-indices (equal-weighted)
    for sector_id, meta in sector_meta.items():
        if meta.get("is_benchmark"):
            continue
        sec_syms = [s["symbol"] for s in stock_snaps if s["sector"] == sector_id]
        if not sec_syms:
            continue
        dates, vals = _weighted_return_series(df, sec_syms, {s: 1.0 for s in sec_syms}, anchor)
        if dates:
            if not master_dates:
                master_dates = dates
            series_out.append(
                {
                    "id": f"sector_{sector_id}",
                    "name": meta["short_name"],
                    "kind": "sector",
                    "color": meta["color"],
                    "dashed": False,
                    "values": vals,
                    "latest": vals[-1],
                }
            )

    # Benchmark Indices & ETFs
    for bench_sym, bench_id, bench_label, bench_color in BENCHMARK_SERIES_SPEC:
        if bench_sym in df.columns:
            dates, vals = _weighted_return_series(df, [bench_sym], {bench_sym: 1.0}, anchor)
            if dates:
                series_out.append(
                    {
                        "id": bench_id,
                        "name": bench_label,
                        "kind": "benchmark",
                        "color": bench_color,
                        "dashed": True,
                        "values": vals,
                        "latest": vals[-1],
                    }
                )

    return {"dates": master_dates, "series": series_out, "range": range_key}


def build_intraday_chart_data(
    intra_df: pd.DataFrame,
    snapshots: list[dict[str, Any]],
    sector_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build intraday % change curves relative to each ticker's previous close."""
    if intra_df.empty:
        return {"timestamps": [], "series": []}

    df = intra_df.sort_index().ffill()
    prev_map = {
        s["symbol"]: s["prev_close"]
        for s in snapshots
        if s.get("prev_close") and s["prev_close"] > 0
    }

    pct_cols: dict[str, pd.Series] = {}
    for sym, prev in prev_map.items():
        if sym in df.columns:
            pct_cols[sym] = (pd.to_numeric(df[sym], errors="coerce") / prev - 1.0) * 100.0
    if not pct_cols:
        return {"timestamps": [], "series": []}

    pct_df = pd.DataFrame(pct_cols, index=df.index).dropna(how="all")
    if pct_df.empty:
        return {"timestamps": [], "series": []}

    idx = pd.to_datetime(pct_df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York")
    timestamps = [ts.strftime("%H:%M") for ts in idx]

    stock_snaps = [s for s in snapshots if not s["is_benchmark"] and s["symbol"] in pct_df.columns]
    stock_syms = [s["symbol"] for s in stock_snaps]

    def weighted_avg(syms: list[str], weights: dict[str, float]) -> list[float | None]:
        sub = pct_df[[s for s in syms if s in pct_df.columns]]
        if sub.empty:
            return []
        w = pd.Series({c: max(0.0, float(weights.get(c, 1.0))) for c in sub.columns})
        vals: list[float | None] = []
        for _, row in sub.iterrows():
            valid = row.dropna()
            if valid.empty:
                vals.append(None)
                continue
            aw = w[valid.index]
            ws = float(aw.sum())
            avg = float((valid * aw).sum() / ws) if ws > 0 else float(valid.mean())
            vals.append(round(avg, 2))
        return vals

    series_out: list[dict[str, Any]] = []
    if stock_syms:
        eq_vals = weighted_avg(stock_syms, {s: 1.0 for s in stock_syms})
        cap_w = {
            s["symbol"]: float(s["market_cap"]) if s.get("market_cap") else 1.0
            for s in stock_snaps
        }
        cap_vals = weighted_avg(stock_syms, cap_w)
        for sid, name, color, vals in [
            ("ai_equal", "AI Composite (Equal-Wt)", "#22d3ee", eq_vals),
            ("ai_cap", "AI Composite (Cap-Wt)", "#f43f5e", cap_vals),
        ]:
            last_v = next((v for v in reversed(vals) if v is not None), None)
            series_out.append(
                {
                    "id": sid,
                    "name": name,
                    "kind": "composite",
                    "color": color,
                    "dashed": False,
                    "values": vals,
                    "latest": last_v,
                }
            )

    for sector_id, meta in sector_meta.items():
        if meta.get("is_benchmark"):
            continue
        sec_syms = [s["symbol"] for s in stock_snaps if s["sector"] == sector_id]
        if not sec_syms:
            continue
        vals = weighted_avg(sec_syms, {s: 1.0 for s in sec_syms})
        last_v = next((v for v in reversed(vals) if v is not None), None)
        series_out.append(
            {
                "id": f"sector_{sector_id}",
                "name": meta["short_name"],
                "kind": "sector",
                "color": meta["color"],
                "dashed": False,
                "values": vals,
                "latest": last_v,
            }
        )

    for bench_sym, bench_id, bench_label, bench_color in BENCHMARK_SERIES_SPEC:
        if bench_sym in pct_df.columns:
            vals = [round(float(v), 2) if pd.notna(v) else None for v in pct_df[bench_sym].tolist()]
            last_v = next((v for v in reversed(vals) if v is not None), None)
            series_out.append(
                {
                    "id": bench_id,
                    "name": bench_label,
                    "kind": "benchmark",
                    "color": bench_color,
                    "dashed": True,
                    "values": vals,
                    "latest": last_v,
                }
            )

    return {"timestamps": timestamps, "series": series_out}


def _avg_metric(items: list[dict[str, Any]], key: str, cap_weighted: bool = False) -> float | None:
    """Compute equal- or market-cap-weighted average of a numeric field."""
    valid = [x for x in items if x.get(key) is not None]
    if not valid:
        return None
    if not cap_weighted:
        return round(sum(float(x[key]) for x in valid) / len(valid), 2)
    weights = [float(x["market_cap"]) if x.get("market_cap") else 0.0 for x in valid]
    total_w = sum(weights)
    if total_w <= 0:
        return round(sum(float(x[key]) for x in valid) / len(valid), 2)
    weighted = sum(float(x[key]) * w for x, w in zip(valid, weights)) / total_w
    return round(weighted, 2)


def compute_sector_summaries(
    snapshots: list[dict[str, Any]],
    sector_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate multi-timeframe performance and breadth per sector."""
    summaries: list[dict[str, Any]] = []
    for sector_id, meta in sector_meta.items():
        members = [s for s in snapshots if s["sector"] == sector_id]
        if not members:
            continue
        with_1d = [m for m in members if m.get("ret_1d") is not None]
        up_count = sum(1 for m in with_1d if m["ret_1d"] >= 0)
        sorted_1d = sorted(with_1d, key=lambda m: m["ret_1d"], reverse=True)
        top_gainer = sorted_1d[0] if sorted_1d else None
        top_loser = sorted_1d[-1] if sorted_1d else None
        total_mcap = sum(m["market_cap"] for m in members if m.get("market_cap"))

        summaries.append(
            {
                "id": sector_id,
                "name": meta["name"],
                "short_name": meta["short_name"],
                "color": meta["color"],
                "is_benchmark": bool(meta.get("is_benchmark", False)),
                "description": meta["description"],
                "count": len(members),
                "up_count": up_count,
                "breadth_pct": round(up_count / len(with_1d) * 100.0) if with_1d else None,
                "total_market_cap": total_mcap or None,
                "equal": {
                    "ret_1d": _avg_metric(members, "ret_1d", False),
                    "ret_1w": _avg_metric(members, "ret_1w", False),
                    "ret_1m": _avg_metric(members, "ret_1m", False),
                    "ret_3m": _avg_metric(members, "ret_3m", False),
                    "ret_ytd": _avg_metric(members, "ret_ytd", False),
                    "ret_1y": _avg_metric(members, "ret_1y", False),
                },
                "cap": {
                    "ret_1d": _avg_metric(members, "ret_1d", True),
                    "ret_1w": _avg_metric(members, "ret_1w", True),
                    "ret_1m": _avg_metric(members, "ret_1m", True),
                    "ret_3m": _avg_metric(members, "ret_3m", True),
                    "ret_ytd": _avg_metric(members, "ret_ytd", True),
                    "ret_1y": _avg_metric(members, "ret_1y", True),
                },
                "top_gainer": (
                    {"symbol": top_gainer["symbol"], "ret_1d": top_gainer["ret_1d"]}
                    if top_gainer
                    else None
                ),
                "top_loser": (
                    {"symbol": top_loser["symbol"], "ret_1d": top_loser["ret_1d"]}
                    if top_loser
                    else None
                ),
            }
        )
    return summaries


def compute_composite_summary(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute top-level AI Composite Index summary (all non-benchmark stocks) vs indices/ETFs."""
    stocks = [s for s in snapshots if not s["is_benchmark"]]
    snap_map = {s["symbol"]: s for s in snapshots}

    with_1d = [s for s in stocks if s.get("ret_1d") is not None]
    up_count = sum(1 for s in with_1d if s["ret_1d"] >= 0)

    def tf_block(cap: bool) -> dict[str, float | None]:
        return {
            "ret_1d": _avg_metric(stocks, "ret_1d", cap),
            "ret_1w": _avg_metric(stocks, "ret_1w", cap),
            "ret_1m": _avg_metric(stocks, "ret_1m", cap),
            "ret_3m": _avg_metric(stocks, "ret_3m", cap),
            "ret_ytd": _avg_metric(stocks, "ret_ytd", cap),
            "ret_1y": _avg_metric(stocks, "ret_1y", cap),
        }

    bench_fields = ["price", "ret_1d", "ret_1w", "ret_1m", "ret_3m", "ret_ytd", "ret_1y"]
    benchmarks: dict[str, dict[str, Any] | None] = {}
    for bench_sym, _, _, _ in BENCHMARK_SERIES_SPEC:
        b = snap_map.get(bench_sym)
        benchmarks[bench_sym] = {k: b.get(k) for k in bench_fields} if b else None

    return {
        "constituent_count": len(stocks),
        "up_count": up_count,
        "down_count": len(with_1d) - up_count,
        "breadth_pct": round(up_count / len(with_1d) * 100.0) if with_1d else None,
        "total_market_cap": sum(s["market_cap"] for s in stocks if s.get("market_cap")),
        "equal": tf_block(False),
        "cap": tf_block(True),
        "benchmarks": benchmarks,
    }


def compute_sector_correlation(
    close_df: pd.DataFrame,
    snapshots: list[dict[str, Any]],
    sector_meta: dict[str, dict[str, Any]],
    range_key: str = "3M",
) -> dict[str, Any]:
    """Compute pairwise Pearson correlation of daily returns across AI sectors + SPY/QQQ."""
    if close_df.empty:
        return {"labels": [], "matrix": [], "window": range_key}

    df = close_df.copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()

    # Use at least 3M for correlation if 1W was selected so sample size >= ~60 days
    eff_range = "3M" if range_key == "1W" else range_key
    anchor = get_anchor_date(df.index, eff_range)
    if anchor is not None:
        df = df.loc[df.index >= anchor]

    daily_rets = df.pct_change().dropna(how="all")
    if len(daily_rets) < 5:
        return {"labels": [], "matrix": [], "window": eff_range}

    sector_series: dict[str, pd.Series] = {}
    for sector_id, meta in sector_meta.items():
        if meta.get("is_benchmark"):
            continue
        syms = [s["symbol"] for s in snapshots if s["sector"] == sector_id and s["symbol"] in daily_rets.columns]
        if syms:
            sector_series[meta["short_name"]] = daily_rets[syms].mean(axis=1)

    if "^NDX" in daily_rets.columns:
        sector_series["NDX"] = daily_rets["^NDX"]
    elif "QQQ" in daily_rets.columns:
        sector_series["QQQ"] = daily_rets["QQQ"]

    if "^GSPC" in daily_rets.columns:
        sector_series["S&P 500"] = daily_rets["^GSPC"]
    elif "SPY" in daily_rets.columns:
        sector_series["SPY"] = daily_rets["SPY"]

    if len(sector_series) < 2:
        return {"labels": [], "matrix": [], "window": eff_range}

    corr_df = pd.DataFrame(sector_series).corr()
    labels = list(corr_df.columns)
    matrix = [
        [round(float(corr_df.iloc[r, c]), 2) if pd.notna(corr_df.iloc[r, c]) else None for c in range(len(labels))]
        for r in range(len(labels))
    ]
    return {"labels": labels, "matrix": matrix, "window": eff_range}
