from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessibleNode:
    name: str
    role: str
    description: str = ""
    state: frozenset[str] = frozenset()
