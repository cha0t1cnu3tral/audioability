from __future__ import annotations

from audioability.input.router import CommandRouter


def test_router_runs_registered_action() -> None:
    calls: list[str] = []

    def repeat() -> bool:
        calls.append("repeat")
        return True

    router = CommandRouter({"repeat": repeat})

    assert router.run("repeat") is True
    assert calls == ["repeat"]


def test_router_normalizes_command_names() -> None:
    router = CommandRouter({"repeat-last": lambda: True})

    assert router.run(" REPEAT_LAST ") is True


def test_router_returns_false_for_unknown_command() -> None:
    router = CommandRouter({"repeat": lambda: True})

    assert router.run("missing") is False
