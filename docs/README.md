# Pusat Dokumentasi — XToolKit-Diego

[Kembali ke README Utama](../README.md) · [Keamanan & Penafian](SAFETY.md) · [Pemecahan Masalah](TROUBLESHOOTING.md)

Halaman ini merupakan indeks lengkap seluruh dokumentasi **XToolKit-Diego** dalam Bahasa Indonesia. Gunakan daftar di bawah untuk langsung menuju panduan sesuai kebutuhan Anda.

---

## Mulai Cepat

| Panduan | Isi Ringkas |
| --- | --- |
| [**README Utama**](../README.md) | Ringkasan proyek, fitur utama, tangkapan layar dasbor, dan langkah cepat macOS & Windows |
| [**Panduan macOS**](MACOS-PREVIEW.md) | Instalasi Homebrew ADB, menjalankan `sh run-macos.sh` / `XToolKit-Diego.command`, dan batasan macOS |
| [**Panduan Instalasi Windows**](INSTALLATION.md) | Persiapan PowerShell, Python 3.10+, pemasangan MuMuPlayer, dan peluncuran `.\run-all.ps1` |
| [**Panduan Penggunaan Dasbor & CLI**](USAGE.md) | Penjelasan lengkap Step 0–4, Auto Step 2, Inject Ulang Billing, pemulihan ADB, pintasan keyboard, dan opsi CLI |

---

## Keamanan & Pemecahan Masalah

| Panduan | Isi Ringkas |
| --- | --- |
| [**Keamanan, Pembayaran & Penafian**](SAFETY.md) | Peringatan transaksi nyata Step 2–4, penjelasan penahanan otorisasi 3 × US\$1, dan privasi log/akun |
| [**Pemecahan Masalah (Troubleshooting)**](TROUBLESHOOTING.md) | Solusi cepat untuk `127.0.0.1:16384 offline`, `Connection refused`, Frida 16.5.9, popup billing tertutup, hingga `OR-REH-04` |
| [**Panduan Teknis Mendalam**](DETAILED-GUIDE.md) | Kueri langsung Python, diagnostik ActivityThread, kompatibilitas Android 15/Frida, dan pembacaan laporan aman |

---

## Referensi Proyek & Pengujian

| Panduan | Isi Ringkas |
| --- | --- |
| [**Struktur Proyek**](PROJECT.md) | Peta direktori, peran setiap modul Python/peluncur, serta aturan pemeliharaan |
| [**Referensi Tahapan Step 0–4**](ORIGINAL-STEPS.md) | Pemetaan historis Step 0–4, parameter `--plan`/`--stack`, dan skrip legacy Windows |
| [**Catatan Teknis & Kompatibilitas**](AUTHOR-NOTES.md) | Gambaran cara kerja internal BillingClient/Frida serta batasan klaim promosi |
| [**Daftar Periksa Uji Coba Windows**](WINDOWS-SMOKE-TEST.md) | Prosedur verifikasi manual aman (Step 0–1 saja) pada perangkat Windows + MuMuPlayer |
| [**Catatan Rilis v1.0.1**](releases/v1.0.1.md) | Ringkasan pembaruan keamanan, reliabilitas, dan tata cara pembaruan versi |

---

## Dokumen Pendukung di Root Proyek

- [Penafian Lengkap (`DISCLAIMER.md`)](../DISCLAIMER.md)
- [Kebijakan Keamanan (`SECURITY.md`)](../SECURITY.md)
- [Panduan Kontribusi (`CONTRIBUTING.md`)](../CONTRIBUTING.md)
- [Pemberitahuan Lisensi Pihak Ketiga (`THIRD_PARTY_NOTICES.md`)](../THIRD_PARTY_NOTICES.md)
