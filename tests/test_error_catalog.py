"""Regression guard: every checkout engine status needs human-readable guidance."""
from pathlib import Path
import re
import unittest

from tui_core import CLI_ISSUES, MESSAGES, outcome_for_stage, readable_issue_line

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ultra0.py").read_text(encoding="utf-8")


class ErrorCatalogTests(unittest.TestCase):
    def test_all_engine_report_errors_have_friendly_messages(self):
        statuses = set(re.findall(r'rec\["status"\]\s*=\s*"([a-z_]+)"', SOURCE))
        # The ternary checkout outcome is included explicitly below.
        statuses.update(("checkout_requested", "checkout_not_confirmed"))
        diagnostics = SOURCE.split("def diagnose_launch_failure(", 1)[1].split(
            "def handle_verify(", 1
        )[0]
        statuses.update(re.findall(r'return \("([a-z_]+)"', diagnostics))
        known_success = {"listed", "checkout_requested", "unknown"}
        missing = statuses - known_success - set(MESSAGES) - set(CLI_ISSUES)
        self.assertFalse(missing, f"Engine statuses without readable explanations: {sorted(missing)}")
        for status in statuses - known_success:
            with self.subTest(status=status):
                result = outcome_for_stage(3, 0, {"status": status})
                self.assertNotEqual(result.title, "Could not verify this step")
                self.assertTrue(result.instruction)
                self.assertFalse(result.can_review)

    def test_checkout_rejection_reasons_have_friendly_messages(self):
        reasons = set(re.findall(r'(?:result|out)\["reason"\]\s*=\s*"([a-z_]+)"', SOURCE))
        reasons.update(re.findall(r'"reason": "([a-z_]+)"', SOURCE))
        internal_success = {"zero_today_and_duration_verified"}
        self.assertFalse(
            reasons - internal_success - set(MESSAGES) - set(CLI_ISSUES),
            "Checkout reason without a readable explanation",
        )

    def test_cli_markers_never_appear_on_screen(self):
        for code in set(MESSAGES) | set(CLI_ISSUES) | {"unknown", "new_error_code"}:
            with self.subTest(code=code):
                visible = readable_issue_line(f"EPLUS_ISSUE:{code}")
                self.assertNotIn("EPLUS_ISSUE:", visible)
                self.assertNotIn("Traceback", visible)
                self.assertTrue(visible.strip())


if __name__ == "__main__":
    unittest.main()
