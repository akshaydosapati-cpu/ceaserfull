from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests


class BackendError(Exception):
    def __init__(self, category: str, message: str, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.retryable = retryable


@dataclass
class BackendResponse:
    data: dict[str, Any]
    latency_ms: int
    cache_status: str = "miss"


class CloudBackendClient:
    """Authenticated CEASER backend client for desktop cloud resources.

    Electron owns refresh-token storage. Python receives a short-lived access
    token and calls backend APIs only; it never reaches into Supabase directly.
    """

    def __init__(
        self,
        base_url: str | None = None,
        access_token: str | None = None,
        timeout: float = 8.0,
        transport: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("CEASER_API_URL") or os.getenv("BACKEND_API_URL") or "https://ceaser-backend-production-ur04.onrender.com").rstrip("/")
        self.access_token = access_token if access_token is not None else os.getenv("CEASER_ACCESS_TOKEN", "")
        self.timeout = timeout
        self.transport = transport or requests.request

    def is_authenticated(self) -> bool:
        return bool(self.access_token and len(str(self.access_token)) > 20)

    def request(self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None, retries: int = 1) -> BackendResponse:
        if not self.is_authenticated():
            raise BackendError("auth_required", "Connect your CEASER account to use cloud resources.", 401, False)
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-CEASER-Client": "desktop",
        }
        started = time.perf_counter()
        attempts = max(1, retries + 1)
        last_error: BackendError | None = None
        for attempt in range(attempts):
            try:
                response = self.transport(method.upper(), url, headers=headers, json=json, params=params, timeout=self.timeout)
                latency = int((time.perf_counter() - started) * 1000)
                status = int(getattr(response, "status_code", 0) or 0)
                if 200 <= status < 300:
                    data = response.json() if hasattr(response, "json") else {}
                    if not isinstance(data, dict):
                        data = {"items": data}
                    return BackendResponse(data=data, latency_ms=latency)
                if status in (401, 403):
                    raise BackendError("revoked" if status == 403 else "auth_required", "Your desktop session expired. Please reconnect CEASER.", status, False)
                if status == 404:
                    raise BackendError("not_found", "That CEASER resource was not found.", status, False)
                if status == 429:
                    raise BackendError("rate_limited", "CEASER cloud is busy. Try again shortly.", status, True)
                if status >= 500:
                    raise BackendError("backend_unavailable", "CEASER cloud is unavailable right now.", status, True)
                raise BackendError("backend_error", "CEASER cloud could not complete that request.", status, False)
            except BackendError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise exc
            except (requests.Timeout, TimeoutError) as exc:
                last_error = BackendError("timeout", "CEASER cloud took too long to respond.", None, True)
                if attempt >= attempts - 1:
                    raise last_error from exc
            except requests.ConnectionError as exc:
                last_error = BackendError("offline", "You appear to be offline. Desktop commands still work.", None, True)
                if attempt >= attempts - 1:
                    raise last_error from exc
            except requests.RequestException as exc:
                last_error = BackendError("network_error", "CEASER cloud could not be reached.", None, True)
                if attempt >= attempts - 1:
                    raise last_error from exc
        raise last_error or BackendError("backend_error", "CEASER cloud request failed.")

    def cloud_resource(self, action: str, payload: dict[str, Any] | None = None) -> BackendResponse:
        return self.request("POST", f"/desktop/cloud/{action}", json=payload or {}, retries=1)
