# ThinkPixelSR makeover — chronological checklist

Follow [PLAN.md](PLAN.md). Check a box only after its acceptance evidence exists. Completed baseline documentation does not imply live validation or infrastructure changes. Keep items in dependency order; split work into small reviewable PRs. All live changes require explicit operator authorization.

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

- [ ] **P2-01** Define `.env` schema and precedence, backed by a table mapping keys to existing Terragrunt/Flux/Docker consumers. **Done:** no new competing source of truth.
- [ ] **P2-02** Add sanitized `.env.example` (`ENV`, Hetzner/DNS secret locations, SSH key locations, cluster parameters, registry/image inputs **only as actually needed**). **Done:** no real credentials or private paths exposed.
- [ ] **P2-03** Update `.gitignore` to cover `.env`, local secret files, private SSH keys, kubeconfigs and nested Terraform state, without accidentally ignoring intended checked-in examples. **Done:** `git status`/ignore checks and secret scan pass.
- [ ] **P2-04** Implement safe configuration validation and translation that feeds existing `.secrets.hcl`/Terragrunt behavior or documented environment overrides; avoid shell-evaluating untrusted `.env`. **Done:** previous direct Terragrunt path still works.
- [ ] **P2-05** Test dev/prod and negative cases: missing token, missing key, invalid ENV, malformed numbers, unsupported pool, quoted values, unexpected whitespace, sensitive logging. **Done:** clear errors and no leaked secrets.

## Phase 3 — Implement Makefile in risk order

- [ ] **P3-01** Add `.DEFAULT_GOAL := help` (or equivalent) and `help`, `doctor`, `config-check`; ensure `make` alone cannot modify anything. **Done:** self-documenting help and safe checks.
- [ ] **P3-02** Add `cluster-init` and `cluster-plan` wrappers selecting only known environment roots. **Done:** direct Terragrunt and wrapper previews agree; no implicit apply.
- [ ] **P3-03** Add `cluster-up`, applying a reviewed plan with operator confirmation and explicit production guard. **Done:** deliberate dev apply validated; no unreviewed `-auto-approve`.
- [ ] **P3-04** Add `flux-check`, then guarded `flux-bootstrap` matching existing Flux installation and Git source setup. **Done:** Flux starts reconciling without changing workload ownership.
- [ ] **P3-05** Add `images-build` and `images-push` using existing Dockerfiles, architecture targets and registry/tag conventions; require explicit tags and credentials. **Done:** dev image push and pull reference verified without tag drift.
- [ ] **P3-06** Add `status`, offline `verify` and explicitly gated live smoke checks. **Done:** truthful outputs, actionable failures, no secrets.
- [ ] **P3-07** Add guarded `cluster-scale ENV=dev POOL=<name> COUNT=<n>` for existing worker pools only; show plan first and require explicit reduction acknowledgment. **Done:** scale-up reviewed; scale-down safeguards tested in dry-run and actual reductions only with authorization.
- [ ] **P3-08** Add basic lint/check coverage for Make, shell, YAML, HCL formatting and links where tools exist. **Done:** repeatable CI-safe validation, no unrelated CI redesign.

## Phase 4 — Write operator documentation against actual commands

- [ ] **P4-01** Finalize `docs/architecture.md` with accurate as-built diagram, Qdrant/Redis distinction and data persistence map.
- [ ] **P4-02** Write `docs/configuration.md`: `.env` variable reference, sources of truth, credential paths, precedence and dev/prod examples.
- [ ] **P4-03** Write `docs/deployment/hetzner.md`: prerequisites, SSH/DNS/state, first deploy, plan/apply, health and rollback.
- [ ] **P4-04** Write `docs/deployment/fluxcd.md`: bootstrap inputs, Git source management, reconciliation, troubleshooting and cutover.
- [ ] **P4-05** Write `docs/operations/images.md`: supported images, build platform, registry push, tags and pinning.
- [ ] **P4-06** Write `docs/operations/scaling.md`: worker pools, PDB/storage checks, worker scale-up/down, plan review and recovery.
- [ ] **P4-07** Write `docs/operations/verification.md` and `docs/operations/troubleshooting.md`, including the working plugin golden path and queue/model/Qdrant diagnostics.
- [ ] **P4-08** Refresh root README: replace all "planned" command caveats only for commands implemented and validated; link every durable guide. **Done:** an unfamiliar operator can locate the correct runbook.

## Phase 5 — Validate, migrate, close

- [ ] **P5-01** Run static validation/secret scanning and confirm no unintended changes to code, API contracts, database schema, runtime manifests or resource identities. **Done:** reviewed baseline diff.
- [ ] **P5-02** Walk the documented dev lifecycle: config-check -> cluster-plan -> authorized cluster-up -> Flux bootstrap/reconcile -> image pull -> status. **Done:** record observed results or precise blockers.
- [ ] **P5-03** Exercise the actual ThinkPixelPlugin document-ingest-to-search golden path and compare to baseline. **Done:** expected results and limitations captured with sanitized logs.
- [ ] **P5-04** Verify scaling (at minimum safe plan/review; live scale tests if authorized) and document rollback with actual worker pools and workload constraints.
- [ ] **P5-05** Schedule and perform explicit GitOps remote switch only after verifying access, rollback and old source retention. **Done:** new source reconciles as intended; old source can be restored.
- [ ] **P5-06** Update parent ThinkPixel catalog/docs for actual `ThinkPixelSR` repository and retain lineage link to ThinkPixelInfra; do not elevate maturity automatically.
- [ ] **P5-07** Review release notes, broken links, scripts and cross-file consistency; mark verified commands stable and document open limitations. **Done:** acceptance criteria in PLAN met, with evidence.

## Deferred / separate proposals

- [ ] **D-01 (not part of makeover)** Evaluate broader ThinkPixel platform integration only against a concrete use case and a separately accepted architecture decision.
- [ ] **D-02 (not part of makeover)** Track search performance, API modernization, new models, extra deployment providers and production hardening separately; do not smuggle them into P0–P5.
