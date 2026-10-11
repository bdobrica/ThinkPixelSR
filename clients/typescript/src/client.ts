import { inspect } from "node:util";
import * as E from "./errors.js";
import type {
  AuthResult,
  Document,
  FailedItem,
  RequestOptions,
  SearchOptions,
  SearchResult,
  StoreResult,
} from "./models.js";
/** Caller-owned fetch adapter: honor signal, disable retries/redirects, never log credentials. */
export type Transport = (url: string, init: RequestInit) => Promise<Response>;
export interface ClientOptions {
  readonly baseUrl: string;
  readonly apiKey?: string;
  readonly timeoutMs?: number;
  readonly transport?: Transport;
  readonly allowInsecureLocalhost?: boolean;
}
type JSONMap = Record<string, unknown>;
type Context = {
  controller: AbortController;
  deadline: number;
  operation: string;
  sent: boolean;
  dispose(): void;
};
type Token = {
  value: string;
  exp: number;
};
type Exchange = {
  promise: Promise<Token>;
  context: Context;
  waiters: number;
};
const object = (value: unknown): value is JSONMap =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const integer = (value: unknown): value is number =>
  Number.isSafeInteger(value);
const credential = (value: unknown): value is string =>
  typeof value === "string" && /^[\x21-\x7e]+$/.test(value);
const extensions = (
  value: JSONMap,
  known: readonly string[],
): Readonly<JSONMap> =>
  Object.freeze(
    Object.fromEntries(
      Object.entries(value).filter(([key]) => !known.includes(key)),
    ),
  );
