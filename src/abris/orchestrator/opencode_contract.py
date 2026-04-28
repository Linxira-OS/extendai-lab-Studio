from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class StructuredSchemaRequest:
    prompt: str
    schema: dict[str, Any]
    retry_count: int = 2


class OpenCodeRuntime(Protocol):
    def create_session(self, title: str) -> str: ...

    def list_sessions(self) -> list[dict[str, Any]]: ...

    def get_session(self, session_id: str) -> dict[str, Any]: ...

    def get_session_status(self) -> dict[str, Any]: ...

    def get_messages(self, session_id: str) -> list[dict[str, Any]]: ...

    def get_session_usage(self, session_id: str) -> dict[str, Any]: ...

    def prompt_text(self, session_id: str, text: str) -> dict[str, Any]: ...

    def prompt_async(self, session_id: str, text: str) -> dict[str, Any]: ...

    def prompt_structured(
        self, session_id: str, request: StructuredSchemaRequest
    ) -> dict[str, Any]: ...

    def subscribe_events(
        self, limit: int = 10, timeout_ms: int = 1_000
    ) -> dict[str, Any]: ...

    def abort_session(self, session_id: str) -> dict[str, Any]: ...

    def delete_session(self, session_id: str) -> dict[str, Any]: ...
