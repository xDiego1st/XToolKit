# Draf Pengumuman — XToolKit-Diego

[README Utama](README.md) · [Penafian](DISCLAIMER.md) · [Keamanan](SECURITY.md)

Dokumen ini berisi draf pengumuman siap pakai dalam **Bahasa Indonesia** untuk memperkenalkan **XToolKit-Diego** secara akurat — tanpa menjanjikan langganan gratis, kelayakan promo, atau keberhasilan perpanjangan otomatis. Pastikan isi sesuai dengan [README.md](README.md) dan [DISCLAIMER.md](DISCLAIMER.md) terbaru sebelum dipublikasikan.

---

## 1. Pengumuman Singkat

> **✦ XToolKit-Diego**
>
> Utilitas terminal modern berbahasa Indonesia untuk **macOS** dan **Windows** yang dirancang untuk memeriksa perangkat Android, memulihkan koneksi ADB secara otomatis, meninjau penawaran Google AI Pro melalui Google One & Google Play, serta menjalankan alur **Step 0–4** secara terukur.
>
> **Sorotan fitur:**
> - Antarmuka dasbor Textual bertema gelap (*cyber-slate*) yang modern, rapi, dan responsif.
> - **Pemulihan ADB Otomatis (`⚡ Perbaiki ADB`)** untuk menangani emulator yang nyangkut (`127.0.0.1:16384 offline` atau `Connection refused`).
> - **Auto Step 2 Instan** (dapat diubah antara mode otomatis dan manual).
> - **Peluncuran Billing Cepat & `↻ Inject Ulang Step 2 / 3 / 4`** bila popup Google Play Billing tidak sengaja tertutup (*terclose*).
> - **Log Teknis Realtime** yang bersih, berwarna, dan dilengkapi tombol **`■ Hentikan`**.
>
> **Peringatan Penting:** Step 2–4 membuka layar Google Play Billing nyata dan dapat memicu verifikasi kartu atau biaya sebenarnya. Daftar penawaran, tampilan Rp0/US\$0, maupun terbukanya layar billing bukan bukti kelayakan atau keberhasilan perpanjangan. Selalu cek akun, tagihan, dan tanggal perpanjangan langsung di Google Play.

---

## 2. Pengumuman Teknis

> **XToolKit-Diego** memisahkan antarmuka dasbor Textual (`tui.py` / `tui_core.py`) dari mesin inti Android/ADB/Frida 16.5.9 (`ultra0.py`) melalui peluncur native **`run-macos.sh` / `macos_runner.py`** di macOS dan **`run-all.ps1`** di Windows.
>
> - Jalankan `sh run-macos.sh --list` (macOS) atau `.\run-all.ps1 -Step 1` (Windows) untuk membaca daftar penawaran tanpa membuka layar pembayaran.
> - Logika pemulihan koneksi ADB terpusat di `device_diagnostics.py` (`adb start-server` → `disconnect` → `connect` → reset `kill-server` bila masih `offline`).
> - Tahap pembayaran **Step 2–4** menggunakan mode `--open-only` sehingga langsung selesai ketika Google Play mengembalikan `{'ev': 'launched', 'code': 0}`, dan mendukung `--reinject` / tombol **`↻ Inject Ulang Step N`** apabila jendela billing tertutup sebelum pembayaran selesai.
> - Seluruh pengujian di `tests/` bersifat offline (*mock*) dan tidak pernah mengeksekusi transaksi Google Play nyata. Status lokal tidak menggantikan verifikasi langsung di menu **Langganan Google Play**.

---

## 3. Ringkasan Satu Baris

> **✦ XToolKit-Diego:** Dasbor terminal modern berbahasa Indonesia untuk diagnostik Android, pemulihan ADB otomatis, pemeriksaan penawaran Google AI Pro, dan alur Google Play Billing Step 0–4 dengan Inject Ulang cepat di macOS & Windows.
