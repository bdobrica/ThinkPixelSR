import asyncio
import time

import httpx
from fastmcp import Client
from thinkpixel_mcp import create_server
from thinkpixel_sr import AsyncThinkPixelSRClient


def test_mcp_discovery_and_tools():
    async def scenario():
        requests = []

        async def handler(request):
            requests.append(request)
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "private-token", "exp": int(time.time()) + 900}
                )
            if request.url.path == "/search":
                return httpx.Response(
                    200, json={"results": [{"id": 1, "text": "chunk", "score": 0.2}]}
                )
            return httpx.Response(
                202,
                json={
                    "received_texts": 2,
                    "pending_documents": 1,
                    "failed_documents": 1,
                    "timestamp": "2026-10-11T00:00:00Z",
                    "pending_ids": [1],
                    "failed_items": [{"id": 2, "error": "publication failed"}],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            sdk = AsyncThinkPixelSRClient(
                base_url="https://example.invalid",
                api_key="private-key",
                transport=transport,
            )
            async with Client(create_server(lambda: sdk)) as mcp:
                tools = {tool.name: tool for tool in await mcp.list_tools()}
                assert set(tools) == {"search", "store"}
                assert tools["search"].annotations.readOnlyHint
                assert not tools["store"].annotations.idempotentHint
                assert "api_key" not in str(tools)
                result = await mcp.call_tool("search", {"text": "query"})
                assert result.data["results"][0]["text"] == "chunk"
                result = await mcp.call_tool(
                    "store",
                    {"documents": [{"id": 1, "text": "one"}, {"id": 2, "text": "two"}]},
                )
                assert result.data["delivery_state"] == "accepted"
                assert result.data["failed_documents"] == 1
                count = len(requests)
                bad = await mcp.call_tool(
                    "store",
                    {"documents": [{"id": 2**31, "text": "x"}]},
                    raise_on_error=False,
                )
                assert bad.is_error and len(requests) == count
            assert sdk._codec._closed

    asyncio.run(scenario())


def test_safe_error():
    async def scenario():
        async def handler(request):
            return httpx.Response(500, text="private-key private-body")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            sdk = AsyncThinkPixelSRClient(
                base_url="https://example.invalid",
                api_key="private-key",
                transport=transport,
            )
            async with Client(create_server(lambda: sdk)) as client:
                result = await client.call_tool(
                    "search", {"text": "q"}, raise_on_error=False
                )
                assert result.is_error
                rendered = str(result.content)
                assert "private" not in rendered
                assert "ServerError" in rendered

    asyncio.run(scenario())


def test_streamable_http():
    from fastmcp.client.transports import StreamableHttpTransport

    async def scenario():
        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "t", "exp": int(time.time()) + 900}
                )
            return httpx.Response(200, json={"results": []})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            sdk = AsyncThinkPixelSRClient(
                base_url="https://example.invalid", api_key="k", transport=transport
            )
            app = create_server(lambda: sdk).http_app(path="/mcp", stateless_http=True)

            def factory(**kwargs):
                return httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), **kwargs
                )

            async with (
                app.lifespan(app),
                Client(
                    StreamableHttpTransport(
                        "http://testserver/mcp", httpx_client_factory=factory
                    )
                ) as client,
            ):
                assert {tool.name for tool in await client.list_tools()} == {
                    "search",
                    "store",
                }
                result = await client.call_tool("search", {"text": "q"})
                assert result.data == {"results": []}

    asyncio.run(scenario())


def test_stdio_discovery():
    import sys
    from pathlib import Path

    from fastmcp.client.transports import StdioTransport

    async def scenario():
        script = Path(__file__).resolve().parents[1] / "thinkpixel_mcp.py"
        transport = StdioTransport(
            sys.executable,
            [str(script)],
            env={
                "THINKPIXEL_BASE_URL": "https://example.invalid",
                "THINKPIXEL_API_KEY": "test-only",
            },
        )
        async with asyncio.timeout(10), Client(transport) as client:
            assert {tool.name for tool in await client.list_tools()} == {
                "search",
                "store",
            }

    asyncio.run(scenario())
