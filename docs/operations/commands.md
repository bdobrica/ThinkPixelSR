# Phase 3 operator commands

The root [Makefile](../../Makefile) wraps the existing tools through
[`scripts/ops.py`](../../scripts/ops.py). These commands have offline safety and
command-forwarding coverage; **the dev deployment, registry publishing,
reconciliation and scaling workflow has not been run live**. See
[Phase 3 evidence](../evidence/phase-3/README.md). Production is blocked because
its Terragrunt root is empty and its Flux root is absent.

## Local discovery and configuration

```bash
make                         # help only
make doctor                  # local binary/plugin versions only
make verify                  # offline gates; prints missing-tool skips
cp .env.example .env
# Choose dev and reference existing private credentials/keys locally.
make config-check ENV=dev
```

Python >= 3.9, GNU Make, Terraform >= 1.10 and Terragrunt >= 0.96.1 are
required for the infrastructure wrappers. The inspected versions are Terraform
1.14.3 and Terragrunt 0.96.1; older Terragrunt CLIs use different flag names and
must use the inherited direct workflow. Kubectl with Kustomize and Docker
Buildx are required for their respective command families. Bash is used for
offline script syntax checks. The Flux CLI is optional: this repository uses
the Flux operator, and the wrappers inspect its resources with kubectl.

Doctor reports missing/unsupported tools with a nonzero exit status. It does
not install tools, connect to Docker, authenticate or check a cluster. Offline
verify runs synthetic tests, Make/Python/shell syntax, Terraform formatting,
the edited dev HCL format, documentation links and six dev Kustomize roots.
Three inherited cross-directory overlays use `LoadRestrictionsNone`, as in the
baseline. Rendering does not prove Helm/CRD validity or Flux reconciliation.
Missing optional checking tools are reported as skips. No application runtime
tests, provider initialization, real state operations or live smoke run inside
verify. Its forwarding test uses real Terragrunt with a **fake Terraform
binary** in a temporary fixture; it cannot deploy resources.

The seven-key [configuration contract](../configuration.md) still applies.
Make exports only defined operator arguments as environment data; Python reads
`.env`. It never includes/sources `.env` or substitutes paths/tokens into shell
recipes. Command-line Make arguments take precedence over the inherited process
environment and `.env`. Empty ENV fails; an explicitly blank path selects its
original file default. Use `.env` for paths containing dollar signs or other
Make metacharacters; command-line assignments are also subject to GNU Make's
own expression syntax. Do not supply secret contents through Make arguments.

Command-specific arguments below are **not new `.env` keys**. Pass them through
Make or the process environment; keep kubeconfig and registry authentication
under their existing tool custody. Cloud/key path validation is required for
infrastructure commands; cluster diagnostics do not need cloud credentials,
and image commands do not need ENV.

## State custody, previews and saved-plan apply

Locate the authoritative backend, Terragrunt cache and Terraform workspace,
check lineage/serial and keep a private recovery copy before init or plan.
The repository defines no remote backend. A new cache can otherwise mean a new
local state and duplicate infrastructure. `STATE_REVIEWED=1` acknowledges that
review; the wrapper cannot discover or migrate the correct state for you.
Preserve any operator-specific setup using the existing direct workflow before
using these commands. Ambient `TF_CLI_ARGS*`, `TG_*`, `TERRAGRUNT_*`, logging,
alternate CLI config and TF data-directory overrides are rejected. Unvalidated
tfvars in the source/environment/cache are also rejected. `TF_WORKSPACE`, if
used, remains explicit and is bound into the plan receipt.

```bash
make cluster-init ENV=dev DRY_RUN=1
make cluster-plan ENV=dev DRY_RUN=1
make cluster-up ENV=dev DRY_RUN=1
```

These previews validate the configured local input files, show the selected
root and command with paths redacted, and launch no tools or create artifacts.
They still need existing private credentials/keys, but never authenticate.
No synthetic/placeholder credentials are accepted as a deployment shortcut.

For an authorized operator run, create a private **mode 700** directory outside
the checkout on POSIX storage and export its absolute path as `OPERATOR_DIR`.
Mounted filesystems reporting permissive modes are unsuitable; use private
POSIX storage. Native Windows operators must review equivalent ACLs. Use a
fresh artifact directory for each plan; logs/plans/receipts are never overwritten.
Init and the following plan may share the directory. The directory is an
artifact destination, not a state/backend setting.

