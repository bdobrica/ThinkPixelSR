# ThinkPixelSR Python SDK

Sync and async, typed Python 3.11+ client for the existing gateway's `/search` and
`/store` APIs. Source installation only; this package is not published to PyPI.
An existing operator-provisioned API key is required. Registration is deferred.

From the repository root:

```bash
python3 -m venv clients/python/.venv
clients/python/.venv/bin/python -m pip install ./clients/python
```

Supply `THINKPIXEL_API_KEY` through your process environment or secret manager.
The SDK does not load `.env` files. Alternatively pass `api_key` explicitly;
an explicit value takes precedence, including an empty value (which is rejected).
Configure the actual HTTPS gateway URL; no public origin is assumed.

```python
from thinkpixel_sr import Document, ThinkPixelSRClient, StoreFailedError

with ThinkPixelSRClient(base_url="https://gateway.example.invalid") as client:
    try:
        submission = client.store(
            [
                Document(
                    id=123,
                    text="A lighthouse opens at nine.",
                    language="en",
                    extra={"title": "Opening hours"},
                )
            ]
        )
        # 202 means queue acceptance, including possible partial failures.
        accepted_ids = submission.pending_ids
        failures = submission.failed_items
    except StoreFailedError as error:
        failures = error.result.failed_items  # All publications failed (HTTP 500).

    matches = client.search("When does the lighthouse open?", language="en")
    for match in matches.results:
        document_id, chunk_text, backend_score = match.id, match.text, match.score
```

Search may not see a just-submitted document. Queue acceptance proves neither
completed indexing nor durable delivery. No polling/index-status endpoint exists.
Search preserves order, duplicate document IDs and backend-specific scores.
`to_dict()` exposes the wire data and unknown extensions explicitly; do not log
payloads, error details or extensions containing sensitive information.

`authenticate()` explicitly exchanges the key and returns only `AuthResult.exp`.
Otherwise authentication is lazy: tokens stay in memory and are renewed 30 seconds
before expiry. One protected 401 triggers one exchange/replay; final 401 clears
the cache. No automatic retry on timeout, lost response, 403, 429 or 5xx. The
current gateway returns 500 for invalid keys; that remains `ServerError`.

Errors extend `ThinkPixelSRError`, with `operation`, `http_status` and
`delivery_state`. Store state is `not_sent` for local validation, `rejected` for
400/401/403, `failed` for validated all-failed 500, or `unknown` for ambiguous
failures. A validated result has state `accepted`. Reconcile unknown outcomes
before any explicit resubmission; there is no idempotency guarantee.
`RateLimitError.retry_after_seconds` parses seconds/HTTP dates without sleeping.
Error messages exclude server bodies and credentials. External HTTP logging and
application traceback tools that capture locals can still expose secrets;
disable such logging around authenticated requests.

HTTPS verification is enabled, redirects/retries disabled, and proxy environment
settings ignored by the default transport. Local HTTP requires
`allow_insecure_localhost=True` and literal localhost, 127.0.0.1 or [::1]. A URL
prefix is retained. The client is synchronous and not safe for shared concurrent
use. `close()`/context exit closes owned transports and clears the JWT.

`timeout=15.0` is a shared budget across exchange and protected calls: each HTTP
call gets the remaining budget and late responses are rejected. **HTTPX timeouts
bound individual network phases/inactivity, not a hard wall-clock interruption**;
a continuously streaming peer or DNS resolution may overrun this budget before
control returns. No success or replay occurs after the budget has expired. This
is a documented limitation relative to the Phase 1 deadline target.

For testing, pass a caller-owned adapter implementing the exported `Transport`
protocol (`request` returning `httpx.Response`). It must honor timeout, perform
no retry or redirect, and avoid logging secrets. A configured `httpx.Client` or
HTTPX MockTransport-backed client can be used. The SDK does not close injected
transports; their configuration and lifecycle remain the caller's responsibility.

## Development and versioning

From `clients/python` (the tests use shared repository fixtures):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/python -m build --no-isolation
.venv/bin/bump2version patch
```

bump2version updates the independent SDK version in `pyproject.toml`, the module
and `.bumpversion.cfg`. It creates no commit or tag automatically. Commit the
reviewed changes together. Publishing and package tags require a separate request.
See [changelog](CHANGELOG.md), [wire baseline](../contracts/README.md), and
[offline verification evidence](../../docs/evidence/clients-python/README.md).

## Async client (0.2.0)

`AsyncThinkPixelSRClient` uses HTTPX async I/O; no aiohttp dependency or thread
pool is needed. The synchronous interface remains available unchanged.

```python
import asyncio
import os
from thinkpixel_sr import AsyncThinkPixelSRClient


async def main():
    async with AsyncThinkPixelSRClient(
        base_url=os.environ["THINKPIXEL_BASE_URL"]
    ) as client:
        matches = await client.search("Opening hours", language="en")
        print(matches.to_dict())  # Deliberately exposes retrieved source data.


asyncio.run(main())
```

Await `authenticate`, `search`, `store`, and `aclose`; use `async with` for owned
transport cleanup. A shared client supports concurrent calls on one event loop;
a lock coalesces lazy token exchanges and renewal after a rejected token.
Injected `httpx.AsyncClient` instances remain caller-owned and must disable
redirects/retries and avoid logging secrets. Native `asyncio.CancelledError`
propagates; cancellation during store can leave delivery unknown. Do not replay
it automatically. The shared operation budget includes authentication-lock wait
and uses `asyncio.timeout` to cancel async I/O. A blocking custom transport can
still delay cancellation; late responses are rejected. The SDK itself still
requires an explicit base URL; the [MCP bridge](../../docker/mcp/README.md) reads
both environment variables.
