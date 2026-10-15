"""Latest aircraft snapshot over Poland (map layer). No history is kept.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    # Replaced as a whole on every adsb.lol run: positions are never accumulated into tracks.
    op.execute("""
        CREATE TABLE aircraft (
            hex text PRIMARY KEY,
            class text NOT NULL CHECK (class IN ('commercial', 'private', 'military')),
            callsign text,
            registration text,
            aircraft_type text,
            altitude_ft integer,
            speed_kt real,
            track real,
            geom geometry(Point, 4326) NOT NULL,
            seen_at timestamptz NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE aircraft")
