"""Public types and analysis functions for VoxRacer."""

from .analysis import analyze_session
from .diagnosis import Finding, diagnose_session
from .adapters.protocol import CallId, ProviderAdapter
from .model import METRIC_KEYS, SCHEMA_VERSION, Session, Span, SpanType, Turn
from .schema import validate_session

__version__ = "0.1.0a1"

__all__ = [
    "METRIC_KEYS",
    "CallId",
    "Finding",
    "ProviderAdapter",
    "SCHEMA_VERSION",
    "Session",
    "Span",
    "SpanType",
    "Turn",
    "analyze_session",
    "diagnose_session",
    "validate_session",
]
