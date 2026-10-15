from pathlib import Path

import httpx
import respx

from ingest.gios import BASE, GiosWorker
from tests.conftest import FIXTURES, load


@respx.mock
def test_fetch_and_normalize_from_fixtures() -> None:
    worker = GiosWorker(sleep=lambda _: None)
    respx.get(worker.url).mock(return_value=httpx.Response(200, json=load("gios_stations.json")))
    ids = []
    for path in sorted(Path(FIXTURES).glob("gios_index_*.json")):
        sid = path.stem.rsplit("_", 1)[1]
        ids.append(sid)
        respx.get(f"{BASE}/aqindex/getIndex/{sid}").mock(
            return_value=httpx.Response(200, json=load(path.name))
        )
    with httpx.Client() as client:
        items = worker.validate(worker.fetch(client))
    events = [e for i in items if (e := worker.normalize(i))]
    assert sorted(e.source_event_id for e in events) == sorted(ids)
    assert all(e.type == "air_quality" and 0 <= e.severity <= 3 for e in events)
    assert all(e.valid_to and e.valid_from and e.valid_to > e.valid_from for e in events)


@respx.mock
def test_one_failing_station_does_not_fail_run() -> None:
    worker = GiosWorker(sleep=lambda _: None)
    stations = load("gios_stations.json")
    respx.get(worker.url).mock(return_value=httpx.Response(200, json=stations))
    first, *rest = [s["Identyfikator stacji"] for s in stations["Lista stacji pomiarowych"]]
    respx.get(f"{BASE}/aqindex/getIndex/{first}").mock(return_value=httpx.Response(404))
    for sid in rest:
        respx.get(f"{BASE}/aqindex/getIndex/{sid}").mock(
            return_value=httpx.Response(200, json=load(f"gios_index_{sid}.json"))
        )
    with httpx.Client() as client:
        assert len(worker.fetch(client)) == len(rest)


def test_severity_mapping_and_missing_index() -> None:
    worker = GiosWorker()
    station = load("gios_stations.json")["Lista stacji pomiarowych"][0]
    index = load("gios_index_11.json")["AqIndex"]
    got = []
    for value in [0, 1, 2, 3, 4, 5, None, -1]:
        [item] = worker.validate(
            [{"station": station, "index": {**index, "Wartość indeksu": value}}]
        )
        event = worker.normalize(item)
        got.append(event.severity if event else None)
    assert got == [0, 0, 1, 2, 3, 3, None, None]

    no_data = {k: None for k in index}
    [item] = worker.validate([{"station": station, "index": no_data}])
    assert worker.normalize(item) is None
