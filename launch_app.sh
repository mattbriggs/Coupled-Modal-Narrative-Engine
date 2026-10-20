#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_BUNDLE="$ROOT_DIR/app/src-tauri/target/release/bundle/macos/CMNE Workbench.app"

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
  echo "Usage: ./launch_app.sh"
  echo "Launch the built macOS CMNE Workbench app."
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "Usage: ./launch_app.sh" >&2
  exit 2
fi
if [[ "$(uname -s)" != Darwin ]]; then
  echo "This launcher opens a macOS .app and must run on macOS." >&2
  exit 1
fi
if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "App bundle not found. Run ./build_app.sh first." >&2
  exit 1
fi

open "$APP_BUNDLE"
