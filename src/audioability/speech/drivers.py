from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class SpeechDriver(Protocol):
    """Interface for speech synthesis output."""

    def speak(self, text: str) -> None:
        """Speak text to the user."""


@dataclass(frozen=True)
class SpeechConfiguration:
    rate: float = 1.0
    volume: float = 1.0
    voice: str = "default"
    language: str = "default"
    punctuation: str = "some"


@dataclass(frozen=True)
class SynthesisVoice:
    name: str
    language: str
    variant: str = ""


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
        self._client: Any | None = None
        self._client_checked = False

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
            if self.configuration.language != "default":
                command.extend(("--language", self.configuration.language))
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

    def pause(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.pause("all")
        except Exception:
            return False
        return True

    def resume(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.resume("all")
        except Exception:
            return False
        return True

    def available_voices(self) -> tuple[SynthesisVoice, ...]:
        client = self._get_client()
        if client is not None:
            try:
                voices = client.list_synthesis_voices()
            except Exception:
                voices = ()
            catalog = tuple(
                SynthesisVoice(
                    name=str(voice[0]).strip(),
                    language=str(voice[1]).strip() or "default",
                    variant=str(voice[2]).strip() if len(voice) > 2 else "",
                )
                for voice in voices
                if isinstance(voice, (tuple, list))
                and len(voice) >= 2
                and str(voice[0]).strip()
            )
            if catalog:
                return tuple(dict.fromkeys(catalog))

        resolved_executable = shutil.which(self.executable)
        if resolved_executable is None:
            return (SynthesisVoice("default", "default"),)
        try:
            result = subprocess.run(
                [resolved_executable, "--list-synthesis-voices"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return (SynthesisVoice("default", "default"),)

        catalog = tuple(
            SynthesisVoice(
                name=line[:42].strip(),
                language=line[42:68].strip() or "default",
                variant=line[68:].strip(),
            )
            for line in result.stdout.splitlines()[1:]
            if line[:42].strip()
        )
        return tuple(dict.fromkeys(catalog)) or (SynthesisVoice("default", "default"),)

    def _get_client(self) -> Any | None:
        if self._client_checked:
            return self._client
        self._client_checked = True
        try:
            import speechd  # type: ignore[import-not-found, import-untyped, unused-ignore]

            self._client = speechd.SSIPClient("audioability")
        except Exception:
            self._client = None
        return self._client

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
