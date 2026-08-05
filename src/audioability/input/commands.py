from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

SCREEN_READER_MODIFIER_KEYS = ("capslock", "insert")
MODIFIER_KEYS = frozenset(
    {
        *SCREEN_READER_MODIFIER_KEYS,
        "alt",
        "altgr",
        "control",
        "meta",
        "shift",
        "super",
    }
)
KEY_ALIASES = {
    "alt": "alt",
    "altl": "alt",
    "altr": "alt",
    "leftalt": "alt",
    "rightalt": "alt",
    "isolevel3shift": "altgr",
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
    "kp0": "insert",
    "kpinsert": "insert",
    "numpad0": "insert",
    "numpadinsert": "insert",
    "meta": "meta",
    "metal": "meta",
    "metar": "meta",
    "leftmeta": "meta",
    "rightmeta": "meta",
    "super": "super",
    "superl": "super",
    "superr": "super",
    "leftsuper": "super",
    "rightsuper": "super",
    "win": "super",
    "windows": "super",
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

# AT-SPI's device API reports a numeric X keysym separately from the text a key
# would insert.  The text is empty for most command keys, so relying on it makes
# Tab, arrows, function keys, and the screen-reader modifiers disappear.  Keep
# the small, stable subset of X keysyms used by Audioability here rather than
# requiring a particular GTK/GDK version just to name a key.
KEY_NAME_TO_KEYSYM = {
    "backspace": 0xFF08,
    "tab": 0xFF09,
    "enter": 0xFF0D,
    "pause": 0xFF13,
    "esc": 0xFF1B,
    "home": 0xFF50,
    "left": 0xFF51,
    "up": 0xFF52,
    "right": 0xFF53,
    "down": 0xFF54,
    "pageup": 0xFF55,
    "pagedown": 0xFF56,
    "end": 0xFF57,
    "insert": 0xFF63,
    "numlock": 0xFF7F,
    "numpadenter": 0xFF8D,
    "numpad7": 0xFF95,
    "numpad4": 0xFF96,
    "numpad8": 0xFF97,
    "numpad6": 0xFF98,
    "numpad2": 0xFF99,
    "numpad9": 0xFF9A,
    "numpad3": 0xFF9B,
    "numpad1": 0xFF9C,
    "numpad5": 0xFF9D,
    "numpadinsert": 0xFF9E,
    "numpadminus": 0xFFAD,
    "shiftl": 0xFFE1,
    "shiftr": 0xFFE2,
    "controll": 0xFFE3,
    "controlr": 0xFFE4,
    "capslock": 0xFFE5,
    "metal": 0xFFE7,
    "metar": 0xFFE8,
    "altl": 0xFFE9,
    "altr": 0xFFEA,
    "superl": 0xFFEB,
    "superr": 0xFFEC,
    "delete": 0xFFFF,
    "altgr": 0xFE03,
}

KEYSYM_TO_KEY_NAME = {keysym: name for name, keysym in KEY_NAME_TO_KEYSYM.items()}


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
        meaning="cycle speech mode between talk, on-demand, and off",
    ),
    CommandBinding(
        name=CommandName.OPEN_MENU,
        desktop_key="sr+n",
        laptop_key="sr+n",
        meaning="list Audioability commands",
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
    CommandBinding(
        name=CommandName.REPEAT_LAST,
        desktop_key="sr+r",
        laptop_key="sr+r",
        meaning="repeat the last spoken message",
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


def is_modifier_key(key: str) -> bool:
    return normalize_key(key) in MODIFIER_KEYS


def command_binding_lines() -> tuple[str, ...]:
    lines: list[str] = []
    for binding in DEFAULT_COMMAND_BINDINGS:
        if binding.desktop_key == binding.laptop_key:
            gesture = binding.desktop_key
        else:
            gesture = f"{binding.desktop_key} desktop, {binding.laptop_key} laptop"
        lines.append(f"{gesture}: {binding.meaning}")

    return tuple(lines)


def format_command_bindings() -> str:
    rows = [
        ("Desktop", "Laptop", "Action"),
        *(
            (binding.desktop_key, binding.laptop_key, binding.meaning)
            for binding in DEFAULT_COMMAND_BINDINGS
        ),
    ]
    widths = tuple(max(len(row[index]) for row in rows) for index in range(3))
    return "\n".join(
        f"{desktop:<{widths[0]}}  {laptop:<{widths[1]}}  {meaning}"
        for desktop, laptop, meaning in rows
    )


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


def keysym_for_key(key: str) -> int | None:
    """Return the X keysym used by AT-SPI for a normalized key name."""

    raw_name = key.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    raw_aliases = {
        "kpinsert": "numpadinsert",
        "kpenter": "numpadenter",
        "kpsubtract": "numpadminus",
    }
    direct_name = raw_aliases.get(raw_name, raw_name)
    if direct_name in KEY_NAME_TO_KEYSYM:
        return KEY_NAME_TO_KEYSYM[direct_name]

    normalized = normalize_key(key)
    if len(normalized) == 1 and normalized.isprintable():
        return ord(normalized)
    if normalized == "space":
        return ord(" ")
    if normalized.startswith("f") and normalized[1:].isdigit():
        function_number = int(normalized[1:])
        if 1 <= function_number <= 35:
            return 0xFFBD + function_number

    aliases = {
        "shift": "shiftl",
        "control": "controll",
        "alt": "altl",
        "meta": "metal",
        "super": "superl",
        "numpad0": "numpadinsert",
    }
    return KEY_NAME_TO_KEYSYM.get(aliases.get(normalized, normalized))


def key_from_keysym(keysym: int, text: str = "") -> str:
    """Return the key name for an AT-SPI device event."""

    if keysym in KEYSYM_TO_KEY_NAME:
        return KEYSYM_TO_KEY_NAME[keysym]
    if 0xFFBE <= keysym <= 0xFFE0:
        return f"f{keysym - 0xFFBD}"
    if 0xFFB0 <= keysym <= 0xFFB9:
        return f"numpad{keysym - 0xFFB0}"
    if 0x20 <= keysym <= 0x7E:
        return "space" if keysym == ord(" ") else chr(keysym)
    if keysym & 0xFF000000 == 0x01000000:
        codepoint = keysym & 0x00FFFFFF
        if codepoint <= 0x10FFFF:
            return chr(codepoint)

    if text == " ":
        return "space"
    return text.strip()
