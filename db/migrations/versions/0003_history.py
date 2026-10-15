"""Fetch attempt log (status page) and water level history (station charts).

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    # One row per worker run; feeds the 7-day availability on /status (30-day retention).
    op.execute("""
        CREATE TABLE fetch_attempts (
            id bigserial PRIMARY KEY,
            source event_source NOT NULL,
            worker text NOT NULL,
            started_at timestamptz NOT NULL,
            duration_ms integer NOT NULL,
            ok boolean NOT NULL,
            items integer,
            error text
        )
    """)
    op.execute("CREATE INDEX fetch_attempts_source_time_idx ON fetch_attempts (source, started_at)")

    # Latest metadata per gauge, refreshed every run.
    op.execute("""
        CREATE TABLE hydro_stations (
            station_id text PRIMARY KEY,
            name text NOT NULL,
            river text,
            warning_cm real,
            alarm_cm real,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    # One row per new measurement (7-day retention).
    op.execute("""
        CREATE TABLE water_levels (
            station_id text NOT NULL,
            measured_at timestamptz NOT NULL,
            level_cm real NOT NULL,
            PRIMARY KEY (station_id, measured_at)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE water_levels")
    op.execute("DROP TABLE hydro_stations")
    op.execute("DROP TABLE fetch_attempts")
