# Image build and publishing map — P0-04

All source paths refer to the [frozen ThinkPixelInfra tree](../architecture.md).
Each build context below contains its own checked-in `Dockerfile`; no build or
push was executed. Registry availability and multi-platform success are unverified.

| Context / Dockerfile | `.bumpversion.cfg` and Dockerfile version | Workflow destination suffix | Dev use |
| --- | --- | --- | --- |
| `docker/api_gateway` | `0.7.1` | `thinkpixel-api-gateway-multi:0.7.1` | Kubernetes gateway and local Compose build |
| `docker/models/mpnetv2` | `0.3.5` | `thinkpixel-mpnetv2-multi:0.3.5` | Kubernetes + default local model |
| `docker/models/snowflake-arctic` | `0.1.13` | `thinkpixel-snowflake-arctic-multi:0.1.13` | Kubernetes; commented-out Compose alternative |
| `docker/models/e5-instruct` | `0.1.4` | `thinkpixel-e5-instruct-multi:0.1.4` | No checked-in Kubernetes overlay or Compose service |
| `docker/models/jina-v5` | `0.1.0` | `thinkpixel-jina-v5-multi:0.1.0` | No checked-in Kubernetes overlay or Compose service |
| `docker/models/external` | `0.1.0` | `thinkpixel-external-multi:0.1.0` | External model-service implementation; no deployed overlay; inventory does not authorize ecosystem integration |
| `docker/sentinel` | No version file | Not selected by workflow | Local Compose build; Kubernetes uses stock Redis instead |
| `docker/wordpress` | No version file | Not selected by workflow | Admin theme image definition, absent from dev overlay |
| `local/mock_site` | No version file | Not selected by workflow | Local registration callbacks only |

The workflow `.github/workflows/build-and-push-image.yml` runs on main-branch
pushes, detects changes to `docker/<component>/.bumpversion.cfg` or
`docker/models/<component>/.bumpversion.cfg`, extracts `current_version`, and uses:

```bash
# Recorded workflow shape; placeholders are not runnable credentials.
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg TARGETPLATFORM --file "$folder/Dockerfile" \
  --tag "quay.io/<QUAY_USERNAME>/thinkpixel-<folder-name>-multi:<version>" \
  --tag "quay.io/<QUAY_USERNAME>/thinkpixel-<folder-name>-multi:latest" \
  "$folder" --push
```

Underscores in the folder basename become hyphens. The registry is Quay.io;
`QUAY_USERNAME` and encoded `QUAY_AUTH` are GitHub Actions secrets. Dev manifests
use the `bdobrica` namespace. The workflow installs QEMU/Buildx, writes local
Docker authentication configuration, and publishes both versioned and mutable
`latest` tags. Its no-changes step exits only that step; later setup steps can
still run. It dumps GitHub context and has a before/after fetch assumption; these
are existing review concerns, not edited in this phase. A changed Dockerfile
alone does not trigger its image loop without a version-file change.

The gateway Dockerfile uses Go 1.23, `TARGETOS`/`TARGETARCH`, and a static gateway
and DLQ utility in Alpine 3.21. Its module declares Go 1.23.2. All five model
Dockerfiles use Python 3.10.20 slim trixie and platform-specific BuildKit cache
IDs; MPNetV2/Arctic/E5/Jina use Alpine 3.23.3 weight stages and `weights.sh`.
Those scripts download model files and fastText from the configured upstream
mirror, assemble split weights, and check the assembled checksum on first
assembly; cached assembled files skip reassembly. External downloads fastText
directly and calls its configured external embedding service. Package downloads,
spaCy language models, weight mirror access and native wheel availability on
both architectures remain build prerequisites. Source tags are not digest locks.

Local Compose builds gateway, MPNetV2, sentinel and mock site using their contexts,
without an explicit platform or registry publishing tag. Its pulled images are
`mysql:9.5.0`, `qdrant/qdrant:v1.16.3`, `nats:2.12.3-scratch` and
`redis/redis-stack-server:7.4.0-v0`. These differ from
[Kubernetes image identities](gitops.md#image-identities); passing local checks
does not certify the cluster versions. The WordPress Dockerfile downloads WP
core and wp-cli without an exact application version pin; the unused Kubernetes
WordPress base points to `wordpress:5.8-apache` instead.

Phase 3 wrappers must preserve exact Dockerfiles, inspected platforms, registry
namespace and reviewed version tags. The inherited `latest` convention is
recorded here, not a recommended default for the future wrapper. Registry login,
push authorization, published manifests and node pulls remain live acceptance gates.
