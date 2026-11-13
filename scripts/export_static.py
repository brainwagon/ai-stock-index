"""Export a self-contained static site + precomputed JSON snapshots for GitHub Pages."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.market_data import MarketDataService, market_service  # noqa: E402

OVERVIEW_RANGES = ("1W", "1M", "3M", "YTD", "1Y")
DETAIL_RANGES = ("1D", "1W", "1M", "3M", "YTD", "1Y")


def safe_symbol_filename(symbol: str) -> str:
    """Convert ticker symbol (including ^indices) to a URL/filesystem-safe stem."""
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        return f"IDX_{clean[1:]}"
    return clean.replace("/", "_")


def export_static_site(
    out_dir: Path,
    service: MarketDataService = market_service,
) -> dict[str, Any]:
    """Build static HTML/CSS/JS + JSON market data snapshots into out_dir."""
    static_src = REPO_ROOT / "static"
    out_dir = out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Root index.html + static/ assets (mirrors FastAPI's URL layout on any subpath)
    shutil.copy2(static_src / "index.html", out_dir / "index.html")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    static_dst = out_dir / "static"
    static_dst.mkdir(parents=True, exist_ok=True)
    for asset in ("styles.css", "charts.js", "app.js"):
        shutil.copy2(static_src / asset, static_dst / asset)

    data_dir = out_dir / "data"
    tickers_dir = data_dir / "tickers"
    tickers_dir.mkdir(parents=True, exist_ok=True)

    overview_ytd: dict[str, Any] | None = None
    for idx, range_key in enumerate(OVERVIEW_RANGES):
        payload = service.get_overview(range_key=range_key, force_refresh=(idx == 0))
        (data_dir / f"overview-{range_key}.json").write_text(
            json.dumps(payload, separators=(",", ":")),
            encoding="utf-8",
        )
        if range_key == "YTD":
            overview_ytd = payload

    symbols = [t["symbol"] for t in (overview_ytd or {}).get("tickers", [])]
    for sym in symbols:
        ranges_payload: dict[str, Any] = {}
        snapshot: dict[str, Any] | None = None
        for d_range in DETAIL_RANGES:
            detail = service.get_ticker_detail(symbol=sym, range_key=d_range)
            if snapshot is None:
                snapshot = detail["snapshot"]
            ranges_payload[d_range] = detail["series"]

        ticker_doc = {
            "snapshot": snapshot,
            "ranges": ranges_payload,
        }
        fname = f"{safe_symbol_filename(sym)}.json"
        (tickers_dir / fname).write_text(
            json.dumps(ticker_doc, separators=(",", ":")),
            encoding="utf-8",
        )

    return {
        "out_dir": str(out_dir),
        "overview_files": len(OVERVIEW_RANGES),
        "ticker_files": len(symbols),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export static AI stock index site.")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "dist",
        help="Output directory for static site (default: ./dist)",
    )
    args = parser.parse_args()
    summary = export_static_site(out_dir=args.out)
    print(
        f"Exported static site to {summary['out_dir']} "
        f"({summary['overview_files']} overviews, {summary['ticker_files']} tickers)"
    )


if __name__ == "__main__":
    main()
