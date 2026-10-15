"""HTTP behaviour without a database: validation, ETag, cache, rate limit."""

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.conftest import FakeRedis

client = TestClient(main.app)
BODY = '{"type": "FeatureCollection", "features": []}'


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    seen: list[dict[str, object]] = []

    def fake_query(sql: object, params: dict[str, object]) -> str:
        seen.append(params)
        return BODY

    monkeypatch.setattr(main, "query_json", fake_query)
    return seen


@pytest.mark.parametrize(
    "params",
    [
        {"type": "earthquake"},
        {"bbox": "14,49,24"},
        {"bbox": "24,49,14,54"},
        {"bbox": "a,b,c,d"},
        {"teryt": "123"},
        {"teryt": "14;65"},
    ],
)
def test_invalid_params_rejected(params: dict[str, str], calls: list[object]) -> None:
    assert client.get("/api/events", params=params).status_code == 422
    assert calls == []


def test_params_passed_to_query(calls: list[dict[str, object]]) -> None:
    response = client.get(
        "/api/events",
        params={"type": "fire_hotspot,air_quality", "bbox": "14,49,24.2,54.9", "teryt": "1465,24"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    assert calls[0]["types"] == ["air_quality", "fire_hotspot"]
    assert calls[0]["codes"] == ["1465", "24"]
    assert (calls[0]["west"], calls[0]["north"]) == (14.0, 54.9)
    assert response.headers["cache-control"] == "public, max-age=300"


def test_etag_returns_304(calls: list[object]) -> None:
    first = client.get("/api/events")
    second = client.get("/api/events", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304 and second.content == b""


def test_redis_cache_hit_skips_database(calls: list[object], fake_redis: FakeRedis) -> None:
    for _ in range(3):
        assert client.get("/api/events?type=weather_warning").json()["features"] == []
    assert len(calls) == 1


def test_rate_limit(calls: list[object], fake_redis: FakeRedis) -> None:
    statuses = [client.get("/api/events").status_code for _ in range(main.RATE_LIMIT_PER_MIN + 1)]
    assert statuses[-2:] == [200, 429]
    assert all(isinstance(k, str) and "testclient" not in k for k in fake_redis.data)


def test_gzip_for_large_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    big = '{"type": "FeatureCollection", "features": [' + ",".join(["{}"] * 2000) + "]}"
    monkeypatch.setattr(main, "query_json", lambda sql, params: big)
    response = client.get("/api/events", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"


def test_health_reports_database_down(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.exc import OperationalError

    def broken() -> None:
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr(main, "get_engine", broken)
    response = client.get("/health")
    assert response.status_code == 503 and response.json()["db"] is False
