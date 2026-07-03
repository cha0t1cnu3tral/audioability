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


def test_atspi_backend_reads_richer_accessible_properties_and_children() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)
    child = SimpleNamespace(
        name="Advanced",
        description="",
        childCount=0,
        getRoleName=lambda: "check box",
        getState=lambda: FakeStateSet("checked"),
    )
    source = SimpleNamespace(
        name="Volume",
        description="Master output volume",
        childCount=1,
        getAttributes=lambda: ["placeholder-text:Set volume"],
        getChildAtIndex=lambda index: child if index == 0 else None,
        getRoleName=lambda: "slider",
        getState=lambda: FakeStateSet("focused", "focusable", "enabled"),
        queryAction=lambda: SimpleNamespace(nActions=1, getKeyBinding=lambda index: "Alt+V"),
        queryText=lambda: SimpleNamespace(characterCount=7, getText=lambda start, end: "Volume"),
        queryValue=lambda: SimpleNamespace(currentValue=75.0),
    )

    backend._handle_event(SimpleNamespace(source=source))

    assert nodes == [
        AccessibleNode(
            name="Volume",
            role="slider",
            description="Master output volume",
            value="75",
            text="Volume",
            placeholder="Set volume",
            shortcut="Alt+V",
            state=frozenset({"enabled", "focusable", "focused"}),
            child_count=1,
            children=(
                AccessibleNode(
                    name="Advanced",
                    role="check box",
                    state=frozenset({"checked"}),
                ),
            ),
        )
    ]


def test_atspi_backend_reads_children_from_indexable_container() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)
    child = SimpleNamespace(
        name="Play",
        childCount=0,
        getRoleName=lambda: "button",
    )
    source = FakeIndexableAccessible(
        child,
        name="",
        description="",
        childCount=1,
        getRoleName=lambda: "container",
    )

    backend._handle_event(SimpleNamespace(source=source))

    assert nodes == [
        AccessibleNode(
            name="",
            role="container",
            child_count=1,
            children=(AccessibleNode(name="Play", role="button"),),
        )
    ]


def test_atspi_backend_ignores_focus_event_without_handler() -> None:
    backend = AtSpiAccessibilityBackend()

    backend._handle_event(SimpleNamespace(source=SimpleNamespace()))


def test_atspi_backend_filters_focus_lost_event() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)
    source = SimpleNamespace(
        name="Submit",
        description="Submit the form",
        getRoleName=lambda: "push button",
    )

    backend._handle_event(SimpleNamespace(source=source, detail1=0))

    assert nodes == []


class FakeStateSet:
    def __init__(self, *states: str) -> None:
        self._states = states

    def getStates(self) -> tuple[str, ...]:
        return self._states


class FakeIndexableAccessible(SimpleNamespace):
    def __init__(self, *children: object, **attributes: object) -> None:
        super().__init__(**attributes)
        self._children = children

    def __getitem__(self, index: int) -> object:
        return self._children[index]


def test_atspi_backend_filters_event_without_speakable_text() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)

    backend._handle_event(SimpleNamespace(source=SimpleNamespace(), detail1=1))

    assert nodes == []
