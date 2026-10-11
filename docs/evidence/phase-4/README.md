# Phase 4 documentation evidence

P4-01–P4-08 document the imported implementation and guarded root commands.
The original source baseline remains ThinkPixelInfra
`9e5fc87495832d3a2554965341cbeb43911ff5f5`. Earlier local Phase 2/3 changes are
preserved; Phase 4 changes Markdown only. No application, API/schema, model,
queue, manifest, infrastructure identity, Dockerfile or workflow is changed.

## Documentation coverage

| Task | Durable result |
| --- | --- |
| P4-01 | [Architecture](../../architecture.md): actual gateway/subscriber, Qdrant RRF versus Redis ANN, provisioning/GitOps diagram and persistence/ownership table |
| P4-02 | [Configuration](../../configuration.md): seven dotenv keys, precedence, existing consumers, private paths, dev example, explicit prod rejection and separate Make arguments |
| P4-03 | [Hetzner](../../deployment/hetzner.md): tools/state/SSH/DNS, first versus existing installation, guarded init/plan/apply, kubeconfig handoff, health/recovery limits |
| P4-04 | [Flux](../../deployment/fluxcd.md): source/owner map, unresolved bootstrap inputs/order, existing-operator attachment, tenant/revision checks and migration link |
| P4-05 | [Images](../../operations/images.md): six contexts/versions, both platforms, private OCI export, Quay custody/push, mutable-tag risk and digest/pull verification |
| P4-06 | [Scaling](../../operations/scaling.md): persisted existing worker inputs, all-pool index risk, live PDB/PV/placement reads, scale-up/down plans and recovery |
| P4-07 | [Verification](../../operations/verification.md) and [troubleshooting](../../operations/troubleshooting.md): current offline/live boundary, actual SearchPixel source flow, bounded fixture assertions/cleanup and dependency diagnostics |
| P4-08 | [README](../../../README.md): actual targets, quick start, links to every durable guide and visible unsupported/unverified behavior |

## Acceptance boundary

Documentation completion does not close the overall Phase 4 deployment gate
in PLAN: a fresh operator cannot yet deploy the complete application from this
checkout without external procedures. Known prerequisites are authoritative
state/key/DNS custody, initial Flux Operator/CRD and Sealed Secrets controller/
decryption-key setup, Git/registry/application credentials, compatible MySQL
schema/index-node allocation and live PV binding. The guides identify exact
stop points rather than fabricate installers, migrations or successful runs.
Prod is unimplemented. These gaps and live acceptance remain in Phase 3/5 and
the [baseline blocker record](../phase-0/README.md#baseline-configuration-and-unresolved-assumptions).

The plugin golden path is derived from the unchanged separate SearchPixel
v1.4.5 source, not a newly observed working deployment. A direct API or health
pass cannot substitute for its real WordPress registration/index/search/delete
comparison. No live cloud/backend, SSH, Kubernetes, registry, HTTP fixture,
WordPress, SQL initialization, node change or Git source switch ran for Phase 4.

## Validation

- `make help` and `make doctor` passed. Reported local tools: GNU Make 4.4.1,
  Python 3.13.5, Terraform 1.14.3, Terragrunt 0.96.1, kubectl 1.32.3 and Buildx
  0.30.0. No authentication or services were checked.
- `make verify` passed all **36** offline tests with no test skips, Python/Make/
  Bash syntax, Terraform formatting, edited dev HCL formatting, relative
  documentation links/fragments and six dev Kustomize renders. Three overlays
  retain the documented permissive offline load setting. Live smoke was skipped.
- **58** Bash blocks across root/docs Markdown passed `bash -n` after fence
  extraction, including indented blocks. This is syntax only; deployment,
  capture, HTTP and mutation examples were not executed.
- Unconfigured `make config-check ENV=dev` failed on missing SECRETS_FILE as
  expected. `make config-check ENV=prod` and prod cluster-plan dry-run failed
  with no dev fallback. Valid/invalid dev configuration cases use synthetic
  files in the offline suite; no real credentials were borrowed or created.
- MPNetV2 image and dev Flux-check DRY_RUN previews matched documented commands
  and made no Docker/registry/cluster requests. Local kubectl port-forward and
  Buildx imagetools inspect help confirmed the newly documented CLI shapes.
- Phase 4 Markdown received whitespace, relative-link/heading and a limited
  private-key/GitHub-token/AWS-key pattern review. This is not a comprehensive
  secret audit or historical scan. Documentation examples use placeholders,
  synthetic fixture text and private output paths.
- `git diff --check` passed. Runtime/infrastructure/manifests/Docker/database/
  local/debug/workflow/LICENSE/PLAN/AGENTS paths match preexisting HEAD, apart
  from the already present Phase 2 dev HCL path hooks. The original Infra and
  separate Plugin tracked working trees remain unchanged; only documentation
  was edited for Phase 4. Existing Phase 2/3 working changes remain local.

No commit, push, publication, external message, live credential use or package
installation was performed. The guides and checklist describe documentation
completion, not live Phase 3/5 acceptance or production qualification.