function keys(value: unknown, allowed: readonly string[]): boolean {
  return (
    object(value) && Object.keys(value).every((key) => allowed.includes(key))
  );
}
// Suppress payload/unknown metadata in Node diagnostics while keeping explicit JSON useful.
function result<T extends object>(value: T, label: string): T {
  Object.defineProperty(value, inspect.custom, { value: () => label });
  Object.defineProperty(value, "toJSON", {
    value: () => {
      const fields = Object.fromEntries(
        Object.entries(value).filter(
          ([key]) =>
            !["extensions", "http_status", "delivery_state"].includes(key),
        ),
      );
      const extra =
        "extensions" in value && object(value.extensions)
          ? value.extensions
          : {};
      return { ...extra, ...fields };
    },
  });
  return Object.freeze(value);
}
function timestamp(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|([+-])(\d{2}):(\d{2}))$/.exec(
      value,
    );
  if (!match) return false;
  const [, y, m, d, h, min, sec, , oh, om] = match;
  const year = Number(y),
    month = Number(m),
    day = Number(d);
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month, 0);
  return (
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= calendar.getUTCDate() &&
    Number(h) <= 23 &&
    Number(min) <= 59 &&
    Number(sec) <= 59 &&
    Number(oh ?? 0) <= 23 &&
    Number(om ?? 0) <= 59
  );
}
export class ThinkPixelSRClient {
  #baseUrl: string;
  #key: string;
  #timeout: number;
  #transport: Transport;
  #token: Token | undefined;
  #exchange: Exchange | undefined;
  constructor(options: ClientOptions) {
    let base: URL;
    const key =
      options?.apiKey === undefined
        ? process.env.THINKPIXEL_API_KEY
        : options.apiKey;
    const timeout =
      options?.timeoutMs === undefined ? 15000 : options.timeoutMs;
    try {
      if (
        !keys(options, [
          "baseUrl",
          "apiKey",
          "timeoutMs",
          "transport",
          "allowInsecureLocalhost",
        ]) ||
        typeof options.baseUrl !== "string" ||
        /[\s\\\x00-\x1f\x7f]/.test(options.baseUrl)
      )
        throw 0;
      // Validate literal authority before WHATWG URL normalization (e.g. 127.1 -> 127.0.0.1).
      const raw = /^(https?):\/\/([^/?#]+)([^?#]*?)\/*$/.exec(options.baseUrl);
      if (!raw || raw[2]?.includes("@")) throw 0;
      base = new URL(options.baseUrl);
      const local = /^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]+)?$/.test(
        raw[2] ?? "",
      );
      if (
        base.protocol !== "https:" &&
        !(options.allowInsecureLocalhost === true && local)
      )
        throw 0;
      if (
        !credential(key) ||
        !Number.isFinite(timeout) ||
        timeout <= 0 ||
        timeout > 2147483647
      )
        throw 0;
      if (
        options.transport !== undefined &&
        typeof options.transport !== "function"
      )
        throw 0;
      if (
        options.allowInsecureLocalhost !== undefined &&
        typeof options.allowInsecureLocalhost !== "boolean"
      )
        throw 0;
    } catch {
      throw new E.ConfigurationError("configure");
    }
    this.#baseUrl = base!.href.replace(/\/+$/, "");
    this.#key = key!;
    this.#timeout = timeout;
    this.#transport = options.transport ?? ((url, init) => fetch(url, init));
  }
  toJSON(): object {
    return { name: "ThinkPixelSRClient" };
  }
  [inspect.custom](): string {
    return "ThinkPixelSRClient";
  }
  #context(operation: string, signal?: AbortSignal): Context {
    const controller = new AbortController();
    const abort = () => controller.abort("cancelled");
    const timer = setTimeout(() => controller.abort("timeout"), this.#timeout);
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) abort();
    return {
      controller,
      deadline: performance.now() + this.#timeout,
      operation,
      sent: false,
      dispose: () => {
        clearTimeout(timer);
        signal?.removeEventListener("abort", abort);
      },
    };
  }
  #check(context: Context): void {
    const state =
      context.operation === "store" && context.sent ? "unknown" : "not_sent";
    if (
      context.controller.signal.aborted &&
      context.controller.signal.reason === "cancelled"
    )
      throw new E.CancelledError(context.operation, undefined, state);
    if (
      context.controller.signal.aborted ||
      performance.now() >= context.deadline
    )
      throw new E.TimeoutError(context.operation, undefined, state);
  }
  async #wait<T>(context: Context, action: () => Promise<T>): Promise<T> {
    this.#check(context);
    const signal = context.controller.signal;
    let rejectAbort: () => void = () => {};
    const aborted = new Promise<never>((_, reject) => {
      rejectAbort = () => {
        try {
          this.#check(context);
        } catch (error) {
          reject(error);
        }
      };
    });
    signal.addEventListener("abort", rejectAbort, { once: true });
    try {
      const value = await Promise.race([
        Promise.resolve().then(() => {
          this.#check(context);
          return action();
        }),
        aborted,
      ]);
      this.#check(context);
      return value;
    } finally {
      signal.removeEventListener("abort", rejectAbort);
    }
  }
  #options(options: RequestOptions | SearchOptions, operation: string): void {
    if (
      !keys(
        options,
        operation === "search" ? ["signal", "language"] : ["signal"],
      ) ||
      (options.signal !== undefined && !(options.signal instanceof AbortSignal))
    )
      throw new E.ValidationError(operation);
  }
  async #send(
    operation: string,
    context: Context,
    body?: string,
    token?: Token,
  ): Promise<Response> {
    this.#check(context);
    const headers: Record<string, string> = { Accept: "application/json" };
    const path = operation === "authenticate" ? "/auth/token" : `/${operation}`;
    if (operation === "authenticate") headers["X-API-Key"] = this.#key;
    else {
      headers.Authorization = `Bearer ${token!.value}`;
      headers["Content-Type"] = "application/json";
      context.sent = true;
    }
    try {
      return await this.#wait(context, () =>
        this.#transport(this.#baseUrl + path, {
          method: "POST",
          headers,
          ...(body === undefined ? {} : { body }),
          redirect: "manual",
          signal: context.controller.signal,
        }),
      );
    } catch (error) {
      this.#check(context);
      if (error instanceof E.TimeoutError)
        throw new E.TimeoutError(
          operation,
          undefined,
          operation === "store" ? "unknown" : "not_sent",
        );
      if (error instanceof E.CancelledError)
        throw new E.CancelledError(
          operation,
          undefined,
          operation === "store" ? "unknown" : "not_sent",
        );
      throw new E.TransportError(
        operation,
        undefined,
        operation === "store" ? "unknown" : "not_sent",
      );
    }
  }
  async #discard(response: Response): Promise<void> {
    try {
      await response.body?.cancel();
    } catch {
      /* Never retain raw transport errors. */
    }
  }
  #status(response: Response, operation: string, expected: number): void {
    const status = response.status;
    if (status === expected) return;
    const state =
      operation === "store"
        ? [400, 401, 403].includes(status)
          ? "rejected"
          : "unknown"
        : "not_sent";
    const ErrorType =
      (
        {
          400: E.ValidationError,
          422: E.ValidationError,
          401: E.AuthenticationError,
          403: E.PermissionError,
          408: E.TimeoutError,
          429: E.RateLimitError,
        } as Record<number, typeof E.ThinkPixelSRError>
      )[status] ??
      (status >= 500
        ? E.ServerError
        : status >= 200 && status < 300
          ? E.ProtocolError
          : E.HTTPError);
    const error = new ErrorType(operation, status, state);
    if (error instanceof E.RateLimitError) {
      const raw = response.headers.get("Retry-After") ?? "";
      const seconds = /^\d+$/.test(raw)
        ? Number(raw)
        : /^[A-Za-z]{3},/.test(raw)
          ? (Date.parse(raw) - Date.now()) / 1000
          : NaN;
      if (Number.isFinite(seconds))
        error.retry_after_seconds = Math.max(0, seconds);
    }
    throw error;
  }
  async #json(response: Response, context: Context): Promise<JSONMap> {
    let value: unknown;
    try {
      value = JSON.parse(await this.#wait(context, () => response.text()));
    } catch (error) {
      this.#check(context);
      if (error instanceof E.TimeoutError)
        throw new E.TimeoutError(
          context.operation,
          response.status,
          context.operation === "store" ? "unknown" : "not_sent",
        );
      if (error instanceof E.CancelledError)
        throw new E.CancelledError(
          context.operation,
          response.status,
          context.operation === "store" ? "unknown" : "not_sent",
        );
      if (!(error instanceof SyntaxError))
        throw new E.TransportError(
          context.operation,
          response.status,
          context.operation === "store" ? "unknown" : "not_sent",
        );
    }
    if (!object(value))
      throw new E.ProtocolError(
        context.operation,
        response.status,
        context.operation === "store" ? "unknown" : "not_sent",
      );
    return value;
  }
  async #getToken(context: Context, force = false): Promise<Token> {
    this.#check(context);
    if (!force && this.#token && Date.now() / 1000 < this.#token.exp - 30)
      return this.#token;
    if (!this.#exchange) {
      this.#token = undefined;
      const authContext = this.#context("authenticate");
      const exchange: Exchange = {
        context: authContext,
        waiters: 0,
        promise: Promise.resolve({ value: "", exp: 0 }),
      };
      this.#exchange = exchange;
      exchange.promise = (async () => {
        let response: Response | undefined;
        try {
          response = await this.#send("authenticate", authContext);
          this.#status(response, "authenticate", 200);
          const data = await this.#json(response, authContext);
          if (
            !credential(data.token) ||
            !integer(data.exp) ||
            data.exp <= Date.now() / 1000 + 30
          )
            throw new E.ProtocolError("authenticate", 200);
          const token = { value: data.token, exp: data.exp };
          this.#check(authContext);
          this.#token = token;
          return token;
        } finally {
          authContext.dispose();
          if (response) void this.#discard(response);
          if (this.#exchange === exchange) this.#exchange = undefined;
        }
      })();
    }
    const exchange = this.#exchange;
    exchange.waiters++;
    try {
      return await this.#wait(context, () => exchange.promise);
    } finally {
      exchange.waiters--;
      if (exchange.waiters === 0 && this.#exchange === exchange) {
        this.#exchange = undefined;
        exchange.context.controller.abort("cancelled");
      }
    }
  }
  async authenticate(options: RequestOptions = {}): Promise<AuthResult> {
    this.#options(options, "authenticate");
    const context = this.#context("authenticate", options.signal);
    try {
      const token = await this.#getToken(context, true);
      return result({ exp: token.exp }, "AuthResult");
    } finally {
      context.dispose();
    }
  }
  async #request(
    operation: string,
    payload: unknown,
    context: Context,
  ): Promise<Response> {
    const body = JSON.stringify(payload);
    let token = await this.#getToken(context);
    let response = await this.#send(operation, context, body, token);
    if (response.status === 401) {
      void this.#discard(response);
      context.sent = false; // Middleware rejected before queue publication.
      if (this.#token === token) this.#token = undefined;
      token = await this.#getToken(context);
      response = await this.#send(operation, context, body, token);
      if (response.status === 401 && this.#token === token)
        this.#token = undefined;
    }
    return response;
  }
  #storeResult(data: JSONMap, status: number): StoreResult {
    const {
      received_texts: received,
      pending_documents: pending,
      failed_documents: failed,
      timestamp: stamp,
    } = data;
    const invalid = () => new E.ProtocolError("store", status, "unknown");
    if (
      !integer(received) ||
      !integer(pending) ||
      !integer(failed) ||
      received <= 0 ||
      pending < 0 ||
      failed < 0 ||
      received !== pending + failed ||
      (status === 202 && pending === 0) ||
      (status === 500 && pending !== 0) ||
      !timestamp(stamp)
    )
      throw invalid();
    let ids: number[] | undefined;
    let failures: FailedItem[] | undefined;
    if (Object.hasOwn(data, "pending_ids")) {
      if (
        !Array.isArray(data.pending_ids) ||
        data.pending_ids.length !== pending ||
        !data.pending_ids.every(integer)
      )
        throw invalid();
      ids = data.pending_ids;
    }
    if (Object.hasOwn(data, "failed_items")) {
      if (
        !Array.isArray(data.failed_items) ||
        data.failed_items.length !== failed
      )
        throw invalid();
      failures = data.failed_items.map((item: unknown) => {
        if (
          !object(item) ||
          !integer(item.id) ||
          typeof item.error !== "string"
        )
          throw invalid();
        return result(
          {
            id: item.id,
            error: item.error,
            extensions: extensions(item, ["id", "error"]),
          },
          "FailedItem",
        );
      });
    }
    return result(
      {
        received_texts: received,
        pending_documents: pending,
        failed_documents: failed,
        timestamp: stamp,
        http_status: status,
        delivery_state: status === 202 ? "accepted" : "failed",
        ...(ids ? { pending_ids: Object.freeze(ids) } : {}),
        ...(failures ? { failed_items: Object.freeze(failures) } : {}),
        extensions: extensions(data, [
          "received_texts",
          "pending_documents",
          "failed_documents",
          "timestamp",
          "pending_ids",
          "failed_items",
        ]),
      },
      "StoreResult",
    );
  }
  async store(
    documents: readonly Document[],
    options: RequestOptions = {},
  ): Promise<StoreResult> {
    this.#options(options, "store");
    if (!Array.isArray(documents) || !documents.length)
      throw new E.ValidationError("store");
    const payload = Array.from(documents, (doc: unknown) => {
      if (
        !keys(doc, ["id", "text", "language", "extra"]) ||
        !object(doc) ||
        !integer(doc.id) ||
        doc.id < -(2 ** 31) ||
        doc.id >= 2 ** 31 ||
        typeof doc.text !== "string" ||
        (doc.language !== undefined && typeof doc.language !== "string") ||
        (doc.extra !== undefined &&
          (!object(doc.extra) ||
            Object.values(doc.extra).some((v) => typeof v !== "string")))
      )
        throw new E.ValidationError("store");
      return {
        id: doc.id,
        text: doc.text,
        ...(doc.language === undefined ? {} : { language: doc.language }),
        ...(doc.extra === undefined
          ? {}
          : { extra: { ...(doc.extra as Record<string, string>) } }),
      };
    });
    const context = this.#context("store", options.signal);
    let response: Response | undefined;
    try {
      response = await this.#request("store", payload, context);
      if (response.status === 500) {
        let parsed: StoreResult | undefined;
        try {
          parsed = this.#storeResult(await this.#json(response, context), 500);
        } catch (error) {
          if (!(error instanceof E.ProtocolError)) throw error;
        }
        if (parsed) throw new E.StoreFailedError(parsed);
      }
      this.#status(response, "store", 202);
      return this.#storeResult(await this.#json(response, context), 202);
    } finally {
      context.dispose();
      if (response) void this.#discard(response);
    }
  }
  async search(
    text: string,
    options: SearchOptions = {},
  ): Promise<SearchResult> {
    this.#options(options, "search");
    const language = options.language === undefined ? "auto" : options.language;
    if (typeof text !== "string" || !text || typeof language !== "string")
      throw new E.ValidationError("search");
    const context = this.#context("search", options.signal);
    let response: Response | undefined;
    try {
      response = await this.#request("search", { text, language }, context);
      this.#status(response, "search", 200);
      const data = await this.#json(response, context);
      if (!Array.isArray(data.results))
        throw new E.ProtocolError("search", 200);
      const hits = data.results.map((hit: unknown) => {
        if (
          !object(hit) ||
          !integer(hit.id) ||
          typeof hit.text !== "string" ||
          typeof hit.score !== "number" ||
          !Number.isFinite(hit.score)
        )
          throw new E.ProtocolError("search", 200);
        return result(
          {
            id: hit.id,
            text: hit.text,
            score: hit.score,
            extensions: extensions(hit, ["id", "text", "score"]),
          },
          "SearchHit",
        );
      });
      return result(
        {
          results: Object.freeze(hits),
          extensions: extensions(data, ["results"]),
        },
        "SearchResult",
      );
    } finally {
      context.dispose();
      if (response) void this.#discard(response);
    }
  }
}
