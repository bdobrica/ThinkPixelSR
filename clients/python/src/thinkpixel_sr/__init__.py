"""ThinkPixelSR sync and async SDK."""

from .async_client import AsyncThinkPixelSRClient
from .client import ThinkPixelSRClient, Transport
from .errors import (
    AuthenticationError,
    CancelledError,
    ConfigurationError,
    HTTPError,
    PermissionError,
    ProtocolError,
    RateLimitError,
    ServerError,
    StoreFailedError,
    ThinkPixelSRError,
    TimeoutError,
    TransportError,
    ValidationError,
)
from .models import (
    AuthResult,
    Document,
    FailedItem,
    SearchHit,
    SearchResult,
    StoreResult,
)

__version__ = "0.2.0"
__all__ = [
    "ThinkPixelSRClient",
    "AsyncThinkPixelSRClient",
    "Transport",
    "AuthResult",
    "Document",
    "FailedItem",
    "SearchHit",
    "SearchResult",
    "StoreResult",
    "ThinkPixelSRError",
    "AuthenticationError",
    "CancelledError",
    "ConfigurationError",
    "HTTPError",
    "PermissionError",
    "ProtocolError",
    "RateLimitError",
    "ServerError",
    "StoreFailedError",
    "TimeoutError",
    "TransportError",
    "ValidationError",
]
