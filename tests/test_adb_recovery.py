"""Pengujian offline untuk pemulihan ADB otomatis (offline, Connection refused, server macet)."""
import subprocess
import unittest
from unittest.mock import patch

import device_diagnostics as diag
import macos_runner


def proc(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class AdbRecoveryTests(unittest.TestCase):
    def test_recovers_from_offline_16384_and_connection_refused_via_server_reset(self):
        """Simulasi kasus nyata user: 127.0.0.1:16384 offline + Connection refused -> pulih online."""
        calls = []
        reset_done = {"value": False}

        def fake_run(adb, args, timeout=8):
            calls.append(args)
            if args == ["start-server"]:
                return proc()
            if args == ["kill-server"]:
                reset_done["value"] = True
                return proc()
            if args == ["disconnect"] or args[:1] == ["disconnect"]:
                return proc("disconnected everything\n")
            if args == ["devices"]:
                if not reset_done["value"]:
                    return proc("List of devices attached\n127.0.0.1:16384\toffline\n")
                if ["connect", "127.0.0.1:16384"] in calls[calls.index(["kill-server"]):]:
                    return proc("List of devices attached\n127.0.0.1:16384\tdevice\n")
                return proc("List of devices attached\n")
            if args[:1] == ["connect"]:
                target = args[1]
                if not reset_done["value"]:
                    return proc(
                        f"failed to connect to '{target}': Connection refused\n",
                        returncode=0,
                    )
                if target == "127.0.0.1:16384":
                    return proc(f"connected to {target}\n")
                return proc(f"failed to connect to '{target}': Connection refused\n")
            return proc()

        logs = []
        with patch.object(diag, "_run", side_effect=fake_run), \
             patch.object(diag, "_sleep_cancelable", return_value=False):
            res = diag.recover_adb_connection("adb", log=logs.append)

        self.assertTrue(res.ok)
        self.assertEqual(res.state, "connected")
        self.assertEqual(res.devices, ("127.0.0.1:16384",))
        self.assertIn(["start-server"], calls)
        self.assertIn(["disconnect", "127.0.0.1:16384"], calls)
        self.assertIn(["kill-server"], calls)
        self.assertIn(["connect", "127.0.0.1:16384"], calls)
        self.assertTrue(any("OFFLINE" in line for line in logs))

    def test_reports_connection_refused_clearly_when_emulator_is_not_listening(self):
        def fake_run(adb, args, timeout=8):
            if args[:1] == ["connect"]:
                return proc(f"failed to connect to '{args[1]}': Connection refused\n")
            if args == ["devices"]:
                return proc("List of devices attached\n")
            return proc()

        with patch.object(diag, "_run", side_effect=fake_run), \
             patch.object(diag, "_sleep_cancelable", return_value=False):
            res = diag.recover_adb_connection("adb", targets=("127.0.0.1:16384",))

        self.assertFalse(res.ok)
        self.assertEqual(res.state, "connection_refused")
        self.assertTrue(res.connection_refused)
        self.assertIn("127.0.0.1:16384", res.guidance)
        self.assertIn("Connection refused", res.headline)

    def test_reports_still_offline_when_device_stays_offline_after_full_reset(self):
        def fake_run(adb, args, timeout=8):
            if args == ["devices"]:
                return proc("List of devices attached\n127.0.0.1:16384\toffline\n")
            if args[:1] == ["connect"]:
                return proc("failed to connect to '127.0.0.1:16384': Connection refused\n")
            return proc()

        with patch.object(diag, "_run", side_effect=fake_run), \
             patch.object(diag, "_sleep_cancelable", return_value=False):
            res = diag.recover_adb_connection("adb", targets=("127.0.0.1:16384",))

        self.assertFalse(res.ok)
        self.assertEqual(res.state, "still_offline")
        self.assertIn("127.0.0.1:16384", res.offline_devices)
        self.assertIn("offline", res.guidance.lower())

    def test_recovery_can_be_cancelled_cleanly(self):
        with patch.object(diag, "_run", return_value=proc()):
            res = diag.recover_adb_connection("adb", cancel_check=lambda: True)
        self.assertFalse(res.ok)
        self.assertEqual(res.state, "cancelled")

    def test_macos_preflight_auto_recovers_when_no_device_online_initially(self):
        recovered = diag.AdbRecoveryResult(
            ok=True,
            state="connected",
            devices=("127.0.0.1:16384",),
            headline="Pulih",
            guidance="Terhubung",
        )
        with patch("macos_runner.shutil.which", return_value="/usr/local/bin/adb"), \
             patch("macos_runner.metadata.version", return_value="16.5.9"), \
             patch("macos_runner.online_serials", return_value=[]), \
             patch("macos_runner.recover_adb_connection", return_value=recovered) as rec, \
             patch("macos_runner.auto_select_device", return_value="127.0.0.1:16384"):
            adb, serial = macos_runner.preflight()
        self.assertEqual(adb, "/usr/local/bin/adb")
        self.assertEqual(serial, "127.0.0.1:16384")
        rec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
