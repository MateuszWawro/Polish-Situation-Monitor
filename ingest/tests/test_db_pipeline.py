"""Full pipeline against PostGIS with imported admin_units. Skipped without TEST_DATABASE_URL."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
import respx

from ingest.adsb_gps import AdsbGpsWorker
from ingest.firms import FirmsWorker
from ingest.imgw_hydro import ImgwHydroWarningsWorker
from ingest.imgw_meteo import ImgwMeteoWorker
from tests.conftest import load

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ, reason="needs TEST_DATABASE_URL"
)


@pytest.fixture(scope="session")
def dsn() -> str:
    """Fresh dedicated test DB; never DATABASE_URL (that one holds real data)."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "db"))
    from testdb import prepare  # type: ignore[import-not-found]

    url = os.environ["TEST_DATABASE_URL"]
    prepare(url)
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("DELETE FROM events WHERE source = 'imgw_meteo'")
        c.execute("DELETE FROM source_status WHERE source = 'imgw_meteo'")
        yield c


def run(conn: psycopg.Connection, payload: Any, status: int = 200) -> int:
    worker = ImgwMeteoWorker(sleep=lambda _: None)
    with respx.mock, httpx.Client() as client:
        respx.get(worker.url).mock(return_value=httpx.Response(status, json=payload))
        return worker.run(conn, client)


def rows(conn: psycopg.Connection) -> list[tuple[Any, ...]]:
    return conn.execute(
        "SELECT source_event_id, severity, valid_to > now(), cardinality(teryt_powiat),"
        " ST_IsEmpty(geom), updated_at FROM events WHERE source = 'imgw_meteo'"
        " ORDER BY source_event_id"
    ).fetchall()


def test_upsert_is_idempotent_and_tracks_changes(
    conn: psycopg.Connection, meteo_payload: list[dict[str, Any]]
) -> None:
    payload = [{**w, "obowiazuje_do": "2099-01-01 00:00:00"} for w in meteo_payload]
    assert run(conn, payload) == len(payload)
    first = rows(conn)
    assert len(first) == len(payload)
    assert all(r[3] > 0 and r[4] is False for r in first)  # TERYT + geometry resolved

    run(conn, payload)
    assert rows(conn) == first  # unchanged → updated_at untouched, no duplicates

    payload[0] = {**payload[0], "stopien": "2"}
    run(conn, payload)
    changed = rows(conn)
    assert changed[0][1] == 2 and changed[0][5] > first[0][5]


def test_missing_warning_is_closed(
    conn: psycopg.Connection, meteo_payload: list[dict[str, Any]]
) -> None:
    payload = [{**w, "obowiazuje_do": "2099-01-01 00:00:00"} for w in meteo_payload]
    run(conn, payload)
    run(conn, payload[1:])
    active = {r[0]: r[2] for r in rows(conn)}
    assert active == {payload[0]["id"]: False, payload[1]["id"]: True}


def test_failure_recorded_and_data_kept(
    conn: psycopg.Connection, meteo_payload: list[dict[str, Any]]
) -> None:
    run(conn, meteo_payload)
    before = rows(conn)
    assert run(conn, None, status=500) == -1
    assert rows(conn) == before
    status = conn.execute(
        "SELECT last_success_at IS NOT NULL, last_error FROM source_status"
        " WHERE source = 'imgw_meteo'"
    ).fetchone()
    assert status is not None and status[0] and "500" in status[1]


