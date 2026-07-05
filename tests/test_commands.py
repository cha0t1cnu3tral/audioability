from __future__ import annotations

from audioability.input.commands import (
    DEFAULT_COMMAND_BINDINGS,
    SCREEN_READER_MODIFIER_KEYS,
    CommandName,
    command_for_gesture,
    command_for_key,
    is_screen_reader_modifier,
)


def test_screen_reader_modifier_is_capslock_or_insert() -> None:
    assert SCREEN_READER_MODIFIER_KEYS == ("capslock", "insert")
    assert is_screen_reader_modifier("capslock") is True
    assert is_screen_reader_modifier("Caps_Lock") is True
    assert is_screen_reader_modifier("insert") is True
    assert is_screen_reader_modifier("shift") is False


def test_default_command_bindings_include_requested_commands() -> None:
    bindings = {binding.name: binding for binding in DEFAULT_COMMAND_BINDINGS}

    assert bindings[CommandName.STOP_SPEECH].desktop_key == "control"
    assert bindings[CommandName.PAUSE_SPEECH].desktop_key == "shift"
    assert bindings[CommandName.CYCLE_SPEECH_MODE].desktop_key == "sr+s"
    assert (
        bindings[CommandName.CYCLE_SPEECH_MODE].meaning
        == "cycle speech mode between talk, on-demand, and off"
    )
    assert bindings[CommandName.OPEN_MENU].desktop_key == "sr+n"
    assert bindings[CommandName.INPUT_HELP].desktop_key == "sr+1"
    assert bindings[CommandName.PASS_NEXT_KEY].desktop_key == "sr+f2"
    assert bindings[CommandName.QUIT].desktop_key == "sr+q"
    assert bindings[CommandName.READ_FOCUS].desktop_key == "sr+tab"
    assert bindings[CommandName.READ_TITLE].desktop_key == "sr+t"
    assert bindings[CommandName.READ_WINDOW].desktop_key == "sr+b"
    assert bindings[CommandName.READ_STATUS_BAR].desktop_key == "sr+end"
    assert bindings[CommandName.READ_STATUS_BAR].laptop_key == "sr+shift+end"
    assert bindings[CommandName.TOGGLE_BROWSE_FOCUS_MODE].desktop_key == "sr+space"


def test_control_key_maps_to_stop_speech_command() -> None:
    command = command_for_key("control")
    assert command is not None
    assert command.name is CommandName.STOP_SPEECH

    left_control_command = command_for_key("Control_L")
    assert left_control_command is not None
    assert left_control_command.name is CommandName.STOP_SPEECH

    ctrl_command = command_for_key("ctrl")
    assert ctrl_command is not None
    assert ctrl_command.name is CommandName.STOP_SPEECH

    pause_command = command_for_key("shift")
    assert pause_command is not None
    assert pause_command.name is CommandName.PAUSE_SPEECH


def test_screen_reader_gestures_map_to_commands() -> None:
    read_focus = command_for_gesture(("Caps_Lock", "Tab"))
    assert read_focus is not None
    assert read_focus.name is CommandName.READ_FOCUS

    read_window = command_for_gesture(("Insert", "b"))
    assert read_window is not None
    assert read_window.name is CommandName.READ_WINDOW

    status_bar = command_for_gesture(("Caps_Lock", "End"))
    assert status_bar is not None
    assert status_bar.name is CommandName.READ_STATUS_BAR

    laptop_status_bar = command_for_gesture(("Insert", "Shift_L", "End"))
    assert laptop_status_bar is not None
    assert laptop_status_bar.name is CommandName.READ_STATUS_BAR

    toggle_mode = command_for_gesture(("Caps_Lock", "Space"))
    assert toggle_mode is not None
    assert toggle_mode.name is CommandName.TOGGLE_BROWSE_FOCUS_MODE

    toggle_mode_spacebar = command_for_gesture(("Insert", "spacebar"))
    assert toggle_mode_spacebar is not None
    assert toggle_mode_spacebar.name is CommandName.TOGGLE_BROWSE_FOCUS_MODE


def test_unbound_gesture_returns_none() -> None:
    assert command_for_gesture(("Alt", "F4")) is None
