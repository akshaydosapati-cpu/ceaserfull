from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx


class LLMProvider(ABC):
    _http_client: httpx.AsyncClient | None = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        client = getattr(self, "_http_client", None)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0),
            )
            self._http_client = client
        return client

    async def aclose(self) -> None:
        client = getattr(self, "_http_client", None)
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
    ) -> AsyncIterator[str]:
        raise NotImplementedError
