# TypeScript existing-key SDK — CL-033, CL-034, CL-036, CL-037

The operator authorized Phase 4B with the same existing-key scope as Python on
2026-10-11: API Gateway contracts are authoritative; omitted `apiKey` reads
`THINKPIXEL_API_KEY`; key assignment/CL-035 and Gates 0–3 remain deferred/open.
No gateway, database, plugin, infrastructure or deployment behavior changed.

## Verification

- Node.js 22.23.3 and 24.20.0, TypeScript 5.6.3, Node declarations 22.20.5.
- `npm ci --ignore-scripts --no-audit --no-fund`: lockfile installation passed.
- `npm run lint`: strict compilation and example type checks passed.
- `npm test` on Node 24, and `node --test tests/client.test.mjs` on Node 22:
  90 tests passed on each runtime. Shared gateway fixtures cover accepted/partial/
  all-failed store and search/empty Qdrant/Redis results. Additional cases cover
  auth/expiry, exact requests, 401 replay, status errors, redaction, malformed
  schemas/JSON, unknown fields, unsafe IDs, local validation, timeout/body
  streaming, independent cancellation, concurrent exchange and native fetch
  redirect handling against a synthetic loopback server.
- `bump2version --allow-dirty minor`: independent SDK 0.0.0 → 0.1.0;
  configuration, package.json, package-lock.json and exported VERSION agree.
- `npm pack`: archive builds with ESM JavaScript, declarations, Apache LICENSE,
  README and changelog. Clean temporary archive installation, ESM import,
  mocked request and consumer declaration compilation passed.
- Existing Python SDK regression: `pytest -q clients/python/tests`, 80 passed.
- `make verify`: 42 offline tests passed, one skipped for unsupported installed
  Terragrunt; inherited runtime baseline retained (401/405 byte-identical),
  limited candidate secret/path scan, relative links, syntax, Terraform/dev HCL
  formatting and six dev Kustomize renders passed. `git diff --check` passed.
- `make help` passed. `make doctor` returned expected exit 2 for Terragrunt
  0.81.0. Config checks returned expected exit 2 for missing dev secret file,
  unsupported prod and missing/invalid ENV, without credentials or fallback.

Dependency installation initially failed with sandbox DNS restrictions; it was
rerun with approval. The loopback fetch test and npm cache writes required
approved execution outside the sandbox. No live gateway or cloud was contacted.
Build output, node_modules and archive are ignored rather than committed.
TypeScript and Node declaration dependencies are development-only; lockfile
licenses are Apache-2.0/MIT, including transitive undici-types. Runtime uses
Node's built-in fetch and has no npm dependencies.

## Limits and outstanding acceptance

No staging store→eventual-search or WordPress smoke was run; no approved staging
credentials/environment were supplied. Registration, shared enrollment fixtures,
CI/release gates and npm namespace ownership remain pending. No package was
published, commit pushed or live deployment changed.

Abort deadlines cover exchange, request and body consumption; JavaScript timers
cannot interrupt a blocked event loop. Injected adapters must honor signals and
disable their own redirects/retries; SDK races bound caller waiting but cannot
stop adapter work that ignores cancellation. Nested unknown metadata is not
deeply frozen. Results deliberately preserve gateway scores and duplicate IDs;
queue acceptance is not indexing or durability evidence. The
[usage guide](../../../clients/typescript/README.md) records these limits.

## Prettier formatting follow-up

Source, tests, examples and package/configuration JSON use pinned Prettier 3.9.10
with package.json configuration and `npm run format` / `npm run format:check`
commands. Formatting introduces no intended runtime changes; the SDK remains
version 0.1.0. On Node.js 24.20.0, formatting, TypeScript checks and all 90 tests
passed. Tests needed local loopback-port permission outside the sandbox.
`make verify` passed (44 offline tests, one skip), and `git diff --check` passed.
No live gateway, publication or deployment was used.
