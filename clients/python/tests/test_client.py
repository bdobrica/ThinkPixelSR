import json
import time
import traceback
from pathlib import Path

import httpx
import pytest

from thinkpixel_sr import (
    AuthenticationError,
    ConfigurationError,
    Document,
    HTTPError,
    PermissionError,
    ProtocolError,
    RateLimitError,
    ServerError,
    StoreFailedError,
    ThinkPixelSRClient,
    TimeoutError,
    TransportError,
    ValidationError,
)

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class Adapter:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply()
        return reply

    def close(self):
        self.closed = True


def auth():
    return httpx.Response(
        200, json={"token": "synthetic-token", "exp": int(time.time()) + 900}
    )


def setup(*replies):
    adapter = Adapter(replies)
    return ThinkPixelSRClient(
        base_url="https://example.invalid/prefix/",
        api_key="synthetic-key",
        transport=adapter,
    ), adapter


def test_wire_cache_and_shapes():
    client, adapter = setup(
        auth(),
        httpx.Response(202, json=fixture("store-accepted.response.json")),
        httpx.Response(200, json=fixture("search-success.response.json")),
    )
    docs = fixture("store-accepted.request.json")
    result = client.store([Document(**doc) for doc in docs])
    assert result.to_dict() == fixture("store-accepted.response.json")
    assert result.delivery_state == "accepted"
    assert client.search("question").to_dict() == fixture(
        "search-success.response.json"
    )
    method, url, kwargs = adapter.calls[0]
    assert method == "POST" and url.endswith("/prefix/auth/token")
    assert kwargs["content"] is None
    assert kwargs["headers"] == {
        "Accept": "application/json",
        "X-API-Key": "synthetic-key",
    }
    assert json.loads(adapter.calls[1][2]["content"]) == docs
    assert adapter.calls[1][2]["headers"]["Authorization"] == "Bearer synthetic-token"
    assert len(adapter.calls) == 3


@pytest.mark.parametrize("name", ["store-accepted", "store-partial"])
def test_store_fixtures(name):
    client, _ = setup(
        auth(), httpx.Response(202, json=fixture(name + ".response.json"))
    )
    assert client.store([Document(1, "")]).to_dict() == fixture(name + ".response.json")


def test_all_failed():
    client, adapter = setup(
        auth(), httpx.Response(500, json=fixture("store-all-failed.response.json"))
    )
    with pytest.raises(StoreFailedError) as caught:
        client.store([Document(1, "a")])
    assert caught.value.result.to_dict() == fixture("store-all-failed.response.json")
    assert caught.value.delivery_state == "failed"
    assert len(adapter.calls) == 2


@pytest.mark.parametrize(
    "name", ["search-success", "search-empty-qdrant", "search-empty-redis"]
)
def test_search_fixtures(name):
    client, _ = setup(
        auth(), httpx.Response(200, json=fixture(name + ".response.json"))
    )
    assert client.search("q").to_dict() == fixture(name + ".response.json")


def test_duplicates_extensions_repr():
    data = {
        "results": [{"id": 1, "text": "private", "score": -1.5, "secret": "private"}]
        * 2,
        "unknown": "private",
    }
    client, _ = setup(auth(), httpx.Response(200, json=data))
    result = client.search("q")
    assert result.to_dict() == data and len(result.results) == 2
    assert "private" not in repr(result) + repr(result.results[0])


@pytest.mark.parametrize(
    "status,error",
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, PermissionError),
        (408, TimeoutError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
        (302, HTTPError),
        (201, ProtocolError),
    ],
)
def test_statuses(status, error):
    replies = [auth(), httpx.Response(status, text="private")]
    if status == 401:
        replies += [auth(), httpx.Response(401, text="private")]
    client, _ = setup(*replies)
    with pytest.raises(error) as caught:
        client.search("q")
    assert caught.value.http_status == status
    assert "private" not in repr(caught.value)
    if status == 401:
        assert client._token is None


