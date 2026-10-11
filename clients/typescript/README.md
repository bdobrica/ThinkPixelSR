# ThinkPixelSR TypeScript SDK

Existing-key Node.js client for the gateway's `/auth/token`, `/store` and `/search`.
ESM only, Node.js 22+, no runtime dependencies. Version 0.1.0 is unpublished;
`@thinkpixel/sr` is a provisional npm name, with ownership not yet verified.
Registration stays deferred. The [gateway baseline](../contracts/README.md)
is authoritative; no server or ThinkPixelPlugin changes are required.

## Install from this repository

From the repository root, with Node.js 22+ and npm available:

```sh
cd clients/typescript
npm ci
npm run build
npm pack
```

In your Node application, install the generated archive using its actual path:

```sh
npm install /absolute/path/to/ThinkPixelSR/clients/typescript/thinkpixel-sr-0.1.0.tgz
```

Use ESM (`"type": "module"` in your application package.json, or `.mjs`).
Declarations are included for TypeScript. CommonJS and browser bundles are outside
initial support. Never ship a persistent privileged API key to a browser. A browser
application needs a trusted backend; this SDK makes no CORS or gateway changes.

## Existing key and usage

Supply `THINKPIXEL_API_KEY` through your application's secret manager or process
environment. An explicit `apiKey` overrides the environment; an explicitly empty
key is rejected. The SDK does not read `.env` files. Supply your gateway origin
explicitly; the SDK has no default server URL.

```ts
import { ThinkPixelSRClient, StoreFailedError, ThinkPixelSRError } from "@thinkpixel/sr";

const baseUrl = process.env.THINKPIXEL_BASE_URL;
if (!baseUrl) throw new Error("THINKPIXEL_BASE_URL is required");
const client = new ThinkPixelSRClient({ baseUrl, timeoutMs: 15000 });

try {
  const outcome = await client.store([
    { id: 900001, text: "A synthetic application document", language: "en", extra: { source: "example" } },
  ]);
  console.log("Queued:", outcome.pending_documents, "Failed:", outcome.failed_documents);
  // A 202 can contain failed_items. Acceptance does not prove indexing or durability.
  // Allow for indexing delay before searching; this example does not wait for indexing.
  const result = await client.search("synthetic document", { language: "en" });
  console.log("Search hits:", result.results.length);
} catch (error) {
  if (error instanceof StoreFailedError) {
    console.error("All queue publications failed:", error.result.failed_documents);
  } else if (error instanceof ThinkPixelSRError) {
    console.error(error.name, error.http_status, error.delivery_state);
  } else {
    throw error;
  }
}
```

`authenticate({ signal? })` forces an exchange, returning only `{ exp }` in Unix
seconds. `store(documents, { signal? })` always takes a nonempty array; IDs must
be signed int32 integers. `search(text, { language?, signal? })` requires nonempty
text and defaults language to `auto`. Unsupported fields/options are rejected.
Optional document `language` and string-map `extra` are omitted when absent.
There are no filters, pagination, embeddings, registration or rotation methods.

Results use readonly interfaces and frozen outer objects/arrays. Unknown response
fields live in `extensions` at each object level; nested metadata is not deeply
frozen. JSON serialization explicitly restores wire fields and unknown metadata,
excluding SDK `http_status`/`delivery_state`. Search order, scores and duplicate
IDs remain unchanged. Scores depend on the backend; Redis is not Qdrant hybrid
search. Unsafe integer IDs are rejected. Omitted optional arrays stay absent.
Node inspection of clients, errors and result records hides credentials/payloads;
explicit result serialization and individual fields can contain sensitive data.
Avoid logging them or third-party HTTP traces.

## Authentication, errors and delivery

JWTs stay in memory, are reused until 30 seconds before expiry and are never
returned through `AuthResult`. Concurrent calls share a token exchange. Each
caller retains its own timeout and AbortSignal; cancelling one caller does not
cancel exchange for other waiting callers. When all waiters leave, exchange is
aborted. Concurrent explicit authentication also coalesces an in-flight exchange.

