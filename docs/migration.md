# Repository migration — P1-01 through P1-04

ThinkPixelSR continues ThinkPixelInfra without changing the search MVP. This
phase imports source and history and changes documentation-facing names only.
It does not deploy, move state, switch GitOps, publish images, or change the
separate WordPress plugin. [Phase 1 evidence](evidence/phase-1/README.md) records
what has actually been verified; [Phase 0 gaps](evidence/phase-0/README.md) remain
open until separately validated.

## Lineage and history

The frozen input is ThinkPixelInfra commit
`9e5fc87495832d3a2554965341cbeb43911ff5f5`, also recorded in the
[405-file inventory](evidence/phase-0/source-tree.tsv). Import only its committed
files; never copy the sibling's whole working directory or `.git` directory.
That would include ignored credentials/caches or unrelated local configuration.
ThinkPixelSR retains the original 265-commit main ancestry, commit IDs, authors,
messages, and four release tags (`v0.1.1`, `v0.1.9`, `v0.3.2`, `v0.7.0`). Two
tags retain additional history outside main. Old development branch refs and
reflogs stay in ThinkPixelInfra; this is not a mirror of every experimental
branch. LICENSE and all existing source notices are unchanged.

The original root README remains available in history:

```bash
git show 9e5fc87495832d3a2554965341cbeb43911ff5f5:README.md
```

The initial main HEAD in this checkout was that exact baseline commit. The
import itself made no new commit; publication uses focused documentation
continuation commits. History was imported from the local sibling, not
by querying or modifying its GitHub remote. `thinkpixelinfra` records the old
GitHub URL, while `origin` records the intended new URL; an origin setting is
not proof that the repository exists or is accessible.

## Path and reference mapping

| Before | After this phase | Treatment |
| --- | --- | --- |
| ThinkPixelInfra main history and release tags | Retained in local ThinkPixelSR | Original objects, not squashed or rewritten |
| Root README | ThinkPixelSR entry point | Original retained in history |
| `cluster/README.md` clone URL and `cd` name | ThinkPixelSR documentation-facing names | Old GitHub source retained; new clone waits for publication |
| LICENSE, source, SQL, Dockerfiles, workflows, lockfiles, SSH public keys | Same paths and committed bytes | No dependency, schema, build or resource changes |
| FluxInstance `flux`, `spec.sync.url` | `https://github.com/bdobrica/ThinkPixelInfra` | Preserved until Phase 5 operator-approved switch |
| ResourceSet `flux-notifications`, GitHub Provider address | Same old repository URL | Preserved with sync source |
| Git ref/path/secret | `refs/heads/main`, dev overlay, `github-token` | Preserved |
| Images and Quay registry paths | Original identities/tags | Repository rename does not rename images |
| Namespaces/services/DNS/PVCs/SealedSecrets/Terraform resources | Original identities | No state or ownership migration |
| Local secrets/private keys/state/caches/untracked ZIP | Not imported | Keep under existing custody; not evidence or publication artifacts |
| ThinkPixelPlugin and parent ThinkPixel catalog | Separate, unchanged repositories | Parent links belong to verified Phase 5 publication |

The frozen reference audit is in [the GitOps baseline](baseline/gitops.md).
There were three absolute old repository URLs: one cluster README clone URL
and two Flux owner-manifest URLs. No old URL occurred in the workflow,
Dockerfiles, build scripts, or badges; no badges were checked in. The README's
lineage links and Phase 0 historical references intentionally continue to use
ThinkPixelInfra. External webhooks, branch rules, GitHub Apps, Actions secrets,
and registry permissions are not represented by the tracked tree and remain
unverified.

## Staging and temporary coexistence

1. Keep ThinkPixelInfra readable and its existing remote, main branch, local
   secrets, keys, state and credentials intact. ThinkPixelSR is a separate
   checkout; no shared `.git` objects/alternates or state relocation is required.
2. Review the [baseline comparison](evidence/phase-1/baseline-diff.tsv). The only
   inherited-file changes must be `README.md` and `cluster/README.md`. Compare
   runtime files and LICENSE before preparing the first continuation commit:

   ```bash
   git diff --name-status 9e5fc87495832d3a2554965341cbeb43911ff5f5
   git diff --exit-code 9e5fc87495832d3a2554965341cbeb43911ff5f5 -- LICENSE cluster/infra cluster/live k8s docker database local debug .github .gitignore .gitattributes
   git log --oneline main
   git tag --list
   ```

   Expected: the runtime comparison exits 0. Of inherited files, only the two
   READMEs differ; additional files are governance documents and `docs/`.
   Before staging, additions are visible with `git status --short`. Do not use `git add .`
   before Phase 2 ignore protections and a complete sensitive-file review.
