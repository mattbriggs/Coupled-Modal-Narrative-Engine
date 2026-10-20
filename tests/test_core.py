import tempfile
import unittest
from pathlib import Path

from cmne.core import CmneError, digest, replay, validate_contract
from cmne.project import Project
from cmne_sidecar.server import Dispatcher, handle


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project.create(Path(self.temp.name) / "sample", "Sample", sample=True)

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_sample_replays_deterministically_and_keeps_six_projections(self):
        first = self.project.projection("main")
        second = self.project.projection("main")
        self.assertEqual(first["hashes"], second["hashes"])
        self.assertEqual(len(first["projections"]), 6)
        self.assertEqual(len(self.project.events("main", "story")), 10)
        self.assertEqual(len(self.project.events("main", "discourse")), 7)
        self.assertEqual(first["projections"]["reader"]["simulated"], True)

    def test_reinterpretation_changes_the_mind_but_keeps_the_past(self):
        early = self.project.projection("main", sequence=7)["projections"]["actor_a"]
        later = self.project.projection("main", sequence=9)["projections"]["actor_a"]
        self.assertEqual(early["conceptual_model"]["version"], 1)
        self.assertEqual(later["conceptual_model"]["version"], 2)
        self.assertEqual(len([i for i in later["interpretations"] if i["target_event_ids"]]), 2)
        first_event = self.project.events("main", "story")[0]
        self.assertEqual(self.project.trace("main", first_event["event_id"])["interpretations"][0]["model_version"], 2)

    def test_four_condition_branches_diverge_after_shared_prefix(self):
        branches = {meta.get("condition"): branch_id for branch_id, meta in self.project.meta["branches"].items()
                    if meta.get("condition")}
        self.assertEqual(set(branches), {"C0", "C1", "C2", "C3"})
        self.assertEqual(self.project.meta["active_branch"], branches["C3"])
        prefix = [e["event_id"] for e in self.project.events(branches["C0"], "story")[:7]]
        for condition, branch in branches.items():
            self.assertEqual([e["event_id"] for e in self.project.events(branch, "story")[:7]], prefix)
            self.assertEqual(len(self.project.events(branch, "discourse")), 7)
            self.assertEqual(self.project.run(branch)["conditions"], [condition])
        c0 = self.project.projection(branches["C0"])["projections"]["actor_a"]
        c1 = self.project.projection(branches["C1"])["projections"]["actor_a"]
        c2 = self.project.projection(branches["C2"])["projections"]["actor_a"]
        c3 = self.project.projection(branches["C3"])["projections"]["actor_a"]
        self.assertEqual(c0["conceptual_model"]["version"], 1)
        self.assertEqual(c1["beliefs"]["The repairs are care"]["status"], "rejected")
        self.assertEqual(c2["modal_model"]["version"], 2)
        self.assertEqual(c3["conceptual_model"]["version"], 2)
        self.assertNotEqual(self.project.run(branches["C0"])["prose"],
                            self.project.run(branches["C3"])["prose"])
        mind = self.project.graph("mind", branches["C3"])
        self.assertIn("concept", {node["kind"] for node in mind["nodes"]})
        self.assertIn("migrates-to", {edge["kind"] for edge in mind["edges"]})
        story = self.project.graph("story", branches["C3"])
        self.assertEqual(len([edge for edge in story["edges"] if edge["kind"] == "retrospects"]), 2)

    def test_rejected_observation_does_not_change_history(self):
        before = self.project.projection("main")["hashes"]
        count = len(self.project.events("main", "story"))
        with self.assertRaises(CmneError) as error:
            self.project.append_story("main", {"title": "Impossible sight", "kind": "observation",
                                                "actor_ids": ["mara"]})
        self.assertEqual(error.exception.code, "E-ACCESS-001")
        self.assertEqual(len(self.project.events("main", "story")), count)
        self.assertEqual(self.project.projection("main")["hashes"], before)

    def test_precondition_uses_projection_before_append(self):
        before = len(self.project.events("main", "story"))
        with self.assertRaises(CmneError) as error:
            self.project.append_story("main", {"title": "Impossible command",
                                               "preconditions": [{"op": "atom", "predicate": "Unseen world fact"}]})
        self.assertEqual(error.exception.code, "E-PRECOND-001")
        self.assertEqual(len(self.project.events("main", "story")), before)
        event = self.project.append_story("main", {"title": "Possible command",
                                                   "preconditions": [{"op": "atom", "predicate": "Len leaves"}]})
        self.assertEqual(event["sequence"], before + 1)

    def test_fork_keeps_prefix_and_draft_suffix(self):
        original = self.project.events("main", "story")
        fork = self.project.fork("main", 4, "No rocking chair")
        branch = fork["branch_id"]
        self.assertEqual(self.project.events(branch, "story"), original[:4])
        draft = self.project.draft_get(fork["draft_id"])
        self.assertEqual(len(draft["nodes"]), 6)
        draft["nodes"] = [node for node in draft["nodes"] if node["title"] != "Len leaves; the chair rocks"]
        draft["edges"] = [edge for edge in draft["edges"] if edge["source"] in {n["id"] for n in draft["nodes"]}
                          and edge["target"] in {n["id"] for n in draft["nodes"]}]
        self.project.draft_save(draft)
        self.assertEqual(len(self.project.events("main", "story")), 10)
        self.assertEqual(len(self.project.events(branch, "story")), 4)
        self.assertEqual(self.project.compare("main", branch)["shared_prefix"], 4)

    def test_forked_suffix_can_be_sealed_in_order(self):
        fork = self.project.fork("main", 7, "Replay suffix")
        result = self.project.draft_seal(fork["draft_id"])
        self.assertTrue(result["accepted"], result["errors"])
        self.assertEqual(len(result["emitted_events"]), 3)
        self.assertEqual(len(self.project.events(fork["branch_id"], "story")), 10)
        self.assertGreaterEqual(self.project.compare("main", fork["branch_id"])["shared_prefix"], 7)

    def test_draft_seal_is_atomic_and_rejects_invalid_fields(self):
        draft = self.project.draft_create("main", "story")
        draft["nodes"] = [{"id": "node_a", "title": "", "fields": {"kind": "action"}}]
        self.project.draft_save(draft)
        before = len(self.project.events("main", "story"))
        self.assertFalse(self.project.draft_seal(draft["id"])["accepted"])
        self.assertEqual(len(self.project.events("main", "story")), before)
        draft["nodes"][0]["title"] = "Mara waits"
        self.project.draft_save(draft)
        result = self.project.draft_seal(draft["id"])
        self.assertTrue(result["accepted"])
        self.assertEqual(len(self.project.events("main", "story")), before + 1)

    def test_lock_refuses_second_writer(self):
        with self.assertRaises(CmneError) as error:
            Project(self.project.root)
        self.assertEqual(error.exception.code, "E-LOCK-001")

    def test_run_keeps_prose_out_of_canon(self):
        before = [e["event_id"] for e in self.project.events("main", "story")]
        run = self.project.run("main")
        self.assertEqual(run["status"], "passed")
        self.assertIn("chair rocked once", run["prose"])
        self.assertEqual([e["event_id"] for e in self.project.events("main", "story")], before)
        self.assertEqual(run["packet_hash"], digest({k: v for k, v in __import__("cmne.core", fromlist=["build_packet"]).build_packet(
            self.project.fixture, self.project.contract, self.project.events("main", "story"),
            self.project.events("main", "discourse")).items() if k != "packet_hash"}))

    def test_empty_project_run_reports_repair_first(self):
        other = Project.create(Path(self.temp.name) / "empty", "Empty")
        try:
            run = other.run("main")
            self.assertEqual(run["status"], "failed")
            self.assertEqual(run["stages"][0]["status"], "failed")
            self.assertIn("E-RUN-EMPTY", {f["code"] for f in run["findings"]})
        finally:
            other.close()

    def test_project_rejects_symlink_that_leaves_root(self):
        other = Path(self.temp.name) / "elsewhere.json"
        other.write_text("{}", encoding="utf-8")
        self.project.close()
        contract = self.project.root / "contracts" / "active.json"
        contract.unlink()
        contract.symlink_to(other)
        with self.assertRaises(CmneError) as error:
            Project(self.project.root)
        self.assertEqual(error.exception.code, "E-INPUT-001")


