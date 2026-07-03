#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${AUDIOABILITY_VENV:-"$ROOT_DIR/.venv-linux"}"

usage() {
  cat <<'USAGE'
Audioability source installer

Usage:
  scripts/install-linux.sh
  scripts/install-linux.sh --no-system-packages

This installs the Linux packages uv cannot get from PyPI, creates a venv that can
see distro AT-SPI bindings, then runs uv sync into that venv.
USAGE
}

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Audioability's real screen-reader backend runs on Linux."
  echo "Use this installer from a Linux desktop session."
  exit 1
fi

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

  echo "Installing system packages needs sudo or doas."
  exit 1
}

install_system_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    privileged apt-get update
    local apt_packages=(
      at-spi2-core \
      espeak-ng \
      gcc \
      libgirepository-2.0-dev \
      pkg-config \
      python3 \
      python3-dev \
      python3-gi \
      python3-pyatspi \
      python3-pip \
      python3-venv \
      speech-dispatcher
    )
    if ! privileged apt-get install -y "${apt_packages[@]}"; then
      apt_packages=("${apt_packages[@]/libgirepository-2.0-dev/libgirepository1.0-dev}")
      privileged apt-get install -y "${apt_packages[@]}"
    fi
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    privileged dnf install -y \
      at-spi2-core \
      cairo-gobject-devel \
      espeak-ng \
      gcc \
      gobject-introspection-devel \
      pkgconf-pkg-config \
      python3 \
      python3-devel \
      python3-gobject \
      python3-pip \
      python3-virtualenv \
      pyatspi \
      speech-dispatcher
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    privileged pacman -Sy --needed \
      at-spi2-core \
      cairo \
      espeak-ng \
      gcc \
      gobject-introspection \
      pkgconf \
      python \
      python-atspi \
      python-gobject \
      python-pip \
      speech-dispatcher
    return
  fi

  if command -v zypper >/dev/null 2>&1; then
    privileged zypper --non-interactive refresh
    privileged zypper --non-interactive install \
      at-spi2-core \
      cairo-devel \
      espeak-ng \
      gcc \
      gobject-introspection-devel \
      pkg-config \
      python3 \
      python3-devel \
      python3-gobject \
      python3-pyatspi \
      python3-pip \
      speech-dispatcher
    return
  fi

  echo "Could not find apt-get, dnf, pacman, or zypper."
  echo "Install AT-SPI, PyGObject build deps, pyatspi, Python venv support, and Speech Dispatcher manually."
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  if python3 -m uv --version >/dev/null 2>&1; then
    return
  fi

  python3 -m pip install --user --upgrade uv
}

run_uv() {
  if command -v uv >/dev/null 2>&1; then
    uv "$@"
    return
  fi

  python3 -m uv "$@"
}

ensure_venv() {
  python3 -m venv --system-site-packages "$VENV_DIR"
}

sync_project() {
  (
    cd "$ROOT_DIR"
    UV_PROJECT_ENVIRONMENT="$VENV_DIR" run_uv sync
  )
}

main() {
  local install_packages="yes"
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
        echo "Unknown option: $1"
        usage
        exit 2
        ;;
    esac
  done

  if [[ "$install_packages" == "yes" ]]; then
    install_system_packages
  fi

  ensure_uv
  ensure_venv
  sync_project
}

main "$@"

echo
echo "Audioability is installed in: $VENV_DIR"
echo "Run it with:"
echo "  $ROOT_DIR/scripts/run-linux.sh"
echo
echo "For a non-desktop test:"
echo "  $ROOT_DIR/scripts/run-linux.sh --dry-run"
