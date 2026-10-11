import asyncio
import time

import httpx
import pytest

from thinkpixel_sr import (
    AsyncThinkPixelSRClient,
    Document,
    StoreFailedError,
    TimeoutError,
)


def run(coro):
    return asyncio.run(coro)


def test_concurrent_exchange_and_search():
    async def scenario():
        requests = []

        async def handler(request):
            requests.append(request)
            await asyncio.sleep(0.01)
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "test-token", "exp": int(time.time()) + 900}
                )
            return httpx.Response(
                200, json={"results": [{"id": 1, "text": "chunk", "score": 0.5}]}
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            async with AsyncThinkPixelSRClient(
                base_url="https://example.invalid",
                api_key="test-key",
                transport=transport,
            ) as client:
                results = await asyncio.gather(
                    *(client.search("query") for _ in range(8))
                )
                assert all(r.results[0].text == "chunk" for r in results)
            assert not transport.is_closed
        assert len([r for r in requests if r.url.path == "/auth/token"]) == 1

    run(scenario())


@pytest.mark.parametrize("status", [202, 500])
def test_store_outcomes(status):
    async def scenario():
        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "t", "exp": int(time.time()) + 900}
                )
            assert request.content == b'[{"id": 7, "text": "body"}]'
            return httpx.Response(
                status,
                json={
                    "received_texts": 1,
                    "pending_documents": int(status == 202),
                    "failed_documents": int(status == 500),
                    "timestamp": "2026-10-11T00:00:00Z",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            async with AsyncThinkPixelSRClient(
                base_url="https://example.invalid", api_key="k", transport=transport
            ) as client:
                if status == 500:
                    with pytest.raises(StoreFailedError):
                        await client.store([Document(7, "body")])
                else:
                    assert (
                        await client.store([Document(7, "body")])
                    ).delivery_state == "accepted"

    run(scenario())


def test_one_replay_and_sanitized_error():
    async def scenario():
        paths = []

        async def handler(request):
            paths.append(request.url.path)
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "secret", "exp": int(time.time()) + 900}
                )
            if paths.count("/search") == 1:
                return httpx.Response(401)
            raise RuntimeError("secret-key body")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            async with AsyncThinkPixelSRClient(
                base_url="https://example.invalid", api_key="k", transport=transport
            ) as client:
                with pytest.raises(Exception) as exc:
                    await client.search("q")
                assert "secret" not in str(exc.value)
                assert exc.value.__context__ is None
        assert paths == ["/auth/token", "/search", "/auth/token", "/search"]

    run(scenario())


def test_deadline_and_cancellation():
    async def scenario():
        entered = asyncio.Event()

        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(
                    200, json={"token": "t", "exp": int(time.time()) + 900}
                )
            entered.set()
            await asyncio.sleep(10)
            return httpx.Response(200)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            async with AsyncThinkPixelSRClient(
                base_url="https://example.invalid",
                api_key="k",
                transport=transport,
                timeout=0.04,
            ) as client:
                start = time.monotonic()
                with pytest.raises(TimeoutError) as exc:
                    await client.store([Document(1, "body")])
                assert exc.value.delivery_state == "unknown"
                assert time.monotonic() - start < 1
                entered.clear()
                task = asyncio.create_task(client.search("q"))
                await entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

    run(scenario())


@pytest.mark.parametrize("mode", ["expired", "final401", "malformed"])
def test_auth_state(mode):
    from thinkpixel_sr import AuthenticationError, ProtocolError

    async def scenario():
        exchanges = 0

        async def handler(request):
            nonlocal exchanges
            if request.url.path == "/auth/token":
                exchanges += 1
                if mode == "malformed":
                    return httpx.Response(200, json={"token": "t", "exp": 0})
                return httpx.Response(
                    200, json={"token": f"t{exchanges}", "exp": int(time.time()) + 900}
                )
            return httpx.Response(
                401 if mode == "final401" else 200, json={"results": []}
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as transport:
            async with AsyncThinkPixelSRClient(
                base_url="https://example.invalid", api_key="k", transport=transport
            ) as client:
                if mode == "expired":
                    await client.search("q")
                    client._codec._exp = 0
                    await client.search("q")
                    assert exchanges == 2
                else:
                    with pytest.raises(
                        AuthenticationError if mode == "final401" else ProtocolError
                    ):
                        await client.search("q")
                    assert client._codec._token is None
                    assert exchanges == (2 if mode == "final401" else 1)

    run(scenario())
