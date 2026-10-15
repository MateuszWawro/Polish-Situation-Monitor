from typing import Literal

from fastapi import FastAPI, Response
from sqlalchemy import text

from app.db import get_engine

app = FastAPI(title="Polish Situation Monitor API")

# GeoJSON is assembled in PostGIS: one round trip, no Python-side geometry handling.
ADMIN_UNITS_SQL = text("""
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(json_agg(json_build_object(
            'type', 'Feature',
            'id', teryt,
            'geometry', ST_AsGeoJSON(geom, 4)::json,
            'properties', json_build_object('teryt', teryt, 'level', level, 'name', name)
        ) ORDER BY teryt), '[]'::json)
    )::text
    FROM admin_units
    WHERE CAST(:level AS text) IS NULL OR level = :level
""")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/admin-units")
def admin_units(level: Literal["voivodeship", "powiat"] | None = None) -> Response:
    with get_engine().connect() as conn:
        body = conn.execute(ADMIN_UNITS_SQL, {"level": level}).scalar_one()
    # Boundaries change roughly yearly; let browsers and Caddy cache for a day.
    return Response(
        body, media_type="application/geo+json", headers={"Cache-Control": "public, max-age=86400"}
    )
