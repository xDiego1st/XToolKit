"""Pengujian tampilan penawaran berbahasa Indonesia tanpa kebocoran token."""
import unittest

from tui_core import offer_explorer_lines


class OfferExplorerTests(unittest.TestCase):
    def test_renders_observed_first_phase_without_false_eligibility(self):
        report = {"status": "listed", "offers": [
            {"product": "g1.2tb.ai.subs_variant", "id": "12months-eft",
             "period": "P1Y", "micros": "0", "token": "SECRET_CHECKOUT_TOKEN"},
            {"product": "g1.play.2tb.ai", "id": "eft-3mo",
             "period": "P3M", "micros": "19990000"},
        ]}
        text = "\n".join(offer_explorer_lines(report))
        self.assertIn("12months-eft", text)
        self.assertIn("P1Y", text)
        self.assertIn("Rp0 / $0 (fase awal)", text)
        self.assertIn("Berbayar", text)
        self.assertIn("perpanjangan", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("activated", text)

    def test_does_not_echo_arbitrary_payload_or_credentials(self):
        report = {"offers": [
            {"product": "valid.product", "id": "evil\nsecret@example.com",
             "period": "P1Y", "micros": "0", "token": "private"},
        ]}
        text = "\n".join(offer_explorer_lines(report))
        self.assertIn("valid.product", text)
        self.assertIn("(tidak tersedia)", text)
        self.assertNotIn("secret@", text)
        self.assertNotIn("private", text)

    def test_empty_stale_and_malformed_reports_are_safe(self):
        self.assertIn("Belum ada", offer_explorer_lines(None)[0])
        self.assertIn("Belum ada", offer_explorer_lines({"offers": "fake"})[0])
        self.assertIn("Tidak ada penawaran", offer_explorer_lines({"offers": []})[0])

    def test_limits_output_without_checkout_side_effects(self):
        report = {"offers": [
            {"product": "g1.play.2tb.ai", "id": f"eft-{i}",
             "period": "P3M", "micros": "0"}
            for i in range(25)
        ]}
        output = offer_explorer_lines(report, limit=3)
        self.assertEqual(len(output), 6)
        self.assertIn("22 penawaran lainnya", output[-2])

    def test_malformed_first_phase_is_not_labeled_free(self):
        text = "\n".join(offer_explorer_lines({"offers": [
            {"id": "safe-offer", "micros": "$0"},
        ]}))
        self.assertIn("Tidak diketahui", text)
        self.assertNotIn("Rp0 / $0", text)


if __name__ == "__main__":
    unittest.main()
