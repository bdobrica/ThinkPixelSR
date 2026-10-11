import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { inspect } from "node:util";
import * as sdk from "../dist/index.js";
const key = "SYNTHETIC_NOT_AN_API_KEY";
const auth = () => ({
  token: "SYNTHETIC_NOT_A_JWT",
  exp: Math.floor(Date.now() / 1000) + 900,
});
const response = (status, data, headers) =>
  new Response(typeof data === "string" ? data : JSON.stringify(data), {
    status,
    headers,
  });
const fixture = async (name) =>
  JSON.parse(
    await readFile(
      new URL(`../../contracts/fixtures/${name}.json`, import.meta.url),
    ),
  );
const docs = [{ id: 900001, text: "test" }];
const accepted = {
  received_texts: 1,
  pending_documents: 1,
  failed_documents: 0,
  timestamp: "2030-01-01T00:00:00Z",
};
function client(replies = [], options = {}) {
  const calls = [];
  const transport = async (url, init) => {
    calls.push({ url, ...init });
    const item = replies.shift();
    if (typeof item === "function") return item(url, init);
    if (item instanceof Error) throw item;
    if (!item) throw new Error("unexpected request");
    return item;
  };
  return {
    calls,
    client: new sdk.ThinkPixelSRClient({
      baseUrl: "https://gateway.example/prefix/",
      apiKey: key,
      transport,
      ...options,
    }),
  };
}
for (const name of ["store-accepted", "store-partial", "store-all-failed"])
  test(`shared fixture ${name}`, async () => {
    const data = await fixture(`${name}.response`);
    const status = name === "store-all-failed" ? 500 : 202;
    const c = client([response(200, auth()), response(status, data)]);
    if (status === 500)
      await assert.rejects(
        c.client.store(docs),
        (e) =>
          e instanceof sdk.StoreFailedError &&
          e.result.failed_documents === 2 &&
          e.delivery_state === "failed",
      );
    else {
      const r = await c.client.store(docs);
      assert.equal(r.pending_documents, data.pending_documents);
      assert.equal(r.http_status, 202);
      assert.equal(r.delivery_state, "accepted");
      assert.equal(
        Object.hasOwn(r, "failed_items"),
        Object.hasOwn(data, "failed_items"),
      );
    }
    assert.equal(c.calls.length, 2);
  });
for (const name of [
  "search-success",
  "search-empty-qdrant",
  "search-empty-redis",
])
  test(`shared fixture ${name}`, async () => {
    const data = await fixture(`${name}.response`);
    const c = client([response(200, auth()), response(200, data)]);
    const r = await c.client.search("query");
    assert.deepEqual(
      r.results.map(({ id, text, score }) => ({ id, text, score })),
      data.results,
    );
  });
