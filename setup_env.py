"""Penyiapan Python, Frida, dan ADB otomatis untuk XToolKit-Diego (Windows).

Langkah:
    1. Periksa versi Python.
    2. Pasang Frida 16.5.9 yang kompatibel.
    3. Temukan ADB atau unduh Android platform-tools resmi.
    4. Hubungkan emulator (termasuk pemulihan ADB offline/nyangkut) lalu cek `ultra0.py --check`.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from device_diagnostics import recover_adb_connection
from device_selector import auto_select_device, online_serials

BASE = Path(__file__).resolve().parent
ADB_CANDIDATES = [
    os.environ.get("ADB_PATH", ""),
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
    r"C:\Program Files (x86)\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"D:\Program Files\Netease\MuMu\nx_main\adb.exe",
    r"D:\Program Files\Netease\MuMu\nx_device\12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu\nx_main\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
]
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


def step(msg):
    print(f"\n▶ {msg}", flush=True)


def ok(msg):
    print(f"   ✅ {msg}", flush=True)


def warn(msg):
    print(f"   ⚠️  {msg}", flush=True)


def die(msg):
    print(f"\n❌ {msg}", flush=True)
    sys.exit(1)


def check_python():
    step("Memeriksa Python")
    v = sys.version_info
    print(f"   {platform.python_version()}  ({platform.architecture()[0]})")
    if v < (3, 9):
        die("Versi Python terlalu lama; pasang Python 3.10 atau lebih baru: https://www.python.org/downloads/")
    ok("Python tersedia")


def install_frida():
    step("Memasang Frida 16.5.9")
    try:
        import frida
        if frida.__version__ == "16.5.9":
            ok(f"Frida {frida.__version__} sudah terpasang")
            return
        warn(f"Versi Frida saat ini {frida.__version__}; beralih ke 16.5.9...")
    except Exception:
        pass

    cmds = [
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", "frida==16.5.9"],
        [sys.executable, "-m", "pip", "install", "--no-cache-dir",
         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "frida==16.5.9"],
    ]
    for c in cmds:
        print("   " + " ".join(c[2:]))
        r = subprocess.run(c, capture_output=True, text=True, errors="ignore")
        if r.returncode == 0:
            break
        print("   " + (r.stderr or r.stdout).strip().splitlines()[-1][:160])
    try:
        import importlib
        import frida
        importlib.reload(frida)
        ok(f"Frida {frida.__version__} terpasang")
    except Exception as e:
        die(f"Gagal memasang Frida: {e}\n   Jalankan: pip install frida==16.5.9")


def adb_is_working(adb: Path | str) -> bool:
    """Pastikan binary ADB benar-benar bisa dijalankan."""
    path = Path(adb)
    if not path.is_file():
        return False
    try:
        result = subprocess.run([str(path), "version"], capture_output=True,
                                text=True, timeout=10, errors="replace")
        return result.returncode == 0 and "Android Debug Bridge" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def user_platform_tools() -> Path:
    parent = os.environ.get("LOCALAPPDATA")
    return (Path(parent) if parent else Path.home() / ".cache") / "xtoolkit-diego" / "platform-tools"


def download_platform_tools() -> str:
    preferred = BASE / "platform-tools"
    fallback = user_platform_tools()
    for directory in (preferred, fallback):
        adb = directory / "adb.exe"
        if adb_is_working(adb):
            ok(f"Menggunakan Android platform-tools yang ada: {adb}")
            return str(adb)

    step("Mengunduh Android platform-tools resmi")
    try:
        with tempfile.TemporaryDirectory(prefix="xtoolkit-platform-tools-") as temp_dir:
            temp_root = Path(temp_dir)
            archive = temp_root / "platform-tools.zip"
            with urllib.request.urlopen(PLATFORM_TOOLS_URL, timeout=180) as response, open(archive, "wb") as target:
                shutil.copyfileobj(response, target)
            with zipfile.ZipFile(archive) as z:
                if "platform-tools/adb.exe" not in z.namelist():
                    raise RuntimeError("Arsip platform-tools resmi tidak berisi adb.exe")
                z.extractall(temp_root)
            source = temp_root / "platform-tools"

            for target in (preferred, fallback):
                try:
                    shutil.copytree(source, target, dirs_exist_ok=True)
                    adb = target / "adb.exe"
                    if adb_is_working(adb):
                        ok(f"Android platform-tools terpasang: {adb}")
                        return str(adb)
                    warn(f"ADB gagal dijalankan dari {target}; mencoba lokasi lain.")
                except OSError as exc:
                    warn(f"Tidak dapat memperbarui {target}: {exc}. Mencoba lokasi pengguna.")
    except (OSError, zipfile.BadZipFile, RuntimeError, TimeoutError) as exc:
        die(f"Gagal memasang Android platform-tools: {exc}. "
            "Pasang dari https://developer.android.com/tools/releases/platform-tools "
            "atau atur variabel lingkungan ADB_PATH.")

    die("ADB masih belum dapat digunakan. Tutup proses yang mengunci adb.exe, "
        "atau atur ADB_PATH ke instalasi SDK platform-tools yang berfungsi.")


def find_adb() -> str:
    step("Mencari ADB")
    candidates = [
        os.environ.get("ADB_PATH", ""),
        str(BASE / "platform-tools" / "adb.exe"),
        str(user_platform_tools() / "adb.exe"),
        *ADB_CANDIDATES,
        shutil.which("adb") or "",
    ]
    for candidate in candidates:
        if candidate and adb_is_working(candidate):
            ok(f"Menggunakan ADB: {candidate}")
            return str(candidate)
    warn("Instalasi ADB belum ditemukan; mengunduh platform-tools resmi.")
    return download_platform_tools()


def connect_emulator(adb):
    """Hubungkan perangkat Android/emulator termasuk pemulihan otomatis saat offline/nyangkut."""
    step("Menghubungkan ke emulator Android")
    devices = online_serials(adb)
    if not devices:
        recovery = recover_adb_connection(adb, force_reset=False, log=lambda m: print(f"   {m}", flush=True))
        devices = list(recovery.devices) if recovery.ok else online_serials(adb)
    if not devices:
        warn("Belum ada perangkat Android online. Jalankan MuMuPlayer dan aktifkan ADB Debugging.")
        return None
    selected = auto_select_device(adb, serials=devices)
    if not selected:
        warn("Lebih dari satu perangkat terhubung. Tentukan -Serial pada run-all.ps1.")
        print("   Perangkat: " + ", ".join(devices))
        return None
    if len(devices) > 1:
        ok(f"Perangkat terpilih otomatis: {selected} dari {', '.join(devices)}")
    else:
        ok(f"Perangkat terhubung: {selected}")
    return selected


def run_check(adb, serial):
    step("Menjalankan pemeriksaan lingkungan (ultra0.py --check)")
    env = dict(os.environ)
    env["ADB_PATH"] = adb
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "ultra0.py", "--check", "--serial", serial], cwd=str(BASE),
                       env=env, capture_output=True, encoding="utf-8", errors="ignore")
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode == 0


def main():
    print("=" * 60)
    print("  XToolKit-Diego — Penyiapan Lingkungan Android")
    print("=" * 60)
    check_python()
    install_frida()
    adb = find_adb()
    os.environ["ADB_PATH"] = str(adb)
    serial = connect_emulator(adb)

    if serial:
        good = run_check(adb, serial)
        print("\n" + "=" * 60)
        if good:
            print("  Lingkungan siap. Jalankan: .\\run-all.ps1")
        else:
            print("  Pemeriksaan lingkungan belum lengkap. Cek peringatan di atas.")
        print("=" * 60)
    else:
        print("\nJalankan MuMuPlayer, aktifkan ADB Debugging, lalu jalankan skrip ini kembali.")


if __name__ == "__main__":
    main()
