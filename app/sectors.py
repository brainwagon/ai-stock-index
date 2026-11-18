"""Sector definitions and watchlist persistence for AI & adjacent markets."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"

SECTOR_META: dict[str, dict[str, Any]] = {
    "core_ai": {
        "id": "core_ai",
        "name": "Core AI & Hyperscalers",
        "short_name": "Core AI",
        "color": "#38bdf8",
        "is_benchmark": False,
        "description": "Foundation model leaders, AI compute pioneers, and cloud hyperscalers.",
    },
    "semis": {
        "id": "semis",
        "name": "Semiconductors & Equipment",
        "short_name": "Semis",
        "color": "#a855f7",
        "is_benchmark": False,
        "description": "AI accelerators, foundry, memory, networking silicon, and lithography.",
    },
    "infra_power": {
        "id": "infra_power",
        "name": "Data Center Infra & Power",
        "short_name": "Infra & Power",
        "color": "#f59e0b",
        "is_benchmark": False,
        "description": "Thermal management, electrical gear, data center REITs, and nuclear/power.",
    },
    "software_robotics": {
        "id": "software_robotics",
        "name": "AI Software, Cloud & Robotics",
        "short_name": "Software & Robotics",
        "color": "#10b981",
        "is_benchmark": False,
        "description": "Enterprise data/AI platforms, observability, automation, and robotics.",
    },
    "benchmarks": {
        "id": "benchmarks",
        "name": "Benchmarks & Sector ETFs",
        "short_name": "ETFs & Benchmarks",
        "color": "#94a3b8",
        "is_benchmark": True,
        "description": "Broad market and thematic AI/semiconductor ETF benchmarks.",
    },
}

DEFAULT_TICKERS: list[dict[str, str]] = [
    # Core AI & Hyperscalers
    {"symbol": "NVDA", "name": "NVIDIA", "sector": "core_ai"},
    {"symbol": "MSFT", "name": "Microsoft", "sector": "core_ai"},
    {"symbol": "GOOGL", "name": "Alphabet", "sector": "core_ai"},
    {"symbol": "META", "name": "Meta Platforms", "sector": "core_ai"},
    {"symbol": "AMZN", "name": "Amazon", "sector": "core_ai"},
    {"symbol": "PLTR", "name": "Palantir", "sector": "core_ai"},
    {"symbol": "ANT", "name": "Anthropic", "sector": "core_ai"},  # Nasdaq IPO Nov 19, 2026
    # Semiconductors & Equipment
    {"symbol": "AMD", "name": "AMD", "sector": "semis"},
    {"symbol": "AVGO", "name": "Broadcom", "sector": "semis"},
    {"symbol": "TSM", "name": "TSMC", "sector": "semis"},
    {"symbol": "ASML", "name": "ASML", "sector": "semis"},
    {"symbol": "MU", "name": "Micron", "sector": "semis"},
    {"symbol": "ARM", "name": "Arm Holdings", "sector": "semis"},
    # Data Center Infrastructure & Power
    {"symbol": "VRT", "name": "Vertiv", "sector": "infra_power"},
    {"symbol": "ETN", "name": "Eaton", "sector": "infra_power"},
    {"symbol": "EQIX", "name": "Equinix", "sector": "infra_power"},
    {"symbol": "VST", "name": "Vistra", "sector": "infra_power"},
    {"symbol": "CEG", "name": "Constellation Energy", "sector": "infra_power"},
    {"symbol": "DLR", "name": "Digital Realty", "sector": "infra_power"},
    # AI Software, Cloud & Robotics
    {"symbol": "SNOW", "name": "Snowflake", "sector": "software_robotics"},
    {"symbol": "DDOG", "name": "Datadog", "sector": "software_robotics"},
    {"symbol": "CRM", "name": "Salesforce", "sector": "software_robotics"},
    {"symbol": "NOW", "name": "ServiceNow", "sector": "software_robotics"},
    {"symbol": "TSLA", "name": "Tesla", "sector": "software_robotics"},
    {"symbol": "ISRG", "name": "Intuitive Surgical", "sector": "software_robotics"},
    # Benchmarks & Sector ETFs
    {"symbol": "^GSPC", "name": "S&P 500 Index", "sector": "benchmarks"},
    {"symbol": "^NDX", "name": "NASDAQ 100 Index", "sector": "benchmarks"},
    {"symbol": "SPY", "name": "SPDR S&P 500", "sector": "benchmarks"},
    {"symbol": "QQQ", "name": "Invesco QQQ", "sector": "benchmarks"},
    {"symbol": "SMH", "name": "VanEck Semiconductor", "sector": "benchmarks"},
    {"symbol": "SOXX", "name": "iShares Semiconductor", "sector": "benchmarks"},
    {"symbol": "BOTZ", "name": "Global X Robotics & AI", "sector": "benchmarks"},
    {"symbol": "AIQ", "name": "Global X AI & Tech", "sector": "benchmarks"},
]


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[dict[str, str]]:
    """Load the active watchlist from disk, falling back to defaults."""
    if not path.exists():
        return deepcopy(DEFAULT_TICKERS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list) and all(
            isinstance(item, dict) and "symbol" in item and "sector" in item for item in raw
        ):
            valid = [
                {
                    "symbol": str(item["symbol"]).strip().upper(),
                    "name": str(item.get("name") or item["symbol"]).strip(),
                    "sector": str(item["sector"]).strip(),
                }
                for item in raw
                if str(item.get("sector")) in SECTOR_META and str(item.get("symbol", "")).strip()
            ]
            if valid:
                return valid
    except (OSError, ValueError):
        pass
    return deepcopy(DEFAULT_TICKERS)


def save_watchlist(items: list[dict[str, str]], path: Path = WATCHLIST_PATH) -> list[dict[str, str]]:
    """Persist the watchlist to disk and return the normalized list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [
        {
            "symbol": item["symbol"].strip().upper(),
            "name": item.get("name", item["symbol"]).strip(),
            "sector": item["sector"].strip(),
        }
        for item in items
        if item.get("sector") in SECTOR_META and item.get("symbol", "").strip()
    ]
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized


def reset_watchlist(path: Path = WATCHLIST_PATH) -> list[dict[str, str]]:
    """Reset the watchlist back to defaults."""
    return save_watchlist(deepcopy(DEFAULT_TICKERS), path=path)
