# Phase 0 evidence and validation gaps

Recorded 2026-10-11 for P0-01 through P0-06. The documentation baseline is
complete; a **known-good live deployment/plugin run has not been established**.
P0-06 uses its permitted explicit blocker-record outcome. This does not satisfy
the live golden-path acceptance gate in PLAN.md or authorize the later cutover.

## Frozen inputs and scope

| Input | Observation |
| --- | --- |
| ThinkPixelInfra | Local `../ThinkPixelInfra`, commit `9e5fc87495832d3a2554965341cbeb43911ff5f5`; 405 tracked files |
| Source working-tree delta | No tracked changes; one untracked `docker/api_gateway.zip`, excluded. Ignored local secrets/private keys were not exported or read |
| ThinkPixelPlugin | Local `../ThinkPixelPlugin`, commit `b8f64d05cbe11a58dbf7f7dcee0f5dce271d7d63`; clean tracked working tree; inspected read-only |
| ThinkPixelSR starting point | Unborn `main`, no commits or implementation files; four untracked root documents supplied by the user |
| Check method | Export only tracked source at the frozen revision to a temporary directory; run offline checks there. No sibling source file changed |
| Secret handling | No `.env`, secret values, private keys, kubeconfig, state, tokens, database dumps, raw request logs or sealed payloads copied into evidence |

[source-tree.tsv](source-tree.tsv) records each source file's path, mode, Git blob
ID and byte size. Git blob IDs identify content in retained history; they are not
SHA-256 secret hashes. The index can be compared to a later Phase 1 import without
copying any runtime files now. [manifests.tsv](manifests.tsv) records top-level
manifest kind/name/namespace/image metadata only, including empty files and
implicit Kustomizations. Nested resources inside ResourceSets and generator
outputs are described in the [GitOps map](../../baseline/gitops.md), not expanded
as installed objects in that index. Neither index asserts cluster observation.

The public synthetic fixtures are [store.json](store.json),
[search.json](search.json), and [remove.json](remove.json). Their expected
responses, WordPress procedure and scoped cleanup are in the
[verification specification](../../operations/verification.md).

## Checks actually performed

| Check / invocation on tracked-only export | Result / practical limit |
| --- | --- |
| `git status --short`, `git rev-parse HEAD`, `git ls-tree -r --long <revision>` on source | Captured revision, tracked inventory and source delta; source left unchanged |
| Inspection of Terraform/Terragrunt, K8s/Flux, Docker, SQL, scripts/workflow and plugin client | Dependency, config, migration, image and smoke maps written against files; no ADR/contracts or CODEOWNERS in source |
| `make -C local help` | PASS (exit 0); local default is help, no Docker action |
| `docker compose -f local/docker-compose.yaml config --quiet` | PASS (exit 0); validates Compose configuration without daemon use or credential output |
| `terraform -chdir=cluster fmt -check -recursive` | PASS (exit 0); HCL formatting/parser check only; no init, provider download, state or plan |
| `terragrunt hcl fmt --check --working-dir cluster/live` | FAIL (exit 1): dev `terragrunt.hcl` needs formatting; left unchanged. Empty prod syntax is not usable configuration |
| `kubectl kustomize k8s/flux-system/dev` | PASS (exit 0) |
| `kubectl kustomize k8s/apps/thinkpixel/dev` | PASS (exit 0) |
| `kubectl kustomize k8s/apps/monitoring/dev` | PASS (exit 0) |
| Strict `kubectl kustomize` for cert-manager, reflector and nats dev | FAIL (exit 1 each): individual base files outside overlay rejected by local load restriction |
| Same three dev renders with `--load-restrictor=LoadRestrictionsNone` | PASS (exit 0 each); does not prove Flux controller behavior or Helm/CRD availability |
| `kubectl kustomize k8s/apps/thinkpixel/prod`, `.../monitoring/prod` | FAIL (exit 1 each): `kustomization.yaml is empty`; Flux prod overlay absent |
| `bash -n` on all tracked `.sh` files | PASS: 16 scripts; no script body executed |
| Python `ast.parse` on all tracked `.py` files | PASS: 81 files; no imports, bytecode, model downloads or inference |
| `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOCACHE=<temporary cache> go test ./...` from gateway module | PASS (exit 0): auth, config, db, document_queue, logger, utils suites; remaining packages compile but have no tests. Used installed/cached dependencies, no network download |
| New Markdown relative links, fixture JSON, inventory consistency, whitespace and credential-pattern review | See final validation below; no live assertions |

The initial Terraform check with an absolute path failed path resolution in this
workspace; the corrected `-chdir` invocation above passed. That initial tooling
failure is not an infrastructure defect. Rendered YAML was never applied or
published as an artifact. Full logs stay outside Git because logs and renders
are not required to establish these sanitized results.

Tool versions: Terraform **1.14.3**, Terragrunt **0.96.1**, Go **1.24.10**,
Docker Compose **2.40.3**, kubectl **1.32.3** / built-in Kustomize **5.5.0**.
Standalone Flux/Kustomize, shellcheck, gitleaks, pytest and YAML/HCL Python
parsers were unavailable. Only kubectl client/Kustomize operations were invoked;
no cluster credentials/context were queried. Model tests and pre-commit hooks
were skipped because their dependency environments were not installed for this
documentation task. No tools were downloaded.

