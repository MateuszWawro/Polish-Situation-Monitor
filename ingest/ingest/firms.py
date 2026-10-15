"""NASA FIRMS VIIRS fire hotspots (see docs/SOURCES.md §4).

Uses the public, key-less 24 h Europe CSV files (same columns as the MAP_KEY area API).
Suomi NPP deliveries end 2026-11-02, so only NOAA-20 and NOAA-21 are used.
"""

import csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from ingest.base import Event, Worker

URLS = [
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_Europe_24h.csv",
]
# Poland's bbox (west, south, east, north): cheap pre-filter; exact test is ST_Intersects.
BBOX = (14.07, 49.00, 24.15, 54.84)
SEVERITY = {"low": 1, "nominal": 2, "high": 3}
CONFIDENCE_PL = {"low": "niska", "nominal": "średnia", "high": "wysoka"}


class FireHotspot(BaseModel):
    latitude: float
    longitude: float
    acq_date: date
    acq_time: str = Field(pattern=r"^\d{4}$")
    satellite: str
    confidence: Literal["low", "nominal", "high"]
    frp: float | None = None
    daynight: str | None = None


class FirmsWorker(Worker[FireHotspot]):
    source = "firms"
    url = URLS[0]
    interval_s = 1800
    model = FireHotspot

    def fetch(self, client: httpx.Client) -> list[dict[str, Any]]:
        west, south, east, north = BBOX
        rows = []
        for url in URLS:
            for row in csv.DictReader(io.StringIO(self.get(client, url).text)):
                try:
                    lat, lon = float(row["latitude"]), float(row["longitude"])
                except (KeyError, ValueError):
                    rows.append(row)  # let validation report it
                    continue
                if south <= lat <= north and west <= lon <= east:
                    rows.append(row)
        return rows

    def normalize(self, item: FireHotspot) -> Event | None:
        acquired = datetime.combine(item.acq_date, datetime.min.time(), UTC) + timedelta(
            hours=int(item.acq_time[:2]), minutes=int(item.acq_time[2:])
        )
        frp = f", moc promieniowania {item.frp:g} MW" if item.frp is not None else ""
        lat, lon = round(item.latitude, 5), round(item.longitude, 5)
        return Event(
            source_event_id=f"{item.satellite}:{item.acq_date}:{item.acq_time}:{lat}:{lon}",
            type="fire_hotspot",
            severity=SEVERITY[item.confidence],
            title="Punkt cieplny (możliwy pożar)",
            description=f"Wykrycie satelitarne VIIRS ({item.satellite}), "
            f"pewność: {CONFIDENCE_PL[item.confidence]}{frp}.",
            valid_from=acquired,
            valid_to=acquired + timedelta(hours=24),
            source_url=f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{lon},{lat},12.00z",
            geom_wkt=f"POINT({lon} {lat})",
            raw=item.model_dump(mode="json"),
        )
