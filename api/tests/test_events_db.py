"""Endpoints against PostGIS with imported admin_units. Skipped without DATABASE_URL."""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_engine
from app.main import app

pytestmark = pytest.mark.skipif("DATABASE_URL" not in os.environ, reason="needs PostGIS")
client = TestClient(app)

INSERT = text("""
    INSERT INTO events (source, source_event_id, type, severity, title, geom, teryt_powiat,
                        valid_from, valid_to, fetched_at, raw)
    VALUES (:source, :sid, :type, :severity, :title, ST_GeomFromText(:wkt, 4326), :teryt,
            now() - interval '1 hour', now() + CAST(:ends AS interval), now(), '{"k": 1}')
    RETURNING id
""")


@pytest.fixture
def events() -> Iterator[dict[str, uuid.UUID]]:
    rows = {
        # Warsaw fire, active, severity 3
        "warsaw": ("firms", "test:warsaw", "fire_hotspot", 3, "POINT(21 52.2)", ["1465"], "1 hour"),
        # Kraków air quality, active
        "krakow": ("gios", "test:krakow", "air_quality", 1, "POINT(19.9 50.1)", ["1261"], "1 hour"),
        # ended Warsaw fire
        "old": ("firms", "test:old", "fire_hotspot", 2, "POINT(21.0 52.2)", ["1465"], "-1 minute"),
    }  # fmt: skip
    ids = {}
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM events WHERE source_event_id LIKE 'test:%'"))
        for name, (source, sid, type_, sev, wkt, teryt, ends) in rows.items():
            ids[name] = conn.execute(INSERT, {
                "source": source, "sid": sid, "type": type_, "severity": sev, "title": name,
                "wkt": wkt, "teryt": teryt, "ends": ends,
            }).scalar_one()  # fmt: skip
    yield ids
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM events WHERE source_event_id LIKE 'test:%'"))


def titles(**params: str) -> set[str]:
    response = client.get("/api/events", params=params)
    assert response.status_code == 200
    return {
        f["properties"]["title"]
        for f in response.json()["features"]
        if f["properties"]["title"] in {"warsaw", "krakow", "old"}
    }


def test_filters(events: dict[str, uuid.UUID]) -> None:
    assert titles() == {"warsaw", "krakow"}
    assert titles(active="false") == {"warsaw", "krakow", "old"}
    assert titles(type="air_quality") == {"krakow"}
    assert titles(teryt="1465") == {"warsaw"}
    assert titles(teryt="12") == {"krakow"}  # voivodeship prefix
    assert titles(bbox="19.5,49.8,20.5,50.5") == {"krakow"}


def test_event_detail(events: dict[str, uuid.UUID]) -> None:
    body = client.get(f"/api/events/{events['warsaw']}").json()
    assert body["type"] == "Feature"
    assert body["properties"]["raw"] == {"k": 1}
    assert body["geometry"]["type"] == "Point"
    assert client.get(f"/api/events/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/events/not-a-uuid").status_code == 422


def test_sources_status_lists_all_sources() -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("""
            INSERT INTO source_status (source, last_success_at, expected_interval_s)
            VALUES ('imgw_meteo', now() - interval '31 minutes', 600)
            ON CONFLICT (source) DO UPDATE SET last_success_at = EXCLUDED.last_success_at,
                expected_interval_s = 600
        """)
        )
    status = {s["source"]: s for s in client.get("/api/sources/status").json()}
    assert set(status) == {"imgw_meteo", "imgw_hydro", "gios", "firms", "gddkia"}
    assert status["imgw_meteo"]["stale"] is True  # 31 min > 3 × 10 min
    assert status["imgw_meteo"]["age_s"] >= 31 * 60


def test_health_checks_database() -> None:
    assert client.get("/health").json() == {"status": "ok", "db": True}


def test_areas_summary(events: dict[str, uuid.UUID]) -> None:
    body = client.get("/api/areas/summary", params={"teryt": "1465,1261,0201"}).json()
    assert set(body) == {"1465", "1261", "0201"}
    titles = {code: {e["title"] for e in evs if e["title"] in {"warsaw", "krakow", "old"}}
              for code, evs in body.items()}  # fmt: skip
    assert titles == {"1465": {"warsaw"}, "1261": {"krakow"}, "0201": set()}  # "old" has ended
    assert "geometry" not in body["1465"][0]
    severities = [e["severity"] for e in body["1465"]]
    assert severities == sorted(severities, reverse=True)
