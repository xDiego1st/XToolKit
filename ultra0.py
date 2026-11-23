#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google AI subscription offer inspection and Android diagnostic CLI.

Usage:
        python ultra0.py --check            # Check Android, ADB, root and Frida
        python ultra0.py accounts.txt       # Legacy batch-account mode
        python ultra0.py --account address@example.com --no-add --no-switch

The legacy accounts.txt format uses four hyphens as a field separator:
    email----password----recovery----totp

Requirements:
        - A rooted Android device/emulator with ADB debugging
        - Google Play Store and Google One with the intended account
        - Python 3 and a compatible Frida client and server

WARNING: non-list mode can open Google Play checkout and tap Subscribe.
Offer metadata does not prove eligibility or subscription activation.
"""
import argparse, base64, hashlib, hmac, json, os, re, struct, subprocess, sys, threading, time
import shlex
from pathlib import Path
import tempfile

# Standalone launches may use a Windows legacy console code page that cannot
# encode status symbols. Preserve the console's encoding, but escape unsupported
# characters rather than aborting ADB/device checks with UnicodeEncodeError.
# The PowerShell launcher separately forces UTF-8 for its piped Python children.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="backslashreplace")

# Manual confirmation gate for an unfamiliar Android verification screen.
HUMAN_EVENT = threading.Event()
WAITING = {"on": False, "msg": ""}


def wait_human(msg: str, timeout: int = 600) -> bool:
    """Wait for explicit Enter/approval; never assume success on timeout.

    Windows select.select() cannot poll regular console/pipe stdin, while the
    Textual "Completed action on Android" button writes a newline to the pipe.
    Reading on a daemon thread supports both Windows and other platforms.
    """
    WAITING["on"] = True
    WAITING["msg"] = msg
    HUMAN_EVENT.clear()
    received = threading.Event()
    closed = threading.Event()

    def _read_confirmation():
        try:
            value = sys.stdin.readline()
            if value:
                received.set()
            else:
                closed.set()
        except (OSError, ValueError, UnicodeError):
            closed.set()

    print(f"\n⏸  Action required: {msg}", flush=True)
    print("   Press Enter to continue after completing the step on Android.", flush=True)
    reader = threading.Thread(target=_read_confirmation, daemon=True)
    reader.start()
    deadline = time.monotonic() + max(0, timeout)
    approved = False
    try:
        while time.monotonic() < deadline:
            if HUMAN_EVENT.is_set() or received.is_set():
                approved = True
                break
            if closed.is_set():
                break
            time.sleep(0.1)
    finally:
        WAITING["on"] = False
        WAITING["msg"] = ""
    if approved:
        print("▶  Manual confirmation received; continuing", flush=True)
    else:
        warn("Manual verification was not confirmed before timeout/EOF; stopping this operation")
    return approved

# ---------- Constants ----------
PKG = "com.google.android.apps.subscriptions.red"   # Google One
VENDING = "com.android.vending"                     # Google Play Store
GMS = "com.google.android.gms"
PRODUCT = "g1.play.20tb"                            # Ultra 5x / 20TB
OFFER = "eft-12month"                               # Historical promotional offer ID
MODULE_REMOTE = "/data/local/tmp/module_521.apk"
FRIDA_REMOTE = "/data/local/tmp/frida-server"
FRIDA_REQUIRED = "16.5.9"
REPORT_DIR = Path("ultra0-report")

def report_filename(email: str) -> str:
    """Use the complete account identity without leaking it into filenames.

    The original local-part-only name overwrote reports for accounts at
    different domains (e.g. alice@gmail.com and alice@yahoo.com).
    """
    normalized = email.strip().lower()
    if normalized == "current@device":
        return "current.json"  # Stable identifier for read-only offer listing.
    return "account-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest() + ".json"


ADB_CANDIDATES = [
    os.environ.get("ADB_PATH", ""),
    # Windows / MuMu
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu\emulator\nemu\vmonitor\bin\adb_server.exe",
    r"C:\Program Files\Netease\MuMu\nx_main\adb.exe",
    r"C:\Program Files (x86)\Netease\MuMuPlayer-12.0\shell\adb.exe",
    "adb.exe", "adb",
    # macOS / Linux
    os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
    "/opt/homebrew/bin/adb", "/usr/local/bin/adb", "/usr/bin/adb",
]


# ---------- ADB helpers ----------
def find_adb() -> str:
    for c in ADB_CANDIDATES:
        if not c:
            continue
        if c in ("adb", "adb.exe") or Path(c).exists():
            try:
                subprocess.run([c, "version"], capture_output=True, timeout=5)
                return c
            except Exception:
                continue
    sys.exit("❌ ADB not found. Install Android SDK platform-tools and add adb to PATH.")


ADB = None
SERIAL = None


def sh(*args, timeout=60, check=False, binary=False):
    cmd = [ADB] + (["-s", SERIAL] if SERIAL else []) + list(args)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore")[:300])
    return p.stdout if binary else p.stdout.decode("utf-8", "ignore").strip()


def note(msg):
    print(f"   {msg}", flush=True)


def step(msg):
    print(f"\n▶ {msg}", flush=True)


def ok(msg):
    print(f"   ✅ {msg}", flush=True)


def warn(msg):
    print(f"   ⚠️  {msg}", flush=True)


# ---------- Device selection ----------
def pick_device(preferred=None):
    """Pilih satu perangkat Android online; pulihkan otomatis jika ADB nyangkut/offline."""
    global SERIAL
    out = sh("devices")
    lines = [l for l in out.splitlines()[1:] if "\tdevice" in l]
    online = [l.split("\t")[0] for l in lines]
    if not online or (preferred and preferred not in online):
        from device_diagnostics import recover_adb_connection
        targets = [preferred] if preferred and ":" in preferred else None
        recovery = recover_adb_connection(
            ADB, targets=targets, force_reset=False
        )
        if recovery.ok:
            online = list(recovery.devices)
        else:
            out = sh("devices")
            lines = [l for l in out.splitlines()[1:] if "\tdevice" in l]
            online = [l.split("\t")[0] for l in lines]
    if not online:
        sys.exit("❌ Perangkat Android belum terdeteksi. Jalankan MuMuPlayer, aktifkan ADB Debugging, atau klik Perbaiki ADB.")
    if preferred and preferred not in online:
        sys.exit(f"❌ Perangkat ADB {preferred} tidak online. Tersedia: {', '.join(online)}")
    if not preferred and len(online) != 1:
        from device_selector import auto_select_device
        selected = auto_select_device(ADB, serials=online)
        if not selected:
            sys.exit(f"❌ Lebih dari satu perangkat Android: {', '.join(online)}. "
                     "Gunakan --serial untuk memilih salah satu.")
        note(f"Perangkat Android terpilih otomatis: {selected}")
        SERIAL = selected
    else:
        SERIAL = preferred or online[0]
    ok(f"Connected ADB device: {SERIAL}")


def ensure_root():
    def _id():
        try:
            return sh("shell", "id", timeout=15)
        except Exception:
            return ""

    uid = _id()
    if "uid=0" not in uid:
        # Some emulators support adb root without needing su.
        try:
            sh("root", timeout=20)
            time.sleep(2)
            uid = _id()
            if "uid=0" in uid:
                note("Successfully enabled adb root")
        except Exception:
            pass
    if "uid=0" not in uid:
        try:
            uid = sh("shell", "su -c id", timeout=15)
        except Exception:
            uid = ""
    if "uid=0" not in uid:
        sys.exit("❌ Root is unavailable. Enable root in MuMu settings and restart, or run adb root manually.")


def ensure_frida_client():
    """Pin Frida 16 for the original Java bridge-based script."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        installed = version("frida")
    except PackageNotFoundError:
        installed = "not installed"
    if installed == FRIDA_REQUIRED:
        return
    if os.environ.get("ULTRA0_FRIDA_REPAIR_ATTEMPTED") == "1":
        raise RuntimeError(f"Host Frida is {installed}; expected {FRIDA_REQUIRED}. "
                           f"Manual fix: {sys.executable} -m pip install frida=={FRIDA_REQUIRED}")
    warn(f"Host Frida {installed} is incompatible with the original Java script; installing {FRIDA_REQUIRED}...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                                 "--no-cache-dir", f"frida=={FRIDA_REQUIRED}"],
                                capture_output=True, text=True, errors="replace", timeout=240)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Unable to install Frida {FRIDA_REQUIRED}: {exc}") from exc
    if result.returncode:
        msgs = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(f"Frida installation failed: {(msgs[-1] if msgs else 'pip failed')[:240]}")
    note("Frida Python updated; restarting script with the same arguments...")
    os.environ["ULTRA0_FRIDA_REPAIR_ATTEMPTED"] = "1"
    os.environ["ULTRA0_FRIDA_RESTART_SERVER"] = "1"
    os.execv(sys.executable, [sys.executable, *sys.argv])


