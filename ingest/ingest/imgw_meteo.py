"""IMGW-PIB meteorological warnings (see docs/SOURCES.md §1)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from ingest.base import Event, Worker

WARSAW = ZoneInfo("Europe/Warsaw")


class MeteoWarning(BaseModel):
    id: str
    nazwa_zdarzenia: str
    stopien: int = Field(ge=1, le=3)
    prawdopodobienstwo: int | None = None
    obowiazuje_od: datetime
    obowiazuje_do: datetime
    opublikowano: datetime
    tresc: str
    komentarz: str | None = None
    biuro: str
    teryt: list[str] = Field(min_length=1)


def local(dt: datetime) -> datetime:
    """IMGW sends naive Europe/Warsaw local times."""
    return dt.replace(tzinfo=WARSAW)


class ImgwMeteoWorker(Worker[MeteoWarning]):
    source = "imgw_meteo"
    url = "https://danepubliczne.imgw.pl/api/data/warningsmeteo"
    interval_s = 600
    model = MeteoWarning

    def normalize(self, item: MeteoWarning) -> Event:
        description = item.tresc
        if item.komentarz and item.komentarz.strip(" .") != "Brak":
            description += f"\n\n{item.komentarz}"
        return Event(
            source_event_id=item.id,
            type="weather_warning",
            severity=item.stopien,
            title=item.nazwa_zdarzenia,
            description=description,
            valid_from=local(item.obowiazuje_od),
            valid_to=local(item.obowiazuje_do),
            source_url="https://meteo.imgw.pl/",
            teryt_powiat=sorted(set(item.teryt)),
            raw=item.model_dump(mode="json"),
        )
