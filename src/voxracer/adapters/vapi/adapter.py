"""Vapi provider adapter implementation."""

from __future__ import annotations

from ..protocol import CallId
from ...model import Session
from .client import VapiClient
from .parser import map_call_to_session


class VapiAdapter:
    """Read-only adapter for Vapi call telemetry."""

    name = "vapi"

    def list_call_ids(self, credential: str, *, limit: int = 30) -> list[CallId]:
        return [CallId(value) for value in VapiClient(credential).list_call_ids(limit=limit)]

    def fetch_session(self, credential: str, call_id: CallId) -> Session:
        raw = VapiClient(credential).fetch_call(str(call_id))
        return map_call_to_session(raw)
