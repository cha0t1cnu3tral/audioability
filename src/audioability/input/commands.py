from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommandName(StrEnum):
    QUIT = "quit"
    READ_FOCUS = "read-focus"
    READ_WINDOW = "read-window"


@dataclass(frozen=True)
class Command:
    name: CommandName
    description: str