3. Locate the authoritative state/backend/workspace outside this procedure.
   Do not run `terragrunt init/plan/apply` in the new checkout merely to verify
   an import: an unlocated local backend may appear to need a new cluster.
   Keys and Sealed Secrets controller decryption keys retain existing ownership.
4. Commit the reviewed governance documents and `docs/` together with the two
   README edits. Keep all live Flux manifests unchanged in that commit.
5. The user confirms `bdobrica/ThinkPixelSR` already exists. Publish only after
   authenticated GitHub access is available. [Phase 1 evidence](evidence/phase-1/README.md)
   records the completed publication and remote verification. Inspect existing
   commits and reconcile deliberately; do not force-push, overwrite history,
   change visibility or create another repository.

### Publication once authenticated access is available

The user installed GitHub CLI and authenticated during Phase 1. Read-only
checks confirmed the public remote main was the frozen source revision before
publishing the continuation. The
following is the publication procedure; [evidence](evidence/phase-1/README.md)
records completion. It requires `gh`, GitHub login/permission, a reviewed continuation
commit, and a reviewed historical secret scan (the offline pattern scan is
limited). No token belongs in a command, Git remote URL, or documentation.

```bash
gh auth status
gh repo view bdobrica/ThinkPixelSR --json nameWithOwner,visibility
```

If `repo view` reports an authorization error, resolve access first; the user
has confirmed the repository exists. Preserve its visibility and settings.
Fetch/inspect its existing branches and tags before deciding how to publish;
a non-fast-forward rejection requires a reviewed reconciliation, never force.

