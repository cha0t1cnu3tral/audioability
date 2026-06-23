from __future__ import annotations

from collections.abc import Callable, Mapping


class CommandRouter:
    """Routes short command names to application actions."""

    def __init__(self, actions: Mapping[str, Callable[[], bool]]) -> None:
        self._actions = {self._normalize(name): action for name, action in actions.items()}

    def run(self, command_name: str) -> bool:
        action = self._actions.get(self._normalize(command_name))
        if action is None:
            return False

        return action()

    @staticmethod
    def _normalize(command_name: str) -> str:
        return command_name.strip().lower().replace("_", "-")
