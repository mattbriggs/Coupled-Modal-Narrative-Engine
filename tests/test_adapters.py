"""Behavioral contract for recorded model calls and the canon boundary."""

import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cmne.adapters import CommandAdapter, ModelGateway
from cmne.core import CmneError, template_realize
from cmne.cli import main
from cmne.project import Project
from cmne_sidecar.server import Dispatcher, handle


MANIFEST = {"model_name": "offline-test", "model_version": "1", "prompt_version": "test-v1",
            "seed": 13, "decoding": {"temperature_bp": 0, "max_output_tokens": 512}}
BUDGET = {"max_calls": 5, "max_tokens": 1000}
USAGE = {"input_tokens": 2, "output_tokens": 3, "cost_micros": 0}


class FakeProse:
    def __init__(self):
        self.calls = 0

    def realize(self, request):
        self.calls += 1
        return {"output": template_realize(request["payload"]["packet"])
                if "packet" in request["payload"] else f"candidate {request['payload']['index']}",
                "usage": USAGE}


class FakeProposal:
    def __init__(self):
        self.request = None

    def propose(self, request):
        self.request = request
        return {"output": {"candidates": [{"payload": {"title": "Suggested action",
                                                        "world_facts": ["suggested fact"]},
                                            "rationale": "A possible next step",
                                            "expected_effects": ["adds a world fact"]}]},
                "usage": USAGE}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project.create(Path(self.temp.name) / "scene", "Adapter test")
        self.project.append_story("main", {"title": "Opening", "world_facts": ["the room is quiet"]})
        event_id = self.project.events("main", "story")[0]["event_id"]
        self.project.append_discourse("main", {"title": "Tell opening", "story_refs": [event_id],
                                                 "text": "The room was quiet."})

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_record_and_socket_blocked_replay_are_byte_identical_and_leave_canon_alone(self):
        story_path = self.project._branch_path("main", "story")
        discourse_path = self.project._branch_path("main", "discourse")
        original = (story_path.read_bytes(), discourse_path.read_bytes())
        fake = FakeProse()
        recorded = self.project.run("main", adapter=fake, adapter_mode="record",
                                    adapter_manifest=MANIFEST, adapter_budget=BUDGET,
                                    allow_data_transfer=True)
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            replayed = self.project.run("main", adapter_mode="replay",
                                        adapter_manifest=MANIFEST, adapter_budget=BUDGET)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(recorded["prose"].encode(), replayed["prose"].encode())
        self.assertEqual(recorded["adapter_request_hash"], replayed["adapter_request_hash"])
        self.assertEqual((story_path.read_bytes(), discourse_path.read_bytes()), original)
        self.assertEqual(recorded["adapter_spend"], {"calls": 1, "tokens": 5, "cost_micros": 0})
        self.assertEqual(recorded["reproducibility"]["model_manifest"], MANIFEST)
        self.assertEqual(recorded["reproducibility"]["fixture"], self.project.fixture)

    def test_missing_and_tampered_cassettes_fail_without_model_call(self):
        with self.assertRaises(CmneError) as missing:
            self.project.run("main", adapter_mode="replay", adapter_manifest=MANIFEST,
                             adapter_budget=BUDGET)
        self.assertEqual(missing.exception.code, "E-CASSETTE-001")
        recorded = self.project.run("main", adapter=FakeProse(), adapter_mode="record",
                                    adapter_manifest=MANIFEST, adapter_budget=BUDGET,
                                    allow_data_transfer=True)
        path = self.project.root / "cassettes" / f"{recorded['adapter_request_hash']}.json"
        cassette = json.loads(path.read_text())
        cassette["response"]["output"] = "Tampered"
        path.write_text(json.dumps(cassette))
        with self.assertRaises(CmneError) as tampered:
            self.project.run("main", adapter_mode="replay", adapter_manifest=MANIFEST,
                             adapter_budget=BUDGET)
        self.assertEqual(tampered.exception.code, "E-CASSETTE-001")

    def test_sixth_call_is_blocked_with_spend_and_no_adapter_invocation(self):
        gateway = ModelGateway(self.project.root, MANIFEST, "record", BUDGET, True)
        fake = FakeProse()
        for index in range(5):
            gateway.call("prose", {"index": index}, fake)
        with self.assertRaises(CmneError) as exhausted:
            gateway.call("prose", {"index": 5}, fake)
        self.assertEqual(exhausted.exception.code, "E-BUDGET-001")
        self.assertEqual(fake.calls, 5)
        self.assertEqual(gateway.spend, {"calls": 5, "tokens": 25, "cost_micros": 0})
        self.assertIn("'calls': 5", str(exhausted.exception))

        run_gateway = ModelGateway(self.project.root, MANIFEST, "record", BUDGET, True)
        run_adapter = FakeProse()
        for _ in range(5):
            self.project.run("main", adapter=run_adapter, adapter_mode="record",
                             adapter_manifest=MANIFEST, adapter_gateway=run_gateway)
        with self.assertRaises(CmneError) as stopped:
            self.project.run("main", adapter=run_adapter, adapter_mode="record",
                             adapter_manifest=MANIFEST, adapter_gateway=run_gateway)
        self.assertEqual(stopped.exception.code, "E-BUDGET-001")
        self.assertEqual(run_adapter.calls, 5)
        self.assertEqual(len(self.project.list_runs()), 5)

    def test_no_transfer_opt_in_or_unavailable_adapter_uses_template_without_leaking_error(self):
        fake = FakeProse()
        private = self.project.run("main", adapter=fake, adapter_mode="record",
                                   adapter_manifest=MANIFEST, adapter_budget=BUDGET)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(private["adapter_failure"]["code"], "E-PRIVACY-001")
        self.assertEqual(private["realizer"], "deterministic-template-v2")

        class Broken:
            def realize(self, _request):
                raise RuntimeError("credential=TOP_SECRET_VALUE")

        fallback = self.project.run("main", adapter=Broken(), adapter_mode="record",
                                    adapter_manifest=MANIFEST, adapter_budget=BUDGET,
                                    allow_data_transfer=True)
        self.assertEqual(fallback["adapter_failure"]["code"], "E-ADAPTER-001")
        self.assertNotIn("TOP_SECRET_VALUE", json.dumps(fallback))
        self.assertEqual(fallback["prose"], template_realize({"acts": [{"text": "The room was quiet."}]}))

    def test_proposals_are_diagnostic_until_user_accepts_validated_command(self):
        before = self.project._branch_path("main", "story").read_bytes()
        fake = FakeProposal()
        result = self.project.propose("main", fake, MANIFEST, BUDGET,
                                      allow_data_transfer=True)
        self.assertEqual(fake.request["payload"]["allowed_command_types"], ["story"])
        self.assertEqual(fake.request["payload"]["contract"], self.project.contract)
        self.assertIn("projections", fake.request["payload"])
        self.assertIn("entities", fake.request["payload"])
        self.assertEqual(self.project._branch_path("main", "story").read_bytes(), before)
        proposal = result["proposals"][0]
        self.assertNotIn("rationale", proposal["payload"])
        event = self.project.accept_proposal("main", proposal["proposal_id"])
        self.assertEqual(event["payload"]["source_kind"], "generated")
        self.assertEqual(self.project.trace("main", event["event_id"])["proposal_id"], proposal["proposal_id"])
        self.assertEqual(self.project.trace("main", event["event_id"])["accepting_validator"],
                         "cmne-command-validator-v2")
        with self.assertRaises(CmneError) as stale:
            self.project.accept_proposal("main", proposal["proposal_id"])
        self.assertEqual(stale.exception.code, "E-APPEND-001")

    def test_invalid_later_proposal_leaves_no_partial_diagnostic_set(self):
        class MixedProposal:
            def propose(self, _request):
                return {"output": {"candidates": [
                    {"payload": {"title": "Valid suggestion"}, "rationale": "Maybe",
                     "expected_effects": []},
                    {"payload": {"title": "Malformed suggestion"}, "rationale": "Maybe"}
                ]}, "usage": USAGE}

        before = self.project._branch_path("main", "story").read_bytes()
        with self.assertRaises(CmneError) as invalid:
            self.project.propose("main", MixedProposal(), MANIFEST, BUDGET,
                                 allow_data_transfer=True)
        self.assertEqual(invalid.exception.code, "E-ADAPTER-001")
        self.assertEqual(list((self.project.root / "proposals").glob("*.json")), [])
        self.assertEqual(self.project._branch_path("main", "story").read_bytes(), before)

    def test_command_adapter_uses_json_protocol_and_discards_vendor_stderr(self):
        program = Path(self.temp.name) / "fake_vendor.py"
        program.write_text("import json, sys\n"
                           "request = json.loads(sys.stdin.readline())\n"
                           "sys.stderr.write('credential=TOP_SECRET_VALUE')\n"
                           "print(json.dumps({'output': request['payload']['phrase'], "
                           "'usage': {'input_tokens': 1, 'output_tokens': 1, 'cost_micros': 0}}))\n")
        gateway = ModelGateway(self.project.root, MANIFEST, "record", BUDGET, True)
        result = gateway.call("prose", {"phrase": "A plain sentence."},
                              CommandAdapter([sys.executable, str(program)]))
        self.assertEqual(result["output"], "A plain sentence.")
        self.assertNotIn("TOP_SECRET_VALUE", (self.project.root / "cassettes" /
                                          f"{result['request_hash']}.json").read_text())

    def test_credentials_and_changed_response_cannot_enter_cassette(self):
        gateway = ModelGateway(self.project.root, MANIFEST, "record", BUDGET, True)
        fake = FakeProse()
        with self.assertRaises(CmneError) as field:
            gateway.call("prose", {"api_key": "TOP_SECRET_VALUE", "index": 0}, fake)
        self.assertEqual(field.exception.code, "E-PRIVACY-001")
        self.assertEqual(fake.calls, 0)
        with patch.dict(os.environ, {"CMNE_MODEL_API_KEY": "TOP_SECRET_VALUE"}), \
                self.assertRaises(CmneError) as value:
            gateway.call("prose", {"phrase": "TOP_SECRET_VALUE"}, fake)
        self.assertEqual(value.exception.code, "E-PRIVACY-001")
        original = gateway.call("prose", {"index": 1}, fake)

        class Changed:
            def realize(self, _request):
                return {"output": "A different answer.", "usage": USAGE}

        with self.assertRaises(CmneError) as collision:
            gateway.call("prose", {"index": 1}, Changed())
        self.assertEqual(collision.exception.code, "E-CASSETTE-001")
        cassette = json.loads((self.project.root / "cassettes" /
                               f"{original['request_hash']}.json").read_text())
        self.assertEqual(cassette["response"]["output"], "candidate 1")

    def test_cli_and_rpc_replay_the_same_saved_response(self):
        recorded = self.project.run("main", adapter=FakeProse(), adapter_mode="record",
                                    adapter_manifest=MANIFEST, adapter_budget=BUDGET,
                                    allow_data_transfer=True)
        root = str(self.project.root)
        self.project.close()
        manifest_path = Path(self.temp.name) / "manifest.json"
        manifest_path.write_text(json.dumps(MANIFEST))
        stdout = StringIO()
        with redirect_stdout(stdout), patch.object(socket, "socket",
                                                 side_effect=AssertionError("network used")):
            code = main(["--json", "run", root, "--adapter-mode", "replay",
                         "--model-manifest", str(manifest_path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["prose"], recorded["prose"])
        dispatcher = Dispatcher()
        handle(dispatcher, {"jsonrpc": "2.0", "id": 1, "method": "app.hello"})
        handle(dispatcher, {"jsonrpc": "2.0", "id": 2, "method": "project.open",
                            "params": {"path": root}})
        try:
            with patch.object(socket, "socket", side_effect=AssertionError("network used")):
                result = handle(dispatcher, {"jsonrpc": "2.0", "id": 3, "method": "run.start",
                    "params": {"adapter_mode": "replay", "model_manifest": MANIFEST}})
            self.assertEqual(result["result"]["prose"], recorded["prose"])
        finally:
            dispatcher.project.close()


if __name__ == "__main__":
    unittest.main()
