from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from audioability.accessibility.models import AccessibleNode


class ObjectNavigationAction(StrEnum):
    MOVE_TO_PARENT = "parent"
    MOVE_TO_PREVIOUS = "previous"
    REPORT_CURRENT = "current"
    MOVE_TO_NEXT = "next"
    MOVE_TO_FIRST_CHILD = "first-child"
    MOVE_TO_PREVIOUS_FLAT = "previous-flat"
    MOVE_TO_NEXT_FLAT = "next-flat"
    MOVE_TO_FOCUS = "focus"
    ACTIVATE_CURRENT = "activate"


@dataclass(frozen=True)
class ObjectNavigationResult:
    handled: bool
    node: AccessibleNode | None = None
    message: str = ""


class ObjectNavigator:
    """Navigates an accessible object tree with NVDA-style object commands."""

    def __init__(self, root: AccessibleNode | None = None) -> None:
        self.root = root
        self.current: AccessibleNode | None = root
        self.focus: AccessibleNode | None = root

    def set_root(self, root: AccessibleNode) -> None:
        self.root = root
        self.current = root
        self.focus = root

    def set_focus(self, node: AccessibleNode) -> None:
        if self.root is None:
            self.root = node
        self.focus = node
        self.current = node

    def run(self, action: ObjectNavigationAction) -> ObjectNavigationResult:
        if action is ObjectNavigationAction.REPORT_CURRENT:
            return self._report_current()
        if action is ObjectNavigationAction.MOVE_TO_FOCUS:
            return self._move_to_focus()
        if action is ObjectNavigationAction.MOVE_TO_PARENT:
            return self._move_to_parent()
        if action is ObjectNavigationAction.MOVE_TO_PREVIOUS:
            return self._move_to_sibling(-1)
        if action is ObjectNavigationAction.MOVE_TO_NEXT:
            return self._move_to_sibling(1)
        if action is ObjectNavigationAction.MOVE_TO_FIRST_CHILD:
            return self._move_to_first_child()
        if action is ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT:
            return self._move_flat(-1)
        if action is ObjectNavigationAction.MOVE_TO_NEXT_FLAT:
            return self._move_flat(1)
        if action is ObjectNavigationAction.ACTIVATE_CURRENT:
            return self._activate_current()

        return ObjectNavigationResult(False, message="Unknown object navigation command")

    def _report_current(self) -> ObjectNavigationResult:
        if self.current is None:
            return ObjectNavigationResult(False, message="No navigator object")

        return ObjectNavigationResult(True, self.current)

    def _move_to_focus(self) -> ObjectNavigationResult:
        if self.focus is None:
            return ObjectNavigationResult(False, message="No focused object")

        self.current = self.focus
        return ObjectNavigationResult(True, self.current)

    def _move_to_parent(self) -> ObjectNavigationResult:
        if self.current is None:
            return ObjectNavigationResult(False, message="No navigator object")

        path = self._path_to_current()
        if path is None or len(path) < 2:
            return ObjectNavigationResult(False, self.current, "No parent object")

        self.current = path[-2]
        return ObjectNavigationResult(True, self.current)

    def _move_to_sibling(self, direction: int) -> ObjectNavigationResult:
        if self.current is None:
            return ObjectNavigationResult(False, message="No navigator object")

        path = self._path_to_current()
        if path is None or len(path) < 2:
            return ObjectNavigationResult(False, self.current, "No sibling object")

        siblings = path[-2].children
        index = siblings.index(path[-1]) + direction
        if index < 0 or index >= len(siblings):
            return ObjectNavigationResult(False, self.current, "No sibling object")

        self.current = siblings[index]
        return ObjectNavigationResult(True, self.current)

    def _move_to_first_child(self) -> ObjectNavigationResult:
        if self.current is None:
            return ObjectNavigationResult(False, message="No navigator object")
        if not self.current.children:
            return ObjectNavigationResult(False, self.current, "No child object")

        self.current = self.current.children[0]
        return ObjectNavigationResult(True, self.current)

    def _move_flat(self, direction: int) -> ObjectNavigationResult:
        if self.current is None or self.root is None:
            return ObjectNavigationResult(False, message="No navigator object")

        flattened = self._flatten(self.root)
        index = flattened.index(self.current) + direction
        if index < 0 or index >= len(flattened):
            return ObjectNavigationResult(False, self.current, "No object")

        self.current = flattened[index]
        return ObjectNavigationResult(True, self.current)

    def _activate_current(self) -> ObjectNavigationResult:
        if self.current is None:
            return ObjectNavigationResult(False, message="No navigator object")

        return ObjectNavigationResult(True, self.current, "Activate current object")

    def _path_to_current(self) -> tuple[AccessibleNode, ...] | None:
        if self.root is None or self.current is None:
            return None

        return self._find_path(self.root, self.current)

    def _find_path(
        self,
        node: AccessibleNode,
        target: AccessibleNode,
        path: tuple[AccessibleNode, ...] = (),
    ) -> tuple[AccessibleNode, ...] | None:
        next_path = (*path, node)
        if node == target:
            return next_path

        for child in node.children:
            found = self._find_path(child, target, next_path)
            if found is not None:
                return found

        return None

    def _flatten(self, node: AccessibleNode) -> tuple[AccessibleNode, ...]:
        descendants = tuple(child for item in node.children for child in self._flatten(item))
        return (node, *descendants)
