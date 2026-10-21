"""Expand and validate the executable SRS acceptance inventory.

Default entries have a planned test path. Evidence entries must name real tests.
Use --strict at the final release gate to require every criterion to pass.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "tests" / "acceptance_map.json"


def ids_in(path: Path, prefix: str) -> set[str]:
    pattern = re.compile(rf"^\| ({prefix}-\d{{2,3}}) \|", re.MULTILINE)
    return set(pattern.findall(path.read_text(encoding="utf-8")))


def inventory() -> dict[str, dict]:
    config = json.loads(MAP.read_text(encoding="utf-8"))
    srs = ROOT / config["source_srs"]
    gui = ROOT / config["source_gui"]
    plan = ROOT / config["source_plan"]
    identifiers = (ids_in(srs, "REQ") | ids_in(srs, "GUI") |
                   ids_in(srs, "AC") | ids_in(gui, "GAC") | ids_in(plan, "GAC"))
    expected = ({f"REQ-{n:03d}" for n in range(1, 168)} |
                {f"GUI-{n:03d}" for n in range(1, 41)} |
                {f"AC-{n:02d}" for n in range(1, 43)} |
                {f"GAC-{n:02d}" for n in range(1, 24)})
    if identifiers != expected:
        raise ValueError(f"Specification IDs differ: missing={sorted(expected-identifiers)}, "
                         f"unexpected={sorted(identifiers-expected)}")
    unknown = set(config["evidence"]) - expected
    if unknown:
        raise ValueError(f"Unknown mapped IDs: {sorted(unknown)}")
    result = {}
    for ident in sorted(expected):
        entry = config["evidence"].get(ident, {})
        status = entry.get("status", config["default_status"])
        if status not in ("planned", "partial", "passed"):
            raise ValueError(f"Invalid status for {ident}: {status}")
        tests = entry.get("tests", [])
        if status != "planned" and not tests:
            raise ValueError(f"{ident} needs named evidence")
        for test in tests:
            file_name, sep, method = test.partition("::")
            path = ROOT / file_name
            if not sep or not path.is_file() or not re.search(rf"\bdef {re.escape(method)}\(",
                                                               path.read_text(encoding="utf-8")):
                raise ValueError(f"Missing named test for {ident}: {test}")
        result[ident] = {"status": status, "tests": tests,
                         "planned_test": config["planned_test_pattern"].format(id=ident.lower().replace("-", "_"))}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail unless every criterion has passed")
    parser.add_argument("--json", action="store_true", help="print expanded inventory")
    args = parser.parse_args()
    records = inventory()
    counts = {status: sum(item["status"] == status for item in records.values())
              for status in ("passed", "partial", "planned")}
    if args.json:
        print(json.dumps({"counts": counts, "criteria": records}, indent=2, sort_keys=True))
    else:
        print(f"Mapped {len(records)} IDs: {counts['passed']} passed, "
              f"{counts['partial']} partial, {counts['planned']} planned")
    if args.strict and counts["passed"] != len(records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
