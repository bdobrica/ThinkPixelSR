# GitOps and migration reference inventory — P0-03

Paths and names refer to the frozen source in [architecture](../architecture.md).
The [manifest index](../evidence/phase-0/manifests.tsv) records top-level kinds
and names for every tracked Kubernetes YAML document without encrypted values.

## Source and reconciliation

| Source artifact | Baseline behavior / preservation requirement |
| --- | --- |
| `k8s/flux-system/base/flux-instance.yaml` | `FluxInstance/flux` in `flux-system`, Flux distribution `2.x`, `ghcr.io/fluxcd`, operator manifests OCI tag `latest`; source/kustomize/helm/notification controllers |
| Its `spec.sync` | GitRepository URL `https://github.com/bdobrica/ThinkPixelInfra`, ref `refs/heads/main`, `github-token` pull secret; dev patch selects `k8s/flux-system/dev` |
| `flux-notification.yaml` | ResourceSet produces GitHub Provider/Alert `github-status`; address points to the same old repository; secret `github-token` |
| `flux-operator.yaml` | ResourceSet produces OCIRepository/HelmRelease `flux-operator`, chart `oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator`, semver `*`, cosign GitHub OIDC verification |
| `tenant-apps.yaml` | ResourceSet `apps`: cert-manager, reflector, monitoring, thinkpixel, nats, all `dev`; generates Namespaces, ConfigMaps, service accounts, RoleBindings and Kustomizations |
| Generated Kustomizations | `<tenant>-dev`, namespace `flux-system`, sourceRef GitRepository `flux-system`, path `./k8s/apps/<tenant>/dev`, `prune: true`, serviceAccountName `flux-operator`, wait/timeout and runtime substitutions |
| Privileged tenants | cert-manager and reflector have targetNamespace `flux-system`; others use their tenant namespace. Actual resulting Helm workload namespaces require live verification |
| `flux-runtime-info.yaml` + dev patch | `ENVIRONMENT`, `CLUSTER_DOMAIN` substituted into app manifests; patched dev values are not a generic prod configuration |

This is an **operator-managed FluxInstance** layout. There is no checked-in
`flux bootstrap` invocation, standalone GitRepository manifest, initial operator
installation script, Git credential creator, or Sealed Secrets controller
installer. The ResourceSet managing the operator already depends on its CRDs.
Installation order and cluster decryption-key custody are therefore unverified
manual prerequisites. Do not invent a new bootstrap method in Phase 0.

`k8s/flux-system/prod` does not exist. Thinkpixel and monitoring prod overlays are
empty; cert-manager/reflector/nats have dev overlays only. Offline Kustomize
rendering is not Flux reconciliation, Helm installation or CRD validation.

## Persistence, namespace and secret map

| Component | Checked-in storage / names / references |
| --- | --- |
| Gateway (`thinkpixel`) | `Deployment/api-gateway`, one replica, NodePort 30080 -> 8080, pull secret `quay-io-secret`; `api-gateway-config`, `api-gateway-secret`, `mysql-secret`, `qdrant-secret`, `redis-secret`; NATS volumes `nats-tls-secret`, `nats-nkey-secret` |
| Gateway logging | Fluent Bit sidecar uses `fluent-bit-secret`, S3 settings, request/DLQ log and Fluent Bit `emptyDir` volumes. `dlq-config.yaml` exists but is absent from base kustomization and deployment envFrom |
| MySQL (`thinkpixel`) | StatefulSet `mysql`, one replica, `mysql-data` claim template, local-path RWO 5Gi at `/var/lib/mysql`; `mysql-secret`; no checked-in DB schema init job |
| Qdrant (`thinkpixel`) | StatefulSet `qdrant`, base one replica, dev patch **three**; claim templates `qdrant-storage`, `qdrant-snapshots`, `qdrant-snapshot-restoration`, each local-path RWO 1Gi; config and `qdrant-secret`; separate explicit snapshot claimName references also exist and binding needs verification |
| Redis (`thinkpixel`) | Dev shard `01`: master/replica and sentinel `01`; `redis-secret`; no declared Redis data PVC despite append-only command; do not assume persistence across replacement |
| Models (`thinkpixel`) | MPNetV2 and Arctic deployments/services; no data PVC; baked-in weights; PDB maxUnavailable 1 each; HPA min 1, dev max 2 each |
| Grafana (`monitoring`) | `grafana-pv` hostPath `/mnt/data/grafana`, RWO 5Gi; `grafana-pvc`, `grafana-secret`; NodePort 30030 -> 3000 |
| Prometheus (`monitoring`) | `prometheus-pv` hostPath `/mnt/data/prometheus`, RWO 10Gi; `prometheus-pvc`, `prometheus-secret`; separate service account/RBAC |
| NATS (`nats`) | HelmRelease + HelmRepository; NATS Core with JetStream/cluster disabled; self-signed Issuer/Certificate creates `nats-tls-secret`; `nats-nkey-secret`; certificate reflection annotation allows `thinkpixel` |
| Registry | SealedSecret `quay-io-secret`, consumed by gateway/models; preserve namespace/name and controller key |
| WordPress base | `Deployment/wordpress` is present but not included in dev resources; does not install the separate plugin automatically |

