from audioability.accessibility.models import AccessibleNode
from audioability.accessibility.navigation import ObjectNavigationAction
from audioability.core.application import InteractionMode, ScreenReaderApplication, SpeechMode
from audioability.input.commands import Command, CommandName
from audioability.speech.drivers import NullSpeechDriver


class StoppableSpeechDriver(NullSpeechDriver):
    def __init__(self) -> None:
        super().__init__()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class StoppableBackend:
    def __init__(self) -> None:
        self.stopped = False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        self.stopped = True


def assert_interaction_mode(app: ScreenReaderApplication, mode: InteractionMode) -> None:
    assert app.interaction_mode is mode


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


def test_focused_tree_enables_navigation_outside_focused_node() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    focused = AccessibleNode(name="Search", role="entry")
    sibling = AccessibleNode(name="Cancel", role="button")
    panel = AccessibleNode(name="Controls", role="panel", children=(focused, sibling))
    root = AccessibleNode(name="Settings", role="frame", children=(panel,))

    app._speak_focused_tree(root, focused)

    assert app.navigate_object(ObjectNavigationAction.MOVE_TO_NEXT) is True
    assert app.navigate_object(ObjectNavigationAction.MOVE_TO_PARENT) is True

    assert speech.messages == [
        "Search entry",
        "Cancel button",
        "Controls panel 2 items",
    ]


def test_focused_node_speech_includes_state_value_children_and_shortcut() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(
        AccessibleNode(
            name="Volume",
            role="slider",
            description="Master output volume",
            value="75",
            text="Volume",
            placeholder="Set volume",
            shortcut="Alt+V",
            state=frozenset({"focused", "focusable", "enabled"}),
            child_count=2,
        )
    )

    assert speech.messages == [
        "Volume slider 75 Set volume Master output volume 2 items shortcut Alt+V"
    ]


def test_unnamed_container_speech_includes_readable_children() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(
        AccessibleNode(
            name="",
            role="container",
            children=(AccessibleNode(name="Play", role="button"),),
        )
    )

    assert speech.messages == ["container Play button"]


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


def test_control_key_interrupts_speech() -> None:
    speech = StoppableSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.handle_key("Control_L") is True

    assert speech.stopped is True


def test_screen_reader_key_gesture_reads_focus() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.handle_key("Tab", ("Caps_Lock",)) is True

    assert speech.messages == ["Search entry", "Search entry"]


def test_read_title_window_and_status_bar_commands() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    status = AccessibleNode(name="Ready", role="status bar")
    root = AccessibleNode(
        name="Downloads",
        role="frame",
        children=(AccessibleNode(name="Toolbar", role="panel"), status),
    )
    app.object_navigator.set_root(root)

    assert app.handle_command(Command(CommandName.READ_TITLE, "Read title")) is True
    assert app.handle_command(Command(CommandName.READ_WINDOW, "Read window")) is True
    assert app.handle_command(Command(CommandName.READ_STATUS_BAR, "Read status")) is True

    assert speech.messages == [
        "Downloads",
        "Downloads frame 2 items",
        "Ready status bar",
    ]


def test_sr_space_toggles_browse_and_focus_modes() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.handle_key("Space", ("Caps_Lock",)) is True
    assert_interaction_mode(app, InteractionMode.FOCUS)
    assert app.handle_key("Space", ("Caps_Lock",)) is True
    assert_interaction_mode(app, InteractionMode.BROWSE)

    assert speech.messages == ["Focus mode", "Browse mode"]


def test_editable_focus_auto_enters_focus_mode_and_escape_returns_to_browse() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(
        AccessibleNode(name="Search", role="entry", state=frozenset({"editable"}))
    )

    assert_interaction_mode(app, InteractionMode.FOCUS)
    assert app.handle_key("Escape") is True
    assert_interaction_mode(app, InteractionMode.BROWSE)

    assert speech.messages == ["Search entry editable", "Browse mode"]


def test_manual_focus_mode_passes_plain_keys_to_application() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.handle_key("Space", ("Caps_Lock",)) is True
    assert app.handle_key("Down") is False

    assert speech.messages == ["Focus mode"]


def test_browse_mode_arrow_keys_navigate_accessibility_tree() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    first = AccessibleNode(name="First", role="button")
    second = AccessibleNode(name="Second", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first, second))
    app._speak_focused_tree(root, first)

    assert app.handle_key("Down") is True
    assert app.handle_key("Up") is True

    assert speech.messages == [
        "First button",
        "Second button",
        "First button",
    ]


def test_status_bar_gesture_reports_missing_status_bar() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    app.object_navigator.set_root(AccessibleNode(name="Downloads", role="frame"))

    assert app.handle_key("End", ("Caps_Lock",)) is True

    assert speech.messages == ["No status bar"]


def test_on_demand_speech_mode_suppresses_focus_events_but_keeps_commands() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.cycle_speech_mode() is True
    assert app.speech_mode is SpeechMode.ON_DEMAND

    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.handle_key("Tab", ("Caps_Lock",)) is True
    assert speech.messages == [
        "Speech mode on-demand",
        "Search entry",
    ]


