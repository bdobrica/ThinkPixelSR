# Operator configuration

The implementation is `scripts/config.py`, `.env.example` and optional path
hooks in `cluster/live/dev/terragrunt.hcl`. This is a local, read-only validation
interface. The root Make targets reuse it; see the
[command guide](operations/commands.md) for guarded operations.
Python 3.9 or newer is required; the loader uses only the standard library.

## Start with local validation

From the repository root:

```bash
cp .env.example .env
# Choose ENV=dev, and reference existing credential/key files if needed.
python3 -B scripts/config.py --env dev
```

Success prints only `Configuration OK: ENV=dev; local input files validated
(no live checks).` A failure exits 2 with a field/category and corrective message,
without values, private paths or a traceback. The example is intentionally
incomplete: no credentials or private keys are shipped. An unconfigured checkout
fails on `SECRETS_FILE`; this is expected. Do not copy credentials from a sibling
checkout or create replacement keys for an existing cluster merely to pass.

The check reads local data. It does not execute shell commands, HCL functions,
Terragrunt, Terraform, cloud/registry APIs or Kubernetes commands; write files;
initialize providers/backends; authenticate; approve a plan; or apply changes.
Preserve and locate authoritative state before any later infrastructure command.
See the [baseline](baseline/infrastructure.md) and [migration guide](migration.md).

## Schema and mapping to existing consumers

Every path is optional as an override, but the corresponding file is required
for dev validation. Empty path values select the original environment-local
file. Relative explicit paths resolve from the **repository root**, regardless
of shell working directory or `.env` location; absolute paths are accepted.
No tilde, environment-variable or backslash expansion occurs. Public keys remain
checked in; paths can still point to an existing external credential directory.

| `.env` key | Default after explicit ENV selection | Translated child variable / existing consumer | Sensitivity |
| --- | --- | --- | --- |
| `ENV` | None; require `dev` or `prod` | Selects `cluster/live/<ENV>`; no Terraform input or Flux patch | Non-secret |
| `SECRETS_FILE` | `cluster/live/<ENV>/.secrets.hcl` | `TPSR_SECRETS_FILE` → `read_terragrunt_config()` → `local.secrets.inputs` | Path; referenced file contains cloud/DNS tokens |
| `MASTER_PUBLIC_KEY_FILE` | `cluster/live/<ENV>/.master.key.pub` | `TPSR_MASTER_PUBLIC_KEY_FILE` → `file()` → `master_public_ssh_key` | Path to public data |
| `MASTER_PRIVATE_KEY_FILE` | `cluster/live/<ENV>/.master.key` | `TPSR_MASTER_PRIVATE_KEY_FILE` → `file()` → `master_private_ssh_key` | Path to private key |
| `WORKER_PUBLIC_KEY_FILE` | `cluster/live/<ENV>/.worker.key.pub` | `TPSR_WORKER_PUBLIC_KEY_FILE` → `file()` → `worker_public_ssh_key` | Path to public data |
| `WORKER_PRIVATE_KEY_FILE` | `cluster/live/<ENV>/.worker.key` | `TPSR_WORKER_PRIVATE_KEY_FILE` → `file()` → `worker_private_ssh_key` | Path to private key |
| `MANAGEMENT_PUBLIC_KEY_FILE` | `cluster/live/<ENV>/.management.key.pub` | `TPSR_MANAGEMENT_PUBLIC_KEY_FILE` → `file()` → `management_public_ssh_key` | Path to public data |

