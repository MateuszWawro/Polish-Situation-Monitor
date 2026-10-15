import httpx
import pytest
import respx

from ingest.imgw_meteo import ImgwMeteoWorker


@respx.mock
def test_fetch_retries_with_backoff_and_sends_user_agent() -> None:
    delays: list[float] = []
    worker = ImgwMeteoWorker(sleep=delays.append)
    route = respx.get(worker.url).mock(
        side_effect=[
            httpx.Response(503),
            httpx.ConnectError("boom"),
            httpx.Response(200, json=[]),
        ]
    )
    with httpx.Client() as client:
        assert worker.fetch(client) == []
    assert delays == [2.0, 4.0]
    assert "contact:" in route.calls[0].request.headers["User-Agent"]


@respx.mock
def test_fetch_gives_up_after_max_attempts() -> None:
    worker = ImgwMeteoWorker(sleep=lambda _: None)
    respx.get(worker.url).mock(return_value=httpx.Response(500))
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        worker.fetch(client)


@respx.mock
def test_fetch_does_not_retry_client_errors() -> None:
    worker = ImgwMeteoWorker(sleep=lambda _: pytest.fail("should not retry"))
    route = respx.get(worker.url).mock(return_value=httpx.Response(404))
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        worker.fetch(client)
    assert route.call_count == 1
