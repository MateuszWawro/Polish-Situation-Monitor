from typing import Any

from ingest.aircraft import classify, parse
from tests.conftest import load


def ac(**fields: Any) -> dict[str, Any]:
    return {"hex": "48c1b2", "lat": 52.2, "lon": 21.0, "alt_baro": 34000, **fields}


def cls(**fields: Any) -> str | None:
    parsed = parse(ac(**fields))
    return classify(parsed) if parsed else None


def test_classification() -> None:
    assert cls(flight="LOT3AB  ", category="A3") == "commercial"
    assert cls(flight="RYR12QK ") == "commercial"  # airline callsign, no category
    assert cls(r="D-AEWL", flight="@@@@@@@@", category="A3") == "commercial"  # large aircraft
    assert cls(flight="SPNIC", r="SP-NIC", t="C152", category="A1") == "private"
    assert cls(flight="KR06", t="EC35") == "private"  # helicopter, unknown category
    assert cls(flight="PLF693", t="W3", dbFlags=1) == "military"  # flag wins over callsign
    assert cls(flight="NATO40", t="E3TF", category="A5", dbFlags=1) == "military"


def test_skipped() -> None:
    assert cls(dbFlags=8) is None  # LADD: owner asked not to be shown
    assert cls(dbFlags=4) is None  # PIA
    assert cls(r="TWR", t="TWR") is None  # airport ground station
    assert cls(category="C2") is None  # surface vehicle
    assert cls(alt_baro="ground") is None
    assert cls(seen_pos=300) is None  # stale position
    assert cls(lat=48.2, lon=16.4) is None  # Vienna: outside Poland
    assert parse({"hex": "x"}) is None  # no position
    assert parse(ac(lat="x")) is None  # invalid


def test_real_snapshot() -> None:
    parsed = [a for raw in load("adsb_lol_aircraft.json")["ac"] if (a := parse(raw))]
    classes = {classify(a) for a in parsed}
    assert classes == {"commercial", "private", "military"}
    assert not any(a.r in {"TWR", "GND"} or a.dbFlags & 8 for a in parsed)
