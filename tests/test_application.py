from audioability.core.application import ScreenReaderApplication
from audioability.speech.drivers import NullSpeechDriver


def test_dry_run_speaks_startup_message() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app.run()

    assert speech.messages == ["Audioability initialized in dry-run mode."]
