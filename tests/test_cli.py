from __future__ import annotations

import pytest

from audioability import cli
from audioability.accessibility.backends import AccessibilityBackendUnavailableError


def test_main_runs_dry_run() -> None:
    cli.main(["--dry-run"])


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
