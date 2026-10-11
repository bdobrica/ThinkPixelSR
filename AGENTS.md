# AGENTS.md — ThinkPixelSR coding-agent instructions

This repository is **ThinkPixelSR**, the history-preserving continuation of [ThinkPixelInfra](https://github.com/bdobrica/ThinkPixelInfra) and a standalone Search/RAG member of the [ThinkPixel](https://github.com/bdobrica/ThinkPixel) ecosystem.

**Your mission during the current makeover is to improve repository usability, deployment ergonomics, configuration and documentation while preserving the existing working hybrid-search MVP.** Prefer the smallest coherent change. Do not opportunistically refactor application code, introduce architecture, or claim unverified deployment success.

## Read before changing anything

1. Read `PLAN.md` for scope, invariants, phases and acceptance criteria.
2. Read `TODO.md` for the earliest incomplete and relevant task; work in chronological order unless explicitly instructed otherwise.
3. Read the root `README.md` and the existing files/scripts relevant to the requested change; never assume README claims are evidence that commands exist.
4. Inspect the exact Terragrunt (`cluster/live/{dev,prod}`), Kubernetes (`k8s/`), Flux, Docker (`docker/`), database and workflow files affected by your change.
5. Consult `docs/adr/` and published contracts if present. The wider ThinkPixel catalog documents ecosystem membership, **not** a mandate to integrate agent services.

For **intended architecture and behavior**, follow: accepted ADRs (if any) -> published contracts -> normative architecture/security documentation -> `PLAN.md` -> `TODO.md` -> `README.md`. Existing code/manifests and baseline tests provide evidence of what actually runs. If written intent conflicts with running behavior, report it and preserve working behavior pending an explicit decision; do not silently redefine either.

## Non-negotiable boundaries

- **No architecture redesign.** Keep gateway/auth, MySQL, NATS ingestion, embedding models, Qdrant hybrid retrieval, optional Redis backend, Terraform/Terragrunt Hetzner provisioning and FluxCD deployment behavior.
- **No application rewrite.** Do not modify APIs (`/search`, `/store`), schemas, migrations, business logic, embedding models, queue semantics, storage formats or plugin interfaces under the disguise of a docs/deployment task.
- **No automatic ThinkPixel integrations.** SR remains standalone/adjacent. Do not import responsibilities of AG, AR, LLMGW, TG, WS or MEM; do not invent shared APIs or credentials.
- **No dangerous rename cascade.** Renaming the GitHub repository/documentation does **not** authorize renaming namespaces, services, ingress, state backends, databases, volumes, image repositories, Terraform resources or Flux Git sources.
- Keep `ThinkPixelPlugin` in its own repository; its existing observable search/indexing flow is a compatibility gate.
- Preserve LICENSE, authorship and history. Work on focused commits/PRs.

## Makefile and configuration standards

- The default `make` action is `help`, never deployment.
- Implement only commands whose underlying working invocation you have inspected. Wrappers invoke existing Terraform/Terragrunt/Flux/Docker commands and must not create a second deployment system.
- Always require and validate environment selection for live commands; constrain choices to actual environments and never silently fall back from `prod` to `dev` or vice versa.
- Separate preview (`cluster-plan`, `flux-check`) from change (`cluster-up`, `flux-bootstrap`, `images-push`, `cluster-scale`). All changing commands must state their target and side effects, and require explicit approval where appropriate.
- A plan is not an approval. Avoid `-auto-approve` without reviewed, human-authorized conditions. Never add a casual `destroy`/`down` target.
- Scaling operates only on **existing worker pools**. Do not change control-plane quorum or shrink worker capacity automatically. For reductions, inspect workload placement, storage, disruption budgets and draining requirements; never promise zero downtime.
- `.env.example` has no secrets. `.env` stays local and ignored. Map configuration to **existing** consumers and document precedence. Validate paths and required values without echoing credentials. Do not execute arbitrary `.env` lines as shell code.
- Keep secrets, `.secrets.hcl`, SSH private keys, kubeconfig, state, tokens, registry credentials and generated sensitive output out of Git, logs, CI artifacts and examples. Take care with `make -n`, shell tracing and exceptions.
- Ensure image build and push commands use exact checked-in Dockerfiles, relevant build architectures, documented registry and explicit tags. Do not silently use mutable `latest`.
- Do not assume the operator has access to Hetzner, cluster credentials, registry, Flux Git credentials or production. Work offline where possible and clearly identify environment-gated verification.

## Documentation standards

- Keep `README.md` a truthful entry point: purpose, status, architecture overview, quick start, links. Do **not** duplicate the full plan.
- Keep `PLAN.md` as project strategy and gates; `TODO.md` as ordered, actionable work. Mark tasks done only when acceptance evidence exists; do not treat these files as changelogs.
- Put lasting setup and operations instructions under `docs/`. Include actual commands, prerequisites, expected observable results, common failures, secret handling and recovery where relevant.
- Use relative links for local docs, Mermaid for conceptual diagrams, and clearly distinguish implemented, planned and unverified behavior.
- Do not assert Redis parity with Qdrant hybrid search. Do not claim the current MVP is production-qualified or integrated with the ThinkPixel agent-runtime path.
- Move durable verification evidence to `docs/evidence/` if such a directory is established. Sanitize IPs, tokens, hostnames and payloads where needed.

## Verification policy

For each change:

1. Inspect scope and identify the smallest relevant tests before editing.
2. Validate shell/Make/YAML/HCL syntax and `make help`, `make doctor`, `make config-check` when implemented.
3. Compare wrapper preview output to underlying direct commands; verify no mutation from `help`, `config-check`, `cluster-plan` or `verify` (except documented local/backend init effects).
4. Test both `dev` and `prod` selection and missing/invalid configurations without real tokens.
5. Review diffs for service behavior, manifests, infrastructure identity drift, accidental secrets and broken documentation links.
6. Run live deployment, registry push, Flux bootstrap, scaling or plugin smoke only with appropriate credentials and explicit user/operator permission. Such operations can incur cost or downtime.
7. State exactly what ran, what passed, what was skipped and why. Never fabricate verification results.

A docs-only task may be completed with documentation and link review. Do not change production just to validate prose.

## Task execution and handoff

- Pick the earliest relevant unchecked `TODO.md` item; keep its ID visible in your change description.
- Describe files affected, baseline expectations and risks before making wide changes.
- Make a focused change and preserve old paths/behavior by default.
- Update `TODO.md` only after acceptance criteria are met; update `PLAN.md` only when actual sequencing or scope has legitimately changed.
- Summarize changes, verification commands/results, limitations and any live actions not taken.
- Report unrelated bugs as separate proposals. When the task permits commits, use concise prefixes such as `docs:`, `build:`, `ci:`, or `fix:` and avoid unrelated work in the same commit.

**Escalate rather than improvise:** If satisfying a request appears to require an API change, persistent-state move, database migration, new service, control-plane alteration, new inter-repository dependency, unexpected prod mutation, or removal of a rollback path, stop that part of the task and propose a separately reviewed decision. The overriding principle is **keep the working system working**.
