from __future__ import annotations

import sys
from types import SimpleNamespace

from pytest import MonkeyPatch

from audioability.accessibility.backends import AtSpiAccessibilityBackend
from audioability.accessibility.models import AccessibleNode


def test_atspi_backend_fallback_registers_global_keys_for_every_modifier_mask(
    monkeypatch: MonkeyPatch,
) -> None:
    keystroke_registrations: list[dict[str, object]] = []

    class FakeRegistry:
        @staticmethod
        def registerEventListener(callback: object, event_type: str) -> None:
            return None

        @staticmethod
        def registerKeystrokeListener(callback: object, **options: object) -> None:
            keystroke_registrations.append(options)

        @staticmethod
        def start() -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "pyatspi",
        SimpleNamespace(
            Registry=FakeRegistry,
            KEY_PRESSED_EVENT=1,
            KEY_RELEASED_EVENT=2,
        ),
    )
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    backend.start()

    assert keystroke_registrations == [
        {
            "mask": tuple(range(256)),
            "kind": (1, 2),
            "global_": True,
        }
    ]


def test_atspi_backend_prefers_global_device_signals(monkeypatch: MonkeyPatch) -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []
    legacy_registrations: list[dict[str, object]] = []

    class FakeKeyDefinition:
        keysym = 0
        modifiers = 0

    class FakeDevice:
        def __init__(self) -> None:
            self.callbacks: dict[str, object] = {}
            self.grabs: list[tuple[int, int]] = []
            self.mapped: dict[int, int] = {}
            self.disconnected: list[int] = []
            self.removed_grabs: list[int] = []
            self.unmapped: list[int] = []

        def connect(self, signal: str, callback: object) -> int:
            self.callbacks[signal] = callback
            return len(self.callbacks)

        def map_keysym_modifier(self, keysym: int) -> int:
            if keysym not in self.mapped:
                self.mapped[keysym] = 1 << (8 + len(self.mapped))
            return self.mapped[keysym]

        def add_key_grab(self, definition: FakeKeyDefinition, callback: object) -> int:
            assert callback is None
            self.grabs.append((definition.keysym, definition.modifiers))
            return len(self.grabs)

        def remove_key_grab(self, grab_id: int) -> None:
            self.removed_grabs.append(grab_id)

        def unmap_keysym_modifier(self, keysym: int) -> None:
            self.unmapped.append(keysym)

        def disconnect(self, signal_id: int) -> None:
            self.disconnected.append(signal_id)

    device = FakeDevice()
    created_app_ids: list[str] = []

    class FakeDeviceType:
        @staticmethod
        def new_full(app_id: str) -> FakeDevice:
            created_app_ids.append(app_id)
            return device

    class FakeRegistry:
        @staticmethod
        def registerEventListener(callback: object, event_type: str) -> None:
            return None

        @staticmethod
        def registerKeystrokeListener(callback: object, **options: object) -> None:
            legacy_registrations.append(options)

        @staticmethod
        def start() -> None:
            return None

        @staticmethod
        def stop() -> None:
            return None

    fake_atspi = SimpleNamespace(
        Device=FakeDeviceType,
        KeyDefinition=FakeKeyDefinition,
        ModifierType=SimpleNamespace(SHIFT=0, CONTROL=2, ALT=3, META=4, SUPER=6),
        get_version=lambda: (2, 60, 0),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyatspi",
        SimpleNamespace(
            Atspi=fake_atspi,
            Registry=FakeRegistry,
            KEY_PRESSED_EVENT=1,
            KEY_RELEASED_EVENT=2,
        ),
    )

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)

    backend.start()

    assert created_app_ids == ["org.audioability.Audioability"]
    assert legacy_registrations == []
    assert set(device.callbacks) == {"key-pressed", "key-released"}
    capslock_mask = device.mapped[0xFFE5]
    assert (0xFF09, capslock_mask) in device.grabs
    assert (0xFF99, capslock_mask) in device.grabs
    assert (0xFFB2, capslock_mask) in device.grabs
    assert (0xFFE3, 0) not in device.grabs
    initial_grab_count = len(device.grabs)

    pressed = device.callbacks["key-pressed"]
    released = device.callbacks["key-released"]
    assert callable(pressed)
    assert callable(released)
    pressed(device, 66, 0xFFE5, 0, "")
    pressed(device, 23, 0xFF09, capslock_mask, "")
    released(device, 66, 0xFFE5, 0, "")

    assert key_events == [
        ("capslock", ()),
        ("tab", ("capslock",)),
    ]

    backend.pass_next_key()

    assert len(device.removed_grabs) == initial_grab_count
    pressed(device, 66, 0xFFE5, 0, "")
    pressed(device, 23, 0xFF09, capslock_mask, "")
    released(device, 66, 0xFFE5, 0, "")
    assert len(device.grabs) == initial_grab_count * 2

    backend.stop()

    assert device.disconnected == [1, 2]
    assert len(device.removed_grabs) == len(device.grabs)
    assert device.unmapped == [0xFFE5, 0xFF63, 0xFF9E, 0xFFB0]


def test_atspi_backend_uses_device_watcher_on_pre_260_atspi(
    monkeypatch: MonkeyPatch,
) -> None:
    callbacks: list[object] = []

    class FakeDevice:
        def add_key_watcher(self, callback: object) -> None:
            callbacks.append(callback)

    device = FakeDevice()

    class FakeDeviceType:
        @staticmethod
        def new() -> FakeDevice:
            return device

    class FakeRegistry:
        @staticmethod
        def registerEventListener(callback: object, event_type: str) -> None:
            return None

        @staticmethod
        def start() -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "pyatspi",
        SimpleNamespace(
            Atspi=SimpleNamespace(Device=FakeDeviceType, get_version=lambda: (2, 52, 0)),
            Registry=FakeRegistry,
            KEY_PRESSED_EVENT=1,
            KEY_RELEASED_EVENT=2,
        ),
    )
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    backend.start()

    assert callbacks == [backend._handle_device_key_event]


def test_atspi_backend_disconnects_partial_signal_registration(
    monkeypatch: MonkeyPatch,
) -> None:
    disconnected: list[int] = []
    watchers: list[object] = []

    class FakeDevice:
        def connect(self, signal: str, callback: object) -> int:
            if signal == "key-released":
                raise RuntimeError("signal unavailable")
            return 41

        def disconnect(self, signal_id: int) -> None:
            disconnected.append(signal_id)

        def add_key_watcher(self, callback: object) -> None:
            watchers.append(callback)

    device = FakeDevice()

    class FakeDeviceType:
        @staticmethod
        def new_full(app_id: str) -> FakeDevice:
            return device

    class FakeRegistry:
        @staticmethod
        def registerEventListener(callback: object, event_type: str) -> None:
            return None

        @staticmethod
        def start() -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "pyatspi",
        SimpleNamespace(
            Atspi=SimpleNamespace(Device=FakeDeviceType, get_version=lambda: (2, 60, 0)),
            Registry=FakeRegistry,
            KEY_PRESSED_EVENT=1,
            KEY_RELEASED_EVENT=2,
        ),
    )
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    backend.start()

    assert disconnected == [41]
    assert watchers == [backend._handle_device_key_event]


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


def test_atspi_backend_tracks_keypad_insert_and_standard_modifiers() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)

    backend._handle_key_event(SimpleNamespace(event_string="KP_Insert", type="PRESS"))
    backend._handle_key_event(SimpleNamespace(event_string="Alt_L", type="PRESS"))
    backend._handle_key_event(SimpleNamespace(event_string="Tab", type="PRESS"))

    assert key_events[-1] == ("Tab", ("alt", "insert"))


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
