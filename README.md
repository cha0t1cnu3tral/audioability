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

## Run on Linux

Copy `dist/audioability-linux.run` to a Linux desktop machine, then run:

```bash
chmod +x audioability-linux.run
./audioability-linux.run --dry-run
./audioability-linux.run
```

The Linux runner detects common package managers (`apt-get`, `dnf`, `pacman`, or
`zypper`), installs AT-SPI and speech packages, unpacks Audioability into
`~/.local/share/audioability`, creates a venv with access to system accessibility
packages, and starts the screen reader. Use `--no-system-packages` if you already
installed the desktop accessibility packages yourself.

On Linux, the real accessibility backend will need AT-SPI and speech services from the
system package manager. Common packages include:

- `python3-pyatspi`
- `python3-gi`
- `at-spi2-core`
- `speech-dispatcher`
- `python3-speechd`
- Arch: `python-atspi`, `python-gobject`, `at-spi2-core`, `speech-dispatcher`, `espeak-ng`

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
