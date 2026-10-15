import httpx
import respx

from ingest.satellites import GROUPS, URL, fetch_group, parse_tle

STATIONS = """ISS (ZARYA)
1 25544U 98067A   26288.11220063  .00005682  00000+0  11168-3 0  9991
2 25544  51.6331  66.6267 0006716 264.3647  95.6576 15.48871015590345
CSS (TIANHE)
1 48274U 21035A   26288.24410899  .00023064  00000+0  27253-3 0  9995
2 48274  41.4694 312.8000 0000702 139.8855 220.2036 15.60756584311914
"""


def test_parse_tle_reads_triples() -> None:
    rows = parse_tle(STATIONS, "stations")
    assert [r["norad_id"] for r in rows] == [25544, 48274]
    assert rows[0]["name"] == "ISS (ZARYA)" and rows[0]["grp"] == "stations"
    assert str(rows[0]["tle1"]).startswith("1 25544U")
    assert str(rows[0]["tle2"]).startswith("2 25544")


def test_parse_tle_skips_malformed() -> None:
    bad = "JUNK\nnot a line\nalso not\n" + STATIONS
    rows = parse_tle(bad, "visual")
    assert [r["norad_id"] for r in rows] == [25544, 48274]


@respx.mock
def test_fetch_group_retries_then_raises() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as client:
        try:
            fetch_group(client, "stations", sleep=lambda _: None)
        except httpx.HTTPError:
            pass
        else:
            raise AssertionError("expected HTTPError")
    assert route.call_count == 3


@respx.mock
def test_fetch_group_rejects_non_tle_body() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>error</html>"))
    with httpx.Client() as client:
        try:
            fetch_group(client, "stations", sleep=lambda _: None)
        except ValueError as exc:
            assert "unexpected body" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_groups_cover_defaults_and_toggles() -> None:
    assert GROUPS[:2] == ["stations", "visual"]
    assert set(GROUPS) >= {"starlink", "gnss"}
