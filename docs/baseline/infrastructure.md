# Infrastructure inventory — P0-02

This records the tracked ThinkPixelInfra snapshot identified in
[architecture](../architecture.md). It does not prescribe new configuration or
authorize provisioning. File paths are relative to that source repository.

## Versions, roots and state

| Artifact | Exact baseline |
| --- | --- |
| Terraform root | `cluster/infra/main.tf`, `providers.tf`, `variables.tf`; local child modules only |
| Terraform constraint | `>= 1.10.0` in `main.tf`; no exact CLI pin. `cluster/README.md` says v1.x and is less strict |
| Terragrunt | No checked-in exact version pin; README says `>= 0.31.8`, not demonstrated compatibility with today's CLI |
| Hetzner Cloud | `hetznercloud/hcloud`, constraint `~> 1.48`; both lockfiles select `1.49.1` |
| Hetzner DNS | `timohirt/hetznerdns`, exact `2.1.0`; dev lockfile selects `2.1.0`; infra lockfile omits DNS |
| Lockfiles | `cluster/infra/.terraform.lock.hcl`, `cluster/live/dev/.terraform.lock.hcl`; no prod lockfile |
| Dev Terragrunt | `terraform.source = find_in_parent_folders("infra")`; reads environment-local `.secrets.hcl` and SSH files |
| Prod Terragrunt | `cluster/live/prod/terragrunt.hcl` is zero bytes; no source/inputs/secrets contract defined there |
| Backend | No tracked `backend`, `remote_state`, or generated backend block; no checked-in state files |
| K3s | Cloud-init downloads `https://get.k3s.io` without a version pin; disables Traefik on initial server |

`~> 1.48` is a constraint, not an exact provider pin. Preserve both lockfiles and
their hashes; do not use an init upgrade as part of migration. The installed
inspection tools were Terraform 1.14.3 and Terragrunt 0.96.1; that records the
checker environment, not the versions used by a deployed cluster.

Without a backend declaration Terraform's default is local state. Terragrunt
executes the downloaded root in its cache; the actual working state location,
workspace, provider initialization and any operator-supplied backend arguments
were **not inspected**. Never infer “no live infrastructure” from missing tracked
state. Before Phase 1 provisioning, an operator must locate the authoritative
state/backend and securely preserve its configuration, workspace, lineage,
serial and recovery copy. Do not commit state, render plans to shared logs, move
state, import resources or create a fresh parallel state during this makeover.

## Sanitized dev configuration

| Input / consumer | Tracked value or requirement |
| --- | --- |
| `cluster_prefix`, location, OS | `k8s`, `fsn1`, `debian-12` |
| `cluster_domain`, aliases | One dev domain and one parent-domain alias; actual hostnames intentionally omitted here; authoritative values remain in `cluster/live/dev/terragrunt.hcl` |
| `master_pool` | One `cax21` control-plane node |
| `worker_pools.api` | Three `cax21` nodes |
| `worker_pools.monitor` | One `cax21` node |
| `admin_ips` | One allow-listed operator IPv4; value redacted |
| `exposed_apps.api` | HTTPS external 8080 -> internal 30080; HTTP health check `/ping` |
| `exposed_apps.monitor` | HTTPS external 3000 -> internal 30030; HTTP health check `/api/health` |
| `.secrets.hcl` | `read_terragrunt_config(".secrets.hcl")`; `inputs` must supply `hcloud_token` and `hetznerdns_token` |
| SSH public files | `.master.key.pub`, `.worker.key.pub`, `.management.key.pub` read with `file()` relative to dev root |
| SSH private files | `.master.key`, `.worker.key`; management private key is an operator access prerequisite, not a Terragrunt input |

Dev merges base inputs, then `local.secrets.inputs`, then `local.ssh_keys`.
Consequently secrets inputs may override even non-secret base settings; SSH
file contents take precedence last. The base `hcloud_token = "dummy"` is not a
usable credential. The cloud/DNS token variables are declared sensitive, but
SSH private-key variables are not marked sensitive and are embedded into
cloud-init (`cluster/infra/user-data/main.tf`, `/root/.ssh/id_rsa`). Treat state,
plans and cloud-init as sensitive. Never print their contents in evidence.

Public dev key files are tracked. Ignored secret/private-key files exist in the
local source checkout; only existence was checked, never contents or validity.
This session has no authorization to use them. Prod has no equivalent configured
baseline; do not copy dev settings or keys into prod as a fallback.

## Identity and dependency preservation

`cluster/infra/main.tf` calls `network`, `k8s`, `apps`. Networking creates a
private network/subnet. `k8s/main.tf` calls master, worker and firewall; master
and worker each call the shared load-balancer module. Apps add listener services,
managed certificates and DNS/rDNS to the worker load balancer. Cloud-init
retrieves node tokens over SSH and joins workers, adding a pool-specific taint.

Preserve module addresses, `hcloud_server.this` count indices, network ranges,
`k8s-master-*` / `k8s-worker-<pool>-*` names, `k8s-master-lb` / `k8s-worker-lb`,
DNS zones/records and certificate identities. Load balancers enable deletion
protection. Worker nodes are flattened from all pools into a **single count-based
resource**: increasing an earlier pool can shift indices of later pools. A future
scale wrapper must review replacements across every pool; a count change is not
proof of an additive plan. No scaling or control-plane change was performed.

The inherited direct commands in `cluster/README.md` are `terragrunt init`,
`terragrunt plan`, `terragrunt apply`, run from the chosen environment directory.
These were inspected only. Init can access providers/backends; plan can refresh
remote resources and expose sensitive material; apply mutates cloud resources.
No root Make wrapper exists yet, and an empty prod root is not a valid alternate
deployment path. See [verification evidence](../evidence/phase-0/README.md).
