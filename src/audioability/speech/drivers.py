from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class SpeechDriver(Protocol):
    """Interface for speech synthesis output."""

    def speak(self, text: str) -> None:
        """Speak text to the user."""


@dataclass(frozen=True)
class SpeechConfiguration:
    rate: float = 1.0
    volume: float = 1.0
    voice: str = "default"
    punctuation: str = "some"


@runtime_checkable
class ConfigurableSpeechDriver(Protocol):
    def configure(self, configuration: SpeechConfiguration) -> None:
        """Apply settings used for subsequent speech."""


class NullSpeechDriver:
    """No-op speech driver used by tests and dry runs."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def speak(self, text: str) -> None:
        self.messages.append(text)


class SpeechDispatcherDriver:
    """Speech Dispatcher driver using spd-say when available."""

    def __init__(self, executable: str = "spd-say") -> None:
        self.executable = executable
        self.configuration = SpeechConfiguration()

    def configure(self, configuration: SpeechConfiguration) -> None:
        self.configuration = configuration

    def speak(self, text: str) -> None:
        resolved_executable = shutil.which(self.executable)
        if resolved_executable is not None:
            command = [
                resolved_executable,
                "--rate",
                str(self._rate_argument()),
                "--volume",
                str(self._volume_argument()),
                "--punctuation-mode",
                self.configuration.punctuation,
            ]
            if self.configuration.voice != "default":
                command.extend(("--synthesis-voice", self.configuration.voice))
            command.append(text)
            if self._run(command):
                return

        print(f"[speech fallback] {text}")

    def stop(self) -> None:
        resolved_executable = shutil.which(self.executable)
        if resolved_executable is not None:
            self._run([resolved_executable, "--cancel"])

    def _rate_argument(self) -> int:
        rate = self._clamp(self.configuration.rate, 0.5, 2.0)
        multiplier = 200 if rate < 1.0 else 100
        return round((rate - 1.0) * multiplier)

    def _volume_argument(self) -> int:
        volume = self._clamp(self.configuration.volume, 0.0, 1.0)
        return round((volume * 200) - 100)

    @staticmethod
    def _run(command: list[str]) -> bool:
        try:
            subprocess.run(command, check=False)
        except OSError:
            return False

        return True

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return min(max(value, minimum), maximum)
