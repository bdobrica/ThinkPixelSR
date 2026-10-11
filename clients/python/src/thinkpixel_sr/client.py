"""Existing gateway operations with bounded authentication replay."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from .errors import (
    AuthenticationError,
    ConfigurationError,
    HTTPError,
    PermissionError,
    ProtocolError,
    RateLimitError,
    ServerError,
    StoreFailedError,
    ThinkPixelSRError,
    TimeoutError,
    TransportError,
    ValidationError,
)
from .models import (
    AuthResult,
    Document,
    FailedItem,
    SearchHit,
    SearchResult,
    StoreResult,
)


class Transport(Protocol):
    """Caller-owned adapter: honor timeout, disable redirects/retries, never log secrets."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        content: bytes | None,
        timeout: float,
    ) -> httpx.Response: ...


class ThinkPixelSRClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 15.0,
        transport: Transport | None = None,
        allow_insecure_localhost: bool = False,
    ) -> None:
        try:
            url = urlsplit(base_url)
            _ = url.port
            valid = url.scheme == "https" or (
                allow_insecure_localhost
                and url.scheme == "http"
                and url.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            if (
                not valid
                or not url.hostname
                or url.username is not None
                or url.password is not None
                or url.query
                or url.fragment
                or any(c.isspace() or ord(c) < 32 for c in base_url)
                or "\\" in base_url
            ):
                raise ValueError
            key = (
                api_key if api_key is not None else os.environ.get("THINKPIXEL_API_KEY")
            )
            if (
                not isinstance(key, str)
                or not key
                or any(ord(c) < 33 or ord(c) > 126 for c in key)
            ):
                raise ValueError
            if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ConfigurationError("configure") from None
        self._base_url = base_url.rstrip("/")
        self._key = key
        self._timeout = timeout
        self._owned = transport is None
        self._transport: Transport = (
            transport
            if transport is not None
            else httpx.Client(
                verify=True,
                follow_redirects=False,
                trust_env=False,
                transport=httpx.HTTPTransport(retries=0),
            )
        )
        self._token: str | None = None
        self._exp = 0
        self._closed = False

    def close(self) -> None:
        self._token = None
        self._closed = True
        if self._owned and isinstance(self._transport, httpx.Client):
            self._transport.close()

    def __enter__(self) -> ThinkPixelSRClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _send(
        self, operation: str, deadline: float, content: bytes | None
    ) -> httpx.Response:
        remaining = deadline - time.monotonic()
        state = "unknown" if operation == "store" else "not_sent"
        if remaining <= 0:
            raise TimeoutError(operation, delivery_state="not_sent")
        if self._closed:
            raise ConfigurationError("closed")
        headers = {"Accept": "application/json"}
        if operation == "authenticate":
            headers["X-API-Key"] = self._key
            path = "/auth/token"
        else:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["Content-Type"] = "application/json"
            path = "/" + operation
        error: TransportError | None = None
        response: httpx.Response | None = None
        try:
            response = self._transport.request(
                "POST",
                self._base_url + path,
                headers=headers,
                content=content,
                timeout=remaining,
            )
        except httpx.TimeoutException:
            error = TimeoutError(operation, delivery_state=state)
        except Exception:
            error = TransportError(operation, delivery_state=state)
        # Raise outside except so even exception context contains no raw secrets.
        if error is not None:
            raise error
        if time.monotonic() >= deadline:
            raise TimeoutError(operation, delivery_state=state)
        assert response is not None
        return response

    def _json(self, response: httpx.Response, operation: str) -> dict[str, Any]:
        value: Any = None
        try:
            value = json.loads(response.content, parse_constant=lambda _: None)
        except (ValueError, UnicodeError):
            pass
        if not isinstance(value, dict):
            raise ProtocolError(
                operation,
                http_status=response.status_code,
                delivery_state="unknown" if operation == "store" else "not_sent",
            )
        return value

    def _status(self, response: httpx.Response, operation: str, expected: int) -> None:
        status = response.status_code
        if status == expected:
            return
        state = (
            "rejected"
            if operation == "store" and status in {400, 401, 403}
            else ("unknown" if operation == "store" else "not_sent")
        )
        cls: type[ThinkPixelSRError]
        cls = {
            400: ValidationError,
            422: ValidationError,
            401: AuthenticationError,
            403: PermissionError,
            408: TimeoutError,
            429: RateLimitError,
        }.get(status, HTTPError)
        if status >= 500:
            cls = ServerError
        elif 200 <= status < 300:
            cls = ProtocolError
        error = cls(operation, http_status=status, delivery_state=state)
        if isinstance(error, RateLimitError):
            raw = response.headers.get("Retry-After", "")
            try:
                error.retry_after_seconds = (
                    float(int(raw))
                    if re.fullmatch(r"[0-9]+", raw)
                    else max(0.0, parsedate_to_datetime(raw).timestamp() - time.time())
                )
            except (ValueError, TypeError, OverflowError):
                pass
        raise error

    def _authenticate(self, deadline: float) -> AuthResult:
        self._token = None
        self._exp = 0
        response = self._send("authenticate", deadline, None)
        self._status(response, "authenticate", 200)
        data = self._json(response, "authenticate")
        token, exp = data.get("token"), data.get("exp")
        if (
            not isinstance(token, str)
            or not token
            or any(ord(c) < 33 or ord(c) > 126 for c in token)
            or type(exp) is not int
            or exp <= time.time() + 30
        ):
            raise ProtocolError("authenticate", http_status=200)
        self._token, self._exp = token, exp
        return AuthResult(exp)

    def authenticate(self) -> AuthResult:
        return self._authenticate(time.monotonic() + self._timeout)

    def _request(self, operation: str, payload: object) -> httpx.Response:
        deadline = time.monotonic() + self._timeout
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
        if self._token is None or time.time() >= self._exp - 30:
            self._authenticate(deadline)
        response = self._send(operation, deadline, content)
        if response.status_code == 401:
            self._token = None
            self._authenticate(deadline)
            response = self._send(operation, deadline, content)
            if response.status_code == 401:
                self._token = None
        return response

    def _store_payload(self, documents: Sequence[Document]) -> list[dict[str, Any]]:
        if (
            not isinstance(documents, Sequence)
            or isinstance(documents, (str, bytes))
            or not documents
        ):
            raise ValidationError("store")
        payload: list[dict[str, Any]] = []
        for doc in documents:
            if (
                not isinstance(doc, Document)
                or type(doc.id) is not int
                or not -(2**31) <= doc.id < 2**31
                or not isinstance(doc.text, str)
                or (doc.language is not None and not isinstance(doc.language, str))
                or (
                    doc.extra is not None
                    and (
                        not hasattr(doc.extra, "items")
                        or any(
                            not isinstance(k, str) or not isinstance(v, str)
                            for k, v in doc.extra.items()
                        )
                    )
                )
            ):
                raise ValidationError("store")
            item: dict[str, Any] = {"id": doc.id, "text": doc.text}
            if doc.language is not None:
                item["language"] = doc.language
            if doc.extra is not None:
                item["extra"] = dict(doc.extra)
            payload.append(item)
        return payload

    def store(self, documents: Sequence[Document]) -> StoreResult:
        response = self._request("store", self._store_payload(documents))
        return self._parse_store(response)

    def _parse_store(self, response: httpx.Response) -> StoreResult:
        if response.status_code == 500:
            result: StoreResult | None = None
            try:
                result = self._store_result(response)
            except ProtocolError:
                pass
            if result is not None:
                raise StoreFailedError(result)
        self._status(response, "store", 202)
        return self._store_result(response)

    def _store_result(self, response: httpx.Response) -> StoreResult:
        data = self._json(response, "store")
        result: StoreResult | None = None
        try:
            counts = [
                data[k]
                for k in ("received_texts", "pending_documents", "failed_documents")
            ]
            if (
                any(type(n) is not int or n < 0 for n in counts)
                or counts[0] != counts[1] + counts[2]
            ):
                raise ValueError
            if (
                counts[0] == 0
                or (response.status_code == 202 and counts[1] == 0)
                or (response.status_code == 500 and counts[1] != 0)
            ):
                raise ValueError
            stamp = data["timestamp"]
            if not isinstance(stamp, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
                stamp,
            ):
                raise ValueError
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            ids = data.get("pending_ids")
            failed = data.get("failed_items")
            if "pending_ids" in data and (
                not isinstance(ids, list)
                or len(ids) != counts[1]
                or any(type(i) is not int for i in ids)
            ):
                raise ValueError
            if "failed_items" in data and (
                not isinstance(failed, list) or len(failed) != counts[2]
            ):
                raise ValueError
            failures: list[FailedItem] = []
            for item in failed or []:
                if type(item["id"]) is not int or not isinstance(item["error"], str):
                    raise ValueError
                failures.append(
                    FailedItem(
                        item["id"],
                        item["error"],
                        {k: v for k, v in item.items() if k not in {"id", "error"}},
                    )
                )
            result = StoreResult(
                counts[0],
                counts[1],
                counts[2],
                timestamp=stamp,
                http_status=response.status_code,
                pending_ids=None if ids is None else tuple(ids),
                failed_items=None if failed is None else tuple(failures),
                extensions={
                    k: v
                    for k, v in data.items()
                    if k
                    not in {
                        "received_texts",
                        "pending_documents",
                        "failed_documents",
                        "timestamp",
                        "pending_ids",
                        "failed_items",
                    }
                },
            )
        except (ValueError, KeyError, TypeError):
            pass
        if result is None:
            raise ProtocolError(
                "store", http_status=response.status_code, delivery_state="unknown"
            )
        return result

    def search(self, text: str, *, language: str = "auto") -> SearchResult:
        if not isinstance(text, str) or not text or not isinstance(language, str):
            raise ValidationError("search")
        response = self._request("search", {"text": text, "language": language})
        self._status(response, "search", 200)
        return self._parse_search(response)

    def _parse_search(self, response: httpx.Response) -> SearchResult:
        data = self._json(response, "search")
        hits: list[SearchHit] = []
        valid = False
        try:
            if not isinstance(data["results"], list):
                raise ValueError
            for hit in data["results"]:
                if (
                    type(hit["id"]) is not int
                    or not isinstance(hit["text"], str)
                    or type(hit["score"]) not in (int, float)
                    or not math.isfinite(hit["score"])
                ):
                    raise ValueError
                hits.append(
                    SearchHit(
                        hit["id"],
                        hit["text"],
                        float(hit["score"]),
                        {
                            k: v
                            for k, v in hit.items()
                            if k not in {"id", "text", "score"}
                        },
                    )
                )
            valid = True
        except (ValueError, KeyError, TypeError, OverflowError):
            pass
        if not valid:
            raise ProtocolError("search", http_status=200)
        return SearchResult(
            tuple(hits), {k: v for k, v in data.items() if k != "results"}
        )
