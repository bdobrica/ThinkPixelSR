# Phase 2 evidence — safe local configuration

P2-01–P2-05 are implemented. This evidence records offline checks, not a cloud,
SSH, registry, Kubernetes, Flux or WordPress validation. The source compatibility
reference remains `9e5fc87495832d3a2554965341cbeb43911ff5f5`.

## Scope and authority

- `.env.example` contains seven non-secret selector/path keys. There are no
  copied tokens, private keys, operator paths or duplicate cluster/image settings.
- [Configuration documentation](../../configuration.md) records schema, precedence,
  consumers, environment differences, failures and restricted literal-HCL support.
- `scripts/config.py` performs read-only local validation and returns path-only
  `TPSR_*` environment overrides for future wrappers. It never launches commands.
- Dev Terragrunt adds six optional path hooks; original filenames and input merge
  order are unchanged. The edited file is formatted with `terragrunt hcl fmt`.
  Cluster values, prod, Terraform modules/locks, K8s/Flux manifests, Docker images,
  application code, SQL and CI remain unchanged.
- `.gitignore` covers nested local config, credentials, keys, kubeconfigs,
  state/plans/tfvars/debug output, retaining public keys, examples, lockfiles and
  SealedSecrets. Ignore patterns are not a comprehensive secret scanner.
- No root Makefile was added; help/doctor/config-check wrappers remain P3-01.

## Checks performed

| Check | Observed result |
| --- | --- |
| `python3 -B -m unittest discover -s tests -v` | 16 tests passed, including the actual Terragrunt integration (not skipped) |
| Synthetic complete dev configuration | Accepted; translated six absolute paths, no tokens in returned environment |
| Prod, absent/invalid ENV | Rejected explicitly; no dev fallback |
| Missing/unreadable/empty/directory/non-UTF-8/oversize files; unsafe private permissions | Rejected with fixed messages, no contents or private paths |
| Missing/blank/placeholder/malformed tokens; literal-HCL functions/interpolation/blocks/duplicates | Rejected without evaluation |
| String/fractional/boolean/negative/zero/null counts; unknown or control-plane worker pools | Rejected; valid existing-pool counts accepted as data only |
| CLI/process/`.env`/default precedence; quoted paths, spaces, comments, CRLF, literal metacharacters | Expected selection; no shell/subprocess invoked by validator |
| Unknown/duplicate keys, whitespace/quote errors, ambient `TF_VAR_*`/`TPSR_*`, CLI error canaries | Rejected; synthetic canary values/private paths absent from diagnostics |
| Validator tree snapshot and subprocess prohibition | No changed/generated input files or subprocess calls |
| `git check-ignore --no-index --stdin` | Sensitive nested examples ignored; templates, public keys, lockfiles and SealedSecrets remain visible |
| `git ls-files -ci --exclude-standard` | Empty: no currently tracked files newly ignored |
| `terraform -chdir=cluster fmt -check -recursive` | Passed; no init, plan or apply |
| `terragrunt hcl fmt --check --file cluster/live/dev/terragrunt.hcl` | Passed after formatting only the edited dev file |
| Python syntax; 41 edited-doc relative links/fragments; five Bash snippet syntax checks; `git diff --check`; nine-file limited secret-pattern review | Passed |
| Unconfigured checkout CLI `--env dev` | Expected exit 2 for absent `.secrets.hcl`; no real secret/key file read |
| CLI `--env prod` / invalid ENV | Expected exit 2 with explicit environment error |

The 16-test suite includes an offline comparison using Terragrunt **v0.96.1**:

1. Render the frozen original dev config with synthetic secret/key fixtures.
2. Render the new dev config with its default filenames and the same fixtures.
3. Move fixtures outside the environment directory to a path containing spaces,
   load explicit path overrides, and render using the translated child environment.
4. Assert all three complete `inputs` objects are equal (including original
   cluster settings and merge results); suppress JSON/diagnostics.

Rendering runs only in temporary storage using `--disable-dependent-modules`
and `--no-auto-init`. A Terraform stub answers version detection and rejects any
other action. Assertions confirm no unexpected Terraform action, Terragrunt
cache or Terraform state. The integration test skips visibly if Terragrunt/Git
or the frozen source object are unavailable; other installed Terragrunt CLI
versions are unverified.

## Limits and skipped actions

No operator secrets or private files were imported from ThinkPixelInfra. The
validator deliberately supports data-only secrets inputs; advanced HCL keeps
its direct Terragrunt path pending a reviewed validator extension. Local checks
do not verify key pairing/format/passphrases, token authenticity, provider/network
availability, remote state custody or actual node placement/capacity. Positive
counts do not approve scaling or guarantee additive/no-disruption changes.

Production remains empty and unsupported. POSIX permission checks reject
sensitive files with group/other access, including permissive mounted files;
native Windows ACLs require operator review. Sensitive plans/state/cloud-init
and Terragrunt render output must remain private; inherited SSH Terraform
variables are not marked sensitive.

No init/plan/apply, registry build/push, cluster/Flux change or live plugin test
was run. Make checks are deferred because the root Makefile is not implemented.
No Phase 2 GitHub publication was needed to validate local configuration.
