"""Provider-neutral timing analysis."""

from __future__ import annotations

from .intervals import clip, union_duration_ns
from .model import Session, Turn

_SPAN_TO_METRIC = {
    "endpointing": "endpointing_ms",
    "stt": "stt_ms",
    "llm": "llm_ttft_ms",
    "tool": "tool_ms",
    "tts": "tts_ttfa_ms",
    "transport": "playback_ms",
}


def analyze_turn(turn: Turn) -> Turn:
    window = (turn.start_ns, turn.end_ns)
    critical_spans = [span for span in turn.spans if span.critical_path]
    clocks = {span.clock for span in critical_spans if span.clock is not None}
    for span_type, metric_key in _SPAN_TO_METRIC.items():
        intervals = []
        for span in turn.spans:
            if span.type != span_type or not span.critical_path:
                continue
            bounded = clip((span.start_ns, span.end_ns), window)
            if bounded:
                intervals.append(bounded)
        if intervals:
            turn.metrics[metric_key] = union_duration_ns(intervals) / 1_000_000

    known = []
    for span in turn.spans:
        if not span.critical_path:
            continue
        bounded = clip((span.start_ns, span.end_ns), window)
        if bounded:
            known.append(bounded)
    if known and len(clocks) <= 1:
        observed = turn.end_ns - turn.start_ns
        turn.metrics["ttfab_ms"] = observed / 1_000_000
        turn.metrics["unattributed_ms"] = max(
            0.0, (observed - union_duration_ns(known)) / 1_000_000
        )
    elif len(clocks) > 1:
        turn.metrics["ttfab_ms"] = None
        turn.metrics["unattributed_ms"] = None
    return turn


def analyze_session(session: Session) -> Session:
    for turn in session.turns:
        analyze_turn(turn)
    return session