Base and dev overlays carry SealedSecret templates/patches for gateway, Redis,
Qdrant, MySQL, registry, monitoring and NATS. Encrypted payloads were not copied
into evidence or decrypted. Git credentials and TLS keys are external/generated
Secret consumers. Inspect live names, PVC/PV binding, node placement, retention,
decryption and reflection before any rollout or worker reduction. Only model
PDBs are declared in these application manifests; that is not a general storage
disruption safeguard.

## Image identities

| Workload | Source image reference |
| --- | --- |
| Gateway / Fluent Bit | `quay.io/bdobrica/thinkpixel-api-gateway-multi:0.7.1` / `fluent/fluent-bit:3.2.6` |
| MPNetV2 / Arctic dev overlays | `quay.io/bdobrica/thinkpixel-mpnetv2-multi:0.3.5` / `quay.io/bdobrica/thinkpixel-snowflake-arctic-multi:0.1.13` |
| Model base placeholder | `quay.io/bdobrica/thinkpixel-model-multi:0.1.6`, replaced by dev overlays |
| MySQL | `percona/percona-server:8.0.40-31.1-multi` |
| Qdrant container and ownership init | `docker.io/qdrant/qdrant:v1.13.4` |
| Redis master and replica | `redis/redis-stack:latest` |
| Sentinel / config init | `redis/redis-stack:latest` / `busybox:1.35` (local sentinel Dockerfile instead starts from `redis:7.4.1-bookworm`) |
| Grafana / Prometheus / node exporter | `grafana/grafana:11.5.1` / `prom/prometheus:v3.1.0` / `prom/node-exporter:v1.8.2` |
| WordPress unused base | `wordpress:5.8-apache` |
| Helm version constraints | cert-manager `v1.*`, reflector `9.*`, NATS `1.*`; actual pulled charts and derived images unverified |

No image digest pins or registry inspection prove which versions actually run.
Local Compose uses different MySQL/Qdrant versions; see [image map](images.md).
Keep runtime identities unchanged until a separate reviewed cutover.

## Absolute repository references and cutover checklist

The exact-case and case-insensitive audit of tracked files found five matching
lines (four files), including three absolute URL references:

| File | Absolute old reference | Treatment now |
| --- | --- | --- |
| `cluster/README.md` | Clone URL `https://github.com/bdobrica/ThinkPixelInfra.git`; following `cd ThinkPixelInfra/cluster/live/dev` is a relative folder reference | Documentation-facing rename belongs to Phase 1 |
| `k8s/flux-system/base/flux-instance.yaml` | `https://github.com/bdobrica/ThinkPixelInfra` | Preserve live sync source until operator-approved cutover |
| `k8s/flux-system/base/flux-notification.yaml` | `https://github.com/bdobrica/ThinkPixelInfra` | Preserve GitHub status destination alongside source |
| `README.md` | Heading `ThinkPixelInfra` (name only, not an absolute URL) | Documentation-facing rename belongs to Phase 1 |

The fifth matching line is the relative `cd` reference in `cluster/README.md`.
No absolute old repo reference was found in workflow, Dockerfile,
build scripts or badges; there are no checked-in badges. Quay image paths are
separate identities and must not follow a repository rename.

- [ ] Preserve old remote/history and this baseline; import tracked files and LICENSE in Phase 1 without ignored files.
- [ ] Verify the new Git remote, main branch contents, source path and Git credential access before proposing any Flux edit.
- [ ] Record live FluxInstance, generated GitRepository/Kustomizations, reconcile revision, and GitHub Provider address; source files alone do not prove current live values.
- [ ] Review both sync URL and notification address, credentials, webhook/GitHub App settings and external repository integrations. Webhooks/settings are not represented in Git and were not queried.
- [ ] Inspect `prune: true`, namespaces, SealedSecret scope/key and PVC ownership against a zero-drift workload render.
- [ ] Retain the old source URL/ref/path and credentials for switch-back; do not delete or repoint the old repository.

No remote, webhook, namespace, source, image, secret or persistent volume was changed.
