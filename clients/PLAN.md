# PLAN — ThinkPixelSR language clients

## 1. Objective

Add `clients/` to ThinkPixelSR to provide reliable, idiomatic **Python, TypeScript and PHP** libraries for the existing Search/RAG API. Use the existing API Gateway API as the source of truth for client behavior: API-key authentication, key-to-JWT exchange, document submission and document search. Review the existing callback-based `POST /register` and define a narrowly scoped, secure **SDK API-key registration flow** because obtaining a first key cannot be solved by client libraries alone.

This is a **client usability initiative with one explicit server-side dependency**. It is not permission to redesign the working gateway, database, ingestion, indexing, retrieval or infrastructure architecture. This plan is subordinate to the repository's [root architectural invariants](../PLAN.md) except where the public registration endpoint is deliberately approved as a scoped addition.

## 2. Principles and non-goals

1. **Gateway contract first:** gateway routes, handlers and response structures are authoritative for SDKs. Plugin behavior is compatibility evidence, not an alternative client contract. Preserve existing operations, names and semantics.
2. **Minimal SDKs:** thin HTTP facades, not frameworks, generated microservices or alternate client-side search engines.
3. **One contract, three idiomatic languages:** shared test vectors, shared semantics and recognizable names; native exceptions/types and package conventions.
4. **Safe credentials:** no secrets in repos, query strings, browser bundles or normal logs; TLS, configurable timeouts and limited retries.
5. **Preserve async ingestion:** `/store` success must be represented as accepted/enqueued if that is what the gateway actually reports. Do not promise read-after-write consistency.
6. **Registration is different from authentication:** enrollment must create a new credential under server-side authorization/verification; key exchange must only issue JWTs for existing authorized keys.
7. **No opportunistic endpoint expansion:** no new delete/update/list/bulk/index-status APIs without a separate approved plan. Batch operations may use the existing contract only if confirmed.
8. **Do not mutate plugin or server code for SDK ergonomics** unless necessary for the explicitly approved registration feature or to fix a documented compatibility defect with separate authorization.

## 3. Phase 0 — Verify the real protocol

Inspect the **source** of `docker/api_gateway` and the ThinkPixelPlugin client implementation (including PHP classes, hooks and tests). Capture:

- API root/base URL rules, TLS requirements, API versioning and routing.
- Exact API-key-to-JWT endpoint, method, headers, body, JWT response and expiry semantics.
- `/store` and `/search` methods, required fields, document identity, metadata, supported filters/options, accepted status, error payloads and response structure.
- Tenant/site/key ownership rules and permission boundaries.
- Retry behavior, idempotency support or lack of it, actual error codes and rate-limit indicators.
- Current API-key provisioning workflow, schema, hashing/storage and administrative controls.

Write `clients/contracts/README.md` and sanitized JSON fixtures with a source location/commit reference. Resolve SDK inconsistencies in favor of the gateway API and record plugin differences separately; do not change the plugin or gateway to reconcile them. Obtain an integration environment or record test gaps.

The [Phase 0 baseline](contracts/README.md) records the existing `POST /register`
callback flow and source revisions. A generic synchronous enrollment route is
not implemented; do not add or replace a route before Gate 2 review.

**Gate 0:** source protocol and fixtures remain subject to independent review.
On 2026-10-11 the operator explicitly selected the API Gateway API as the SDK
source of truth and authorized Phase 1 despite the unexecuted CL-007 smoke and
plugin/API differences. This scoped sequencing exception permits interface
specification against the source baseline; it does not mark Gate 0 or live
plugin compatibility passed. CL-007 remains deferred and unchecked.

## 4. Phase 1 — Define the SDK contract

Proposed logical interface: `authenticate`, `store`, `search`, `register_key`/`registerKey`. Map exact arguments/responses after Gate 0. Define:

- Config: gateway `base_url`, key, timeout, optional transport/HTTP client, optional user-agent.
- Lazy token exchange; in-memory JWT cache; expiry-aware reuse if the server provides lifetime; re-authenticate on demand. JWTs are **not** written to disk automatically.
- Refresh by repeat API-key exchange, **not** an invented refresh-token endpoint. At most one re-auth attempt after 401; never infinite loops.
- Retries: no automatic store retry if delivery could have succeeded and idempotency is unverified; narrow retry policy for demonstrably safe requests and only with bounded backoff.
- Store outcome mapped without conflating `accepted` with `indexed`; return server IDs/status and raw metadata where available.
- Search filters/query options limited to verified server support; preserve ranking/result fields and unknown metadata as appropriate.
- Typed error hierarchy for auth, permission, validation, rate limiting, transport, server and registration failures; avoid leaking secrets in messages.
- Cancellation/timeouts and hooks for HTTP mocking according to language conventions.

The [Phase 1 SDK interface specification](../docs/clients/sdk-interface.md)
records CL-008–CL-013: exact signatures, argument/result mappings, auth state,
retry and error rules, runtime targets and packaging choices. These are design
requirements for later implementation, not shipped SDK capabilities.

**Gate 1:** review the specification and its cross-language conformance scenarios
before implementation. Independent approval remains pending.

## 5. Phase 2 — Design and add secure public key registration

### 5.1 Critical distinction

“Public endpoint” means callable without an **existing** API key/JWT. It does **not** authorize anonymous users to mint unlimited, privileged keys. Before implementing, choose and document the business policy: invitation token, email/domain verification, existing account authentication via a distinct proof, human approval, or controlled self-service. For MVP, prefer an operator-issued **single-use, expiring invitation** if no identity/verification mechanism already exists; don't introduce a new full identity service merely to support the SDKs.

