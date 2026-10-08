import asyncio
import httpx
import logging
from time import perf_counter
from urllib.parse import urlencode

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class SupabaseAuth:
    _timeout = httpx.Timeout(6.0, connect=3.0, pool=2.0)
    _request_deadline_seconds = 7.0

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                trust_env=False,
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=30.0),
            )
            logger.debug("supabase_client_lifecycle created=true")
        else:
            logger.debug("supabase_client_lifecycle created=false reused=true")
        return self._client

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        start_time = perf_counter()
        try:
            async with asyncio.timeout(self._request_deadline_seconds):
                response = await self._http_client().request(method, f"{self.supabase_url}{path}", **kwargs)
            elapsed_ms = (perf_counter() - start_time) * 1000
            logger.debug("supabase_request_complete path=%s elapsed_ms=%.1f status=%s", path, elapsed_ms, response.status_code)
            return response
        except asyncio.TimeoutError as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            logger.warning("supabase_request_timeout path=%s elapsed_ms=%.1f exception_class=%s", path, elapsed_ms, type(e).__name__)
            raise
        except httpx.ConnectError as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            exc_cause_class = type(e.__cause__).__name__ if e.__cause__ else "none"
            logger.warning("supabase_request_connect_error path=%s elapsed_ms=%.1f exception_class=%s cause=%s", path, elapsed_ms, type(e).__name__, exc_cause_class)
            raise
        except httpx.PoolTimeout as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            logger.warning("supabase_request_pool_timeout path=%s elapsed_ms=%.1f exception_class=%s", path, elapsed_ms, type(e).__name__)
            raise
        except httpx.ReadTimeout as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            logger.warning("supabase_request_read_timeout path=%s elapsed_ms=%.1f exception_class=%s", path, elapsed_ms, type(e).__name__)
            raise
        except httpx.RequestError as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            exc_cause_class = type(e.__cause__).__name__ if e.__cause__ else "none"
            logger.warning("supabase_request_error path=%s elapsed_ms=%.1f exception_class=%s cause=%s", path, elapsed_ms, type(e).__name__, exc_cause_class)
            raise
        except Exception as e:
            elapsed_ms = (perf_counter() - start_time) * 1000
            exc_cause_class = type(e.__cause__).__name__ if e.__cause__ else "none"
            logger.warning("supabase_request_exception path=%s elapsed_ms=%.1f exception_class=%s cause=%s", path, elapsed_ms, type(e).__name__, exc_cause_class)
            raise

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
    @property
    def supabase_url(self) -> str | None:
        return settings.supabase_url

    @property
    def anon_key(self) -> str | None:
        return settings.supabase_anon_key

    @property
    def configured(self) -> bool:
        return bool(self.supabase_url and self.anon_key)

    async def signup(self, email: str, password: str) -> dict:
        payload: dict = {"email": email, "password": password}
        redirect_to = self._email_redirect_to()
        if redirect_to:
            payload["options"] = {"emailRedirectTo": redirect_to}
        return await self._post("/auth/v1/signup", payload)

    async def login(self, email: str, password: str) -> dict:
        return await self._post("/auth/v1/token?grant_type=password", {"email": email, "password": password})

    async def refresh_session(self, refresh_token: str) -> dict:
        return await self._post("/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token})

    async def recover_password(self, email: str, redirect_to: str | None = None) -> dict:
        path = "/auth/v1/recover"
        redirect_target = redirect_to or self._email_redirect_to()
        if redirect_target:
            path = f"{path}?{urlencode({'redirect_to': redirect_target})}"
        return await self._post(path, {"email": email})

    async def update_password(self, access_token: str, password: str) -> dict:
        return await self._put("/auth/v1/user", {"password": password}, access_token=access_token)

    async def resend_verification(self, email: str, verification_type: str = "signup") -> dict:
        payload: dict = {"type": verification_type, "email": email}
        redirect_to = self._email_redirect_to()
        if redirect_to:
            payload["options"] = {"emailRedirectTo": redirect_to}
        return await self._post("/auth/v1/resend", payload)

    def _email_redirect_to(self) -> str | None:
        base = (settings.frontend_app_url or "").strip()
        if not base:
            return None
        base = base.rstrip("/")
        if not base.endswith("/console"):
            base = f"{base}/console"
        return f"{base}/auth/verified/"

    async def enroll_totp(self, access_token: str, friendly_name: str) -> dict:
        return await self._post(
            "/auth/v1/factors",
            {"factor_type": "totp", "friendly_name": friendly_name},
            access_token=access_token,
        )

    async def list_factors(self, access_token: str) -> dict:
        return await self._get("/auth/v1/factors", access_token=access_token)

    async def challenge_factor(self, access_token: str, factor_id: str) -> dict:
        return await self._post(f"/auth/v1/factors/{factor_id}/challenge", {}, access_token=access_token)

    async def verify_factor(self, access_token: str, factor_id: str, challenge_id: str, code: str) -> dict:
        return await self._post(
            f"/auth/v1/factors/{factor_id}/verify",
            {"challenge_id": challenge_id, "code": code},
            access_token=access_token,
        )

    async def unenroll_factor(self, access_token: str, factor_id: str) -> dict:
        return await self._delete(f"/auth/v1/factors/{factor_id}", access_token=access_token)

    async def get_user(self, access_token: str) -> dict:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured")
        response = await self._request(
            "GET",
            "/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": self.anon_key or "",
            },
        )
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, payload: dict, access_token: str | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured")
        response = await self._request("POST", path, json=payload, headers=self._headers(access_token))
        response.raise_for_status()
        return response.json()

    async def _put(self, path: str, payload: dict, access_token: str | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured")
        response = await self._request("PUT", path, json=payload, headers=self._headers(access_token))
        response.raise_for_status()
        return response.json()

    async def _get(self, path: str, access_token: str | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured")
        response = await self._request("GET", path, headers=self._headers(access_token))
        response.raise_for_status()
        return response.json()

    async def _delete(self, path: str, access_token: str | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured")
        response = await self._request("DELETE", path, headers=self._headers(access_token))
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"apikey": self.anon_key or ""}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers


supabase_auth = SupabaseAuth()