For a first source push to an **empty** destination, disable Actions in GitHub settings
(or the following [GitHub Actions permissions API](https://docs.github.com/en/rest/actions/permissions#set-github-actions-permissions-for-a-repository)
call with repository administration access). Review any existing workflows
before changing that setting. The inherited publishing workflow uses
`github.event.before` and registry secrets; the initial push has an all-zero
before revision, and its skip step does not skip the whole job. Importing that
workflow must not inadvertently trigger a registry publication attempt. Leave
it unchanged in Git, and review its enablement/secrets separately. This
destination already has baseline main, so the Phase 1 continuation is not an
initial all-zero-before push. Its documentation-only commits change no
`.bumpversion.cfg` files; the existing workflow can run, but its image-build
loop should be empty. Actions settings and workflow remain unchanged; inspect
the observed run separately.

```bash
gh api --method PUT repos/bdobrica/ThinkPixelSR/actions/permissions -F enabled=false
```

The command above applies to the empty-destination case only; it was not run
for this repository. With its existing baseline verified:

```bash
git ls-remote origin
git fetch origin
git push origin main
git push origin refs/tags/v0.1.1 refs/tags/v0.1.9 refs/tags/v0.3.2 refs/tags/v0.7.0
git ls-remote --exit-code origin refs/heads/main
```

Do not push until main contains the reviewed continuation commit. Compare the
remote main object ID to `git rev-parse main`, verify all four tag objects and
inspect the published tree/links. For an empty-destination import, keep Actions
disabled until permissions, registry settings, and initial-push behavior have
been reviewed. Do not use
`--mirror`, `--force`, or point Flux at an unpublished/unvalidated new remote.

## GitOps cutover gate — deferred to Phase 5

The initial import retains both old runtime URLs. A future cutover requires:

- Authenticated source-controller access to the published ThinkPixelSR main
  revision; account/secret names alone do not establish access.
- Dev/plugin validation, zero workload/render drift, installed CRDs/controller
  versions and reconcile revision, PVC/storage/decryption-key checks, and an
  authorized operator with a tested recovery path. Production is unconfigured.
- Inspection of the live FluxInstance and its generated GitRepository and
  Kustomizations. The baseline expects GitRepository/Kustomization
  `flux-system` in namespace `flux-system`; verify observed names first.
- A reviewed commit in the new repository changing only the owner-manifest
  sync URL and notification address. Keep the Git ref, sync path, secretRef,
  tenant resources, images and namespaces unchanged. Keep old main at the
  working old-source configuration for rollback.
- A deliberate live switch of the **FluxInstance owner** and notification
  **ResourceSet owner**, consistent with the desired commit in the new source.
  Editing only the generated GitRepository/Provider can be overwritten by
  their owners. Do not introduce a competing bootstrap/deployment system.

No live switch commands are executed by Phase 1. The rollback below uses the
existing owner resources and requires separately authorized cluster access.
It is a documented procedure, not a live-tested guarantee of an atomic switch.

### Capture switch-back inputs before an authorized cutover

Use the explicit operator-verified context; never rely on the shell's default
cluster. Keep snapshots private and outside Git. Capture immediately before
the switch, while old sync and notification settings are known-good:

```bash
export MIGRATION_CONTEXT='<verified-dev-context>'
umask 077
rollback_dir=$(mktemp -d)
kubectl --context "$MIGRATION_CONTEXT" -n flux-system get fluxinstance flux -o json > "$rollback_dir/flux-instance.before.json"
kubectl --context "$MIGRATION_CONTEXT" -n flux-system get resourceset flux-notifications -o json > "$rollback_dir/notifications.before.json"
python3 - "$rollback_dir" <<'PY_ROLLBACK'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
instance = json.loads((p / 'flux-instance.before.json').read_text())
notifications = json.loads((p / 'notifications.before.json').read_text())
sync = instance['spec']['sync']
assert sync['url'] == 'https://github.com/bdobrica/ThinkPixelInfra'
assert sync['ref'] == 'refs/heads/main'
assert sync['path'] == 'k8s/flux-system/dev'
assert sync['pullSecret'] == 'github-token'
(p / 'flux-sync.rollback.json').write_text(json.dumps([
    {'op': 'replace', 'path': '/spec/sync', 'value': sync}
]))
providers = [(i, r) for i, r in enumerate(notifications['spec']['resources'])
             if r.get('kind') == 'Provider'
             and r.get('metadata', {}).get('name') == 'github-status']
assert len(providers) == 1
index, provider = providers[0]
assert provider['spec']['address'] == 'https://github.com/bdobrica/ThinkPixelInfra'
prefix = f'/spec/resources/{index}'
(p / 'notifications.rollback.json').write_text(json.dumps([
    {'op': 'test', 'path': prefix + '/kind', 'value': 'Provider'},
    {'op': 'test', 'path': prefix + '/metadata/name', 'value': 'github-status'},
    {'op': 'replace', 'path': prefix + '/spec/address',
     'value': provider['spec']['address']}
]))
PY_ROLLBACK
```

A failed assertion means live settings differ from this source baseline. Stop
and record the actual known-good URL/ref/path/credential and owner layout;
review the rollback for that installation before proceeding. Do not print
Secret objects, tokens, kubeconfig or controller decryption keys. Record the
last working source revision and reconciliation status separately, without
publishing sensitive resource dumps. Retain access to the old remote/ref and
its credential, as well as the private rollback directory.

### Exact switch-back steps after a failed cutover

These commands assume the verified names/settings above and the snapshots
from that cutover session. Confirm no owner/resource ordering or unrelated
sync settings changed since capture. Keep the new source's failing revision
for diagnosis; never delete repositories or reset/force-push history.

1. Stop further cutover edits and suspend the observed root Kustomization to
   prevent its new-source manifests from racing the restoration. Inspect the
   FluxInstance/controller behavior and confirm suspension stays in effect:

   ```bash
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system patch kustomization flux-system --type=merge -p '{"spec":{"suspend":true}}'
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system get kustomization flux-system -o jsonpath='{.spec.suspend}'
   ```

   Expected: `true`. If an owner immediately undoes suspension, stop and use
   that installation's reviewed controller recovery procedure; do not guess.
2. Restore the original FluxInstance sync and notification ResourceSet address:

   ```bash
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system patch fluxinstance flux --type=json --patch-file "$rollback_dir/flux-sync.rollback.json"
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system patch resourceset flux-notifications --type=json --patch-file "$rollback_dir/notifications.rollback.json"
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system annotate gitrepository flux-system reconcile.fluxcd.io/requestedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system get gitrepository flux-system -o jsonpath='{.spec.url}{"\n"}{.spec.ref}{"\n"}{.status.artifact.revision}{"\n"}{.status.conditions}{"\n"}'
   ```

   Wait for the generated GitRepository to show the original URL/ref, an
   artifact from the retained old main, and successful Ready status. A stale
   Ready condition alone is insufficient; verify the observed generation and
   expected artifact revision. If fetching fails, check credential permission,
   source-controller/operator events and connectivity; leave the root suspended
   while resolving access instead of resuming a stale new-source artifact.
3. Once the old artifact is confirmed, resume and request root reconciliation:

   ```bash
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system patch kustomization flux-system --type=merge -p '{"spec":{"suspend":false}}'
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system annotate kustomization flux-system reconcile.fluxcd.io/requestedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system get kustomizations
   kubectl --context "$MIGRATION_CONTEXT" -n flux-system get provider github-status -o jsonpath='{.spec.address}{"\n"}'
   ```

   Confirm the root and tenant Kustomizations reconcile the expected old
   revision, the Provider address is restored, and workloads/PVCs/secrets/images
   retain their identities. Perform the authorized dev/plugin smoke comparison
   from [verification](operations/verification.md). Notify the operator of any
   residual drift; Ready alone is not proof of data or plugin recovery.

GitOps switch-back does not undo database writes, image publication, node
replacement or data loss. Those actions are excluded from this repository
cutover. Preserve backups/state/key custody and the original checkout; do not
remove a rollback path merely because new-source fetching succeeds.