def test_store_401_once_same_body():
    client, adapter = setup(
        auth(),
        httpx.Response(401),
        auth(),
        httpx.Response(202, json=fixture("store-accepted.response.json")),
    )
    client.store([Document(1, "a")])
    assert len(adapter.calls) == 4
    assert adapter.calls[1][2]["content"] == adapter.calls[3][2]["content"]


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("private"),
        httpx.ConnectError("private"),
        httpx.Response(503),
        httpx.Response(202, text="broken"),
    ],
)
def test_store_uncertain_no_retry(failure):
    client, adapter = setup(auth(), failure)
    with pytest.raises((TransportError, ServerError, ProtocolError)) as caught:
        client.store([Document(1, "a")])
    assert caught.value.delivery_state == "unknown" and len(adapter.calls) == 2
    assert caught.value.__context__ is None
    assert "private" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": None},
        {"results": [None]},
        {"results": [{"id": True, "text": "x", "score": 1}]},
        {"results": [{"id": 1, "text": "x", "score": float("inf")}]},
    ],
)
def test_bad_search(payload):
    client, _ = setup(auth(), httpx.Response(200, content=json.dumps(payload)))
    with pytest.raises(ProtocolError):
        client.search("q")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"token": "x", "exp": True},
        {"token": "x", "exp": 1},
        {"token": "", "exp": 9999999999},
    ],
)
def test_bad_auth(payload):
    client, _ = setup(httpx.Response(200, json=payload))
    with pytest.raises(ProtocolError):
        client.authenticate()
    assert client._token is None


def test_invalid_key_stays_500():
    client, _ = setup(
        httpx.Response(500, json=fixture("auth-invalid-key.response.json"))
    )
    with pytest.raises(ServerError):
        client.authenticate()


def test_expiry_and_explicit_exchange(monkeypatch):
    client, adapter = setup(
        auth(), auth(), httpx.Response(200, json={"results": []}), auth()
    )
    client.authenticate()
    client._exp = int(time.time()) + 29
    client.search("q")
    client.authenticate()
    assert len(adapter.calls) == 4


@pytest.mark.parametrize(
    "docs",
    [
        [],
        [Document(True, "x")],
        [Document(2**31, "x")],
        [Document(-(2**31) - 1, "x")],
        [Document(1, 42)],
        [Document(1, "x", extra={"x": 2})],
        [{}],
    ],
)
def test_local_validation(docs):
    client, adapter = setup()
    with pytest.raises(ValidationError):
        client.store(docs)
    assert not adapter.calls


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid",
        "https://u:p@example.invalid",
        "https://example.invalid?q=x",
        "https://example.invalid#x",
        "",
        "https://example.invalid:bad",
        "http://localhost.evil",
        "https://example.invalid\\evil",
    ],
)
def test_bad_origin(url):
    with pytest.raises(ConfigurationError):
        ThinkPixelSRClient(base_url=url, api_key="x", allow_insecure_localhost=True)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_local_optin(host):
    with pytest.raises(ConfigurationError):
        ThinkPixelSRClient(base_url="http://" + host, api_key="x")
    with ThinkPixelSRClient(
        base_url="http://" + host, api_key="x", allow_insecure_localhost=True
    ):
        pass


def test_env_precedence(monkeypatch):
    monkeypatch.setenv("THINKPIXEL_API_KEY", "environment-key")
    client = ThinkPixelSRClient(
        base_url="https://example.invalid", transport=Adapter([])
    )
    assert client._key == "environment-key" and "environment-key" not in repr(client)
    explicit = ThinkPixelSRClient(
        base_url="https://example.invalid", api_key="explicit", transport=Adapter([])
    )
    assert explicit._key == "explicit"
    with pytest.raises(ConfigurationError):
        ThinkPixelSRClient(base_url="https://example.invalid", api_key="")
    monkeypatch.delenv("THINKPIXEL_API_KEY")
    with pytest.raises(ConfigurationError):
        ThinkPixelSRClient(base_url="https://example.invalid")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12", 12),
        ("bad", None),
        ("-1", None),
        ("Tue, 01 Jan 2030 00:00:00 GMT", 10),
        ("Mon, 01 Jan 2029 00:00:00 GMT", 0),
    ],
)
def test_retry_after(monkeypatch, raw, expected):
    monkeypatch.setattr(time, "time", lambda: 1893455990)
    client, _ = setup(auth(), httpx.Response(429, headers={"Retry-After": raw}))
    with pytest.raises(RateLimitError) as caught:
        client.search("q")
    assert caught.value.retry_after_seconds == expected


