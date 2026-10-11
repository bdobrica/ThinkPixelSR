"""Typed records. Explicit to_dict exposes payload data; repr hides it."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Document:
    id: int
    text: str = field(repr=False)
    language: str | None = None
    extra: Mapping[str, str] | None = field(default=None, repr=False)


@dataclass(frozen=True)
class AuthResult:
    exp: int


@dataclass(frozen=True)
class FailedItem:
    id: int
    error: str = field(repr=False)
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {**self.extensions, "id": self.id, "error": self.error}


@dataclass(frozen=True)
class StoreResult:
    received_texts: int
    pending_documents: int
    failed_documents: int
    timestamp: str
    http_status: int
    pending_ids: tuple[int, ...] | None = None
    failed_items: tuple[FailedItem, ...] | None = field(default=None, repr=False)
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def delivery_state(self) -> str:
        return "accepted" if self.http_status == 202 else "failed"

    def to_dict(self) -> dict[str, Any]:
        result = {
            **self.extensions,
            "received_texts": self.received_texts,
            "pending_documents": self.pending_documents,
            "failed_documents": self.failed_documents,
            "timestamp": self.timestamp,
        }
        if self.pending_ids is not None:
            result["pending_ids"] = list(self.pending_ids)
        if self.failed_items is not None:
            result["failed_items"] = [item.to_dict() for item in self.failed_items]
        return result


@dataclass(frozen=True)
class SearchHit:
    id: int
    text: str = field(repr=False)
    score: float
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extensions,
            "id": self.id,
            "text": self.text,
            "score": self.score,
        }


@dataclass(frozen=True)
class SearchResult:
    results: tuple[SearchHit, ...] = field(repr=False)
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {**self.extensions, "results": [hit.to_dict() for hit in self.results]}
