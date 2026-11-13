"""Tests for static GitHub Pages exporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.export_static import (
    DETAIL_RANGES,
    OVERVIEW_RANGES,
    export_static_site,
    safe_symbol_filename,
)


class FakeService:
    """Minimal mock of MarketDataService for static export tests."""

    def get_overview(self, range_key: str = "YTD", force_refresh: bool = False) -> dict[str, Any]:
        return {
            "range": range_key,
            "market_timestamp": "2026-11-13 12:30 ET",
            "tickers": [
                {"symbol": "NVDA", "name": "NVIDIA"},
                {"symbol": "^GSPC", "name": "S&P 500 Index"},
            ],
        }

    def get_ticker_detail(self, symbol: str, range_key: str = "3M") -> dict[str, Any]:
        return {
            "snapshot": {"symbol": symbol, "name": symbol, "price": 100.0},
            "range": range_key,
            "series": {"labels": ["2026-11-13"], "prices": [100.0], "volumes": [1000]},
        }


def test_safe_symbol_filename() -> None:
    assert safe_symbol_filename("NVDA") == "NVDA"
    assert safe_symbol_filename("^GSPC") == "IDX_GSPC"
    assert safe_symbol_filename("^NDX") == "IDX_NDX"
    assert safe_symbol_filename("BRK/B") == "BRK_B"


def test_export_static_site_creates_all_assets_and_json(tmp_path: Path) -> None:
    out = tmp_path / "dist"
    summary = export_static_site(out_dir=out, service=FakeService())  # type: ignore[arg-type]

    assert summary["overview_files"] == len(OVERVIEW_RANGES)
    assert summary["ticker_files"] == 2
    assert (out / "index.html").exists()
    assert (out / ".nojekyll").exists()
    assert (out / "static" / "app.js").exists()
    assert (out / "static" / "charts.js").exists()
    assert (out / "static" / "styles.css").exists()

    for r in OVERVIEW_RANGES:
        ov_path = out / "data" / f"overview-{r}.json"
        assert ov_path.exists()
        assert json.loads(ov_path.read_text(encoding="utf-8"))["range"] == r

    gspc_doc = json.loads((out / "data" / "tickers" / "IDX_GSPC.json").read_text(encoding="utf-8"))
    assert gspc_doc["snapshot"]["symbol"] == "^GSPC"
    assert set(gspc_doc["ranges"].keys()) == set(DETAIL_RANGES)
