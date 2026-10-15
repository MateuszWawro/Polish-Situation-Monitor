from datetime import datetime, timedelta
from typing import Any

import pytest

from ingest.imgw_hydro import ImgwHydroStationsWorker, ImgwHydroWarningsWorker
from ingest.imgw_meteo import WARSAW
from tests.conftest import load


def test_warnings_fixture_maps_drought_to_voivodeships() -> None:
    worker = ImgwHydroWarningsWorker()
    payload = load("imgw_hydro_warnings.json")
    events = [worker.normalize(i) for i in worker.validate(payload)]
    first = events[0]
    assert first is not None
    assert first.source_event_id.startswith("warning:")
    assert first.severity == 1  # drought -1 → 1
    assert first.valid_to is None  # 9999-12-31 = open-ended
    assert first.teryt_powiat and all(len(c) == 2 for c in first.teryt_powiat)


def test_unknown_voivodeship_is_dropped() -> None:
    worker = ImgwHydroWarningsWorker()
    item = {**load("imgw_hydro_warnings.json")[0], "obszary": [{"wojewodztwo": "Atlantyda"}]}
    [validated] = worker.validate([item])
    event = worker.normalize(validated)
    assert event is not None and event.teryt_powiat == []  # skipped later by the upsert


def station(level: str | None, measured: datetime | None = None) -> dict[str, Any]:
    base = load("imgw_hydro_stations.json")[0]
    measured = measured or datetime.now(WARSAW).replace(tzinfo=None)
    return {
        **base,
        "stan_wody": level,
        "stan_ostrzegawczy": "300",
        "stan_alarmowy": "340",
        "stan_wody_data_pomiaru": measured.strftime("%Y-%m-%d %H:%M:%S"),
    }


@pytest.mark.parametrize(("level", "severity"), [("299", None), ("300", 2), ("339", 2), ("340", 3)])
def test_station_thresholds(level: str, severity: int | None) -> None:
    worker = ImgwHydroStationsWorker()
    [validated] = worker.validate([station(level)])
    event = worker.normalize(validated)
    assert (event.severity if event else None) == severity
    if event:
        assert event.geom_wkt and event.geom_wkt.startswith("POINT(")
        assert event.source_event_id.startswith("station:")


def test_station_stale_or_missing_data_ignored() -> None:
    worker = ImgwHydroStationsWorker()
    old = datetime.now(WARSAW).replace(tzinfo=None) - timedelta(days=2)
    items = worker.validate([station("400", old), station(None)])
    assert [worker.normalize(i) for i in items] == [None, None]


def test_stations_fixture_validates() -> None:
    worker = ImgwHydroStationsWorker()
    payload = load("imgw_hydro_stations.json")
    assert len(worker.validate(payload)) == len(payload)
