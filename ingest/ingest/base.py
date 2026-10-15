"""Shared worker pipeline: fetch → validate → normalize → upsert → source_status."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import psycopg
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

USER_AGENT = (
    "PolishSituationMonitor/0.1 (non-commercial open-source; "
    f"contact: {os.environ.get('INGEST_CONTACT', 'unset')})"
)
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Event:
    source_event_id: str
    type: str
    severity: int
    title: str
    valid_from: datetime | None
    valid_to: datetime | None
    raw: dict[str, Any]
    description: str | None = None
    source_url: str | None = None
    # Either TERYT codes from the source (4-digit powiat or 2-digit voivodeship), or a
    # point/shape (WKT, SRID 4326) from which powiat codes are derived with ST_Intersects.
    teryt_powiat: list[str] = field(default_factory=list)
    geom_wkt: str | None = None


# geom: given WKT, else union of the listed powiaty. teryt: listed powiat codes (2-digit
# voivodeship codes expand to all their powiaty), else powiaty intersecting the geometry.
# The WHERE clause keeps updated_at/fetched_at untouched when nothing meaningful changed.
UPSERT_SQL = """
WITH input AS (
    SELECT %(geom_wkt)s::text AS wkt, %(teryt)s::text[] AS teryt
), resolved AS (
    SELECT
        coalesce(
            ST_GeomFromText(wkt, 4326),
            -- ±0.002° (~200 m) buffer closes hairline gaps between separately simplified
            -- powiaty; without it a union keeps hundreds of sliver holes (~10× the JSON).
            -- shortcut: switch to ST_CoverageSimplify at import once prod runs PostGIS ≥ 3.6.
            (SELECT ST_Buffer(ST_Buffer(ST_Union(a.geom), 0.002), -0.002) FROM admin_units a
             WHERE a.level = 'powiat'
               AND (a.teryt = ANY(input.teryt) OR left(a.teryt, 2) = ANY(input.teryt)))
        ) AS geom,
        coalesce((SELECT array_agg(a.teryt ORDER BY a.teryt) FROM admin_units a
            WHERE a.level = 'powiat' AND CASE
                WHEN cardinality(input.teryt) > 0
                THEN a.teryt = ANY(input.teryt) OR left(a.teryt, 2) = ANY(input.teryt)
                ELSE ST_Intersects(a.geom, ST_GeomFromText(input.wkt, 4326)) END
        ), '{}') AS teryt
    FROM input
)
INSERT INTO events (source, source_event_id, type, severity, title, description, geom,
                    teryt_powiat, valid_from, valid_to, source_url, fetched_at, raw)
SELECT %(source)s, %(source_event_id)s, %(type)s, %(severity)s, %(title)s, %(description)s,
       resolved.geom, resolved.teryt, %(valid_from)s, %(valid_to)s, %(source_url)s, now(),
       %(raw)s::jsonb
FROM resolved
WHERE cardinality(resolved.teryt) > 0  -- outside Poland (or unknown codes): not our event
ON CONFLICT (source, source_event_id) DO UPDATE SET
    type = EXCLUDED.type, severity = EXCLUDED.severity, title = EXCLUDED.title,
    description = EXCLUDED.description, geom = EXCLUDED.geom,
    teryt_powiat = EXCLUDED.teryt_powiat, valid_from = EXCLUDED.valid_from,
    valid_to = EXCLUDED.valid_to, source_url = EXCLUDED.source_url,
    raw = EXCLUDED.raw, fetched_at = now(), updated_at = now()
WHERE (events.type, events.severity, events.title, events.description, events.teryt_powiat,
       events.valid_from, events.valid_to)
   IS DISTINCT FROM
      (EXCLUDED.type, EXCLUDED.severity, EXCLUDED.title, EXCLUDED.description,
       EXCLUDED.teryt_powiat, EXCLUDED.valid_from, EXCLUDED.valid_to)
