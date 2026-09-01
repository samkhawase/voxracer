"""ElevenLabs adapter implementation."""

from __future__ import annotations

from ..protocol import CallId
from ...model import Session
from .client import ElevenLabsClient
from .parser import map_otlp_to_session
from .transcript import merge_transcript_metrics


class ElevenLabsAdapter:
    """Read-only adapter for ElevenLabs conversation telemetry."""

    name = "elevenlabs"

    def list_call_ids(self, credential: str, *, limit: int = 30) -> list[CallId]:
        return [CallId(value) for value in ElevenLabsClient(credential).list_conversation_ids(limit=limit)]

    def fetch_session(self, credential: str, call_id: CallId) -> Session:
        client = ElevenLabsClient(credential)
        session = map_otlp_to_session(client.fetch_otlp(str(call_id)))
        return merge_transcript_metrics(session, client.fetch_transcript(str(call_id)))
