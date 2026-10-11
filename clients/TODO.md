# TODO — ThinkPixelSR language clients

Chronological implementation checklist for [PLAN.md](PLAN.md). Completed Phase 0 source/documentation tasks link to their evidence below. Mark complete only with a reviewed change and test/documentation evidence. IDs are stable for issues and PRs. Use the API Gateway API as the SDK source of truth; plugin differences remain separate compatibility findings. Public registration needs a security decision before server changes.

## Phase 0 — Evidence and baseline (Gate 0)

- [x] **CL-001** Inspect ThinkPixelSR gateway code and ThinkPixelPlugin authentication, storage and search calls. Record source paths and commit SHAs.
- [x] **CL-002** Document actual API base URL, auth endpoint and header/body/response/expiry behavior. Do not assume route names from SDK sketches.
- [x] **CL-003** Document exact `/store` method, schema, metadata, accepted response, error codes and asynchronous indexing guarantees.
- [x] **CL-004** Document exact `/search` method, query/filter/scope schema, result fields, ranking metadata and errors.
- [x] **CL-005** Inspect existing key generation, ownership, MySQL persistence, hashing, revocation and registration/provisioning paths.
- [x] **CL-006** Add `contracts/README.md` and sanitized golden JSON fixtures; record uncertainties, versioning and source provenance.
- [ ] **CL-007** Run the baseline ThinkPixelPlugin→gateway→index→search smoke test. Procedure documented; live acceptance deferred because API/plugin differences remain unresolved and no approved disposable environment was supplied.
- [ ] **GATE 0** Peer-review and freeze a *verified* initial wire-compatibility matrix.

**CL-001–CL-006 evidence and CL-007 procedure:** [wire baseline and fixtures](contracts/README.md),
[source revisions, verification and documented smoke omissions](../docs/evidence/clients-phase-0/README.md).
Gate 0 awaits independent review; live compatibility remains unverified.
**Operator decision (2026-10-11):** the API Gateway API is authoritative for SDKs.
Proceed with Phase 1 against the source-audited gateway baseline despite the
open CL-007/Gate 0 live/plugin gaps. This does not authorize server/plugin fixes
or claim integration success.

## Phase 1 — SDK interface and engineering choices (Gate 1)

- [x] **CL-008** Agree on `base_url`, `api_key`, transport, timeouts and method names for Python, TypeScript and PHP.
- [x] **CL-009** Define canonical store and search argument/result mappings; preserve existing response fields.
- [x] **CL-010** Specify token cache, expiry handling, re-exchange after 401 (one retry maximum) and no invented refresh-token endpoint.
- [x] **CL-011** Specify retry/idempotency policy, especially no blind resend of an accepted `/store` request.
- [x] **CL-012** Specify error classes, redaction, TLS expectations and rate-limit behavior in all languages.
- [x] **CL-013** Decide supported language/runtime versions, transport libraries, SDK naming and packaging (names not presumed registered).
- [ ] **GATE 1** Review cross-language public interface and backward-compatibility rules.

**CL-008–CL-013 evidence:** [SDK interface and engineering specification](../docs/clients/sdk-interface.md).
Signatures, mapping tables, auth/retry state rules, error policy, runtime targets
and package/transport choices are specified for all three languages. Gate 1
remains open for independent review; SDK code and contract tests are later phases.

## Phase 2 — Key-registration policy and public endpoint (Gate 2)

- [ ] **CL-014** Define who can obtain a key, tenant/site binding, allowed privileges, issuance quotas, expiration and revocation.
- [ ] **CL-015** Threat-model anonymous/public enrollment: spam, enumeration, brute force, invitation replay, credential leakage and privilege escalation.
- [ ] **CL-016** Select approved registration proof/verification flow; prefer scoped one-time invitations for MVP if no trusted identity mechanism exists.
- [ ] **CL-017** Specify the proposed public endpoint(s), payloads, return state, statuses and error format aligned with existing gateway routing.
- [ ] **CL-018** Decide whether an existing auth schema suffices; design the smallest necessary persistence/config change if not.
- [ ] **CL-019** Add operator controls: disabled-by-default rollout, rate limiting, audit logging without secrets, lifecycle/revocation and TLS/CORS policy.
- [ ] **GATE 2** Approve endpoint, threat model and rollout rules before making an internet-accessible registration route.
- [ ] **CL-020** Implement only the reviewed gateway registration flow, reusing existing auth storage and deployment architecture.
- [ ] **CL-021** Add gateway tests: success, absent/invalid/expired/replayed proof, tenant isolation, disabled mode, rate limit, key secrecy and revocation.
- [ ] **CL-022** Deploy and exercise registration in a restricted non-production environment; do not expose production enrollment by default.

