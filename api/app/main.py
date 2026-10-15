import hashlib
import re
import time
import uuid
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import TextClause, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app import cache
from app.db import get_engine
from app.events import (
    ADMIN_UNITS_SQL,
    CACHE_TTL_S,
    EVENT_SQL,
    EVENT_TYPES,
    EVENTS_SQL,
    STATUS_SQL,
)

RATE_LIMIT_PER_MIN = 120
TERYT_RE = re.compile(r"^\d{2}(\d{2})?$")

app = FastAPI(title="Polish Situation Monitor API")
app.add_middleware(GZipMiddleware, minimum_size=1000)


class RateLimit(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/api/"):
            # Hash, not the raw IP: Redis never holds client addresses.
            ip = request.client.host if request.client else "unknown"
            client_id = hashlib.sha256(ip.encode()).hexdigest()[:16]
            if cache.over_limit(client_id, int(time.time() // 60), RATE_LIMIT_PER_MIN):
                return JSONResponse(
                    {"detail": "Too many requests"}, status_code=429, headers={"Retry-After": "60"}
                )
        return await call_next(request)


app.add_middleware(RateLimit)


def query_json(sql: TextClause, params: dict[str, object]) -> str | None:
    with get_engine().connect() as conn:
        result: str | None = conn.execute(sql, params).scalar_one_or_none()
        return result


def geojson_response(request: Request, body: bytes, max_age: int) -> Response:
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={max_age}"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/geo+json", headers=headers)


def cached_query(key: str, ttl_s: int, sql: TextClause, params: dict[str, object]) -> bytes:
    if (hit := cache.cached(key)) is not None:
        return hit
    body = (query_json(sql, params) or "null").encode()
    cache.store_cached(key, body, ttl_s)
    return body


def split(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def parse_bbox(value: str) -> list[float | None]:
    try:
        west, south, east, north = (float(v) for v in value.split(","))
    except ValueError:
        raise HTTPException(422, "bbox must be west,south,east,north") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise HTTPException(422, "bbox must be west,south,east,north")
    return [west, south, east, north]


@app.get("/health")
def health() -> JSONResponse:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, KeyError):  # KeyError: DATABASE_URL missing
        return JSONResponse({"status": "error", "db": False}, status_code=503)
    return JSONResponse({"status": "ok", "db": True})


@app.get("/api/events")
def list_events(
    request: Request,
    type: Annotated[str | None, Query(description="Comma-separated event types")] = None,
    bbox: Annotated[str | None, Query(description="west,south,east,north (WGS84)")] = None,
    teryt: Annotated[str | None, Query(description="Comma-separated 2/4-digit TERYT")] = None,
    active: bool = True,
) -> Response:
    types = sorted(set(split(type)))
    if unknown := set(types) - set(EVENT_TYPES):
        raise HTTPException(422, f"unknown type(s): {', '.join(sorted(unknown))}")
    codes = sorted(set(split(teryt)))
    if len(codes) > 50 or not all(TERYT_RE.match(c) for c in codes):
        raise HTTPException(422, "teryt must be up to 50 codes of 2 or 4 digits")
    box = parse_bbox(bbox) if bbox else [None] * 4
    params: dict[str, object] = {
        "types": types or None,
        "active": active,
        "codes": codes or None,
        "west": box[0], "south": box[1], "east": box[2], "north": box[3],
    }  # fmt: skip
    ttl = min(CACHE_TTL_S[t] for t in (types or EVENT_TYPES))
    key = "events:" + hashlib.sha256(repr(sorted(params.items())).encode()).hexdigest()
    return geojson_response(request, cached_query(key, ttl, EVENTS_SQL, params), ttl)


@app.get("/api/events/{event_id}")
def get_event(request: Request, event_id: uuid.UUID) -> Response:
    body = query_json(EVENT_SQL, {"id": event_id})
    if body is None:
        raise HTTPException(404, "event not found")
    return geojson_response(request, body.encode(), 60)


@app.get("/api/sources/status")
def sources_status() -> Response:
    body = query_json(STATUS_SQL, {}) or "[]"
    return Response(body, media_type="application/json", headers={"Cache-Control": "no-cache"})


@app.get("/api/admin-units")
def admin_units(
    request: Request, level: Literal["voivodeship", "powiat"] | None = None
) -> Response:
    # Boundaries change roughly yearly.
    body = cached_query(f"admin-units:{level}", 86400, ADMIN_UNITS_SQL, {"level": level})
    return geojson_response(request, body, 86400)
