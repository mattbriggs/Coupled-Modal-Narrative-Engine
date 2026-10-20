#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
APP_BUNDLE="$ROOT_DIR/app/src-tauri/target/release/bundle/macos/CMNE Workbench.app"
SKIP_INSTALL=false

usage() {
  cat <<'EOF'
Usage: ./build_app.sh [--skip-install]

Build the macOS CMNE Workbench app, including its bundled Python sidecar.
By default, create .venv if needed and install Python and Node dependencies.
Use --skip-install to rebuild with dependencies already installed.
EOF
}

case "${1:-}" in
  "") ;;
  --skip-install) SKIP_INSTALL=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

if [[ "$(uname -s)" != Darwin ]]; then
  echo "This build script packages a macOS .app and must run on macOS." >&2
  exit 1
fi

# Tauri's beforeBuildCommand calls python3. Put the project environment first.
# Prefer rustup's toolchain when an older system Cargo is also installed.
if [[ -x "${HOME:-}/.cargo/bin/cargo" ]]; then
  export PATH="$VENV_DIR/bin:${HOME}/.cargo/bin:$PATH"
else
  export PATH="$VENV_DIR/bin:$PATH"
fi

for tool in python3 npm cargo rustc; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing prerequisite: $tool. See README.md for installation steps." >&2
    exit 1
  fi
done

if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
  if [[ "$SKIP_INSTALL" == true ]]; then
    echo "Missing .venv. Run ./build_app.sh without --skip-install first." >&2
    exit 1
  fi
  echo "Creating Python virtual environment in .venv..."
  python3 -m venv "$VENV_DIR"
fi

if [[ "$SKIP_INSTALL" == true ]]; then
  if ! "$VENV_DIR/bin/python3" -c 'import cmne, PyInstaller' >/dev/null 2>&1; then
    echo "Missing Python build dependencies. Run ./build_app.sh without --skip-install." >&2
    exit 1
  fi
  if [[ ! -x "$ROOT_DIR/app/node_modules/.bin/tauri" ]]; then
    echo "Missing Node dependencies. Run ./build_app.sh without --skip-install." >&2
    exit 1
  fi
else
  echo "Installing Python package and PyInstaller into .venv..."
  (cd "$ROOT_DIR" && "$VENV_DIR/bin/python3" -m pip install -e '.[bundle]')
  echo "Installing Node dependencies from app/package-lock.json..."
  (cd "$ROOT_DIR/app" && npm ci)
fi

echo "Building the frontend, bundled sidecar, Rust shell, and macOS app..."
(cd "$ROOT_DIR/app" && npm run tauri -- build --bundles app)

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "Tauri finished without producing the expected app: $APP_BUNDLE" >&2
  exit 1
fi

printf '\nBuilt: %s\nLaunch with: %s/launch_app.sh\n' "$APP_BUNDLE" "$ROOT_DIR"
