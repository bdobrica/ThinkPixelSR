# Planning existing worker-pool changes

`make cluster-scale` validates a **persisted** api/monitor count change and saves
a plan. It never edits configuration, applies, drains or reduces capacity
automatically. The safeguards pass synthetic tests; live scale-up review and
any actual reduction remain unverified and need operator authorization.
Production and control-plane changes are blocked.

## Pool authority and replacement risk

The base [dev HCL](../../cluster/live/dev/terragrunt.hcl) has one cax21 master,
three api workers and one monitor worker. Effective HCL inputs are base merged
with literal secret-file overrides, then SSH file inputs. Keep those sources of
truth; no new scaling dotenv key or second pool definition is added.

The [worker module](../../cluster/infra/k8s/worker/main.tf) flattens all pools
into a single `hcloud_server.this[count.index]`. Growing api can shift monitor
indices and cause replacements outside api. Review every resource action, not
just the net worker count. Cloud labels do not prove Kubernetes pod placement.
Existing tolerations allow scheduling on tainted workers; inspect the actual
nodes and pods. Do not change pool names/types, master_pool, control-plane
quorum or resource addresses through this procedure.

## Before any deletion or replacement

The operator must review the authoritative state/current counts, proposed
worker addresses and Kubernetes node correspondence, spare capacity and all
affected workloads. Use a private POSIX OPERATOR_DIR and explicit reviewed
KUBE_CONTEXT; these commands only read the cluster, but their output can contain
IPs, node names and workload metadata:

```bash
umask 077
: "${KUBE_CONTEXT:?Set the verified dev context}"
: "${OPERATOR_DIR:?Set a private directory outside Git}"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get nodes -o wide > "$OPERATOR_DIR/scale-nodes.txt"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get pods -A -o wide > "$OPERATOR_DIR/scale-pods.txt"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get pdb -A -o json > "$OPERATOR_DIR/scale-pdb.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get pv -o json > "$OPERATOR_DIR/scale-pv.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get pvc -A -o json > "$OPERATOR_DIR/scale-pvc.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s get volumeattachments -o json > "$OPERATOR_DIR/scale-attachments.json"
```

Review resource requests, taints/tolerations, topology constraints, desired/Ready
replicas, pending pods, PV node affinity and reclaim/retention policies. Do not
infer safety from the absence of VolumeAttachments: local-path and hostPath data
are node-local. Verify backup integrity and a usable restoration procedure
before removing their nodes. The [persistence map](../architecture.md#persistence-and-exposure)
identifies the important differences:

- MySQL has one replica with local-path storage; its node cannot simply be
  replaced without assessing data access and restoration.
- Qdrant has three dev replicas and local-path storage/snapshot references;
  inspect collection replication, cluster membership, binding and recovery.
  Three pods do not establish data redundancy for every collection.
- Grafana/Prometheus use hostPath PVs. Review monitor workers affected by api
  index shifts even when monitor count is unchanged.
- Redis declares no data PVC; ANN indexes and DLQ TTL records can be lost.
  NATS Core has no durable ingestion guarantee; drains/restarts can drop work
  while consumers are absent. Gateway emptyDir logs also disappear.
- Only model PDBs are declared in the app tree, with maxUnavailable 1. At one
  replica they do not guarantee uninterrupted service, and they do not protect
  database or queue storage.

A PDB regulates voluntary evictions; it does not stop Terraform from deleting
the VM. [Kubernetes drain documentation](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_drain/)
describes eviction and local-data handling. Select a per-node drain/recovery
order with the operator; no generic drain command or PDB bypass is provided
here because workload/storage preconditions have not been validated. Plan-only
success does not authorize apply. Downtime is possible.

## Scale-up plan

Obtain CURRENT_COUNT from reviewed live state, not the tracked default. After
approval to prepare a change, persist the desired count in the existing HCL
input. If using the secret-file worker_pools override, retain the complete map,
other pool counts and server types. Do not print that private file for review.

For example, **only if** api is observed at 3 and its effective desired count
has been persisted as 4:

```bash
make config-check ENV=dev
make cluster-scale ENV=dev POOL=api COUNT=4 CURRENT_COUNT=3 DRY_RUN=1
# With authoritative state and authorization to contact the dev backend:
make cluster-scale ENV=dev POOL=api COUNT=4 CURRENT_COUNT=3 STATE_REVIEWED=1
```

Use a fresh private OPERATOR_DIR as documented in
[saved-plan commands](commands.md#state-custody-previews-and-saved-plan-apply).
Dry-run validates local counts only; a real plan refreshes state and verifies
its actual before/after api counts against CURRENT_COUNT/COUNT. Existing worker
pool names and positive integer counts are mandatory; zero/equal counts, new
pools, mismatched persisted counts and master changes are rejected.

Review dev.tfplan/plan.log privately, all pool indices and deletion actions.
If there are no worker deletions/replacements, an explicitly approved apply is:

```bash
make cluster-up ENV=dev STATE_REVIEWED=1 \
  REVIEWED_SHA='<reviewed-sha256>' CONFIRM=apply-dev
```

If **any** worker is replaced or deleted, complete the placement/storage/drain
review for those workers first. With renewed operator approval, apply the same
saved plan using the extra acknowledgments:

```bash
make cluster-up ENV=dev STATE_REVIEWED=1 \
  REVIEWED_SHA='<reviewed-sha256>' CONFIRM=apply-dev \
  REPLACEMENTS_REVIEWED=1 REDUCTION_REVIEWED=1
```

These flags acknowledge risk; they do not execute drains, copy data or validate
backups. After apply, privately verify expected nodes/counts, all workload and
storage health, Flux revisions, then authorized [smoke](verification.md).

## Reduction and recovery

Persisting a smaller positive count and using cluster-scale additionally needs
REDUCTION_REVIEWED=1, **including for preview**. Example only after api was
observed at 4, its effective desired count was persisted as 3 and the complete
review above was approved:

```bash
make cluster-scale ENV=dev POOL=api COUNT=3 CURRENT_COUNT=4 \
  REDUCTION_REVIEWED=1 DRY_RUN=1
make cluster-scale ENV=dev POOL=api COUNT=3 CURRENT_COUNT=4 \
  REDUCTION_REVIEWED=1 STATE_REVIEWED=1
```

A real reduction is not authorized by this example or this documentation task.
Review the exact saved plan, perform only the installation's separately
approved drain/data recovery steps, renew deletion acknowledgments, and apply
through cluster-up. Never bypass PDBs or remove PVCs merely to unblock it.

Before apply, abandoning a plan means restoring the prior intended input and
discarding the unused plan through private operator custody; no VM changed.
After an attempted/failed apply, stop and inspect authoritative partial state,
remaining nodes, workload/data placement and private logs. The receipt is single
attempt. Restore prior desired counts only with a **new** reviewed plan and
approval. Recreated VMs are not the old local storage, and increased count is
not a guaranteed rollback. Use verified backup restoration where needed and
re-run health/plugin acceptance; never replay an old plan or destroy the cluster.
