import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from ingest.base import Event
from ingest.emsc import QUERY_URL, EmscWorker, severity
from tests.conftest import load


def fetched(payload: dict[str, Any]) -> list[dict[str, Any]]:
    worker = EmscWorker(sleep=lambda _: None)
    with respx.mock, httpx.Client() as client:
        route = respx.get(url__startswith=QUERY_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        items = worker.fetch(client)
        assert "starttime=" in str(route.calls.last.request.url)
    return items


def events(payload: dict[str, Any] | None = None) -> list[Event]:
    worker = EmscWorker()
    items = worker.validate(fetched(payload or load("emsc_events.json")))
    return [e for i in items if (e := worker.normalize(i))]


def test_fixture_normalizes_every_event() -> None:
    evs = events()
    assert len(evs) == 4
    first = evs[0]
    assert first.source_event_id == "20261016_0000213"
    assert first.type == "earthquake"
    assert first.title == "Wstrząs M2.5 – Polska"
    assert first.geom_wkt == "POINT(16.1008 51.5633)"
    assert first.teryt_powiat == []  # derived from the point with ST_Intersects
    assert first.valid_from == datetime(2026, 10, 16, 17, 0, 55, 920000, tzinfo=UTC)
    assert first.valid_to == first.valid_from + timedelta(hours=24)
    assert first.source_url == (
        "https://www.seismicportal.eu/eventdetails.html?unid=20261016_0000213"
    )
    assert first.description == "Magnituda 2.5 (m)\ngłębokość 1 km\ntyp: trzęsienie ziemi"


@pytest.mark.parametrize(
    ("mag", "expected"),
    [(0.5, 0), (1.99, 0), (2.0, 1), (2.9, 1), (3.0, 2), (3.9, 2), (4.0, 3), (6.1, 3)],
)
def test_severity_by_magnitude(mag: float, expected: int) -> None:
    assert severity(mag) == expected


def test_fixture_severities() -> None:
    assert sorted(e.severity for e in events()) == [0, 1, 1, 1]


def test_outside_poland_is_kept_as_a_point_for_the_db_to_drop() -> None:
    # The base upsert drops events that intersect no Polish powiat; normalize must not
    # guess from the region name (border events can be labelled either country).
    payload = load("emsc_events.json")
    slovak = copy.deepcopy(payload["features"][0])
    slovak["geometry"]["coordinates"] = [19.1, 48.9, -5.0]
    slovak["properties"] |= {"unid": "sk1", "flynn_region": "SLOVAKIA", "lat": 0, "lon": 0}
    payload["features"] = [slovak]
    (ev,) = events(payload)
    assert ev.geom_wkt == "POINT(19.1 48.9)"  # geometry wins over the properties
    assert ev.title == "Wstrząs M2.5 – Słowacja"


def test_invalid_feature_is_skipped() -> None:
    payload = load("emsc_events.json")
    del payload["features"][1]["properties"]["mag"]
    assert len(events(payload)) == 3
