"""Async HTTPX client; wire validation is shared with the synchronous SDK."""

from __future__ import annotations

import asyncio
import builtins
import json
import time
from collections.abc import Sequence

import httpx

from .client import ThinkPixelSRClient
from .errors import (
    ConfigurationError,
    ProtocolError,
    TimeoutError,
    TransportError,
    ValidationError,
)
from .models import AuthResult, Document, SearchResult, StoreResult


class _CodecTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        content: bytes | None,
        timeout: float,
    ) -> httpx.Response:
        raise AssertionError("Async codec must never perform synchronous I/O")


class AsyncThinkPixelSRClient:
    """Share within one event loop. Injected HTTPX clients remain caller-owned."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 15.0,
        transport: httpx.AsyncClient | None = None,
        allow_insecure_localhost: bool = False,
    ) -> None:
        # This adapter is used only for configuration and pure response decoding.
        self._codec = ThinkPixelSRClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            transport=_CodecTransport(),
            allow_insecure_localhost=allow_insecure_localhost,
        )
        self._transport = transport or httpx.AsyncClient(
            verify=True,
            follow_redirects=False,
            trust_env=False,
            transport=httpx.AsyncHTTPTransport(retries=0),
        )
        self._owned = transport is None
        self._auth_lock = asyncio.Lock()

    async def aclose(self) -> None:
        self._codec.close()
        if self._owned:
            await self._transport.aclose()

    async def __aenter__(self) -> AsyncThinkPixelSRClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _send(
        self, operation: str, deadline: float, content: bytes | None
    ) -> httpx.Response:
        remaining = deadline - time.monotonic()
        if self._codec._closed:
            raise ConfigurationError("closed")
        if remaining <= 0:
            raise TimeoutError(operation)
        headers = {"Accept": "application/json"}
        path = "/" + operation
        if operation == "authenticate":
            headers["X-API-Key"] = self._codec._key
            path = "/auth/token"
        else:
            headers["Authorization"] = f"Bearer {self._codec._token}"
            headers["Content-Type"] = "application/json"
        error: TransportError | None = None
        response: httpx.Response | None = None
        try:
            async with asyncio.timeout(remaining):
                response = await self._transport.request(
                    "POST",
                    self._codec._base_url + path,
                    headers=headers,
                    content=content,
                    timeout=remaining,
                )
        except (httpx.TimeoutException, builtins.TimeoutError):
            error = TimeoutError(
                operation,
                delivery_state="unknown" if operation == "store" else "not_sent",
            )
        except Exception:
            error = TransportError(
                operation,
                delivery_state="unknown" if operation == "store" else "not_sent",
            )
        if error is not None:
            raise error
        if time.monotonic() >= deadline:
            raise TimeoutError(
                operation,
                delivery_state="unknown" if operation == "store" else "not_sent",
            )
        assert response is not None
        return response

    async def _authenticate(self, deadline: float) -> AuthResult:
        self._codec._token = None
        self._codec._exp = 0
        response = await self._send("authenticate", deadline, None)
        self._codec._status(response, "authenticate", 200)
        data = self._codec._json(response, "authenticate")
        token, exp = data.get("token"), data.get("exp")
        if (
            not isinstance(token, str)
            or not token
            or any(ord(c) < 33 or ord(c) > 126 for c in token)
            or type(exp) is not int
            or exp <= time.time() + 30
        ):
            raise ProtocolError("authenticate", http_status=200)
        self._codec._token, self._codec._exp = token, exp
        return AuthResult(exp)

    async def _ensure_token(
        self, deadline: float, rejected: str | None = None, *, force: bool = False
    ) -> None:
        error = False
        try:
            async with asyncio.timeout(max(0, deadline - time.monotonic())):
                async with self._auth_lock:
                    if (
                        force
                        or self._codec._token is None
                        or time.time() >= self._codec._exp - 30
                        or (rejected is not None and self._codec._token == rejected)
                    ):
                        await self._authenticate(deadline)
        except builtins.TimeoutError:
            error = True
        if error:
            raise TimeoutError("authenticate")

    async def authenticate(self) -> AuthResult:
        deadline = time.monotonic() + self._codec._timeout
        await self._ensure_token(deadline, force=True)
        return AuthResult(self._codec._exp)

    async def _request(self, operation: str, payload: object) -> httpx.Response:
        deadline = time.monotonic() + self._codec._timeout
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
        await self._ensure_token(deadline)
        token = self._codec._token
        response = await self._send(operation, deadline, content)
        if response.status_code == 401:
            await self._ensure_token(deadline, rejected=token)
            replay_token = self._codec._token
            response = await self._send(operation, deadline, content)
            if response.status_code == 401 and self._codec._token == replay_token:
                self._codec._token = None
        return response

    async def store(self, documents: Sequence[Document]) -> StoreResult:
        payload = self._codec._store_payload(documents)
        return self._codec._parse_store(await self._request("store", payload))

    async def search(self, text: str, *, language: str = "auto") -> SearchResult:
        if not isinstance(text, str) or not text or not isinstance(language, str):
            raise ValidationError("search")
        response = await self._request("search", {"text": text, "language": language})
        self._codec._status(response, "search", 200)
        return self._codec._parse_search(response)
