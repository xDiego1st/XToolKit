"""No-device Frida target selection and subscription state regression tests."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

source = Path(__file__).resolve().parents[1] / "ultra0.py"
spec = importlib.util.spec_from_file_location("original_flow_guardrails", source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def mock_dev(device_id, name="com.google.android.apps.subscriptions.red"):
    device = MagicMock()
    device.id = device_id
    device.type = "usb"
    device.get_process.return_value = types.SimpleNamespace(name=name)
    return device


class OriginalFlowGuardrails(unittest.TestCase):
    def test_offer_check_restarts_google_one_once_when_startup_fails(self):
        for pid, status in ((456, "listed"), (0, "app_not_started")):
            with self.subTest(pid=pid), \
                 patch.object(mod, "current_play_account", return_value="test@example.com"), \
                 patch.object(mod, "launch_app", side_effect=[0, pid]) as launch, \
                 patch.object(mod, "query_offers_with_recovery",
                              return_value={"offers": [{"id": "test"}]}) as offers, \
                 patch.object(mod, "confirm_zero") as checkout:
                result = mod.process("current@device", add=False, list_only=True)
                self.assertEqual(result["status"], status)
                self.assertEqual(launch.call_count, 2)
                if pid:
                    self.assertEqual(offers.call_args.args[0], pid)
                else:
                    offers.assert_not_called()
                checkout.assert_not_called()

    def test_paid_stage_does_not_retry_google_one_startup(self):
        with patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=0) as launch, \
             patch.object(mod, "run_trial") as checkout:
            result = mod.process("test@example.com", add=False, no_switch=True)
        self.assertEqual(result["status"], "app_not_started")
        launch.assert_called_once()
        checkout.assert_not_called()

    def test_read_only_transient_frida_failure_restarts_once(self):
        class TransportError(Exception):
            pass
        frida = types.SimpleNamespace(TransportError=TransportError)
        expected = {"offers": [{"id": "test"}]}
        with patch.dict(sys.modules, {"frida": frida}), \
             patch.object(mod, "run_trial", side_effect=[TransportError(), expected]) as run, \
             patch.object(mod, "ensure_frida_server") as server, \
             patch.object(mod, "launch_app", return_value=456):
            self.assertEqual(mod.query_offers_with_recovery(123, plan="pro12"), expected)
        server.assert_called_once()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0], 456)
        self.assertTrue(run.call_args.kwargs["list_only"])

    def test_unknown_failure_is_not_retried(self):
        with patch.dict(sys.modules, {"frida": types.SimpleNamespace()}), \
             patch.object(mod, "run_trial", side_effect=RuntimeError("wrong device")) as run, \
             patch.object(mod, "ensure_frida_server") as server:
            with self.assertRaisesRegex(RuntimeError, "wrong device"):
                mod.query_offers_with_recovery(123)
        run.assert_called_once()
        server.assert_not_called()

    def test_google_play_unavailable_is_not_eligibility_proof(self):
        result = mod.assess_checkout_terms("Error The item you requested is not available for purchase. Got it")
        self.assertEqual(result["reason"], "purchase_unavailable")

    def test_error_after_subscribe_is_not_reported_as_submitted(self):
        # Google Play can present ITEM_UNAVAILABLE after the Subscribe tap.
        pages = iter([
            "Google AI Pro Subscribe Due today US$0 12-month trial",
            "Error The item you requested is not available for purchase. Got it",
        ])
        with patch.object(mod, "ui_xml", side_effect=lambda: next(pages)), \
             patch.object(mod, "nodes", side_effect=lambda page: [{"text": page, "desc": ""}]), \
             patch.object(mod, "tap_text", return_value=True) as tapped, \
             patch.object(mod.time, "sleep"):
            result = mod.confirm_zero(wait=4, expected_plan="pro12")
        tapped.assert_called_once()
        self.assertEqual(result["reason"], "purchase_unavailable")
        self.assertFalse(result["confirmed"])
        self.assertTrue(result["ineligible"])

    def test_unverified_terms_after_subscribe_revoke_confirmation(self):
        for screen, reason in (
                ("Google AI Pro Subscribe Due today US$1 12-month trial", "today_price_unverified"),
                ("Google AI Pro Subscribe Due today US$0 limited trial", "trial_duration_unverified")):
            with self.subTest(reason=reason):
                pages = iter([
                    "Google AI Pro Subscribe Due today US$0 12-month trial", screen,
                ])
                with patch.object(mod, "ui_xml", side_effect=lambda: next(pages)), \
                     patch.object(mod, "nodes", side_effect=lambda page: [{"text": page, "desc": ""}]), \
                     patch.object(mod, "tap_text", return_value=True), \
                     patch.object(mod.time, "sleep"):
                    result = mod.confirm_zero(wait=4, expected_plan="pro12")
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["confirmed"])

    def test_checkout_refuses_account_without_explicit_payer_label(self):
        page = "Google AI Pro alice@example.com Subscribe Due today US$0 12-month trial"
        with patch.object(mod, "ui_xml", return_value=page), \
             patch.object(mod, "nodes", side_effect=lambda page: [{"text": page, "desc": ""}]), \
             patch.object(mod, "tap_text") as tapped:
            result = mod.confirm_zero(wait=2, expected_plan="pro12", expected_account="alice@example.com")
        self.assertEqual(result["reason"], "checkout_account_unverified")
        tapped.assert_not_called()

    def test_backup_payment_prompt_after_subscribe_is_not_success(self):
        screens = iter([
            "Google AI Pro Subscribe Today US$0 12-month free trial",
            "Google Play Turn on backup payment methods? Manage Turn on",
        ])
        with patch.object(mod, "ui_xml", side_effect=lambda: next(screens)), \
             patch.object(mod, "nodes", side_effect=lambda page: [{"text": page, "desc": ""}]), \
             patch.object(mod, "tap_text", return_value=True), \
             patch.object(mod.time, "sleep"):
            result = mod.confirm_zero(wait=4, expected_plan="pro12")
        self.assertEqual(result["reason"], "backup_payment_methods_prompt")
        self.assertFalse(result["confirmed"])

    def test_posttap_error_status_is_preserved_without_verification_navigation(self):
        with patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "run_trial", return_value={
                 "offers": [{"id": "12months-eft", "micros": "0"}],
                 "launched": {"code": 0}, "purchase": None, "errors": [],
                 "chosen_offer": {"id": "12months-eft"}}), \
             patch.object(mod, "confirm_zero", return_value={
                 "confirmed": False, "reason": "purchase_unavailable"}) as check, \
             patch.object(mod, "verify") as verify:
            report = mod.process("test@example.com", add=False, no_switch=True, plan="pro12")
        self.assertEqual(report["status"], "purchase_unavailable")
        check.assert_called_once()
        verify.assert_not_called()

    def test_purchase_callback_rejection_takes_priority_over_launch_ok(self):
        with patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "run_trial", return_value={
                 "offers": [], "launched": {"code": 0}, "purchase": {"code": 4},
                 "chosen_offer": {"id": "12months-eft"}, "errors": []}), \
             patch.object(mod, "confirm_zero") as check, \
             patch.object(mod, "verify") as verify:
            report = mod.process("test@example.com", add=False, no_switch=True, plan="pro12")
        self.assertEqual(report["status"], "purchase_unavailable")
        check.assert_not_called()
        verify.assert_not_called()

    def test_wrong_or_missing_selected_offer_stops_before_subscribe(self):
        for chosen in (None, {"id": "12months-eft"}, {"id": "other"}):
            with self.subTest(chosen=chosen):
                with patch.object(mod, "current_play_account", return_value="test@example.com"), \
                     patch.object(mod, "launch_app", return_value=123), \
                     patch.object(mod, "run_trial", return_value={
                         "offers": [{"id": "6months-eft", "micros": "0"}],
                         "chosen_offer": chosen, "launched": {"code": 0},
                         "purchase": None, "errors": []}), \
                     patch.object(mod, "confirm_zero") as check, \
                     patch.object(mod, "verify") as verify:
                    report = mod.process("test@example.com", add=False, no_switch=True, plan="pro6")
                self.assertEqual(report["status"], "offer_not_available")
                check.assert_not_called()
                verify.assert_not_called()

    def test_android_account_inventory_is_deduplicated_and_not_active_play_identity(self):
        entries = [
            "Account {name=First@Gmail.com, type=com.google}",
            "Account {name=second@example.com, type=com.google}",
            "Account {name=FIRST@gmail.com, type=com.google}",
            "Account {name=third@example.com, type=com.other}",
            "hidden Account {name=REDACTED, type=com.google}",
        ]
        with patch.object(mod, "accounts_on_device", return_value=entries):
            self.assertEqual(mod.available_google_accounts(), [
                "first@gmail.com", "second@example.com"
            ])

    def test_play_account_refuses_ambiguous_multi_account_profile(self):
        def fake_nodes(xml):
            if 'com.android.vending' in xml:
                return [{"desc": "Account and settings", "text": "", "x": 10, "y": 20}]
            return [
                {"desc": "Primary one@example.com", "text": ""},
                {"desc": "Other two@example.com", "text": ""},
            ]

        with patch.object(mod, "ui_xml", side_effect=[
                 '<node package="com.android.vending"/>', 'PROFILE'
             ]), \
             patch.object(mod, "nodes", side_effect=fake_nodes), \
             patch.object(mod, "tap"), \
             patch.object(mod.time, "sleep"), \
             patch.object(mod, "sh") as shell:
            self.assertEqual(mod.current_play_account(), "")
        shell.assert_called_with("shell", "input keyevent 4")

    def test_play_account_accepts_only_one_visible_profile_account(self):
        with patch.object(mod, "ui_xml", side_effect=[
                 '<node package="com.android.vending"/>', 'PROFILE'
             ]), \
             patch.object(mod, "nodes", side_effect=[
                 [{"desc": "Account and settings", "text": "", "x": 10, "y": 20}],
                 [{"desc": "one@example.com", "text": ""},
                  {"desc": "one@example.com", "text": ""}]
             ]), \
             patch.object(mod, "tap"), \
             patch.object(mod.time, "sleep"), \
             patch.object(mod, "sh"):
            self.assertEqual(mod.current_play_account(), "one@example.com")

    def test_play_account_rejects_email_without_opening_profile(self):
        with patch.object(mod, "ui_xml", side_effect=[
                 '<node package="com.android.vending"/>', 'MAIN'
             ]), \
             patch.object(mod, "nodes", side_effect=[
                 [{"desc": "Unrelated label", "text": "", "x": 10, "y": 20}],
                 [{"desc": "one@example.com", "text": ""}]
             ]), \
             patch.object(mod, "sh"):
            self.assertEqual(mod.current_play_account(), "")

    def test_offer_tokens_are_never_saved_in_reports(self):
        device = MagicMock()
        session = MagicMock()
        script = MagicMock()
        device.attach.return_value = session
        session.create_script.return_value = script
        callbacks = {}
        script.on.side_effect = lambda event, handler: callbacks.setdefault(event, handler)

        def simulate_offer(_wait):
            callbacks["message"]({
                "type": "send", "payload": {
                    "ev": "offer", "product": "g1.2tb.ai.subs_variant",
                    "id": "12months-eft", "micros": "0", "period": "P1Y",
                    "token": "private-token", "title": "private-title",
                },
            }, None)

        with patch.object(mod, "get_target_frida_device", return_value=device), \
             patch.object(mod.time, "sleep", side_effect=simulate_offer):
            report = mod.run_trial(123, list_only=True)
        self.assertEqual(report["offers"][0]["id"], "12months-eft")
        self.assertNotIn("token", report["offers"][0])
        self.assertNotIn("title", report["offers"][0])
        session.detach.assert_called_once()

    def test_frida_remains_attached_during_subscribe_observation(self):
        device = MagicMock()
        session = MagicMock()
        script = MagicMock()
        device.attach.return_value = session
        session.create_script.return_value = script
        callbacks = {}
        script.on.side_effect = lambda event, handler: callbacks.setdefault(event, handler)

        def signal(_wait):
            callbacks["message"]({"type": "send",
                                  "payload": {"ev": "chosen", "id": "12months-eft"}}, None)
            callbacks["message"]({"type": "send",
                                  "payload": {"ev": "launched", "code": 0}}, None)

        def observe():
            session.detach.assert_not_called()
            callbacks["message"]({"type": "send",
                                  "payload": {"ev": "purchase_cb", "code": 4}}, None)
            return {"confirmed": False, "reason": "purchase_unavailable"}

        with patch.object(mod, "get_target_frida_device", return_value=device), \
             patch.object(mod.time, "sleep", side_effect=signal):
            report = mod.run_trial(123, wait=1, plan="pro12",
                                   post_launch=observe)
        self.assertEqual(report["sheet"]["reason"], "purchase_unavailable")
        self.assertEqual(report["purchase"]["code"], 4)
        session.detach.assert_called_once()

    def test_paid_stage_does_not_use_read_only_recovery(self):
        with patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "query_offers_with_recovery") as recover, \
             patch.object(mod, "run_trial", side_effect=RuntimeError("connection lost")) as run:
            with self.assertRaisesRegex(RuntimeError, "connection lost"):
                mod.process("test@example.com", add=False, no_switch=True)
        run.assert_called_once()
        recover.assert_not_called()

    def test_session_is_detached_on_script_failure(self):
        session = MagicMock()
        session.create_script.side_effect = RuntimeError("script failure")
        device = MagicMock()
        device.attach.return_value = session
        with patch.object(mod, "get_target_frida_device", return_value=device):
            with self.assertRaisesRegex(RuntimeError, "script failure"):
                mod.run_trial(123, list_only=True)
        session.detach.assert_called_once()

    def test_serial_match_takes_precedence(self):
        devices = [mock_dev("127.0.0.1:16384"), mock_dev("emulator-5554")]
        module = types.SimpleNamespace(get_device_manager=lambda: types.SimpleNamespace(
            enumerate_devices=lambda: devices))
        with patch.dict(sys.modules, {"frida": module}), \
             patch.object(mod, "verify_adb_target_pid", return_value=mod.PKG):
            self.assertIs(mod.get_target_frida_device(123, "emulator-5554"), devices[1])

    def test_different_frida_devices_do_not_default_to_first(self):
        devices = [mock_dev("device-a"), mock_dev("device-b")]
        module = types.SimpleNamespace(get_device_manager=lambda: types.SimpleNamespace(
            enumerate_devices=lambda: devices))
        with patch.dict(sys.modules, {"frida": module}):
            with self.assertRaisesRegex(RuntimeError, "Cannot map ADB serial"):
                mod.get_target_frida_device(123, "emulator-5554")

    def test_frida_process_enumeration_failure_does_not_block_valid_adb_pid(self):
        device = mock_dev("emulator-5554")
        device.get_process.side_effect = RuntimeError("Android 15 process enumeration unavailable")
        module = types.SimpleNamespace(get_device_manager=lambda: types.SimpleNamespace(
            enumerate_devices=lambda: [device]))
        with patch.dict(sys.modules, {"frida": module}), \
             patch.object(mod, "verify_adb_target_pid", return_value=mod.PKG):
            self.assertIs(mod.get_target_frida_device(11004, "emulator-5554"), device)
        device.get_process.assert_not_called()

    def test_unrelated_adb_process_is_rejected(self):
        from unittest.mock import patch as mock_patch
        device = mock_dev("emulator-5554")
        module = types.SimpleNamespace(get_device_manager=lambda: types.SimpleNamespace(
            enumerate_devices=lambda: [device]))
        with patch.dict(sys.modules, {"frida": module}), \
             mock_patch.object(mod, "verify_adb_target_pid",
                               side_effect=RuntimeError("ADB PID 123 is unrelated")):
            with self.assertRaisesRegex(RuntimeError, "unrelated"):
                mod.get_target_frida_device(123, "emulator-5554")

    def test_missing_purchase_token_has_distinct_failure(self):
        s, message = mod.diagnose_launch_failure(
            {"launched": None, "errors": [{"ev": "no_purchase"}]})
        self.assertEqual(s, "subscription_update_unavailable")
        self.assertIn("token", message)

    def test_read_only_listing_saves_verified_play_account(self):
        with patch.dict(sys.modules, {"frida": types.SimpleNamespace()}), \
             patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "run_trial", return_value={
                 "offers": [{"id": "12months-eft", "micros": "0"}],
                 "launched": None, "errors": []}):
            result = mod.process("current@device", add=False, list_only=True, plan="pro12")
        self.assertEqual(result["status"], "listed")
        self.assertEqual(result["detected_play_account"], "test@example.com")

    def test_checkout_launch_is_not_subscription_activation(self):
        with patch.dict(sys.modules, {"frida": types.SimpleNamespace()}), \
             patch.object(mod, "current_play_account", return_value=""), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "run_trial", return_value={
                 "offers": [{"id": "12months-eft", "micros": "0"}], "launched": {"code": 0}, "errors": [],
                 "purchase": None, "chosen_offer": {"id": "12months-eft"}}), \
             patch.object(mod, "confirm_zero", return_value={"confirmed": True}), \
             patch.object(mod, "verify", return_value="Google AI Pro subscription"):
            result = mod.process("current@device", add=False, list_only=True)
            self.assertEqual(result["status"], "listed")
        with patch.object(mod, "current_play_account", return_value="test@example.com"), \
             patch.object(mod, "launch_app", return_value=123), \
             patch.object(mod, "run_trial", return_value={
                 "offers": [{"id": "12months-eft", "micros": "0"}], "launched": {"code": 0}, "errors": [],
                 "purchase": None, "chosen_offer": {"id": "12months-eft"}}), \
             patch.object(mod, "confirm_zero", return_value={"confirmed": True}), \
             patch.object(mod, "verify", return_value="Google AI Pro subscription"):
            result = mod.process("test@example.com", add=False, no_switch=True)
        self.assertEqual(result["status"], "checkout_requested")


if __name__ == "__main__":
    unittest.main()
