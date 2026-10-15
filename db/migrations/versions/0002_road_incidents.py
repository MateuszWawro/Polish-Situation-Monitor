"""Add GDDKiA source and road_incident event type.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.execute("ALTER TYPE event_source ADD VALUE IF NOT EXISTS 'gddkia'")
    op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'road_incident'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values; remove the rows so the values are simply unused.
    op.execute("DELETE FROM events WHERE source = 'gddkia' OR type = 'road_incident'")
    op.execute("DELETE FROM source_status WHERE source = 'gddkia'")
