"""Full pipeline against PostGIS with imported admin_units. Skipped without DATABASE_URL."""

import os
from collections.abc import Iterator
from typing import Any

import httpx
import psycopg
import pytest
import respx

from ingest.imgw_meteo import ImgwMeteoWorker

pytestmark = pytest.mark.skipif("DATABASE_URL" not in os.environ, reason="needs PostGIS")


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("DELETE FROM events WHERE source = 'imgw_meteo'")
        c.execute("DELETE FROM source_status WHERE source = 'imgw_meteo'")
        yield c
        c.execute("DELETE FROM events WHERE source = 'imgw_meteo'")
        c.execute("DELETE FROM source_status WHERE source = 'imgw_meteo'")


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
