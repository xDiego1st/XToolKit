"""Pengujian adapter macOS XToolKit-Diego (semua interaksi Android/checkout di-mock)."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import macos_runner
from tui_core import command_for_step


class MacStageAdapterTests(unittest.TestCase):
    def test_android_details_query_uses_selected_device(self):
        result = subprocess.CompletedProcess([], 0, "14\n34\narm64-v8a\n", "")
        with patch("macos_runner.subprocess.run", return_value=result) as run:
            with patch("builtins.print") as output:
                macos_runner.show_android_details("/tools/adb", "emulator-5554")
        self.assertEqual(run.call_args.args[0][:4], ["/tools/adb", "-s", "emulator-5554", "shell"])
        output.assert_called_once_with("Android 14 (SDK 34), ABI arm64-v8a", flush=True)

    def test_five_stage_mapping_and_no_force(self):
        offers = {
            2: ("pro12", "12months-eft", False),
            3: ("pro6", "6months-eft", True),
            4: ("pro6b", "6months-eft-2", True),
        }
        for step, (plan, expected, stacking) in offers.items():
            with self.subTest(step=step):
                cmd = macos_runner.stage_command(step, "emulator-5554", "alice@example.com", "python")
                self.assertEqual(cmd[cmd.index("--plan") + 1], plan)
                self.assertEqual(macos_runner.STAGES[step][1], expected)
                self.assertEqual("--stack" in cmd, stacking)
                self.assertIn("--no-switch", cmd)
                self.assertIn("--no-add", cmd)
                self.assertNotIn("--force", cmd)
        for step in (-1, 5, 6, True, "2"):
            with self.assertRaises(ValueError):
                macos_runner.stage_command(step, "emulator-5554")
        for step in (2, 3, 4):
            with self.assertRaises(ValueError):
                macos_runner.stage_command(step, "emulator-5554", "current@device")

    def test_list_never_opens_checkout(self):
        cmd = macos_runner.stage_command(1, "emulator-5554")
        for flag in ("--list", "--no-add", "--no-switch"):
            self.assertIn(flag, cmd)
        for forbidden in ("--force", "--stack", "--confirmed"):
            self.assertNotIn(forbidden, cmd)

    def test_play_account_is_read_from_exact_lookup_result(self):
        token = base64.b64encode(b"alice@example.com").decode("ascii")
        response = type("Result", (), {
            "returncode": 0, "stdout": f"RUNTIME_RESULT:{token}\n"
        })()
        with patch("macos_runner.subprocess.run", return_value=response) as invoke:
            self.assertEqual(macos_runner.read_play_account("device-1", {}), "alice@example.com")
            self.assertIn("play-account", invoke.call_args.args[0])
            self.assertEqual(invoke.call_args.args[0][-2:], ["--serial", "device-1"])

    def test_paid_stage_rejects_wrong_verified_device(self):
        with patch("macos_runner.run_engine") as engine:
            with self.assertRaisesRegex(RuntimeError, "berubah"):
                macos_runner.run_stage(3, "device-b", {}, confirmed=True,
                                       active_confirmed=True, expected_device="device-a")
        engine.assert_not_called()

    def test_paid_stage_refuses_unconfirmed_or_wrong_account(self):
        report = {"status": "listed", "offers": [{"id": "12months-eft", "micros": "0"}],
                  "detected_play_account": "alice@example.com"}
        with self.assertRaisesRegex(RuntimeError, "confirmations"):
            macos_runner.run_stage(2, "device-1", {})
        with patch("macos_runner.run_engine", return_value=0):
            with patch("macos_runner.list_offers", return_value=report):
                with patch("macos_runner.read_play_account", return_value="bob@example.com"):
                    with self.assertRaisesRegex(RuntimeError, "berubah"):
                        macos_runner.run_stage(2, "device-1", {}, confirmed=True)

    def test_paid_stage_rejects_nonzero_offer(self):
        report = {"status": "listed", "offers": [{"id": "12months-eft", "micros": "3000000"}],
                  "detected_play_account": "alice@example.com"}
        with patch("macos_runner.run_engine", return_value=0) as send:
            with patch("macos_runner.list_offers", return_value=report):
                with patch("macos_runner.read_play_account", return_value="alice@example.com"):
                    with self.assertRaisesRegex(RuntimeError, "zero-priced"):
                        macos_runner.run_stage(2, "device-1", {}, confirmed=True)
            self.assertEqual(send.call_count, 1)

    def test_paid_stage_invokes_original_engine_only_after_checks(self):
        report = {"status": "listed", "offers": [{"id": "6months-eft", "micros": 0}],
                  "detected_play_account": "alice@example.com"}
        with patch("macos_runner.run_engine", return_value=0) as send:
            with patch("macos_runner.list_offers", return_value=report):
                with patch("macos_runner.read_play_account", return_value="alice@example.com"):
                    self.assertEqual(
                        macos_runner.run_stage(3, "device-1", {}, confirmed=True,
                                               active_confirmed=True), 0
                    )
            self.assertEqual(send.call_count, 2)
            paid = send.call_args.args[0]
            self.assertIn("--stack", paid)
            self.assertNotIn("--force", paid)
            self.assertEqual(paid[paid.index("--account") + 1], "alice@example.com")
            with self.assertRaisesRegex(RuntimeError, "confirmations"):
                macos_runner.run_stage(3, "device-1", {}, confirmed=True)

    def test_tui_core_mac_passes_verified_device(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "macos_runner.py").write_text("# mock", encoding="utf-8")
            with patch("tui_core.sys.platform", "darwin"):
                command = command_for_step(3, root, account="alice@example.com", device="device-a")
                self.assertEqual(command[command.index("--expected-device") + 1], "device-a")
                self.assertEqual(command[command.index("--expected-account") + 1], "alice@example.com")

    def test_tui_core_mac_passes_explicit_checkout_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "macos_runner.py").write_text("# mock", encoding="utf-8")
            with patch("tui_core.sys.platform", "darwin"):
                for step in range(5):
                    command = command_for_step(step, root)
                    self.assertEqual(command[0], sys.executable)
                    self.assertEqual(command[command.index("--step") + 1], str(step))
                    self.assertEqual("--confirmed" in command, step >= 2)
                    self.assertEqual("--active-confirmed" in command, step >= 3)

    def test_reports_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(macos_runner, "REPORT_DIR", Path(temp)):
                path = Path(temp) / "current.json"
                path.write_text(json.dumps({"status": "listed"}), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    macos_runner.fresh_report("current.json", time.time_ns() + 1_000_000_000)

    def test_macos_adapter_shows_friendly_error_and_private_tui_marker(self):
        for tui_mode in (False, True):
            with self.subTest(tui_mode=tui_mode):
                output = io.StringIO()
                errors = io.StringIO()
                environment = {"EPLUS_TUI": "1"} if tui_mode else {"EPLUS_TUI": ""}
                with patch.dict(os.environ, environment):
                    with patch("macos_runner.preflight",
                               side_effect=RuntimeError("No online Android device. Check adb devices.")):
                        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                            self.assertEqual(macos_runner.main(["--step", "1"]), 1)
                self.assertIn("Perangkat Android belum terhubung", errors.getvalue())
                self.assertNotIn("RuntimeError:", errors.getvalue())
                self.assertNotIn("EPLUS_ISSUE:", errors.getvalue())
                self.assertEqual("EPLUS_ISSUE:device_missing" in output.getvalue(), tui_mode)

    def test_launcher_uses_xtoolkit_diego_branding(self):
        src = (Path(__file__).resolve().parents[1] / "run-macos.sh").read_text(encoding="utf-8")
        self.assertIn("XToolKit-Diego", src)
        self.assertIn("sh run-macos.sh", src)
        self.assertNotIn("ePlus AI Toolkit", src)
        self.assertNotIn("ultra0.py --force", src)

    def test_steps_2_to_4_reinject_skip_step0_and_list_and_use_open_only(self):
        expected_plans = {2: "pro12", 3: "pro6", 4: "pro6b"}
        for step, plan in expected_plans.items():
            with self.subTest(step=step):
                with patch("macos_runner.run_engine", return_value=0) as send, \
                     patch("macos_runner.list_offers") as offers, \
                     patch("macos_runner.read_play_account", return_value="diego@gmail.com"):
                    rc = macos_runner.run_stage(
                        step, "127.0.0.1:16384", {}, confirmed=True,
                        active_confirmed=(step >= 3),
                        expected_account="diego@gmail.com", expected_device="127.0.0.1:16384",
                        reinject=True,
                    )
                self.assertEqual(rc, 0)
                offers.assert_not_called()
                send.assert_called_once()
                cmd = send.call_args.args[0]
                self.assertIn("--open-only", cmd)
                self.assertEqual(cmd[cmd.index("--plan") + 1], plan)
                self.assertEqual("--stack" in cmd, step >= 3)
                self.assertNotIn("--force", cmd)

    def test_steps_2_to_4_normal_run_also_pass_open_only(self):
        expected_offers = {2: "12months-eft", 3: "6months-eft", 4: "6months-eft-2"}
        for step, offer_id in expected_offers.items():
            with self.subTest(step=step):
                report = {"status": "listed", "offers": [{"id": offer_id, "micros": 0}],
                          "detected_play_account": "diego@gmail.com"}
                with patch("macos_runner.run_engine", return_value=0) as send, \
                     patch("macos_runner.list_offers", return_value=report), \
                     patch("macos_runner.read_play_account", return_value="diego@gmail.com"):
                    rc = macos_runner.run_stage(
                        step, "127.0.0.1:16384", {}, confirmed=True, active_confirmed=(step >= 3)
                    )
                self.assertEqual(rc, 0)
                paid_cmd = send.call_args.args[0]
                self.assertIn("--open-only", paid_cmd)
                self.assertEqual("--stack" in paid_cmd, step >= 3)


class MacTuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_macos_exposes_five_steps_0_to_4_and_never_auto_runs_on_startup(self):
        from textual.widgets import Select
        from tui import GoogleAITUI
        with tempfile.TemporaryDirectory() as temp:
            with patch("tui.is_macos_platform", return_value=True), \
                 patch.object(GoogleAITUI, "_poll_connection"):
                app = GoogleAITUI(repo=Path(temp), selected_step=3)
            with patch("tui.subprocess.Popen") as child:
                async with app.run_test(size=(110, 35)) as pilot:
                    self.assertEqual(app.query_one("#step", Select).value, 3)
                    self.assertEqual(len(app.query("#workflow .workflow-step")), 5)
                    self.assertFalse(app.query_one("#mode", Select).disabled)
                    self.assertFalse(app.busy)
                    self.assertTrue(app.debug_visible)
                    await pilot.pause()
                child.assert_not_called()

    async def test_macos_tui_manual_mode_shows_approval_for_step_3(self):
        from tui import GoogleAITUI, Approval
        with tempfile.TemporaryDirectory() as temp:
            with patch("tui.is_macos_platform", return_value=True), \
                 patch.object(GoogleAITUI, "_poll_connection"):
                app = GoogleAITUI(repo=Path(temp), selected_step=3)
            with patch("tui.subprocess.Popen") as child:
                async with app.run_test(size=(110, 35)) as pilot:
                    app._offer_check_ready = True
                    app._confirm_stage(3, False)
                    await pilot.pause()
                    self.assertIsInstance(app.screen, Approval)
                    self.assertFalse(app.busy)
                child.assert_not_called()


if __name__ == "__main__":
    unittest.main()
