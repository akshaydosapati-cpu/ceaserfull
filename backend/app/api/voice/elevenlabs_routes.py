from __future__ import annotations

import time
from typing import AsyncGenerator, Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.core.database.session import get_db
from app.core.rate_limiter import rate_limiter
from app.core.security.dependencies import get_current_user
from app.models.user import User
from app.services.desktop_auth_service import verify_desktop_access_token

router = APIRouter(prefix="/elevenlabs", tags=["elevenlabs"])


def enforce_tts_rate_limit(request: Request, device_id: str) -> None:
    """Enforce rate limiting for TTS requests by device identity."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    identity = forwarded or (request.client.host if request.client else "unknown")
    decision = rate_limiter.check("tts", device_id, limit=settings.tts_rate_limit_requests, window_seconds=settings.tts_rate_limit_window_seconds)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "TTS rate limit exceeded. Please try again later.",
                "retry_after": decision.retry_after,
            },
        )


def get_device_from_token(authorization: str, db: Session) -> dict:
    """Extract and validate device info from device authorization header."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing device authorization")
    token = authorization.split(" ", 1)[1]
    payload = verify_desktop_access_token(token)
    if not payload or not payload.get("sub") or not payload.get("device_id"):
        raise HTTPException(status_code=401, detail="Invalid device session")
    device_id = payload.get("device_id")
    user_id = payload.get("sub")

    # Verify device exists and is not revoked
    from app.models.desktop import DesktopDevice
    from app.services.desktop_auth_service import utc_now

    device = db.query(DesktopDevice).filter(
        DesktopDevice.user_id == user_id,
        DesktopDevice.device_id == device_id
    ).first()
    if not device:
        raise HTTPException(status_code=401, detail="Device not found")
    if device.revoked_at and device.revoked_at < utc_now():
        raise HTTPException(status_code=403, detail="Device has been revoked")

    # Check session expiration
    exp = int(payload.get("exp") or 0)
    now = int(time.time())
    if exp and now >= exp:
        raise HTTPException(status_code=401, detail="Device session expired")

    return payload


class ElevenLabsStreamProxy:
    """Proxy for ElevenLabs streaming API with cancellation support."""

    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.base_url = "https://api.elevenlabs.io"

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured.")
        if not self.voice_id:
            raise RuntimeError("ELEVENLABS_VOICE_ID is not configured.")

    async def stream_audio(
        self, text: str, voice_id: str | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream audio chunks from ElevenLabs API."""
        self._require_key()
        selected_voice = voice_id or self.voice_id

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
        }
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/v1/text-to-speech/{selected_voice}/stream"

        # Use httpx async client for streaming
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()

                # Check if response is chunked
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    if chunk:
                        yield chunk


# Global proxy instance
_elevenlabs_proxy = ElevenLabsStreamProxy()


@router.post("/stream")
async def elevenlabs_stream(
    payload: dict,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Stream audio from ElevenLabs API through the backend.

    This endpoint proxies requests to ElevenLabs and streams audio chunks
    directly to the client without buffering. The ElevenLabs API key is
    never exposed to the desktop application.

    Request body:
    {
        "text": "text to synthesize",
        "voice_id": "optional_voice_id_override"
    }
    """
    text = str(payload.get("text") or "").strip()
    voice_id = payload.get("voice_id")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    async def audio_generator():
        """Generator that yields audio chunks from ElevenLabs."""
        started = time.perf_counter()
        first_chunk_ms = None

        try:
            async for chunk in _elevenlabs_proxy.stream_audio(text, voice_id=voice_id):
                if first_chunk_ms is None:
                    first_chunk_ms = int((time.perf_counter() - started) * 1000)
                yield chunk
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="ElevenLabs timeout") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise HTTPException(status_code=502, detail="ElevenLabs authentication failed") from exc
            if exc.response.status_code == 429:
                raise HTTPException(status_code=503, detail="ElevenLabs rate limited") from exc
            raise HTTPException(status_code=502, detail=f"ElevenLabs error: {exc.response.text}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/device/stream")
async def elevenlabs_device_stream(
    request: Request,
    payload: Annotated[dict, Body(...)],
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Device-authenticated stream audio from ElevenLabs API through the backend.

    This endpoint allows NIX desktop to use ElevenLabs TTS without user login.
    The device authorization token is verified, and the ElevenLabs API key is
    never exposed to the desktop application.

    Headers:
        Authorization: Bearer <device_access_token>

    Request body:
    {
        "text": "text to synthesize",
        "voice_id": "optional_voice_id_override"
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing device authorization")

    device_info = get_device_from_token(authorization, db)
    device_id = device_info.get("device_id")

    # Enforce rate limiting
    enforce_tts_rate_limit(request, device_id)

    # Validate text length
    text = str(payload.get("text") or "").strip()
    voice_id = payload.get("voice_id")

    max_text_length = settings.tts_max_text_length or 4000
    if len(text) > max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text exceeds maximum length of {max_text_length} characters. Got {len(text)} characters.",
        )

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    async def audio_generator():
        """Generator that yields audio chunks from ElevenLabs."""
        started = time.perf_counter()
        first_chunk_ms = None

        try:
            async for chunk in _elevenlabs_proxy.stream_audio(text, voice_id=voice_id):
                if first_chunk_ms is None:
                    first_chunk_ms = int((time.perf_counter() - started) * 1000)
                yield chunk
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="ElevenLabs timeout") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise HTTPException(status_code=502, detail="ElevenLabs authentication failed") from exc
            if exc.response.status_code == 429:
                raise HTTPException(status_code=503, detail="ElevenLabs rate limited") from exc
            raise HTTPException(status_code=502, detail=f"ElevenLabs error: {exc.response.text}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
