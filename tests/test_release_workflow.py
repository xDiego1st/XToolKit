"""Prevent release automation from becoming version-specific again.

These tests inspect YAML source only; they never publish a release.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


class ReusableReleaseWorkflowTests(unittest.TestCase):
    def test_single_reusable_publisher(self):
        self.assertTrue((WORKFLOW_DIR / "publish-release.yml").is_file())
        self.assertFalse((WORKFLOW_DIR / "publish-v1.0.1.yml").exists())
        self.assertEqual(
            [p.name for p in WORKFLOW_DIR.glob("publish-*.yml")],
            ["publish-release.yml"],
        )

    def test_version_is_input_not_hardcoded(self):
        content = (WORKFLOW_DIR / "publish-release.yml").read_text(encoding="utf-8")
        for required in (
            "workflow_dispatch:",
            "version:",
            "VERSION: ${{ inputs.version }}",
            "verified_device_smoke:",
            "prerelease:",
            'notes_file="docs/releases/v$VERSION.md"',
            "--generate-notes",
            '"refs/tags/$VERSION"',
            'gh "${args[@]}"',
            "windows-smoke:",
            "Static checks",
        ):
            with self.subTest(term=required):
                self.assertIn(required, content)
        self.assertNotIn("gh release create 1.0.1", content)
        self.assertNotIn("publish-eplus-ai-toolkit-v1.0.1", content)

    def test_windows_runner_watches_reusable_workflow(self):
        content = (WORKFLOW_DIR / "windows-release-smoke.yml").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/publish-release.yml", content)
        self.assertNotIn("publish-v1.0.1.yml", content)

    def test_windows_smoke_preserves_exact_source_and_sha256(self):
        workflow = (WORKFLOW_DIR / "windows-release-smoke.yml").read_text(encoding="utf-8")
        for term in (
            "Get-FileHash",
            "-Algorithm SHA256",
            "actions/upload-artifact@v4",
            "eplus-ai-toolkit-source-${{ github.sha }}",
            "eplus-ai-toolkit-source.zip.sha256",
            "retention-days: 14",
            "if-no-files-found: error",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)

    def test_manual_hardware_checklist_links_tested_artifact(self):
        content = (ROOT / "docs" / "WINDOWS-SMOKE-TEST.md").read_text(encoding="utf-8")
        self.assertIn("actions/workflows/windows-release-smoke.yml", content)
        self.assertIn("Get-FileHash", content)
        self.assertIn("14 days", content)
        self.assertIn("not* a published GitHub Release", content)

    def test_manual_checklist_applies_to_future_versions(self):
        content = (ROOT / "docs" / "WINDOWS-SMOKE-TEST.md").read_text(encoding="utf-8")
        self.assertIn("Publish ePlus AI Toolkit (manual)", content)
        self.assertIn("version", content.lower())
        self.assertIn("Static checks", content)


if __name__ == "__main__":
    unittest.main()
