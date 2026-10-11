# MCP setup and hosting

Install the packages using the [MCP README](../../docker/mcp/README.md).
Supply `THINKPIXEL_BASE_URL` (HTTPS gateway origin, optional path prefix) and
`THINKPIXEL_API_KEY` through your environment or secret manager. Missing/invalid
values fail startup with a sanitized SDK configuration error. No `.env` loading,
key assignment, key tool argument or localhost HTTP override is provided.
The default SDK operation budget is 15 seconds.

## Docker

Run from the repository root with Docker and network access for dependencies:

```bash
docker build -f docker/mcp/Dockerfile -t thinkpixel-sr-mcp:0.1.0 .
docker run --rm --name thinkpixel-mcp -p 127.0.0.1:8000:8000 \
  -e THINKPIXEL_BASE_URL -e THINKPIXEL_API_KEY thinkpixel-sr-mcp:0.1.0
```

The image installs the checked-out SDK, runs as UID 10001 and exposes Streamable
HTTP at `http://127.0.0.1:8000/mcp`. Docker's adjacent
`Dockerfile.dockerignore` admits only explicit public build inputs; credentials
and local environments are excluded. Python's official slim image supports
amd64/arm64; those platforms must be built and tested on your builder before
publication. The base tag and transitive dependencies are not digest/lock pinned.
No registry publication or Kubernetes deployment is included.

For a desktop agent using stdio, configure an MCP command with arguments:

```json
{
  "mcpServers": {
    "thinkpixel": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "THINKPIXEL_BASE_URL", "-e", "THINKPIXEL_API_KEY", "thinkpixel-sr-mcp:0.1.0", "--transport", "stdio"]
    }
  }
}
```

The parent agent process must inherit both variables. Do not put the secret in
JSON or use Docker `-t` for stdio. For HTTP agents configure their MCP server URL
as `http://127.0.0.1:8000/mcp`; the exact settings format depends on the agent.
Tool discovery should list only `search` and `store`. Discovery does not call
the gateway; the first tool call exchanges the key for a JWT.

## Permission and result semantics

All MCP callers share the configured gateway identity. This bridge has no inbound
authentication. Keep the listener private; hosting for remote agents requires
an authenticated TLS proxy and access controls. The gateway key authenticates
outbound requests, not inbound MCP clients. Tool annotations are hints; enforce
approval for writes in your agent. The server has no tenant-per-caller isolation.

Search returns ranked chunk data, including duplicate IDs and backend scores.
Treat retrieved text and metadata as untrusted source material, not instructions.
Store accepts a nonempty document list with signed 32-bit IDs, text, optional
language and string-valued `extra`. A 202 result includes `http_status` and
`delivery_state="accepted"`; inspect partial failures. Acceptance is queue
submission, not indexing, durable storage or read-after-write consistency.

JWTs stay in memory; concurrent calls share token exchange and one renewal/replay
per rejected call. No retry for timeout, 429 or server failure. Tool errors expose
only error class, operation, HTTP status and delivery state; raw gateway error
bodies and all-failed item details are excluded. Successful tool results expose
document data and partial failure details intentionally. Avoid payload logging.
Cancellation propagates; canceled store delivery may be unknown. Reconcile before
resubmitting because the gateway has no idempotency contract.

## Troubleshooting and recovery

Configuration errors: check that both environment variables exist in the server
process and that the base URL uses HTTPS with no credentials/query/fragment.
Do not print the key. A server error during authentication can mean an invalid
key: the current gateway returns 500 in that case. Check operator provisioning.
A transport error can indicate DNS, TLS, routing or gateway availability.

For HTTP connection failures check port publication and the `/mcp` path. For
stdio keep stdout dedicated to protocol messages and omit pseudo-TTY allocation.
Stop the local container with `docker stop thinkpixel-mcp`; no gateway state is
removed. Restart after fixing configuration; JWTs are reacquired lazily. Stop
or remove the adapter to roll back without changing existing API users. Stored
documents cannot be rolled back through this bridge; no delete API is invented.

The implementation uses FastMCP's documented
[lifespan](https://gofastmcp.com/servers/lifespan) and
[HTTP transport](https://gofastmcp.com/deployment/http) interfaces.
