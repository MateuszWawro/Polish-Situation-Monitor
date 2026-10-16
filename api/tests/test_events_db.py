"""Endpoints against PostGIS with imported admin_units. Skipped without TEST_DATABASE_URL."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_engine
from app.main import app
from tests.conftest import needs_db

pytestmark = needs_db
client = TestClient(app)
SOURCES = {"imgw_meteo", "imgw_hydro", "gios", "firms", "gddkia", "adsb_lol", "emsc"}

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
    assert set(status) == SOURCES
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


def test_sources_history_has_7_days_per_source() -> None:
    body = client.get("/api/sources/history").json()
    assert {s["source"] for s in body} == SOURCES
    for s in body:
        assert len(s["days"]) == 7
        assert all(0 <= d["ok"] <= d["attempts"] for d in s["days"])


def test_water_levels() -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("""
            INSERT INTO hydro_stations (station_id, name, river, warning_cm, alarm_cm)
            VALUES ('999000001', 'Testowa', 'Wisła', 300, 400) ON CONFLICT DO NOTHING;
            INSERT INTO water_levels VALUES
              ('999000001', now() - interval '2 hours', 280),
              ('999000001', now() - interval '1 hour', 310),
              ('999000001', now() - interval '100 hours', 200)
            ON CONFLICT DO NOTHING;
        """)
        )
    try:
        body = client.get("/api/hydro/stations/999000001/levels?hours=72").json()
        assert body["warning_cm"] == 300 and body["alarm_cm"] == 400
        assert [cm for _, cm in body["levels"]] == [280, 310]  # oldest first, 100 h ago excluded
        assert client.get("/api/hydro/stations/999000002/levels").status_code == 404
        assert client.get("/api/hydro/stations/abc/levels").status_code == 422
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM water_levels WHERE station_id = '999000001'"))
            conn.execute(text("DELETE FROM hydro_stations WHERE station_id = '999000001'"))


def test_admin_bboxes() -> None:
    body = client.get("/api/admin-units/bboxes").json()
    assert set(body) == {"1261", "1465", "1661", "1807", "1861", "2061"}  # testdb fixture
    west, south, east, north = body["1861"]  # Krosno
    assert 21.6 < west < east < 21.9 and 49.6 < south < north < 49.8


def test_aircraft_hides_stale_positions() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM aircraft"))
        conn.execute(
            text("""
            INSERT INTO aircraft (hex, class, callsign, geom, seen_at) VALUES
              ('fresh', 'military', 'PLF693', ST_SetSRID(ST_MakePoint(21, 52.2), 4326), now()),
              ('stale', 'private', NULL, ST_SetSRID(ST_MakePoint(19, 50), 4326),
               now() - interval '10 minutes')
        """)
        )
    try:
        body = client.get("/api/aircraft").json()
        assert [f["id"] for f in body["features"]] == ["fresh"]
        props = body["features"][0]["properties"]
        assert props["class"] == "military" and props["callsign"] == "PLF693"
        assert body["features"][0]["geometry"]["coordinates"] == [21, 52.2]
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM aircraft"))


def test_satellites_filtered_by_group() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM satellites"))
        conn.execute(
            text("""
            INSERT INTO satellites (norad_id, name, grp, tle1, tle2, fetched_at) VALUES
              (25544, 'ISS (ZARYA)', 'stations', '1 25544U ...', '2 25544 ...', now()),
              (99999, 'STARLINK-1', 'starlink', '1 99999U ...', '2 99999 ...', now())
        """)
        )
    try:
        body = client.get("/api/satellites", params={"groups": "stations"}).json()
        assert [s["norad_id"] for s in body["satellites"]] == [25544]
        assert body["satellites"][0]["group"] == "stations"
        assert body["updated_at"] is not None
        # default = stations + visual, so the starlink row is excluded
        assert [s["norad_id"] for s in client.get("/api/satellites").json()["satellites"]] == [
            25544
        ]
        assert client.get("/api/satellites", params={"groups": "moon"}).status_code == 422
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM satellites"))
