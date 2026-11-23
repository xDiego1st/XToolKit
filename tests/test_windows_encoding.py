"""Regression checks for Windows PowerShell/Python output encodings (no Android)."""
from pathlib import Path
import os
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsEncodingTests(unittest.TestCase):
    def test_launcher_configures_utf8_before_running_python(self):
        script = (ROOT / "run-all.ps1").read_text(encoding="utf-8")
        marker = script.index('function Run-Command')
        self.assertIn('$env:PYTHONIOENCODING = "utf-8:backslashreplace"', script[:marker])
        self.assertIn('$env:PYTHONUTF8 = "1"', script[:marker])
        self.assertIn('[Console]::OutputEncoding = $utf8Output', script[:marker])

    def test_legacy_cp1252_stdout_does_not_crash_ultra0_status(self):
        # Simulate Windows' legacy stdout encoding without ADB/Frida or checkout.
        code = (
            "import sys; "
            "sys.stdout.reconfigure(encoding='cp1252', errors='strict'); "
            "import ultra0; ultra0.ok('adb test')"
        )
        env = os.environ.copy()
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT, env=env, capture_output=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn(b"adb test", result.stdout)
        self.assertIn(b"\\u2705", result.stdout)

    def test_forced_utf8_child_emits_utf8_symbols(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8:backslashreplace"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", "print('   ✅ adb test', flush=True)"],
            env=env, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn("✅ adb test", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
