"""Prepare a dedicated test database: Alembic schema, empty data tables, tiny admin_units.

Used by the api/ and ingest/ test conftests (imported via sys.path). Never point it at a
database with real data: every call wipes all tables.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg

DB_DIR = Path(__file__).parent

# Simple boxes instead of real PRG shapes, placed around the real cities so tests can use
# real coordinates: (teryt, level, name, west, south, east, north).
ADMIN_UNITS = [
    ("16", "voivodeship", "opolskie", 16.9, 49.97, 18.7, 51.2),
    ("1261", "powiat", "Kraków", 19.79, 49.97, 20.22, 50.13),
    ("1465", "powiat", "Warszawa", 20.85, 52.10, 21.27, 52.37),
    ("1661", "powiat", "Opole", 17.80, 50.60, 18.05, 50.75),
    ("1807", "powiat", "krośnieński", 21.30, 49.40, 21.60, 49.70),
    ("1861", "powiat", "Krosno", 21.70, 49.65, 21.80, 49.72),
    ("2061", "powiat", "Białystok", 23.05, 53.05, 23.30, 53.20),
]
TABLES = ("events, source_status, fetch_attempts, water_levels, hydro_stations, aircraft,"
          " satellites, admin_units")  # fmt: skip


def prepare(url: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=DB_DIR, env=env,
                   check=True)  # fmt: skip
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute(f"TRUNCATE {TABLES}")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO admin_units VALUES"
                " (%s, %s, %s, ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)))",
                ADMIN_UNITS,
            )
