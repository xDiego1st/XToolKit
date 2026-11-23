#!/usr/bin/env python3
"""Adapter native macOS untuk XToolKit-Diego; memakai ulang ultra0.py tanpa skrip Windows.

Mendukung pemulihan ADB otomatis untuk kasus server macet, `127.0.0.1:16384 offline`,
atau `Connection refused` sebelum menjalankan Step 0–4.
"""
from __future__ import annotations

import argparse
import base64
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from device_diagnostics import recover_adb_connection
from device_selector import auto_select_device, online_serials

ROOT = Path(__file__).resolve().parent
FRIDA_REQUIRED = "16.5.9"
REPORT_DIR = ROOT / "ultra0-report"
EMAIL = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
STAGES = {
    2: ("pro12", "12months-eft", False),
    3: ("pro6", "6months-eft", True),
    4: ("pro6b", "6months-eft-2", True),
}


def stage_command(step: int, serial: str, account: str = "",
                  python: str = sys.executable, open_only: bool = False) -> list[str]:
    if type(step) is not int or step not in range(5):
        raise ValueError("Nomor langkah harus berupa angka bulat antara 0 dan 4")
    if not serial or serial.startswith("-"):
        raise ValueError("Perangkat Android target harus memiliki serial ADB yang valid")
    base = [python, str(ROOT / "ultra0.py")]
    if step == 0:
        return base + ["--check", "--serial", serial]
    if step == 1:
        return base + ["--list", "--no-add", "--no-switch", "--plan", "pro12",
                       "--account", "current@device", "--serial", serial]
    if not EMAIL.fullmatch(account):
        raise ValueError("Diperlukan email Google Play yang terverifikasi sebelum checkout")
    plan, _offer, stack = STAGES[step]
    result = base + ["--account", account, "--no-add", "--no-switch",
                     "--plan", plan, "--serial", serial]
    if stack:
        result.append("--stack")
    if open_only:
        result.append("--open-only")
    return result


def preflight(expected_serial: str = "") -> tuple[str, str]:
    adb = os.environ.get("ADB_PATH") or shutil.which("adb")
    if not adb:
        raise RuntimeError("ADB tidak ditemukan. Pasang Android SDK Platform-Tools.")
    try:
        installed = metadata.version("frida")
    except metadata.PackageNotFoundError:
        installed = None
    if installed != FRIDA_REQUIRED:
        raise RuntimeError(
            f"Frida {FRIDA_REQUIRED} diperlukan (ditemukan {installed or 'belum terpasang'}). "
            "Jalankan sh run-macos.sh untuk menyiapkan lingkungan virtual lokal."
        )
    devices = online_serials(adb)
    if not devices or (expected_serial and expected_serial not in devices):
        # Pulihkan otomatis jika daemon ADB macet atau 127.0.0.1:16384 nyangkut offline
        targets = [expected_serial] if expected_serial and ":" in expected_serial else None
        recovery = recover_adb_connection(
            adb,
            targets=targets,
            force_reset=False,
        )
        if recovery.ok:
            devices = list(recovery.devices)
        else:
            devices = online_serials(adb)
            if not devices:
                raise RuntimeError(recovery.guidance or "Perangkat Android tidak terhubung. Periksa adb devices.")
    if expected_serial and expected_serial not in devices:
        raise RuntimeError("Perangkat Android berubah sejak Step 1; checkout dibatalkan")
    serial = expected_serial or auto_select_device(adb, serials=devices)
    if not serial:
        raise RuntimeError("Lebih dari satu perangkat Android berbeda terdeteksi. Putuskan perangkat tambahan.")
    return adb, serial


