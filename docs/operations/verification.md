# Verification and API/WordPress smoke

This is an operator specification against [the as-built source](../architecture.md),
not a report of successful deployment. [Evidence](../evidence/phase-0/README.md)
records what actually ran and why live checks did not run. Root `make verify`,
`doctor`, `config-check` and opt-in `verify-live` now exist; see the
[command guide](commands.md). Offline wrapper checks do not establish the live
baseline described here. These procedures do not authorize a live
test, installation, SQL migration or repository cutover.

## Current checkout checks and dev acceptance

From ThinkPixelSR, without operator credentials:

```bash
make help
make doctor
make verify
```

Help lists actual root targets. Doctor checks binary versions without service
access; it can fail when a tool for a command family is missing. Verify runs
synthetic configuration/wrapper tests, syntax/format/render/link gates and
reports optional-tool skips. It contacts no real backend, Docker daemon,
cluster or API. The forwarding test uses real Terragrunt with a fake Terraform
in a temporary fixture. Full runtime/model tests are not part of this command.

With existing local credentials configured, `make config-check ENV=dev` should
pass without authenticating. `make config-check ENV=prod` should fail explicitly;
there is no dev fallback. To preview actual arguments locally, use the DRY_RUN
examples in the [command reference](commands.md). No production setup is
implemented. Documentation syntax/render success is not live acceptance.

For an explicitly authorized dev lifecycle, use the guides in this order:

1. [Configuration](../configuration.md), then authoritative state/key/DNS review
   and [Hetzner init/plan/reviewed apply](../deployment/hetzner.md).
2. Existing operator/CRD/decryption/credential prerequisites, then
   [Flux attachment and revision checks](../deployment/fluxcd.md). Stop at any
   missing bootstrap or schema prerequisite; do not invent an installer/migration.
3. Verify [exact image platforms, published digest and cluster pulls](images.md),
   secret decryption, PVC binding, and every tenant/workload. No push is needed
   merely to test an already approved image; publishing is a separate live action.
4. Run redacted status and the opt-in health check below. Then perform the
   disposable-site API and **actual plugin** checks in this guide.
5. Record sanitized assertions with checkout/plugin revision, effective deployed
   image tags/digests, Flux applied revision, schema prerequisite status and
   fixture IDs. Compare to the source baseline; record every failure/blocker.

```bash
make status ENV=dev KUBE_CONTEXT='<verified-dev-context>'
make verify-live ENV=dev API_URL='https://<reviewed-dev-gateway>:8080' LIVE_REVIEWED=1 DRY_RUN=1
make verify-live ENV=dev API_URL='https://<reviewed-dev-gateway>:8080' LIVE_REVIEWED=1
```

The live health target validates HTTPS, refuses redirects and checks GET /ping
and /ready with bounded time/response size. It requires status ok and database
healthy readiness. It does not inspect NATS, models, Qdrant, Redis or WordPress,
authenticate, ingest or delete. Those acceptance gates remain separate.
Context and endpoint must refer to the same reviewed dev installation.

Do not continue a writable smoke after unexplained source/image drift, broken
state/ownership, missing storage/backups, pending secret decryption or an
unsettled consumer. Stop after a bounded retrieval failure; keep private logs
and only scoped fixture cleanup. Repository/source rollback follows
[migration](../migration.md); node/data recovery follows the deployment/scaling
guides and existing backups. A successful health check is insufficient to
approve cutover or declare recovered data.

## Frozen baseline reproduction

Use a **tracked-only temporary export** of ThinkPixelInfra commit
`9e5fc87495832d3a2554965341cbeb43911ff5f5`, not a copy including ignored local
secrets. From ThinkPixelSR, the inventory is reproduced by:

```bash
git -C ../ThinkPixelInfra ls-tree -r --long 9e5fc87495832d3a2554965341cbeb43911ff5f5
git -C ../ThinkPixelInfra status --short
```

After exporting to an operator-selected temporary directory, run the following
from the export root. These commands change no cluster resources:

```bash
make -C local help
docker compose -f local/docker-compose.yaml config --quiet
terraform -chdir=cluster fmt -check -recursive
terragrunt hcl fmt --check --working-dir cluster/live
kubectl kustomize k8s/flux-system/dev > /dev/null
kubectl kustomize k8s/apps/thinkpixel/dev > /dev/null
kubectl kustomize k8s/apps/monitoring/dev > /dev/null
kubectl kustomize --load-restrictor=LoadRestrictionsNone k8s/apps/nats/dev > /dev/null
kubectl kustomize --load-restrictor=LoadRestrictionsNone k8s/apps/cert-manager/dev > /dev/null
kubectl kustomize --load-restrictor=LoadRestrictionsNone k8s/apps/reflector/dev > /dev/null
```

The last three require permissive loading because they reference individual
files outside their overlay directory. That is a local render observation, not
an instruction to relax cluster security or evidence of Flux success. The
frozen dev HCL formatting check fails; the current Phase 2 dev HCL passes.
Empty prod overlays fail rendering. No init/apply/bootstrap is needed for
these checks. These statements concern the frozen export, not a new failed
check on the current checkout.