```bash
# Only after state review and authorization to contact the dev cloud/backend:
make cluster-init ENV=dev STATE_REVIEWED=1
make cluster-plan ENV=dev STATE_REVIEWED=1
# Inspect OPERATOR_DIR/plan.log privately; it may contain SSH private keys.
# Copy the printed plan SHA256 after reviewing the exact saved plan:
make cluster-up ENV=dev STATE_REVIEWED=1 REVIEWED_SHA='<reviewed-sha256>' CONFIRM=apply-dev
```

Underlying invocations run in `cluster/live/dev`:

```text
terragrunt run --no-auto-init --no-auto-retry --non-interactive \
  --tf-path terraform --log-disable --tf-forward-stdout -- \
  init -input=false -lockfile=readonly
terragrunt run <same flags> -- plan -input=false -no-color -out=<absolute-private-plan>
terragrunt run <same flags> -- show -json <absolute-private-plan>
terragrunt run <same flags> -- apply -input=false -no-color <absolute-private-plan>
```

Terragrunt's [run interface](https://docs.terragrunt.com/reference/cli/commands/run/)
passes the existing Terraform commands through; no second provisioner or
auto-init/upgrade is added. Init can download providers, contact a backend and
write metadata. Plan can refresh remote resources, acquire a state lock and
write local/cache files. It never implicitly applies. Provider plan/data-source
behavior remains the operator's responsibility; a preview is not live proof.

Raw output stays in private `init.log`, `plan.log` and `apply.log`, with fixed
safe failure messages on the terminal. `dev.tfplan` and `dev.receipt.json` are
private too. Do not publish these, archive them in CI or paste logs into issues.
The receipt binds the plan bytes, source TF/HCL/lockfiles, six input files and
workspace. Changed inputs, plan bytes, environment or checkout invalidate it.
Terraform also performs its own stale-state/backend checks during apply.
Before execution, an exclusive `apply.attempted` marker prevents another attempt
from this receipt, including after failure. Diagnose partial state privately,
then create and review a fresh plan; never blindly replay or force-unlock.