test("exact requests, prefix, lazy cache, explicit auth, private credentials", async () => {
  const c = client([
    response(200, auth()),
    response(202, accepted),
    response(200, { results: [] }),
    response(200, auth()),
  ]);
  await c.client.store(docs);
  await c.client.search(" query ", { language: "en" });
  const r = await c.client.authenticate();
  assert.deepEqual(Object.keys(r), ["exp"]);
  assert.equal(c.calls.length, 4);
  assert.equal(c.calls[0].url, "https://gateway.example/prefix/auth/token");
  assert.equal(c.calls[0].body, undefined);
  assert.equal(c.calls[0].headers["X-API-Key"], key);
  assert.equal(c.calls[1].headers.Authorization, "Bearer SYNTHETIC_NOT_A_JWT");
  assert.equal(c.calls[1].headers["X-API-Key"], undefined);
  assert.equal(c.calls[1].body, JSON.stringify(docs));
  assert.deepEqual(JSON.parse(c.calls[2].body), {
    text: " query ",
    language: "en",
  });
  for (const call of c.calls) {
    assert.equal(call.method, "POST");
    assert.equal(call.redirect, "manual");
    assert.ok(call.signal instanceof AbortSignal);
  }
  assert.ok(!inspect(c.client).includes(key));
  assert.ok(!JSON.stringify(c.client).includes(key));
});
test("one store replay, immutable payload, final 401", async () => {
  const c = client([
    response(200, auth()),
    response(401, "bad"),
    response(200, auth()),
    response(401, "bad"),
    response(200, auth()),
    response(200, { results: [] }),
  ]);
  await assert.rejects(
    c.client.store(docs),
    (e) =>
      e instanceof sdk.AuthenticationError && e.delivery_state === "rejected",
  );
  assert.equal(c.calls[1].body, c.calls[3].body);
  assert.equal(c.calls.length, 4);
  await c.client.search("q");
  assert.equal(c.calls.length, 6);
});
for (const [status, type] of [
  [400, "ValidationError"],
  [422, "ValidationError"],
  [403, "PermissionError"],
  [408, "TimeoutError"],
  [429, "RateLimitError"],
  [500, "ServerError"],
  [503, "ServerError"],
  [302, "HTTPError"],
  [201, "ProtocolError"],
])
  test(`status ${status} no retry, redacted`, async () => {
    const c = client([response(200, auth()), response(status, "SECRET body")]);
    await assert.rejects(
      c.client.store(docs),
      (e) =>
        e instanceof sdk[type] &&
        e.http_status === status &&
        !inspect(e).includes("SECRET"),
    );
    assert.equal(c.calls.length, 2);
  });
test("invalid-key gateway 500 stays ServerError", async () => {
  const c = client([response(500, await fixture("auth-invalid-key.response"))]);
  await assert.rejects(c.client.search("q"), sdk.ServerError);
  assert.equal(c.calls.length, 1);
});
for (const value of [
  "10",
  "-1",
  "bad",
  "Tue, 01 Jan 2030 00:00:00 GMT",
  "Tue, 01 Jan 2000 00:00:00 GMT",
])
  test(`Retry-After ${value}`, async () => {
    const c = client([
      response(200, auth()),
      response(429, "bad", { "Retry-After": value }),
    ]);
    await assert.rejects(c.client.search("q"), (e) => {
      assert.ok(e instanceof sdk.RateLimitError);
      if (value === "10") assert.equal(e.retry_after_seconds, 10);
      else if (value === "-1" || value === "bad")
        assert.equal(e.retry_after_seconds, null);
      else assert.ok(e.retry_after_seconds >= 0);
      return true;
    });
  });
for (const data of [
  {},
  { results: null },
  { results: [{ id: 2 ** 53, text: "t", score: 1 }] },
  { results: [{ id: 1, text: "t", score: "1" }] },
  { results: [null] },
  "{bad",
  "null",
])
  test(`malformed search ${JSON.stringify(data)}`, async () => {
    const c = client([response(200, auth()), response(200, data)]);
    await assert.rejects(c.client.search("q"), sdk.ProtocolError);
  });
for (const changes of [
  { pending_documents: 0 },
  { received_texts: 2 },
  { pending_ids: null },
  { pending_ids: [1, 2] },
  { failed_items: null },
  { timestamp: "2030-02-30T00:00:00Z" },
  { timestamp: "invalid" },
  { timestamp: "2030-01-01T25:00:00Z" },
])
  test(`malformed store ${JSON.stringify(changes)}`, async () => {
    const c = client([
      response(200, auth()),
      response(202, { ...accepted, ...changes }),
    ]);
    await assert.rejects(
      c.client.store(docs),
      (e) => e instanceof sdk.ProtocolError && e.delivery_state === "unknown",
    );
    assert.equal(c.calls.length, 2);
  });
for (const data of [
  { token: "", exp: 9999999999 },
  { token: "bad\nheader", exp: 9999999999 },
  { token: "t", exp: true },
  { token: "t", exp: Math.floor(Date.now() / 1000) + 20 },
  { exp: 9999999999 },
])
  test("malformed exchange clears cache", async () => {
    const c = client([response(200, data)]);
    await assert.rejects(c.client.authenticate(), sdk.ProtocolError);
  });
