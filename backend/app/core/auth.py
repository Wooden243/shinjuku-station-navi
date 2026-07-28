from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response

from app.core.config import Settings

ADMIN_COOKIE = "shinjuku_admin_session"
SESSION_HOURS = 8


def _session_secret(settings: Settings) -> bytes:
    if not settings.session_secret or len(settings.session_secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="SHINJUKU_SESSION_SECRETを32文字以上で設定してください。",
        )
    return settings.session_secret.encode("utf-8")


def _encode_session(actor: str, expires_at: datetime, settings: Settings) -> str:
    payload = f"{actor}|{int(expires_at.timestamp())}"
    signature = hmac.new(
        _session_secret(settings), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    token = f"{payload}|{signature}".encode()
    return base64.urlsafe_b64encode(token).decode("ascii")


def _decode_session(token: str, settings: Settings) -> str | None:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        actor, expiry_text, signature = decoded.rsplit("|", 2)
        payload = f"{actor}|{expiry_text}"
        expected = hmac.new(
            _session_secret(settings), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if int(expiry_text) <= int(time.time()):
            return None
        return actor
    except (ValueError, UnicodeDecodeError):
        return None


def create_development_session(
    response: Response,
    *,
    key: str,
    settings: Settings,
) -> tuple[str, datetime]:
    if settings.is_production or settings.auth_mode != "development-key":
        raise HTTPException(
            status_code=403,
            detail="開発用キー認証は本番環境では利用できません。",
        )
    if not settings.admin_key:
        raise HTTPException(
            status_code=503, detail="SHINJUKU_ADMIN_KEYが設定されていません。"
        )
    if not hmac.compare_digest(key, settings.admin_key):
        raise HTTPException(status_code=401, detail="管理者認証に失敗しました。")
    actor = "local-development-admin"
    expires_at = datetime.now(UTC) + timedelta(hours=SESSION_HOURS)
    response.set_cookie(
        ADMIN_COOKIE,
        _encode_session(actor, expires_at, settings),
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
    )
    return actor, expires_at


def clear_admin_session(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        ADMIN_COOKIE,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
    )


def verify_admin_request(request: Request, settings: Settings) -> str:
    if settings.auth_mode == "development-key":
        if settings.is_production:
            raise HTTPException(
                status_code=503,
                detail="本番環境でdevelopment-key認証は使用できません。",
            )
        session_token = request.cookies.get(ADMIN_COOKIE)
        if session_token:
            actor = _decode_session(session_token, settings)
            if actor:
                return actor
        legacy_key = request.headers.get("X-Admin-Key")
        if (
            legacy_key
            and settings.admin_key
            and hmac.compare_digest(legacy_key, settings.admin_key)
        ):
            return "local-development-admin"
        raise HTTPException(status_code=401, detail="管理者認証に失敗しました。")
    if settings.auth_mode == "oidc-proxy":
        user = request.headers.get("X-Authenticated-User")
        proxy_secret = request.headers.get("X-Auth-Proxy-Secret")
        if (
            not user
            or not settings.auth_proxy_shared_secret
            or not proxy_secret
            or not hmac.compare_digest(
                proxy_secret, settings.auth_proxy_shared_secret
            )
        ):
            raise HTTPException(status_code=401, detail="OIDC認証が必要です。")
        return user[:240]
    raise HTTPException(status_code=503, detail="管理者認証方式が不正です。")
