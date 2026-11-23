"""Android 15 ADB PID validation tests without an emulator or purchases."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / "ultra0.py"
spec = importlib.util.spec_from_file_location("frida_pid_validation", source)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def command_result(stdout, returncode=0, stderr=b""):
    return subprocess.CompletedProcess([], returncode, stdout.encode("utf-8"), stderr)


class AdbPidTests(unittest.TestCase):
    def setUp(self):
        app.ADB = "adb.exe"
        app.SERIAL = "another-device"

    def test_matching_pid_and_cmdline_pass(self):
        def invoke(command, **_):
            self.assertEqual(command[:3], ["adb.exe", "-s", "emulator-5554"])
            if command[4] == "pidof":
                return command_result("11004\n")
            return command_result("com.google.android.apps.subscriptions.red\x00")
        with patch.object(app.subprocess, "run", side_effect=invoke) as run:
            self.assertEqual(app.verify_adb_target_pid(11004, "emulator-5554"), app.PKG)
        self.assertEqual(run.call_count, 2)

    def test_stale_pid_stops_before_attach(self):
        with patch.object(app.subprocess, "run", return_value=command_result("23931\n")):
            with self.assertRaisesRegex(RuntimeError, "no longer running"):
                app.verify_adb_target_pid(11004, "emulator-5554")

    def test_unrelated_process_stops_before_attach(self):
        with patch.object(app.subprocess, "run", side_effect=[
                command_result("11004\n"), command_result("com.example.other\x00")]):
            with self.assertRaisesRegex(RuntimeError, "refusing to attach"):
                app.verify_adb_target_pid(11004, "emulator-5554")

    def test_proc_restriction_uses_fresh_exact_package_pidof(self):
        with patch.object(app.subprocess, "run", side_effect=[
                command_result("11004\n"), command_result("", returncode=1, stderr=b"Permission denied")]):
            self.assertEqual(app.verify_adb_target_pid(11004, "emulator-5554"), app.PKG)

    def test_pidof_failure_stops(self):
        with patch.object(app.subprocess, "run",
                          return_value=command_result("", returncode=1, stderr=b"device offline")):
            with self.assertRaisesRegex(RuntimeError, "ADB process inspection failed"):
                app.verify_adb_target_pid(11004, "emulator-5554")


if __name__ == "__main__":
    unittest.main()