## Baseline configuration and unresolved assumptions

The sanitized [infrastructure table](../../baseline/infrastructure.md),
[GitOps/storage/secret map](../../baseline/gitops.md) and
[image map](../../baseline/images.md) capture checked-in **intent**. They are
not an export of a running dev installation. The project's description of a
working MVP is retained as project context, not relabeled as a test result.

| ID | Gap / source evidence | Required next evidence or separately reviewed follow-up |
| --- | --- | --- |
| B01 | No live dev/WordPress session authorized; ignored source credentials exist but validity/access are unknown | Operator-approved dev endpoint, installed image/chart revisions, active test site, safe fixture run and sanitized results |
| B02 | Prod Terragrunt and app overlays empty; no Flux prod directory | Explicit production configuration decision; never substitute dev |
| B03 | Base SQL v0.1.0 lacks newer gateway columns; local `db-init` skips v0.1.8 patch and seeds `master_name` | Focused local setup repair and fresh/disposable DB validation, preserving existing live schema |
| B04 | `database/init.sh` queries/updates `wp_thinkpixel_db_versions`; base SQL creates `wp_thinkpixel_db_version` | Reviewed migration bookkeeping repair; do not infer live DB version or apply patches blindly |
| B05 | No backend declaration; local/cache state and operator backend inputs not inspected | Locate authoritative state/workspace, preserve recovery copy and identities before any init/plan in a migrated checkout |
| B06 | No initial Flux Operator/Sealed Secrets controller or Git credential installation command | Document actual bootstrap, CRDs, account permissions, decryption key custody and reconciliation source revision |
| B07 | Strict local rendering fails for three dev overlays; chart/Flux versions float | Establish actual Flux build/install behavior and chart/image revisions; local permissive render alone is insufficient |
| B08 | NATS Core, no queue group, latency-driven subscription toggling | Observe subscriber active before publish and confirm indexed points; 202 is not a durable-ingest guarantee |
| B09 | Worker resource flattens multiple pools into shared count indices | Review all replacements on a future scale plan; adding to api may affect monitor identity |
| B10 | Qdrant local-path and snapshot PVC references; monitoring hostPath; Redis lacks K8s data PVCs | Inspect live PVC binding, node placement, backups/drain implications; no zero-downtime claim |
| B11 | Gateway readiness checks only DB; search handler waits 10s while dev model timeout is 180s | Confirm model warm-up/retrieval, record actual latency and separate dependency health |
| B12 | Plugin `/searchpixel/v1/` callbacks differ from gateway/mock defaults `/thinkpixel/v1/`; plugin compiled gateway URL | Verify test plugin build and matching dev callback settings without modifying the separate plugin |
| B13 | Plugin falls back to submitted IDs; gateway returns pending IDs and permits partial publication | Compare actual queued/indexed post IDs and WordPress search results, not just the plugin's processed count |
| B14 | `/refresh/apikey` and `/store/max_batch_text_size` read `db.APIKeyDetails` but JWT middleware sets `auth.CacheEntry`; batch-size response `size` differs from plugin expectation `max_batch_text_size` | Focused runtime/compatibility bug proposal; excluded from minimum API smoke and unchanged here; plugin uses fallback batch size |
| B15 | JWT default secret fallback, plaintext API key in JWT claim, sensitive registration/debug/request logging; SSH private keys embedded in cloud-init without sensitive variable annotations | Preserve existing behavior; handle tokens/logs/plans/state privately and review credential/log handling separately |
| B16 | Model assets/native dependencies and external-service configuration untested; local MySQL/Qdrant versions differ from K8s | Authorized builds/pulls/inference at exact deployed revisions; no cross-backend parity or production qualification |

No live Terraform init/plan/apply, cloud API query, Flux bootstrap/reconcile,
registry build/push/pull, scaling, SQL initialization/migration, Docker service
startup, network API smoke, debug extractor or WordPress test was performed.
Their omission follows the repository requirement for explicit operator
authorization, not an assertion that credentials are absent. P0 establishes the
source freeze and explicit validation gaps; runtime acceptance remains open.

## Final validation

Passed Markdown relative-file/fragment link and whitespace checks, JSON parsing
and fixture/cleanup ID consistency, comparison of all **405** source inventory
entries with the frozen Git tree, and manifest-index coverage of all **100**
tracked Kubernetes YAML files (**108** document/index rows). A limited
credential-pattern scan of new documents, fixtures and indexes found no private
key blocks or credential values matching the checked patterns; this is not a
full gitleaks audit. Source and plugin tracked working trees remain unchanged.
ThinkPixelSR changes are documentation, synthetic JSON fixtures and metadata
inventories only; no service/manifests/infrastructure identity drift was introduced.

Final checks covered **45** relative links across eight Markdown files (including
README and TODO), `git diff --no-index --check` on task documents/artifacts, and
`bash -n` on all **seven** documented Bash blocks without executing them. Source
working-tree comparison accounts for `.gitattributes` text/LF normalization;
the source export and inventory always identify committed blobs, not local CRLF
checkout bytes. No source line-ending changes were made.
