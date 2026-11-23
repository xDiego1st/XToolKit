# Penafian (Disclaimer) — XToolKit-Diego

[README Utama](README.md) · [Keamanan & Peringatan Pembayaran](SECURITY.md) · [Pusat Dokumentasi](docs/README.md)

**XToolKit-Diego** adalah proyek perangkat lunak independen yang ditujukan untuk keperluan inspeksi teknis, diagnostik koneksi Android, dan edukasi. Harap baca seluruh isi penafian ini serta [Keamanan & Peringatan Pembayaran](SECURITY.md) sebelum menjalankan aplikasi.

> [!CAUTION]
> **Dengan menjalankan XToolKit-Diego, Anda memahami seluruh risiko teknis dan finansial di bawah ini serta bertanggung jawab penuh untuk memverifikasi setiap tindakan pada perangkat Android dan akun Google Play Anda.**

---

## 1. Independensi & Merek Dagang

Proyek ini **bukan produk resmi Google maupun NetEase**, serta tidak berafiliasi dengan, tidak didukung oleh, tidak disponsori oleh, dan tidak disetujui oleh **Google**, **Google One**, **Google Play**, **MuMuPlayer**, maupun **NetEase**. Seluruh nama produk dan merek dagang tetap menjadi milik pemegang hak masing-masing dan hanya disebut untuk menjelaskan layanan pihak ketiga serta syarat kompatibilitas.

---

## 2. Risiko Pembayaran & Langganan

- **Tanpa jaminan promo atau gratis:** XToolKit-Diego **tidak menyediakan, menjual, atau menjamin langganan Google AI Pro gratis**, kelayakan promo, penambahan durasi bulan, keberhasilan transaksi, maupun ketentuan perpanjangan di masa mendatang.
- **Step 2–4 berpotensi menimbulkan biaya nyata:** Tahap **Step 2 (Pro 12 Bulan)**, **Step 3 (Pro +6 Bulan)**, dan **Step 4 (Pro +6 Bulan Ke-2)** membuka layar **Google Play Billing** nyata pada perangkat Android Anda. Pengguna bertanggung jawab penuh memeriksa kebenaran akun Google aktif, nominal tagihan hari ini, biaya perpanjangan berikutnya, mata uang, tanggal perpanjangan, serta syarat pembatalan **sebelum** menyelesaikan pembayaran di layar Android.
- **Tampilan bukan bukti aktivasi:** Tarif fase awal Rp0/US\$0, kode penawaran, respons `Google Play billing flow response: {'ev': 'launched', 'code': 0}`, maupun status lokal (`billing_opened` / `checkout_requested`) **tidak membuktikan** langganan aktif atau perpanjangan berhasil. Selalu periksa status langsung di [Langganan Google Play](https://play.google.com/store/account/subscriptions).
- **Verifikasi kartu terpisah dari total tagihan hari ini:** Meski layar checkout menampilkan **Rp0 / US\$0 hari ini**, Google Payments atau bank penerbit kartu dapat melakukan **penahanan otorisasi sementara (*authorization hold*)** untuk memvalidasi kartu. Pada rangkaian 3 tahap (Step 2, Step 3, dan Step 4), penahanan terpisah sekitar **US\$1 per tahap (3 × US\$1 = US\$3)** atau nominal lain dapat terjadi. Nominal tersebut hanyalah ilustrasi umum, bukan biaya tetap Google dan bukan jaminan kelayakan akun. Penahanan sementara dapat mengurangi saldo tersedia dan umumnya dilepaskan kembali dalam **1–14 hari kerja** tergantung kebijakan bank. Jika terpotong permanen atau tertahan lebih dari 14 hari kerja, hubungi penerbit kartu dan periksa Google Payments. Lihat [Panduan resmi Google Play](https://support.google.com/googleplay/answer/6224192?hl=en).
- **Penghentian aplikasi tidak membatalkan transaksi:** Menekan **`■ Hentikan`** (`x`) atau **`⏻ Keluar`** (`q`) tidak dapat membatalkan pembayaran yang sudah dikonfirmasi di Google Play. Jika proses terhenti di tengah jalan, cek langsung status di Google Play alih-alih mengulang tanpa verifikasi.

---

## 3. Risiko Perangkat, Akun & Data

- **Modifikasi lingkungan Android/emulator:** Aplikasi memanfaatkan **ADB, akses root, Frida 16.5.9, modul injeksi**, serta utilitas persiapan lingkungan. Langkah persiapan (Step 0) atau diagnostik dapat mengubah konfigurasi ADB, Frida, atau jaringan pada emulator yang berpotensi memicu kendala kompatibilitas maupun kehilangan data.
- **Gunakan hanya pada perangkat & akun sah:** Jalankan XToolKit-Diego hanya pada perangkat Android dan akun Google yang Anda miliki atau berwenang mengelolanya. Cadangkan data penting terlebih dahulu dan pahami cara kerja skrip sebelum mengeksekusinya.
- **Kepatuhan hukum & ketentuan layanan:** Penggunaan perangkat lunak dan layanan pihak ketiga wajib mematuhi hukum yang berlaku, ketentuan layanan Google Play, kebijakan keamanan akun, dan lisensi perangkat lunak terkait. **Jangan gunakan aplikasi ini untuk mengakali syarat kelayakan, pemeriksaan keamanan pembayaran, atau pembatasan akun.**
- **Kerahasiaan log & laporan:** Perlakukan seluruh file di `logs/`, `ultra0-report/`, dan `accounts.txt` sebagai data sensitif. Jangan pernah memublikasikan email penuh, kata sandi, kode OTP/2FA, detail kartu, `offerToken`, `purchaseToken`, serial perangkat, maupun laporan mentah yang belum disamarkan.

---

## 4. Ketersediaan & Batasan Tanggung Jawab

Perangkat lunak ini disediakan **apa adanya (*"as is"*) dan sebagaimana tersedia (*"as available"*)**, tanpa jaminan akurasi, kelancaran operasi, kesesuaian untuk tujuan tertentu, kompatibilitas dengan semua sistem operasi/emulator/versi Android, maupun keberlanjutan ketersediaan promo pihak ketiga. API, harga, syarat langganan, serta proteksi keamanan platform dapat berubah sewaktu-waktu tanpa pemberitahuan.

Sejauh diizinkan oleh hukum yang berlaku, pengembang dan kontributor tidak bertanggung jawab atas segala kerugian yang timbul dari penggunaan maupun ketidakmampuan menggunakan perangkat lunak ini, termasuk tagihan yang tidak diinginkan, gangguan akun/langganan, kehilangan data, perubahan konfigurasi perangkat, atau gangguan layanan. **Tidak ada ketentuan dalam dokumen ini yang menghapus atau membatasi tanggung jawab yang menurut hukum tidak boleh dikesampingkan.** Dokumen ini bersifat informatif dan bukan nasihat hukum.

---

## 5. Lisensi & Komponen Pihak Ketiga

Informasi mengenai komponen pihak ketiga serta salinan pemberitahuan lisensi MIT hulu yang dipertahankan tercantum pada [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Pemberitahuan lisensi hulu tersebut tidak secara otomatis menetapkan lisensi MIT pada kontribusi baru yang tidak terkait di dalam proyek ini.
