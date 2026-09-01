"""Provider-neutral data types.

The model stores facts. It does not fetch data or make diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

SCHEMA_VERSION = "0.1"
SpanType: TypeAlias = Literal[
    "endpointing", "stt", "llm", "tool", "tts", "transport", "other"
]
MetricKey: TypeAlias = Literal[
    "ttfab_ms",
    "endpointing_ms",
    "stt_ms",
    "llm_ttft_ms",
    "tool_ms",
    "tts_ttfa_ms",
    "playback_ms",
    "unattributed_ms",
]
MeasurementSource: TypeAlias = Literal["audio", "provider", "carrier", "client"]
MeasurementScope: TypeAlias = Literal["per_turn", "per_call"]
MeasurementQuality: TypeAlias = Literal["accepted", "discarded", "uncertain"]

METRIC_KEYS: tuple[MetricKey, ...] = (
    "ttfab_ms",
    "endpointing_ms",
    "stt_ms",
    "llm_ttft_ms",
    "tool_ms",
    "tts_ttfa_ms",
    "playback_ms",
    "unattributed_ms",
)
SPAN_TYPES: tuple[SpanType, ...] = (
    "endpointing", "stt", "llm", "tool", "tts", "transport", "other"
)


def _metric_dict(values: dict[str, float | None] | None = None) -> dict[str, float | None]:
    result: dict[str, float | None] = {key: None for key in METRIC_KEYS}
    if values:
        unknown = set(values) - set(METRIC_KEYS)
        if unknown:
            raise ValueError(f"unknown metric keys: {sorted(unknown)}")
        result.update(values)
    return result


@dataclass
class Span:
    span_id: str
    type: SpanType
    start_ns: int
    end_ns: int
    parent_span_id: str | None = None
    critical_path: bool = True
    clock: str | None = None
    precision_ns: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in SPAN_TYPES:
            raise ValueError(f"unsupported span type: {self.type}")
        if self.start_ns < 0 or self.end_ns < self.start_ns:
            raise ValueError("span times must be non-negative and ordered")
        if self.precision_ns is not None and self.precision_ns < 0:
            raise ValueError("precision_ns must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "type": self.type,
            "start_ns": self.start_ns,
            "end_ns": self.end_ns,
            "parent_span_id": self.parent_span_id,
            "critical_path": self.critical_path,
            "clock": self.clock,
            "precision_ns": self.precision_ns,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Span":
        return cls(**data)


@dataclass
class Turn:
    turn_id: str
    start_ns: int
    end_ns: int
    spans: list[Span] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=_metric_dict)
    precision_ns: int | None = None
    measurement_source: MeasurementSource | None = None
    measurement_scope: MeasurementScope | None = None
    measurement_quality: MeasurementQuality | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metrics = _metric_dict(self.metrics)
        if self.start_ns < 0 or self.end_ns < self.start_ns:
            raise ValueError("turn times must be non-negative and ordered")

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "start_ns": self.start_ns,
            "end_ns": self.end_ns,
            "spans": [span.to_dict() for span in self.spans],
            "metrics": dict(self.metrics),
            "precision_ns": self.precision_ns,
            "measurement_source": self.measurement_source,
            "measurement_scope": self.measurement_scope,
            "measurement_quality": self.measurement_quality,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Turn":
        values = dict(data)
        values["spans"] = [Span.from_dict(span) for span in values.get("spans", [])]
        return cls(**values)


@dataclass
class Session:
    session_id: str
    provider: str | None
    started_at: str
    ended_at: str | None
    turns: list[Turn] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "provider": self.provider,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "turns": [turn.to_dict() for turn in self.turns],
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        values = dict(data)
        values["turns"] = [Turn.from_dict(turn) for turn in values.get("turns", [])]
        return cls(**values)
