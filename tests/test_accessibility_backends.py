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
            "synchronous": True,
            "preemptive": True,
            "global_": False,
        }
    ]


def test_atspi_backend_device_listener_supports_global_signals(
    monkeypatch: MonkeyPatch,
) -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []
    legacy_registrations: list[dict[str, object]] = []

    class FakeKeyDefinition:
        keycode = 0
        keysym = 0
        modifiers = 0

    class FakeDevice:
        def __init__(self) -> None:
            self.callbacks: dict[str, object] = {}
            self.grab_callbacks: list[object] = []
            self.grabs: list[tuple[int, int]] = []
            self.grab_keycodes: list[int] = []
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
            assert callable(callback)
            self.grab_callbacks.append(callback)
            self.grabs.append((definition.keysym, definition.modifiers))
            self.grab_keycodes.append(definition.keycode)
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
    monkeypatch.setattr(backend, "_keycodes_for_keysym", lambda keysym: (keysym & 0xFF,))

    assert backend._start_device_key_listener(SimpleNamespace(Atspi=fake_atspi)) is True

    assert created_app_ids == ["org.audioability.Audioability"]
    assert legacy_registrations == []
    assert set(device.callbacks) == {"key-pressed", "key-released"}
    capslock_mask = device.mapped[0xFFE5]
    assert (0xFF09, capslock_mask) in device.grabs
    assert (0xFF99, capslock_mask) in device.grabs
    assert (0xFFB2, capslock_mask) in device.grabs
    assert (0xFFE3, 0) not in device.grabs
    assert (0xFF54, 0) in device.grabs
    assert (0xFF0D, 0) in device.grabs
    assert (ord("h"), 0) in device.grabs
    assert (ord("h"), 1) in device.grabs
    assert (0xFFE5, 0) in device.grabs
    assert (0xFF63, 0) in device.grabs
    down_index = device.grabs.index((0xFF54, 0))
    assert device.grab_keycodes[down_index] == 0x54
    capslock_index = device.grabs.index((0xFFE5, capslock_mask))
    assert device.grab_keycodes[capslock_index] == 0xE5
    initial_grab_count = len(device.grabs)
    assert len(device.grab_callbacks) == initial_grab_count
    assert len({id(callback) for callback in device.grab_callbacks}) == 1

    pressed = device.callbacks["key-pressed"]
    released = device.callbacks["key-released"]
    assert callable(pressed)
    assert callable(released)
    pressed(device, 66, 0xFFE5, 0, "")
    pressed(device, 23, 0xFF09, capslock_mask, "")
    grab_callback = device.grab_callbacks[device.grabs.index((0xFF09, capslock_mask))]
    assert callable(grab_callback)
    assert grab_callback(device, True, 23, 0xFF09, capslock_mask, "") is True
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


def test_atspi_backend_only_dispatches_shift_when_used_alone() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)

    backend._handle_device_key_pressed(None, 50, 0xFFE1, 0, "")
    backend._handle_device_key_pressed(None, 23, 0xFF09, 1, "")
    backend._handle_device_key_released(None, 23, 0xFF09, 1, "")
    backend._handle_device_key_released(None, 50, 0xFFE1, 1, "")

    assert key_events == [("tab", ("shift",))]

    backend._handle_device_key_pressed(None, 50, 0xFFE1, 0, "")
    backend._handle_device_key_released(None, 50, 0xFFE1, 1, "")

    assert key_events[-1] == ("shiftl", ("shift",))


