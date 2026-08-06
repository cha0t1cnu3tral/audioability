from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol, TypeVar, runtime_checkable

from audioability.input.commands import is_screen_reader_modifier
from audioability.speech.drivers import (
    ConfigurableSpeechDriver,
    SpeechConfiguration,
    SpeechDriver,
    SynthesisVoice,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class SpeechOption(StrEnum):
    RATE = "rate"
    VOLUME = "volume"
    LANGUAGE = "language"
    VOICE = "voice"
    PUNCTUATION = "punctuation"
    VERBOSITY = "verbosity"


class PunctuationMode(StrEnum):
    NONE = "none"
    SOME = "some"
    ALL = "all"


class VerbosityMode(StrEnum):
    BRIEF = "brief"
    NORMAL = "normal"
    DETAILED = "detailed"


@dataclass(frozen=True)
class SpeechSettings:
    rate: float = 1.0
    volume: float = 1.0
    language_index: int = 0
    voice_index: int = 0
    punctuation: PunctuationMode = PunctuationMode.SOME
    verbosity: VerbosityMode = VerbosityMode.NORMAL


@runtime_checkable
class StoppableSpeechDriver(Protocol):
    def stop(self) -> None:
        """Stop speech that is currently being spoken."""


@runtime_checkable
class PausableSpeechDriver(Protocol):
    def pause(self) -> bool:
        """Pause speech that is currently being spoken."""

    def resume(self) -> bool:
        """Resume paused speech."""


class SpeechController:
    """Stateful speech controls for speaking, repeating, and settings changes."""

    _options = (
        SpeechOption.RATE,
        SpeechOption.VOLUME,
        SpeechOption.LANGUAGE,
        SpeechOption.VOICE,
        SpeechOption.PUNCTUATION,
        SpeechOption.VERBOSITY,
    )
    _punctuation_modes = tuple(PunctuationMode)
    _verbosity_modes = tuple(VerbosityMode)

    def __init__(
        self,
        driver: SpeechDriver,
        *,
        voices: tuple[SynthesisVoice, ...] = (SynthesisVoice("default", "default"),),
        duplicate_window_seconds: float = 0.75,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._driver = driver
        self._voices = voices or (SynthesisVoice("default", "default"),)
        self._languages = tuple(dict.fromkeys(voice.language for voice in self._voices))
        self._duplicate_window_seconds = duplicate_window_seconds
        self._clock = clock
        self._last_spoken_text: str | None = None
        self._last_spoken_at: float | None = None
        self._selected_option_index = 0
        self._paused = False
        self.settings = SpeechSettings()
        self._sync_driver_configuration()

    @property
    def last_spoken_text(self) -> str | None:
        return self._last_spoken_text

    @property
    def selected_option(self) -> SpeechOption:
        return self._options[self._selected_option_index]

    def speak(self, text: str, *, allow_duplicate: bool = False) -> bool:
        cleaned_text = text.strip()
        if not cleaned_text:
            return False

        now = self._clock()
        if not allow_duplicate and self._is_duplicate_spam(cleaned_text, now):
            logger.debug("speech_duplicate_suppressed text=%r", cleaned_text)
            return False

        if isinstance(self._driver, StoppableSpeechDriver):
            self._driver.stop()
        self._paused = False
        logger.debug("speech_dispatch text=%r settings=%r", cleaned_text, self.settings)
        self._driver.speak(cleaned_text)
        self._last_spoken_text = cleaned_text
        self._last_spoken_at = now
        return True

    def stop(self) -> bool:
        if not isinstance(self._driver, StoppableSpeechDriver):
            return False

        self._driver.stop()
        self._paused = False
        logger.debug("speech_stopped")
        return True

    def toggle_pause(self) -> bool:
        if not isinstance(self._driver, PausableSpeechDriver):
            return False

        if self._paused:
            handled = self._driver.resume()
            if handled:
                self._paused = False
                logger.debug("speech_resumed")
            return handled

        handled = self._driver.pause()
        if handled:
            self._paused = True
            logger.debug("speech_paused")
        return handled

    @property
    def paused(self) -> bool:
        return self._paused

    def repeat_last(self) -> bool:
        if self._last_spoken_text is None:
            return False

        return self.speak(self._last_spoken_text, allow_duplicate=True)

    def handle_modifier_arrow(
        self,
        modifier_key: str,
        arrow_key: str,
        *,
        announce: bool = True,
    ) -> bool:
        if not is_screen_reader_modifier(modifier_key):
            return False

        key = self._normalize_key(arrow_key)
        if key == "left":
            self._select_previous_option(announce=announce)
            return True
        if key == "right":
            self._select_next_option(announce=announce)
            return True
        if key == "up":
            self._change_selected_option(1, announce=announce)
            return True
        if key == "down":
            self._change_selected_option(-1, announce=announce)
            return True

        return False

    def _is_duplicate_spam(self, text: str, now: float) -> bool:
        if self._last_spoken_text != text or self._last_spoken_at is None:
            return False

        return now - self._last_spoken_at < self._duplicate_window_seconds

    def _select_previous_option(self, *, announce: bool) -> None:
        self._selected_option_index = (self._selected_option_index - 1) % len(self._options)
        if announce:
            self._announce_selected_option()

    def _select_next_option(self, *, announce: bool) -> None:
        self._selected_option_index = (self._selected_option_index + 1) % len(self._options)
        if announce:
            self._announce_selected_option()

    def _change_selected_option(self, direction: int, *, announce: bool) -> None:
        option = self.selected_option
        if option is SpeechOption.RATE:
            self.settings = replace(
                self.settings,
                rate=self._clamp(round(self.settings.rate + (0.1 * direction), 1), 0.5, 2.0),
            )
        elif option is SpeechOption.VOLUME:
            self.settings = replace(
                self.settings,
                volume=self._clamp(round(self.settings.volume + (0.1 * direction), 1), 0.0, 1.0),
            )
        elif option is SpeechOption.LANGUAGE:
            self.settings = replace(
                self.settings,
                language_index=(self.settings.language_index + direction) % len(self._languages),
                voice_index=0,
            )
        elif option is SpeechOption.VOICE:
            voices = self._voices_for_selected_language()
            self.settings = replace(
                self.settings,
                voice_index=(self.settings.voice_index + direction) % len(voices),
            )
        elif option is SpeechOption.PUNCTUATION:
            self.settings = replace(
                self.settings,
                punctuation=self._cycle(
                    self._punctuation_modes,
                    self.settings.punctuation,
                    direction,
                ),
            )
        elif option is SpeechOption.VERBOSITY:
            self.settings = replace(
                self.settings,
                verbosity=self._cycle(self._verbosity_modes, self.settings.verbosity, direction),
            )

        self._sync_driver_configuration()
        if announce:
            self._announce_selected_option()

    def _sync_driver_configuration(self) -> None:
        if not isinstance(self._driver, ConfigurableSpeechDriver):
            return

        self._driver.configure(
            SpeechConfiguration(
                rate=self.settings.rate,
                volume=self.settings.volume,
                voice=self._selected_voice().name,
                language=self._selected_language(),
                punctuation=self.settings.punctuation.value,
            )
        )

    def _announce_selected_option(self) -> None:
        self.speak(self._selected_option_message(), allow_duplicate=True)

    def _selected_option_message(self) -> str:
        option = self.selected_option
        if option is SpeechOption.RATE:
            return f"Rate {self._percent(self.settings.rate)} percent"
        if option is SpeechOption.VOLUME:
            return f"Volume {self._percent(self.settings.volume)} percent"
        if option is SpeechOption.LANGUAGE:
            return f"Language {self._selected_language()}"
        if option is SpeechOption.VOICE:
            voice = self._selected_voice()
            return f"Voice {voice.variant or voice.name}"
        if option is SpeechOption.PUNCTUATION:
            return f"Punctuation {self.settings.punctuation.value}"
        if option is SpeechOption.VERBOSITY:
            return f"Verbosity {self.settings.verbosity.value}"

        raise ValueError(f"Unknown speech option: {option}")

    def _selected_language(self) -> str:
        return self._languages[self.settings.language_index]

    def _voices_for_selected_language(self) -> tuple[SynthesisVoice, ...]:
        language = self._selected_language()
        return tuple(voice for voice in self._voices if voice.language == language)

    def _selected_voice(self) -> SynthesisVoice:
        voices = self._voices_for_selected_language()
        return voices[self.settings.voice_index % len(voices)]

    @staticmethod
    def _cycle(items: tuple[T, ...], current: T, direction: int) -> T:
        return items[(items.index(current) + direction) % len(items)]

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return min(max(value, minimum), maximum)

    @staticmethod
    def _percent(value: float) -> int:
        return round(value * 100)

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.lower().replace("_", "").replace("-", "").removeprefix("arrow")
