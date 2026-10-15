"""Aircraft over Poland for the map layer (adsb.lol, see docs/SOURCES.md §10).

Only the latest snapshot is stored: the table is replaced on every run, so no flight
tracks are accumulated. Aircraft whose owners asked not to be shown (FAA LADD, PIA)
are skipped.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import psycopg
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

AircraftClass = Literal["commercial", "private", "military"]

# Poland's bbox (west, south, east, north); the API circle also covers the neighbours.
BBOX = (14.07, 49.00, 24.15, 54.84)
MAX_POSITION_AGE_S = 60
# adsb.lol dbFlags bits: 1 military, 2 interesting, 4 PIA, 8 LADD.
FLAG_MILITARY = 1
FLAGS_HIDDEN = 4 | 8
# ICAO airline designator + flight number, e.g. LOT3AB, RYR12QK, DLH4CM.
AIRLINE_CALLSIGN = re.compile(r"^[A-Z]{3}\d[0-9A-Z]{0,4}$")
# Wake categories A3–A6 (≥ 34 t): practically always airliners or cargo.
LARGE_CATEGORIES = {"A3", "A4", "A5", "A6"}
# Airport ground stations and vehicles that some feeders report as "aircraft".
GROUND_REGISTRATIONS = {"TWR", "GND"}


class MapAircraft(BaseModel):
    hex: str
    lat: float
    lon: float
    flight: str | None = None
    r: str | None = None
    t: str | None = None
    category: str | None = None
    dbFlags: int = 0  # noqa: N815 – API field name
    alt_baro: int | str | None = None
    gs: float | None = None
    track: float | None = None
    seen_pos: float = 0.0


def classify(ac: MapAircraft) -> AircraftClass:
    if ac.dbFlags & FLAG_MILITARY:
        return "military"
    callsign = (ac.flight or "").strip()
    if AIRLINE_CALLSIGN.match(callsign) or ac.category in LARGE_CATEGORIES:
        return "commercial"
    # Light aircraft, helicopters (incl. rescue and police), gliders, unknown.
    return "private"


def parse(raw: Any) -> MapAircraft | None:
    """Airborne aircraft over Poland with a fresh position, else None."""
    if not isinstance(raw, dict) or "lat" not in raw:
        return None
    try:
        ac = MapAircraft.model_validate(raw)
    except ValidationError as exc:
        log.warning("adsb_lol: skipping invalid aircraft: %s", exc)
        return None
    west, south, east, north = BBOX
    if not (south <= ac.lat <= north and west <= ac.lon <= east):
        return None
    if ac.dbFlags & FLAGS_HIDDEN or ac.seen_pos > MAX_POSITION_AGE_S:
        return None
    if ac.alt_baro == "ground" or (ac.category or "").startswith("C"):  # C* = surface/obstacle
        return None
    if ac.r in GROUND_REGISTRATIONS:
        return None
    return ac


REPLACE_SQL = "DELETE FROM aircraft"
INSERT_SQL = """
INSERT INTO aircraft (hex, class, callsign, registration, aircraft_type, altitude_ft,
                      speed_kt, track, geom, seen_at)
VALUES (%(hex)s, %(class)s, %(callsign)s, %(registration)s, %(type)s, %(altitude)s,
        %(speed)s, %(track)s, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(seen_at)s)
ON CONFLICT (hex) DO NOTHING
"""


def rows(aircraft: list[MapAircraft], now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "hex": ac.hex,
            "class": classify(ac),
            "callsign": (ac.flight or "").strip() or None,
            "registration": ac.r,
            "type": ac.t,
            "altitude": ac.alt_baro if isinstance(ac.alt_baro, int) else None,
            "speed": ac.gs,
            "track": ac.track,
            "lat": ac.lat,
            "lon": ac.lon,
            "seen_at": now - timedelta(seconds=ac.seen_pos),
        }
        for ac in aircraft
    ]


def replace_snapshot(conn: psycopg.Connection, aircraft: list[MapAircraft]) -> None:
    with conn.cursor() as cur:
        cur.execute(REPLACE_SQL)
        cur.executemany(INSERT_SQL, rows(aircraft, datetime.now(UTC)))