test("unknown fields, duplicate scores, safe diagnostic results", async () => {
  const hit = {
    id: 1,
    text: "SECRET text",
    score: 0.4,
    untrusted: "SECRET metadata",
  };
  const c = client([
    response(200, auth()),
    response(200, { results: [hit, hit], unknown: { value: 1 } }),
    response(202, { ...accepted, unknown: "SECRET metadata" }),
  ]);
  const r = await c.client.search("q");
  assert.equal(r.results.length, 2);
  assert.equal(r.results[0].extensions.untrusted, "SECRET metadata");
  assert.equal(r.extensions.unknown.value, 1);
  assert.ok(!inspect(r).includes("SECRET"));
  assert.ok(!inspect(r.results[0]).includes("SECRET"));
  const s = await c.client.store(docs);
  assert.equal(s.extensions.unknown, "SECRET metadata");
  assert.ok(!inspect(s).includes("SECRET"));
});
for (const url of [
  "http://remote.example",
  "https://user:pass@gateway.example",
  "https://gateway.example?q=1",
  "https://gateway.example#x",
  "https://gateway.example?",
  "https://gateway.example#",
  "https://gateway.example\\path",
  "https://gateway.example/ bad",
  "https:/gateway.example",
  "http://127.1",
  "http://2130706433",
])
  test(`reject URL ${url}`, () =>
    assert.throws(
      () => client([], { baseUrl: url, allowInsecureLocalhost: true }),
      sdk.ConfigurationError,
    ));
for (const host of ["localhost", "127.0.0.1", "[::1]"])
  test(`HTTP literal local opt-in ${host}`, () => {
    assert.throws(
      () => client([], { baseUrl: `http://${host}:8080` }),
      sdk.ConfigurationError,
    );
    assert.doesNotThrow(() =>
      client([], {
        baseUrl: `http://${host}:8080`,
        allowInsecureLocalhost: true,
      }),
    );
  });
for (const timeoutMs of [0, -1, NaN, Infinity, true, 2147483648])
  test(`bad timeout ${timeoutMs}`, () =>
    assert.throws(() => client([], { timeoutMs }), sdk.ConfigurationError));
test("environment fallback and explicit precedence", () => {
  const old = process.env.THINKPIXEL_API_KEY;
  try {
    process.env.THINKPIXEL_API_KEY = key;
    assert.doesNotThrow(() => client([], { apiKey: undefined }));
    assert.throws(() => client([], { apiKey: "" }), sdk.ConfigurationError);
    delete process.env.THINKPIXEL_API_KEY;
    assert.throws(
      () => client([], { apiKey: undefined }),
      sdk.ConfigurationError,
    );
    assert.doesNotThrow(() => client());
  } finally {
    if (old === undefined) delete process.env.THINKPIXEL_API_KEY;
    else process.env.THINKPIXEL_API_KEY = old;
  }
});
for (const input of [
  [],
  [{ id: 2 ** 31, text: "t" }],
  [{ id: true, text: "t" }],
  [{ id: 1, text: 5 }],
  [{ id: 1, text: "t", extra: { n: 1 } }],
  [{ id: 1, text: "t", extra: null }],
  [{ id: 1, text: "t", filter: 1 }],
])
  test(`local store validation ${JSON.stringify(input)}`, async () => {
    const c = client();
    await assert.rejects(c.client.store(input), sdk.ValidationError);
    assert.equal(c.calls.length, 0);
  });
