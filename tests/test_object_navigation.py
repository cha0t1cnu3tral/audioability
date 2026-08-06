from __future__ import annotations

from audioability.accessibility.models import AccessibleNode
from audioability.accessibility.navigation import ObjectNavigationAction, ObjectNavigator


def test_object_navigator_moves_to_parent_previous_next_and_child() -> None:
    first = AccessibleNode(name="First", role="button")
    second = AccessibleNode(
        name="Second",
        role="group",
        children=(AccessibleNode(name="Nested", role="checkbox"),),
    )
    root = AccessibleNode(name="Window", role="frame", children=(first, second))
    navigator = ObjectNavigator(root)

    assert navigator.run(ObjectNavigationAction.MOVE_TO_FIRST_CHILD).node == first
    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT).node == second
    assert navigator.run(ObjectNavigationAction.MOVE_TO_PREVIOUS).node == first
    assert navigator.run(ObjectNavigationAction.MOVE_TO_PARENT).node == root


def test_object_navigator_moves_through_flattened_tree() -> None:
    nested = AccessibleNode(name="Nested", role="checkbox")
    group = AccessibleNode(name="Group", role="group", children=(nested,))
    root = AccessibleNode(name="Window", role="frame", children=(group,))
    navigator = ObjectNavigator(root)

    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT).node == group
    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT).node == nested
    assert navigator.run(ObjectNavigationAction.MOVE_TO_PREVIOUS_FLAT).node == group


def test_object_navigator_skips_non_showing_subtrees() -> None:
    hidden_button = AccessibleNode(
        "Hidden",
        "button",
        state=frozenset({"visible", "enabled"}),
    )
    hidden_page = AccessibleNode(
        "Inactive page contents",
        "panel",
        state=frozenset({"visible", "enabled"}),
        children=(hidden_button,),
    )
    shown_button = AccessibleNode(
        "Shown",
        "button",
        state=frozenset({"visible", "showing", "enabled"}),
    )
    root = AccessibleNode("Window", "frame", children=(hidden_page, shown_button))
    navigator = ObjectNavigator(root)

    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT).node is shown_button


def test_object_navigator_does_not_activate_disabled_control() -> None:
    activated = False

    def activate() -> bool:
        nonlocal activated
        activated = True
        return True

    button = AccessibleNode(
        "Unavailable",
        "button",
        state=frozenset({"disabled"}),
        activation=activate,
    )
    result = ObjectNavigator(button).run(ObjectNavigationAction.ACTIVATE_CURRENT)

    assert result.handled is False
    assert activated is False


def test_object_navigator_reports_focus_and_current_object() -> None:
    first = AccessibleNode(name="First", role="button")
    second = AccessibleNode(name="Second", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first, second))
    navigator = ObjectNavigator(root)

    navigator.set_focus(second)

    assert navigator.run(ObjectNavigationAction.REPORT_CURRENT).node == second
    assert navigator.run(ObjectNavigationAction.MOVE_TO_PREVIOUS).node == first
    assert navigator.run(ObjectNavigationAction.MOVE_TO_FOCUS).node == second


def test_object_navigator_activates_current_object() -> None:
    activated = False

    def activate() -> bool:
        nonlocal activated
        activated = True
        return True

    button = AccessibleNode(name="Submit", role="button", activation=activate)
    navigator = ObjectNavigator(button)

    result = navigator.run(ObjectNavigationAction.ACTIVATE_CURRENT)

    assert result.handled is True
    assert result.node == button
    assert activated is True


def test_object_navigator_moves_to_next_and_previous_matching_object() -> None:
    heading = AccessibleNode(name="Overview", role="heading")
    button = AccessibleNode(name="Save", role="button")
    second_heading = AccessibleNode(name="Details", role="heading")
    root = AccessibleNode(
        name="Document",
        role="document",
        children=(heading, button, second_heading),
    )
    navigator = ObjectNavigator(root)

    result = navigator.move_to_match(
        lambda node: node.role == "heading",
        direction=1,
        label="heading",
    )
    assert result.node is heading
    result = navigator.move_to_match(
        lambda node: node.role == "heading",
        direction=1,
        label="heading",
    )
    assert result.node is second_heading
    result = navigator.move_to_match(
        lambda node: node.role == "heading",
        direction=-1,
        label="heading",
    )
    assert result.node is heading


