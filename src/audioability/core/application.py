from __future__ import annotations

from audioability.accessibility.backends import AccessibilityBackend, NullAccessibilityBackend
from audioability.speech.drivers import NullSpeechDriver, SpeechDriver


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
        self.accessibility_backend = accessibility_backend or NullAccessibilityBackend()
        self.speech_driver = speech_driver or NullSpeechDriver()

    def run(self) -> None:
        if self.dry_run:
            self.speech_driver.speak("Audioability initialized in dry-run mode.")
            return

        self.accessibility_backend.start()
        self.speech_driver.speak("Audioability started.")