test("unsupported query/options rejected, boundaries and empty doc text allowed", async () => {
  const c = client([response(200, auth()), response(202, accepted)]);
  await assert.rejects(c.client.search(""), sdk.ValidationError);
  await assert.rejects(
    c.client.search("q", { filter: "x" }),
    sdk.ValidationError,
  );
  await assert.rejects(
    c.client.store(docs, { retry: true }),
    sdk.ValidationError,
  );
  await c.client.store([{ id: -(2 ** 31), text: "", language: "", extra: {} }]);
  assert.deepEqual(JSON.parse(c.calls[1].body), [
    { id: -(2 ** 31), text: "", language: "", extra: {} },
  ]);
});
test("raw transport failure has no cause, no store resend", async () => {
  const c = client([response(200, auth()), new Error(`SECRET ${key}`)]);
  await assert.rejects(
    c.client.store(docs),
    (e) =>
      e instanceof sdk.TransportError &&
      e.delivery_state === "unknown" &&
      e.cause === undefined &&
      !inspect(e).includes("SECRET"),
  );
  assert.equal(c.calls.length, 2);
});
test("timeout bounds uncooperative transport and no replay", async () => {
  const c = client([response(200, auth()), () => new Promise(() => {})], {
    timeoutMs: 25,
  });
  await assert.rejects(
    c.client.store(docs),
    (e) => e instanceof sdk.TimeoutError && e.delivery_state === "unknown",
  );
  assert.equal(c.calls.length, 2);
});
test("body streaming shares deadline", async () => {
  const c = client(
    [
      response(200, auth()),
      () =>
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new TextEncoder().encode("{"));
            },
          }),
          { status: 202 },
        ),
    ],
    { timeoutMs: 25 },
  );
  await assert.rejects(c.client.store(docs), sdk.TimeoutError);
});
test("pre-cancellation sends nothing", async () => {
  const c = client();
  await assert.rejects(
    c.client.store(docs, { signal: AbortSignal.abort("SECRET") }),
    (e) => e instanceof sdk.CancelledError && e.delivery_state === "not_sent",
  );
  assert.equal(c.calls.length, 0);
});
test("cancellation after dispatch unknown, no replay", async () => {
  const abort = new AbortController();
  const c = client([
    response(200, auth()),
    () => {
      abort.abort("SECRET");
      return response(401, "bad");
    },
  ]);
  await assert.rejects(
    c.client.store(docs, { signal: abort.signal }),
    (e) => e instanceof sdk.CancelledError && e.delivery_state === "unknown",
  );
  assert.equal(c.calls.length, 2);
});
test("concurrent exchange, independent cancellation", async () => {
  let resolve;
  const c = client([
    () =>
      new Promise((r) => {
        resolve = r;
      }),
    response(200, { results: [] }),
  ]);
  const abort = new AbortController();
  const first = c.client.search("first", { signal: abort.signal });
  const second = c.client.search("second");
  await new Promise((r) => setImmediate(r));
  assert.equal(c.calls.length, 1);
  abort.abort();
  await assert.rejects(first, sdk.CancelledError);
  assert.equal(c.calls[0].signal.aborted, false);
  resolve(response(200, auth()));
  await second;
  assert.equal(c.calls.length, 2);
});
test("two concurrent protected requests coalesce exchange", async () => {
  const c = client([
    async () => {
      await new Promise((r) => setImmediate(r));
      return response(200, auth());
    },
    response(200, { results: [] }),
    response(200, { results: [] }),
  ]);
  await Promise.all([c.client.search("a"), c.client.search("b")]);
  assert.equal(
    c.calls.filter((call) => call.url.endsWith("/auth/token")).length,
    1,
  );
});
test("shared budget includes exchange", async () => {
  const c = client(
    [
      async () => {
        await new Promise((r) => setTimeout(r, 25));
        return response(200, auth());
      },
      () => new Promise(() => {}),
    ],
    { timeoutMs: 40 },
  );
  const start = performance.now();
  await assert.rejects(c.client.search("q"), sdk.TimeoutError);
  assert.ok(performance.now() - start < 100);
});
test("failed explicit exchange invalidates previous token", async () => {
  const c = client([
    response(200, auth()),
    response(500, "bad"),
    response(200, auth()),
    response(200, { results: [] }),
  ]);
  await c.client.authenticate();
  await assert.rejects(c.client.authenticate(), sdk.ServerError);
  await c.client.search("q");
  assert.equal(c.calls.length, 4);
});
test("expiry skew forces new exchange", async () => {
  const old = Date.now;
  let now = old();
  Date.now = () => now;
  try {
    const c = client([
      response(200, auth()),
      response(200, { results: [] }),
      () => response(200, auth()),
      response(200, { results: [] }),
    ]);
    await c.client.search("q");
    now += 880000;
    await c.client.search("q");
    assert.equal(c.calls.length, 4);
  } finally {
    Date.now = old;
  }
});
test("explicit JSON retains wire extensions and absent fields", async () => {
  const data = { ...accepted, unknown: { x: 1 } };
  const c = client([response(200, auth()), response(202, data)]);
  const r = await c.client.store(docs);
  assert.deepEqual(JSON.parse(JSON.stringify(r)), data);
});
test("null key, timeout and language rejected", async () => {
  assert.throws(() => client([], { apiKey: null }), sdk.ConfigurationError);
  assert.throws(() => client([], { timeoutMs: null }), sdk.ConfigurationError);
  const c = client();
  await assert.rejects(
    c.client.search("q", { language: null }),
    sdk.ValidationError,
  );
  assert.equal(c.calls.length, 0);
});
test("cancelled sole waiter aborts exchange, late response cannot populate cache", async () => {
  let resolve;
  const abort = new AbortController();
  const c = client([
    () =>
      new Promise((r) => {
        resolve = r;
      }),
    response(200, auth()),
    response(200, { results: [] }),
  ]);
  const first = c.client.search("q", { signal: abort.signal });
  await new Promise((r) => setImmediate(r));
  abort.abort();
  await assert.rejects(first, sdk.CancelledError);
  assert.equal(c.calls[0].signal.aborted, true);
  resolve(response(200, auth()));
  await new Promise((r) => setImmediate(r));
  await c.client.search("q");
  assert.equal(c.calls.length, 3);
});
test("renewed concurrent requests share one exchange after 401", async () => {
  let releases = [];
  let count = 0;
  const c = client([], {
    transport: async (url) => {
      if (url.endsWith("/auth/token")) {
        count++;
        await new Promise((r) => setImmediate(r));
        return response(200, auth());
      }
      if (count === 1)
        return await new Promise((r) => {
          releases.push(() => r(response(401, "bad")));
          if (releases.length === 2) for (const release of releases) release();
        });
      return response(200, { results: [] });
    },
  });
  await Promise.all([c.client.search("a"), c.client.search("b")]);
  assert.equal(count, 2);
});
test("default fetch does not forward credentials on redirects", async () => {
  const { createServer } = await import("node:http");
  let forwarded = 0;
  const server = createServer((req, res) => {
    if (req.url === "/auth/token") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(auth()));
    } else if (req.url === "/search") {
      res.writeHead(302, { Location: "/target" });
      res.end();
    } else {
      forwarded++;
      res.end();
    }
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  try {
    const c = new sdk.ThinkPixelSRClient({
      baseUrl: `http://127.0.0.1:${server.address().port}`,
      apiKey: key,
      allowInsecureLocalhost: true,
    });
    await assert.rejects(c.search("q"), sdk.HTTPError);
    assert.equal(forwarded, 0);
  } finally {
    await new Promise((r) => server.close(r));
  }
});
test("sparse document arrays rejected locally", async () => {
  const c = client();
  await assert.rejects(c.client.store(new Array(1)), sdk.ValidationError);
  assert.equal(c.calls.length, 0);
});
test("adapter error subclasses are sanitized", async () => {
  const raw = new sdk.TimeoutError("SECRET");
  raw.cause = new Error(key);
  const c = client([response(200, auth()), raw]);
  await assert.rejects(
    c.client.store(docs),
    (e) =>
      e instanceof sdk.TimeoutError &&
      !inspect(e).includes("SECRET") &&
      e.cause === undefined &&
      e.delivery_state === "unknown",
  );
});
