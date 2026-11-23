"""Regression checks for extracted Frida and DEX assets; no Android operations."""
import base64
import importlib.util
import io
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ultra0_assets", ROOT / "ultra0.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class EmbeddedAssetsTests(unittest.TestCase):
    def test_frida_hook_exists_and_is_loaded(self):
        expected = (ROOT / "assets/frida/billing.js").read_text(encoding="utf-8")
        self.assertEqual(app.FRIDA_JS, expected)
        self.assertIn("function getActivity()", app.FRIDA_JS)
        self.assertIn("function launch(", app.FRIDA_JS)
        self.assertIn('var ACTIVITY_METHOD="auto";', app.FRIDA_JS)

    def test_dex_archive_decodes(self):
        content = (ROOT / "assets/modules/module_521.b64").read_text(encoding="ascii").strip()
        self.assertEqual(app.MODULE_B64, content)
        decoded = base64.b64decode(content, validate=True)
        with zipfile.ZipFile(io.BytesIO(decoded)) as bundle:
            self.assertIn("classes.dex", bundle.namelist())

    def test_loading_not_dependent_on_working_directory(self):
        # The absolute Path(__file__) resolver keeps resource locations stable.
        self.assertTrue((ROOT / "assets/frida/billing.js").exists())
        self.assertTrue((ROOT / "assets/modules/module_521.b64").exists())

    def test_cli_generation_works_after_extraction(self):
        for activity_method in ("auto", "choose", "thread"):
            script = app.build_js(plan="pro12", list_only=True, activity_method=activity_method)
            self.assertIn('var ACTIVITY_METHOD="%s";' % activity_method, script)
            self.assertIn("12months-eft", script)


if __name__ == "__main__":
    unittest.main()
