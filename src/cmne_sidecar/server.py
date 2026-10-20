"""Line-framed JSON-RPC 2.0 sidecar. Standard output contains RPC only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from cmne import __version__
from cmne.core import CmneError, LENSES, SCHEMA_VERSION, require, validate_contract, validate_fixture
from cmne.project import Project, contained, write_json

PROTOCOL_VERSION = "1.0"


class Dispatcher:
    def __init__(self) -> None:
        self.project: Project | None = None
        self.hello_done = False

    def dispatch(self, method: str, params: dict | None) -> Any:
        p = params or {}
        if method == "app.hello":
            requested = str(p.get("protocol_version", PROTOCOL_VERSION))
            require(requested.split(".")[0] == PROTOCOL_VERSION.split(".")[0],
                    "E-PROTO-001", "Incompatible protocol major version.")
            self.hello_done = True
            return {"protocol_version": PROTOCOL_VERSION, "schema_version": SCHEMA_VERSION,
                    "package_version": __version__, "lenses": LENSES}
        require(self.hello_done, "E-PROTO-001", "Call app.hello before other methods.")
        if method == "project.create":
            if self.project:
                self.project.close()
            self.project = Project.create(p["path"], p.get("name", "Untitled scene"), bool(p.get("sample")))
            return self._summary()
        if method == "project.sample":
            if self.project:
                self.project.close()
            path = Path(p.get("path") or Path.home() / "Documents" / "CMNE" / "Mara and Len")
            if (path / "project.cmne.json").exists():
                self.project = Project(path)
            else:
                self.project = Project.create(path, "Mara and Len · The chair and the bowl", sample=True)
            return self._summary()
        if method == "project.open":
            if self.project:
                self.project.close()
            self.project = Project(p["path"])
            return self._summary()
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
            fixture = validate_fixture(p["fixture"])
            write_json(contained(project.root, "fixtures", "active.json"), fixture)
            project.fixture = fixture
            return fixture
        if method == "contract.save":
            contract = validate_contract(p["contract"])
            write_json(contained(project.root, "contracts", "active.json"), contract)
            project.contract = contract
            return contract
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
                if stream == "story":
                    event = project.append_story(branch, p["payload"], p.get("expected_sequence"))
                elif stream == "discourse":
                    event = project.append_discourse(branch, p["payload"], p.get("expected_sequence"))
                else:
                    raise CmneError("E-COMMAND-001", "Only story and discourse commands are supported.")
                return {"accepted": True, "emitted_events": [event], "rejected_reason": None,
                        "invariant_results": [], "projection_hash_before": before,
                        "projection_hash_after": project.projection(branch)["hashes"]}
            except CmneError as exc:
                return {"accepted": False, "emitted_events": [], "rejected_reason": str(exc),
                        "invariant_results": [{"id": exc.code, "passed": False, "field_path": exc.field_path}],
                        "projection_hash_before": before, "projection_hash_after": before}
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
        if method == "draft.patch":
            return project.draft_save(p["draft"])
        if method == "draft.compile_preview":
            return project.draft_preview(p.get("draft") or project.draft_get(p["draft_id"]))
        if method == "draft.seal":
            return project.draft_seal(p["draft_id"])
        if method == "draft.delete":
            project.draft_path(p["draft_id"]).unlink(missing_ok=True)
            return {"deleted": True}
        if method == "scrub.projection":
            return project.projection(branch, p.get("sequence"), p.get("discourse_index"))
        if method == "overlay.series" or method == "strain.series":
            return project.projection(branch)["projections"]["tension"]
        if method == "trace.query":
            return project.trace(branch, p["node_id"])
        if method == "packet.build" or method == "packet.get":
            from cmne.core import build_packet
            return build_packet(project.fixture, project.contract,
                                project.events(branch, "story"), project.events(branch, "discourse"))
        if method == "run.start":
            requested = p.get("conditions")
            if requested and len(requested) > 1:
                require(requested == ["C0", "C1", "C2", "C3"], "E-RUN-001",
                        "Run all expects C0, C1, C2, C3 in order.")
                by_condition = {meta.get("condition"): bid for bid, meta in project.meta["branches"].items()
                                if meta.get("condition")}
                require(all(condition in by_condition for condition in requested), "E-RUN-001",
                        "This project does not have all four condition branches.")
                runs = [project.run(by_condition[condition], [condition]) for condition in requested]
                return {"runs": runs, "status": "failed" if any(run["status"] != "passed" for run in runs)
                        else "passed"}
            return project.run(branch, p.get("conditions"))
        if method == "run.status":
            runs = project.list_runs()
            if p.get("branch_id"):
                runs = [run for run in runs if run.get("branch_id") == branch]
            return runs[-1] if runs else {"status": "idle", "stages": [], "findings": []}
        if method == "run.cancel":
            return {"cancelled": False, "reason": "No asynchronous run is active."}
        if method == "export.report":
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
        return self.project

    def _summary(self) -> dict:
        project = self._project()
        return {"path": str(project.root), "name": project.meta["name"],
                "active_branch": project.meta.get("active_branch", "main"),
                "branches": [{"branch_id": bid, **meta} for bid, meta in project.meta["branches"].items()],
                "fixture": project.fixture, "contract": project.contract}


def handle(dispatcher: Dispatcher, request: dict) -> dict:
    ident = request.get("id")
    try:
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            raise CmneError("E-PROTO-001", "Expected a JSON-RPC 2.0 request.")
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
