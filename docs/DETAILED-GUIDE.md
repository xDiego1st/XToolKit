# Panduan Teknis Mendalam — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Keamanan](../SECURITY.md) · [Referensi Tahapan Step 0–4](ORIGINAL-STEPS.md)

Panduan ini membahas alur teknis **Python + ADB + Frida 16.5.9**, perintah diagnostik langsung, kompatibilitas Android/ART, serta pembacaan laporan secara aman.

> **Keamanan:** Data penawaran atau tarif fase awal Rp0/US\$0 **tidak membuktikan** bahwa promo berlaku untuk akun tersebut, bahwa langganan telah aktif, atau bahwa masa langganan pasti bertambah. Selalu cek harga langsung, biaya perpanjangan, dan catatan langganan aktual di Google Play.

---

## 1. Prasyarat Teknis

- **macOS** (Terminal zsh/bash + `brew install android-platform-tools` + Python 3.10+) atau **Windows** (PowerShell 5.1+ + Python 3.10+ + MuMuPlayer).
- Perangkat atau emulator Android ber-root yang mendukung debugging ADB dan `frida-server` yang kompatibel.
- **Google Play Store** dan **Google One** terpasang dan aktif pada perangkat Android.
- **Frida 16.5.9** dipin secara ketat oleh implementasi proyek (kompatibilitas bergantung pada arsitektur & versi ART Android).
- Akun Google yang sudah login di Google Play Store dan Google One.

---

## 2. Diagnostik ADB & Pemeriksaan Perangkat

### Memeriksa perangkat dari terminal

```sh
adb devices
adb -s 127.0.0.1:16384 shell getprop ro.build.version.release
adb -s 127.0.0.1:16384 shell getprop ro.build.version.sdk
adb -s 127.0.0.1:16384 shell getprop ro.product.cpu.abi
```

Ganti `127.0.0.1:16384` dengan serial yang muncul di `adb devices`. Perangkat yang berstatus `offline` atau `unauthorized` belum siap dipakai.

### Pemulihan otomatis ADB (`device_diagnostics.py`)

XToolKit-Diego memusatkan logika pemulihan ADB di `device_diagnostics.py` (`recover_adb_connection()`), yang dipakai bersama oleh dasbor (`tui.py`), adapter macOS (`macos_runner.py`), dan mesin inti (`ultra0.py`):

1. Menjalankan `adb start-server`.
2. Membaca keluaran `adb devices` (memisahkan perangkat `device`, `offline`, dan `unauthorized`).
3. Jika ada endpoint `offline` (seperti `127.0.0.1:16384 offline`), menjalankan `adb disconnect <serial>` lalu mencoba `adb connect` ke endpoint MuMu/emulator umum (`127.0.0.1:16384`, `127.0.0.1:7555`, dll.).
4. Jika perangkat tetap `offline` atau tidak tersambung, melakukan reset penuh `adb kill-server` → `adb start-server` → `adb connect`.
5. Jika terjadi `Connection refused`, memberikan panduan terarah untuk memastikan emulator berjalan dan ADB Debugging aktif.

### Seleksi perangkat deterministik (`device_selector.py`)

Jika `adb devices` menampilkan beberapa alias seperti `127.0.0.1:16384`, `127.0.0.1:7555`, dan `emulator-5554`, XToolKit-Diego memeriksa boot UUID masing-masing instance dan memperlakukan UUID identik sebagai satu perangkat yang sama. Bila terdapat beberapa kernel Android berbeda, sistem memilih perangkat yang menjalankan/memasang Google One secara unik, dan **tidak menebak** bila tetap ambigu (gunakan `-Serial` / `--serial`).

---

## 3. Setup ADB di Windows (`setup_env.py`)

Khusus Windows PowerShell, bila Anda perlu menyiapkan ADB/Frida secara manual:

```powershell
python --version
python setup_env.py
```

