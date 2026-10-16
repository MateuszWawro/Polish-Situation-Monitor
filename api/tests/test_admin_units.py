from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import needs_db

pytestmark = needs_db


def test_admin_units_powiat_feature_collection() -> None:
    response = TestClient(app).get("/api/admin-units", params={"level": "powiat"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert {f["properties"]["level"] for f in body["features"]} == {"powiat"}
    assert all(len(f["id"]) == 4 for f in body["features"])


def test_admin_units_rejects_unknown_level() -> None:
    assert TestClient(app).get("/api/admin-units", params={"level": "gmina"}).status_code == 422