## Phase 3 — Contract testing (Gate 3)

- [ ] **CL-023** Establish shared mocked HTTP scenarios and sanitized fixtures for auth, store, search and registration.
- [ ] **CL-024** Cover malformed responses, invalid keys, expired JWT, 401/403/4xx, 429, 5xx, transport errors and timeouts.
- [ ] **CL-025** Cover store accepted vs eventually indexed and document the system's actual consistency guarantees.
- [ ] **CL-026** Add optional staging-only live test harness with credentials supplied via CI secrets, never tracked files.
- [ ] **GATE 3** Verify contract suite can be run independently of a live cluster.

## Phase 4A — Python SDK

- [ ] **CL-027** Create `python/` package, `pyproject.toml`, supported runtime policy and local development commands.
- [ ] **CL-028** Implement configured HTTP transport, safe request handling, API-key→JWT flow and token management.
- [ ] **CL-029** Implement `/store` and `/search` mapped to verified fixtures and response types.
- [ ] **CL-030** Implement registration call(s) only against the approved public server contract.
- [ ] **CL-031** Add pytest contract, edge/error and mock tests; type/lint checks.
- [ ] **CL-032** Write Python install, safe credential handling, full usage examples and package build check.

## Phase 4B — TypeScript SDK

- [ ] **CL-033** Create `typescript/` package with explicit Node support, TypeScript build/types and npm metadata.
- [ ] **CL-034** Implement transport, JWT exchange/cache, `/store` and `/search` with typed results.
- [ ] **CL-035** Add approved registration workflow and constrained renewal/error handling.
- [ ] **CL-036** Add shared contract tests, lint/build checks, and timeout/cancellation tests.
- [ ] **CL-037** Document server-side key safety, optional browser restrictions, CORS and complete Node usage examples.

## Phase 4C — PHP SDK

- [ ] **CL-038** Create `php/` Composer package, namespaces, supported runtime declaration and HTTP transport strategy.
- [ ] **CL-039** Implement key→JWT exchange/cache, `/store` and `/search` without changing the existing WordPress plugin.
- [ ] **CL-040** Add approved registration workflow and consistent exception mapping.
- [ ] **CL-041** Add PHPUnit/shared fixture tests, static analysis and Composer validity checks.
- [ ] **CL-042** Document plain PHP and optional WordPress-adjacent examples, key storage precautions and installation.
- [ ] **GATE 4** Confirm parity matrix and staging store→eventual-search test for each language, or record explicit environment limitations.

## Phase 5 — Docs, security, CI and release (Gate 5)

- [ ] **CL-043** Add maintainable per-language READMEs with verified setup, code samples, API surface and troubleshooting.
- [ ] **CL-044** Document operator registration enablement, invitation/proof issuance, key revocation and safe disablement.
- [ ] **CL-045** Add CI for packages, tests, lint/static checks and build artifacts, with no leaked credentials or production side effects.
- [ ] **CL-046** Verify dependency licenses, secret scanning, examples and published-package ownership/name availability.
- [ ] **CL-047** Establish semantic versioning, independent package tags/releases and changelog policy; publish only when approved.
- [ ] **CL-048** Run existing ThinkPixelPlugin compatibility regression after registration gateway changes.
- [ ] **CL-049** Link `clients/` from the root README and integrate accepted change scope into root tracking docs.
- [ ] **GATE 5** Validate end-to-end success, security review, documented limitations and production rollout approval.

## Completion evidence template

For each completed task, include a PR/commit link, verification command and output summary, any staging environment used, and any blocked/unverified behavior. Do not check off live tests when only mocked tests were run.
