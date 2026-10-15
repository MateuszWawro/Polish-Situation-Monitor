from typing import Any

import httpx
import respx

from ingest.adsb_gps import (
    MIN_AIRCRAFT,
    URL,
    WINDOW_S,
    AdsbGpsWorker,
    Cell,
    Report,
    aggregate,
    share_pct,
    usable,
)
from tests.conftest import load


def aircraft(hex_: str, lat: float, lon: float, nac_p: int, **extra: Any) -> dict[str, Any]:
    return {"hex": hex_, "lat": lat, "lon": lon, "nac_p": nac_p, "version": 2,
            "alt_baro": 35000, "seen_pos": 1.0, **extra}  # fmt: skip


def test_usable_keeps_only_airborne_gps_positions() -> None:
    assert usable(aircraft("a", 52.0, 21.0, 9)) is not None
    assert usable(aircraft("a", 52.0, 21.0, 9, version=0)) is None  # no NACp semantics
    assert usable(aircraft("a", 52.0, 21.0, 9, mlat=["lat", "lon"])) is None
    assert usable(aircraft("a", 52.0, 21.0, 9, tisb=["lat", "lon"])) is None
    assert usable(aircraft("a", 52.0, 21.0, 9, alt_baro="ground")) is None
    assert usable(aircraft("a", 52.0, 21.0, 9, seen_pos=120)) is None
    assert usable({"hex": "a", "version": 2, "nac_p": 9}) is None  # no position
    assert usable({**aircraft("a", 52.0, 21.0, 9), "lat": "x"}) is None  # invalid → skipped


def test_real_payload_parses() -> None:
    payload = load("adsb_lol_point.json")
    usable_aircraft = [a for a in payload["ac"] if usable(a)]
    assert 0 < len(usable_aircraft) < len(payload["ac"])  # fixture mixes mlat, ground, v0


def test_aggregate_counts_distinct_aircraft_bad_if_ever_bad() -> None:
    cell = (104, 28)
    snapshots = [
        [Report("a", cell, False), Report("b", cell, True)],
        [Report("a", cell, True), Report("b", cell, False), Report("c", cell, False)],
    ]
    assert aggregate(snapshots) == [Cell(row=104, col=28, total=3, bad=2)]


def test_share_ignores_a_single_bad_aircraft() -> None:
    assert share_pct(1, 10) == 0
    assert share_pct(3, 10) == 20


def run_fetch(worker: AdsbGpsWorker, ac: list[dict[str, Any]]) -> list[dict[str, Any]]:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ac": ac}))
    with httpx.Client() as client:
        return worker.fetch(client)


@respx.mock
def test_window_drops_old_snapshots_and_normalizes() -> None:
    now = [1_800_000_000.0]
    worker = AdsbGpsWorker(sleep=lambda _: None, clock=lambda: now[0])
    # 10 aircraft over Białystok, 4 with degraded accuracy → (4 - 1) / 10 = 30 % → severity 3
    jammed = [aircraft(f"h{i}", 53.1, 23.2, 0 if i < 4 else 10) for i in range(10)]
    events = [e for c in worker.validate(run_fetch(worker, jammed)) if (e := worker.normalize(c))]
    assert len(events) == 1
    event = events[0]
    assert event.type == "gps_interference" and event.severity == 3
    assert event.geom_wkt is not None and event.geom_wkt.startswith("POLYGON((22.5 53.0,")
    assert "4 z 10" in (event.description or "")
    first_since = event.valid_from

    # Later snapshot, all clean: still elevated while the bad one is inside the window...
    now[0] += 600
    clean = [aircraft(f"h{i}", 53.1, 23.2, 10) for i in range(10)]
    cells = worker.validate(run_fetch(worker, clean))
    still = [e for c in cells if (e := worker.normalize(c))]
    assert still and still[0].valid_from == first_since  # stable start time

    # ...and gone once it has left the window.
    now[0] += WINDOW_S
    cells = worker.validate(run_fetch(worker, clean))
    assert [e for c in cells if (e := worker.normalize(c))] == []


def test_too_few_aircraft_gives_no_estimate() -> None:
    worker = AdsbGpsWorker(sleep=lambda _: None)
    cell = Cell(row=106, col=31, total=MIN_AIRCRAFT - 1, bad=MIN_AIRCRAFT - 1)
    assert worker.normalize(cell) is None


@respx.mock
def test_unexpected_payload_raises() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json=[]))
    worker = AdsbGpsWorker(sleep=lambda _: None)
    with httpx.Client() as client:
        try:
            worker.fetch(client)
        except ValueError as exc:
            assert "'ac'" in str(exc)
        else:
            raise AssertionError("expected ValueError")
