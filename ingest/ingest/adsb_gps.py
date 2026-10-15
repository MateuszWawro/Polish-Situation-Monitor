"""Possible GPS interference estimated from ADS-B (adsb.lol, see docs/SOURCES.md §9).

Aircraft broadcast how accurate their GPS position is (NACp). When a share of aircraft
in an area reports degraded accuracy, GNSS interference (jamming) there is likely.
This is the gpsjam.org method, but over a rolling 60-minute window instead of a day.

Not an official source and not proof of jamming: low NACp can also come from aircraft
equipment. The map labels the layer as an estimate.
"""

import logging
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from ingest.base import Event, Worker

log = logging.getLogger(__name__)

# One circle covers all of Poland: the farthest corner (Bieszczady) is ~420 km away,
# 250 NM (the API maximum) is 463 km. Neighbours are dropped by the powiat intersection.
URL = "https://api.adsb.lol/v2/point/51.9/19.3/250"

CELL_LAT = 0.5  # ~55 km
CELL_LON = 0.75  # ~50 km at Polish latitudes
WINDOW_S = 3600
BAD_NACP = 8  # NACp < 8 = estimated position error ≥ 93 m; airliners normally report 9–11
MIN_AIRCRAFT = 8  # distinct aircraft per cell in the window; fewer → no estimate
MAX_POSITION_AGE_S = 60
# Share of aircraft with degraded accuracy → severity (gpsjam.org uses 2 % and 10 %).
SEVERITY_THRESHOLDS = ((30.0, 3), (10.0, 2), (2.0, 1))


class Aircraft(BaseModel):
    hex: str
    lat: float
    lon: float
    nac_p: int
    version: int
    alt_baro: int | str | None = None
    seen_pos: float = 0.0
    mlat: list[str] = []
    tisb: list[str] = []


class Cell(BaseModel):
    row: int
    col: int
    total: int
    bad: int


@dataclass(frozen=True)
class Report:
    hex: str
    cell: tuple[int, int]
    bad: bool


def usable(raw: dict[str, Any]) -> Aircraft | None:
    """Airborne ADS-B v2 aircraft with a fresh, GPS-derived position, else None."""
    if raw.get("version") != 2 or raw.get("nac_p") is None or "lat" not in raw:
        return None
    try:
        ac = Aircraft.model_validate(raw)
    except ValidationError as exc:
        log.warning("adsb_lol: skipping invalid aircraft: %s", exc)
        return None
    # Multilateration / TIS-B positions are computed on the ground: NACp says nothing there.
    if "lat" in ac.mlat or "lat" in ac.tisb:
        return None
    if ac.alt_baro == "ground" or ac.seen_pos > MAX_POSITION_AGE_S:
        return None
    return ac


def cell_of(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / CELL_LAT), math.floor(lon / CELL_LON)


def share_pct(bad: int, total: int) -> float:
    # gpsjam.org formula: one bad aircraft alone never counts (fewer false positives).
    return max(0.0, 100 * (bad - 1) / total)


def aggregate(snapshots: list[list[Report]]) -> list[Cell]:
    """Distinct aircraft per cell over all snapshots; an aircraft is bad if it ever was there."""
    seen: dict[tuple[int, int], dict[str, bool]] = {}
    for snapshot in snapshots:
        for r in snapshot:
            per_cell = seen.setdefault(r.cell, {})
            per_cell[r.hex] = per_cell.get(r.hex, False) or r.bad
    return [
        Cell(row=row, col=col, total=len(hexes), bad=sum(hexes.values()))
        for (row, col), hexes in sorted(seen.items())
    ]


class AdsbGpsWorker(Worker[Cell]):
    source = "adsb_lol"
    url = URL
    interval_s = 120
    model = Cell

    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(sleep)
        self.clock = clock
        # In memory on purpose: after a restart the window simply refills within an hour.
        self.window: deque[tuple[float, list[Report]]] = deque()
        self.elevated_since: dict[str, datetime] = {}

    def fetch(self, client: httpx.Client) -> list[dict[str, Any]]:
        payload = self.get(client, self.url).json()
        if not isinstance(payload, dict) or not isinstance(payload.get("ac"), list):
            raise ValueError("adsb_lol: expected an object with an 'ac' array")
        reports = [
            Report(ac.hex, cell_of(ac.lat, ac.lon), ac.nac_p < BAD_NACP)
            for raw in payload["ac"]
            if isinstance(raw, dict) and (ac := usable(raw))
        ]
        now = self.clock()
        self.window.append((now, reports))
        while self.window and self.window[0][0] < now - WINDOW_S:
            self.window.popleft()
        return [c.model_dump() for c in aggregate([r for _, r in self.window])]

    def normalize(self, item: Cell) -> Event | None:
        cell_id = f"{item.row}:{item.col}"
        pct = share_pct(item.bad, item.total)
        severity = next((s for limit, s in SEVERITY_THRESHOLDS if pct >= limit), 0)
        if item.total < MIN_AIRCRAFT or severity == 0:
            self.elevated_since.pop(cell_id, None)
            return None
        now = datetime.fromtimestamp(self.clock(), UTC)
        since = self.elevated_since.setdefault(cell_id, now)
        south, west = item.row * CELL_LAT, item.col * CELL_LON
        north, east = south + CELL_LAT, west + CELL_LON
        lat, lon = round(south + CELL_LAT / 2, 3), round(west + CELL_LON / 2, 3)
        return Event(
            source_event_id=cell_id,
            type="gps_interference",
            severity=severity,
            title="Możliwe zakłócenia GPS",
            description=(
                f"W ostatniej godzinie {item.bad} z {item.total} samolotów w tym obszarze "
                f"zgłaszało obniżoną dokładność pozycji GPS (szacunek: {pct:.0f}%). "
                "Wynik oparty na społecznościowych danych ADS-B – wskazuje prawdopodobne "
                "zakłócenia, nie potwierdza zagłuszania."
            ),
            valid_from=since,
            valid_to=None,  # open-ended; closed when the cell drops below the threshold
            source_url=f"https://adsb.lol/?lat={lat}&lon={lon}&zoom=8",
            geom_wkt=(
                f"POLYGON(({west} {south},{east} {south},{east} {north},"
                f"{west} {north},{west} {south}))"
            ),
            raw={**item.model_dump(), "pct": round(pct, 1), "window_s": WINDOW_S},
        )
