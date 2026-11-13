"""Unit tests for pure financial analytics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics import (
    build_historical_chart_data,
    build_intraday_chart_data,
    compute_composite_summary,
    compute_return_pct,
    compute_sector_correlation,
    compute_sector_summaries,
    compute_ticker_snapshot,
)
from app.sectors import SECTOR_META


def _sample_daily_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2025-12-01", "2026-11-13", freq="B")
    n = len(dates)
    close_df = pd.DataFrame(
        {
            "NVDA": np.linspace(100.0, 150.0, n),
            "AMD": np.linspace(120.0, 108.0, n),
            "VRT": np.linspace(80.0, 120.0, n),
            "^GSPC": np.linspace(5000.0, 5500.0, n),
            "^NDX": np.linspace(18000.0, 21600.0, n),
            "SPY": np.linspace(500.0, 550.0, n),
        },
        index=dates,
    )
    vol_df = pd.DataFrame(
        {
            "NVDA": np.full(n, 40_000_000.0),
            "AMD": np.full(n, 30_000_000.0),
            "VRT": np.full(n, 5_000_000.0),
            "^GSPC": np.full(n, 1_000_000_000.0),
            "^NDX": np.full(n, 800_000_000.0),
            "SPY": np.full(n, 60_000_000.0),
        },
        index=dates,
    )
    # Spike AMD volume on last bar
    vol_df.iloc[-1, vol_df.columns.get_loc("AMD")] = 60_000_000.0
    return close_df, vol_df


def test_compute_return_pct_handles_edge_cases() -> None:
    assert compute_return_pct(110.0, 100.0) == 10.0
    assert compute_return_pct(90.0, 100.0) == -10.0
    assert compute_return_pct(100.0, 0.0) is None
    assert compute_return_pct(None, 100.0) is None


def test_ticker_snapshot_returns_and_unusual_flags() -> None:
    close_df, vol_df = _sample_daily_frame()
    cfg = {"symbol": "AMD", "name": "AMD", "sector": "semis"}
    snap = compute_ticker_snapshot(
        ticker_cfg=cfg,
        sector_meta=SECTOR_META,
        close_series=close_df["AMD"],
        volume_series=vol_df["AMD"],
        fast_quote={
            "last_price": 98.0,
            "previous_close": 108.0,
            "market_cap": 200_000_000_000,
            "last_volume": 60_000_000,
        },
    )
    assert snap["price"] == 98.0
    assert snap["ret_1d"] == round((98.0 / 108.0 - 1) * 100, 2)
    assert snap["vol_ratio"] == 2.0
    assert snap["is_unusual"] is True
    assert any("Move" in r for r in snap["unusual_reasons"])
    assert any("Vol 2.0x" in r for r in snap["unusual_reasons"])


def test_historical_chart_and_composite_summary() -> None:
    close_df, vol_df = _sample_daily_frame()
    configs = [
        {"symbol": "NVDA", "name": "NVIDIA", "sector": "core_ai"},
        {"symbol": "AMD", "name": "AMD", "sector": "semis"},
        {"symbol": "VRT", "name": "Vertiv", "sector": "infra_power"},
        {"symbol": "^GSPC", "name": "S&P 500 Index", "sector": "benchmarks"},
        {"symbol": "^NDX", "name": "NASDAQ 100 Index", "sector": "benchmarks"},
        {"symbol": "SPY", "name": "SPDR S&P 500", "sector": "benchmarks"},
    ]
    mcaps = {"NVDA": 3e12, "AMD": 2e11, "VRT": 5e10, "^GSPC": None, "^NDX": None, "SPY": None}
    snaps = [
        compute_ticker_snapshot(
            c,
            SECTOR_META,
            close_df[c["symbol"]],
            vol_df[c["symbol"]],
            {"market_cap": mcaps[c["symbol"]]},
        )
        for c in configs
    ]

    comp = compute_composite_summary(snaps)
    assert comp["constituent_count"] == 3
    assert comp["benchmarks"]["SPY"] is not None
    assert comp["benchmarks"]["^GSPC"] is not None
    assert comp["benchmarks"]["^NDX"] is not None

    chart = build_historical_chart_data(close_df, snaps, SECTOR_META, range_key="YTD")
    assert len(chart["dates"]) > 100
    ids = {s["id"] for s in chart["series"]}
    assert {"ai_equal", "ai_cap", "sector_core_ai", "bench_gspc", "bench_ndx", "bench_spy"}.issubset(ids)
    # Cap-weighted composite is dominated by NVDA (+50% trend) vs AMD (-10% trend)
    eq_last = next(s["latest"] for s in chart["series"] if s["id"] == "ai_equal")
    cap_last = next(s["latest"] for s in chart["series"] if s["id"] == "ai_cap")
    assert cap_last > eq_last


def test_intraday_chart_and_correlations() -> None:
    close_df, vol_df = _sample_daily_frame()
    configs = [
        {"symbol": "NVDA", "name": "NVIDIA", "sector": "core_ai"},
        {"symbol": "AMD", "name": "AMD", "sector": "semis"},
        {"symbol": "^GSPC", "name": "S&P 500 Index", "sector": "benchmarks"},
        {"symbol": "^NDX", "name": "NASDAQ 100 Index", "sector": "benchmarks"},
        {"symbol": "SPY", "name": "SPDR S&P 500", "sector": "benchmarks"},
    ]
    snaps = [
        compute_ticker_snapshot(
            c,
            SECTOR_META,
            close_df[c["symbol"]],
            vol_df[c["symbol"]],
            {"last_price": 105.0, "previous_close": 100.0, "market_cap": 1e12},
        )
        for c in configs
    ]

    intra_idx = pd.date_range("2026-11-13 09:30", periods=5, freq="5min", tz="America/New_York")
    intra_df = pd.DataFrame(
        {
            "NVDA": [100.0, 101.0, 102.0, 103.0, 104.0],
            "AMD": [100.0, 99.0, 98.0, 99.0, 100.0],
            "^GSPC": [100.0, 100.2, 100.4, 100.6, 100.8],
            "^NDX": [100.0, 100.5, 101.0, 101.2, 101.6],
            "SPY": [100.0, 100.5, 101.0, 101.0, 101.5],
        },
        index=intra_idx,
    )
    intra_chart = build_intraday_chart_data(intra_df, snaps, SECTOR_META)
    assert intra_chart["timestamps"] == ["09:30", "09:35", "09:40", "09:45", "09:50"]
    eq_series = next(s for s in intra_chart["series"] if s["id"] == "ai_equal")
    assert eq_series["values"][-1] == 2.0  # mean(+4.0%, 0.0%)
    intra_ids = {s["id"] for s in intra_chart["series"]}
    assert {"bench_gspc", "bench_ndx"}.issubset(intra_ids)

    summaries = compute_sector_summaries(snaps, SECTOR_META)
    assert len(summaries) == 3

    corr = compute_sector_correlation(close_df, snaps, SECTOR_META, range_key="3M")
    assert "Core AI" in corr["labels"]
    assert "NDX" in corr["labels"]
    assert "S&P 500" in corr["labels"]
    assert len(corr["matrix"]) == len(corr["labels"])
