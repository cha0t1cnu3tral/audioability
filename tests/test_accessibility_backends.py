from __future__ import annotations

from types import SimpleNamespace

from audioability.accessibility.backends import AtSpiAccessibilityBackend
from audioability.accessibility.models import AccessibleNode


def test_atspi_backend_converts_focus_event_to_accessible_node() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)
    source = SimpleNamespace(
        name="Submit",
        description="Submit the form",
        getRoleName=lambda: "push button",
    )

    backend._handle_event(SimpleNamespace(source=source))

    assert nodes == [
        AccessibleNode(
            name="Submit",
            role="push button",
            description="Submit the form",
        )
    ]


def test_atspi_backend_ignores_focus_event_without_handler() -> None:
    backend = AtSpiAccessibilityBackend()

    backend._handle_event(SimpleNamespace(source=SimpleNamespace()))
