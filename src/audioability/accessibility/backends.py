from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from audioability.accessibility.models import AccessibleNode


class AccessibilityBackend(Protocol):
    """Interface for desktop accessibility event sources."""

    def start(self) -> None:
        """Connect to desktop accessibility services and start listening."""


class AccessibilityBackendUnavailableError(RuntimeError):
    """Raised when a platform accessibility backend cannot be loaded."""


class NullAccessibilityBackend:
    """No-op backend for tests and non-Linux development environments."""

    def start(self) -> None:
        return None


class AtSpiAccessibilityBackend:
    """AT-SPI backend for Linux desktop accessibility events."""

    def __init__(
        self,
        *,
        event_types: Sequence[str] = ("object:state-changed:focused",),
        on_focus: Callable[[AccessibleNode], None] | None = None,
    ) -> None:
        self.event_types = tuple(event_types)
        self.on_focus = on_focus

    def start(self) -> None:
        try:
            import pyatspi  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AccessibilityBackendUnavailableError(
                "AT-SPI support is unavailable. Install python3-pyatspi and at-spi2-core."
            ) from exc

        for event_type in self.event_types:
            pyatspi.Registry.registerEventListener(self._handle_event, event_type)

        pyatspi.Registry.start()

    def _handle_event(self, event: Any) -> None:
        if self.on_focus is None:
            return

        source = event.source
        self.on_focus(
            AccessibleNode(
                name=self._read_text_attribute(source, "name"),
                role=self._read_role(source),
                description=self._read_text_attribute(source, "description"),
            )
        )

    @staticmethod
    def _read_text_attribute(source: Any, attribute: str) -> str:
        value = getattr(source, attribute, "")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _read_role(source: Any) -> str:
        get_role_name = getattr(source, "getRoleName", None)
        if not callable(get_role_name):
            return ""

        role = get_role_name()
        return role if isinstance(role, str) else ""