def show_android_details(adb: str, serial: str) -> None:
    try:
        result = subprocess.run(
            [adb, "-s", serial, "shell",
             "getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.product.cpu.abi"],
            capture_output=True, text=True, errors="replace", timeout=5, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return
    properties = [line.strip() for line in result.stdout.splitlines()]
    if len(properties) == 3 and all(properties):
        release, sdk, abi = properties
        print(f"Android {release} (SDK {sdk}), ABI {abi}", flush=True)


def run_engine(command: list[str], env: dict[str, str]) -> int:
    return subprocess.call(command, cwd=ROOT, env=env)


def read_play_account(serial: str, env: dict[str, str]) -> str:
    """Baca profil Google Play aktif tanpa mengimpor skrip Windows."""
    command = [sys.executable, str(ROOT / "scripts/runtime-lookup.py"),
               "play-account", "--serial", serial]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, errors="replace", timeout=60)
    if result.returncode:
        raise RuntimeError("Gagal membaca akun Google Play; checkout tidak dimulai")
    lines = [line.removeprefix("RUNTIME_RESULT:") for line in result.stdout.splitlines()
             if line.startswith("RUNTIME_RESULT:")]
    if len(lines) != 1:
        raise RuntimeError("Hasil pembacaan akun Google Play tidak tunggal")
    try:
        account = base64.b64decode(lines[0], validate=True).decode("utf-8").strip().lower()
    except ValueError as error:
        raise RuntimeError("Format teks akun Google Play tidak valid") from error
    return account if EMAIL.fullmatch(account) else ""


def fresh_report(filename: str, since_ns: int) -> dict:
    path = REPORT_DIR / filename
    try:
        if path.stat().st_mtime_ns < since_ns:
            raise RuntimeError("Laporan hasil berasal dari eksekusi sebelumnya")
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("Laporan hasil baru tidak ditemukan") from error
    if not isinstance(obj, dict) or not isinstance(obj.get("status"), str):
        raise RuntimeError("Format laporan hasil tidak valid")
    return obj


def list_offers(serial: str, env: dict[str, str], plan: str = "pro12") -> dict:
    command = stage_command(1, serial)
    if plan != "pro12":
        command[command.index("--plan") + 1] = plan
    start_ns = time.time_ns()
    if run_engine(command, env):
        raise RuntimeError("Gagal mengambil daftar penawaran Google Play")
    report = fresh_report("current.json", start_ns)
    if report["status"] in ("app_not_started", "play_store_not_started"):
        raise RuntimeError(f"Offer listing could not start: {report['status']}")
    if report["status"] != "listed" or not isinstance(report.get("offers"), list):
        raise RuntimeError("Daftar penawaran tidak berhasil dimuat")
    return report


def verified_account(serial: str, env: dict[str, str], report: dict) -> str:
    before = read_play_account(serial, env)
    listed = str(report.get("detected_play_account") or "").strip().lower()
    if listed and not EMAIL.fullmatch(listed):
        raise RuntimeError("Akun Google Play yang dilaporkan tidak valid")
    if before and listed and before != listed:
        raise RuntimeError("Akun Google Play berubah saat pemeriksaan; proses dihentikan")
    account = listed or before
    if not account or not EMAIL.fullmatch(account):
        raise RuntimeError("Gagal memverifikasi akun Google Play")
    return account


def check_offer(report: dict, step: int) -> None:
    _plan, expected, _stack = STAGES[step]
    matches = [offer for offer in report["offers"] if isinstance(offer, dict) and
               offer.get("id") == expected and str(offer.get("micros")) == "0"]
    if not matches:
        raise RuntimeError(
            f"Penawaran Step {step} ({expected}) tidak memiliki fase awal nol (zero-priced first phase)."
        )


