"""Project service: safe local files, immutable events, drafts and view graphs."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .core import (CmneError, LENSES, STAGES, build_packet, check_realization, digest,
                   make_event, replay, require, stable_id, template_realize,
                   validate_contract, validate_discourse_act, validate_fixture,
                   validate_story_event, verify_events)
from .sample import CONDITION_PAUSES, CONDITION_SUFFIXES, CONTRACT, DISCOURSE, FIXTURE, STORY
from .formula import context_from_projection, evaluate

MAX_FILE_BYTES = 5 * 1024 * 1024


def contained(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    require(candidate.is_relative_to(root.resolve()), "E-INPUT-001", "Project file leaves its root.")
    return candidate


def read_json(path: Path) -> dict:
    require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES,
            "E-INPUT-001", f"Missing or oversized file: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise CmneError("E-INPUT-001", f"Invalid JSON in {path.name}: {exc}") from exc


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: Any) -> None:
    write_atomic(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        require(self.root.is_dir() and contained(self.root, "project.cmne.json").is_file(),
                "E-PROJECT-001", "This folder is not a CMNE project.")
        self.meta = read_json(contained(self.root, "project.cmne.json"))
        self.fixture = validate_fixture(read_json(contained(self.root, "fixtures", "active.json")))
        self.contract = validate_contract(read_json(contained(self.root, "contracts", "active.json")))
        self._lock_owned = False
        self._acquire_lock()

    def _acquire_lock(self) -> None:
        path = self.root / ".cmne.lock"
        require(not path.is_symlink(), "E-INPUT-001", "Project lock cannot be a symlink.")
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    pid = int(path.read_text(encoding="ascii").strip())
                    os.kill(pid, 0)
                except ProcessLookupError:
                    path.unlink(missing_ok=True)
                    continue
                except (ValueError, OSError):
                    raise CmneError("E-LOCK-001", "Project lock is unreadable or held by another process.")
                raise CmneError("E-LOCK-001", f"Project is open for writing in process {pid}.")
            else:
                with os.fdopen(fd, "w", encoding="ascii") as lock:
                    lock.write(str(os.getpid()))
                self._lock_owned = True
                return
        raise CmneError("E-LOCK-001", "Unable to acquire the project lock.")

    def close(self) -> None:
        if getattr(self, "_lock_owned", False):
            path = self.root / ".cmne.lock"
            if path.exists() and path.read_text(encoding="ascii").strip() == str(os.getpid()):
                path.unlink()
            self._lock_owned = False

    def __del__(self) -> None:
        self.close()

    @classmethod
    def create(cls, root: str | Path, name: str, sample: bool = False) -> "Project":
        path = Path(root).expanduser().resolve()
        require(not (path / "project.cmne.json").exists(), "E-PROJECT-001",
                "A project already exists at this path.")
        path.mkdir(parents=True, exist_ok=True)
        fixture = validate_fixture(FIXTURE if sample else {
            "name": name, "actors": [{"id": "actor_a", "name": "Actor A"},
                                      {"id": "actor_b", "name": "Actor B"}], "entities": []})
        contract = validate_contract(CONTRACT if sample else {"id": "default"})
        write_json(contained(path, "project.cmne.json"), {"schema_version": 1, "name": name,
                                                  "active_branch": "main", "branches": {"main": {"parent": None, "fork_sequence": 0}}})
        write_json(contained(path, "fixtures", "active.json"), fixture)
        write_json(contained(path, "contracts", "active.json"), contract)
        project = cls(path)
        if sample:
            for item in STORY:
                parents = [project.events("main", "story")[-1]["event_id"]] if project.events("main", "story") else []
                project.append_story("main", {**item, "causal_parents": parents})
            story = project.events("main", "story")
            for item in DISCOURSE:
                index = item["story_index"]
                project.append_discourse("main", {**{k: v for k, v in item.items() if k != "story_index"},
                                                   "story_refs": [story[index]["event_id"]], "focalizer": "mara"})
            for condition, label in (("C0", "Fact revelation"), ("C1", "Belief revision"),
                                     ("C2", "Modal revision"), ("C3", "Conceptual revision")):
                fork = project.fork("main", 7, f"{condition} · {label}")
                branch = fork["branch_id"]
                project.meta["branches"][branch]["condition"] = condition
                if condition == "C3":
                    sealed = project.draft_seal(fork["draft_id"])
                    require(sealed["accepted"], "E-SAMPLE-001", "Sample C3 suffix failed to seal.")
                else:
                    project.draft_path(fork["draft_id"]).unlink()
                    for item in CONDITION_SUFFIXES[condition]:
                        parent = project.events(branch, "story")[-1]["event_id"]
                        project.append_story(branch, {**item, "causal_parents": [parent]})
                branch_story = project.events(branch, "story")
                for index in (5, 6):
                    item = DISCOURSE[index]
                    project.append_discourse(branch, {**{k: v for k, v in item.items() if k != "story_index"},
                                                      "text": CONDITION_PAUSES[condition] if index == 5 else item["text"],
                                                      "story_refs": [branch_story[item["story_index"]]["event_id"]],
                                                      "focalizer": "mara"})
                if condition == "C3":
                    project.meta["active_branch"] = branch
            write_json(contained(path, "project.cmne.json"), project.meta)
        return project

    def branch_ids(self) -> list[str]:
        return list(self.meta["branches"])

    def _branch_path(self, branch: str, stream: str) -> Path:
        require(branch in self.meta["branches"], "E-BRANCH-001", "Unknown branch.", "branch")
        require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", branch)), "E-INPUT-001", "Unsafe branch ID.")
        require(stream in ("story", "discourse", "evaluation"), "E-STORE-001", "Unknown stream.")
        return contained(self.root, "branches", branch, f"{stream}.ndjson")

    def events(self, branch: str, stream: str) -> list[dict]:
        path = self._branch_path(branch, stream)
        if not path.exists():
            return []
        require(path.stat().st_size <= MAX_FILE_BYTES, "E-INPUT-001", "Event file exceeds 5 MB.")
        result = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CmneError("E-STORE-001", f"Corrupt {stream} event at line {line_no}: {exc}") from exc
        ancestry = {branch}
        parent = self.meta["branches"][branch].get("parent")
        while parent:
            require(parent not in ancestry and parent in self.meta["branches"],
                    "E-BRANCH-001", "Branch ancestry is invalid.")
            ancestry.add(parent)
            parent = self.meta["branches"][parent].get("parent")
        verify_events(result, stream, branch, ancestry)
        direct_parent = self.meta["branches"][branch].get("parent")
        if direct_parent:
            parent_events = self.events(direct_parent, stream)
            for index, event in enumerate(result):
                if event["branch_id"] != branch:
                    require(index < len(parent_events) and event == parent_events[index],
                            "E-STORE-001", f"Invalid shared prefix in {stream} at sequence {index + 1}.")
        return result

    def _append(self, branch: str, stream: str, payload: dict, expected_sequence: int | None = None) -> dict:
        events = self.events(branch, stream)
        require(expected_sequence is None or expected_sequence == len(events),
                "E-APPEND-001", f"Expected sequence {expected_sequence}, head is {len(events)}.")
        event = make_event(stream, branch, len(events) + 1, payload)
        events.append(event)
        path = self._branch_path(branch, stream)
        write_atomic(path, b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n" for e in events))
        return event

    def append_story(self, branch: str, payload: dict, expected_sequence: int | None = None) -> dict:
        story = self.events(branch, "story")
        validated = validate_story_event(payload, story, {a["id"] for a in self.fixture["actors"]})
        self._check_preconditions(validated, story, self.events(branch, "discourse"))
        return self._append(branch, "story", validated, expected_sequence)

    def _check_preconditions(self, payload: dict, story: list[dict], discourse: list[dict]) -> None:
        if not payload.get("preconditions"):
            return
        current = replay(self.fixture, self.contract, story, discourse)["projections"]
        context = context_from_projection(current)
        for index, formula in enumerate(payload["preconditions"]):
            require(evaluate(formula, context) is True, "E-PRECOND-001",
                    "Event precondition does not hold in the preceding projection.",
                    f"preconditions.{index}")

    def append_discourse(self, branch: str, payload: dict, expected_sequence: int | None = None) -> dict:
        story, previous = self.events(branch, "story"), self.events(branch, "discourse")
        validated = validate_discourse_act(payload, story, previous, {a["id"] for a in self.fixture["actors"]})
        return self._append(branch, "discourse", validated, expected_sequence)

    def projection(self, branch: str, sequence: int | None = None, discourse_index: int | None = None) -> dict:
        return replay(self.fixture, self.contract, self.events(branch, "story"),
                      self.events(branch, "discourse"), sequence, discourse_index)

    def fork(self, branch: str, sequence: int, name: str) -> dict:
        story = self.events(branch, "story")
        require(0 <= sequence <= len(story), "E-BRANCH-001", "Fork sequence is outside the branch.")
        new_id = stable_id("branch", {"parent": branch, "sequence": sequence, "name": name})
        require(new_id not in self.meta["branches"], "E-BRANCH-001", "This branch already exists.")
        prefix = story[:sequence]
        prefix_ids = {e["event_id"] for e in prefix}
        discourse = []
        for act in self.events(branch, "discourse"):
            if not set(act["payload"].get("story_refs", [])).issubset(prefix_ids):
                break
            discourse.append(act)
        self.meta["branches"][new_id] = {"name": name, "parent": branch, "fork_sequence": sequence}
        if self.meta["branches"][branch].get("condition"):
            self.meta["branches"][new_id]["condition"] = self.meta["branches"][branch]["condition"]
        for stream, source in (("story", prefix), ("discourse", discourse)):
            path = self._branch_path(new_id, stream)
            write_atomic(path, b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                                        for e in source))
        write_json(contained(self.root, "project.cmne.json"), self.meta)
        suffix = story[sequence:]
        draft = self.draft_create(new_id, "story")
        copy_ids = {e["event_id"]: f"node_{e['event_id'][4:]}" for e in suffix}
        draft["nodes"] = [{"id": copy_ids[e["event_id"]], "title": e["payload"]["title"],
                            "fields": {k: v for k, v in e["payload"].items() if k not in ("title", "causal_parents")}}
                           for e in suffix]
        draft["edges"] = [{"id": stable_id("draftedge", [source, e["event_id"]]),
                           "source": copy_ids.get(source, source), "target": copy_ids[e["event_id"]],
                           "kind": "causes", "state": "draft"}
                          for e in suffix for source in e["payload"].get("causal_parents", [])]
        self.draft_save(draft)
        return {"branch_id": new_id, "name": name, "fork_sequence": sequence, "draft_id": draft["id"]}

    def compare(self, left: str, right: str) -> dict:
        a, b = self.events(left, "story"), self.events(right, "story")
        shared = 0
        for x, y in zip(a, b):
            if x["payload"] != y["payload"]:
                break
            shared += 1
        return {"left": left, "right": right, "shared_prefix": shared,
                "first_diverging_sequence": shared + 1 if shared < max(len(a), len(b)) else None,
                "left_only": len(a) - shared, "right_only": len(b) - shared,
                "projection_hashes": {left: self.projection(left)["hashes"], right: self.projection(right)["hashes"]}}

    def draft_path(self, draft_id: str) -> Path:
        require(draft_id.startswith("draft_") and draft_id.replace("_", "").isalnum(),
                "E-DRAFT-001", "Invalid draft ID.")
        return contained(self.root, "drafts", f"{draft_id}.json")

    def draft_create(self, branch: str, lens: str) -> dict:
        require(branch in self.branch_ids() and lens in ("story", "discourse"),
                "E-DRAFT-001", "Draft needs a valid branch and editable lens.")
        import secrets
        draft = {"id": f"draft_{secrets.token_hex(8)}", "branch_id": branch,
                 "lens": lens, "nodes": [], "edges": []}
        write_json(self.draft_path(draft["id"]), draft)
        return draft

    def draft_get(self, draft_id: str) -> dict:
        return read_json(self.draft_path(draft_id))

    def draft_save(self, draft: dict) -> dict:
        require(isinstance(draft, dict) and isinstance(draft.get("nodes"), list)
                and isinstance(draft.get("edges"), list), "E-DRAFT-001", "Malformed draft.")
        old = self.draft_get(draft["id"])
        require(old["branch_id"] == draft.get("branch_id") and old["lens"] == draft.get("lens"),
                "E-DRAFT-001", "Draft branch and lens cannot change.")
        require(len(draft["nodes"]) <= 300 and len(draft["edges"]) <= 600,
                "E-DRAFT-001", "Draft exceeds graph limits.")
        write_json(self.draft_path(draft["id"]), draft)
        return draft

    def validate_connection(self, branch: str, lens: str, source: str, target: str,
                            kind: str, draft: dict | None = None) -> dict:
        story = self.events(branch, "story")
        discourse = self.events(branch, "discourse")
        kinds = {e["event_id"]: "story_event" for e in story}
        kinds.update({e["event_id"]: "discourse_act" for e in discourse})
        if draft:
            kinds.update({n["id"]: "story_event" if lens == "story" else "discourse_act"
                          for n in draft.get("nodes", [])})
        valid_pair = (kind == "causes" and kinds.get(source) == "story_event" and kinds.get(target) == "story_event"
                      or kind == "refs" and kinds.get(source) == "discourse_act" and kinds.get(target) == "story_event")
        reason = "" if valid_pair else "This connection does not match the lens and node kinds."
        if valid_pair and kind == "causes" and target not in {n["id"] for n in (draft or {}).get("nodes", [])}:
            reason = "A sealed event cannot gain a new causal parent."
        if valid_pair and kind == "causes" and not reason:
            pairs = [(e["source"], e["target"]) for e in (draft or {}).get("edges", []) if e["kind"] == "causes"]
            pairs.append((source, target))
            graph: dict[str, list[str]] = {}
            for a, b in pairs:
                graph.setdefault(a, []).append(b)
            seen, active = set(), set()
            def visit(node: str) -> bool:
                if node in active:
                    return True
                if node in seen:
                    return False
                active.add(node)
                if any(visit(next_node) for next_node in graph.get(node, [])):
                    return True
                active.remove(node)
                seen.add(node)
                return False
            if any(visit(n) for n in graph):
                reason = "Causal links cannot form a cycle."
        return {"accepted": not bool(reason), "reason": reason}

    def draft_preview(self, draft: dict) -> dict:
        errors = []
        branch, lens = draft["branch_id"], draft["lens"]
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        actor_ids = {a["id"] for a in self.fixture["actors"]}
        node_ids = [n.get("id") for n in draft["nodes"]]
        if len(node_ids) != len(set(node_ids)):
            errors.append({"code": "E-DRAFT-001", "field_path": "nodes", "message": "Duplicate draft node ID."})
        for edge in draft["edges"]:
            verdict = self.validate_connection(branch, lens, edge["source"], edge["target"], edge["kind"],
                                               {**draft, "edges": [e for e in draft["edges"] if e is not edge]})
            if not verdict["accepted"]:
                errors.append({"code": "E-GRAPH-001", "field_path": edge.get("id", "edges"), "message": verdict["reason"]})
        for node in draft["nodes"]:
            try:
                if lens == "story":
                    payload = {**node.get("fields", {}), "title": node.get("title", "")}
                    payload["causal_parents"] = [e["source"] for e in draft["edges"] if e["kind"] == "causes"
                                                  and e["target"] == node["id"] and e["source"] not in node_ids]
                    validate_story_event(payload, story, actor_ids)
                else:
                    payload = {**node.get("fields", {}), "title": node.get("title", "")}
                    payload["story_refs"] = [e["target"] for e in draft["edges"] if e["kind"] == "refs"
                                             and e["source"] == node["id"]]
                    validate_discourse_act(payload, story, discourse, actor_ids)
            except CmneError as exc:
                errors.append({"code": exc.code, "field_path": f"{node['id']}.{exc.field_path}", "message": str(exc)})
        return {"accepted": not errors, "errors": errors, "count": len(draft["nodes"])}

    def draft_seal(self, draft_id: str) -> dict:
        draft = self.draft_get(draft_id)
        preview = self.draft_preview(draft)
        if not preview["accepted"]:
            return {**preview, "emitted_events": [], "id_map": {}}
        branch, lens = draft["branch_id"], draft["lens"]
        stream = "story" if lens == "story" else "discourse"
        existing = self.events(branch, stream)
        story = existing[:] if lens == "story" else self.events(branch, "story")
        discourse = existing[:] if lens == "discourse" else self.events(branch, "discourse")
        actor_ids = {a["id"] for a in self.fixture["actors"]}
        nodes = {n["id"]: n for n in draft["nodes"]}
        remaining = set(nodes)
        id_map: dict[str, str] = {}
        emitted = []
        while remaining:
            ready = [node_id for node_id in remaining if all(e["source"] not in remaining
                     for e in draft["edges"] if e["kind"] == "causes" and e["target"] == node_id)]
            require(bool(ready), "E-GRAPH-001", "Causal cycle in draft.")
            for node_id in sorted(ready):
                node = nodes[node_id]
                payload = {**node.get("fields", {}), "title": node["title"]}
                if lens == "story":
                    payload["causal_parents"] = [id_map.get(e["source"], e["source"]) for e in draft["edges"]
                                                  if e["kind"] == "causes" and e["target"] == node_id]
                    payload = validate_story_event(payload, story, actor_ids)
                    self._check_preconditions(payload, story, discourse)
                    event = make_event(stream, branch, len(existing) + len(emitted) + 1, payload)
                    story.append(event)
                else:
                    payload["story_refs"] = [e["target"] for e in draft["edges"] if e["kind"] == "refs"
                                             and e["source"] == node_id]
                    payload = validate_discourse_act(payload, story, discourse, actor_ids)
                    event = make_event(stream, branch, len(existing) + len(emitted) + 1, payload)
                    discourse.append(event)
                emitted.append(event)
                id_map[node_id] = event["event_id"]
                remaining.remove(node_id)
        path = self._branch_path(branch, stream)
        write_atomic(path, b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                                      for e in existing + emitted))
        self.draft_path(draft_id).unlink()
        return {"accepted": True, "errors": [], "emitted_events": emitted, "id_map": id_map}

    def graph(self, lens: str, branch: str, draft_id: str | None = None,
              sequence: int | None = None, discourse_index: int | None = None) -> dict:
        require(lens in LENSES, "E-GRAPH-001", "Unknown lens.")
        story = self.events(branch, "story")
        discourse = self.events(branch, "discourse")
        selected_story = story[:sequence] if sequence is not None else story
        selected_discourse = discourse[:discourse_index] if discourse_index is not None else discourse
        nodes, edges = [], []
        def node(id: str, kind: str, title: str, fields: dict, state: str = "sealed", seq: int = 0) -> None:
            nodes.append({"id": id, "kind": kind, "title": title, "fields": fields, "state": state,
                          "lens": lens, "refs": {"branchId": branch, "sequence": seq}, "badges": [],
                          "textAlt": f"{state.capitalize()} {kind.replace('_', ' ')} {title}"})
        def edge(source: str, target: str, kind: str, state: str = "sealed") -> None:
            edges.append({"id": stable_id("edge", [source, target, kind]), "source": source,
                          "target": target, "kind": kind, "state": state})
        if lens == "fixture":
            for actor in self.fixture["actors"]:
                node(actor["id"], "actor", actor["name"], actor)
            for entity in self.fixture["entities"]:
                node(entity["id"], entity.get("kind", "object"), entity["name"], entity)
        elif lens in ("story", "discourse"):
            for event in (selected_story if lens == "story" else selected_discourse):
                p = event["payload"]
                node(event["event_id"], "story_event" if lens == "story" else "discourse_act",
                     p["title"], p, seq=event["sequence"])
                for parent in p.get("causal_parents", []):
                    edge(parent, event["event_id"], "causes")
                if lens == "story":
                    for interpretation in p.get("interpretations", []):
                        for target_seq in interpretation.get("target_story_sequences", []):
                            if 1 <= target_seq <= len(selected_story):
                                edge(event["event_id"], selected_story[target_seq - 1]["event_id"], "retrospects")
            if lens == "discourse":
                for event in selected_story:
                    node(event["event_id"], "story_event", event["payload"]["title"], event["payload"], seq=event["sequence"])
                for event in selected_discourse:
                    for ref in event["payload"].get("story_refs", []):
                        edge(event["event_id"], ref, "refs")
        elif lens == "mind":
            projection = self.projection(branch, sequence, discourse_index)["projections"]
            for actor in (projection["actor_a"], projection["actor_b"]):
                node(actor["id"], "actor", actor["name"], actor)
                for claim, belief in actor["beliefs"].items():
                    belief_id = stable_id("belief", [actor["id"], claim])
                    node(belief_id, "belief", claim, belief)
                    edge(actor["id"], belief_id, "holds")
                for scenario in actor["modal_model"].get("scenarios", []):
                    scenario_id = stable_id("scenario", [actor["id"], scenario])
                    node(scenario_id, "scenario", str(scenario), {"actor_id": actor["id"]})
                    edge(actor["id"], scenario_id, "holds")
                for interpretation in actor["interpretations"]:
                    node(interpretation["id"], "interpretation", interpretation["claim"], interpretation)
                    edge(actor["id"], interpretation["id"], "holds")
                    for target in interpretation["target_event_ids"] or [interpretation["source_event_id"]]:
                        if target in {e["event_id"] for e in selected_story}:
                            if target not in {n["id"] for n in nodes}:
                                source_event = next(e for e in selected_story if e["event_id"] == target)
                                node(target, "story_event", source_event["payload"]["title"], source_event["payload"])
                            edge(interpretation["id"], target, "interprets")
                model = actor["conceptual_model"]
                model_id = f"{actor['id']}_model_{model.get('version', 1)}"
                node(model_id, "model_version", f"{actor['name']} model v{model.get('version', 1)}", model)
                edge(actor["id"], model_id, "holds")
                for concept in model.get("concepts", []):
                    concept_id = stable_id("concept", [model_id, concept])
                    node(concept_id, "concept", str(concept), {"model_version": model.get("version", 1)})
                    edge(model_id, concept_id, "contains")
                old = model.get("supersedes")
                if old:
                    old_id = f"{actor['id']}_model_{old.get('version', 1)}"
                    node(old_id, "model_version", f"{actor['name']} model v{old.get('version', 1)}", old)
                    edge(old_id, model_id, "migrates-to")
                    for concept in old.get("concepts", []):
                        old_concept_id = stable_id("concept", [old_id, concept])
                        node(old_concept_id, "concept", str(concept), {"model_version": old.get("version", 1)})
                        edge(old_id, old_concept_id, "contains")
                        for target in model.get("migration_map", {}).get(concept, []):
                            new_concept_id = stable_id("concept", [model_id, target])
                            edge(old_concept_id, new_concept_id, "migrates-to")
        elif lens == "provenance":
            for event in selected_story:
                node(event["event_id"], "evidence", event["payload"]["title"], event["payload"])
                for interp in event["payload"].get("interpretations", []):
                    claim_id = stable_id("claim", [event["event_id"], interp])
                    node(claim_id, "claim", interp["claim"], interp)
                    edge(event["event_id"], claim_id, "supports")
        elif lens == "motif":
            for entity in self.fixture["entities"]:
                if entity.get("motif"):
                    node(entity["id"], "object", entity["name"], entity)
                    for act in selected_discourse:
                        refs = {e["event_id"]: e for e in selected_story}
                        if any(entity["id"] in refs[ref]["payload"].get("entity_ids", [])
                               for ref in act["payload"].get("story_refs", []) if ref in refs):
                            appearance = f"{entity['id']}_{act['event_id']}"
                            node(appearance, "appearance", act["payload"]["title"],
                                 {"entity": entity["id"], "act": act["event_id"]})
                            edge(entity["id"], appearance, "links")
        elif lens == "pipeline":
            runs = self.list_runs()
            latest = {condition: run for run in runs for condition in run.get("conditions", [])}
            for condition in ("C0", "C1", "C2", "C3"):
                run = latest.get(condition)
                for index, stage in enumerate(STAGES):
                    sid = f"{condition}_{stage.lower()}"
                    status = next((s["status"] for s in run.get("stages", [])
                                   if s["condition"] == condition and s["stage"] == stage), "pending") if run else "pending"
                    node(sid, "stage", stage, {"condition": condition, "status": status})
                    if index:
                        edge(f"{condition}_{STAGES[index-1].lower()}", sid, "flows")
        if draft_id and lens in ("story", "discourse"):
            draft = self.draft_get(draft_id)
            if draft["branch_id"] == branch and draft["lens"] == lens:
                for n in draft["nodes"]:
                    node(n["id"], "story_event" if lens == "story" else "discourse_act",
                         n["title"], n.get("fields", {}), "draft")
                for e in draft["edges"]:
                    edge(e["source"], e["target"], e["kind"], "draft")
        return {"lens": lens, "branchId": branch, "nodes": nodes, "edges": edges,
                "groups": [], "protocolVersion": "1.0"}

    def trace(self, branch: str, node_id: str) -> dict:
        story = self.events(branch, "story")
        event = next((e for e in story if e["event_id"] == node_id), None)
        if event:
            later_interpretations = [{**interp, "creating_event": later["event_id"]}
                                     for later in story for interp in later["payload"].get("interpretations", [])
                                     if event["sequence"] in interp.get("target_story_sequences", [])]
            return {"subject": node_id, "kind": "story_event", "causal_parents": event["payload"].get("causal_parents", []),
                    "observed_by": event["payload"].get("observed_by", []),
                    "disclosures": [a["event_id"] for a in self.events(branch, "discourse")
                                    if node_id in a["payload"].get("story_refs", [])],
                    "interpretations": event["payload"].get("interpretations", []) + later_interpretations}
        return {"subject": node_id, "kind": "unknown", "causal_parents": [], "disclosures": []}

    def list_runs(self) -> list[dict]:
        folder = contained(self.root, "runs")
        runs = [read_json(path) for path in folder.glob("*.json")] if folder.exists() else []
        return sorted(runs, key=lambda run: run.get("run_sequence", 0))

    def run(self, branch: str, conditions: list[str] | None = None) -> dict:
        branch_condition = self.meta["branches"][branch].get("condition", "C3")
        conditions = conditions or [branch_condition]
        require(conditions == [branch_condition], "E-RUN-001",
                "Run the condition on its matching branch.")
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        packet = build_packet(self.fixture, self.contract, story, discourse)
        prose = template_realize(packet)
        findings = check_realization(prose, packet)
        if not story:
            findings.append({"code": "E-RUN-EMPTY", "layer": "story", "message": "Seal at least one story event before running."})
        if not discourse:
            findings.append({"code": "E-RUN-PLAN", "layer": "discourse", "message": "Seal a discourse act before running."})
        story_facts = set(packet["grounded_story_facts"])
        for condition in self.contract["required_story_conditions"]:
            if condition not in story_facts:
                findings.append({"code": "E-RUN-CONTRACT", "layer": "story",
                                 "message": f"Required story condition is missing: {condition}"})
        failed_stage = "Validate" if any(f["layer"] == "story" for f in findings) else "Plan" if any(
            f["layer"] == "discourse" for f in findings) else "Check"
        stages = [{"condition": c, "stage": stage, "status": "failed" if stage == failed_stage and findings
                   else "skipped" if findings and STAGES.index(stage) > STAGES.index(failed_stage) else "passed"}
                  for c in conditions for stage in STAGES]
        next_run_sequence = len(self.list_runs()) + 1
        run = {"run_id": stable_id("run", {"branch": branch, "packet": packet["packet_hash"],
                                          "conditions": conditions, "count": next_run_sequence}),
               "run_sequence": next_run_sequence,
               "branch_id": branch, "conditions": conditions, "packet_hash": packet["packet_hash"],
               "prose": prose, "findings": findings, "stages": stages,
               "projection_hashes": self.projection(branch)["hashes"],
               "status": "failed" if findings else "passed", "realizer": "deterministic-template-v2"}
        write_json(contained(self.root, "runs", f"{run['run_id']}.json"), run)
        write_json(contained(self.root, "packets", f"{packet['packet_hash']}.json"), packet)
        return run