def ensure_frida_server():
    """Check running Frida version; replace 17.x with the matching 16.5.9 build."""
    ensure_frida_client()
    running = sh("shell", "pidof frida-server || true").strip()
    try:
        deployed_version = sh("shell", f"{FRIDA_REMOTE} --version 2>/dev/null", timeout=12).strip()
    except subprocess.TimeoutExpired:
        deployed_version = ""
    must_restart = os.environ.pop("ULTRA0_FRIDA_RESTART_SERVER", "") == "1"
    if running and deployed_version == FRIDA_REQUIRED and not must_restart:
        ok(f"frida-server {FRIDA_REQUIRED} is running")
        return
    if running:
        warn(f"Restarting frida-server (device version: {deployed_version or 'unknown'})")
        for pid in running.split():
            if pid.isdigit():
                sh("shell", f"kill {pid}")
        time.sleep(1)
        remaining = sh("shell", "pidof frida-server || true").strip()
        if remaining:
            for pid in remaining.split():
                if pid.isdigit():
                    sh("shell", f"su -c 'kill {pid}'")
            time.sleep(1)
        if sh("shell", "pidof frida-server || true").strip():
            raise RuntimeError("Cannot stop old Frida server; restart MuMu and retry")
    if deployed_version != FRIDA_REQUIRED:
        abi = sh("shell", "getprop ro.product.cpu.abi").strip()
        arch = {"arm64-v8a": "arm64", "armeabi-v7a": "arm", "armeabi": "arm",
                "x86_64": "x86_64", "x86": "x86"}.get(abi)
        if not arch:
            raise RuntimeError(f"Unsupported device ABI: {abi}")
        import urllib.request, lzma
        url = (f"https://github.com/frida/frida/releases/download/{FRIDA_REQUIRED}/"
               f"frida-server-{FRIDA_REQUIRED}-android-{arch}.xz")
        archive = Path(tempfile.gettempdir()) / f"frida-server-{FRIDA_REQUIRED}-{arch}.xz"
        extracted = Path(tempfile.gettempdir()) / f"frida-server-{FRIDA_REQUIRED}-{arch}"
        note(f"Downloading official matching Frida server: {url}")
        with urllib.request.urlopen(url, timeout=120) as response, open(archive, "wb") as output:
            output.write(response.read())
        with lzma.open(archive, "rb") as source, open(extracted, "wb") as output:
            output.write(source.read())
        sh("push", str(extracted), FRIDA_REMOTE, timeout=180, check=True)
        sh("shell", f"chmod 755 {FRIDA_REMOTE}", check=True)
    if "uid=0" in sh("shell", "id"):
        sh("shell", f"nohup {FRIDA_REMOTE} -D >/dev/null 2>&1 &", timeout=15)
    else:
        sh("shell", f"su -c 'nohup {FRIDA_REMOTE} -D >/dev/null 2>&1 &'", timeout=15)
    for _ in range(20):
        time.sleep(0.5)
        if sh("shell", "pidof frida-server || true").strip():
            ok(f"frida-server {FRIDA_REQUIRED} started")
            return
    raise RuntimeError(f"frida-server {FRIDA_REQUIRED} could not start")


def read_purchase_token(sku_short: str, expected_account: str = "") -> str:
    """Read a valid matching-account purchase token without retaining Play DB copies."""
    import sqlite3
    import json as _json

    # Never leave a world-readable copy of the Play Store database on Android.
    # Unique paths prevent concurrent lookups from touching each other's files.
    remote = f"/data/local/tmp/lib_read_{os.getpid()}_{time.time_ns()}.db"
    try:
        sh("shell", f"cp /data/data/{VENDING}/databases/library.db {remote} 2>/dev/null && chmod 666 {remote}",
           timeout=30)
        with tempfile.TemporaryDirectory(prefix="google-ai-play-db-") as folder:
            local = Path(folder) / "library.db"
            try:
                sh("pull", remote, str(local), timeout=60)
            except Exception as error:
                warn(f"Failed to retrieve Google Play database: {type(error).__name__}")
                return ""
            if not local.is_file():
                return ""

            now_ms = int(time.time() * 1000)
            picked = None
            try:
                with sqlite3.connect(str(local)) as con:
                    rows = con.execute(
                        "select account, subs_valid_until_time, inapp_purchase_data "
                        "from ownership where doc_id like ?",
                        (f"%{sku_short}%",),
                    ).fetchall()
                for account, valid, data in rows:
                    if not data:
                        continue
                    if expected_account and str(account).strip().lower() != expected_account.lower():
                        continue
                    try:
                        record = _json.loads(data)
                    except (TypeError, ValueError):
                        continue
                    token = record.get("purchaseToken")
                    if not token:
                        continue
                    try:
                        expiry = int(valid)
                    except (ValueError, TypeError):
                        continue
                    if expiry <= now_ms:
                        continue
                    if picked is None or expiry > picked[2]:
                        picked = (token, account, expiry)
                if picked:
                    note("Found an active purchase token for the verified Google Play account.")
                    return picked[0]
            except (sqlite3.Error, OSError, ValueError) as error:
                warn(f"Failed to inspect Google Play database: {type(error).__name__}")
            return ""
    except Exception as error:
        # ADB may be unavailable during diagnostics; fail closed and still clean up.
        warn(f"Could not read Google Play purchase token: {type(error).__name__}")
        return ""
    finally:
        # Cleanup must run even if the copy, pull, query or token validation fails.
        # Never print token values or account identifiers in this path.
        try:
            sh("shell", f"rm -f {remote}", timeout=15)
        except Exception:
            pass


def ensure_vending(*, retry_startup: bool = False) -> bool:
    """Google Play Store must be running for BillingClient queries to complete."""
    if sh("shell", f"pidof {VENDING}"):
        ok("Google Play Store process is running")
        return True
    warn("Google Play Store is not running; attempting to start it...")
    for attempt in range(2 if retry_startup else 1):
        if attempt:
            warn("Google Play Store did not start during the offer check; restarting it once.")
            sh("shell", f"am force-stop {VENDING}", timeout=15)
        try:
            sh("shell", f"monkey -p {VENDING} -c android.intent.category.LAUNCHER 1", timeout=30)
        except subprocess.TimeoutExpired:
            if not retry_startup:
                raise
            warn("Google Play Store launch command timed out; checking whether it started.")
        for _ in range(20):
            time.sleep(1)
            if sh("shell", f"pidof {VENDING}"):
                ok("Google Play Store started")
                time.sleep(2)
                return True
    warn("Google Play Store did not start. Open it manually or restart the emulator.")
    return False


