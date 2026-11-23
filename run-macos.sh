#!/bin/sh
# Peluncur native macOS untuk XToolKit-Diego.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

usage() {
  printf '%s\n' \
    "XToolKit-Diego — macOS (Dasbor Textual, Step 0–4)" \
    "Penggunaan: sh run-macos.sh [--check | --list | --step N [--sequence] | --sequence | --manual-step2 | --help]" \
    "  (tanpa opsi)    Buka dasbor interaktif XToolKit-Diego" \
    "  --check         Cek lingkungan Android/ADB/Frida (Step 0)" \
    "  --list          Cek daftar penawaran saja (Step 1)" \
    "  --step N        Buka dasbor dengan Step 0..4 terpilih" \
    "  --sequence      Buka dasbor dengan mode berurutan" \
    "  --manual-step2  Nonaktifkan auto-lanjut Step 2 otomatis" \
    "  --help          Tampilkan bantuan ini"
}
if [ "$#" -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then
  usage
  exit 0
fi

MODE=""
case "$#" in
  0) MODE="tui" ;;
  1) case "$1" in
    --check) MODE="check" ;;
    --list) MODE="list" ;;
    --sequence|--manual-step2) MODE="tui" ;;
    *) usage >&2; exit 2 ;;
  esac ;;
  2|3)
    if [ "$1" != "--step" ]; then usage >&2; exit 2; fi
    case "$2" in
      0|1|2|3|4) : ;;
      *) usage >&2; exit 2 ;;
    esac
    if [ "$#" -eq 3 ] && [ "$3" != "--sequence" ] && [ "$3" != "--manual-step2" ]; then
      usage >&2; exit 2
    fi
    MODE="tui" ;;
  *) usage >&2; exit 2 ;;
esac

if [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' "Peluncur ini khusus macOS; di Windows jalankan .\\run-all.ps1" >&2
  exit 2
fi

# Pilih Python 3.11–3.13 jika tersedia (paling stabil untuk wheel Frida 16.5.9), fallback ke python3 >= 3.10
PY_HOST=""
for candidate in python3.11 python3.12 python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PY_HOST="$candidate"
    break
  fi
done
if [ -z "$PY_HOST" ]; then
  printf '%s\n' "Pasang Python 3.10+ (disarankan 3.11) untuk menjalankan XToolKit-Diego." >&2
  exit 2
fi

if ! command -v adb >/dev/null 2>&1; then
  printf '%s\n' "ADB tidak ditemukan. Pasang Android SDK Platform-Tools: brew install android-platform-tools" >&2
  exit 2
fi

if [ ! -x .venv/bin/python ]; then
  printf '%s\n' "Menyiapkan lingkungan virtual Python (.venv) dengan $PY_HOST..."
  "$PY_HOST" -m venv .venv
fi
PYTHON=.venv/bin/python
if ! "$PYTHON" -c "import importlib.metadata as m; import textual, frida; assert m.version('frida') == '16.5.9'" >/dev/null 2>&1; then
  printf '%s\n' "Memasang dependensi Textual dan Frida 16.5.9..."
  "$PYTHON" -m pip install --disable-pip-version-check -r requirements-tui.txt "frida==16.5.9"
fi
export PYTHONIOENCODING=utf-8:backslashreplace
export PYTHONUTF8=1
case "$MODE" in
  check) exec "$PYTHON" macos_runner.py --step 0 ;;
  list)  exec "$PYTHON" macos_runner.py --step 1 ;;
  tui)
    if [ "$#" -eq 0 ]; then exec "$PYTHON" tui.py; fi
    exec "$PYTHON" tui.py "$@" ;;
esac
exit 2
