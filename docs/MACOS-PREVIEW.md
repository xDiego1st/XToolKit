# Panduan Instalasi & Penggunaan macOS — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Panduan Penggunaan](USAGE.md) · [Keamanan](SAFETY.md)

Peluncur macOS menghadirkan dasbor Textual lengkap **XToolKit-Diego (Step 0–4)** menggunakan mesin Android/ADB/Frida yang sama melalui adapter native `macos_runner.py`.

> [!WARNING]
> **Peringatan Transaksi:** Step **2–4** membuka layar Google Play Billing nyata pada perangkat Android Anda. Fase awal bertarif Rp0/US\$0 **tidak menjamin** kelayakan promo atau perpanjangan gratis. Adapter macOS secara sengaja **tidak menyediakan opsi `--force`** maupun perpindahan akun otomatis demi menjaga keamanan verifikasi akun.

---

## 1. Prasyarat di macOS

- **macOS** dengan aplikasi **Terminal** bawaan (`zsh` atau `bash`). **PowerShell tidak diperlukan** — jangan pernah menjalankan `run-all.ps1`, `.bat`, atau `setup_env.py` di macOS.
- **Python 3.10 atau lebih baru** (disarankan **Python 3.11** untuk kompatibilitas wheel Frida 16.5.9 paling stabil). Peluncur `run-macos.sh` otomatis memilih `python3.11` / `python3.12` / `python3.13` / `python3` yang tersedia dan membuat lingkungan virtual `.venv` secara mandiri.
- **Android SDK Platform-Tools (ADB)** terpasang di `PATH`. Cara termudah melalui Homebrew:

  ```sh
  brew install android-platform-tools
  adb devices
  ```

- **Perangkat Android dengan akses root** atau **emulator Android kompatibel** yang memiliki **Google Play Store** dan **Google One** terpasang:
  - **MuMuPlayer Pro untuk Mac** mendukung **Apple Silicon (M1/M2/M3/M4)**; Mac berbasis Intel memerlukan perangkat Android fisik ber-root atau emulator lain yang kompatibel.
  - Aktifkan **Root** dan **ADB Debugging** di pengaturan emulator/perangkat.

Peluncur macOS otomatis memasang Textual dan **Frida 16.5.9** ke dalam `.venv` lokal, tetapi tidak memasang atau mengonfigurasi emulator Android secara otomatis.

---

## 2. Cara Menjalankan di macOS

### Cara 1 — Melalui Terminal (Disarankan)

Masuk ke folder proyek **XToolKit-Diego** di Terminal, lalu jalankan:

```sh
adb devices
sh run-macos.sh
```

### Cara 2 — Klik Ganda dari Finder

Cukup klik ganda file **`XToolKit-Diego.command`** di dalam folder proyek. File ini otomatis membuka Terminal dan menjalankan `sh run-macos.sh`.

> Jika macOS menampilkan peringatan izin eksekusi saat pertama kali membuka `.command`, jalankan sekali di Terminal:
>
> ```sh
> chmod +x run-macos.sh XToolKit-Diego.command
> ```

---

## 3. Opsi Baris Perintah `run-macos.sh`

```sh
sh run-macos.sh                      # Buka dasbor interaktif XToolKit-Diego (Step 0–4)
sh run-macos.sh --check              # Step 0: Cek lingkungan ADB/root/Frida (dapat ubah konfigurasi emulator)
sh run-macos.sh --list               # Step 1: Daftar penawaran saja tanpa membuka checkout
sh run-macos.sh --step 2             # Buka dasbor dengan Step 2 terpilih (tidak langsung berjalan)
sh run-macos.sh --step 3 --sequence  # Buka dasbor dengan mode berurutan mulai Step 3
sh run-macos.sh --manual-step2       # Buka dasbor dengan mode Auto Step 2 dimatikan
sh run-macos.sh --help               # Tampilkan daftar opsi
```

Untuk keperluan inject ulang billing dari CLI macOS (jika popup billing pada Step 2, 3, atau 4 tertutup):

```sh
.venv/bin/python macos_runner.py --step 2 --confirm-checkout --reinject
.venv/bin/python macos_runner.py --step 3 --confirm-checkout --reinject
.venv/bin/python macos_runner.py --step 4 --confirm-checkout --reinject
```

---

## 4. Apa yang Dikerjakan Adapter Native macOS (`macos_runner.py`)

- **Pemulihan ADB Otomatis di Preflight:** Jika `adb devices` kosong, `offline` (seperti `127.0.0.1:16384 offline`), atau terjadi `Connection refused`, adapter otomatis menjalankan `adb start-server`, membersihkan koneksi nyangkut dengan `adb disconnect`, menyambungkan kembali ke `127.0.0.1:16384`, hingga `adb kill-server` bila diperlukan.
- **Step 0 (Cek Lingkungan):** Memeriksa ketersediaan ADB, perangkat tunggal yang sah, status root, Google Play/Google One, serta kesiapan Frida 16.5.9.
- **Step 1 (Cek Penawaran):** Membaca metadata penawaran yang tersedia pada akun aktif tanpa membuka layar pembayaran.
- **Step 2–4 (Pro 12 Bulan, Pro +6 Bulan, Pro +6 Bulan Ke-2):**
  1. Memverifikasi satu perangkat ADB yang sah dan aktif.
  2. Memeriksa penawaran terbaru untuk tahap yang sesuai serta memastikan akun Google Play cocok (tanpa `--force`).
  3. Menjalankan mode **`--open-only`**: segera setelah respons `Google Play billing flow response: {'ev': 'launched', 'code': 0}` diterima, proses langsung selesai agar Anda bisa melanjutkan pembayaran di layar Android/emulator.
  4. Mendukung **`--reinject`** (melalui tombol **`↻ Inject Ulang Step N`** di dasbor) agar popup Google Play Billing dapat dimunculkan ulang bila tidak sengaja tertutup.

---

## 5. Batasan & Catatan Penting

- Pengujian otomatis (unit test) di macOS hanya menggunakan *mock* dan tidak terhubung ke perangkat Android nyata maupun Google Play Billing.
- Kompatibilitas Frida 16.5.9 dan akses root bergantung pada image Android serta versi emulator yang terpasang di Mac Anda.
- Jangan pernah menganggap kode keluar sukses atau pesan "Billing terbuka" sebagai bukti langganan aktif; selalu cek langsung di **Google Play Store → Pembayaran & langganan → Langganan**.
