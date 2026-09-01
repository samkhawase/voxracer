import json

import pytest

from voxracer import Session, Span, Turn, analyze_session, validate_session
from voxracer.adapters import ProviderAdapter
from voxracer.adapters.protocol import CallId
from voxracer.cli import main
from voxracer.intervals import merge_intervals, union_duration_ns


def make_session() -> Session:
    turn = Turn(
        turn_id="turn-1",
        start_ns=0,
        end_ns=1_000_000_000,
        spans=[
            Span("llm-1", "llm", 100_000_000, 600_000_000),
            Span("tool-1", "tool", 400_000_000, 800_000_000),
        ],
    )
    return Session("session-1", "example", "2026-08-31T00:00:00Z", None, [turn])


def test_overlapping_intervals_are_counted_once():
    assert merge_intervals([(0, 5), (3, 10), (20, 25)]) == [(0, 10), (20, 25)]
    assert union_duration_ns([(0, 5), (3, 10)]) == 10


def test_analysis_keeps_eight_metrics_and_accounts_for_union():
    session = analyze_session(make_session())
    metrics = session.turns[0].metrics
    assert metrics["ttfab_ms"] == 1000.0
    assert metrics["llm_ttft_ms"] == 500.0
    assert metrics["tool_ms"] == 400.0
    assert metrics["unattributed_ms"] == 300.0
    assert sum(value or 0 for value in metrics.values()) >= metrics["ttfab_ms"]


def test_session_round_trip_is_valid():
    data = make_session().to_dict()
    assert validate_session(data) == []
    assert Session.from_dict(data).to_dict() == data


def test_mixed_clocks_keep_component_values_but_hide_unattributed():
    turn = Turn(
        turn_id="turn-1",
        start_ns=0,
        end_ns=1_000_000_000,
        spans=[
            Span("llm-1", "llm", 100_000_000, 600_000_000, clock="provider"),
            Span("tts-1", "tts", 600_000_000, 800_000_000, clock="telephony"),
        ],
    )
    analyze_session(Session("s", None, "2026-08-31T00:00:00Z", None, [turn]))
    assert turn.metrics["llm_ttft_ms"] == 500.0
    assert turn.metrics["tts_ttfa_ms"] == 200.0
    assert turn.metrics["unattributed_ms"] is None


def test_validator_rejects_unknown_metric():
    data = make_session().to_dict()
    data["turns"][0]["metrics"]["invented_ms"] = 1
    assert validate_session(data)


def test_cli_help_and_validation(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "validate" in capsys.readouterr().out
    path = tmp_path / "session.json"
    path.write_text(json.dumps(make_session().to_dict()), encoding="utf-8")
    assert main(["validate", str(path)]) == 0
    assert "valid session" in capsys.readouterr().out


def test_provider_adapter_protocol_accepts_read_only_adapter():
    class FakeAdapter:
        name = "fake"

        def list_call_ids(self, credential: str, *, limit: int = 30) -> list[CallId]:
            return [CallId("call-1")][:limit]

        def fetch_session(self, credential: str, call_id: CallId) -> Session:
            return make_session()

    adapter = FakeAdapter()
    assert isinstance(adapter, ProviderAdapter)
    assert adapter.list_call_ids("credential") == [CallId("call-1")]
