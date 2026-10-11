# Gateway wire baseline v0

Source-audited baseline for **CL-001–CL-007**. This describes the existing
protocol, not proposed SDK signatures. Gate 0 remains open for independent
review; live plugin compatibility is unverified. No server changes are implied.
See [inspection and verification evidence](../../docs/evidence/clients-phase-0/README.md).

## Provenance and change rules

Inspected 2026-10-11:

- ThinkPixelSR commit `89fe1899b7f008cbd30cf073e0f748e1529d7519`;
  gateway sources below are relative to `docker/api_gateway/api_gateway/`.
- ThinkPixelPlugin commit `b8f64d05cbe11a58dbf7f7dcee0f5dce271d7d63`
  (SearchPixel 1.4.5), fetched read-only into a temporary checkout.
  [Pinned plugin tree](https://github.com/bdobrica/ThinkPixelPlugin/tree/b8f64d05cbe11a58dbf7f7dcee0f5dce271d7d63).
  Plugin paths below are relative to that repository.
- No accepted ADR or previously published API contract directory was found.
  Older gateway README examples are not authoritative: `/register/exchange`
  is not registered by `main.go`.

`v0` is this evidence revision, **not an API path/version or SDK release**.
Changes must identify new source SHAs, distinguish source/mock/live evidence,
and retain existing fixtures or explain compatibility impact. Do not freeze
public signatures or silently turn observed defects into desired behavior.

## Origin, routing and transport

`searchpixel/class/core/strings.php::ApiUrl` is compiled as
`https://api.thinkpixel.io:8080`; this is a source value, not a verified reachable
endpoint or permission to send requests. The gateway `main.go` listens on plain
HTTP `:8080` with unversioned routes and no path prefix. Local Compose exposes
`http://localhost:8080`. Kubernetes service maps port 8080 to 8080; TLS/ingress
termination and the effective deployed origin remain operator evidence gaps.
Configure the SDK origin explicitly; do not infer a default from the plugin.
HTTPS is required for credentials outside isolated local development. No CORS
middleware, request rate limiter or `Retry-After` contract was found in routing.
Proxy behavior, redirects, TLS and 429 responses remain unverified.

Use `Content-Type: application/json` for JSON bodies. Successful handler and
handler-error responses use that content type (`utils/rest.go`); router-level
404/405 responses need not be JSON. Methods below are exact; other methods are
rejected by Gorilla mux. Unknown JSON fields are ignored by these decoders;
this does not make them supported options. No idempotency header is implemented.

## Initial wire-compatibility matrix (review candidate)

| Operation | Method / path | Authentication / request | Response | Evidence |
| --- | --- | --- | --- | --- |
| Key exchange | POST `/auth/token` | `X-API-Key`; no body needed | 200 `{token:string,exp:integer}` | `auth/auth.go`, `auth/jwt.go`; plugin `Api::fetch_jwt` |
| Store | POST `/store` | Bearer JWT; JSON array of documents | 202 complete/partial queue acceptance; 500 if all fail | `handlers/store_handler.go`; plugin `Api::process_posts_raw` |
| Search | POST `/search` | Bearer JWT; `{text,language?}` | 200 `{results:[{id,text,score}]}` | `handlers/search_handler.go`, backend sources; plugin `Api::do_search` |
| Site enrollment (existing) | POST `/register` | No key/JWT; site statistics and callback-capable domain/path | 200 validation token/expiry/message; asynchronous callbacks deliver key | `register/`; plugin `Api::register_site`, `Rest` |
| Batch guidance (defective) | POST `/store/max_batch_text_size` | Bearer JWT; plugin sends `{timeout}` | Currently 500 context type mismatch; declared `{size}` differs from plugin expectation | `handlers/max_batch_text_size.go`; plugin `Api::fetch_max_batch_text_size` |
| Key rotation (defective) | POST `/refresh/apikey` | Bearer JWT | Currently 500 context type mismatch | `handlers/refresh_key_handler.go`; plugin `Api::refresh_api_key` |

## API key → JWT

[`AuthHandler`](../../docker/api_gateway/api_gateway/auth/auth.go) reads only
`X-API-Key`, not a JSON `api_key`. Missing/empty header returns 400
`{"error":"API Key is required"}`. Successful exchange returns `token` and
absolute Unix-seconds `exp`, not `expires_in`. JWT is HS256, issued for 15 minutes
in [`jwt.go`](../../docker/api_gateway/api_gateway/auth/jwt.go); database `jwt_ttl`
is not consumed here. JWT claims include `sub` containing the **plaintext API
key**, `hashed_key` and `exp`: treat the entire token as a secret, never decode
it into diagnostic output. There is no refresh-token endpoint.

[`ValidateAPIKey`](../../docker/api_gateway/api_gateway/auth/api_key.go) computes
lowercase hex SHA-256 and looks up the cached/site record. An invalid, revoked
or expired key with no valid cache entry produces an error, so AuthHandler
returns **500** `Error validating API Key: invalid API key` for no matching row.
Its nominal 401 `Invalid API Key` branch is not reached by the current validator
for that case. Database failures also return 500, with implementation details.
Do not normalize all these failures to a verified 401 in future fixtures.

[`JWTMiddleware`](../../docker/api_gateway/api_gateway/middleware/auth_middleware.go)
returns 401 `Missing token` without Authorization and 401 `Invalid token` for
malformed/expired JWT. It strips a case-sensitive `Bearer ` prefix (raw tokens
also pass parsing). Use the plugin's `Authorization: Bearer <token>` form.
Decode/cache lookup failures return 500. No separate role/scope 403 contract is
implemented here. Plugin `get_jwt` uses a WordPress transient for `exp - time()`;
it does not re-exchange/retry automatically on 401. Future SDK renewal policy
belongs to Phase 1.

## Document submission

[`StoreRequest`](../../docker/api_gateway/api_gateway/handlers/store_handler.go)
is a JSON **array**, even for one document:

- `id`: Go integer, supplied WordPress post ID; cast to signed int32 for queue
  payload. Do not assume UUID/string IDs or safe values outside int32.
- `text`: string; plugin sends title plus content converted to Markdown.
- `language`: optional string, omitted/empty defaults to `auto`.
- `extra`: optional object of **string values**, e.g. `title` and `type`.

The decoder rejects incompatible types or malformed JSON with 400 `Invalid
request payload`; `[]` and `null` return 400 `Request must contain at least one
item`. It does not explicitly validate required ID/text, positivity, uniqueness,
text length or metadata keys; omitted ID/text decode to zero/empty. That is
observed permissiveness, not a promise that downstream indexing will succeed.
There is no request-selected tenant, model or backend. Authenticated site ID,
model and chunk settings come from the key record. `extra` travels through the
queue, but Qdrant storage builds only site/post ID, offset and text payload;
metadata round trips are not guaranteed.

Response fields: integer `received_texts`, `pending_documents`,
`failed_documents`; optional integer array `pending_ids`; optional
`failed_items:[{id:integer,error:string}]`; `timestamp` in RFC3339. Empty optional
fields are omitted. A 202 means **at least one** publish succeeded, including
partial failure. Total publish failure returns 500 with the same structured
store response, not the generic error envelope. The normal nil-queue branch
returns 503; middleware supplies the queue in ordinary routed operation.
Other context/dependency failures may return 500.

Core NATS `Publish` is not a durable/indexing acknowledgment. Subscriber retries
and DLQ handling do not establish delivery, exactly-once processing, bounded
indexing latency or read-after-write guarantees. No status/polling API or
idempotency key exists. Qdrant uses `site_<site ID>` and point ID
`uint64(post ID)<<32 | uint64(chunk offset)`; upsert alone does not prove safe
request replay or removal of obsolete chunks after document changes.

Plugin `process_posts_raw` prefers `stored_ids` (absent from this gateway), then
falls back to **all submitted IDs** unless a top-level `error` exists. Thus a
partial 202 or total structured 500 can mark unsuccessful posts processed.
`process_posts` marks these rows locally; that is not indexing evidence.
Preserve the plugin while recording this separately reviewed compatibility defect.

## Search

[`SearchRequest`](../../docker/api_gateway/api_gateway/handlers/search_handler.go)
accepts string `text` (nonempty required) and optional string `language`
(default `auto`). No filters, pagination, client limit, scope, hybrid weights,
model or metadata selectors are supported. Limit is the key's
`max_search_results`; site/backend/model selection is server-owned.

Success is 200 `{"results":[{"id":900001,"text":"...","score":0.5}]}`.
`id` is an integer post ID; `text` is the matched chunk, not necessarily the
full document. No title, URL, offset, vectors, rank explanations or timing
metadata are returned. Qdrant initializes results to `[]`, fuses dense/sparse
prefetch using RRF, sorts descending by score and limits results; multiple
chunks can repeat a post ID, without document deduplication.
[`qdrantconn.go`](../../docker/api_gateway/api_gateway/qdrantconn/qdrantconn.go)
is the source for these fields, not captured live rankings.

Redis uses its existing dense ANN path and transforms distance to
`100 * (1 - abs(distance))`; its empty result slice encodes as `results:[]`.
Scores are backend-specific, not calibrated percentages or comparable across
models/backends. Redis appends float32 scores but its sort asserts float64;
multiple results can panic. Nonempty Redis result parity is unverified and
this defect requires a separate fix; the SDK must not claim backend parity. No Redis hybrid parity is implied.

Malformed/wrong-type JSON gives 400 `Invalid request payload`; absent/empty text
(including `{}` or `null`) gives 400 `Text field is required`. Unsupported
backend/model/inference failures give 500; retrieval failure gives 500
`Error performing ANN search` (including absent Qdrant collection). The handler
wait gives 408 `Request timed out` after 10 seconds; server write timeout is
30 seconds. This is not a verified cancellation or client timeout contract.
Plugin `do_search` returns the decoded object; `Plugin::do_custom_search` uses
`results[].id` to select WordPress posts through `pre_get_posts`, with local
search caching. Save/cron hooks track/process posts; plugin mocked unit tests
use `stored_ids` and do not cover the current 202/partial acknowledgement.

## Existing provisioning, persistence and revocation

Enrollment already exists; it is **not a generic synchronous SDK key issuer**.
[`RegisterHandler`](../../docker/api_gateway/api_gateway/register/register.go)
decodes `domain`, `path` (strings), `estimated_pages`, `average_page_size`,
`st_dev_page_size` (integers). It has no explicit field validation beyond JSON
types. Malformed payload gives 400; database/reset failures give 500. Response
200 contains `validation_token`, RFC3339 `validation_token_expires_at` (may
include fractional seconds), and `message`. Default challenge lifetime is five
minutes. Pending/suspended site data is stored, or failed validation is reset.

Gateway asynchronously GETs `<protocol>://<domain><path><validation suffix>`;
plugin returns domain/path/token and a WordPress nonce. Gateway checks stored
pending token and expiry, marks verified, then POSTs `{api_key,nonce,message}`
to the exchange callback. Plugin validates the nonce and stores the key in
WordPress settings; it responds with **string** `success:"true"` plus message.
Only after that response does gateway activate/hash the key and assign a node.
Gateway defaults use `/thinkpixel/v1/`; checked-in K8s ConfigMap explicitly
uses the plugin's `/searchpixel/v1/validate/` and `/exchange/` suffixes.
Callbacks default to HTTPS unless insecure validation is enabled.

Source: `register/{validation,exchange,protocol,tokens}.go`,
[`db.go`](../../docker/api_gateway/api_gateway/db/db.go), plugin
`searchpixel/class/core/{api,rest,settings,ui}.php`.
Key generation is `api-key-` plus 32 characters of URL-base64 SHA-256 of the
current nanosecond timestamp, **not a cryptographic random generator**.
Validation tokens use the same construction with `verify-` and 16 characters.
MySQL `wp_thinkpixel_sites.api_key` stores unsalted hex SHA-256; domain/path
has a unique key. Default activation validity is 720 hours (30 days).
Site ID binds storage/retrieval; domain/path is provisioning identity, not
per-request hostname verification. No invitation table or single-use invitation
primitive was found in base SQL or patches. Base schema lacks the gateway's
`indexing_node_type`; existing migration/setup gaps remain unresolved.

`status` supports active/revoked/suspended; DB lookup checks active and expiry.
There is no revocation HTTP route. Cached key entries survive database status
changes until cached expiry; immediate revocation is not guaranteed. Nullable
`expires_at` is selected into `time.Time`, another unverified compatibility edge.
The rotation handler's context mismatch means it is not a verified key renewal
path; its DB helper changes hash without cache invalidation or expiry extension.

No registration disable switch, quota enforcement, invitation/replay policy or
SSRF protection was found in this path. Timestamp-derived credentials,
callback identity validation and credential-bearing logs need separate security
review. This audit does not approve public exposure or add controls. Phase 2
must review **the existing flow and any proposed addition**, preserving plugin
compatibility and requiring an approved enrollment policy first.

## Fixtures and unresolved acceptance

[fixtures/index.json](fixtures/index.json) lists HTTP cases and exact source
locations. Bodies are synthetic golden **shape/branch examples**, never live
captures; credentials are nonfunctional markers and dates/scores are fixed
illustrations. Unknown runtime error details use a sanitized queue error.
They must not be advertised as runnable valid JWTs or observed rankings.

Open questions before Gate 0/signatures: independent review of this matrix;
effective deployed gateway/plugin/image/schema revisions; actual TLS origin;
non-production WordPress store→index→search observation; queue loss/retry
behavior; deployed backend behavior; enrollment policy/security decisions.
The [baseline procedure and omissions](../../docs/evidence/clients-phase-0/README.md)
records CL-007's permitted documentation outcome. No live test is checked off.
