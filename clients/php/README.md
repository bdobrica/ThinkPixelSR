# ThinkPixelSR PHP SDK

Unpublished **0.1.0**, implementing the gateway's existing-key `authenticate`,
`store` and `search` operations (CL-038–CL-039, CL-041–CL-042). Registration is
unavailable and deferred. The API Gateway is authoritative; this package does
not replace or modify ThinkPixelPlugin.

Requires **64-bit PHP 8.3+**, JSON and cURL extensions, Composer 2, and an existing
API key. PHP 8.4 was tested; PHP 8.3 remains an unverified minimum target.
Synchronous server-side use only; do not share a client concurrently between
fibers or threads. No browser credential support or asynchronous cancellation.
See [verification evidence](../../docs/evidence/clients-php/README.md).

## Install from this repository

`thinkpixel/sr` is a provisional Composer name, not a published Packagist package.
From the repository root:

```bash
cd clients/php
composer install
composer validate --strict
composer lint
composer analyse
composer test
composer archive --format=tar --dir=dist --file=thinkpixel-sr-0.1.0
```

Development dependencies are locked for reproducible checks. An application can
use a Composer path repository pointing to its local checkout. In the application's
`composer.json`, merge these entries with its existing configuration:

```json
{
  "repositories": [{"type": "path", "url": "/absolute/path/ThinkPixelSR/clients/php", "options": {"symlink": false, "versions": {"thinkpixel/sr": "0.1.0"}}}],
  "require": {"thinkpixel/sr": "0.1.0"}
}
```

Run `composer install`, then load the application's `vendor/autoload.php`.
The SDK's development dependencies are not installed in consumer applications.
The archive contains source, metadata, README, changelog and Apache-2.0 license;
no vendor directory, tests, examples or local credentials. No publication is
performed by these commands.

## Credentials and usage

Supply `THINKPIXEL_API_KEY` through your process's secret manager/environment.
An explicit `api_key` option takes precedence. Omission reads the environment;
explicit empty or null keys fail. No `.env` loader or key-provisioning procedure
is included. Never store keys in source, URLs, browser code or logs.

```php
<?php
declare(strict_types=1);
require __DIR__ . '/vendor/autoload.php';

use ThinkPixel\SR\Document;
use ThinkPixel\SR\ThinkPixelSRClient;
use ThinkPixel\SR\Exception\StoreFailedError;
use ThinkPixel\SR\Exception\ThinkPixelSRError;

$client = new ThinkPixelSRClient([
    'base_url' => 'https://gateway.example',
    'timeout' => 15.0,
    // api_key omitted: THINKPIXEL_API_KEY from process environment
]);
try {
    $outcome = $client->store([
        new Document(42, 'Example document', language: 'en', extra: ['kind' => 'guide']),
    ]);
    echo $outcome->pending_documents . " documents accepted for enqueueing\n";
    // Partial 202 outcomes can also contain failed_documents and failed_items.
    // Search is independent: acceptance does not mean the new document is indexed.
    $result = $client->search('Example question', language: 'en');
    echo count($result->results) . " results\n";
} catch (StoreFailedError $error) {
    $failed = $error->getResult();
    echo $failed->failed_documents . " documents failed to enqueue\n";
} catch (ThinkPixelSRError $error) {
    // Fixed diagnostic message, operation, http_status and delivery_state only.
    error_log($error->getMessage());
} finally {
    $client->close();
}
```

`examples/search.php` reads `THINKPIXEL_BASE_URL` and the environment key. It is
a live application example; unit tests never require gateway credentials.

For optional WordPress-adjacent use, load the application's Composer autoloader
on the server and call the same API from a trusted backend task. Inject its key
from the hosting environment or a private secret store. Do not expose it in
HTML, JavaScript, options exports or public callbacks. This SDK neither hooks
WordPress nor changes the plugin's callback registration or indexing workflow.

## Wire behavior and results

Construction does no I/O. `authenticate(): AuthResult` explicitly exchanges the
key; only `exp` is returned. Protected operations authenticate lazily. The JWT
stays in memory, reused until 30 seconds before expiry. Renewal repeats the
existing `POST /auth/token`, with `X-API-Key` and no body. Explicit authentication
invalidates the previous cache even if the new exchange fails.

A protected HTTP 401 invalidates the token, exchanges again and replays the same
serialized payload once. A final 401 clears the cache and raises
`AuthenticationError`. No other transport or status retries occur, including
search, exchange, timeout, 429 or 5xx. There is no idempotency guarantee.

`store(array $documents): StoreResult` accepts a nonempty list of `Document`
objects. IDs must be signed int32 integers; text is required but may be empty;
language is optional; extra is a string-key/string-value map. Empty extra maps
encode as JSON objects. Native strict PHP types govern scalar arguments; use
`declare(strict_types=1)` in callers to prevent scalar coercion. Invalid types
may raise native `TypeError`; invalid values raise `ValidationError` locally.
Unknown constructor options are rejected. No arbitrary document fields,
filters, pagination, model selection or extra endpoint wrappers are supported.

`search(string $text, string $language = 'auto'): SearchResult` requires nonempty
text. Results retain order, duplicate IDs, backend scores and unknown fields in
`extensions`. Response IDs must be actual PHP integers; oversized JSON integers
are rejected rather than rounded. Value objects use readonly properties;
unknown nested JSON objects are untrusted and not deeply immutable.

