# Flux ownership and dev attachment

ThinkPixelSR preserves the operator-managed Flux deployment. The implemented
`flux-bootstrap` target attaches the checked-in root overlay to an **existing**
Flux Operator; initial installation is unresolved. Reconciliation, Helm releases
and plugin behavior have not been tested live. Production has no Flux root.
See [command guards](../operations/commands.md#flux-readiness-and-guarded-attachment).

## Sources and owners

| Resource / owner | Existing setting |
| --- | --- |
| FluxInstance `flux`, namespace `flux-system` | Source/kustomize/helm/notification controllers; Flux `2.x`, operator manifests OCI `latest` |
| `spec.sync` → generated GitRepository and root Kustomization `flux-system` | `https://github.com/bdobrica/ThinkPixelInfra`, `refs/heads/main`, `k8s/flux-system/dev`, pull secret `github-token` |
| ResourceSet `flux-operator` | OCIRepository and HelmRelease for operator chart, semver `*`, cosign verification |
| ResourceSet `flux-notifications` | GitHub Provider/Alert `github-status`, old repository address, `github-token` |
| ResourceSet `apps` | cert-manager, reflector, nats, monitoring and thinkpixel dev tenants |
| Tenant Kustomizations `<tenant>-dev` | Same GitRepository, `./k8s/apps/<tenant>/dev`, `prune: true`, wait, runtime ConfigMap substitution, serviceAccountName `flux-operator` |
| `flux-runtime-info` | Dev ENVIRONMENT and CLUSTER_DOMAIN; copies/substitutions retain manifest authority, not dotenv templating |

cert-manager and reflector Kustomizations select targetNamespace `flux-system`;
other tenants select their tenant namespace. The actual Helm workload namespaces
and controller RBAC must be checked live. WordPress base is absent from dev;
ThinkPixelPlugin must already run on a separate approved test installation.

## Bootstrap inputs and order

For an existing installation, retain its operator/controller versions,
credentials, decryption keys, source ownership and last working revision. Before
attachment, the operator must establish:

1. Ready dev K3s nodes and verified kubeconfig/context from
   [Hetzner deployment](hetzner.md#ssh-kubeconfig-and-network-checks).
2. Namespace `flux-system`, an available Deployment `flux-operator`, and
   FluxInstance/ResourceSet CRDs. Their ResourceSets cannot install themselves
   before those CRDs/controllers exist. No initial installer is checked in.
3. Sealed Secrets controller/CRD and the **original matching decryption key**.
   A new controller/key cannot decrypt the inherited ciphertext. Controller
   existence alone does not demonstrate successful decryption.
4. Existing `github-token` Secret in flux-system, sufficient source-fetch and
   GitHub status permissions. Preserve secret names and operator-approved
   credential creation/rotation; no token-generation command is provided here.
5. Application secrets: Quay pull credentials, gateway JWT, MySQL/Qdrant/Redis,
   Fluent Bit object storage and monitoring settings. Verify SealedSecret
   status privately. NATS certificate generation and reflection into thinkpixel
   require cert-manager and reflector; TLS/nkey mount names must match gateway.
6. Compatible MySQL schema and index-node records plus usable PV/PVC bindings.
   No schema init Job is checked in. Base SQL/local db-init are insufficient
   for the current gateway; [verification](../operations/verification.md#existing-integration-scripts-inspect-before-use)
   documents the unresolved setup path. Do not run an unreviewed migration.

For a fresh cluster, stop at the first missing prerequisite and establish a
separately reviewed installation/recovery procedure. This documentation does
not substitute `flux bootstrap github`, Helm install guesses, new encrypted
secrets or imperative tenant deployments for the inherited system.

## Check, attach and reconcile

From the repository root, with the verified dev context:

```bash
make flux-check ENV=dev KUBE_CONTEXT='<verified-dev-context>' DRY_RUN=1
make flux-check ENV=dev KUBE_CONTEXT='<verified-dev-context>'
make status ENV=dev KUBE_CONTEXT='<verified-dev-context>'
```

Dry-run makes no cluster requests. A live check reads prerequisite metadata and
waits up to 30s each for operator availability and Ready on FluxInstance/root
GitRepository/root Kustomization; the aggregate wrapper is not an indefinite
wait loop. A failed check suppresses raw diagnostics. It may fail on a prepared
cluster before root attachment because root resources do not yet exist.
Status prints Ready counts, not resource dumps or a full health judgment.

After ownership/source/decryption review and explicit approval to start dev
reconciliation, use a fresh private OPERATOR_DIR as in the
[command guide](../operations/commands.md#state-custody-previews-and-saved-plan-apply):

```bash
umask 077
export OPERATOR_DIR="$(mktemp -d /tmp/thinkpixelsr-flux.XXXXXX)"
make flux-bootstrap ENV=dev KUBE_CONTEXT='<verified-dev-context>' DRY_RUN=1
make flux-bootstrap ENV=dev KUBE_CONTEXT='<verified-dev-context>' \
  GITOPS_REVIEWED=1 CONFIRM=bootstrap-dev
make flux-check ENV=dev KUBE_CONTEXT='<verified-dev-context>'
make status ENV=dev KUBE_CONTEXT='<verified-dev-context>'
```

Attachment checks prerequisites, performs server-side dry-run, then applies
only `k8s/flux-system/dev`; output stays in flux-attach.log. This can trigger
live workload changes via reconciliation. No source URL/ref/path, namespace,
image or secret reference is rewritten. A successful apply is not a successful
reconcile. The old source remains authoritative for tenant content, so local
ThinkPixelSR edits alone do not deploy application changes.

Inspect revisions and conditions privately with explicit context:

```bash
: "${KUBE_CONTEXT:?Set the verified dev context}"
: "${OPERATOR_DIR:?Set a private directory outside Git}"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get fluxinstance flux -o json > "$OPERATOR_DIR/flux-instance.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get gitrepository flux-system -o json > "$OPERATOR_DIR/git-source.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get kustomizations -o json > "$OPERATOR_DIR/kustomizations.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get helmreleases -A -o json > "$OPERATOR_DIR/helm-releases.json"
```

Require Ready for the observed generation, expected source artifact revision,
root and **every tenant**'s applied revision/conditions, Helm readiness, secret
decryption, PVC binding and workload readiness. Compare observed identities to
the [GitOps baseline](../baseline/gitops.md). Flux
[Kustomization status](https://fluxcd.io/flux/components/kustomize/kustomizations/)
exposes observedGeneration and lastAppliedRevision; stale Ready is insufficient.
Only sanitized revisions/counts/assertions belong in evidence. A root Ready
count cannot prove that MySQL, NATS, models or retrieval work. Finish the
authorized [verification procedure](../operations/verification.md).

## Failures and source management

Missing CRDs/operator require the installation prerequisite above. Source
authorization or revision errors require private credential/ref/access review.
Helm/tenant failures require their events, RBAC, substitution and prerequisite
statuses; inspect [troubleshooting](../operations/troubleshooting.md#flux-and-sealed-secrets).
Three inherited app overlays need permissive loading for offline rendering;
that observation is not evidence of live controller compatibility. Record any
live build failure rather than changing controller security flags casually.

The Git source **owner** is FluxInstance; the GitHub notification owner is
ResourceSet. Patching only generated GitRepository/Provider can be overwritten.
ThinkPixelSR publication does not authorize a switch. A future cutover needs
explicit approval, validated dev/plugin path, credential access to the new
source, zero workload drift and retained old remote/ref/keys. Follow
[migration and exact switch-back](../migration.md),
which captures owner settings before mutation. Keep both repositories readable.

For an unrelated reconcile failure, preserve the last working revision and
private logs, stop further rollout edits and use the existing installation's
reviewed recovery process. Pruning, namespace/PVC deletion and controller
reinstallation can lose ownership or data; do not use them as routine repair.
Source rollback does not restore database writes, overwritten image tags or
local storage.
