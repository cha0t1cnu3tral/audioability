from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AccessibleNode:
    name: str
    role: str
    description: str = ""
    value: str = ""
    text: str = ""
    placeholder: str = ""
    shortcut: str = ""
    state: frozenset[str] = frozenset()
    child_count: int = 0
    children: tuple[AccessibleNode, ...] = ()
    activation: Callable[[], bool] | None = field(default=None, repr=False, compare=False)

    def activate(self) -> bool:
        if self.activation is None:
            return False

        return self.activation()
