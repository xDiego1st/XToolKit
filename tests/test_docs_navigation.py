"""Validasi struktur dokumentasi Bahasa Indonesia XToolKit-Diego dan tautan lokal."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TOPIC_PAGES = (
    "docs/README.md",
    "docs/SAFETY.md",
    "docs/INSTALLATION.md",
    "docs/USAGE.md",
    "docs/TROUBLESHOOTING.md",
    "docs/PROJECT.md",
    "docs/MACOS-PREVIEW.md",
    "docs/DETAILED-GUIDE.md",
    "docs/ORIGINAL-STEPS.md",
    "docs/AUTHOR-NOTES.md",
    "docs/WINDOWS-SMOKE-TEST.md",
    "docs/releases/v1.0.1.md",
)
MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class DocumentationNavigationTests(unittest.TestCase):
    def test_only_indonesian_readme_exists_and_no_i18n_folder(self):
        root_readmes = sorted(p.name for p in ROOT.glob("README*.md"))
        self.assertEqual(root_readmes, ["README.md"])
        self.assertFalse((DOCS / "i18n").exists())

    def test_readme_has_xtoolkit_diego_sections_and_screenshots(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("# ✦ XToolKit-Diego", readme)
        self.assertIn("[!CAUTION]", readme)
        self.assertIn("[!NOTE]", readme)
        for img in (
            "images/terminal-ui-overview.png",
            "images/terminal-ui-step2-billing.png",
            "images/terminal-ui-step-picker.png",
            "images/terminal-ui-adb-recovery.png",
        ):
            with self.subTest(image=img):
                self.assertIn(img, readme)
                self.assertTrue((ROOT / img).is_file())
        for expected in (
            "sh run-macos.sh",
            "XToolKit-Diego.command",
            r".\run-all.ps1",
            "Step 0–4",
            "Inject Ulang",
            "Perbaiki ADB",
            "Auto Step 2",
        ):
            with self.subTest(token=expected):
                self.assertIn(expected, readme)

    def test_documentation_hub_references_every_topic_page(self):
        hub = (DOCS / "README.md").read_text(encoding="utf-8")
        self.assertIn("XToolKit-Diego", hub)
        for target in TOPIC_PAGES:
            with self.subTest(page=target):
                self.assertTrue((ROOT / target).is_file())
                if target != "docs/README.md":
                    rel = str(Path(target).relative_to("docs"))
                    self.assertIn(f"({rel})", hub)

    def test_all_local_links_and_images_point_to_existing_files(self):
        locations = [
            ROOT / "README.md",
            ROOT / "DISCLAIMER.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "ANNOUNCE.md",
            ROOT / "AGENTS.md",
            ROOT / "THIRD_PARTY_NOTICES.md",
            ROOT / "SECURITY.md",
        ] + sorted(DOCS.rglob("*.md"))
        for source in locations:
            text = source.read_text(encoding="utf-8")
            self.assertEqual(
                len([ln for ln in text.splitlines() if ln.strip().startswith("```")]) % 2,
                0,
                f"Unbalanced code fence in {source}",
            )
            for target in MD_LINK.findall(text):
                clean = target.strip().split()[0]
                if clean.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                relative = clean.partition("#")[0]
                if not relative:
                    continue
                with self.subTest(source=str(source.relative_to(ROOT)), link=relative):
                    self.assertTrue((source.parent / relative).is_file())

    def test_removed_branding_does_not_appear_in_readme_or_docs(self):
        locations = [ROOT / "README.md"] + sorted(DOCS.rglob("*.md"))
        forbidden = ("ePlus AI Toolkit", "hoangsvit", "gylive", "t.me/eplus_news", "eplus.dev")
        for source in locations:
            text = source.read_text(encoding="utf-8")
            for term in forbidden:
                with self.subTest(source=str(source.relative_to(ROOT)), term=term):
                    self.assertNotIn(term.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