def test_off_speech_mode_suppresses_normal_speech_until_mode_changes() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))
    assert app.cycle_speech_mode() is True
    assert app.cycle_speech_mode() is True
    assert app.speech_mode is SpeechMode.OFF

    app._speak_focused_node(AccessibleNode(name="Results", role="list"))
    assert app.handle_key("Tab", ("Caps_Lock",)) is True
    assert app.repeat_last_spoken() is True
    assert app.cycle_speech_mode() is True

    assert speech.messages == [
        "Search entry",
        "Speech mode on-demand",
        "Speech mode off",
        "Speech mode talk",
    ]


def test_off_speech_mode_keeps_speech_setting_shortcuts_silent() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.cycle_speech_mode() is True
    assert app.cycle_speech_mode() is True

    assert app.handle_key("Up", ("Caps_Lock",)) is True

    assert app.speech_controller.settings.rate == 1.1
    assert speech.messages == [
        "Speech mode on-demand",
        "Speech mode off",
    ]


def test_documented_command_shortcuts_are_handled() -> None:
    speech = NullSpeechDriver()
    backend = StoppableBackend()
    app = ScreenReaderApplication(
        dry_run=True,
        accessibility_backend=backend,
        speech_driver=speech,
    )

    assert app.handle_key("s", ("Caps_Lock",)) is True
    assert app.handle_key("n", ("Caps_Lock",)) is True
    assert app.handle_key("1", ("Caps_Lock",)) is True
    assert app.handle_key("F2", ("Caps_Lock",)) is True
    assert app.handle_key("q", ("Caps_Lock",)) is True
    assert app.handle_key("Shift_L") is True

    assert backend.stopped is True
    assert app.quit_requested is True
    assert speech.messages == [
        "Speech mode on-demand",
        "Menu unavailable",
        "Input help",
        "capslock+f2 send the next key directly to the app",
        "Audioability exiting",
        "Pause speech unavailable",
    ]


def test_pass_next_key_lets_one_key_through() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.handle_key("F2", ("Caps_Lock",)) is True
    assert app.handle_key("Tab", ("Caps_Lock",)) is False
    assert app.handle_key("Tab", ("Caps_Lock",)) is True

    assert speech.messages == [
        "Search entry",
        "Pass next key",
        "Search entry",
    ]


def test_input_help_announces_next_shortcut_without_running_it() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    app._speak_focused_node(AccessibleNode(name="Search", role="entry"))

    assert app.handle_key("1", ("Caps_Lock",)) is True
    assert app.handle_key("Tab", ("Caps_Lock",)) is True

    assert speech.messages == [
        "Search entry",
        "Input help",
        "capslock+tab read the currently focused control",
    ]


def test_capslock_numpad_keys_navigate_objects_like_nvda_desktop_layout() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    first = AccessibleNode(name="First", role="button")
    second = AccessibleNode(name="Second", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first, second))
    app.object_navigator.set_root(root)

    assert app.handle_modifier_numpad("capslock", "numpad2") is True
    assert app.handle_modifier_numpad("capslock", "numpad6") is True
    assert app.handle_modifier_numpad("capslock", "numpad4") is True
    assert app.handle_modifier_numpad("capslock", "numpad8") is True
    assert app.handle_modifier_numpad("capslock", "numpad5") is True

    assert speech.messages == [
        "First button",
        "Second button",
        "First button",
        "Window frame 2 items",
        "Window frame 2 items",
    ]


def test_key_handler_routes_modifier_numpad_navigation() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    root = AccessibleNode(
        name="Window",
        role="frame",
        children=(AccessibleNode(name="First", role="button"),),
    )
    app.object_navigator.set_root(root)

    assert app.handle_key("Numpad2", ("Caps_Lock",)) is True

    assert speech.messages == ["First button"]


def test_key_handler_routes_linux_keypad_names() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    first = AccessibleNode(name="First", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first,))
    app.object_navigator.set_root(root)

    assert app.handle_key("KP_Down", ("Caps_Lock",)) is True
    assert app.handle_key("KP_Subtract", ("Caps_Lock",)) is True
    assert app.handle_key("KP_Enter", ("Caps_Lock",)) is True

    assert speech.messages == [
        "First button",
        "Window frame 1 item",
        "No action",
    ]


def test_key_handler_routes_modifier_arrow_speech_settings() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)

    assert app.handle_key("Right", ("Caps_Lock",)) is True

    assert speech.messages == ["Volume 100 percent"]


def test_insert_numpad_keys_navigate_objects_like_capslock() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    root = AccessibleNode(
        name="Window",
        role="frame",
        children=(AccessibleNode(name="First", role="button"),),
    )
    app.object_navigator.set_root(root)

    assert app.handle_modifier_numpad("insert", "numpad2") is True

    assert speech.messages == ["First button"]


def test_router_object_next_runs_object_navigation_action() -> None:
    speech = NullSpeechDriver()
    app = ScreenReaderApplication(dry_run=True, speech_driver=speech)
    root = AccessibleNode(
        name="Window",
        role="frame",
        children=(
            AccessibleNode(name="First", role="button"),
            AccessibleNode(name="Second", role="button"),
        ),
    )
    app.object_navigator.set_root(root)

    assert app.navigate_object(ObjectNavigationAction.MOVE_TO_FIRST_CHILD) is True
    assert app.router.run("object-next") is True

    assert speech.messages == ["First button", "Second button"]
