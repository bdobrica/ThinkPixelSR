# SDK key registration proposal — CL-014–CL-019

Status: proposed for Gate 2 review, 2026-10-11. No endpoint, migration,
configuration flag or operator command in this document is implemented.
CL-020–CL-022 require separate approval and restricted-environment verification.
The gateway remains the [SDK source of truth](../../clients/contracts/README.md).
This document does not freeze a new wire contract before server implementation.

## Source findings and compatibility boundary

Reviewed against gateway source retained at commit
`1a5e47d88311d4283d7add086441a51ae02a526f`:

- [Routing](../../docker/api_gateway/api_gateway/main.go) exposes unversioned
  `POST /register` without JWT; it initiates WordPress callbacks. Preserve it.
- [Registration](../../docker/api_gateway/api_gateway/register/register.go),
  [validation](../../docker/api_gateway/api_gateway/register/validation.go) and
  [exchange](../../docker/api_gateway/api_gateway/register/exchange.go) do not
  provide invitation authorization. Callback URLs derive from caller input;
  default HTTP clients follow redirects. Validation tokens are logged.
- [Token generation](../../docker/api_gateway/api_gateway/register/tokens.go)
  hashes timestamps rather than reading cryptographic randomness. Do not reuse
  these generators for invitations or new SDK credentials.
- [Sites schema](../../database/db_thinkpixel.sql) and
  [node patch](../../database/patches/0001-wp_thinkpixel_index_nodes.sql) store
  one hashed key per site, status/expiry and indexing assignment; there is no
  invitation ledger, atomic consumption state or endpoint scope column.
- [DB helpers](../../docker/api_gateway/api_gateway/db/db.go) activate keys and
  assign nodes in separate steps. Reusing activation unchanged would not make
  issuance atomic. The generic flow must not call callback registration helpers.
- [Auth cache](../../docker/api_gateway/api_gateway/auth/api_key.go) trusts a
  cached active key until its key expiry, so changing DB status alone does not
  promptly revoke it. [JWTs](../../docker/api_gateway/api_gateway/auth/jwt.go)
  include the plaintext key in `sub` and last 15 minutes.
- [Request logger](../../docker/api_gateway/api_gateway/logger/request_logger.go)
  records request bodies and headers except Authorization. It is currently wired
  to selected protected routes, not registration/auth. Attaching it to the new
  route would disclose proof; attaching it to auth would disclose X-API-Key.
- The checked-in [Service](../../k8s/apps/thinkpixel/base/api-gateway/service.yaml)
  exposes port 8080 through NodePort; TLS termination is not established by that
  file. [Configuration](../../k8s/apps/thinkpixel/base/api-gateway/configmap.yaml)
  and [deployment](../../k8s/apps/thinkpixel/base/api-gateway/deployment.yaml)
  provide existing MySQL/config/secret consumers and request-log forwarding.
  Do not copy secrets or assume logs are confined to the pod.

These are source findings, not an exploit demonstration or deployment audit.
Existing callback security defects are separate follow-ups, not authorization
for an API/plugin rewrite. A new route's disable switch will not disable the
existing `/register`; operators must assess that independent exposure.

## Proposed enrollment policy (CL-014, CL-016)

Only an operator-approved application may enroll. An operator provisions an
existing site record with a verified owner, canonical domain/path, suspended
status, no API key, finite expiry policy, and an already assigned indexing node.
The invitation proves delegated operator approval, not automated domain ownership.
No public account creation, email service, callbacks or network validation.

An invitation binds to exactly one existing numeric site ID. Metadata and
capacity are operator-owned and cannot be supplied or overridden by the caller.
One unexpired invitation per site; one successful issuance per invitation;
no replacement of an active, revoked or historical key through enrollment.
Rotation/recovery requires a separate operator procedure and a fresh review.
Use a non-NULL canonical path for enrollment targets; the current nullable
unique domain/path key must not be treated as guaranteed owner uniqueness.

Proposed defaults: invitation lifetime 15 minutes (maximum 1 hour), issued key
lifetime 30 days (maximum 30 days), at most one outstanding invitation per site
and 10 invitation issuances per operator per UTC day. Enforce quotas in shared
MySQL state, including canceled invitations; these are proposed policy limits,
not current gateway limits. Deliver invitation once through a private channel.

New key rights equal the gateway's existing site-bound key rights, including
existing protected removal routes; they are not read-only or limited to
store/search. No new endpoint privilege is granted. If this breadth is
unacceptable, Gate 2 must reject this proposal and separately review scope
storage/enforcement. Tenant isolation uses the existing site ID/auth context,
not an arbitrary caller-supplied tenant. Require negative cross-site tests.

## Threat model (CL-015)

