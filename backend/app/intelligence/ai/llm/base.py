from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx


class LLMProvider(ABC):
    _http_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient]

    @property
    def http_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        clients = getattr(self, "_http_clients", None)
        if clients is None:
            clients = {}
            self._http_clients = clients
        client = clients.get(loop)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                # keepalive_expiry raised from 30s → 120s: providers are singleton objects
                # cached in ModelRouter._providers for the process lifetime; longer keepalive
                # means TCP+TLS connections survive short idle gaps (nights, inter-message pauses)
                # and do not eat into the 4s first-token timeout on reconnect.
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=120.0),
            )
            clients[loop] = client
        return client

    async def aclose(self) -> None:
        clients = getattr(self, "_http_clients", {})
        client = clients.pop(asyncio.get_running_loop(), None)
        if client is not None and not client.is_closed:
            await client.aclose()

    @asynccontextmanager
    async def http_session(self, *, timeout: httpx.Timeout):
        # Timeout remains request-specific while the transport pool is reused.
        yield self.http_client
    @abstractmethod
    async def generate(
        self,
        *,
        instructions: str,
        input_text: str,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_json(
        self,
        *,
        instructions: str,
        input_text: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        *,
        instructions: str,
        input_text: str,
        model: str | None = None,
        max_output_tokens: int | None = None,
        trace: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
