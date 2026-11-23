"""Original detailed README format and localized Mac installation guidance."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("vi", "zh-CN", "ja", "ko", "es", "fr")
OVERVIEWS = ("README.md",) + tuple(f"README.{lang}.md" for lang in LANGUAGES)
NAVIGATION = ("README.md",) + tuple(f"README.{lang}.md" for lang in LANGUAGES)
ENGLISH_GUIDES = (
    "docs/SAFETY.md", "docs/INSTALLATION.md", "docs/USAGE.md",
    "docs/TROUBLESHOOTING.md", "docs/PROJECT.md",
)


def content(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def detailed_path(overview: str) -> str:
    return "docs/i18n/" + overview if overview != "README.md" else ""


def detailed_content(overview: str) -> str:
    if overview == "README.md":
        return "\n".join(content(path) for path in ENGLISH_GUIDES)
    return content(detailed_path(overview))


class ReadmeLocalesTests(unittest.TestCase):
    def test_language_switcher_and_detailed_guide_links(self):
        for overview in OVERVIEWS:
            with self.subTest(file=overview):
                text = content(overview)
                for ref in NAVIGATION:
                    if ref != overview:
                        self.assertIn(f"({ref})", text)
                self.assertIn("(docs/README.md)", text)
                if overview != "README.md":
                    self.assertIn(f"(docs/i18n/{overview})", text)
                    self.assertIn(f"(../../{overview})", detailed_content(overview))
                self.assertEqual(text.count("```") % 2, 0)

    def test_readmes_link_safety_and_platform_guidance(self):
        for overview in OVERVIEWS:
            with self.subTest(file=overview):
                text = content(overview)
                self.assertIn("[!CAUTION]", text)
                self.assertIn("2–5", text)
                self.assertIn("Google Play", text)
                self.assertIn("MuMuPlayer", text)
                self.assertIn(".\\run-all.ps1", text)
                self.assertIn("sh run-macos.sh", text)
                self.assertIn("(docs/MACOS-PREVIEW.md)", text)
                self.assertIn("(docs/SAFETY.md)", text)
                self.assertIn("(DISCLAIMER.md)", text)

    def test_original_commands_and_account_checks_remain_in_full_guides(self):
        commands = (
            ".\\run-all.ps1", "-Step 1", "-Step 2", "-Step 3",
            "-Step 4", "-Step 5", "-AllStages", "-StartStep 3",
        )
        labels = ("Frida 16.5.9", "Google Play", "MuMuPlayer",
                  "Verified in Google Play", "David Nguyen (@hoangsvit)")
        for overview in OVERVIEWS:
            with self.subTest(file=overview):
                guide = detailed_content(overview)
                for item in commands + labels:
                    self.assertIn(item, guide)
                self.assertIn("https://github.com/hoangsvit/google-ai/wiki/Install", guide)
                self.assertIn("https://www.mumuplayer.com/download/", guide)

    def test_card_hold_and_release_notes_remain_in_detailed_guides(self):
        official = "https://support.google.com/googleplay/answer/6224192?hl=en"
        for overview in OVERVIEWS:
            with self.subTest(file=overview):
                guide = detailed_content(overview)
                self.assertIn("> [!NOTE]", guide)
                self.assertIn(official, guide)
                self.assertIn("3", guide)
                self.assertIn("14", guide)
                for item in ("Source code (zip)", "`.exe`", "ADB/Frida"):
                    self.assertIn(item, guide)

    def test_support_and_muse_distinction_remains_in_detailed_guides(self):
        for overview in OVERVIEWS:
            with self.subTest(file=overview):
                guide = detailed_content(overview)
                for url in (
                    "https://t.me/eplus_news/29",
                    "https://github.com/hoangsvit/google-ai/issues",
                    "https://github.com/ePlus-DEV/muse-invite-hub",
                    "https://muse.eplus.dev/",
                ):
                    self.assertIn(url, guide)
                self.assertIn("Muse", guide)
                self.assertIn("Google AI Pro", guide)
                self.assertIn("2FA", guide)


if __name__ == "__main__":
    unittest.main()
