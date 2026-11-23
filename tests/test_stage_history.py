import json
from pathlib import Path
import tempfile
import unittest

from stage_history import history_path, read_history, record_history


class HistoryTests(unittest.TestCase):
    def test_history_persists_and_keeps_accounts_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            record_history(repo, "one@example.com", 2, "started")
            record_history(repo, "one@example.com", 2, "checkout_requested")
            entries = read_history(repo, "ONE@example.com")
            self.assertEqual([entry["status"] for entry in entries],
                             ["started", "checkout_requested"])
            self.assertEqual(read_history(repo, "two@example.com"), [])
            self.assertNotIn("one@example.com", str(history_path(repo, "one@example.com")))
            self.assertNotIn("one@example.com", json.dumps(entries))

