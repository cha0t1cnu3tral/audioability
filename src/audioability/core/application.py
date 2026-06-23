from __future__ import annotations

from audioability.accessibility.backends import (
    AccessibilityBackend,
    AtSpiAccessibilityBackend,
    NullAccessibilityBackend,
)
from audioability.accessibility.models import AccessibleNode
from audioability.input.commands import Command, CommandName
from audioability.speech.controller import SpeechController
from audioability.speech.drivers import NullSpeechDriver, SpeechDispatcherDriver, SpeechDriver


class ScreenReaderApplication:
    """Coordinates accessibility events, command input, and speech output."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        accessibility_backend: AccessibilityBackend | None = None,
        speech_driver: SpeechDriver | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.speech_driver = speech_driver or (
            NullSpeechDriver() if dry_run else SpeechDispatcherDriver()
        )
        self.speech_controller = SpeechController(self.speech_driver)
        self.accessibility_backend = accessibility_backend or (
            NullAccessibilityBackend()
            if dry_run
            else AtSpiAccessibilityBackend(on_focus=self._speak_focused_node)
        )

    def run(self) -> None:
        if self.dry_run:
            self.speech_controller.speak("Audioability initialized in dry-run mode.")
            return

        self.speech_controller.speak("Audioability started.")
        self.accessibility_backend.start()

    def handle_command(self, command: Command) -> bool:
        if command.name is CommandName.REPEAT_LAST:
            return self.repeat_last_spoken()
        if command.name is CommandName.STOP_SPEECH:
            return self.stop_speech()

        return False

    def repeat_last_spoken(self) -> bool:
        return self.speech_controller.repeat_last()

    def stop_speech(self) -> bool:
        return self.speech_controller.stop()

    def _speak_focused_node(self, node: AccessibleNode) -> None:
        text = " ".join(part for part in (node.name, node.role, node.description) if part)
        if text:
            self.speech_controller.speak(text)
