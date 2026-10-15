from collections.abc import Iterator

import pytest

from app import cache


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, bytes | int] = {}

    def get(self, key: str) -> bytes | None:
        value = self.data.get(key)
        return value if isinstance(value, bytes) else None

    def setex(self, key: str, seconds: int, value: bytes) -> None:
        self.data[key] = value

    def incr(self, key: str) -> int:
        value = int(self.data.get(key, 0)) + 1
        self.data[key] = value
        return value

    def expire(self, key: str, seconds: int) -> None:
        pass


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeRedis]:
    store = FakeRedis()
    monkeypatch.setattr(cache, "get_store", lambda: store)
    yield store


@pytest.fixture(autouse=True)
def no_redis_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "get_store", lambda: None)
