from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any, Protocol

from audioability.accessibility.filtering import FocusEventFilter
from audioability.accessibility.models import AccessibleNode, CaretNavigation
from audioability.input.commands import (
    DEFAULT_COMMAND_BINDINGS,
    is_modifier_key,
    key_from_keysym,
    keysym_for_key,
    normalize_key,
)

logger = logging.getLogger(__name__)


class AccessibilityBackend(Protocol):
    """Interface for desktop accessibility event sources."""

    def start(self) -> None:
        """Connect to desktop accessibility services and start listening."""

    def stop(self) -> None:
        """Disconnect from desktop accessibility services."""


class AccessibilityBackendUnavailableError(RuntimeError):
    """Raised when a platform accessibility backend cannot be loaded."""


class NullAccessibilityBackend:
    """No-op backend for tests and non-Linux development environments."""

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class AtSpiAccessibilityBackend:
    """AT-SPI backend for Linux desktop accessibility events."""

    _application_id = "org.audioability.Audioability"
    # Some AT-SPI versions report a grabbed key through both the device signal
    # and the grab callback. Under WSLg those copies can arrive tens of
    # milliseconds apart, so keep the window wide enough to identify them.
    # A real second press still follows a release and is therefore not a match.
    _duplicate_device_event_window_seconds = 0.1

    # PyAtspi defaults to mask 0, which only reports keys pressed without a
    # modifier. Register every combination from AT-SPI's eight-bit legacy
    # modifier mask so screen-reader gestures reach the application.
    _modifier_masks = tuple(range(256))
    _standard_modifier_names = frozenset(
        {"shift", "control", "alt", "altgr", "meta", "super"}
    )

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
        "visited",
    )

    def __init__(
        self,
        *,
        event_types: Sequence[str] = (
            "object:state-changed:focused",
            "object:state-changed:checked",
            "object:state-changed:pressed",
            "object:state-changed:selected",
            "object:state-changed:expanded",
            "object:active-descendant-changed",
            "object:text-changed:insert",
            "object:text-caret-moved",
        ),
        on_focus: Callable[[AccessibleNode], None] | None = None,
        on_focus_tree: Callable[[AccessibleNode, AccessibleNode], None] | None = None,
        on_key: Callable[[str, tuple[str, ...]], bool] | None = None,
        on_text_insert: Callable[[str], None] | None = None,
        on_caret_move: Callable[[CaretNavigation], None] | None = None,
        on_state_change: Callable[[AccessibleNode, str, bool], None] | None = None,
        event_filter: FocusEventFilter | None = None,
        max_text_length: int = 240,
        max_tree_depth: int = 6,
        max_children_per_node: int = 200,
        max_ancestor_depth: int = 24,
        max_nodes_per_tree: int = 2_000,
    ) -> None:
        self.event_types = tuple(event_types)
        self.on_focus = on_focus
        self.on_focus_tree = on_focus_tree
        self.on_key = on_key
        self.on_text_insert = on_text_insert
        self.on_caret_move = on_caret_move
        self.on_state_change = on_state_change
        self.event_filter = event_filter or FocusEventFilter()
        self.max_text_length = max_text_length
        self.max_tree_depth = max_tree_depth
        self.max_children_per_node = max_children_per_node
        self.max_ancestor_depth = max_ancestor_depth
        self.max_nodes_per_tree = max_nodes_per_tree
        self._pressed_modifiers: set[str] = set()
        self._keyboard_atspi: Any | None = None
        self._keyboard_device: Any | None = None
        self._device_key_callback: Callable[..., bool] | None = None
        self._keyboard_signal_ids: list[int] = []
        self._key_grab_ids: list[int] = []
        self._key_grabs_suspended = False
        self._mapped_reader_keysyms: list[int] = []
        self._mapped_reader_keycodes: list[int] = []
        self._reader_modifier_masks: dict[int, str] = {}
        self._reader_modifier_by_keysym: dict[int, int] = {}
        self._keyboard_captured = False
        self._browse_mode_active = True
        self._device_grab_refresh_pending = False
        self._key_callback_depth = 0
        self._stop_pending = False
        self._key_grab_suspend_pending = False
        self._key_grab_resume_pending = False
        self._keyboard_capture_pending = False
        self._pending_keyboard_capture: bool | None = None
        self._last_caret_gesture: tuple[str, tuple[str, ...], float] | None = None
        self._last_device_event: tuple[bool, int, int, int, str] | None = None
        self._last_device_event_at = 0.0
        self._last_device_event_handled = False
        self._deferred_modifier_keys: set[str] = set()

    def start(self) -> None:
        try:
            import pyatspi  # type: ignore[import-not-found, import-untyped, unused-ignore]
        except ImportError as exc:
            raise AccessibilityBackendUnavailableError(
                "AT-SPI support is unavailable. Install python3-pyatspi and at-spi2-core."
            ) from exc

        for event_type in self.event_types:
            pyatspi.Registry.registerEventListener(self._handle_event, event_type)

        using_device_listener = self.on_key is not None and self._start_device_key_listener(pyatspi)
        using_registry_listener = self.on_key is not None and not using_device_listener
        if using_registry_listener:
            pyatspi.Registry.registerKeystrokeListener(
                self._handle_key_event,
                mask=self._modifier_masks,
                kind=(pyatspi.KEY_PRESSED_EVENT, pyatspi.KEY_RELEASED_EVENT),
                synchronous=True,
                preemptive=True,
                global_=True,
            )

        keyboard_listener = (
            "device" if using_device_listener else "registry"
        )
        logger.info(
            "atspi_start event_types=%r keyboard_listener=%s",
            self.event_types,
            keyboard_listener,
        )
        pyatspi.Registry.start()

    def stop(self) -> None:
        if self._key_callback_depth:
            if not self._stop_pending:
                self._stop_pending = True
                if not self._schedule_idle(self._finish_deferred_stop):
                    self._stop_pending = False
                    logger.error("atspi_stop_defer_failed")
            return

        self._stop_now()

    def _finish_deferred_stop(self) -> bool:
        self._stop_pending = False
        self._stop_now()
        return False

    def _stop_now(self) -> None:
        logger.info("atspi_stop")
        self._stop_device_key_listener()
        try:
            import pyatspi  # type: ignore[import-not-found, import-untyped, unused-ignore]
        except ImportError:
            return

        pyatspi.Registry.stop()

    def _handle_event(self, event: Any) -> None:
        try:
            self._dispatch_accessibility_event(event)
        except Exception:
            logger.exception(
                "atspi_event_callback_error type=%r",
                getattr(event, "type", None),
            )

    def _dispatch_accessibility_event(self, event: Any) -> None:
        event_type = str(getattr(event, "type", ""))
        if "text-caret-moved" in event_type:
            self._handle_caret_move(event)
            return
        if "text-changed:insert" in event_type:
            self._handle_text_insert(event)
            return

        if "state-changed:" in event_type and "state-changed:focused" not in event_type:
            self._handle_state_change(event, event_type)
            return

        if self.on_focus is None and self.on_focus_tree is None:
            return

        source = getattr(event, "source", None)
        if "active-descendant-changed" in event_type:
            source = self._read_active_descendant(event) or source
        node = self._read_node(
            source,
            depth=min(self.max_tree_depth, 2),
            node_budget=[self.max_nodes_per_tree],
        )
        logger.debug(
            "atspi_event type=%r name=%r role=%r state=%r",
            getattr(event, "type", None),
            node.name,
            node.role,
            sorted(node.state),
        )
        if not self.event_filter.accepts(event, node):
            logger.debug("atspi_event_rejected type=%r", getattr(event, "type", None))
            return

        if self.on_focus_tree is not None:
            root, focused = self._read_focus_tree(source, fallback_focus=node)
            self.on_focus_tree(root, focused)
            return

        if self.on_focus is not None:
            self.on_focus(node)

    def _handle_key_event(self, event: Any) -> bool:
        self._key_callback_depth += 1
        try:
            event_text = self._read_key_event_string(event)
            event_keysym = getattr(event, "id", 0)
            key = (
                key_from_keysym(event_keysym, event_text)
                if isinstance(event_keysym, int)
                else event_text
            )
            if not key:
                return False

            modifiers = getattr(event, "modifiers", None)
            modifier_mask = modifiers if isinstance(modifiers, int) else None
            return self._handle_key_transition(
                key,
                pressed=not self._is_key_release_event(event),
                modifier_mask=modifier_mask,
            )
        except Exception:
            logger.exception("atspi_registry_key_callback_error")
            return False
        finally:
            self._key_callback_depth -= 1

    def _handle_device_key_event(
        self,
        _device: Any,
        pressed: bool,
        _keycode: int,
        keysym: int,
        modifiers: int,
        text: str,
    ) -> bool:
        self._key_callback_depth += 1
        try:
            signature = (pressed, _keycode, keysym, modifiers, text)
            now = time.monotonic()
            if (
                signature == self._last_device_event
                and now - self._last_device_event_at
                < self._duplicate_device_event_window_seconds
            ):
                return self._last_device_event_handled

            key = key_from_keysym(keysym, text)
            if not key:
                return False

            handled = self._handle_key_transition(
                key,
                pressed=pressed,
                modifier_mask=modifiers,
            )
            self._last_device_event = signature
            self._last_device_event_at = now
            self._last_device_event_handled = handled
            return handled
        except Exception:
            logger.exception(
                "atspi_device_key_callback_error pressed=%s keycode=%s keysym=%s",
                pressed,
                _keycode,
                keysym,
            )
            return False
        finally:
            self._key_callback_depth -= 1

    def _handle_device_key_pressed(
        self,
        _device: Any,
        _keycode: int,
        keysym: int,
        modifiers: int,
        text: str,
    ) -> None:
        self._handle_device_key_event(_device, True, _keycode, keysym, modifiers, text)

    def _handle_device_key_released(
        self,
        _device: Any,
        _keycode: int,
        keysym: int,
        modifiers: int,
        text: str,
    ) -> None:
        self._handle_device_key_event(_device, False, _keycode, keysym, modifiers, text)

    def _handle_key_transition(
        self,
        key: str,
        *,
        pressed: bool,
        modifier_mask: int | None = None,
    ) -> bool:
        normalized_key = normalize_key(key)
        if pressed and modifier_mask is not None:
            reported_modifiers = self._modifier_names_from_mask(modifier_mask)
            tracked_modifiers = self._standard_modifier_names | frozenset(
                self._reader_modifier_masks.values()
            )
            self._pressed_modifiers.difference_update(tracked_modifiers)
            self._pressed_modifiers.update(
                reported_modifiers.intersection(tracked_modifiers)
            )
        logger.debug(
            "key_transition key=%r pressed=%s modifier_mask=%s pressed_modifiers=%r",
            key,
            pressed,
            modifier_mask,
            sorted(self._pressed_modifiers),
        )
        if not pressed:
            handled = False
            if normalized_key in self._deferred_modifier_keys:
                handled = self._dispatch_key_event(
                    key, modifier_mask or 0
                )
                self._deferred_modifier_keys.discard(normalized_key)
            self._pressed_modifiers.discard(normalized_key)
            return handled

        if normalized_key == "shift":
            self._pressed_modifiers.add(normalized_key)
            self._deferred_modifier_keys.add(normalized_key)
            return False

        if not self._tracks_as_modifier(key):
            self._deferred_modifier_keys.clear()

        grabs_were_suspended = self._key_grabs_suspended
        handled = self._dispatch_key_event(key, modifier_mask or 0)
        if self._tracks_as_modifier(key):
            self._pressed_modifiers.add(normalize_key(key))
        elif grabs_were_suspended:
            self._schedule_device_key_grab_resume()

        return handled

    def _dispatch_key_event(
        self,
        key: str,
        modifier_mask: int = 0,
    ) -> bool:
        if self.on_key is None:
            return False

        modifiers = self._pressed_modifiers | self._modifier_names_from_mask(modifier_mask)
        normalized_key = normalize_key(key).removeprefix("arrow")
        normalized_modifiers = tuple(sorted(modifiers))
        if (
            not self._browse_mode_active
            and normalized_key in {"left", "right"}
            and set(normalized_modifiers).issubset({"control", "shift"})
        ):
            self._last_caret_gesture = (
                normalized_key,
                normalized_modifiers,
                time.monotonic(),
            )
        elif not is_modifier_key(key):
            self._last_caret_gesture = None

        return self.on_key(key, normalized_modifiers)

    def set_browse_mode(self, active: bool) -> None:
        """Switch between browse grabs and pass-through focus-mode input."""

        if self._browse_mode_active == active:
            return
        self._browse_mode_active = active
        if (
            self._keyboard_atspi is not None
            and self._keyboard_device is not None
            and not self._key_grabs_suspended
            and not self._device_grab_refresh_pending
        ):
            self._device_grab_refresh_pending = True
            if not self._schedule_device_key_grab_refresh():
                self._device_grab_refresh_pending = False
                logger.error("browse_key_grab_refresh_failed active=%s", active)
        logger.info(
            "browse_key_grabs active=%s refresh_pending=%s",
            active,
            self._device_grab_refresh_pending,
        )

    def _schedule_device_key_grab_refresh(self) -> bool:
        """Apply a grab profile after the current AT-SPI callback returns."""

        return self._schedule_idle(self._apply_device_key_grab_profile)

    @staticmethod
    def _schedule_idle(callback: Callable[[], bool]) -> bool:
        try:
            from gi.repository import (  # type: ignore[import-not-found, unused-ignore]
                GLib,
            )

            source_id = GLib.idle_add(callback)
        except Exception:
            logger.exception("atspi_idle_schedule_error callback=%r", callback)
            return False
        return isinstance(source_id, int) and source_id > 0

    def _apply_device_key_grab_profile(self) -> bool:
        """Replace device grabs with the profile for the latest interaction mode."""

        self._device_grab_refresh_pending = False
        atspi = self._keyboard_atspi
        device = self._keyboard_device
        if atspi is None or device is None or self._key_grabs_suspended:
            return False

        self._remove_device_key_grabs(device)
        self._register_device_key_grabs(atspi, device)
        logger.info("browse_key_grab_refresh_applied active=%s", self._browse_mode_active)
        return False

    def pass_next_key(self) -> None:
        """Temporarily release command grabs so one complete gesture can pass through."""

        device = self._keyboard_device
        if device is None or not self._key_grab_ids:
            return

        self._key_grabs_suspended = True
        if self._key_callback_depth:
            if not self._key_grab_suspend_pending:
                self._key_grab_suspend_pending = True
                if not self._schedule_idle(self._finish_deferred_key_grab_suspend):
                    self._key_grab_suspend_pending = False
                    self._key_grabs_suspended = False
                    logger.error("key_grab_suspend_defer_failed")
            return

        self._remove_device_key_grabs(device)
        logger.info("key_grabs_suspended")

    def _finish_deferred_key_grab_suspend(self) -> bool:
        self._key_grab_suspend_pending = False
        device = self._keyboard_device
        if device is not None and self._key_grabs_suspended:
            self._remove_device_key_grabs(device)
            logger.info("key_grabs_suspended")
        return False

    def capture_keyboard(self, active: bool) -> bool:
        """Capture all keys temporarily for modal input help."""

        if self._key_callback_depth:
            self._pending_keyboard_capture = active
            if not self._keyboard_capture_pending:
                self._keyboard_capture_pending = True
                if not self._schedule_idle(self._apply_pending_keyboard_capture):
                    self._keyboard_capture_pending = False
                    self._pending_keyboard_capture = None
                    logger.error("keyboard_capture_defer_failed active=%s", active)
                    return False
            return True

        return self._set_keyboard_capture(active)

    def _apply_pending_keyboard_capture(self) -> bool:
        self._keyboard_capture_pending = False
        active = self._pending_keyboard_capture
        self._pending_keyboard_capture = None
        if active is not None:
            self._set_keyboard_capture(active)
        return False

    def _set_keyboard_capture(self, active: bool) -> bool:
        device = self._keyboard_device
        if device is None:
            return False

        if active:
            grab_keyboard = getattr(device, "grab_keyboard", None)
            if not callable(grab_keyboard):
                return False
            try:
                captured = bool(grab_keyboard())
            except Exception:
                return False
            self._keyboard_captured = captured
            logger.info("keyboard_capture active=%s", captured)
            return captured

        ungrab_keyboard = getattr(device, "ungrab_keyboard", None)
        if self._keyboard_captured and callable(ungrab_keyboard):
            with suppress(Exception):
                ungrab_keyboard()
        self._keyboard_captured = False
        logger.info("keyboard_capture active=false")
        return True

    def _start_device_key_listener(self, pyatspi: Any) -> bool:
        """Use AT-SPI's global X11/Wayland device API when available."""

        atspi = getattr(pyatspi, "Atspi", None)
        # The compositor-backed device API was added in 2.55. Older Device
        # objects are the legacy controller in disguise; accepting one makes
        # Registry registration non-global and loses GNOME Wayland shortcuts.
        if self._atspi_version(atspi) < (2, 55):
            return False
        device_type = getattr(atspi, "Device", None)
        if device_type is None:
            return False

        new_full = getattr(device_type, "new_full", None)
        new = getattr(device_type, "new", None)
        try:
            if callable(new_full):
                device = new_full(self._application_id)
            elif callable(new):
                device = new()
            else:
                return False
        except Exception:
            return False

        if device is None or not self._connect_device_key_listener(atspi, device):
            return False

        self._keyboard_atspi = atspi
        self._keyboard_device = device
        self._register_device_key_grabs(atspi, device)
        return True

    def _connect_device_key_listener(self, atspi: Any, device: Any) -> bool:
        if self._device_key_callback is None:
            # PyGObject does not keep a Python bound method alive for all
            # Atspi.Device callback annotations. Keep one stable callback for
            # the lifetime of the watcher and every key grab.
            self._device_key_callback = self._handle_device_key_event

        connect = getattr(device, "connect", None)
        if callable(connect):
            signal_ids: list[int] = []
            try:
                signal_ids.append(connect("key-pressed", self._handle_device_key_pressed))
                signal_ids.append(connect("key-released", self._handle_device_key_released))
            except Exception:
                disconnect = getattr(device, "disconnect", None)
                if callable(disconnect):
                    for signal_id in signal_ids:
                        with suppress(Exception):
                            disconnect(signal_id)
            else:
                self._keyboard_signal_ids = signal_ids
                return True

        add_key_watcher = getattr(device, "add_key_watcher", None)
        if not callable(add_key_watcher):
            return False

        try:
            add_key_watcher(self._device_key_callback)
        except Exception:
            self._device_key_callback = None
            return False
        return True

    def _register_device_key_grabs(self, atspi: Any, device: Any) -> None:
        add_key_grab = getattr(device, "add_key_grab", None)
        map_keysym_modifier = getattr(device, "map_keysym_modifier", None)
        map_modifier = getattr(device, "map_modifier", None)
        key_definition_type = getattr(atspi, "KeyDefinition", None)
        if not callable(add_key_grab) or not callable(key_definition_type):
            return

        if not self._mapped_reader_keysyms and not self._mapped_reader_keycodes:
            for name, keysym in self._screen_reader_modifier_keysyms():
                modifier = 0
                if callable(map_keysym_modifier):
                    try:
                        modifier = map_keysym_modifier(keysym)
                    except Exception:
                        continue
                    if isinstance(modifier, int) and modifier != 0:
                        self._mapped_reader_keysyms.append(keysym)
                elif callable(map_modifier):
                    for keycode in self._keycodes_for_keysym(keysym):
                        try:
                            modifier = map_modifier(keycode)
                        except Exception:
                            continue
                        if isinstance(modifier, int) and modifier != 0:
                            if keycode not in self._mapped_reader_keycodes:
                                self._mapped_reader_keycodes.append(keycode)
                            break
                if not isinstance(modifier, int) or modifier == 0:
                    continue
                self._reader_modifier_masks[modifier] = name
                self._reader_modifier_by_keysym[keysym] = modifier

        reader_modifiers = tuple(self._reader_modifier_masks)

        registered: set[tuple[int, int, int]] = set()
        rejected = 0
        for gesture in self._grab_gestures():
            key = gesture[-1]
            modifier_names = gesture[:-1]
            base_modifier = self._standard_modifier_mask(atspi, modifier_names)
            for keysym in self._keysyms_for_grab(key):
                if "sr" in modifier_names:
                    modifiers = reader_modifiers
                elif key in {"capslock", "insert"}:
                    own_modifier = self._reader_modifier_by_keysym.get(keysym, 0)
                    modifiers = (0, own_modifier) if own_modifier else (0,)
                else:
                    modifiers = (0,)

                # DeviceLegacy compares incoming grabs by hardware keycode,
                # even when the grab was specified with a keysym. Supplying
                # both fields keeps grabs consumable on the legacy backend
                # while retaining keysym-based grabs for modern compositors.
                keycodes = self._keycodes_for_keysym(keysym) or (0,)
                for reader_modifier in modifiers:
                    modifier = base_modifier | reader_modifier
                    for keycode in keycodes:
                        registration = (keycode, keysym, modifier)
                        if registration in registered:
                            continue
                        try:
                            definition = key_definition_type()
                            definition.keycode = keycode
                            definition.keysym = keysym
                            definition.modifiers = modifier
                            grab_id = add_key_grab(
                                definition, self._device_key_callback
                            )
                        except Exception:
                            rejected += 1
                            continue
                        registered.add(registration)
                        if isinstance(grab_id, int) and grab_id != 0:
                            self._key_grab_ids.append(grab_id)
                        else:
                            rejected += 1

        logger.info(
            "device_key_grabs registered=%d rejected=%d definitions=%d",
            len(self._key_grab_ids),
            rejected,
            len(registered),
        )

    def _remove_device_key_grabs(self, device: Any) -> None:
        remove_key_grab = getattr(device, "remove_key_grab", None)
        if callable(remove_key_grab):
            for grab_id in self._key_grab_ids:
                with suppress(Exception):
                    remove_key_grab(grab_id)
        self._key_grab_ids.clear()

    def _resume_device_key_grabs(self) -> None:
        if not self._key_grabs_suspended:
            return

        self._key_grabs_suspended = False
        if self._keyboard_atspi is not None and self._keyboard_device is not None:
            self._register_device_key_grabs(self._keyboard_atspi, self._keyboard_device)

    def _schedule_device_key_grab_resume(self) -> None:
        if self._key_grab_resume_pending:
            return
        self._key_grab_resume_pending = True
        if not self._schedule_idle(self._finish_deferred_key_grab_resume):
            self._key_grab_resume_pending = False
            logger.error("key_grab_resume_defer_failed")

    def _finish_deferred_key_grab_resume(self) -> bool:
        self._key_grab_resume_pending = False
        self._resume_device_key_grabs()
        return False

    def _stop_device_key_listener(self) -> None:
        device = self._keyboard_device
        self._keyboard_atspi = None
        self._keyboard_device = None
        self._device_grab_refresh_pending = False
        self._key_grab_suspend_pending = False
        self._key_grab_resume_pending = False
        self._keyboard_capture_pending = False
        self._pending_keyboard_capture = None
        self._pressed_modifiers.clear()
        if device is None:
            self._key_grabs_suspended = False
            return


        if self._keyboard_captured:
            ungrab_keyboard = getattr(device, "ungrab_keyboard", None)
            if callable(ungrab_keyboard):
                with suppress(Exception):
                    ungrab_keyboard()
            self._keyboard_captured = False

        self._remove_device_key_grabs(device)

        unmap_keysym_modifier = getattr(device, "unmap_keysym_modifier", None)
        if callable(unmap_keysym_modifier):
            for keysym in self._mapped_reader_keysyms:
                with suppress(Exception):
                    unmap_keysym_modifier(keysym)

        unmap_modifier = getattr(device, "unmap_modifier", None)
        if callable(unmap_modifier):
            for keycode in self._mapped_reader_keycodes:
                with suppress(Exception):
                    unmap_modifier(keycode)

        disconnect = getattr(device, "disconnect", None)
        if callable(disconnect):
            for signal_id in self._keyboard_signal_ids:
                with suppress(Exception):
                    disconnect(signal_id)

        self._keyboard_signal_ids.clear()
        self._device_key_callback = None
        self._key_grabs_suspended = False
        self._mapped_reader_keysyms.clear()
        self._mapped_reader_keycodes.clear()
        self._reader_modifier_masks.clear()
        self._reader_modifier_by_keysym.clear()

    def _modifier_names_from_mask(self, mask: int) -> set[str]:
        names = {
            name
            for bit, name in (
                (1 << 0, "shift"),
                (1 << 2, "control"),
                (1 << 3, "alt"),
                (1 << 4, "meta"),
                (1 << 5, "meta"),
                (1 << 6, "super"),
            )
            if mask & bit
        }
        names.update(name for bit, name in self._reader_modifier_masks.items() if mask & bit)
        return names

    @staticmethod
    def _atspi_version(atspi: Any) -> tuple[int, int]:
        get_version = getattr(atspi, "get_version", None)
        if not callable(get_version):
            return (0, 0)
        try:
            version = get_version()
        except Exception:
            return (0, 0)
        if not isinstance(version, Sequence) or len(version) < 2:
            return (0, 0)
        major, minor = version[0], version[1]
        if not isinstance(major, int) or not isinstance(minor, int):
            return (0, 0)
        return (major, minor)

    @staticmethod
    def _screen_reader_modifier_keysyms() -> tuple[tuple[str, int], ...]:
        return (
            ("capslock", 0xFFE5),
            ("insert", 0xFF63),
            ("insert", 0xFF9E),
            ("insert", 0xFFB0),
        )

    @staticmethod
    def _keycodes_for_keysym(keysym: int) -> tuple[int, ...]:
        """Resolve the hardware keycodes needed by AT-SPI's legacy device."""

        try:
            import gi  # type: ignore[import-not-found, import-untyped, unused-ignore]

            gi.require_version("Gdk", "3.0")
            from gi.repository import (  # type: ignore[import-not-found, unused-ignore]
                Gdk,
            )

            keymap = Gdk.Keymap.get_default()
            if keymap is None:
                return ()
            found, entries = keymap.get_entries_for_keyval(keysym)
        except Exception:
            return ()

        if not found:
            return ()
        return tuple(
            sorted(
                {
                    keycode
                    for entry in entries
                    if isinstance((keycode := getattr(entry, "keycode", None)), int)
                    and keycode > 0
                }
            )
        )

    def _grab_gestures(self) -> tuple[tuple[str, ...], ...]:
        gestures = set(self._global_grab_gestures())
        if not self._browse_mode_active:
            return tuple(sorted(gestures))

        browse_keys = (
            "left",
            "right",
            "up",
            "down",
            "enter",
            "space",
            "esc",
            ",",
            "h",
            "l",
            "i",
            "t",
            "k",
            "n",
            "f",
            "u",
            "v",
            "e",
            "b",
            "x",
            "c",
            "r",
            "q",
            "s",
            "m",
            "g",
            "d",
            "o",
            "a",
            "p",
            "w",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
        )
        gestures.update((key,) for key in browse_keys)
        gestures.update(("shift", key) for key in browse_keys if key not in {"esc"})
        gestures.update(
            ("control", "alt", key)
            for key in (
                "left",
                "right",
                "up",
                "down",
                "home",
                "end",
                "pageup",
                "pagedown",
            )
        )
        return tuple(sorted(gestures))

    @staticmethod
    def _global_grab_gestures() -> tuple[tuple[str, ...], ...]:
        gestures = {
            tuple(normalize_key(part) for part in gesture.split("+"))
            for binding in DEFAULT_COMMAND_BINDINGS
            for gesture in (binding.desktop_key, binding.laptop_key)
            if "+" in gesture
        }
        gestures.update(
            {
                ("sr", key)
                for key in (
                    "left",
                    "right",
                    "up",
                    "down",
                    "numpad8",
                    "numpad4",
                    "numpad5",
                    "numpad6",
                    "numpad2",
                    "numpad9",
                    "numpad3",
                    "numpadminus",
                    "numpadenter",
                )
            }
        )
        gestures.update({("capslock",), ("insert",)})
        return tuple(sorted(gestures))

    @staticmethod
    def _standard_modifier_mask(atspi: Any, names: tuple[str, ...]) -> int:
        modifier_type = getattr(atspi, "ModifierType", None)
        fallback_indexes = {
            "shift": 0,
            "control": 2,
            "alt": 3,
            "meta": 4,
            "super": 6,
        }
        mask = 0
        for name in names:
            if name == "sr":
                continue
            index = fallback_indexes.get(name)
            enum_value = getattr(modifier_type, name.upper(), None)
            if enum_value is not None:
                with suppress(TypeError, ValueError):
                    index = int(enum_value)
            if index is not None:
                mask |= 1 << index
        return mask

    @staticmethod
    def _keysyms_for_grab(key: str) -> tuple[int, ...]:
        normalized = normalize_key(key)
        paired_modifiers = {
            "control": (0xFFE3, 0xFFE4),
            "shift": (0xFFE1, 0xFFE2),
            "alt": (0xFFE9, 0xFFEA),
            "meta": (0xFFE7, 0xFFE8),
            "super": (0xFFEB, 0xFFEC),
        }
        if normalized in paired_modifiers:
            return paired_modifiers[normalized]
        keypad_navigation_keysyms = {
            "numpad0": 0xFF9E,
            "numpad1": 0xFF9C,
            "numpad2": 0xFF99,
            "numpad3": 0xFF9B,
            "numpad4": 0xFF96,
            "numpad5": 0xFF9D,
            "numpad6": 0xFF98,
            "numpad7": 0xFF95,
            "numpad8": 0xFF97,
            "numpad9": 0xFF9A,
        }
        if normalized in keypad_navigation_keysyms:
            digit = int(normalized[-1])
            return (keypad_navigation_keysyms[normalized], 0xFFB0 + digit)
        keysym = keysym_for_key(normalized)
        return (keysym,) if keysym is not None else ()

    @staticmethod
    def _read_key_event_string(event: Any) -> str:
        for attribute in ("event_string", "eventString", "key_string", "keyString"):
            key = getattr(event, attribute, "")
            if isinstance(key, str) and key.strip():
                return key.strip()

        return ""

    def _is_key_release_event(self, event: Any) -> bool:
        event_type = getattr(event, "type", None)
        try:
            import pyatspi  # type: ignore[import-not-found, import-untyped, unused-ignore]
        except ImportError:
            pyatspi = None

        if pyatspi is not None and event_type == pyatspi.KEY_RELEASED_EVENT:
            return True

        if not isinstance(event_type, str):
            return False

        normalized = normalize_key(event_type)
        return normalized in {"keyreleasedevent", "releasedevent", "released", "release"}

    def _tracks_as_modifier(self, key: str) -> bool:
        return is_modifier_key(key)

    def _read_node(
        self,
        source: Any,
        *,
        depth: int,
        focus_path: tuple[int, ...] = (),
        node_budget: list[int] | None = None,
    ) -> AccessibleNode:
        if node_budget is not None:
            if node_budget[0] <= 0:
                return AccessibleNode(name="", role="")
            node_budget[0] -= 1
        child_count = self._read_child_count(source)
        return AccessibleNode(
            name=self._read_text_attribute(source, "name"),
            role=self._read_role(source),
            description=self._read_text_attribute(source, "description"),
            value=self._read_value(source),
            text=self._read_text(source),
            placeholder=self._read_attribute(source, "placeholder-text"),
            shortcut=self._read_shortcut(source),
            attributes=self._read_attributes(source),
            state=self._read_state(source),
            child_count=child_count,
            children=self._read_children(
                source,
                child_count,
                depth=depth,
                focus_path=focus_path,
                node_budget=node_budget,
            ),
            activation=self._read_activation(source),
            focus_action=self._read_focus_action(source),
        )

    def _read_focus_tree(
        self,
        source: Any,
        *,
        fallback_focus: AccessibleNode,
    ) -> tuple[AccessibleNode, AccessibleNode]:
        root_source, focus_path = self._read_root_source_and_focus_path(source)
        root = self._read_node(
            root_source,
            depth=self.max_tree_depth,
            focus_path=focus_path,
            node_budget=[self.max_nodes_per_tree],
        )
        focused = self._node_at_path(root, focus_path)
        return root, focused or fallback_focus

    def _read_root_source_and_focus_path(self, source: Any) -> tuple[Any, tuple[int, ...]]:
        root = source
        reversed_path: list[int] = []
        seen: set[int] = set()

        for _ in range(self.max_ancestor_depth):
            source_id = id(root)
            if source_id in seen:
                break
            seen.add(source_id)

            parent = self._read_parent(root)
            if parent is None:
                break

            if self._read_role(parent).casefold() in {
                "application",
                "desktop frame",
                "desktop",
            }:
                break

            index = self._read_index_in_parent(root, parent)
            if index is None:
                break

            reversed_path.append(index)
            root = parent

        return root, tuple(reversed(reversed_path))

    @staticmethod
    def _read_parent(source: Any) -> Any | None:
        parent = getattr(source, "parent", None)
        if parent is not None:
            return parent

        get_parent = getattr(source, "getParent", None)
        if callable(get_parent):
            try:
                return get_parent()
            except Exception:
                return None

        return None

    def _read_index_in_parent(self, source: Any, parent: Any) -> int | None:
        get_index = getattr(source, "getIndexInParent", None)
        if callable(get_index):
            index = self._safe_call(get_index)
            if isinstance(index, int) and index >= 0:
                return index

        child_count = self._read_child_count(parent)
        for index in range(min(child_count, self.max_children_per_node)):
            if self._same_accessible(self._read_child(parent, index), source):
                return index

        return None

    @staticmethod
    def _same_accessible(left: Any, right: Any) -> bool:
        if left is right:
            return True
        try:
            return bool(left == right)
        except Exception:
            return False

    @staticmethod
    def _node_at_path(node: AccessibleNode, path: tuple[int, ...]) -> AccessibleNode | None:
        current = node
        for index in path:
            if index < 0 or index >= len(current.children):
                return None
            current = current.children[index]

        return current

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
        attribute_set = self._read_attributes(source)
        prefix = f"{name}:"
        for attribute in attribute_set:
            if isinstance(attribute, str) and attribute.startswith(prefix):
                return attribute.removeprefix(prefix).strip()

        return ""

    def _read_attributes(self, source: Any) -> tuple[str, ...]:
        attribute_set = self._safe_call(getattr(source, "getAttributes", None))
        if not isinstance(attribute_set, Sequence):
            return ()
        return tuple(attribute for attribute in attribute_set if isinstance(attribute, str))

    def _read_active_descendant(self, event: Any) -> Any | None:
        descendant = getattr(event, "any_data", None)
        if descendant is not None and (
            self._read_text_attribute(descendant, "name") or self._read_role(descendant)
        ):
            return descendant

        source = getattr(event, "source", None)
        selection = self._query_interface(source, "querySelection")
        selected_count = getattr(selection, "nSelectedChildren", 0)
        get_selected_child = getattr(selection, "getSelectedChild", None)
        if isinstance(selected_count, int) and selected_count > 0 and callable(get_selected_child):
            return self._safe_call(get_selected_child, 0)
        return None

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

    def _read_activation(self, source: Any) -> Callable[[], bool] | None:
        action_interface = self._query_interface(source, "queryAction")
        if action_interface is None:
            return None

        action_count = getattr(action_interface, "nActions", 0)
        do_action = getattr(action_interface, "doAction", None)
        if not isinstance(action_count, int) or action_count <= 0 or not callable(do_action):
            return None

        def activate() -> bool:
            return self._safe_call(do_action, 0) is True

        return activate

    def _read_focus_action(self, source: Any) -> Callable[[], bool] | None:
        component_interface = self._query_interface(source, "queryComponent")
        if component_interface is None:
            return None

        grab_focus = getattr(component_interface, "grabFocus", None)
        if not callable(grab_focus):
            return None

        def focus() -> bool:
            return self._safe_call(grab_focus) is True

        return focus

    def _handle_text_insert(self, event: Any) -> None:
        if self.on_text_insert is None:
            return

        source = getattr(event, "source", None)
        role = self._read_role(source).casefold()
        length = getattr(event, "detail2", 0)
        if "password" in role:
            text = " ".join("star" for _ in range(max(length if isinstance(length, int) else 1, 1)))
        else:
            text = getattr(event, "any_data", "")
            if not isinstance(text, str) or not text:
                offset = getattr(event, "detail1", 0)
                text_interface = self._query_interface(source, "queryText")
                get_text = getattr(text_interface, "getText", None)
                if isinstance(offset, int) and isinstance(length, int) and callable(get_text):
                    value = self._safe_call(get_text, offset, offset + length)
                    text = value if isinstance(value, str) else ""

        if text:
            logger.debug("text_insert text=%r role=%r", text, role)
            self.on_text_insert(text)

    def _handle_caret_move(self, event: Any) -> None:
        if self.on_caret_move is None or self._last_caret_gesture is None:
            return

        key, modifiers, gesture_time = self._last_caret_gesture
        self._last_caret_gesture = None
        if time.monotonic() - gesture_time > 2.0:
            return

        offset = getattr(event, "detail1", None)
        if not isinstance(offset, int) or offset < 0:
            return

        source = getattr(event, "source", None)
        role = self._read_role(source).casefold()
        text_interface = self._query_interface(source, "queryText")
        character_count = getattr(text_interface, "characterCount", 0)
        if not isinstance(character_count, int) or character_count < 0:
            return

        password = "password" in role
        if password:
            text = "*" * character_count
            relative_offset = min(offset, character_count)
        else:
            get_text = getattr(text_interface, "getText", None)
            if not callable(get_text):
                return
            radius = max(self.max_text_length, 512)
            start = max(0, offset - radius)
            end = min(character_count, offset + radius)
            value = self._safe_call(get_text, start, end)
            if not isinstance(value, str):
                return
            text = value
            relative_offset = offset - start

        navigation = CaretNavigation(
            text=text,
            offset=relative_offset,
            key=key,
            modifiers=modifiers,
            password=password,
        )
        logger.debug(
            "caret_navigation key=%r modifiers=%r offset=%d password=%s",
            key,
            modifiers,
            offset,
            password,
        )
        self.on_caret_move(navigation)

    def _handle_state_change(self, event: Any, event_type: str) -> None:
        if self.on_state_change is None:
            return

        node = self._read_node(getattr(event, "source", None), depth=1)
        state_name = event_type.rsplit(":", 1)[-1].strip().casefold()
        enabled = bool(getattr(event, "detail1", 0))
        logger.debug(
            "atspi_state_change name=%r role=%r state=%s enabled=%s",
            node.name,
            node.role,
            state_name,
            enabled,
        )
        self.on_state_change(node, state_name, enabled)

    def _read_state(self, source: Any) -> frozenset[str]:
        state_set = self._safe_call(getattr(source, "getState", None))
        if state_set is None:
            return frozenset()

        state_names = set(self._read_named_states(state_set))
        state_names.update(self._read_pyatspi_states(state_set))
        if (
            "enabled" not in state_names
            and "sensitive" not in state_names
            and {"focusable", "showing", "visible"}.intersection(state_names)
        ):
            state_names.add("disabled")
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
        focus_path: tuple[int, ...] = (),
        node_budget: list[int] | None = None,
    ) -> tuple[AccessibleNode, ...]:
        if (depth <= 0 and not focus_path) or child_count <= 0:
            return ()

        children: list[AccessibleNode] = []
        for index in range(min(child_count, self.max_children_per_node)):
            if node_budget is not None and node_budget[0] <= 0:
                logger.warning("atspi_tree_node_budget_exhausted limit=%d", self.max_nodes_per_tree)
                break
            child = self._read_child(source, index)
            if child is not None:
                child_focus_path = (
                    focus_path[1:]
                    if focus_path and index == focus_path[0]
                    else ()
                )
                children.append(
                    self._read_node(
                        child,
                        depth=max(depth - 1, 0),
                        focus_path=child_focus_path,
                        node_budget=node_budget,
                    )
                )

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
