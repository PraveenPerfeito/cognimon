"""add revoked refresh tokens table

Revision ID: 20260510_0002
Revises: 20260509_0001
Create Date: 2026-05-10 11:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260510_0002"
down_revision = "20260509_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_refresh_tokens",
        sa.Column("token_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index(
        op.f("ix_revoked_refresh_tokens_user_id"),
        "revoked_refresh_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_revoked_refresh_tokens_user_id"), table_name="revoked_refresh_tokens")
    op.drop_table("revoked_refresh_tokens")
