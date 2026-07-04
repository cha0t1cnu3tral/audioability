from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

SCREEN_READER_MODIFIER_KEYS = ("capslock", "insert")
KEY_ALIASES = {
    "capslock": "capslock",
    "control": "control",
    "controll": "control",
    "controlr": "control",
    "ctrl": "control",
    "leftcontrol": "control",
    "rightcontrol": "control",
    "shift": "shift",
    "shiftl": "shift",
    "shiftr": "shift",
    "leftshift": "shift",
    "rightshift": "shift",
    "insert": "insert",
    "ins": "insert",
    "spacebar": "space",
    "spacekey": "space",
    "kp2": "numpad2",
    "kpdown": "numpad2",
    "kp3": "numpad3",
    "kpnext": "numpad3",
    "kppagedown": "numpad3",
    "kp4": "numpad4",
    "kpleft": "numpad4",
    "kp5": "numpad5",
    "kpbegin": "numpad5",
    "kp6": "numpad6",
    "kpright": "numpad6",
    "kp8": "numpad8",
    "kpup": "numpad8",
    "kp9": "numpad9",
    "kpprior": "numpad9",
    "kppageup": "numpad9",
    "kpenter": "numpadenter",
    "kpminus": "numpadminus",
    "kpsubtract": "numpadminus",
    "return": "enter",
    "escape": "esc",
}


class CommandName(StrEnum):
    QUIT = "quit"
    OPEN_MENU = "open-menu"
    INPUT_HELP = "input-help"
    PASS_NEXT_KEY = "pass-next-key"
    READ_FOCUS = "read-focus"
    READ_TITLE = "read-title"
    READ_WINDOW = "read-window"
    READ_STATUS_BAR = "read-status-bar"
    TOGGLE_BROWSE_FOCUS_MODE = "toggle-browse-focus-mode"
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
    CommandBinding(
        name=CommandName.TOGGLE_BROWSE_FOCUS_MODE,
        desktop_key="sr+space",
        laptop_key="sr+space",
        meaning="toggle between browse mode and focus mode",
    ),
)


def command_for_key(key: str) -> Command | None:
    return command_for_gesture((key,))


def command_for_gesture(keys: Iterable[str]) -> Command | None:
    normalized_keys = frozenset(filter(None, (normalize_key(key) for key in keys)))
    if not normalized_keys:
        return None

    for binding in DEFAULT_COMMAND_BINDINGS:
        if _binding_matches(binding.desktop_key, normalized_keys) or _binding_matches(
            binding.laptop_key,
            normalized_keys,
        ):
            return Command(binding.name, binding.meaning)

    return None


def is_screen_reader_modifier(key: str) -> bool:
    return normalize_key(key) in SCREEN_READER_MODIFIER_KEYS


def _binding_matches(binding_key: str, keys: frozenset[str]) -> bool:
    binding_parts = frozenset(normalize_key(part) for part in binding_key.split("+"))
    if "sr" not in binding_parts:
        return binding_parts == keys

    required_keys = binding_parts - {"sr"}
    pressed_reader_modifiers = keys.intersection(SCREEN_READER_MODIFIER_KEYS)
    return bool(pressed_reader_modifiers) and keys - pressed_reader_modifiers == required_keys


def normalize_key(key: str) -> str:
    normalized = key.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    return KEY_ALIASES.get(normalized, normalized)
