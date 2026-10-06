"""Create curated FAQ knowledge base."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faqs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("answer", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("product", sa.String(length=200), nullable=True),
        sa.Column("version", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('active', 'inactive', 'draft')", name="ck_faqs_faq_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index("ix_faqs_status", "faqs", ["status"])
    op.create_index("ix_faqs_status_category", "faqs", ["status", "category"])
    op.create_index("ix_faqs_status_product", "faqs", ["status", "product"])
    op.create_index("ix_faqs_status_version", "faqs", ["status", "version"])


def downgrade() -> None:
    op.drop_index("ix_faqs_status_version", table_name="faqs")
    op.drop_index("ix_faqs_status_product", table_name="faqs")
    op.drop_index("ix_faqs_status_category", table_name="faqs")
    op.drop_index("ix_faqs_status", table_name="faqs")
    op.drop_table("faqs")
