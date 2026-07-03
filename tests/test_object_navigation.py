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


def test_object_navigator_reports_focus_and_current_object() -> None:
    first = AccessibleNode(name="First", role="button")
    second = AccessibleNode(name="Second", role="button")
    root = AccessibleNode(name="Window", role="frame", children=(first, second))
    navigator = ObjectNavigator(root)

    navigator.set_focus(second)

    assert navigator.run(ObjectNavigationAction.REPORT_CURRENT).node == second
    assert navigator.run(ObjectNavigationAction.MOVE_TO_PREVIOUS).node == first
    assert navigator.run(ObjectNavigationAction.MOVE_TO_FOCUS).node == second
