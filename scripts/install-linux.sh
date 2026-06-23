#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${AUDIOABILITY_VENV:-"$ROOT_DIR/.venv-linux"}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Audioability's real screen-reader backend runs on Linux."
  echo "Use this installer from a Linux desktop session."
  exit 1
fi

install_system_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y \
      at-spi2-core \
      python3-gi \
      python3-pyatspi \
      python3-venv \
      speech-dispatcher
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y \
      at-spi2-core \
      espeak-ng \
      python3-gobject \
      python3-pip \
      pyatspi \
      python3-virtualenv \
      speech-dispatcher
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed \
      at-spi2-core \
      espeak-ng \
      python \
      python-atspi \
      python-gobject \
      python-pip \
      speech-dispatcher
    return
  fi

  echo "Could not find apt-get, dnf, or pacman."
  echo "Install AT-SPI, PyGObject, pyatspi, Python venv support, and Speech Dispatcher manually."
}

if [[ "${1:-}" != "--no-system-packages" ]]; then
  install_system_packages
fi

python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"

echo
echo "Audioability is installed in: $VENV_DIR"
echo "Run it with:"
echo "  $ROOT_DIR/scripts/run-linux.sh"
echo
echo "For a non-desktop test:"
echo "  $ROOT_DIR/scripts/run-linux.sh --dry-run"
