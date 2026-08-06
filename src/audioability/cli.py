from __future__ import annotations

import argparse
import faulthandler
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO

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
    parser.add_argument(
        "--crash-log",
        metavar="PATH",
        help=(
            "Write fatal Python and native crash traces to PATH. On Linux this defaults to "
            "~/.local/state/audioability/crash.log."
        ),
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

    crash_path = _crash_log_path(args.crash_log, dry_run=args.dry_run)
    crash_file = _open_crash_log(crash_path)
    fault_handler_enabled_here = False
    if crash_file is not None and not faulthandler.is_enabled():
        faulthandler.enable(file=crash_file, all_threads=True)
        fault_handler_enabled_here = True

    try:
        app = ScreenReaderApplication(dry_run=args.dry_run)
        app.run()
    except AccessibilityBackendUnavailableError as exc:
        parser.exit(1, f"audioability: {exc}\n")
    except Exception as exc:
        if crash_file is not None:
            traceback.print_exc(file=crash_file)
            crash_file.flush()
        detail = f" Diagnostics: {crash_path}" if crash_path is not None else ""
        parser.exit(1, f"audioability: unexpected failure: {exc}.{detail}\n")
    finally:
        if fault_handler_enabled_here:
            faulthandler.disable()
        if crash_file is not None:
            print(
                f"Audioability process ended at {datetime.now().astimezone().isoformat()}",
                file=crash_file,
            )
            crash_file.close()


def _crash_log_path(value: str | None, *, dry_run: bool) -> Path | None:
    if value:
        return Path(value).expanduser()
    if dry_run or sys.platform != "linux":
        return None

    state_home = os.environ.get("XDG_STATE_HOME")
    state_directory = Path(state_home).expanduser() if state_home else Path.home() / ".local/state"
    return state_directory / "audioability" / "crash.log"


def _open_crash_log(path: Path | None) -> TextIO | None:
    if path is None:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        crash_file = path.open("a", encoding="utf-8")
    except OSError:
        logging.getLogger(__name__).exception("crash_log_open_failed path=%s", path)
        return None

    started_at = datetime.now().astimezone().isoformat()
    print(f"Audioability process started at {started_at} pid={os.getpid()}", file=crash_file)
    crash_file.flush()
    return crash_file