class ContractTests(unittest.TestCase):
    def test_overlap_is_rejected_with_field_path(self):
        with self.assertRaises(CmneError) as error:
            validate_contract({"required_story_conditions": ["x"], "forbidden_story_conditions": ["x"]})
        self.assertEqual(error.exception.field_path, "required_story_conditions")

    def test_protocol_requires_hello(self):
        dispatcher = Dispatcher()
        first = handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "project.get", "params": {}})
        self.assertEqual(first["error"]["data"]["cmne_code"], "E-PROTO-001")
        hello = handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "app.hello",
                                    "params": {"protocol_version": "1.0"}})
        self.assertEqual(hello["result"]["protocol_version"], "1.0")

    def test_sidecar_runs_all_sample_conditions(self):
        with tempfile.TemporaryDirectory() as folder:
            dispatcher = Dispatcher()
            handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello", "params": {}})
            created = handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.create",
                                          "params": {"path": folder + "/sample", "name": "Sample", "sample": True}})
            self.assertIn("result", created)
            runs = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "run.start",
                                       "params": {"conditions": ["C0", "C1", "C2", "C3"]}})
            self.assertEqual([r["conditions"][0] for r in runs["result"]["runs"]], ["C0", "C1", "C2", "C3"])
            pipeline = handle(dispatcher, {"jsonrpc": "2.0", "id": 4, "method": "graph.get",
                                           "params": {"lens": "pipeline"}})["result"]
            self.assertEqual(len([n for n in pipeline["nodes"] if n["fields"]["status"] == "passed"]), 28)
            dispatcher.project.close()


if __name__ == "__main__":
    unittest.main()