Assets: invitation, key/JWT, site identity, indexing capacity, DB and audit data.
Trust boundaries: caller to TLS edge to gateway to shared MySQL; operator to
private issuance tool; gateway logs to forwarding/storage. Attackers may send
arbitrary requests, replay captured proof, race replicas or hold another site's
valid credential. Compromised operators/hosts require incident recovery.

| Threat | Required control and residual limitation |
| --- | --- |
| Spam/capacity exhaustion | Operator-only invitations; shared quotas and rate budgets; existing preassigned capacity; bounded body/concurrency/timeouts |
| Enumeration/brute force | 32 random bytes per proof; uniform invalid-proof response for unknown, expired, used, canceled and ineligible; no site lookup endpoint; constant-time digest comparison where applicable |
| Invitation replay/racing | Transactional row lock/consume; concurrent requests across replicas yield at most one committed key |
| Credential leakage | TLS, no URLs/cookies/browser storage; no raw bodies/headers/proof/hash/key/JWT in logs, tracing or errors; no response caching |
| Tenant/privilege escalation | Site binding loaded from invitation only; reject extra fields; no client-selected owner, node, scope or lifetime; preserve gateway isolation |
| SSRF/domain takeover | No outbound requests or caller-selected URLs in new flow; existing callback risk remains separate |
| Stolen invitation | Bearer proof can be redeemed by its holder; short expiry/private distribution and cancellation reduce risk, do not establish caller identity |
| Lost success response | Key may already exist; never replay issuance or redisclose plaintext; operator revokes, then reviews recovery |
| DB/audit/limiter outage | Fail closed before issuance; atomic consume/key/audit commit; never return a key for rolled-back state |
| Stale auth cache | Enrollment blocked pending reviewed revocation control; DB status alone is insufficient |

## Proposed wire contract (CL-017)

Add `POST /register/key`, distinct from legacy `/register`, without API key/JWT.
TLS required through a verified trusted edge; no redirects. No permissive CORS
and no cookie authentication. Initial SDKs are server-side. Browser preflight
gets no cross-origin permission. Only POST is allowed (405 with Allow: POST).

Content-Type application/json, maximum 4096-byte body, reject trailing JSON,
unknown fields, missing/empty/wrong-type proof. Proposed sole request field:

```json
{"invitation_token":"<privately-delivered-proof>"}
```

Proof format: `sr-invite-` plus unpadded base64url of 32 cryptographically random
bytes. Key format: `sr-key-` plus the same random-byte length, independently
sampled. Store SHA-256 digests only; existing 64-character key hash fits.
Never accept a caller-generated key. Response after committed issuance:

```json
{"api_key":"<disclosed-once>","site_id":123,"expires_at":"2030-01-01T00:00:00Z","status":"active"}
```

201 only, Cache-Control: no-store on every response. Example values are synthetic;
expiry is a server-generated UTC RFC3339 timestamp. No pending state, JWT or
invitation echo. Existing `/auth/token` then authenticates normally. Do not
silently normalize enrollment results into the Phase 1 auth result.

Errors retain the gateway's JSON `error` string convention, with fixed messages
and no DB details. They are proposals for this route only; old routes retain
current status/error behavior.

| Status | Fixed error | Meaning |
| --- | --- | --- |
| 404 | Not found | Disabled route; no proof lookup |
| 400 | Invalid request payload | JSON/field/proof-format failure |
| 401 | Invalid registration proof | Unknown/expired/used/canceled/ineligible proof; no distinctions |
| 413 | Request too large | Body bound exceeded |
| 415 | Unsupported media type | JSON required |
| 429 | Registration rate limit exceeded | Shared rate budget; integer Retry-After seconds |
| 503 | Registration unavailable | Missing readiness controls, DB/limiter/audit failure or contention timeout |
| 500 | Registration failed | Unexpected internal failure; no raw exception |

A network failure or 5xx after sending has unknown issuance outcome. SDKs must
never automatically retry registration; a used proof returns generic 401,
not the original key. Operator recovery handles lost-response cases. No
idempotency header or plaintext recovery store is proposed.

## Persistence decision and transaction (CL-018)

Existing schema is insufficient. Propose an additive MySQL invitation ledger
and secret-free audit/rate-budget storage in the existing database, subject to
separate migration review under root AGENTS.md. No migration is added here.

Ledger fields: internal ID, unique proof digest, site foreign key, operator
identity, created/expires timestamps, consumed/canceled timestamps and issued
site reference. Site row locking enforces one outstanding invitation without
relying on nullable SQL uniqueness. Audit records contain operator/site/internal
invitation IDs, event, timestamp and request correlation ID, never proof/digest.
Shared budgets record bucket identity, window and count, with atomic increments.
Retention proposal: purge expired proof digests after 7 days; retain secret-free
audit 90 days. Confirm privacy/operational retention at Gate 2.

