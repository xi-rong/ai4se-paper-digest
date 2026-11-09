import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from paper_digest.cli import main
from paper_digest.operations import check_config, status_summary
from paper_digest.storage import LocalStore, empty


class OperationalChecks(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_config_check_distinguishes_schedule_intent_and_cloud_storage(self):
        result = check_config(self.config, "git")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(any("scheduler separately" in n for n in result["notes"]))
        bad = copy.deepcopy(self.config)
        bad["timezone"] = "Not/A_Timezone"
        bad["mail"]["api_url"] = "https://wrong.example/"
        bad["storage"]["branch"] = "main"
        self.assertEqual(len(check_config(bad, "git")["errors"]), 3)

    def test_status_redacts_raw_candidates_and_keeps_coverage(self):
        state = empty()
        state["runs"].append({"type": "collect", "status": "partial", "at": "2026-11-09T00:00:00+00:00",
                              "coverage": [{"source": "arxiv-api", "status": "failed", "http_status": 429}],
                              "discovery_candidates": [{"secret": "RAW_CANDIDATE_SHOULD_NOT_APPEAR"}]})
        state["outbox"]["old"] = {"status": "superseded", "html": "PRIVATE_MESSAGE"}
        output = json.dumps(status_summary(state))
        self.assertIn('429', output)
        self.assertNotIn('RAW_CANDIDATE_SHOULD_NOT_APPEAR', output)
        self.assertNotIn('PRIVATE_MESSAGE', output)

    def test_check_config_and_invalid_collect_do_not_write_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            store = LocalStore(state_path)
            store.save(empty(), None)
            before = state_path.read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--state", str(state_path), "check-config"]), 0)
                with self.assertRaises(ValueError):
                    main(["--state", str(state_path), "collect", "--days", "0"])
            self.assertEqual(before, state_path.read_bytes())

    def test_pending_omits_superseded_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state = empty()
            state["outbox"] = {"older": {"status": "superseded"}, "failed": {"status": "retry"}}
            LocalStore(state_path).save(state, None)
            output = io.StringIO()
            with redirect_stdout(output):
                main(["--state", str(state_path), "pending"])
            self.assertEqual([m["id"] for m in json.loads(output.getvalue())["pending"]], ["failed"])


if __name__ == "__main__":
    unittest.main()
