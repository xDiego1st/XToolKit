"""Diagnostik koneksi Android & pemulihan ADB otomatis untuk XToolKit-Diego.

Menangani kasus umum ADB pada Windows dan macOS (termasuk MuMuPlayer):
- Daemon ADB belum berjalan atau macet (`adb start-server` / `adb kill-server`)
- Port emulator (seperti `127.0.0.1:16384`) nyangkut dalam status `offline`
- Gagal koneksi sementara (`Connection refused` / transport basi)
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Callable


FRIDA_REQUIRED = "16.5.9"
GOOGLE_ONE = "com.google.android.apps.subscriptions.red"
GOOGLE_PLAY = "com.android.vending"
SAFE_TEXT = re.compile(r"^[a-zA-Z0-9._:/-]{1,90}$")
TCP_SERIAL = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}$")

DEFAULT_EMULATOR_TARGETS: tuple[str, ...] = (
    "127.0.0.1:16384",  # MuMuPlayer 12 / Pro (macOS & Windows default)
    "127.0.0.1:16416",  # MuMuPlayer instance ke-2
    "127.0.0.1:7555",   # MuMuPlayer 6 / legacy
    "127.0.0.1:5555",   # Emulator Android / BlueStacks / standar TCP ADB
    "127.0.0.1:62001",  # Nox
    "127.0.0.1:21503",  # MEmu
)


@dataclass(frozen=True)
class ConnectionDiagnosis:
    status: str
    headline: str
    details: tuple[str, ...]
    guidance: str


@dataclass(frozen=True)
class ConnectionStatus:
    state: str
    devices: tuple[str, ...] = ()
    offline_devices: tuple[str, ...] = ()
    unauthorized_devices: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdbRecoveryResult:
    ok: bool
    state: str
    devices: tuple[str, ...] = ()
    offline_devices: tuple[str, ...] = ()
    unauthorized_devices: tuple[str, ...] = ()
    headline: str = ""
    guidance: str = ""
    steps: tuple[str, ...] = ()
    connection_refused: bool = False


def _clean(value: str, fallback: str = "tidak diketahui") -> str:
    text = value.strip()
    return text if SAFE_TEXT.fullmatch(text) else fallback


def locate_adb(platform_name: str | None = None) -> str | None:
    """Cari binary ADB yang sudah terpasang tanpa mengunduh apa pun."""
    platform_name = platform_name or sys.platform
    configured = os.environ.get("ADB_PATH")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("adb")
    if found:
        return found
    home = Path.home()
    if platform_name == "win32":
        paths = [
            Path(__file__).resolve().parent / "platform-tools/adb.exe",
            Path(os.environ.get("LOCALAPPDATA") or home / ".cache") / "google-ai/platform-tools/adb.exe",
            home / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
            Path(os.environ.get("LOCALAPPDATA") or home) / "Android/Sdk/platform-tools/adb.exe",
            Path("C:/Program Files/Netease/MuMuPlayer-12.0/shell/adb.exe"),
            Path("C:/Program Files/Netease/MuMuPlayerGlobal-12.0/shell/adb.exe"),
            Path("C:/Program Files (x86)/Netease/MuMuPlayer-12.0/shell/adb.exe"),
            Path("D:/Program Files/Netease/MuMu/nx_main/adb.exe"),
            Path("D:/Program Files/Netease/MuMu/nx_device/12.0/shell/adb.exe"),
            Path("C:/Program Files/Netease/MuMu/nx_main/adb.exe"),
            Path(os.environ.get("PROGRAMFILES") or "C:/Program Files")
            / "Netease/MuMu Player 12/shell/adb.exe",
        ]
    else:
        paths = [
            Path("/opt/homebrew/bin/adb"),
            Path("/usr/local/bin/adb"),
            home / "Library/Android/sdk/platform-tools/adb",
            home / "Android/Sdk/platform-tools/adb",
        ]
    return next((str(path) for path in paths if path.is_file()), None)


def _run(adb: str, args: list[str], timeout: int = 8):
    try:
        return subprocess.run(
            [adb, *args], capture_output=True, text=True, errors="replace",
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_adb_devices(output: str) -> tuple[list[str], list[str], list[str]]:
    """Pisahkan hasil `adb devices` menjadi (online, offline, unauthorized)."""
    online: list[str] = []
    offline: list[str] = []
    unauthorized: list[str] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2 or not SAFE_TEXT.fullmatch(fields[0]):
            continue
        serial, state = fields[0], fields[1]
        if state == "device":
            online.append(serial)
        elif state == "offline":
            offline.append(serial)
        elif state == "unauthorized":
            unauthorized.append(serial)
    return (
        sorted(set(online)),
        sorted(set(offline)),
        sorted(set(unauthorized)),
    )


def configured_targets(extra_targets: tuple[str, ...] | list[str] | None = None) -> tuple[str, ...]:
    """Susun daftar target TCP ADB dengan prioritas MuMu 127.0.0.1:16384."""
    ordered: list[str] = []

    def _add(item: str) -> None:
        cleaned = item.strip()
        if cleaned and SAFE_TEXT.fullmatch(cleaned) and cleaned not in ordered:
            ordered.append(cleaned)

    env_target = os.environ.get("ADB_TARGET", "")
    for item in env_target.split(","):
        if item.strip():
            _add(item)
    if extra_targets:
        for item in extra_targets:
            _add(item)
    for item in DEFAULT_EMULATOR_TARGETS:
        _add(item)
    return tuple(ordered)


def poll_connection() -> ConnectionStatus:
    """Periksa status perangkat ADB saat ini tanpa memaksa reset server."""
    adb = locate_adb()
    if not adb:
        return ConnectionStatus("missing_adb")
    response = _run(adb, ["devices"])
    if response is None or response.returncode:
        return ConnectionStatus("adb_error")
    online, offline, unauthorized = parse_adb_devices(response.stdout)
    if online:
        return ConnectionStatus(
            "connected",
            tuple(online),
            offline_devices=tuple(offline),
            unauthorized_devices=tuple(unauthorized),
        )
    if offline:
        return ConnectionStatus(
            "offline",
            (),
            offline_devices=tuple(offline),
            unauthorized_devices=tuple(unauthorized),
        )
    if unauthorized:
        return ConnectionStatus(
            "unauthorized",
            (),
            offline_devices=tuple(offline),
            unauthorized_devices=tuple(unauthorized),
        )
    return ConnectionStatus("disconnected")


def _sleep_cancelable(seconds: float, cancel_check: Callable[[], bool] | None) -> bool:
    """Tidur singkat yang bisa dibatalkan seketika saat tombol Hentikan ditekan."""
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        if cancel_check and cancel_check():
            return True
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return bool(cancel_check and cancel_check())


def recover_adb_connection(
    adb: str | None = None,
    *,
    targets: tuple[str, ...] | list[str] | None = None,
    force_reset: bool = False,
    log: Callable[[str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> AdbRecoveryResult:
    """Pulihkan koneksi ADB yang nyangkut, offline, atau menolak koneksi.

    Alur pemulihan otomatis:
    1. Pastikan daemon berjalan (`adb start-server`).
    2. Cek `adb devices`; bersihkan entri TCP yang nyangkut `offline` via `adb disconnect`.
    3. Coba hubungkan ulang target emulator (`127.0.0.1:16384` dan port umum lain).
    4. Jika masih `offline`, macet, atau belum online: lakukan reset penuh
       (`adb disconnect` -> `adb kill-server` -> `adb start-server` -> `adb connect` -> `adb devices`).
    5. Klasifikasikan hasil secara jelas (`connected`, `connection_refused`, `still_offline`,
       `unauthorized`, `disconnected`, `cancelled`).
    """
    steps: list[str] = []

    def emit(message: str) -> None:
        steps.append(message)
        if log:
            log(message)

    def cancelled() -> bool:
        return bool(cancel_check and cancel_check())

    def cancelled_result() -> AdbRecoveryResult:
        emit("Pemulihan ADB dihentikan oleh pengguna.")
        return AdbRecoveryResult(
            ok=False,
            state="cancelled",
            headline="Pemulihan ADB dihentikan",
            guidance="Proses pemulihan ADB dibatalkan oleh pengguna.",
            steps=tuple(steps),
        )

    adb_bin = adb or locate_adb()
    if not adb_bin:
        emit("ADB tidak ditemukan di sistem.")
        return AdbRecoveryResult(
            ok=False,
            state="missing_adb",
            headline="ADB tidak ditemukan",
            guidance="Pasang Android SDK Platform-Tools (di macOS: brew install android-platform-tools) lalu coba lagi.",
            steps=tuple(steps),
        )

    if cancelled():
        return cancelled_result()

    emit("ADB: Menjalankan `adb start-server`...")
    start_res = _run(adb_bin, ["start-server"], timeout=12)
    server_stuck = start_res is None or start_res.returncode != 0
    if server_stuck:
        emit("ADB: `adb start-server` tidak merespons — akan melakukan reset server ADB.")
    else:
        emit("ADB: Server ADB aktif (✔).")

    if cancelled():
        return cancelled_result()

    online: list[str] = []
    offline: list[str] = []
    unauthorized: list[str] = []
    if not server_stuck:
        dev_res = _run(adb_bin, ["devices"], timeout=8)
        if dev_res is None or dev_res.returncode != 0:
            server_stuck = True
            emit("ADB: `adb devices` gagal merespons — daemon ADB terdeteksi nyangkut.")
        else:
            online, offline, unauthorized = parse_adb_devices(dev_res.stdout)
            if online and not offline and not force_reset:
                emit(f"ADB: Perangkat sudah terhubung online: {', '.join(online)} (✔).")
                return AdbRecoveryResult(
                    ok=True,
                    state="connected",
                    devices=tuple(online),
                    headline="Perangkat Android terhubung",
                    guidance=f"Terhubung ke {', '.join(online)}.",
                    steps=tuple(steps),
                )
            if offline:
                emit(f"ADB: Terdeteksi perangkat nyangkut OFFLINE: {', '.join(offline)}.")
                for stale in offline:
                    if TCP_SERIAL.fullmatch(stale):
                        emit(f"ADB: Memutus transport offline `adb disconnect {stale}`...")
                        _run(adb_bin, ["disconnect", stale], timeout=6)
                if online and not force_reset:
                    emit(f"ADB: Entri offline dibersihkan; perangkat online: {', '.join(online)} (✔).")
                    return AdbRecoveryResult(
                        ok=True,
                        state="connected",
                        devices=tuple(online),
                        headline="Perangkat Android terhubung",
                        guidance=f"Entri offline dibersihkan. Aktif: {', '.join(online)}.",
                        steps=tuple(steps),
                    )

    # Prioritaskan target dari entri offline yang baru saja dilihat + target default (127.0.0.1:16384 duluan)
    probe_list = configured_targets(
        list(targets or ()) + [s for s in offline if TCP_SERIAL.fullmatch(s)]
    )
    refused_targets: list[str] = []
    saw_offline = bool(offline)

    def _probe_targets(phase_label: str) -> tuple[list[str], list[str], list[str]]:
        nonlocal saw_offline
        for target in probe_list:
            if cancelled():
                return [], [], []
            emit(f"ADB ({phase_label}): Mencoba `adb connect {target}`...")
            conn = _run(adb_bin, ["connect", target], timeout=6)
            combined = ""
            if conn is not None:
                combined = ((conn.stdout or "") + " " + (conn.stderr or "")).strip()
            low = combined.lower()
            if "connection refused" in low or "failed to connect" in low or "unable to connect" in low or "cannot connect" in low:
                if target not in refused_targets:
                    refused_targets.append(target)
                emit(f"ADB: {target} menolak koneksi (Connection refused).")
            elif combined:
                first_line = combined.splitlines()[0].strip()
                emit(f"ADB: {first_line}")
            else:
                emit(f"ADB: Tidak ada respons dari {target}.")

            # Beri jeda singkat untuk jabat tangan ADB (terutama transisi offline -> device)
            if "connected to" in low or "already connected" in low:
                if _sleep_cancelable(0.7, cancel_check):
                    return [], [], []

            check = _run(adb_bin, ["devices"], timeout=8)
            if check is not None and check.returncode == 0:
                cur_on, cur_off, cur_unauth = parse_adb_devices(check.stdout)
                if cur_on:
                    emit(f"ADB: `adb devices` -> {', '.join(cur_on)} [ONLINE ✔]")
                    return cur_on, cur_off, cur_unauth
                if cur_off:
                    saw_offline = True
                    emit(f"ADB: {target} muncul sebagai OFFLINE; membersihkan transport basi...")
                    for stale in cur_off:
                        if TCP_SERIAL.fullmatch(stale):
                            _run(adb_bin, ["disconnect", stale], timeout=6)
                if cur_unauth:
                    return cur_on, cur_off, cur_unauth
        final = _run(adb_bin, ["devices"], timeout=8)
        if final is not None and final.returncode == 0:
            return parse_adb_devices(final.stdout)
        return [], [], []

    # Tahap 1: Coba reconnect lunak (kecuali daemon macet atau diminta reset paksa)
    if not server_stuck and not force_reset:
        online, offline, unauthorized = _probe_targets("Hubungkan Ulang")
        if cancelled():
            return cancelled_result()
        if online:
            return AdbRecoveryResult(
                ok=True,
                state="connected",
                devices=tuple(online),
                offline_devices=tuple(offline),
                unauthorized_devices=tuple(unauthorized),
                headline="Koneksi ADB berhasil dipulihkan",
                guidance=f"Perangkat terhubung: {', '.join(online)}.",
                steps=tuple(steps),
            )
        if unauthorized:
            emit(f"ADB: Perangkat menunggu otorisasi USB Debugging: {', '.join(unauthorized)}.")
            return AdbRecoveryResult(
                ok=False,
                state="unauthorized",
                unauthorized_devices=tuple(unauthorized),
                headline="Perangkat belum diotorisasi",
                guidance="Buka layar Android/MuMu lalu setujui dialog izin USB Debugging.",
                steps=tuple(steps),
            )

    # Tahap 2: Reset penuh daemon ADB untuk mengatasi nyangkut / offline permanen
    if cancelled():
        return cancelled_result()
    emit("ADB: Melakukan reset penuh server (`disconnect` -> `kill-server` -> `start-server`)...")
    _run(adb_bin, ["disconnect"], timeout=6)
    _run(adb_bin, ["kill-server"], timeout=8)
    if _sleep_cancelable(1.0, cancel_check):
        return cancelled_result()
    restart = _run(adb_bin, ["start-server"], timeout=12)
    if restart is None or restart.returncode != 0:
        emit("ADB: Gagal memulai ulang server ADB.")
        return AdbRecoveryResult(
            ok=False,
            state="adb_error",
            headline="Server ADB tidak merespons",
            guidance="Periksa instalasi Android Platform-Tools atau proses ADB yang terkunci, lalu coba lagi.",
            steps=tuple(steps),
        )
    emit("ADB: Server ADB berhasil dimulai ulang (✔).")

    if _sleep_cancelable(0.5, cancel_check):
        return cancelled_result()

    # Cek apakah perangkat USB/emulator langsung muncul setelah server baru aktif
    post_reset = _run(adb_bin, ["devices"], timeout=8)
    if post_reset is not None and post_reset.returncode == 0:
        online, offline, unauthorized = parse_adb_devices(post_reset.stdout)
        if online:
            emit(f"ADB: Perangkat pulih setelah reset server: {', '.join(online)} (✔).")
            return AdbRecoveryResult(
                ok=True,
                state="connected",
                devices=tuple(online),
                offline_devices=tuple(offline),
                unauthorized_devices=tuple(unauthorized),
                headline="Koneksi ADB pulih setelah reset server",
                guidance=f"Perangkat aktif: {', '.join(online)}.",
                steps=tuple(steps),
            )

    # Hubungkan ulang semua target port setelah reset server
    online, offline, unauthorized = _probe_targets("Pasca-Reset")
    if cancelled():
        return cancelled_result()
    if online:
        return AdbRecoveryResult(
            ok=True,
            state="connected",
            devices=tuple(online),
            offline_devices=tuple(offline),
            unauthorized_devices=tuple(unauthorized),
            headline="Koneksi ADB berhasil dipulihkan",
            guidance=f"Perangkat aktif: {', '.join(online)}.",
            steps=tuple(steps),
        )

    # Jika masih offline, tunggu sebentar sekali lagi untuk perangkat yang sedang handshake
    if offline:
        emit(f"ADB: Menunggu perangkat offline ({', '.join(offline)}) menyelesaikan handshake...")
        if _sleep_cancelable(1.5, cancel_check):
            return cancelled_result()
        retry_dev = _run(adb_bin, ["devices"], timeout=8)
        if retry_dev is not None and retry_dev.returncode == 0:
            online, offline, unauthorized = parse_adb_devices(retry_dev.stdout)
            if online:
                emit(f"ADB: Perangkat kini ONLINE: {', '.join(online)} (✔).")
                return AdbRecoveryResult(
                    ok=True,
                    state="connected",
                    devices=tuple(online),
                    headline="Koneksi ADB berhasil dipulihkan",
                    guidance=f"Perangkat aktif: {', '.join(online)}.",
                    steps=tuple(steps),
                )

    if unauthorized:
        return AdbRecoveryResult(
            ok=False,
            state="unauthorized",
            unauthorized_devices=tuple(unauthorized),
            headline="Perangkat membutuhkan izin USB Debugging",
            guidance="Buka layar Android dan ketuk 'Izinkan' pada dialog USB Debugging, lalu klik Perbaiki ADB.",
            steps=tuple(steps),
        )
    if offline or saw_offline:
        primary = offline[0] if offline else probe_list[0]
        emit(f"ADB: Target {primary} masih berstatus offline setelah reset penuh.")
        return AdbRecoveryResult(
            ok=False,
            state="still_offline",
            offline_devices=tuple(offline),
            headline="Perangkat ADB masih offline",
            guidance=(
                f"Target {primary} menolak koneksi atau tetap offline setelah reset ADB server. "
                "Restart instance MuMuPlayer, tunggu Android selesai boot penuh, pastikan ADB Debugging aktif, "
                "lalu klik 'Perbaiki ADB'."
            ),
            steps=tuple(steps),
            connection_refused=bool(refused_targets),
        )
    if refused_targets:
        primary = refused_targets[0]
        emit(f"ADB: Semua port emulator menolak koneksi (termasuk {primary}).")
        return AdbRecoveryResult(
            ok=False,
            state="connection_refused",
            headline="Koneksi ke port emulator ditolak (Connection refused)",
            guidance=(
                f"Port {primary} tidak menerima koneksi ADB. Pastikan MuMuPlayer sudah dibuka "
                "dan selesai boot, aktifkan ADB Debugging di pengaturan emulator, lalu klik 'Perbaiki ADB'."
            ),
            steps=tuple(steps),
            connection_refused=True,
        )
    emit("ADB: Tidak ada perangkat Android online yang terdeteksi.")
    return AdbRecoveryResult(
        ok=False,
        state="disconnected",
        headline="Perangkat Android tidak terhubung",
        guidance="Jalankan MuMuPlayer atau hubungkan ponsel Android ber-root dengan USB Debugging aktif, lalu klik 'Perbaiki ADB'.",
        steps=tuple(steps),
    )


def inspect_connection(platform_name: str | None = None) -> ConnectionDiagnosis:
    """Periksa prasyarat host & Android tanpa mengubah akun atau memulai checkout."""
    platform_name = platform_name or sys.platform
    mac = platform_name == "darwin"
    details = [
        f"Host: {'Terminal macOS' if mac else 'Windows / PowerShell' if platform_name == 'win32' else 'Shell POSIX'}"
    ]
    try:
        frida = metadata.version("frida")
    except metadata.PackageNotFoundError:
        frida = ""
    details.append(
        f"Frida host: {frida or 'belum terpasang'} "
        f"(dibutuhkan {FRIDA_REQUIRED}; tanpa instalasi otomatis)"
    )
    install = (
        "Pasang ADB dengan: brew install android-platform-tools"
        if mac else "Pasang Android SDK Platform-Tools atau aktifkan ADB di MuMu"
    )
    adb = locate_adb(platform_name)
    if not adb:
        return ConnectionDiagnosis(
            "missing_adb", "ADB tidak ditemukan", tuple(details),
            f"{install}. Kemudian buka emulator/perangkat Android ber-root dan coba lagi.",
        )
    details.append(f"ADB: {_clean(adb, 'terpasang (jalur disembunyikan)')}")
    response = _run(adb, ["devices"])
    if response is None or response.returncode != 0:
        return ConnectionDiagnosis(
            "adb_error", "ADB tidak merespons", tuple(details),
            "Server ADB mungkin macet. Klik 'Perbaiki ADB' untuk memulai ulang server dan menghubungkan ulang perangkat.",
        )
    online, offline, unauthorized = parse_adb_devices(response.stdout)
    total_devices = len(online) + len(offline) + len(unauthorized)
    if not online:
        state_list = []
        if offline:
            state_list.append(f"offline ({', '.join(offline)})")
        if unauthorized:
            state_list.append(f"unauthorized ({', '.join(unauthorized)})")
        summary = ", ".join(state_list) or "kosong"
        details.append(f"Perangkat Android: {total_devices} ({summary})")
        if unauthorized:
            fix = "Buka layar Android dan setujui permintaan otorisasi USB Debugging."
        elif offline:
            fix = (
                "Perangkat terdeteksi OFFLINE (seperti 127.0.0.1:16384 offline). "
                "Klik 'Perbaiki ADB' untuk membersihkan transport basi dan menyambungkan ulang otomatis."
            )
        else:
            fix = "Jalankan MuMuPlayer atau hubungkan perangkat Android ber-root, aktifkan ADB Debugging, lalu klik 'Perbaiki ADB'."
        return ConnectionDiagnosis("no_online_device", "Belum ada perangkat Android online", tuple(details), fix)
    if len(online) != 1:
        details.append(f"Transport Android online: {len(online)} ({', '.join(online)})")
        return ConnectionDiagnosis(
            "ambiguous", "Lebih dari satu perangkat Android terdeteksi", tuple(details),
            "Putuskan perangkat tambahan agar hanya tersisa satu perangkat target yang aktif.",
        )
    serial = online[0]
    details.append(f"Serial Android: {_clean(serial)}")
    if offline:
        details.append(f"Catatan: ada entri offline ({', '.join(offline)}) — bisa dibersihkan dengan 'Perbaiki ADB'")
    abi = _run(adb, ["-s", serial, "shell", "getprop", "ro.product.cpu.abi"])
    if abi is not None and abi.returncode == 0:
        details.append(f"ABI Android: {_clean(abi.stdout)}")
    play = _run(adb, ["-s", serial, "shell", "pm", "path", GOOGLE_PLAY])
    play_installed = play is not None and play.returncode == 0 and "package:" in play.stdout
    details.append("Google Play Store: terpasang" if play_installed else "Google Play Store: tidak terdeteksi")
    app = _run(adb, ["-s", serial, "shell", "pm", "path", GOOGLE_ONE])
    installed = app is not None and app.returncode == 0 and "package:" in app.stdout
    details.append("Google One: terpasang" if installed else "Google One: tidak terdeteksi")
    root = _run(adb, ["-s", serial, "shell", "id"])
    if root is not None and root.returncode == 0:
        details.append(
            "Shell ADB: root (uid=0)" if "uid=0(" in root.stdout
            else "Shell ADB: non-root (root mungkin tersedia via su)"
        )
    if not play_installed:
        return ConnectionDiagnosis(
            "missing_google_play", "Google Play Store tidak terdeteksi", tuple(details),
            "Aktifkan Google Play Store atau gunakan image emulator yang memiliki Google Play.",
        )
    if not installed:
        return ConnectionDiagnosis(
            "missing_google_one", "Koneksi Android ditemukan (Google One belum ada)", tuple(details),
            "Pasang aplikasi Google One dari Play Store di perangkat Android target.",
        )
    if frida != FRIDA_REQUIRED:
        return ConnectionDiagnosis(
            "frida_mismatch", "Koneksi Android ditemukan (Frida belum sesuai)", tuple(details),
            f"XToolKit-Diego membutuhkan Frida {FRIDA_REQUIRED}. Jalankan launcher agar lingkungan disiapkan otomatis.",
        )
    return ConnectionDiagnosis(
        "connected", "Koneksi dasar Android siap", tuple(details),
        "Perangkat, ADB, Google Play, dan Google One terdeteksi. Klik tombol Cek Perangkat & Penawaran untuk mulai.",
    )
