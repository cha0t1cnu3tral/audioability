from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

SCREEN_READER_MODIFIER_KEYS = ("capslock", "insert")


class CommandName(StrEnum):
    QUIT = "quit"
    OPEN_MENU = "open-menu"
    INPUT_HELP = "input-help"
    PASS_NEXT_KEY = "pass-next-key"
    READ_FOCUS = "read-focus"
    READ_TITLE = "read-title"
    READ_WINDOW = "read-window"
    READ_STATUS_BAR = "read-status-bar"
    REPEAT_LAST = "repeat-last"
    PAUSE_SPEECH = "pause-speech"
    CYCLE_SPEECH_MODE = "cycle-speech-mode"
    STOP_SPEECH = "stop-speech"


@dataclass(frozen=True)
class Command:
    name: CommandName
    description: str


@dataclass(frozen=True)
class CommandBinding:
    name: CommandName
    desktop_key: str
    laptop_key: str
    meaning: str


DEFAULT_COMMAND_BINDINGS = (
    CommandBinding(
        name=CommandName.STOP_SPEECH,
        desktop_key="control",
        laptop_key="control",
        meaning="stop current speech",
    ),
    CommandBinding(
        name=CommandName.PAUSE_SPEECH,
        desktop_key="shift",
        laptop_key="shift",
        meaning="pause or resume speech if supported",
    ),
    CommandBinding(
        name=CommandName.CYCLE_SPEECH_MODE,
        desktop_key="sr+s",
        laptop_key="sr+s",
        meaning="cycle speech mode, such as talk, beeps, off, or on-demand",
    ),
    CommandBinding(
        name=CommandName.OPEN_MENU,
        desktop_key="sr+n",
        laptop_key="sr+n",
        meaning="open screenreader menu or settings",
    ),
    CommandBinding(
        name=CommandName.INPUT_HELP,
        desktop_key="sr+1",
        laptop_key="sr+1",
        meaning="hear what command a key runs",
    ),
    CommandBinding(
        name=CommandName.PASS_NEXT_KEY,
        desktop_key="sr+f2",
        laptop_key="sr+f2",
        meaning="send the next key directly to the app",
    ),
    CommandBinding(
        name=CommandName.QUIT,
        desktop_key="sr+q",
        laptop_key="sr+q",
        meaning="quit the screenreader",
    ),
    CommandBinding(
        name=CommandName.READ_FOCUS,
        desktop_key="sr+tab",
        laptop_key="sr+tab",
        meaning="read the currently focused control",
    ),
    CommandBinding(
        name=CommandName.READ_TITLE,
        desktop_key="sr+t",
        laptop_key="sr+t",
        meaning="read the current window title",
    ),
    CommandBinding(
        name=CommandName.READ_WINDOW,
        desktop_key="sr+b",
        laptop_key="sr+b",
        meaning="read the active window or dialog",
    ),
    CommandBinding(
        name=CommandName.READ_STATUS_BAR,
        desktop_key="sr+end",
        laptop_key="sr+shift+end",
        meaning="read the status bar if available",
    ),
)


def command_for_key(key: str) -> Command | None:
    normalized = _normalize_key(key)
    if normalized in {"control", "ctrl", "controll", "controlr", "leftcontrol", "rightcontrol"}:
        return Command(CommandName.STOP_SPEECH, "Stop current speech.")

    return None


def is_screen_reader_modifier(key: str) -> bool:
    return _normalize_key(key) in SCREEN_READER_MODIFIER_KEYS


def _normalize_key(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")
