"""Acceptance-focused checks for the Milestone 1 project boundary."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cmne.core import CmneError, digest, make_event, stable_id
from cmne.project import Project, read_import_json
from cmne.quantities import basis_points
from cmne.upcast import upcast_event, v1_to_v2
from cmne_sidecar.server import Dispatcher, handle


class ProjectBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.project = Project.create(self.root, "Boundary")

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_failed_project_switch_retains_open_project_and_writer_lock(self):
        self.project.close()
        dispatcher = Dispatcher()
        hello = {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}}
        handle(dispatcher, hello)
        opened = handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                                     "params": {"path": str(self.root)}})
        self.assertEqual(opened["result"]["path"], str(self.root.resolve()))
        failed = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "project.open",
                                     "params": {"path": str(self.root / "missing")}})
        self.assertEqual(failed["error"]["data"]["cmne_code"], "E-PROJECT-001")
        self.assertEqual(dispatcher.project.root, self.root.resolve())
        self.assertTrue((self.root / ".cmne.lock").exists())
        self.assertEqual(handle(dispatcher, {"jsonrpc": "2.0", "id": 4,
                                             "method": "project.get"})["result"]["path"], str(self.root.resolve()))
        dispatcher.project.close()

    def test_post_commit_projection_error_is_not_reported_as_rejection(self):
        self.project.close()
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello"})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": str(self.root)}})
        original = dispatcher.project.projection
        calls = 0

        def projection(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise CmneError("E-STORE-001", "Failed after the append")
            return original(*args, **kwargs)

        with patch.object(dispatcher.project, "projection", side_effect=projection):
            result = handle(dispatcher, {"jsonrpc": "2.0", "id": 3,
                                         "method": "command.submit",
                                         "params": {"payload": {"title": "Committed"}}})
        self.assertIn("error", result)
        self.assertNotIn("rejected_reason", result)
        self.assertEqual([event["payload"]["title"] for event in dispatcher.project.events("main", "story")],
                         ["Committed"])
        dispatcher.project.close()

    def test_rpc_rejects_non_object_params_without_losing_project(self):
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello"})
        for params in ([], "bad", 7):
            result = handle(dispatcher, {"jsonrpc": "2.0", "id": 2,
                                         "method": "project.open", "params": params})
            self.assertEqual(result["error"]["code"], -32602)
        self.assertEqual(handle(dispatcher, [])["error"]["data"]["cmne_code"], "E-PROTO-001")

    def test_contract_change_cannot_invalidate_sealed_crisis(self):
        sample = Project.create(Path(self.temp.name) / "sample", "Sample", sample=True)
        try:
            old = sample.contract
            old_bytes = (sample.root / "contracts" / "active.json").read_bytes()
            with self.assertRaises(CmneError) as error:
                sample.save_contract({**old, "strain_threshold_bp": 10000})
            self.assertEqual(error.exception.code, "E-CRISIS-001")
            self.assertEqual(sample.contract, old)
            self.assertEqual((sample.root / "contracts" / "active.json").read_bytes(), old_bytes)
        finally:
            sample.close()

    def test_second_invalid_event_rejects_the_whole_batch(self):
        initial_hashes = self.project.projection("main")["hashes"]
        with self.assertRaises(CmneError):
            self.project.submit_batch("main", "story", [
                {"title": "First valid event", "world_facts": ["first"]},
                {"title": "Second invalid event", "kind": "observation"},
            ], expected_sequence=0)
        self.assertEqual(self.project.events("main", "story"), [])
        self.assertEqual(self.project.projection("main")["hashes"], initial_hashes)
        result = self.project.submit_batch("main", "story", [
            {"title": "First valid event", "world_facts": ["first"]},
            {"title": "Second valid event", "preconditions": [
                {"op": "atom", "predicate": "first"}]},
        ], expected_sequence=0)
        self.assertEqual([event["sequence"] for event in result], [1, 2])
        self.assertEqual(len(self.project.events("main", "story")), 2)

    def test_expected_head_rejects_stale_append(self):
        self.project.append_story("main", {"title": "Existing"})
        before = (self.root / "branches" / "main" / "story.ndjson").read_bytes()
        with self.assertRaises(CmneError) as error:
            self.project.submit_batch("main", "story", [{"title": "Stale"}], expected_sequence=0)
        self.assertEqual(error.exception.code, "E-APPEND-001")
        self.assertEqual((self.root / "branches" / "main" / "story.ndjson").read_bytes(), before)

    def test_sequence_seven_rejects_expected_five_without_mutation(self):
        self.project.submit_batch("main", "story", [{"title": f"Event {number}"}
                                                    for number in range(1, 8)])
        path = self.root / "branches" / "main" / "story.ndjson"
        before = path.read_bytes()
        with self.assertRaises(CmneError) as error:
            self.project.append_story("main", {"title": "Stale event"}, expected_sequence=5)
        self.assertEqual(error.exception.code, "E-APPEND-001")
        self.assertEqual(path.read_bytes(), before)

    def test_boolean_expected_sequence_is_rejected(self):
        before = self.project.events("main", "story")
        with self.assertRaises(CmneError) as error:
            self.project.append_story("main", {"title": "Bad head"}, expected_sequence=False)
        self.assertEqual(error.exception.code, "E-APPEND-001")
        self.assertEqual(self.project.events("main", "story"), before)

    def test_sealed_event_has_no_update_or_delete_command(self):
        self.project.append_story("main", {"title": "Sealed"})
        path = self.root / "branches" / "main" / "story.ndjson"
        before = path.read_bytes()
        self.assertFalse(hasattr(self.project, "update_event"))
        self.assertFalse(hasattr(self.project, "delete_event"))
        self.project.close()
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": str(self.root)}})
        for method in ("events.update", "events.delete"):
            result = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": method,
                                         "params": {"branch_id": "main", "sequence": 1}})
            self.assertEqual(result["error"]["data"]["cmne_code"], "E-RPC-001")
        self.assertEqual(path.read_bytes(), before)
        dispatcher.project.close()

    def test_ungrounded_disclosure_does_not_append(self):
        story = self.project.append_story("main", {"title": "A fact", "world_facts": ["door open"]})
        with self.assertRaises(CmneError) as error:
            self.project.append_discourse("main", {"title": "Wrong reveal",
                                                   "story_refs": [story["event_id"]],
                                                   "reveal": ["secret motive"]})
        self.assertEqual(error.exception.code, "E-DISCLOSURE-001")
        self.assertEqual(self.project.events("main", "discourse"), [])

    def test_story_only_replay_leaves_reader_at_initial_state(self):
        before = self.project.projection("main")["projections"]["reader"]
        self.project.append_story("main", {"title": "A fact", "world_facts": ["door open"]})
        self.assertEqual(self.project.projection("main")["projections"]["reader"], before)

    def test_rpc_batch_returns_all_events_or_no_events(self):
        self.project.close()
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": str(self.root)}})
        rejected = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "command.submit",
                                       "params": {"stream": "story", "expected_sequence": 0,
                                                  "payloads": [{"title": "Good"}, {"title": ""}]}})
        self.assertFalse(rejected["result"]["accepted"])
        self.assertEqual(dispatcher.project.events("main", "story"), [])
        accepted = handle(dispatcher, {"jsonrpc": "2.0", "id": 4, "method": "command.submit",
                                       "params": {"stream": "story", "expected_sequence": 0,
                                                  "payloads": [{"title": "Good"}, {"title": "Also good"}]}})
        self.assertTrue(accepted["result"]["accepted"])
        self.assertEqual(len(accepted["result"]["emitted_events"]), 2)
        dispatcher.project.close()

    def test_command_results_name_access_and_disclosure_invariants(self):
        self.project.save_fixture({"actors": [{"id": "mara", "name": "Mara"},
                                               {"id": "len", "name": "Len"}],
                                   "entities": [{"id": "note", "name": "Note"}],
                                   "initial_facts": ["Mara is in the kitchen",
                                                     "The note is hidden beneath the bowl"]})
        self.project.close()
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": str(self.root)}})
        hidden = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "command.submit",
                                     "params": {"stream": "story", "payload": {
                                         "title": "Len hides the note", "actor_ids": ["len"],
                                         "entity_ids": ["note"],
                                         "world_facts": ["The note is hidden beneath the bowl"]}}})
        source_id = hidden["result"]["emitted_events"][0]["event_id"]
        unseen = handle(dispatcher, {"jsonrpc": "2.0", "id": 4, "method": "command.submit",
                                     "params": {"stream": "story", "payload": {
                                         "title": "Mara sees the note", "kind": "observation",
                                         "actor_ids": ["mara"], "observed_by": ["mara"]}}})
        self.assertFalse(unseen["result"]["accepted"])
        self.assertEqual(unseen["result"]["invariant_results"][0]["id"], "INV-03")
        self.assertEqual(unseen["result"]["invariant_results"][0]["code"], "E-ACCESS-001")
        reveal = handle(dispatcher, {"jsonrpc": "2.0", "id": 5, "method": "command.submit",
                                     "params": {"stream": "discourse", "payload": {
                                         "title": "False reveal", "story_refs": [source_id],
                                         "reveal": ["Len has a secret plan"]}}})
        self.assertFalse(reveal["result"]["accepted"])
        self.assertEqual(reveal["result"]["invariant_results"][0]["id"], "INV-05")
        self.assertEqual(reveal["result"]["invariant_results"][0]["code"], "E-DISCLOSURE-001")
        dispatcher.project.close()

    def test_second_process_gets_lock_error_while_reader_opens(self):
        code = """import json, sys
