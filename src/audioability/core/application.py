from __future__ import annotations

import logging
from enum import StrEnum

from audioability.accessibility.backends import (
    AccessibilityBackend,
    AtSpiAccessibilityBackend,
    NullAccessibilityBackend,
)
from audioability.accessibility.models import AccessibleNode
from audioability.accessibility.navigation import ObjectNavigationAction, ObjectNavigator
from audioability.input.commands import (
    Command,
    CommandName,
    command_binding_lines,
    command_for_gesture,
    is_modifier_key,
    is_screen_reader_modifier,
    normalize_key,
)
from audioability.input.router import CommandRouter
from audioability.speech.controller import SpeechController, VerbosityMode
from audioability.speech.drivers import (
    NullSpeechDriver,
    SpeechDispatcherDriver,
    SpeechDriver,
    SynthesisVoice,
)

logger = logging.getLogger(__name__)


class InteractionMode(StrEnum):
    BROWSE = "browse"
    FOCUS = "focus"


class SpeechMode(StrEnum):
    TALK = "talk"
    ON_DEMAND = "on-demand"
    OFF = "off"


class ScreenReaderApplication:
    """Coordinates accessibility events, command input, and speech output."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        accessibility_backend: AccessibilityBackend | None = None,
        speech_driver: SpeechDriver | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.speech_driver = speech_driver or (
            NullSpeechDriver() if dry_run else SpeechDispatcherDriver()
        )
        available_voices = getattr(self.speech_driver, "available_voices", None)
        voices = (
            available_voices()
            if callable(available_voices)
            else (SynthesisVoice("default", "default"),)
        )
        logger.info(
            "speech_voices_discovered count=%d languages=%d",
            len(voices),
            len({voice.language for voice in voices}),
        )
        self.speech_controller = SpeechController(self.speech_driver, voices=voices)
        self.current_focus: AccessibleNode | None = None
        self.object_navigator = ObjectNavigator()
        self.quit_requested = False
        self._input_help_active = False
        self._pass_next_key = False
        self.interaction_mode = InteractionMode.BROWSE
        self._focus_mode_auto_entered = False
        self._speech_modes = tuple(SpeechMode)
        self._speech_mode_index = 0
        self.router = CommandRouter(
            {
                "focus": self.speak_current_focus,
                "read-focus": self.speak_current_focus,
                "object-activate": lambda: self.navigate_object(
                    ObjectNavigationAction.ACTIVATE_CURRENT
                ),
                "object-current": lambda: self.navigate_object(
                    ObjectNavigationAction.REPORT_CURRENT
                ),
                "object-first-child": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_FIRST_CHILD
                ),
                "object-focus": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_FOCUS
                ),
                "object-next": lambda: self.navigate_object(ObjectNavigationAction.MOVE_TO_NEXT),
                "object-next-flat": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_NEXT_FLAT
                ),
                "object-parent": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_PARENT
                ),
                "object-previous": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_PREVIOUS
                ),
                "object-previous-flat": lambda: self.navigate_object(
                    ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT
                ),
                "repeat": self.repeat_last_spoken,
                "repeat-last": self.repeat_last_spoken,
                "stop": self.stop_speech,
                "stop-speech": self.stop_speech,
            }
        )
        self.accessibility_backend = accessibility_backend or (
            NullAccessibilityBackend()
            if dry_run
            else AtSpiAccessibilityBackend(
                on_focus_tree=self._speak_focused_tree,
                on_key=self.handle_key,
                on_text_insert=self._speak_typed_text,
                on_state_change=self._speak_state_change,
            )
        )

    def run(self) -> None:
        logger.info("application_start dry_run=%s", self.dry_run)
        if self.dry_run:
            self._speak_status("Audioability initialized in dry-run mode.")
            return

        self._speak_status("Audioability started.")
        self.accessibility_backend.start()

    def handle_command(self, command: Command) -> bool:
        logger.debug(
            "command name=%s mode=%s speech_mode=%s",
            command.name,
            self.interaction_mode,
            self.speech_mode,
        )
        if command.name is CommandName.QUIT:
            return self.quit()
        if command.name is CommandName.OPEN_MENU:
            return self._speak_command("Commands. " + ". ".join(command_binding_lines()))
        if command.name is CommandName.INPUT_HELP:
            self._input_help_active = not self._input_help_active
            state = "on" if self._input_help_active else "off"
            return self._speak_command(f"Input help {state}")
        if command.name is CommandName.PASS_NEXT_KEY:
            self._pass_next_key = True
            pass_next_key = getattr(self.accessibility_backend, "pass_next_key", None)
            if callable(pass_next_key):
                pass_next_key()
            return self._speak_command("Pass next key")
        if command.name is CommandName.READ_FOCUS:
            return self.speak_current_focus()
        if command.name is CommandName.READ_TITLE:
            return self.speak_current_title()
        if command.name is CommandName.READ_WINDOW:
            return self.speak_current_window()
        if command.name is CommandName.READ_STATUS_BAR:
            return self.speak_status_bar()
        if command.name is CommandName.TOGGLE_BROWSE_FOCUS_MODE:
            return self.toggle_browse_focus_mode()
        if command.name is CommandName.REPEAT_LAST:
            return self.repeat_last_spoken()
        if command.name is CommandName.PAUSE_SPEECH:
            return self.speech_controller.toggle_pause()
        if command.name is CommandName.CYCLE_SPEECH_MODE:
            return self.cycle_speech_mode()
        if command.name is CommandName.STOP_SPEECH:
            return self.stop_speech()

        return False

    def handle_key(self, key: str, modifiers: tuple[str, ...] = ()) -> bool:
        logger.debug("key key=%r modifiers=%r mode=%s", key, modifiers, self.interaction_mode)
        if self._pass_next_key:
            if is_modifier_key(key):
                return False
            self._pass_next_key = False
            return False

        if self._input_help_active:
            if is_modifier_key(key):
                return True
            help_command = command_for_gesture((*modifiers, key))
            if help_command is not None and help_command.name is CommandName.INPUT_HELP:
                return self.handle_command(help_command)
            return self.speak_input_help(key, modifiers)

        if self._handle_modifier_shortcut(key, modifiers):
            return True

        command = command_for_gesture((*modifiers, key))
        if command is None:
            return self._handle_interaction_mode_key(key, modifiers)

        return self.handle_command(command)

    def repeat_last_spoken(self) -> bool:
        if self.speech_mode is SpeechMode.OFF:
            return self.speech_controller.last_spoken_text is not None

        return self.speech_controller.repeat_last()

    def stop_speech(self) -> bool:
        return self.speech_controller.stop()

    def cycle_speech_mode(self) -> bool:
        self._speech_mode_index = (self._speech_mode_index + 1) % len(self._speech_modes)
        logger.info("speech_mode_changed mode=%s", self.speech_mode)
        return self._speak_status(f"Speech mode {self.speech_mode.value}")

    def toggle_browse_focus_mode(self) -> bool:
        if self.interaction_mode is InteractionMode.BROWSE:
            self.interaction_mode = InteractionMode.FOCUS
            self._focus_mode_auto_entered = False
            logger.info("interaction_mode_changed mode=%s automatic=false", self.interaction_mode)
            return self._speak_command("Focus mode")

        self.interaction_mode = InteractionMode.BROWSE
        self._focus_mode_auto_entered = False
        logger.info("interaction_mode_changed mode=%s automatic=false", self.interaction_mode)
        return self._speak_command("Browse mode")

    def quit(self) -> bool:
        logger.info("quit_requested")
        self.quit_requested = True
        self.accessibility_backend.stop()
        return self._speak_status("Audioability exiting")

    def speak_input_help(self, key: str, modifiers: tuple[str, ...] = ()) -> bool:
        command = command_for_gesture((*modifiers, key))
        if command is None:
            normalized_key = normalize_key(key)
            normalized_modifiers = {normalize_key(modifier) for modifier in modifiers}
            label = self._quick_navigation_label(normalized_key)
            if label is not None and normalized_modifiers.issubset({"shift"}):
                direction = "previous" if "shift" in normalized_modifiers else "next"
                gesture = self._gesture_text(key, modifiers)
                return self._speak_command(f"{gesture} {direction} {label}")
            if normalized_key in {",", "<"} and normalized_modifiers.issubset({"shift"}):
                action = (
                    "start of container"
                    if normalized_modifiers or normalized_key == "<"
                    else "past end of container"
                )
                return self._speak_command(f"{self._gesture_text(key, modifiers)} {action}")
            return self._speak_command("Unassigned")

        return self._speak_command(f"{self._gesture_text(key, modifiers)} {command.description}")

    def speak_current_focus(self) -> bool:
        if self.current_focus is None:
            return False

        text = self._focused_node_text(self.current_focus)
        if not text:
            return False

        return self._speak_command(text)

    def speak_current_title(self) -> bool:
        root = self.object_navigator.root
        if root is None or not root.name.strip():
            return self._speak_command("No title")

        return self._speak_command(root.name)

    def speak_current_window(self) -> bool:
        node = self.object_navigator.root or self.current_focus
        if node is None:
            return self._speak_command("No window")

        text = self._focused_node_text(node)
        if not text:
            return self._speak_command("No window")

        return self._speak_command(text)

    def speak_status_bar(self) -> bool:
        root = self.object_navigator.root or self.current_focus
        status_bar = self._find_first_role(root, {"status bar", "statusbar"}) if root else None
        if status_bar is None:
            return self._speak_command("No status bar")

        return self._speak_command(self._focused_node_text(status_bar))

    def navigate_object(self, action: ObjectNavigationAction) -> bool:
        result = self.object_navigator.run(action)
        if result.node is not None:
            return self._speak_command(self._focused_node_text(result.node))
        if result.message:
            return self._speak_command(result.message)

        return result.handled

    def navigate_quick(self, key: str, *, direction: int) -> bool:
        label = self._quick_navigation_label(key)
        if label is None:
            return False

        result = self.object_navigator.move_to_match(
            lambda node: self._matches_quick_navigation(node, key),
            direction=direction,
            label=label,
        )
        if result.node is not None:
            return self._speak_command(self._focused_node_text(result.node))
        if result.message:
            return self._speak_command(result.message)
        return result.handled

    def navigate_container_boundary(self, *, to_start: bool) -> bool:
        result = self.object_navigator.move_to_container_boundary(to_start=to_start)
        if result.node is not None:
            return self._speak_command(self._focused_node_text(result.node))
        if result.message:
            return self._speak_command(result.message)
        return result.handled

    def handle_modifier_numpad(self, modifier_key: str, numpad_key: str) -> bool:
        if not is_screen_reader_modifier(modifier_key):
            return False

        action = self._numpad_object_navigation_action(numpad_key)
        if action is None:
            return False

        return self.navigate_object(action)

    def _handle_modifier_shortcut(self, key: str, modifiers: tuple[str, ...]) -> bool:
        modifier_key = self._screen_reader_modifier_from(modifiers)
        if modifier_key is None:
            return False

        if self.speech_controller.handle_modifier_arrow(
            modifier_key,
            key,
            announce=self.speech_mode is not SpeechMode.OFF,
        ):
            return True

        return self.handle_modifier_numpad(modifier_key, key)

    def _speak_focused_node(self, node: AccessibleNode) -> None:
        self.current_focus = node
        self.object_navigator.set_focus(node)
        self._sync_interaction_mode_for_focus(node)
        text = self._focused_node_text(node)
        if text:
            self._speak_auto(text)

    def _speak_focused_tree(self, root: AccessibleNode, focused: AccessibleNode) -> None:
        logger.debug(
            "focus_tree root_name=%r root_role=%r focused_name=%r focused_role=%r",
            root.name,
            root.role,
            focused.name,
            focused.role,
        )
        self.current_focus = focused
        self.object_navigator.set_root(root)
        self.object_navigator.set_focus(focused)
        self._sync_interaction_mode_for_focus(focused)
        text = self._focused_node_text(focused)
        if text:
            self._speak_auto(text)

    def _speak_state_change(
        self,
        node: AccessibleNode,
        state_name: str,
        enabled: bool,
    ) -> None:
        logger.debug(
            "state_change name=%r role=%r state=%s enabled=%s",
            node.name,
            node.role,
            state_name,
            enabled,
        )
        text = self._focused_node_text(node)
        if text:
            self._speak_auto(text)

    def _sync_interaction_mode_for_focus(self, node: AccessibleNode) -> None:
        if self._focus_mode_auto_entered and not self._requires_focus_mode(node):
            self.interaction_mode = InteractionMode.BROWSE
            self._focus_mode_auto_entered = False
            return

        if self.interaction_mode is InteractionMode.BROWSE and self._requires_focus_mode(node):
            self.interaction_mode = InteractionMode.FOCUS
            self._focus_mode_auto_entered = True

    def _handle_interaction_mode_key(self, key: str, modifiers: tuple[str, ...]) -> bool:
        normalized_key = normalize_key(key)
        normalized_modifiers = {normalize_key(modifier) for modifier in modifiers}
        if (
            self.interaction_mode is InteractionMode.FOCUS
            and self._focus_mode_auto_entered
            and normalized_key == "esc"
            and not normalized_modifiers
        ):
            self.interaction_mode = InteractionMode.BROWSE
            self._focus_mode_auto_entered = False
            return self._speak_command("Browse mode")

        if self.interaction_mode is InteractionMode.FOCUS:
            return False

        if normalized_modifiers.issubset({"shift"}):
            if normalized_key in {",", "<"}:
                return self.navigate_container_boundary(
                    to_start="shift" in normalized_modifiers or normalized_key == "<"
                )
            label = self._quick_navigation_label(normalized_key)
            if label is not None:
                direction = -1 if "shift" in normalized_modifiers else 1
                return self.navigate_quick(normalized_key, direction=direction)

        if normalized_modifiers:
            return False

        target = self.object_navigator.current or self.current_focus
        if normalized_key in {"enter", "space"} and target and self._requires_focus_mode(target):
            focused = target.focus()
            logger.debug("editable_focus_requested node=%r result=%s", target, focused)
            self.interaction_mode = InteractionMode.FOCUS
            self._focus_mode_auto_entered = True
            return self._speak_command("Focus mode")

        browse_action = self._browse_key_action(normalized_key)
        if browse_action is None:
            return False

        return self.navigate_object(browse_action)

    def _speak_typed_text(self, text: str) -> None:
        if self.interaction_mode is not InteractionMode.FOCUS:
            return

        spoken = {" ": "space", "\n": "enter", "\t": "tab"}.get(text, text)
        self._speak_auto(spoken)

    @staticmethod
    def _requires_focus_mode(node: AccessibleNode) -> bool:
        role = node.role.casefold().replace("-", " ")
        states = {state.casefold().replace("-", " ") for state in node.state}
        return bool(
            {"editable", "expanded"}.intersection(states)
            or (role == "table" and "focusable" in states)
            or role
            in {
                "combo box",
                "combobox",
                "entry",
                "editable text",
                "list",
                "list box",
                "listbox",
                "menu",
                "menu item",
                "spin button",
                "spinbutton",
                "text",
                "text area",
                "tree",
                "tree table",
            }
        )

    @staticmethod
    def _browse_key_action(key: str) -> ObjectNavigationAction | None:
        return {
            "down": ObjectNavigationAction.MOVE_TO_NEXT_FLAT,
            "right": ObjectNavigationAction.MOVE_TO_NEXT_FLAT,
            "up": ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT,
            "left": ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT,
            "enter": ObjectNavigationAction.ACTIVATE_CURRENT,
            "space": ObjectNavigationAction.ACTIVATE_CURRENT,
        }.get(key.removeprefix("arrow"))

    @staticmethod
    def _quick_navigation_label(key: str) -> str | None:
        labels = {
            "h": "heading",
            "l": "list",
            "i": "list item",
            "t": "table",
            "k": "link",
            "n": "non-linked text",
            "f": "form field",
            "u": "unvisited link",
            "v": "visited link",
            "e": "edit field",
            "b": "button",
            "x": "check box",
            "c": "combo box",
            "r": "radio button",
            "q": "block quote",
            "s": "separator",
            "m": "frame",
            "g": "graphic",
            "d": "landmark",
            "o": "embedded object",
            "a": "annotation",
            "p": "text paragraph",
            "w": "spelling error",
        }
        if key in "123456789":
            return f"heading level {key}"
        return labels.get(key)

    @classmethod
    def _matches_quick_navigation(cls, node: AccessibleNode, key: str) -> bool:
        role = node.role.casefold().replace("-", " ")
        states = {state.casefold().replace("-", " ") for state in node.state}
        button_roles = {
            "button",
            "push button",
            "toggle button",
            "drop down button",
            "menu button",
        }
        edit_roles = {"entry", "editable text", "password text", "text", "text area"}
        form_roles = button_roles | edit_roles | {
            "check box",
            "check menu item",
            "combo box",
            "list",
            "list box",
            "radio button",
            "slider",
            "spin button",
            "tree",
            "tree table",
        }
        heading = role == "heading" or role.startswith("heading level")
        link = role in {"link", "hyperlink"}
        matches = {
            "h": heading,
            "l": role in {"list", "list box"},
            "i": role in {"list item", "list box item"},
            "t": role in {"table", "tree table"},
            "k": link,
            "n": role in {"label", "paragraph", "static", "static text"},
            "f": role in form_roles,
            "u": link and "visited" not in states,
            "v": link and "visited" in states,
            "e": role in edit_roles and ("editable" in states or role != "text"),
            "b": role in button_roles,
            "x": role in {"check box", "check menu item"},
            "c": role in {"combo box", "combobox"},
            "r": role == "radio button",
            "q": role in {"block quote", "blockquote"},
            "s": role in {"separator", "horizontal separator", "vertical separator"},
            "m": role in {"frame", "internal frame"},
            "g": role in {"canvas", "graphic", "icon", "image"},
            "d": role in {"landmark", "header", "footer", "navigation"}
            or bool(cls._attribute_value(node, "xml-roles")),
            "o": role in {
                "application",
                "audio",
                "dialog",
                "embedded",
                "embedded object",
                "plugin",
                "video",
            },
            "a": role in {"annotation", "comment", "footnote", "endnote"},
            "p": role == "paragraph",
            "w": "invalid" in states or role == "spelling error",
        }
        if key in "123456789":
            return heading and cls._heading_level(node) == int(key)
        return matches.get(key, False)

    @staticmethod
    def _screen_reader_modifier_from(modifiers: tuple[str, ...]) -> str | None:
        return next(
            (modifier for modifier in modifiers if is_screen_reader_modifier(modifier)),
            None,
        )

    @staticmethod
    def _gesture_text(key: str, modifiers: tuple[str, ...]) -> str:
        parts = (*modifiers, key)
        return "+".join(normalize_key(part) for part in parts if part.strip())

    def _focused_node_text(self, node: AccessibleNode) -> str:
        if self.speech_controller.settings.verbosity is VerbosityMode.BRIEF:
            brief_parts = [
                node.name,
                node.role,
                *self._state_text(node),
                self._level_text(node),
                self._unique_detail(node.value, node.name),
            ]
            return " ".join(part for part in brief_parts if part)

        parts = [
            node.name,
            node.role,
            *self._state_text(node),
            self._level_text(node),
            self._position_text(node),
            self._unique_detail(node.value, node.name),
            self._unique_detail(node.text, node.name, node.description),
            self._unique_detail(node.placeholder, node.name, node.text),
            node.description,
            self._children_text(node),
            self._shortcut_text(node),
        ]
        return " ".join(part for part in parts if part)

    @staticmethod
    def _state_text(node: AccessibleNode) -> tuple[str, ...]:
        spoken_states = (
            "checked",
            "pressed",
            "selected",
            "expanded",
            "collapsed",
            "required",
            "invalid",
            "editable",
            "disabled",
        )
        states = set(node.state)
        result = [state for state in spoken_states if state in states]
        role = node.role.casefold().replace("-", " ")
        if role in {"check box", "check menu item", "radio button"} and "checked" not in states:
            result.insert(0, "not checked")
        if role == "toggle button" and "pressed" not in states:
            result.insert(0, "not pressed")
        return tuple(result)

    @classmethod
    def _level_text(cls, node: AccessibleNode) -> str:
        level = cls._heading_level(node) or cls._numeric_attribute(node, "level")
        return f"level {level}" if level is not None else ""

    @classmethod
    def _position_text(cls, node: AccessibleNode) -> str:
        position = cls._numeric_attribute(node, "posinset")
        size = cls._numeric_attribute(node, "setsize")
        return f"{position} of {size}" if position is not None and size is not None else ""

    @classmethod
    def _heading_level(cls, node: AccessibleNode) -> int | None:
        level = cls._numeric_attribute(node, "level")
        if level is not None:
            return level
        words = node.role.casefold().replace("-", " ").split()
        return int(words[-1]) if words and words[-1].isdigit() else None

    @classmethod
    def _numeric_attribute(cls, node: AccessibleNode, name: str) -> int | None:
        value = cls._attribute_value(node, name)
        return int(value) if value.isdigit() else None

    @staticmethod
    def _attribute_value(node: AccessibleNode, name: str) -> str:
        for attribute in node.attributes:
            for separator in (":", "="):
                prefix = f"{name}{separator}"
                if attribute.casefold().startswith(prefix):
                    return attribute[len(prefix) :].strip()
        return ""

    @staticmethod
    def _unique_detail(value: str, *existing_values: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""

        existing = {item.strip().casefold() for item in existing_values if item.strip()}
        return "" if normalized.casefold() in existing else normalized

    def _children_text(self, node: AccessibleNode) -> str:
        if node.children and self._is_unnamed_container(node):
            return "; ".join(
                filter(
                    None,
                    (self._focused_node_text(child) for child in node.children[:5]),
                )
            )

        child_count = node.child_count or len(node.children)
        if child_count <= 0:
            return ""
        if child_count == 1:
            return "1 item"

        return f"{child_count} items"

    @staticmethod
    def _is_unnamed_container(node: AccessibleNode) -> bool:
        generic_container_roles = {
            "",
            "container",
            "filler",
            "frame",
            "panel",
            "scroll pane",
            "section",
            "viewport",
        }
        return not node.name.strip() and node.role.casefold() in generic_container_roles

    @staticmethod
    def _shortcut_text(node: AccessibleNode) -> str:
        return f"shortcut {node.shortcut}" if node.shortcut else ""

    @staticmethod
    def _find_first_role(
        node: AccessibleNode,
        roles: frozenset[str] | set[str],
    ) -> AccessibleNode | None:
        if node.role.casefold() in roles:
            return node

        for child in node.children:
            found = ScreenReaderApplication._find_first_role(child, roles)
            if found is not None:
                return found

        return None

    @classmethod
    def _numpad_object_navigation_action(
        cls,
        numpad_key: str,
    ) -> ObjectNavigationAction | None:
        return {
            "numpad8": ObjectNavigationAction.MOVE_TO_PARENT,
            "numpad4": ObjectNavigationAction.MOVE_TO_PREVIOUS,
            "numpad5": ObjectNavigationAction.REPORT_CURRENT,
            "numpad6": ObjectNavigationAction.MOVE_TO_NEXT,
            "numpad2": ObjectNavigationAction.MOVE_TO_FIRST_CHILD,
            "numpad9": ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT,
            "numpad3": ObjectNavigationAction.MOVE_TO_NEXT_FLAT,
            "numpadminus": ObjectNavigationAction.MOVE_TO_FOCUS,
            "numpadenter": ObjectNavigationAction.ACTIVATE_CURRENT,
        }.get(normalize_key(numpad_key))

    @property
    def speech_mode(self) -> SpeechMode:
        return self._speech_modes[self._speech_mode_index]

    def _speak_auto(self, text: str) -> bool:
        logger.debug("speech_auto mode=%s text=%r", self.speech_mode, text)
        if self.speech_mode is not SpeechMode.TALK:
            return False

        return self.speech_controller.speak(text)

    def _speak_command(self, text: str) -> bool:
        cleaned_text = text.strip()
        if not cleaned_text:
            return False
        if self.speech_mode is SpeechMode.OFF:
            logger.debug("speech_command_suppressed mode=off text=%r", cleaned_text)
            return True

        logger.debug("speech_command text=%r", cleaned_text)
        return self.speech_controller.speak(cleaned_text, allow_duplicate=True)

    def _speak_status(self, text: str) -> bool:
        logger.info("speech_status text=%r", text)
        return self.speech_controller.speak(text, allow_duplicate=True)
