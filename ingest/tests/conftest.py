import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def meteo_payload() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / "imgw_meteo.json").read_text())
    return data
