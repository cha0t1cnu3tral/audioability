# Linux Setup Notes

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

## Development

```bash
uv sync
uv run audioability --dry-run
uv run pytest
```