### 5.2 Concrete proposal for Gate 2 review

The [Phase 2 registration proposal](../docs/clients/key-registration.md) records
CL-014–CL-019: operator-approved, site-bound single-use invitations; a separate
`POST /register/key` preserving callback `/register`; exact proposed JSON/status
mapping; transactional consumption; shared abuse controls; secret-free audit;
and disabled-by-default rollout. These are review proposals, not implemented
contracts or approved business policy.

Source inspection finds that the current schema cannot enforce one-time
invitations atomically. The proposed additive MySQL ledger and audit/rate state
require separate migration approval under root AGENTS.md. Prompt revocation
also requires a reviewed auth-path change because the current cache trusts keys
until expiry. Neither change is silently authorized by SDK ergonomics.
Existing keys authorize more than store/search; reviewers must accept those
rights or separately approve scope enforcement before enrollment implementation.

**Gate 2:** approve owner/privilege policy, endpoint, threat model, persistence,
revocation, abuse controls and rollout before CL-020 implementation. The request
to work on Phase 2 starts design review; it does not constitute approval of an
as-yet unspecified migration or public exposure. CL-020–CL-022 remain pending.
Registration must stay disabled/inaccessible until controls and tests pass.

## 6. Phase 3 — Shared test contracts

Provide scrubbed fixtures and mock-server/HTTP test cases for successful exchange, invalid/expired key, JWT expiry, store accepted/not indexed, search, empty results, client errors, bad JSON, 429 and transient 5xx/timeouts. Use one cross-language behavior matrix, with no real key committed. Establish optional live integration tests against non-production staging. Include registration invitation success, expiration, reuse, unauthorized enrollment and revocation/disable behavior.

**Gate 3:** all required scenarios are specified and runnable in CI/offline where possible.

## 7. Phase 4 — Implement Python, TypeScript and PHP

### Python

**Operator sequencing decision (2026-10-11):** proceed directly to Phase 4A
for existing-key `/store` and `/search`, deferring Phase 2 key assignment and
CL-030 registration. Implement the relevant offline contract cases within the
Python package despite open Gates 0–3; these gates and live acceptance stay open.
Python accepts an explicit key or, when omitted, `THINKPIXEL_API_KEY` from the
process environment. No server, schema or plugin changes are authorized.
Use bump2version for independent SDK versions; publication remains separate.


Typed package targeting a documented supported Python range, lightweight mainstream HTTP client, sync interface first. Provide `pyproject.toml`, pytest, type checking/linting, examples, packaging metadata and PyPI publication plan. Do not add async API until demand warrants it.

### TypeScript

**Operator sequencing decision (2026-10-11):** implement Phase 4B with the same
existing-key scope as Python. Defer CL-035 registration and keep Gates 0–3 and
live acceptance open. Omitted `apiKey` reads `THINKPIXEL_API_KEY`; explicit keys
win. Use bump2version for the independent SDK version. No server changes,
publication or browser credential support are authorized.

ESM-first package with clear declared Node.js support; typed request/results, `fetch` or a small injectable transport, tests, build and npm metadata. Define Node/browser support honestly. Never advocate placing persistent privileged API keys in client-shipped JS. Do not require frontend framework dependencies.

### PHP

Composer-distributed library with namespaces and a documented supported PHP range; prefer PSR-18/PSR-17-compatible transport if practical without heavy dependencies. Use PHPUnit, PHPStan (or equivalent), short WordPress-compatible usage examples and a clear explanation that it does **not** replace ThinkPixelPlugin.

Build the languages sequentially, stabilizing shared fixtures before each port. Avoid cross-language generated SDK code if it complicates the MVP more than hand-maintained thin clients.

**Gate 4:** each client passes identical semantics tests, idiomatic static checks and at least one non-production store→eventual-search integration scenario (or explicitly documented environment block).

## 8. Phase 5 — Documentation, CI and releases

- Language-specific installation and quickstarts with verified request/response data.
- Registration instructions for deployment operators (enablement/invitations/revocation) and SDK users (proof handling); explain no-first-key bootstrap before endpoint is enabled.
- Troubleshooting: HTTP errors, expired key/JWT, ingestion delay, rate limits, TLS, CORS and async indexing.
- CI matrix for unit, contract and build tests; protected secrets for optional staging tests. No live tests against production.
- License, maintainers, releases/changelogs and independently versioned packages; PyPI/npm/Packagist names subject to availability and verification.
- Update root README to link to `clients/` and root TODO to track this approved extension.

**Gate 5 / definition of done:** all three SDKs demonstrated against verified existing `/store` and `/search`; registration validated end-to-end with abuse controls; existing WordPress plugin remains functional; no architectural changes except the explicitly scoped public endpoint; docs, CI and security review complete.

## 9. Known decisions to record

- Gateway `POST /auth/token`, absolute Unix-seconds `exp`; see the wire baseline.
- Gateway array `/store` and text/language `/search`; see the wire baseline and SDK specification.
- Definition of owner/tenant and who may register an API key.
- Public enrollment policy and whether verification is synchronous or two-stage.
- Whether current MySQL schema can express single-use invitations without migration.
- Python 3.11+, Node 22+, PHP 8.3+ targets and provisional package names; see the SDK specification. Publication ownership remains unverified.
- Initial TypeScript SDK is Node-only; no browser API-key support.

Do not silently choose these details in SDK code. Track decisions in the contract notes or a short ADR and update this plan only when decisions are accepted.
