#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/audioability-linux-runner.sh"
OUTPUT="${1:-"$ROOT_DIR/dist/audioability-linux.run"}"

if [[ ! -f "$RUNNER" ]]; then
  echo "Missing runner template: $RUNNER" >&2
  exit 1
fi

if ! grep -q '^__AUDIOABILITY_PAYLOAD_BELOW__$' "$RUNNER"; then
  echo "Runner template is missing the payload marker." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to build the release runner." >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "tar is required to build the release runner." >&2
  exit 1
fi

if ! command -v base64 >/dev/null 2>&1; then
  echo "base64 is required to build the release runner." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

payload="$tmp_dir/audioability.tar.gz"
mkdir -p "$(dirname "$OUTPUT")"

(
  cd "$ROOT_DIR"
  git ls-files -z \
    | tar --null --files-from - --transform 's,^,audioability/,' -czf "$payload"
)

cp "$RUNNER" "$OUTPUT"
base64 "$payload" >> "$OUTPUT"
chmod +x "$OUTPUT"

echo "Built $OUTPUT"
