"""Fail when a domain error code used in source lacks cause and next action."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cmne.errors import ERROR_CATALOG, ERROR_MESSAGES  # noqa: E402


def main() -> None:
    used = set()
    for folder in (ROOT / "src" / "cmne", ROOT / "src" / "cmne_sidecar"):
        for path in folder.glob("*.py"):
            if path.name == "errors.py":
                continue
            used.update(re.findall(r'"(E-[A-Z0-9-]+)"', path.read_text(encoding="utf-8")))
    missing = used - ERROR_CATALOG.keys()
    invalid = {code for code, fields in ERROR_CATALOG.items()
               if len(fields) != 3 or not all(isinstance(value, str) and value.strip() for value in fields)}
    extra = ERROR_CATALOG.keys() - used
    unmapped_messages = ERROR_MESSAGES.keys() ^ ERROR_CATALOG.keys()
    if missing or invalid or extra or unmapped_messages:
        raise SystemExit(f"Error catalog problems: missing={sorted(missing)}, "
                         f"invalid={sorted(invalid)}, extra={sorted(extra)}, "
                         f"unmapped_messages={sorted(unmapped_messages)}")
    print(f"Catalog covers {len(used)} source codes ({len(ERROR_CATALOG)} entries).")


if __name__ == "__main__":
    main()