From `docker/api_gateway/api_gateway` in the export:

```bash
GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off go test ./...
```

Use a private writable Go cache, as in the evidence run. Missing cached modules
would be a prerequisite gap, not a reason to fabricate a pass. `bash -n <file>`
checks each of the 16 tracked shell scripts; Python `ast.parse` checks all 81
tracked Python files without writing bytecode or loading models. Model unit
tests additionally require their Python dependencies/model assets and were not
run. Go tests use mocks where applicable and do not prove live MySQL, NATS,
model inference or Qdrant compatibility.

## Existing integration scripts: inspect before use

`local/tests/` contains seven shell tests. They mutate a disposable Docker stack;
they are not offline checks. In particular:

- `test-api.sh`, `test-store-handler.sh`: registration/mock-site, JWT and request behavior; valid stores require the compatible schema and node assignment.
- `test-auth-store-search.sh`: inserts sites, applies a patch, logs test keys, uses `eval`, and its exit trap deletes **every Qdrant collection**. Never run it against shared data or treat it as safe cleanup.
- `test-database-nats.sh`: dependency inspection and database/queue activity.
- `test-dlq-reinject.sh`: broken node assignment, retries, Redis DLQ and reinjection; only in a disposable stack.
- `test-graceful-shutdown.sh`: stops/restarts containers; disruptive.
- `test-metrics.sh`: metrics requests plus workload generation; requires a running stack.

The local Make `db-init` path loads base SQL and `local/init-db.sql` and skips
patches although the gateway reads newer columns. `database/init.sh` has a
plural/singular version-table mismatch. Do not bypass either problem with an
unreviewed live migration. Resolve the setup baseline in a focused follow-up
before calling local integration tests a reproducible golden path.

## Minimal Qdrant API smoke: disposable site only

Prerequisites: operator-approved dev target, reachable gateway, compatible MySQL
schema and **dedicated disposable site**, valid API key, site configured for
Qdrant and the deployed model, running NATS consumer, reachable model and Qdrant.
Confirm that document IDs 900001 and 900002 are unused in that site. Never use
production, customer data or an existing post ID. Do not switch a real site's
backend or model to satisfy this test.

Fixtures in [phase-0 evidence](../evidence/phase-0/README.md) contain public
synthetic facts: an orange lighthouse and a violet library. Expected IDs, rather
than exact embedding scores, provide the comparison. Search scores/order across
different model/image versions are not asserted. A result with the matching ID
and text is required; a mere HTTP 200 or plugin indexing mark is insufficient.

| Step | Input / assertion | Expected observable result |
| --- | --- | --- |
| Liveness | GET `/ping` | 200 with `status: ok` |
| Readiness | GET `/ready` | 200, `status: ready`, `checks.database: healthy`; does not check NATS/model/vector DB |
| Missing JWT | POST `/store` with store fixture, no Authorization | 401, no authenticated publishing |
| Missing API key | POST `/auth/token`, no X-API-Key | 400; invalid keys can return 500 on DB lookup, so do not assert universal 401 |
| Token | POST `/auth/token`, X-API-Key supplied privately | 200; nonempty `token`, numeric future `exp`; do not capture token in evidence |
| Negative payloads | With valid JWT: store `[]`; search `{}` | 400 in both cases |
| Enqueue | POST `/store` with `store.json` | 202; `received_texts: 2`, `pending_documents: 2`, `failed_documents: 0`, pending IDs 900001/900002, RFC3339 timestamp |
| Retrieve | POST `/search` with `search.json`, bounded retry | 200; `results` array includes `id: 900001`, numeric `score`, text containing the lighthouse fact |
| Cleanup | POST `/remove/embeddings` with `remove.json`, only after ingestion finishes | 200 with `ids: ["900001", "900002"]` and success message; verify those post IDs absent from the disposable site's Qdrant points |

The fixture store and retrieval are writable live actions. The following shows
the inspected API invocation without embedding secrets in shell commands; it
has not been executed. Run from ThinkPixelSR after authorization. Set
`P0_API_URL` to the reviewed dev HTTPS origin (including its verified port,
with no userinfo, path, query or fragment). Supply `P0_AUTH_CURL_CONFIG` as an
existing private curl config containing only the X-API-Key header for the
disposable site (mode 0600, outside both repositories). No shell tracing or
curl verbosity should be enabled.

