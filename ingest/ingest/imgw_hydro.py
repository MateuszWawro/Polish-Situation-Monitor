"""IMGW-PIB hydrological warnings and water levels (see docs/SOURCES.md §2a, §2b)."""

import logging
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from ingest.base import Event, Worker
from ingest.imgw_meteo import WARSAW, local

log = logging.getLogger(__name__)

# TERYT voivodeship codes; IMGW sends lower-case Polish names identical to PRG.
VOIVODESHIPS = {
    "dolnośląskie": "02", "kujawsko-pomorskie": "04", "lubelskie": "06", "lubuskie": "08",
    "łódzkie": "10", "małopolskie": "12", "mazowieckie": "14", "opolskie": "16",
    "podkarpackie": "18", "podlaskie": "20", "pomorskie": "22", "śląskie": "24",
    "świętokrzyskie": "26", "warmińsko-mazurskie": "28", "wielkopolskie": "30",
    "zachodniopomorskie": "32",
}  # fmt: skip


class HydroArea(BaseModel):
    wojewodztwo: str
    opis: str | None = None


class HydroWarning(BaseModel):
    numer: str
    biuro: str
    # -1 = hydrological drought, 1–3 = flood warning levels
    stopien: int = Field(alias="stopień", ge=-1, le=3)
    zdarzenie: str
    przebieg: str | None = None
    komentarz: str | None = None
    opublikowano: datetime
    data_od: datetime
    data_do: datetime
    obszary: list[HydroArea] = Field(min_length=1)


class ImgwHydroWarningsWorker(Worker[HydroWarning]):
    source = "imgw_hydro"
    id_prefix = "warning:"
    url = "https://danepubliczne.imgw.pl/api/data/warningshydro"
    interval_s = 600
    model = HydroWarning

    def normalize(self, item: HydroWarning) -> Event | None:
        if item.stopien == 0:
            return None
        codes = []
        for area in item.obszary:
            if code := VOIVODESHIPS.get(area.wojewodztwo.strip().lower()):
                codes.append(code)
            else:
                log.warning("imgw_hydro: unknown voivodeship %r", area.wojewodztwo)
        description = "\n\n".join(p for p in (item.przebieg, item.komentarz) if p)
        return Event(
            source_event_id=f"warning:{item.biuro}:{item.numer}",
            type="hydro_warning",
            # decision 2026-10-15: drought (-1) is shown as the lowest level
            severity=max(item.stopien, 1),
            title=item.zdarzenie,
            description=description or None,
            valid_from=local(item.data_od),
            valid_to=None if item.data_do.year == 9999 else local(item.data_do),
            source_url="https://hydro.imgw.pl/",
            teryt_powiat=sorted(set(codes)),  # coarse: whole voivodeships (no catchment shapes)
            raw=item.model_dump(mode="json", by_alias=True),
        )


class HydroStation(BaseModel):
    id_stacji: str
    stacja: str
    rzeka: str | None = None
    lat: float
    lon: float
    stan_wody: float | None = None
    stan_wody_data_pomiaru: datetime | None = None
    stan_ostrzegawczy: float | None = None
    stan_alarmowy: float | None = None


MAX_MEASUREMENT_AGE = timedelta(hours=24)


class ImgwHydroStationsWorker(Worker[HydroStation]):
    """Only stations at/above warning level become events (decision 2026-10-15)."""

    source = "imgw_hydro"
    id_prefix = "station:"
    url = "https://danepubliczne.imgw.pl/api/data/hydro"
    interval_s = 600
    model = HydroStation

    def normalize(self, item: HydroStation) -> Event | None:
        level, warning, alarm = item.stan_wody, item.stan_ostrzegawczy, item.stan_alarmowy
        measured = item.stan_wody_data_pomiaru
        if level is None or warning is None or measured is None or level < warning:
            return None
        measured_at = local(measured)
        if datetime.now(WARSAW) - measured_at > MAX_MEASUREMENT_AGE:
            return None  # stale gauge: don't keep raising an alarm from old data
        is_alarm = alarm is not None and level >= alarm
        place = f"{item.rzeka} – {item.stacja}" if item.rzeka else item.stacja
        limits = f"ostrzegawczy {warning:g} cm" + (f", alarmowy {alarm:g} cm" if alarm else "")
        return Event(
            source_event_id=f"station:{item.id_stacji}",
            type="hydro_warning",
            severity=3 if is_alarm else 2,
            title=f"{'Stan alarmowy' if is_alarm else 'Stan ostrzegawczy'}: {place}",
            description=f"Stan wody {level:g} cm ({limits}), pomiar {measured:%Y-%m-%d %H:%M}.",
            valid_from=measured_at,
            valid_to=None,  # ends when the station drops below warning level (closed as missing)
            source_url="https://hydro.imgw.pl/",
            geom_wkt=f"POINT({item.lon} {item.lat})",
            raw=item.model_dump(mode="json"),
        )
