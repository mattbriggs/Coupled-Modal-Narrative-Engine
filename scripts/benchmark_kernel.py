"""Measure AC-37's kernel and sidecar budgets on the current host."""

from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cmne.core import build_packet, replay  # noqa: E402
from cmne.project import Project  # noqa: E402


def timed(call, count: int = 5) -> dict:
    values = []
    for _ in range(count):
        start = time.perf_counter()
        call()
        values.append(time.perf_counter() - start)
    return {"median_seconds": round(statistics.median(values), 4),
            "max_seconds": round(max(values), 4), "samples": count}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cmne-benchmark-") as directory:
        project = Project.create(Path(directory) / "project", "Benchmark")
        try:
            project.submit_batch("main", "story", [
                {"title": f"Event {index:03d}", "actor_ids": ["actor_a"],
                 "observed_by": ["actor_a"], "world_facts": [f"fact {index:03d}"],
                 "strain_bp": index * 50} for index in range(1, 101)])
            story = project.events("main", "story")
            project.submit_batch("main", "discourse", [
                {"title": f"Act {index:02d}", "mode": "summary",
                 "story_refs": [story[index * 10 - 1]["event_id"]],
                 "focalizer": "actor_a", "text": f"Actor A saw event {index * 10}."}
                for index in range(1, 11)])
            discourse = project.events("main", "discourse")
            replay_result = timed(lambda: replay(project.fixture, project.contract, story, discourse))
            packet_result = timed(lambda: build_packet(project.fixture, project.contract, story, discourse))
        finally:
            project.close()
    hello = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "app.hello",
                        "params": {"protocol_version": "1.0"}}) + "\n"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    def sidecar_hello():
        done = subprocess.run([sys.executable, "-m", "cmne_sidecar.server"], input=hello,
                              text=True, capture_output=True, timeout=5, env=env, check=True)
        if "\"result\"" not in done.stdout:
            raise RuntimeError("Sidecar did not answer the handshake")
    sidecar_result = timed(sidecar_hello, 3)
    report = {"host": platform.platform(), "python": platform.python_version(),
              "fixture": {"story_events": 100, "discourse_acts": 10},
              "replay": {**replay_result, "budget_seconds": 1.0,
                         "passed": replay_result["max_seconds"] <= 1.0},
              "packet": {**packet_result, "budget_seconds": 2.0,
                         "passed": packet_result["max_seconds"] <= 2.0},
              "sidecar_ready": {**sidecar_result, "budget_seconds": 3.0,
                                "passed": sidecar_result["max_seconds"] <= 3.0}}
    target = ROOT / "reports" / "benchmark-kernel.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: report[name] for name in ("replay", "packet", "sidecar_ready")}, indent=2))
    return 0 if all(report[name]["passed"] for name in ("replay", "packet", "sidecar_ready")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
