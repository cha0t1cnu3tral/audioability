#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Audioability"
INSTALL_ROOT="${AUDIOABILITY_HOME:-"$HOME/.local/share/audioability"}"
APP_DIR="$INSTALL_ROOT/app"
PREVIOUS_APP_DIR="$INSTALL_ROOT/app.previous"
VENV_DIR="${AUDIOABILITY_VENV:-"$INSTALL_ROOT/venv"}"
LAUNCHER_DIR="$INSTALL_ROOT/bin"
LAUNCHER="$LAUNCHER_DIR/audioability"
USER_BIN_DIR="${AUDIOABILITY_BIN_DIR:-"$HOME/.local/bin"}"
USER_LAUNCHER="$USER_BIN_DIR/audioability"
PAYLOAD_SHA256="__AUDIOABILITY_PAYLOAD_SHA256__"
PYTHON_BIN=""
OS_DESCRIPTION="Linux"

usage() {
  cat <<'USAGE'
Audioability Linux installer and runner

Usage:
  ./audioability-linux.run [audioability options]
  ./audioability-linux.run --dry-run
  ./audioability-linux.run --install-only
  ./audioability-linux.run --no-system-packages [audioability options]

Each run updates the required distro packages, installs or updates Audioability
under ~/.local/share/audioability, creates ~/.local/bin/audioability, and starts
the screen reader. The previous application payload is kept as app.previous.

Installer options:
  --install-only        Install or update without starting Audioability.
  --no-system-packages  Do not invoke apt, dnf, yum, pacman, zypper, or apk.
  -h, --help            Show this help.

All other options are passed to Audioability.

Environment overrides:
  AUDIOABILITY_HOME     Application data directory.
  AUDIOABILITY_VENV     Python virtual environment directory.
  AUDIOABILITY_BIN_DIR  Directory that receives the audioability launcher.
USAGE
}

