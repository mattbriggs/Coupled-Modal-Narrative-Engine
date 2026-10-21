"""Project service: safe local files, immutable events, drafts and view graphs."""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import time
from pathlib import Path
from typing import Any

from .core import (CmneError, LENSES, REDUCER_VERSION, SCHEMA_VERSION, STAGES,
                   build_packet, check_realization, digest,
                   make_event, replay, require, stable_id, template_realize,
                   validate_contract, validate_discourse_act, validate_fixture,
                   validate_story_event, verify_events)
from .sample import CONDITION_PAUSES, CONDITION_SUFFIXES, CONTRACT, DISCOURSE, FIXTURE, STORY
from .formula import context_from_projection, evaluate
from .upcast import upcast_event

MAX_FILE_BYTES = 5 * 1024 * 1024


def process_is_alive(pid: int) -> bool:
    """Probe a lock owner without sending a signal or terminating it on Windows."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        win_ctypes: Any = ctypes
        kernel = win_ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return win_ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER; deny = assume live
        try:
            status = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(status)) or status.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def contained(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    require(candidate.is_relative_to(root.resolve()), "E-INPUT-001", "Project file leaves its root.")
    return candidate


def read_json(path: Path) -> dict:
    require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES,
            "E-INPUT-001", f"Missing or oversized file: {path.name}")
    try:
        return parse_json_object(path.read_text(encoding="utf-8"), path.name)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CmneError("E-INPUT-001", f"Invalid JSON in {path.name}: {exc}") from exc


def parse_json_object(source: str, label: str) -> dict:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "E-INPUT-001", f"Duplicate JSON key: {key}.")
            result[key] = value
        return result
    def reject_constant(value):
        raise CmneError("E-INPUT-001", f"Non-finite JSON value: {value}.")
    result = json.loads(source, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    require(isinstance(result, dict), "E-INPUT-001", f"{label} must be a JSON object.")
    return result


def read_import_json(path: str | Path) -> dict:
    """Read bounded JSON and reject a symlink at the selected file path."""
    source = Path(path).expanduser()
    require(".." not in source.parts and source.suffix.lower() == ".json", "E-INPUT-001",
            "Import requires a JSON path without parent traversal.")
    probe = source.absolute()
    require(not probe.is_symlink(), "E-INPUT-001", "Import file cannot be a symlink.")
    return read_json(probe)


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is unavailable on some supported filesystems.
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: Any) -> None:
    write_atomic(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())


class Project:
    def __init__(self, root: str | Path, read_only: bool = False):
        self.root = Path(root).expanduser().resolve()
        require(self.root.is_dir() and contained(self.root, "project.cmne.json").is_file(),
                "E-PROJECT-001", "This folder is not a CMNE project.")
        self.read_only = read_only
        self._lock_owned = False
        self._lock_token: dict[str, Any] | None = None
        if not read_only:
            self._acquire_lock()
        try:
            self.meta = read_json(contained(self.root, "project.cmne.json"))
            require(self.meta.get("schema_version") == 1 and isinstance(self.meta.get("branches"), dict),
                    "E-SCHEMA-001", "Unsupported or malformed project metadata.")
            stored_fixture = read_json(contained(self.root, "fixtures", "active.json"))
            stored_contract = read_json(contained(self.root, "contracts", "active.json"))
            self.fixture = validate_fixture(stored_fixture)
            self.contract = validate_contract(stored_contract)
            for source, validated in ((stored_fixture, self.fixture), (stored_contract, self.contract)):
                require("content_hash" not in source or source["content_hash"] == validated["content_hash"],
                        "E-STORE-001", "Fixture or contract content hash does not match its data.")
        except Exception:
            self.close()
            raise

    def _ensure_writable(self) -> None:
        require(not self.read_only and self._lock_owned, "E-LOCK-001",
                "Open the project for writing before changing it.")
        path = self.root / ".cmne.lock"
        require(path.exists() and not path.is_symlink() and self._lock_info(path) == self._lock_token,
                "E-LOCK-001", "Project writer lock was lost; reopen before changing it.")

    @staticmethod
    def _lock_info(path: Path) -> dict:
        try:
            data = path.read_text(encoding="ascii").strip()
            info = json.loads(data) if data.startswith("{") else {"pid": int(data), "host": socket.gethostname()}
            require(isinstance(info, dict) and type(info.get("pid")) is int
                    and isinstance(info.get("host"), str), "E-LOCK-001", "Project lock is malformed.")
            return info
        except (OSError, ValueError, UnicodeError) as exc:
            raise CmneError("E-LOCK-001", "Project lock is unreadable.") from exc

    @classmethod
    def clear_stale_lock(cls, root: str | Path) -> bool:
        path = Path(root).expanduser().resolve() / ".cmne.lock"
        if not path.exists():
            return False
        require(not path.is_symlink(), "E-INPUT-001", "Project lock cannot be a symlink.")
        info = cls._lock_info(path)
        require(info.get("host") == socket.gethostname() and isinstance(info.get("pid"), int),
                "E-LOCK-001", "A lock from another host cannot be cleared automatically.")
        if not process_is_alive(info["pid"]):
            path.unlink()
            return True
        raise CmneError("E-LOCK-001", "Project lock belongs to a running process.")

    def _acquire_lock(self) -> None:
        path = self.root / ".cmne.lock"
        require(not path.is_symlink(), "E-INPUT-001", "Project lock cannot be a symlink.")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            info = self._lock_info(path)
            if (info.get("host") == socket.gethostname() and isinstance(info.get("pid"), int)
                    and not process_is_alive(info["pid"])):
                raise CmneError("E-LOCK-001", "Project has a stale lock; clear it explicitly.",
                                next_action="Call Project.clear_stale_lock(path) after checking the writer stopped.") from exc
            raise CmneError("E-LOCK-001", "Project is open for writing in another process or host.") from exc
        self._lock_token = {"pid": os.getpid(), "host": socket.gethostname(),
                            "started_at_ns": time.time_ns()}
        with os.fdopen(fd, "w", encoding="ascii") as lock:
            json.dump(self._lock_token, lock, sort_keys=True)
        self._lock_owned = True

    def close(self) -> None:
        if getattr(self, "_lock_owned", False):
            path = self.root / ".cmne.lock"
            if path.exists() and not path.is_symlink() and self._lock_info(path) == self._lock_token:
                path.unlink()
            self._lock_owned = False

    def __del__(self) -> None:
        self.close()

    @classmethod
    def create(cls, root: str | Path, name: str, sample: bool = False) -> Project:
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
                index = int(item["story_index"])
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
                                                      "story_refs": [branch_story[int(item["story_index"])]["event_id"]],
                                                      "focalizer": "mara"})
                if condition == "C3":
                    project.meta["active_branch"] = branch
            write_json(contained(path, "project.cmne.json"), project.meta)
        return project

    def branch_ids(self) -> list[str]:
        return list(self.meta["branches"])

    def save_fixture(self, fixture: dict) -> dict:
        self._ensure_writable()
        validated = validate_fixture(fixture)
        actor_ids = {actor["id"] for actor in validated["actors"]}
        entity_ids = {entity["id"] for entity in validated["entities"]}
        for branch in self.branch_ids():
            story: list[dict] = []
            discourse_events = self.events(branch, "discourse")
            for event in self.events(branch, "story"):
                validate_story_event(event["payload"], story, actor_ids, entity_ids, self.contract,
                                     {a["id"]: a.get("modal_model", {}) for a in validated["actors"]})
                self._check_preconditions(event["payload"], story, discourse_events, validated)
                story.append(event)
            discourse: list[dict] = []
            for act in discourse_events:
                validate_discourse_act(act["payload"], story, discourse, actor_ids)
                discourse.append(act)
        write_json(contained(self.root, "fixtures", "active.json"), validated)
        self.fixture = validated
        return validated

    def save_contract(self, contract: dict) -> dict:
        self._ensure_writable()
        validated = validate_contract(contract)
        actor_ids = {actor["id"] for actor in self.fixture["actors"]}
        entity_ids = {entity["id"] for entity in self.fixture["entities"]}
        models = {actor["id"]: actor.get("modal_model", {}) for actor in self.fixture["actors"]}
        for branch in self.branch_ids():
            story: list[dict] = []
            discourse = self.events(branch, "discourse")
            for event in self.events(branch, "story"):
                validate_story_event(event["payload"], story, actor_ids, entity_ids, validated, models)
                self._check_preconditions(event["payload"], story, discourse, contract=validated)
                story.append(event)
        write_json(contained(self.root, "contracts", "active.json"), validated)
        self.contract = validated
        return validated

    def import_document(self, kind: str, source: str | Path) -> dict:
        require(kind in ("fixture", "contract"), "E-INPUT-001", "Unknown import document kind.")
        data = read_import_json(source)
        if "content_hash" in data:
            validated = validate_fixture(data) if kind == "fixture" else validate_contract(data)
            require(data["content_hash"] == validated["content_hash"], "E-INPUT-001",
                    "Imported document content hash does not match its data.", "content_hash")
        return self.save_fixture(data) if kind == "fixture" else self.save_contract(data)

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
        try:
            raw = path.read_bytes()
            require(not raw or raw.endswith(b"\n"), "E-STORE-001",
                    f"Incomplete {stream} event at final line; the stream lacks a newline.")
            lines = raw.decode("utf-8").splitlines()
        except UnicodeError as exc:
            raise CmneError("E-STORE-001", f"Invalid UTF-8 in {stream} stream.") from exc
        result = []
        for line_no, line in enumerate(lines, 1):
            try:
                result.append(parse_json_object(line, f"line {line_no}"))
            except (ValueError, UnicodeError, RecursionError, CmneError) as exc:
                raise CmneError("E-STORE-001", f"Corrupt {stream} event at line {line_no}: {exc}") from exc
        ancestry = {branch}
        parent = self.meta["branches"][branch].get("parent")
        while parent:
            require(parent not in ancestry and parent in self.meta["branches"],
                    "E-BRANCH-001", "Branch ancestry is invalid.")
            ancestry.add(parent)
            parent = self.meta["branches"][parent].get("parent")
        verify_events(result, stream, branch, ancestry)
        view = [upcast_event(event) for event in result]
        direct_parent = self.meta["branches"][branch].get("parent")
        if direct_parent:
            parent_events = self.events(direct_parent, stream)
            for index, event in enumerate(view):
                if event["branch_id"] != branch:
                    require(index < len(parent_events) and event == parent_events[index],
                            "E-STORE-001", f"Invalid shared prefix in {stream} at sequence {index + 1}.")
        return view

    def _append(self, branch: str, stream: str, payload: dict, expected_sequence: int | None = None) -> dict:
        return self.submit_batch(branch, stream, [payload], expected_sequence)[0]

    def submit_batch(self, branch: str, stream: str, payloads: list[dict],
                     expected_sequence: int | None = None) -> list[dict]:
        """Validate a complete same-stream command before one atomic stream replacement."""
        self._ensure_writable()
        require(stream in ("story", "discourse") and isinstance(payloads, list) and bool(payloads),
                "E-COMMAND-001", "A command needs nonempty story or discourse payloads.")
        require(expected_sequence is None or type(expected_sequence) is int,
                "E-APPEND-001", "Expected sequence must be an integer.")
        existing = self.events(branch, stream)
        require(expected_sequence is None or expected_sequence == len(existing),
                "E-APPEND-001", f"Expected sequence {expected_sequence}, head is {len(existing)}.")
        story = existing[:] if stream == "story" else self.events(branch, "story")
        discourse = existing[:] if stream == "discourse" else self.events(branch, "discourse")
        actor_ids = {actor["id"] for actor in self.fixture["actors"]}
        emitted: list[dict] = []
        for payload in payloads:
            if stream == "story":
                validated = validate_story_event(payload, story, actor_ids,
                                                 {entity["id"] for entity in self.fixture["entities"]},
                                                 self.contract,
                                                 {a["id"]: a.get("modal_model", {}) for a in self.fixture["actors"]})
                self._check_preconditions(validated, story, discourse)
            else:
                validated = validate_discourse_act(payload, story, discourse, actor_ids)
            event = make_event(stream, branch, len(existing) + len(emitted) + 1, validated)
            emitted.append(event)
            (story if stream == "story" else discourse).append(event)
        path = self._branch_path(branch, stream)
        previous_bytes = path.read_bytes() if path.exists() else b""
        write_atomic(path, previous_bytes + b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True,
                                                                separators=(",", ":")).encode() + b"\n"
                                                   for e in emitted))
        return emitted

    def append_story(self, branch: str, payload: dict, expected_sequence: int | None = None) -> dict:
        return self.submit_batch(branch, "story", [payload], expected_sequence)[0]

    def _check_preconditions(self, payload: dict, story: list[dict], discourse: list[dict],
                             fixture: dict | None = None, contract: dict | None = None) -> None:
        if not payload.get("preconditions"):
            return
        current = replay(fixture or self.fixture, contract or self.contract, story, discourse)["projections"]
        context = context_from_projection(current)
        for index, formula in enumerate(payload["preconditions"]):
            require(evaluate(formula, context) is True, "E-PRECOND-001",
                    "Event precondition does not hold in the preceding projection.",
                    f"preconditions.{index}")

    def append_discourse(self, branch: str, payload: dict, expected_sequence: int | None = None) -> dict:
        return self.submit_batch(branch, "discourse", [payload], expected_sequence)[0]

    def projection(self, branch: str, sequence: int | None = None, discourse_index: int | None = None) -> dict:
        story = self.events(branch, "story")
        discourse = self.events(branch, "discourse")
        result = replay(self.fixture, self.contract, story, discourse, sequence, discourse_index)
        if sequence is None and discourse_index is None:
            self._check_snapshot(branch, story, discourse, result)
        return result

    def _check_snapshot(self, branch: str, story: list[dict], discourse: list[dict], result: dict) -> bool:
        """Treat snapshots as verified caches; repair a bad cache only when writable."""
        path = contained(self.root, "snapshots", f"{branch}.json")
        snapshot = {"schema_version": SCHEMA_VERSION, "reducer_version": REDUCER_VERSION,
                    "fixture_hash": self.fixture["content_hash"],
                    "contract_hash": self.contract["content_hash"],
                    "story_sequence": len(story), "discourse_sequence": len(discourse),
                    "last_story_event_id": story[-1]["event_id"] if story else None,
                    "last_discourse_event_id": discourse[-1]["event_id"] if discourse else None,
                    "projections": result["projections"], "hashes": result["hashes"]}
        snapshot["content_hash"] = digest(snapshot)
        try:
            valid = path.exists() and read_json(path) == snapshot
        except CmneError:
            valid = False
        if not valid and not self.read_only:
            self._ensure_writable()
            write_json(path, snapshot)
        return valid

    def snapshot_status(self, branch: str) -> dict:
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        result = replay(self.fixture, self.contract, story, discourse)
        valid = self._check_snapshot(branch, story, discourse, result)
        return {"valid_before_rebuild": valid, "rebuilt": not valid and not self.read_only,
                "hashes": result["hashes"]}

    def fork(self, branch: str, sequence: int, name: str) -> dict:
        self._ensure_writable()
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
            origin = self._branch_path(branch, stream)
            raw_lines = origin.read_bytes().splitlines(keepends=True) if origin.exists() else []
            write_atomic(path, b"".join(raw_lines[:len(source)]))
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
        for x, y in zip(a, b, strict=False):
            if x["payload"] != y["payload"]:
                break
            shared += 1
        def transitions(events: list[dict]) -> list[dict]:
            history = []
            for event in events[shared:]:
                payload = event["payload"]
                operator = ("conceptual" if payload.get("conceptual_revision") else
                            "modal" if payload.get("modal_revision") else
                            "belief" if payload.get("belief_revision") else
                            "crisis" if payload.get("kind") == "crisis" else "fact")
                history.append({"sequence": event["sequence"], "event_id": event["event_id"],
                                "operator": operator, "interpretation_claims": [
                                    item["claim"] for item in payload.get("interpretations", [])]})
            return history
        left_history, right_history = transitions(a), transitions(b)
        projections = {left: self.projection(left)["hashes"], right: self.projection(right)["hashes"]}
        left_interpretations = self.projection(left)["projections"]["actor_a"]["interpretations"]
        right_interpretations = self.projection(right)["projections"]["actor_a"]["interpretations"]
        left_ids = {i["id"] for i in left_interpretations}
        right_ids = {i["id"] for i in right_interpretations}
        return {"left": left, "right": right, "shared_prefix": shared,
                "first_diverging_sequence": shared + 1 if shared < max(len(a), len(b)) else None,
                "left_only": len(a) - shared, "right_only": len(b) - shared,
                "projection_hashes": projections,
                "transition_history": {left: left_history, right: right_history},
                "state_distinguishable": left_history != right_history and projections[left] != projections[right],
                "changed_interpretations": {left: [i for i in left_interpretations if i["id"] not in right_ids],
                                            right: [i for i in right_interpretations if i["id"] not in left_ids]}}

    def motif_ledger(self, branch: str) -> dict:
        story = self.events(branch, "story")
        discourse = self.events(branch, "discourse")
        by_id = {event["event_id"]: event for event in story}
        projection = self.projection(branch)["projections"]
        interpretations = [item for actor in (projection["actor_a"], projection["actor_b"])
                           for item in actor["interpretations"]]
        ledger = {}
        for entity in self.fixture["entities"]:
            if not entity.get("motif"):
                continue
            appearances = []
            for act in discourse:
                refs = [ref for ref in act["payload"].get("story_refs", [])
                        if ref in by_id and entity["id"] in by_id[ref]["payload"].get("entity_ids", [])]
                if refs:
                    links = [item["id"] for item in interpretations
                             if set(item["target_event_ids"]).intersection(refs)]
                    appearances.append({"discourse_act_id": act["event_id"],
                        "discourse_index": act["sequence"], "discourse_title": act["payload"]["title"],
                        "story_event_ids": refs, "salience_bp": act["payload"].get("salience_bp", 5000),
                        "interpretation_ids": links})
            ledger[entity["id"]] = {"entity_id": entity["id"], "name": entity["name"],
                                    "appearances": appearances}
        return {"simulated": True, "branch_id": branch, "entities": ledger}

    def draft_path(self, draft_id: str) -> Path:
        require(draft_id.startswith("draft_") and draft_id.replace("_", "").isalnum(),
                "E-DRAFT-001", "Invalid draft ID.")
        return contained(self.root, "drafts", f"{draft_id}.json")

    def draft_create(self, branch: str, lens: str) -> dict:
        self._ensure_writable()
        require(branch in self.branch_ids() and lens in ("story", "discourse"),
                "E-DRAFT-001", "Draft needs a valid branch and editable lens.")
        import secrets
        draft = {"id": f"draft_{secrets.token_hex(8)}", "branch_id": branch,
                 "lens": lens, "nodes": [], "edges": []}
        write_json(self.draft_path(str(draft["id"])), draft)
        return draft

    def draft_get(self, draft_id: str) -> dict:
        return read_json(self.draft_path(draft_id))

    def draft_list(self, branch: str, lens: str) -> list[dict]:
        """Find recoverable on-disk drafts even when UI local storage was lost."""
        require(branch in self.branch_ids() and lens in ("story", "discourse"),
                "E-DRAFT-001", "Draft recovery needs a valid branch and lens.")
        folder = contained(self.root, "drafts")
        if not folder.exists():
            return []
        recovered = []
        for path in folder.glob("draft_*.json"):
            if path.is_symlink() or not re.fullmatch(r"draft_[0-9a-f]{16}", path.stem):
                continue
            try:
                draft = read_json(path)
            except CmneError:
                continue
            if (draft.get("id") == path.stem and draft.get("branch_id") == branch
                    and draft.get("lens") == lens and isinstance(draft.get("nodes"), list)
                    and isinstance(draft.get("edges"), list)):
                recovered.append((path.stat().st_mtime_ns, draft))
        return [draft for _, draft in sorted(recovered, key=lambda item: (-item[0], item[1]["id"]))]

    def draft_save(self, draft: dict) -> dict:
        self._ensure_writable()
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
                    validate_story_event(payload, story, actor_ids,
                                         {entity["id"] for entity in self.fixture["entities"]}, self.contract)
                else:
                    payload = {**node.get("fields", {}), "title": node.get("title", "")}
                    payload["story_refs"] = [e["target"] for e in draft["edges"] if e["kind"] == "refs"
                                             and e["source"] == node["id"]]
                    validate_discourse_act(payload, story, discourse, actor_ids)
            except CmneError as exc:
                errors.append({"code": exc.code, "field_path": f"{node['id']}.{exc.field_path}", "message": str(exc)})
        return {"accepted": not errors, "errors": errors, "count": len(draft["nodes"])}

    def draft_seal(self, draft_id: str) -> dict:
        self._ensure_writable()
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
        emitted: list[dict] = []
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
                    payload = validate_story_event(payload, story, actor_ids,
                                                   {entity["id"] for entity in self.fixture["entities"]}, self.contract)
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
        previous_bytes = path.read_bytes() if path.exists() else b""
        write_atomic(path, previous_bytes + b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True,
                                                                separators=(",", ":")).encode() + b"\n"
                                                   for e in emitted))
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

    def trace(self, branch: str, node_id: str, query: str = "event", **params) -> dict:
        story = self.events(branch, "story")
        projection = self.projection(branch)["projections"]
        if query == "actor_belief":
            actor_id = params.get("actor_id")
            claim = params.get("claim", node_id)
            actor = next((a for a in (projection["actor_a"], projection["actor_b"])
                          if a["id"] == actor_id), None)
            require(actor is not None, "E-TRACE-001", "Unknown actor for belief trace.")
            assert actor is not None
            return {"query": query, "holder": actor_id, "claim": claim,
                    "belief": actor["beliefs"].get(claim),
                    "provenance": [p for p in actor["provenance"] if p.get("claim") == claim]}
        if query == "reader_inference":
            claim = params.get("claim", node_id)
            return {"query": query, "claim": claim, "simulated": True,
                    "disclosures": [{"discourse_act_id": act["event_id"], "index": act["sequence"],
                                     "role": field, "story_refs": act["payload"].get("story_refs", [])}
                                    for act in self.events(branch, "discourse")
                                    for field in ("reveal", "cue") if claim in act["payload"].get(field, [])]}
        if query == "model_interpretations":
            version = params.get("model_version")
            require(type(version) is int, "E-TRACE-001", "Model version must be an integer.")
            assert isinstance(version, int)
            actor_id = params.get("actor_id")
            return {"query": query, "actor_id": actor_id, "after_model_version": version,
                    "interpretations": [i for actor in (projection["actor_a"], projection["actor_b"])
                                        if actor["id"] == actor_id for i in actor["interpretations"]
                                        if i["model_version"] > version]}
        if query == "prose_access":
            run = next((item for item in self.list_runs() if item["run_id"] == node_id), None)
            require(run is not None, "E-TRACE-001", "Unknown run for prose access trace.")
            assert run is not None
            return {"query": query, "run_id": node_id,
                    "exposures": [f for f in run["findings"] if f["code"] in
                                  ("E-PROSE-PRIVATE", "E-PROSE-CLAIM", "E-PROSE-EARLY")]}
        event = next((e for e in story if e["event_id"] == node_id), None)
        if event:
            later_interpretations = [{**interp, "creating_event": later["event_id"]}
                                     for later in story for interp in later["payload"].get("interpretations", [])
                                     if event["sequence"] in interp.get("target_story_sequences", [])]
            return {"subject": node_id, "kind": "story_event", "causal_parents": event["payload"].get("causal_parents", []),
                    "proposal_id": event["payload"].get("proposal_id"),
                    "accepting_validator": event["payload"].get("validator_id"),
                    "observed_by": event["payload"].get("observed_by", []),
                    "disclosures": [a["event_id"] for a in self.events(branch, "discourse")
                                    if node_id in a["payload"].get("story_refs", [])],
                    "interpretations": event["payload"].get("interpretations", []) + later_interpretations}
        return {"subject": node_id, "kind": "unknown", "causal_parents": [], "disclosures": []}

    def list_runs(self) -> list[dict]:
        folder = contained(self.root, "runs")
        runs = [read_json(path) for path in folder.glob("*.json")] if folder.exists() else []
        return sorted(runs, key=lambda run: run.get("run_sequence", 0))

    def run(self, branch: str, conditions: list[str] | None = None,
            variant_index: int = 0) -> dict:
        self._ensure_writable()
        require(type(variant_index) is int and variant_index in (0, 1, 2), "E-RUN-001",
                "Matched template variant must be 0, 1, or 2.")
        branch_condition = self.meta["branches"][branch].get("condition", "C3")
        conditions = conditions or [branch_condition]
        require(conditions == [branch_condition], "E-RUN-001",
                "Run the condition on its matching branch.")
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        packet = build_packet(self.fixture, self.contract, story, discourse)
        prose = template_realize(packet, variant_index)
        from .prose import check_candidate
        sentence_records, findings = check_candidate(prose, packet)
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
               "matched_variant_index": variant_index,
               "prose": prose, "findings": findings, "stages": stages,
               "candidate": {"packet_hash": packet["packet_hash"], "sentences": sentence_records,
                             "accepted": not findings, "findings": findings},
               "repair_first": failed_stage if findings else None,
               "projection_hashes": self.projection(branch)["hashes"],
               "status": "failed" if findings else "passed", "realizer": "deterministic-template-v2"}
        write_json(contained(self.root, "runs", f"{run['run_id']}.json"), run)
        write_json(contained(self.root, "packets", f"{packet['packet_hash']}.json"), packet)
        return run

    def save_analysis_plan(self, plan: dict) -> dict:
        """Freeze a plan; any subsequent change is a linked amendment."""
        self._ensure_writable()
        from datetime import UTC, datetime
        from .study import validate_plan
        validated = validate_plan(plan)
        current_path = contained(self.root, "study", "current_plan.json")
        previous = read_json(current_path) if current_path.exists() else None
        if previous and previous["plan"]["content_hash"] == validated["content_hash"]:
            return previous
        record = {"plan": validated, "created_at": datetime.now(UTC).isoformat(),
                  "amends_plan_hash": previous["plan"]["content_hash"] if previous else None}
        write_json(contained(self.root, "study", "plans", f"{validated['content_hash']}.json"), record)
        write_json(current_path, record)
        return record

    def analysis_plan(self) -> dict:
        path = contained(self.root, "study", "current_plan.json")
        require(path.exists(), "E-PLAN-001", "Save an analysis plan before exporting an evaluation set.")
        record = read_json(path)
        from .study import validate_plan
        require(record["plan"] == validate_plan(record["plan"]), "E-PLAN-001",
                "Stored analysis plan hash is invalid.")
        return record

    def generate_matched_realizations(self) -> list[dict]:
        """Create three deterministic composition variants for each sample branch."""
        self._ensure_writable()
        branches = {meta.get("condition"): branch for branch, meta in self.meta["branches"].items()
                    if meta.get("condition")}
        require(set(branches) == {"C0", "C1", "C2", "C3"}, "E-STUDY-001",
                "Matched generation needs the four sample branches.")
        existing = self.list_runs()
        generated = []
        for condition in ("C0", "C1", "C2", "C3"):
            for variant in (0, 1, 2):
                prior = next((run for run in existing if run["branch_id"] == branches[condition]
                              and run.get("matched_variant_index", 0) == variant
                              and run.get("status") == "passed"), None)
                generated.append(prior or self.run(branches[condition], [condition], variant))
        return generated

    def study_metrics(self, branch: str) -> dict:
        from .study import structural_measures
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        projections = self.projection(branch)["projections"]
        packet = build_packet(self.fixture, self.contract, story, discourse)
        prose = template_realize(packet)
        findings = check_realization(prose, packet)
        claims = [record for actor in (projections["actor_a"], projections["actor_b"])
                  for record in actor["provenance"]]
        layer_a = {"accepted": not findings and all(record.get("source_event_ids")
                   and record.get("integrity_hash") for record in claims),
                   "blocking_findings": findings, "provenance_records": len(claims),
                   "replay_hashes": self.projection(branch)["hashes"]}
        return {"branch_id": branch, "layer_a": layer_a,
                "layer_b": structural_measures(projections, story, discourse,
                                                self.motif_ledger(branch), prose)}

    def study_ablations(self, branch: str) -> list[dict]:
        from .study import ablation_catalog
        return ablation_catalog(self.events(branch, "story"), self.events(branch, "discourse"))

    def realize_ablations(self, branch: str) -> list[dict]:
        """Realize each altered, uncommitted stream and retain checker findings."""
        self._ensure_writable()
        from .study import ablated_streams, ablation_prose
        story, discourse = self.events(branch, "story"), self.events(branch, "discourse")
        baseline = build_packet(self.fixture, self.contract, story, discourse)
        baseline_prose = template_realize(baseline)
        results = []
        for item in self.study_ablations(branch):
            changed_story, changed_discourse = ablated_streams(item["name"], story, discourse)
            packet = build_packet(self.fixture, self.contract, changed_story, changed_discourse)
            prose, method = ablation_prose(item["name"], baseline_prose, packet)
            findings = check_realization(prose, packet)
            record = {**item, "analysis_only": False, "branch_id": branch,
                      "baseline_packet_hash": baseline["packet_hash"],
                      "baseline_text_hash": digest(baseline_prose),
                      "packet_hash": packet["packet_hash"], "text_hash": digest(prose),
                      "text_changed": prose != baseline_prose,
                      "realization_method": method,
                      "prose": prose, "findings": findings,
                      "status": "rejected" if findings else "passed"}
            results.append(record)
        for record in results:
            write_json(contained(self.root, "study", "ablations", branch,
                                 f"{record['name']}.json"), record)
        return results

    def export_evaluation_set(self, seed: int = 33) -> dict:
        self._ensure_writable()
        from .study import blinded_order, passage_html, protocol_html
        record = self.analysis_plan()
        plan = record["plan"]
        runs = self.list_runs()
        entries, key = blinded_order(runs, seed, plan["content_hash"])
        study_id = stable_id("study", {"plan_hash": plan["content_hash"], "seed": seed,
                                      "text_hashes": [entry["text_hash"] for entry in entries]})
        public = contained(self.root, "exports", "evaluation", study_id, "public")
        private = contained(self.root, "study", "keys", f"{study_id}.json")
        by_id = {run["run_id"]: run for run in runs}
        for entry in entries:
            prose = by_id[key[entry["passage_id"]]["run_id"]]["prose"]
            text_path = contained(public, entry["text_file"])
            html_path = contained(public, entry["html_file"])
            write_atomic(text_path, (prose + "\n").encode("utf-8"))
            write_atomic(html_path, passage_html(prose, entry["passage_id"]).encode("utf-8"))
        manifest = {"study_id": study_id, "plan_hash": plan["content_hash"],
                    "session_limit_minutes": plan["session_limit_minutes"], "passages": entries}
        write_json(contained(public, "manifest.json"), manifest)
        write_atomic(contained(public, "protocol.html"), protocol_html(plan).encode("utf-8"))
        write_json(private, {"study_id": study_id, "plan_hash": plan["content_hash"],
                             "seed": seed, "passages": key})
        return {"study_id": study_id, "public_path": str(public), "key_path": str(private),
                "passage_count": len(entries), "plan_hash": plan["content_hash"]}

    def import_responses(self, study_id: str, source: str | Path | dict) -> dict:
        self._ensure_writable()
        from .study import validate_responses
        require(bool(re.fullmatch(r"study_[0-9a-f]{16}", study_id)), "E-STUDY-001",
                "Unknown study ID.")
        key = read_json(contained(self.root, "study", "keys", f"{study_id}.json"))["passages"]
        public = contained(self.root, "exports", "evaluation", study_id, "public")
        manifest = read_json(contained(public, "manifest.json"))
        passages = {entry["passage_id"]: {**entry,
            "text": contained(public, entry["text_file"]).read_text(encoding="utf-8").rstrip("\n")}
            for entry in manifest["passages"]}
        document = read_import_json(source) if not isinstance(source, dict) else source
        require(isinstance(document, dict) and isinstance(document.get("responses"), list), "E-RESPONSE-001",
                "Response document needs a responses array.", "responses")
        accepted = validate_responses(document["responses"], key, passages)
        response_path = contained(self.root, "study", "responses", f"{study_id}.json")
        prior = read_json(response_path).get("responses", []) if response_path.exists() else []
        seen = {(row["evaluator_id"], row["passage_id"]) for row in prior}
        require(all((row["evaluator_id"], row["passage_id"]) not in seen for row in accepted),
                "E-RESPONSE-001", "An evaluator/passage response already exists.")
        write_json(response_path, {"study_id": study_id, "responses": prior + accepted})
        return {"study_id": study_id, "accepted": len(accepted), "total": len(prior) + len(accepted)}

    def analysis_report(self, study_id: str) -> dict:
        self._ensure_writable()
        from .study import analyze_responses
        require(bool(re.fullmatch(r"study_[0-9a-f]{16}", study_id)), "E-STUDY-001",
                "Unknown study ID.")
        key_record = read_json(contained(self.root, "study", "keys", f"{study_id}.json"))
        plan_record = read_json(contained(self.root, "study", "plans",
                                          f"{key_record['plan_hash']}.json"))
        response_path = contained(self.root, "study", "responses", f"{study_id}.json")
        rows = read_json(response_path).get("responses", []) if response_path.exists() else []
        report = {"study_id": study_id, **analyze_responses(rows, plan_record["plan"], self.list_runs())}
        write_json(contained(self.root, "study", "reports", f"{study_id}.json"), report)
        return report

    def decision_packet(self, study_id: str) -> dict:
        """Build a reproducible evidence packet for the later human decision gate."""
        self._ensure_writable()
        report = self.analysis_report(study_id)
        plan = read_json(contained(self.root, "study", "plans",
                                   f"{report['plan_hash']}.json"))["plan"]
        branches = {meta.get("condition"): bid for bid, meta in self.meta["branches"].items()
                    if meta.get("condition")}
        require(all(condition in branches for condition in ("C0", "C1", "C2", "C3")),
                "E-STUDY-001", "The decision packet needs C0–C3 branches.")
        structural = {condition: self.study_metrics(branches[condition])
                      for condition in ("C0", "C1", "C2", "C3")}
        ablations = self.realize_ablations(branches["C3"])
        evidence = {"study_id": study_id, "plan_hash": report["plan_hash"],
                    "response_count": report["responses"],
                    "target_sample_size": plan["target_sample_size"],
                    "primary_effects": report["effect_sizes"],
                    "contrary_results": report["contrary_results"],
                    "null_result": report["null_result"],
                    "null_alternatives": report["null_alternatives"],
                    "structural": structural,
                    "ablations": [{key: item[key] for key in
                                   ("name", "changed_payload_hash", "baseline_text_hash", "text_hash",
                                    "status", "findings", "realization_method")}
                                  for item in ablations],
                    "human_review_required": True,
                    "decision": "pending_human_review"}
        packet = {**evidence, "content_hash": digest(evidence)}
        write_json(contained(self.root, "study", "decision-packets", f"{study_id}.json"), packet)
        return packet
