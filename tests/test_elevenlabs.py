from voxracer.adapters.elevenlabs import ElevenLabsAdapter, map_otlp_to_session, merge_transcript_metrics
from voxracer.adapters.protocol import CallId, ProviderAdapter
from voxracer.adapters.vapi import map_call_to_session
from voxracer.adapters.vapi.client import USER_AGENT, VapiClient


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


def transcript_response():
    return {
        "transcript": [
            {
                "role": "user",
                "private": "ignored",
                "conversation_turn_metrics": {
                    "metrics": {
                        "convai_asr_trailing_service_latency": {"elapsed_time": 0.12},
                    }
                },
            },
            {
                "role": "agent",
                "message": "reply",
                "conversation_turn_metrics": {
                    "metrics": {
                        "convai_turn_silence_before_initiation": {"elapsed_time": 0.31},
                        "convai_ttf_audio_since_silence": {"elapsed_time": 0.44},
                    }
                },
            },
        ]
    }


def test_transcript_metrics_attach_to_the_next_agent_turn():
    session = map_otlp_to_session(otlp_response())
    merge_transcript_metrics(session, transcript_response())

    turn = session.turns[0]
    assert turn.metrics["stt_ms"] == 120.0
    assert turn.metrics["endpointing_ms"] == 310.0
    assert turn.attributes["provider_ttfab_ms"] == 440.0
    assert turn.metrics["ttfab_ms"] is None
    assert session.attributes["stt_preceded_by_user_turn"] == {"turn-0": True}


def test_opening_agent_turn_has_no_stt_fact():
    session = map_otlp_to_session(otlp_response())
    merge_transcript_metrics(session, {"transcript": [{"role": "agent"}]})

    assert session.turns[0].metrics["stt_ms"] is None
    assert session.attributes["stt_preceded_by_user_turn"] == {"turn-0": False}


def test_transcript_count_mismatch_does_not_partially_update_session():
    session = map_otlp_to_session(otlp_response())
    raw = transcript_response()
    raw["transcript"].append({"role": "agent"})

    merge_transcript_metrics(session, raw)

    assert session.turns[0].metrics["stt_ms"] is None
    assert session.turns[0].metrics["endpointing_ms"] is None
    assert session.attributes == {"status": 1}


def test_vapi_parser_maps_positioned_provider_latencies():
    session = map_call_to_session({
        "id": "call-redacted",
        "startedAt": "2026-08-31T00:00:00Z",
        "endedAt": "2026-08-31T00:00:05Z",
        "status": "ended",
        "messages": [{"role": "assistant", "secondsFromStart": 1.0, "duration": 2.0}],
        "artifact": {"performanceMetrics": {"turnLatencies": [{
            "modelLatency": 0.4,
            "voiceLatency": 0.2,
            "transcriberLatency": 0.1,
            "endpointingLatency": 0.3,
        }]}},
    })

    turn = session.turns[0]
    assert turn.start_ns == 1_000_000_000
    assert turn.metrics["llm_ttft_ms"] == 400.0
    assert turn.metrics["endpointing_ms"] == 300.0
    assert turn.metrics["ttfab_ms"] is None


def test_vapi_client_sends_explicit_user_agent():
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, limit):
            return b"[]"

    def opener(request, timeout):
        requests.append(request)
        return Response()

    VapiClient("redacted-key", opener=opener).list_call_ids(limit=1)

    assert requests[0].get_header("User-agent") == USER_AGENT
