"""ADB installer checks: no network access, Android device, or real ADB."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_env", ROOT / "setup_env.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def fake_official_zip():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("platform-tools/adb.exe", b"test not a real executable")
        archive.writestr("platform-tools/AdbWinApi.dll", b"test")
    return io.BytesIO(data.getvalue())


class AdbSetupTests(unittest.TestCase):
    def test_existing_local_adb_is_reused_without_download(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adb = root / "platform-tools" / "adb.exe"
            adb.parent.mkdir()
            adb.write_bytes(b"existing in-use adb")
            with patch.object(installer, "BASE", root), \
                 patch.object(installer, "user_platform_tools", return_value=root / "cache"), \
                 patch.object(installer, "adb_is_working", side_effect=lambda p: Path(p) == adb), \
                 patch.object(installer.urllib.request, "urlopen") as download:
                self.assertEqual(installer.find_adb(), str(adb))
                download.assert_not_called()

    def test_invalid_executable_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            adb = Path(temp) / "adb.exe"
            adb.write_bytes(b"not an executable")
            with patch.object(installer.subprocess, "run", side_effect=OSError("invalid")):
                self.assertFalse(installer.adb_is_working(adb))

    def test_locked_project_file_uses_per_user_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project_dir = root / "platform-tools"
            cache_dir = root / "user" / "platform-tools"
            real_copytree = installer.shutil.copytree
            def copytree(source, dest, **kwargs):
                if Path(dest) == project_dir:
                    raise PermissionError(13, "Permission denied", str(project_dir / "adb.exe"))
                return real_copytree(source, dest, **kwargs)
            def working(adb):
                return Path(adb) == cache_dir / "adb.exe" and Path(adb).exists()
            with patch.object(installer, "BASE", root), \
                 patch.object(installer, "user_platform_tools", return_value=cache_dir), \
                 patch.object(installer, "adb_is_working", side_effect=working), \
                 patch.object(installer.urllib.request, "urlopen", return_value=fake_official_zip()), \
                 patch.object(installer.shutil, "copytree", side_effect=copytree):
                result = installer.download_platform_tools()
                self.assertEqual(result, str(cache_dir / "adb.exe"))
            self.assertTrue((cache_dir / "AdbWinApi.dll").exists())

    def test_preflight_uses_explicit_serial(self):
        class MockResult:
            returncode = 0
            stdout = "Success"
            stderr = ""
        with patch.object(installer.subprocess, "run", return_value=MockResult()) as called:
            self.assertTrue(installer.run_check("C:/adb.exe", "emulator-5554"))
        self.assertIn("--serial", called.call_args.args[0])
        self.assertIn("emulator-5554", called.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
