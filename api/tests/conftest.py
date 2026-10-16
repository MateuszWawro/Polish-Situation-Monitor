import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from app import cache
from app.db import get_engine


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


@pytest.fixture(scope="session")
def test_db() -> Iterator[None]:
    """Point the app at TEST_DATABASE_URL (never DATABASE_URL), freshly migrated."""
    sys.path.insert(0, str(Path(__file__).parents[2] / "db"))
    from testdb import prepare  # type: ignore[import-not-found]

    url = os.environ["TEST_DATABASE_URL"]
    prepare(url)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", url)
        get_engine.cache_clear()
        yield
    get_engine.cache_clear()


needs_db = [
    pytest.mark.skipif("TEST_DATABASE_URL" not in os.environ, reason="needs TEST_DATABASE_URL"),
    pytest.mark.usefixtures("test_db"),
]
