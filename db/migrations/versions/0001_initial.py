"""Initial schema: admin_units, events, source_status.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("""
        CREATE TABLE admin_units (
            teryt text PRIMARY KEY,
            level text NOT NULL CHECK (level IN ('voivodeship', 'powiat')),
            name text NOT NULL,
            geom geometry(MultiPolygon, 4326) NOT NULL
        )
    """)
    op.execute("CREATE INDEX admin_units_geom_idx ON admin_units USING gist (geom)")

    op.execute("CREATE TYPE event_source AS ENUM ('imgw_meteo', 'imgw_hydro', 'gios', 'firms')")
    op.execute(
        "CREATE TYPE event_type AS ENUM "
        "('weather_warning', 'hydro_warning', 'air_quality', 'fire_hotspot')"
    )
    op.execute("""
        CREATE TABLE events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source event_source NOT NULL,
            source_event_id text NOT NULL,
            type event_type NOT NULL,
            severity smallint NOT NULL CHECK (severity BETWEEN 0 AND 3),
            title text NOT NULL,
            description text,
            geom geometry(Geometry, 4326),
            teryt_powiat text[] NOT NULL DEFAULT '{}',
            valid_from timestamptz,
            valid_to timestamptz,
            source_url text,
            fetched_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            raw jsonb,
            UNIQUE (source, source_event_id)
        )
    """)
    op.execute("CREATE INDEX events_geom_idx ON events USING gist (geom)")
    op.execute("CREATE INDEX events_teryt_idx ON events USING gin (teryt_powiat)")
    op.execute("CREATE INDEX events_type_valid_to_idx ON events (type, valid_to)")

    op.execute("""
        CREATE TABLE source_status (
            source event_source PRIMARY KEY,
            last_success_at timestamptz,
            last_error text,
            last_error_at timestamptz,
            expected_interval_s integer NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE source_status")
    op.execute("DROP TABLE events")
    op.execute("DROP TYPE event_type")
    op.execute("DROP TYPE event_source")
    op.execute("DROP TABLE admin_units")
