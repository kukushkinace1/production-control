"""init models

Revision ID: 20260417_0001
Revises:
Create Date: 2026-04-17 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260417_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("secret_key", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("timeout", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_subscriptions")),
    )

    op.create_table(
        "work_centers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_centers")),
        sa.UniqueConstraint("identifier", name=op.f("uq_work_centers_identifier")),
    )
    op.create_index(op.f("ix_work_centers_identifier"), "work_centers", ["identifier"], unique=True)

    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_description", sa.String(length=500), nullable=False),
        sa.Column("work_center_id", sa.Integer(), nullable=False),
        sa.Column("shift", sa.String(length=100), nullable=False),
        sa.Column("team", sa.String(length=100), nullable=False),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("batch_date", sa.Date(), nullable=False),
        sa.Column("nomenclature", sa.String(length=255), nullable=False),
        sa.Column("ekn_code", sa.String(length=100), nullable=False),
        sa.Column("shift_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_center_id"],
            ["work_centers.id"],
            name=op.f("fk_batches_work_center_id_work_centers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.UniqueConstraint("batch_number", "batch_date", name="uq_batch_number_date"),
    )
    op.create_index(op.f("ix_batches_batch_date"), "batches", ["batch_date"], unique=False)
    op.create_index(op.f("ix_batches_batch_number"), "batches", ["batch_number"], unique=False)
    op.create_index("idx_batch_closed", "batches", ["is_closed"], unique=False)
    op.create_index("idx_batch_shift_times", "batches", ["shift_start", "shift_end"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unique_code", sa.String(length=255), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("is_aggregated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("aggregated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["batches.id"],
            name=op.f("fk_products_batch_id_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("unique_code", name=op.f("uq_products_unique_code")),
    )
    op.create_index(op.f("ix_products_batch_id"), "products", ["batch_id"], unique=False)
    op.create_index(
        "idx_product_batch_aggregated",
        "products",
        ["batch_id", "is_aggregated"],
        unique=False,
    )
    op.create_index(op.f("ix_products_is_aggregated"), "products", ["is_aggregated"], unique=False)
    op.create_index(op.f("ix_products_unique_code"), "products", ["unique_code"], unique=True)

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["webhook_subscriptions.id"],
            name=op.f("fk_webhook_deliveries_subscription_id_webhook_subscriptions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_deliveries")),
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_index(op.f("ix_products_unique_code"), table_name="products")
    op.drop_index(op.f("ix_products_is_aggregated"), table_name="products")
    op.drop_index("idx_product_batch_aggregated", table_name="products")
    op.drop_index(op.f("ix_products_batch_id"), table_name="products")
    op.drop_table("products")
    op.drop_index("idx_batch_shift_times", table_name="batches")
    op.drop_index("idx_batch_closed", table_name="batches")
    op.drop_index(op.f("ix_batches_batch_number"), table_name="batches")
    op.drop_index(op.f("ix_batches_batch_date"), table_name="batches")
    op.drop_table("batches")
    op.drop_index(op.f("ix_work_centers_identifier"), table_name="work_centers")
    op.drop_table("work_centers")
    op.drop_table("webhook_subscriptions")
