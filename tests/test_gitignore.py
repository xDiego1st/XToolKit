"""Regression checks for sensitive-file ignore rules (runs with git, no Android)."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ignored(path):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", path],
        cwd=ROOT, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return result.returncode == 0


class GitignoreTests(unittest.TestCase):
    def test_local_credentials_and_runtime_artifacts_are_ignored(self):
        paths = (
            "accounts.txt", "accounts-work.csv", "accounts-backup.json",
            ".env", ".env.local", "secret.pem", "temp.token",
            "ultra0-report/current.json", "platform-tools/adb.exe",
            "reports/summary.json", "logs/adb.log", ".venv/Scripts/python.exe",
            "__pycache__/ultra0.pyc", "screenshots/playstore.png",
            "debug.trace", "module.apk",
        )
        self.assertEqual([], [p for p in paths if not ignored(p)])

    def test_bundled_code_and_safe_templates_remain_trackable(self):
        paths = (
            "README.md", "README.en.md", "requirements.txt",
            "assets/frida/billing.js", "assets/modules/module_521.b64",
            "tests/test_assets.py", "docs/DETAILED-GUIDE.md",
            ".env.example", "run-all.ps1", "notes.txt",
        )
        self.assertEqual([], [p for p in paths if ignored(p)])


if __name__ == "__main__":
    unittest.main()
