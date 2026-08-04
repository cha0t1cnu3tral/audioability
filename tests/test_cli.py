from __future__ import annotations

import pytest

from audioability import cli
from audioability.accessibility.backends import AccessibilityBackendUnavailableError


def test_main_runs_dry_run() -> None:
    cli.main(["--dry-run"])


def test_main_lists_commands_without_starting_application(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_started(*, dry_run: bool) -> None:
        pytest.fail("application should not be created when listing commands")

    monkeypatch.setattr(cli, "ScreenReaderApplication", fail_if_started)

    cli.main(["--list-commands"])

    output = capsys.readouterr().out
    assert "Desktop" in output
    assert "sr+tab" in output
    assert "read the currently focused control" in output


def test_version_option_reports_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == "audioability 0.1.0\n"


def test_main_reports_unavailable_accessibility_backend(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class UnavailableApplication:
        def __init__(self, *, dry_run: bool) -> None:
            self.dry_run = dry_run

        def run(self) -> None:
            raise AccessibilityBackendUnavailableError("Install accessibility packages.")

    monkeypatch.setattr(cli, "ScreenReaderApplication", UnavailableApplication)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == "audioability: Install accessibility packages.\n"
