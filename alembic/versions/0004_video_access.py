"""Add private video access grants.

Revision ID: 0004_video_access
Revises: 0003_refresh_tokens
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_video_access"
down_revision: str | Sequence[str] | None = "0003_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the video_access table."""

    op.create_table(
        "video_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_video_access_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_video_access_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_video_access"),
        sa.UniqueConstraint("video_id", "user_id", name="uq_video_access_video_user"),
    )
    op.create_index("ix_video_access_user_id", "video_access", ["user_id"])


def downgrade() -> None:
    """Drop the video_access table."""

    op.drop_index("ix_video_access_user_id", table_name="video_access")
    op.drop_table("video_access")
