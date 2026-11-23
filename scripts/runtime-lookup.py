#!/usr/bin/env python3
"""ASCII-only runtime discovery for Windows PowerShell and other terminals.

The original helpers print Unicode progress banners. Those outputs may fail in
cp1252 pipelines. Capture banners and emit only one Base64-encoded UTF-8 value.
No purchase, offer or payment operations are performed here.
"""
import argparse
import base64
import contextlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def resolve_value(command, serial=None):
    with contextlib.redirect_stdout(io.StringIO()):
        if command == "adb":
            import setup_env
            return str(setup_env.find_adb())
        if command == "device":
            import setup_env
            from device_selector import auto_select_device
            return auto_select_device(setup_env.find_adb()) or ""
        if command == "connect-device":
            import setup_env
            return setup_env.connect_emulator(setup_env.find_adb()) or ""
        if command in ("play-account", "play-accounts"):
            import ultra0
            ultra0.ADB = ultra0.find_adb()
            ultra0.pick_device(preferred=serial)
            if command == "play-accounts":
                # Candidate list only: not verified as current billing account.
                return json.dumps(ultra0.available_google_accounts(), separators=(",", ":"))
            return str(ultra0.current_play_account() or "")
    raise ValueError("Unsupported runtime lookup command")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ASCII-safe runtime metadata lookup")
    parser.add_argument("command", choices=("adb", "device", "connect-device", "play-account", "play-accounts"))
    parser.add_argument("--serial", help="ADB device serial (required for play-account)")
    args = parser.parse_args(argv)
    if args.command in ("play-account", "play-accounts") and not args.serial:
        parser.error("--serial is required for Play account lookup")
    try:
        value = resolve_value(args.command, args.serial)
    except (Exception, SystemExit) as exc:
        print("Runtime lookup failed ({0}); run python setup_env.py for ADB diagnostics.".format(
            type(exc).__name__), file=sys.stderr)
        return 1
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    print("RUNTIME_RESULT:" + encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
