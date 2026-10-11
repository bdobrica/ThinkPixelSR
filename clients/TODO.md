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

**CL-014–CL-019 review proposal:** [registration policy, threat model and endpoint design](../docs/clients/key-registration.md).
These tasks remain unchecked: policies are proposed, not approved; operator
controls are specified, not implemented. Existing auth storage cannot enforce
single-use proofs without an additive migration. Gate 2 must approve that change
and the proposed revocation enforcement before CL-020. CL-020–CL-022 remain
blocked on that review and a separately authorized restricted environment.
No generic enrollment endpoint or live rollout has been added.

## Phase 3 — Contract testing (Gate 3)

- [ ] **CL-023** Establish shared mocked HTTP scenarios and sanitized fixtures for auth, store, search and registration.
- [ ] **CL-024** Cover malformed responses, invalid keys, expired JWT, 401/403/4xx, 429, 5xx, transport errors and timeouts.
- [ ] **CL-025** Cover store accepted vs eventually indexed and document the system's actual consistency guarantees.
- [ ] **CL-026** Add optional staging-only live test harness with credentials supplied via CI secrets, never tracked files.
- [ ] **GATE 3** Verify contract suite can be run independently of a live cluster.

## Phase 4A — Python SDK

- [x] **CL-027** Create `python/` package, `pyproject.toml`, supported runtime policy and local development commands.
- [x] **CL-028** Implement configured HTTP transport, safe request handling, API-key→JWT flow and token management.
- [x] **CL-029** Implement `/store` and `/search` mapped to verified fixtures and response types.
- [ ] **CL-030** Implement registration call(s) only against the approved public server contract. Deferred by operator: existing keys suffice for current scope.
- [x] **CL-031** Add pytest contract, edge/error and mock tests; type/lint checks.
- [x] **CL-032** Write Python install, safe credential handling, full usage examples and package build check.

**Operator sequencing exception (2026-10-11):** jump to Python existing-key
store/search; defer Phase 2 and registration. Explicit `api_key` overrides the
`THINKPIXEL_API_KEY` process environment fallback. Gates 0–3 remain open; Python
mock tests do not complete shared registration scenarios or staging acceptance.
**CL-027–CL-029, CL-031–CL-032 evidence:** [package and local commands](python/README.md),
[verification and runtime/deadline limits](../docs/evidence/clients-python/README.md).
Version 0.1.0 was assigned using bump2version; no package was published.

## Phase 4B — TypeScript SDK

- [x] **CL-033** Create `typescript/` package with explicit Node support, TypeScript build/types and npm metadata.
- [x] **CL-034** Implement transport, JWT exchange/cache, `/store` and `/search` with typed results.
- [ ] **CL-035** Add approved registration workflow and constrained renewal/error handling. Registration deferred by operator; existing-key renewal/error handling is covered by CL-034/CL-036.
- [x] **CL-036** Add shared contract tests, lint/build checks, and timeout/cancellation tests.
- [x] **CL-037** Document server-side key safety, optional browser restrictions, CORS and complete Node usage examples.

**Operator sequencing exception (2026-10-11):** implement TypeScript with the
same existing-key scope as Python; defer key assignment and CL-035. Explicit
`apiKey` overrides `THINKPIXEL_API_KEY`. Gates 0–3 and live acceptance stay open.
**CL-033–CL-034, CL-036–CL-037 evidence:** [package and commands](typescript/README.md),
[tests, packaging, runtime coverage and limits](../docs/evidence/clients-typescript/README.md).
Independent version 0.1.0 was assigned using bump2version; nothing was published.

## Phase 4C — PHP SDK

- [x] **CL-038** Create `php/` Composer package, namespaces, supported runtime declaration and HTTP transport strategy.
- [x] **CL-039** Implement key→JWT exchange/cache, `/store` and `/search` without changing the existing WordPress plugin.
- [ ] **CL-040** Add approved registration workflow and consistent exception mapping. Registration deferred by operator; exception mapping is covered by CL-039/CL-041.
- [x] **CL-041** Add PHPUnit/shared fixture tests, static analysis and Composer validity checks.
- [x] **CL-042** Document plain PHP and optional WordPress-adjacent examples, key storage precautions and installation.

**Operator sequencing exception (2026-10-11):** implement PHP existing-key
store/search; defer CL-040 registration. Omitted `api_key` reads
`THINKPIXEL_API_KEY`; explicit keys take precedence. Gates 0–3 and live acceptance
remain open. **CL-038–CL-039, CL-041–CL-042 evidence:** [package and commands](php/README.md),
[tests, archive/consumer checks and runtime limits](../docs/evidence/clients-php/README.md).
Independent 0.1.0 was assigned using bump2version; nothing was published.

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

## Operator extension — MCP (existing key)

Registration and original live gates remain deferred. The operator requested
this extension directly, overriding the previous async deferral.

- [x] **CL-050** Add async Python search/store client while preserving sync behavior; shared auth renewal, bounded replay, deadline and cancellation tests.
- [x] **CL-051** Add FastMCP search/store tools, strict input schemas, lifecycle cleanup, safe errors, stdio and Streamable HTTP tests.
- [x] **CL-052** Provide non-root Docker image, restricted build context and hosting/agent setup instructions. Local build and network-disabled container smoke passed; live gateway and remote hosting remain unverified.

Acceptance commands, runtime and limitations: [MCP evidence](../docs/evidence/mcp/README.md).
