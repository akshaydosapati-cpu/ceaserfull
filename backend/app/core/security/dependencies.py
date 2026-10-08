from typing import Annotated
from time import monotonic, perf_counter
from threading import Lock
import logging

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
import httpx
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config.settings import settings
from app.core.database.session import database_timing, get_db
from app.core.database.execution import measured_db_call
from app.core.security.supabase_auth import supabase_auth
from app.models.user import User
from app.models.desktop import DesktopDevice
from app.repositories.user_repository import UserRepository
from app.services.desktop_auth_service import verify_desktop_access_token


_AUTH_CACHE_TTL_SECONDS = 300.0
_AUTH_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_AUTH_CACHE_LOCK = Lock()
logger = logging.getLogger(__name__)


def _cached_supabase_user(access_token: str) -> dict[str, str] | None:
    now = monotonic()
    with _AUTH_CACHE_LOCK:
        cached = _AUTH_CACHE.get(access_token)
        if not cached:
            return None
        expires_at, user = cached
        if expires_at <= now:
            _AUTH_CACHE.pop(access_token, None)
            return None
        return user


def _store_cached_supabase_user(access_token: str, user: dict[str, str]) -> None:
    with _AUTH_CACHE_LOCK:
        _AUTH_CACHE[access_token] = (monotonic() + _AUTH_CACHE_TTL_SECONDS, user)


def _get_dev_user(db: Session) -> User:
    user = UserRepository(db).get_or_create(
        email="dev@ceaser.local",
        user_id="00000000-0000-4000-8000-000000000001",
    )
    db.commit()
    db.refresh(user)
    return user


def _validate_desktop_user(db: Session, user_id: str | None, device_id: str | None) -> User:
    query = db.query(User, DesktopDevice.revoked_at).outerjoin(
        DesktopDevice,
        (DesktopDevice.user_id == User.id) & (DesktopDevice.device_id == device_id),
    ).filter(User.id == user_id)
    row = query.first()
    user = row[0] if row else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid desktop session")
    if device_id and row[1]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Desktop device revoked")
    return user


def _get_or_create_supabase_user(db: Session, user_id: str, email: str) -> User:
    measured_db_call(db.connection, perf_counter())
    repo = UserRepository(db)
    user = repo.get(user_id) or repo.get_by_email(email)
    if user is None:
        user = repo.create(email=email, user_id=user_id)
        db.commit()
        db.refresh(user)
    return user


def _rollback(db: Session) -> None:
    db.rollback()


async def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    auth_started = monotonic()
    auth_trace: dict[str, float | str | bool] = {}
    request.state.ceaser_auth_trace = auth_trace
    logger.info("ceaser_auth_stage stage=auth_started")
    if settings.dev_auth_bypass:
        try:
            db_started = monotonic()
            user = await run_in_threadpool(_get_dev_user, db)
            auth_trace.update(mode="dev", cache_hit=False, remote_ms=0.0, db_validation_ms=round((monotonic() - db_started) * 1000, 2))
            auth_trace["total_ms"] = round((monotonic() - auth_started) * 1000, 2)
            logger.info("ceaser_auth_stage stage=auth_complete mode=dev duration_ms=%.2f", (monotonic() - auth_started) * 1000)
            return user
        except (SQLAlchemyError, Exception) as exc:
            await run_in_threadpool(_rollback, db)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CEASER account setup is temporarily unavailable.") from exc

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    desktop_payload = verify_desktop_access_token(token)
    if desktop_payload:
        try:
            db_started = monotonic()
            user = await run_in_threadpool(
                _validate_desktop_user,
                db,
                desktop_payload.get("sub"),
                desktop_payload.get("device_id"),
            )
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await run_in_threadpool(_rollback, db)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CEASER desktop service is temporarily unavailable.") from exc
        auth_trace.update(mode="desktop", cache_hit=False, remote_ms=0.0, db_validation_ms=round((monotonic() - db_started) * 1000, 2))
        auth_trace["total_ms"] = round((monotonic() - auth_started) * 1000, 2)
        logger.info("ceaser_auth_stage stage=auth_complete mode=desktop duration_ms=%.2f", (monotonic() - auth_started) * 1000)
        return user
    try:
        supabase_user = _cached_supabase_user(token)
        if supabase_user is None:
            remote_started = monotonic()
            supabase_user = await supabase_auth.get_user(token)
            _store_cached_supabase_user(token, {"email": supabase_user.get("email") or "", "id": supabase_user.get("id") or ""})
            logger.info("ceaser_auth_stage stage=supabase_remote duration_ms=%.2f", (monotonic() - remote_started) * 1000)
            auth_trace.update(cache_hit=False, remote_ms=round((monotonic() - remote_started) * 1000, 2))
        else:
            logger.info("ceaser_auth_stage stage=supabase_cache_hit")
            auth_trace.update(cache_hit=True, remote_ms=0.0)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500 or exc.response.status_code == 429:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service temporarily unavailable") from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    except (httpx.RequestError, TimeoutError) as exc:
        logger.warning("ceaser_auth_stage stage=supabase_unavailable error=%s", exc.__class__.__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service temporarily unavailable") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    email = supabase_user.get("email")
    user_id = supabase_user.get("id")
    if not email or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase user")

    try:
        db_started = monotonic()
        db_count_before, db_ms_before = database_timing()
        # Supabase has already validated the token. Existing local identities
        # need only a read; committing and refreshing an unchanged user added
        # two remote database round trips to every authenticated request.
        user = await run_in_threadpool(measured_db_call, _get_or_create_supabase_user, perf_counter(), db, user_id, email)
        auth_trace.update(mode="supabase", db_validation_ms=round((monotonic() - db_started) * 1000, 2))
        db_count_after, db_ms_after = database_timing()
        auth_trace.update(
            db_queries=max(0, db_count_after - db_count_before),
            db_query_ms=round(max(0.0, db_ms_after - db_ms_before), 2),
        )
        auth_trace["total_ms"] = round((monotonic() - auth_started) * 1000, 2)
        logger.info(
            "ceaser_auth_stage stage=auth_complete mode=supabase duration_ms=%.2f db_queries=%s db_ms=%.2f",
            (monotonic() - auth_started) * 1000,
            auth_trace["db_queries"],
            auth_trace["db_query_ms"],
        )
        return user
    except (SQLAlchemyError, Exception) as exc:
        await run_in_threadpool(_rollback, db)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CEASER account setup is temporarily unavailable.") from exc