def test_atspi_backend_registers_grabs_with_legacy_modifier_api(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeKeyDefinition:
        keycode = 0
        keysym = 0
        modifiers = 0

    class LegacyDevice:
        def __init__(self) -> None:
            self.mapped: list[int] = []
            self.grabs: list[tuple[int, int, int]] = []

        def map_modifier(self, keycode: int) -> int:
            self.mapped.append(keycode)
            return 1 << (8 + len(self.mapped))

        def add_key_grab(self, definition: FakeKeyDefinition, callback: object) -> int:
            self.grabs.append(
                (definition.keycode, definition.keysym, definition.modifiers)
            )
            return len(self.grabs)

    keycodes = {
        0xFFE5: (66,),
        0xFF63: (118,),
        0xFF9E: (90,),
        0xFFB0: (90,),
        0xFF54: (116,),
        ord("n"): (57,),
    }
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)
    monkeypatch.setattr(
        backend,
        "_keycodes_for_keysym",
        lambda keysym: keycodes.get(keysym, (keysym & 0xFF,)),
    )
    device = LegacyDevice()
    atspi = SimpleNamespace(
        KeyDefinition=FakeKeyDefinition,
        ModifierType=SimpleNamespace(SHIFT=0, CONTROL=2, ALT=3, META=4, SUPER=6),
    )

    backend._register_device_key_grabs(atspi, device)

    capslock_mask = backend._reader_modifier_by_keysym[0xFFE5]
    assert device.mapped[:3] == [66, 118, 90]
    assert (66, 0xFFE5, capslock_mask) in device.grabs
    assert (57, ord("n"), capslock_mask) in device.grabs
    assert (116, 0xFF54, 0) in device.grabs


def test_atspi_backend_clears_stale_standard_modifiers_from_current_mask() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)
    backend._pressed_modifiers.update({"alt", "control", "shift"})

    backend._handle_device_key_pressed(None, 53, ord("x"), 0, "x")

    assert key_events == [("x", ())]


def test_atspi_backend_clears_stale_modifiers_before_reader_shortcut() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)
    backend._pressed_modifiers.add("alt")

    backend._handle_device_key_pressed(None, 66, 0xFFE5, 0, "")
    backend._handle_device_key_pressed(None, 10, ord("1"), 2, "1")

    assert key_events == [("capslock", ()), ("1", ("capslock",))]


def test_atspi_backend_clears_stale_reader_modifier_from_current_mask() -> None:
    key_events: list[tuple[str, tuple[str, ...]]] = []

    def on_key(key: str, modifiers: tuple[str, ...]) -> bool:
        key_events.append((key, modifiers))
        return True

    backend = AtSpiAccessibilityBackend(on_key=on_key)
    backend._reader_modifier_masks[1 << 12] = "capslock"
    backend._pressed_modifiers.add("capslock")

    backend._handle_device_key_pressed(None, 53, ord("x"), 0, "x")

    assert key_events == [("x", ())]


def test_atspi_backend_captures_and_releases_keyboard_for_modal_input() -> None:
    calls: list[str] = []

    class Device:
        def grab_keyboard(self) -> bool:
            calls.append("grab")
            return True

        def ungrab_keyboard(self) -> None:
            calls.append("ungrab")

    backend = AtSpiAccessibilityBackend()
    backend._keyboard_device = Device()

    assert backend.capture_keyboard(True) is True
    assert backend.capture_keyboard(False) is True
    assert calls == ["grab", "ungrab"]


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

    fake_atspi = SimpleNamespace(Device=FakeDeviceType, get_version=lambda: (2, 52, 0))
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
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    assert backend._start_device_key_listener(SimpleNamespace(Atspi=fake_atspi)) is True

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

    fake_atspi = SimpleNamespace(Device=FakeDeviceType, get_version=lambda: (2, 60, 0))
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
    backend = AtSpiAccessibilityBackend(on_key=lambda key, modifiers: True)

    assert backend._start_device_key_listener(SimpleNamespace(Atspi=fake_atspi)) is True

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
            attributes=("placeholder-text:Set volume",),
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


