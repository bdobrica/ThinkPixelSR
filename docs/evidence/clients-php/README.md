# PHP existing-key SDK evidence — 2026-10-11

Scope: CL-038–CL-039, CL-041–CL-042, operator-requested Phase 4C with the same
existing-key scope as Python/TypeScript. [Package guide](../../../clients/php/README.md).
API Gateway baseline and shared fixtures remain authoritative; no API, plugin,
database, deployment or infrastructure files changed. CL-040 registration is
deferred; its exception mapping subset is implemented. Gates 0–3 and live parity
remain open. The existing frozen-byte audit allowlist was extended only for the
PHP package's metadata and source/test/example paths. Documentation link checks
now follow Git's tracked/nonignored scope, excluding installed dependency docs;
two regression tests ensure ignored dependencies are skipped and SDK links checked.

## Tools and checks

Temporary tools under `/tmp`, without installing system packages:
64-bit PHP **8.4.26**, Composer **2.9.5**, PHPUnit **11.5.57**, PHPStan **2.3.1**,
Guzzle **7.15.5**, PSR-7 **2.13.1**. Composer dependencies are locked. Runtime
transitives are MIT; development tooling is MIT/BSD-3-Clause; the SDK retains
an exact copy of the repository's Apache-2.0 license.

Commands run inside `clients/php` with temporary PHP/Composer executables:

- `composer install`: passed; dependencies downloaded with approved network access.
- `composer validate --strict`: passed, no warnings or stale lock.
- `composer lint`: all source/test/example PHP files parsed successfully.
- `composer analyse`: PHPStan level 8 passed for source and example. PHPDoc
  types are treated as uncertain to preserve runtime array element validation.
- `composer test`: 88 tests, 214 assertions passed on PHP 8.4.26, zero skips.
  Includes six shared store/search fixtures, exact headers/body/prefix, JWT
  expiry skew and renewal/cache invalidation, bounded 401 replay, malformed
  auth/search/store replies, status mapping, Retry-After, origin/key/input checks,
  unknown metadata/duplicate IDs, diagnostics, timeout budgets and ownership.
- Default cURL loopback tests: redirect target was not contacted; stalled search
  timed out without retry. These synthetic tests and normal PHPStan worker sockets
  required approved execution outside the sandbox; no live gateway was contacted.
- `bump2version --allow-dirty minor`: assigned 0.0.0 → **0.1.0**, updating config,
  Composer SDK-version metadata and exported class constant. Future bumps also update the package guide. Commit/tag disabled.
  `bump2version --allow-dirty --dry-run patch` passed without further changes.
- `composer archive --format=tar --dir=dist --file=thinkpixel-sr-0.1.0`: passed.
  Archive inspected: 27 files, source/manifest/license/README/changelog only;
  excludes vendor, tests, examples, caches, lockfile and developer config.
- Extracted archive installed into a separate `/tmp` consumer using a Composer
  path repository and offline cached dependencies. Autoload/version and mocked
  auth/search smoke passed. PHP 8.3.0 platform resolution for that consumer
  passed; this checks dependency constraints, not execution on PHP 8.3.

## Repository verification and limits

`make verify` passed: 44 offline tests, one Terragrunt-version skip; frozen
runtime byte comparison, limited secret/path audit, 294 relative documentation links,
Python/Make/shell/HCL checks and six Kustomize renders passed. `make help` passed.
`make doctor` returned expected exit 2 for unsupported Terragrunt 0.81.0.
The existing Python SDK regression suite also passed (80 tests).
Configuration checks returned expected exit 2 for missing dev secrets,
unsupported prod, missing environment and invalid environment; no real tokens
or environment fallback were used. `git diff --check` passed.

PHP 8.3 is a declared minimum target but its runtime was not available for
execution. No live credentials, TLS endpoint/CA deployment, plugin smoke,
registration, store→eventual-search acceptance, 32-bit PHP or concurrent use was
tested. cURL DNS/platform behavior and arbitrary injected synchronous adapters
can limit hard wall-clock interruption; late responses are rejected but the SDK
cannot interrupt arbitrary PHP code. Diagnostic redaction is not protection
against deliberate reflection/var_export or third-party adapter traces.

No package publication, Git push, live API request or deployment occurred.