def run_stage(step: int, serial: str, env: dict[str, str],
              confirmed: bool = False, active_confirmed: bool = False,
              expected_account: str = "", expected_device: str = "",
              reinject: bool = False) -> int:
    if step >= 2 and expected_device and serial != expected_device:
        raise RuntimeError("Perangkat Android berubah sejak Step 1; checkout dibatalkan")
    if step == 0:
        return run_engine(stage_command(0, serial), env)
    if step == 1:
        report = list_offers(serial, env)
        account = verified_account(serial, env, report)
        print(f"Account {account}", flush=True)
        print(f"Penawaran ditemukan: {len(report['offers'])}", flush=True)
        return 0
    if not confirmed or (step >= 3 and not active_confirmed):
        raise RuntimeError("Explicit checkout and existing-plan confirmations required")
    if step >= 2 and reinject and expected_account:
        account = expected_account.strip().lower()
        current = read_play_account(serial, env)
        if current and current != account:
            raise RuntimeError("Akun Google Play berubah; tidak cocok dengan akun yang dipilih")
        print(f"Account {account}", flush=True)
        print(f"Menyuntikkan ulang Google Play Billing (Step {step})...", flush=True)
        return run_engine(stage_command(step, serial, account, open_only=True), env)
    print("Memeriksa lingkungan Android sebelum melanjutkan...", flush=True)
    if run_engine(stage_command(0, serial), env):
        raise RuntimeError("Cek lingkungan Android gagal; checkout tidak dimulai")
    print("EPLUS_STAGE_DONE:0", flush=True)
    plan, _offer, _stack = STAGES[step]
    report = list_offers(serial, env, plan)
    account = verified_account(serial, env, report)
    if expected_account and account != expected_account.lower():
        raise RuntimeError("Akun Google Play berubah; tidak cocok dengan akun yang dipilih")
    check_offer(report, step)
    if read_play_account(serial, env) != account:
        raise RuntimeError("Akun Google Play berubah sebelum checkout")
    print(f"Account {account}", flush=True)
    print(f"Penawaran Step {step} terverifikasi (fase awal Rp0/$0).", flush=True)
    print("PERHATIAN: Pastikan ketentuan dan status langganan di layar Google Play.", flush=True)
    return run_engine(stage_command(step, serial, account, open_only=(step >= 2)), env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="XToolKit-Diego — Adapter macOS Native")
    parser.add_argument("--step", type=int, required=True, choices=range(5))
    parser.add_argument("--confirmed", action="store_true",
                        help="Izinkan eksekusi langkah checkout yang dipilih")
    parser.add_argument("--active-confirmed", action="store_true",
                        help="Konfirmasi paket aktif untuk Step 3–4")
    parser.add_argument("--expected-account", default="",
                        help="Akun Google Play target yang dipilih")
    parser.add_argument("--expected-device", default="",
                        help="Serial ADB yang diverifikasi pada Step 1")
    parser.add_argument("--reinject", action="store_true",
                        help="Suntik ulang cepat Google Play Billing Step 2–4 bila popup tertutup")
    args = parser.parse_args(argv)
    if args.step >= 2 and not args.confirmed:
        parser.error("Step 2–4 memerlukan flag --confirmed")
    if args.step >= 3 and not args.active_confirmed:
        parser.error("Step 3–4 juga memerlukan flag --active-confirmed")
    if args.expected_account and not EMAIL.fullmatch(args.expected_account.lower()):
        parser.error("Format akun Google Play target tidak valid")
    try:
        adb, serial = preflight(args.expected_device if args.step >= 2 else "")
        env = os.environ.copy()
        env["ADB_PATH"] = adb
        env["PYTHONIOENCODING"] = "utf-8:backslashreplace"
        env["PYTHONUTF8"] = "1"
        print(f"Device {serial}", flush=True)
        show_android_details(adb, serial)
        return run_stage(args.step, serial, env, args.confirmed, args.active_confirmed,
                         args.expected_account, args.expected_device, reinject=args.reinject)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        from tui_core import runtime_error_outcome
        issue = runtime_error_outcome(str(error), args.step)
        if os.environ.get("EPLUS_TUI") == "1":
            print(f"EPLUS_ISSUE:{issue.code}", flush=True)
        print(f"{issue.title}. Saran: {issue.instruction}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
