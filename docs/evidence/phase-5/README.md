# Phase 5 validation and cutover preparation

**Current scope:** On 2026-10-11 the operator removed unfinished items from the
active TODO and deferred further acceptance/cutover work. See the
[deferral decision](../../../PLAN.md#operator-deferral). The unchecked/pending
statuses below are historical acceptance records, not active tasks. Later
[machine inspection](operator-machine.md) and [plan review](dev-plan-review.md)
record Flux recovery and an incomplete unsafe infrastructure plan.

Phase 5 is **partially complete**. Offline validation and a precise dev lifecycle
blocker record are complete; live plugin/scaling acceptance, source cutover,
parent publication and final PLAN acceptance remain open. The checks below
describe the implementation-time checkout before the follow-up local commit
pass for Phases 2–5. No deployment, fixture write, image push, live source switch
or repository publication ran here.

## P5-01: baseline and publication candidates

The frozen ThinkPixelInfra revision is
`9e5fc87495832d3a2554965341cbeb43911ff5f5`. The
[405-file comparison](baseline-diff.tsv) was generated from Git blob IDs and
current file bytes. **401 inherited files are byte-identical.** The four
reviewed exceptions are root README, cluster README, `.gitignore` and dev
Terragrunt HCL. The dev change is formatting plus six optional credential/key
path hooks; removing those exact hooks reproduces the original HCL. The
existing real Terragrunt synthetic-input test also compares effective inputs.

Application code, API/auth/business logic, SQL, model code/assets definitions,
Dockerfiles, workflows, Terraform resources/lockfiles/public keys, prod roots,
Kubernetes/Flux manifests and LICENSE retain frozen bytes and index modes.
The baseline gate rejects inherited file removal, runtime edits, unexpected
new runtime paths, symlinks and dev input/identity changes. Added candidates
are restricted to the reviewed governance, dotenv example, Make, scripts,
tests and docs paths. This is a repository comparison, not a cloud drift check.

`make verify` now includes [the repeatable audit](../../../scripts/audit.py).
It reads tracked and nonignored candidate files, including currently untracked
makeover files, and never scans ignored operator credentials or stages files.
The secret check rejects sensitive file paths and limited high-confidence
private-key, GitHub token, AWS access-key and NATS seed patterns. All candidates
passed. It is **not** an entropy/generic-password scanner, full Git history
scan, credential-validity check or guarantee of no secrets. Gitleaks was not
available on PATH; no scanner or dependencies were downloaded. The original history
and encrypted SealedSecrets are retained, not decrypted or rewritten.

Run from a full history checkout:

```bash
make help
make doctor
python3 -B scripts/audit.py
make verify
git diff --check
```

Six audit regression tests cover runtime removal/change, dev identity drift,
secret redaction, ignored-file privacy, unexpected runtime additions and an
unavailable baseline. Missing frozen history fails the audit explicitly;
use a full clone rather than treating a shallow checkout as verified.

## P5-02: documented dev lifecycle walkthrough

These are the observed results and first unmet prerequisites, in lifecycle
order. No ignored files from ThinkPixelInfra were borrowed. GitHub login does
not establish Hetzner, Kubernetes, registry or WordPress access.
The operator confirmed the existing dev configuration is not on this machine;
offline validation can proceed here, while actual acceptance must run from an
authorized operator environment. No credential transfer is required for these
offline results.

| Step | Observed result or precise blocker | Required next evidence |
| --- | --- | --- |
| help / doctor / verify | Local discovery and offline gates pass | Local versions only; access is not checked |
| config-check dev | Exits 2: SECRETS_FILE missing/unreadable in the unconfigured checkout | Operator-owned dev credential/key paths and successful local validation |
| config-check / plan prod preview | Exit 2: prod is unimplemented, no fallback | A separately reviewed prod configuration; excluded here |
| cluster-plan dev | Not run against a provider/backend; synthetic forwarding and guards pass | Authoritative state/cache/workspace and recovery custody, matching SSH keys and cloud/DNS access; authorization to contact dev backend |
| cluster-up dev | Not run; exact-plan/confirmation/tamper/single-attempt guards pass offline | Reviewed real saved plan/hash, explicit approval and private apply result |
| Flux attach/reconcile | No cluster queried or modified; root render and preview pass | Explicit dev context, existing Flux Operator/CRDs, original SealedSecrets decryption key/controller, Git credential and authorized attachment; current-generation applied revisions |
| application bootstrap | No schema or data initialized | Existing compatible MySQL schema/index-node allocation and actual PV binding; fresh schema/installer gaps B03/B04/B06 require separate review |
| image pull | No build, push, registry manifest lookup or cluster pull | Approved exact image refs/platforms/digests, registry access and observed pod image IDs; existing images may be used without an unnecessary push |
| status / health | Only command previews and synthetic tests | Explicit dev context/HTTPS origin and authorized actual readiness; health alone checks DB, not indexing |

The [Hetzner](../../deployment/hetzner.md), [Flux](../../deployment/fluxcd.md)
and [image](../../operations/images.md) guides remain the executable procedures.
These blockers satisfy P5-02's explicit blocker-record alternative, **not** the
live Phase 3/4 or final Phase 5 gates.

## P5-03 and P5-04: plugin and scaling acceptance still open

ThinkPixelPlugin remains a separate, unchanged repository. No WordPress site,
gateway credential, compatible live schema/node assignment or authorized
disposable fixture session was provided. The frozen plugin source/procedure
and B12–B14 limitations remain in [verification](../../operations/verification.md)
and [baseline blockers](../phase-0/README.md#baseline-configuration-and-unresolved-assumptions).
There is no baseline live result to compare against. Registration, actual post
ingestion, indexed IDs, frontend semantic/exact search and scoped deletion all
need observed results. No synthetic test is presented as that golden path.

Existing dev defaults are api=3, monitor=1, master=1, all cax21. The worker
module shares count indices across pools; api expansion can replace monitor
workers. Offline tests exercise persisted counts, unsupported/control-plane
pools, zero/reductions, mismatched before/after JSON and cross-pool replacement
acknowledgments. No real Terraform scale plan, actual current counts, placement,
PDB/PV/backup inspection or drain occurred; P5-04 remains unchecked. Recovery
uses a fresh reviewed plan restoring desired existing-pool counts, with data
restoration handled separately; see [scaling](../../operations/scaling.md).

## P5-05 and P5-06: concrete unapplied review patches

- [GitOps cutover patch](gitops-cutover.patch): only FluxInstance sync URL and
  notification ResourceSet Provider address change to ThinkPixelSR. Names,
  ref/path/secret, tenant ownership, images and storage stay byte-identical.
- [Parent catalog patch](parent-catalog.patch): prepared against published
  ThinkPixel main `129f113a54355cd4d6bd2c503dececcc2c763db2`. Changes canonical
  adjacent repository name/URL and two human-facing links, retaining `id: infra`,
  the Infra lineage, standalone status and undefined agent-platform boundary.
  No maturity, ownership, integration or platform-release claim is added.

Both patches pass `git apply --check` against their intended trees. Neither is
applied to this checkout, the parent repository or a cluster. The parent sibling
is absent; public files were read through authenticated GitHub API, with its
AGENTS, alignment, catalog and release guidance inspected. Read-only API checks
confirmed published ThinkPixelSR main was still
`2f678f085b87240b1713d8d51d8ae89c57ad987d`; the local Phase 2–5 additions
are not yet published. Public GitHub access does not establish source-controller
access through `github-token`. No maintenance window was scheduled or guessed.

[Six render comparisons](render-checks.tsv) compare frozen, working and proposed
trees with kubectl 1.32.3. All current renders equal frozen renders. Applying the
actual cutover patch in an isolated temporary tree changes exactly two URLs
in the Flux root render; all five tenant renders remain byte-identical. The
cert-manager, reflector and NATS offline renders retain LoadRestrictionsNone;
this does not establish live Flux build behavior. No rendered secret ciphertext
or private resource output is included in evidence.

The migration guide contains [staging and cutover decision](../../migration.md#phase-5-review-patches-and-cutover-decision)
and owner-resource [switch-back](../../migration.md#exact-switch-back-steps-after-a-failed-cutover).
The rollback JSON generator was replayed with private synthetic owner snapshots
and restores old sync/notification settings. This validates its local transform,
not live operator behavior, access, suspension, reconciliation or data recovery.
Keep old source/main, credentials, state and decryption-key custody intact.

## P5-07: release review and final gate

[Unreleased operator notes](../../releases/operator-makeover.md) distinguish
offline-verified commands from live-pending operations. Docs links, script
syntax/tests, dev render comparisons and cross-file status claims were reviewed.
The PLAN acceptance criteria are **not all met**: the authorized reproducible
dev deployment/image/scaling/plugin path and source recovery remain unobserved.
P5-07 stays unchecked; no release tag or tested platform manifest was created.

Before closing Phase 5, replace the relevant blocker rows with sanitized actual
results and exact revisions/digests; complete plugin and real scale-plan review;
publish reviewed local changes; confirm controller access, old source retention
and recovery; approve a dev cutover window; apply/publish the two-owner change;
observe current-generation source/root/tenant reconciliation and plugin behavior;
verify switch-back; then publish the parent correction and final release notes.
Any actual baseline exception requires a focused review, not disabling the audit.

## Checks run

- `make help`, `make doctor`, `make verify`, direct audit and `git diff --check`.
  Offline suite: **42 tests**, including six new audit regressions, no skips.
- Python, Make and Bash syntax, Terraform formatting, dev HCL formatting,
  **218** relative links/fragments and six dev Kustomize roots passed.
- Actual dev missing-file and prod rejection results recorded above; valid
  dev and invalid input/secret/selection cases use the synthetic suite.
- Two unapplied patches passed applicability checks; frozen/current/proposed
  renders and synthetic owner rollback passed as described above.
- **61** documentation Bash examples passed syntax checks only. None were executed
  as live deployment, SSH, registry, fixture or source-switch operations.
- Dev Flux-check and MPNetV2 image-build DRY_RUN previews passed without cluster,
  Docker or registry requests. The final baseline report matches current bytes.

The implementation-time checks preceded the follow-up local commit pass. No
cloud/backend init/plan/apply, Kubernetes/registry/gateway/WordPress request,
SQL migration, live scaling, external message, push or release ran. Only public
repository reads used network access.
