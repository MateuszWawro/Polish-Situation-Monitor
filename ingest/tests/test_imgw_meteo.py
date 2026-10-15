from datetime import UTC, datetime
from typing import Any

from ingest.imgw_meteo import ImgwMeteoWorker


def test_normalize_fixture(meteo_payload: list[dict[str, Any]]) -> None:
    worker = ImgwMeteoWorker()
    events = [worker.normalize(i) for i in worker.validate(meteo_payload)]

    assert len(events) == len(meteo_payload)
    first, raw = events[0], meteo_payload[0]
    assert first.source_event_id == raw["id"]
    assert first.type == "weather_warning"
    assert first.severity == int(raw["stopien"])
    assert first.teryt_powiat == sorted(set(raw["teryt"]))
    assert first.description is not None and "Brak" not in first.description


def test_local_time_converted_with_dst() -> None:
    worker = ImgwMeteoWorker()
    item = {
        "id": "x",
        "nazwa_zdarzenia": "Upał",
        "stopien": "3",
        "opublikowano": "2026-07-01 08:00:00",
        "obowiazuje_od": "2026-07-01 12:00:00",
        "obowiazuje_do": "2026-12-01 12:00:00",
        "tresc": "t",
        "biuro": "b",
        "teryt": ["1465"],
    }
    [validated] = worker.validate([item])
    event = worker.normalize(validated)
    assert event.valid_from == datetime(2026, 7, 1, 10, tzinfo=UTC)  # CEST, UTC+2
    assert event.valid_to == datetime(2026, 12, 1, 11, tzinfo=UTC)  # CET, UTC+1
    assert event.severity == 3


def test_invalid_item_skipped(meteo_payload: list[dict[str, Any]]) -> None:
    broken = {**meteo_payload[0], "stopien": "7"}
    items = ImgwMeteoWorker().validate([broken, meteo_payload[1]])
    assert [i.id for i in items] == [meteo_payload[1]["id"]]
