# Phase 1 — local lineage and import evidence

P1-02 through P1-04 are implemented. P1-01's local history-preserving import is
implemented, and authenticated checks confirm the existing **public** GitHub
repository main matches the frozen source. Publication of the reviewed
continuation and release tags is the remaining acceptance check. No remote
creation, Actions change or GitOps cutover occurred. This evidence does not resolve the
[Phase 0 live-validation gaps](../phase-0/README.md).

## Inputs and scope

| Input | Recorded result |
| --- | --- |
| Source | `../ThinkPixelInfra`, frozen main `9e5fc87495832d3a2554965341cbeb43911ff5f5` |
| Starting destination | Unborn main, no remotes; existing user governance documents and completed Phase 0 documentation |
| Import method | Local `git archive` of the committed tree; original main/tag objects imported using local Git fetch; index initialized from the frozen tree without overwriting working files |
| Retained history | 265 main commits; four original release tags; 267 commits reachable from main plus those tags; original object IDs/authorship preserved |
| Excluded material | Ignored secrets/private keys, untracked `docker/api_gateway.zip`, caches, `.git` config/reflogs and experimental branch refs |
| Remote settings | `origin` points to existing public ThinkPixelSR; authenticated remote main equals the frozen source; `thinkpixelinfra` records the old GitHub URL |
| Continuation changes | Working-tree documentation changes; no new commit or staged documentation |
| Source/plugin | Their working files, refs and remotes remain unchanged |

The [comparison table](baseline-diff.tsv) has one row for every frozen tracked
file. **403 files are byte-identical** to the committed baseline. The only two
changed inherited files are `README.md` and `cluster/README.md`; changes are
names, links and explicit inherited-setup limitations. All 405 original paths
remain present, and their Git index modes are retained. The mounted filesystem
reports mode 777 even after chmod; `core.filemode=false` already existed, so
mode preservation is checked through Git objects/index rather than filesystem
permission bits. The first filesystem-mode comparison failed for that reason;
it was replaced by the index comparison, not by changing source permissions.

LICENSE, all application code, API/schema/SQL, Dockerfiles, workflow, deployment
manifests, Terraform/Terragrunt files, public SSH keys, locks and inherited
ignore/attribute files are unchanged. Flux sync and GitHub notification URLs
still target ThinkPixelInfra. No file in an ignored/untracked sibling path was
imported. The original README is retained in history. PLAN.md and AGENTS.md
remain unchanged; TODO.md and README.md reflect implemented versus pending work.

## Offline checks

| Check | Result |
| --- | --- |
| All 405 source paths against frozen Git blob inventory | PASS: 403 exact matches, two approved documentation changes; index path/mode/blob equality with frozen tree |
| Original main ancestry and four release-tag objects | PASS: exact object ID comparison; 265 main / 267 including tagged side history; no shared Git alternates |
| `git fsck --no-reflogs` | PASS: imported Git objects/connectivity |
| `git diff --exit-code <baseline> -- LICENSE cluster/infra cluster/live k8s docker database local debug .github .gitignore .gitattributes` | PASS: no inherited runtime/build/license changes |
| `git diff --cached --exit-code <baseline>` | PASS: index contains the unchanged original tree; makeover edits remain reviewable |
| `make -C local help` | PASS; local help only, no service startup |
| `docker compose -f local/docker-compose.yaml config --quiet` | PASS; no daemon or secret-bearing rendered output |
| `terraform -chdir=cluster fmt -check -recursive` | PASS; no init/provider download/state/backend/plan |
| `kubectl kustomize` for Flux dev, thinkpixel dev, monitoring dev | PASS; rendered output discarded, never applied |
| `kubectl kustomize` for thinkpixel/monitoring prod | FAIL as baseline: empty kustomizations; no fallback to dev |
| `bash -n` on inherited shell files | PASS: 16 scripts, no script executed |
| Python `ast.parse` | PASS: 81 inherited Python files, no imports/model loading |
| Gateway `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOCACHE=/tmp/thinkpixelsr-p1-go-cache go test ./...` | PASS: auth, config, db, document_queue, logger, utils suites; remaining packages compile without tests; cached dependencies only |
| Relative links, Markdown fragments, Bash fences and whitespace in root/new/revised docs | PASS; documented live commands syntax-checked only; publication commands additionally checked against the actual remote |
| Rollback patch generator | PASS against synthetic baseline-shaped snapshots and mismatch/reordering cases; never connected to Kubernetes |
| Source/plugin before/after status and source/tag provenance | PASS; no sibling changes |

Phase 0 already records the unchanged dev Terragrunt formatting failure and
strict loading failures for three dev overlays; these checks were not rerun
because the affected files are byte-identical. Root `make help`, `doctor` and
`config-check` do not exist yet and were not claimed to pass. No Phase 2
configuration/ignore changes or Phase 3 wrappers were introduced.

## Limited secret review

The main-plus-release-tag history scan inspected **1,201 unique blobs** and
historical path names. It found no `.env`, `.secrets.hcl`, private `.key`,
kubeconfig or Terraform-state path candidates. One historical PEM private-key
marker (`cluster/cloud-init/worker.yaml`, blob
`b5153297301d5e924deb03fd927c89638dd73ca7`) contains only an angle-bracket
placeholder, not key material. Current documents/indexes were also reviewed for
private-key blocks and credential-shaped values. No secret values or encrypted
payloads are copied into evidence.

This is a limited pattern/path review, **not** a comprehensive secret scanner
or certification of the inherited history. Gitleaks is unavailable; a
comprehensive scanner remains unrun. Do not rewrite history without a separate
decision if later scanning finds actual credentials. Existing default/example
credentials and logging risks remain the inherited Phase 0 follow-ups.

## External and live limits

Initial read-only access lacked authentication. The user then installed
**gh 2.46.0** and logged in. With approved network access, `gh auth status`,
`gh repo view`, the commit/tree API and `git ls-remote origin` confirmed the
existing public repository main is exactly the frozen source commit. No
repository creation or history reconciliation is needed. P1-01 remains open
until the reviewed continuation/tags are pushed and remote tree verified.
See [publication steps](../../migration.md#publication-once-authenticated-access-is-available).

The Actions permissions API reports enabled/all. Settings and workflow remain
unchanged: this is a fast-forward continuation from the existing baseline,
not an initial all-zero-before source push. No `.bumpversion.cfg` changes are
included, so the inherited image-build loop should be empty. Check the workflow
result after publication; workflow success is not inferred from this review.

The [migration guide](../../migration.md) records unchanged live sources,
coexistence, publication precautions for the inherited Actions workflow,
Phase 5 switch gates, private rollback capture and exact owner-resource
switch-back commands. The rollback generator was exercised offline; the
cluster procedure is **unverified**, depends on observed owner/resource names
and operator credentials, and makes no atomic-recovery or zero-downtime claim.

No Terraform init/plan/apply, cloud query, state/key relocation, image build/push,
Actions API change, Flux bootstrap/reconcile/suspension/patch, Kubernetes apply,
SQL migration, Docker service startup, plugin smoke or parent-catalog change
was performed. Old repository links and both sibling checkouts remain available.
