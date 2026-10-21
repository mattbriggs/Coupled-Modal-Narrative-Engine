"""Milestone 2/3 acceptance histories and independent projection fixtures."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from cmne.core import (CmneError, build_packet, check_realization, digest,
                       validate_fixture)
from cmne.machines import (REVISION_OPTIONS, apply_modal_revision, crisis_assessment,
                           strain, validate_modal_model)
from cmne.project import Project
from cmne.prose import check_candidate


class MachineGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project.create(Path(self.temp.name) / "sample", "Sample", sample=True)
        self.branches = {meta.get("condition"): branch for branch, meta in self.project.meta["branches"].items()
                         if meta.get("condition")}

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_ac08_necessity_and_impossibility_conflict_is_rejected(self):
        fixture = {"actors": [{"id": "a", "name": "A", "modal_model": {
            "version": 1, "constraints": {"necessary": ["p"], "impossible": ["p"]}}},
                              {"id": "b", "name": "B"}], "entities": []}
        with self.assertRaises(CmneError) as error:
            validate_fixture(fixture)
        self.assertEqual(error.exception.code, "E-MODEL-001")
        with self.assertRaises(CmneError) as operation_error:
            apply_modal_revision({"version": 1, "constraints": {"necessary": ["p"]}},
                                 {"add_impossible": ["p"]}, "evt_revision")
        self.assertEqual(operation_error.exception.code, "E-MODEL-001")

    def test_modal_scenario_needs_revision_basis_and_weights_determine_strain(self):
        model = {"version": 1, "constraints": {"necessary": ["p"], "impossible": []},
                 "ranked_scenarios": [{"possible": True, "violates_necessity": ["p"]}]}
        with self.assertRaises(CmneError) as error:
            validate_modal_model(model)
        self.assertEqual(error.exception.code, "E-MODEL-001")
        revised = apply_modal_revision({"version": 1, "constraints": {"necessary": ["p"]}},
            {"remove_necessity": ["p"], "ranked_scenarios": [{"possible": True,
             "violates_necessity": ["p"]}]}, "evt_revision")
        self.assertEqual(revised["constraints"]["necessary"], [])
        self.assertEqual(revised["ranked_scenarios"][0]["revision_event_id"], "evt_revision")
        components = {"contradiction": 10000, "unexplained": 0, "failed_prediction": 0,
                      "repair_complexity": 0, "identity_goal": 0}
        self.assertEqual(strain(self.project.contract, {"strain_components_bp": components})["score_bp"], 2500)

    def test_ac09_ac10_old_models_and_interpretations_survive_revision(self):
        branch = self.branches["C3"]
        before_bytes = (self.project.root / "branches" / branch / "story.ndjson").read_bytes()
        old = self.project.projection(branch, sequence=7)["projections"]["actor_a"]
        new = self.project.projection(branch)["projections"]["actor_a"]
        self.assertEqual(new["conceptual_model"]["supersedes"], old["conceptual_model"])
        self.assertEqual(new["conceptual_model"]["migration_map"]["care"], ["care", "avoidance"])
        self.assertEqual(set(new["conceptual_model"]["unresolved_terms"]), {"care", "avoidance"})
        for target in self.project.events(branch, "story")[:2]:
            records = [i for i in new["interpretations"] if target["event_id"] in i["target_event_ids"]]
            self.assertEqual({i["model_version"] for i in records}, {1, 2})
            self.assertTrue(any(i["supersedes_interpretations"] for i in records if i["model_version"] == 2))
        self.assertEqual((self.project.root / "branches" / branch / "story.ndjson").read_bytes(), before_bytes)

    def test_ac11_ac12_crisis_needs_access_and_offers_seven_options(self):
        branch = self.branches["C3"]
        story = self.project.events(branch, "story")
        crisis = story[8]["payload"]
        assessment = crisis_assessment(self.project.contract, story[:8], crisis)
        self.assertTrue(assessment["eligible"])
        self.assertEqual(tuple(assessment["options"]), REVISION_OPTIONS)
        inaccessible = deepcopy(crisis)
        inaccessible["title"] = "Unseen trigger"
        inaccessible["crisis"]["evidence_story_sequence"] = 3  # Len's private note
        before = len(story)
        with self.assertRaises(CmneError) as error:
            self.project.append_story(branch, inaccessible)
        self.assertEqual(error.exception.code, "E-CRISIS-001")
        self.assertEqual(len(self.project.events(branch, "story")), before)

    def test_ac13_four_conditions_have_distinct_state_transitions(self):
        for left_index, left in enumerate(("C0", "C1", "C2", "C3")):
            for right in ("C0", "C1", "C2", "C3")[left_index + 1:]:
                compared = self.project.compare(self.branches[left], self.branches[right])
                self.assertGreaterEqual(compared["shared_prefix"], 7)
                self.assertTrue(compared["state_distinguishable"], (left, right))
        c1 = self.project.projection(self.branches["C1"])["projections"]["actor_a"]
        self.assertEqual(c1["conceptual_model"]["version"], 1)
        self.assertEqual(c1["modal_model"]["version"], 1)
        self.assertEqual(c1["beliefs"]["The repairs are care"]["status"], "rejected")

    def test_ac20_generated_proposal_trace_cites_validator(self):
        event = self.project.append_story("main", {"title": "Proposed action", "source_kind": "generated",
            "proposal_id": "proposal-001", "validator_id": "cmne-command-validator-v2"})
        trace = self.project.trace("main", event["event_id"])
        self.assertEqual((trace["proposal_id"], trace["accepting_validator"]),
                         ("proposal-001", "cmne-command-validator-v2"))

    def test_ac21_candidate_has_seven_structural_checks(self):
        actor = self.project.projection(self.branches["C3"])["projections"]["actor_a"]
        candidate = actor["epiphany_candidate"]
        self.assertEqual(candidate["label"], "epiphany candidate")
        self.assertTrue(candidate["candidate"])
        self.assertEqual(len(candidate["checks"]), 7)
        self.assertTrue(all(candidate["checks"].values()))
        self.assertGreaterEqual(len(candidate["retrospective_interpretation_ids"]), 2)

    def test_ac39_motif_ledger_links_appearances_and_interpretations(self):
        ledger = self.project.motif_ledger(self.branches["C3"])["entities"]
        self.assertEqual({entry["discourse_index"] for entry in ledger["chair"]["appearances"]}, {1, 4, 6})
        self.assertEqual({entry["discourse_index"] for entry in ledger["bowl"]["appearances"]}, {3, 5, 6, 7})
        self.assertTrue(any(entry["interpretation_ids"] for entry in ledger["chair"]["appearances"]))
        self.assertTrue(any(entry["interpretation_ids"] for entry in ledger["bowl"]["appearances"]))

    def test_five_provenance_trace_queries(self):
        branch = self.branches["C3"]
        belief = self.project.trace(branch, "The repairs are care", "actor_belief",
                                    actor_id="mara")
        self.assertTrue(belief["provenance"])
        inference = self.project.trace(branch, "something has changed", "reader_inference")
        self.assertTrue(inference["simulated"])
        self.assertEqual(inference["disclosures"][0]["index"], 1)
        changed = self.project.trace(branch, "", "model_interpretations",
                                     actor_id="mara", model_version=1)
        self.assertGreaterEqual(len(changed["interpretations"]), 2)
        run = self.project.run(branch)
        exposed = self.project.trace(branch, run["run_id"], "prose_access")
        self.assertEqual(exposed["exposures"], [])
        event = self.project.events(branch, "story")[0]
        self.assertEqual(self.project.trace(branch, event["event_id"])["kind"], "story_event")

    def test_nine_sample_history_observations(self):
        """Check nine outcomes in the bundled sample; independent goldens remain a gate."""
        branch = self.branches["C3"]
        story = self.project.events(branch, "story")
        actor = self.project.projection(branch)["projections"]["actor_a"]
        cases = {
            "direct observation": "mara" in story[5]["payload"]["observed_by"],
            "deceptive testimony": story[3]["payload"]["kind"] == "utterance" and
                "The repairs are care" in actor["beliefs"] and
                "The repairs are care" not in self.project.projection(branch)["projections"]["environment"]["facts"],
            "mistaken memory": story[7]["payload"]["kind"] == "recollection" and
                actor["interpretations"][0]["model_version"] == 1,
            "simple belief correction": self.project.projection(self.branches["C1"])["projections"]["actor_a"]
                ["beliefs"]["The repairs are care"]["status"] == "rejected",
            "modal expansion": self.project.projection(self.branches["C2"])["projections"]["actor_a"]
                ["modal_model"]["version"] == 2,
            "conceptual split": actor["conceptual_model"]["migration_map"]["care"] == ["care", "avoidance"],
            "unresolved crisis": actor["epiphany_candidate"]["candidate"] and
                bool(actor["conceptual_model"]["unresolved_terms"]),
            "reader-only epiphany": self.project.projection(branch, sequence=7)["projections"]["reader"]["simulated"],
            "character-only epiphany": self.project.projection(branch, discourse_index=0)["projections"]["actor_a"]
                ["conceptual_model"]["version"] == 2,
        }
        self.assertEqual(len(cases), 9)
        self.assertTrue(all(cases.values()), cases)

    def test_nine_independent_golden_histories(self):
        cases = json.loads((Path(__file__).parent / "golden_histories.json").read_text())
        self.assertEqual(len(cases), 9)
        self.assertEqual(len({case["id"] for case in cases}), 9)
        for case in cases:
            with self.subTest(history=case["id"]), tempfile.TemporaryDirectory() as folder:
                project = Project.create(Path(folder) / case["id"], case["id"])
                try:
                    if "fixture_initial_facts" in case:
                        project.save_fixture({**project.fixture,
                                              "initial_facts": case["fixture_initial_facts"]})
                    story = [project.append_story("main", payload) for payload in case["story"]]
                    for act in case["discourse"]:
                        payload = {key: value for key, value in act.items() if key != "story_ref_indices"}
                        payload["story_refs"] = [story[index]["event_id"]
                                                 for index in act["story_ref_indices"]]
                        project.append_discourse("main", payload)
                    result = project.projection("main")
                    self.assertEqual(result["hashes"], project.projection("main")["hashes"])
                    for expectation in case["expect"]:
                        actual = result
                        for part in expectation["path"].split("."):
                            actual = actual[int(part)] if isinstance(actual, list) else actual[part]
                        if "equals" in expectation:
                            self.assertEqual(actual, expectation["equals"])
                        if "length" in expectation:
                            self.assertEqual(len(actual), expectation["length"])
                        if "contains" in expectation:
                            self.assertIn(expectation["contains"], actual)
                        if "excludes" in expectation:
                            self.assertNotIn(expectation["excludes"], actual)
                finally:
                    project.close()


class DiscourseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project.create(Path(self.temp.name) / "sample", "Sample", sample=True)
        self.branches = {meta.get("condition"): branch for branch, meta in self.project.meta["branches"].items()
                         if meta.get("condition")}

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_ac15_packet_repeat_is_identical_and_filtered(self):
        branch = self.branches["C3"]
        args = (self.project.fixture, self.project.contract, self.project.events(branch, "story"),
                self.project.events(branch, "discourse"))
        first, second = build_packet(*args), build_packet(*args)
        self.assertEqual(first["packet_hash"], second["packet_hash"])
        self.assertEqual(first["packet_hash"], digest({k: v for k, v in first.items() if k != "packet_hash"}))
        self.assertNotIn("Len writes a note", first["licensed_claims"])
        self.assertEqual(first["acts"][0]["reader_before"]["revealed"], [])
        self.assertTrue(first["acts"][0]["reader_after"]["cued"])

    def test_ac16_private_motive_rejected(self):
        packet = self._packet()
        findings = check_realization("Len knew he wanted to leave Mara.", packet)
        self.assertIn("E-PROSE-PRIVATE", {item["code"] for item in findings})

    def test_ac17_open_question_resolution_rejected(self):
        findings = check_realization("Len's acts were care, not avoidance.", self._packet())
        self.assertIn("E-PROSE-RESOLUTION", {item["code"] for item in findings})

    def test_ac18_metaphor_is_not_fact(self):
        packet = self._packet()
        _, findings = check_candidate("The bowl was a small moon.", packet,
                                      [{"claim_type": "metaphor", "claims": ["The moon is in the kitchen"]}])
        self.assertNotIn("E-PROSE-CLAIM", {item["code"] for item in findings})

    def test_ac33_voice_phrase_and_length(self):
        packet = self._packet()
        packet["word_bounds"] = {"min_words": 0, "max_words": 1100}
        packet["voice"] = {"forbidden_phrases": ["in conclusion"], "sentence_max_words": 7}
        findings = check_realization("In conclusion, Mara saw the chair and wanted it to stop moving.", packet)
        self.assertEqual({"E-VOICE-PHRASE", "E-VOICE-LENGTH"} & {f["code"] for f in findings},
                         {"E-VOICE-PHRASE", "E-VOICE-LENGTH"})

    def test_ungrounded_claim_cause_and_early_reveal(self):
        packet = self._packet()
        packet["word_bounds"] = {"min_words": 0, "max_words": 1100}
        _, findings = check_candidate("Mara met Owen because Len had arranged it.\n\nThe note lists deferred departures.",
            packet, [{"claims": ["Owen visited"], "grounding_source_ids": []}, {}])
        self.assertTrue({"E-PROSE-CLAIM", "E-PROSE-ENTITY", "E-PROSE-CAUSAL", "E-PROSE-EARLY"}
                        <= {item["code"] for item in findings})

    def test_failed_candidate_kept_without_canon_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.create(Path(folder) / "plain", "Plain")
            try:
                story = project.append_story("main", {"title": "A chair moved", "observed_by": ["actor_a"]})
                project.append_discourse("main", {"title": "Telling", "focalizer": "actor_a",
                    "story_refs": [story["event_id"]], "text": "Actor B knew every secret."})
                path = project.root / "branches" / "main" / "story.ndjson"
                before = path.read_bytes()
                run = project.run("main")
                self.assertEqual(run["status"], "failed")
                self.assertFalse(run["candidate"]["accepted"])
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(project.list_runs()[0]["candidate"]["packet_hash"], run["packet_hash"])
            finally:
                project.close()

    def _packet(self):
        branch = self.branches["C3"]
        packet = build_packet(self.project.fixture, self.project.contract,
                              self.project.events(branch, "story"), self.project.events(branch, "discourse"))
        packet["word_bounds"] = {"min_words": 0, "max_words": 1100}
        return packet
