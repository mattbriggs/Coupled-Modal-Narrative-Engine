"""Prepare the Tauri sidecar binary for development or a packaged build.

Tauri expects <externalBin>-<target triple>. Development uses a tiny wrapper;
release builds use PyInstaller so Python is included in the app bundle.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARIES = ROOT / "app" / "src-tauri" / "binaries"


def host_triple() -> str:
    result = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True)
    return next(line.split(": ", 1)[1] for line in result.stdout.splitlines() if line.startswith("host: "))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--bundle", action="store_true")
    args = parser.parse_args()
    if args.dev == args.bundle:
        parser.error("Choose --dev or --bundle")
    BINARIES.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if sys.platform == "win32" else ""
    destination = BINARIES / f"cmne-sidecar-{host_triple()}{suffix}"
    if args.dev:
        if sys.platform == "win32":
            print("On Windows, set CMNE_SIDECAR_BIN to a bundled sidecar for development.", file=sys.stderr)
            sys.exit(1)
        script = f"#!/bin/sh\nPYTHONPATH='{ROOT / 'src'}' exec '{sys.executable}' -m cmne_sidecar.server\n"
        destination.write_text(script, encoding="utf-8")
        destination.chmod(0o755)
        print(f"Prepared development sidecar: {destination}")
        return
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is needed for a packaged app. Install: python3 -m pip install '.[bundle]'", file=sys.stderr)
        sys.exit(1)
    staging = ROOT / "app" / "src-tauri" / "sidecar-dist"
    environment = os.environ.copy()
    environment.setdefault("PYINSTALLER_CONFIG_DIR", str(staging / "cache"))
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--onefile", "--noconfirm",
                    "--name", "cmne-sidecar", "--paths", str(ROOT / "src"),
                    "--distpath", str(staging), "--workpath", str(staging / "build"),
                    "--specpath", str(staging), str(ROOT / "src" / "cmne_sidecar" / "server.py")],
                   check=True, env=environment)
    shutil.copy2(staging / f"cmne-sidecar{suffix}", destination)
    destination.chmod(0o755)
    print(f"Prepared bundled sidecar: {destination}")


if __name__ == "__main__":
    main()
