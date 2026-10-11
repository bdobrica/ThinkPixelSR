# Dev diagnostics and recovery limits

Start with the smallest failing layer: local configuration, infrastructure/API
access, Flux source/tenant, workload startup, then gateway/queue/model/vector
behavior. These commands were reviewed against the source and local CLI help;
they have not been executed against a live installation. Read
[verification](verification.md) before a writable smoke or recovery operation.

## Private capture and target selection

Live reads need an operator-approved dev context. Never rely on the current
context, print Secret objects, `printenv` inside pods, enable shell tracing or
paste raw logs into issues. Kubernetes metadata/events, request logs, DLQ data
and database responses can contain addresses, payloads or credentials. Keep
captures in private storage outside Git, then share sanitized assertions only.

```bash
umask 077
export OPERATOR_DIR="$(mktemp -d /tmp/thinkpixelsr-diagnostics.XXXXXX)"
export KUBE_CONTEXT='<verified-dev-context>'
make doctor
make status ENV=dev KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get pods -A -o wide > "$OPERATOR_DIR/pods.txt"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get events -A --sort-by=.metadata.creationTimestamp > "$OPERATOR_DIR/events.txt"
```

OPERATOR_DIR must be private on POSIX storage (mode 700), with owner-only files.
It is not state/backend configuration. Keep a separate fresh plan/run directory
when retrying a guarded operation; never remove apply.attempted to replay it.
Root command errors intentionally suppress raw diagnostics; consult their
private logs and the checks below. `status` reports Ready counts, so inspect
the affected resource conditions privately when those counts are insufficient.

## Configuration, Terraform and API access

