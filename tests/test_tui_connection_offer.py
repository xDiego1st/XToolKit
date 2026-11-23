"""Pengujian offline untuk diagnosa koneksi dan tampilan penawaran pada XToolKit-Diego."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from device_diagnostics import ConnectionDiagnosis
from tui_core import Outcome


class ConnectionAndOfferUITests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnose_button_shows_guidance_without_checkout(self):
        from tui import GoogleAITUI
        from textual.widgets import Button, Static
        fake = ConnectionDiagnosis(
            "missing_adb", "ADB tidak ditemukan",
            ("Host: Terminal macOS", "Frida host: belum terpasang"),
            "Pasang Android SDK Platform-Tools, lalu coba lagi.",
        )
        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch.object(GoogleAITUI, "_poll_connection"), \
                 patch("tui.inspect_connection", return_value=fake), \
                 patch("tui.subprocess.Popen") as checkout:
                async with app.run_test(size=(110, 35)) as pilot:
                    self.assertTrue(app.query_one("#diagnose", Button).display)
                    await pilot.click("#diagnose")
                    for _ in range(30):
                        await pilot.pause(0.05)
                        if not app._diagnosing:
                            break
                    self.assertFalse(app._diagnosing)
                    self.assertIn("ADB tidak ditemukan", str(app.query_one("#state", Static).render()))
                    self.assertIn("Terminal macOS", str(app.query_one("#step_result", Static).render()))
                    self.assertFalse(app.busy)
                checkout.assert_not_called()

    async def test_offer_explorer_is_only_shown_after_fresh_listing(self):
        from tui import GoogleAITUI
        from textual.widgets import RichLog, Static
        report = {"status": "listed", "offers": [
            {"product": "g1.2tb.ai.subs_variant", "id": "12months-eft",
             "micros": "0", "period": "P1Y", "token": "MUST_NOT_SHOW"}
        ]}
        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory), auto_step2=False)
            with patch.object(GoogleAITUI, "_poll_connection"), \
                 patch("tui.subprocess.Popen") as checkout:
                async with app.run_test(size=(110, 35)) as pilot:
                    viewer = app.query_one("#offer_view", RichLog)
                    self.assertFalse(viewer.display)
                    app._finished(1, Outcome("listed", "Penawaran dimuat", "Periksa secara manual."), report)
                    await pilot.pause()
                    self.assertTrue(viewer.display)
                    self.assertTrue(app.query_one("#offers_title", Static).display)
                    self.assertGreater(len(viewer.lines), 0)
                    self.assertFalse(app.query_one("#next").display)
                checkout.assert_not_called()

    async def test_new_run_hides_old_offer_details(self):
        from tui import GoogleAITUI
        from textual.widgets import RichLog
        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory), auto_step2=False)
            with patch.object(GoogleAITUI, "_poll_connection"), \
                 patch.object(GoogleAITUI, "run_stage"):
                async with app.run_test(size=(110, 35)):
                    viewer = app.query_one("#offer_view", RichLog)
                    app._finished(1, Outcome("listed", "Penawaran dimuat", "Cek"), {
                        "offers": [{"id": "eft-3mo", "micros": "0"}]})
                    self.assertTrue(viewer.display)
                    app._start(1, False)
                    self.assertFalse(viewer.display)
                    self.assertEqual(len(viewer.lines), 0)

    async def test_diagnosis_blocks_concurrent_paid_stage(self):
        from tui import GoogleAITUI
        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch.object(GoogleAITUI, "_poll_connection"), \
                 patch.object(GoogleAITUI, "run_stage") as paid:
                async with app.run_test(size=(110, 35)):
                    app._offer_check_ready = True
                    app._diagnosing = True
                    app._start(2, False)
                    self.assertFalse(app.busy)
                    paid.assert_not_called()


if __name__ == "__main__":
    unittest.main()
