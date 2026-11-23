"""Local DB tests: only valid, matching-account Google AI Pro tokens qualify."""
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("purchase_token_checks", ROOT / "ultra0.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


class PurchaseTokenTests(unittest.TestCase):
    def test_android_database_copy_is_removed_after_success(self):
        with tempfile.TemporaryDirectory() as home:
            source = Path(home) / "test.db"
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE ownership (doc_id text, account text, "
                           "subs_valid_until_time integer, inapp_purchase_data text)")
                db.execute("INSERT INTO ownership VALUES (?, ?, ?, ?)",
                           ("subs_variant", "test@example.com",
                            int(time.time() * 1000) + 60000,
                            json.dumps({"purchaseToken": "mock-secret"})))
            calls = []
            def fake_sh(*args, **kwargs):
                calls.append(args)
                if args[0] == "pull":
                    shutil.copyfile(source, args[2])
                return ""
            with patch.object(script, "sh", side_effect=fake_sh), \
                 patch.object(script, "note") as note:
                self.assertEqual(
                    script.read_purchase_token("subs_variant", "test@example.com"),
                    "mock-secret")
            remote = [a[1] for a in calls if a[0] == "shell" and "rm -f" in a[1]]
            self.assertEqual(len(remote), 1)
            self.assertIn("/data/local/tmp/lib_read_", remote[0])
            self.assertTrue(any(a[0] == "pull" for a in calls))
            self.assertNotIn("mock-secret", " ".join(str(c) for c in note.call_args_list))
            self.assertNotIn("test@example.com", " ".join(str(c) for c in note.call_args_list))

    def test_android_database_copy_is_removed_when_pull_fails(self):
        calls = []
        def fake_sh(*args, **kwargs):
            calls.append(args)
            if args[0] == "pull":
                raise OSError("ADB pull failed")
            return ""
        with patch.object(script, "sh", side_effect=fake_sh):
            self.assertEqual(script.read_purchase_token("subs_variant", "test@example.com"), "")
        self.assertTrue(any(a[0] == "shell" and "rm -f" in a[1] for a in calls))

    def test_local_copy_is_removed_when_sql_query_fails(self):
        with tempfile.TemporaryDirectory() as home:
            source = Path(home) / "bad.db"
            source.write_bytes(b"corrupt database")
            targets = []
            commands = []
            def fake_sh(*args, **kwargs):
                commands.append(args)
                if args[0] == "pull":
                    targets.append(Path(args[2]))
                    shutil.copyfile(source, args[2])
                return ""
            with patch.object(script, "sh", side_effect=fake_sh):
                self.assertEqual(script.read_purchase_token("subs_variant"), "")
            self.assertEqual(len(targets), 1)
            self.assertFalse(targets[0].exists())
            self.assertTrue(any(a[0] == "shell" and "rm -f" in a[1] for a in commands))

    def test_rejects_wrong_account_expired_tokens_and_accepts_matching_active_token(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home)
            source = root / "play-library.db"
            now = int(time.time() * 1000)
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE ownership (doc_id text, account text, "
                           "subs_valid_until_time integer, inapp_purchase_data text)")
                for account, until, token in (
                    ("other@example.com", now + 300000, "other-token"),
                    ("test@example.com", now - 300000, "expired-token"),
                    ("test@example.com", now + 300000, "valid-token"),
                ):
                    db.execute("INSERT INTO ownership VALUES (?, ?, ?, ?)",
                               ("g1.2tb.ai.subs_variant", account, until,
                                json.dumps({"purchaseToken": token})))
            def fake_sh(*args, **kwargs):
                if args[0] == "pull":
                    shutil.copyfile(source, args[2])
                return ""
            with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                 patch.object(script, "sh", side_effect=fake_sh):
                self.assertEqual(
                    script.read_purchase_token("subs_variant", expected_account="test@example.com"),
                    "valid-token")
                self.assertEqual(
                    script.read_purchase_token("subs_variant", expected_account="absent@example.com"),
                    "")


if __name__ == "__main__":
    unittest.main()
