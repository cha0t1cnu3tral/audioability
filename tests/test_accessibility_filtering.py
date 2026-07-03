from __future__ import annotations

from types import SimpleNamespace

from audioability.accessibility.filtering import FocusEventFilter
from audioability.accessibility.models import AccessibleNode


def test_filter_rejects_focus_lost_event() -> None:
    event_filter = FocusEventFilter()
    node = AccessibleNode(name="Submit", role="push button")

    assert event_filter.accepts(SimpleNamespace(detail1=0), node) is False


def test_filter_rejects_node_without_speakable_text() -> None:
    event_filter = FocusEventFilter()
    node = AccessibleNode(name="", role="", description="")

    assert event_filter.accepts(SimpleNamespace(detail1=1), node) is False


def test_filter_accepts_container_with_speakable_child() -> None:
    event_filter = FocusEventFilter()
    node = AccessibleNode(
        name="",
        role="",
        description="",
        children=(AccessibleNode(name="Play", role="button"),),
    )

    assert event_filter.accepts(SimpleNamespace(detail1=1), node) is True


def test_filter_rejects_immediate_duplicate_focus_event() -> None:
    now = 10.0
    event_filter = FocusEventFilter(clock=lambda: now)
    event = SimpleNamespace(detail1=1)
    node = AccessibleNode(name="Submit", role="push button")

    assert event_filter.accepts(event, node) is True
    assert event_filter.accepts(event, node) is False


def test_filter_allows_duplicate_after_window() -> None:
    now = 10.0

    def clock() -> float:
        return now

    event_filter = FocusEventFilter(duplicate_window_seconds=0.25, clock=clock)
    event = SimpleNamespace(detail1=1)
    node = AccessibleNode(name="Submit", role="push button")

    assert event_filter.accepts(event, node) is True
    now = 10.3

    assert event_filter.accepts(event, node) is True
