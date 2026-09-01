"""Command-line interface for local canonical-session files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analysis import analyze_session
from .model import Session
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        session = _load(args.session)
        if args.command == "validate":
            print(f"valid session: {session.session_id}")
        else:
            print(json.dumps(analyze_session(session).to_dict(), indent=2))
        return 0
    except ValueError as exc:
        print(f"voxracer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
