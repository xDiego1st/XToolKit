"""Unit tests for billing-launch diagnostics; no emulator or transactions."""
import importlib.util
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "ultra0.py"
spec = importlib.util.spec_from_file_location("billing_diag", script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class LaunchDiagnosticsTests(unittest.TestCase):
    def test_missing_art_symbol_is_classified(self):
        result = {"launched": None, "errors": [
            {"ev": "choose_err", "m": "libart.so: unable to find export EnsurePluginLoaded"},
            {"ev": "no_activity"}]}
        status, detail = mod.diagnose_launch_failure(result)
        self.assertEqual(status, "activity_lookup_failed")
        self.assertIn("Java.choose", detail)

    def test_no_activity_different_from_frida_failure(self):
        status, detail = mod.diagnose_launch_failure(
            {"launched": None, "errors": [{"ev": "no_activity"}]})
        self.assertEqual(status, "no_activity")

    def test_billing_code_not_confused_with_success(self):
        status, detail = mod.diagnose_launch_failure(
            {"launched": {"code": 6, "msg": "BILLING_ERROR"}, "errors": []})
        self.assertEqual(status, "billing_flow_error")
        self.assertIn("code=6", detail)

    def test_launch_exception_recorded(self):
        status, detail = mod.diagnose_launch_failure(
            {"launched": None, "errors": [{"ev": "launch_err", "m": "missing class"}]})
        self.assertEqual(status, "billing_launch_error")
        self.assertIn("missing class", detail)

    def test_no_signal_stays_unknown(self):
        status, detail = mod.diagnose_launch_failure({"launched": None, "errors": []})
        self.assertEqual(status, "launch_failed")


if __name__ == "__main__":
    unittest.main()
