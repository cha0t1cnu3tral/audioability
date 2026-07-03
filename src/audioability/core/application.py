from __future__ import annotations

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
    command_for_key,
    is_screen_reader_modifier,
)
from audioability.input.router import CommandRouter
from audioability.speech.controller import SpeechController
from audioability.speech.drivers import NullSpeechDriver, SpeechDispatcherDriver, SpeechDriver


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
        self.speech_controller = SpeechController(self.speech_driver)
        self.current_focus: AccessibleNode | None = None
        self.object_navigator = ObjectNavigator()
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
            else AtSpiAccessibilityBackend(on_focus=self._speak_focused_node)
        )

    def run(self) -> None:
        if self.dry_run:
            self.speech_controller.speak("Audioability initialized in dry-run mode.")
            return

        self.speech_controller.speak("Audioability started.")
        self.accessibility_backend.start()

    def handle_command(self, command: Command) -> bool:
        if command.name is CommandName.READ_FOCUS:
            return self.speak_current_focus()
        if command.name is CommandName.REPEAT_LAST:
            return self.repeat_last_spoken()
        if command.name is CommandName.STOP_SPEECH:
            return self.stop_speech()

        return False

    def handle_key(self, key: str) -> bool:
        command = command_for_key(key)
        if command is None:
            return False

        return self.handle_command(command)

    def repeat_last_spoken(self) -> bool:
        return self.speech_controller.repeat_last()

    def stop_speech(self) -> bool:
        return self.speech_controller.stop()

    def speak_current_focus(self) -> bool:
        if self.current_focus is None:
            return False

        text = self._focused_node_text(self.current_focus)
        if not text:
            return False

        return self.speech_controller.speak(text, allow_duplicate=True)

    def navigate_object(self, action: ObjectNavigationAction) -> bool:
        result = self.object_navigator.run(action)
        if result.node is not None:
            return self.speech_controller.speak(
                self._focused_node_text(result.node),
                allow_duplicate=True,
            )
        if result.message:
            return self.speech_controller.speak(result.message, allow_duplicate=True)

        return result.handled

    def handle_modifier_numpad(self, modifier_key: str, numpad_key: str) -> bool:
        if not is_screen_reader_modifier(modifier_key):
            return False

        action = self._numpad_object_navigation_action(numpad_key)
        if action is None:
            return False

        return self.navigate_object(action)

    def _speak_focused_node(self, node: AccessibleNode) -> None:
        self.current_focus = node
        self.object_navigator.set_focus(node)
        text = self._focused_node_text(node)
        if text:
            self.speech_controller.speak(text)

    @staticmethod
    def _focused_node_text(node: AccessibleNode) -> str:
        parts = [
            node.name,
            node.role,
            *ScreenReaderApplication._state_text(node),
            ScreenReaderApplication._unique_detail(node.value, node.name),
            ScreenReaderApplication._unique_detail(node.text, node.name, node.description),
            ScreenReaderApplication._unique_detail(node.placeholder, node.name, node.text),
            node.description,
            ScreenReaderApplication._children_text(node),
            ScreenReaderApplication._shortcut_text(node),
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
        return tuple(state for state in spoken_states if state in states)

    @staticmethod
    def _unique_detail(value: str, *existing_values: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""

        existing = {item.strip().casefold() for item in existing_values if item.strip()}
        return "" if normalized.casefold() in existing else normalized

    @staticmethod
    def _children_text(node: AccessibleNode) -> str:
        if node.children and ScreenReaderApplication._is_unnamed_container(node):
            return "; ".join(
                filter(
                    None,
                    (
                        ScreenReaderApplication._focused_node_text(child)
                        for child in node.children[:5]
                    ),
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
        }.get(cls._normalize_key(numpad_key))

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.lower().replace("_", "").replace("-", "")
