from audioability.accessibility.models import AccessibleNode
from audioability.core.application import ScreenReaderApplication
from audioability.input.commands import Command, CommandName
from audioability.speech.drivers import NullSpeechDriver


def test_dry_run_speaks_startup_message() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app.run()

    assert speech.messages == ["Audioability initialized in dry-run mode."]


def test_focused_node_is_spoken() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(
        AccessibleNode(name="Submit", role="push button", description="Submit the form")
    )

    assert speech.messages == ["Submit push button Submit the form"]


def test_repeating_last_spoken_text_repeats_last_focused_node() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(
        AccessibleNode(name="Submit", role="push button", description="Submit the form")
    )

    assert app.repeat_last_spoken() is True
    assert speech.messages == [
        "Submit push button Submit the form",
        "Submit push button Submit the form",
    ]


def test_repeat_last_command_repeats_last_spoken_text() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    handled = app.handle_command(
        Command(
            name=CommandName.REPEAT_LAST,
            description="Repeat the last spoken text.",
        )
    )

    assert handled is True
    assert speech.messages == ["Search entry", "Search entry"]


def test_router_repeat_repeats_last_spoken_text() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.router.run("repeat") is True
    assert speech.messages == ["Search entry", "Search entry"]


def test_router_focus_speaks_current_focus() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.router.run("focus") is True
    assert speech.messages == ["Search entry", "Search entry"]


def test_router_stop_returns_false_when_driver_cannot_stop() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.router.run("stop") is False
