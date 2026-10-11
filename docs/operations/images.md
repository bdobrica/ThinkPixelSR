# Building and publishing existing images

The root Make wrappers use the six checked-in versioned build contexts below.
Offline previews and forwarding tests pass; actual multi-platform build, Quay
push and cluster pull remain unverified. No image reference, Dockerfile or CI
publishing behavior is changed by this runbook.

## Image inventory and platforms

| IMAGE | Context / Dockerfile | Current TAG | Checked-in dev deployment |
| --- | --- | --- | --- |
| `api-gateway` | [docker/api_gateway](../../docker/api_gateway/Dockerfile) | `0.7.1` | Gateway; image also includes dlq-reinject |
| `mpnetv2` | [docker/models/mpnetv2](../../docker/models/mpnetv2/Dockerfile) | `0.3.5` | Model deployment/service |
| `snowflake-arctic` | [docker/models/snowflake-arctic](../../docker/models/snowflake-arctic/Dockerfile) | `0.1.13` | Model deployment/service |
| `e5-instruct` | [docker/models/e5-instruct](../../docker/models/e5-instruct/Dockerfile) | `0.1.4` | No dev overlay |
| `jina-v5` | [docker/models/jina-v5](../../docker/models/jina-v5/Dockerfile) | `0.1.0` | No dev overlay |
| `external` | [docker/models/external](../../docker/models/external/Dockerfile) | `0.1.0` | No dev overlay; no ecosystem integration implied |

REGISTRY must explicitly be `quay.io/bdobrica`; the resulting tag is
`quay.io/bdobrica/thinkpixel-<IMAGE>-multi:<TAG>`. TAG must exactly match that
context's `.bumpversion.cfg` current_version. Latest and arbitrary tag overrides
are rejected. To release another version, use a separately reviewed version
change consistent with Dockerfile/version files and intended GitOps refs.

Both commands use `linux/amd64,linux/arm64` and the inherited TARGETPLATFORM
build argument. The dev cax21 nodes require ARM64 support. Gateway builds Go
binaries; model images download Python packages/language assets/weights and
may require mirror access, large disk/cache space and native wheel support on
both platforms. Upstream downloads and base images are not digest locked;
a version tag alone does not make a build reproducible. See the detailed
[baseline inventory](../baseline/images.md).

Sentinel, WordPress and local mock-site Dockerfiles are outside this wrapper
allowlist. Local Compose builds its own contexts and pulls different database
and vector images; it is not a publishing or cluster-version qualification path.

## Prepare, preview and build

Before a real build, the operator needs Docker/Buildx, a running builder with
OCI export and both platforms, sufficient CPU/memory/disk, and access to package
and model mirrors. Configure builders/emulation through the existing operator
procedure; wrappers never install QEMU or bootstrap a builder. `make doctor`
checks the local Buildx version, not daemon/builder/mirror access.

From the repository root:

```bash
make images-build IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 DRY_RUN=1
make images-push IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 DRY_RUN=1
```

Expected: exact checked-in Dockerfile/context, platforms and versioned tag,
without Docker execution, credentials, downloads or artifacts. ENV is not
required for image commands and does not select a publishing namespace.

For an authorized build, create a private POSIX artifact directory outside Git:

```bash
umask 077
export OPERATOR_DIR="$(mktemp -d /tmp/thinkpixelsr-image.XXXXXX)"
make images-build IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5
```

Expected: private `mpnetv2.oci.tar` and images-build.log under OPERATOR_DIR.
The command uses `--output type=oci,dest=<private archive>`; it does not load
the multi-platform result into the local Docker store or push to Quay.
Docker documents this behavior in its
[exporter reference](https://docs.docker.com/build/exporters/). Build caches
and intermediate images remain under Docker's custody outside OPERATOR_DIR.
Fresh directories prevent overwrite of logs/archives. A failure requires private
log review and a fresh run directory, not a tag change to evade validation.

## Registry credentials and deliberate publication

Registry access is external to `.env`; retain existing Quay account/robot
permissions and Docker credential-store custody. Never put passwords in
Make arguments, use shell tracing or commit Docker auth configuration. For
interactive operator login:

```bash
docker login quay.io
```

Before authorizing push, inspect the existing version tag and registry policy.
The current workflow may already have published it. Republishing can replace
the tag even when manifests do not change. If the registry enforces immutability,
do not disable it to force this run; review a proper versioned release instead.

With explicit publication approval and private OPERATOR_DIR:

```bash
make images-push IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 CONFIRM=push
```

This performs another Buildx build with `--push`; it does **not** upload the
earlier OCI archive. It may download/build again and stores images-push.log
privately. No latest tag, automatic version bump, Git commit, workload rollout
or image reference change is made. Reusing a build directory is possible if
its push log does not already exist; prefer a fresh directory per operation.

## Published manifests, pulls and pinning

For an authorized read of Quay artifacts, inspect the exact published tag:

```bash
: "${OPERATOR_DIR:?Set a private directory outside Git}"
docker buildx imagetools inspect \
  quay.io/bdobrica/thinkpixel-mpnetv2-multi:0.3.5 > "$OPERATOR_DIR/mpnetv2-manifest.txt"
```

Expected: an index digest plus runnable linux/amd64 and linux/arm64 manifests;
attestation entries alone do not prove platform support. This contacts the
registry. The command is documented by
[Docker](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/).
Keep the reviewed digest for comparison; the Make target does not assert it.

On the authorized dev cluster, inspect desired images and actual imageIDs
privately using the [troubleshooting commands](troubleshooting.md#image-pulls-and-model-startup).
Verify the registry pull secret `quay-io-secret` is usable in thinkpixel, the
correct platform starts, and the model `/ping` and actual inference pass.
Publishing is not pull/rollout evidence: existing pods and IfNotPresent caches
can still run an earlier digest under a reused tag. A registry inspection alone
does not prove gateway compatibility or WordPress search.

Current Kubernetes refs are version tags, not digests. Digest pinning or a new
version requires a reviewed GitOps manifest change and authorized rollout;
never `kubectl set image` a Flux-owned deployment as a publishing shortcut.
Record the prior tag **and digest**, workload revision and model selection before
such a release. Restoring a tag overwritten by push requires the preserved
artifact/digest and separate registry approval; source rollback alone cannot
recover it. This runbook performs no pinning or rollout.

The inherited [GitHub workflow](../../.github/workflows/build-and-push-image.yml)
selects changed `.bumpversion.cfg` files on main pushes and publishes versioned
**and latest** tags using QUAY_USERNAME/QUAY_AUTH secrets. Its QEMU/Buildx setup,
skip behavior and Docker authentication remain unchanged. A Dockerfile-only
edit does not trigger its build loop. Review workflow effects before publishing
version changes; no CI redesign is part of Phase 4.