def ensure_module_apk():
    if sh("shell", f"ls {MODULE_REMOTE} 2>/dev/null"):
        ok("Billing module is already installed")
        return
    note("Pushing billing module to Android (one-time setup)...")
    tmp = Path(tempfile.gettempdir()) / "module_521.apk"
    tmp.write_bytes(base64.b64decode(MODULE_B64))
    sh("push", str(tmp), MODULE_REMOTE, timeout=120)
    ok("Billing module installed")


def ensure_network():
    proxy = sh("shell", "settings get global http_proxy")
    if proxy and proxy != "null" and proxy != ":0":
        sh("shell", "settings put global http_proxy :0")
        warn(f"Cleared Android proxy (previous value: {proxy}) to restore network access")
    # Stop common VPN apps that may intercept Google Play network traffic.
    for p in ("com.github.metacubex.clash.meta", "com.github.kr328.clash"):
        if sh("shell", f"pm list packages | grep -q {p} && echo yes"):
            sh("shell", f"am force-stop {p}")
            warn(f"Temporarily stopped {p}, which may intercept Google Play traffic")


# ---------- UI ----------
def ui_xml() -> str:
    sh("shell", "uiautomator dump /sdcard/ui.xml")
    return sh("shell", "cat /sdcard/ui.xml")


def nodes(xml: str):
    for m in re.finditer(r"<node[^>]*>", xml):
        s = m.group(0)
        t = re.search(r'text="([^"]*)"', s)
        d = re.search(r'content-desc="([^"]*)"', s)
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s)
        c = re.search(r'class="([^"]*)"', s)
        if not b:
            continue
        yield {
            "text": (t.group(1) if t else "") or "",
            "desc": (d.group(1) if d else "") or "",
            "cls": (c.group(1) if c else "") or "",
            "x": (int(b.group(1)) + int(b.group(3))) // 2,
            "y": (int(b.group(2)) + int(b.group(4))) // 2,
        }


def tap(x, y):
    sh("shell", f"input tap {x} {y}")


def tap_text(*needles, exact=False) -> bool:
    for n in nodes(ui_xml()):
        label = n["text"] or n["desc"]
        if not label:
            continue
        hit = (label == needles[0]) if exact and needles else any(k in label for k in needles)
        if hit and (n["x"] or n["y"]):
            tap(n["x"], n["y"])
            return True
    return False


def type_text(s: str):
    # Quote the full text for the Android shell so passwords/emails containing
    # quotes, semicolons or substitutions cannot become shell instructions.
    sh("shell", "input text " + shlex.quote(s.replace(" ", "%s")))


def find_edit():
    for n in nodes(ui_xml()):
        if "EditText" in n["cls"]:
            return n["x"], n["y"]
    return None


# ---------- TOTP ----------
def totp(secret: str, digits=6, period=30) -> str:
    if not secret:
        return ""
    s = re.sub(r"[^A-Za-z2-7]", "", secret).upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    key = base64.b32decode(s)
    ctr = int(time.time()) // period
    mac = hmac.new(key, struct.pack(">Q", ctr), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


# ---------- Account management ----------
def accounts_on_device() -> list:
    out = sh("shell", "dumpsys account | grep 'type=com.google'")
    return out.splitlines()


def available_google_accounts() -> list[str]:
    """Read candidate accounts from Android. NOT proof of the active Play payer.

    Some Android versions redact AccountManager identities, so an empty list
    should prompt manual Play Store selection rather than guessing.
    """
    found = set()
    for line in accounts_on_device():
        if "type=com.google" not in line:
            continue
        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                                line, flags=re.I):
            if len(email) <= 254:
                found.add(email.lower())
    return sorted(found)


def add_account(email, password, totp_secret="") -> bool:
    """Add a Google account on Android, pausing for manual verification when needed."""
    step(f"Adding account to Android: {email}")
    before = len(accounts_on_device())
    sh("shell", "am start -a android.settings.ADD_ACCOUNT_SETTINGS")
    time.sleep(3)
    tap_text("Google", exact=True) or tap_text("Google")
    time.sleep(5)

    pos = find_edit()
    if pos:
        for _ in range(3):                      # Verify the typed email to catch missing characters.
            tap(*pos); time.sleep(0.8)
            sh("shell", "input keyevent 123")   # Move cursor to end.
            for _ in range(60):
                sh("shell", "input keyevent 67")  # Backspace to clear the field.
            type_text(email); time.sleep(1)
            cur = " ".join(n["text"] for n in nodes(ui_xml()) if "@" in n["text"])
            if email.lower() in cur.lower():
                break
            warn(f"Email input was incomplete; retrying (current: {cur[:40]})")
        else:
            warn("Could not enter the complete email after several attempts")
        tap_text("\u4e0b\u4e00\u6b65", "Next"); time.sleep(6)

    if find_edit():
        tap(*find_edit()); time.sleep(1)
        type_text(password); time.sleep(1)
        tap_text("\u4e0b\u4e00\u6b65", "Next"); time.sleep(7)

    # Advance through recognized screens; ask the user to handle unknown screens.
    unknown_rounds = 0
    for _ in range(90):
        if len(accounts_on_device()) > before:
            ok("Google account added to Android")
            return True
        xml = ui_xml()
        text = " ".join(n["text"] for n in nodes(xml) if n["text"])

        if "\u6b64\u8d26\u53f7\u5df2\u5728\u60a8\u7684\u8bbe\u5907\u4e0a" in text or "already on your device" in text.lower():
            ok("This Google account is already on the device")
            return True
        if "\u627e\u4e0d\u5230\u6b64\u8d26\u53f7" in text or "Couldn't find your Google Account" in text:
            warn("Google could not find this account; check the email address")
            return False
        if "\u5bc6\u7801\u4e0d\u6b63\u786e" in text or "Wrong password" in text:
            warn("Google account password was rejected")
            return False

        if ("\u4e24\u6b65\u9a8c\u8bc1" in text or "2-Step" in text or "\u8f93\u5165\u9a8c\u8bc1\u7801" in text):
            if totp_secret and find_edit():
                code = totp(totp_secret)
                note("Submitting the two-factor code without printing it")
                tap(*find_edit()); type_text(code); time.sleep(1)
                tap_text("\u4e0b\u4e00\u6b65", "Next"); time.sleep(8)
                continue
            if not wait_human("Two-step verification required; complete the check on Android.", 300):
                return False
            continue

        if tap_text("\u4ee5\u540e\u518d\u8bf4", "Not now"):
            time.sleep(3); continue
        if tap_text("\u6211\u540c\u610f", "I agree"):
            time.sleep(5); continue
        if tap_text("\u53d6\u6d88", "Skip", "\u8df3\u8fc7"):
            time.sleep(2); continue

        if any(k in text for k in ("\u8bc1\u660e\u60a8\u4e0d\u662f\u81ea\u52a8\u7a0b\u5e8f", "\u9a8c\u8bc1\u8eab\u4efd", "\u8bf7\u8f93\u5165\u7535\u8bdd\u53f7\u7801", "\u65e0\u6cd5\u9a8c\u8bc1", "\u786e\u8ba4\u662f\u60a8\u672c\u4eba")):
            if not wait_human("Complete the CAPTCHA or identity verification on Android.", 300):
                return False
            continue

        unknown_rounds += 1
        if unknown_rounds >= 8:
            if not wait_human("Unrecognized Android screen; finish account setup manually.", 300):
                return False
            unknown_rounds = 0
        time.sleep(2)

    if len(accounts_on_device()) > before:
        ok("Google account added to Android")
        return True
    warn("Timed out adding the Google account")
    return False


