from __future__ import annotations

import sys
from types import SimpleNamespace

from pytest import MonkeyPatch

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


def test_atspi_backend_exposes_default_action_activation() -> None:
    activated_indexes: list[int] = []
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)

    def do_action(index: int) -> bool:
        activated_indexes.append(index)
        return True

    source = SimpleNamespace(
        name="Submit",
        description="",
        getRoleName=lambda: "button",
        queryAction=lambda: SimpleNamespace(
            nActions=1,
            doAction=do_action,
        ),
    )

    backend._handle_event(SimpleNamespace(source=source))

    assert nodes[0].activate() is True
    assert activated_indexes == [0]


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


def test_atspi_backend_dispatches_focus_tree_with_focused_node() -> None:
    focus_events: list[tuple[AccessibleNode, AccessibleNode]] = []

    def on_focus_tree(root: AccessibleNode, focused: AccessibleNode) -> None:
        focus_events.append((root, focused))

    focused_source = FakeTreeAccessible(name="Search", role="entry")
    sibling_source = FakeTreeAccessible(name="Cancel", role="button")
    panel_source = FakeTreeAccessible(
        focused_source,
        sibling_source,
        name="Controls",
        role="panel",
    )
    FakeTreeAccessible(panel_source, name="Settings", role="frame")
    backend = AtSpiAccessibilityBackend(on_focus_tree=on_focus_tree)

    backend._handle_event(SimpleNamespace(source=focused_source, detail1=1))

    root, focused = focus_events[0]
    assert root == AccessibleNode(
        name="Settings",
        role="frame",
        child_count=1,
        children=(
            AccessibleNode(
                name="Controls",
                role="panel",
                child_count=2,
                children=(
                    AccessibleNode(name="Search", role="entry"),
                    AccessibleNode(name="Cancel", role="button"),
                ),
            ),
        ),
    )
    assert focused == root.children[0].children[0]


def test_atspi_backend_dispatches_key_events_with_pressed_modifiers() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)

    assert (
        backend._handle_key_event(SimpleNamespace(event_string="Caps_Lock", type="PRESS"))
        is True
    )
    assert backend._handle_key_event(SimpleNamespace(event_string="Tab", type="PRESS")) is True
    assert (
        backend._handle_key_event(
            SimpleNamespace(event_string="Caps_Lock", type="KEY_RELEASED_EVENT")
        )
        is False
    )
    assert backend._handle_key_event(SimpleNamespace(event_string="Tab", type="PRESS")) is True

    assert key_events == [
        ("Caps_Lock", ()),
        ("Tab", ("capslock",)),
        ("Tab", ()),
    ]


def test_atspi_backend_recognizes_numeric_key_release_constants(monkeypatch: MonkeyPatch) -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    monkeypatch.setitem(sys.modules, "pyatspi", SimpleNamespace(KEY_RELEASED_EVENT=1))
    backend = AtSpiAccessibilityBackend(on_key=on_key)

    assert backend._handle_key_event(SimpleNamespace(event_string="Caps_Lock", type=0)) is True
    assert backend._handle_key_event(SimpleNamespace(event_string="Caps_Lock", type=1)) is False
    assert backend._handle_key_event(SimpleNamespace(event_string="Tab", type=0)) is True

    assert key_events == [
        ("Caps_Lock", ()),
        ("Tab", ()),
    ]


def test_atspi_backend_ignores_empty_key_events() -> None:
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    assert backend._handle_key_event(SimpleNamespace(type="PRESS")) is False


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


class FakeTreeAccessible(SimpleNamespace):
    def __init__(self, *children: FakeTreeAccessible, name: str, role: str) -> None:
        super().__init__(
            name=name,
            description="",
            childCount=len(children),
            parent=None,
        )
        self._role = role
        self._children = children
        self._parent: FakeTreeAccessible | None = None
        for child in children:
            child._parent = self
            child.parent = self

    def getRoleName(self) -> str:
        return self._role

    def getChildAtIndex(self, index: int) -> FakeTreeAccessible:
        return self._children[index]

    def getIndexInParent(self) -> int:
        if self._parent is None:
            return -1

        return self._parent._children.index(self)


def test_atspi_backend_filters_event_without_speakable_text() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)

    backend._handle_event(SimpleNamespace(source=SimpleNamespace(), detail1=1))

    assert nodes == []
