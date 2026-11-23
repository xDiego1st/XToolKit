"""Pengujian offline untuk XToolKit-Diego (Textual TUI, tui_core, realtime log, stop, auto Step 2, ADB)."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tui_core import (
    Outcome,
    cli_issue_outcome,
    command_for_step,
    format_realtime_log,
    mask_email,
    needs_setup,
    outcome_for_stage,
    read_fresh_report,
    readable_issue_line,
    report_summary,
    runtime_error_outcome,
    safe_launch_diagnostic,
    validate_step,
)


class CoreTests(unittest.TestCase):
    def test_structured_cli_error_shows_actionable_failure(self):
        result = cli_issue_outcome(["Device emulator-5554", "EPLUS_ISSUE:app_missing"], 1)
        self.assertEqual(result.code, "app_missing")
        self.assertIn("Google One", result.instruction)
        self.assertFalse(result.can_review)

    def test_paid_cli_errors_never_authorize_next_and_warn_about_payments(self):
        result = cli_issue_outcome(["EPLUS_ISSUE:offer_query_failed"], 2)
        self.assertFalse(result.can_review)
        self.assertIn("Google Play", result.instruction)
        self.assertIsNone(cli_issue_outcome(["EPLUS_ISSUE:checkout_requested"], 2))

    def test_cli_error_rejects_untrusted_text(self):
        self.assertIsNone(cli_issue_outcome(["EPLUS_ISSUE:app_missing private@example.com"], 1))
        self.assertEqual(
            cli_issue_outcome(["EPLUS_ISSUE:unknown"], 1).title,
            "Langkah ini tidak dapat diselesaikan",
        )

    def test_launch_error_has_friendly_indonesian_title_and_guidance(self):
        for code, phrase in (
            ("launch_failed", "checkout Google Play"),
            ("billing_flow_error", "Google Play"),
            ("activity_lookup_failed", "Google One"),
            ("no_activity", "Google One"),
        ):
            with self.subTest(code=code):
                result = cli_issue_outcome([f"EPLUS_ISSUE:{code}"], 3)
                self.assertIsNotNone(result)
                self.assertIn(phrase, result.title)
                self.assertIn("Google Play", result.instruction)
                self.assertFalse(result.can_review)

    def test_fresh_billing_error_report_is_explained_even_on_nonzero_exit(self):
        report = {"status": "launch_failed"}
        for code in (0, 1):
            with self.subTest(exit_code=code):
                result = outcome_for_stage(3, code, report)
                self.assertEqual(result.code, "launch_failed")
                self.assertIn("checkout Google Play", result.title)
                self.assertFalse(result.can_review)
        self.assertEqual(report_summary(report), "Gagal membuka layar checkout Google Play")

    def test_cli_protocol_markers_are_humanized_and_sanitized(self):
        readable = readable_issue_line("EPLUS_ISSUE:launch_failed")
        self.assertIn("Gagal membuka layar checkout Google Play", readable)
        self.assertIn("Saran:", readable)
        self.assertNotIn("EPLUS_ISSUE:", readable)
        self.assertNotIn("launch_failed", readable)
        self.assertEqual(readable_issue_line("Baris normal"), "Baris normal")
        malformed = readable_issue_line("EPLUS_ISSUE:launch_failed person@example.com")
        self.assertNotIn("person@example.com", malformed)
        self.assertNotIn("EPLUS_ISSUE:", malformed)

    def test_format_realtime_log_masks_email_and_escapes_markup(self):
        formatted = format_realtime_log("Account secret.user@gmail.com [red]tag[/red]", timestamp="04:15:00")
        self.assertIn("04:15:00", formatted)
        self.assertIn("[AKUN ]", formatted)
        self.assertIn("se***@gmail.com", formatted)
        self.assertNotIn("secret.user@gmail.com", formatted)
        self.assertIn("\\[red]", formatted)

    def test_every_known_engine_failure_has_user_guidance(self):
        statuses = (
            "add_account_failed", "add_account_error",
            "payment_method_not_confirmed", "account_unverified",
            "wrong_account", "play_account_switch_failed", "app_not_started",
            "offer_query_failed", "checkout_security_blocked",
            "checkout_not_confirmed", "launch_failed", "billing_flow_error",
            "billing_launch_error", "activity_lookup_failed", "no_activity",
            "subscription_update_unavailable", "ineligible",
            "purchase_unavailable", "today_price_unverified",
            "trial_duration_unverified", "already_subscribed",
            "processing", "backup_payment_methods_prompt",
            "subscribe_button_not_found", "checkout_not_visible",
        )
        for status in statuses:
            with self.subTest(status=status):
                result = outcome_for_stage(3, 0, {"status": status})
                self.assertNotIn("Hasil langkah tidak dapat dipastikan", result.title)
                self.assertTrue(result.instruction)
                self.assertFalse(result.can_review)
                self.assertNotIn("EPLUS_ISSUE:", result.instruction)
                self.assertNotEqual(report_summary({"status": status}), status)

    def test_startup_debug_does_not_leak_private_paths_or_account_data(self):
        examples = (
            (FileNotFoundError("setup_env.py is missing from C:/Users/private@example.com"), "setup_env.py"),
            (FileNotFoundError("C:/Users/private@example.com/private.json"), "File lokal"),
            (PermissionError("Access denied: /Users/private@example.com"), "Akses ditolak"),
            (RuntimeError("PowerShell was not found."), "PowerShell"),
            (RuntimeError("Token secret-private@example.com"), "kesalahan"),
        )
        for error, expected in examples:
            with self.subTest(error=type(error).__name__):
                diagnosis = safe_launch_diagnostic(error)
                self.assertIn(expected, diagnosis)
                self.assertNotIn("private@example.com", diagnosis)

    def test_macos_runtime_failures_are_mapped_to_safe_guidance(self):
        examples = {
            "ADB tidak ditemukan. Pasang Android SDK Platform-Tools.": "adb_missing",
            "Perangkat Android tidak terhubung. Periksa adb devices.": "device_missing",
            "Target 127.0.0.1:16384 masih offline": "device_missing",
            "Connection refused pada 127.0.0.1:16384": "device_missing",
            "Perangkat Android berubah sejak Step 1": "device_mismatch",
            "Lebih dari satu perangkat Android berbeda terdeteksi.": "device_ambiguous",
            "Frida 16.5.9 diperlukan": "frida_missing",
            "Akun Google Play berubah saat pemeriksaan": "account_mismatch",
            "Gagal membaca akun Google Play": "account_unavailable",
            "Gagal mengambil daftar penawaran": "offer_query_failed",
            "Penawaran Step 3 tidak memiliki fase awal nol (zero-priced first phase).": "offer_not_available",
            "Laporan hasil baru tidak ditemukan": "report_missing",
            "Cek lingkungan Android gagal": "environment_failed",
            "Explicit checkout and existing-plan confirmations required": "confirmation_required",
        }
        for error, code in examples.items():
            with self.subTest(code=code):
                result = runtime_error_outcome(error, 3)
                self.assertEqual(result.code, code)
                self.assertTrue(result.title)
                self.assertFalse(result.can_review)
        fallback = runtime_error_outcome("Unexpected private error@example.com", 2)
        self.assertEqual(fallback.code, "unknown")
        self.assertNotIn("error@example.com", fallback.instruction)

    def test_setup_only_when_pinned_frida_is_missing(self):
        with patch("tui_core.importlib.metadata.version", return_value="16.5.9"):
            self.assertFalse(needs_setup())
        with patch("tui_core.importlib.metadata.version", return_value="16.4.0"):
            self.assertTrue(needs_setup())
        from importlib.metadata import PackageNotFoundError
        with patch("tui_core.importlib.metadata.version", side_effect=PackageNotFoundError):
            self.assertTrue(needs_setup())

    def test_step_range(self):
        for step in range(5):
            self.assertEqual(validate_step(step), step)
        for value in (-1, 5, 6, "2", True):
            with self.assertRaises(ValueError):
                validate_step(value)

    def test_reuses_single_step_powershell_wrapper(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "run-all.ps1").write_text("# test")
            command = command_for_step(3, p, shell="powershell.exe")
            self.assertEqual(command[-4:], ["-File", str(p / "run-all.ps1"), "-Step", "3"])
            self.assertNotIn("-AllStages", command)
            self.assertNotIn("-Force", command)

    def test_windows_paid_command_pins_verified_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "run-all.ps1").write_text("# test", encoding="utf-8")
            command = command_for_step(3, root, shell="pwsh",
                                       account="alice@example.com", device="device-a")
            self.assertEqual(command[-4:], ["-Email", "alice@example.com", "-Serial", "device-a"])
            self.assertNotIn("-Force", command)

    def test_no_shell_or_script_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                command_for_step(1, Path(folder), shell="pwsh")

    def test_stale_and_foreign_reports_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "report"
            p.mkdir()
            f = p / "test.json"
            f.write_text(json.dumps({"status": "checkout_requested", "email": "alice@example.com"}))
            now = time.time()
            os.utime(f, (now - 600, now - 600))
            self.assertIsNone(read_fresh_report(p, 3, now, expected_account="alice@example.com"))
            self.assertFalse(outcome_for_stage(3, 0, None).can_review)

    def test_one_fresh_checkout_report_can_be_reviewed(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            started_at = time.time() - 10
            (p / "account.json").write_text(
                json.dumps({"status": "checkout_requested", "email": "alice@example.com",
                            "sheet": {"confirmed": True, "reason": "zero_today_and_duration_verified"}}))
            report = read_fresh_report(p, 3, started_at, expected_account="alice@example.com")
            self.assertIsNotNone(report)
            self.assertTrue(outcome_for_stage(3, 0, report).can_review)

    def test_account_mask(self):
        self.assertEqual(mask_email("example@gmail.com"), "ex***@gmail.com")
        self.assertEqual(mask_email("invalid"), "Belum terdeteksi")


class TextualDashboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tui import GoogleAITUI
        patcher = patch.object(GoogleAITUI, "_poll_connection")
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_branding_is_xtoolkit_diego_without_support_or_credits(self):
        from textual.widgets import Static
        from tui import GoogleAITUI

        self.assertEqual(GoogleAITUI.TITLE, "XToolKit-Diego")
        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch("tui.subprocess.Popen") as popen:
                async with app.run_test(size=(110, 35)) as pilot:
                    await pilot.pause()
                    self.assertIn("XToolKit-Diego", str(app.query_one("#app_title", Static).render()))
                    # Support, Original, dan Maintained harus sudah dihapus sepenuhnya dari UI
                    self.assertFalse(app.query("#support_link"))
                    self.assertFalse(app.query("#support_label"))
                    self.assertFalse(app.query("#original_author"))
                    self.assertFalse(app.query("#maintainer"))
                    self.assertFalse(app.query("#credit"))
                popen.assert_not_called()

    async def test_realtime_technical_log_is_automatically_shown_and_formatted(self):
        from textual.widgets import RichLog, Static
        from tui import GoogleAITUI

        for size in ((110, 35), (90, 20)):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                app = GoogleAITUI(repo=Path(directory))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    log = app.query_one("#debug_log", RichLog)
                    panel = app.query_one("#console_panel")
                    self.assertTrue(app.debug_visible)
                    self.assertTrue(panel.display)
                    self.assertTrue(log.display)
                    self.assertGreater(log.region.height, 2)
                    self.assertLessEqual(panel.region.bottom, size[1])
                    app._received("ADB: Menjalankan `adb start-server`...")
                    app._received("Account diego@gmail.com")
                    app._received("EPLUS_ISSUE:launch_failed")
                    await pilot.pause()
                    all_text = "\n".join(line.text for line in log.lines)
                    self.assertIn("[ADB", all_text)
                    self.assertIn("di***@gmail.com", all_text)
                    self.assertNotIn("diego@gmail.com", all_text)
                    self.assertNotIn("EPLUS_ISSUE:", all_text)
                    self.assertIn("baris", str(app.query_one("#log_meta", Static).render()))

    async def test_step1_auto_continues_instantly_to_step2_without_confirmation(self):
        from tui import GoogleAITUI, Approval, CheckComplete
        from tui_core import Outcome

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            started_steps = []

            def fake_run_stage(step):
                started_steps.append(step)

            with patch.object(GoogleAITUI, "run_stage", side_effect=fake_run_stage):
                async with app.run_test(size=(110, 35)) as pilot:
                    self.assertTrue(app.auto_step2)
                    # Klik tombol utama memulai Step 1 dan mengaktifkan auto-lanjut Step 2
                    await pilot.click("#quickstart")
                    await pilot.pause()
                    self.assertEqual(started_steps, [1])
                    self.assertTrue(app._auto_continue_armed)

                    # Simulasikan Step 1 selesai dengan penawaran 12months-eft Rp0
                    app._received("Device 127.0.0.1:16384")
                    app._verified_account = "diego@gmail.com"
                    app._finished(1, Outcome("listed", "Penawaran berhasil dimuat", "Siap."), {
                        "status": "listed",
                        "detected_play_account": "diego@gmail.com",
                        "offers": [{"id": "12months-eft", "micros": "0", "period": "P1Y"}],
                    })
                    await pilot.pause()

                    # Harus LANGSUNG menjalankan Step 2 tanpa popup CheckComplete maupun Approval
                    self.assertNotIsInstance(app.screen, CheckComplete)
                    self.assertNotIsInstance(app.screen, Approval)
                    self.assertEqual(started_steps, [1, 2])
                    self.assertTrue(app.busy)
                    self.assertEqual(app.current_step, 2)

    async def test_manual_mode_still_shows_indonesian_modals_when_toggled_off(self):
        from tui import GoogleAITUI, Approval, CheckComplete
        from tui_core import Outcome

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch.object(GoogleAITUI, "run_stage") as run:
                async with app.run_test(size=(110, 35)) as pilot:
                    await pilot.click("#auto_toggle")
                    await pilot.pause()
                    self.assertFalse(app.auto_step2)

                    app._received("Device 127.0.0.1:16384")
                    app._verified_account = "diego@gmail.com"
                    app._finished(1, Outcome("listed", "Penawaran berhasil dimuat", "Siap."), {
                        "status": "listed",
                        "detected_play_account": "diego@gmail.com",
                        "offers": [{"id": "12months-eft", "micros": "0", "period": "P1Y"}],
                    })
                    await pilot.pause()
                    self.assertIsInstance(app.screen, CheckComplete)
                    run.assert_not_called()
                    await pilot.click("#check_continue")
                    await pilot.pause()
                    self.assertIsInstance(app.screen, Approval)
                    run.assert_not_called()

    async def test_stop_button_is_always_visible_when_busy_and_stops_any_step(self):
        from textual.widgets import Button
        from tui import GoogleAITUI
        from device_diagnostics import ConnectionStatus

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch.object(GoogleAITUI, "run_stage"), \
                 patch.object(GoogleAITUI, "terminate_running_child") as kill_child:
                async with app.run_test(size=(110, 35)) as pilot:
                    # Step 1 berjalan dengan panel manual TERTUTUP -> tombol Hentikan tetap HARUS tampil!
                    self.assertFalse(app.query_one("#workflow_actions").display)
                    app._auto_continue_armed = True
                    app._start(1, False)
                    await pilot.pause()
                    stop_btn = app.query_one("#stop", Button)
                    self.assertTrue(stop_btn.display)
                    self.assertFalse(stop_btn.disabled)
                    self.assertGreater(stop_btn.region.width, 10)

                    await pilot.click("#stop")
                    await pilot.pause()
                    self.assertTrue(app._cancel_requested)
                    self.assertFalse(app._auto_continue_armed)
                    kill_child.assert_called_once()

                    # Step 2 juga harus bisa dihentikan saat user menekan Hentikan
                    kill_child.reset_mock()
                    app.busy = False
                    app._cancel_requested = False
                    app._offer_check_ready = True
                    app._offer_ready_device = "127.0.0.1:16384"
                    app._connection_state = ConnectionStatus("connected", ("127.0.0.1:16384",))
                    app._start(2, True)
                    await pilot.pause()
                    self.assertTrue(stop_btn.display)
                    await pilot.click("#stop")
                    await pilot.pause()
                    self.assertTrue(app._cancel_requested)
                    kill_child.assert_called_once()

    async def test_recover_adb_button_recovers_device_and_updates_ui(self):
        from textual.widgets import Static
        from device_diagnostics import AdbRecoveryResult
        from tui import GoogleAITUI

        fake_result = AdbRecoveryResult(
            ok=True,
            state="connected",
            devices=("127.0.0.1:16384",),
            headline="Koneksi ADB berhasil dipulihkan",
            guidance="Perangkat aktif: 127.0.0.1:16384.",
        )

        def fake_recover(*args, **kwargs):
            log = kwargs.get("log")
            if log:
                log("ADB: Menjalankan `adb start-server`...")
                log("ADB: `adb devices` -> 127.0.0.1:16384 [ONLINE ✔]")
            return fake_result

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch("tui.recover_adb_connection", side_effect=fake_recover):
                async with app.run_test(size=(110, 35)) as pilot:
                    initial_logs = len(app._last_output)
                    # Toggle mode Auto Step 2 tidak boleh menambah log teknis
                    await pilot.click("#auto_toggle")
                    await pilot.pause()
                    self.assertEqual(len(app._last_output), initial_logs)

                    # Proses Perbaiki ADB juga tidak boleh memenuhi log teknis
                    await pilot.click("#recover_adb")
                    for _ in range(30):
                        await pilot.pause(0.05)
                        if not app._recovering_adb:
                            break
                    self.assertFalse(app._recovering_adb)
                    self.assertEqual(len(app._last_output), initial_logs)
                    self.assertIn("127.0.0.1:16384", str(app.query_one("#device", Static).render()))
                    self.assertIn("berhasil dipulihkan", str(app.query_one("#state", Static).render()))

    async def test_start_screen_layout_fits_compact_and_normal_terminals(self):
        from tui import GoogleAITUI

        for size in ((90, 20), (110, 35), (120, 38)):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                app = GoogleAITUI(repo=Path(directory))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    action = app.query_one("#quickstart").region
                    status = app.query_one("#status_panel").region
                    console = app.query_one("#console_panel").region
                    self.assertGreaterEqual(action.y, 0)
                    self.assertLessEqual(action.bottom, size[1])
                    self.assertGreater(status.height, 3)
                    self.assertGreater(console.height, 3)
                    self.assertLessEqual(console.bottom, size[1])

    async def test_connection_monitor_handles_offline_and_recovers(self):
        from tui import GoogleAITUI, ConnectionNotice
        from device_diagnostics import ConnectionStatus
        from textual.widgets import Static

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            async with app.run_test(size=(110, 35)) as pilot:
                app._offer_check_ready = True
                app._connection_polled(ConnectionStatus("offline", (), offline_devices=("127.0.0.1:16384",)))
                await pilot.pause()
                self.assertIsInstance(app.screen, ConnectionNotice)
                self.assertFalse(app._offer_check_ready)
                self.assertIn("OFFLINE", str(app.query_one("#device", Static).render()))

                app._connection_polled(ConnectionStatus("connected", ("127.0.0.1:16384",)))
                await pilot.pause()
                self.assertNotIsInstance(app.screen, ConnectionNotice)
                self.assertIn("127.0.0.1:16384", str(app.query_one("#device", Static).render()))

    async def test_steps_2_to_4_billing_flow_ok_mark_success_and_enable_reinject(self):
        from textual.widgets import Button, Static
        from device_diagnostics import ConnectionStatus
        from tui import GoogleAITUI

        for step in (2, 3, 4):
            with self.subTest(step=step), tempfile.TemporaryDirectory() as directory:
                app = GoogleAITUI(repo=Path(directory))
                started = []

                def fake_run(current_step):
                    started.append((current_step, app._reinject_mode))

                with patch.object(GoogleAITUI, "run_stage", side_effect=fake_run):
                    async with app.run_test(size=(135, 42)) as pilot:
                        app._offer_check_ready = True
                        app._offer_ready_device = "127.0.0.1:16384"
                        app._offer_ready_account = "diego@gmail.com"
                        app._connection_state = ConnectionStatus("connected", ("127.0.0.1:16384",))
                        app._start(step, True)
                        await pilot.pause()
                        self.assertEqual(started, [(step, False)])

                        # Simulasikan respons live Google Play Billing terbuka (`code: 0`)
                        app._received("   ✅ Google Play billing flow response: {'ev': 'launched', 'code': 0, 'msg': ''}")
                        await pilot.pause()
                        self.assertEqual(app._billing_opened_step, step)
                        self.assertIn(f"step {step}", str(app.query_one("#state", Static).render()).lower())
                        self.assertIn("lanjutkan pembayaran", str(app.query_one("#state", Static).render()).lower())

                        # Selesai dengan status billing_opened -> tampilkan tombol Inject Ulang Step N
                        app._finished(
                            step,
                            outcome_for_stage(step, 0, {"status": "billing_opened"}),
                            {"status": "billing_opened"},
                        )
                        await pilot.pause()
                        reinject_btn = app.query_one("#reinject_billing", Button)
                        next_btn = app.query_one("#next", Button)
                        self.assertTrue(reinject_btn.display)
                        self.assertFalse(reinject_btn.disabled)
                        self.assertEqual(str(reinject_btn.label), f"↻ Inject Ulang Step {step}")
                        self.assertEqual(reinject_btn.region.height, 3)
                        if step < 4:
                            self.assertTrue(next_btn.display)
                            self.assertEqual(reinject_btn.region.y, next_btn.region.y)
                        else:
                            self.assertFalse(next_btn.display)

                        # Klik Inject Ulang -> jalankan Step N dalam mode reinject cepat
                        await pilot.click("#reinject_billing")
                        await pilot.pause()
                        self.assertEqual(started, [(step, False), (step, True)])
                        self.assertTrue(app.busy)
                        self.assertEqual(app.current_step, step)

    async def test_silent_adb_auto_recovery_never_leaves_button_stuck_on_recovering(self):
        from textual.widgets import Button
        from device_diagnostics import AdbRecoveryResult
        from tui import GoogleAITUI

        with tempfile.TemporaryDirectory() as directory:
            app = GoogleAITUI(repo=Path(directory))
            with patch.object(GoogleAITUI, "_run_adb_recovery_worker"):
                async with app.run_test(size=(110, 35)) as pilot:
                    app._start_adb_recovery(force_reset=False, silent=True)
                    app._tick_realtime()
                    # Background silent recovery tidak boleh membajak label tombol utama
                    self.assertNotIn("Memulihkan ADB", str(app.query_one("#quickstart", Button).label))

                    # Sekalipun label sempat berubah, saat ADB pulih tombol wajib kembali normal
                    app.query_one("#quickstart", Button).label = "⠋ Memulihkan ADB… 2d"
                    app._adb_recovery_done(
                        AdbRecoveryResult(ok=True, state="connected", devices=("127.0.0.1:16384",)),
                        silent=True,
                    )
                    await pilot.pause()
                    self.assertFalse(app._recovering_adb)
                    self.assertFalse(app.query_one("#quickstart", Button).disabled)
                    self.assertEqual(str(app.query_one("#quickstart", Button).label), "▶ Cek & Lanjut Step 2")


if __name__ == "__main__":
    unittest.main()
