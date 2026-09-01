"""Map allowlisted Vapi call fields to the canonical model."""

from __future__ import annotations

from typing import Any

from ...model import Session, Turn
from ..protocol import MalformedResponseError


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _time_ns(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number * 1_000_000_000)


def _latency(metrics: dict[str, Any], name: str) -> float | None:
    value = _number(metrics.get(name))
    return None if value is None else round(value * 1000, 3)


def map_call_to_session(raw: dict[str, Any]) -> Session:
    """Map positioned assistant messages and matching provider latencies."""
    call_id = raw.get("id")
    started_at = raw.get("startedAt")
    if not isinstance(call_id, str) or not call_id:
        raise MalformedResponseError("Vapi call has no identifier")
    if not isinstance(started_at, str) or not started_at:
        raise MalformedResponseError("Vapi call has no start timestamp")

    messages = raw.get("messages", [])
    if not isinstance(messages, list):
        raise MalformedResponseError("Vapi call messages are not a list")
    latency_data = raw.get("artifact", {}).get("performanceMetrics", {}) if isinstance(raw.get("artifact"), dict) else {}
    turn_latencies = latency_data.get("turnLatencies", []) if isinstance(latency_data, dict) else []
    if not isinstance(turn_latencies, list):
        turn_latencies = []

    turns: list[Turn] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        start = _time_ns(message.get("secondsFromStart"))
        duration = _time_ns(message.get("duration"))
        if start is None or duration is None:
            continue
        metrics: dict[str, float | None] = {}
        latency = turn_latencies[len(turns)] if len(turns) < len(turn_latencies) else {}
        if not isinstance(latency, dict):
            latency = {}
        for source, target in (
            ("endpointingLatency", "endpointing_ms"),
            ("transcriberLatency", "stt_ms"),
            ("modelLatency", "llm_ttft_ms"),
            ("voiceLatency", "tts_ttfa_ms"),
        ):
            value = _latency(latency, source)
            if value is not None:
                metrics[target] = value
        turns.append(
            Turn(
                turn_id=f"turn-{len(turns)}",
                start_ns=start,
                end_ns=start + duration,
                metrics=metrics,
                measurement_source="provider",
                measurement_scope="per_turn",
                measurement_quality="accepted",
            )
        )

    ended_at = raw.get("endedAt")
    return Session(
        session_id=call_id,
        provider="vapi",
        started_at=started_at,
        ended_at=ended_at if isinstance(ended_at, str) else None,
        turns=turns,
        attributes={"status": raw.get("status")} if isinstance(raw.get("status"), str) else {},
    )
