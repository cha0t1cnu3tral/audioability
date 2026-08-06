from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from audioability.accessibility.models import AccessibleNode

logger = logging.getLogger(__name__)


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
class TableCellPosition:
    row: int
    column: int
    row_count: int
    column_count: int
    column_header: str = ""


@dataclass(frozen=True)
class ObjectNavigationResult:
    handled: bool
    node: AccessibleNode | None = None
    message: str = ""
    table_position: TableCellPosition | None = None


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

    def move_to_match(
        self,
        predicate: Callable[[AccessibleNode], bool],
        *,
        direction: int,
        label: str,
    ) -> ObjectNavigationResult:
        if self.current is None or self.root is None:
            return ObjectNavigationResult(False, message=f"No {label}")

        flattened = self._flatten(self.root)
        current_index = self._identity_index(flattened, self.current)
        if current_index is None:
            return ObjectNavigationResult(False, message=f"No {label}")

        indexes = (
            range(current_index + 1, len(flattened))
            if direction > 0
            else range(current_index - 1, -1, -1)
        )
        for index in indexes:
            if predicate(flattened[index]):
                self.current = flattened[index]
                return ObjectNavigationResult(True, self.current)

        relative = "next" if direction > 0 else "previous"
        return ObjectNavigationResult(False, message=f"No {relative} {label}")

    def move_to_container_boundary(self, *, to_start: bool) -> ObjectNavigationResult:
        if self.current is None or self.root is None:
            return ObjectNavigationResult(False, message="No containing list or table")

        path = self._path_to_current()
        if path is None:
            return ObjectNavigationResult(False, message="No containing list or table")
        container_roles = {"list", "list box", "table", "tree", "tree table"}
        container = next(
            (
                node
                for node in reversed(path)
                if node.role.casefold().replace("-", " ") in container_roles
            ),
            None,
        )
        if container is None:
            return ObjectNavigationResult(False, message="No containing list or table")

        if to_start:
            self.current = container.children[0] if container.children else container
            return ObjectNavigationResult(True, self.current)

        flattened = self._flatten(self.root)
        descendants = self._flatten(container)
        last_index = self._identity_index(flattened, descendants[-1])
        if last_index is None or last_index + 1 >= len(flattened):
            return ObjectNavigationResult(False, message="No object after container")
        self.current = flattened[last_index + 1]
        return ObjectNavigationResult(True, self.current)

    def move_table_cell(self, key: str) -> ObjectNavigationResult:
        table = self._containing_table()
        if table is None:
            return ObjectNavigationResult(False, message="Not in a table")

        headers, rows = self._table_grid(table)
        if not rows or not rows[0]:
            return ObjectNavigationResult(True, message="Empty table")

        position = self._cell_coordinates(rows, self.current)
        if position is None:
            row = 0
            column = 0
        else:
            row, column = position
            normalized_key = key.casefold().removeprefix("arrow")
            if normalized_key == "left":
                column -= 1
            elif normalized_key == "right":
                column += 1
            elif normalized_key == "up":
                row -= 1
            elif normalized_key == "down":
                row += 1
            elif normalized_key == "home":
                column = 0
            elif normalized_key == "end":
                column = len(rows[row]) - 1
            elif normalized_key == "pageup":
                row = 0
            elif normalized_key == "pagedown":
                row = len(rows) - 1
            else:
                return ObjectNavigationResult(False, message="Unknown table command")

        if row < 0 or row >= len(rows) or column < 0 or column >= len(rows[row]):
            return ObjectNavigationResult(True, self.current, "Edge of table")

        self.current = rows[row][column]
        header = headers[column].name if column < len(headers) else ""
        table_position = TableCellPosition(
            row=row,
            column=column,
            row_count=len(rows),
            column_count=max(len(table_row) for table_row in rows),
            column_header=header,
        )
        return ObjectNavigationResult(True, self.current, table_position=table_position)

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
        current_index = self._identity_index(siblings, path[-1])
        if current_index is None:
            return ObjectNavigationResult(False, self.current, "No sibling object")

        index = current_index + direction
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
        current_index = self._identity_index(flattened, self.current)
        if current_index is None:
            return ObjectNavigationResult(False, self.current, "No object")

        index = current_index + direction
        if index < 0 or index >= len(flattened):
            return ObjectNavigationResult(False, self.current, "No object")

        self.current = flattened[index]
        return ObjectNavigationResult(True, self.current)

    def _activate_current(self) -> ObjectNavigationResult:
        if self.current is None:
            logger.debug("object_activation result=no-current")
            return ObjectNavigationResult(False, message="No navigator object")
        activated = self.current.activate()
        logger.debug(
            "object_activation name=%r role=%r result=%s",
            self.current.name,
            self.current.role,
            activated,
        )
        if not activated:
            return ObjectNavigationResult(False, message="No action")

        return ObjectNavigationResult(True, self.current, "Activate current object")

    def _path_to_current(self) -> tuple[AccessibleNode, ...] | None:
        if self.root is None or self.current is None:
            return None

        return self._find_path(self.root, self.current)

    def _containing_table(self) -> AccessibleNode | None:
        path = self._path_to_current()
        if path is None:
            return None
        return next(
            (
                node
                for node in reversed(path)
                if self._normalized_role(node) in {"table", "tree table"}
            ),
            None,
        )

    def _table_grid(
        self, table: AccessibleNode
    ) -> tuple[tuple[AccessibleNode, ...], tuple[tuple[AccessibleNode, ...], ...]]:
        row_roles = {"table row", "row"}
        cell_roles = {"cell", "table cell", "table row header", "row header"}
        header_roles = {"column header", "table column header"}
        row_nodes = [child for child in table.children if self._normalized_role(child) in row_roles]
        headers = tuple(
            child for child in table.children if self._normalized_role(child) in header_roles
        )
        if row_nodes:
            rows = tuple(
                tuple(
                    child
                    for child in row_node.children
                    if self._normalized_role(child) in cell_roles | header_roles
                )
                for row_node in row_nodes
            )
            return headers, tuple(row for row in rows if row)

        direct_headers: list[AccessibleNode] = []
        direct_cells: list[AccessibleNode] = []
        reading_headers = True
        for child in table.children:
            role = self._normalized_role(child)
            if reading_headers and role in header_roles:
                direct_headers.append(child)
                continue
            reading_headers = False
            if role in cell_roles:
                direct_cells.append(child)

        column_count = len(direct_headers) or self._table_column_count(table)
        if column_count <= 0:
            column_count = len(direct_cells)
        rows = tuple(
            tuple(direct_cells[index : index + column_count])
            for index in range(0, len(direct_cells), column_count)
        )
        return tuple(direct_headers), rows

    @staticmethod
    def _cell_coordinates(
        rows: tuple[tuple[AccessibleNode, ...], ...],
        current: AccessibleNode | None,
    ) -> tuple[int, int] | None:
        return next(
            (
                (row_index, column_index)
                for row_index, row in enumerate(rows)
                for column_index, cell in enumerate(row)
                if cell is current
            ),
            None,
        )

    @staticmethod
    def _table_column_count(table: AccessibleNode) -> int:
        for attribute in table.attributes:
            normalized = attribute.casefold().replace("_", "-")
            for prefix in ("column-count:", "column-count=", "columns:", "columns="):
                if normalized.startswith(prefix):
                    value = normalized.removeprefix(prefix).strip()
                    if value.isdigit():
                        return int(value)
        return 0

    @staticmethod
    def _normalized_role(node: AccessibleNode) -> str:
        return node.role.casefold().replace("-", " ")

    def _find_path(
        self,
        node: AccessibleNode,
        target: AccessibleNode,
        path: tuple[AccessibleNode, ...] = (),
    ) -> tuple[AccessibleNode, ...] | None:
        next_path = (*path, node)
        if node is target:
            return next_path

        for child in node.children:
            found = self._find_path(child, target, next_path)
            if found is not None:
                return found

        return None

    def _flatten(self, node: AccessibleNode) -> tuple[AccessibleNode, ...]:
        states = {state.casefold().replace("-", " ") for state in node.state}
        if "visible" in states and "showing" not in states:
            return ()
        descendants = tuple(child for item in node.children for child in self._flatten(item))
        return (node, *descendants)

    @staticmethod
    def _identity_index(
        nodes: tuple[AccessibleNode, ...], target: AccessibleNode
    ) -> int | None:
        return next((index for index, node in enumerate(nodes) if node is target), None)