def test_deadline_shared(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    def exchange():
        clock[0] = 10
        return auth()

    client, adapter = setup(exchange, httpx.Response(200, json={"results": []}))
    client.search("q")
    assert adapter.calls[0][2]["timeout"] == 15
    assert adapter.calls[1][2]["timeout"] == 5


def test_deadline_no_replay(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    def slow():
        clock[0] = 16
        return httpx.Response(401)

    client, adapter = setup(auth(), slow)
    with pytest.raises(TimeoutError):
        client.store([Document(1, "x")])
    assert len(adapter.calls) == 2


def test_owned_and_injected_close():
    client, adapter = setup()
    client.close()
    assert not adapter.closed
    with pytest.raises(ConfigurationError):
        client.authenticate()
    owned = ThinkPixelSRClient(base_url="https://example.invalid", api_key="x")
    owned.close()
    assert owned._transport.is_closed


@pytest.mark.parametrize(
    "change",
    [
        {"pending_ids": None},
        {"failed_items": None},
        {"pending_documents": -1},
        {"received_texts": True},
        {"timestamp": "yesterday"},
        {"pending_ids": []},
        {"failed_items": [None]},
    ],
)
def test_malformed_store(change):
    data = {**fixture("store-partial.response.json"), **change}
    client, _ = setup(auth(), httpx.Response(202, json=data))
    with pytest.raises(ProtocolError) as caught:
        client.store([Document(1, "x")])
    assert caught.value.delivery_state == "unknown"


def test_httpx_adapter_no_redirect():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("auth/token"):
            return auth()
        return httpx.Response(302, headers={"Location": "https://other.invalid"})

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as transport:
        client = ThinkPixelSRClient(
            base_url="https://example.invalid", api_key="x", transport=transport
        )
        with pytest.raises(HTTPError):
            client.search("q")
    assert len(requests) == 2


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_bad_timeout(timeout):
    with pytest.raises(ConfigurationError):
        ThinkPixelSRClient(
            base_url="https://example.invalid", api_key="x", timeout=timeout
        )


def test_explicit_auth_failure_clears_cache():
    client, _ = setup(auth(), httpx.Response(500, text="private"))
    client.authenticate()
    with pytest.raises(ServerError):
        client.authenticate()
    assert client._token is None


def test_store_optional_absence_and_extensions():
    data = {
        "received_texts": 1,
        "pending_documents": 1,
        "failed_documents": 0,
        "timestamp": "2030-01-01T00:00:00Z",
        "opaque": "private",
    }
    client, _ = setup(auth(), httpx.Response(202, json=data))
    result = client.store([Document(-(2**31), "")])
    assert result.to_dict() == data
    assert result.pending_ids is None and result.failed_items is None
    assert "private" not in repr(result)


@pytest.mark.parametrize("body", [b"not-json", b'{"results": []', b"[]", b"null"])
def test_bad_json(body):
    client, _ = setup(auth(), httpx.Response(200, content=body))
    with pytest.raises(ProtocolError):
        client.search("q")


def test_malformed_store_500_is_server_error():
    client, _ = setup(auth(), httpx.Response(500, json={"received_texts": 5}))
    with pytest.raises(ServerError) as caught:
        client.store([Document(1, "a")])
    assert not isinstance(caught.value, StoreFailedError)
    assert caught.value.delivery_state == "unknown"