def add_card(card: dict) -> bool:
    """Add a payment card through the original Google Pay UI workflow."""
    if not card:
        return True
    step(f"Adding a payment method ending in {card['number'][-4:]}")
    sh("shell", "am start -a android.intent.action.VIEW "
                "-d 'https://pay.google.com/gp/w/u/0/home/paymentmethods'")
    time.sleep(10)
    if not tap_text("Add a payment method", "\u6dfb\u52a0\u4ed8\u6b3e\u65b9\u5f0f", "\u6dfb\u52a0\u4fe1\u7528\u5361", "Add card"):
        warn("Could not find the add-card entry; enter the payment method manually")
        return False
    time.sleep(9)
    # Fill only supplied card information. Never invent a billing address or
    # cardholder name: a real address must be entered and reviewed on Android.
    mm = re.sub(r"\D", "", card["exp"])[:2] or "01"
    yy = re.sub(r"\D", "", card["exp"])[2:][-2:] or "30"
    seq = [card["number"], mm, yy, card["cvc"]]
    if card.get("holder"):
        seq.append(card["holder"])
    for i, val in enumerate(seq):
        edits = [n for n in nodes(ui_xml()) if "EditText" in n["cls"]]
        if i >= len(edits):
            break
        tap(edits[i]["x"], edits[i]["y"]); time.sleep(0.6)
        type_text(val); time.sleep(0.5)
    note("Review and complete the actual cardholder/billing address on Android.")
    if not wait_human("Enter your real billing details, save the card on Android, then press Enter.", 240):
        warn("Payment method could not be confirmed")
        return False
    ok("Manual payment-method step acknowledged (not independently verified)")
    return True


