"""Pure tests for cross-device selection and Activity method JS generation."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / "ultra0.py"
spec = importlib.util.spec_from_file_location("activity_config", source)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DeviceSelectionTests(unittest.TestCase):
    def setUp(self):
        app.ADB = "adb"

    def test_serial_selects_exact_online_device(self):
        devices = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"
        with patch.object(app, "sh", return_value=devices):
            app.pick_device(preferred="emulator-5556")
            self.assertEqual(app.SERIAL, "emulator-5556")

    def test_multiple_devices_require_serial(self):
        devices = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"
        with patch.object(app, "sh", return_value=devices):
            with self.assertRaises(SystemExit):
                app.pick_device()

    def test_offline_serial_is_rejected(self):
        devices = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n"
        with patch.object(app, "sh", return_value=devices):
            with self.assertRaises(SystemExit):
                app.pick_device(preferred="emulator-5556")


class ActivityMethodTests(unittest.TestCase):
    def test_default_auto(self):
        js = app.build_js(plan="pro12", list_only=True)
        self.assertIn('var ACTIVITY_METHOD="auto";', js)
        self.assertIn('if (ACTIVITY_METHOD !== "choose")', js)
        self.assertIn('current.mActivities.value', js)
        self.assertIn("Java.choose", js)

    def test_explicit_choose(self):
        js = app.build_js(activity_method="choose")
        self.assertIn('var ACTIVITY_METHOD="choose";', js)

    def test_explicit_thread(self):
        js = app.build_js(activity_method="thread")
        self.assertIn('var ACTIVITY_METHOD="thread";', js)

    def test_unexpected_mode_fails(self):
        with self.assertRaises(ValueError):
            app.build_js(activity_method="unsupported")


if __name__ == "__main__":
    unittest.main()
