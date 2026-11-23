"""Helper murni untuk status, pemetaan langkah, log realtime, dan laporan XToolKit-Diego.

Modul ini tidak memulai transaksi checkout secara langsung.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.metadata
import json
import re
import shutil
import sys
import time

from rich.markup import escape


@dataclass(frozen=True)
class Stage:
    number: int
    label: str
    offer: str


FRIDA_VERSION = "16.5.9"


def needs_setup() -> bool:
    """Pasang alat Python Android hanya jika versi Frida yang dibutuhkan belum tersedia."""
    try:
        return importlib.metadata.version("frida") != FRIDA_VERSION
    except importlib.metadata.PackageNotFoundError:
        return True


STAGES = (
    Stage(0, "Cek Lingkungan", ""),
    Stage(1, "Cek Penawaran", ""),
    Stage(2, "Pro 12 Bulan", "12months-eft"),
    Stage(3, "Pro +6 Bulan", "6months-eft"),
    Stage(4, "Pro +6 Bulan (Ke-2)", "6months-eft-2"),
)


@dataclass(frozen=True)
class Outcome:
    code: str
    title: str
    instruction: str
    can_review: bool = False


MESSAGES = {
    "checkout_account_mismatch": (
        "Checkout menggunakan akun yang berbeda",
        "Periksa akun pada layar checkout Google Play. Tutup checkout, pilih akun yang benar di Play Store dan Google One, lalu jalankan Cek Perangkat & Penawaran lagi.",
    ),
    "checkout_account_unverified": (
        "Akun checkout tidak dapat dibaca",
        "Perluas detail akun pada layar checkout Google Play dan pastikan email sesuai. Tutup checkout lalu jalankan Cek Perangkat & Penawaran kembali.",
    ),
    "listed": ("Penawaran berhasil dimuat", "Data penawaran berhasil dibaca dari Google Play."),
    "billing_opened": (
        "Proses berhasil — silakan lanjutkan pembayaran",
        "Layar Google Play Billing sudah terbuka di perangkat Android. Silakan selesaikan pembayaran di layar emulator. "
        "Bila popup billing tertutup (terclose), klik tombol '↻ Inject Ulang Billing' untuk memunculkannya kembali.",
    ),
    "checkout_requested": (
        "Checkout dikirim — belum terverifikasi",
        "Periksa menu Langganan, tanggal perpanjangan, dan riwayat pembayaran di Google Play sebelum lanjut ke langkah berikutnya.",
    ),
    "checkout_security_blocked": (
        "Google Play meminta verifikasi keamanan akun",
        "Periksa peringatan Keamanan Akun Google dan Google Payments (OR-REH-04). Jangan ulangi checkout dulu.",
    ),
    "already_subscribed": (
        "Paket ini sudah berlangganan aktif",
        "Tidak ada tambahan bulan yang terverifikasi. Periksa tanggal perpanjangan di Google Play; jangan ulangi checkout.",
    ),
    "payment_security_blocked": (
        "Google Play memblokir pembayaran demi keamanan",
        "Periksa peringatan Keamanan Akun Google dan Google Payments (OR-REH-04). Hentikan percobaan ulang.",
    ),
    "today_price_unverified": (
        "Nominal tagihan hari ini belum jelas",
        "Periksa nominal yang harus dibayar hari ini langsung di layar Android sebelum mencoba lagi.",
    ),
    "trial_duration_unverified": (
        "Durasi masa percobaan tidak dapat dipastikan",
        "Periksa durasi dan harga perpanjangan yang ditampilkan Google Play di layar Android.",
    ),
    "ineligible": (
        "Akun ini tidak memenuhi syarat promo",
        "Periksa ketentuan penawaran di Google Play. Mode paksa tidak dapat mengubah kelayakan akun.",
    ),
    "purchase_unavailable": (
        "Item tidak tersedia untuk dibeli di Google Play",
        "Periksa akun, negara Google Play, dan ketersediaan Google One. Tidak ada pembelian yang terkonfirmasi.",
    ),
    "backup_payment_methods_prompt": (
        "Google Play menanyakan metode pembayaran cadangan",
        "Tinjau pengaturan opsional tersebut di Google Play; ini belum mengonfirmasi langganan.",
    ),
    "processing": (
        "Google Play masih memproses transaksi",
        "Periksa riwayat pembayaran di Google Play sebelum mencoba langkah lainnya.",
    ),
    "checkout_not_confirmed": (
        "Checkout belum terkonfirmasi",
        "Periksa status langganan di Google Play sebelum mencoba ulang.",
    ),
    "offer_query_failed": (
        "Gagal memuat daftar penawaran",
        "Buka aplikasi Google One dan Google Play di Android, lalu coba jalankan cek penawaran lagi.",
    ),
    "offer_not_available": (
        "Penawaran tidak tersedia",
        "Gunakan Langkah 1 untuk meninjau daftar penawaran yang tersedia saat ini.",
    ),
    "launch_failed": (
        "Gagal membuka layar checkout Google Play",
        "Aplikasi tidak mengonfirmasi layar checkout terbuka. Periksa Google One, Google Play, dan riwayat pembayaran sebelum mencoba lagi.",
    ),
    "billing_flow_error": (
        "Google Play gagal membuka alur checkout",
        "Google Play mengembalikan kesalahan checkout. Periksa layar Android dan riwayat pembayaran sebelum mengulang langkah ini.",
    ),
    "billing_launch_error": (
        "Tidak dapat memulai checkout Google Play",
        "Terjadi kendala saat membuka checkout. Periksa Google One, layar Android, dan Log Teknis Realtime di bawah.",
    ),
    "activity_lookup_failed": (
        "Gagal mengakses layar aplikasi Google One",
        "Buka kembali Google One ke layar depan dan periksa koneksi ADB/Frida di Log Teknis Realtime.",
    ),
    "no_activity": (
        "Aplikasi Google One belum siap",
        "Tampilkan Google One di layar depan Android lalu jalankan pemeriksaan kembali.",
    ),
    "app_not_started": (
        "Aplikasi Google One gagal dibuka",
        "Restart emulator/perangkat Android dan tunggu boot selesai, lalu jalankan Cek Perangkat & Penawaran dari Langkah 1.",
    ),
    "play_store_not_started": (
        "Google Play Store gagal dibuka",
        "Restart emulator/perangkat Android dan tunggu boot selesai, lalu jalankan Cek Perangkat & Penawaran dari Langkah 1.",
    ),
    "subscription_update_unavailable": (
        "Gagal menyiapkan pembaruan langganan",
        "Token langganan aktif tidak ditemukan. Periksa langganan saat ini di Google Play sebelum mengulang.",
    ),
    "subscribe_button_not_found": (
        "Tombol konfirmasi langganan tidak ditemukan",
        "Periksa tampilan layar Google Play dan harga saat ini di Android. Belum ada perubahan langganan yang terverifikasi.",
    ),
    "checkout_not_visible": (
        "Layar checkout Google Play tidak terlihat",
        "Buka Google Play di Android dan periksa status langganan serta tagihan sebelum mencoba lagi.",
    ),
    "price_unverified": (
        "Harga checkout tidak dapat diverifikasi",
        "Periksa jumlah yang harus dibayar hari ini dan harga perpanjangan di Google Play.",
    ),
    "add_account_failed": (
        "Gagal menambahkan akun Google",
        "Buka Pengaturan Android dan Google Play untuk memeriksa status login akun yang dituju.",
    ),
    "add_account_error": (
        "Penyiapan akun Google terputus",
        "Periksa pengaturan akun Android dan verifikasi akun Google Play yang aktif.",
    ),
    "payment_method_not_confirmed": (
        "Metode pembayaran belum terverifikasi",
        "Periksa metode pembayaran Google Play secara manual. Belum ada transaksi yang terkonfirmasi.",
    ),
    "play_account_switch_failed": (
        "Gagal mengganti akun Google Play",
        "Pilih akun yang diinginkan secara manual di Play Store, lalu jalankan pemeriksaan penawaran kembali.",
    ),
    "frida_missing": (
        "Frida Android belum siap",
        "Di macOS, jalankan ulang lewat `sh run-macos.sh` agar Frida 16.5.9 disiapkan otomatis.",
    ),
    "environment_failed": (
        "Pemeriksaan lingkungan Android belum selesai",
        "Periksa ADB, Google One, dan Frida di Log Teknis Realtime, atau klik 'Perbaiki ADB' sebelum mencoba ulang.",
    ),
    "confirmation_required": (
        "Diperlukan persetujuan untuk melanjutkan",
        "Konfirmasi langkah yang dipilih terlebih dahulu sebelum memulai checkout.",
    ),
    "exception": (
        "Terjadi kesalahan tak terduga",
        "Periksa Log Teknis Realtime untuk detailnya. Jangan ulangi pembayaran sebelum status transaksi pasti.",
    ),
}

CLI_ISSUES = {
    "app_not_started": (
        MESSAGES["app_not_started"][0],
        "Tutup dan buka kembali MuMuPlayer, tunggu Android selesai boot, lalu jalankan Cek Perangkat & Penawaran lagi.",
    ),
    "play_store_not_started": (
        MESSAGES["play_store_not_started"][0],
        "Tutup dan buka kembali MuMuPlayer, tunggu Android selesai boot, lalu jalankan Cek Perangkat & Penawaran lagi.",
    ),
    "device_missing": (
        "Perangkat Android belum terhubung",
        "Jalankan emulator/perangkat Android dengan ADB Debugging aktif, lalu klik 'Perbaiki ADB' atau ulangi pemeriksaan.",
    ),
    "device_mismatch": (
        "Perangkat Android berubah sejak cek penawaran",
        "Hubungkan kembali perangkat yang diverifikasi di Langkah 1 lalu jalankan Cek Perangkat & Penawaran ulang.",
    ),
    "device_ambiguous": (
        "Lebih dari satu perangkat Android terhubung",
        "Putuskan perangkat Android tambahan agar hanya tersisa satu perangkat target, lalu coba lagi.",
    ),
    "app_missing": (
        "Aplikasi Android belum terpasang atau nonaktif",
        "Aktifkan Google Play dan pasang Google One dari Play Store pada perangkat Android target.",
    ),
    "adb_missing": (
        "ADB tidak ditemukan",
        "Jalankan setup_env.py di Windows atau pasang Android SDK Platform-Tools (di macOS: brew install android-platform-tools).",
    ),
    "python_missing": (
        "Python tidak tersedia",
        "Pasang Python 3.10 atau lebih baru lalu mulai ulang XToolKit-Diego.",
    ),
    "runtime_lookup_failed": (
        "Gagal memeriksa informasi perangkat Android",
        "Periksa koneksi ADB (klik 'Perbaiki ADB'), emulator target, dan Log Teknis Realtime.",
    ),
    "account_unavailable": (
        "Akun Google Play tidak dapat diidentifikasi",
        "Buka profil Google Play Store di Android dan pastikan akun target sudah aktif.",
    ),
    "account_mismatch": (
        "Akun Google Play berubah",
        "Pilih akun yang sesuai di Google Play Store dan jalankan pemeriksaan ulang sebelum lanjut.",
    ),
    "offer_query_failed": MESSAGES["offer_query_failed"],
    "offers_unavailable": MESSAGES["offer_query_failed"],
    "report_missing": (
        "Proses tidak menghasilkan laporan",
        "Periksa Log Teknis Realtime untuk detail error yang terjadi.",
    ),
    "account_unverified": (
        "Akun Google Play belum terverifikasi",
        "Buka profil Play Store di Android dan pastikan akun target aktif sebelum melanjutkan.",
    ),
    "wrong_account": (
        "Google Play sedang memakai akun lain",
        "Ganti ke akun Google Play yang dituju lalu jalankan Langkah 1 kembali.",
    ),
}


def cli_issue_outcome(lines: list[str], step: int) -> Outcome | None:
    """Baca kode status terstruktur dari wrapper tanpa menebak keberhasilan checkout."""
    for line in reversed(lines):
        match = re.fullmatch(r"\s*EPLUS_ISSUE:([a-z_]+)\s*", line)
        if not match:
            continue
        code = match.group(1)
        if code in ("listed", "checkout_requested"):
            return None
        entry = CLI_ISSUES.get(code) or MESSAGES.get(code)
        if not entry:
            entry = (
                "Langkah ini tidak dapat diselesaikan",
                "Periksa layar Android dan Log Teknis Realtime. Verifikasi Google Play sebelum mengulang langkah berbayar.",
            )
        title, instruction = entry
        if step >= 2:
            instruction += " Periksa status langganan dan riwayat pembayaran di Google Play sebelum mencoba ulang."
        return Outcome(code, title, instruction, can_review=False)
    return None


def readable_issue_line(line: str) -> str:
    """Ganti penanda protokol internal CLI menjadi teks bahasa Indonesia yang rapi."""
    match = re.fullmatch(r"\s*EPLUS_ISSUE:([a-z_]+)\s*", line)
    if not match:
        if "EPLUS_ISSUE:" in line:
            return "Langkah tidak dapat diselesaikan. Periksa status dan detail pada Log Teknis Realtime."
        return line
    code = match.group(1)
    if code in ("listed", "checkout_requested"):
        return "Hasil langkah diterima. Periksa Google Play untuk memverifikasi status."
    entry = CLI_ISSUES.get(code) or MESSAGES.get(code)
    if not entry:
        return "Langkah tidak dapat diselesaikan. Periksa status dan detail pada Log Teknis Realtime."
    title, guidance = entry
    return f"{title}. Saran: {guidance}"


def runtime_error_outcome(message: str, step: int) -> Outcome:
    """Klasifikasikan error adapter macOS menjadi panduan bahasa Indonesia yang aman."""
    validate_step(step)
    detail = message.lower()
    cases = (
        ("adb is missing", "adb_missing"),
        ("adb tidak ditemukan", "adb_missing"),
        ("no online android device", "device_missing"),
        ("perangkat android tidak terhubung", "device_missing"),
        ("masih offline", "device_missing"),
        ("connection refused", "device_missing"),
        ("android device changed since step 1", "device_mismatch"),
        ("perangkat android berubah", "device_mismatch"),
        ("multiple different android devices", "device_ambiguous"),
        ("lebih dari satu perangkat", "device_ambiguous"),
        ("frida ", "frida_missing"),
        ("google play account changed", "account_mismatch"),
        ("akun google play berubah", "account_mismatch"),
        ("account changed during checks", "account_mismatch"),
        ("google play account lookup", "account_unavailable"),
        ("could not verify google play account", "account_unavailable"),
        ("invalid google play account", "account_unavailable"),
        ("verified google play email", "account_unavailable"),
        ("gagal membaca akun google play", "account_unavailable"),
        ("offer listing could not start: app_not_started", "app_not_started"),
        ("offer listing could not start: play_store_not_started", "play_store_not_started"),
        ("offer listing", "offer_query_failed"),
        ("daftar penawaran", "offer_query_failed"),
        ("zero-priced first phase", "offer_not_available"),
        ("fase awal nol", "offer_not_available"),
        ("new matching report", "report_missing"),
        ("result report", "report_missing"),
        ("result belongs to an older", "report_missing"),
        ("laporan hasil", "report_missing"),
        ("android environment checks failed", "environment_failed"),
        ("cek lingkungan android gagal", "environment_failed"),
        ("confirmations required", "confirmation_required"),
    )
    code = next((name for fragment, name in cases if fragment in detail), "unknown")
    entry = MESSAGES.get(code) or CLI_ISSUES.get(code) or (
        "Langkah tidak dapat diselesaikan",
        "Periksa layar Android dan Log Teknis Realtime. Cek riwayat Google Play sebelum mencoba ulang.",
    )
    title, instruction = entry
    if step >= 2:
        instruction += " Pastikan status langganan dan riwayat pembayaran langsung di Google Play."
    return Outcome(code, title, instruction, can_review=False)


def safe_launch_diagnostic(error: Exception) -> str:
    """Klasifikasikan error peluncuran lokal tanpa membocorkan path atau data sensitif."""
    message = str(error).lower()
    if isinstance(error, FileNotFoundError):
        for filename in ("setup_env.py", "run-all.ps1", "macos_runner.py"):
            if filename in message:
                return f"File penting toolkit tidak ditemukan: {filename}. Pastikan file proyek lengkap."
        return "File lokal yang dibutuhkan tidak ditemukan. Periksa instalasi toolkit."
    if isinstance(error, PermissionError):
        return "Akses ditolak saat menjalankan utilitas lokal. Periksa izin file."
    if "powershell was not found" in message or "powershell tidak ditemukan" in message:
        return "PowerShell tidak ditemukan di sistem. Periksa instalasi PowerShell."
    if isinstance(error, OSError):
        return "Proses lokal gagal dijalankan. Periksa utilitas dan izin eksekusi."
    return "Terjadi kesalahan saat memulai proses. Periksa lingkungan lokal dan koneksi Android."


def validate_step(step: int) -> int:
    if type(step) is not int or not 0 <= step <= 4:
        raise ValueError("Nomor langkah harus berupa angka bulat antara 0 sampai 4")
    return step


def command_for_step(step: int, repo: Path, shell: str | None = None,
                     account: str | None = None, device: str | None = None,
                     reinject: bool = False) -> list[str]:
    validate_step(step)
    if sys.platform == "darwin" and not shell:
        bridge = repo / "macos_runner.py"
        if not bridge.is_file():
            raise FileNotFoundError("macos_runner.py tidak ditemukan")
        command = [sys.executable, str(bridge), "--step", str(step)]
        if step >= 2:
            command.append("--confirmed")
        if step >= 3:
            command.append("--active-confirmed")
        if step >= 2 and reinject:
            command.append("--reinject")
        if step >= 2 and account:
            command.extend(["--expected-account", account])
        if step >= 2 and device:
            command.extend(["--expected-device", device])
        return command
    executable = shell or shutil.which("powershell.exe") or shutil.which("pwsh")
    if not executable:
        raise RuntimeError("PowerShell tidak ditemukan. Pasang PowerShell atau jalankan di Windows.")
    script = repo / "run-all.ps1"
    if not script.is_file():
        raise FileNotFoundError("run-all.ps1 tidak ditemukan di direktori proyek")
    command = [executable, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(script), "-Step", str(step)]
    if step >= 2 and reinject:
        command.append("-Reinject")
    if step >= 2 and account:
        command.extend(["-Email", account])
    if step >= 2 and device:
        command.extend(["-Serial", device])
    return command


def read_fresh_report(directory: Path, step: int, started_at: float,
                      expected_account: str | None = None) -> dict | None:
    """Baca hanya laporan terbaru yang dibuat setelah langkah ini dimulai."""
    validate_step(step)
    if not directory.exists():
        return None
    if step >= 2 and not expected_account:
        return None
    expected = (expected_account or "").strip().lower()
    candidates = []
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime_ns < int(started_at * 1_000_000_000):
                continue
            if step == 1 and path.name != "current.json":
                continue
            if step >= 2 and path.name == "current.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("status"), str):
                if step >= 2 and str(data.get("email", "")).strip().lower() != expected:
                    continue
                candidates.append(data)
        except (OSError, ValueError):
            continue
    return candidates[0] if len(candidates) == 1 else None


def outcome_for_stage(step: int, exit_code: int, report: dict | None) -> Outcome:
    validate_step(step)
    if exit_code != 0 and step == 1 and report and report.get("status") == "exception":
        return Outcome("exception", "Gagal terhubung ke utilitas Android",
                       "Pemeriksaan gagal. Cek Log Teknis Realtime; pastikan Frida, ADB, dan Google One siap lalu coba lagi.")
    if exit_code != 0:
        status = str(report.get("status", "")) if isinstance(report, dict) else ""
        sheet = report.get("sheet") if isinstance(report, dict) else None
        reason = str(sheet.get("reason", "")) if isinstance(sheet, dict) else ""
        code = reason if reason in MESSAGES else status
        issue = CLI_ISSUES.get(code) or MESSAGES.get(code)
        if issue and code not in ("listed", "checkout_requested"):
            title, instruction = issue
            return Outcome(code, title, instruction, can_review=False)
        return Outcome("tool_error", "Langkah berhenti sebelum selesai",
                       "Periksa Log Teknis Realtime dan layar Android sebelum mencoba ulang.")
    if step == 0:
        return Outcome("environment_ok", "Lingkungan Android siap",
                       "ADB, root, Frida, dan aplikasi siap. Anda dapat lanjut memeriksa penawaran.")
    if report is None:
        return Outcome("missing_report", "Hasil tidak dapat diverifikasi",
                       "Laporan hasil terbaru tidak ditemukan. Jangan lanjut ke langkah berikutnya sebelum memastikan status di Google Play.")
    status = str(report.get("status", "unknown"))
    sheet = report.get("sheet")
    reason = str(sheet.get("reason", "")) if isinstance(sheet, dict) else ""
    if status == "billing_opened":
        _, instruction = MESSAGES["billing_opened"]
        return Outcome(
            "billing_opened",
            f"Proses Step {step} berhasil — silakan lanjutkan pembayaran",
            instruction,
            can_review=(step >= 2),
        )
    tapped_with_verified_terms = (
        isinstance(sheet, dict) and sheet.get("confirmed") is True
        and reason == "zero_today_and_duration_verified"
    )
    if status == "checkout_requested" and not tapped_with_verified_terms:
        code = reason if reason in MESSAGES else "checkout_not_confirmed"
    else:
        code = reason if status != "checkout_requested" and reason in MESSAGES else status
    title, instruction = (CLI_ISSUES.get(code) or MESSAGES.get(
        code, ("Hasil langkah tidak dapat dipastikan",
               "Periksa layar Android dan Log Teknis Realtime sebelum mencoba ulang.")))
    return Outcome(code, title, instruction,
                   can_review=(step >= 2 and status == "checkout_requested"
                               and tapped_with_verified_terms))


def mask_email(value: str) -> str:
    m = re.fullmatch(r"([^@\s]+)@([^@\s]+)", value.strip())
    if not m:
        return "Belum terdeteksi"
    name, domain = m.groups()
    return f"{name[:2]}***@{domain}"


def report_summary(report: dict | None) -> str:
    if not report:
        return "Belum ada laporan terbaru"
    offers = report.get("offers")
    if isinstance(offers, list):
        return f"{len(offers)} penawaran ditemukan (kelayakan tetap ditentukan Google Play)"
    status = str(report.get("status", ""))
    entry = CLI_ISSUES.get(status) or MESSAGES.get(status)
    return entry[0] if entry else "Tinjau hasil pada panel Status Langsung"


_SAFE_OFFER_FIELD = re.compile(r"^[A-Za-z0-9._:-]{1,72}$")
_EMAIL_IN_LOG = re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")


def _offer_field(value: object) -> str:
    text = str(value) if value is not None else ""
    return text if _SAFE_OFFER_FIELD.fullmatch(text) else "(tidak tersedia)"


def offer_explorer_lines(report: dict | None, limit: int = 20) -> list[str]:
    """Format daftar fase awal penawaran secara rapi dalam Bahasa Indonesia."""
    if not isinstance(report, dict) or not isinstance(report.get("offers"), list):
        return ["Belum ada rincian penawaran terbaru."]
    items = [o for o in report["offers"] if isinstance(o, dict)]
    if not items:
        return ["Tidak ada penawaran yang dikembalikan. Kelayakan belum diketahui."]
    rows = ["PRODUK / ID PENAWARAN          |  PERIODE  |  HARGA FASE AWAL"]
    for offer in items[:max(0, limit)]:
        product = _offer_field(offer.get("product"))
        offer_id = _offer_field(offer.get("id"))
        period = _offer_field(offer.get("period"))
        micros = offer.get("micros")
        if isinstance(micros, (int, str)) and str(micros) == "0":
            price = "Rp0 / $0 (fase awal)"
        elif isinstance(micros, (int, str)) and str(micros).isdigit():
            price = "Berbayar (mata uang sesuai Play)"
        else:
            price = "Tidak diketahui"
        rows.append(f"{product} / {offer_id}  |  {period}  |  {price}")
    if len(items) > max(0, limit):
        rows.append(f"... {len(items) - max(0, limit)} penawaran lainnya tidak ditampilkan.")
    rows.append("Catatan: harga perpanjangan & kelayakan akhir tetap diverifikasi di Google Play.")
    return rows


def sanitize_log_line(line: str) -> str:
    """Masking email sensitif dan kode internal agar aman tampil di Log Realtime."""
    cleaned = readable_issue_line(line).strip()
    return _EMAIL_IN_LOG.sub(lambda m: mask_email(m.group(1)), cleaned)


def format_realtime_log(line: str, *, level: str | None = None, timestamp: str | None = None) -> str:
    """Format satu baris log menjadi baris Rich warna-warni modern & aman dari injeksi markup."""
    ts = timestamp or time.strftime("%H:%M:%S")
    text = sanitize_log_line(line)
    low = text.lower()

    tag = level
    if not tag:
        if any(tok in low for tok in ("❌", "gagal", "failed", "error", "exception", "tidak ditemukan", "tidak merespons")):
            tag = "ERR"
        elif any(tok in low for tok in ("⚠", "warn", "offline", "connection refused", "menolak koneksi", "peringatan", "caution", "dihentikan")):
            tag = "WARN"
        elif any(tok in low for tok in ("✅", "✔", "berhasil", "online", "pulih", "siap", "terhubung", "tapped subscribe", "verified")):
            tag = "OK"
        elif any(tok in low for tok in ("auto-lanjut", "[auto]", "otomatis lanjut")):
            tag = "AUTO"
        elif any(tok in low for tok in ("adb", "127.0.0.1", "emulator", "serial", "perangkat", "device", "android")):
            tag = "ADB"
        elif any(tok in low for tok in ("frida", "inject", "script", "module", "billing")):
            tag = "FRIDA"
        elif any(tok in low for tok in ("offer", "penawaran", "12months", "6months", "pro12", "pro6")):
            tag = "OFFER"
        elif any(tok in low for tok in ("account", "akun", "play store")):
            tag = "AKUN"
        elif text.startswith("▶") or any(tok in low for tok in ("langkah ", "step ", "tahap ")):
            tag = "STEP"
        else:
            tag = "INFO"

    styles = {
        "OK": ("#34d399", "#d1fae5"),
        "WARN": ("#fbbf24", "#fef3c7"),
        "ERR": ("#fb7185", "#ffe4e6"),
        "AUTO": ("#facc15", "#fef9c3"),
        "ADB": ("#38bdf8", "#e0f2fe"),
        "FRIDA": ("#c084fc", "#f3e8ff"),
        "OFFER": ("#22d3ee", "#cffafe"),
        "AKUN": ("#2dd4bf", "#ccfbf1"),
        "STEP": ("#818cf8", "#e0e7ff"),
        "INFO": ("#94a3b8", "#cbd5e1"),
    }
    badge_color, msg_color = styles.get(tag, ("#94a3b8", "#cbd5e1"))
    safe_text = escape(text)
    return f"[#64748b]{escape(ts)}[/] [bold {badge_color}][{tag:<5}][/] [{msg_color}]{safe_text}[/]"
