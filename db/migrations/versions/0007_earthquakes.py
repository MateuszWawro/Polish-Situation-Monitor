"""Add EMSC source and earthquake event type.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.execute("ALTER TYPE event_source ADD VALUE IF NOT EXISTS 'emsc'")
    op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'earthquake'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values; remove the rows so the values are simply unused.
    op.execute("DELETE FROM events WHERE source = 'emsc' OR type = 'earthquake'")
    op.execute("DELETE FROM source_status WHERE source = 'emsc'")
