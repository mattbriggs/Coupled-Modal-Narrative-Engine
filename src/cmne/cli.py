"""Command-line access to the deterministic workbench and study workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (CmneError, build_packet, check_realization, template_realize,
                   validate_contract)
from .project import Project, read_import_json


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cmne", description="Local narrative workbench kernel")
    root.add_argument("--json", action="store_true", help="Print a machine-readable result or error")
    sub = root.add_subparsers(dest="action", required=True)

    def project_command(name: str, help_text: str, branch: bool = True):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("path", help="Project folder")
        if branch:
            command.add_argument("--branch", default="main", help="Branch ID (default: main)")
        return command

    create = project_command("create", "Create a project; use --sample for Mara and Len", False)
    create.add_argument("--name", default="Untitled scene")
    create.add_argument("--sample", action="store_true")
    validate = sub.add_parser("validate-contract", help="Validate a JSON narrative contract")
    validate.add_argument("file")
    project_command("replay", "Replay a branch into its six projections")
    project_command("graph", "Read a lens graph").add_argument("--lens", default="story")
    fork = project_command("fork", "Fork a branch at a committed story sequence")
    fork.add_argument("sequence", type=int)
    fork.add_argument("name")
    revision = project_command("apply-revision", "Inspect a seeded C0–C3 revision condition", False)
    revision.add_argument("condition", choices=("C0", "C1", "C2", "C3"))
    discourse = project_command("plan-discourse", "Atomically seal acts from a JSON discourse plan")
    discourse.add_argument("file")
    project_command("packet", "Build a filtered scene packet")
    realize = project_command("realize", "Realize a scene packet with the offline template")
    realize.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    check = project_command("check", "Check a UTF-8 prose file against a scene packet")
    check.add_argument("file")
    trace = project_command("trace", "Trace an event, belief, reader inference, model, or prose run")
    trace.add_argument("target")
    trace.add_argument("--query", default="event", choices=("event", "actor_belief", "reader_inference",
                                                         "model_interpretations", "prose_access"))
    trace.add_argument("--actor-id")
    trace.add_argument("--model-version", type=int)
    run = project_command("run", "Run and save a deterministic realization")
    run.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    plan = project_command("analysis-plan", "Save or amend a fixed JSON study plan", False)
    plan.add_argument("file")
    project_command("study-generate", "Create three matched candidates for each sample condition", False)
    project_command("study-metrics", "Compute blocking and descriptive structural measures")
    project_command("study-ablations", "List seven analysis-only ablation variants")
    project_command("study-realize-ablations", "Realize and check seven controlled ablation passages")
    export = project_command("export-evaluation", "Export a randomized blinded set and separate key", False)
    export.add_argument("--seed", type=int, default=33)
    responses = project_command("responses-import", "Validate and import structured evaluator responses", False)
    responses.add_argument("study_id")
    responses.add_argument("file")
    report = project_command("report", "Generate a descriptive study report", False)
    report.add_argument("study_id")
    decision = project_command("decision-packet", "Build a reproducible generalization review packet", False)
    decision.add_argument("study_id")
    return root


def execute(args: argparse.Namespace):
    if args.action == "validate-contract":
        return validate_contract(read_import_json(args.file))
    if args.action == "create":
        project = Project.create(args.path, args.name, args.sample)
        try:
            return {"path": str(project.root), "branches": project.branch_ids()}
        finally:
            project.close()
    project = Project(args.path)
    try:
        action = args.action
        if action == "replay":
            return project.projection(args.branch)
        if action == "graph":
            return project.graph(args.lens, args.branch)
        if action == "fork":
            return project.fork(args.branch, args.sequence, args.name)
        if action == "apply-revision":
            branch = next((bid for bid, meta in project.meta["branches"].items()
                           if meta.get("condition") == args.condition), None)
            if branch is None:
                raise CmneError("E-BRANCH-001", "This project has no seeded branch for that condition.")
            return {"condition": args.condition, "branch_id": branch,
                    "projection": project.projection(branch)}
        if action == "plan-discourse":
            plan = read_import_json(args.file)
            return {"emitted_events": project.submit_batch(args.branch, "discourse", plan["acts"])}
        if action in ("packet", "realize", "check"):
            packet = build_packet(project.fixture, project.contract,
                                  project.events(args.branch, "story"),
                                  project.events(args.branch, "discourse"))
            if action == "packet":
                return packet
            if action == "realize":
                prose = template_realize(packet, args.variant)
                return {"packet_hash": packet["packet_hash"], "prose": prose,
                        "findings": check_realization(prose, packet)}
            file_path = Path(args.file).expanduser()
            if file_path.suffix.lower() != ".txt" or file_path.is_symlink() or file_path.stat().st_size > 5*1024*1024:
                raise CmneError("E-INPUT-001", "Use a regular UTF-8 text file under 5 MB.")
            findings = check_realization(file_path.read_text(encoding="utf-8"), packet)
            return {"accepted": not findings, "findings": findings}
        if action == "trace":
            return project.trace(args.branch, args.target, args.query,
                                 actor_id=args.actor_id, model_version=args.model_version)
        if action == "run":
            return project.run(args.branch, variant_index=args.variant)
        if action == "analysis-plan":
            return project.save_analysis_plan(read_import_json(args.file))
        if action == "study-generate":
            return {"runs": project.generate_matched_realizations()}
        if action == "study-metrics":
            return project.study_metrics(args.branch)
        if action == "study-ablations":
            return project.study_ablations(args.branch)
        if action == "study-realize-ablations":
            return project.realize_ablations(args.branch)
        if action == "export-evaluation":
            return project.export_evaluation_set(args.seed)
        if action == "responses-import":
            return project.import_responses(args.study_id, args.file)
        if action == "report":
            return project.analysis_report(args.study_id)
        if action == "decision-packet":
            return project.decision_packet(args.study_id)
        raise CmneError("E-RPC-001", f"Unknown command: {action}")
    finally:
        project.close()


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2))
        return 0
    except (CmneError, OSError, UnicodeError, KeyError, ValueError) as exc:
        error = exc.as_dict() if isinstance(exc, CmneError) else CmneError(
            "E-INPUT-001", str(exc)).as_dict()
        if args.json:
            print(json.dumps({"error": error}, ensure_ascii=False))
        else:
            print(f"{error['cmne_code']}: {error['cause']}\nNext: {error['next_action']}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
