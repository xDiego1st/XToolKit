# Catatan Teknis & Kompatibilitas — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Panduan Teknis Mendalam](DETAILED-GUIDE.md)

> **Catatan Penting:** Informasi tentang promo historis (seperti penawaran 12 bulan atau tambahan 6 bulan) bersifat ilustratif dan **bukan kebijakan resmi Google** maupun jaminan hak promo saat ini. Server Google Play berhak menerima atau menolak penawaran apa pun meskipun muncul pada respons `BillingClient`.

---

## 1. Gambaran Cara Kerja Internal

Secara garis besar, alur teknis yang dijalankan mesin inti (`ultra0.py` + `assets/frida/billing.js`) pada perangkat Android ber-root adalah:

1. Memeriksa dan memulihkan koneksi ADB (`device_diagnostics.py`) hingga satu perangkat Android berstatus `device`.
2. Memverifikasi akun Google Play yang sedang aktif di perangkat.
3. Membuka aplikasi **Google One** (`com.google.android.apps.subscriptions.red`) dan melampirkan hook **Frida 16.5.9**.
4. Memanggil Android `BillingClient` untuk membaca daftar ID penawaran dan fase harga (Step 1).
5. Pada Step 2–4, meluncurkan dialog **Google Play Billing** (`launchBillingFlow`) dalam mode cepat `--open-only` sehingga begitu respons `{'ev': 'launched', 'code': 0}` diterima, kontrol langsung diserahkan kepada pengguna di layar Android.
6. Menyimpan ringkasan diagnostik ke `ultra0-report/` dan riwayat singkat ke `logs/stage-history/`.

---

## 2. Komponen Pendukung

- **Python 3.10+** (disarankan Python 3.11 di macOS)
- **Android SDK Platform-Tools (ADB)**
- Modul Python **Textual** dan **Frida 16.5.9** beserta `frida-server` yang cocok dengan arsitektur perangkat
- Perangkat atau emulator Android ber-root dengan **Google Play Store** dan **Google One**

---

## 3. Peringatan Keamanan Kode Lama

- Hindari penggunaan file akun mentah (`accounts.txt`) yang menyimpan kata sandi atau data kartu pembayaran dalam teks biasa.
- Jangan memakai opsi `--force` untuk mengabaikan ketidakcocokan akun.
- Jangan memublikasikan file laporan lengkap dari `ultra0-report/` maupun log mentah dari `logs/`.

Baca juga [Panduan Teknis Mendalam](DETAILED-GUIDE.md), [Referensi Tahapan Step 0–4](ORIGINAL-STEPS.md), dan [Kebijakan Keamanan](../SECURITY.md).
