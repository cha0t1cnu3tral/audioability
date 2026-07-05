from __future__ import annotations

import argparse

from audioability.accessibility.backends import AccessibilityBackendUnavailableError
from audioability.core.application import ScreenReaderApplication


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audioability",
        description="Run the Audioability Linux screen reader.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Initialize the app without connecting to Linux desktop services.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = ScreenReaderApplication(dry_run=args.dry_run)
    try:
        app.run()
    except AccessibilityBackendUnavailableError as exc:
        parser.exit(1, f"audioability: {exc}\n")
