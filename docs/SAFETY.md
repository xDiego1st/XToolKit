# Keamanan, Peringatan Pembayaran & Penafian — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Pemecahan Masalah](TROUBLESHOOTING.md)

> [!CAUTION]
> **Proyek tidak resmi. Berpotensi memicu biaya nyata.** Tahap **Step 2–4** membuka alur pembayaran Google Play Billing secara langsung di perangkat Android Anda. Munculnya penawaran dalam daftar, tarif fase awal Rp0/US\$0, atau pesan bahwa layar Google Play Billing telah terbuka **tidak membuktikan** kelayakan akun, aktivasi langganan, masa pakai gratis, maupun perubahan tanggal perpanjangan. Selalu periksa akun yang login, nominal tagihan hari ini, tarif periode berikutnya, dan tanggal perpanjangan langsung di **Google Play** sebelum menyelesaikan pembayaran.

> [!NOTE]
> **Verifikasi kartu dapat menahan saldo sementara meskipun layar checkout menampilkan Rp0/US\$0.** Pada alur Step 2, Step 3, dan Step 4 (total 3 tahap terpisah), Anda dapat melihat hingga **3 kali penahanan otorisasi sementara sekitar US\$1 per tahap (total ~US\$3)** atau nominal lain sesuai wilayah dan kebijakan bank. **Nominal US\$1/US\$3 hanyalah ilustrasi umum, bukan tarif tetap Google dan bukan jaminan kelayakan akun.** Google menjelaskan bahwa otorisasi kartu bukan transaksi pembelian permanen dan biasanya dilepaskan kembali dalam **1–14 hari kerja** tergantung penerbit kartu. Jika tagihan tercatat sebagai transaksi final atau penahanan belum kembali setelah 14 hari kerja, hubungi penerbit kartu dan periksa riwayat di Google Payments. Lihat [Google Play: Biaya, tagihan & otorisasi](https://support.google.com/googleplay/answer/6224192?hl=en).

---

## 1. Penafian (Disclaimer)

**XToolKit-Diego adalah proyek independen dan tidak resmi** — tidak berafiliasi dengan, tidak didukung oleh, dan tidak disetujui oleh Google, Google Play, Google One, NetEase, maupun MuMuPlayer.

Perangkat lunak disediakan **apa adanya (*as is*)**, tanpa jaminan kelayakan promo Google AI Pro, gratis/perpanjangan langganan, hasil transaksi, keamanan akun, maupun kompatibilitas emulator. **Step 2–4 berinteraksi dengan Google Play Billing nyata**, sementara persiapan lingkungan (Step 0) dapat mengubah konfigurasi ADB, Frida, atau jaringan pada perangkat/emulator. Gunakan hanya pada akun dan perangkat yang Anda miliki atau berwenang mengelolanya, patuhi seluruh ketentuan layanan dan hukum yang berlaku, serta verifikasi setiap pembayaran dan tanggal perpanjangan langsung di **[Langganan Google Play](https://play.google.com/store/account/subscriptions)**. Menghentikan aplikasi tidak membatalkan transaksi yang sudah disetujui di Google Play.

---

## 2. Praktik Keamanan Wajib

1. **Lindungi data sensitif:** Jangan pernah membagikan, mengunggah, atau menyertakan file berikut ke publik:
   - Email penuh, kata sandi, kode OTP/2FA, atau detail kartu pembayaran.
   - File laporan mentah di `ultra0-report/` (berisi `offerToken` / `purchaseToken`).
   - File log mentah di `logs/` atau file `accounts.txt`.
2. **Jangan lewati verifikasi akun:** Hindari opsi `-Force` / `--force` (termasuk pintasan lama di `legacy/windows/`). Pastikan akun Google aktif di **Google Play Store** dan **Google One** sama persis sebelum menjalankan Step 1–4.
3. **Verifikasi mandiri setelah setiap tahap:** Jangan langsung melanjutkan dari Step 2 ke Step 3 atau Step 4 sebelum Anda mengecek sendiri bahwa paket aktif dan tanggal perpanjangan di Google Play telah diperbarui.
4. **Hentikan percobaan saat muncul blokir keamanan:** Jika Google Play menampilkan peringatan keamanan seperti **`OR-REH-04`**, segera hentikan semua tahap pembayaran dan selesaikan verifikasi resmi melalui [Google Payments](https://payments.google.com/) dan [Keamanan Akun Google](https://myaccount.google.com/security).

---

## Dokumen Terkait

Baca [Penafian Lengkap (`DISCLAIMER.md`)](../DISCLAIMER.md) dan [Kebijakan Keamanan (`SECURITY.md`)](../SECURITY.md) sebelum penggunaan. Pemberitahuan ini tidak menghapus kewajiban hukum yang tidak dapat dikesampingkan menurut peraturan perundang-undangan yang berlaku.
