import { inspect } from "node:util";
import type { StoreResult } from "./models.js";
export type DeliveryState = "not_sent" | "rejected" | "accepted" | "failed" | "unknown";
export class ThinkPixelSRError extends Error {
    constructor(readonly operation: string, readonly http_status?: number, readonly delivery_state: DeliveryState = "not_sent") {
        super(`${new.target.name}: ${operation}`);
        this.name = new.target.name;
    }
    toJSON(): object { return { name: this.name, operation: this.operation, http_status: this.http_status, delivery_state: this.delivery_state }; }
    [inspect.custom](): string { return this.message; }
}
export class ConfigurationError extends ThinkPixelSRError {
}
export class ValidationError extends ThinkPixelSRError {
}
export class AuthenticationError extends ThinkPixelSRError {
}
export class PermissionError extends ThinkPixelSRError {
}
export class TransportError extends ThinkPixelSRError {
}
export class TimeoutError extends TransportError {
}
export class CancelledError extends ThinkPixelSRError {
}
export class ProtocolError extends ThinkPixelSRError {
}
export class HTTPError extends ThinkPixelSRError {
}
export class ServerError extends HTTPError {
}
export class RateLimitError extends HTTPError {
    retry_after_seconds: number | null = null;
}
export class StoreFailedError extends ServerError {
    readonly result: StoreResult;
    constructor(result: StoreResult) {
        super("store", 500, "failed");
        // Accessible explicitly, excluded from ordinary inspection/serialization.
        Object.defineProperty(this, "result", { value: result, enumerable: false });
        this.result = result;
    }
}
