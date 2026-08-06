from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaretNavigation:
    """Text and input gesture associated with a system-caret movement."""

    text: str
    offset: int
    key: str
    modifiers: tuple[str, ...] = ()
    password: bool = False


@dataclass(frozen=True)
class AccessibleNode:
    name: str
    role: str
    description: str = ""
    value: str = ""
    text: str = ""
    placeholder: str = ""
    shortcut: str = ""
    attributes: tuple[str, ...] = ()
    state: frozenset[str] = frozenset()
    child_count: int = 0
    children: tuple[AccessibleNode, ...] = ()
    activation: Callable[[], bool] | None = field(default=None, repr=False, compare=False)
    focus_action: Callable[[], bool] | None = field(default=None, repr=False, compare=False)

    def activate(self) -> bool:
        if self.activation is None or "disabled" in self.state:
            return False

        return self.activation()

    def focus(self) -> bool:
        if self.focus_action is None:
            return False

        return self.focus_action()
