from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from audioability.accessibility.filtering import FocusEventFilter
from audioability.accessibility.models import AccessibleNode
from audioability.input.commands import is_screen_reader_modifier, normalize_key


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

    _state_names = (
        "active",
        "checked",
        "collapsed",
        "defunct",
        "editable",
        "enabled",
        "expanded",
        "focused",
        "focusable",
        "invalid",
        "modal",
        "multiselectable",
        "pressed",
        "required",
        "selected",
        "sensitive",
        "showing",
        "visible",
    )

    def __init__(
        self,
        *,
        event_types: Sequence[str] = ("object:state-changed:focused",),
        on_focus: Callable[[AccessibleNode], None] | None = None,
        on_key: Callable[[str, tuple[str, ...]], bool] | None = None,
        event_filter: FocusEventFilter | None = None,
        max_text_length: int = 240,
        max_tree_depth: int = 2,
        max_children_per_node: int = 50,
    ) -> None:
        self.event_types = tuple(event_types)
        self.on_focus = on_focus
        self.on_key = on_key
        self.event_filter = event_filter or FocusEventFilter()
        self.max_text_length = max_text_length
        self.max_tree_depth = max_tree_depth
        self.max_children_per_node = max_children_per_node
        self._pressed_modifiers: set[str] = set()

    def start(self) -> None:
        try:
            import pyatspi  # type: ignore[import-not-found, import-untyped, unused-ignore]
        except ImportError as exc:
            raise AccessibilityBackendUnavailableError(
                "AT-SPI support is unavailable. Install python3-pyatspi and at-spi2-core."
            ) from exc

        for event_type in self.event_types:
            pyatspi.Registry.registerEventListener(self._handle_event, event_type)

        if self.on_key is not None:
            pyatspi.Registry.registerKeystrokeListener(
                self._handle_key_event,
                kind=(pyatspi.KEY_PRESSED_EVENT, pyatspi.KEY_RELEASED_EVENT),
            )

        pyatspi.Registry.start()

    def _handle_event(self, event: Any) -> None:
        if self.on_focus is None:
            return

        source = getattr(event, "source", None)
        node = self._read_node(source, depth=self.max_tree_depth)
        if not self.event_filter.accepts(event, node):
            return

        self.on_focus(node)

    def _handle_key_event(self, event: Any) -> bool:
        key = self._read_key_event_string(event)
        if not key:
            return False

        if self._is_key_release_event(event):
            self._pressed_modifiers.discard(normalize_key(key))
            return False

        handled = self._dispatch_key_event(key)
        if self._tracks_as_modifier(key):
            self._pressed_modifiers.add(normalize_key(key))

        return handled

    def _dispatch_key_event(self, key: str) -> bool:
        if self.on_key is None:
            return False

        return self.on_key(key, tuple(sorted(self._pressed_modifiers)))

    @staticmethod
    def _read_key_event_string(event: Any) -> str:
        for attribute in ("event_string", "eventString", "key_string", "keyString"):
            key = getattr(event, attribute, "")
            if isinstance(key, str) and key.strip():
                return key.strip()

        return ""

    def _is_key_release_event(self, event: Any) -> bool:
        event_type = getattr(event, "type", None)
        return event_type is not None and str(event_type).endswith("RELEASED_EVENT")

    def _tracks_as_modifier(self, key: str) -> bool:
        normalized = normalize_key(key)
        return normalized in {"control", "shift"} or is_screen_reader_modifier(normalized)

    def _read_node(self, source: Any, *, depth: int) -> AccessibleNode:
        child_count = self._read_child_count(source)
        return AccessibleNode(
            name=self._read_text_attribute(source, "name"),
            role=self._read_role(source),
            description=self._read_text_attribute(source, "description"),
            value=self._read_value(source),
            text=self._read_text(source),
            placeholder=self._read_attribute(source, "placeholder-text"),
            shortcut=self._read_shortcut(source),
            state=self._read_state(source),
            child_count=child_count,
            children=self._read_children(source, child_count, depth=depth),
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

    def _read_value(self, source: Any) -> str:
        value_interface = self._query_interface(source, "queryValue")
        if value_interface is None:
            return ""

        for attribute in ("currentValue", "minimumValue", "maximumValue"):
            value = getattr(value_interface, attribute, None)
            if isinstance(value, int | float):
                return self._format_number(value)

        get_current_value = getattr(value_interface, "getCurrentValue", None)
        if not callable(get_current_value):
            return ""

        value = self._safe_call(get_current_value)
        return self._format_number(value) if isinstance(value, int | float) else ""

    def _read_text(self, source: Any) -> str:
        text_interface = self._query_interface(source, "queryText")
        if text_interface is None:
            return ""

        character_count = getattr(text_interface, "characterCount", 0)
        if not isinstance(character_count, int) or character_count <= 0:
            return ""

        get_text = getattr(text_interface, "getText", None)
        if not callable(get_text):
            return ""

        text = self._safe_call(get_text, 0, min(character_count, self.max_text_length))
        return text.strip() if isinstance(text, str) else ""

    def _read_attribute(self, source: Any, name: str) -> str:
        attribute_set = self._safe_call(getattr(source, "getAttributes", None))
        if not isinstance(attribute_set, Sequence):
            return ""

        prefix = f"{name}:"
        for attribute in attribute_set:
            if isinstance(attribute, str) and attribute.startswith(prefix):
                return attribute.removeprefix(prefix).strip()

        return ""

    def _read_shortcut(self, source: Any) -> str:
        action_interface = self._query_interface(source, "queryAction")
        if action_interface is None:
            return ""

        action_count = getattr(action_interface, "nActions", 0)
        if not isinstance(action_count, int):
            return ""

        get_key_binding = getattr(action_interface, "getKeyBinding", None)
        if not callable(get_key_binding):
            return ""

        for index in range(action_count):
            shortcut = self._safe_call(get_key_binding, index)
            if isinstance(shortcut, str) and shortcut.strip():
                return shortcut.strip()

        return ""

    def _read_state(self, source: Any) -> frozenset[str]:
        state_set = self._safe_call(getattr(source, "getState", None))
        if state_set is None:
            return frozenset()

        state_names = set(self._read_named_states(state_set))
        state_names.update(self._read_pyatspi_states(state_set))
        return frozenset(state_names)

    def _read_named_states(self, state_set: Any) -> tuple[str, ...]:
        get_states = getattr(state_set, "getStates", None)
        if not callable(get_states):
            return ()

        states = self._safe_call(get_states)
        if not isinstance(states, Sequence):
            return ()

        return tuple(filter(None, (self._normalize_state_name(state) for state in states)))

    def _read_pyatspi_states(self, state_set: Any) -> tuple[str, ...]:
        contains = getattr(state_set, "contains", None)
        if not callable(contains):
            return ()

        try:
            import pyatspi  # type: ignore[import-not-found, import-untyped, unused-ignore]
        except ImportError:
            return ()

        names: list[str] = []
        for name in self._state_names:
            constant = getattr(pyatspi, f"STATE_{name.upper()}", None)
            if constant is not None and self._safe_call(contains, constant) is True:
                names.append(name)

        return tuple(names)

    def _read_children(
        self,
        source: Any,
        child_count: int,
        *,
        depth: int,
    ) -> tuple[AccessibleNode, ...]:
        if depth <= 0 or child_count <= 0:
            return ()

        children: list[AccessibleNode] = []
        for index in range(min(child_count, self.max_children_per_node)):
            child = self._read_child(source, index)
            if child is not None:
                children.append(self._read_node(child, depth=depth - 1))

        return tuple(children)

    def _read_child(self, source: Any, index: int) -> Any | None:
        get_child = getattr(source, "getChildAtIndex", None)
        if callable(get_child):
            child = self._safe_call(get_child, index)
            if child is not None:
                return child

        try:
            return source[index]
        except (IndexError, KeyError, TypeError, AttributeError):
            return None

    @staticmethod
    def _read_child_count(source: Any) -> int:
        child_count = getattr(source, "childCount", 0)
        return child_count if isinstance(child_count, int) and child_count > 0 else 0

    @staticmethod
    def _query_interface(source: Any, name: str) -> Any | None:
        query = getattr(source, name, None)
        if not callable(query):
            return None

        try:
            return query()
        except Exception:
            return None

    @staticmethod
    def _safe_call(callable_object: Any, *args: object) -> Any | None:
        if not callable(callable_object):
            return None

        try:
            return callable_object(*args)
        except Exception:
            return None

    @staticmethod
    def _normalize_state_name(state: Any) -> str:
        if isinstance(state, str):
            raw_name = state
        else:
            raw_name = getattr(state, "name", "")
            if not isinstance(raw_name, str):
                return ""

        return raw_name.lower().removeprefix("state_").replace("_", "-")

    @staticmethod
    def _format_number(value: int | float) -> str:
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
