"""Offline checks for root layout, relocated Windows shortcuts and branch routing."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

LEGACY = (
    "00-environment-check.bat",
    "01-list-offers.bat",
    "02-pro-12-months.bat",
    "03-pro-add-6-months.bat",
    "04-pro-add-6-months-again.bat",
    "05-pro-alternative-6-months.bat",
)


class RepositoryLayoutTests(unittest.TestCase):
    def test_root_has_no_legacy_batch_shortcuts(self):
        self.assertEqual(list(ROOT.glob("*.bat")), [])

    def test_current_runtime_paths_are_preserved(self):
        for filename in (
            "run-all.ps1", "tui.py", "tui_core.py", "ultra0.py",
            "setup_env.py", "device_selector.py", "query_sku.py",
        ):
            with self.subTest(file=filename):
                self.assertTrue((ROOT / filename).is_file())

    def test_relocated_batch_shortcuts_resolve_repo_root(self):
        files = [ROOT / "tools/windows/setup-environment.bat"]
        files += [ROOT / "legacy/windows" / path for path in LEGACY]
        for path in files:
            with self.subTest(file=path):
                self.assertTrue(path.is_file())
                content = path.read_text(encoding="utf-8")
                self.assertIn('cd /d "%~dp0..\\.."', content)
                self.assertIn(
                    "python setup_env.py" if path.name == "setup-environment.bat"
                    else "python ultra0.py",
                    content,
                )

    def test_new_docs_explain_historical_checkout_risks(self):
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        project_guide = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        legacy = (ROOT / "legacy/windows/README.md").read_text(encoding="utf-8")
        self.assertIn("(docs/PROJECT.md)", root_readme)
        self.assertIn("legacy/windows/README.md", project_guide)
        self.assertIn("tools/windows/README.md", project_guide)
        self.assertIn("--force", legacy)
        self.assertIn("real Google Play", legacy)
        self.assertIn("dev", (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))

    def test_branch_policy_requires_dev_to_main(self):
        policy = (ROOT / ".github/workflows/branch-routing.yml").read_text(encoding="utf-8")
        self.assertIn("branches:", policy)
        self.assertIn("- dev", policy)
        self.assertIn("- main", policy)
        self.assertIn('"$HEAD" != "dev"', policy)
        self.assertIn('"$HEAD_REPO" != "$TARGET_REPO"', policy)


if __name__ == "__main__":
    unittest.main()