"""

# Items that disappeared from the source feed are ended now (withdrawn or expired early).
CLOSE_MISSING_SQL = """
UPDATE events SET valid_to = now(), updated_at = now()
WHERE source = %(source)s AND source_event_id LIKE %(prefix)s || '%%'
  AND NOT (source_event_id = ANY(%(seen)s))
  AND (valid_to IS NULL OR valid_to > now())
"""

STATUS_SUCCESS_SQL = """
INSERT INTO source_status (source, last_success_at, expected_interval_s)
VALUES (%(source)s, now(), %(interval)s)
ON CONFLICT (source) DO UPDATE SET last_success_at = now(),
    expected_interval_s = EXCLUDED.expected_interval_s
"""

STATUS_ERROR_SQL = """
INSERT INTO source_status (source, last_error, last_error_at, expected_interval_s)
VALUES (%(source)s, %(error)s, now(), %(interval)s)
ON CONFLICT (source) DO UPDATE SET last_error = EXCLUDED.last_error, last_error_at = now(),
    expected_interval_s = EXCLUDED.expected_interval_s
"""


class Worker[T: BaseModel](ABC):
    source: str
    url: str
    interval_s: int
    model: type[T]
    # Scope for closing missing items when one source is fed by several workers.
    id_prefix: str = ""
    max_attempts: int = 4
    backoff_base_s: float = 2.0

    def __init__(self, sleep: Callable[[float], None] = time.sleep) -> None:
        self.sleep = sleep

    def get(self, client: httpx.Client, url: str) -> httpx.Response:
        """GET with exponential backoff on network errors, 429 and 5xx."""
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()
                    return response
                error: Exception = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request, response=response
                )
            except httpx.TransportError as exc:
                error = exc
            if attempt == self.max_attempts:
                raise error
            delay = self.backoff_base_s * 2 ** (attempt - 1)
            log.warning(
                "%s fetch attempt %d failed (%s), retry in %.0fs",
                self.source,
                attempt,
                error,
                delay,
            )
            self.sleep(delay)
        raise AssertionError("unreachable")

    def fetch(self, client: httpx.Client) -> Any:
        return self.get(client, self.url).json()

    def validate(self, payload: Any) -> list[T]:
        """Validate each item separately: one malformed record must not drop the whole feed."""
        if not isinstance(payload, list):
            raise ValueError(f"{self.source}: expected a JSON array, got {type(payload).__name__}")
        items = []
        for raw in payload:
            try:
                items.append(self.model.model_validate(raw))
            except ValidationError as exc:
                log.warning("%s: skipping invalid item: %s", self.source, exc)
        if payload and not items:
            raise ValueError(f"{self.source}: all {len(payload)} items failed validation")
        return items

    @abstractmethod
    def normalize(self, item: T) -> Event | None:
        """Map one item to an event, or None when it is not an event (e.g. below threshold)."""

    def upsert(self, conn: psycopg.Connection, events: list[Event]) -> None:
        with conn.cursor() as cur:
            cur.executemany(
                UPSERT_SQL,
                [
                    {
                        **e.__dict__,
                        "source": self.source,
                        "teryt": e.teryt_powiat,
                        "raw": json.dumps(e.raw, ensure_ascii=False, default=str),
                    }
                    for e in events
                ],
            )
            cur.execute(
                CLOSE_MISSING_SQL,
                {
                    "source": self.source,
                    "prefix": self.id_prefix,
                    "seen": [e.source_event_id for e in events],
                },
            )

    def run(self, conn: psycopg.Connection, client: httpx.Client) -> int:
        """One full cycle. Never raises: errors are logged and recorded in source_status."""
        params = {"source": self.source, "interval": self.interval_s}
        try:
            events = [e for i in self.validate(self.fetch(client)) if (e := self.normalize(i))]
            with conn.transaction():
                self.upsert(conn, events)
                conn.execute(STATUS_SUCCESS_SQL, params)
            log.info("%s: %d events", self.source, len(events))
            return len(events)
        except Exception as exc:
            log.exception("%s: run failed", self.source)
            with conn.transaction():
                conn.execute(
                    STATUS_ERROR_SQL, {**params, "error": f"{type(exc).__name__}: {exc}"[:1000]}
                )
            return -1
