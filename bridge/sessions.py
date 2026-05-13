"""
In-memory session store with TTL-based expiry.
No database, no disk. Sessions die with the process.
"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    created_at: float
    last_active: float
    messages: list[dict] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    request_count: int = 0

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self.last_active = time.time()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self.last_active = time.time()

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.request_count += 1


class SessionStore:
    def __init__(self, ttl_minutes: int = 30, max_turns: int = 50):
        self._sessions: dict[str, Session] = {}
        self._ttl_seconds = ttl_minutes * 60
        self._max_turns = max_turns

    def get_or_create(self, session_id: str | None = None) -> Session:
        """Get existing session or create a new one."""
        self._expire_stale()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_active = time.time()
            return session

        new_id = session_id or str(uuid.uuid4())
        now = time.time()
        session = Session(session_id=new_id, created_at=now, last_active=now)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session by ID, or None if not found/expired."""
        self._expire_stale()
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[dict]:
        """List all active sessions with summary info."""
        self._expire_stale()
        result = []
        for s in self._sessions.values():
            result.append({
                "session_id": s.session_id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "message_count": len(s.messages),
                "total_tokens": s.total_prompt_tokens + s.total_completion_tokens,
                "request_count": s.request_count,
            })
        return result

    def is_at_turn_limit(self, session: Session) -> bool:
        """Check if session has hit the max conversation depth."""
        # Count user messages as turns
        user_turns = sum(1 for m in session.messages if m["role"] == "user")
        return user_turns >= self._max_turns

    def get_conversation_history(self, session: Session) -> list[dict]:
        """Return message history suitable for the vLLM messages array."""
        return list(session.messages)

    @property
    def active_count(self) -> int:
        self._expire_stale()
        return len(self._sessions)

    def _expire_stale(self) -> None:
        """Remove sessions that have exceeded TTL."""
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if (now - s.last_active) > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
