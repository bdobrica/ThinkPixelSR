# Phase 3 wrapper evidence

Scope: P3-01 through P3-08 implementation and offline gates. No live
cloud/backend, Kubernetes, registry or plugin operation ran. The deliberate dev
workflow gate remains open. Existing application code, Terraform resources,
state/backend declarations, Kubernetes/Flux identities, Dockerfiles, CI and
license are unchanged by Phase 3. Phase 2 local changes are retained.

## Implementation and acceptance

| Task | Implemented behavior | Acceptance status |
| --- | --- | --- |
| P3-01 | Default help; local doctor; safe configuration checks | Offline checks pass |
| P3-02 | Explicit dev root; init/read-only lockfile; saved plan; no auto-init/apply; read-only dry-run | Direct argument comparison and real Terragrunt forwarding to fake Terraform pass |
| P3-03 | Saved-plan hash/input/workspace binding; explicit approval; private logs; single attempt; prod blocked | Guards pass offline; deliberate real dev apply pending |
| P3-04 | Explicit-context readiness and guarded attach to existing Flux operator; old Git source preserved | Guards/command checks pass offline; initial operator install unresolved and reconciliation pending |
| P3-05 | Exact checked-in contexts/Dockerfiles, both architectures, Quay namespace and version; private OCI build/export; approved push | Six-image command checks pass; real build/push/pull pending |
| P3-06 | Redacted readiness counts; offline verify; opt-in HTTPS liveness/database health | Offline behavior passes; live health and full disposable-site/plugin smoke pending |
| P3-07 | Persisted existing-worker counts; plan only; current-state count assertion; master block; deletion/reduction approvals | Synthetic guard cases pass; real scale-up plan/state review pending |
| P3-08 | Repeatable Make/Python/shell/HCL/Kustomize/doc checks | Available offline gates pass; no CI redesign |

TODO items requiring live acceptance remain unchecked even though their wrappers
are implemented. [Command guide](../../operations/commands.md) contains
prerequisites, actual invocations, output expectations, failure handling and
recovery limitations.

## Checks run

- `make` / `make help`: help only, no deployment/default environment.
- `make doctor`: passed with GNU Make 4.4.1, Python 3.13.5, Terraform 1.14.3,
  Terragrunt 0.96.1, kubectl 1.32.3 and Docker Buildx 0.30.0. Client/version
  commands only, no Docker daemon, credential or cluster authentication checks.
- `python3 -B -m unittest discover -s tests -v`: 36 tests passed, including
  real Terragrunt input comparison from Phase 2 and wrapper forwarding to an
  offline Terraform stub. No operator credentials used. Fake init/plan/show/apply
  operate only inside temporary synthetic fixtures; no live Terraform action.
- `make verify`: passed Python/Make/shell syntax, tests, documentation links,
  `terraform -chdir=cluster fmt -check -recursive`, edited dev
  `terragrunt hcl fmt --check`, and six dev Kustomize renders.
- Relative documentation links/fragments: 103 passed. Eighteen Bash snippets
  in the entry point, configuration, command and verification guides passed
  `bash -n` (syntax only; deployment examples were not executed).
- `git diff --check`, tracked ignore review and an eleven-file limited scan for
  private-key headers, GitHub token patterns and AWS access-key patterns passed.
  This is not a comprehensive secret-scanner certification. Source
  ThinkPixelInfra remains at the frozen commit with no tracked diff; application,
  manifests, Dockerfiles, CI, Terraform modules, prod and governance plan/license
  paths have no diff from current ThinkPixelSR HEAD.
- The inherited cert-manager/reflector/NATS overlays require relaxed local
  `LoadRestrictionsNone`; strict rendering fails as recorded in Phase 0. No
  manifest fix or claim of live Flux behavior is made here.
- Unconfigured `make config-check ENV=dev`: expected nonzero, missing secret
  file; no authenticating/deploying shortcut. Empty/invalid/prod selection is
  rejected across environment-sensitive commands in synthetic tests.
- Preview tests launch no tools and preserve a byte snapshot of fixture files.
  Image previews match inherited names/platforms/context and omit latest.
- Negative cases cover unsafe ambient overrides, malformed worker counts,
  unpersisted count changes, control-plane changes, replacement/reduction
  approvals, stale/tampered plans, changed keys/workspace, missing state approval,
  private permissions/symlinks, explicit context/Flux prerequisites and redacted
  tool failures. Live-health assertions use mocked HTTP responses only.

## Remaining gates

The authoritative state/backend/workspace is still unlocated. Real init, plan,
apply and scaling need state custody, existing private credentials/keys and
explicit operator authorization. An existing cluster's operator/CRDs,
decryption-key custody, Git pull credentials, ownership and context must be
reviewed before Flux attachment; no fresh operator install is invented.
Registry/builder authentication, QEMU/architecture support, model download
availability and actual pull references are unverified. No remote Git source
cutover, root Make deployment, writable API fixture or WordPress action ran.
Production has no configuration and remains blocked.

Offline checks establish wrapper safety and argument forwarding, not provider
plan correctness, live compatibility, zero downtime, immutable registry policy
or production qualification. Generated logs/plans/receipts may contain secrets
and stay outside Git/CI artifacts in private operator storage.
