"""Command-line interface for local canonical-session files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .adapters.elevenlabs import ElevenLabsAdapter
from .adapters.vapi import VapiAdapter
from .adapters.protocol import AdapterError
from .analysis import analyze_session
from .diagnosis import diagnose_session
from .model import METRIC_KEYS, Session, Turn
from .schema import validate_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxracer",
        description="Measure where time went during a voice-agent turn.",
    )
    parser.add_argument("--version", action="version", version=f"voxracer {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a session JSON file")
    validate.add_argument("session", type=Path)
    analyze = subparsers.add_parser("analyze", help="analyze a session JSON file")
    analyze.add_argument("session", type=Path)
    report = subparsers.add_parser("report", help="print a human-readable session report")
    report.add_argument("session", type=Path)
    diagnose = subparsers.add_parser("diagnose", help="show deterministic session findings")
    diagnose.add_argument("session", type=Path)
    latest = subparsers.add_parser("latest", help="fetch and analyze the latest provider call")
    latest.add_argument("--provider", choices=("elevenlabs", "vapi"), default="elevenlabs")
    latest.add_argument(
        "--api-key-env",
        default=None,
        help="environment variable containing the provider API key",
    )
    fetch = subparsers.add_parser("fetch", help="fetch and analyze one provider call")
    fetch.add_argument("--provider", choices=("elevenlabs", "vapi"), required=True)
    fetch.add_argument("--call", required=True, help="provider call identifier")
    fetch.add_argument(
        "--api-key-env",
        default=None,
        help="environment variable containing the provider API key",
    )
    fetch.add_argument("--format", choices=("report", "json"), default="report")
    latest.add_argument("--format", choices=("report", "json"), default="json")
    return parser


def _load(path: Path) -> Session:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from None
    errors = validate_session(data)
    if errors:
        raise ValueError("invalid session:\n" + "\n".join(f"- {error}" for error in errors))
    return Session.from_dict(data)


def _report(session: Session) -> str:
    def duration(value: float | None) -> str:
        if value is None:
            return "unknown"
        return f"{value:.0f} ms" if value < 1000 else f"{value / 1000:.2f} s"

    def percentile(values: list[float], fraction: float) -> float:
        values = sorted(values)
        return values[min(len(values) - 1, int((len(values) - 1) * fraction))]

    def bar(fraction: float, width: int) -> str:
        filled = max(0, min(width, round(fraction * width)))
        if fraction > 0 and filled == 0:
            filled = 1
        return "█" * filled

    def display_timing(turn: Turn) -> tuple[float | None, str]:
        caller = turn.metrics["ttfab_ms"]
        if caller is not None:
            return caller, "caller"
        provider = turn.attributes.get("provider_ttfab_ms")
        preceded = session.attributes.get("stt_preceded_by_user_turn", {}).get(turn.turn_id, True)
        if isinstance(provider, (int, float)) and not isinstance(provider, bool) and preceded:
            return float(provider), "provider"
        return None, "unknown"

    timings = [(turn, *display_timing(turn)) for turn in session.turns]
    measured = [value for _, value, source in timings if value is not None]
    timing_sources = {source for _, value, source in timings if value is not None}
    lines = [f"Session {session.session_id} · source={session.provider or 'unknown'} · {len(session.turns)} turns"]
    first_audio = session.attributes.get("time_to_first_audio_ms")
    if isinstance(first_audio, (int, float)):
        lines.append(f"Time to first audio: {first_audio:.0f} ms (caller connected → agent audible)")
    if measured:
        response_label = "Response time" if timing_sources == {"caller"} else "Provider response time"
        lines.append(
            f"{response_label}  p50 {duration(percentile(measured, 0.50))} · "
            f"p95 {duration(percentile(measured, 0.95))} · "
            f"slowest {duration(max(measured))}   ({len(measured)} of {len(session.turns)} turns measured)"
        )
    else:
        lines.append("Response time  unavailable (no measured caller-perceived turn time)")
    if timing_sources == {"provider"}:
        lines.append("  (provider silence → provider first audio; not caller-perceived audio)")
    if len(measured) < 5 and measured:
        lines.append(f"  (p95 needs 5 measured turns to mean anything — this call has {len(measured)})")

    ranked = sorted(
        session.turns,
        key=lambda turn: (display_timing(turn)[0] is None, -(display_timing(turn)[0] or 0)),
    )
    if len(session.turns) > 1:
        lines.append("\nTurns by response time")
        width = max(len(turn.turn_id) for turn in session.turns)
        slowest = max(measured, default=0.0)
        for turn in ranked:
            value, _ = display_timing(turn)
            drawn = "·" if value is None or slowest == 0 else bar(value / slowest, 20)
            lines.append(f"  {turn.turn_id:<{width}}  {drawn:<20}  {duration(value)}")

    labels = (
        ("endpointing_ms", "endpointing"), ("stt_ms", "STT"),
        ("llm_ttft_ms", "LLM"), ("tool_ms", "tool"),
        ("tts_ttfa_ms", "TTS"), ("playback_ms", "playback"),
        ("unattributed_ms", "unattributed"),
    )
    for turn in session.turns:
        response, timing_source = display_timing(turn)
        lines.append(f"\n{turn.turn_id}")
        lines.append(f"  {'response time':<14} {duration(response)}")
        if timing_source == "provider":
            lines.append(f"  {'timing source':<14} provider silence → provider first audio")
        for key, label in labels:
            value = turn.metrics[key]
            if value is None:
                value_text = "unknown"
                share_text = ""
                bar_text = ""
            else:
                share = f"  {value / response:.0%}" if response and response > 0 else ""
                value_text = f"{value:.0f} ms"
                share_text = share.strip()
                bar_text = bar(value / response, 16) if response and response > 0 else ""
            lines.append(f"  {label:<14} {value_text:>10} {share_text:>5}  {bar_text:<16}".rstrip())
    findings = diagnose_session(session)
    if findings:
        lines.append("findings:")
        for finding in findings:
            lines.append(f"  {finding.turn_id}: {finding.message}")
    return "\n".join(lines)


def _adapter(provider: str) -> ElevenLabsAdapter | VapiAdapter:
    return ElevenLabsAdapter() if provider == "elevenlabs" else VapiAdapter()


def _key_env(provider: str, override: str | None) -> str:
    return override or ("ELEVENLABS_API_KEY" if provider == "elevenlabs" else "VAPI_API_KEY")


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"validate", "analyze", "report", "diagnose", "latest", "fetch"}
    if not any(item in commands for item in raw_argv) and {"--provider", "--call"}.issubset(raw_argv):
        raw_argv.insert(0, "fetch")
    args = _parser().parse_args(raw_argv)
    try:
        if args.command in ("validate", "analyze", "report", "diagnose"):
            session = _load(args.session)
        else:
            key_env = _key_env(args.provider, args.api_key_env)
            credential = os.environ.get(key_env)
            if not credential:
                raise ValueError(f"environment variable {key_env} is not set")
            adapter = _adapter(args.provider)
            if args.command == "latest":
                call_ids = adapter.list_call_ids(credential, limit=1)
                if not call_ids:
                    raise ValueError("provider returned no calls")
                call_id = call_ids[0]
            else:
                call_id = args.call
            session = adapter.fetch_session(credential, call_id)

        if args.command == "validate":
            print(f"valid session: {session.session_id}")
        elif args.command == "report":
            print(_report(analyze_session(session)))
        elif args.command == "diagnose":
            print(json.dumps([finding.to_dict() for finding in diagnose_session(analyze_session(session))], indent=2))
        elif args.command in ("latest", "fetch") and args.format == "report":
            print(_report(analyze_session(session)))
        else:
            print(json.dumps(analyze_session(session).to_dict(), indent=2))
        return 0
    except (AdapterError, ValueError) as exc:
        print(f"voxracer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
