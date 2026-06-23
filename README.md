# Audioability

Audioability is a Python project scaffold for a Linux screen reader. It is set up for `uv`,
uses a `src/` package layout, and keeps Linux desktop integration behind adapters so core
screen-reader behavior can be tested without a running desktop session.

## Development

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run mypy
uv run audioability --help
```

On Linux, the real accessibility backend will need AT-SPI and speech services from the
system package manager. Common packages include:

- `python3-pyatspi`
- `python3-gi`
- `at-spi2-core`
- `speech-dispatcher`
- `python3-speechd`

Exact package names vary by distribution.

## Project Layout

- `src/audioability/core/`: event routing, app lifecycle, and screen-reader orchestration
- `src/audioability/accessibility/`: AT-SPI-facing adapters and accessible object models
- `src/audioability/speech/`: speech output abstraction and drivers
- `src/audioability/input/`: keyboard and command input handling
- `docs/`: architecture and Linux setup notes
- `tests/`: unit tests for core behavior

## Status

This repository currently contains the development scaffold and a runnable CLI. The Linux
AT-SPI and speech-dispatcher integrations are intentionally isolated as adapters so they can
be implemented and tested incrementally.
