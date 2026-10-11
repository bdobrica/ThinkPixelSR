# SDK interface specification — Phase 1

CL-008–CL-013 design requirements for future Python, TypeScript and PHP SDKs.
No packages or executable examples are shipped by this phase. Gate 1 review
remains pending. The [gateway wire baseline](../../clients/contracts/README.md)
and [synthetic fixtures](../../clients/contracts/fixtures/index.json) describe
server behavior at gateway revision `89fe1899b7f008cbd30cf073e0f748e1529d7519`;
that gateway source remains unchanged by this specification.

## Authority and sequencing decision

On 2026-10-11 the operator requested Phase 1 and selected the API Gateway API
as the source of truth. Where ThinkPixelPlugin differs, implement the gateway
contract: do not invent `stored_ids`, use the plugin's batch-size response,
copy its processed-row fallback, or normalize invalid-key 500 into 401.
Plugin compatibility defects remain separate follow-ups. CL-007 live smoke is
deferred and unchecked; its procedure exists but execution has not occurred.
The operator authorized Phase 1 despite that gap and pending Gate 0 review.
This does not authorize gateway/plugin changes, enrollment exposure or release.

## CL-008: configuration and public operations

One `ThinkPixelSRClient` per gateway/key, synchronous Python/PHP and asynchronous
TypeScript. Construction performs no I/O. Key and origin are required; no default
public origin or environment-variable auto-discovery. Applications inject secrets.

| Concept | Python | TypeScript | PHP |
| --- | --- | --- | --- |
| Configuration | keyword `base_url`, `api_key`, `timeout=15.0`, `transport=None`, `allow_insecure_localhost=False` | object `baseUrl`, `apiKey`, `timeoutMs=15000`, `transport?`, `allowInsecureLocalhost=false` | options array `base_url`, `api_key`, `timeout=15.0`, `transport`, `allow_insecure_localhost=false` |
| Authenticate | `authenticate() -> AuthResult` | `authenticate(options?) -> Promise<AuthResult>` | `authenticate(): AuthResult` |
| Store | `store(documents: Sequence[Document]) -> StoreResult` | `store(documents: readonly Document[], options?) -> Promise<StoreResult>` | `store(array $documents): StoreResult` |
| Search | `search(text: str, *, language: str = "auto") -> SearchResult` | `search(text: string, options?: {language?: string; signal?: AbortSignal}) -> Promise<SearchResult>` | `search(string $text, string $language = 'auto'): SearchResult` |

TypeScript authenticate/store options contain only optional `signal`.
No single-document overload: store always accepts a nonempty sequence/array.
No public registration methods until Gate 2 defines their actual contract;
no placeholder method that pretends to issue a key. No wrappers for defective
batch guidance or rotation endpoints.

Origin must be an absolute HTTPS URL, optionally with a deployment prefix;
reject userinfo, query, fragment and empty key. Strip trailing slash, append
fixed route paths without discarding the prefix. Do not follow redirects.
Validate certificates and hostnames, with no insecure TLS toggle. Explicit
local HTTP opt-in accepts only literal localhost, 127.0.0.1 or [::1], with no
DNS resolution used to broaden that exception. Never forward credentials to
another origin. HTTP is forbidden for all other hosts.

Timeout is finite and positive, an overall operation budget including exchange,
renewal and any permitted replay. Injected transports must honor remaining
budget, disable their own retries/redirects and provide status/headers/body;
reject adapters that cannot enforce these requirements. SDK-owned transports
are closed by the SDK (Python context manager/close, PHP close); injected
transports remain caller-owned. TypeScript AbortSignal covers both exchange
and operation; cancellation prevents replay. Python/PHP provide synchronous
timeout behavior, not a claimed public async cancellation API.

## CL-009: argument and result mapping

All languages use identical snake_case wire fields in document/result types.
Python typed immutable records, TypeScript readonly interfaces and PHP typed
value objects retain the same field names. Configuration follows language
conventions above. Unknown response fields are retained in an `extensions`
map at each object level; never promoted to supported request options.

| Input | SDK validation | Wire mapping |
| --- | --- | --- |
| Document `id` | integer, excluding bool; signed int32 range | `id` unchanged; prevents the gateway's int32 queue truncation |
| Document `text` | string, required; empty allowed as observed | `text` unchanged; no Markdown conversion |
| Document `language` | optional string | omitted if absent; empty remains empty (gateway defaults to auto) |
| Document `extra` | optional map of string keys to string values | `extra` unchanged; no metadata round-trip guarantee |
| Search `text` | required nonempty string | `{text,language}`; no trimming/rewrite |
| Search `language` | string, defaults to auto | `language` unchanged |

Reject unsupported request fields/options locally rather than relying on the
Go decoder ignoring them. No positivity/unique-ID rule, text length limit,
filters, pagination, model, tenant, weights or client-selected result limit.
The signed int32 constraint is a deliberate SDK safety restriction on store
input, not a claim that the handler validates it. Response IDs are integers
representable exactly in the language (TypeScript safe integers); reject
unrepresentable values rather than rounding. Duplicate search IDs remain intact.