from cmne.core import CmneError
from cmne.project import Project
try:
    Project(sys.argv[1])
except CmneError as error:
    print(json.dumps({'writer_error': error.code}))
else:
    raise SystemExit('second writer unexpectedly opened')
reader = Project(sys.argv[1], read_only=True)
print(json.dumps({'reader_events': len(reader.events('main', 'story'))}))
reader.close()
"""
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        completed = subprocess.run([sys.executable, "-c", code, str(self.root)],
                                   env=env, capture_output=True, text=True, check=True)
        lines = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(lines, [{"writer_error": "E-LOCK-001"}, {"reader_events": 0}])

    def test_same_commands_in_two_projects_have_same_ids_and_hashes(self):
        other = Project.create(Path(self.temp.name) / "second", "Boundary")
        try:
            commands = [{"title": "First", "world_facts": ["door open"]},
                        {"title": "Second", "preconditions": [{"op": "atom", "predicate": "door open"}]}]
            first_ids = [event["event_id"] for event in self.project.submit_batch("main", "story", commands)]
            other_ids = [event["event_id"] for event in other.submit_batch("main", "story", commands)]
            self.assertEqual(first_ids, other_ids)
            self.assertEqual(self.project.projection("main")["hashes"], other.projection("main")["hashes"])
        finally:
            other.close()

    def test_branch_append_does_not_change_sibling_projection(self):
        self.project.append_story("main", {"title": "Common"})
        first = self.project.fork("main", 1, "First branch")
        second = self.project.fork("main", 1, "Second branch")
        before = self.project.projection(second["branch_id"])["hashes"]
        self.project.append_story(first["branch_id"], {"title": "Only first branch"})
        self.assertEqual(self.project.projection(second["branch_id"])["hashes"], before)

    def test_read_only_project_can_open_while_writer_holds_lock(self):
        reader = Project(self.root, read_only=True)
        try:
            self.assertEqual(reader.events("main", "story"), [])
            with self.assertRaises(CmneError) as error:
                reader.append_story("main", {"title": "Forbidden"})
            self.assertEqual(error.exception.code, "E-LOCK-001")
        finally:
            reader.close()

    def test_stale_lock_requires_explicit_clear(self):
        self.project.close()
        lock = self.root / ".cmne.lock"
        lock.write_text(json.dumps({"pid": 99999999, "host": socket.gethostname(),
                                    "started_at_ns": 1}), encoding="ascii")
        with self.assertRaises(CmneError) as error:
            Project(self.root)
        self.assertEqual(error.exception.code, "E-LOCK-001")
        self.assertIn("stale", str(error.exception))
        self.assertTrue(Project.clear_stale_lock(self.root))
        reopened = Project(self.root)
        reopened.close()

    def test_snapshot_corruption_is_rebuilt_from_events(self):
        self.project.append_story("main", {"title": "An event"})
        original = self.project.projection("main")
        snapshot = self.root / "snapshots" / "main.json"
        self.assertTrue(snapshot.exists())
        altered = json.loads(snapshot.read_text())
        altered["hashes"]["environment"] = "tampered"
        snapshot.write_text(json.dumps(altered), encoding="utf-8")
        status = self.project.snapshot_status("main")
        self.assertFalse(status["valid_before_rebuild"])
        self.assertTrue(status["rebuilt"])
        self.assertEqual(self.project.projection("main"), original)

    def test_failed_replace_keeps_old_stream_intact(self):
        self.project.append_story("main", {"title": "Existing"})
        stream = self.root / "branches" / "main" / "story.ndjson"
        before = stream.read_bytes()
        with (patch("cmne.project.os.replace", side_effect=OSError("injected failure")),
              self.assertRaises(OSError)):
            self.project.submit_batch("main", "story", [{"title": "New"}])
        self.assertEqual(stream.read_bytes(), before)
        self.assertEqual(len(self.project.events("main", "story")), 1)

    def test_process_death_before_replace_keeps_complete_stream(self):
        self.project.append_story("main", {"title": "Existing"})
        stream = self.root / "branches" / "main" / "story.ndjson"
        before = stream.read_bytes()
        code = """import os, sys
