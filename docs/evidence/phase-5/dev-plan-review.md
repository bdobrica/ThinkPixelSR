# P3-03 / P5-04: isolated dev plan review, 2026-10-11

The operator authorized isolated tooling, authoritative-state review and a
no-apply dev plan, with preservation of the live cluster and all running
containers. **The plan failed and is not suitable for apply.** No acceptance
item requiring a successful plan, apply or scaling test is closed here.

## State and tooling custody

The original provisioning checkout contains one current dev state and backup
in its Terragrunt cache. The workspace is default, with no workspace marker,
remote-backend metadata, automatic tfvars or active state-lock marker found.
The state snapshot has serial 253 and records one master, three api workers
and one monitor worker. Its Terraform version is 1.10.3.

A private mode-0700 session under `/tmp` holds recovery snapshots, an isolated
checkout, credentials copied with mode 0600, provider metadata and private
logs/plans. The original credentials, state, backup and cache were not modified.
SHA256 comparisons before/after the plan confirmed the original current state
and backup were unchanged. Snapshot lineage and serial matched the original.
Private artifacts are deliberately outside Git; `/tmp` is temporary custody,
not a durable backup location. The original authoritative state remains in its
existing location. Raw snapshots, logs and plans must not be published.

Terragrunt v0.96.1 was downloaded from its official GitHub release into the
session and checked against that release's SHA256SUMS. This verifies checksum
agreement, not independent signature verification. Existing Terragrunt 0.81.0
was not replaced. Existing Terraform 1.12.1 was used. Isolated init preserved
the checked-in locks: hcloud 1.49.1 and hetznerdns 2.1.0. The isolated cache
uses the implicit local backend. After init, the original-state recovery
snapshot was copied into that cache, before any plan ran. No import, state
move, state upgrade, original-cache init or apply was performed.

The deployed source cache differs from SR in three Terraform text files:
root/app variable definitions and app load-balancer service mapping. It uses
one `port` for listener/backend, while current source uses `external_port` and
`internal_port`. Other cache/source byte differences were newline differences;
42 Terraform files compare equal as text. This source discrepancy is separate
from the observed node-replacement trigger below. Original/SR dev HCL compares
equal after normalizing the already-reviewed path hooks and formatting.

## Commands and observed results

All infrastructure commands used the isolated checkout, private OPERATOR_DIR,
explicit ENV=dev and TF_WORKSPACE=default. Network/provider commands required
approved execution outside the sandbox. No original deployment root was used
as a command working directory.

| Check | Result |
| --- | --- |
| `make config-check ENV=dev` | Passed with private copied credentials and original keys |
| `make cluster-plan ENV=dev DRY_RUN=1` | Passed; expected direct command, no tools launched |
| `make cluster-init ENV=dev STATE_REVIEWED=1` | Passed against isolated local backend; locked providers installed |
| `make cluster-plan ENV=dev STATE_REVIEWED=1` | Failed, wrapper exit 2; raw provider output retained privately |
| Plan inspection with Terragrunt `show -json` | `complete=false`, `errored=true` |
| Apply receipt | Absent; no apply executed |

With the isolated Terragrunt directory prepended to PATH, `make doctor` passed
and the final repository `make verify` passed all 42 tests with no skips,
including real Terragrunt forwarding to the synthetic Terraform stub. Syntax,
formatting, six renders, frozen runtime comparison, candidate secret checks and
221 documentation links passed; `git diff --check` passed. These offline checks
do not override the real provider plan failure. The system toolchain is unchanged.

The plan's DNS refresh failed at the existing `hetznerdns_zone` resource with
`invalid character '<' looking for beginning of value`. Hetzner's
[shutdown notice](https://status.hetzner.com/incident/c2146c42-6dd2-4454-916a-19f07e0e5a44)
confirms removal of the old DNS Console/API on 2026-05-27 and redirection to
the new Console. This is consistent with a non-JSON response from the legacy
provider, but no raw HTTP response was captured to prove the exact response.
Hetzner's [integration guidance](https://docs.hetzner.com/networking/dns/migration-to-hetzner-console/features-and-differences/)
identifies new API credentials and support through the hcloud provider. Neither
credentials nor provider/resource definitions were migrated here.

The **incomplete** summary reports 9 additions, 5 changes and 9 destructions.
It proposes replacing all five servers and four worker load-balancer targets,
plus firewall/attachment and reverse-DNS changes. All five server replacements
have `location` in `replace_paths`: refreshed before-values are empty, desired
values are `fsn1`. This does not prove actual relocation; provider/API response
compatibility must be investigated before interpreting it as real drift.
The old hcloud provider is pinned; no upgrade or ignore_changes workaround was
introduced. An incomplete plan cannot establish zero drift or scaling safety.

## Read-only placement review

Explicit-context Kubernetes GET snapshots captured nodes, all pods/PDBs/PVCs,
PVs and VolumeAttachments into private storage. No exec, drain, restart, patch,
apply or Docker-daemon operation occurred.

- Five live nodes matched the original state's names/addresses: one master,
  three api workers and one monitor worker; all five nodes were Ready.
- ProviderID matching alone matched no nodes; names/address correspondence was
  used instead. Nodes also lack the expected `pool` labels, so pool counts
  must not be guessed from Kubernetes labels.
- 14 PVs: 12 `local` sources with node affinity, two `hostPath` sources.
  12 PVCs and zero VolumeAttachments were observed. No VolumeAttachments does
  not establish that node deletion is safe.
- Five PDBs were observed; two report zero disruptions allowed.
- Backup integrity, restoration, spare capacity and a usable drain procedure
  have not been established. No hypothetical count change or scale plan ran
  after the ordinary plan exposed control-plane replacement and DNS failure.

## Acceptance and separately reviewed next work

P3-03 remains open: no complete safe plan or authorized apply exists.
P3-07/P5-04 remain open: actual node correspondence and storage/PDB evidence now
exist, but a valid scale plan and complete recovery review do not.

Before another infrastructure plan, separately review legacy-provider API
compatibility and the DNS resource/state migration needed for the new API.
Preserve resource IDs, DNS records, provider credentials, original state and
rollback custody; do not remove DNS resources from state, recreate zones,
change location, ignore drift or apply the partial plan to bypass errors.
Any provider/schema/state migration is a separate decision under AGENTS.md.
Plugin acceptance, image publication and GitOps source cutover remain their
own explicit live gates. No cluster or container mutation was performed by
the agent during this review.