```bash
umask 077
P0_RUN_DIR=$(mktemp -d)
: "${P0_API_URL:?Set the authorized dev gateway URL}"
: "${P0_AUTH_CURL_CONFIG:?Set the private API-key curl config path}"
curl --proto '=https' --fail --silent --show-error --max-time 30 \
  --config "$P0_AUTH_CURL_CONFIG" -X POST "$P0_API_URL/auth/token" \
  --output "$P0_RUN_DIR/auth.json"
# Derive the private Bearer-header curl config without printing the token.
python3 - "$P0_RUN_DIR" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
token = json.loads((root / 'auth.json').read_text())['token']
if not isinstance(token, str) or not token or any(c in token for c in '\r\n"\\'):
    raise SystemExit('Invalid token response')
(root / 'bearer.conf').write_text('header = "Authorization: Bearer ' + token + '"\n')
PY
curl --proto '=https' --fail --silent --show-error --max-time 30 \
  --config "$P0_RUN_DIR/bearer.conf" -H 'Content-Type: application/json' \
  --data-binary @docs/evidence/phase-0/store.json "$P0_API_URL/store" \
  --output "$P0_RUN_DIR/store.json" --write-out '%{http_code}\n'
curl --proto '=https' --fail --silent --show-error --max-time 30 \
  --config "$P0_RUN_DIR/bearer.conf" -H 'Content-Type: application/json' \
  --data-binary @docs/evidence/phase-0/search.json "$P0_API_URL/search" \
  --output "$P0_RUN_DIR/search.json" --write-out '%{http_code}\n'
```

Inspect response assertions locally with a JSON parser. Repeat the last search
every two seconds for at most 60 seconds; record timeout/failure rather than
retrying indefinitely. Wait for the consumer before the initial publish: NATS
Core plus subscriber toggling can lose messages while unsubscribed. Search can
return 500 for a not-yet-created collection or 408 after the handler's 10-second
wait; the dev model HTTP timeout of 180s does not remove that search limit.
These outcomes are baseline failures to investigate, not smoke passes.

After confirming processing has stopped for both fixture IDs, cleanup uses the
same private bearer config and **only** the two IDs:

```bash
curl --proto '=https' --fail --silent --show-error --max-time 30 \
  --config "$P0_RUN_DIR/bearer.conf" -H 'Content-Type: application/json' \
  --data-binary @docs/evidence/phase-0/remove.json "$P0_API_URL/remove/embeddings" \
  --output "$P0_RUN_DIR/remove.json" --write-out '%{http_code}\n'
```

Read-only Qdrant inspection should filter the dedicated `site_<site ID>`
collection by `post_id` to confirm absence; a semantic search alone may return
similar unrelated content. If queued retries remain, deletion may race reindexing;
stop and have the operator settle that disposable site's work before final
cleanup. Dispose of private auth/config files and test-site credentials locally.
Never delete all collections, wipe shared volumes, or run the inherited broad
cleanup trap. Only sanitized assertions/counts belong in Git.

## WordPress plugin golden path (separate acceptance test)

This records the existing client flow inspected in the separate repository;
it is not a claim that a live known-good run has been reproduced. The actual
plugin test is required even after a passing direct API smoke. Existing queue,
model and Qdrant diagnostic commands are in [troubleshooting](troubleshooting.md).

The available separate plugin checkout is SearchPixel v1.4.5 at
`b8f64d05cbe11a58dbf7f7dcee0f5dce271d7d63`. Its gateway URL is compiled into
`searchpixel/class/core/strings.php`; it is not an operator setting demonstrated
by this baseline. A dev WordPress test requires an already approved plugin build
targeting the selected dev gateway. Do not silently edit that repository or send
fixture traffic to its default public endpoint.

1. On a dedicated test WordPress installation, confirm the plugin build/revision,
   callback reachability over HTTPS, matching `/searchpixel/v1/validate/` and
   `/searchpixel/v1/exchange/` gateway settings, valid schema, node allocation and
   model. Record hostnames as placeholders.
2. Register through the plugin's existing settings flow. Observe gateway `/register`
   success, WordPress validation response matching domain/path/token and nonce,
   exchange response `success: "true"`, active hashed API-key row and successful
   JWT exchange. Save no tokens or headers.
3. Publish a post titled “Phase 0 Orange Lighthouse” containing the first fixture's
   synthetic fact, record its **actual WordPress post ID**, and let the plugin's
   existing indexing mechanism submit it. It sends `{id,text,extra:{title,type}}`;
   verify gateway 202 counts and the matching site/post in Qdrant independently.
4. Search “orange lighthouse opens at nine” through WordPress and confirm the
   fixture post/link appears. This validates the WordPress UI path as well as
   the gateway result, not just a direct API call. Record the sanitized result
   and compare both source revision and actual running image tags.
5. Delete the fixture post through the plugin path, verify its embedding removal
   and settle any queued work. If needed, use the existing scoped removal API
   for that recorded post ID in that test site only; dispose of the test-site
   credentials and private WordPress fixtures through the operator's normal process.

The mock site only simulates callbacks and cannot prove WordPress compatibility.
The plugin prefers `stored_ids` then falls back to sent IDs instead of inspecting
gateway `pending_ids`; partial publication must be verified separately. The
batch-size guidance handler has a context-type/schema mismatch (blocker B14); record
the plugin's fallback sizing rather than claiming that endpoint passed. Live
WordPress, registration, indexing, retrieval and deletion are all **unverified**
in this makeover. A real known-good comparison remains a Phase 5 gate.
