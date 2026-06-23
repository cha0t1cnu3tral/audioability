# Linux Setup Notes

## Quick Start

With `dist/audioability-linux.run` copied to a Linux desktop:

```bash
chmod +x audioability-linux.run
./audioability-linux.run --dry-run
./audioability-linux.run
```

Use `./audioability-linux.run --no-system-packages` if you already installed the system
accessibility packages yourself.

Most Linux distributions provide AT-SPI and speech services through system packages rather
than PyPI. Install the equivalent packages for your distribution before running the real
screen reader backend.

## Debian or Ubuntu

```bash
sudo apt install at-spi2-core python3-gi python3-pyatspi speech-dispatcher python3-speechd
```

## Fedora

```bash
sudo dnf install at-spi2-core python3-gobject pyatspi speech-dispatcher python3-speechd
```

## Arch Linux and MATE

```bash
sudo pacman -Sy --needed at-spi2-core python-atspi python-gobject speech-dispatcher espeak-ng
```

Run the final `dist/audioability-linux.run` file from inside a graphical MATE session.
`--dry-run` can be used from a terminal-only session to verify that the bundled app starts.

## Development

```bash
uv sync
uv run audioability --dry-run
uv run pytest
```
