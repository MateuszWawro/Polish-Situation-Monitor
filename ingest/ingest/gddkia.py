"""GDDKiA road incidents on national roads (see docs/SOURCES.md §6)."""

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, field_validator

from ingest.base import Event, Worker
from ingest.imgw_hydro import VOIVODESHIPS

LIMITS = {
    "ogr_predkosc": ("ograniczenie prędkości", "km/h"),
    "ogr_nosnosc": ("ograniczenie nośności", "t"),
    "ogr_nacisk": ("ograniczenie nacisku osi", "t"),
    "ogr_szerokosc": ("ograniczenie szerokości", "m"),
    "ogr_skrajnia_pionowa": ("ograniczenie wysokości", "m"),
}
# Severity 2 labels, in priority order (decision 2026-10-15, docs/SOURCES.md §6).
RESTRICTIONS = {
    "awaria_mostu": "Awaria mostu",
    "ruch_wahadlowy": "Ruch wahadłowy",
    "ruch_2_kierunkowy": "Ruch dwukierunkowy na jednej jezdni",
    "sygnalizacja_swietlna": "Sygnalizacja świetlna",
}


class RoadIncident(BaseModel):
    typ: str
    nr_drogi: str
    woj: str
    km: str | None = None
    dl: float | None = None
    geo_lat: float | None = None
    geo_long: float | None = None
    nazwa_odcinka: str
    data_powstania: datetime
    data_likwidacji: datetime | None = None
    objazd: str | None = None
    rodzaj: str | None = None
    ruch_wahadlowy: bool = False
    sygnalizacja_swietlna: bool = False
    ruch_2_kierunkowy: bool = False
    awaria_mostu: bool = False
    droga_zamknieta: bool = False
    limits: dict[str, str] = {}

    @field_validator("data_powstania", "data_likwidacji", mode="before")
    @classmethod
    def colon_offset(cls, v: Any) -> Any:
        # GDDKiA writes "+0200"; ISO 8601 parsers want "+02:00".
        if isinstance(v, str) and len(v) > 5 and v[-5] in "+-" and v[-4:].isdigit():
            return f"{v[:-2]}:{v[-2:]}"
        return v


def parse_xml(content: bytes) -> list[dict[str, Any]]:
    items = []
    for utr in ET.fromstring(content).iter("utr"):
        item: dict[str, Any] = {}
        for child in utr:
            text = (child.text or "").strip()
            if child.tag == "rodzaj":
                item["rodzaj"] = child.findtext("poz")
            elif child.tag in LIMITS:
                if text:
                    item.setdefault("limits", {})[child.tag] = text
            elif text:
                item[child.tag] = text
        items.append(item)
    return items


def road_name(number: str) -> str:
    return f"DK{number}" if number[:1].isdigit() else number  # A1, S7 stay as they are


class GddkiaWorker(Worker[RoadIncident]):
    source = "gddkia"
    url = "https://www.archiwum.gddkia.gov.pl/dane/zima_html/utrdane.xml"
    interval_s = 900
    model = RoadIncident

    def fetch(self, client: httpx.Client) -> list[dict[str, Any]]:
        return parse_xml(self.get(client, self.url).content)

    def normalize(self, item: RoadIncident) -> Event | None:
        if item.droga_zamknieta:
            severity, label = 3, "Zamknięcie drogi"
        elif flag := next((f for f in RESTRICTIONS if getattr(item, f)), None):
            severity, label = 2, RESTRICTIONS[flag]
        elif item.typ == "W":
            severity, label = 2, "Zdarzenie drogowe"
        else:
            severity, label = 1, "Roboty drogowe" if item.typ == "U" else "Utrudnienie"

        details = [item.objazd] if item.objazd else []
        details += [f"{LIMITS[k][0]}: {v} {LIMITS[k][1]}" for k, v in item.limits.items()]
        if item.km:
            details.append(f"km {item.km}" + (f", odcinek {item.dl:g} km" if item.dl else ""))

        # No source ID: hash of the fields that identify a record (docs/SOURCES.md §6).
        key = "|".join(
            [item.typ, item.nr_drogi, item.woj, item.km or "", item.data_powstania.isoformat(),
             item.nazwa_odcinka]
        )  # fmt: skip
        has_point = item.geo_lat is not None and item.geo_long is not None
        woj = VOIVODESHIPS.get(item.woj.strip().lower())
        return Event(
            source_event_id=hashlib.sha256(key.encode()).hexdigest()[:24],
            type="road_incident",
            severity=severity,
            title=f"{label}: {road_name(item.nr_drogi)}, {item.nazwa_odcinka}",
            description="\n".join(details) or None,
            valid_from=item.data_powstania,
            valid_to=item.data_likwidacji,
            source_url="https://www.gov.pl/web/gddkia",
            geom_wkt=f"POINT({item.geo_long} {item.geo_lat})" if has_point else None,
            # decision 2026-10-15: no coordinates → whole voivodeship (coarse)
            teryt_powiat=[] if has_point or woj is None else [woj],
            raw=item.model_dump(mode="json"),
        )
