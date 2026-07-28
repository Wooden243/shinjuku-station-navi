"""Persistent submissions, moderation, audit, and official data versions.

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_submission_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("normalized_description", sa.Text(), nullable=False),
        sa.Column("floor", sa.String(length=20), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("source_method", sa.String(length=240), nullable=False),
        sa.Column("supplemental", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=240), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', "
            "'needs_verification', 'archived')",
            name="ck_mapping_submissions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_submission_id"),
    )
    op.create_index(
        "ix_mapping_submissions_filters",
        "mapping_submissions",
        ["status", "category", "floor"],
    )
    op.create_index(
        "ix_mapping_submissions_location",
        "mapping_submissions",
        ["floor", "lon", "lat"],
    )
    op.create_table(
        "submission_supports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("client_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["mapping_submissions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id", "client_hash", name="uq_submission_support_client"
        ),
    )
    op.create_index(
        "ix_submission_supports_rate",
        "submission_supports",
        ["client_hash", "created_at"],
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=240), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["mapping_submissions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_table(
        "data_versions",
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_table(
        "official_places",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("data_version", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("floor", sa.String(length=20), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["data_version"], ["data_versions.version"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "data_version",
            "external_id",
            name="uq_official_place_version_id",
        ),
    )
    op.create_index(
        "ix_official_places_kind", "official_places", ["kind", "published"]
    )
    op.create_index(
        "ix_official_places_location",
        "official_places",
        ["floor", "lon", "lat"],
    )


def downgrade() -> None:
    op.drop_table("official_places")
    op.drop_table("data_versions")
    op.drop_table("audit_logs")
    op.drop_table("submission_supports")
    op.drop_table("mapping_submissions")
