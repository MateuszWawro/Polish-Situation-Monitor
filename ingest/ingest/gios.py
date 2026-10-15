"""GIOŚ air quality index per station (see docs/SOURCES.md §3)."""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ingest.base import Event, Worker
from ingest.imgw_meteo import local

log = logging.getLogger(__name__)

BASE = "https://api.gios.gov.pl/pjp-api/v1/rest"
STATIONS_TTL_S = 24 * 3600  # station list endpoint allows only a few requests per minute
REQUEST_GAP_S = 0.2  # ~5 req/s, far below the 1500 req/min index limit
# decision 2026-10-15: index 0–5 → severity 0–3
SEVERITY = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 3}


class GiosStation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int = Field(alias="Identyfikator stacji")
    name: str = Field(alias="Nazwa stacji")
    lat: float = Field(alias="WGS84 φ N")
    lon: float = Field(alias="WGS84 λ E")
    city: str | None = Field(None, alias="Nazwa miasta")


class GiosIndex(BaseModel):
    value: int | None = Field(None, alias="Wartość indeksu")
    category: str | None = Field(None, alias="Nazwa kategorii indeksu")
    calculated_at: datetime | None = Field(None, alias="Data wykonania obliczeń indeksu")
    ok: bool | None = Field(None, alias="Status indeksu ogólnego dla stacji pomiarowej")
    critical: str | None = Field(None, alias="Kod zanieczyszczenia krytycznego")


class AirQuality(BaseModel):
    station: GiosStation
    index: GiosIndex | None


class GiosWorker(Worker[AirQuality]):
    source = "gios"
    url = f"{BASE}/station/findAll?size=500"
    interval_s = 1800
    model = AirQuality

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stations: list[dict[str, Any]] = []
        self._stations_at = 0.0

    def stations(self, client: httpx.Client) -> list[dict[str, Any]]:
        if not self._stations or time.monotonic() - self._stations_at > STATIONS_TTL_S:
            stations, url = [], self.url
            for _ in range(20):  # page guard
                body = self.get(client, url).json()
                stations += body["Lista stacji pomiarowych"]
                next_url = body.get("links", {}).get("next")
                if body.get("totalPages", 1) <= 1 or not next_url or next_url == url:
                    break
                url = next_url
            self._stations, self._stations_at = stations, time.monotonic()
        return self._stations

    def fetch(self, client: httpx.Client) -> list[dict[str, Any]]:
        items, failures = [], 0
        stations = self.stations(client)
        for station in stations:
            sid = station["Identyfikator stacji"]
            try:
                index = self.get(client, f"{BASE}/aqindex/getIndex/{sid}").json().get("AqIndex")
            except httpx.HTTPError as exc:
                failures += 1
                log.warning("gios: index for station %s failed: %s", sid, exc)
                continue
            finally:
                self.sleep(REQUEST_GAP_S)
            items.append({"station": station, "index": index})
        if stations and not items:
            raise RuntimeError(f"gios: all {failures} index requests failed")
        return items

    def normalize(self, item: AirQuality) -> Event | None:
        s, idx = item.station, item.index
        if idx is None or idx.value not in SEVERITY or not idx.ok or idx.calculated_at is None:
            return None  # station without a current index (no data)
        where = f"{s.name}" + (f" ({s.city})" if s.city and s.city not in s.name else "")
        critical = f", zanieczyszczenie decydujące: {idx.critical}" if idx.critical else ""
        calculated = local(idx.calculated_at)
        return Event(
            source_event_id=str(s.id),
            type="air_quality",
            severity=SEVERITY[idx.value],
            title=f"Jakość powietrza: {idx.category or idx.value}",
            description=f"Stacja {where}. Indeks jakości powietrza: "
            f"{idx.category or idx.value}{critical}.",
            valid_from=calculated,
            # index is hourly; an index not refreshed for 3 h is no longer "current"
            valid_to=calculated + timedelta(hours=3),
            source_url="https://powietrze.gios.gov.pl/",
            geom_wkt=f"POINT({s.lon} {s.lat})",
            raw=item.model_dump(mode="json", by_alias=True),
        )
