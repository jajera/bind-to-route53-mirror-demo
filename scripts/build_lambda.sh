#!/bin/bash
# Build a deterministic Lambda deployment package under dist/lambda/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/dist/lambda"
STAMP="$ROOT/dist/.lambda-build.stamp"
SRC="$ROOT/src/zone_sync"

needs_build() {
  [[ "${FORCE_LAMBDA_BUILD:-}" == "1" ]] && return 0
  [[ ! -d "$BUILD/zone_sync" ]] && return 0
  [[ ! -f "$STAMP" ]] && return 0
  find "$SRC" -type f -newer "$STAMP" -print -quit | grep -q .
}

if ! needs_build; then
  echo "Lambda package up to date at $BUILD"
  exit 0
fi

rm -rf "$BUILD"
mkdir -p "$BUILD"
cp -r "$SRC" "$BUILD/"
pip install 'dnspython==2.8.0' -t "$BUILD" --no-cache-dir --quiet
# Normalize mtimes so archive_file hash is stable across rebuilds of unchanged code.
find "$BUILD" -exec touch -h -d '@0' {} +
touch "$STAMP"
echo "Lambda package staged at $BUILD"
