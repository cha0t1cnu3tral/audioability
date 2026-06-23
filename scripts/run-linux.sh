#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${AUDIOABILITY_VENV:-"$ROOT_DIR/.venv-linux"}"

if [[ ! -x "$VENV_DIR/bin/audioability" ]]; then
  echo "Audioability is not installed in $VENV_DIR yet."
  echo "Run: $ROOT_DIR/scripts/install-linux.sh"
  exit 1
fi

if [[ "${1:-}" != "--dry-run" && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  echo "No Linux desktop session was detected."
  echo "Run from a graphical desktop, or use: $0 --dry-run"
  exit 1
fi

exec "$VENV_DIR/bin/audioability" "$@"