info() {
  printf '%s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

need_linux() {
  [[ "$(uname -s)" == "Linux" ]] \
    || die "$APP_NAME's desktop accessibility backend requires Linux."
}

check_invocation_user() {
  if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    die "Run this file as your desktop user, without sudo. It requests sudo only for packages."
  fi
}

load_os_description() {
  if [[ -r /etc/os-release ]]; then
    # The file is defined as shell-compatible key/value data by os-release(5).
    # shellcheck disable=SC1091
    source /etc/os-release
    OS_DESCRIPTION="${PRETTY_NAME:-${NAME:-Linux}}"
  fi
}

validate_install_paths() {
  [[ "$INSTALL_ROOT" == /* ]] || die "AUDIOABILITY_HOME must be an absolute path."
  [[ "$VENV_DIR" == /* ]] || die "AUDIOABILITY_VENV must be an absolute path."
  [[ "$USER_BIN_DIR" == /* ]] || die "AUDIOABILITY_BIN_DIR must be an absolute path."

  case "$INSTALL_ROOT" in
    /|"$HOME"|"$HOME"/)
      die "Refusing unsafe installation root: $INSTALL_ROOT"
      ;;
  esac

  [[ "$APP_DIR" == "$INSTALL_ROOT"/* ]] || die "Invalid application path."
  [[ "$PREVIOUS_APP_DIR" == "$INSTALL_ROOT"/* ]] || die "Invalid backup path."
  [[ "$VENV_DIR" != "/" && "$VENV_DIR" != "$HOME" ]] \
    || die "Refusing unsafe virtual environment path: $VENV_DIR"
}

privileged() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  elif command -v doas >/dev/null 2>&1; then
    doas "$@"
  else
    die "Updating system dependencies requires root, sudo, or doas."
  fi
}

install_apt_packages() {
  local packages=(
    at-spi2-core
    coreutils
    espeak-ng
    python3
    python3-gi
    python3-pyatspi
    python3-speechd
    python3-venv
    speech-dispatcher
    tar
  )
  privileged apt-get update
  privileged env DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
}

install_dnf_packages() {
  local manager="$1"
  local packages=(
    at-spi2-core
    coreutils
    espeak-ng
    pyatspi
    python3
    python3-gobject
    python3-speechd
    python3-virtualenv
    speech-dispatcher
    tar
  )
  privileged "$manager" install -y --refresh "${packages[@]}"
}

install_yum_packages() {
  local packages=(
    at-spi2-core
    coreutils
    espeak-ng
    pyatspi
    python3
    python3-gobject
    python3-speechd
    python3-virtualenv
    speech-dispatcher
    tar
  )
  privileged yum makecache -y
  privileged yum install -y "${packages[@]}"
}

install_pacman_packages() {
  local packages=(
    at-spi2-core
    coreutils
    espeak-ng
    python
    python-atspi
    python-gobject
    speech-dispatcher
    tar
  )
  info "Arch-based systems require a synchronized package upgrade."
  privileged pacman -Syu --needed --noconfirm "${packages[@]}"
}

install_zypper_packages() {
  local packages=(
    at-spi2-core
    coreutils
    espeak-ng
    python3
    python3-gobject
    python3-pyatspi
    python3-speechd
    speech-dispatcher
    tar
  )
  privileged zypper --non-interactive refresh
  privileged zypper --non-interactive install --auto-agree-with-licenses "${packages[@]}"
}

install_apk_packages() {
  local packages=(
    at-spi2-core
    bash
    coreutils
    espeak-ng
    py3-gobject3
    py3-pyatspi
    py3-virtualenv
    python3
    speech-dispatcher
    tar
  )
  privileged apk update
  privileged apk add --upgrade "${packages[@]}"
}

install_system_packages() {
  info "Updating $APP_NAME system dependencies for $OS_DESCRIPTION..."
  if command -v apt-get >/dev/null 2>&1; then
    install_apt_packages
  elif command -v dnf5 >/dev/null 2>&1; then
    install_dnf_packages dnf5
  elif command -v dnf >/dev/null 2>&1; then
    install_dnf_packages dnf
  elif command -v yum >/dev/null 2>&1; then
    install_yum_packages
  elif command -v pacman >/dev/null 2>&1; then
    install_pacman_packages
  elif command -v zypper >/dev/null 2>&1; then
    install_zypper_packages
  elif command -v apk >/dev/null 2>&1; then
    install_apk_packages
  else
    info "No supported package manager was found; checking existing dependencies."
  fi
}

find_python() {
  local candidate
  for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
      PYTHON_BIN="$(command -v "$candidate")"
      return
    fi
  done
  die "$APP_NAME requires Python 3.11 or newer."
}

require_payload_tools() {
  local tool
  for tool in awk base64 mktemp tar; do
    command -v "$tool" >/dev/null 2>&1 || die "Required tool is missing: $tool"
  done
  if ! command -v sha256sum >/dev/null 2>&1 \
    && ! command -v shasum >/dev/null 2>&1; then
    die "A SHA-256 utility is required (sha256sum or shasum)."
  fi
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{ print $1 }'
  else
    shasum -a 256 "$1" | awk '{ print $1 }'
  fi
}

extract_payload() (
  local temp_dir payload_file actual_sha staged_app
  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/audioability-installer.XXXXXX")"
  payload_file="$temp_dir/audioability.tar.gz"
  staged_app="$INSTALL_ROOT/.app.new.$$"

  cleanup_payload() {
    rm -rf -- "$temp_dir"
    if [[ "$staged_app" == "$INSTALL_ROOT"/.app.new.* ]]; then
      rm -rf -- "$staged_app"
    fi
  }
  trap cleanup_payload EXIT

  awk '/^__AUDIOABILITY_PAYLOAD_BELOW__$/ { found = 1; next } found { print }' "$0" \
    | base64 -d > "$payload_file"
  actual_sha="$(sha256_file "$payload_file")"
  [[ "$PAYLOAD_SHA256" =~ ^[[:xdigit:]]{64}$ ]] \
    || die "This runner was not built with an embedded payload checksum."
  [[ "$actual_sha" == "$PAYLOAD_SHA256" ]] \
    || die "The embedded Audioability payload is corrupt or incomplete."

  mkdir -p "$INSTALL_ROOT"
  rm -rf -- "$staged_app"
  mkdir -p "$staged_app"
  tar -xzf "$payload_file" -C "$staged_app"
  [[ -f "$staged_app/audioability/pyproject.toml" ]] \
    || die "The embedded payload does not contain Audioability."

  rm -rf -- "$PREVIOUS_APP_DIR"
  if [[ -d "$APP_DIR" ]]; then
    mv "$APP_DIR" "$PREVIOUS_APP_DIR"
  fi
  if ! mv "$staged_app/audioability" "$APP_DIR"; then
    [[ -d "$PREVIOUS_APP_DIR" ]] && mv "$PREVIOUS_APP_DIR" "$APP_DIR"
    die "Could not activate the new Audioability payload."
  fi
  info "Installed application files in $APP_DIR"
)

ensure_venv() {
  info "Creating or updating the Audioability Python environment..."
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
  "$VENV_DIR/bin/python" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Audioability requires Python 3.11 or newer")

try:
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi  # noqa: F401
    import pyatspi  # noqa: F401
    import speechd  # noqa: F401
except Exception as exc:
    raise SystemExit(f"A required Linux accessibility dependency is unavailable: {exc}") from exc
PY
}

verify_application_import() {
  PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$VENV_DIR/bin/python" -c 'import audioability'
}

install_launcher() {
  local launcher_temp existing_backup
  mkdir -p "$LAUNCHER_DIR" "$USER_BIN_DIR"
  launcher_temp="$LAUNCHER.tmp.$$"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'export PYTHONPATH=%q${PYTHONPATH:+:$PYTHONPATH}\n' "$APP_DIR/src"
    printf 'exec %q -m audioability "$@"\n' "$VENV_DIR/bin/python"
  } > "$launcher_temp"
  chmod 755 "$launcher_temp"
  mv -f "$launcher_temp" "$LAUNCHER"

  if [[ -e "$USER_LAUNCHER" && ! -L "$USER_LAUNCHER" ]]; then
    existing_backup="$USER_LAUNCHER.before-audioability"
    mv -f "$USER_LAUNCHER" "$existing_backup"
    info "Saved the previous launcher as $existing_backup"
  fi
  ln -sfn "$LAUNCHER" "$USER_LAUNCHER"
  info "Installed launcher: $USER_LAUNCHER"
  if [[ ":$PATH:" != *":$USER_BIN_DIR:"* ]]; then
    info "Add $USER_BIN_DIR to PATH to run 'audioability' from a terminal."
  fi
}

start_audioability() {
  if [[ "${1:-}" != "--dry-run" && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    die "No Linux graphical session was detected. Run with --dry-run for a smoke test."
  fi
  info "Starting $APP_NAME..."
  exec "$LAUNCHER" "$@"
}

main() {
  local install_packages="yes"
  local install_only="no"
  local args=()

  need_linux
  check_invocation_user
  load_os_description
  validate_install_paths

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h)
        usage
        exit 0
        ;;
      --install-only)
        install_only="yes"
        shift
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
  else
    info "Skipping system package installation by request."
  fi

  find_python
  require_payload_tools
  ensure_venv
  extract_payload
  verify_application_import
  install_launcher

  info "$APP_NAME installation is up to date."
  if [[ "$install_only" == "yes" ]]; then
    exit 0
  fi
  start_audioability "${args[@]}"
}

main "$@"
exit 0

__AUDIOABILITY_PAYLOAD_BELOW__
