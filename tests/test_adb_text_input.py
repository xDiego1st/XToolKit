"""Do not let user-entered text escape Android's adb shell command."""
import inspect
import shlex
import unittest
from unittest.mock import patch

import ultra0


class AndroidTextInputTests(unittest.TestCase):
    def test_input_is_quoted_as_one_literal_android_argument(self):
        for original in (
            "simple@example.com",
            "pa'ss with spaces",
            "hello; echo unsafe",
            "hello$(id)",
            "hello`id`",
            "a\"b\\c",
        ):
            with self.subTest(original=original), patch.object(ultra0, "sh") as shell:
                ultra0.type_text(original)
                shell.assert_called_once()
                self.assertEqual(shell.call_args.args[0], "shell")
                parsed = shlex.split(shell.call_args.args[1])
                self.assertEqual(parsed, ["input", "text", original.replace(" ", "%s")])

    def test_totp_secret_must_not_be_written_to_debug_log(self):
        # We do not need real Google credentials or Android for this guard.
        source = inspect.getsource(ultra0.add_account)
        self.assertNotIn("Two-factor verification code: {code}", source)
        self.assertIn("type_text(code)", source)


if __name__ == "__main__":
    unittest.main()
