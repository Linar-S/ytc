"""Initial empty migration.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-07

This revision intentionally creates no schema objects. Domain tables will be
added by subsequent migrations.
"""

from collections.abc import Sequence

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