| Symptom | Check / next action |
| --- | --- |
| Missing/invalid ENV or prod rejection | Choose dev explicitly. Prod is unimplemented, not a credential problem; never copy dev to prod |
| Missing secret/key, bad permissions, placeholder token | Use [existing path/schema contract](../configuration.md), private resolved file modes and matching keys. config-check does not authenticate |
| Unknown dotenv key/HCL expression or ambient override | Use the restricted literal schema. Keep advanced existing setups on the separately reviewed direct workflow; never source dotenv or remove controls blindly |
| Init fails | Inspect private init.log for pinned-provider access/checksum/backend errors. Preserve lockfiles; do not use init upgrade or migrate state to silence a failure |
| Plan proposes a duplicate cluster/all creates | Stop. Locate authoritative backend/cache/workspace/lineage and account ownership; missing tracked state is not proof of an empty project |
| Lock or partial apply failure | Establish whether another operation is active. Preserve state/logs, inspect partial resources and review a new plan after repair; no casual force-unlock/replay |
| Stale receipt/hash or existing artifact | Inputs/workspace/plan bytes changed or a run already happened. Use a fresh private directory and newly reviewed plan |
| SSH / kubectl unavailable or certificate failure | Verify host fingerprint, management key, user cluster, admin-IP allowlist, reachable API endpoint and TLS SAN/trust via [Hetzner guide](../deployment/hetzner.md#ssh-kubeconfig-and-network-checks). No global firewall opening or insecure TLS workaround |
| API hostname/TLS works but listener unhealthy | Privately inspect DNS, certificate, app listener external 8080→30080 and HTTP /ping backend health; inspect gateway scheduling/service endpoints next |

No doctor/config result proves account/project/zone permissions, state custody,
SSH pairing or live Kubernetes access. Do not dump state/cloud-init or render
credentials to debug configuration.

## Flux and Sealed Secrets

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get fluxinstance flux -o json > "$OPERATOR_DIR/flux-instance.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get gitrepository flux-system -o json > "$OPERATOR_DIR/git-source.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get kustomizations -o json > "$OPERATOR_DIR/kustomizations.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get helmreleases -A -o json > "$OPERATOR_DIR/helm-releases.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get sealedsecrets -A -o json > "$OPERATOR_DIR/sealed-secrets.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n flux-system \
  get secret github-token -o name > "$OPERATOR_DIR/git-secret-name.txt"
```

Secret lookup requests only its name; do not change it to yaml/json. Keep
SealedSecret ciphertext/status captures private too. Missing Flux CRDs or
operator means initial bootstrap is unresolved; see
[bootstrap order](../deployment/fluxcd.md#bootstrap-inputs-and-order), not an
invented Helm reinstall. Existence of github-token does not prove fetch/status
permission. Compare source URL/ref/path/artifact revision, observed generation,
Ready conditions and each tenant's applied revision.

Inspect failing tenant build/Helm events privately for missing substitutions,
RBAC, Helm dependencies, chart fetch/cosign failures or load restrictions.
Three inherited overlays need permissive **offline** loading; no live result
proves their controller behavior. Do not change security flags as a docs fix.
Decryption failure requires the original controller key and correct scope/name;
newly sealing/replacing secrets is a separately approved credential change.
Check cert-manager Certificate/Issuer conditions and reflector operation for
NATS TLS delivery. Never print the certificate private key or nkey seed.

Repair desired workload configuration through its existing GitOps authority.
The old ThinkPixelInfra main remains the source. Patching generated resources
can be overwritten; `prune: true` makes unreviewed ownership/source changes
particularly risky. Source switch-back is in [migration](../migration.md), not
a general fix for queue/data problems.

## Image pulls and model startup

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  get deployments,statefulsets,pods -o json > "$OPERATOR_DIR/workloads.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  get secret quay-io-secret -o name > "$OPERATOR_DIR/pull-secret-name.txt"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  logs deployment/mpnetv2 --tail=200 > "$OPERATOR_DIR/mpnetv2.log"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  logs deployment/snowflake-arctic --tail=200 > "$OPERATOR_DIR/arctic.log"
```

For ImagePullBackOff, compare the **exact** desired image tag, usable pull secret
and published platform manifests with [images](images.md). Check actual imageID
digests, ARM64 node architecture and private pod events. A version tag may have
been overwritten; do not substitute latest. For Pending/OOMKilled/CrashLoop,
inspect memory/CPU requests/limits, disk, taints/tolerations, probes and previous
container logs scoped to the failing pod. Model assets are baked into images;
a build failure may be mirror/package/native-wheel access rather than GitOps.

For an approved read-only model liveness probe, open a loopback tunnel in one
terminal (this contacts the cluster and remains running until Ctrl-C):

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  port-forward --address=127.0.0.1 service/mpnetv2 18000:8000 > "$OPERATOR_DIR/model-forward.log" 2>&1
```

In another terminal using the same private OPERATOR_DIR:

```bash
curl --fail --silent --show-error --max-time 30 \
  http://127.0.0.1:18000/ping --output "$OPERATOR_DIR/model-ping.json"
```

Confirm the model's existing ping response privately, then close the tunnel.
This proves liveness of the forwarded model only, not inference or gateway-to-
model routing. Actual embedding behavior is exercised by the synthetic
disposable-site [store/search smoke](verification.md#minimal-qdrant-api-smoke-disposable-site-only).
Only mpnetv2 and snowflake-arctic have dev overlays. Do not deploy another model
or change an existing site's model merely to pass diagnostics.

## Gateway, authentication and schema

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  logs deployment/api-gateway -c api-gateway --tail=200 > "$OPERATOR_DIR/gateway.log"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  get services,endpointslices -o json > "$OPERATOR_DIR/services.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  get pvc -o json > "$OPERATOR_DIR/thinkpixel-pvc.json"
```

Read gateway logs privately: debug/auth/callback/request entries may contain
API keys, JWTs or text. `/ping` is liveness; `/ready` checks MySQL only. Use
`make verify-live` with the approved HTTPS endpoint for those assertions.
For token failure, check the correct test-site key, active hashed MySQL row,
gateway database access and JWT lifecycle privately. Missing X-API-Key returns
400; invalid-key DB lookup can return 500. Do not assume every failure is 401
or rotate a real site's key to satisfy smoke.

Registration requires reachable matching `/searchpixel/v1/` callbacks, correct
domain/path/nonce and usable index-node allocation. Gateway/mock defaults use
`/thinkpixel/v1/`, whereas dev config matches the actual plugin. Base SQL lacks
new gateway columns; local db-init skips patches and database/init.sh uses the
wrong plural version-table name. Inspect the live schema read-only through
existing private DB tooling; do not run either initializer on shared data.
Schema/node setup needs a reviewed repair. `/refresh/apikey` and batch guidance
have recorded context/schema mismatches; see [known blockers](../evidence/phase-0/README.md#baseline-configuration-and-unresolved-assumptions).

## NATS ingestion and DLQ

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n nats \
  get pods,services,certificates,issuers -o json > "$OPERATOR_DIR/nats-resources.json"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  get secret nats-tls-secret nats-nkey-secret -o name > "$OPERATOR_DIR/nats-secret-names.txt"
```

Verify gateway-to-NATS DNS/service routing, reflected TLS/nkey mounts and
certificate trust without reading credential contents. Check gateway subscriber
start/stop/retry errors in the private log above, not just NATS pod Ready.
Default subject is `store.jobs`, DLQ suffix `.dlq`; confirm actual configured
subjects. Subscriber toggling depends on model latency (default target 100ms,
check interval 5s); high latency can unsubscribe it. Dev is Core NATS with
JetStream/cluster disabled and ordinary Publish/Subscribe, not a durable queue
or queue group. Multiple gateway subscribers must not be assumed to distribute
each job exactly once.

Useful existing gateway metrics at `/metrics` include
`api_gateway_nats_messages_published_total`,
`api_gateway_nats_messages_processed_total`, `api_gateway_nats_dlq_messages_total`,
`api_gateway_nats_unmarshal_errors_total` and `api_gateway_model_latency_seconds`.
Compare changes during an approved fixture run; counters do not prove a specific
document was indexed. No durable backlog length is supplied by Core NATS here.
Avoid a diagnostic subscription that captures customer document payloads.

A 202 means publication, possibly partial, not completed indexing. Confirm
received/pending/failed counts and actual fixture points. Retries/DLQ records can
be sensitive, expire or be lost with Redis; inspect `/dlq/stats` and, only if
needed, `/dlq/messages` through an existing private Bearer curl config scoped to
the dedicated site. Reinjection tools publish work and are **mutating**, requiring
separate approval and inspection; do not invoke them to verify prose.

## Qdrant, Redis and storage

```bash
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s -n thinkpixel \
  logs statefulset/qdrant --tail=200 > "$OPERATOR_DIR/qdrant.log"
kubectl --context "$KUBE_CONTEXT" --request-timeout=30s \
  get pv -o json > "$OPERATOR_DIR/pv.json"
```

For Qdrant connection/authorization failure, inspect the site's allocated
indexing_node and qdrant backend, gateway secret reference, service endpoints,
Qdrant readiness/config and PVC binding. Collections are `site_<site ID>`;
points have named dense/sparse vectors and `site_id`, `post_id`, `offset`, `text`
payload. Use approved private Qdrant tooling/authentication to inspect **only**
the disposable site's collection. Check actual collection vector schema,
point IDs/payload and cluster membership/replication; do not recreate/delete
collections or publish content dumps. Read-only filtered scroll/count inspection
can confirm a fixture post ID; a similar semantic result alone cannot confirm
cleanup. The full smoke requires the expected ID and synthetic text.

Search fuses dense/sparse Qdrant prefetch with RRF; no separate BM42 reranker is
established by code. Search can return 500 before collection creation or 408
after its 10s wait even though the dev model HTTP timeout is 180s. Investigate
warm-up, node allocation and model latency; do not silently raise timeouts as a
documentation fix.

Redis sites use the existing ANN path, with no claimed Qdrant hybrid parity.
Inspect Sentinel discovery/master name, existing credential references and
service reachability through private tools. Redis also serves the DLQ for Qdrant
sites. Kubernetes Redis has no data PVC; monitoring uses hostPath and database/
vector services use local-path. See [scaling/storage review](scaling.md#before-any-deletion-or-replacement)
before restarting/removing nodes. Never run debug/redis-extractor.sh as a
read-only check: it creates/deletes resources and passes a password in argv.

## WordPress and stopping criteria

If direct API retrieval works but WordPress does not, compare the actual plugin
build/compiled gateway URL, callback settings, nonce/exchange, token expiry,
actual submitted post ID and UI result/link with the
[plugin golden path](verification.md#wordpress-plugin-golden-path-separate-acceptance-test).
Plugin processed IDs can fall back to submitted IDs; they do not prove indexing.
Its batch-size fallback is a known gap. The local mock cannot verify the real UI.

Stop after bounded failures, preserve sanitized comparisons and private logs,
and settle retries before scoped fixture deletion. Use a reviewed recovery
procedure for ownership, node/data or registry problems. Git source rollback
cannot undo database writes, node-local data loss or overwritten tags. Do not
wipe shared volumes, delete all collections, bypass PDBs, migrate state or
alter production to investigate a documentation task.
