from __future__ import annotations

import shutil
import subprocess
from typing import Protocol


class SpeechDriver(Protocol):
    """Interface for speech synthesis output."""

    def speak(self, text: str) -> None:
        """Speak text to the user."""


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

    def speak(self, text: str) -> None:
        if shutil.which(self.executable):
            subprocess.run([self.executable, text], check=False)
            return

        print(f"[speech fallback] {text}")

    def stop(self) -> None:
        if shutil.which(self.executable):
            subprocess.run([self.executable, "-C"], check=False)
