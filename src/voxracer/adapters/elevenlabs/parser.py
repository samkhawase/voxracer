"""Allowlisted ElevenLabs OTLP parser."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...model import Session, Span, Turn
from ..protocol import MalformedResponseError

_ROOT_NAME = "elevenlabs.conversation"
_RESPONSE_NAME = "elevenlabs.recv.agent_response"
_TOOL_PREFIX = "elevenlabs.tool."
_ROOT_ATTRS = {
    "elevenlabs.conversation_id": "conversation_id",
    "elevenlabs.status": "status",
}
_METRIC_ATTRS = {
    "elevenlabs.metric.convai_llm_service_ttfb_ms": "llm_ttft_ms",
    "elevenlabs.metric.convai_tts_service_ttfb_ms": "tts_ttfa_ms",
}
_TOOL_ATTRS = {
    "elevenlabs.tool.name": "name",
    "elevenlabs.tool.latency_ms": "latency_ms",
}


def _spans(raw: dict[str, Any]) -> list[dict[str, Any]]:
    traces = raw.get("otlp_traces")
    if not isinstance(traces, dict):
        raise MalformedResponseError("ElevenLabs response has no OTLP traces")
    result: list[dict[str, Any]] = []
    for resource in traces.get("resourceSpans", []):
        if not isinstance(resource, dict):
            continue
        for scope in resource.get("scopeSpans", []):
            if isinstance(scope, dict):
                result.extend(span for span in scope.get("spans", []) if isinstance(span, dict))
    return result


def _nano(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MalformedResponseError("ElevenLabs span has an invalid timestamp") from exc
    if result < 0:
        raise MalformedResponseError("ElevenLabs span has a negative timestamp")
    return result


def _timestamp(nanoseconds: int) -> str:
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, timezone.utc).isoformat().replace("+00:00", "Z")


def _attributes(span: dict[str, Any], allowed: dict[str, str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or item.get("key") not in allowed:
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        key = allowed[item["key"]]
        for raw_key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if raw_key in value:
                output[key] = value[raw_key]
                break
    return output


def _metric_value(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _tool_span(span: dict[str, Any]) -> Span:
    attrs = _attributes(span, _TOOL_ATTRS)
    return Span(
        span_id=str(span.get("spanId", "tool")),
        type="tool",
        start_ns=_nano(span.get("startTimeUnixNano")),
        end_ns=_nano(span.get("endTimeUnixNano")),
        parent_span_id=span.get("parentSpanId") if isinstance(span.get("parentSpanId"), str) else None,
        clock="provider",
        attributes={key: value for key, value in attrs.items() if key == "name"},
    )


def map_otlp_to_session(raw: dict[str, Any]) -> Session:
    """Map an allowlisted OTLP response into a canonical session."""
    spans = _spans(raw)
    root = next((span for span in spans if span.get("name") == _ROOT_NAME), None)
    if root is None:
        raise MalformedResponseError("ElevenLabs response has no conversation span")
    root_start = _nano(root.get("startTimeUnixNano"))
    root_end = _nano(root.get("endTimeUnixNano"))
    root_attrs = _attributes(root, _ROOT_ATTRS)
    session_id = str(raw.get("conversation_id") or root_attrs.get("conversation_id") or "")
    if not session_id:
        raise MalformedResponseError("ElevenLabs response has no conversation identifier")

    response_spans = sorted(
        (span for span in spans if span.get("name") == _RESPONSE_NAME),
        key=lambda span: _nano(span.get("startTimeUnixNano")),
    )
    turns: list[Turn] = []
    for index, response in enumerate(response_spans):
        start = _nano(response.get("startTimeUnixNano"))
        end = _nano(response.get("endTimeUnixNano"))
        metrics: dict[str, float | None] = {}
        metrics.update({key: None for key in ("ttfab_ms", "endpointing_ms", "stt_ms", "llm_ttft_ms", "tool_ms", "tts_ttfa_ms", "playback_ms", "unattributed_ms")})
        response_attrs = _attributes(response, _METRIC_ATTRS)
        for key, value in response_attrs.items():
            parsed = _metric_value(value)
            if parsed is not None:
                metrics[key] = parsed
        children = [
            span for span in spans
            if span.get("name", "").startswith(_TOOL_PREFIX)
            and span.get("parentSpanId") == response.get("spanId")
        ]
        turns.append(
            Turn(
                turn_id=f"turn-{index}",
                start_ns=start,
                end_ns=end,
                spans=[_tool_span(span) for span in children],
                metrics=metrics,
                measurement_source="provider",
                measurement_scope="per_turn",
                measurement_quality="accepted",
            )
        )
    return Session(
        session_id=session_id,
        provider="elevenlabs",
        started_at=_timestamp(root_start),
        ended_at=_timestamp(root_end),
        turns=turns,
        attributes={key: value for key, value in root_attrs.items() if key == "status"},
    )
