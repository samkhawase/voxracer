"""Map allowlisted Vapi call and event-log fields to the canonical model."""

from __future__ import annotations

from typing import Any

from ...analysis import analyze_session
from ...model import Session, Span, Turn
from ..protocol import MalformedResponseError

_NON_TURN_IDS = {None, "CLEAN_UP"}
_BOT_SPEECH_STARTED = "pipeline.botSpeechStarted"
_TURN_STARTED = "pipeline.turnStarted"
_MODEL_STARTED = "assistant.model.requestStarted"
_MODEL_TOKEN = "assistant.model.firstTokenReceived"
_TOOL_STARTED = "assistant.tool.started"
_TOOL_COMPLETED = "assistant.tool.completed"
_VOICE_AUDIO = "assistant.voice.firstAudioReceived"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _time_ns(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number * 1_000_000)


def _seconds_ns(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number * 1_000_000_000)


def _event_time(event: dict[str, Any]) -> int | None:
    return _time_ns(event.get("time"))


def _events(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [
        event for event in events
        if isinstance(event.get("attributes"), dict)
        and event["attributes"].get("event") == name
        and _event_time(event) is not None
    ]


def _span(span_id: str, span_type: str, start_ns: int, duration_ms: Any) -> Span | None:
    duration = _number(duration_ms)
    if duration is None:
        return None
    return Span(
        span_id=span_id,
        type=span_type,  # type: ignore[arg-type]
        start_ns=start_ns,
        end_ns=start_ns + int(duration * 1_000_000),
        clock="provider",
        precision_ns=1_000_000,
    )


def _paired_spans(events: list[dict[str, Any]], start_name: str, end_name: str, span_type: str, duration_key: str) -> dict[str, list[Span]]:
    ends = {
        event["attributes"].get("spanId"): event
        for event in _events(events, end_name)
        if event["attributes"].get("spanId")
    }
    result: dict[str, list[Span]] = {}
    for start in _events(events, start_name):
        attrs = start["attributes"]
        span_id = attrs.get("spanId")
        turn_id = attrs.get("turnId")
        end = ends.get(span_id)
        start_ns = _event_time(start)
        if not isinstance(span_id, str) or not isinstance(turn_id, str) or end is None or start_ns is None:
            continue
        item = _span(span_id, span_type, start_ns, end["attributes"].get(duration_key))
        if item is not None:
            result.setdefault(turn_id, []).append(item)
    return result


def _turn_latencies(raw: dict[str, Any]) -> list[dict[str, Any]]:
    artifact = raw.get("artifact")
    metrics = artifact.get("performanceMetrics") if isinstance(artifact, dict) else None
    values = metrics.get("turnLatencies") if isinstance(metrics, dict) else None
    return [value for value in values if isinstance(value, dict)] if isinstance(values, list) else []


def _map_event_log(raw: dict[str, Any], events: list[dict[str, Any]]) -> list[Turn]:
    closing = [event for event in _events(events, _BOT_SPEECH_STARTED) if event["attributes"].get("turnId") not in _NON_TURN_IDS]
    latencies = _turn_latencies(raw)
    if len(closing) != len(latencies):
        latencies = []
    turn_started = {
        event["attributes"].get("turnId"): _event_time(event)
        for event in _events(events, _TURN_STARTED)
        if event["attributes"].get("turnId") not in _NON_TURN_IDS
    }
    model_spans = _paired_spans(events, _MODEL_STARTED, _MODEL_TOKEN, "llm", "latency")
    tool_spans = _paired_spans(events, _TOOL_STARTED, _TOOL_COMPLETED, "tool", "duration")
    voice_events = {
        event["attributes"].get("turnId"): event
        for event in _events(events, _VOICE_AUDIO)
        if event["attributes"].get("turnId") not in _NON_TURN_IDS
    }
    turns: list[Turn] = []
    for index, bot in enumerate(closing):
        bot_ns = _event_time(bot)
        turn_id = bot["attributes"].get("turnId")
        if bot_ns is None or not isinstance(turn_id, str):
            continue
        spans = model_spans.get(turn_id, []) + tool_spans.get(turn_id, [])
        latency = latencies[index] if index < len(latencies) else {}
        window_ms = _number(latency.get("turnLatency"))
        start_ns = bot_ns - int(window_ms * 1_000_000) if window_ms is not None else min((span.start_ns for span in spans), default=bot_ns)
        if window_ms is not None:
            stt = _span(f"stt-turn-{index}", "stt", start_ns, latency.get("transcriberLatency"))
            if stt is not None and not any(other.start_ns < stt.end_ns and other.end_ns > stt.start_ns for other in spans):
                spans.append(stt)
            endpoint_start = turn_started.get(turn_id)
            endpoint = _span(f"endpointing-turn-{index}", "endpointing", endpoint_start or start_ns, latency.get("endpointingLatency"))
            if endpoint is not None:
                spans.append(endpoint)
        audio = voice_events.get(turn_id)
        if audio is not None:
            audio_ns = _event_time(audio)
            if audio_ns is not None:
                audio_latency = _number(audio["attributes"].get("latency")) or 0
                tts = _span(f"tts-turn-{index}", "tts", audio_ns - int(audio_latency * 1_000_000), audio["attributes"].get("latency"))
                if tts is not None:
                    spans.append(tts)
                playback = _span(f"playback-turn-{index}", "transport", audio_ns, (bot_ns - audio_ns) / 1_000_000)
                if playback is not None:
                    spans.append(playback)
        end_ns = bot_ns if window_ms is not None else max((span.end_ns for span in spans), default=bot_ns)
        turns.append(Turn(
            turn_id=f"turn-{index}", start_ns=max(0, start_ns), end_ns=max(start_ns, end_ns), spans=spans,
            measurement_source="provider", measurement_scope="per_turn", measurement_quality="accepted",
        ))
    return turns


def _map_message_fallback(raw: dict[str, Any]) -> list[Turn]:
    messages = raw.get("messages")
    if not isinstance(messages, list):
        artifact = raw.get("artifact")
        messages = artifact.get("messages") if isinstance(artifact, dict) else []
    turns: list[Turn] = []
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, dict) or message.get("role") not in {"assistant", "bot"}:
            continue
        start = _seconds_ns(message.get("secondsFromStart"))
        duration = _seconds_ns(message.get("duration"))
        if start is None or duration is None:
            continue
        latency = _turn_latencies(raw)
        provider = latency[len(turns)] if len(turns) < len(latency) else {}
        metrics: dict[str, float | None] = {
            target: round(value, 3)
            for source, target in (
                ("endpointingLatency", "endpointing_ms"),
                ("transcriberLatency", "stt_ms"),
                ("modelLatency", "llm_ttft_ms"),
                ("voiceLatency", "tts_ttfa_ms"),
            )
            if isinstance(provider, dict) and (value := _number(provider.get(source))) is not None
        }
        turns.append(Turn(turn_id=f"turn-{len(turns)}", start_ns=start, end_ns=start + duration, metrics=metrics, measurement_source="provider", measurement_scope="per_turn", measurement_quality="accepted"))
    return turns


def map_call_to_session(raw: dict[str, Any], events: list[dict[str, Any]] | None = None) -> Session:
    """Map a call and, when available, its event log to canonical data."""
    call_id = raw.get("id")
    started_at = raw.get("startedAt")
    if not isinstance(call_id, str) or not call_id:
        raise MalformedResponseError("Vapi call has no identifier")
    if not isinstance(started_at, str) or not started_at:
        raise MalformedResponseError("Vapi call has no start timestamp")
    turns = _map_event_log(raw, events or []) if events else _map_message_fallback(raw)
    session = Session(
        session_id=call_id, provider="vapi", started_at=started_at,
        ended_at=raw.get("endedAt") if isinstance(raw.get("endedAt"), str) else None,
        turns=turns,
        attributes={"status": raw.get("status")} if isinstance(raw.get("status"), str) else {},
    )
    return analyze_session(session)
