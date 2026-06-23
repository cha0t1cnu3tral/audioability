from __future__ import annotations

from typing import Protocol


class AccessibilityBackend(Protocol):
    """Interface for desktop accessibility event sources."""

    def start(self) -> None:
        """Connect to desktop accessibility services and start listening."""


class NullAccessibilityBackend:
    """No-op backend for tests and non-Linux development environments."""

    def start(self) -> None:
        return None


class AtSpiAccessibilityBackend:
    """AT-SPI backend placeholder.

    The implementation will live here so platform-specific imports do not leak
    into the rest of the screen reader.
    """

    def start(self) -> None:
        raise NotImplementedError("AT-SPI integration has not been implemented yet.")
