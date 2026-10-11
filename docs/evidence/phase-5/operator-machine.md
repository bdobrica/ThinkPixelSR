# Operator-machine inspection, 2026-10-11

Follow-up for **P3-03**, the earliest incomplete task, and the dependent
P3-04/P5-04/P5-05 acceptance gates. The operator supplied the original
provisioning machine and required preservation of all live environments and
running containers. No live acceptance checkbox is closed by this inspection.

## Local findings

The original ThinkPixelInfra checkout was located outside this repository.
It contains one dev local-state file and its backup in the original Terragrunt
cache. The state records Terraform 1.10.3, serial 253, one master and four worker
instances in the node modules. Additional server entries belong to firewall
module references; counting every server entry would overcount nodes. These
are local snapshot observations, not proof of current cloud state or sufficient
authorization to apply. State, cache, workspace and keys were neither moved nor
modified. No new state was initialized in ThinkPixelSR.

Installed tools: Make 4.4.1, Python 3.13.5, Terraform 1.12.1, Terragrunt 0.81.0,
kubectl 1.32.0 and Docker Buildx 0.34.0. `make doctor` exits 2 because the
wrappers require Terragrunt >=0.96.1. The installed toolchain was left intact.
The original secret file, state and backup report mode 0755; private SSH keys
report 0600. Secret-file permissions do not meet the new validator's contract.
No credentials were copied, displayed, changed or loaded into a new `.env`.

## Approved read-only dev observations

Before any cluster query, the explicitly selected kubeconfig context's server
host was compared in memory with the original state's master address and
matched. Raw kubeconfig, IPs, resource messages and credentials are omitted.
Sandbox network access initially failed; the operator approved the subsequent
read-only GET queries outside the sandbox.

| Resource | Observed status |
| --- | --- |
| Nodes | 5/5 Ready; no `pool` labels observed |
| thinkpixel pods | 10/11 Ready; the remaining pod is Failed, terminated reason Unknown |
| flux-system pods | 11/11 Ready |
| FluxInstance | 0/1 Ready; ReconciliationFailed |
| GitRepository | 0/1 Ready; GitOperationFailed / FetchFailed |
| Kustomizations | 0/6 Ready; ArtifactFailed |

The source retains the ThinkPixelInfra URL. Its Ready condition refers to the
current generation, and the private error text includes repository-access
failure indications. This does not prove token expiration specifically. The
operator suspects expiration and is updating the Git token independently.
Recovery has not yet been observed. A Failed pod in the list does not by itself
prove an active application outage; no availability claim follows from these
counts. No source URL, Secret, reconciliation setting or workload was changed.

The operator subsequently confirmed updating the live Kubernetes Secret.
Repeated approved read-only queries still showed GitOperationFailed with
`authentication required`, the same six ArtifactFailed Kustomizations and
unchanged node/pod counts. The source references `github-token` and declares
a one-minute interval; Secret metadata is readable. The source-controller
Deployment has one available replica. No restart or forced reconciliation was
performed. Credential validity, repository permissions and Secret field
contents have not been inspected; recovery remains unverified.

## Recovery after operator reconciliation

After updating the live Secret, the operator reported running
`flux reconcile ks flux-system --with-source`. Subsequent approved read-only
queries confirmed recovery:

- FluxInstance 1/1 Ready, GitRepository 1/1 Ready and Kustomizations 6/6 Ready.
  Every Ready condition refers to the current resource generation; none of
  these resources is suspended.
- The source and all six Kustomizations report revision
  `refs/heads/main@sha1:9e5fc87495832d3a2554965341cbeb43911ff5f5`.
  The Git URL still points to ThinkPixelInfra; no SR cutover occurred.
- FluxInstance reports distribution revision
  `v2.9.6@sha256:3c9f770f8d59394a07088e274df43276b6ad69c5b570cb639b3dda1227f96a98`,
  compared with v2.9.4 before the operator action. Reconciliation requests a
  sync; the observed distribution change establishes that an upgrade also
  occurred during this recovery. No upgrade command was run by the agent.
- Nodes remain 5/5 Ready, thinkpixel pods 10/11 Ready and flux-system pods
  11/11 Ready. The earlier Failed pod remains included in the application count.
- `make flux-check ENV=dev KUBE_CONTEXT=default`: passed against the live
  cluster, including operator/CRD/Secret metadata prerequisites and root readiness.
- `make status ENV=dev KUBE_CONTEXT=default`: passed; additionally reports
  NATS pods 2/2 Ready and monitoring pods 7/7 Ready.

These results satisfy the live read-only readiness portion of P3-04. Guarded
attachment, ownership validation across an attachment, plugin acceptance and
source cutover/switch-back remain unperformed, so the full item stays open.
Pod/controller readiness is not end-to-end search or data-integrity evidence.

## Offline verification repair and results

The first `make verify` failed for two reasons: three already tracked client
planning documents were outside the audit allowlist, and the optional real
Terragrunt forwarding test attempted to run against unsupported 0.81.0.
The audit now allows exactly `clients/README.md`, `clients/PLAN.md` and
`clients/TODO.md`; all candidate secret checks and runtime restrictions remain.
The optional forwarding test explicitly skips unsupported versions. Doctor
and real wrapper operations continue rejecting unsupported Terragrunt.

- `make help`: passed; help only.
- `make doctor`: expected exit 2 for unsupported Terragrunt.
- `make verify`: passed, 42 tests with one explicit optional forwarding skip.
  Python/Make/shell syntax, Terraform/HCL formatting, six Kustomize renders,
  401/405 frozen byte-identical paths and candidate secret checks passed.
- `make config-check ENV=dev`: expected exit 2, missing local secret file.
- `make config-check ENV=prod`: expected exit 2, unimplemented prod, no fallback.
- `make config-check ENV=invalid`: expected exit 2, invalid selector.
- Documentation links and `git diff --check`: passed after the evidence update.

## Next gates

Read-only Flux recovery and wrapper checks now pass. Do not
bootstrap or cut over merely to repair a fetch error: renewed source access can
itself resume normal reconciliation, so review the selected remote revision.
Retain original state/cache/workspace custody and separately review a compatible
wrapper toolchain before preparing any real plan. Scaling additionally needs
actual node correspondence, placement/PDB/PV review and an inspectable plan;
the local four-worker snapshot is insufficient. Plugin fixtures, registry
publication, saved-plan apply and source cutover remain separately authorized
live gates. No init/plan/apply, SSH, Docker daemon request, build/push, drain,
scale, bootstrap, fixture write, source switch or repository push was performed.
