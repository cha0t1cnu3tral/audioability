from __future__ import annotations

import argparse

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
    args = build_parser().parse_args(argv)
    app = ScreenReaderApplication(dry_run=args.dry_run)
    app.run()
