# Panduan Instalasi Windows — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Panduan macOS](MACOS-PREVIEW.md) · [Keamanan](SAFETY.md)

Panduan ini khusus untuk **Windows**. Jika Anda menggunakan **macOS**, ikuti [Panduan macOS](MACOS-PREVIEW.md) dan jangan jalankan skrip PowerShell (`.ps1`) atau `setup_env.py` di Mac.

---

## 1. Persyaratan Sistem (Windows)

Sebelum menjalankan **XToolKit-Diego**, pastikan komponen berikut siap:

- **Windows 10/11** dengan **PowerShell 5.1 atau lebih baru**.
- **Python 3.10 atau lebih baru** yang dapat dipanggil melalui perintah `python`.
- **MuMuPlayer untuk Windows** (atau perangkat/emulator Android kompatibel) dengan **akses Root** dan **ADB Debugging** aktif.
- Aplikasi **Google Play Store** dan **Google One** terpasang di dalam Android, serta sudah masuk ke akun Google yang ingin diperiksa.
- **ADB** dan **Frida 16.5.9** yang kompatibel. Peluncur Windows dapat membantu menemukan atau mengunduh Platform-Tools dan memasang Frida, tetapi **tidak memasang MuMuPlayer secara otomatis**.

---

## 2. Memasang & Menyiapkan MuMuPlayer

1. Unduh installer MuMuPlayer versi Windows hanya dari [halaman unduhan resmi NetEase MuMuPlayer](https://www.mumuplayer.com/download/).
2. Jalankan instalasi hingga selesai, lalu buka instance Android di MuMuPlayer.
3. Buka pengaturan emulator dan aktifkan:
   - **Akses Root (Root permission)**
   - **ADB Debugging**
4. Di dalam Android, pastikan **Google Play Store** dan **Google One** sudah tersedia dan diperbarui.
5. Login ke akun Google target pada kedua aplikasi tersebut (Google Play Store dan Google One).

---

## 3. Menjalankan XToolKit-Diego di Windows

Buka **PowerShell** di dalam folder proyek XToolKit-Diego, lalu jalankan:

```powershell
.\run-all.ps1
```

Perilaku peluncuran pertama:

- Menjalankan `.\run-all.ps1` **tanpa parameter** langsung membuka **dasbor interaktif Textual XToolKit-Diego** — tidak langsung memulai transaksi atau pembayaran.
- Jika dependensi antarmuka (Textual), ADB, atau Frida 16.5.9 belum tersedia, peluncur dapat membantu menyiapkannya secara otomatis.
- Anda **tidak perlu** menjalankan `setup_env.py` secara terpisah sebelum membuka dasbor.
- Perlu diperhatikan bahwa langkah persiapan lingkungan (Step 0) dapat memasang paket Python, menyalakan ulang server Frida, atau menyesuaikan konfigurasi jaringan/ADB pada emulator.

---

## 4. Memeriksa Koneksi ADB di PowerShell

Jika `adb` sudah terdaftar di `PATH`, Anda dapat memeriksa status perangkat kapan saja:

```powershell
adb devices
```

Hasil yang diharapkan harus berstatus **`device`** (misalnya `127.0.0.1:16384    device` atau `emulator-5554    device`), bukan `offline` atau `unauthorized`.

Jika `adb` belum ada di `PATH`, Anda tetap bisa langsung menjalankan dasbor (`.\run-all.ps1`) atau memanggil executable lokal yang diunduh:

```powershell
.\platform-tools\adb.exe devices
```

Bila perangkat muncul sebagai `127.0.0.1:16384 offline` atau `Connection refused`, buka dasbor XToolKit-Diego lalu tekan tombol **`⚡ Perbaiki ADB`** (pintasan **`a`**) agar aplikasi melakukan pemulihan otomatis (`start-server` → `disconnect` → `connect` → `kill-server` jika perlu).

---

## 5. Alat Setup Manual Windows (Opsional)

Jika Anda membutuhkan perbaikan lingkungan secara manual di luar dasbor, tersedia dua opsi:

```powershell
# Menjalankan cek/setup lingkungan saja tanpa membuka dasbor
.\run-all.ps1 -Step 0

# Atau menggunakan skrip setup Python secara langsung
python setup_env.py
```

Tersedia pula pintasan [`tools/windows/setup-environment.bat`](../tools/windows/README.md) untuk keperluan troubleshooting saja. Hindari menggunakan skrip lama di [`legacy/windows/`](../legacy/windows/README.md) untuk pemakaian harian karena beberapa file `.bat` historis membawa flag `--force` yang melewati verifikasi akun.

---

## Langkah Berikutnya

Setelah dasbor terbuka dan perangkat berstatus **`● TERHUBUNG`**, lanjutkan membaca [Panduan Penggunaan Dasbor & CLI](USAGE.md) atau [Pemecahan Masalah](TROUBLESHOOTING.md) jika menemui kendala.
