#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Audioability"
INSTALL_ROOT="${AUDIOABILITY_HOME:-"$HOME/.local/share/audioability"}"
APP_DIR="$INSTALL_ROOT/app"
VENV_DIR="${AUDIOABILITY_VENV:-"$INSTALL_ROOT/venv"}"

usage() {
  cat <<'USAGE'
Audioability Linux runner

Usage:
  ./audioability-linux.run [audioability options]
  ./audioability-linux.run --dry-run
  ./audioability-linux.run --no-system-packages [audioability options]

The runner installs Linux accessibility packages when it recognizes the distro,
unpacks Audioability into ~/.local/share/audioability, then starts the screen reader.
USAGE
}

info() {
  printf '%s\n' "$*"
}

need_linux() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    info "$APP_NAME runs with the real desktop accessibility backend on Linux."
    exit 1
  fi
}

privileged() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  if command -v doas >/dev/null 2>&1; then
    doas "$@"
    return
  fi

  info "Installing system packages needs sudo or doas."
  exit 1
}

install_system_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    privileged apt-get update
    privileged apt-get install -y \
      at-spi2-core \
      espeak-ng \
      python3 \
      python3-gi \
      python3-pyatspi \
      python3-venv \
      speech-dispatcher
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    privileged dnf install -y \
      at-spi2-core \
      espeak-ng \
      python3 \
      python3-gobject \
      python3-virtualenv \
      pyatspi \
      speech-dispatcher
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    privileged pacman -Sy --needed \
      at-spi2-core \
      espeak-ng \
      python \
      python-atspi \
      python-gobject \
      speech-dispatcher
    return
  fi

  if command -v zypper >/dev/null 2>&1; then
    privileged zypper --non-interactive refresh
    privileged zypper --non-interactive install \
      at-spi2-core \
      espeak-ng \
      python3 \
      python3-gobject \
      python3-pyatspi \
      speech-dispatcher
    return
  fi

  info "Unsupported Linux package manager."
  info "Install AT-SPI, PyGObject, pyatspi, Python venv support, Speech Dispatcher, and espeak-ng manually."
}

extract_payload() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  mkdir -p "$INSTALL_ROOT"
  awk '/^__AUDIOABILITY_PAYLOAD_BELOW__$/ { found = 1; next } found { print }' "$0" \
    | base64 -d \
    | tar -xz -C "$tmp_dir"

  rm -rf "$APP_DIR"
  mv "$tmp_dir/audioability" "$APP_DIR"
}

ensure_venv() {
  python3 -m venv --system-site-packages "$VENV_DIR"
}

start_audioability() {
  if [[ "${1:-}" != "--dry-run" && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    info "No Linux desktop session was detected."
    info "Run from MATE or another graphical desktop, or use: $0 --dry-run"
    exit 1
  fi

  PYTHONPATH="$APP_DIR/src" exec "$VENV_DIR/bin/python" -m audioability "$@"
}

main() {
  need_linux

  local install_packages="yes"
  local args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h)
        usage
        exit 0
        ;;
      --no-system-packages)
        install_packages="no"
        shift
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done

  if [[ "$install_packages" == "yes" ]]; then
    install_system_packages
  fi

  extract_payload
  ensure_venv
  start_audioability "${args[@]}"
}

main "$@"
exit 0

__AUDIOABILITY_PAYLOAD_BELOW__
