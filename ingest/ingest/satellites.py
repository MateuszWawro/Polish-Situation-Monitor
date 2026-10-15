"""Satellite TLE sets for the map layer (CelesTrak, see docs/SOURCES.md §11).

CelesTrak publishes GP (TLE) data that updates every ~2 h; it stays accurate for days.
We fetch a few groups every 6 h and store the latest set; the browser propagates the
positions with SGP4 (satellite.js). Not events – a standalone snapshot table, like aircraft.
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import psycopg

from ingest.base import USER_AGENT

log = logging.getLogger(__name__)

URL = "https://celestrak.org/NORAD/elements/gp.php"
# Fetched in priority order; a satellite listed in several groups keeps the first (ON CONFLICT).
# Matches the web layer: "visual" + "stations" shown by default, "starlink"/"gnss" on toggle.
GROUPS = ["stations", "visual", "gnss", "starlink"]
INTERVAL_S = 6 * 3600  # CelesTrak asks for no more than one fetch per 2 h; 6 h is gentle.
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 2.0


def parse_tle(text: str, group: str) -> list[dict[str, object]]:
    """Parse CelesTrak 3-line TLE sets (name, line1, line2) into rows."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    rows = []
    for i in range(0, len(lines) - 2, 3):
        name, line1, line2 = lines[i].strip(), lines[i + 1], lines[i + 2]
        if not (line1.startswith("1 ") and line2.startswith("2 ")):
            log.warning("celestrak: skipping malformed TLE near line %d", i)
            continue
        try:
            norad = int(line1[2:7])
        except ValueError:
            continue
        rows.append({"norad_id": norad, "name": name, "grp": group, "tle1": line1, "tle2": line2})
    return rows


def fetch_group(client: httpx.Client, group: str, sleep: Callable[[float], None]) -> str:
    """GET one group's TLE text with backoff; CelesTrak asks callers to stop on non-200."""
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = client.get(
                URL,
                params={"GROUP": group, "FORMAT": "TLE"},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            r.raise_for_status()
            if not r.text.lstrip().startswith(("1 ", "0 ")) and "\n1 " not in r.text:
                raise ValueError(f"celestrak: unexpected body for group {group!r}")
            return r.text
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            if attempt < MAX_ATTEMPTS:
                sleep(BACKOFF_BASE_S * 2 ** (attempt - 1))
    raise last if last else RuntimeError("unreachable")


REPLACE_SQL = "DELETE FROM satellites"
INSERT_SQL = """
INSERT INTO satellites (norad_id, name, grp, tle1, tle2, fetched_at)
VALUES (%(norad_id)s, %(name)s, %(grp)s, %(tle1)s, %(tle2)s, %(fetched_at)s)
ON CONFLICT (norad_id) DO NOTHING
"""


def store(conn: psycopg.Connection, rows: list[dict[str, object]]) -> None:
    now = datetime.now(UTC)
    with conn.cursor() as cur:
        cur.execute(REPLACE_SQL)
        cur.executemany(INSERT_SQL, [{**r, "fetched_at": now} for r in rows])


def run(
    conn: psycopg.Connection, client: httpx.Client, sleep: Callable[[float], None] = time.sleep
) -> int:
    """Fetch every group and replace the table. One failing group aborts the run (table kept)."""
    rows: list[dict[str, object]] = []
    for group in GROUPS:
        rows.extend(parse_tle(fetch_group(client, group, sleep), group))
    if not rows:
        raise ValueError("celestrak: no satellites parsed from any group")
    store(conn, rows)
    log.info("celestrak: stored %d satellites", len(rows))
    return len(rows)
