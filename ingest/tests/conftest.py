import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def meteo_payload() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / "imgw_meteo.json").read_text())
    return data


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def text(name: str) -> str:
    return (FIXTURES / name).read_text()
