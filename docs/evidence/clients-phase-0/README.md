# Client Phase 0 evidence

CL-001–CL-007, recorded 2026-10-11. The
[wire baseline](../../../clients/contracts/README.md) is source-audited and
ready for independent review. Gate 0 remains unchecked: no peer review or live
WordPress compatibility result is asserted.

## Inspected inputs

| Input | Revision / paths inspected |
| --- | --- |
| ThinkPixelSR | `89fe1899b7f008cbd30cf073e0f748e1529d7519`; clean initial working tree; `docker/api_gateway/api_gateway/main.go`, `auth/`, `middleware/auth_middleware.go`, `handlers/{store,search,max_batch_text_size,refresh_key}_handler.go` (batch guidance file is `max_batch_text_size.go`), `utils/rest.go`, `register/`, `db/db.go`, `db/assign*.go`, `document_queue/`, `model/interface.go`, `qdrantconn/qdrantconn.go`, `redisconn/redisconn.go` |
| Persistence/configuration | `database/db_thinkpixel.sql`, `database/patches/`, `local/docker-compose.yaml`, `k8s/apps/thinkpixel/base/api-gateway/{service,configmap,deployment}.yaml`; no sensitive local config read |
| ThinkPixelPlugin | `b8f64d05cbe11a58dbf7f7dcee0f5dce271d7d63`; temporary read-only shallow clone from the public repository; `searchpixel/class/core/{strings,api,rest,settings,ui,plugin,cron}.php`, `tests/unit/core/ApiTest.php`, test setup/Composer manifest |
| Prior baseline | `docs/evidence/phase-0/README.md`, public store/search fixtures, `docs/operations/verification.md`; historical evidence is not a new live run |

The source paths and branches underpin the matrix and fixture index. This
change only adds contract/evidence artifacts and updates client tracking/docs;
no application, plugin, database, deployment or infrastructure files change.
The offline audit allows only the new contract README and JSON fixture paths;
documentation link checking now includes `clients/`. SDK code remains outside
the reviewed makeover allowlist.
No credentials, raw HTTP logs, state or live payloads were copied.

## CL-007: documented baseline smoke (not executed)

Use the existing [operator smoke specification](../../operations/verification.md#wordpress-plugin-golden-path-separate-acceptance-test)
and [direct API prerequisites](../../operations/verification.md#minimal-qdrant-api-smoke-disposable-site-only).
They include private credential handling, expected responses, bounded polling,
scoped cleanup and recovery. Those procedures require explicit permission and
a disposable non-production site; this source audit does not authorize traffic
to the compiled public plugin endpoint.

1. Confirm approved dev origin/TLS, installed gateway image and plugin revisions,
   compatible SQL schema, dedicated site/key, node/model assignment, matching
   callback paths, warm model and active NATS subscriber. Keep source SHAs and
   deployed digests separately recorded; this checkout SHA is not deployment proof.
2. On a dedicated WordPress test installation, register through existing settings
   and observe validation/exchange callbacks, active hashed-key row and JWT
   exchange. Record counts/statuses only, never credentials or token responses.
3. Publish a post with the orange-lighthouse synthetic fact from the fixture;
   record its actual WordPress ID (900001 is only a direct API fixture ID).
   Trigger the existing plugin indexing flow. Check 202 `pending_ids` and every
   failure, then independently inspect the matching site/post in Qdrant.
4. Search the fact through WordPress. Poll retrieval every two seconds for no
   more than 60 seconds and record failure if the post/link does not appear.
   Verify indexing separately from the plugin's processed-row count; its fallback
   can mark all sent IDs despite partial or total queue failure.
5. Delete only the test post through the existing plugin path. Settle queued
   processing, confirm its points are absent in the test site's collection,
   and use scoped removal if necessary. Never run inherited all-collection
   cleanup scripts against a shared stack.

Current result: **NOT RUN**. No approved dev smoke target, disposable WordPress
installation or test credentials were supplied for this task. Existing cluster
use/deferred live acceptance remains in force. No cloud calls, registry actions,
Flux changes, SQL writes, Docker startup, registration or API ingestion occurred.
CL-007 is completed via its explicit “document a baseline” option, not a live pass.

## Verification

| Command/check | Result |
| --- | --- |
| `make help` | PASS; lists existing targets without deployment |
| `make doctor` | Exit 2: installed Terragrunt 0.81.0 is below supported 0.96.1; no packages installed |
| `make config-check ENV=dev` | Expected exit 2 for missing secret file; no credentials used |
| `make config-check ENV=prod` | Expected exit 2: production configuration unsupported, no fallback |
| `make config-check`, `make config-check ENV=invalid` | Expected exit 2 for missing/invalid environment |
| `make verify` | PASS after narrow contract-artifact audit allowance: 42 tests run, 1 skipped; Python/Make/shell syntax, Terraform/dev HCL formatting and six Kustomize renders pass; 401/405 inherited files byte-identical; limited candidate secret/path scan passes; 247 documentation links pass |
| Fixture/link consistency via Python standard library | PASS: 34 JSON files, 18 indexed HTTP cases; all indexed source/body paths exist; store counters/ID counts agree; 31 local client/evidence links and fragments resolve |
| `git diff --check` and final scope review | PASS; runtime/manifests/schema unchanged |

The first `make verify` run rejected the new contract paths under the previous
makeover allowlist. It was resolved by allowing the exact contract README and
JSON fixtures only, retaining SDK-code rejection; the existing audit regression
now covers client code and non-JSON fixture rejection. The forwarding test is
skipped because this machine's Terragrunt is too old. Full gateway/model and
plugin PHPUnit suites were not run: this change does not edit those sources,
and their checks do not prove live acceptance.

Synthetic fixtures verify documented shapes; they do not execute
auth/queue/retrieval handlers or establish Gate 3. Plugin PHPUnit requires its dependency/runtime
setup and is not a live compatibility test; no plugin dependency installation
or WordPress startup is part of this docs-only task.

## Gate 0 review checklist

Independent reviewer should compare the pinned plugin methods against gateway
routes/structs and examine invalid-key 500 behavior, partial/all-failed store
responses, missing stored IDs, broken batch/rotation context types, backend
scores, cache revocation delay and the existing callback registration path.
Record reviewer/revision and remaining acceptance gaps before checking Gate 0.
Do not begin SDK implementations by treating synthetic fixtures as live captures.