The path hooks use Terragrunt's documented
[`get_env()` and `read_terragrunt_config()` functions](https://docs.terragrunt.com/reference/hcl/functions/).
Unset hooks retain the original relative filenames and direct invocation from
`cluster/live/dev`. `.env` is read by the Python loader, **not** automatically by
Terragrunt. The loader returns absolute paths through
`Configuration.child_environment()` for the root Make wrappers. This API returns an
environment dictionary; it does not print shell exports or launch a command.
Its translation has been compared with the direct baseline using synthetic
files and offline Terragrunt rendering; see [evidence](evidence/phase-2/README.md).

These consumers retain their existing authority:

| Settings | Existing source and consumer | Phase 2 treatment |
| --- | --- | --- |
| Hetzner/DNS credentials | `.secrets.hcl` `inputs.hcloud_token` / `inputs.hetznerdns_token` → sensitive Terraform variables and providers | Reference one private file; no inline `.env` tokens or new credential lifecycle |
| Domain, aliases, prefix, region, OS, master/worker counts/types, admin IPs, exposed apps | Dev Terragrunt base inputs, then `.secrets.hcl` overrides → existing Terraform modules | No duplicate `.env` settings or resource renames |
| Flux environment/domain, Git URL/ref/path, pull secret | `k8s/flux-system/dev/kustomization.yaml` and base FluxInstance/runtime ConfigMap/ResourceSets | Unchanged; ENV selection does not template or rewrite manifests |
| Registry, platforms, image names/tags | Existing workflow, Dockerfiles, version files, K8s overlays and Compose | Unchanged; Make image arguments must match checked-in namespace/version; no new `.env` keys |
| Application auth, MySQL/NATS/Qdrant/Redis credentials | Existing local/application configuration and Kubernetes Secret/SealedSecret references | Unchanged; no propagation from this operator `.env` |
| Kubeconfig, contexts, state/backend/workspace | Existing operator custody; explicit Make KUBE_CONTEXT and state review | No guessed default, generated credentials or backend changes; OPERATOR_DIR holds artifacts only |

## Precedence and format

Local configuration precedence is **CLI override > process environment > `.env`
> original path default**. `--env` overrides ENV even when `--set ENV=...` was
provided. There is no environment fallback. An explicit empty path chooses its
original default; an empty ENV fails. Known process variables have the same
seven names as the table. Unrelated process variables are ignored. Ambient
`TF_VAR_*` and `TPSR_*` are rejected by validation/translation, because they
could bypass or disagree with validated inputs. Unset them for this interface;
the inherited direct Terragrunt workflow remains available separately.

Root `make config-check ENV=dev` uses this loader. The Makefile exports defined
arguments without shell interpolation and never includes `.env`. Command-specific
state/approval, context, image and live-health arguments are passed separately;
see the [Phase 3 command guide](operations/commands.md). They are not accepted
as `.env` keys. Infrastructure wrappers also reject ambient Terraform/Terragrunt
argument/config/logging overrides and unvalidated tfvars files.

Examples of explicit local overrides (paths are illustrative):

```bash
python3 -B scripts/config.py --env dev --env-file .env
python3 -B scripts/config.py --env dev --set SECRETS_FILE='secrets.local/dev.secrets.hcl'
python3 -B scripts/config.py --env prod
```

The prod check fails explicitly: its Terragrunt root is empty, no Flux prod root
exists, and there is no credential/configuration contract to validate. It does
not borrow dev settings. Production support requires a separately reviewed
configuration; changing ENV alone cannot provision it.

The `.env` grammar accepts one known uppercase `KEY=value` per line, blank lines
and full-line `#` comments. Ordinary spaces around `=` or at line edges are
accepted. Values with spaces must use matching single or double quotes.
An unquoted inline comment requires spaces before `#`; after a quoted value,
only spaces and an optional `#` comment are allowed. CRLF files are accepted.
Duplicate/unknown keys, `export`, tabs/control characters, unterminated quotes,
trailing data and multiline values fail. Quotes are delimiters, not shell syntax:
`$HOME`, `${...}`, `$(...)`, backticks, backslashes and `~` remain literal text.
Use a complete actual path. Do not `source .env`, use Make `include .env`, or
generate shell assignments from it. No raw input is echoed on parse failure.

## Dev and prod examples

An illustrative dev `.env` referencing an existing private operator directory
is shown below. Replace every path locally; these files are not provided. The
public keys must match the cluster's existing private keys.

```dotenv
ENV=dev
SECRETS_FILE=/private/operator/dev/.secrets.hcl
MASTER_PUBLIC_KEY_FILE=/private/operator/dev/.master.key.pub
MASTER_PRIVATE_KEY_FILE=/private/operator/dev/.master.key
WORKER_PUBLIC_KEY_FILE=/private/operator/dev/.worker.key.pub
WORKER_PRIVATE_KEY_FILE=/private/operator/dev/.worker.key
MANAGEMENT_PUBLIC_KEY_FILE=/private/operator/dev/.management.key.pub
```

Run `make config-check ENV=dev`; expect local validation success only. If
the files already reside at their original dev paths, leave the six path
values blank. Never overwrite tracked public keys to configure an existing
cluster without reviewing the identity change.

The production selection example is intentionally a failure check:

```bash
make config-check ENV=prod
make cluster-plan ENV=prod DRY_RUN=1
```

Both exit nonzero without falling back to dev. Do not supply dev files to make
prod pass: its empty Terragrunt configuration and missing Flux root need a
separate approved implementation.

## Make arguments outside the dotenv schema

These names are accepted by the root Make interface as process/command-line
arguments. Putting them in `.env` produces an unknown-key error. Empty/unset
approval flags grant no permission. Details and side effects are in the
[command reference](operations/commands.md).

| Argument | Consumer and requirement | Sensitivity / authority |
| --- | --- | --- |
| `DRY_RUN` | Operation previews; `1` skips external execution, `0` or unset uses the target's normal guards | Preview is not live validation |
| `OPERATOR_DIR` | Actual init/plan/apply, Flux attach, image build/push; existing absolute private directory outside checkout | Contains sensitive output; no backend selection |
| `STATE_REVIEWED` | Actual infrastructure operations; `1` after backend/cache/workspace custody review | Acknowledgment, not state discovery or cloud authorization |
| `REVIEWED_SHA`, `CONFIRM` | Apply needs exact saved-plan SHA and `apply-dev`; Flux attach uses `bootstrap-dev`; image push uses `push` | Binds approval to the operation; no secret values |
| `POOL`, `COUNT`, `CURRENT_COUNT` | Scale plan: existing api/monitor, positive desired and observed counts | Desired count must already be persisted in effective HCL; current count comes from authoritative state |
| `REDUCTION_REVIEWED`, `REPLACEMENTS_REVIEWED` | Explicit `1` for relevant scale plans / worker-deletion apply | Requires workload/storage/drain review; does not drain nodes |
| `KUBE_CONTEXT` | All live cluster targets; explicit verified dev context | Kubeconfig remains in tool custody; context must match selected environment |
| `GITOPS_REVIEWED` | Flux attach needs `1` after source/owner/decryption review | Does not install operator or generate credentials |
| `IMAGE`, `REGISTRY`, `TAG` | Image targets: one supported image, `quay.io/bdobrica`, checked-in version | No mutable latest, automatic tag bump or manifest rewrite |
| `API_URL`, `LIVE_REVIEWED` | verify-live: reviewed HTTPS origin and explicit `1` | Endpoint kept out of output; health only |

`KUBECONFIG`, `TF_WORKSPACE` and Docker authentication are existing tool inputs,
not dotenv keys. Plans bind the workspace into their receipt. Wrappers reject
unvalidated Terraform/Terragrunt overrides; a custom backend/CLI setup may need
the separately reviewed direct workflow. The operator must verify that context,
workspace, endpoint and credentials refer to the same authorized dev installation.

## Secret-file contract and checks

The inherited contract is a Terragrunt file containing an `inputs` object.
The following uses **placeholders**; replace values locally using existing
operator credential custody. Do not commit the populated file:

```hcl
inputs = {
  hcloud_token     = "your-hetzner-api-token"
  hetznerdns_token = "your-hetzner-dns-api-token"
}
```

Both tokens must be nonempty literal strings without whitespace or common
placeholder values. They are read only for validation, never added to the
translated child environment or retained in the returned configuration.
The loader accepts literal HCL objects/lists/strings/numbers/booleans/null,
comments and optional object commas. It rejects expressions, function calls,
interpolation, heredocs, duplicate keys and extra blocks instead of evaluating
untrusted configuration. Existing additional literal overrides are accepted
only for declared Terraform inputs. Full Terraform type/provider validation
is deferred to a reviewed plan; this check does not validate domain ownership,
IP routing, server availability or credential validity.

Pool validation merges the inherited base with secrets overrides in the same
order, requires positive integer counts and nonempty server types, and retains
exactly the base worker pool names (`api`, `monitor`). It rejects new/deleted
pools and control-plane names in `worker_pools`. A valid count does **not**
authorize scaling or prove an additive plan: the current count-based worker
resource can replace later-pool nodes when indices shift. No count is applied
by this script. Live reductions and control-plane changes still require their
separate review gates.

If an existing secret file uses full HCL expressions/functions or custom worker
pools, this restricted validator fails explicitly. It does not rewrite that
file. Preserve the direct Terragrunt path and request a reviewed validator
extension for that installation; do not flatten credentials into logs to debug
it. The inherited merge remains **base inputs < secrets inputs < SSH file
contents**, so secret-file SSH inputs cannot replace the final file values.

All files must be readable, nonempty UTF-8 regular files, at most 1 MiB. Symlinks
to private storage are supported; checks apply to the target. On POSIX systems,
secret files and private keys must have no group/other permission bits (typically
mode `600`). Windows-mounted files may report permissive modes that `chmod`
cannot fix: keep sensitive material in private POSIX storage, or configure
appropriate filesystem permission support. On native Windows, this script
cannot verify ACLs; the operator must restrict access. The check validates file
availability, **not** key syntax, pairing, passphrase handling or SSH access.

`.gitignore` covers nested `.env` files, local secret files, private-key
conventions, kubeconfigs, Terraform state/plans and debug outputs; `.env.example`,
public `.key.pub` files, lockfiles and existing SealedSecrets remain visible.
Ignore patterns cannot detect credentials saved under arbitrary filenames or
remove already tracked secrets. Never upload rendered Terragrunt JSON, plans,
state or cloud-init: inherited private SSH variables are not marked sensitive.
Avoid shell tracing and unreviewed tool/debug output. Root `make -n` prints
only fixed Python recipes; credential/path values are not interpolated into them.

## Common failures and verification

| Failure | Local corrective action |
| --- | --- |
| ENV missing/invalid | Set `ENV=dev` explicitly or pass `--env dev`; prod remains blocked |
| Missing secret/key file | Reference existing operator files through the documented keys; public keys must match private keys |
| Private file permissions | Restrict permissions on the resolved target or use private POSIX storage |
| Missing/placeholder token | Supply both existing provider credentials in the private `inputs` object |
| Unknown `.env` key or HCL expression | Use the documented schema; retain advanced HCL on the direct path pending review |
| Ambient override conflict | Remove `TF_VAR_*`/`TPSR_*` from this loader's process environment |
| Bad count or unsupported pool | Review authoritative pool inputs; validation never edits them |

Run the synthetic regression suite without operator credentials:

```bash
python3 -B -m unittest discover -s tests -v
```

The optional Terragrunt integration test uses the inspected v0.96.1 `render`
CLI in a temporary directory with synthetic credentials/key bytes and a
Terraform stub that allows version detection only. It compares frozen baseline,
default-hook and externally relocated-file inputs, suppressing rendered output.
When Terragrunt, Git or the frozen source object (in a shallow checkout) is
absent, that test is reported skipped. Compatibility
with other Terragrunt versions and live deployment remain unverified.
