"""Run reproducible local release checks and retain their actual outcomes.

This is a preflight record, not a substitute for target-OS CI, a packaged GUI
journey, accessibility checks, performance measurements, or human review.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str], cwd: Path = ROOT, env: dict | None = None) -> dict:
    try:
        done = subprocess.run(command, cwd=cwd, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=600, check=False)
        return {"name": name, "command": command, "status": "passed" if done.returncode == 0 else "failed",
                "exit_code": done.returncode, "output_tail": done.stdout[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"name": name, "command": command, "status": "failed", "error": str(error)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record local CMNE release preflight checks")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "release-preflight.json")
    args = parser.parse_args(argv)
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    checks = [
        run("python-tests", [python, "-m", "unittest", "discover", "-s", "tests", "-q"], env=env),
        run("python-types", ["mypy", "src", "--ignore-missing-imports", "--no-incremental"], env=env),
        run("python-lint", ["ruff", "check", "src", "scripts", "tests", "--select", "F,B,UP,SIM"], env=env),
        run("acceptance-inventory", [python, "scripts/check_acceptance.py"], env=env),
        run("schema-artifacts", [python, "scripts/export_schemas.py", "--check"], env=env),
        run("error-catalog", [python, "scripts/check_error_catalog.py"], env=env),
        run("error-catalog-page", [python, "scripts/export_error_catalog.py", "--check"], env=env),
        run("frontend", ["npm", "run", "build"], ROOT / "app", env),
        run("documentation", ["mkdocs", "build", "--strict"], env=env),
        run("kernel-benchmark", [python, "scripts/benchmark_kernel.py"], env=env),
    ]
    if platform.system() == "Darwin":
        compiler = subprocess.run(["rustup", "which", "rustc"], text=True, capture_output=True,
                                  check=False)
        rust_env = {**env, "RUSTC": compiler.stdout.strip()} if compiler.returncode == 0 else env
        rust_env["PATH"] = str(Path.home() / ".cargo" / "bin") + os.pathsep + rust_env["PATH"]
        checks.append(run("rust-shell", [str(Path.home() / ".cargo" / "bin" / "cargo"),
                                         "+stable", "clippy", "--locked", "--all-targets", "--", "-D", "warnings"],
                          ROOT / "app" / "src-tauri", rust_env))
    report = {"checked_at": datetime.now(UTC).isoformat(),
              "platform": platform.platform(), "checks": checks,
              "local_preflight_passed": all(item["status"] == "passed" for item in checks),
              "outstanding_evidence": ["clean-checkout CI on supported operating systems",
                                       "packaged GUI end-to-end journey",
                                       "automated accessibility and keyboard checks",
                                       "reference-machine graph and latency measurements",
                                       "full AC/GAC trace and mutation threshold"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(item['status'] == 'passed' for item in checks)}/{len(checks)} local checks passed; "
          f"report: {args.output}")
    return 0 if report["local_preflight_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
