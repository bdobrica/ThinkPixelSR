# MCP extension verification — CL-050–CL-052

Verified locally on 2026-10-11 with CPython 3.13, FastMCP 3.4.8 and HTTPX 0.28.1.
The Python SDK was bumped to 0.2.0 using `bump2version --allow-dirty minor` in
`clients/python`; the MCP package/image starts at 0.1.0. Neither is published.

Commands from the repository root (temporary virtual environment used):

```bash
PYTHONPATH=clients/python/src:docker/mcp python -m pytest clients/python/tests docker/mcp/tests -q
ruff check clients/python docker/mcp
ruff format --check clients/python docker/mcp
mypy clients/python/src
python -m pip install --no-deps --no-build-isolation ./clients/python ./docker/mcp
make verify
git diff --check
docker build -f docker/mcp/Dockerfile -t thinkpixel-sr-mcp:0.1.0 .
```

- 92 tests passed: 80 unchanged sync SDK cases, 8 async cases and 4 MCP cases.
  Async cases exercise concurrent lazy exchange, store outcomes, one 401 replay,
  sanitization, deadlines, cancellation, expiry, final 401 and malformed auth.
- MCP discovery/search/store and partial acceptance passed with mocked HTTP.
  Invalid int32 input made no HTTP call; auth server errors omitted private bodies.
  Actual stdio subprocess discovery and Streamable HTTP via HTTPX ASGI transport
  passed. The sandbox stdio subprocess stalled; the full suite passed with
  subprocess permission outside the sandbox. All fixtures/credentials were
  synthetic; no live gateway calls.
- Ruff formatting/import/lint and strict SDK mypy passed. Both wheels built and
  installed from source. Python 3.11 minimum was not separately executed.
- Repository verification passed: 44 tests, one existing optional skip, inherited
  runtime baseline retained, documentation links and limited secret scan passed.
- Docker build passed locally on linux/amd64. Network-disabled container smoke
  imported both packages, confirmed UID 10001, SDK 0.2.0 and the two tool names.
  Docker/dependency access required sandbox permission; no registry push occurred.

No arm64 build, live gateway, remote authenticated proxy, image publication,
Kubernetes deployment or production qualification was attempted. Docker base and
transitive dependency versions are not locked. HTTP hosting uses a shared gateway
identity and must remain private or sit behind authenticated TLS access controls.
