#!/usr/bin/env python3
"""Read-only diagnostic for Android 15 ActivityThread, without checkout or Java.choose()."""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

GOOGLE_ONE = "com.google.android.apps.subscriptions.red"

# Deliberately no BillingClient, purchase APIs, Java.choose or UI clicking.
PROBE_JS = r"""
Java.perform(function () {
  try {
    var ActivityThread = Java.use("android.app.ActivityThread");
    var thread = ActivityThread.currentActivityThread();
    if (!thread) {
      send({kind:"activity_probe", status:"no_activity_thread"});
      return;
    }
    var records = thread.mActivities.value;
    var Record = Java.use("android.app.ActivityThread$ActivityClientRecord");
    var n = records.size();
    var found = [];
    var errors = [];
    for (var i = 0; i < n; i++) {
      try {
        var record = Java.cast(records.valueAt(i), Record);
        var activity = record.activity.value;
        if (activity) {
          found.push({
            className: String(activity.getClass().getName()),
            finishing: !!activity.isFinishing(),
            destroyed: !!activity.isDestroyed()
          });
        }
      } catch (e) {
        errors.push(String(e).slice(0, 180));
      }
    }
    send({kind:"activity_probe", status: found.length ? "ok" : "no_activity",
          recordCount:n, activities:found.slice(0, 10), errors:errors.slice(0, 5)});
  } catch (e) {
    send({kind:"activity_probe", status:"error", error:String(e).slice(0, 500)});
  }
});
"""


def parse_pid(output):
    """Accept only a single numeric Android PID."""
    value = output.strip()
    return int(value) if re.fullmatch(r"[1-9][0-9]*", value) else None


def main():
    parser = argparse.ArgumentParser(description="Read-only ActivityThread probe on MuMu/Android")
    parser.add_argument("--serial", required=True, help="ADB serial from 'adb devices', e.g. emulator-5554")
    args = parser.parse_args()
    adb = os.environ.get("ADB_PATH") or "adb"
    try:
        p = subprocess.run([adb, "-s", args.serial, "shell", "pidof", GOOGLE_ONE],
                           capture_output=True, text=True, timeout=15)
        pid = parse_pid(p.stdout)
        if not pid:
            print("Google One is not running. Open it manually in MuMu, then retry.")
            return 2
        # Use the same verified ADB/Frida mapping as the main offer query.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import ultra0 as main_cli
        main_cli.ADB = adb
        main_cli.SERIAL = args.serial
        dev = main_cli.get_target_frida_device(pid, args.serial)
        session = dev.attach(pid)
        done = threading.Event()
        outcome = {}
        def on_message(message, _data):
            if message.get("type") == "send":
                payload = message.get("payload")
                if isinstance(payload, dict) and payload.get("kind") == "activity_probe":
                    outcome.update(payload)
                    done.set()
            elif message.get("type") == "error":
                outcome.update({"status": "frida_script_error",
                                "error": str(message.get("description") or "Unknown Frida error")[:500]})
                done.set()
        try:
            js = session.create_script(PROBE_JS)
            js.on("message", on_message)
            js.load()
            if not done.wait(20):
                print("No ActivityThread response after 20 seconds; Google One may be paused.")
                return 4
            print(json.dumps(outcome, ensure_ascii=False, indent=2))
            return 0 if outcome.get("status") == "ok" else 5
        finally:
            session.detach()
    except (OSError, subprocess.TimeoutExpired, Exception) as exc:
        # No credential, offer token, or purchase information should be printed.
        print(f"Activity probe failed: {type(exc).__name__}: {str(exc)[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