Applying a [saved Terraform plan](https://developer.hashicorp.com/terraform/tutorials/cli/plan)
does not prompt again. Therefore the wrapper requires both the exact reviewed
SHA and `CONFIRM=apply-dev`. There is no `-auto-approve`, automatic retry,
destruction target or prod approval escape hatch. Plans that change existing
control-plane resources are blocked for separate review. Any planned worker
deletion/replacement also requires `REPLACEMENTS_REVIEWED=1` and
`REDUCTION_REVIEWED=1` at apply, even for an ordinary cluster plan.

## Worker scaling

Scale operates on existing `api` or `monitor` pools. First persist the desired
count in the existing dev `worker_pools` input or its literal secret-file
override. Include the complete map when overriding it: retain other pool counts
and server types. Do not change `master_pool`. Obtain `CURRENT_COUNT` from the
reviewed authoritative state/cluster, not from a guessed default.

```bash
# Example: api was confirmed to have 3 workers; its persisted desired count is 4.
make cluster-scale ENV=dev POOL=api COUNT=4 CURRENT_COUNT=3 DRY_RUN=1
make cluster-scale ENV=dev POOL=api COUNT=4 CURRENT_COUNT=3 STATE_REVIEWED=1
# Inspect the saved plan, including workers in other pools, then use cluster-up.
```

`cluster-scale` only creates a saved plan. It never edits files, drains nodes or
applies. It verifies the plan's before/after pool counts against CURRENT_COUNT
and COUNT and rejects control-plane changes. The existing worker resource
flattens all pools into count indices, so growing api can replace monitor nodes.
Every deletion/replacement is recorded in the receipt and requires renewed
explicit acknowledgments at apply.

Reductions require `REDUCTION_REVIEWED=1` even for a dry-run. Before setting it,
review workload placement, Qdrant/Redis/MySQL/NATS data, PV/PVC ownership and
attachments, backups, PDBs, spare capacity, draining order and recovery. Review
all pools affected by index shifts. There is no automatic drain procedure or
zero-downtime guarantee. Restore the prior persisted counts and **review a new
plan** if reversal is required; replacement nodes/storage may need additional
recovery, and an old plan is not rollback.

## Flux readiness and guarded attachment

```bash
make flux-check ENV=dev KUBE_CONTEXT='<reviewed-dev-context>' DRY_RUN=1
make flux-check ENV=dev KUBE_CONTEXT='<reviewed-dev-context>'
make status ENV=dev KUBE_CONTEXT='<reviewed-dev-context>'
```

Kubectl uses the explicit context on every cluster request, never the current
context implicitly. Checks require the flux-system namespace, FluxInstance,
ResourceSet and SealedSecret CRDs, an available `flux-operator` Deployment,
and `github-token` Secret metadata. They never print Secret contents. Flux
check additionally waits for Ready on FluxInstance/flux and the root source and
Kustomization. Status prints counts of Ready resources/pods in the inherited
namespaces; failing requests exit nonzero. It is not an application smoke test.

`flux-bootstrap` is a guarded **attach** operation for an already installed
operator. Fresh operator/controller installation and decryption-key recovery
remain unresolved manual prerequisites. It does not run `flux bootstrap github`,
create tokens, replace sealed secrets or commit generated manifests. Review
existing ownership and Git/decryption credentials before the operation:

```bash
make flux-bootstrap ENV=dev KUBE_CONTEXT='<reviewed-dev-context>' DRY_RUN=1
# Only with explicit operator authorization and the prerequisites already met:
make flux-bootstrap ENV=dev KUBE_CONTEXT='<reviewed-dev-context>' \
  GITOPS_REVIEWED=1 CONFIRM=bootstrap-dev
```

The command checks prerequisites and runs server dry-run, then
`kubectl --context <context> apply -k k8s/flux-system/dev`. It attaches the exact
checked-in operator-managed [FluxInstance](https://fluxoperator.dev/docs/crd/fluxinstance/)
and ResourceSets. It does not apply application overlays imperatively. Applying
the root can start reconciliation and alter workloads through Flux. Source URL,
Git ref, paths, secrets and resource ownership remain inherited; the Git URL
still points to ThinkPixelInfra. Missing operator/CRDs/credentials, wrong context,
RBAC or server validation stop before attachment. Success of apply alone does
not establish reconciliation or plugin compatibility; run flux-check/status and
the separately authorized smoke. Root reinstall/rollback requires the existing
operator's reviewed recovery process and decryption key custody.

## Versioned images

Select one of `api-gateway`, `mpnetv2`, `snowflake-arctic`, `e5-instruct`,
`jina-v5`, `external`. Names map to the exact checked-in Dockerfiles and contexts
in the [image inventory](../baseline/images.md). REGISTRY must be the explicit
checked-in `quay.io/bdobrica` namespace; TAG must equal that context's
`.bumpversion.cfg` current_version. Latest and arbitrary versions are blocked.
Manifests and image refs are never rewritten.

```bash
make images-build IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 DRY_RUN=1
make images-build IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5
# Authenticate with existing Quay custody, outside traced scripts/logs:
docker login quay.io
make images-push IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 CONFIRM=push
```

Both commands use Buildx, `linux/amd64,linux/arm64`, the inherited TARGETPLATFORM
argument and `thinkpixel-<image>-multi:<version>`. Build writes a private OCI
archive under OPERATOR_DIR; it does not load an image into the local Docker
store. Push builds and publishes to Quay as the inherited workflow does, using
only the explicit version tag. Publishing can replace an existing version tag;
inspect registry policy/current artifacts before authorizing it. Version tags
do not make upstream model/package downloads reproducible or digest locked.
The inherited CI workflow still publishes latest; it is unchanged here.

Configure a running builder with OCI export, both architectures/QEMU, sufficient
disk/memory and access to model/package mirrors before building. Wrappers never
install emulators, bootstrap a builder or print registry credentials. Docker
build/push errors are retained in private logs. Fresh artifact directories avoid
overwriting local archives/logs. Actual multi-architecture builds, pushes and
cluster pulls remain live acceptance gaps.

## Explicit live health and full smoke

```bash
make verify-live ENV=dev API_URL='https://<reviewed-dev-gateway>' LIVE_REVIEWED=1 DRY_RUN=1
make verify-live ENV=dev API_URL='https://<reviewed-dev-gateway>' LIVE_REVIEWED=1
```

This opt-in check uses HTTPS GET /ping and /ready, with certificate validation,
no redirects, bounded response size and a 30-second timeout per request. It
requires HTTP 200 and the existing status/database assertions. The endpoint and
responses are not printed. It never authenticates, ingests or removes data.
Readiness only checks the database: NATS, embedding, retrieval and plugin behavior
still require the [disposable-site smoke procedure](verification.md). That
procedure writes fixture data and requires separate operator authorization.
No full integration success is inferred from this health target.
