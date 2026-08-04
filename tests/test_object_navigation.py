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
