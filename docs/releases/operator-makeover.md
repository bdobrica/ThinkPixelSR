# Operator makeover — unreleased

Local changes improve ThinkPixelSR's configuration, command interface and
documentation while preserving the inherited search implementation. These
notes describe the candidate working tree, not a published release or a
qualified deployment. [Phase 5 evidence](../evidence/phase-5/README.md) records
validation and the remaining gates.

## Changes

- Seven-key non-secret dotenv/path contract, safe literal loader, private file
  validation, explicit dev selection and prod rejection.
- Default Make help, local doctor/config checks, guarded existing-tool wrappers
  for saved-plan apply, Flux attachment, images, worker plans and diagnostics.
- As-built architecture and configuration/deployment/operations runbooks,
  including exact image identities, storage/recovery constraints and WordPress
  fixture acceptance procedure.
- Repeatable frozen-source audit and limited candidate secret-pattern/path
  scan in `make verify`; six audit regressions added to the 36 existing offline
  tests. No new application dependencies or deployment system.
- Unapplied two-owner GitOps and parent catalog patches for later approved
  migration; retained original Git history, license and old source.

## Validation scope

`help`, `doctor`, `config-check`, `verify` and wrapper DRY_RUN behavior are
verified offline within the documented contracts. An unconfigured dev checkout
fails for missing files; prod fails explicitly. `doctor` checks local versions,
not access. Full history is required for the frozen baseline audit.

Init/plan use existing Terraform/Terragrunt and may access providers/state;
actual use needs reviewed state custody. Apply, Flux attach, image publishing,
scaling and plugin writes retain explicit authorization gates. They are
implemented and tested with synthetic fixtures, **not live-qualified**. Image
tags remain the checked-in versions, can be overwritten at the registry, and
upstream downloads are not fully reproducible. No mutable latest default is
added by the root wrappers; the inherited publishing workflow is unchanged.

## Open limitations and recovery

Fresh Flux Operator/decryption installation and compatible SQL/index-node setup
remain external prerequisites. Prod is unimplemented. No real dev/plugin,
image pull or scale-plan acceptance, GitOps switch/recovery or cloud zero-drift
observation has been recorded. Redis ANN is not Qdrant hybrid parity; Core NATS
does not provide durable ingestion; local-path/hostPath storage constrains
worker replacement. Inherited runtime defects remain separately recorded in
[baseline blockers](../evidence/phase-0/README.md#baseline-configuration-and-unresolved-assumptions).

Old ThinkPixelInfra main/credentials and state/decryption keys retain custody.
Source switch-back cannot undo data writes, registry tag replacement or node
loss. Review [migration](../migration.md), [scaling](../operations/scaling.md)
and [verification](../operations/verification.md) before live acceptance.

This candidate does not change APIs, schema, queue/model behavior, infrastructure
or storage identities, plugin code, platform responsibilities or maturity.
Live source changes and parent publication wait for the explicit Phase 5 gates.
