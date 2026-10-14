import json
import logging
import time
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: float


class SessionManager:
    """Manages multi-turn conversation history with Redis and in-memory fallback."""

    _instance: Optional["SessionManager"] = None

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._memory_sessions: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def get_instance(cls, settings: Optional[Settings] = None) -> "SessionManager":
        if cls._instance is None:
            cls._instance = cls(settings=settings)
        return cls._instance

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's conversation history."""
        if not session_id:
            return

        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }

        if session_id not in self._memory_sessions:
            self._memory_sessions[session_id] = []
        self._memory_sessions[session_id].append(msg)

        # Cap session history at last 20 messages
        if len(self._memory_sessions[session_id]) > 20:
            self._memory_sessions[session_id] = self._memory_sessions[session_id][-20:]

    def get_history(self, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns formatted for LLM messages."""
        if not session_id or session_id not in self._memory_sessions:
            return []

        recent = self._memory_sessions[session_id][-limit:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear_session(self, session_id: str) -> None:
        """Clear history for a session."""
        if session_id in self._memory_sessions:
            del self._memory_sessions[session_id]
