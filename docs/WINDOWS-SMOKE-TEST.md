# Daftar Periksa Uji Coba Windows + MuMu (Manual) — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Keamanan](../SECURITY.md)

Halaman ini adalah daftar periksa verifikasi perangkat keras manual untuk **Windows + MuMuPlayer**. Pengujian otomatis (unit test / CI) tidak dapat menggantikan pengujian ini karena CI tidak memiliki emulator MuMuPlayer ber-root maupun akun Google Play nyata. **Jangan menjalankan tahap pembayaran Step 2–4 saat melakukan smoke test.**

---

## 1. Persiapan Sebelum Pengujian

- **Windows 10/11** dengan PowerShell 5.1+, Python 3.10+, dan salinan kode **XToolKit-Diego** di folder terpisah.
- **MuMuPlayer** terpasang dari [situs resmi NetEase](https://www.mumuplayer.com/download/), berjalan dengan akses Root dan ADB aktif, serta **Google Play Store** dan **Google One** sudah terpasang.
- Gunakan hanya perangkat dan akun yang memang Anda miliki atau berwenang mengelolanya.
- Pastikan tidak ada transaksi Google Play yang sedang tertunda. Cadangkan data emulator sebelum menjalankan Step 0 karena cek lingkungan dapat mengubah konfigurasi ADB/Frida/jaringan.
- Jangan pernah menyertakan kata sandi, kode OTP, email penuh, token pembelian, log mentah, atau data kartu pada tangkapan layar maupun catatan pengujian.

---

## 2. Daftar Periksa Aman (Tanpa Transaksi Pembayaran)

| Tes | Tindakan | Kriteria Lulus |
| --- | --- | --- |
| **A. Bantuan Peluncur** | Jalankan `.\run-all.ps1 -Help` di PowerShell | Teks bantuan tampil bersih tanpa galat Unicode dan tanpa membuka checkout |
| **B. Deteksi Perangkat** | Jalankan `adb devices` (atau `⚡ Perbaiki ADB` di dasbor) | Serial perangkat Android muncul berstatus `device` (bukan `offline` atau `unauthorized`) |
| **C. Dasbor Textual** | Jalankan `.\run-all.ps1` tanpa parameter | Dasbor **XToolKit-Diego** menampilkan Step 0–4, Status Langsung, Log Teknis Realtime, dan toggle Auto Step 2 tanpa memulai transaksi |
| **D. Cek Penawaran (Step 1)** | Matikan Auto Step 2 ke `MANUAL`, lalu tekan **Cek Perangkat & Penawaran** atau jalankan `.\run-all.ps1 -Step 1 -Debug` | Status menampilkan perangkat/akun yang diperiksa; hasil berupa daftar penawaran, kosong, atau pesan galat yang jelas — tidak pernah membuka checkout |
| **E. Pemulihan ADB, Hentikan & Keluar** | Uji tombol `⚡ Perbaiki ADB` (`a`), `■ Hentikan` (`x`), dan `⏻ Keluar` (`q`) | Proses berhenti bersih, log teknis tetap rapi tanpa noise tombol mode/ADB, dan aplikasi keluar tanpa memulai tahap lain |
| **F. Integritas Direktori** | Pastikan seluruh skrip, aset Frida, dan dokumentasi hadir lengkap | `run-all.ps1`, `tui.py`, `tui_core.py`, `device_diagnostics.py`, `assets/frida/billing.js` tersedia dan dapat dijalankan |

Perintah ringkas di PowerShell:

```powershell
.\run-all.ps1 -Help
adb devices
.\run-all.ps1
.\run-all.ps1 -Step 1 -Debug
```

Jalankan Step 0 **hanya jika diperlukan** (karena dapat memperbaiki ADB/Frida atau konfigurasi emulator):

```powershell
.\run-all.ps1 -Step 0
```

Penawaran yang kosong atau akun yang tidak memenuhi syarat **bukan kegagalan aplikasi**; catat ringkasan diagnostik yang sudah disamarkan. Jangan pernah memakai `-Force` untuk memaksa hasil.

---

## 3. Bukti Pengujian yang Perlu Dicatat

- Versi Windows, versi PowerShell, dan versi Python
- Versi MuMuPlayer / Android serta status perangkat ADB (samarkan serial unik bila perlu)
- Tanggal pengujian
- Status hasil **A–F** (`Lulus` / `Gagal` / `Tidak diuji`) beserta ringkasan galat yang sudah disamarkan bila ada
- Pernyataan eksplisit: **Tidak ada checkout Google Play nyata yang dijalankan selama smoke test**

Lihat juga [README Utama](../README.md), [Keamanan](../SECURITY.md), dan [Catatan Rilis v1.0.1](releases/v1.0.1.md).