| Result | Required fields and handling |
| --- | --- |
| `AuthResult` | integer `exp` only, as absolute Unix seconds; token remains private in cache, excluded from representation/serialization |
| `StoreResult` | integer `received_texts`, `pending_documents`, `failed_documents`; RFC3339 `timestamp` string; optional `pending_ids` integer array and `failed_items` array of `{id,error}`; `http_status=202` |
| `SearchResult` | `results` array of `{id:integer,text:string,score:finite number}`; preserve order, duplicate IDs and backend score values |

Keep omitted optional fields absent (`None`/undefined/null in the typed accessor),
with explicit serialization omitting them; do not fabricate empty arrays or
`stored_ids`. Preserve timestamp text and unknown JSON fields. Counters must
be nonnegative and sum correctly; optional ID/item lists must match their
corresponding counts when present. Malformed/missing required fields produce
ProtocolError. Scores are not normalized or deduplicated. Unknown metadata
is untrusted data, excluded from diagnostic representations.

202 returns StoreResult even with failed items: caller checks counts. Accepted
means queue publication, never indexing or eventual durability. A structured
500 all-failed response raises StoreFailedError containing a validated
StoreResult with `http_status=500`; generic 500 raises ServerError. Do not turn
all-failed into success. Failure detail strings remain available explicitly,
not in automatic logs/repr. A malformed 202 is ProtocolError with delivery
state unknown; it must never cause automatic resubmission.

## CL-010: authentication state

1. Initially no token. `authenticate()` always exchanges with POST /auth/token,
   X-API-Key and no body; replaces cache only on a valid 200 response.
2. Store/search lazily exchange when no usable token exists. Cache is memory
   only; validate nonempty string token and integer exp from response, without
   decoding JWT claims. Never return the token through public AuthResult.
3. Reuse until local UTC epoch reaches exp minus 30 seconds. An exchanged token
   already within that window is ProtocolError; do not loop exchanges. Clock
   injection for tests is internal. Failed explicit exchange clears old cache.
4. A protected request receiving 401 clears cache, re-exchanges once and replays
   once if budget/cancellation permits. A second 401 raises AuthenticationError
   and clears cache. Exchange itself is never automatically retried.
5. Store replay is permitted only for an actual 401 response: middleware rejects
   before the handler publishes. No replay on lost response, 408 or 5xx. This
   assumption relies on gateway/proxy preserving the middleware status; no
   custom transport may manufacture 401 after delivering an accepted response.

No /refresh/token, refresh credential, automatic API-key rotation or on-disk
cache. 403 never triggers exchange. Exchange 500 remains ServerError even
when its body says invalid API key; do not classify by parsing error prose.
TypeScript coalesces concurrent exchanges for one client; callers waiting on
that exchange retain independent budgets/signals (one caller cancellation
must not cancel other callers). Python/PHP initial clients are documented as
not safe for concurrent shared use. Replay uses the same immutable payload.

## CL-011: retries and delivery state

Default transport/status retry count is zero for every operation, including
search and exchange. Only the bounded 401 flow above is automatic. No retry
configuration in the initial public interface, no backoff scheduler, and no
idempotency header. Caller may elect to retry search after investigating its
failure; SDK never silently repeats inference.

Store failures expose `delivery_state`: `rejected` for a gateway 400/401/403
before handling; `accepted` for validated 202; `failed` for validated all-failed
500; `unknown` for transport failures, timeouts, cancellation, malformed replies
and other statuses (including proxy-generated 429/5xx). Locally rejected input
uses `not_sent`. Do not infer rejection from a disconnect or HTTP 408.
Caller-selected resubmission of failed_items is an explicit new operation;
never automatically resend the whole batch or infer idempotency from Qdrant
upserts. Unknown delivery needs operator reconciliation; there is no status API.

## CL-012: errors, credentials and rate limits

Shared exported names across languages (native Exception/Error inheritance):
`ThinkPixelSRError` base; `ConfigurationError`, `ValidationError`,
`AuthenticationError`, `PermissionError`, `RateLimitError`, `TransportError`,
`TimeoutError`, `CancelledError`, `ProtocolError`, `ServerError`,
`StoreFailedError` (extends ServerError), and `HTTPError` for other statuses.
Registration errors are deferred until the approved endpoint exists.

| Failure | Mapping |
| --- | --- |
| Invalid local arguments/config | ValidationError/ConfigurationError; no HTTP |
| Final HTTP 401 / HTTP 403 | AuthenticationError / PermissionError |
| HTTP 400 or 422 | ValidationError with status; preserve gateway status |
| HTTP 429 | RateLimitError; no auto-sleep/retry |
| HTTP 408 / operation deadline | TimeoutError; distinguish status-bearing server timeout |
| Valid store-all-failed 500 | StoreFailedError with structured outcome |
| Other 5xx | ServerError, regardless of error message |
| DNS/connect/TLS/I/O failure | TransportError; credential-free message |
| Caller cancellation | CancelledError |
| Other non-success status, including redirects | HTTPError; no redirect |
| Bad JSON/schema on expected success | ProtocolError |

