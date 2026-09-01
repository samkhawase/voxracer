"""Deterministic findings from measured session data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model import Session


@dataclass(frozen=True)
class Finding:
    """A reproducible observation with its source values."""

    code: str
    turn_id: str
    message: str
    evidence: dict[str, float | None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "turn_id": self.turn_id,
            "message": self.message,
            "evidence": dict(self.evidence),
        }


def diagnose_session(session: Session) -> list[Finding]:
    """Return findings based only on canonical metric values."""
    findings: list[Finding] = []
    for turn in session.turns:
        ttfab = turn.metrics["ttfab_ms"]
        provider_ttfab = turn.attributes.get("provider_ttfab_ms")
        if ttfab is None and provider_ttfab is None:
            findings.append(Finding(
                code="ttfab_unknown",
                turn_id=turn.turn_id,
                message="caller-perceived time to first audio is unknown",
                evidence={"ttfab_ms": None},
            ))
        unattributed = turn.metrics["unattributed_ms"]
        if ttfab is not None and unattributed is not None and unattributed >= ttfab * 0.2:
            findings.append(Finding(
                code="high_unattributed_time",
                turn_id=turn.turn_id,
                message="at least 20 percent of the turn is unattributed",
                evidence={"ttfab_ms": ttfab, "unattributed_ms": unattributed},
            ))
    return findings
