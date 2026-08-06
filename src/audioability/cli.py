from __future__ import annotations

import argparse
import logging
from pathlib import Path

from audioability import __version__
from audioability.accessibility.backends import AccessibilityBackendUnavailableError
from audioability.core.application import ScreenReaderApplication
from audioability.input.commands import format_command_bindings


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
    parser.add_argument(
        "--list-commands",
        action="store_true",
        help="Print the default keyboard command reference and exit.",
    )
    parser.add_argument(
        "--debug-log",
        metavar="PATH",
        help="Write detailed diagnostic events to PATH.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_commands:
        print(format_command_bindings())
        return

    if args.debug_log:
        log_path = Path(args.debug_log).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            handlers=[logging.FileHandler(log_path, encoding="utf-8")],
            force=True,
        )
        logging.getLogger(__name__).info("diagnostic_log_started path=%s", log_path)

    app = ScreenReaderApplication(dry_run=args.dry_run)
    try:
        app.run()
    except AccessibilityBackendUnavailableError as exc:
        parser.exit(1, f"audioability: {exc}\n")
