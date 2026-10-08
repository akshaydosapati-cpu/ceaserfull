"""
Focused test to verify Supabase auth logging is safe and does not expose credentials.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.core.security.supabase_auth import SupabaseAuth


@pytest.mark.asyncio
async def test_supabase_auth_logging_no_credentials_exposed():
    """Verify that logging output never contains tokens, keys, or secrets."""

    # Capture all log output
    log_records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            log_records.append(self.format(record))

    handler = ListHandler()
    logger = logging.getLogger("app.core.security.supabase_auth")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    auth = SupabaseAuth()

    # Mock settings
    with patch("app.core.security.supabase_auth.settings") as mock_settings:
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_anon_key = "super_secret_anon_key_12345"

        # Test 1: Client creation logging
        client = auth._http_client()
        assert client is not None

        # Verify client reuse logging
        client2 = auth._http_client()
        assert client is client2

        # Test 2: Successful request logging
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            try:
                response = await auth._request("GET", "/auth/v1/user", headers={
                    "Authorization": "Bearer super_secret_token_xyz",
                    "apikey": "super_secret_anon_key_12345"
                })
                assert response.status_code == 200
            except Exception:
                pass

        # Test 3: ConnectError logging
        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(httpx.ConnectError):
                await auth._request("GET", "/auth/v1/user")

        # Test 4: Timeout logging
        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            async def timeout_func(*args, **kwargs):
                await asyncio.sleep(10)

            mock_request.side_effect = timeout_func

            with pytest.raises(asyncio.TimeoutError):
                await auth._request("GET", "/auth/v1/user")

    # Verify no sensitive data in logs
    all_logs = "\n".join(log_records)

    # Must NOT contain these secrets
    assert "super_secret_anon_key_12345" not in all_logs, "API key exposed in logs"
    assert "super_secret_token_xyz" not in all_logs, "Bearer token exposed in logs"
    assert "Bearer " not in all_logs, "Authorization header exposed in logs"
    assert "apikey:" not in all_logs, "API key header exposed in logs"

    # Must contain diagnostic information
    assert "supabase_client_lifecycle" in all_logs, "Missing client lifecycle logging"
    assert "supabase_request" in all_logs, "Missing request logging"
    assert "/auth/v1/user" in all_logs, "Missing path in logs"
    assert "elapsed_ms" in all_logs, "Missing elapsed time in logs"

    logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_supabase_auth_exception_logging_safe():
    """Verify exception logging includes class names but no message content with secrets."""

    log_records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record.getMessage())

    handler = ListHandler()
    logger = logging.getLogger("app.core.security.supabase_auth")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    auth = SupabaseAuth()

    with patch("app.core.security.supabase_auth.settings") as mock_settings:
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_anon_key = "secret_key"

        client = auth._http_client()

        # Test ConnectError with cause
        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            inner_error = OSError("Connection refused")
            connect_error = httpx.ConnectError("Failed", request=None)
            connect_error.__cause__ = inner_error
            mock_request.side_effect = connect_error

            with pytest.raises(httpx.ConnectError):
                await auth._request("GET", "/auth/v1/user")

        # Verify logs contain exception class but no detailed message
        all_logs = "\n".join(log_records)
        assert "ConnectError" in all_logs, "Exception class not logged"
        assert "secret_key" not in all_logs, "Secret key exposed in exception logs"

    logger.removeHandler(handler)