An actual protected HTTP 401 permits one exchange and one replay of the same
serialized payload, relying on gateway middleware rejecting before publication.
A second 401 clears that token and raises `AuthenticationError`. No other
transport/status error is retried, and redirects are never followed. No refresh
endpoint, on-disk cache, automatic key rotation, backoff or idempotency is implied.

Exported errors include `ConfigurationError`, `ValidationError`,
`AuthenticationError`, `PermissionError`, `RateLimitError`, `TransportError`,
`TimeoutError`, `CancelledError`, `ProtocolError`, `HTTPError`, `ServerError`
and `StoreFailedError`, all extending `ThinkPixelSRError`. Errors expose operation,
optional `http_status` and `delivery_state`, using fixed messages without raw
URLs, headers, bodies, transport exceptions or exception causes. The gateway's
invalid-key 500 remains `ServerError`. `RateLimitError.retry_after_seconds` parses
integer/date Retry-After, or is null; there is no automatic sleep/retry.

Store outcomes distinguish `accepted` (validated 202), `failed` (validated
all-failed 500 in `StoreFailedError.result`), `rejected` (400/401/403), `not_sent`
(local validation, or cancellation/timeout before protected dispatch) and
`unknown` (lost/malformed responses, other statuses, or cancellation/timeout after
dispatch). A malformed 202 is `ProtocolError` with unknown delivery. Reconcile
unknown delivery before deciding whether to resubmit; the gateway offers no
status lookup or proven batch idempotency. Resubmitting failed items is an
explicit new application operation.

## Transport and cancellation

HTTPS with Node's normal certificate validation is required. Do not disable TLS
verification through Node environment settings. Local development alone may opt
in to HTTP with `allowInsecureLocalhost: true` for literal `localhost`, `127.0.0.1`
or `[::1]`. URL userinfo, query, fragment, whitespace and backslashes are rejected.
Deployment path prefixes are preserved. The SDK uses native fetch with manual
redirect handling and owns no closeable transport; no client `close()` is needed.

One `timeoutMs` budget covers exchange, protected dispatch, replay and body
consumption. It must be finite, positive and at most 2,147,483,647 ms (Node timer
limit). AbortController propagates timeout/cancellation to fetch; a promise race
also bounds caller waiting on an uncooperative injected transport. Timers cannot
interrupt a blocked JavaScript event loop, and an adapter ignoring abort may
continue its underlying work. Late responses never populate an abandoned token
exchange or trigger replay. Cancellation after store dispatch cannot undo server
publication. A shared exchange has its own bounded lifetime; joining callers keep
their own remaining budgets and do not extend that lifetime.

Tests/applications may inject `transport: (url, init) => Promise<Response>`. The
caller owns this adapter: it must honor `init.signal`, `redirect: "manual"`, keep
TLS verification, disable its own retries, and avoid logging secrets. The SDK
cannot inspect or enforce an arbitrary adapter's internal behavior.

## Development and versioning

```sh
npm ci
npm run format:check
npm run lint
npm test
npm pack
```

`format` applies Prettier to source, tests, examples and package/configuration JSON;
`format:check` checks the same files without changing them. Prettier is a pinned
development dependency, with its style configured in package.json.

`lint` runs strict TypeScript checks, including examples; tests use Node's built-in
test runner and shared synthetic gateway fixtures. The loopback fetch test needs
permission to bind a local port. No credentials or live gateway are needed.

Install `bump2version==1.0.1` in an isolated Python virtual environment. From this
package directory, increment the independent SDK version with:

```sh
bump2version patch
npm run lint
npm test
npm pack
```

`.bumpversion.cfg` updates package.json, package-lock.json and exported `VERSION`.
It does not commit, tag or publish. Update the changelog separately. Publication
and staging acceptance need a separate request; see [verification evidence](../../docs/evidence/clients-typescript/README.md).
