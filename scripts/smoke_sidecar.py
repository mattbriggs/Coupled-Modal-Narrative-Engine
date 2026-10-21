"""Exercise a packaged Python sidecar over its real line-framed protocol."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import tempfile
from pathlib import Path


PLAN = {"hypotheses": ["C3 yields more cited reinterpretation than C0"],
        "primary_measures": ["retrospective_citation", "distinct_details", "preparedness",
                             "unresolved_meaningful"], "secondary_measures": ["motif_recurrence"],
        "target_sample_size": 8, "sample_size_rationale": "Synthetic packaged smoke protocol.",
        "agreement_metric": "percent_agreement", "exclusion_rules": [],
        "session_limit_minutes": 20}


def exchange(binary: Path, requests: list[dict]) -> list[dict]:
    completed = subprocess.run([str(binary)], input="".join(json.dumps(request) + "\n"
                                                    for request in requests),
                               text=True, capture_output=True, timeout=45, check=True)
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(responses) == len(requests), (responses, completed.stderr)
    assert [response["id"] for response in responses] == [request["id"] for request in requests], responses
    assert all("error" not in response for response in responses), responses
    return responses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cmne-packaged-smoke-") as folder:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {"protocol_version": "1.0"}},
            {"jsonrpc": "2.0", "id": 2, "method": "project.create",
             "params": {"path": str(Path(folder) / "project"), "name": "Packaged smoke"}},
            {"jsonrpc": "2.0", "id": 3, "method": "draft.create",
             "params": {"branch_id": "main", "lens": "story"}},
            {"jsonrpc": "2.0", "id": 4, "method": "draft.list",
             "params": {"branch_id": "main", "lens": "story"}},
            {"jsonrpc": "2.0", "id": 5, "method": "command.submit",
             "params": {"branch_id": "main", "stream": "story", "expected_sequence": 0,
                        "payloads": [{"title": "First"}, {"title": "Second"}]}},
            {"jsonrpc": "2.0", "id": 6, "method": "events.read",
             "params": {"branch_id": "main", "stream": "story"}},
            {"jsonrpc": "2.0", "id": 7, "method": "project.close", "params": {}},
        ]
        responses = exchange(args.binary, requests)
        assert responses[0]["result"]["schema_version"] == 2, responses[0]
        assert responses[3]["result"][0]["id"] == responses[2]["result"]["id"], responses[3]
        assert responses[4]["result"]["accepted"] is True, responses[4]
        assert len(responses[4]["result"]["emitted_events"]) == 2, responses[4]
        assert len(responses[5]["result"]) == 2, responses[5]
        assert responses[6]["result"]["closed"] is True, responses[6]
        study_path = str(Path(folder) / "study-project")
        study = exchange(args.binary, [
            {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "project.create",
             "params": {"path": study_path, "name": "Study smoke", "sample": True}},
            {"jsonrpc": "2.0", "id": 3, "method": "study.plan.save", "params": {"plan": PLAN}},
            {"jsonrpc": "2.0", "id": 4, "method": "study.generate", "params": {}},
            {"jsonrpc": "2.0", "id": 5, "method": "study.export", "params": {"seed": 11}},
            {"jsonrpc": "2.0", "id": 6, "method": "project.close", "params": {}},
        ])
        assert len(study[3]["result"]["runs"]) == 12, study[3]
        study_id = study[4]["result"]["study_id"]
        c3 = next(item["branch_id"] for item in study[1]["result"]["branches"]
                  if item.get("condition") == "C3")
        review = exchange(args.binary, [
            {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "project.open", "params": {"path": study_path}},
            {"jsonrpc": "2.0", "id": 3, "method": "study.ablations.realize",
             "params": {"branch_id": c3}},
            {"jsonrpc": "2.0", "id": 4, "method": "study.decision_packet",
             "params": {"study_id": study_id}},
            {"jsonrpc": "2.0", "id": 5, "method": "project.close", "params": {}},
        ])
        assert len(review[2]["result"]) == 7, review[2]
        assert review[3]["result"]["decision"] == "pending_human_review", review[3]
    checks = ["schema-2 handshake", "project create and close", "disk-backed draft recovery",
              "atomic two-event batch", "verified read", "12-passage study generation and blind export",
              "seven realized ablations", "generalization decision packet"]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"platform": platform.platform(), "binary": str(args.binary),
                                          "status": "passed", "checks": checks}, indent=2) + "\n",
                               encoding="utf-8")
    print("Packaged sidecar smoke passed: " + ", ".join(checks))


if __name__ == "__main__":
    main()
