import httpx
import respx

from ingest.firms import URLS, FirmsWorker
from tests.conftest import text


@respx.mock
def test_fetch_keeps_only_poland_bbox_and_normalizes() -> None:
    csv_body = text("firms_viirs.csv")
    for url in URLS:
        respx.get(url).mock(return_value=httpx.Response(200, text=csv_body))
    worker = FirmsWorker(sleep=lambda _: None)
    with httpx.Client() as client:
        rows = worker.fetch(client)
    assert len(rows) == 2 * 5  # fixture: 5 rows in Poland's bbox + 2 far south, per file
    events = [e for i in worker.validate(rows) if (e := worker.normalize(i))]
    first = events[0]
    assert first is not None
    assert first.type == "fire_hotspot" and first.severity == 2  # nominal
    assert first.valid_to is not None and first.valid_from is not None
    assert (first.valid_to - first.valid_from).total_seconds() == 24 * 3600
    assert first.valid_from.hour == 0 and first.valid_from.minute == 9  # acq_time 0009 UTC
