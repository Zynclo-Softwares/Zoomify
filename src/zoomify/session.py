"""In-memory API sessions (conversation + zoom stack)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .tools import ImageState


@dataclass
class Session:
    conv_messages: list[dict] = field(default_factory=list)
    image_state: ImageState | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> str:
        sid = uuid.uuid4().hex
        self._sessions[sid] = Session()
        return sid

    def get(self, session_id: str | None) -> tuple[str, Session]:
        if session_id and session_id in self._sessions:
            return session_id, self._sessions[session_id]
        sid = self.create()
        return sid, self._sessions[sid]

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def clear(self) -> None:
        self._sessions.clear()


store = SessionStore()
