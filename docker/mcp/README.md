# ThinkPixelSR MCP bridge

FastMCP 3.4.8 exposes two tools through the Python SDK: `search(text, language="auto")`
and `store(documents)`. Requires Python 3.11+ and an existing gateway key. This
optional server does not implement enrollment or modify the gateway/cluster.

Setup, Docker hosting, agent configuration, permissions and recovery:
[operator guide](../../docs/clients/mcp.md). Verification:
[offline evidence](../../docs/evidence/mcp/README.md).

From the repository root:

```bash
python3 -m venv docker/mcp/.venv
docker/mcp/.venv/bin/pip install ./clients/python ./docker/mcp
# Inject THINKPIXEL_BASE_URL and THINKPIXEL_API_KEY into the process environment.
docker/mcp/.venv/bin/thinkpixel-sr-mcp                  # stdio
docker/mcp/.venv/bin/thinkpixel-sr-mcp --transport http # 127.0.0.1:8000/mcp
```

Development checks after installing the SDK's `dev` extras:

```bash
PYTHONPATH=clients/python/src:docker/mcp python -m pytest clients/python/tests docker/mcp/tests
ruff check clients/python docker/mcp
ruff format --check clients/python docker/mcp
mypy clients/python/src
```
