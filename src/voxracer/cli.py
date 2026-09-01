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
from .model import METRIC_KEYS, Session
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
    lines = [f"session: {session.session_id}", f"provider: {session.provider or 'unknown'}"]
    for turn in session.turns:
        lines.append(f"turn: {turn.turn_id}")
        for key in METRIC_KEYS:
            value = turn.metrics[key]
            display = "unknown" if value is None else f"{value:.3f} ms"
            lines.append(f"  {key}: {display}")
    return "\n".join(lines)


def _adapter(provider: str) -> ElevenLabsAdapter | VapiAdapter:
    return ElevenLabsAdapter() if provider == "elevenlabs" else VapiAdapter()


def _key_env(provider: str, override: str | None) -> str:
    return override or ("ELEVENLABS_API_KEY" if provider == "elevenlabs" else "VAPI_API_KEY")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
        else:
            print(json.dumps(analyze_session(session).to_dict(), indent=2))
        return 0
    except (AdapterError, ValueError) as exc:
        print(f"voxracer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