def test_voivodeship_codes_expand_and_outside_poland_skipped(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM events WHERE source IN ('imgw_hydro', 'firms')")
    try:
        hydro = ImgwHydroWarningsWorker(sleep=lambda _: None)
        warning = {**load("imgw_hydro_warnings.json")[0], "obszary": [{"wojewodztwo": "opolskie"}]}
        firms = FirmsWorker(sleep=lambda _: None)
        rows = [  # Opole (PL) and Ostrava (CZ)
            {
                "latitude": "50.67",
                "longitude": "17.92",
                "acq_date": "2026-10-14",
                "acq_time": "0100",
                "satellite": "N20",
                "confidence": "high",
            },
            {
                "latitude": "49.83",
                "longitude": "18.29",
                "acq_date": "2026-10-14",
                "acq_time": "0100",
                "satellite": "N20",
                "confidence": "high",
            },
        ]
        with respx.mock, httpx.Client() as client:
            respx.get(hydro.url).mock(return_value=httpx.Response(200, json=[warning]))
            hydro.run(conn, client)
        firms.fetch = lambda client: rows  # type: ignore[method-assign]
        with httpx.Client() as client:
            firms.run(conn, client)
        found = conn.execute(
            "SELECT source, teryt_powiat FROM events WHERE source IN ('imgw_hydro', 'firms')"
        ).fetchall()
        by_source = {source: teryt for source, teryt in found}
        assert len(found) == 2
        assert by_source["imgw_hydro"] and all(t.startswith("16") for t in by_source["imgw_hydro"])
        assert by_source["firms"] == ["1661"]  # city of Opole
    finally:
        conn.execute("DELETE FROM events WHERE source IN ('imgw_hydro', 'firms')")


def test_runs_are_logged_and_station_history_kept(conn: psycopg.Connection) -> None:
    from datetime import datetime

    from ingest.imgw_hydro import ImgwHydroStationsWorker
    from ingest.imgw_meteo import WARSAW

    conn.execute("DELETE FROM water_levels WHERE station_id LIKE 'test%'")
    conn.execute("DELETE FROM hydro_stations WHERE station_id LIKE 'test%'")
    worker = ImgwHydroStationsWorker(sleep=lambda _: None)
    now = datetime.now(WARSAW).strftime("%Y-%m-%d %H:%M:00")
    station = {"id_stacji": "test1", "stacja": "Testowa", "rzeka": "Wisła", "lat": "52.2",
               "lon": "21.0", "stan_wody": "120", "stan_wody_data_pomiaru": now,
               "stan_ostrzegawczy": "300", "stan_alarmowy": "400"}  # fmt: skip
    try:
        with respx.mock, httpx.Client() as client:
            respx.get(worker.url).mock(return_value=httpx.Response(200, json=[station]))
            worker.run(conn, client)
            worker.run(conn, client)  # same reading again → stored once
        levels = conn.execute(
            "SELECT level_cm FROM water_levels WHERE station_id = 'test1'"
        ).fetchall()
        assert levels == [(120.0,)]
        meta = conn.execute(
            "SELECT warning_cm, alarm_cm FROM hydro_stations WHERE station_id = 'test1'"
        ).fetchone()
        assert meta == (300.0, 400.0)
        attempts = conn.execute(
            "SELECT ok, items FROM fetch_attempts WHERE worker = 'ImgwHydroStationsWorker'"
            " ORDER BY id DESC LIMIT 2"
        ).fetchall()
        assert attempts == [(True, 0), (True, 0)]  # below warning level → no events
    finally:
        conn.execute("DELETE FROM water_levels WHERE station_id LIKE 'test%'")
        conn.execute("DELETE FROM hydro_stations WHERE station_id LIKE 'test%'")


def test_gps_interference_cells_in_poland_only(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM events WHERE source = 'adsb_lol'")
    worker = AdsbGpsWorker(sleep=lambda _: None)

    def ac(prefix: str, lat: float, lon: float, nac_p: int, n: int) -> list[dict[str, Any]]:
        return [{"hex": f"{prefix}{i}", "lat": lat, "lon": lon, "nac_p": nac_p, "version": 2,
                 "alt_baro": 35000} for i in range(n)]  # fmt: skip

    def run_adsb(aircraft: list[dict[str, Any]]) -> None:
        with respx.mock, httpx.Client() as client:
            respx.get(worker.url).mock(return_value=httpx.Response(200, json={"ac": aircraft}))
            worker.run(conn, client)

    # Białystok (in Poland) and a cell entirely over Kaliningrad, both 40 % degraded.
    run_adsb(ac("b", 53.1, 23.2, 0, 5) + ac("g", 53.1, 23.2, 10, 5)
             + ac("k", 54.8, 20.5, 0, 5) + ac("n", 54.8, 20.5, 10, 5))  # fmt: skip
    found = conn.execute(
        "SELECT source_event_id, severity, valid_to IS NULL, '2061' = ANY(teryt_powiat)"
        " FROM events WHERE source = 'adsb_lol'"
    ).fetchall()
    assert found == [("106:30", 3, True, True)]  # Białystok city powiat; Kaliningrad dropped

    worker.window.clear()
    run_adsb(ac("g", 53.1, 23.2, 10, 10))
    closed = conn.execute(
        "SELECT valid_to <= now() FROM events WHERE source = 'adsb_lol'"
    ).fetchone()
    assert closed == (True,)
    conn.execute("DELETE FROM events WHERE source = 'adsb_lol'")


def test_aircraft_snapshot_replaced_each_run(conn: psycopg.Connection) -> None:
    worker = AdsbGpsWorker(sleep=lambda _: None)

    def run_adsb(aircraft: list[dict[str, Any]]) -> None:
        with respx.mock, httpx.Client() as client:
            respx.get(worker.url).mock(return_value=httpx.Response(200, json={"ac": aircraft}))
            worker.run(conn, client)

    plane = {"lat": 52.2, "lon": 21.0, "alt_baro": 34000, "gs": 450.0, "track": 90.0}
    run_adsb([{"hex": "a1", "flight": "LOT1 ", **plane}, {"hex": "a2", "dbFlags": 1, **plane}])
    got = conn.execute("SELECT hex, class, callsign FROM aircraft ORDER BY hex").fetchall()
    assert got == [("a1", "commercial", "LOT1"), ("a2", "military", None)]

    run_adsb([{"hex": "a3", **plane}])
    assert conn.execute("SELECT hex, class FROM aircraft").fetchall() == [("a3", "private")]
    conn.execute("DELETE FROM aircraft")
    conn.execute("DELETE FROM events WHERE source = 'adsb_lol'")


def test_satellites_snapshot_replaced(conn: psycopg.Connection) -> None:
    from ingest import satellites

    conn.execute("DELETE FROM satellites")
    tle = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   26288.11220063  .00005682  00000+0  11168-3 0  9991\n"
        "2 25544  51.6331  66.6267 0006716 264.3647  95.6576 15.48871015590345\n"
    )

    def run_sats(groups: list[str]) -> None:
        rows = [r for g in groups for r in satellites.parse_tle(tle, g)]
        satellites.store(conn, rows)

    # ISS appears in both groups; ON CONFLICT keeps the first (priority) group.
    run_sats(["stations", "visual"])
    got = conn.execute("SELECT norad_id, name, grp FROM satellites").fetchall()
    assert got == [(25544, "ISS (ZARYA)", "stations")]

    run_sats(["visual"])
    assert conn.execute("SELECT grp FROM satellites").fetchall() == [("visual",)]
    conn.execute("DELETE FROM satellites")
