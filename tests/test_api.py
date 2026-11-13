"""API integration tests using FastAPI TestClient with mocked MarketDataService."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, market_service

client = TestClient(app)


def test_health_endpoint() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_index_html_served() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "AI &amp; Adjacent Markets Index" in res.text


def test_overview_endpoint_with_mocked_service(monkeypatch) -> None:
    fake_payload = {
        "generated_at": "2026-11-13T17:30:00+00:00",
        "market_timestamp": "2026-11-13 12:30 ET",
        "range": "YTD",
        "sector_meta": [],
        "composite": {"constituent_count": 2, "up_count": 1, "down_count": 1, "breadth_pct": 50, "equal": {}, "cap": {}, "benchmarks": {}},
        "sectors": [],
        "tickers": [],
        "unusual_moves": [],
        "chart": {"dates": [], "series": []},
        "intraday_chart": {"timestamps": [], "series": []},
        "correlations": {"labels": [], "matrix": [], "window": "YTD"},
    }
    monkeypatch.setattr(market_service, "get_overview", lambda range_key="YTD", force_refresh=False: fake_payload)
    res = client.get("/api/market/overview?range=YTD")
    assert res.status_code == 200
    body = res.json()
    assert body["range"] == "YTD"
    assert body["composite"]["constituent_count"] == 2