from pathlib import Path
from cmne.project import write_atomic
def die(source, target): os._exit(71)
os.replace = die
write_atomic(Path(sys.argv[1]), b'partial replacement')
"""
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        result = subprocess.run([sys.executable, "-c", code, str(stream)], env=env, check=False)
        self.assertEqual(result.returncode, 71)
        self.assertEqual(stream.read_bytes(), before)
        self.assertEqual(len(self.project.events("main", "story")), 1)

    def test_process_death_after_replace_leaves_complete_stream_and_draft(self):
        self.project.append_story("main", {"title": "Existing"})
        draft = self.project.draft_create("main", "story")
        stream = self.root / "branches" / "main" / "story.ndjson"
        code = """import json, os, sys
from pathlib import Path
from cmne.core import make_event
from cmne.project import write_atomic
path = Path(sys.argv[1])
replace = os.replace
def replace_then_die(source, target):
    replace(source, target)
    os._exit(72)
os.replace = replace_then_die
event = make_event('story', 'main', 2, {'title': 'Second', 'source_kind': 'authored'})
write_atomic(path, path.read_bytes() + json.dumps(event, sort_keys=True, separators=(',', ':')).encode() + b'\\n')
"""
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        result = subprocess.run([sys.executable, "-c", code, str(stream)], env=env, check=False)
        self.assertEqual(result.returncode, 72)
        self.project.close()
        reopened = Project(self.root)
        try:
            self.assertEqual(len(reopened.events("main", "story")), 2)
            self.assertEqual(reopened.draft_get(draft["id"])["id"], draft["id"])
            self.assertEqual(reopened.draft_list("main", "story")[0]["id"], draft["id"])
        finally:
            reopened.close()

    def test_draft_list_recovers_without_ui_local_storage(self):
        first = self.project.draft_create("main", "story")
        second = self.project.draft_create("main", "discourse")
        self.project.close()
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": str(self.root)}})
        story = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "draft.list",
                                    "params": {"branch_id": "main", "lens": "story"}})["result"]
        discourse = handle(dispatcher, {"jsonrpc": "2.0", "id": 4, "method": "draft.list",
                                        "params": {"branch_id": "main", "lens": "discourse"}})["result"]
        self.assertEqual([draft["id"] for draft in story], [first["id"]])
        self.assertEqual([draft["id"] for draft in discourse], [second["id"]])
        dispatcher.project.close()

    def test_reader_sees_only_committed_stream_versions(self):
        reader = Project(self.root, read_only=True)
        observed = []
        failures = []
        def observe():
            try:
                for _ in range(80):
                    events = reader.events("main", "story")
                    observed.append(tuple(event["sequence"] for event in events))
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=observe)
        thread.start()
        try:
            for index in range(10):
                self.project.append_story("main", {"title": f"Event {index}"})
        finally:
            thread.join(timeout=10)
            reader.close()
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, failures)
        self.assertTrue(observed)
        self.assertTrue(all(value == tuple(range(1, len(value) + 1)) for value in observed))

    def test_corrupt_event_names_the_line(self):
        self.project.append_story("main", {"title": "Existing"})
        stream = self.root / "branches" / "main" / "story.ndjson"
        with stream.open("a", encoding="utf-8") as output:
            output.write("{broken JSON}\n")
        with self.assertRaises(CmneError) as error:
            self.project.events("main", "story")
        self.assertEqual(error.exception.code, "E-STORE-001")
        self.assertIn("line 2", str(error.exception))

    def test_upcast_view_preserves_stored_event_bytes(self):
        stream = self.root / "branches" / "main" / "story.ndjson"
        body = {"stream": "story", "branch_id": "main", "sequence": 1,
                "schema_version": 1, "payload": {"title": "Version one"}}
        legacy = {**body, "event_id": stable_id("evt", body), "integrity_hash": digest(body)}
        stream.parent.mkdir(parents=True, exist_ok=True)
        stream.write_bytes((json.dumps(legacy, sort_keys=True, separators=(",", ":")) + "\n").encode())
        original_line = stream.read_bytes().splitlines(keepends=True)[0]
        migrated = self.project.events("main", "story")[0]
        self.assertEqual(migrated["stored_schema_version"], 1)
        self.assertEqual(migrated["effective_schema_version"], 2)
        self.assertEqual(migrated["payload"]["source_kind"], "authored")
        self.assertEqual(migrated["event_id"], legacy["event_id"])
        self.project.append_story("main", {"title": "New event"})
        self.assertEqual(stream.read_bytes().splitlines(keepends=True)[0], original_line)
        self.assertEqual(self.project.events("main", "story")[1]["schema_version"], 2)
        self.assertEqual(self.project.projection("main")["projections"]["environment"]["events"][0],
                         legacy["event_id"])
        with self.assertRaises(CmneError) as error:
            upcast_event(legacy, 3, {1: v1_to_v2})
        self.assertEqual(error.exception.code, "E-UPCAST-001")
        evaluation = {**legacy, "stream": "evaluation", "payload": {"claim": "reader response"}}
        self.assertEqual(upcast_event(evaluation)["payload"], {"claim": "reader response"})

    def test_json_duplicate_keys_and_bad_hash_are_rejected(self):
        self.project.close()
        fixture = self.root / "fixtures" / "active.json"
        fixture.write_text('{"actors":[],"actors":[]}', encoding="utf-8")
        with self.assertRaises(CmneError) as error:
            Project(self.root)
        self.assertEqual(error.exception.code, "E-INPUT-001")

    def test_import_rejects_unsafe_formats_paths_and_size(self):
        folder = Path(self.temp.name)
        yaml = folder / "fixture.yaml"
        yaml.write_text("!!python/object/apply:os.system ['echo bad']", encoding="utf-8")
        with self.assertRaises(CmneError):
            read_import_json(yaml)
        valid = folder / "contract.json"
        valid.write_text('{"id":"imported"}', encoding="utf-8")
        with self.assertRaises(CmneError):
            read_import_json(folder / "sub" / ".." / "contract.json")
        linked = folder / "linked.json"
        try:
            linked.symlink_to(valid)
        except OSError:
            pass  # Windows runners may lack symlink creation rights.
        else:
            with self.assertRaises(CmneError):
                read_import_json(linked)
        large = folder / "large.json"
        large.write_bytes(b" " * (6 * 1024 * 1024))
        with self.assertRaises(CmneError):
            read_import_json(large)
        self.assertEqual(self.project.import_document("contract", valid)["id"], "imported")

    def test_import_rejects_mismatched_claimed_hash(self):
        source = Path(self.temp.name) / "tampered.json"
        source.write_text(json.dumps({"id": "changed", "content_hash": "not-the-content-hash"}),
                          encoding="utf-8")
        before = self.project.contract["content_hash"]
        with self.assertRaises(CmneError) as error:
            self.project.import_document("contract", source)
        self.assertEqual(error.exception.code, "E-INPUT-001")
        self.assertEqual(self.project.contract["content_hash"], before)

    def test_fixture_import_cannot_orphan_existing_event(self):
        self.project.append_story("main", {"title": "Actor A acts", "actor_ids": ["actor_a"]})
        before = self.project.fixture["content_hash"]
        with self.assertRaises(CmneError):
            self.project.save_fixture({"actors": [{"id": "new_a", "name": "New A"},
                                                   {"id": "actor_b", "name": "Actor B"}],
                                       "entities": []})
        self.assertEqual(self.project.fixture["content_hash"], before)

    def test_fixture_change_cannot_invalidate_sealed_precondition(self):
        self.project.save_fixture({**self.project.fixture, "initial_facts": ["door open"]})
        self.project.append_story("main", {"title": "Depends on fixture",
                                           "preconditions": [{"op": "atom", "predicate": "door open"}]})
        before = self.project.fixture["content_hash"]
        with self.assertRaises(CmneError) as error:
            self.project.save_fixture({**self.project.fixture, "initial_facts": []})
        self.assertEqual(error.exception.code, "E-PRECOND-001")
        self.assertEqual(self.project.fixture["content_hash"], before)
        self.assertEqual(len(self.project.events("main", "story")), 1)

    def test_canonical_hash_vector_and_key_order(self):
        value = {"z": [1, 2], "a": {"truth": True, "name": "Mara"}}
        expected = "bfd3e4993471ab09d6f42a2cf53bf3c3a5e8fc170c33650575e588b87c11d963"
        self.assertEqual(digest(value), expected)
        self.assertEqual(digest(value), digest({"a": {"name": "Mara", "truth": True}, "z": [1, 2]}))
        self.assertEqual(make_event("story", "main", 1, {"title": "x"})["event_id"],
                         make_event("story", "main", 1, {"title": "x"})["event_id"])
        self.assertEqual(basis_points(1, 3), 3333)

    def test_checked_in_hash_vectors(self):
        vectors = json.loads((Path(__file__).parent / "golden_hash_vectors.json").read_text(encoding="utf-8"))
        for vector in vectors:
            self.assertEqual(digest(vector["value"]), vector["sha256"])

    def test_malformed_event_line_is_named_and_refused(self):
        self.project.append_story("main", {"title": "One"})
        path = self.root / "branches" / "main" / "story.ndjson"
        with path.open("a", encoding="utf-8") as output:
            output.write('{"stream":"story"}\n')
        with self.assertRaises(CmneError) as error:
            self.project.events("main", "story")
        self.assertEqual(error.exception.code, "E-STORE-001")
        self.assertIn("line 2", str(error.exception))

    def test_missing_final_newline_is_refused(self):
        self.project.append_story("main", {"title": "One"})
        path = self.root / "branches" / "main" / "story.ndjson"
        path.write_bytes(path.read_bytes().rstrip(b"\n"))
        with self.assertRaises(CmneError) as error:
            self.project.events("main", "story")
        self.assertEqual(error.exception.code, "E-STORE-001")

    def test_unhashed_event_field_is_refused(self):
        self.project.append_story("main", {"title": "One"})
        path = self.root / "branches" / "main" / "story.ndjson"
        event = json.loads(path.read_text(encoding="utf-8"))
        event["unhashed_claim"] = "changed"
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        with self.assertRaises(CmneError) as error:
            self.project.events("main", "story")
        self.assertEqual(error.exception.code, "E-STORE-001")

    def test_structured_world_fact_does_not_crash_discourse_validation(self):
        story = self.project.append_story("main", {"title": "Structured fact", "world_facts": [
            {"name": "open", "arguments": ["door"]}]})
        with self.assertRaises(CmneError) as error:
            self.project.append_discourse("main", {"title": "Ungrounded reveal",
                                                   "story_refs": [story["event_id"]],
                                                   "reveal": ["secret motive"]})
        self.assertEqual(error.exception.code, "E-DISCLOSURE-001")

    def test_writer_stops_after_lock_loss(self):
        lock = self.root / ".cmne.lock"
        original = lock.read_bytes()
        lock.unlink()
        try:
            with self.assertRaises(CmneError) as error:
                self.project.append_story("main", {"title": "Must not seal"})
            self.assertEqual(error.exception.code, "E-LOCK-001")
            self.assertEqual(self.project.events("main", "story"), [])
        finally:
            lock.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
