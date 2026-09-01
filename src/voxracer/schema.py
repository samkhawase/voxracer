"""Small, dependency-free validator for canonical sessions."""

from __future__ import annotations

import re
from typing import Any

from .model import METRIC_KEYS, SCHEMA_VERSION, SPAN_TYPES

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T[^ ]+Z$")


def validate_session(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["session must be an object"]
    required = {"schema_version", "session_id", "provider", "started_at", "ended_at", "turns", "attributes"}
    for key in sorted(required - set(data)):
        errors.append(f"session missing {key}")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("session has unsupported schema_version")
    if not isinstance(data.get("session_id"), str) or not data.get("session_id"):
        errors.append("session_id must be a non-empty string")
    if data.get("provider") is not None and not isinstance(data.get("provider"), str):
        errors.append("provider must be a string or null")
    if not isinstance(data.get("started_at"), str) or not _TIMESTAMP.match(data.get("started_at", "")):
        errors.append("started_at must be an RFC3339 UTC timestamp")
    if data.get("ended_at") is not None and not isinstance(data.get("ended_at"), str):
        errors.append("ended_at must be a string or null")
    if not isinstance(data.get("turns"), list):
        return errors + ["turns must be a list"]
    turn_ids: set[str] = set()
    span_ids: set[str] = set()
    for ti, turn in enumerate(data["turns"]):
        where = f"turns[{ti}]"
        if not isinstance(turn, dict):
            errors.append(f"{where} must be an object")
            continue
        for key in ("turn_id", "start_ns", "end_ns", "spans", "metrics"):
            if key not in turn:
                errors.append(f"{where} missing {key}")
        turn_id = turn.get("turn_id")
        if not isinstance(turn_id, str):
            errors.append(f"{where}.turn_id must be a string")
        elif turn_id in turn_ids:
            errors.append(f"duplicate turn_id: {turn_id}")
        else:
            turn_ids.add(turn_id)
        start, end = turn.get("start_ns"), turn.get("end_ns")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            errors.append(f"{where} times must be integers")
        elif start < 0 or end < start:
            errors.append(f"{where} times are not ordered")
        metrics = turn.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(METRIC_KEYS):
            errors.append(f"{where}.metrics must contain exactly the metric keys")
        elif any(value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0) for value in metrics.values()):
            errors.append(f"{where}.metrics contains an invalid value")
        for key, allowed in (
            ("measurement_source", {"audio", "provider", "carrier", "client"}),
            ("measurement_scope", {"per_turn", "per_call"}),
            ("measurement_quality", {"accepted", "discarded", "uncertain"}),
        ):
            if key in turn and turn[key] is not None and turn[key] not in allowed:
                errors.append(f"{where}.{key} is not supported")
        spans = turn.get("spans")
        if not isinstance(spans, list):
            errors.append(f"{where}.spans must be a list")
            continue
        for si, span in enumerate(spans):
            sw = f"{where}.spans[{si}]"
            if not isinstance(span, dict):
                errors.append(f"{sw} must be an object")
                continue
            for key in ("span_id", "type", "start_ns", "end_ns"):
                if key not in span:
                    errors.append(f"{sw} missing {key}")
            sid = span.get("span_id")
            if not isinstance(sid, str):
                errors.append(f"{sw}.span_id must be a string")
            elif sid in span_ids:
                errors.append(f"duplicate span_id: {sid}")
            else:
                span_ids.add(sid)
            if span.get("type") not in SPAN_TYPES:
                errors.append(f"{sw}.type is not supported")
            if not all(isinstance(span.get(key), int) and not isinstance(span.get(key), bool) for key in ("start_ns", "end_ns")):
                errors.append(f"{sw} times must be integers")
            elif span["start_ns"] < 0 or span["end_ns"] < span["start_ns"]:
                errors.append(f"{sw} times are not ordered")
    return errors
