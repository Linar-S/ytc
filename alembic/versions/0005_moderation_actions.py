"""Add moderation action audit table.

Revision ID: 0005_moderation_actions
Revises: 0004_video_access
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_moderation_actions"
down_revision: str | Sequence[str] | None = "0004_video_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the moderation_actions table."""

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("moderator_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["moderator_id"],
            ["users.id"],
            name="fk_moderation_actions_moderator_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_moderation_actions_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_actions"),
    )
    op.create_index("ix_moderation_actions_video_id", "moderation_actions", ["video_id"])


def downgrade() -> None:
    """Drop the moderation_actions table."""

    op.drop_index("ix_moderation_actions_video_id", table_name="moderation_actions")
    op.drop_table("moderation_actions")
