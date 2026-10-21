"""Generate the user-facing error catalog from the Python registry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUTPUT = ROOT / "site" / "api" / "error-catalog.md"


def render() -> str:
    from cmne.errors import ERROR_CATALOG
    lines = ["# Error catalog", "",
             "Each domain error has a stable code, cause, and corrective action. The JSON-RPC error data also carries `field_path` when a validator can locate the offending input.",
             "", "| Code | Message | Cause | Next action |", "|---|---|---|---|"]
    lines.extend(f"| `{code}` | {message} | {cause} | {action} |"
                 for code, (message, cause, action) in sorted(ERROR_CATALOG.items()))
    lines.extend(["", "`E-RPC-INPUT` covers malformed RPC parameters; a programming fault is returned as a JSON-RPC internal error and should be reported with the request method and application version.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the catalog page is stale")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Stale generated error catalog: {OUTPUT.relative_to(ROOT)}")
    else:
        OUTPUT.write_text(content, encoding="utf-8")
        print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
