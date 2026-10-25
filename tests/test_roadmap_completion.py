"""Reject premature roadmap completion; no GitHub calls or trading execution."""
import copy
import json
from pathlib import Path
import unittest
from scripts.check_roadmap import validate

ROOT = Path(__file__).resolve().parents[1]


class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "research/roadmap_evidence.json").read_text())

    def attempted_completion(self):
        task = self.data["tasks"][1]
        task.update(complete=True, assessment="completed")
        return task

    def test_audited_snapshot_is_consistent(self):
        self.assertEqual(validate(self.data), [])

    def test_merge_and_ci_cannot_substitute_for_human_confirmation(self):
        self.attempted_completion()
        self.assertTrue(any("human confirmation" in e for e in validate(self.data)))

    def test_human_metadata_cannot_substitute_for_merge_ci_or_task_tests(self):
        task = self.attempted_completion()
        task["human_review"] = {"confirmed": True, "login": "fixture-reviewer",
                               "url": "https://github.com/iikaitlynii/trading-bot/pull/7#fixture"}
        # This tests structural evidence only, not the authenticity of this fixture.
        baseline = copy.deepcopy(self.data)
        for field, value, expected in [("merged", False, "merged PR"),
                                       ("ci_conclusion", "failure", "successful CI")]:
            with self.subTest(field=field):
                data = copy.deepcopy(baseline)
                data["prs"][0][field] = value
                self.assertTrue(any(expected in e for e in validate(data)))
        task["tests"] = []
        self.assertTrue(any("task verification" in e for e in validate(self.data)))

    def test_task_inventory_cannot_silently_drop_or_duplicate_a_phase_item(self):
        self.data["tasks"].pop()
        self.assertTrue(any("47 unique" in e for e in validate(self.data)))

    def test_test_path_must_exist_inside_repository(self):
        self.data["tasks"][1]["tests"] = ["../nonexistent.py"]
        self.assertTrue(any("unsafe test path" in e for e in validate(self.data)))


if __name__ == "__main__":
    unittest.main()
