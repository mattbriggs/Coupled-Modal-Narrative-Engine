"""Seeded state properties across varied event histories and branch forks."""

import random
import tempfile
import unittest
from pathlib import Path

from cmne.core import digest
from cmne.project import Project


class StateProperties(unittest.TestCase):
    def test_replay_append_branch_provenance_and_snapshot_properties(self):
        for seed in range(8):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as folder:
                project = Project.create(Path(folder) / "scene", "Properties")
                try:
                    randomizer = random.Random(seed)
                    path = project._branch_path("main", "story")
                    previous = b""
                    for index in range(4):
                        observer = randomizer.choice(["actor_a", "actor_b"])
                        claim = f"fact {seed}-{index}"
                        event = project.append_story("main", {"title": f"Beat {index}",
                            "observed_by": [observer], "world_facts": [claim]})
                        current = path.read_bytes()
                        self.assertTrue(current.startswith(previous))
                        self.assertEqual(event["sequence"], index + 1)
                        previous = current
                        actor = project.projection("main")["projections"][
                            "actor_a" if observer == "actor_a" else "actor_b"]
                        records = [p for p in actor["provenance"] if p.get("claim") == claim]
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]["source_event_ids"], [event["event_id"]])
                        self.assertEqual(records[0]["integrity_hash"],
                                         digest({k: v for k, v in records[0].items()
                                                 if k != "integrity_hash"}))
                    before = project.projection("main")["hashes"]
                    self.assertEqual(project.snapshot_status("main")["valid_before_rebuild"], True)
                    fork = project.fork("main", 2, "Alternative")
                    project.append_story(fork["branch_id"], {"title": "Different ending",
                                                          "world_facts": ["new fact"]})
                    self.assertEqual(project.projection("main")["hashes"], before)
                    self.assertNotEqual(project.projection(fork["branch_id"])["hashes"]["environment"],
                                        before["environment"])
                    forked = project.projection(fork["branch_id"])["projections"]
                    forked["environment"]["facts"].append("mutated local copy")
                    self.assertNotIn("mutated local copy", project.projection(fork["branch_id"])
                                     ["projections"]["environment"]["facts"])
                    reader = Project(project.root, read_only=True)
                    try:
                        self.assertEqual(reader.projection("main")["hashes"], before)
                    finally:
                        reader.close()
                finally:
                    project.close()

    def test_concept_versions_preserve_each_superseded_model(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.create(Path(folder) / "scene", "Versions")
            try:
                for index in range(1, 5):
                    project.append_story("main", {"title": f"Revision {index}",
                        "conceptual_revision": {"observer_id": "actor_a",
                            "concepts": [f"term-{index}"],
                            "migration_map": {f"term-{index - 1}": [f"term-{index}"]}}})
                    model = project.projection("main")["projections"]["actor_a"]["conceptual_model"]
                    self.assertEqual(model["version"], index + 1)
                    for prior in range(index, 0, -1):
                        self.assertEqual(model["concepts"], [f"term-{prior}"])
                        model = model["supersedes"]
                    self.assertEqual(model["version"], 1)
            finally:
                project.close()
