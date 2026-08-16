from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SettingsStore:
    """Small, best-effort JSON store for preferences between launches."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path.expanduser()
            return

        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
        self.path = base / "audioability" / "settings.json"

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

        return value if isinstance(value, dict) else {}

    def save(self, settings: dict[str, Any]) -> None:
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(settings, temporary_file, indent=2, sort_keys=True)
                temporary_file.write("\n")
            temporary_path.replace(self.path)
        except OSError:
            logger.warning("settings_save_failed path=%s", self.path, exc_info=True)
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink()
