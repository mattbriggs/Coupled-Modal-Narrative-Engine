"""Measure Python executable-line coverage with the standard-library tracer.

Run: PYTHONPATH=src python3 scripts/coverage_report.py
This is line coverage, not branch coverage or a mutation score. It uses the
same executable-line definition as ``python -m trace --count``.
"""

from __future__ import annotations

import json
import sys
import trace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_tests() -> bool:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    return unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(suite).wasSuccessful()


def main() -> int:
    tracer = trace.Trace(count=True, trace=False)
    passed = tracer.runfunc(run_tests)
    counts = tracer.results().counts
    recorded = {}
    for (filename, line), count in counts.items():
        if count:
            recorded.setdefault(str(Path(filename).resolve()), set()).add(line)
    files = sorted((ROOT / "src" / "cmne").glob("*.py")) + [ROOT / "src" / "cmne_sidecar" / "server.py"]
    rows = []
    for path in files:
        executable = set(trace._find_executable_linenos(str(path)))
        covered = executable & recorded.get(str(path.resolve()), set())
        rows.append({"file": str(path.relative_to(ROOT)), "covered": len(covered),
                     "executable": len(executable),
                     "line_coverage_pct": round(100*len(covered)/len(executable), 1) if executable else 100.0})
    total = sum(row["executable"] for row in rows)
    covered = sum(row["covered"] for row in rows)
    report = {"method": "stdlib trace executable-line coverage", "tests_passed": passed,
              "covered": covered, "executable": total,
              "line_coverage_pct": round(100*covered/total, 1), "files": rows}
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
