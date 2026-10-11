# ThinkPixelSR makeover — chronological checklist

No active makeover tasks remain in this checklist. At the operator's request,
unfinished items have been removed from the active scope; their unverified
acceptance criteria are retained in [PLAN.md](PLAN.md#operator-deferral).
Completed items below retain their evidence. Removal does not imply successful
live validation, deployment, scaling or cutover.

The [2026-10-11 operator-machine inspection](docs/evidence/phase-5/operator-machine.md)
locates the original dev state and records approved read-only readiness checks,
Flux fetch failure and subsequent verified recovery, wrapper prerequisites and
repaired offline checks. Live `flux-check` and `status` pass after operator
credential repair/reconciliation; mutating and end-to-end acceptance remain open.

The [isolated dev plan review](docs/evidence/phase-5/dev-plan-review.md) now
records successful private configuration/init and live node/storage/PDB review.
The real plan failed on legacy DNS refresh and proposes replacing all five nodes;
no apply receipt was created. Provider/API compatibility and any DNS-state
migration require a separate review before deployment/scaling acceptance.

## Phase 0 — Verify what exists (baseline)

- [x] **P0-01** Inventory `cluster/`, `k8s/`, `docker/`, `database/`, `local/`, `debug/`, `.github/workflows/`, existing manifests and scripts; record owners, commands, assumptions and pointers in `docs/architecture.md` (draft). **Done:** paths and dependency map correspond to checked-in files. [Evidence](docs/architecture.md).
- [x] **P0-02** Record exact Terraform/Terragrunt/Hetzner provider versions, `cluster/live/dev` and `cluster/live/prod` settings, SSH key paths, `.secrets.hcl` requirements, remote state/backends and lockfiles. **Done:** baseline inventory table and state-preservation notes. [Evidence](docs/baseline/infrastructure.md); absent CLI pins and empty prod config explicitly recorded.
- [x] **P0-03** Inventory Flux sources, Kustomizations, bootstrap method, namespaces, persistent volumes, secrets, image tags and all absolute `ThinkPixelInfra` references. **Done:** migration reference checklist. [Evidence](docs/baseline/gitops.md); initial installation method remains unverified.
- [x] **P0-04** Inventory model Dockerfiles, build platforms, tag conventions, publishing workflows and destination registries. **Done:** image build/push map. [Evidence](docs/baseline/images.md).
- [x] **P0-05** Identify existing gateway endpoints and auth flow, NATS ingestion, embedding deployments, Qdrant retrieval and plugin integration; define minimal smoke tests with non-sensitive test data. **Done:** test inputs, expected responses, cleanup and limitations recorded. [Specification](docs/operations/verification.md).
- [x] **P0-06** Capture known-working dev behavior and configuration (sanitized); document unverified aspects if live access is unavailable. **Done:** repeatable baseline or explicit blocker record. [Evidence and blockers](docs/evidence/phase-0/README.md): offline baseline captured; live dev/plugin behavior remains unverified because no live run was authorized.

## Phase 1 — Establish the new repository without behavioral drift

- [x] **P1-01** Create `bdobrica/ThinkPixelSR` from a history-preserving copy of ThinkPixelInfra, retaining LICENSE, notices and all functional paths. **Done:** original main ancestry, release tags, LICENSE and 405 paths retained; 403 files unchanged and two README-only changes. The existing public GitHub repository received a fast-forward continuation and all four original tags; remote main and all 422 published file blobs/modes verified. [Evidence](docs/evidence/phase-1/README.md).
- [x] **P1-02** Add root `README.md`, `PLAN.md`, `TODO.md`, `AGENTS.md`; validate their relative links and consistent maturity/status claims. **Done:** no planned command represented as already working; root documents and linked guides reviewed. [Evidence](docs/evidence/phase-1/README.md).
- [x] **P1-03** Audit references to old repo, image identities, Flux GitRepository URLs and badges. Change documentation-facing references only for now; record live-reference cutover separately. **Done:** cluster clone documentation renamed; runtime Flux URLs, images and identities unchanged. [Reference mapping](docs/migration.md#path-and-reference-mapping).
- [x] **P1-04** Document repository history strategy, staging, temporary coexistence and rollback in `docs/migration.md`. **Done:** owner-resource switch-back steps, private capture, publication and validation gates documented; rollback generator checked offline, live procedure remains unverified. [Guide](docs/migration.md).

## Phase 2 — Introduce safe configuration

- [x] **P2-01** Define `.env` schema and precedence, backed by a table mapping keys to existing Terragrunt/Flux/Docker consumers. **Done:** selector/path mapping and unchanged authorities documented; no duplicate cluster/image settings. [Contract](docs/configuration.md).
- [x] **P2-02** Add sanitized `.env.example` (`ENV`, Hetzner/DNS secret locations, SSH key locations, cluster parameters, registry/image inputs **only as actually needed**). **Done:** seven selector/path keys, no credentials or private operator paths. [Template](.env.example).
- [x] **P2-03** Update `.gitignore` to cover `.env`, local secret files, private SSH keys, kubeconfigs and nested Terraform state, without accidentally ignoring intended checked-in examples. **Done:** synthetic nested ignore checks, tracked-file review and limited secret-pattern scan pass. [Evidence](docs/evidence/phase-2/README.md).
- [x] **P2-04** Implement safe configuration validation and translation that feeds existing `.secrets.hcl`/Terragrunt behavior or documented environment overrides; avoid shell-evaluating untrusted `.env`. **Done:** read-only Python loader and optional dev path hooks; complete inputs equal the frozen direct baseline in offline Terragrunt tests. [Contract and limits](docs/configuration.md).
- [x] **P2-05** Test dev/prod and negative cases: missing token, missing key, invalid ENV, malformed numbers, unsupported pool, quoted values, unexpected whitespace, sensitive logging. **Done:** 16 synthetic tests pass; empty prod explicitly blocked, diagnostics redacted, no live checks. [Evidence](docs/evidence/phase-2/README.md).

## Phase 3 — Implement Makefile in risk order

Wrappers are implemented; unfinished live acceptance has been deferred.

- [x] **P3-01** Add `.DEFAULT_GOAL := help` (or equivalent) and `help`, `doctor`, `config-check`; ensure `make` alone cannot modify anything. **Done:** fixed recipes, self-documenting help and safe checks validated. [Evidence](docs/evidence/phase-3/README.md).
- [x] **P3-02** Add `cluster-init` and `cluster-plan` wrappers selecting only known environment roots. **Done:** direct arguments and real Terragrunt forwarding to offline Terraform stub agree; previews execute no tools and no implicit apply. Live state/provider validation remains gated. [Evidence](docs/evidence/phase-3/README.md).
- [x] **P3-06** Add `status`, offline `verify` and explicitly gated live smoke checks. **Done:** redacted readiness summaries, offline gates and opt-in HTTPS `verify-live` liveness/database checks; synthetic tests pass. Full writable API/plugin smoke remains separately authorized and unverified. [Guide](docs/operations/commands.md#explicit-live-health-and-full-smoke).
- [x] **P3-08** Add basic lint/check coverage for Make, shell, YAML, HCL formatting and links where tools exist. **Done:** repeatable `make verify` passes available offline gates, explicitly reports tool skips and inherited Kustomize load restrictions; no CI redesign. [Evidence](docs/evidence/phase-3/README.md).

## Phase 4 — Write operator documentation against actual commands

Documentation tasks are complete; the PLAN deployment gate remains pending
external bootstrap/schema prerequisites and authorized live dev/plugin validation.
[Documentation evidence and precise limits](docs/evidence/phase-4/README.md).

- [x] **P4-01** Finalize `docs/architecture.md` with accurate as-built diagram, Qdrant/Redis distinction and data persistence map. **Done:** source-reviewed request/provisioning/GitOps diagrams and persistence/ownership table. [Guide](docs/architecture.md).
- [x] **P4-02** Write `docs/configuration.md`: `.env` variable reference, sources of truth, credential paths, precedence and dev/prod examples. **Done:** seven-key contract, separate Make arguments, dev path example and explicit prod rejection. [Guide](docs/configuration.md).
- [x] **P4-03** Write `docs/deployment/hetzner.md`: prerequisites, SSH/DNS/state, first deploy, plan/apply, health and rollback. **Done:** implemented guarded commands, existing/new state review, kubeconfig and recovery limits; fresh application bootstrap/schema stop points explicit. [Guide](docs/deployment/hetzner.md).
- [x] **P4-04** Write `docs/deployment/fluxcd.md`: bootstrap inputs, Git source management, reconciliation, troubleshooting and cutover. **Done:** existing-operator attach, prerequisite order, owners/revisions, retained old source and controlled switch-back link. [Guide](docs/deployment/fluxcd.md).
- [x] **P4-05** Write `docs/operations/images.md`: supported images, build platform, registry push, tags and pinning. **Done:** six exact contexts/versions, both platforms, private OCI/push workflow, digest/pull checks and mutable-tag/recovery limits. [Guide](docs/operations/images.md).
- [x] **P4-06** Write `docs/operations/scaling.md`: worker pools, PDB/storage checks, worker scale-up/down, plan review and recovery. **Done:** persisted existing-worker plans, all-pool replacement risk, private placement/PV/PDB reads and reduction/recovery gates. [Guide](docs/operations/scaling.md).
- [x] **P4-07** Write `docs/operations/verification.md` and `docs/operations/troubleshooting.md`, including the working plugin golden path and queue/model/Qdrant diagnostics. **Done:** current checks and source-inspected SearchPixel procedure with scoped fixtures/cleanup; real live known-good comparison remains unverified. [Verification](docs/operations/verification.md), [diagnostics](docs/operations/troubleshooting.md).
- [x] **P4-08** Refresh root README: replace all "planned" command caveats only for commands implemented and validated; link every durable guide. **Done:** task-to-guide index, real quick start and truthful offline/live/bootstrap status. [Entry point](README.md).

## Phase 5 — Validate, migrate, close

Offline validation and the dev blocker-record alternative are complete.
Remaining live acceptance, source cutover, parent publication and final
qualification are deferred; the original acceptance gate has not been met.
[Evidence and prepared review patches](docs/evidence/phase-5/README.md).

- [x] **P5-01** Run static validation/secret scanning and confirm no unintended changes to code, API contracts, database schema, runtime manifests or resource identities. **Done:** repeatable baseline gate, limited candidate secret-pattern/path scan, 401/405 inherited files byte-identical with four reviewed docs/ignore/path-hook exceptions; six current renders match frozen renders. [Comparison and scope](docs/evidence/phase-5/README.md#p5-01-baseline-and-publication-candidates).
- [x] **P5-02** Walk the documented dev lifecycle: config-check -> cluster-plan -> authorized cluster-up -> Flux bootstrap/reconcile -> image pull -> status. **Done:** actual local check failures plus ordered, precise state/credentials/bootstrap/schema/live authorization blockers recorded; no live lifecycle success implied. [Walkthrough](docs/evidence/phase-5/README.md#p5-02-documented-dev-lifecycle-walkthrough).