Issue transaction locks site, checks operator quota/ineligibility/outstanding
proof, writes ledger/budget/audit together. Redeem first resolves the proof digest to a candidate site ID without trusting
that lookup as authorization. Its transaction then locks site followed by the
invitation row, matching issuance/cancellation lock order, and revalidates the
digest-to-site binding. It verifies expiry/cancellation/
consumption and site eligibility, generates random key, updates the existing
site hash/status/expiry, consumes invitation and appends audit, then commits.
Return plaintext only after commit. DB clock governs expiry. Failure rolls back
all issuance state. Do not invoke nontransactional activation/node-assignment
helpers. Deadlock/commit ambiguity produces a safe error without automatic
redeem retry. Test duplicate/random collisions and conditional row counts.

This needs an explicit migration/rollback decision: take a private backup;
apply additive schema only in reviewed staging; rollback application with new
route disabled while retaining ledger/audit. Do not drop issuance records or
undo consumed proofs during rollback. Existing sites/keys remain intact.

## Operator controls and rollout proposal (CL-019)

Proposed `API_GATEWAY_SDK_REGISTRATION_ENABLED` defaults false. Missing/invalid
control values fail closed for this route. No corresponding checked-in setting
or Make target is added. When enabled, shared limiter/audit/schema readiness and
verified TLS boundary are mandatory; otherwise 503. HTTPS-forwarding headers
are trusted only from explicitly configured proxy peers; arbitrary
X-Forwarded-Proto cannot establish TLS. Existing HTTP health checks remain.

Proposed rate limits: 5 attempts per source IP per minute and 100 attempts per
minute per deployment, enforced across replicas before proof parsing/lookup.
Use normalized direct peer address unless a reviewed trusted proxy resolves it.
Do not log raw IPs as audit identity; use bounded, expiring limiter records.
No attacker-selected unbounded metric labels. Limit body reads and operation
runtime to 5 seconds; cap concurrent redemption work. Limiter capacity and
trusted proxy settings require staging review before exposure.

A local operator tool, not a public admin HTTP endpoint, issues/cancels proofs
and revokes keys under existing DB access custody; dry-run output never shows
secrets. Explicit issuance writes proof once to a private file, not stdout/logs.
Tool syntax/implementation remains CL-020 work after approval. No casual SQL
recipe is supplied for bypassing invitation policy.

Revocation must prevent cached credentials from continuing to authorize:
propose DB active/expiry recheck for SDK-enrolled sites at each protected
request, identified by retained consumed ledger rows. This is a narrowly
reviewed auth-path change and adds DB load; do not implement without approval.
No positive-cache fallback on DB outage. Revoked JWT must also fail its site
status check. Legacy-key cache behavior remains a separately documented risk.
If reviewers reject this mechanism, choose another enforceable revocation
strategy before implementation; pod restart alone is not a durable guarantee.

Stage with route network-restricted and flag false; verify disabled behavior,
then enable only for approved test callers. Use synthetic owners/private proofs,
exercise issuance/auth/store/eventual-search/revocation, inspect sanitized logs
and cross-replica concurrency. Review plugin regression with old `/register`.
Disable route and cancel outstanding proofs for rollback; disablement stops new
issuance, not existing keys. Revoke issued test credentials and confirm rejection
across replicas before deleting test data under a separate cleanup approval.
No production enablement, migration or cluster action is authorized here.

## Gate 2 review and implementation acceptance

Approve or amend owner policy, existing key privilege breadth, quota/expiry
limits, additive schema, transaction design, auth revocation change, trusted
TLS boundary, rate controls and rollout/rollback before CL-020. Gate 0/1 review
and CL-007 remain pending; this proposal is not their acceptance evidence.

CL-021 must prove successful one-time disclosure; absent/invalid/expired/used/
canceled proof; cross-site isolation; concurrent redemption across two instances;
disabled/misconfigured mode; shared rate limits; rollback on DB/audit failure;
commit/response-loss handling; no key/proof/JWT in captured logs/errors;
revocation of both cached key exchange and existing JWT; TLS spoof/redirect/CORS
rejection; body bounds and existing plugin behavior. Run offline gateway tests
with synthetic credentials and transaction mocks, then shared-DB concurrency
integration tests in restricted staging. Mocks alone do not prove atomicity.

CL-022 requires separately authorized environment/credentials, reviewed migration,
TLS/edge ownership, rollback custody and scoped cleanup. Record exact results and
sanitized evidence; no live success claimed by this design.

Verification for this documentation change: `make verify` passed (42 offline
tests, one skipped; 272 documentation links; source baseline, limited secret
scan, Python/Make/shell syntax, HCL formatting and six Kustomize roots).
The skip is the installed Terragrunt version below the required minimum.
`git diff --check` passed. Actual gateway/security tests and staging exercise
are pending; no live API calls, migration, deployment or plugin smoke ran.
