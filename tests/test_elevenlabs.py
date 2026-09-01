from voxracer.adapters.elevenlabs import ElevenLabsAdapter, map_otlp_to_session
from voxracer.adapters.protocol import CallId, ProviderAdapter


def otlp_response():
    def span(span_id, name, start, end, attributes=None, parent=None):
        return {
            "spanId": span_id,
            "parentSpanId": parent,
            "name": name,
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(end),
            "attributes": [
                {"key": key, "value": {"doubleValue": value}}
                for key, value in (attributes or {}).items()
            ],
        }

    return {
        "conversation_id": "conversation-redacted",
        "otlp_traces": {
            "resourceSpans": [{"scopeSpans": [{"spans": [
                span("root", "elevenlabs.conversation", 0, 3_000_000_000, {
                    "elevenlabs.status": 1,
                }),
                span("turn", "elevenlabs.recv.agent_response", 0, 1_000_000_000, {
                    "elevenlabs.metric.convai_llm_service_ttfb_ms": 300.0,
                    "elevenlabs.metric.convai_tts_service_ttfb_ms": 150.0,
                }),
                span("tool", "elevenlabs.tool.lookup", 400_000_000, 800_000_000, {
                    "elevenlabs.tool.latency_ms": 400.0,
                }, "turn"),
            ]}]}]
        },
    }


def test_parser_maps_only_allowlisted_provider_facts():
    session = map_otlp_to_session(otlp_response())
    turn = session.turns[0]
    assert session.provider == "elevenlabs"
    assert turn.metrics["llm_ttft_ms"] == 300.0
    assert turn.metrics["tts_ttfa_ms"] == 150.0
    assert turn.spans[0].type == "tool"
    assert turn.metrics["ttfab_ms"] is None


def test_adapter_matches_protocol():
    assert isinstance(ElevenLabsAdapter(), ProviderAdapter)
    assert CallId("abc") == "abc"