Classify error statuses before trying to parse their body: a plain-text 401
still follows auth handling, a malformed 500 remains ServerError. Structured
store 500 is the sole schema-specific exception. Expected success statuses are
200 for auth/search and 202 for store; other 2xx are ProtocolError.
Errors carry operation, optional HTTP status and store delivery state, without
raw headers/body/URL, API key, token or server exception prose. Sanitized fixed
messages and safe repr/stack wrapping must not expose transport exceptions;
raw exceptions must not be automatically chained if they contain credentials.
No default HTTP tracing, payload logging or hooks exposing auth headers.

RateLimitError includes nullable `retry_after_seconds`: parse nonnegative
integer Retry-After seconds or an HTTP date using injected UTC clock; past dates
become zero, invalid/missing values null. Expose only this parsed value, not raw
headers. 429 support is defensive for proxies, not a gateway rate-limit promise.
TLS verification is always enabled. Environment keys and response extensions
must be excluded from serialized diagnostic client/error objects.

## CL-013: runtime, transport and packaging choices

These are initial support targets, not assertions that packages are registered
or current dependency releases have been tested. Pin dependency/tool ranges
and verify lowest runtime support in Phase 4; check ownership before publishing.

| Language | Target / transport | Provisional package and exports |
| --- | --- | --- |
| Python | CPython 3.11+; synchronous HTTPX transport adapter with retries disabled and shared deadline | PyPI `thinkpixel-sr`; import `thinkpixel_sr`; pyproject.toml, wheel/sdist, typed `py.typed`; pytest, Ruff, mypy |
| TypeScript | Node.js 22+ only; native fetch adapter, AbortController, no fetch polyfill; TypeScript 5.6+ authoring target | npm `@thinkpixel/sr`; ESM-only export with declarations; `ThinkPixelSRClient`; node:test, tsc |
| PHP | PHP 8.3+ on 64-bit runtime; PSR-18/PSR-17 injection through an SDK deadline-aware adapter; default Guzzle 7 adapter enforcing timeout/no retry/no redirects | Composer `thinkpixel/sr`; namespace `ThinkPixel\SR`; PSR-4; PHPUnit, PHPStan, composer validate |

PSR-18 alone cannot guarantee timeouts: an arbitrary PSR client without a
configured deadline adapter is insufficient. Package dependencies and licenses
are checked in the package phases, not installed here. Python async, CommonJS,
browsers, 32-bit PHP and replacing WordPress plugin transport are outside initial
support. No CORS/server changes. Independent SDK semantic versions start with
unpublished 0.x; gateway baseline v0 is not an SDK version. Adding optional
response fields is compatible; removing/renaming fields, method arguments or
error semantics requires an explicit compatibility review and version decision.

## Gate 1 review and later conformance evidence

Reviewers should approve the signatures and deliberate store ID restriction,
origin handling, result/error mappings, shared deadline and concurrency rules.
Required offline scenarios for Phase 3/4 include:

- Exact auth headers/no body, lazy cache reuse, expiry skew, malformed/expired
  exchange response, invalid-key 500 and one-retry/final-401 behavior.
- Full/partial 202, structured all-failed 500, omitted optional fields, counter
  validation, signed int32 boundaries, lost/malformed responses and zero replay
  after timeout/5xx; 401 store replay only before handler execution.
- Search empty/order/duplicate IDs/backend scores, unknown fields, malformed
  JSON, unsafe integer values and unsupported request-option rejection.
- 403/429/Retry-After/date parsing, redirects/TLS/origin validation, sanitized
  errors and repr, deadline exhaustion/cancellation and concurrent TS exchange.

These requirements extend the existing synthetic fixture set; they are not
passing tests or Gate 3 evidence. No live smoke, package builds, dependency
installation or server mutation occurred in Phase 1.

## Phase 1 verification

`make verify` passed: 42 offline tests run, one skipped; inherited runtime
baseline retained (401/405 files byte-identical with existing reviewed
exceptions), limited candidate secret/path scan, documentation links, Python,
Make and shell syntax, Terraform/dev HCL formatting and six Kustomize renders
passed. The Terragrunt forwarding test remains skipped for the installed
version. `git diff --check` passed. This documentation-only change does not
require runtime/package tests; live smoke remains deferred. No deployment,
registration, store/search requests, database writes or plugin edits occurred.

`make help` passed. `make doctor` returned exit 2 for unsupported Terragrunt
0.81.0. Configuration checks returned expected exit 2 for missing dev secret
file, unsupported prod, and missing/invalid environment selection. No real
credentials were used and no fallback or mutation occurred.
