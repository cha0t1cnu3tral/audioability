from __future__ import annotations

import shutil
import subprocess

import pytest

from audioability.speech.drivers import (
    SpeechConfiguration,
    SpeechDispatcherDriver,
    SynthesisVoice,
)


def test_speech_dispatcher_uses_configured_output_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        calls.append((command, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(shutil, "which", lambda executable: "/usr/bin/spd-say")
    monkeypatch.setattr(subprocess, "run", fake_run)
    driver = SpeechDispatcherDriver()
    driver.configure(
        SpeechConfiguration(
            rate=1.5,
            volume=0.75,
            voice="English+Ava",
            language="en",
            punctuation="all",
        )
    )

    driver.speak("Hello")

    assert calls == [
        (
            [
                "/usr/bin/spd-say",
                "--rate",
                "50",
                "--volume",
                "50",
                "--punctuation-mode",
                "all",
                "--language",
                "en",
                "--synthesis-voice",
                "English+Ava",
                "Hello",
            ],
            False,
        )
    ]


def test_speech_dispatcher_maps_setting_limits_and_cancels_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(shutil, "which", lambda executable: "/usr/bin/spd-say")
    monkeypatch.setattr(subprocess, "run", fake_run)
    driver = SpeechDispatcherDriver()
    driver.configure(SpeechConfiguration(rate=0.5, volume=0.0))

    driver.speak("Quiet and slow")
    driver.stop()

    assert commands[0][1:7] == [
        "--rate",
        "-100",
        "--volume",
        "-100",
        "--punctuation-mode",
        "some",
    ]
    assert commands[1] == ["/usr/bin/spd-say", "--cancel"]


def test_speech_dispatcher_falls_back_when_process_cannot_start(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_to_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        raise OSError("cannot execute")

    monkeypatch.setattr(shutil, "which", lambda executable: "/usr/bin/spd-say")
    monkeypatch.setattr(subprocess, "run", fail_to_run)

    SpeechDispatcherDriver().speak("Fallback message")

    assert capsys.readouterr().out == "[speech fallback] Fallback message\n"


def test_speech_dispatcher_uses_native_client_for_pause_resume() -> None:
    calls: list[tuple[str, str]] = []

    class Client:
        def pause(self, scope: str) -> None:
            calls.append(("pause", scope))

        def resume(self, scope: str) -> None:
            calls.append(("resume", scope))

    driver = SpeechDispatcherDriver()
    driver._client = Client()
    driver._client_checked = True

    assert driver.pause() is True
    assert driver.resume() is True
    assert calls == [("pause", "all"), ("resume", "all")]


def test_speech_dispatcher_lists_all_native_synthesis_voices() -> None:
    class Client:
        def list_synthesis_voices(self) -> list[tuple[str, str, str]]:
            return [
                ("English+Alex", "en", "Alex"),
                ("English+Annie", "en", "Annie"),
                ("English+Alex", "en", "Alex"),
            ]

    driver = SpeechDispatcherDriver()
    driver._client = Client()
    driver._client_checked = True

    assert driver.available_voices() == (
        SynthesisVoice("English+Alex", "en", "Alex"),
        SynthesisVoice("English+Annie", "en", "Annie"),
    )
