# ThinkPixelSR repository makeover plan

## 1. Purpose

Move the existing [ThinkPixelInfra](https://github.com/bdobrica/ThinkPixelInfra) implementation into **ThinkPixelSR** with improved operability, configuration and documentation, preserving the working hybrid search MVP and its [ThinkPixelPlugin](https://github.com/bdobrica/ThinkPixelPlugin) integration. This is a **repository and delivery-experience renovation**, not an architectural initiative. [ThinkPixel](https://github.com/bdobrica/ThinkPixel) currently categorizes the Search/RAG lineage as a standalone adjacent component; no platform integration is required.

`TODO.md` is the ordered execution checklist. `AGENTS.md` is mandatory guidance for coding agents. This plan specifies intent and gates, not proof that tasks are completed.

### Operator deferral

On 2026-10-11, the operator removed unfinished makeover tasks from the active
TODO scope. The cluster and pods are needed for at least the next couple of
weeks, and the Hetzner VM quota prevents allocating capacity for scale tests.
No resumption date or maintenance window is scheduled. Further live acceptance,
publication and cutover work requires a new operator request.

The following original task IDs are deferred, not completed:

| Original IDs | Unverified or unperformed work |
| --- | --- |
| P3-03 | Complete safe dev plan and reviewed saved-plan apply |
| P3-04 | Guarded Flux attachment and ownership verification; read-only readiness already passed |
| P3-05 | Actual model-image build, publication and pull verification |
| P3-07, P5-04 | Valid existing-worker scale plan/recovery review and any separately authorized live scaling |
| P5-03 | Real WordPress/plugin ingestion-to-search acceptance and scoped cleanup |
| P5-05 | GitOps source switch to SR and verified switch-back |
| P5-06 | Parent ThinkPixel catalog publication |
| P5-07 | Final release qualification against the original live acceptance gates |

D-01/D-02 proposals remain outside makeover scope, as described in section 8,
and have also been removed from the active TODO. Historical evidence records
their status at the time of inspection; it is not an instruction to resume work.

The original gates and acceptance criteria below remain reference requirements
for any future deployment qualification. They have not all been met. The
[operator inspection](docs/evidence/phase-5/operator-machine.md) records recovered
Flux readiness; the [isolated plan review](docs/evidence/phase-5/dev-plan-review.md)
records legacy DNS refresh failure and an incomplete plan proposing replacement
of all five nodes. Preserve the live system, original state and rollback custody;
provider/API compatibility and any DNS-state migration need separate review.

## 2. Non-negotiable invariants

1. Preserve deployed behavior for API authentication, `/store`, `/search`, queue processing, embeddings, hybrid Qdrant retrieval and existing WordPress plugin integration.
2. Preserve the existing API gateway, MySQL, NATS, Qdrant, model-service and optional Redis roles. No replacement databases, message buses, embedding strategies, or service decomposition.
3. Preserve Terraform/Terragrunt and the Hetzner architecture, including cluster environments (`dev`, `prod`), node pools and load-balancer/network behavior; wrappers may supply inputs but cannot silently reinterpret them.
4. Preserve FluxCD as the source of truth for GitOps workloads. Do not introduce imperative deployments that compete with existing reconciliation.
5. Preserve infrastructure/resource identities, volume/data ownership, Kubernetes namespaces, secrets references, ingress/DNS, registry tags and persistent storage unless migration impact is reviewed.
6. No new ThinkPixelAG/AR/LLMGW/TG integration, API redesign, schema migration, runtime refactor or production architecture hardening in this project.
7. Never commit credentials, `.env`, SSH private keys, kubeconfigs, state files, populated `.secrets.hcl`, or generated secret-bearing output.
8. Retain licensing and attribution. Do not remove old repository/history until a verified migration and rollback strategy exists.

## 3. Baseline inventory and migration decision

Before implementation, inventory the **actual** current tree, including all Terraform and Terragrunt roots, provider/version pins, backend/state locations, CI workflows, Flux sources/kustomizations, Kubernetes clusters/namespaces/CRDs, Docker builds, image registries and tags, local development, database migrations, all `.secrets.hcl`/SSH key consumers, and known manual steps. Record command outputs or sanitized screenshots where useful.

Document a reference installation and execute an end-to-end check for the plugin -> gateway -> ingestion -> indexing -> retrieval path where credentials/environment exist. If access is unavailable, record the validation gap rather than treating the README diagram as test evidence.

**Repository cutover:** Prefer a history-preserving copy/new remote, keeping ThinkPixelInfra readable during transition. Audit absolute repository URLs in Flux GitRepository sources, CI, build automation, docs, image source references, webhooks and badges. Choose whether live Flux sources remain pinned to the old repository until an explicitly controlled cutover. Update the parent ThinkPixel component catalog and use-case links only once the new repository is real and usable; do not silently claim new maturity or platform integration.

## 4. Target operator interface

### 4.1 `.env` and configuration

Add `.env.example` with commented non-secret defaults and clearly named *local path* settings plus documented required variables. Maintain `ENV=dev|prod` or an equivalent single, validated environment selector for Make. Secrets are never mandatory as inline cleartext in `.env`: prefer standard environment injection or ignored local secret files, protecting the current Terragrunt `.secrets.hcl` contract. Keep a mapping table: `.env` key -> existing Terragrunt/Kubernetes/Flux variable -> consumer -> required/optional -> sensitivity. Do not duplicate or contradict authority across `.env`, Terragrunt files and GitOps declarations. Specify precedence (CLI explicit overrides > `.env` defaults > safe documented fallback) and fail on unknown envs/missing critical inputs. Ensure Make loads `.env` without unsafe shell evaluation and never prints secrets.

### 4.2 Command naming and safety

Use concise nouns and verbs, and prefer stable command families over cloud-provider names embedded in every target. Recommended interface:

| Target | Intent | Implementation constraint |
| --- | --- | --- |
| `make help` | List meaningful tasks and example arguments | Default target; never deploy |
| `make doctor` | Check required binaries, versions, and access prerequisites | Do not dump credential values |
| `make config-check ENV=dev` | Validate selected environment and inputs | Safe read-only checks |
| `make cluster-init ENV=dev` | Initialize existing Terragrunt root | Explicit environment selection |
| `make cluster-plan ENV=dev` | Show/save inspectable infrastructure plan | No automatic apply |
| `make cluster-up ENV=dev` | Apply a specifically reviewed plan | Explicit confirmation; prod extra guard |
| `make cluster-scale ENV=dev POOL=api COUNT=4` | Modify existing worker-pool count safely | Validate pool, prevent master/control-plane changes, preview reduction, confirmation; document review/rollback |
| `make flux-check ENV=dev` | Confirm cluster access and GitOps readiness | No bootstrap side effects |
| `make flux-bootstrap ENV=dev` | Bootstrap/attach existing Flux deployment | Guarded; preserve current GitRepository and reconciliation setup |
| `make images-build` / `make images-push` | Build/publish existing model image definitions | Require registry, immutable/reproducible tags; no floating `latest` by default |
| `make status ENV=dev` | Show selected cluster and Flux diagnostics | Read-only, secrets redacted |
| `make verify` | Run static gates and available smoke tests | Clearly distinguish offline and live checks |

Optional aliases can provide operator familiarity (e.g. `deploy-hetzner-cluster` -> `cluster-up`) but documentation should teach the canonical names. Do not implement `cluster-down` or automatic scale-down as a routine shortcut. Use `DRY_RUN=1` or explicit `*-plan` for previews where meaningful; a dry-run mode must not claim to validate runtime behavior.

**Scale-up versus scale-down:** Count adjustments belong to existing worker pools. For reductions, warn about workloads/PDBs, Qdrant/Redis/data placement, storage attachments, node drains, cluster quorum and cost/state changes. Do not promise zero downtime. Manual inspection and explicit approval are mandatory; safe automated drain requires separate validation and must not be guessed.

### 4.3 Secret and state handling

- Ignore `.env`, `.secrets.hcl`, private key files, kubeconfigs and Terraform state, including nested paths.
- Keep `.env.example` non-sensitive and check it with a secret scan.
- Keep remote-state configuration and credentials explicit; do not change backend/storage ownership during migration.
- Ensure logs, `make -n`, CI, command echo and exceptions do not expose credentials.
- Do not source arbitrary `.env` as shell code; use an explicit, validated format/loader or Make-safe parsing after evaluating limitations (quoting, whitespace, `$` and comments).
- Existing auth and database credentials retain their current consumers and lifecycle.

## 5. Documentation shape

The root `README.md` remains an overview and clearly labels planned commands until shipped. Keep durable reference documentation under `docs/`:

- `docs/architecture.md`: faithful as-built diagrams and API/store/search paths; optional Redis behavior accurately limited.
- `docs/configuration.md`: variable table, precedence, example values, secrets handling, environment differences.
- `docs/deployment/hetzner.md`: prerequisites, node access, DNS, Terragrunt and safe `plan`/apply order; dev and prod.
- `docs/deployment/fluxcd.md`: actual GitOps source layouts, bootstrap order, reconciliation and GitRepository cutover.
- `docs/operations/scaling.md`: worker pool adjustment, plan review, drain implications, reduction safeguards and reversal.
- `docs/operations/images.md`: model Dockerfile inventory, build platforms/architectures, tag/push destinations, registry login and manifest references.
- `docs/operations/verification.md`: offline checks, live health checks, actual plugin ingestion-to-search smoke procedure and rollback criteria.
- `docs/operations/troubleshooting.md`: categorized diagnostics for infrastructure, Flux, image pull, queue, embedding, Qdrant and gateway.
- `docs/migration.md`: old-to-new mapping, references, Git history strategy, progressive cutover, rollback.
- Optional `docs/adr/` only for genuinely new approved decisions; this effort should largely **record** existing decisions rather than create architecture.

## 6. Implementation phases and gates

### Phase 0 — Freeze and baseline

Complete inventory, baseline configurations and reproducible test cases. **Gate:** known-good deployment/WordPress use case recorded and a list of unverified assumptions maintained.

### Phase 1 — Repository creation and lineage

Create ThinkPixelSR preserving license, provenance, and preferably Git history; establish baseline diff and migration/cutover strategy. Rename documentation-facing identifiers, not runtime identifiers by default. **Gate:** source code and deployment behavior match the baseline; old links stay operational.

### Phase 2 — Configuration surface

Implement `.env.example`, `.gitignore` and local config validation/translation without modifying underlying service architecture. Test multi-environment selection, secret protection, paths and failure cases. **Gate:** repeatable, audited mapping to existing input files and no secret leaks.

### Phase 3 — Makefile wrapper

Add help/doctor/check and safe Terraform preview first; then guarded apply, Flux workflow, image build/push and scaling. Wrappers must **call existing tools**, not replace them. Document destructive and remote side effects. **Gate:** Make's plan targets match direct existing commands; no live action occurs on help/check/preview; deliberate dev workflow passes.

### Phase 4 — Documentation

Write as-built architecture, configuration, deployment, scaling, image and runbook documentation; link from root README. **Gate:** a reader can deploy to dev using docs without reverse-engineering code; docs reflect implemented target names.

### Phase 5 — Validate and cut over

Run static checks, `dev` deployment/Flux smoke tests, and a real ThinkPixelPlugin ingestion/search flow; inspect rollback and zero-drift baseline. Stage new Git source references with explicit approval. Update parent ThinkPixel catalog and release notes after verification. **Gate:** documented reproducible golden path, retained rollback, no unintended service/architecture changes.

## 7. Acceptance criteria

- Four root governance/orientation files present and coherent: `README.md`, `PLAN.md`, `TODO.md`, `AGENTS.md`.
- `.env.example`, `.gitignore` and Make targets exist, accurately documented and validated.
- All deployment and scaling operations use existing Terraform/Terragrunt/Flux conventions; the same running MVP remains operational.
- `make help`, `make doctor`, `make config-check`, `make cluster-plan` and `make verify` are safe without credentials or deployment, subject to clearly identified checks.
- An authorized operator can reproduce a Hetzner dev deployment, connect Flux, publish existing images, scale workers with plan review and verify search from the plugin.
- Production mutations, node reductions and Git source cutover are deliberate, reviewable and reversible where feasible.
- No accidental secrets, Terraform state, or runtime data enter Git.
- All docs mark unsupported or unverified procedures rather than asserting success.

## 8. Out of scope and later work

No API changes, new hybrid-search algorithm, embedding model switch, data/schema migration, storage redesign, CI/CD overhaul, high-availability redesign, platform-agent integration or feature expansion. If discovered defects prevent reliable deployment, log a focused follow-up and seek approval rather than hiding a runtime refactor inside this makeover. The parent ThinkPixel agent demo remains independent.

## Authorized standalone MCP extension

The operator requested an optional Dockerised FastMCP search/store bridge under
`docker/mcp`, backed by the Python SDK and an existing environment-supplied key
and gateway URL. This scoped addition permits an additive async SDK; it does not
resume infrastructure tasks, change the gateway contract or integrate the
ThinkPixel agent runtime. See [MCP setup](docker/mcp/README.md).
