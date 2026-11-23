"""Pure Frida compatibility checks; no real Android or checkout."""
import importlib.util
import io
import lzma
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

script = Path(__file__).resolve().parents[1] / "ultra0.py"
spec = importlib.util.spec_from_file_location("google_ai_original", script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FridaCompatibilityTests(unittest.TestCase):
    def test_pinned_host_is_not_reinstalled(self):
        with patch("importlib.metadata.version", return_value="16.5.9"), patch.object(mod.subprocess, "run") as run:
            mod.ensure_frida_client()
            run.assert_not_called()

    def test_frida_17_downgrades_and_restarts(self):
        with patch("importlib.metadata.version", return_value="17.27.0"), \
             patch.dict(os.environ, {"ULTRA0_FRIDA_REPAIR_ATTEMPTED": "0"}), \
             patch.object(mod.subprocess, "run", return_value=MagicMock(returncode=0)), \
             patch.object(mod.os, "execv", side_effect=RuntimeError("mock process restart")) as restart:
            with self.assertRaisesRegex(RuntimeError, "mock process restart"):
                mod.ensure_frida_client()
            restart.assert_called_once()

    def test_failed_install_explains_error(self):
        with patch("importlib.metadata.version", return_value="17.27.0"), \
             patch.dict(os.environ, {"ULTRA0_FRIDA_REPAIR_ATTEMPTED": "0"}), \
             patch.object(mod.subprocess, "run", return_value=MagicMock(returncode=1, stderr="network error")), \
             patch.object(mod.os, "execv") as restart:
            with self.assertRaisesRegex(RuntimeError, "network error"):
                mod.ensure_frida_client()
            restart.assert_not_called()

    def test_matching_server_is_kept(self):
        def shell(*args, **kwargs):
            if "pidof frida-server" in args[-1]: return "4123"
            if "--version" in args[-1]: return "16.5.9"
            raise AssertionError(args)
        with patch.object(mod, "ensure_frida_client"), patch.object(mod, "sh", side_effect=shell) as adb:
            mod.ensure_frida_server()
            self.assertEqual(adb.call_count, 2)

    def test_mismatched_running_server_is_replaced(self):
        state = {"pid": "4123", "version": "17.27.0", "pushed": False}
        calls = []
        def shell(*args, **kwargs):
            command = " ".join(args)
            calls.append(command)
            if "pidof frida-server" in command: return state["pid"]
            if "--version" in command: return state["version"]
            if "getprop ro.product.cpu.abi" in command: return "x86_64"
            if "kill 4123" in command: state["pid"] = ""; return ""
            if args[0] == "push":
                state["pushed"] = True
                state["version"] = "16.5.9"
                return ""
            if "shell id" in command: return "uid=0(root)"
            if "nohup " in command: state["pid"] = "8200"; return ""
            if "chmod 755" in command: return ""
            raise AssertionError(args)
        compressed = lzma.compress(b"test binary; do not execute")
        with patch.object(mod, "ensure_frida_client"), patch.object(mod, "sh", side_effect=shell), \
             patch.object(mod.time, "sleep"), patch("urllib.request.urlopen", return_value=io.BytesIO(compressed)):
            mod.ensure_frida_server()
        self.assertTrue(state["pushed"])
        self.assertEqual(state["pid"], "8200")
        self.assertTrue(any("kill 4123" in c for c in calls))


if __name__ == "__main__":
    unittest.main()
