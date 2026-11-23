"""Regression tests for safe cross-codepage runtime lookup on Windows."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_lookup", ROOT / "scripts" / "runtime-lookup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeLookupTests(unittest.TestCase):
    def test_connection_lookup_reuses_existing_emulator_connector(self):
        import setup_env
        with patch.object(setup_env, "find_adb", return_value="adb"), \
             patch.object(setup_env, "connect_emulator", return_value="emulator-5554") as connect:
            self.assertEqual(module.resolve_value("connect-device"), "emulator-5554")
        connect.assert_called_once_with("adb")

    def test_unicode_logs_are_suppressed_when_resolving_adb(self):
        import setup_env
        expected = r"D:\laragon\www\dev\google-ai\platform-tools\adb.exe"

        def mocked_find():
            print("\u25b6 Locating ADB")
            return expected

        with patch.object(setup_env, "find_adb", side_effect=mocked_find):
            self.assertEqual(module.resolve_value("adb"), expected)

    def test_encoded_result_is_ascii_under_cp1252(self):
        path = "C:\\Users\\Fran\u00e7ois\\platform-tools\\adb.exe"
        buffer = io.BytesIO()
        narrow_console = io.TextIOWrapper(buffer, encoding="cp1252", write_through=True)
        with patch.object(module, "resolve_value", return_value=path), \
             patch.object(sys, "stdout", narrow_console):
            status = module.main(["adb"])
        self.assertEqual(status, 0)
        output = buffer.getvalue().decode("ascii").strip()
        self.assertTrue(output.startswith("RUNTIME_RESULT:"))
        self.assertEqual(base64.b64decode(output.split(":", 1)[1]).decode("utf-8"), path)

    def test_empty_account_output_has_stable_prefix(self):
        with patch.object(module, "resolve_value", return_value=""), \
             patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            status = module.main(["play-account", "--serial", "emulator-5554"])
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue().strip(), "RUNTIME_RESULT:")

    def test_account_candidate_lookup_has_no_checkout_side_effects(self):
        import ultra0
        candidates = ["one@example.com", "two@example.com"]
        with patch.object(ultra0, "find_adb", return_value="adb"), \
             patch.object(ultra0, "pick_device"), \
             patch.object(ultra0, "available_google_accounts", return_value=candidates), \
             patch.object(ultra0, "run_trial") as billing:
            encoded = module.resolve_value("play-accounts", "emulator-5554")
        self.assertEqual(json.loads(encoded), candidates)
        billing.assert_not_called()

    def test_account_lookup_requires_serial(self):
        with self.assertRaises(SystemExit):
            module.main(["play-account"])


if __name__ == "__main__":
    unittest.main()
