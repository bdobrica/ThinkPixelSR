# Hetzner dev deployment

This runbook uses the implemented root Make commands and preserves the
[inherited Terraform topology](../architecture.md). Its commands are inspected
and covered offline; **no live deployment has been validated**. Only dev is
configured. Production has an empty Terragrunt root and no Flux root, and is
blocked by every environment-dependent wrapper.

## Prerequisites and ownership

Read [configuration](../configuration.md), [state and command guards](../operations/commands.md#state-custody-previews-and-saved-plan-apply)
and [migration](../migration.md) before contacting Hetzner. Required inputs are:

- GNU Make, Python >=3.9, Terraform >=1.10, Terragrunt >=0.96.1; kubectl for
  later cluster checks. `make doctor` checks local versions only.
- Operator-approved dev project, budget and cloud/DNS access; both provider
  tokens in a private literal `.secrets.hcl` inputs object. Authentication and
  project/zone permissions are not checked by config-check.
- Existing matching master/worker SSH pairs and management public key. The
  management private key remains in operator custody; it is not a dotenv input.
- Authoritative state location, Terragrunt execution cache, workspace and
  recovery copy. No remote backend is declared in Git. Missing tracked state
  does not mean the cloud is empty.
- Reviewed dev inputs: domain/aliases, cluster prefix, fsn1/debian-12, one cax21
  master, api/monitor worker counts and types, admin IP allowlist and listeners.
  Secret-file overrides can alter those inputs; inspect their effective values.

Preserve both provider lockfiles: hcloud 1.49.1 and hetznerdns 2.1.0 are the
recorded selections. Do not upgrade providers, rekey existing nodes, import/move
state or change resource addresses as a setup shortcut. SSH private keys are
embedded in cloud-init and are not marked sensitive Terraform variables;
plans, state, renders and logs must remain private.

## First deployment versus an existing installation

For an existing installation, locate its authoritative state and cache before
init. Confirm lineage/serial, workspace and current node/resource ownership
using the operator's established private procedure. If that setup depends on
unsupported CLI/backend overrides or tfvars, stop and use its reviewed direct
workflow; the wrappers reject them rather than guessing.

For a genuinely new dev installation, the operator must explicitly establish
that no resources/state already own the chosen identities, approve the initial
state location and recovery process, and review domain/zone ownership. Terraform
creates DNS zones/records and managed certificates; an existing zone requires
an ownership decision, not a blind second apply. Do not repurpose the checked-in
dev identities for an unrelated cluster.

A fresh **application** deployment cannot currently be completed from this
checkout alone: initial Flux Operator/CRD installation, Sealed Secrets
controller/decryption key, external credentials and compatible MySQL
schema/index-node allocation remain unresolved setup prerequisites. Use
[Flux deployment](fluxcd.md#bootstrap-inputs-and-order) for those stop points.
The inherited cluster README includes generic key generation and master-count
examples; this runbook preserves the actual one-master configuration. Additional
control-plane nodes require a separate decision.

## Validate, initialize, plan and apply

All commands below run from the repository root. No secrets are supplied as
Make values. Configure local paths through `.env` first:

```bash
make help
make doctor
make verify
make config-check ENV=dev
make cluster-init ENV=dev DRY_RUN=1
make cluster-plan ENV=dev DRY_RUN=1
```

Expected: help/versions/offline checks, local configuration success, then
redacted dev commands. Dry-run executes no tools or artifact writes; it still
requires valid local input files. It cannot validate cloud access or state.

After explicit authorization to initialize/contact the dev backend/project,
create a fresh private artifact directory on POSIX storage outside Git:

```bash
umask 077
export OPERATOR_DIR="$(mktemp -d /tmp/thinkpixelsr-dev.XXXXXX)"
make cluster-init ENV=dev STATE_REVIEWED=1
make cluster-plan ENV=dev STATE_REVIEWED=1
```

OPERATOR_DIR is not a backend. Use protected durable operator storage instead
of `/tmp` if artifacts must survive reboot; never lose the authoritative state
or recovery copy. Init uses the existing root with `-lockfile=readonly`; plan
refreshes resources and writes `dev.tfplan`, its receipt and private logs.
Check the exact plan privately: account/zone, creates/updates/deletes, state
ownership, worker indices, DNS/TLS/load-balancer targets and all identity drift.
Stop if an existing cluster unexpectedly appears as all creates. Do not publish
plan.log, show JSON, cloud-init or private paths.

For the exact reviewed plan, with explicit operator approval to apply:

```bash
make cluster-up ENV=dev STATE_REVIEWED=1 \
  REVIEWED_SHA='<reviewed-sha256>' CONFIRM=apply-dev
```

Expected: the saved plan is applied once and output is retained in apply.log.
No `-auto-approve` or automatic retry is used. Any changed inputs/workspace/plan
invalidate the receipt. Existing master changes are blocked. Worker deletion
or replacement needs the additional reviewed acknowledgments documented in
[scaling](../operations/scaling.md); never add flags merely to suppress a guard.

## SSH, kubeconfig and network checks

The cloud-init source creates user `cluster` with passwordless sudo, installs
K3s without a version pin and joins nodes with the existing SSH keys. Use the
reviewed first master's reachable address and management key; verify its SSH
host fingerprint through the operator's trusted channel before access. Do not
disable host-key or TLS verification. Node tokens are credentials and must
never be printed or captured in public diagnostics.

For an authorized operator retrieving **their** kubeconfig, the inspected K3s
path is `/etc/rancher/k3s/k3s.yaml`:

```bash
: "${DEV_MASTER_ADDRESS:?Set the verified reachable master address}"
: "${DEV_MANAGEMENT_KEY:?Set the existing management private key path}"
: "${OPERATOR_DIR:?Set the private artifact directory}"
ssh -i "$DEV_MANAGEMENT_KEY" "cluster@$DEV_MASTER_ADDRESS" \
  'sudo cat /etc/rancher/k3s/k3s.yaml' > "$OPERATOR_DIR/kubeconfig.yaml"
chmod 600 "$OPERATOR_DIR/kubeconfig.yaml"
export KUBECONFIG="$OPERATOR_DIR/kubeconfig.yaml"
```

Review the file privately. If its server is loopback, select the verified
reachable API endpoint through the installation's approved access method;
confirm certificate SAN/trust first. Do not assume the application load
balancer is the Kubernetes API endpoint or use insecure-skip-tls-verify.
Choose an explicit context after private inspection; kubeconfig setup changes
local credential configuration, not deployed manifests.

```bash
export KUBE_CONTEXT='<verified-dev-context>'
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get nodes -o wide > "$OPERATOR_DIR/nodes.txt"
```

Expected: the intended master and workers are Ready; verify actual node count,
architecture, taints and placement privately. Failures may be cloud-init/SSH
join, admin-IP/firewall or API routing/certificate issues. Do not broaden the
firewall globally to diagnose access.

The existing app load balancer terminates HTTPS: api external 8080 maps to
NodePort 30080, monitor external 3000 to NodePort 30030. Its health checks use
HTTP `/ping` and `/api/health`. Check DNS, certificate issuance, listener and
backend health through private operator diagnostics; healthy `/ping` alone
does not establish MySQL, indexing or plugin compatibility.

## Application handoff and recovery

Once cluster access and the external bootstrap prerequisites are established,
follow [Flux attachment and reconciliation](fluxcd.md), then
[health and disposable-site verification](../operations/verification.md).
Use `make status ENV=dev KUBE_CONTEXT='<verified-dev-context>'` for redacted
summaries. Live acceptance needs image pulls and the plugin ingestion/search
path, not just infrastructure apply success.

On failure stop further applies. Keep the single-attempt marker, state and
private logs. Identify partial resources/state privately and create a **new**
plan after repair and approval; do not replay the old receipt, force-unlock an
active operation or destroy the cluster. Restore prior intended inputs only
after reviewing the new diff. This cannot undo node replacement or lost local
data. Storage recovery needs verified backups and the installation's recovery
procedure. Repository/source rollback is separate and described in
[migration](../migration.md#exact-switch-back-steps-after-a-failed-cutover).

See [troubleshooting](../operations/troubleshooting.md) for categorized checks.
