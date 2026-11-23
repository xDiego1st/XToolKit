"""Offline regression checks for public maintainer documentation.

No Android device, checkout, or application runtime is touched.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MaintainerDocumentationTests(unittest.TestCase):
    def read(self, filename: str) -> str:
        return (ROOT / filename).read_text(encoding="utf-8")

    def test_release_announcement_uses_current_brand_and_safety_terms(self):
        content = self.read("ANNOUNCE.md")
        self.assertIn("ePlus AI Toolkit", content)
        self.assertNotIn("Google AI Android Toolkit", content)
        self.assertIn("https://github.com/hoangsvit/google-ai/releases", content)
        self.assertIn("Steps 2", content)
        self.assertIn("Google Play", content)
        self.assertIn("Vietnamese", content)

    def test_contributor_guide_installs_required_tui_dependency(self):
        content = self.read("CONTRIBUTING.md")
        self.assertIn("python -m pip install -r requirements-tui.txt", content)
        self.assertIn("python -m unittest discover -s tests -v", content)
        self.assertIn("node --test", content)
        self.assertIn("test_terminal_prompts.ps1", content)
        self.assertIn("Do not", content)

    def test_security_doc_distinguishes_no_checkout_from_no_side_effects(self):
        content = self.read("SECURITY.md")
        self.assertIn("run-all.ps1 -Step 1", content)
        self.assertIn("do **not request subscription checkout**", content)
        self.assertIn("not completely side-effect-free", content)

    def test_local_links_in_maintainer_docs_are_valid(self):
        for filename in ("ANNOUNCE.md", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md"):
            text = self.read(filename)
            for target in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                clean = target.partition("#")[0]
                with self.subTest(filename=filename, link=clean):
                    self.assertTrue((ROOT / clean).is_file())


if __name__ == "__main__":
    unittest.main()