def test_atspi_backend_exposes_component_focus_action() -> None:
    focus_calls = 0
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)

    def grab_focus() -> bool:
        nonlocal focus_calls
        focus_calls += 1
        return True

    source = SimpleNamespace(
        name="Editor",
        description="",
        getRoleName=lambda: "text",
        queryComponent=lambda: SimpleNamespace(grabFocus=grab_focus),
    )

    backend._handle_event(SimpleNamespace(source=source))

    assert nodes[0].focus() is True
    assert focus_calls == 1


def test_atspi_backend_reports_inserted_text() -> None:
    inserted: list[str] = []
    backend = AtSpiAccessibilityBackend(on_text_insert=inserted.append)
    source = SimpleNamespace(getRoleName=lambda: "text")

    backend._handle_event(
        SimpleNamespace(
            type="object:text-changed:insert",
            source=source,
            detail1=2,
            detail2=1,
            any_data="x",
        )
    )

    assert inserted == ["x"]


def test_atspi_backend_reports_control_state_changes_without_focus_dispatch() -> None:
    focus_nodes: list[AccessibleNode] = []
    changes: list[tuple[AccessibleNode, str, bool]] = []
    backend = AtSpiAccessibilityBackend(
        on_focus=focus_nodes.append,
        on_state_change=lambda node, state, enabled: changes.append(
            (node, state, enabled)
        ),
    )
    source = SimpleNamespace(
        name="Notifications",
        description="",
        getRoleName=lambda: "check box",
        getState=lambda: FakeStateSet("checked", "enabled", "showing", "visible"),
    )

    backend._handle_event(
        SimpleNamespace(
            type="object:state-changed:checked",
            source=source,
            detail1=1,
        )
    )

    assert focus_nodes == []
    assert changes == [
        (
            AccessibleNode(
                "Notifications",
                "check box",
                state=frozenset({"checked", "enabled", "showing", "visible"}),
            ),
            "checked",
            True,
        )
    ]


def test_atspi_backend_reports_active_tree_descendant() -> None:
    nodes: list[AccessibleNode] = []
    backend = AtSpiAccessibilityBackend(on_focus=nodes.append)
    row = SimpleNamespace(
        name="Bravo",
        description="",
        getRoleName=lambda: "table cell",
        getAttributes=lambda: ["level:2", "posinset:2", "setsize:3"],
    )
    tree = SimpleNamespace(name="Projects", description="", getRoleName=lambda: "table")

    backend._handle_event(
        SimpleNamespace(
            type="object:active-descendant-changed",
            source=tree,
            any_data=row,
            detail1=0,
        )
    )

    assert nodes == [
        AccessibleNode(
            name="Bravo",
            role="table cell",
            attributes=("level:2", "posinset:2", "setsize:3"),
        )
    ]


def test_atspi_backend_masks_inserted_password_text() -> None:
    inserted: list[str] = []
    backend = AtSpiAccessibilityBackend(on_text_insert=inserted.append)
    source = SimpleNamespace(getRoleName=lambda: "password text")

    backend._handle_event(
        SimpleNamespace(
            type="object:text-changed:insert",
            source=source,
            detail1=0,
            detail2=2,
            any_data="hi",
        )
    )

    assert inserted == ["star star"]


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


def test_atspi_backend_stops_focus_tree_at_top_level_window() -> None:
    focus_events: list[tuple[AccessibleNode, AccessibleNode]] = []
    focused_source = FakeTreeAccessible(name="Save", role="button")
    window_source = FakeTreeAccessible(focused_source, name="Editor", role="frame")
    application_source = FakeTreeAccessible(window_source, name="Editor app", role="application")
    FakeTreeAccessible(application_source, name="Desktop", role="desktop frame")
    backend = AtSpiAccessibilityBackend(
        on_focus_tree=lambda root, focused: focus_events.append((root, focused))
    )

    backend._handle_event(SimpleNamespace(source=focused_source, detail1=1))

    root, focused = focus_events[0]
    assert root.name == "Editor"
    assert root.role == "frame"
    assert focused.name == "Save"


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
