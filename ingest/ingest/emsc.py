"""EMSC earthquakes and mining tremors (see docs/SOURCES.md §9)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from ingest.base import Event, Worker

QUERY_URL = (
    "https://www.seismicportal.eu/fdsnws/event/1/query?format=json"
    "&minlat=48.5&maxlat=55.5&minlon=13.5&maxlon=24.5&limit=500"
)
WINDOW = timedelta(days=7)
VISIBLE_FOR = timedelta(hours=24)
# EMSC region names are English upper case; the ones around Poland in Polish.
REGIONS = {"POLAND": "Polska", "CZECH REPUBLIC": "Czechy", "SLOVAKIA": "Słowacja",
           "GERMANY": "Niemcy", "LITHUANIA": "Litwa", "UKRAINE": "Ukraina"}  # fmt: skip
EVTYPES = {"ke": "trzęsienie ziemi", "km": "wstrząs górniczy", "qb": "odstrzał w kamieniołomie"}


class Quake(BaseModel):
    unid: str
    time: datetime
    lon: float
    lat: float
    mag: float
    magtype: str | None = None
    depth: float | None = None
    evtype: str | None = None
    flynn_region: str = ""


def severity(mag: float) -> int:
    return 0 if mag < 2.0 else 1 if mag < 3.0 else 2 if mag < 4.0 else 3


def region(name: str) -> str:
    return REGIONS.get(name, name.title())


class EmscWorker(Worker[Quake]):
    source = "emsc"
    url = QUERY_URL
    interval_s = 900
    model = Quake

    def fetch(self, client: httpx.Client) -> list[dict[str, Any]]:
        start = (datetime.now(UTC) - WINDOW).strftime("%Y-%m-%dT%H:%M:%S")
        payload = self.get(client, f"{self.url}&starttime={start}").json()
        # Geometry wins over the duplicated lat/lon properties.
        return [
            {**f["properties"], "lon": f["geometry"]["coordinates"][0],
             "lat": f["geometry"]["coordinates"][1]}
            for f in payload["features"]
        ]  # fmt: skip

    def normalize(self, item: Quake) -> Event | None:
        details = [f"Magnituda {item.mag:g}" + (f" ({item.magtype})" if item.magtype else "")]
        if item.depth is not None:
            details.append(f"głębokość {item.depth:g} km")
        if item.evtype:
            details.append(f"typ: {EVTYPES.get(item.evtype, item.evtype)}")
        return Event(
            source_event_id=item.unid,
            type="earthquake",
            severity=severity(item.mag),
            title=f"Wstrząs M{item.mag:.1f} – {region(item.flynn_region)}",
            description="\n".join(details),
            valid_from=item.time,
            valid_to=item.time + VISIBLE_FOR,
            source_url=f"https://www.seismicportal.eu/eventdetails.html?unid={item.unid}",
            geom_wkt=f"POINT({item.lon} {item.lat})",
            raw=item.model_dump(mode="json"),
        )
