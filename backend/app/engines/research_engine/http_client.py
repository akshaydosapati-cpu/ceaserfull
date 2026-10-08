from __future__ import annotations

import atexit
import threading

import httpx


_lock = threading.Lock()
_client: httpx.Client | None = None


def research_http_client() -> httpx.Client:
    global _client
    client = _client
    if client is not None and not client.is_closed:
        return client
    with _lock:
        client = _client
        if client is None or client.is_closed:
            client = httpx.Client(
                follow_redirects=True,
                trust_env=False,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
                headers={"User-Agent": "CEASER Research/1.0"},
            )
            _client = client
        return client


def close_research_http_client() -> None:
    global _client
    with _lock:
        client, _client = _client, None
    if client is not None and not client.is_closed:
        client.close()


atexit.register(close_research_http_client)
