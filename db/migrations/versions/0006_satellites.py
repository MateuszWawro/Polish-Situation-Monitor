"""Latest TLE sets for the satellite map layer (CelesTrak). No history.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # Replaced on every fetch. The browser propagates positions from the TLE with SGP4,
    # so only the orbital elements are stored, not positions.
    op.execute("""
        CREATE TABLE satellites (
            norad_id integer PRIMARY KEY,
            name text NOT NULL,
            grp text NOT NULL,
            tle1 text NOT NULL,
            tle2 text NOT NULL,
            fetched_at timestamptz NOT NULL
        )
    """)
    op.execute("CREATE INDEX satellites_grp_idx ON satellites (grp)")


def downgrade() -> None:
    op.execute("DROP TABLE satellites")
