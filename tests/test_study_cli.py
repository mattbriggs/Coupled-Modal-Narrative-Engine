"""Blinded study, response, report, and CLI acceptance checks."""

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cmne.cli import main
from cmne.core import CmneError
from cmne.project import Project
from cmne.study import analyze_responses
from cmne_sidecar.server import Dispatcher, handle


PLAN = {"hypotheses": ["C3 yields more cited reinterpretation than C0"],
        "primary_measures": ["retrospective_citation", "distinct_details", "preparedness",
                             "unresolved_meaningful"],
        "secondary_measures": ["motif_recurrence"], "target_sample_size": 8,
        "sample_size_rationale": "Pilot checks the protocol before recruiting a larger sample.",
        "agreement_metric": "percent_agreement", "exclusion_rules": ["Incomplete passages"],
        "session_limit_minutes": 20}


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project.create(Path(self.temp.name) / "sample", "Sample", sample=True)

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def _export(self):
        self.project.save_analysis_plan(PLAN)
        runs = self.project.generate_matched_realizations()
        exported = self.project.export_evaluation_set(seed=42)
        manifest = json.loads((Path(exported["public_path"]) / "manifest.json").read_text())
        key = json.loads(Path(exported["key_path"]).read_text())["passages"]
        return runs, exported, manifest, key

    def _response(self, passage, text, evaluator="reader_01", cites=True,
                  preparedness=3, resolution="meaningful"):
        span = text[:10]
        return {"evaluator_id": evaluator, "passage_id": passage["passage_id"],
                "text_version": passage["text_hash"], "paired_ranking": "not_shown",
                "free_response": "A detail changes meaning." if cites else "No earlier detail changed.",
                "cited_spans": [{"start": 0, "end": len(span), "earlier_detail": span}] if cites else [],
                "confidence_bp": 7500, "no_discernible_difference": not cites,
                "preparedness_rating": preparedness, "resolution_class": resolution}

    def test_malformed_study_inputs_return_field_errors(self):
        from cmne.study import validate_plan, validate_responses
        with self.assertRaises(CmneError) as plan_error:
            validate_plan({**PLAN, "primary_measures": [["nested"]]})
        self.assertEqual(plan_error.exception.field_path, "primary_measures")
        _, _, manifest, key = self._export()
        passage = manifest["passages"][0]
        bad = self._response(passage, "This passage is long enough")
        bad["passage_id"] = []
        with self.assertRaises(CmneError) as response_error:
            validate_responses([bad], key, {passage["passage_id"]: {**passage, "text": "This passage is long enough"}})
        self.assertEqual(response_error.exception.field_path, "responses.0.passage_id")
        study_id = self.project.export_evaluation_set(seed=43)["study_id"]
        with self.assertRaises(CmneError) as document_error:
            self.project.import_responses(study_id, {"responses": "not a list"})
        self.assertEqual(document_error.exception.field_path, "responses")

    def test_ac34_export_requires_plan_and_amendment_cites_prior_hash(self):
        with self.assertRaises(CmneError) as error:
            self.project.export_evaluation_set()
        self.assertEqual(error.exception.code, "E-PLAN-001")
        initial = self.project.save_analysis_plan(PLAN)
        self.assertTrue(initial["created_at"])
        amendment = self.project.save_analysis_plan({**PLAN, "target_sample_size": 12})
        self.assertEqual(amendment["amends_plan_hash"], initial["plan"]["content_hash"])
        self.assertNotEqual(amendment["plan"]["content_hash"], initial["plan"]["content_hash"])

    def test_ac25_blinded_public_set_has_no_condition_labels_or_key(self):
        runs, exported, manifest, key = self._export()
        public = Path(exported["public_path"])
        self.assertEqual(len(runs), 12)
        self.assertEqual(len(manifest["passages"]), 12)
        self.assertEqual(len({run["prose"] for run in runs}), 12)
        self.assertEqual(set(item["condition"] for item in key.values()), {"C0", "C1", "C2", "C3"})
        self.assertFalse((public / "key.json").exists())
        self.assertNotIn("condition", (public / "manifest.json").read_text().lower())
        self.assertIn("no discernible difference", (public / "protocol.html").read_text().lower())
        for passage in manifest["passages"]:
            self.assertNotIn("C3", (public / passage["text_file"]).read_text())
            self.assertIn("<main>", (public / passage["html_file"]).read_text())

    def test_response_batch_is_atomic_and_field_specific(self):
        _, exported, manifest, _ = self._export()
        first = manifest["passages"][0]
        text = (Path(exported["public_path"]) / first["text_file"]).read_text()
        good = self._response(first, text)
        bad = {**good, "evaluator_id": "reader_02", "confidence_bp": 10001}
        with self.assertRaises(CmneError) as error:
            self.project.import_responses(exported["study_id"], {"responses": [good, bad]})
        self.assertEqual(error.exception.code, "E-RESPONSE-001")
        self.assertEqual(error.exception.field_path, "responses.1.confidence_bp")
        self.assertFalse((self.project.root / "study" / "responses" /
                          f"{exported['study_id']}.json").exists())
        result = self.project.import_responses(exported["study_id"], {"responses": [good]})
        self.assertEqual(result["accepted"], 1)

    def test_ac40_report_handles_null_and_contrary_results_with_intervals(self):
        runs, exported, manifest, key = self._export()
        empty = self.project.analysis_report(exported["study_id"])
        self.assertTrue(empty["null_result"])
        self.assertTrue(empty["null_alternatives"])
        c0 = next(item for item in manifest["passages"] if key[item["passage_id"]]["condition"] == "C0")
        c3 = next(item for item in manifest["passages"] if key[item["passage_id"]]["condition"] == "C3")
        public = Path(exported["public_path"])
        rows = [self._response(c0, (public / c0["text_file"]).read_text(),
                               preparedness=5, resolution="meaningful"),
                self._response(c0, (public / c0["text_file"]).read_text(),
                               evaluator="reader_02", preparedness=4, resolution="meaningful"),
                self._response(c3, (public / c3["text_file"]).read_text(),
                               cites=False, preparedness=1, resolution="confusing"),
                self._response(c3, (public / c3["text_file"]).read_text(),
                               evaluator="reader_02", cites=False,
                               preparedness=2, resolution="confusing")]
        self.project.import_responses(exported["study_id"], {"responses": rows})
        report = self.project.analysis_report(exported["study_id"])
        self.assertEqual(report["responses"], 4)
        self.assertTrue(report["contrary_results"])
        self.assertEqual(set(report["effect_sizes"]), set(PLAN["primary_measures"]))
        self.assertTrue(all(item["confidence_interval_95"] is not None
                            for item in report["effect_sizes"].values()))
        self.assertEqual(report["candidate_counts"]["C3"]["generated"], 3)
        self.assertEqual(report["agreement"]["value"], 1.0)

    def test_agreement_counts_all_rater_pairs_and_does_not_fake_two_rater_kappa(self):
        rows = [{"passage_id": "p", "condition": "C0", "resolution_class": label,
                 "cited_spans": [], "preparedness_rating": 3}
                for label in ("meaningful", "meaningful", "confusing")]
        percent = analyze_responses(rows, {**PLAN, "content_hash": "plan"}, [])
        self.assertEqual(percent["agreement"]["paired_items"], 3)
        self.assertAlmostEqual(percent["agreement"]["value"], 1/3)
        kappa = analyze_responses(rows, {**PLAN, "content_hash": "plan",
                                         "agreement_metric": "cohen_kappa"}, [])
        self.assertIsNone(kappa["agreement"]["value"])
        self.assertIn("two ratings", kappa["agreement"]["not_computable_reason"])

    def test_cli_json_exit_codes_and_study_commands(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(["--json", "export-evaluation", str(self.project.root)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stream.getvalue())["error"]["cmne_code"], "E-LOCK-001")
        self.project.close()
        plan_path = Path(self.temp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--json", "analysis-plan", str(self.project.root), str(plan_path)]), 0)
        self.assertIn("content_hash", json.loads(output.getvalue())["plan"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--json", "study-generate", str(self.project.root)]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["runs"]), 12)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--json", "export-evaluation", str(self.project.root)]), 0)
        study_id = json.loads(output.getvalue())["study_id"]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--json", "study-realize-ablations", str(self.project.root),
                                   "--branch", self._c3_branch()]), 0)
        self.assertEqual(len(json.loads(output.getvalue())), 7)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--json", "decision-packet", str(self.project.root), study_id]), 0)
        self.assertEqual(json.loads(output.getvalue())["decision"], "pending_human_review")

    def _c3_branch(self):
        return next(b for b, meta in self.project.meta["branches"].items()
                    if meta.get("condition") == "C3")

    def test_sidecar_study_round_trip(self):
        self.project.close()
        dispatcher = Dispatcher()
        def call(method, params=None):
            return handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
        self.assertIn("result", call("app.hello"))
        self.assertIn("result", call("project.open", {"path": str(self.project.root)}))
        self.assertIn("result", call("study.plan.save", {"plan": PLAN}))
        self.assertEqual(len(call("study.generate")["result"]["runs"]), 12)
        exported = call("study.export", {"seed": 9})["result"]
        self.assertEqual(exported["passage_count"], 12)
        self.assertTrue(call("study.report", {"study_id": exported["study_id"]})["result"]["null_result"])
        dispatcher.project.close()

    def test_layer_a_b_and_seven_ablation_descriptions_leave_canon_unchanged(self):
        branch = next(b for b, meta in self.project.meta["branches"].items()
                      if meta.get("condition") == "C3")
        path = self.project.root / "branches" / branch / "story.ndjson"
        before = path.read_bytes()
        metrics = self.project.study_metrics(branch)
        self.assertTrue(metrics["layer_a"]["accepted"])
        self.assertEqual(metrics["layer_b"]["label"], "descriptive structural measures")
        self.assertEqual(metrics["layer_b"]["reinterpretation_count"], 2)
        self.assertEqual(metrics["layer_b"]["motif_recurrence"]["chair"], 3)
        ablations = self.project.study_ablations(branch)
        self.assertEqual(len(ablations), 7)
        self.assertEqual(len({entry["changed_payload_hash"] for entry in ablations}), 7)
        self.assertTrue(all(entry["analysis_only"] for entry in ablations))
        self.assertEqual(path.read_bytes(), before)

    def test_realized_ablations_are_distinct_audited_and_do_not_change_canon(self):
        branch = next(b for b, meta in self.project.meta["branches"].items()
                      if meta.get("condition") == "C3")
        path = self.project.root / "branches" / branch / "story.ndjson"
        before = path.read_bytes()
        results = self.project.realize_ablations(branch)
        self.assertEqual(len(results), 7)
        self.assertEqual(len({entry["text_hash"] for entry in results}), 7)
        self.assertTrue(all(entry["text_changed"] and entry["packet_hash"]
                            and entry["baseline_text_hash"] for entry in results))
        self.assertTrue(any(entry["status"] == "rejected" and entry["findings"]
                            for entry in results))
        self.assertEqual(path.read_bytes(), before)
        for entry in results:
            saved = self.project.root / "study" / "ablations" / branch / f"{entry['name']}.json"
            self.assertEqual(json.loads(saved.read_text()), entry)

    def test_decision_packet_preserves_null_result_and_requires_human_decision(self):
        _, exported, _, _ = self._export()
        packet = self.project.decision_packet(exported["study_id"])
        self.assertEqual(packet["decision"], "pending_human_review")
        self.assertTrue(packet["human_review_required"])
        self.assertTrue(packet["null_result"])
        self.assertEqual(packet["response_count"], 0)
        self.assertEqual(len(packet["ablations"]), 7)
        self.assertEqual(set(packet["structural"]), {"C0", "C1", "C2", "C3"})
        saved = self.project.root / "study" / "decision-packets" / f"{exported['study_id']}.json"
        self.assertEqual(json.loads(saved.read_text()), packet)
        self.assertEqual(self.project.decision_packet(exported["study_id"]), packet)

    def test_async_run_progress_cancel_and_committed_read(self):
        self.project.close()
        dispatcher = Dispatcher()
        def call(method, params=None):
            return handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
        call("app.hello")
        call("project.open", {"path": str(self.project.root)})
        entered, release = threading.Event(), threading.Event()
        real_run = dispatcher.project.run
        def held_run(*args, **kwargs):
            entered.set()
            release.wait(timeout=3)
            return real_run(*args, **kwargs)
        with patch.object(dispatcher.project, "run", side_effect=held_run):
            started = call("run.start", {"async": True, "conditions": ["C0", "C1", "C2", "C3"]})["result"]
            self.assertTrue(entered.wait(timeout=2))
            status = call("run.status", {"job_id": started["job_id"]})["result"]
            self.assertEqual(status["status"], "running")
            branch = next(b for b, m in dispatcher.project.meta["branches"].items()
                          if m.get("condition") == "C0")
            self.assertEqual(len(call("events.read", {"branch_id": branch})["result"]), 10)
            self.assertEqual(call("study.plan.save", {"plan": PLAN})["error"]["data"]["cmne_code"],
                             "E-RUN-001")
            self.assertIn("result", call("draft.create", {"branch_id": branch}))
            self.assertTrue(call("run.cancel")["result"]["cancelled"])
            release.set()
            dispatcher._run_thread.join(timeout=3)
        final = call("run.status", {"job_id": started["job_id"]})["result"]
        self.assertEqual(final["status"], "cancelled")
        self.assertEqual(final["completed"], 1)
        self.assertEqual(status["completed"], 0)
        self.assertEqual(status["runs"], [])
        self.assertEqual(len(final["runs"]), 1)
        dispatcher.project.close()
