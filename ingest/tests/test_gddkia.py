from datetime import UTC, datetime

from ingest.gddkia import GddkiaWorker, parse_xml
from tests.conftest import FIXTURES


def events() -> list:  # type: ignore[type-arg]
    worker = GddkiaWorker()
    items = worker.validate(parse_xml((FIXTURES / "gddkia_utrdane.xml").read_bytes()))
    return [e for i in items if (e := worker.normalize(i))]


def test_fixture_parses_all_records() -> None:
    assert len(events()) == 8


def test_severity_mapping() -> None:
    by_title = {e.title.split(":")[0]: e.severity for e in events()}
    assert by_title["Zamknięcie drogi"] == 3
    assert by_title["Ruch wahadłowy"] == 2
    assert by_title["Zdarzenie drogowe"] == 2  # typ W
    assert by_title["Roboty drogowe"] == 1


def test_offsets_and_ids() -> None:
    evs = events()
    first = evs[0]
    assert first.valid_from == datetime(2026, 9, 22, 22, tzinfo=UTC)  # 00:00+02:00
    assert first.valid_to == datetime(2026, 11, 8, 22, 59, tzinfo=UTC)  # 23:59+01:00 (CET)
    assert len({e.source_event_id for e in evs}) == len(evs)
    assert evs == events()  # deterministic IDs across runs


def test_geometry_or_voivodeship_fallback() -> None:
    evs = events()
    with_point = [e for e in evs if e.geom_wkt]
    without = [e for e in evs if not e.geom_wkt]
    assert with_point and all(e.teryt_powiat == [] for e in with_point)
    assert without and all(
        len(e.teryt_powiat) == 1 and len(e.teryt_powiat[0]) == 2 for e in without
    )


def test_description_has_limits_and_road_names() -> None:
    evs = events()
    assert any("ograniczenie prędkości" in (e.description or "") for e in evs)
    assert any(", DK" in e.title or ": DK" in e.title for e in evs)
