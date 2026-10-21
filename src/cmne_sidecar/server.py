"""Line-framed JSON-RPC 2.0 sidecar. Standard output contains RPC only."""

from __future__ import annotations

import json
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from cmne import __version__
from cmne.core import (CmneError, LENSES, SCHEMA_VERSION, require, stable_id,
                       validate_contract, validate_fixture)
from cmne.project import Project, contained

PROTOCOL_VERSION = "1.0"
INVARIANT_FOR_ERROR = {"E-PRECOND-001": "INV-02", "E-ACCESS-001": "INV-03",
                       "E-DISCLOSURE-001": "INV-05"}


class Dispatcher:
    def __init__(self) -> None:
        self.project: Project | None = None
        self.hello_done = False
        self._run_state: dict | None = None
        self._run_state_lock = threading.Lock()
        self._run_thread: threading.Thread | None = None
        self._run_cancel = threading.Event()

    def _start_async_run(self, project: Project, branches: list[tuple[str, str]], variant: int) -> dict:
        require(not self._run_thread or not self._run_thread.is_alive(), "E-RUN-001",
                "A run is already active.")
        self._run_cancel.clear()
        job_id = stable_id("job", [str(project.root), time.time_ns()])
        self._run_state = {"job_id": job_id, "status": "running", "completed": 0,
                           "total": len(branches), "current_condition": None, "runs": [],
                           "stages": [], "findings": []}

        def worker() -> None:
            state = self._run_state
            assert state is not None
            try:
                for condition, branch_id in branches:
                    if self._run_cancel.is_set():
                        with self._run_state_lock:
                            state["status"] = "cancelled"
                            state["current_condition"] = None
                        break
                    with self._run_state_lock:
                        state["current_condition"] = condition
                    result = project.run(branch_id, [condition], variant)
                    with self._run_state_lock:
                        state["runs"].append(result)
                        state["stages"].extend(result["stages"])
                        state["completed"] += 1
                        if result["status"] != "passed":
                            state["findings"].extend(result["findings"])
            except Exception as exc:
                with self._run_state_lock:
                    state["status"] = "failed"
                    state["current_condition"] = None
                    state["findings"].append({"code": getattr(exc, "code", "E-RUN-001"),
                                              "layer": "run", "message": str(exc)})
            finally:
                with self._run_state_lock:
                    state["current_condition"] = None
                    if state["status"] == "running":
                        state["status"] = "failed" if state["findings"] else "passed"

        self._run_thread = threading.Thread(target=worker, daemon=True, name="cmne-run")
        self._run_thread.start()
        return {"job_id": job_id, "status": "running", "total": len(branches)}

    def dispatch(self, method: str, params: dict | None) -> Any:
        p = params or {}
        if self._run_thread and self._run_thread.is_alive() and method in (
                "project.create", "project.sample", "project.open", "project.close",
                "fixture.save", "fixture.import", "contract.save", "contract.import",
                "branch.fork", "command.submit", "draft.seal", "run.start", "export.report",
                "study.plan.save", "study.generate", "study.ablations.realize",
                "study.export", "study.responses.import", "study.report",
                "study.decision_packet"):
            raise CmneError("E-RUN-001", "A run is active; wait or cancel before changing the project.")
        if method == "app.hello":
            requested = str(p.get("protocol_version", PROTOCOL_VERSION))
            require(requested.split(".")[0] == PROTOCOL_VERSION.split(".")[0],
                    "E-PROTO-001", "Incompatible protocol major version.")
            self.hello_done = True
            return {"protocol_version": PROTOCOL_VERSION, "schema_version": SCHEMA_VERSION,
                    "package_version": __version__, "lenses": LENSES}
        require(self.hello_done, "E-PROTO-001", "Call app.hello before other methods.")
        if method == "project.create":
            replacement = Project.create(p["path"], p.get("name", "Untitled scene"), bool(p.get("sample")))
            if self.project:
                self.project.close()
            self.project = replacement
            return self._summary()
        if method == "project.sample":
            path = Path(p.get("path") or Path.home() / "Documents" / "CMNE" / "Mara and Len")
            if self.project and self.project.root == path.expanduser().resolve() and not self.project.read_only:
                return self._summary()
            if (path / "project.cmne.json").exists():
                replacement = Project(path)
            else:
                replacement = Project.create(path, "Mara and Len · The chair and the bowl", sample=True)
            if self.project:
                self.project.close()
            self.project = replacement
            return self._summary()
        if method == "project.open":
            path = Path(p["path"]).expanduser().resolve()
            read_only = bool(p.get("read_only", False))
            if self.project and self.project.root == path:
                require(self.project.read_only == read_only, "E-PROJECT-001",
                        "Close this project before changing its access mode.")
                return self._summary()
            replacement = Project(path, read_only=read_only)
            if self.project:
                self.project.close()
            self.project = replacement
            return self._summary()
        if method == "project.clear_stale_lock":
            return {"cleared": Project.clear_stale_lock(p["path"])}
        if method == "project.close":
            if self.project:
                self.project.close()
            self.project = None
            return {"closed": True}
        if method == "fixture.validate":
            return validate_fixture(p["fixture"])
        if method == "contract.validate":
            return validate_contract(p["contract"])
        project = self._project()
        branch = p.get("branch_id", project.meta.get("active_branch", "main"))
        if method == "project.get":
            return self._summary()
        if method == "fixture.get":
            return project.fixture
        if method == "contract.get":
            return project.contract
        if method == "fixture.save":
            return project.save_fixture(p["fixture"])
        if method == "contract.save":
            return project.save_contract(p["contract"])
        if method == "fixture.import":
            return project.import_document("fixture", p["path"])
        if method == "contract.import":
            return project.import_document("contract", p["path"])
        if method == "branch.list":
            return [{"branch_id": bid, **meta} for bid, meta in project.meta["branches"].items()]
        if method == "branch.fork":
            return project.fork(branch, int(p["sequence"]), p.get("name", "Alternate path"))
        if method == "branch.compare":
            return project.compare(p["left"], p["right"])
        if method == "events.read":
            return project.events(branch, p.get("stream", "story"))
        if method == "command.submit":
            stream = p.get("stream", "story")
            before = project.projection(branch)["hashes"]
            try:
                payloads = p.get("payloads", [p["payload"]] if "payload" in p else None)
                require(isinstance(payloads, list), "E-COMMAND-001", "Command payloads must be an array.")
                assert isinstance(payloads, list)
                events = project.submit_batch(branch, stream, payloads, p.get("expected_sequence"))
            except CmneError as exc:
                return {"accepted": False, "emitted_events": [], "rejected_reason": str(exc),
                        "invariant_results": [{"id": INVARIANT_FOR_ERROR.get(exc.code, exc.code),
                                               "code": exc.code, "passed": False,
                                               "field_path": exc.field_path}],
                        "projection_hash_before": before, "projection_hash_after": before}
            # A post-commit projection failure must not be reported as a rejected command.
            return {"accepted": True, "emitted_events": events, "rejected_reason": None,
                    "invariant_results": [], "projection_hash_before": before,
                    "projection_hash_after": project.projection(branch)["hashes"]}
        if method == "graph.get":
            return project.graph(p.get("lens", "story"), branch, p.get("draft_id"),
                                 p.get("sequence"), p.get("discourse_index"))
        if method == "graph.validate_connection":
            return project.validate_connection(branch, p["lens"], p["source"], p["target"],
                                               p["kind"], p.get("draft"))
        if method == "draft.create":
            return project.draft_create(branch, p.get("lens", "story"))
        if method == "draft.get":
            return project.draft_get(p["draft_id"])
        if method == "draft.list":
            return project.draft_list(branch, p.get("lens", "story"))
        if method == "draft.patch":
            return project.draft_save(p["draft"])
        if method == "draft.compile_preview":
            return project.draft_preview(p.get("draft") or project.draft_get(p["draft_id"]))
        if method == "draft.seal":
            return project.draft_seal(p["draft_id"])
        if method == "draft.delete":
            project._ensure_writable()
            project.draft_path(p["draft_id"]).unlink(missing_ok=True)
            return {"deleted": True}
        if method == "scrub.projection":
            return project.projection(branch, p.get("sequence"), p.get("discourse_index"))
        if method == "overlay.series" or method == "strain.series":
            return project.projection(branch)["projections"]["tension"]
        if method == "trace.query":
            return project.trace(branch, p.get("node_id", ""), p.get("query", "event"),
                                 actor_id=p.get("actor_id"), claim=p.get("claim"),
                                 model_version=p.get("model_version"))
        if method == "packet.build" or method == "packet.get":
            from cmne.core import build_packet
            return build_packet(project.fixture, project.contract,
                                project.events(branch, "story"), project.events(branch, "discourse"))
        if method == "study.plan.save":
            return project.save_analysis_plan(p["plan"])
        if method == "study.plan.get":
            return project.analysis_plan()
        if method == "study.generate":
            return {"runs": project.generate_matched_realizations()}
        if method == "study.metrics":
            return project.study_metrics(branch)
        if method == "study.ablations":
            return project.study_ablations(branch)
        if method == "study.ablations.realize":
            return project.realize_ablations(branch)
        if method == "study.export":
            return project.export_evaluation_set(p.get("seed", 33))
        if method == "study.responses.import":
            source = p.get("responses", p.get("path"))
            require(isinstance(source, (str, Path, dict)), "E-RESPONSE-001",
                    "Provide a response object or JSON path.")
            assert isinstance(source, (str, Path, dict))
            return project.import_responses(p["study_id"], source)
        if method == "study.report":
            return project.analysis_report(p["study_id"])
        if method == "study.decision_packet":
            return project.decision_packet(p["study_id"])
        if method == "run.start":
            requested_conditions = p.get("conditions")
            require(requested_conditions is None or isinstance(requested_conditions, list), "E-RUN-001",
                    "Conditions must be an array.")
            if requested_conditions and len(requested_conditions) > 1:
                require(requested_conditions == ["C0", "C1", "C2", "C3"], "E-RUN-001",
                        "Run all expects C0, C1, C2, C3 in order.")
                by_condition = {meta.get("condition"): bid for bid, meta in project.meta["branches"].items()
                                if meta.get("condition")}
                require(all(condition in by_condition for condition in requested_conditions), "E-RUN-001",
                        "This project does not have all four condition branches.")
                if p.get("async"):
                    return self._start_async_run(project,
                        [(condition, by_condition[condition]) for condition in requested_conditions],
                        p.get("variant_index", 0))
                runs = [project.run(by_condition[condition], [condition], p.get("variant_index", 0))
                        for condition in requested_conditions]
                return {"runs": runs, "status": "failed" if any(run["status"] != "passed" for run in runs)
                        else "passed"}
            if p.get("async"):
                condition = project.meta["branches"][branch].get("condition", "C3")
                return self._start_async_run(project, [(condition, branch)], p.get("variant_index", 0))
            return project.run(branch, p.get("conditions"), p.get("variant_index", 0))
        if method == "run.status":
            if p.get("job_id"):
                with self._run_state_lock:
                    require(self._run_state is not None and p["job_id"] == self._run_state["job_id"],
                            "E-RUN-001", "Unknown run job ID.")
                    assert self._run_state is not None
                    return deepcopy(self._run_state)
            runs = project.list_runs()
            if p.get("branch_id"):
                runs = [run for run in runs if run.get("branch_id") == branch]
            return runs[-1] if runs else {"status": "idle", "stages": [], "findings": []}
        if method == "run.cancel":
            if self._run_thread and self._run_thread.is_alive():
                self._run_cancel.set()
                assert self._run_state is not None
                return {"cancelled": True, "job_id": self._run_state["job_id"],
                        "reason": "Cancellation requested at the next condition boundary."}
            return {"cancelled": False, "reason": "No asynchronous run is active."}
        if method == "export.report":
            project._ensure_writable()
            runs = [run for run in project.list_runs() if run.get("branch_id") == branch]
            require(bool(runs), "E-EXPORT-001", "Run the scene before exporting.")
            report = runs[-1]
            output = contained(project.root, "exports", f"{report['run_id']}.md")
            output.parent.mkdir(exist_ok=True)
            output.write_text(f"# {project.meta['name']}\n\nRun: {report['run_id']}\n\n"
                              f"Status: {report['status']}\n\n## Passage\n\n{report['prose']}\n\n"
                              f"## Findings\n\n" + "\n".join(f"- {f['code']}: {f['message']}" for f in report["findings"]),
                              encoding="utf-8")
            return {"path": str(output)}
        raise CmneError("E-RPC-001", f"Unknown method: {method}")

    def _project(self) -> Project:
        require(self.project is not None, "E-PROJECT-001", "Open a project first.")
        assert self.project is not None
        return self.project

    def _summary(self) -> dict:
        project = self._project()
        return {"path": str(project.root), "name": project.meta["name"],
                "active_branch": project.meta.get("active_branch", "main"),
                "read_only": project.read_only,
                "branches": [{"branch_id": bid, **meta} for bid, meta in project.meta["branches"].items()],
                "fixture": project.fixture, "contract": project.contract}


def handle(dispatcher: Dispatcher, request: dict) -> dict:
    ident = request.get("id") if isinstance(request, dict) else None
    try:
        if not isinstance(request, dict):
            raise CmneError("E-PROTO-001", "Expected a JSON-RPC 2.0 request object.")
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            raise CmneError("E-PROTO-001", "Expected a JSON-RPC 2.0 request.")
        if request.get("params") is not None and not isinstance(request["params"], dict):
            raise TypeError("params must be an object")
        result = dispatcher.dispatch(request["method"], request.get("params"))
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    except CmneError as exc:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32000,
                "message": str(exc), "data": exc.as_dict()}}
    except (KeyError, TypeError, ValueError) as exc:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602,
                "message": f"Invalid params: {exc}", "data": {"cmne_code": "E-RPC-INPUT"}}}


def main() -> None:
    dispatcher = Dispatcher()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle(dispatcher, request)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700,
                        "message": f"Parse error: {exc}"}}
        except Exception as exc:
            print(f"sidecar error: {exc!r}", file=sys.stderr)
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603,
                        "message": "Internal sidecar error."}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
