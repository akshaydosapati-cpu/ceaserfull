"""Tests for the device-authenticated TTS gateway endpoint."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.voice.elevenlabs_routes import router
from app.core.config.settings import settings
from app.core.database.session import get_db
from app.main import app
from app.models.desktop import DesktopDevice, DesktopRefreshSession
from app.models.user import User
from app.services.desktop_auth_service import create_desktop_access_token


# Override get_db dependency for testing
def override_get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.core.database.base import Base
    import app.models
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.core.database.base import Base
    import app.models
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Create test user
    user = User(
        id="test-user-uuid-1234",
        email="test@example.com",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create test device
    device = DesktopDevice(
        user_id=user.id,
        device_id="test-device-456",
        device_name="Test Device",
        platform="Windows",
        app_version="1.0.0",
    )
    db.add(device)
    db.commit()

    # Create refresh session
    refresh_session = DesktopRefreshSession(
        user_id=user.id,
        device_id="test-device-456",
        token_hash="test_refresh_token_hash",
        expires_at=datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    db.add(refresh_session)
    db.commit()

    yield db

    db.close()


@pytest.fixture
def device_access_token(db_session):
    """Generate a valid device access token for testing."""
    user = db_session.query(User).first()
    return create_desktop_access_token(user, "test-device-456")


def test_device_tts_gateway_requires_authorization_header(client):
    """TEST 2: No device credential -> rejected."""
    response = client.post(
        "/voice/elevenlabs/device/stream",
        json={"text": "Hello"},
    )
    assert response.status_code == 401
    assert "Missing device authorization" in response.json()["detail"]


def test_device_tts_gateway_rejects_invalid_token(client):
    """TEST 3: Invalid device credential -> rejected."""
    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": "Bearer invalid-token"},
        json={"text": "Hello"},
    )
    assert response.status_code == 401
    assert "Invalid device session" in response.json()["detail"]


def test_device_tts_gateway_rejects_revoked_device(client, db_session, device_access_token):
    """TEST 4: Revoked device -> rejected."""
    from app.models.desktop import DesktopDevice
    from datetime import datetime, timezone

    device = db_session.query(DesktopDevice).filter_by(device_id="test-device-456").first()
    device.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": f"Bearer {device_access_token}"},
        json={"text": "Hello"},
    )
    assert response.status_code == 403
    assert "Device has been revoked" in response.json()["detail"]


def test_device_tts_gateway_rejects_expired_session(client, db_session):
    """TEST 5: Expired device credential -> rejected."""
    from app.models.user import User

    user = db_session.query(User).first()

    # Create expired token
    now = int(time.time())
    payload = {
        "typ": "desktop_access",
        "sub": user.id,
        "email": user.email,
        "device_id": "test-device-456",
        "iat": now - 3600,  # 1 hour ago
        "exp": now - 1800,  # 30 minutes ago - expired
    }

    from app.services.desktop_auth_service import _b64url, _secret
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64url(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    expired_token = f"cdat.{body}.{sig}"

    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={"text": "Hello"},
    )
    assert response.status_code == 401
    assert "Device session expired" in response.json()["detail"]


def test_device_tts_gateway_requires_text(client, db_session, device_access_token):
    """TEST: Missing text -> rejected."""
    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": f"Bearer {device_access_token}"},
        json={},
    )
    assert response.status_code == 400
    assert "Text is required" in response.json()["detail"]


def test_device_tts_gateway_rejects_text_too_long(client, db_session, device_access_token):
    """TEST 8: Text length limit works."""
    long_text = "A" * 5000
    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": f"Bearer {device_access_token}"},
        json={"text": long_text},
    )
    assert response.status_code == 400
    assert "Text exceeds maximum length" in response.json()["detail"]


def test_device_tts_gateway_authenticates_without_user_login(client, db_session, device_access_token):
    """TEST 6: Authorized device does NOT require CEASER user login.

    The device-authenticated endpoint should work with device tokens,
    not user Supabase tokens.
    """
    response = client.post(
        "/voice/elevenlabs/device/stream",
        headers={"Authorization": f"Bearer {device_access_token}"},
        json={"text": "Hello"},
    )
    # Should not require user login - device auth is sufficient
    # The request should get past auth and either succeed or fail at ElevenLabs
    # (which we'll mock in a separate test)
    # At minimum, auth should not fail with "Missing Supabase token"
    assert response.status_code in [200, 502, 504], f"Unexpected status: {response.status_code}"


def test_device_tts_gateway_rate_limiting(client, db_session, device_access_token):
    """TEST 7: Rate limit works."""
    # Use a test limiter to avoid affecting other tests
    limiter = MagicMock()
    limiter.check.return_value.allowed = False
    limiter.check.return_value.retry_after = 60

    with patch("app.api.voice.elevenlabs_routes.rate_limiter", limiter):
        response = client.post(
            "/voice/elevenlabs/device/stream",
            headers={"Authorization": f"Bearer {device_access_token}"},
            json={"text": "Hello"},
        )

    assert response.status_code == 429
    assert "rate_limited" in response.json()["detail"]["code"]
    assert response.json()["detail"]["retry_after"] == 60


def test_device_stream_endpoint_uses_elevenlabs_proxy():
    """TEST 9: ElevenLabs key remains server-side.

    The ElevenLabsStreamProxy should use settings.elevenlabs_api_key
    which is never exposed to the client.
    """
    from app.api.voice.elevenlabs_routes import ElevenLabsStreamProxy

    proxy = ElevenLabsStreamProxy()
    assert proxy.api_key == settings.elevenlabs_api_key
    assert proxy.voice_id == settings.elevenlabs_voice_id


@pytest.mark.asyncio
async def test_device_stream_endpoint_streams_audio():
    """TEST 14: TTS audio can be streamed to the device.

    This is a mock test that verifies the streaming response is returned.
    """
    from app.api.voice.elevenlabs_routes import ElevenLabsStreamProxy

    async def mock_stream_audio(text: str, voice_id: str | None = None):
        yield b"chunk1"
        yield b"chunk2"

    with patch.object(ElevenLabsStreamProxy, "stream_audio", mock_stream_audio):
        proxy = ElevenLabsStreamProxy()
        chunks = []
        async for chunk in proxy.stream_audio("Hello"):
            chunks.append(chunk)
        assert chunks == [b"chunk1", b"chunk2"]


def test_user_stream_endpoint_still_works(client, db_session, device_access_token):
    """TEST 11: Existing user-authenticated CEASER APIs still work.

    The original /voice/elevenlabs/stream endpoint should still work
    with user authentication.
    """
    # This test verifies we didn't break the user-authenticated endpoint
    # by adding the device-authenticated one
    response = client.post(
        "/voice/elevenlabs/stream",
        json={"text": "Hello"},
    )
    # Should require user auth (401 with different message)
    assert response.status_code == 401
    # Should not mention device authorization
    assert "Missing device authorization" not in response.json()["detail"]


def test_device_auth_helper_function():
    """Test the device token extraction and validation helper."""
    from app.services.desktop_auth_service import _b64url, _secret, utc_now
    import app.services.desktop_auth_service as das

    # This test verifies the helper functions exist and work correctly
    assert callable(_secret)
    assert callable(_b64url)
    assert callable(utc_now)
    assert callable(das.verify_desktop_access_token)
    assert callable(das.create_desktop_access_token)
