from __future__ import annotations

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
    """Speech Dispatcher driver placeholder."""

    def speak(self, text: str) -> None:
        raise NotImplementedError("Speech Dispatcher integration has not been implemented yet.")
