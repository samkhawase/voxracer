"""ElevenLabs adapter implementation."""

from __future__ import annotations

from ..protocol import CallId
from ...model import Session
from .client import ElevenLabsClient
from .parser import map_otlp_to_session


class ElevenLabsAdapter:
    """Read-only adapter for ElevenLabs conversation telemetry."""

    name = "elevenlabs"

    def list_call_ids(self, credential: str, *, limit: int = 30) -> list[CallId]:
        return [CallId(value) for value in ElevenLabsClient(credential).list_conversation_ids(limit=limit)]

    def fetch_session(self, credential: str, call_id: CallId) -> Session:
        raw = ElevenLabsClient(credential).fetch_otlp(str(call_id))
        return map_otlp_to_session(raw)
