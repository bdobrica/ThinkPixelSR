"""Fixed diagnostic messages; server bodies and transport exceptions stay private."""


class ThinkPixelSRError(Exception):
    def __init__(
        self,
        operation: str,
        *,
        http_status: int | None = None,
        delivery_state: str = "not_sent",
    ) -> None:
        self.operation = operation
        self.http_status = http_status
        self.delivery_state = delivery_state
        super().__init__(f"{type(self).__name__}: {operation}")


class ConfigurationError(ThinkPixelSRError):
    pass


class ValidationError(ThinkPixelSRError):
    pass


class AuthenticationError(ThinkPixelSRError):
    pass


class PermissionError(ThinkPixelSRError):
    pass


class TransportError(ThinkPixelSRError):
    pass


class TimeoutError(TransportError):
    pass


class CancelledError(ThinkPixelSRError):
    pass


class ProtocolError(ThinkPixelSRError):
    pass


class HTTPError(ThinkPixelSRError):
    pass


class ServerError(HTTPError):
    pass


class RateLimitError(HTTPError):
    retry_after_seconds: float | None = None


class StoreFailedError(ServerError):
    def __init__(self, result: "StoreResult") -> None:
        super().__init__("store", http_status=500, delivery_state="failed")
        self.result = result


from .models import StoreResult  # noqa: E402
