from __future__ import annotations

from audioability.speech.controller import SpeechController, SpeechOption


class StoppableSpeechDriver:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.stopped = False

    def speak(self, text: str) -> None:
        self.messages.append(text)

    def stop(self) -> None:
        self.stopped = True


def test_speak_tracks_last_message_and_skips_immediate_duplicates() -> None:
    now = 10.0
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech, clock=lambda: now)

    assert controller.speak("Save") is True
    assert controller.speak("Save") is False

    assert speech.messages == ["Save"]
    assert controller.last_spoken_text == "Save"


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


def test_non_capslock_arrow_is_not_handled() -> None:
    speech = StoppableSpeechDriver()
    controller = SpeechController(speech)

    assert controller.handle_modifier_arrow("shift", "up") is False
    assert speech.messages == []
