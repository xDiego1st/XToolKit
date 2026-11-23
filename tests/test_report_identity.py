"""Report naming must separate account domains and never expose email in filenames."""
import hashlib
from pathlib import Path
import unittest

from ultra0 import report_filename

ROOT = Path(__file__).resolve().parents[1]


class ReportIdentityTests(unittest.TestCase):
    def test_readonly_listing_keeps_current_json(self):
        self.assertEqual(report_filename("current@device"), "current.json")

    def test_full_email_identity_avoids_cross_domain_collisions(self):
        first = report_filename("alice@gmail.com")
        second = report_filename("alice@yahoo.com")
        self.assertNotEqual(first, second)
        self.assertEqual(first, report_filename(" ALICE@GMAIL.COM "))
        expected = "account-" + hashlib.sha256(b"alice@gmail.com").hexdigest() + ".json"
        self.assertEqual(first, expected)

    def test_filenames_do_not_expose_account_or_path_separators(self):
        value = report_filename("alice@example.com")
        self.assertNotIn("alice", value)
        self.assertNotIn("example.com", value)
        self.assertNotIn("/", value)
        self.assertNotIn("\\", value)

    def test_powershell_uses_full_identity_not_local_part(self):
        ps = (ROOT / "run-all.ps1").read_text(encoding="utf-8")
        self.assertIn("$key = Get-AccountReportKey $Email", ps)
        self.assertNotIn("$Email.Split('@')[0]", ps)


if __name__ == "__main__":
    unittest.main()
