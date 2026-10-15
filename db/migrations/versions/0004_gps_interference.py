"""Add adsb.lol source and gps_interference event type.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.execute("ALTER TYPE event_source ADD VALUE IF NOT EXISTS 'adsb_lol'")
    op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'gps_interference'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values; remove the rows so the values are simply unused.
    op.execute("DELETE FROM events WHERE source = 'adsb_lol' OR type = 'gps_interference'")
    op.execute("DELETE FROM fetch_attempts WHERE source = 'adsb_lol'")
    op.execute("DELETE FROM source_status WHERE source = 'adsb_lol'")