Store results retain the gateway's snake_case counts, timestamp and optional
`pending_ids`/`failed_items`, plus SDK `http_status` and `delivery_state`. An absent
optional list remains null. Explicit `toArray()` reconstructs wire fields and
unknown extensions, omitting absent fields and SDK-only status/delivery markers.
Search/failed-item `toArray()` behaves similarly. Use this only when deliberately
accessing payloads; document text, failure prose and extensions may be sensitive.

202 means accepted for queue publication, including partial failures. It proves
neither indexing, search visibility nor durable delivery (the baseline uses Core
NATS). A valid all-failed 500 raises `StoreFailedError` with `getResult()`;
other 500s raise `ServerError`, preserving the gateway's invalid-key 500 behavior.
A malformed 202 raises `ProtocolError` with unknown delivery; never blindly resend.
There is no SDK indexing wait loop or store-status API.

## Errors, transport and deadlines

Exceptions under `ThinkPixel\SR\Exception` share `ThinkPixelSRError`:

| Failure | Class |
| --- | --- |
| Local configuration / values | `ConfigurationError` / `ValidationError` |
| 400/422, final 401, 403 | `ValidationError`, `AuthenticationError`, `PermissionError` |
| 408 or operation timeout | `TimeoutError` |
| 429 | `RateLimitError` with nullable `retry_after_seconds` |
| Other 5xx, validated all-failed store | `ServerError`, `StoreFailedError` |
| Network/TLS/I/O failure | `TransportError` |
| Bad success JSON/schema or unexpected 2xx | `ProtocolError` |
| Other status, including redirect | `HTTPError` |

`CancelledError` is exported for vocabulary parity, with no synchronous
cancellation API. Retry-After parses nonnegative integer seconds or an IMF HTTP
date; past dates become zero. No automatic sleeping/resubmission occurs.
Store error delivery is `not_sent` for local/pre-dispatch failures, `rejected`
for gateway 400/401/403, `failed` for validated all-failed 500, and `unknown` for
other failures after dispatch. Investigate unknown outcomes before resubmitting.

The default Guzzle adapter uses a fixed cURL handler without retry/redirect
middleware, verifies certificates/hostnames and fully buffers responses. Each
request receives the remaining monotonic operation budget, shared across auth,
operation and one possible renewal/replay. Late responses are rejected. A minimum
1 ms remaining budget is required before dispatch; configured timeout is finite,
positive and at most 2147483.647 seconds. cURL/DNS platform behavior still controls
blocking resolution; no hard interruption guarantee is made for arbitrary PHP
extensions or custom adapters/factories. There is no insecure TLS option.

The URL requires HTTPS, permits a path prefix, and forbids credentials, queries,
fragments, whitespace and backslashes. Explicit `allow_insecure_localhost => true`
permits HTTP only on literal `localhost`, `127.0.0.1` or `[::1]` for local testing.
Do not disable certificate validation in deployment.

Inject `transport => DeadlineTransport` for mocking or a caller-owned adapter.
It accepts a PSR-7 request and remaining seconds and returns a fully buffered
PSR-7 response. It must enforce TLS, timeout, no retries/redirects/logging; its
behavior cannot be inspected or forcibly interrupted by the SDK. PSR-18 by
itself has no deadline control and is insufficient. Optional PSR-17
`request_factory` and `stream_factory` must implement their respective interfaces.
`close()` is idempotent, invalidates the client and releases the SDK-owned
Guzzle client; it never closes caller-owned adapters.

Client/result/error `var_dump`, `print_r`, JSON diagnostics and native serialization
hide credentials and payloads. Exceptions have fixed messages and no chained raw
transport cause. Sensitive parameters redact SDK trace arguments. Objects are
not a persistence format: reconstruct clients and use explicit `toArray()` for
payload access. Deliberate introspection such as `var_export`, reflection or raw
third-party adapter traces can expose private state; avoid them in logs. Configure
PHP `zend.exception_ignore_args=On` for application-level trace safety.

## Development and versioning

```bash
composer install
composer validate --strict
composer lint
composer analyse                  # PHPStan level 8, source and example
composer test                     # PHPUnit; synthetic loopback binding required
composer archive --format=tar --dir=dist --file=thinkpixel-sr-0.1.0
```

Tests consume the existing shared fixtures and mocked failure scenarios. The
loopback tests verify real cURL timeout/no-redirect behavior, with no live gateway.
PHPStan validates types; runtime validation deliberately treats PHPDoc types as
uncertain because PHP does not enforce array element types.

Use an isolated Python environment with bump2version installed:

```bash
# Run inside clients/php with your bump2version executable on PATH.
bump2version patch
composer validate --strict
composer test
```

The bump configuration updates itself, the `composer.json` SDK version metadata,
`ThinkPixelSRClient::VERSION` and this guide;
commit/tag/publish are separate. Composer's dependency lock has no root version;
version bumps do not alter dependency resolution. Composer normally derives package
versions from release tags; the local path example explicitly assigns 0.1.0 until
release tags exist. The manifest has no top-level version field. SDK versions are independent
of Python/TypeScript and the frozen gateway baseline. Package ownership and
publication, minimum-runtime verification and live store→eventual-search
acceptance remain open.
