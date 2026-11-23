# Keamanan & Peringatan Pembayaran — XToolKit-Diego

[README Utama](README.md) · [Penafian Lengkap](DISCLAIMER.md) · [Panduan Keamanan](docs/SAFETY.md) · [Pusat Dokumentasi](docs/README.md)

**XToolKit-Diego** adalah perangkat utilitas independen yang tidak berafiliasi dengan Google. Mesin inti aplikasi memanfaatkan **ADB dengan akses root, `frida-server` 16.5.9, modul billing yang diinjeksikan, serta alur Google Play Billing**. Tinjau seluruh skrip dan pahami dampaknya sebelum dijalankan.

> [!CAUTION]
> **Jangan gunakan proyek ini untuk melewati syarat kelayakan promo, blokir keamanan pembayaran, atau kendali keamanan akun Google.**

---

## 1. Prinsip Penggunaan Aman

| Aspek | Praktik yang Disarankan |
| --- | --- |
| **Utamakan mode cek penawaran** | Gunakan `sh run-macos.sh --list` (macOS), `.\run-all.ps1 -Step 1` (Windows), atau ubah toggle dasbor ke **`○ Auto Step 2: MANUAL`** sebelum menekan pemeriksaan. Mode ini **tidak membuka transaksi pembayaran**, meski cek lingkungan awal (Step 0) tetap dapat menyesuaikan konfigurasi ADB/Frida/emulator. |
| **Waspadai potensi tagihan Step 2–4** | Tahap **Step 2, Step 3, dan Step 4** membuka layar **Google Play Billing** nyata. Jangan pernah menyimpulkan layanan gratis atau perpanjangan berhasil hanya dari daftar penawaran, tarif fase awal Rp0/US\$0, maupun pesan bahwa layar billing sudah terbuka (`billing_opened`). |
| **Jaga validasi identitas akun** | Hindari penggunaan `--force` / `-Force` (karena melewati pemeriksaan kecocokan akun). Adapter macOS (`macos_runner.py`) secara sengaja **tidak menyediakan opsi `--force`**. Pastikan profil Google aktif di **Google Play Store** dan **Google One** sama persis. |
| **Verifikasi mandiri di Google Play** | Setelah menyelesaikan pembayaran pada setiap tahap, selalu periksa status langganan aktif, nominal tagihan, mata uang, tanggal perpanjangan berikutnya, serta syarat pembatalan langsung di **Google Play Store → Pembayaran & langganan → Langganan** ([buka di web](https://play.google.com/store/account/subscriptions)). |
| **Gunakan lingkungan uji yang terkendali** | Langkah persiapan lingkungan (Step 0 / `setup_env.py`) dapat memasang atau memperbarui ADB/Frida serta mengubah konfigurasi emulator. Jalankan hanya pada perangkat/emulator yang Anda kendalikan sendiri. |

---

## 2. Privasi Kredensial, Token & Laporan

Lindungi seluruh data sensitif agar tidak pernah bocor ke tangkapan layar, laporan kendala, maupun komit repositori:

- **Jangan pernah membagikan:** alamat email Google penuh, kata sandi, kode OTP/2FA, informasi kartu pembayaran, serial perangkat unik, `offerToken`, atau `purchaseToken`.
- **Biarkan file lokal tetap privat:** direktori `logs/`, `ultra0-report/`, dan file `accounts.txt` harus selalu tetap berada di mesin lokal dan tidak boleh dipublikasikan.
- **Samarkan sebelum berbagi diagnostik:** saat melaporkan galat teknis, cukup salin ringkasan status yang sudah disamarkan (`status`, `error`, `launched`, `errors`) tanpa isi laporan JSON lengkap.

---

## 3. Penanganan Blokir Keamanan (`OR-REH-04`)

Jika Google Play menampilkan pesan kesalahan keamanan transaksi (seperti **`OR-REH-04`**):

1. **Segera hentikan** seluruh percobaan Step 2–4 dan jangan mengulang inject billing.
2. Periksa pemberitahuan verifikasi resmi di [Google Payments](https://payments.google.com/) dan [Keamanan Akun Google](https://myaccount.google.com/security).
3. Selesaikan verifikasi sesuai instruksi resmi Google sebelum melakukan transaksi apa pun kembali.

---

## 4. Batasan Pengujian Otomatis

Seluruh pengujian otomatis dalam folder `tests/` bersifat **offline (mock)** dan hanya memverifikasi logika antarmuka, pemulihan ADB simulasi, serta validasi laporan tanpa terhubung ke perangkat Android nyata maupun Google Play Billing. Kompatibilitas perangkat, ROM, akses root, dan Frida 16.5.9 dapat berbeda pada setiap mesin.
