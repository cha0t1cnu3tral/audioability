from __future__ import annotations

from dataclasses import dataclass


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
