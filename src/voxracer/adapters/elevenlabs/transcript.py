"""Map allowlisted transcript timing fields to canonical turn metrics."""

from __future__ import annotations

from typing import Any

from ...model import Session
from ..protocol import MalformedResponseError

STT_PRECEDED_BY_USER_TURN_ATTR = "stt_preceded_by_user_turn"
PROVIDER_TTFAB_ATTR = "provider_ttfab_ms"

_METRICS_KEY = "conversation_turn_metrics"
_STT_KEY = "convai_asr_trailing_service_latency"
_ENDPOINTING_KEY = "convai_turn_silence_before_initiation"
_TTFAB_KEY = "convai_ttf_audio_since_silence"


def _entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    transcript = raw.get("transcript")
    if not isinstance(transcript, list):
        raise MalformedResponseError("ElevenLabs response has no transcript list")
    return [entry for entry in transcript if isinstance(entry, dict)]


def _elapsed_ms(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    elapsed = value.get("elapsed_time")
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
        return None
    return round(float(elapsed) * 1000, 3)


def _metric(entry: dict[str, Any], key: str) -> float | None:
    metrics = entry.get(_METRICS_KEY)
    if not isinstance(metrics, dict):
        return None
    return _elapsed_ms(metrics.get("metrics", {}).get(key)) if isinstance(metrics.get("metrics"), dict) else None


def merge_transcript_metrics(session: Session, raw: dict[str, Any]) -> Session:
    """Merge transcript timing facts when transcript and OTLP turn counts agree."""
    records: list[tuple[float | None, float | None, float | None, bool]] = []
    pending_stt: float | None = None
    had_user_turn = False
    for entry in _entries(raw):
        role = entry.get("role")
        if role == "user":
            had_user_turn = True
            pending_stt = _metric(entry, _STT_KEY)
        elif role == "agent":
            records.append(
                (
                    pending_stt,
                    _metric(entry, _ENDPOINTING_KEY),
                    _metric(entry, _TTFAB_KEY),
                    had_user_turn,
                )
            )
            pending_stt = None
            had_user_turn = False

    if len(records) != len(session.turns):
        return session

    preceding_user: dict[str, bool] = {}
    provider_ttfab: dict[str, float | None] = {}
    for turn, (stt, endpointing, ttfab, had_user) in zip(session.turns, records):
        if stt is not None:
            turn.metrics["stt_ms"] = stt
        if endpointing is not None:
            turn.metrics["endpointing_ms"] = endpointing
        preceding_user[turn.turn_id] = had_user
        provider_ttfab[turn.turn_id] = ttfab
        if ttfab is not None:
            turn.attributes[PROVIDER_TTFAB_ATTR] = ttfab
    session.attributes[STT_PRECEDED_BY_USER_TURN_ATTR] = preceding_user
    return session