def test_object_navigator_reports_when_no_matching_object_remains() -> None:
    root = AccessibleNode(name="Document", role="document")
    navigator = ObjectNavigator(root)

    result = navigator.move_to_match(
        lambda node: node.role == "heading",
        direction=1,
        label="heading",
    )

    assert result.handled is False
    assert result.message == "No next heading"


def test_object_navigator_moves_to_start_and_past_container() -> None:
    first = AccessibleNode("First", "list item")
    second = AccessibleNode("Second", "list item")
    items = AccessibleNode("Topics", "list", children=(first, second))
    after = AccessibleNode("After", "heading")
    root = AccessibleNode("Document", "document", children=(items, after))
    navigator = ObjectNavigator(root)
    navigator.current = second

    result = navigator.move_to_container_boundary(to_start=True)
    assert result.node is first
    navigator.current = second
    result = navigator.move_to_container_boundary(to_start=False)
    assert result.node is after


def test_object_navigator_reports_missing_action() -> None:
    navigator = ObjectNavigator(AccessibleNode(name="Label", role="label"))

    result = navigator.run(ObjectNavigationAction.ACTIVATE_CURRENT)

    assert result.handled is False
    assert result.message == "No action"


def test_object_navigator_distinguishes_identical_siblings() -> None:
    first = AccessibleNode(name="Item", role="button")
    second = AccessibleNode(name="Item", role="button")
    third = AccessibleNode(name="Item", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first, second, third))
    navigator = ObjectNavigator(root)
    navigator.set_focus(second)

    assert navigator.run(ObjectNavigationAction.MOVE_TO_PREVIOUS).node is first
    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT).node is second
    assert navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT).node is third


def test_object_navigator_handles_focus_outside_cached_tree() -> None:
    root = AccessibleNode(name="Old window", role="frame")
    new_focus = AccessibleNode(name="New control", role="button")
    navigator = ObjectNavigator(root)
    navigator.set_focus(new_focus)

    result = navigator.run(ObjectNavigationAction.MOVE_TO_NEXT_FLAT)

    assert result.handled is False
    assert result.node is new_focus
    assert result.message == "No object"


def test_object_navigator_moves_across_table_rows_and_columns() -> None:
    headers = tuple(
        AccessibleNode(name, "table column header")
        for name in ("Item", "Status", "Enabled")
    )
    cells = tuple(
        AccessibleNode(name, "table cell")
        for name in ("Alpha", "Ready", "Yes", "Bravo", "Review", "No")
    )
    table = AccessibleNode("Projects", "tree table", children=(*headers, *cells))
    navigator = ObjectNavigator(table)

    first = navigator.move_table_cell("right")
    assert first.node is cells[0]
    assert first.table_position is not None
    assert first.table_position.column_header == "Item"

    second = navigator.move_table_cell("right")
    assert second.node is cells[1]
    assert second.table_position is not None
    assert (second.table_position.row, second.table_position.column) == (0, 1)

    below = navigator.move_table_cell("down")
    assert below.node is cells[4]
    assert below.table_position is not None
    assert (below.table_position.row, below.table_position.column) == (1, 1)

    assert navigator.move_table_cell("left").node is cells[3]
    edge = navigator.move_table_cell("left")
    assert edge.handled is True
    assert edge.message == "Edge of table"


def test_object_navigator_moves_to_table_edges() -> None:
    headers = tuple(AccessibleNode(str(index), "column header") for index in range(3))
    cells = tuple(AccessibleNode(str(index), "cell") for index in range(9))
    table = AccessibleNode("Data", "table", children=(*headers, *cells))
    navigator = ObjectNavigator(table)

    navigator.move_table_cell("right")
    assert navigator.move_table_cell("end").node is cells[2]
    assert navigator.move_table_cell("pagedown").node is cells[8]
    assert navigator.move_table_cell("home").node is cells[6]
    assert navigator.move_table_cell("pageup").node is cells[0]
