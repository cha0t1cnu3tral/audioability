from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from audioability.accessibility.models import AccessibleNode


class FocusEventFilter:
    """Filters noisy focus events before they reach speech."""

    def __init__(
        self,
        *,
        duplicate_window_seconds: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._duplicate_window_seconds = duplicate_window_seconds
        self._clock = clock
        self._last_node: AccessibleNode | None = None
        self._last_accepted_at: float | None = None

    def accepts(self, event: Any, node: AccessibleNode) -> bool:
        if self._is_focus_lost_event(event):
            return False
        if not self._has_speakable_text(node):
            return False

        now = self._clock()
        if self._is_duplicate(node, now):
            return False

        self._last_node = node
        self._last_accepted_at = now
        return True

    def _is_duplicate(self, node: AccessibleNode, now: float) -> bool:
        if self._last_accepted_at is None:
            return False
        if node != self._last_node:
            return False

        return now - self._last_accepted_at < self._duplicate_window_seconds

    @staticmethod
    def _is_focus_lost_event(event: Any) -> bool:
        event_type = getattr(event, "type", "")
        if (
            isinstance(event_type, str)
            and event_type
            and "state-changed:focused" not in event_type
        ):
            return False
        detail1 = getattr(event, "detail1", None)
        return isinstance(detail1, int) and detail1 == 0

    @staticmethod
    def _has_speakable_text(node: AccessibleNode) -> bool:
        return any(
            (
                node.name,
                node.role,
                node.description,
                node.value,
                node.text,
                node.placeholder,
                node.shortcut,
            )
        ) or any(FocusEventFilter._has_speakable_text(child) for child in node.children)
