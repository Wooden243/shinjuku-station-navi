from __future__ import annotations

import hashlib
import hmac
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import session_scope
from app.models import (
    AuditLogRecord,
    MappingSubmissionRecord,
    OfficialPlaceRecord,
    SubmissionSupportRecord,
)
from app.schemas.api import (
    AuditLog,
    MappingReview,
    MappingSubmission,
    MappingSubmissionCreate,
    OfficialComparison,
)


class SubmissionRateLimitError(RuntimeError):
    pass


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def hash_client_identifier(identifier: str, settings: Settings) -> str:
    return hmac.new(
        settings.client_hash_salt.encode("utf-8"),
        identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _to_submission(record: MappingSubmissionRecord) -> MappingSubmission:
    return MappingSubmission.model_validate(
        {
            column.name: getattr(record, column.name)
            for column in MappingSubmissionRecord.__table__.columns
            if column.name
            not in {
                "normalized_name",
                "normalized_description",
            }
        }
    )


def _audit(
    session: Session,
    *,
    submission_id: int | None,
    action: str,
    actor: str,
    details: dict[str, Any],
    now: datetime,
) -> None:
    session.add(
        AuditLogRecord(
            submission_id=submission_id,
            action=action,
            actor=actor,
            details=details,
            created_at=now,
        )
    )


def _enforce_rate_limit(
    session: Session,
    client_hash: str,
    settings: Settings,
    now: datetime,
) -> None:
    window_start = now - timedelta(minutes=settings.submission_rate_window_minutes)
    recent = session.scalar(
        select(func.count(SubmissionSupportRecord.id)).where(
            SubmissionSupportRecord.client_hash == client_hash,
            SubmissionSupportRecord.created_at >= window_start,
        )
    )
    if int(recent or 0) >= settings.submission_rate_limit:
        raise SubmissionRateLimitError(
            f"{settings.submission_rate_window_minutes}分間の投稿上限に達しました"
        )


def create_submission(
    payload: MappingSubmissionCreate,
    *,
    client_hash: str,
    settings: Settings,
) -> MappingSubmission:
    now = datetime.now(UTC)
    normalized_name = normalized_text(payload.name)
    normalized_description = normalized_text(payload.description)
    with session_scope(settings) as session:
        idempotent = session.scalar(
            select(MappingSubmissionRecord).where(
                MappingSubmissionRecord.client_submission_id
                == payload.client_submission_id
            )
        )
        if idempotent is not None:
            return _to_submission(idempotent)
        _enforce_rate_limit(session, client_hash, settings, now)
        duplicate = session.scalar(
            select(MappingSubmissionRecord)
            .where(
                MappingSubmissionRecord.status.notin_(["rejected", "archived"]),
                MappingSubmissionRecord.category == payload.category,
                MappingSubmissionRecord.floor == payload.floor,
                MappingSubmissionRecord.normalized_name == normalized_name,
                MappingSubmissionRecord.normalized_description
                == normalized_description,
                MappingSubmissionRecord.lon.between(
                    payload.lon - 0.00006, payload.lon + 0.00006
                ),
                MappingSubmissionRecord.lat.between(
                    payload.lat - 0.000045, payload.lat + 0.000045
                ),
            )
            .order_by(MappingSubmissionRecord.id)
        )
        if duplicate is not None:
            existing_support = session.scalar(
                select(SubmissionSupportRecord.id).where(
                    SubmissionSupportRecord.submission_id == duplicate.id,
                    SubmissionSupportRecord.client_hash == client_hash,
                )
            )
            if existing_support is None:
                session.add(
                    SubmissionSupportRecord(
                        submission_id=duplicate.id,
                        client_hash=client_hash,
                        created_at=now,
                    )
                )
                duplicate.support_count += 1
                duplicate.updated_at = now
                _audit(
                    session,
                    submission_id=duplicate.id,
                    action="submission_supported",
                    actor="anonymous-client",
                    details={"support_count": duplicate.support_count},
                    now=now,
                )
            return _to_submission(duplicate)

        record = MappingSubmissionRecord(
            client_submission_id=payload.client_submission_id,
            category=payload.category,
            name=payload.name,
            normalized_name=normalized_name,
            description=payload.description,
            normalized_description=normalized_description,
            floor=payload.floor,
            lon=payload.lon,
            lat=payload.lat,
            source_method=payload.source_method,
            supplemental=payload.supplemental,
            observed_at=payload.observed_at,
            status="pending",
            review_note="",
            reviewed_by=None,
            reviewed_at=None,
            support_count=1,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        session.add(
            SubmissionSupportRecord(
                submission_id=record.id,
                client_hash=client_hash,
                created_at=now,
            )
        )
        _audit(
            session,
            submission_id=record.id,
            action="submission_created",
            actor="anonymous-client",
            details={
                "category": record.category,
                "floor": record.floor,
                "client_submission_id": record.client_submission_id,
            },
            now=now,
        )
        result = _to_submission(record)
    return result


def list_submissions(
    settings: Settings,
    *,
    public_only: bool = False,
    status: str | None = None,
    category: str | None = None,
    floor: str | None = None,
    sort: Literal["newest", "oldest", "supports"] = "newest",
) -> list[MappingSubmission]:
    statement = select(MappingSubmissionRecord)
    if public_only:
        statement = statement.where(MappingSubmissionRecord.status == "approved")
    elif status:
        statement = statement.where(MappingSubmissionRecord.status == status)
    if category:
        statement = statement.where(MappingSubmissionRecord.category == category)
    if floor:
        statement = statement.where(MappingSubmissionRecord.floor == floor)
    if sort == "supports":
        statement = statement.order_by(
            MappingSubmissionRecord.support_count.desc(),
            MappingSubmissionRecord.created_at.desc(),
        )
    elif sort == "oldest":
        statement = statement.order_by(MappingSubmissionRecord.created_at.asc())
    else:
        statement = statement.order_by(MappingSubmissionRecord.created_at.desc())
    with session_scope(settings) as session:
        return [
            _to_submission(record)
            for record in session.scalars(statement).all()
        ]


def get_submission(
    settings: Settings, submission_id: int
) -> MappingSubmission | None:
    with session_scope(settings) as session:
        record = session.get(MappingSubmissionRecord, submission_id)
        return None if record is None else _to_submission(record)


def review_submission(
    settings: Settings,
    submission_id: int,
    payload: MappingReview,
    actor: str,
) -> MappingSubmission | None:
    now = datetime.now(UTC)
    with session_scope(settings) as session:
        record = session.get(MappingSubmissionRecord, submission_id)
        if record is None:
            return None
        changed: dict[str, Any] = {
            "status": {"from": record.status, "to": payload.status},
            "review_note": payload.review_note,
        }
        for field in ("category", "name", "description", "floor", "lon", "lat"):
            value = getattr(payload, field)
            if value is None or value == getattr(record, field):
                continue
            changed[field] = {"from": getattr(record, field), "to": value}
            setattr(record, field, value)
        record.normalized_name = normalized_text(record.name)
        record.normalized_description = normalized_text(record.description)
        record.status = payload.status
        record.review_note = payload.review_note
        record.reviewed_by = actor
        record.reviewed_at = now
        record.updated_at = now
        _audit(
            session,
            submission_id=record.id,
            action=f"submission_{payload.status}",
            actor=actor,
            details=changed,
            now=now,
        )
        result = _to_submission(record)
    return result


def similar_submissions(
    settings: Settings,
    submission: MappingSubmission,
    *,
    limit: int = 8,
) -> list[MappingSubmission]:
    with session_scope(settings) as session:
        statement = (
            select(MappingSubmissionRecord)
            .where(
                MappingSubmissionRecord.id != submission.id,
                MappingSubmissionRecord.floor == submission.floor,
                MappingSubmissionRecord.lon.between(
                    submission.lon - 0.00012, submission.lon + 0.00012
                ),
                MappingSubmissionRecord.lat.between(
                    submission.lat - 0.00009, submission.lat + 0.00009
                ),
            )
            .order_by(MappingSubmissionRecord.support_count.desc())
            .limit(limit)
        )
        return [_to_submission(item) for item in session.scalars(statement).all()]


def _distance_meters(
    left_lon: float, left_lat: float, right_lon: float, right_lat: float
) -> float:
    lat1 = math.radians(left_lat)
    lat2 = math.radians(right_lat)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(right_lon - left_lon)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6_371_008.8 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def official_nearby(
    settings: Settings,
    submission: MappingSubmission,
    *,
    limit: int = 8,
) -> list[OfficialComparison]:
    with session_scope(settings) as session:
        records = session.scalars(
            select(OfficialPlaceRecord).where(
                OfficialPlaceRecord.published.is_(True),
                OfficialPlaceRecord.floor == submission.floor,
                OfficialPlaceRecord.lon.between(
                    submission.lon - 0.00035, submission.lon + 0.00035
                ),
                OfficialPlaceRecord.lat.between(
                    submission.lat - 0.00027, submission.lat + 0.00027
                ),
            )
        ).all()
        candidates = [
            (
                _distance_meters(
                    submission.lon,
                    submission.lat,
                    record.lon,
                    record.lat,
                ),
                record,
            )
            for record in records
        ]
        return [
            OfficialComparison(
                id=record.external_id,
                kind=record.kind,
                name=record.name,
                floor=record.floor,
                distance_meters=round(distance, 1),
            )
            for distance, record in sorted(candidates, key=lambda item: item[0])[
                :limit
            ]
        ]


def list_audit_logs(settings: Settings, *, limit: int = 200) -> list[AuditLog]:
    with session_scope(settings) as session:
        records = session.scalars(
            select(AuditLogRecord)
            .order_by(AuditLogRecord.created_at.desc())
            .limit(limit)
        ).all()
        return [
            AuditLog.model_validate(
                {
                    "id": record.id,
                    "submission_id": record.submission_id,
                    "action": record.action,
                    "actor": record.actor,
                    "details": record.details,
                    "created_at": record.created_at,
                }
            )
            for record in records
        ]