def current_play_account() -> str:
    """Read the visible account from Play Store; unknown is not an account mismatch."""
    xml = ui_xml()
    if f'package="{VENDING}"' not in xml:
        note("Opening Play Store to verify the account (Google One may be foreground)...")
        sh("shell", f"am start -n {VENDING}/com.google.android.finsky.activities.MainActivity", timeout=25)
        time.sleep(3)
        xml = ui_xml()
    if f'package="{VENDING}"' not in xml:
        warn("Cannot inspect Play Store UI. Open Play Store, tap the profile icon, and retry.")
        return ""

    opened_profile = False
    for n in nodes(xml):
        # Play Store exposes the active profile on its account button in
        # some versions. Other signed-in accounts in the expanded menu
        # must not override that explicit identity.
        if re.match(r"^(?:Google Account|T\u00e0i kho\u1ea3n Google|Google \u5e10\u53f7|Google \u8d26\u53f7)\s*[:\uff1a]", n["desc"], re.I):
            active = {value.lower() for value in re.findall(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", n["desc"])}
            if len(active) == 1:
                return next(iter(active))
        if ("\u8d26\u53f7\u548c\u8bbe\u7f6e" in n["desc"] or "Account and settings" in n["desc"]
                or "T\u00e0i kho\u1ea3n v\u00e0 ch\u1ebf \u0111\u1ed9 c\u00e0i \u0111\u1eb7t" in n["desc"]):
            tap(n["x"], n["y"])
            time.sleep(3)
            opened_profile = True
            break
    # The profile popup may show multiple signed-in Google accounts. Its
    # first email is NOT necessarily the account currently selected for
    # billing. Never infer identity from the first arbitrary UI node.
    emails = set()
    for n in nodes(ui_xml()):
        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                                n["desc"] + " " + n["text"]):
            emails.add(email.lower())
    if opened_profile:
        sh("shell", "input keyevent 4")
    if len(emails) > 1:
        warn("Multiple Google accounts are visible in Play Store; the active billing "
             "account cannot be identified safely. Select the intended account "
             "manually, then repeat the read-only check.")
        return ""
    if not emails:
        warn("Play account is not visible to UI automation; check the Play Store profile manually.")
        return ""
    if not opened_profile:
        warn("Play Store profile was not opened; a visible email does not prove "
             "which account is active for billing.")
        return ""
    return next(iter(emails))


def switch_play(email) -> bool:
    """Switch Play Store account, but fail closed when the active account cannot be verified."""
    step(f"Switching to Play Store account: {email}")
    want = email.lower()
    sh("shell", f"am force-stop {VENDING}")
    sh("shell", f"am force-stop {PKG}")
    sh("shell", f"am start -n {VENDING}/com.google.android.finsky.activities.MainActivity "
                f"--es authAccount {email}")
    time.sleep(9)
    if current_play_account() == want:
        ok("Google Play account verified"); return True
    for n in nodes(ui_xml()):
        if "\u8d26\u53f7\u548c\u8bbe\u7f6e" in n["desc"] or "Account and settings" in n["desc"]:
            tap(n["x"], n["y"]); time.sleep(3); break
    for n in nodes(ui_xml()):
        if "\u5c55\u5f00\u8d26\u53f7\u5217\u8868" in n["desc"]:
            tap(n["x"], n["y"]); time.sleep(3); break
    for n in nodes(ui_xml()):
        if want in (n["text"] + " " + n["desc"]).lower():
            tap(n["x"], n["y"]); time.sleep(6); break
    sh("shell", "input keyevent 4")
    got = current_play_account()
    if got == want:
        ok("Google Play account verified"); return True
    warn(f"Google Play account did not switch (current: {got or 'unknown'}). Aborting to avoid the wrong account.")
    return False


# ---------- Frida ----------
def launch_app() -> int:
    """Start Google One and wait for a real PID; report launch failures clearly."""
    if not sh("shell", f"pm path {PKG}", timeout=15).strip():
        warn(f"Google One is not installed or enabled ({PKG}). Install/open it from Play Store.")
        return 0
    step("Restarting Google One before querying offers")
    sh("shell", f"am force-stop {PKG}", check=True)
    try:
        launch_output = sh("shell", f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1", timeout=30)
    except subprocess.TimeoutExpired:
        warn("Google One launch (monkey) timed out; inspect the emulator screen.")
        launch_output = ""
    if "No activities found" in launch_output:
        warn("Google One has no launchable activity on this Android instance.")
        return 0
    for seconds in (7, 3, 3, 3):
        time.sleep(seconds)
        pid = sh("shell", f"pidof {PKG}").strip()
        if pid.isdigit():
            return int(pid)
    warn("Google One stopped or did not launch after 16 seconds. Open it manually in MuMu.")
    warn(f"Diagnostics: adb shell pm path {PKG} ; adb shell monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    return 0


def build_js(plan: str = "auto", list_only: bool = False, stack: bool = False, old_token: str = "", stack_mode=None, activity_method="auto") -> str:
    """Build the product query for the requested Google Play plan."""
    if activity_method not in ("auto", "choose", "thread"):
        raise ValueError(f"Unsupported activity method: {activity_method}")
    js = FRIDA_JS.replace('var ACTIVITY_METHOD="auto";',
                          f'var ACTIVITY_METHOD="{activity_method}";', 1)
    if list_only:
        js = js.replace('var PREFER="";', 'var PREFER=""; var LIST_ONLY=true;', 1)
    if stack:
        js = js.replace('var PREFER="";', 'var PREFER=""; var STACK=true;', 1)
    if old_token:
        js = js.replace('var PREFER="";', 'var PREFER=""; var OLD_TOKEN="%s";' % old_token, 1)
    if stack_mode is not None:
        js = js.replace('var PREFER="";', 'var PREFER=""; var STACK_MODE=%d;' % stack_mode, 1)
    if plan == "20x":
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.play.ai.pro","g1.ai.pro","g1.30tb"];')
    elif plan == "5x":
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.play.20tb"];')
    elif plan.startswith("pro"):
        # Google AI Pro 5TB（g1.2tb.ai.subs_variant）：12months-eft / 6months-eft / 6months-eft-2 / 6months-eft-ss-2026
        prefer = {"pro12": "12months-eft", "pro6": "6months-eft",
                  "pro6b": "6months-eft-2", "pro6c": "6months-eft-ss-2026"}.get(plan, "12months-eft")
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.2tb.ai.subs_variant"];')
        js = js.replace('var PREFER="";', 'var PREFER="%s";' % prefer, 1)
    return js


def verify_adb_target_pid(pid: int, serial: str) -> str:
    """Validate PID and process ownership on the EXACT ADB device.

    Frida get_process()/enumerate_processes() can fail independently of attach
    on certain ART/Android versions. ADB is the authoritative PID source.
    Never guess if PID was recycled or belongs to an unrelated process.
    """
    if not ADB or not serial or not isinstance(pid, int) or pid <= 0:
        raise RuntimeError("ADB executable, device serial, or Google One PID is invalid.")

    def adb_shell(*command: str):
        result = subprocess.run([ADB, "-s", serial, "shell", *command],
                                capture_output=True, timeout=12)
        if result.returncode != 0:
            raise RuntimeError(
                "ADB process inspection failed on %s: %s" %
                (serial, result.stderr.decode("utf-8", "replace").strip()[:160]))
        return result.stdout.decode("utf-8", "replace").strip()

    pids = adb_shell("pidof", PKG).split()
    if str(pid) not in pids:
        raise RuntimeError(
            f"Google One PID {pid} is no longer running on ADB device {serial}. "
            "Reopen Google One and retry read-only offer listing.")
    try:
        cmdline = adb_shell("cat", f"/proc/{pid}/cmdline")
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        # Some Android builds restrict /proc. A fresh, exact-package pidof
        # check is still sufficient to reject unrelated or stale PIDs.
        note("ADB /proc inspection is restricted; PID verified by package pidof.")
        return PKG

    name = cmdline.split("\x00", 1)[0].strip()
    if name and name != PKG and not name.startswith(PKG + ":"):
        raise RuntimeError(
            f"ADB PID {pid} is {name!r}, not {PKG!r}; refusing to attach.")
    return name or PKG


def get_target_frida_device(pid: int, serial: str):
    """Map Frida to the ADB-selected Android and validate the process via ADB."""
    import frida
    candidates = [dev for dev in frida.get_device_manager().enumerate_devices()
                  if getattr(dev, "type", None) == "usb"]
    exact = [dev for dev in candidates if getattr(dev, "id", None) == serial]
    if len(exact) == 1:
        selected = exact[0]
    elif len(candidates) == 1:
        # Frida may report another ADB alias for the same emulator. Require
        # a matching Android boot UUID before treating these as equivalent.
        from device_selector import boot_uuid, online_serials
        candidate = candidates[0]
        candidate_serial = str(candidate.id)
        online = online_serials(ADB)
        original_boot = boot_uuid(ADB, serial)
        frida_boot = boot_uuid(ADB, candidate_serial) if candidate_serial in online else ""
        if not original_boot or original_boot != frida_boot:
            raise RuntimeError(
                f"Frida device {candidate_serial!r} does not match ADB device {serial!r}. "
                "Select a matching --serial; refusing to attach to another emulator.")
        selected = candidate
    else:
        available = ", ".join(str(dev.id) for dev in candidates) or "none"
        raise RuntimeError(
            f"Cannot map ADB serial {serial!r} to a unique Frida device. "
            f"Frida USB devices: {available}. Check frida-ls-devices and use --serial.")

    # Frida's get_process(pid) may fail to enumerate Android processes even
    # though the process is running and attach(pid) works. Verify with ADB.
    identity = verify_adb_target_pid(pid, serial)
    note(f"Verified Google One PID {pid} via ADB: {identity}")
    return selected


def run_trial(pid: int, wait=90, plan="auto", list_only=False, stack=False, old_token="", stack_mode=None, activity_method="auto", post_launch=None, open_only=False) -> dict:
    step("Injecting billing module to inspect introductory offers")
    dev = get_target_frida_device(pid, SERIAL)
    note(f"Using Frida device: {dev.id} (ADB: {SERIAL})")
    sess = dev.attach(pid)
    res = {"offers": [], "launched": None, "purchase": None, "activity": None, "errors": []}
    launched_event = threading.Event()

    def on_msg(m, _):
        if m.get("type") == "error":
            detail = str(m.get("description") or m.get("stack") or "Unknown JavaScript error")
            res["errors"].append({"ev": "frida_script_error", "message": detail[:400]})
            warn(f"Frida JavaScript error: {detail[:240]}")
            return
        p = m.get("payload") or {}
        if not isinstance(p, dict):
            return
        ev = p.get("ev")
        if ev == "offer":
            # Never store private offer tokens or product titles in exported reports.
            res["offers"].append({key: p.get(key) for key in
                                  ("product", "id", "micros", "period")})
            note(f"offer {p.get('id')} → {p.get('micros')} ({p.get('period','')})")
        elif ev == "chosen":
            res["chosen_offer"] = {key: p.get(key) for key in ("product", "id", "period")}
            note(f"Selected Google Play offer ID: {p.get('id')}")
        elif ev == "activity_selected":
            res["activity"] = {"method": p.get("method"), "class": p.get("name")}
            note(f"Activity found via {p.get('method')}: {p.get('name')}")
        elif ev == "launched":
            res["launched"] = p
            ok(f"Google Play billing flow response: {p}")
            launched_event.set()
        elif ev == "purchase_cb":
            res["purchase"] = p
        elif ev and ("err" in ev or ev.startswith("no_")):
            res["errors"].append(p)

    try:
        sc = sess.create_script(build_js(plan, list_only, stack, old_token, stack_mode, activity_method))
        sc.on("message", on_msg)
        sc.load()
        if open_only and not list_only:
            # Begitu Google Play Billing merespons `launched`, tidak perlu menunggu 90 detik penuh.
            if launched_event.wait(timeout=wait):
                time.sleep(1.5)
        else:
            time.sleep(wait)
        # Keep Frida attached through the Subscribe tap and bounded UI observation,
        # allowing delayed purchase_cb failures to reach on_msg before cleanup.
        # Never tap for an unverified offer or a failed billing callback.
        if post_launch is not None and not list_only and not open_only and (
                isinstance(res.get("launched"), dict) and res["launched"].get("code") == 0):
            expected = {"pro12": "12months-eft", "pro6": "6months-eft",
                        "pro6b": "6months-eft-2", "pro6c": "6months-eft-ss-2026"}.get(plan)
            chosen = res.get("chosen_offer")
            callback = res.get("purchase")
            rejected = isinstance(callback, dict) and str(callback.get("code")) not in ("0", "None")
            if expected and isinstance(chosen, dict) and chosen.get("id") == expected and not rejected:
                res["sheet"] = post_launch()
    finally:
        try:
            sess.detach()
        except Exception:
            pass  # The device may already have disconnected.
    return res


def query_offers_with_recovery(pid: int, **kwargs) -> dict:
    """Retry transient Frida connection failures once, only for read-only queries."""
    import frida
    transient = tuple(cls for name in ("TransportError", "ServerNotRunningError",
                                        "ProcessNotFoundError", "TimedOutError")
                      if isinstance((cls := getattr(frida, name, None)), type)
                      and issubclass(cls, Exception))
    try:
        return run_trial(pid, list_only=True, **kwargs)
    except transient:
        warn("Frida connection failed during the read-only check; reconnecting once.")
        ensure_frida_server()
        fresh_pid = launch_app()
        if not fresh_pid:
            raise RuntimeError("Google One could not be restarted for the read-only retry")
        return run_trial(fresh_pid, list_only=True, **kwargs)


def diagnose_launch_failure(fr: dict) -> tuple:
    """Explain why billing UI was not opened, without retrying purchases."""
    events = fr.get("errors") or []
    ev_names = {e.get("ev") for e in events if isinstance(e, dict)}
    if ev_names.intersection({"no_purchase", "no_matching_purchase", "stack_query_err", "stack_outer_err",
                              "stack_param_err", "mode_err"}):
        return ("subscription_update_unavailable",
                "Existing subscription token or replacement parameters were unavailable. "
                "No safe subscription update was launched. Inspect the Play subscription state.")
    if "choose_err" in ev_names and ("activity_thread_err" in ev_names or "no_activity" in ev_names):
        return ("activity_lookup_failed",
                "Both Java.choose and ActivityThread failed to locate a usable Activity. "
                "Check the recorded ART errors and the Android version; no checkout was opened.")
    if "choose_err" in ev_names:
        return ("activity_lookup_failed",
                "Java.choose failed; rerun with --activity-method thread to test the fallback.")
    if "activity_thread_err" in ev_names:
        return ("activity_lookup_failed",
                "ActivityThread lookup failed; try --activity-method choose on a compatible device.")
    if "no_activity" in ev_names:
        return ("no_activity",
                "Google One had no usable Android Activity; reopen the app in MuMu.")
    for event in events:
        if isinstance(event, dict) and event.get("ev") in (
                "launch_err", "launch_outer_err", "mode_err", "frida_script_error"):
            message = str(event.get("m") or event.get("message") or event["ev"])[:240]
            return ("billing_launch_error", message)
    result = fr.get("launched")
    if isinstance(result, dict):
        code = result.get("code")
        message = str(result.get("msg") or "")[:180]
        return ("billing_flow_error",
                f"BillingClient launchBillingFlow returned code={code}; message={message}.")
    return ("launch_failed",
            "No successful launchBillingFlow response was observed. "
            "Inspect the report's errors field; do not infer subscription success.")


def handle_verify(password="") -> bool:
    """Handle optional Google Play identity verification and Play Points prompts."""
    changed = False
    for _ in range(12):
        blob = " ".join(n["text"] for n in nodes(ui_xml()) if n["text"])
        if "\u4ee5\u540e\u518d\u8bf4" in blob or "Play \u79ef\u5206" in blob:
            tap_text("\u4ee5\u540e\u518d\u8bf4", "Not now"); time.sleep(2); changed = True; continue
        if ("\u9a8c\u8bc1" in blob or "Verify" in blob) and password:
            es = [n for n in nodes(ui_xml()) if "EditText" in n["cls"]]
            if es:
                tap(es[0]["x"], es[0]["y"]); time.sleep(0.8)
                slow_type(password, 0.1); time.sleep(0.8)
                tap_text("\u9a8c\u8bc1", "Verify"); time.sleep(6); changed = True; continue
        break
    return changed


def assess_checkout_terms(text: str, expected_plan: str = "auto") -> dict:
    """Do not mistake a renewal price for the amount due today."""
    clean = " ".join(text.split())
    low = clean.lower()
    result = {"reason": "checkout_not_visible", "today_price": None, "text": clean[:400]}
    # A payment security refusal overrides any $0/trial wording that may
    # still be visible in the background behind Google's error dialog.
    if "or-reh-04" in low or (
            "your transaction can't be completed" in low and
            "secure your account" in low):
        result["reason"] = "payment_security_blocked"
        result["error_code"] = "OR-REH-04" if "or-reh-04" in low else None
        return result
    if any(x in low for x in ("backup payment methods", "\u5907\u7528\u4ed8\u6b3e\u65b9\u5f0f",
                               "phương thức thanh toán dự phòng")):
        result["reason"] = "backup_payment_methods_prompt"
        return result
    if any(x in low for x in ("you're already subscribed", "you are already subscribed",
                               "already subscribed to", "\u5df2\u8ba2\u9605", "đã đăng ký gói")):
        result["reason"] = "already_subscribed"
        return result
    if any(x in low for x in ("not eligible", "ineligible", "\u4e0d\u7b26\u5408\u514d\u8d39\u8bd5\u7528\u6761\u4ef6",
                               "không đủ điều kiện dùng thử")):
        result["reason"] = "ineligible"
        return result
    if "the item you requested is not available for purchase" in low:
        result["reason"] = "purchase_unavailable"
        return result
    if "processing" in low and "subscribe" not in low:
        result["reason"] = "processing"
        return result
    if not (any(x in low for x in ("subscribe", "\u8ba2\u9605", "đăng ký")) and
            any(x in low for x in ("google ai", "google one", "ultra", "pro"))):
        return result
    currency = r"(?:US\$|HK\$|NT\$|CA\$|AU\$|JP¥|¥|￥|\$|€|£|₫|VND\s*)"
    zero = currency + r"\s*0(?:[.,]0{1,2})?(?![\d.,])"
    today = r"(?:today|due today|pay today|total today|charged today|\u4eca\u5929|\u4eca\u65e5|\u672c\u65e5|hôm nay)"
    zero_today = bool(re.search(today + r"\s*[:：–-]?\s*" + zero, clean, re.I) or
                      re.search(zero + r"\s*(?:due\s*)?" + today, clean, re.I))
    result["prices"] = re.findall(currency + r"\s*\d[\d,.]*", clean, re.I)[:8]
    if not zero_today:
        result["reason"] = "today_price_unverified"
        return result
    result["today_price"] = "0"
    patterns = {
        "pro12": r"(?:12\s*[- ]?\s*months?|1\s*[- ]?\s*year|one year|365\s*days|12\s*\u4e2a\s*\u6708|\u4e00\u5e74|12\s*\u304b\u6708)",
        "pro6": r"(?:6\s*[- ]?\s*months?|6\s*\u4e2a\s*\u6708|\u534a\u5e74|6\s*\u304b\u6708)",
        "pro6b": r"(?:6\s*[- ]?\s*months?|6\s*\u4e2a\s*\u6708|\u534a\u5e74|6\s*\u304b\u6708)",
        "pro6c": r"(?:6\s*[- ]?\s*months?|6\s*\u4e2a\s*\u6708|\u534a\u5e74|6\s*\u304b\u6708)",
    }
    if not re.search(patterns.get(expected_plan, r"(?!x)x"), clean, re.I):
        result["reason"] = "trial_duration_unverified"
        return result
    result["reason"] = "zero_today_and_duration_verified"
    return result


def confirm_zero(wait=40, password="", expected_plan="auto", expected_account="") -> dict:
    step("Checking today's Google Play checkout total and trial duration")
    out = {"price": None, "confirmed": False, "ineligible": False,
           "text": "", "reason": "checkout_not_visible"}
    for _ in range(max(1, wait // 2)):
        visible = " ".join(n["text"] or n["desc"] for n in nodes(ui_xml())
                           if n["text"] or n["desc"])
        assessment = assess_checkout_terms(visible, expected_plan)
        reason = assessment["reason"]
        out.update({"reason": reason, "price": assessment["today_price"],
                    "text": assessment["text"]})
        if reason in ("ineligible", "purchase_unavailable"):
            out["ineligible"] = True
            warn("Google Play reports that this item or offer is unavailable; no Subscribe tap.")
            return out
        if reason == "payment_security_blocked":
            out["error_code"] = assessment.get("error_code")
            warn("Google Play blocked this payment pending account security checks "
                 "(OR-REH-04). This is NOT a trial-duration issue. "
                 "Do not retry checkout or use --force; check Google Account "
                 "and Google Payments notices. Leaving the error dialog open.")
            return out
        if reason == "already_subscribed":
            warn("Google Play reports this plan is already subscribed. "
                 "No extension was verified; leaving the dialog open.")
            return out
        if reason == "backup_payment_methods_prompt":
            warn("Google Play backup-payment prompt needs manual review; not enabling it automatically.")
            return out
        if reason == "zero_today_and_duration_verified":
            if expected_account:
                accounts = {email.lower() for email in re.findall(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", visible)}
                if accounts != {expected_account.strip().lower()}:
                    out["reason"] = "checkout_account_mismatch" if accounts else "checkout_account_unverified"
                    warn("Checkout account could not be matched to the selected account. "
                         "Review the account on the Google Play checkout screen before retrying.")
                    return out
                # An email anywhere on the screen is NOT evidence of the payer.
                # Require the checkout itself to explicitly identify the payer,
                # otherwise leave the sheet open for manual confirmation.
                payer_label = (
                    r"(?:paying\s+(?:with|as)|billed\s+to|purchase\s+account|"
                    r"google\s+play\s+account)\s*[:：\-]?\s*" +
                    re.escape(expected_account.strip().lower())
                )
                if not re.search(payer_label, visible, re.I):
                    out["reason"] = "checkout_account_unverified"
                    warn("Google Play does not explicitly identify the purchase payer. "
                         "No automatic Subscribe tap; verify manually in Google Play.")
                    return out
            if tap_text("\u8ba2\u9605", "Subscribe", "Đăng ký"):
                out["confirmed"] = True
                ok("Tapped Subscribe after verifying today's zero total and expected trial period.")
                # A tap is not a purchase. Play can reject it *after* the button
                # was pressed. Inspect the real Play UI before navigating away.
                for _ in range(4):
                    time.sleep(1)
                    after = " ".join(n["text"] or n["desc"] for n in nodes(ui_xml())
                                     if n["text"] or n["desc"])
                    observed = assess_checkout_terms(after, expected_plan)
                    if observed["reason"] in (
                            "purchase_unavailable", "ineligible", "already_subscribed",
                            "payment_security_blocked", "processing",
                            "backup_payment_methods_prompt",
                            "today_price_unverified", "trial_duration_unverified"):
                        out["confirmed"] = False
                        out["reason"] = observed["reason"]
                        out["text"] = observed["text"]
                        out["ineligible"] = observed["reason"] in ("purchase_unavailable", "ineligible")
                        warn("Google Play rejected or held checkout after the tap; "
                             "no subscription or renewal was verified.")
                        return out
            else:
                out["reason"] = "subscribe_button_not_found"
                warn("Subscribe control not found; no transaction confirmed.")
            return out
        if reason in ("today_price_unverified", "trial_duration_unverified"):
            warn("Checkout does not explicitly verify BOTH today's $0 total and the expected duration. "
                 "A nonzero amount could be the future renewal price. Leaving Google Play open.")
            return out
        time.sleep(2)
    warn(f"Checkout was not confirmed ({out['reason']}); leaving Google Play open.")
    return out


def verify() -> str:
    step("Checking the Google Play subscription page")
    sh("shell", f"am start -a android.intent.action.VIEW "
                f"-d 'https://play.google.com/store/account/subscriptions'")
    time.sleep(9)
    text = " | ".join(n["text"] for n in nodes(ui_xml()) if n["text"])
    if "Ultra" in text:
        ok("Subscription page mentions Ultra; this does not prove activation")
    return text[:500]


# ---------- Per-account workflow ----------
def process(email, password="", totp_secret="", add=True, card=None, plan="auto", no_switch=False, list_only=False, stack=False, old_token="", stack_mode=None, activity_method="auto", open_only=False) -> dict:
    print("\n" + "=" * 56)
    print(f"  Processing account: {email}")
    print("=" * 56)
    rec = {"email": email, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "unknown"}
    if add:
        try:
            if not add_account(email, password, totp_secret):
                rec["status"] = "add_account_failed"
                return rec
        except Exception as e:
            warn(f"Could not add Google account: {e}")
            rec["status"] = "add_account_error"
            return rec
    if card:
        try:
            if not add_card(card):
                rec["status"] = "payment_method_not_confirmed"
                return rec
        except Exception as e:
            warn(f"Could not add payment card: {type(e).__name__}")
            rec["status"] = "payment_method_not_confirmed"
            return rec
    if globals().get("SKIP_ACCOUNT_CHECK"):
        ok("WARNING: Play Store account check bypassed (--force)")
    elif list_only:
        cur = current_play_account()
        # Persist the verified identity in the read-only report. PowerShell
        # might have tried account discovery before Play Store finished loading.
        # This value is rechecked before any purchase in the live stage.
        rec["detected_play_account"] = cur or ""
        ok(f"List-only: current Play Store account is {cur or 'unknown'} (no checkout)")
    elif no_switch:
        cur = current_play_account()
        if not cur:
            warn("Play Store account could not be verified; aborting without checkout.")
            rec["status"] = "account_unverified"
            rec["error"] = "Play Store profile email was not readable; check the foreground Play Store UI"
            return rec
        if cur != email.lower():
            warn(f"Current Play Store account is {cur}, not {email}; aborting")
            rec["status"] = "wrong_account"
            return rec
        ok("Google Play account verified (manual selection)")
    elif not switch_play(email):
        rec["status"] = "play_account_switch_failed"
        return rec
    if stack and not old_token:
        note("Reading the existing subscription purchase token...")
        old_token = read_purchase_token("subs_variant", expected_account=email)
        if old_token:
            ok(f"Read existing purchase token ({old_token[:16]}...); attempting subscription update")
        else:
            warn("No purchase token found; falling back to queryPurchases (may fail)")

    pid = launch_app()
    if not pid and list_only:
        warn("Google One did not start during the offer check; restarting it once.")
        pid = launch_app()
    if not pid:
        rec["status"] = "app_not_started"
        return rec
    options = dict(plan=plan, stack=stack, old_token=old_token,
                   stack_mode=stack_mode, activity_method=activity_method)
    if list_only:
        fr = query_offers_with_recovery(pid, **options)
    elif open_only:
        fr = run_trial(pid, list_only=False, open_only=True, **options)
    else:
        fr = run_trial(pid, list_only=False, **options,
                       post_launch=lambda: confirm_zero(
                           password=password, expected_plan=plan, expected_account=email))
    rec.update(fr)
    if not list_only and plan in ("pro12", "pro6", "pro6b", "pro6c"):
        expected = {"pro12": "12months-eft", "pro6": "6months-eft",
                    "pro6b": "6months-eft-2", "pro6c": "6months-eft-ss-2026"}[plan]
        chosen = fr.get("chosen_offer")
        if not isinstance(chosen, dict) or chosen.get("id") != expected:
            rec["status"] = "offer_not_available"
            rec["error"] = "The requested Google Play offer could not be verified in the billing response."
            warn("The selected offer did not match the requested step. No Subscribe tap was attempted.")
            return rec
    if list_only:
        rec["status"] = "listed" if fr.get("offers") else "offer_query_failed"
        if not fr.get("offers"):
            rec["error"] = "No offer data returned; inspect BillingClient and Frida errors."
        return rec
    if fr["launched"] and fr["launched"].get("code") == 0:
        # A rejection callback takes precedence over an OK launch response.
        callback = fr.get("purchase")
        if isinstance(callback, dict):
            try:
                purchase_code = int(callback.get("code"))
            except (TypeError, ValueError):
                purchase_code = None
            if purchase_code not in (None, 0):
                rec["status"] = "purchase_unavailable" if purchase_code == 4 else "billing_flow_error"
                rec["error"] = ("Google Play rejected the purchase (ITEM_UNAVAILABLE)."
                                if purchase_code == 4 else
                                f"Google Play purchase callback returned code {purchase_code}.")
                return rec
        if open_only:
            ok("Google Play Billing terbuka! Silakan lanjutkan pembayaran di layar Android.")
            rec["sheet"] = {"confirmed": True, "reason": "billing_flow_opened"}
            rec["status"] = "billing_opened"
            return rec
        # Production observes the post-tap screen while Frida remains attached.
        # Fallback supports existing test doubles that only return launch events.
        rec["sheet"] = (fr["sheet"] if isinstance(fr.get("sheet"), dict) else
                        confirm_zero(password=password, expected_plan=plan, expected_account=email))
        # Preserve the original checkout screen if amount or offer terms
        # are ambiguous; never navigate away before the user can inspect it.
        if rec["sheet"].get("confirmed"):
            # Do not navigate away automatically: Play can still display a
            # delayed payment rejection or need additional user confirmation.
            note("Subscribe was tapped, but the purchase is unverified. "
                 "Leave Google Play open for manual review of its final status.")
        else:
            note("Checkout not confirmed; Google Play remains open for inspection.")
        # launchBillingFlow code 0 and seeing a product name on the Play page
        # DO NOT prove the subscription is active or a free trial is applied.
        reason = rec["sheet"].get("reason")
        if reason == "payment_security_blocked":
            rec["status"] = "checkout_security_blocked"
        elif rec["sheet"].get("confirmed"):
            # Button tap means submitted, not paid or subscription activated.
            rec["status"] = "checkout_requested"
        elif reason in (
                "purchase_unavailable", "ineligible", "already_subscribed",
                "processing", "backup_payment_methods_prompt",
                "today_price_unverified", "trial_duration_unverified",
                "subscribe_button_not_found", "checkout_not_visible",
                "checkout_account_mismatch", "checkout_account_unverified"):
            rec["status"] = reason
        else:
            rec["status"] = "checkout_not_confirmed"
    else:
        rec["status"], rec["error"] = diagnose_launch_failure(fr)
        warn(f"Checkout not opened: {rec['status']}: {rec['error']}")
    return rec


# ---------- CLI entrypoint ----------
def do_check(serial=None):
    global ADB
    ADB = find_adb()
    ok(f"adb：{ADB}")
    pick_device(serial)
    ensure_root()
    ensure_network()
    ensure_frida_server()
    ensure_module_apk()
    ensure_vending()
    try:
        import frida
        ok(f"frida：{frida.__version__}")
    except Exception:
        warn("Frida is missing on this computer; install it with: pip3 install frida")
    ok("Environment preflight passed; ready for further diagnostics")
    return 0


def parse_accounts(path: Path):
    """Legacy account row: email----password----recovery----totp----card----expiry----CVC----holder----postal code."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("----")]
        while len(parts) < 9:
            parts.append("")
        rows.append(parts[:9])
    return rows


def parse_card(parts) -> dict | None:
    """Parse optional card details in columns 5-9 of a legacy account row."""
    if len(parts) < 5 or not parts[4]:
        return None
    return {
        "number": re.sub(r"\s+", "", parts[4]),
        "exp": parts[5] or "",
        "cvc": parts[6] or "",
        "holder": parts[7] or "",
        "zip": parts[8] or "97201",
    }


def main():
    global ADB, SERIAL
    ap = argparse.ArgumentParser(description="Google AI Android offer diagnostics and optional billing CLI")
    ap.add_argument("accounts", nargs="?", help="Legacy accounts file: email----password----recovery----totp")
    ap.add_argument("--account", help="Account: email[:password[:totp]]")
    ap.add_argument("--check", action="store_true", help="Check the Android, ADB and Frida environment")
    ap.add_argument("--list", action="store_true", help="List offer metadata without opening checkout")
    ap.add_argument("--force", action="store_true", help="UNSAFE: bypass Play Store account verification")
    ap.add_argument("--mode", type=int, default=None,
                    help="Subscription replacement mode: 1=TIME_PRORATION 2=CHARGE_PRORATED_PRICE 3=WITHOUT_PRORATION 4=DEFERRED 5=CHARGE_FULL_PRICE")
    ap.add_argument("--old-token", default="",
                    help="Existing subscription purchase token (used with --stack)")
    ap.add_argument("--stack", action="store_true",
                    help="Legacy subscription update using old purchase token; actual renewal terms are set by Google Play")
    ap.add_argument("--serial", default=None, help="ADB serial; required if multiple devices are online")
    ap.add_argument("--activity-method", choices=["auto", "choose", "thread"], default="auto",
                    help="Android Activity lookup: auto=Java.choose then ActivityThread fallback")
    ap.add_argument("--no-add", action="store_true", help="Do not add the account to Android")
    ap.add_argument("--no-switch", action="store_true",
                    help="Verify the current Google Play account without switching automatically")
    ap.add_argument("--plan", default="auto", choices=["auto", "5x", "20x", "pro12", "pro6", "pro6b", "pro6c"],
                    help="auto=query available products; 5x=Ultra 20TB; 20x=Ultra 30TB")
    ap.add_argument("--open-only", action="store_true",
                    help="Buka layar Google Play Billing lalu langsung selesai agar pengguna melanjutkan pembayaran secara manual")
    a = ap.parse_args()

    ADB = find_adb()
    globals()["SKIP_ACCOUNT_CHECK"] = bool(a.force)
    if a.check:
        return do_check(serial=a.serial)

    pick_device(preferred=a.serial)
    ensure_root()
    ensure_network()
    ensure_frida_server()
    ensure_module_apk()
    play_started = ensure_vending(retry_startup=a.list)

    REPORT_DIR.mkdir(exist_ok=True)
    rows = []
    if a.list and not a.account and not a.accounts:
        a.account = "current@device"
    if a.account:
        parts = a.account.split(":")
        rows = [[parts[0], parts[1] if len(parts) > 1 else "", "", parts[2] if len(parts) > 2 else ""]]
    elif a.accounts:
        rows = parse_accounts(Path(a.accounts))
    else:
        ap.print_help()
        return 1

    print(f"\nStarting workflow for {len(rows)} account(s)\n")
    results = []
    for i, row in enumerate(rows, 1):
        email, pw, _rec, sec = row[0], row[1], row[2], row[3]
        card = parse_card(row)
        print(f"\n---- Progress {i}/{len(rows)} ----")
        try:
            if a.list and not play_started:
                rec = {"email": email, "status": "play_store_not_started"}
            else:
                rec = process(email, pw, sec, add=(not a.no_add and not a.list), card=card, plan=a.plan,
                              no_switch=a.no_switch, list_only=a.list, stack=a.stack, old_token=a.old_token,
                              stack_mode=a.mode, activity_method=a.activity_method, open_only=a.open_only)
        except Exception as e:
            warn(f"{type(e).__name__}: {str(e)[:320]}")
            rec = {"email": email, "status": "exception", "error": str(e)[:320],
                   "exception_type": type(e).__name__}
        results.append(rec)
        (REPORT_DIR / report_filename(email)).write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   Result: {rec.get('status')}")

    print("\n" + "=" * 56)
    print("  Summary")
    print("=" * 56)
    for r in results:
        print(f"  {r['email']:<42} {r.get('status')}")
    print(f"\nDetails saved to {REPORT_DIR.resolve()}")
    return 0


entry = main


# The original BillingClient hook and embedded DEX archive are maintained as assets.
# Paths are relative to this file, not the process working directory.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FRIDA_JS = (ASSETS_DIR / "frida" / "billing.js").read_text(encoding="utf-8")
MODULE_B64 = (ASSETS_DIR / "modules" / "module_521.b64").read_text(encoding="ascii").strip()

if __name__ == "__main__":
    sys.exit(entry())