- `setup_env.py` **tidak** memasang MuMuPlayer; pasang MuMuPlayer dari [halaman resmi NetEase](https://www.mumuplayer.com/download/).
- Skrip mencari `ADB_PATH`, folder `platform-tools`, lokasi MuMuPlayer umum, dan `PATH`. Jika harus mengunduh Android SDK Platform-Tools resmi Google, ekstraksi dilakukan di direktori sementara lalu dipasang ke folder proyek atau fallback ke `%LOCALAPPDATA%\google-ai\platform-tools` bila file sedang terkunci (`PermissionError`).
- Di Windows PowerShell, `run-all.ps1` menggunakan `scripts/runtime-lookup.py` untuk penemuan runtime aman-ASCII dan menyetel `PYTHONIOENCODING=utf-8:backslashreplace` serta `PYTHONUTF8=1` guna mencegah crash `UnicodeEncodeError: cp1252`.

---

## 4. Perintah Diagnostik Python Langsung

### Cek lingkungan tanpa transaksi

```sh
# macOS
.venv/bin/python ultra0.py --check --serial 127.0.0.1:16384

# Windows
python ultra0.py --check --serial 127.0.0.1:16384
```

### Daftar penawaran tanpa checkout

```sh
# macOS
.venv/bin/python ultra0.py --account "current@device" --no-add --list --plan pro12 --serial 127.0.0.1:16384

# Windows
python ultra0.py --account "current@device" --no-add --list --plan pro12 --serial 127.0.0.1:16384
```

### Inspeksi Activity (hanya-baca) setelah Google One dibuka

```sh
python scripts/diagnose-activity.py --serial 127.0.0.1:16384
```

Skrip melaporkan `ok` hanya bila berhasil membaca Android `Activity` aktif melalui `ActivityThread`. Perintah ini tidak membuka checkout atau mengubah status langganan.

---

## 5. Strategi Peluncuran Billing (`--open-only` & `--reinject`)

Pada **Step 2, Step 3, dan Step 4**, XToolKit-Diego melewati tahap `Checking today's Google Play checkout total and trial duration` yang rentan lambat atau gagal membaca elemen UI, dengan memakai flag `--open-only` pada `ultra0.py`:

- Saat hook Frida (`assets/frida/billing.js`) memanggil `launchBillingFlow` dan menerima respons:
  ```text
  ✅ Google Play billing flow response: {'ev': 'launched', 'code': 0, 'msg': ''}
  ```
- `ultra0.py` langsung menyimpan status `billing_opened` ke laporan JSON (`ultra0-report/`) dan keluar dengan kode sukses `0`.
- Di dasbor, status langsung tampil **`✓ BILLING SIAP`** dan tombol **`↻ Inject Ulang Step N`** diaktifkan.
- Jika popup Google Play Billing tertutup (*terclose*), menekan **`↻ Inject Ulang Step N`** (atau menjalankan `--reinject` / `-Reinject`) memanggil ulang peluncuran billing untuk tahap yang sama secara instan.

---

## 6. Kompatibilitas Android 15 & Frida

Strategi default pencarian Activity adalah `--activity-method auto`: mencoba `Java.choose()` terlebih dahulu, lalu fallback otomatis ke `ActivityThread.mActivities`. Anda dapat memaksa salah satu metode lewat `-ActivityMethod auto|choose|thread` (Windows) atau `--activity-method auto|choose|thread` (Python).

Pada beberapa image emulator **Android 15 / API 35 x86_64**, `Java.choose()` pada Frida dapat memicu galat `libart.so` / `EnsurePluginLoaded`. Masalah ini adalah kompatibilitas runtime ART/Frida, bukan ketidaklayakan akun Google Play. Fallback `ActivityThread` membantu pada banyak build, tetapi tidak dijamin bekerja pada semua vendor/image Android.

---

## 7. Daftar Kode Status Laporan (`ultra0-report/`)

| Kode Status | Arti & Tindak Lanjut |
| --- | --- |
| `listed` | Daftar penawaran berhasil dibaca; tidak ada checkout yang dibuka |
| `billing_opened` | Google Play Billing berhasil diluncurkan (`code: 0`); lanjutkan pembayaran di Android atau klik **Inject Ulang** jika popup tertutup |
| `checkout_requested` | Status internal lama ketika klik Subscribe dilaporkan; **bukan** bukti langganan aktif |
| `account_unverified` | Email aktif Google Play gagal dibaca; buka profil Play Store dan cek manual |
| `wrong_account` | Akun aktif di Play Store berbeda dengan akun target; jangan lewati pemeriksaan |
| `app_not_started` | Proses Google One gagal dimulai; buka Google One manual di Android lalu ulangi |
| `activity_lookup_failed` | Frida tidak menemukan Activity yang valid; cek kompatibilitas ART/Frida dengan `scripts/diagnose-activity.py` |
| `no_activity` | Aplikasi berjalan tetapi tidak berada di layar depan (*foreground*); tampilkan Google One di layar |
| `billing_flow_error` | `BillingClient` mengembalikan kode error; cek ringkasan `launched` dan `errors` |
| `launch_failed` | Peluncuran dialog checkout tidak terkonfirmasi; bukan bukti pembelian |
| `checkout_security_blocked` | Google Play memblokir transaksi demi keamanan (`OR-REH-04`); hentikan percobaan ulang |

### Membaca ringkasan laporan secara aman (tanpa membocorkan token)

Di PowerShell (Windows):

```powershell
Get-Content .\ultra0-report\current.json -Raw |
    ConvertFrom-Json |
    Select-Object status, error, launched, errors
```

Di Terminal (macOS):

```sh
.venv/bin/python -c "import json,sys; d=json.load(open('ultra0-report/current.json')); print({k:d.get(k) for k in ('status','error','launched','errors')})"
```

**Jangan pernah membagikan isi lengkap file JSON** di `ultra0-report/` karena berisi `offerToken` / `purchaseToken`.

---

## 8. Penanganan Error Keamanan `OR-REH-04`

Jika layar Google Play menampilkan **"Transaksi tidak dapat diselesaikan / Your transaction can't be completed"** dengan kode **`OR-REH-04`**:

- Ini merupakan blokir keamanan akun pembayaran dari Google, **bukan** bug Frida atau penawaran hilang.
- Segera hentikan semua tahap checkout; jangan mencoba Step 3 atau Step 4 sebelum kendala akun selesai.
- Buka [Bantuan Pembayaran Google Play](https://support.google.com/googleplay/answer/1267137), [Google Payments](https://payments.google.com/), dan [Keamanan Akun Google](https://myaccount.google.com/security) untuk menindaklanjuti peringatan atau verifikasi profil pembayaran.
