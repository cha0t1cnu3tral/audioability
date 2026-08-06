#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT_DIR/logs"
DEBUG_LOG="$LOG_DIR/audioability-wsl-$SESSION_ID.log"
CONSOLE_LOG="$LOG_DIR/audioability-wsl-$SESSION_ID.console.log"
APP_LOG="$LOG_DIR/gtk-test-app-$SESSION_ID.log"

mkdir -p "$LOG_DIR"
printf '%s\n' \
  "session=$SESSION_ID" \
  "debug_log=$DEBUG_LOG" \
  "console_log=$CONSOLE_LOG" \
  "app_log=$APP_LOG" > "$LOG_DIR/latest-wsl-session.txt"

export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
export GTK_MODULES="${GTK_MODULES:+$GTK_MODULES:}gail:atk-bridge"
export NO_AT_BRIDGE=0
export PYTHONUNBUFFERED=1

"$ROOT_DIR/.venv-linux/bin/audioability" --debug-log "$DEBUG_LOG" \
  >"$CONSOLE_LOG" 2>&1 &
AUDIOABILITY_PID=$!

cleanup() {
  if kill -0 "$AUDIOABILITY_PID" 2>/dev/null; then
    kill "$AUDIOABILITY_PID" 2>/dev/null || true
    wait "$AUDIOABILITY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

sleep 2
if ! kill -0 "$AUDIOABILITY_PID" 2>/dev/null; then
  echo "Audioability stopped during startup; see $CONSOLE_LOG" >&2
  exit 1
fi

python3 "$ROOT_DIR/scripts/accessibility-test-app.py" >"$APP_LOG" 2>&1
