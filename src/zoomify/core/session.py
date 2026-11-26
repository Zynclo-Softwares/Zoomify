"""In-memory zoom sessions — one opened image (and its zoom stack) per session id."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from .tools import ImageState

SESSION_ID_PREFIX = "zs_"
SESSION_TTL_SECONDS = 30 * 60  # idle time before a session is dropped


@dataclass
class ZoomSession:
    id: str
    owner: str
    state: ImageState
    label: str
    source_kind: str = "image"
    page: int = 1
    page_count: int = 1
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    # Tools on one session are stateful; serialise them.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    """Per-process store with idle expiry and a per-account cap (oldest evicted)."""

    def __init__(self) -> None:
        self._sessions: dict[str, ZoomSession] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        expired = [
            sid for sid, s in self._sessions.items() if now - s.last_used_at > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]

    def create(
        self,
        owner: str,
        state: ImageState,
        *,
        label: str,
        max_open: int,
        source_kind: str = "image",
        page: int = 1,
        page_count: int = 1,
    ) -> tuple[ZoomSession, list[str]]:
        """Store a new session; returns it plus ids evicted to respect ``max_open``."""
        session = ZoomSession(
            id=SESSION_ID_PREFIX + secrets.token_urlsafe(9),
            owner=owner,
            state=state,
            label=label,
            source_kind=source_kind,
            page=page,
            page_count=page_count,
        )
        with self._lock:
            self._purge(time.time())
            mine = sorted(
                (s for s in self._sessions.values() if s.owner == owner),
                key=lambda s: s.last_used_at,
            )
            evicted = [s.id for s in mine[: max(0, len(mine) - max(1, max_open) + 1)]]
            for sid in evicted:
                del self._sessions[sid]
            self._sessions[session.id] = session
        return session, evicted

    def get(self, owner: str, session_id: str) -> ZoomSession | None:
        with self._lock:
            now = time.time()
            self._purge(now)
            session = self._sessions.get(session_id)
            if session is None or session.owner != owner:
                return None
            session.last_used_at = now
            return session

    def delete(self, owner: str, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.owner != owner:
                return False
            del self._sessions[session_id]
            return True

    def count(self, owner: str) -> int:
        with self._lock:
            self._purge(time.time())
            return sum(1 for s in self._sessions.values() if s.owner == owner)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


store = SessionStore()
