from __future__ import annotations

from audioability.speech.controller import SpeechController, SpeechOption
from audioability.speech.drivers import SpeechConfiguration, SynthesisVoice


class StoppableSpeechDriver:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.stop_count = 0

    def speak(self, text: str) -> None:
        self.messages.append(text)

    def stop(self) -> None:
        self.stop_count += 1

    @property
    def stopped(self) -> bool:
        return self.stop_count > 0


class ConfigurableSpeechDriver(StoppableSpeechDriver):
    def __init__(self) -> None:
        super().__init__()
        self.configurations: list[SpeechConfiguration] = []

    def configure(self, configuration: SpeechConfiguration) -> None:
        self.configurations.append(configuration)


class PausableSpeechDriver(StoppableSpeechDriver):
    def __init__(self) -> None:
        super().__init__()
        self.pause_count = 0
        self.resume_count = 0

    def pause(self) -> bool:
        self.pause_count += 1
        return True

    def resume(self) -> bool:
        self.resume_count += 1
        return True


def test_speak_tracks_last_message_and_skips_immediate_duplicates() -> None:
    now = 10.0
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech, clock=lambda: now)

    assert controller.speak("Save") is True
    assert controller.speak("Save") is False

    assert speech.messages == ["Save"]
    assert speech.stop_count == 1
    assert controller.last_spoken_text == "Save"


def test_speak_interrupts_previous_output_when_driver_can_stop() -> None:
    now = 10.0
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech, clock=lambda: now)

    assert controller.speak("First") is True
    now = 11.0
    assert controller.speak("Second") is True

    assert speech.messages == ["First", "Second"]
    assert speech.stop_count == 2


def test_repeat_bypasses_duplicate_spam_protection() -> None:
    now = 10.0
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech, clock=lambda: now)

    controller.speak("Save")

    assert controller.repeat_last() is True
    assert speech.messages == ["Save", "Save"]


def test_stop_delegates_to_driver_when_supported() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.stop() is True

    assert speech.stopped is True


def test_stop_resumes_paused_driver_before_canceling() -> None:
    speech = PausableSpeechDriver()
    controller = SpeechController(speech)
    controller.toggle_pause()

    assert controller.stop() is True

    assert controller.paused is False
    assert speech.resume_count == 1
    assert speech.stop_count == 1


def test_toggle_pause_pauses_and_resumes_speech() -> None:
    speech = PausableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.toggle_pause() is True
    assert controller.paused is True
    assert controller.toggle_pause() is True
    assert controller.paused is False

    assert speech.pause_count == 1
    assert speech.resume_count == 1


def test_new_speech_clears_paused_state() -> None:
    speech = PausableSpeechDriver()
    controller = SpeechController(speech)
    controller.toggle_pause()

    controller.speak("New message")

    assert controller.paused is False
    assert speech.resume_count == 1
    assert speech.messages == ["New message"]


def test_capslock_left_and_right_navigate_options() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("capslock", "right") is True
    assert controller.selected_option.value == SpeechOption.VOLUME.value
    assert speech.messages[-1] == "Volume 100 percent"

    assert controller.handle_modifier_arrow("capslock", "left") is True
    assert controller.selected_option.value == SpeechOption.RATE.value
    assert speech.messages[-1] == "Rate 100 percent"


def test_capslock_up_and_down_change_selected_option() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("capslock", "up") is True
    assert controller.settings.rate == 1.1
    assert speech.messages[-1] == "Rate 110 percent"

    assert controller.handle_modifier_arrow("capslock", "down") is True
    assert controller.settings.rate == 1.0
    assert speech.messages[-1] == "Rate 100 percent"


def test_modifier_arrow_can_change_option_without_announcement() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("capslock", "up", announce=False) is True

    assert controller.settings.rate == 1.1
    assert speech.messages == []


def test_insert_arrows_navigate_speech_options_like_capslock() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("insert", "right") is True

    assert controller.selected_option.value == SpeechOption.VOLUME.value
    assert speech.messages[-1] == "Volume 100 percent"


def test_non_capslock_arrow_is_not_handled() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("shift", "up") is False
    assert speech.messages == []


def test_setting_changes_are_applied_to_configurable_driver() -> None:
    speech = ConfigurableSpeechDriver()
    controller = SpeechController(
        speech,
        voices=(
            SynthesisVoice("English+default", "en", "default"),
            SynthesisVoice("English+Ava", "en", "Ava"),
        ),
    )

    assert speech.configurations == [
        SpeechConfiguration(voice="English+default", language="en")
    ]

    controller.handle_modifier_arrow("capslock", "up", announce=False)
    controller.handle_modifier_arrow("capslock", "right", announce=False)
    controller.handle_modifier_arrow("capslock", "right", announce=False)
    controller.handle_modifier_arrow("capslock", "right", announce=False)
    controller.handle_modifier_arrow("capslock", "up", announce=False)

    assert speech.configurations[-1] == SpeechConfiguration(
        rate=1.1,
        volume=1.0,
        voice="English+Ava",
        language="en",
        punctuation="some",
    )


def test_language_and_voice_are_selected_separately() -> None:
    speech = ConfigurableSpeechDriver()
    controller = SpeechController(
        speech,
        voices=(
            SynthesisVoice("English+Alex", "en", "Alex"),
            SynthesisVoice("English+Annie", "en", "Annie"),
            SynthesisVoice("French+Alex", "fr", "Alex"),
        ),
    )

    controller.handle_modifier_arrow("capslock", "right")
    controller.handle_modifier_arrow("capslock", "right")
    assert controller.selected_option.value == SpeechOption.LANGUAGE.value
    controller.handle_modifier_arrow("capslock", "up")
    assert speech.messages[-1] == "Language fr"

    controller.handle_modifier_arrow("capslock", "right")
    assert controller.selected_option.value == SpeechOption.VOICE.value
    assert speech.messages[-1] == "Voice Alex"
    assert speech.configurations[-1].language == "fr"
    assert speech.configurations[-1].voice == "French+Alex"
