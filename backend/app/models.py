from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MappingSubmissionRecord(Base):
    __tablename__ = "mapping_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', "
            "'needs_verification', 'archived')",
            name="ck_mapping_submissions_status",
        ),
        Index("ix_mapping_submissions_filters", "status", "category", "floor"),
        Index("ix_mapping_submissions_location", "floor", "lon", "lat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_submission_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_description: Mapped[str] = mapped_column(Text, nullable=False)
    floor: Mapped[str] = mapped_column(String(20), nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    source_method: Mapped[str] = mapped_column(String(240), nullable=False)
    supplemental: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(240))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    support_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubmissionSupportRecord(Base):
    __tablename__ = "submission_supports"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "client_hash", name="uq_submission_support_client"
        ),
        Index("ix_submission_supports_rate", "client_hash", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("mapping_submissions.id", ondelete="CASCADE"), nullable=False
    )
    client_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("mapping_submissions.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(240), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataVersionRecord(Base):
    __tablename__ = "data_versions"

    version: Mapped[str] = mapped_column(String(120), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OfficialPlaceRecord(Base):
    __tablename__ = "official_places"
    __table_args__ = (
        UniqueConstraint(
            "data_version", "external_id", name="uq_official_place_version_id"
        ),
        Index("ix_official_places_location", "floor", "lon", "lat"),
        Index("ix_official_places_kind", "kind", "published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_version: Mapped[str] = mapped_column(
        ForeignKey("data_versions.version", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    floor: Mapped[str] = mapped_column(String(20), nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    published: Mapped[bool] = mapped_column(default=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

